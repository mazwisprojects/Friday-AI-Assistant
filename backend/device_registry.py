"""Persistent registry for explicitly paired Friday companion devices."""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class DeviceRegistry:
    """Store paired devices without persisting bearer tokens in plain text."""

    def __init__(self, state_path: str | Path, heartbeat_timeout: int = 180):
        self.state_path = Path(state_path)
        self.heartbeat_timeout = heartbeat_timeout
        self._lock = threading.RLock()
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(state, dict) and isinstance(state.get("devices"), dict):
                return state
        except (OSError, json.JSONDecodeError):
            pass
        return {"pairing": None, "devices": {}}

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.state_path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        temporary_path.replace(self.state_path)

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def create_pairing_code(self, ttl_seconds: int = 300) -> dict[str, Any]:
        with self._lock:
            code = f"{secrets.randbelow(1_000_000):06d}"
            pairing = {
                "code_hash": self._hash(code),
                "expires_at": time.time() + max(30, min(ttl_seconds, 900)),
            }
            self._state["pairing"] = pairing
            self._save()
            return {"code": code, "expires_at": pairing["expires_at"]}

    def pair(self, code: str, metadata: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            pairing = self._state.get("pairing") or {}
            if pairing.get("expires_at", 0) < time.time() or not secrets.compare_digest(
                pairing.get("code_hash", ""), self._hash(str(code))
            ):
                raise ValueError("The pairing code is invalid or expired.")

            device_id = str(metadata.get("device_id") or uuid.uuid4().hex)
            token = secrets.token_urlsafe(32)
            now = time.time()
            self._state["devices"][device_id] = {
                "device_id": device_id,
                "name": str(metadata.get("name") or device_id),
                "platform": str(metadata.get("platform") or "unknown"),
                "model": str(metadata.get("model") or "unknown"),
                "token_hash": self._hash(token),
                "paired_at": now,
                "last_seen": now,
                "status": "online",
                "battery": metadata.get("battery"),
                "network": metadata.get("network"),
                "location": None,
            }
            self._state["pairing"] = None
            self._save()
            return {"device_id": device_id, "device_token": token, "device": self._public(self._state["devices"][device_id])}

    def heartbeat(self, token: str, metadata: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            device = self._find_by_token(token)
            if not device:
                raise ValueError("The device token is invalid or revoked.")
            now = time.time()
            for key in ("name", "model", "battery", "network", "location"):
                if key in metadata:
                    device[key] = metadata[key]
            device["last_seen"] = now
            device["status"] = "online"
            self._save()
            return self._public(device)

    def list_devices(self) -> list[dict[str, Any]]:
        with self._lock:
            now = time.time()
            devices = []
            changed = False
            for device in self._state["devices"].values():
                status = "online" if now - device.get("last_seen", 0) <= self.heartbeat_timeout else "offline"
                if device.get("status") != status:
                    device["status"] = status
                    changed = True
                devices.append(self._public(device))
            if changed:
                self._save()
            return sorted(devices, key=lambda item: item.get("name", "").lower())

    def revoke(self, device_id: str) -> bool:
        with self._lock:
            removed = self._state["devices"].pop(device_id, None) is not None
            if removed:
                self._save()
            return removed

    def _find_by_token(self, token: str) -> dict[str, Any] | None:
        token_hash = self._hash(token)
        for device in self._state["devices"].values():
            if secrets.compare_digest(device.get("token_hash", ""), token_hash):
                return device
        return None

    @staticmethod
    def _public(device: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in device.items() if key != "token_hash"}
