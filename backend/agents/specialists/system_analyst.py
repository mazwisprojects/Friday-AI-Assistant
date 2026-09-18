"""
System analyst agent for F.R.I.D.A.Y.

Monitors system health, resource usage, and performance trends.
Publishes anomalies to the event bus.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SystemAnalystAgent:
    """Monitor system health and detect performance anomalies."""

    def __init__(self, event_bus=None, history_size: int = 60):
        self._bus = event_bus
        self._history: dict[str, deque] = {
            "cpu": deque(maxlen=history_size),
            "ram": deque(maxlen=history_size),
            "gpu": deque(maxlen=history_size),
        }
        self._baseline: dict[str, float] = {}

    def _get_bus(self):
        if self._bus is None:
            from event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    def record_sample(self, cpu_percent: float, ram_percent: float,
                      gpu_percent: float | None = None) -> None:
        """Record a system metrics sample."""
        now = time.time()
        self._history["cpu"].append((now, cpu_percent))
        self._history["ram"].append((now, ram_percent))
        if gpu_percent is not None:
            self._history["gpu"].append((now, gpu_percent))

    def check_health(self, cpu_percent: float, ram_percent: float,
                     gpu_percent: float | None = None,
                     cpu_temp: float | None = None) -> dict[str, Any]:
        """Check current system health and detect anomalies."""
        self.record_sample(cpu_percent, ram_percent, gpu_percent)
        findings: list[dict[str, Any]] = []

        # CPU checks
        if cpu_percent > 90:
            findings.append({"type": "cpu_high", "severity": "warning",
                             "message": f"CPU usage critical: {cpu_percent:.0f}%"})
        elif cpu_percent > 75:
            findings.append({"type": "cpu_elevated", "severity": "info",
                             "message": f"CPU usage elevated: {cpu_percent:.0f}%"})

        # RAM checks
        if ram_percent > 90:
            findings.append({"type": "ram_high", "severity": "warning",
                             "message": f"RAM usage critical: {ram_percent:.0f}%"})
        elif ram_percent > 80:
            findings.append({"type": "ram_elevated", "severity": "info",
                             "message": f"RAM usage elevated: {ram_percent:.0f}%"})

        # Temperature checks
        if cpu_temp is not None and cpu_temp > 85:
            findings.append({"type": "temp_high", "severity": "critical",
                             "message": f"CPU temperature critical: {cpu_temp:.0f}°C"})

        # Trend analysis
        trend = self._analyse_trends()
        if trend.get("cpu_increasing"):
            findings.append({"type": "cpu_trend", "severity": "info",
                             "message": "CPU usage trending upward"})

        result = {
            "ok": True,
            "cpu_percent": cpu_percent,
            "ram_percent": ram_percent,
            "gpu_percent": gpu_percent,
            "cpu_temp": cpu_temp,
            "findings": findings,
            "trend": trend,
            "healthy": not any(f["severity"] in ("warning", "critical") for f in findings),
        }

        for f in findings:
            if f["severity"] in ("warning", "critical"):
                self._get_bus().publish_simple("anomaly.detected", {
                    "category": "system",
                    "title": f["type"],
                    "description": f["message"],
                    "severity": f["severity"],
                })

        return result

    def _analyse_trends(self) -> dict[str, Any]:
        """Analyse metric trends from history."""
        trends: dict[str, Any] = {}
        for metric in ("cpu", "ram"):
            values = self._history.get(metric, deque())
            if len(values) >= 5:
                recent = [v for _, v in list(values)[-5:]]
                older = [v for _, v in list(values)[-10:-5]] if len(values) >= 10 else recent
                if older:
                    avg_recent = sum(recent) / len(recent)
                    avg_older = sum(older) / len(older)
                    trends[f"{metric}_increasing"] = avg_recent > avg_older + 10
                    trends[f"{metric}_avg"] = round(avg_recent, 1)
        return trends

    def get_history(self) -> dict[str, list]:
        """Return metric history for dashboards."""
        return {k: list(v) for k, v in self._history.items()}
