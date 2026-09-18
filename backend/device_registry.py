"""Persistent registry for explicitly paired Friday companion devices."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import threading
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
            logger.warning("Device registry at %s has an unexpected shape; starting fresh", self.state_path)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load device registry from %s: %s", self.state_path, exc)
        return {"pairing": None, "devices": {}}

    def _save(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.state_path.with_suffix(".tmp")
            temporary_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
            temporary_path.replace(self.state_path)
        except OSError as exc:
            logger.error("Could not persist device registry to %s: %s", self.state_path, exc)
            raise

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

    def create_pairing_session(self, server_url: str, ttl_seconds: int = 300) -> dict[str, Any]:
        """Create a one-time QR bootstrap session without exposing server credentials."""
        with self._lock:
            session_id = uuid.uuid4().hex
            secret = secrets.token_urlsafe(32)
            expires_at = time.time() + max(30, min(int(ttl_seconds), 900))
            self._state["pairing_session"] = {
                "session_id": session_id,
                "secret_hash": self._hash(secret),
                "server_url": str(server_url).rstrip("/"),
                "expires_at": expires_at,
            }
            self._save()
            return {
                "version": 1,
                "session_id": session_id,
                "pairing_secret": secret,
                "server_url": self._state["pairing_session"]["server_url"],
                "expires_at": expires_at,
            }

    def consume_pairing_session(self, session_id: str, secret: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Exchange a QR bootstrap secret for a persistent device token exactly once."""
        with self._lock:
            session = self._state.get("pairing_session") or {}
            if (
                session.get("session_id") != str(session_id)
                or session.get("expires_at", 0) < time.time()
                or not secrets.compare_digest(session.get("secret_hash", ""), self._hash(str(secret)))
            ):
                raise ValueError("The QR pairing session is invalid or expired.")
            result = self._pair_unlocked(metadata)
            self._state.pop("pairing_session", None)
            self._save()
            return result

    def is_valid_pairing_session(self, session_id: str, secret: str) -> bool:
        with self._lock:
            session = self._state.get("pairing_session") or {}
            return bool(
                session.get("session_id") == str(session_id)
                and session.get("expires_at", 0) >= time.time()
                and secrets.compare_digest(session.get("secret_hash", ""), self._hash(str(secret)))
            )

    def pair(self, code: str, metadata: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            pairing = self._state.get("pairing") or {}
            if pairing.get("expires_at", 0) < time.time() or not secrets.compare_digest(
                pairing.get("code_hash", ""), self._hash(str(code))
            ):
                raise ValueError("The pairing code is invalid or expired.")

            result = self._pair_unlocked(metadata)
            self._state["pairing"] = None
            self._save()
            return result

    def _pair_unlocked(self, metadata: dict[str, Any]) -> dict[str, Any]:
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
        return {"device_id": device_id, "device_token": token, "device": self._public(self._state["devices"][device_id])}

    def is_valid_token(self, token: str) -> bool:
        with self._lock:
            return bool(token and self._find_by_token(token))

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

    def refresh_token(self, old_token: str) -> dict[str, Any]:
        """Rotate a device's token. Returns the new public device info."""
        import secrets as _secrets
        with self._lock:
            device = self._find_by_token(old_token)
            if not device:
                raise ValueError("The device token is invalid or revoked.")
            new_token = _secrets.token_urlsafe(32)
            device["token_hash"] = self._hash(new_token)
            device["last_seen"] = time.time()
            self._save()
            public = self._public(device)
            public["device_token"] = new_token  # Return new token once
            return public

    def _find_by_token(self, token: str) -> dict[str, Any] | None:
        token_hash = self._hash(token)
        for device in self._state["devices"].values():
            if secrets.compare_digest(device.get("token_hash", ""), token_hash):
                return device
        return None

    @staticmethod
    def _public(device: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in device.items() if key != "token_hash"}
