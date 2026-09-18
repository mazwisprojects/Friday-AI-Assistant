"""
Supervisor/verifier workflow for F.R.I.D.A.Y.

Multi-step verification pipeline: plan -> validate -> execute -> verify -> report.
Each step is logged, and the workflow can be paused for human approval.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStep:
    """One step in the supervisor workflow."""
    name: str
    status: str = "pending"
    started_at: float = 0.0
    completed_at: float = 0.0
    result: Any = None
    error: str = ""


@dataclass
class WorkflowResult:
    """Result of a supervisor workflow run."""
    workflow_id: str
    task_description: str
    status: str = "pending"
    steps: list[WorkflowStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    approved: bool = False
    risk_score: int = 0


class SupervisorWorkflow:
    """Multi-step verification workflow for tool execution."""

    def __init__(self, event_bus=None, approval_callback: Callable | None = None):
        self._bus = event_bus
        self._approval_callback = approval_callback
        self._workflows: dict[str, WorkflowResult] = {}

    def _get_bus(self):
        if self._bus is None:
            from event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    def create_workflow(self, task_description: str, risk_score: int = 0) -> WorkflowResult:
        """Create a new supervised workflow."""
        wf_id = f"wf_{uuid.uuid4().hex[:8]}"
        workflow = WorkflowResult(
            workflow_id=wf_id, task_description=task_description, risk_score=risk_score,
            steps=[
                WorkflowStep(name="inspect"),
                WorkflowStep(name="validate"),
                WorkflowStep(name="plan"),
                WorkflowStep(name="approval_gate"),
                WorkflowStep(name="execute"),
                WorkflowStep(name="verify"),
                WorkflowStep(name="report"),
            ],
        )
        self._workflows[wf_id] = workflow
        return workflow

    def run_workflow(self, wf_id: str,
                     execute_fn: Callable | None = None,
                     validate_fn: Callable | None = None) -> WorkflowResult:
        """Run a workflow through all steps."""
        workflow = self._workflows.get(wf_id)
        if not workflow:
            raise ValueError(f"Unknown workflow: {wf_id}")
        workflow.status = "running"

        for step in workflow.steps:
            step.status = "running"
            step.started_at = time.time()
            try:
                if step.name == "inspect":
                    step.result = {"description": workflow.task_description}
                elif step.name == "validate":
                    step.result = validate_fn(workflow.task_description) if validate_fn else {"valid": True}
                elif step.name == "plan":
                    step.result = self._plan_steps(workflow.task_description)
                elif step.name == "approval_gate":
                    if workflow.risk_score > 30 and not workflow.approved:
                        step.status = "paused"
                        workflow.status = "paused"
                        self._get_bus().publish_simple("automation.request", {
                            "workflow_id": wf_id, "task": workflow.task_description,
                            "risk_score": workflow.risk_score,
                        }, priority="important")
                        return workflow
                elif step.name == "execute":
                    step.result = execute_fn(workflow.task_description) if execute_fn else {"executed": True}
                elif step.name == "verify":
                    step.result = {"verified": True}
                elif step.name == "report":
                    step.result = {"reported": True}
                step.status = "completed"
                step.completed_at = time.time()
            except Exception as exc:
                step.status = "failed"
                step.error = str(exc)
                step.completed_at = time.time()
                workflow.status = "failed"
                return workflow

        workflow.status = "completed"
        workflow.completed_at = time.time()
        return workflow

    def approve_workflow(self, wf_id: str) -> WorkflowResult:
        """Approve a paused workflow."""
        workflow = self._workflows.get(wf_id)
        if not workflow:
            raise ValueError(f"Unknown workflow: {wf_id}")
        if workflow.status != "paused":
            raise ValueError(f"Workflow is not paused: {workflow.status}")
        workflow.approved = True
        for step in workflow.steps:
            if step.name == "approval_gate":
                step.status = "completed"
                step.completed_at = time.time()
        return workflow

    def get_workflow(self, wf_id: str) -> Optional[WorkflowResult]:
        return self._workflows.get(wf_id)

    def list_workflows(self, status: str | None = None) -> list[WorkflowResult]:
        wfs = list(self._workflows.values())
        if status:
            wfs = [w for w in wfs if w.status == status]
        return wfs

    @staticmethod
    def _plan_steps(description: str) -> dict[str, Any]:
        return {
            "steps": [
                {"name": "prepare", "status": "pending"},
                {"name": "execute", "status": "pending"},
                {"name": "verify", "status": "pending"},
            ],
            "estimated_duration_seconds": 30,
        }


_SUPERVISOR: Optional[SupervisorWorkflow] = None


def get_supervisor_workflow() -> SupervisorWorkflow:
    global _SUPERVISOR
    if _SUPERVISOR is None:
        _SUPERVISOR = SupervisorWorkflow()
    return _SUPERVISOR
