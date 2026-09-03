"""Supervisor layer for tool execution planning and verification.

This lightweight orchestration layer gives the assistant a consistent
"inspect -> validate -> execute -> verify" flow for tool calls without
requiring a large framework. It is intentionally simple, explicit, and easy
for the rest of the project to consume.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List


class AgentSupervisor:
    """Plans, guards, and verifies tool execution across the Friday assistant."""

    DEFAULT_RISK_SCORES = {
        "read_file": 10,
        "write_file": 35,
        "read_directory": 15,
        "search_memory": 20,
        "list_projects": 10,
        "switch_project": 20,
        "list_smart_devices": 15,
        "control_light": 45,
        "desktop_control": 82,
        "browser_control": 70,
        "process_file": 55,
        "send_message": 65,
        "computer_control": 88,
        "computer_settings": 76,
        "open_application": 40,
        "build_project": 65,
        "code_helper": 50,
        "self_maintenance": 75,
        "game_updater": 78,
        "manage_uploads": 30,
        "discover_printers": 20,
        "print_stl": 80,
        "cancel_current_task": 35,
    }

    def __init__(self):
        self.execution_history: List[Dict[str, Any]] = []
        self.audit_log: List[Dict[str, Any]] = []
        self._task_journal: Dict[str, List[Dict[str, Any]]] = {"active": [], "completed": [], "failed": []}
        self._tasks: Dict[str, Dict[str, Any]] = {}

    def create_task(self, description: str, context: Dict[str, Any] | None = None, deadline_seconds: int | None = None) -> Dict[str, Any]:
        """Create a structured task object with a default agent loop: observe -> plan -> execute -> verify -> summarize."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        now = time.time()
        task = {
            "task_id": task_id,
            "description": description,
            "context": context or {},
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "deadline_seconds": deadline_seconds,
            "deadline_at": now + deadline_seconds if deadline_seconds else None,
            "retry_count": 0,
            "max_retries": 3,
            "result": None,
            "steps": [],
        }
        self._tasks[task_id] = task
        self._task_journal["active"].append({
            "task_id": task_id,
            "description": description,
            "status": "active",
            "updated_at": now,
        })
        return task

    def plan_task(self, task_id: str) -> Dict[str, Any]:
        """Break a task into a default orchestration loop: observe -> plan -> execute -> verify -> summarize."""
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Unknown task_id: {task_id}")

        steps = [
            {"name": "observe", "status": "pending"},
            {"name": "plan", "status": "pending"},
            {"name": "execute", "status": "pending"},
            {"name": "verify", "status": "pending"},
            {"name": "summarize", "status": "pending"},
        ]
        task["steps"] = steps
        task["status"] = "planned"
        task["updated_at"] = time.time()
        task["plan"] = {"task_id": task_id, "status": "planned", "steps": steps}
        return task["plan"]

    def validate_task_result(self, task_id: str, result: Any) -> Dict[str, Any]:
        """Run a result validation pass before the assistant reports completion to the user."""
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Unknown task_id: {task_id}")

        valid = self.verify_result(task.get("context", {}).get("tool", "task"), result)
        task["result"] = result
        task["validated"] = valid
        task["updated_at"] = time.time()

        if valid:
            task["status"] = "completed"
            self._task_journal["completed"].append({
                "task_id": task_id,
                "description": task["description"],
                "status": "completed",
                "updated_at": task["updated_at"],
            })
            self._task_journal["active"] = [item for item in self._task_journal["active"] if item["task_id"] != task_id]
        else:
            task["status"] = "failed"
            task["retry_count"] = task.get("retry_count", 0) + 1
            self._task_journal["failed"].append({
                "task_id": task_id,
                "description": task["description"],
                "status": "failed",
                "updated_at": task["updated_at"],
                "retry_count": task["retry_count"],
            })
            self._task_journal["active"] = [item for item in self._task_journal["active"] if item["task_id"] != task_id]

        return {"task_id": task_id, "verified": valid, "status": task["status"], "result": result}

    def get_task_journal(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return the shared task journal used by the orchestrator."""
        return {"active": list(self._task_journal["active"]), "completed": list(self._task_journal["completed"]), "failed": list(self._task_journal["failed"])}

    def set_task_status(self, task_id: str, status: str) -> Dict[str, Any]:
        """Update a task state and move it across the shared journal as needed."""
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Unknown task_id: {task_id}")
        task["status"] = status
        task["updated_at"] = time.time()
        return {"task_id": task_id, "status": status}

    def _default_steps(self, tool_name: str) -> List[str]:
        base = [
            "inspect_request",
            "validate_inputs",
            "execute_tool",
            "verify_result",
        ]
        if tool_name in {"desktop_control", "browser_control", "process_file", "send_message"}:
            return [
                "inspect_target",
                "validate_target",
                "execute_action",
                "verify_result",
            ]
        if tool_name in {"build_project", "code_helper", "self_maintenance"}:
            return [
                "plan_work",
                "validate_environment",
                "execute_work",
                "verify_result",
            ]
        return base

    def plan_tool_call(self, tool_name: str, args: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Return a structured plan for a tool call."""
        args = args or {}
        steps = [
            {"name": step_name, "status": "pending"}
            for step_name in self._default_steps(tool_name)
        ]
        plan = {
            "tool_name": tool_name,
            "status": "planned",
            "args": args,
            "steps": steps,
        }
        self.execution_history.append({"tool_name": tool_name, "plan": plan})
        return plan

    def verify_result(self, tool_name: str, result: Any) -> bool:
        """Return True when tool output looks successful, False when it looks failed."""
        if result is None:
            return False

        if isinstance(result, bool):
            return result

        if isinstance(result, str):
            text = result.strip().lower()
            if not text:
                return False
            if "error" in text or "failed" in text or "denied" in text or "not executed" in text:
                return False
            return True

        if isinstance(result, dict):
            if "ok" in result:
                return bool(result["ok"])
            if "success" in result:
                return bool(result["success"])
            if "status" in result:
                status = str(result["status"]).lower()
                if status in {"error", "failed", "denied", "cancelled"}:
                    return False
                return True
            if "error" in result and result["error"]:
                return False
            if "result" in result:
                nested = result["result"]
                if isinstance(nested, dict):
                    return self.verify_result(tool_name, nested)
                if isinstance(nested, str):
                    return self.verify_result(tool_name, nested)
            return True

        return True

    def record_execution(self, tool_name: str, result: Any) -> Dict[str, Any]:
        """Store execution result and return a quick summary."""
        outcome = {
            "tool_name": tool_name,
            "ok": self.verify_result(tool_name, result),
            "result": result,
        }
        self.execution_history.append({"tool_name": tool_name, "outcome": outcome})
        return outcome

    def _score_risk(self, tool_name: str, args: Dict[str, Any] | None, context: Dict[str, Any] | None) -> int:
        """Compute a per-tool risk score based on the tool and its arguments."""
        base = self.DEFAULT_RISK_SCORES.get(tool_name, 25)
        args = args or {}
        context = context or {}

        if "path" in args and isinstance(args["path"], str):
            p = args["path"].lower()
            if any(marker in p for marker in ("desktop", "documents", "pictures", "userprofile", "c:/", "windows")):
                base += 8
            if "wallpaper" in p or "system" in p:
                base += 10

        if "url" in args and isinstance(args["url"], str):
            if "http" in args["url"].lower() or "www" in args["url"].lower():
                base += 12

        if tool_name in {"browser_control", "desktop_control", "computer_control"} and args.get("action") in {"navigate", "click", "wallpaper", "keyboard", "mouse"}:
            base += 12

        if tool_name in {"send_message"} and args.get("receiver"):
            base += 8

        if context.get("safe_mode"):
            base += 10

        if not context.get("authenticated", True):
            base += 10

        return max(0, min(100, base))

    def evaluate_policy(self, tool_name: str, args: Dict[str, Any] | None, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Decide approval, safe-mode, and execution policy for a tool call."""
        args = args or {}
        context = context or {}
        risk_score = self._score_risk(tool_name, args, context)
        safe_mode = bool(context.get("safe_mode", False))
        authenticated = bool(context.get("authenticated", True))
        user_reason = str(context.get("user_reason", "")).strip()

        requires_approval = risk_score >= 70
        requires_confirmation = requires_approval or risk_score >= 60
        requires_reason = safe_mode and risk_score >= 40
        reversible = tool_name in {"desktop_control", "browser_control", "write_file", "process_file", "send_message"}

        allowed = True
        reason = "Policy check passed."

        if not authenticated and risk_score >= 50:
            allowed = False
            reason = "Authentication is required before running high-risk actions."

        if safe_mode and risk_score >= 60:
            allowed = False
            reason = "Safe mode is enabled and this action is too risky to run automatically."

        if requires_reason and not user_reason:
            allowed = False
            reason = "Safe mode requires a brief reason before executing this action."

        if requires_approval and not authenticated:
            allowed = False
            reason = "This action requires authentication and approval."

        policy = {
            "tool_name": tool_name,
            "args": args,
            "risk_score": risk_score,
            "requires_approval": requires_approval,
            "requires_confirmation": requires_confirmation,
            "requires_reason": requires_reason,
            "reversible": reversible,
            "safe_mode": safe_mode,
            "authenticated": authenticated,
            "allowed": allowed,
            "reason": reason,
        }
        self.execution_history.append({"tool_name": tool_name, "policy": policy})
        return policy

    def log_action(self, tool_name: str, args: Dict[str, Any] | None, outcome: Any, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Record an auditable action event with approval metadata and result."""
        args = args or {}
        context = context or {}
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "args": args,
            "context": context,
            "approved": bool(context.get("approved", outcome.get("approved", True) if isinstance(outcome, dict) else True)),
            "risk_score": context.get("risk_score", self._score_risk(tool_name, args, context)),
            "outcome": outcome,
        }
        if isinstance(outcome, dict):
            record["ok"] = bool(outcome.get("ok", outcome.get("success", True)))
        else:
            record["ok"] = bool(outcome)

        self.audit_log.append(record)
        return record
