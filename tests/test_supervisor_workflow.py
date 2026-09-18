"""Tests for the supervisor/verifier workflow."""
import pytest
from backend.agents.supervisor_workflow import SupervisorWorkflow, WorkflowResult


class TestSupervisorWorkflow:
    def test_create_workflow(self):
        wf = SupervisorWorkflow()
        result = wf.create_workflow("Test task", risk_score=10)
        assert result.workflow_id
        assert result.task_description == "Test task"
        assert len(result.steps) == 7

    def test_run_low_risk_workflow(self):
        wf = SupervisorWorkflow()
        result = wf.create_workflow("Simple task", risk_score=10)
        run_result = wf.run_workflow(result.workflow_id)
        assert run_result.status == "completed"
        assert all(s.status == "completed" for s in run_result.steps)

    def test_run_high_risk_workflow_pauses(self):
        wf = SupervisorWorkflow()
        result = wf.create_workflow("Risky task", risk_score=80)
        run_result = wf.run_workflow(result.workflow_id)
        assert run_result.status == "paused"
        approval_step = [s for s in run_result.steps if s.name == "approval_gate"][0]
        assert approval_step.status == "paused"

    def test_approve_and_continue(self):
        wf = SupervisorWorkflow()
        result = wf.create_workflow("Risky task", risk_score=80)
        wf.run_workflow(result.workflow_id)
        approved = wf.approve_workflow(result.workflow_id)
        assert approved.approved is True
        approval_step = [s for s in approved.steps if s.name == "approval_gate"][0]
        assert approval_step.status == "completed"

    def test_get_workflow(self):
        wf = SupervisorWorkflow()
        result = wf.create_workflow("Test", risk_score=5)
        found = wf.get_workflow(result.workflow_id)
        assert found is not None
        assert found.task_description == "Test"

    def test_list_workflows(self):
        wf = SupervisorWorkflow()
        wf.create_workflow("Task A", risk_score=5)
        wf.create_workflow("Task B", risk_score=5)
        assert len(wf.list_workflows()) == 2

    def test_run_nonexistent_workflow(self):
        wf = SupervisorWorkflow()
        with pytest.raises(ValueError):
            wf.run_workflow("nonexistent")

    def test_run_with_execute_fn(self):
        wf = SupervisorWorkflow()
        result = wf.create_workflow("Task", risk_score=5)
        executed = []

        def mock_execute(desc):
            executed.append(desc)
            return {"ok": True}

        run_result = wf.run_workflow(result.workflow_id, execute_fn=mock_execute)
        assert run_result.status == "completed"
        assert len(executed) == 1
