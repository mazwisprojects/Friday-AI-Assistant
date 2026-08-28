"""
System Monitor — background metric checks with voice alert support.
Zero subprocess calls on all platforms — uses ctypes/pynvml/psutil/wmi only.
"""
import ctypes
import platform
import time

import psutil

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"

DEFAULT_THRESHOLDS = {
    "cpu":  90.0,
    "ram":  90.0,
    "temp": 85.0,
    "gpu":  95.0,
}

_CPU_STREAK = 3
DEFAULT_COOLDOWNS = {
    "cpu": 1800,
    "ram": 1800,
    "temp": 900,
    "gpu": 900,
}
DEFAULT_HYSTERESIS = {
    "cpu": 10.0,
    "ram": 5.0,
    "temp": 5.0,
    "gpu": 10.0,
}

# ── NVML DLL cache (Windows: nvml.dll, Linux: libnvidia-ml.so.1) ─────────────
_nvml_lib: object = None
_nvml_ok:  object = None   # None=untested  True=works  False=unavailable


def _nvml_gpu() -> float:
    """GPU utilisation via NVML — zero subprocess on all platforms."""
    global _nvml_lib, _nvml_ok
    if _nvml_ok is False:
        return -1.0
    try:
        class _Util(ctypes.Structure):
            _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

        if _nvml_lib is None:
            if _OS == "Windows":
                candidates = ("nvml", r"C:\Windows\System32\nvml.dll")
                _load = ctypes.WinDLL
            else:
                candidates = (
                    "libnvidia-ml.so.1",
                    "libnvidia-ml.so",
                    "libnvidia-ml.dylib",
                )
                _load = ctypes.CDLL
            for name in candidates:
                try:
                    lib = _load(name)
                    lib.nvmlInit_v2()
                    _nvml_lib = lib
                    break
                except Exception:
                    continue

        if _nvml_lib is None:
            _nvml_ok = False
            return -1.0

        dev = ctypes.c_void_p()
        _nvml_lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
        u = _Util()
        _nvml_lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(u))
        _nvml_ok = True
        return float(u.gpu)
    except Exception:
        _nvml_ok = False
        return -1.0


def _get_gpu_usage() -> float:
    # pynvml — subprocess-free, works everywhere if installed
    try:
        import pynvml  # type: ignore
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        return float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
    except Exception:
        pass

    return _nvml_gpu()


def _get_cpu_temp() -> float:
    # psutil — works on Linux; occasionally Windows with proper drivers
    try:
        temps = psutil.sensors_temperatures()
        for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                     "cpu-thermal", "zenpower", "it8688"]:
            if name in temps and temps[name]:
                return temps[name][0].current
        for entries in temps.values():
            if entries:
                return entries[0].current
    except Exception:
        pass

    # Windows: wmi module (pure Python COM, zero subprocess)
    if _OS == "Windows":
        try:
            import wmi  # type: ignore
            w = wmi.WMI(namespace="root/wmi")
            tz = w.MSAcpi_ThermalZoneTemperature()
            if tz:
                return (tz[0].CurrentTemperature / 10.0) - 273.15
        except Exception:
            pass

    return -1.0


def get_system_status() -> dict:
    """Snapshot of current system metrics for the system_status tool."""
    cpu  = psutil.cpu_percent(interval=0.2)
    ram  = psutil.virtual_memory()
    temp = _get_cpu_temp()
    gpu  = _get_gpu_usage()

    boot_time   = psutil.boot_time()
    uptime_secs = time.time() - boot_time
    uptime_h    = int(uptime_secs // 3600)
    uptime_m    = int((uptime_secs % 3600) // 60)

    return {
        "cpu_percent":   round(cpu, 1),
        "ram_percent":   round(ram.percent, 1),
        "ram_used_gb":   round(ram.used   / 1024 ** 3, 1),
        "ram_total_gb":  round(ram.total  / 1024 ** 3, 1),
        "cpu_temp_c":    round(temp, 1) if temp > 0 else None,
        "gpu_percent":   round(gpu,  1) if gpu  >= 0 else None,
        "uptime":        f"{uptime_h}h {uptime_m}m",
        "process_count": len(psutil.pids()),
    }


class SystemMonitor:
    """
    Stateful monitor — cooldown state persists across session reconnections.
    Call check() periodically; returns a [SYSTEM_ALERT] string or None.
    """

    def __init__(self, thresholds: dict | None = None, alerts_enabled: bool = True, muted_categories: set[str] | None = None, cooldowns: dict | None = None):
        self.thresholds   = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.alerts_enabled = alerts_enabled
        self.muted_categories = set(muted_categories or set())
        self.cooldowns = {**DEFAULT_COOLDOWNS, **(cooldowns or {})}
        self._last_alert: dict[str, float] = {}
        self._alert_active: dict[str, bool] = {}
        self._cpu_streak  = 0

    def _can_alert(self, key: str) -> bool:
        return (time.monotonic() - self._last_alert.get(key, 0)) > self.cooldowns.get(key, 300)

    def _record(self, key: str):
        self._last_alert[key] = time.monotonic()

    def configure(self, alerts_enabled: bool | None = None, muted_categories: set[str] | None = None, cooldowns: dict | None = None):
        if alerts_enabled is not None:
            self.alerts_enabled = alerts_enabled
        if muted_categories is not None:
            self.muted_categories = {category.lower() for category in muted_categories}
        if cooldowns is not None:
            self.cooldowns.update(cooldowns)

    def mute_category(self, category: str) -> str:
        category = category.lower().strip()
        if category not in DEFAULT_THRESHOLDS:
            return f"Unknown alert category: {category}. Use cpu, ram, temp, or gpu."
        self.muted_categories.add(category)
        return f"Muted {category.upper()} alerts."

    def unmute_category(self, category: str) -> str:
        category = category.lower().strip()
        self.muted_categories.discard(category)
        return f"Unmuted {category.upper()} alerts."

    def set_alerts_enabled(self, enabled: bool) -> str:
        self.alerts_enabled = enabled
        return f"System alerts {'enabled' if enabled else 'disabled'}."

    def _reset_after_recovery(self, values: dict[str, float]):
        for category, value in values.items():
            threshold = self.thresholds[category]
            hysteresis = DEFAULT_HYSTERESIS[category]
            if value < threshold - hysteresis:
                self._alert_active[category] = False

    def check(self) -> str | None:
        try:
            cpu  = psutil.cpu_percent(interval=None)
            ram  = psutil.virtual_memory().percent
            temp = _get_cpu_temp()
            gpu  = _get_gpu_usage()
        except Exception:
            return None

        values = {"cpu": cpu, "ram": ram, "temp": temp, "gpu": gpu}
        self._reset_after_recovery(values)
        if not self.alerts_enabled:
            return None

        alerts: list[str] = []

        if cpu >= self.thresholds["cpu"]:
            self._cpu_streak += 1
            if self._cpu_streak >= _CPU_STREAK and "cpu" not in self.muted_categories and not self._alert_active.get("cpu", False) and self._can_alert("cpu"):
                alerts.append(
                    f"[SYSTEM_ALERT] CPU usage has been critically high ({cpu:.0f}%) "
                    "for several seconds. Warn the user in their language and suggest "
                    "closing heavy applications."
                )
                self._record("cpu")
                self._alert_active["cpu"] = True
                self._cpu_streak = 0
        else:
            self._cpu_streak = 0

        if ram >= self.thresholds["ram"] and "ram" not in self.muted_categories and not self._alert_active.get("ram", False) and self._can_alert("ram"):
            alerts.append(
                f"[SYSTEM_ALERT] RAM is at {ram:.0f}% — nearly exhausted. "
                "Warn the user in their language and suggest freeing memory."
            )
            self._record("ram")
            self._alert_active["ram"] = True

        if temp > 0 and temp >= self.thresholds["temp"] and "temp" not in self.muted_categories and not self._alert_active.get("temp", False) and self._can_alert("temp"):
            alerts.append(
                f"[SYSTEM_ALERT] CPU temperature is {temp:.0f}°C — above the safe limit. "
                "Warn the user in their language and advise reducing system load "
                "or checking cooling."
            )
            self._record("temp")
            self._alert_active["temp"] = True

        if gpu >= 0 and gpu >= self.thresholds["gpu"] and "gpu" not in self.muted_categories and not self._alert_active.get("gpu", False) and self._can_alert("gpu"):
            alerts.append(
                f"[SYSTEM_ALERT] GPU load is at {gpu:.0f}%. "
                "Briefly inform the user in their language."
            )
            self._record("gpu")
            self._alert_active["gpu"] = True

        return " ".join(alerts) if alerts else None
