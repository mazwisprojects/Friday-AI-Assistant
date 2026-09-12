import time

import pytest

from backend.device_registry import DeviceRegistry


def test_pairing_code_is_one_time_and_token_is_not_persisted(tmp_path):
    registry = DeviceRegistry(tmp_path / "devices.json")
    pairing = registry.create_pairing_code()

    result = registry.pair(pairing["code"], {"device_id": "phone-1", "name": "My Phone", "platform": "android"})

    assert result["device_token"]
    assert "token_hash" not in result["device"]
    assert "token_hash" in (tmp_path / "devices.json").read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        registry.pair(pairing["code"], {"device_id": "phone-2"})


def test_heartbeat_updates_presence_and_stale_devices_go_offline(tmp_path):
    registry = DeviceRegistry(tmp_path / "devices.json", heartbeat_timeout=1)
    pairing = registry.create_pairing_code()
    result = registry.pair(pairing["code"], {"device_id": "phone-1"})

    updated = registry.heartbeat(result["device_token"], {"battery": 73, "network": "wifi"})
    assert updated["battery"] == 73
    assert registry.list_devices()[0]["status"] == "online"

    registry._state["devices"]["phone-1"]["last_seen"] = time.time() - 2
    assert registry.list_devices()[0]["status"] == "offline"
