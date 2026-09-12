"""Central policy for Friday and OpenClaw actions.

NO LIMITS - Friday can build and execute anything.
User takes responsibility for what they build.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# Actions that can cause irreversible local changes.
ALWAYS_CONFIRM = {
    "computer_settings",
    "self_maintenance",
    "self_modify",
}
APPROVAL_REQUIRED = {
    "send_message",
    "google_calendar_create",
}
NOTIFY_ONLY: set[str] = set()


def decision(tool_name: str, args: dict | None = None) -> dict:
    args = args or {}
    if tool_name == "game_updater" and args.get("shutdown_when_done"):
        return {"tier": "always_confirm", "reason": "The action can shut down the computer."}
    if tool_name == "self_maintenance" and args.get("action") == "self_upgrade":
        return {"tier": "always_confirm", "reason": "Self-upgrade changes the running assistant."}
    if tool_name in ALWAYS_CONFIRM:
        return {"tier": "always_confirm", "reason": "This action can change system state."}
    if tool_name in APPROVAL_REQUIRED:
        return {"tier": "approval_required", "reason": "This action affects an external service or recipient."}
    if tool_name in NOTIFY_ONLY:
        return {"tier": "notify_only", "reason": "The action is reported after execution."}
    return {"tier": "automatic", "reason": "Read-only or bounded local action."}


def requires_confirmation(tool_name: str, args: dict | None = None) -> bool:
    return decision(tool_name, args)["tier"] in {"always_confirm", "approval_required"}
