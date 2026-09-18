"""Persistent human-reviewed plans. This module never builds or executes code."""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import threading
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


class PlanConflict(ValueError):
    """The submitted revision or lifecycle transition is no longer valid."""


class CapabilityPlanStore:
    """Single-process store; share one instance between all request handlers."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self._lock = threading.RLock()

    @staticmethod
    def validate(plan: dict) -> dict:
        if not isinstance(plan, dict):
            raise ValueError("plan must be an object")
        fields = {"title", "goal", "kind", "steps", "risks", "advantages", "permissions", "tests", "first_run", "rollback"}
        if set(plan) != fields:
            raise ValueError("plan must contain exactly: " + ", ".join(sorted(fields)))
        for key in ("title", "goal", "first_run", "rollback"):
            if not isinstance(plan[key], str) or not plan[key].strip():
                raise ValueError(f"{key} must be nonempty text")
        if plan["kind"] not in ("tool", "agent", "workflow", "app"):
            raise ValueError("kind must be tool, agent, workflow, or app")
        for key in ("steps", "risks", "advantages", "permissions", "tests"):
            values = plan[key]
            if not isinstance(values, list) or len(values) > 100:
                raise ValueError(f"{key} must be a list of at most 100 items")
            if key != "permissions" and not values:
                raise ValueError(f"{key} must not be empty")
            if any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError(f"{key} must contain nonempty text")
        if len(json.dumps(plan, ensure_ascii=False).encode("utf-8")) > 32000:
            raise ValueError("plan exceeds 32000 bytes")
        return copy.deepcopy(plan)

    @staticmethod
    def _hash(plan: dict) -> str:
        return hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def _path(self, plan_id: str) -> Path:
        try:
            canonical = str(uuid.UUID(plan_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("Invalid plan ID") from exc
        return self.directory / f"{canonical}.json"

    def _save(self, record: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(record["id"])
        temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)
        except OSError as exc:
            logger.error("Failed to persist capability plan %s: %s", record.get("id"), exc)
            raise
        finally:
            temporary.unlink(missing_ok=True)

    def create(self, plan: dict, *, owner: str = "server_token_owner") -> dict:
        content = self.validate(plan)
        record = {"id": str(uuid.uuid4()), "version": 1, "status": "pending", "owner": owner,
                  "plan": content, "content_hash": self._hash(content),
                  "created_at": time.time(), "history": [], "approval": None,
                  "assessment_status": "human_review_required", "execution_available": False,
                  "implementation": None}
        with self._lock:
            self._save(record)
        return copy.deepcopy(record)

    def get(self, plan_id: str) -> dict:
        with self._lock:
            # Corrupt storage must raise, never silently recreate or approve a plan.
            record = json.loads(self._path(plan_id).read_text(encoding="utf-8"))
            if record["content_hash"] != self._hash(record["plan"]):
                raise PlanConflict("Stored plan content does not match its hash")
            return record

    def transition(self, plan_id: str, version: int, action: str, *, plan=None, content_hash=None) -> dict:
        if type(version) is not int or version < 1:
            raise ValueError("version must be a positive integer")
        if action not in {"edit", "approve", "cancel"}:
            raise ValueError("Unknown plan action")
        with self._lock:
            record = self.get(plan_id)
            if record["version"] != version:
                raise PlanConflict("Plan changed; review the latest version")
            if record["status"] == "cancelled":
                raise PlanConflict("Cancelled plans cannot be changed")
            if action == "approve":
                if content_hash != record["content_hash"]:
                    raise PlanConflict("Approval must match the reviewed content hash")
                if record["status"] == "approved":
                    return record  # Duplicate clicks do not create another action.
                if record["status"] == "implemented":
                    raise PlanConflict("This version is already implemented; edit the plan to build a new version")
                record["approval"] = {"version": version, "content_hash": content_hash,
                                      "approved_at": time.time(), "actor": record.get("owner", "server_token_owner")}
                record["status"] = "approved"
            elif action == "edit":
                content = self.validate(plan)
                record["history"].append({"version": version, "plan": record["plan"],
                                          "content_hash": record["content_hash"],
                                          "approval": record["approval"]})
                # A new revision is unapproved and unimplemented; the previous
                # artifact stays live but no longer answers for this revision.
                record.update(plan=content, version=version + 1, status="pending",
                              content_hash=self._hash(content), approval=None,
                              execution_available=False)
            else:
                if record["status"] == "implemented":
                    raise PlanConflict(
                        "This plan is already implemented and its capability is live; "
                        "edit the plan or disable the capability instead of cancelling the plan")
                record.update(status="cancelled", approval=None, execution_available=False)
            self._save(record)
            return copy.deepcopy(record)

    def record_implementation(self, plan_id: str, version: int, implementation: dict) -> dict:
        """Attach the outcome of the build/verify/register stage.

        Deliberately not a `transition` action: the review API can only record
        human decisions, so execution stays reachable solely through an
        authenticated device session. Only a verified artifact may set
        execution_available, and a failed attempt stays retryable.
        """
        if type(version) is not int or version < 1:
            raise ValueError("version must be a positive integer")
        if not isinstance(implementation, dict):
            raise ValueError("implementation must be an object")
        with self._lock:
            record = self.get(plan_id)
            if record["version"] != version:
                raise PlanConflict("Plan changed while it was being built; the build was discarded")
            if record["status"] == "cancelled":
                raise PlanConflict("Cancelled plans cannot be implemented")
            if record["status"] == "implemented":
                raise PlanConflict("This version is already implemented; edit the plan to build a new version")
            if record["status"] not in {"approved", "implement_failed"}:
                # A failed attempt keeps the approval, so it stays retryable.
                raise PlanConflict("Only an approved plan can be implemented")
            verification = json.loads(json.dumps(implementation, default=str))
            verified = implementation.get("status") == "implemented" and implementation.get("verified") is True
            record["implementation"] = {**verification, "version": version}
            record["status"] = "implemented" if verified else "implement_failed"
            record["execution_available"] = verified
            self._save(record)
            return copy.deepcopy(record)
