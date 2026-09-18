"""Tests for the controlled automation agent."""
import pytest
from backend.agents.automation_agent import AutomationAgent, RISK_LOW, RISK_MEDIUM
from backend.models import AutomationTask


class TestAutomationAgent:
    def test_create_low_risk_task(self):
        agent = AutomationAgent()
        task = agent.create_task(
            name="Take screenshot",
            description="Capture the screen",
            steps=[{"action": "screenshot", "domain": "control"}],
        )
        assert task.status == "approved"  # Low risk, auto-approved
        assert task.risk_score <= RISK_LOW

    def test_create_high_risk_task(self):
        agent = AutomationAgent()
        task = agent.create_task(
            name="Shutdown",
            description="Shutdown the computer",
            steps=[{"action": "shutdown", "domain": "settings", "confirmed": "yes"}],
        )
        assert task.status == "pending"  # High risk, requires approval
        assert task.requires_approval is True
        assert task.risk_score > RISK_MEDIUM

    def test_approve_task(self):
        agent = AutomationAgent()
        task = agent.create_task(
            name="Shutdown", description="Shutdown",
            steps=[{"action": "shutdown", "domain": "settings"}],
        )
        assert task.status == "pending"
        approved = agent.approve_task(task.task_id)
        assert approved.status == "approved"

    def test_approve_nonexistent_task(self):
        agent = AutomationAgent()
        with pytest.raises(ValueError):
            agent.approve_task("nonexistent")

    def test_risk_label(self):
        assert AutomationAgent.risk_label(5) == "low"
        assert AutomationAgent.risk_label(25) == "medium"
        assert AutomationAgent.risk_label(55) == "high"
        assert AutomationAgent.risk_label(95) == "critical"

    def test_list_tasks(self):
        agent = AutomationAgent()
        agent.create_task(name="Task A", description="A", steps=[{"action": "screenshot", "domain": "control"}])
        agent.create_task(name="Task B", description="B", steps=[{"action": "shutdown", "domain": "settings"}])
        all_tasks = agent.list_tasks()
        assert len(all_tasks) == 2
        pending = agent.list_tasks(status="pending")
        assert len(pending) == 1
        approved = agent.list_tasks(status="approved")
        assert len(approved) == 1

    def test_get_task(self):
        agent = AutomationAgent()
        task = agent.create_task(name="Test", description="T", steps=[])
        found = agent.get_task(task.task_id)
        assert found is not None
        assert found.name == "Test"

    def test_assess_risk_empty(self):
        assert AutomationAgent._assess_risk([]) == 0

    def test_assess_risk_mixed(self):
        steps = [
            {"action": "screenshot", "domain": "control"},
            {"action": "type", "domain": "control"},
            {"action": "volume_up", "domain": "settings"},
        ]
        risk = AutomationAgent._assess_risk(steps)
        assert 0 < risk <= 100
