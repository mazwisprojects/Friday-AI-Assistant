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


def test_security_findings_can_be_reviewed_and_accepted(tmp_path):
    tools_dir = tmp_path / "mytools"
    tools_dir.mkdir()
    (tools_dir / "risky_tool.py").write_text("import subprocess\n", encoding="utf-8")

    ledger = ExecutionLedger(str(tmp_path))
    learning = CapabilityLearning(str(tmp_path), ledger, EmptyPlugins())
    first = learning.inspect()
    finding = next(item for item in first["security"] if item["value"] == "subprocess")
    assert finding["path"].endswith("risky_tool.py")

    # A human review decision clears the finding from the next scan...
    learning.accept_finding(finding["path"], finding["value"])
    assert learning.inspect()["security"] == []

    # ...and the decision survives restarts (accepted_findings.json).
    reloaded = CapabilityLearning(str(tmp_path), ledger, EmptyPlugins())
    assert reloaded.inspect()["security"] == []


def test_accept_finding_requires_path_and_value(tmp_path):
    ledger = ExecutionLedger(str(tmp_path))
    learning = CapabilityLearning(str(tmp_path), ledger, EmptyPlugins())
    try:
        learning.accept_finding("", "subprocess")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_marked_patterns_stop_being_reported_for_review(tmp_path):
    ledger = ExecutionLedger(str(tmp_path))
    for index in range(3):
        entry_id = ledger.start("tool", "repeatable_tool", f"goal {index}")
        ledger.finish(entry_id, "done", {"ok": True})
    learning = CapabilityLearning(str(tmp_path), ledger, EmptyPlugins())
    assert learning.inspect()["proposals"][0]["name"] == "repeatable_tool"

    # The pipeline marks a pattern once its proposal is minted, and a human
    # approval closes it out: after either, inspect() must stop surfacing it,
    # or the supervisor re-raises governed work as fresh approval requests.
    learning.mark_pattern_status("repeatable_tool", "proposed")
    assert learning.inspect()["proposals"] == []
    learning.mark_pattern_status("repeatable_tool", "approved")
    reloaded = CapabilityLearning(str(tmp_path), ledger, EmptyPlugins())
    assert reloaded.inspect()["proposals"] == []


def test_mark_pattern_status_requires_name_and_status(tmp_path):
    ledger = ExecutionLedger(str(tmp_path))
    learning = CapabilityLearning(str(tmp_path), ledger, EmptyPlugins())
    try:
        learning.mark_pattern_status("", "approved")
        assert False, "expected ValueError"
    except ValueError:
        pass
