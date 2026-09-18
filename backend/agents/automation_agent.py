from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any


class RiskLevel(IntEnum):
    RISK_LOW = 1
    RISK_MEDIUM = 2
    RISK_HIGH = 3


RISK_LOW = RiskLevel.RISK_LOW
RISK_MEDIUM = RiskLevel.RISK_MEDIUM
RISK_HIGH = RiskLevel.RISK_HIGH


@dataclass
class AutomationTask:
    """A controlled automation task with risk assessment and approval flow."""
    name: str
    description: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    risk_score: int = 1
    requires_approval: bool = False
    status: str = "pending"
    task_id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    approved_by: str | None = None
    error_message: str | None = None
    result_data: dict[str, Any] | None = None

    def __post_init__(self):
        if self.task_id is None:
            import uuid
            object.__setattr__(self, "task_id", str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "risk_score": self.risk_score,
            "requires_approval": self.requires_approval,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "approved_by": self.approved_by,
            "error_message": self.error_message,
            "result_data": self.result_data,
        }

    def approve(self, approver: str) -> None:
        self.approved_by = approver
        self.status = "approved"

    def reject(self, reason: str) -> None:
        self.status = "rejected"
        self.error_message = reason

    def complete(self, result: dict[str, Any] | None = None) -> None:
        self.status = "completed"
        self.completed_at = datetime.utcnow()
        self.result_data = result

    def fail(self, error: str) -> None:
        self.status = "failed"
        self.completed_at = datetime.utcnow()
        self.error_message = error


class AutomationAgent:
    """Create, validate, and execute controlled automation tasks."""

    def __init__(self, event_bus=None):
        self._bus = event_bus
        self._tasks: dict[str, AutomationTask] = {}
        self._history: list[dict[str, Any]] = []

    def _get_bus(self):
        if self._bus is None:
            from backend.event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    def create_task(self, name: str, description: str,
                    steps: list[dict[str, Any]]) -> AutomationTask:
        """Create an automation task with risk assessment."""
        risk = self._assess_risk(steps)
        requires_approval = risk > RISK_LOW
        task = AutomationTask(
            name=name, description=description, steps=steps,
            risk_score=risk, requires_approval=requires_approval,
            status="pending" if requires_approval else "approved",
        )
        self._tasks[task.task_id] = task
        self._get_bus().publish_simple("automation.request", task.to_dict(),
                                       priority="important" if risk > RISK_HIGH else "normal")
        return task

    def approve_task(self, task_id: str) -> AutomationTask:
        """Approve a pending automation task."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")
        if task.status != "pending":
            raise ValueError(f"Task is not pending: {task.status}")
        task.status = "approved"
        self._get_bus().publish_simple("automation.approved", task.to_dict())
        return task

    async def execute_task(self, task_id: str,
                           computer_control_fn: Callable | None = None,
                           computer_settings_fn: Callable | None = None) -> AutomationTask:
        """Execute an approved automation task step by step."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")
        if task.status != "approved":
            raise ValueError(f"Task not approved: {task.status}")
        task.status = "running"
        try:
            for step in task.steps:
                step["status"] = "running"
                step_result = await self._execute_step(step, computer_control_fn, computer_settings_fn)
                step["status"] = "completed" if step_result.get("ok") else "failed"
                step["result"] = step_result
                if not step_result.get("ok"):
                    task.status = "failed"
                    break
            else:
                task.status = "completed"
        except Exception:
            task.status = "failed"
            logger.exception("Automation task failed: %s", task_id)
        self._history.append({
            "task_id": task.task_id, "name": task.name, "status": task.status,
            "completed_at": time.time(), "steps": len(task.steps),
        })
        self._get_bus().publish_simple("automation.completed", task.to_dict())
        return task

    async def _execute_step(self, step: dict[str, Any],
                            computer_control_fn, computer_settings_fn) -> dict[str, Any]:
        """Execute a single automation step."""
        action = step.get("action", "")
        domain = step.get("domain", "control")
        if domain == "settings" and computer_settings_fn:
            try:
                result = await computer_settings_fn(action, step)
                return {"ok": True, "result": result}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
        elif computer_control_fn:
            try:
                result = await computer_control_fn(action, step)
                return {"ok": True, "result": result}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
        return {"ok": False, "error": "No execution function provided"}

    @staticmethod
    def _assess_risk(steps: list[dict[str, Any]]) -> int:
        total_risk = 0
        for step in steps:
            action = step.get("action", "")
            domain = step.get("domain", "control")
            if domain == "settings":
                total_risk += SETTINGS_RISK.get(action, 20)
            else:
                total_risk += ACTION_RISK.get(action, 15)
        return min(100, total_risk)

    @staticmethod
    def risk_label(score: int) -> str:
        if score <= RISK_LOW:
            return "low"
        elif score <= RISK_MEDIUM:
            return "medium"
        elif score <= RISK_HIGH:
            return "high"
        return "critical"

    def get_task(self, task_id: str) -> Optional[AutomationTask]:
        return self._tasks.get(task_id)

    def list_tasks(self, status: str | None = None) -> list[AutomationTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def get_history(self) -> list[dict[str, Any]]:
        return list(self._history)


_AUTOMATION_AGENT: Optional[AutomationAgent] = None


def get_automation_agent() -> AutomationAgent:
    global _AUTOMATION_AGENT
    if _AUTOMATION_AGENT is None:
        _AUTOMATION_AGENT = AutomationAgent()
    return _AUTOMATION_AGENT

ACTION_RISK = {
    "type": 10, "smart_type": 10, "click": 10, "double_click": 10,
    "right_click": 10, "move": 5, "drag": 15, "hotkey": 20, "press": 10,
    "scroll": 5, "copy": 5, "paste": 15, "screenshot": 5, "wait": 0,
    "clear_field": 15, "focus_window": 5, "random_data": 15, "user_data": 15,
}
SETTINGS_RISK = {
    "volume_up": 5, "volume_down": 5, "volume_set": 5, "mute": 5,
    "brightness_up": 5, "brightness_down": 5, "close_window": 30,
    "minimize": 5, "maximize": 5, "snap_left": 5, "snap_right": 5,
    "switch_window": 10, "show_desktop": 5, "new_tab": 5, "close_tab": 5,
    "next_tab": 5, "prev_tab": 5, "go_back": 5, "go_forward": 5,
    "zoom_in": 0, "zoom_out": 0, "dark_mode": 5, "toggle_wifi": 30,
    "lock_screen": 15, "restart": 90, "shutdown": 95,
}
RISK_LOW = 15
RISK_MEDIUM = 40
RISK_HIGH = 70
