import socket

import pytest

from openclaw_bridge import OpenClawBridge


class FakePluginManager:
    def list_plugins(self):
        return []

    def health(self):
        return {}


class FakeDispatcher:
    def list_agents(self):
        return []

    def registered_agents(self):
        return []


def test_health_check_is_cached_between_calls(monkeypatch):
    probes = []

    def fake_connect(*args, **kwargs):
        probes.append(1)
        raise OSError("refused")

    monkeypatch.setattr(socket, "create_connection", fake_connect)
    bridge = OpenClawBridge(FakePluginManager(), FakeDispatcher(), api_key="")

    assert bridge.is_reachable() is False
    assert bridge.is_reachable() is False
    assert len(probes) == 1


def test_plan_skips_cli_when_gateway_known_down(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(OSError("refused")))
    bridge = OpenClawBridge(FakePluginManager(), FakeDispatcher(), api_key="")
    bridge.api_key = ""  # force no fallback API key regardless of the environment
    bridge.is_reachable()

    attempted = []
    bridge._run_openclaw = lambda prompt: attempted.append(prompt) or "should-not-run"

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        bridge.plan("test goal")

    assert attempted == []


def test_mark_unreachable_forces_reprobe(monkeypatch):
    probes = []

    def fake_connect(*args, **kwargs):
        probes.append(1)
        raise OSError("refused")

    monkeypatch.setattr(socket, "create_connection", fake_connect)
    bridge = OpenClawBridge(FakePluginManager(), FakeDispatcher(), api_key="")

    bridge.is_reachable()
    bridge.is_reachable()
    assert len(probes) == 1

    bridge.mark_unreachable()
    bridge.is_reachable()
    assert len(probes) == 2
