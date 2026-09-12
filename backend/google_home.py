"""Google Home / Smart Home bridge for FRIDAY."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


class GoogleHomeBridge:
    """Thin wrapper around Google Smart Home and Home Graph endpoints.

    FRIDAY does not hardcode specific devices. Instead it uses the Google OAuth
    session, a configured enterprise ID, and generic API calls to discover known
    Home devices and report state back to the Google ecosystem.
    """

    def __init__(self, google_account: Any):
        self.google_account = google_account
        self.enterprise_id = os.getenv("GOOGLE_HOME_ENTERPRISE_ID", "default")

    @property
    def available(self) -> bool:
        credentials = getattr(self.google_account, "credentials", None)
        return bool(credentials and getattr(credentials, "valid", False))

    def _require_connection(self) -> None:
        if not self.available:
            raise RuntimeError("Google account is not connected to Google Home.")

    def _smart_home_service(self):
        self._require_connection()
        return build("smartdevicemanagement", "v1", credentials=self.google_account.credentials, cache_discovery=False)

    def _home_graph_service(self):
        self._require_connection()
        return build("homegraph", "v1", credentials=self.google_account.credentials, cache_discovery=False)

    def list_devices(self) -> list[dict[str, Any]]:
        """List Google Home / Smart Home devices visible to the connected account."""
        service = self._smart_home_service()
        parent = f"enterprises/{self.enterprise_id}"
        result = service.enterprises().devices().list(parent=parent).execute()
        devices = result.get("devices", [])
        logger.info("Google Home discovered %s devices", len(devices))
        return devices

    def get_device(self, device_id: str) -> dict[str, Any]:
        """Fetch a single device by ID."""
        service = self._smart_home_service()
        parent = f"enterprises/{self.enterprise_id}"
        result = service.enterprises().devices().get(name=f"{parent}/devices/{device_id}").execute()
        return result

    def execute_command(self, device_id: str, command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a generic command to a Google Home device.

        The actual payload is intentionally generic so Friday can work with many
        device types instead of only a single hardcoded class.
        """
        service = self._smart_home_service()
        device_name = device_id if device_id.startswith("enterprises/") else (
            f"enterprises/{self.enterprise_id}/devices/{device_id}"
        )
        command_body = {"command": command, "params": params or {}}
        return service.enterprises().devices().executeCommand(
            name=f"{device_name}:executeCommand", body=command_body
        ).execute()

    def report_state(self, device_id: str, state: dict[str, Any]) -> dict[str, Any]:
        """Push a device state snapshot to the Google Home Graph."""
        service = self._home_graph_service()
        request_id = f"friday-{uuid.uuid4().hex}"
        payload = {
            "requestId": request_id,
            "payload": {
                "devices": {
                    "states": {
                        device_id: state,
                    }
                }
            },
            "agentUserId": "friday",
        }
        return service.devices().reportStateAndNotification(body=payload).execute()

    def status(self) -> dict[str, Any]:
        return {
            "connected": self.available,
            "enterprise_id": self.enterprise_id,
            "device_count": len(self.list_devices()) if self.available else 0,
            "provider": "google_home",
        }