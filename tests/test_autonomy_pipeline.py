import pytest

from autonomy_pipeline import AutonomyPipeline
from execution_ledger import ExecutionLedger


class FakeLearning:
    def inspect(self):
        return {
            "proposals": [{"name": "repeatable_tool", "reason": "repeated use", "usage_count": 3}],
            "security": [],
            "usage": {"repeatable_tool": 3},
            "failures": {},
        }


class FakePlugins:
    def list_plugins(self):
        return []

    def expire(self):
        return []


def test_pipeline_completes_safe_phases_and_requests_approval(tmp_path):
    pipeline = AutonomyPipeline(str(tmp_path), FakeLearning(), FakePlugins(), ExecutionLedger(str(tmp_path)))
    result = pipeline.run_cycle()
    assert result["phases"]["observe"] == "complete"
    assert result["phases"]["request_approval"] == "pending"
    assert result["phases"]["deploy"] == "approval_required"
    assert result["proposals"][0]["status"] == "pending_review"


def test_pipeline_refuses_unknown_approval(tmp_path):
    pipeline = AutonomyPipeline(str(tmp_path), FakeLearning(), FakePlugins(), ExecutionLedger(str(tmp_path)))
    with pytest.raises(ValueError, match="not found"):
        pipeline.approve("missing")
