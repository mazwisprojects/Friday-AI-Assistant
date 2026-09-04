import threading

import pytest

from agent_builder import AgentBuilder
from agent_scheduler import AgentScheduler
from actions.agent_dispatcher import AgentDispatcher
from execution_ledger import ExecutionLedger


def test_agent_build_rejects_bad_runtime_result(tmp_path):
    builder = AgentBuilder(str(tmp_path))
    code = "def run(goal, repo_path, log, cancel_event):\n    return ['invalid']\n"

    with pytest.raises(ValueError, match="smoke test failed"):
        builder.build("invalid_return_agent", "Invalid return", code)

    assert "invalid_return_agent" not in builder.agents
    assert not (tmp_path / "agents" / "invalid_return_agent.py").exists()


def test_dispatcher_cancellation_and_completion(tmp_path):
    dispatcher = AgentDispatcher()
    started = threading.Event()

    def worker(goal, repo_path, log, cancel_event):
        started.set()
        cancel_event.wait(2)
        return {"ok": True}

    dispatcher.register_agent("worker", worker)
    agent_id = dispatcher.deploy_agent("worker", "cancel me")
    assert started.wait(1)
    assert dispatcher.cancel(agent_id)

    for _ in range(20):
        if dispatcher.get_status(agent_id)["status"] != "running":
            break
        threading.Event().wait(0.02)
    assert dispatcher.get_status(agent_id)["status"] == "cancelled"


def test_scheduler_controls_and_execution_ledger(tmp_path):
    dispatcher = AgentDispatcher()
    dispatcher.register_agent("worker", lambda goal, repo, log, cancel: {"ok": True})
    scheduler = AgentScheduler(str(tmp_path), dispatcher)
    item = scheduler.schedule("worker", "run once", 900, max_retries=2)
    assert item["max_retries"] == 2
    assert scheduler.set_enabled(item["id"], False)
    assert scheduler.set_enabled(item["id"], True)
    assert scheduler.run_now(item["id"])["status"] == "running"

    ledger = ExecutionLedger(str(tmp_path))
    entry_id = ledger.start("agent", "worker", "run once")
    ledger.finish(entry_id, "done", {"ok": True})
    assert ledger.list()[-1]["status"] == "done"
    scheduler.stop()
