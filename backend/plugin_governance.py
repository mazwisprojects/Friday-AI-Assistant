"""Governance metadata and lifecycle checks for generated Friday capabilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


DEFAULT_LIMITS = {"timeout_seconds": 60, "max_memory_mb": 256, "max_output_chars": 6000}
DEFAULT_GOVERNANCE = {
    "approval": "pending_review",
    "permissions": [],
    "dependencies": [],
    "resource_limits": DEFAULT_LIMITS,
    "test_fixtures": {},
    "security_review": "pending",
    "rollback_plan": "restore_previous_snapshot",
    "expires_at": None,
    "score": {"successes": 0, "failures": 0},
}


def normalize_governance(value: dict | None, trusted: bool = False) -> dict:
    governance = {**DEFAULT_GOVERNANCE, **(value or {})}
    governance["permissions"] = list(governance.get("permissions") or [])
    governance["dependencies"] = list(governance.get("dependencies") or [])
    governance["resource_limits"] = {**DEFAULT_LIMITS, **(governance.get("resource_limits") or {})}
    governance["score"] = {"successes": 0, "failures": 0, **(governance.get("score") or {})}
    if trusted and governance["approval"] == "pending_review":
        governance["approval"] = "approved"
        governance["security_review"] = "approved"
    return governance


def is_expired(governance: dict) -> bool:
    expires_at = governance.get("expires_at")
    if not expires_at:
        return False
    try:
        return datetime.fromisoformat(expires_at).astimezone(timezone.utc) <= datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return True


def default_expiry(days: int = 90) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(timespec="seconds")


def validate_limits(governance: dict) -> None:
    limits = governance.get("resource_limits", {})
    for key, minimum in (("timeout_seconds", 1), ("max_memory_mb", 16), ("max_output_chars", 100)):
        value = int(limits.get(key, DEFAULT_LIMITS[key]))
        if value < minimum or value > {"timeout_seconds": 3600, "max_memory_mb": 4096, "max_output_chars": 100000}[key]:
            raise ValueError(f"Invalid governance resource limit: {key}")


def is_active(manifest: dict) -> bool:
    if not manifest.get("enabled", True):
        return False
    governance = manifest.get("governance")
    if not governance:
        return True
    return governance.get("approval") == "approved" and governance.get("security_review") == "approved" and not is_expired(governance)
