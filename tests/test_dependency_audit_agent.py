import json
import threading

from actions import self_maintenance
from agents.dependency_audit_agent import run as dependency_audit_run


def test_dependency_audit_agent_reports_findings():
    result = dependency_audit_run("audit", ".", lambda message: None, threading.Event())

    assert result["ok"] is True
    assert "outdated_python_count" in result
    assert "outdated_node_count" in result
    assert "deprecation_count" in result
    assert "lost_tools" in result
    assert isinstance(result["needs_attention"], bool)


def test_dependency_audit_agent_detects_disappeared_tool(monkeypatch, tmp_path):
    registry_path = tmp_path / "capability_registry.json"
    registry_path.write_text(json.dumps({"tools": ["a_tool_that_will_disappear", "get_weather"]}), encoding="utf-8")
    monkeypatch.setattr(self_maintenance, "_BACKEND_DIR", tmp_path)

    result = dependency_audit_run("audit", ".", lambda message: None, threading.Event())

    assert "a_tool_that_will_disappear" in result["lost_tools"]
    assert result["needs_attention"] is True


def test_dependency_audit_agent_respects_cancellation():
    cancel_event = threading.Event()
    cancel_event.set()

    result = dependency_audit_run("audit", ".", lambda message: None, cancel_event)

    assert result == {"ok": False, "agent": "dependency_audit_agent", "status": "cancelled"}
