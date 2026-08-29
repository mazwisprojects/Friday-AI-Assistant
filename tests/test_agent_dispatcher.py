import threading
import time

from actions import agent_dispatcher as ad


def test_deploy_agent_returns_immediately_and_does_not_block(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def slow_agent(goal, repo_path, log, cancel_event):
        started.set()
        release.wait(timeout=2)
        return {"summary": f"done: {goal}"}

    dispatcher = ad.AgentDispatcher()
    dispatcher.register_agent("slow_agent", slow_agent)

    begin = time.monotonic()
    agent_id = dispatcher.deploy_agent("slow_agent", goal="test goal", repo_path=".")
    elapsed = time.monotonic() - begin

    assert agent_id
    assert elapsed < 1.0
    assert started.wait(timeout=2)

    status = dispatcher.get_status(agent_id)
    assert status["status"] == "running"

    release.set()
    for _ in range(50):
        status = dispatcher.get_status(agent_id)
        if status["status"] == "done":
            break
        time.sleep(0.02)

    assert status["status"] == "done"
    assert status["result"]["summary"] == "done: test goal"


def test_deploy_agent_marks_failed_on_exception():
    def failing_agent(goal, repo_path, log, cancel_event):
        raise RuntimeError("boom")

    dispatcher = ad.AgentDispatcher()
    dispatcher.register_agent("failing_agent", failing_agent)

    agent_id = dispatcher.deploy_agent("failing_agent", goal="goal", repo_path=".")

    status = {}
    for _ in range(50):
        status = dispatcher.get_status(agent_id)
        if status["status"] == "failed":
            break
        time.sleep(0.02)

    assert status["status"] == "failed"
    assert "boom" in status["error"]


def test_list_agents_returns_all_deployed():
    def noop_agent(goal, repo_path, log, cancel_event):
        return {"summary": "ok"}

    dispatcher = ad.AgentDispatcher()
    dispatcher.register_agent("noop_agent", noop_agent)

    first = dispatcher.deploy_agent("noop_agent", goal="a", repo_path=".")
    second = dispatcher.deploy_agent("noop_agent", goal="b", repo_path=".")

    agents = dispatcher.list_agents()
    ids = {entry["id"] for entry in agents}
    assert {first, second} <= ids


def test_cancel_sets_cancel_event_observed_by_agent():
    observed = threading.Event()

    def cancellable_agent(goal, repo_path, log, cancel_event):
        for _ in range(100):
            if cancel_event.is_set():
                observed.set()
                return {"summary": "cancelled early"}
            time.sleep(0.01)
        return {"summary": "ran full"}

    dispatcher = ad.AgentDispatcher()
    dispatcher.register_agent("cancellable_agent", cancellable_agent)

    agent_id = dispatcher.deploy_agent("cancellable_agent", goal="goal", repo_path=".")
    dispatcher.cancel(agent_id)

    assert observed.wait(timeout=2)


def test_deploy_unknown_agent_type_raises():
    dispatcher = ad.AgentDispatcher()
    try:
        dispatcher.deploy_agent("does_not_exist", goal="goal", repo_path=".")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "does_not_exist" in str(exc)


def test_agent_dispatcher_tool_dispatch_deploy_and_status():
    def quick_agent(goal, repo_path, log, cancel_event):
        return {"summary": "quick done"}

    dispatcher = ad.AgentDispatcher()
    dispatcher.register_agent("quick_agent", quick_agent)

    deploy_result = ad.agent_dispatcher_action(
        {"action": "deploy", "agent_type": "quick_agent", "goal": "do it", "repo_path": "."},
        dispatcher=dispatcher,
    )
    assert "agent_id" in deploy_result

    agent_id = deploy_result["agent_id"]
    for _ in range(50):
        status_result = ad.agent_dispatcher_action(
            {"action": "status", "agent_id": agent_id},
            dispatcher=dispatcher,
        )
        if status_result["status"] == "done":
            break
        time.sleep(0.02)

    assert status_result["status"] == "done"
