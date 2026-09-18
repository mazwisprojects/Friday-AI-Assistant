"""Per-device live runtime management for Friday."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DeviceRuntime:
    device_id: str
    device_type: str
    audio_loop: Any
    loop_task: asyncio.Task | None = None


class RuntimeManager:
    """Own one live AudioLoop per connected device while sharing services elsewhere."""

    def __init__(self):
        self._runtimes: dict[str, DeviceRuntime] = {}

    def get(self, device_id: str) -> DeviceRuntime | None:
        return self._runtimes.get(device_id)

    def all(self) -> list[DeviceRuntime]:
        return list(self._runtimes.values())

    def add(self, device_id: str, device_type: str, audio_loop: Any, loop_task: asyncio.Task) -> DeviceRuntime:
        runtime = DeviceRuntime(device_id, device_type, audio_loop, loop_task)
        self._runtimes[device_id] = runtime
        return runtime

    def remove(self, device_id: str) -> DeviceRuntime | None:
        return self._runtimes.pop(device_id, None)

    def stop(self, device_id: str) -> bool:
        runtime = self.remove(device_id)
        if not runtime:
            return False
        try:
            runtime.audio_loop.stop()
        except Exception:
            logger.exception("Failed stopping runtime for %s", device_id)
        if runtime.loop_task and not runtime.loop_task.done():
            runtime.loop_task.cancel()
        return True

    def stop_all(self) -> None:
        for device_id in list(self._runtimes):
            self.stop(device_id)

    def check_health(self) -> list[dict]:
        """Return a list of unhealthy runtimes for monitoring.

        A runtime is unhealthy if its loop_task is done but was not cancelled.
        This indicates the AudioLoop crashed rather than being stopped cleanly.
        """
        problems = []
        for runtime in self.all():
            task = runtime.loop_task
            if task is None:
                problems.append({
                    "device_id": runtime.device_id,
                    "device_type": runtime.device_type,
                    "issue": "no_task",
                })
            elif task.done() and not task.cancelled():
                problems.append({
                    "device_id": runtime.device_id,
                    "device_type": runtime.device_type,
                    "issue": "crashed",
                    "exception": task.exception() if not task.cancelled() else None,
                })
        return problems
