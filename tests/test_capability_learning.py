from capability_learning import CapabilityLearning
from execution_ledger import ExecutionLedger


class EmptyPlugins:
    def list_plugins(self):
        return []

    def expire(self):
        return []


def test_learning_detects_repeated_patterns_and_failures(tmp_path):
    ledger = ExecutionLedger(str(tmp_path))
    for index in range(3):
        entry_id = ledger.start("tool", "repeatable_tool", f"goal {index}")
        ledger.finish(entry_id, "done", {"ok": True})
    failed_id = ledger.start("agent", "unstable_agent", "repair")
    ledger.finish(failed_id, "failed", error="test failure")

    learning = CapabilityLearning(str(tmp_path), ledger, EmptyPlugins())
    result = learning.inspect()
    assert result["usage"]["repeatable_tool"] == 3
    assert result["failures"]["unstable_agent"] == 1
    assert result["proposals"][0]["status"] == "pending_review"
    assert len(ledger.list()) == 4


def test_scoring_is_idempotent(tmp_path):
    ledger = ExecutionLedger(str(tmp_path))
    entry_id = ledger.start("tool", "tool", "goal")
    ledger.finish(entry_id, "done", {"ok": True})
    learning = CapabilityLearning(str(tmp_path), ledger, EmptyPlugins())
    learning._score_plugins = lambda entries: None
    first = learning.inspect()
    second = learning.inspect()
    assert first["usage"]["tool"] == second["usage"]["tool"] == 1
