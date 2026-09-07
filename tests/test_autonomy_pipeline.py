import pytest

from agent_builder import AgentBuilder
from actions.agent_dispatcher import AgentDispatcher
from agent_scheduler import AgentScheduler
from autonomy_pipeline import AutonomyPipeline
from execution_ledger import ExecutionLedger
from plugin_manager import PluginManager
from tool_builder import ToolBuilder


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


def test_approving_a_workflow_proposal_builds_and_activates_a_real_agent(tmp_path):
    tools = ToolBuilder(str(tmp_path))
    agents = AgentBuilder(str(tmp_path))
    dispatcher = AgentDispatcher()
    manager = PluginManager(str(tmp_path), tools, agents, dispatcher)
    scheduler = AgentScheduler(str(tmp_path), dispatcher)
    pipeline = AutonomyPipeline(str(tmp_path), FakeLearning(), manager, ExecutionLedger(str(tmp_path)), scheduler)

    result = pipeline.run_cycle()
    proposal_id = result["proposals"][0]["id"]

    approved = pipeline.approve(proposal_id)

    assert approved["status"] == "approved"
    assert approved["deployed_agent"] == "workflow_repeatable_tool"
    assert "workflow_repeatable_tool" in dispatcher.registered_agents()
    plugin = next(item for item in manager.list_plugins() if item["name"] == "workflow_repeatable_tool")
    assert plugin["enabled"] is True

    schedules = scheduler.list()
    assert any(item["agent_type"] == "workflow_repeatable_tool" for item in schedules)
    scheduler.stop()


class BlockedBySecurityLearning(FakeLearning):
    """FakeLearning whose inspect() reports one security finding until reviewed."""

    def __init__(self):
        super().__init__()
        self.security = [{"path": "agents/example_agent.py", "line": 1, "kind": "risky_import", "value": "subprocess"}]
        self.accepted = []

    def inspect(self):
        data = super().inspect()
        data["security"] = self.security
        return data

    def accept_finding(self, finding_path, finding_value):
        self.accepted.append((finding_path, finding_value))
        self.security = []


def test_resolving_security_finding_records_review_and_clears_block(tmp_path):
    learning = BlockedBySecurityLearning()
    pipeline = AutonomyPipeline(str(tmp_path), learning, FakePlugins(), ExecutionLedger(str(tmp_path)))

    blocked = pipeline.run_cycle()
    assert blocked["phases"]["security_review"] == "blocked"
    assert blocked["security_findings"][0]["value"] == "subprocess"

    result = pipeline.resolve_security("agents/example_agent.py", "subprocess")

    assert learning.accepted == [("agents/example_agent.py", "subprocess")]
    assert result["phases"]["security_review"] == "complete"
    assert result["security_findings"] == []


def test_resolve_security_requires_path_and_value(tmp_path):
    learning = BlockedBySecurityLearning()
    pipeline = AutonomyPipeline(str(tmp_path), learning, FakePlugins(), ExecutionLedger(str(tmp_path)))
    with pytest.raises(ValueError, match="required"):
        pipeline.resolve_security("", None)
    with pytest.raises(ValueError, match="required"):
        pipeline.resolve_security("agents/example_agent.py", "")


class MarkingLearning(FakeLearning):
    """FakeLearning that records lifecycle syncs from the pipeline."""

    def __init__(self):
        super().__init__()
        self.marks = []

    def mark_pattern_status(self, name, status):
        self.marks.append((name, status))


def test_pipeline_syncs_pattern_lifecycle_into_learning_store(tmp_path):
    learning = MarkingLearning()
    tools = ToolBuilder(str(tmp_path))
    agents = AgentBuilder(str(tmp_path))
    dispatcher = AgentDispatcher()
    manager = PluginManager(str(tmp_path), tools, agents, dispatcher)
    scheduler = AgentScheduler(str(tmp_path), dispatcher)
    pipeline = AutonomyPipeline(str(tmp_path), learning, manager, ExecutionLedger(str(tmp_path)), scheduler)

    proposal_id = pipeline.run_cycle()["proposals"][0]["id"]
    assert learning.marks == [("repeatable_tool", "proposed")]

    pipeline.approve(proposal_id)
    assert ("repeatable_tool", "approved") in learning.marks
    scheduler.stop()

