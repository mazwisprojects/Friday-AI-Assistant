import asyncio
import json

import pytest

import server


class _FakeSio:
    def __init__(self):
        self.emitted = []

    async def emit(self, event, data=None, room=None):
        self.emitted.append({"event": event, "data": data, "room": room})


@pytest.fixture(autouse=True)
def restore_settings():
    original = server.SETTINGS.copy()
    yield
    server.SETTINGS.clear()
    server.SETTINGS.update(original)


def test_load_settings_merges_tool_permissions(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "tool_permissions": {"send_message": False},
        "camera_flipped": True,
    }))
    monkeypatch.setattr(server, "SETTINGS_FILE", str(settings_path))
    server.SETTINGS = server.DEFAULT_SETTINGS.copy()
    server.SETTINGS["tool_permissions"] = server.DEFAULT_SETTINGS["tool_permissions"].copy()

    server.load_settings()

    assert server.SETTINGS["tool_permissions"]["send_message"] is False
    assert server.SETTINGS["tool_permissions"]["generate_cad"] is True
    assert server.SETTINGS["camera_flipped"] is True


def test_load_settings_ignores_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "SETTINGS_FILE", str(tmp_path / "does_not_exist.json"))
    before = server.SETTINGS.copy()

    server.load_settings()

    assert server.SETTINGS == before


def test_save_settings_writes_json(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(server, "SETTINGS_FILE", str(settings_path))

    server.save_settings()

    assert settings_path.exists()
    saved = json.loads(settings_path.read_text())
    assert "tool_permissions" in saved


def test_get_contacts_is_shadowed_by_a_duplicate_stub_handler(monkeypatch):
    # NOTE: server.py defines `get_contacts` twice (once with a real
    # contacts_manager-backed implementation, and again later as a dead stub).
    # Python keeps only the last definition, so the real contact list handler
    # is currently unreachable. This test documents that actual behavior.
    fake_sio = _FakeSio()
    monkeypatch.setattr(server, "sio", fake_sio)
    monkeypatch.setattr(server.contacts_manager, "list_contacts", lambda: [{"name": "Jane"}])

    asyncio.run(server.get_contacts("sid-1", {"platform": "whatsapp"}))

    assert fake_sio.emitted == [{"event": "contact_list", "data": [], "room": None}]


def test_save_contact_delegates_to_contacts_manager(monkeypatch):
    fake_sio = _FakeSio()
    monkeypatch.setattr(server, "sio", fake_sio)
    monkeypatch.setattr(server.contacts_manager, "add_or_update", lambda name, recipient, platform: f"Saved {name}")

    asyncio.run(server.save_contact("sid-1", {"name": "Jane", "recipient": "+1555", "platform": "whatsapp"}))

    assert fake_sio.emitted[0]["event"] == "contacts_status"
    assert fake_sio.emitted[0]["data"]["msg"] == "Saved Jane"


def test_delete_contact_delegates_to_contacts_manager(monkeypatch):
    fake_sio = _FakeSio()
    monkeypatch.setattr(server, "sio", fake_sio)
    monkeypatch.setattr(server.contacts_manager, "remove", lambda name, platform: f"Removed {name}")

    asyncio.run(server.delete_contact("sid-1", {"name": "Jane", "platform": ""}))

    assert fake_sio.emitted[0]["data"]["msg"] == "Removed Jane"


def test_disconnect_cancels_pending_confirmations_when_audio_loop_active(monkeypatch):
    calls = []

    class FakeAudioLoop:
        def cancel_pending_confirmations(self):
            calls.append(True)

    monkeypatch.setattr(server, "audio_loop", FakeAudioLoop())

    asyncio.run(server.disconnect("sid-1"))

    assert calls == [True]


def test_disconnect_is_safe_when_no_audio_loop(monkeypatch):
    monkeypatch.setattr(server, "audio_loop", None)

    asyncio.run(server.disconnect("sid-1"))


def test_start_audio_blocks_when_face_auth_enabled_and_not_authenticated(monkeypatch):
    fake_sio = _FakeSio()
    monkeypatch.setattr(server, "sio", fake_sio)
    monkeypatch.setattr(server, "SETTINGS", {**server.SETTINGS, "face_auth_enabled": True})

    class FakeAuthenticator:
        authenticated = False

    monkeypatch.setattr(server, "authenticator", FakeAuthenticator())

    asyncio.run(server.start_audio("sid-1", {}))

    assert any(e["event"] == "error" and e["data"]["msg"] == "Authentication Required" for e in fake_sio.emitted)


def test_ensure_audio_ready_reports_when_not_started(monkeypatch):
    fake_sio = _FakeSio()
    monkeypatch.setattr(server, "sio", fake_sio)
    monkeypatch.setattr(server, "audio_loop", None)

    ready = asyncio.run(server.ensure_audio_ready("sid-1"))

    assert ready is False
    assert any("still starting" in e["data"]["msg"] for e in fake_sio.emitted)


def test_ensure_audio_ready_reports_when_session_not_ready(monkeypatch):
    fake_sio = _FakeSio()
    monkeypatch.setattr(server, "sio", fake_sio)

    class FakeAudioLoop:
        session = None

    monkeypatch.setattr(server, "audio_loop", FakeAudioLoop())

    ready = asyncio.run(server.ensure_audio_ready("sid-1", require_session=True))

    assert ready is False
    assert any("Gemini session" in e["data"]["msg"] for e in fake_sio.emitted)


def test_ensure_audio_ready_returns_true_when_ready(monkeypatch):
    fake_sio = _FakeSio()
    monkeypatch.setattr(server, "sio", fake_sio)

    class FakeAudioLoop:
        session = object()

    monkeypatch.setattr(server, "audio_loop", FakeAudioLoop())

    ready = asyncio.run(server.ensure_audio_ready("sid-1", require_session=True))

    assert ready is True
    assert fake_sio.emitted == []
