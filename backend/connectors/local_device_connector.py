"""
Local-device connector for F.R.I.D.A.Y.

Discovers and tracks devices on the local network: smart-home devices (Kasa),
3D printers (OctoPrint/Moonraker), and paired companion devices. Publishes
normalised LocalDevice events on the central bus.
"""
from __future__ import annotations

import logging
import socket
import time
from typing import Any, Optional

from backend.models import LocalDevice

logger = logging.getLogger(__name__)


class LocalDeviceConnector:
    """Discover and track local devices."""

    def __init__(self, event_bus=None, cache_ttl_seconds: int = 60):
        self._bus = event_bus
        self._cache_ttl = cache_ttl_seconds
        self._last_scan = 0.0
        self._devices: dict[str, LocalDevice] = {}

    def _get_bus(self):
        if self._bus is None:
            from event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    # ---------- public API ----------

    def scan(self, kasa_agent=None, printer_agent=None) -> list[LocalDevice]:
        """Scan for all local devices and publish updates."""
        devices: dict[str, LocalDevice] = {}

        # Smart-home devices
        if kasa_agent is not None:
            try:
                import asyncio
                discovered = asyncio.run(kasa_agent.discover()) if asyncio.iscoroutinefunction(kasa_agent.discover) else kasa_agent.discover()
                for d in discovered or []:
                    dev = LocalDevice(
                        device_id=d.get("ip", d.get("alias", "")),
                        name=d.get("alias") or d.get("model") or "Kasa device",
                        device_type=d.get("device_type", "smart_plug"),
                        address=d.get("ip", ""),
                        status="online",
                        capabilities=self._kasa_capabilities(d),
                        last_seen=self._now(),
                    )
                    devices[dev.device_id] = dev
            except Exception as exc:
                logger.debug("Kasa scan failed: %s", exc)

        # 3D printers
        if printer_agent is not None:
            try:
                for host, printer in (printer_agent.printers or {}).items():
                    dev = LocalDevice(
                        device_id=host,
                        name=printer.name or host,
                        device_type="3d_printer",
                        address=host,
                        status="online",
                        capabilities=["print", "monitor", "temperature"],
                        last_seen=self._now(),
                    )
                    devices[host] = dev
            except Exception as exc:
                logger.debug("Printer scan failed: %s", exc)

        self._devices = devices
        self._last_scan = time.time()

        if devices:
            self._get_bus().publish_simple("device.discovered", {
                "count": len(devices),
                "devices": [d.to_dict() for d in devices.values()],
            })
        return list(devices.values())

    def get_devices(self) -> list[LocalDevice]:
        return list(self._devices.values())

    def is_port_open(self, host: str, port: int, timeout: float = 2.0) -> bool:
        """Check if a TCP port is open on a host."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (OSError, socket.timeout):
            return False

    # ---------- helpers ----------

    @staticmethod
    def _kasa_capabilities(device_info: dict) -> list[str]:
        caps = ["on", "off"]
        if device_info.get("is_dimmable"):
            caps.append("brightness")
        if device_info.get("is_color"):
            caps.append("color")
        if device_info.get("has_emeter"):
            caps.append("energy_monitor")
        return caps

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S")


_LOCAL_DEVICE_CONNECTOR: Optional[LocalDeviceConnector] = None


def get_local_device_connector() -> LocalDeviceConnector:
    global _LOCAL_DEVICE_CONNECTOR
    if _LOCAL_DEVICE_CONNECTOR is None:
        _LOCAL_DEVICE_CONNECTOR = LocalDeviceConnector()
    return _LOCAL_DEVICE_CONNECTOR
