import json

from actions.agent_dispatcher import AgentDispatcher
from agent_scheduler import AgentScheduler


def test_ensure_default_workflows_schedules_dependency_audit_agent(tmp_path):
    scheduler = AgentScheduler(str(tmp_path), AgentDispatcher())
    created = scheduler.ensure_default_workflows()

    dependency_audit = next(item for item in created if item["key"] == "dependency_audit")
    assert dependency_audit["agent_type"] == "dependency_audit_agent"
    scheduler.stop()


def test_legacy_dependency_audit_schedule_is_migrated(tmp_path):
    schedules_path = tmp_path / "long_term_memory" / "agent_schedules.json"
    schedules_path.parent.mkdir(parents=True, exist_ok=True)
    schedules_path.write_text(json.dumps([{
        "id": "legacy-1", "key": "dependency_audit", "agent_type": "project_health_agent",
        "goal": "old goal", "repo_path": ".", "schedule_type": "weekly", "hour": 10, "minute": 0,
        "weekday": 5, "enabled": True, "next_run": 0,
    }]), encoding="utf-8")

    scheduler = AgentScheduler(str(tmp_path), AgentDispatcher())
    scheduler.ensure_default_workflows()

    migrated = next(item for item in scheduler.list() if item["key"] == "dependency_audit")
    assert migrated["agent_type"] == "dependency_audit_agent"
    scheduler.stop()
