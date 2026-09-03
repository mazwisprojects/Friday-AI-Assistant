from agents.agent_supervisor import AgentSupervisor
from agents.routine_manager import RoutineManager
from actions.proactive import ProactiveEngine


def test_supervisor_builds_execution_plan_for_tool():
    supervisor = AgentSupervisor()

    plan = supervisor.plan_tool_call("desktop_control", {"action": "wallpaper", "path": "test.png"})

    assert plan["tool_name"] == "desktop_control"
    assert plan["status"] == "planned"
    assert len(plan["steps"]) >= 3
    assert plan["steps"][0]["name"] in {"inspect_target", "validate_target"}


def test_supervisor_rejects_failed_tool_results():
    supervisor = AgentSupervisor()

    failed = supervisor.verify_result("desktop_control", {"ok": False, "error": "wallpaper path missing"})
    passed = supervisor.verify_result("read_file", {"ok": True, "content": "hello"})

    assert failed is False
    assert passed is True


def test_supervisor_scores_risk_and_requires_approval_for_high_risk_tools():
    supervisor = AgentSupervisor()

    policy = supervisor.evaluate_policy("desktop_control", {"action": "wallpaper", "path": "test.png"}, {"safe_mode": False})

    assert policy["risk_score"] >= 70
    assert policy["requires_approval"] is True
    assert policy["reversible"] is True


def test_supervisor_reasons_before_execute_in_safe_mode():
    supervisor = AgentSupervisor()

    policy = supervisor.evaluate_policy(
        "browser_control",
        {"action": "open", "url": "https://example.com"},
        {"safe_mode": True, "user_reason": ""},
    )

    assert policy["requires_reason"] is True
    assert policy["safe_mode"] is True


def test_supervisor_logs_action_audit_events():
    supervisor = AgentSupervisor()

    supervisor.log_action("read_file", {"path": "notes.txt"}, {"approved": True, "risk_score": 20})

    assert supervisor.audit_log[-1]["tool_name"] == "read_file"
    assert supervisor.audit_log[-1]["approved"] is True


def test_policy_scores_high_risk_actions_and_requires_confirmation():
    supervisor = AgentSupervisor()

    policy = supervisor.evaluate_policy(
        "desktop_control",
        {"action": "wallpaper", "path": "C:/Users/test/wallpaper.jpg"},
        {"authenticated": True, "safe_mode": False},
    )

    assert policy["risk_score"] >= 7
    assert policy["requires_confirmation"] is True
    assert policy["allowed"] is True


def test_safe_mode_blocks_high_risk_actions():
    supervisor = AgentSupervisor()

    policy = supervisor.evaluate_policy(
        "browser_control",
        {"browser": "chrome", "action": "navigate", "url": "https://example.com"},
        {"authenticated": True, "safe_mode": True},
    )

    assert policy["allowed"] is False
    assert "safe mode" in policy["reason"].lower()


def test_audit_log_records_tool_outcome():
    supervisor = AgentSupervisor()

    record = supervisor.log_action(
        "read_file",
        {"path": "notes.txt"},
        {"ok": True, "content": "hello"},
    )

    assert record["tool_name"] == "read_file"
    assert record["outcome"]["ok"] is True
    assert len(supervisor.audit_log) >= 1


def test_routine_manager_builds_morning_briefing():
    manager = RoutineManager()

    briefing = manager.run_routine("morning_briefing", {
        "weather": "Sunny",
        "tasks": ["Review PR", "Fix auth bug"],
        "system_health": {"cpu": 42, "ram": 58},
    })

    assert briefing["routine"] == "morning_briefing"
    assert "weather" in briefing["summary"].lower()
    assert len(briefing["actions"]) >= 2


def test_routine_manager_focus_mode_prep():
    manager = RoutineManager()

    focus = manager.run_routine("focus_mode", {"project": "Friday", "notifications": False})

    assert focus["routine"] == "focus_mode"
    assert focus["context"]["project"] == "Friday"
    assert focus["context"]["notifications_disabled"] is True


def test_routine_manager_work_summary_collects_outcomes():
    manager = RoutineManager()

    summary = manager.run_routine("work_summary", {
        "completed": ["fixed import bug", "updated tests"],
        "remaining": ["deploy build"],
    })

    assert summary["routine"] == "work_summary"
    assert summary["summary"]["completed_count"] == 2
    assert summary["summary"]["remaining_count"] == 1


def test_routine_manager_dev_assistant_can_plan_a_fix():
    manager = RoutineManager()

    plan = manager.run_routine("dev_assistant", {
        "issue": "ImportError in backend startup",
        "repo": "Friday-AI-Assistant",
    })

    assert plan["routine"] == "dev_assistant"
    assert plan["next_steps"]
    assert "import" in plan["next_steps"][0].lower()


def test_routine_manager_supports_real_desktop_workflows():
    manager = RoutineManager()

    start = manager.run_routine("start_work_routine", {"project": "Friday", "tasks": ["fix auth bug"]})
    prep = manager.run_routine("prepare_environment", {"project": "Friday"})
    checkup = manager.run_routine("project_checkup", {"project": "Friday", "test_command": "pytest -q"})
    calendar = manager.run_routine("calendar_check", {"events": ["design review at 4:00 PM"]})
    cleanup = manager.run_routine("workspace_cleanup", {"notes": ["Review PR"]})
    report = manager.run_routine("daily_report", {"completed": ["tests passed"], "remaining": ["deploy build"]})

    assert start["routine"] == "start_work_routine"
    assert len(start["actions"]) >= 3
    assert prep["routine"] == "prepare_environment"
    assert checkup["routine"] == "project_checkup"
    assert calendar["routine"] == "calendar_check"
    assert cleanup["routine"] == "workspace_cleanup"
    assert report["routine"] == "daily_report"
    assert report["summary"]["remaining_count"] == 1


def test_routine_manager_executes_real_runtime_actions():
    manager = RoutineManager()

    class DummyRuntime:
        def __init__(self):
            self.calls = []

        def get_system_status(self):
            self.calls.append("status")
            return {"cpu_percent": 25, "ram_percent": 40}

        def run_powershell_command(self, params):
            self.calls.append(params["command"])
            return "pytest passed"

        def set_reminder(self, params):
            self.calls.append(params["message"])
            return "Reminder created"

        def desktop_control(self, params):
            self.calls.append(params["action"])
            return "desktop action complete"

    runtime = DummyRuntime()
    result = manager.execute_runtime(
        "project_checkup",
        {"project": "Friday", "test_command": "pytest -q", "cwd": "."},
        runtime=runtime,
    )

    assert result["routine"] == "project_checkup"
    assert "pytest passed" in str(result["execution"]["test_result"])
    assert "status" in runtime.calls or "pytest -q" in runtime.calls


def test_routine_tool_is_exposed_to_the_assistant():
    from tools import tools_list

    names = {tool["name"] for tool in tools_list[0]["function_declarations"]}

    assert "run_routine" in names


def test_supervisor_orchestrates_multi_step_task_journal():
    supervisor = AgentSupervisor()

    task = supervisor.create_task(
        "Investigate the import error",
        {"tool": "read_file", "args": {"path": "backend/friday.py"}},
        deadline_seconds=600,
    )

    task_id = task["task_id"]
    planned = supervisor.plan_task(task_id)

    assert planned["status"] == "planned"
    assert [step["name"] for step in planned["steps"][:3]] == ["observe", "plan", "execute"]
    assert any(step["name"] == "summarize" for step in planned["steps"])

    verified = supervisor.validate_task_result(task_id, {"ok": True, "summary": "Import path looks good."})
    assert verified["verified"] is True

    journal = supervisor.get_task_journal()
    assert task_id in {item["task_id"] for item in journal["active"] + journal["failed"] + journal["completed"]}


def test_proactive_engine_detects_stall_and_system_overload():
    engine = ProactiveEngine(min_silence_secs=0, check_cooldown=0)

    assert engine.detect_stall(last_user_speech=9999.0, recent_turns=["I am still trying to fix this import issue."]) is True
    assert engine.detect_system_overload({"cpu_percent": 95, "ram_percent": 92}) == "system_overload"

    prompt = engine.build_prompt(
        {},
        recent_turns=["I am still trying to fix this import issue."],
        system_status={"cpu_percent": 95, "ram_percent": 92},
        missing_context={"tool": "send_message", "issue": "No receiver provided"},
    )

    lowered = prompt.lower()
    assert "stalled" in lowered or "help" in lowered
    assert "cpu" in lowered or "memory" in lowered
    assert "receiver" in lowered or "context" in lowered
