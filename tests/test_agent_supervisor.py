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


def test_routine_tool_is_exposed_to_the_assistant():
    from tools import tools_list

    names = {tool["name"] for tool in tools_list[0]["function_declarations"]}

    assert "run_routine" in names


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
