import pytest

from backend.device_registry import DeviceRegistry


def test_qr_session_is_single_use_and_persists_device_token_hash(tmp_path):
    registry = DeviceRegistry(tmp_path / "devices.json")
    session = registry.create_pairing_session("http://friday.local:8000")

    assert session["server_url"] == "http://friday.local:8000"
    assert registry.is_valid_pairing_session(session["session_id"], session["pairing_secret"])

    result = registry.consume_pairing_session(
        session["session_id"], session["pairing_secret"],
        {"device_id": "android-1", "name": "Friday Phone", "platform": "android"},
    )

    assert result["device_token"]
    assert not registry.is_valid_pairing_session(session["session_id"], session["pairing_secret"])
    assert registry.is_valid_token(result["device_token"])
    assert "token_hash" in (tmp_path / "devices.json").read_text(encoding="utf-8")

    with pytest.raises(ValueError):
        registry.consume_pairing_session(
            session["session_id"], session["pairing_secret"], {"device_id": "android-2"}
        )
