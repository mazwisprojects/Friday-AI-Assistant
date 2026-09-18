"""Small persistent store for device conversation handoffs."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class HandoffStore:
    def __init__(self, path: str | Path, ttl_seconds: int = 86400):
        self.path = Path(path)
        self.ttl_seconds = ttl_seconds
        self._items = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load handoffs from %s: %s", self.path, exc)
            return {}

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._items, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            logger.error("Could not persist handoffs to %s: %s", self.path, exc)
            raise

    def put(self, target_device_id: str, handoff: dict[str, Any]) -> None:
        self._items[target_device_id] = {**handoff, "stored_at": time.time()}
        self._save()

    def pop(self, target_device_id: str) -> dict[str, Any] | None:
        item = self._items.pop(target_device_id, None)
        if item is None:
            return None
        if time.time() - float(item.get("stored_at", 0)) > self.ttl_seconds:
            self._save()
            return None
        self._save()
        return item

    def count(self) -> int:
        return len(self._items)
