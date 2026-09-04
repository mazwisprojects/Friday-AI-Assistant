"""Central human-control policy for Friday and OpenClaw actions."""

from __future__ import annotations


ALWAYS_CONFIRM = {
    "computer_control", "computer_settings", "write_file", "manage_files", "desktop_control",
    "send_message", "gmail_create_draft", "google_calendar_create", "google_calendar_update",
    "google_calendar_delete", "google_calendar_recurring", "google_contacts_import",
    "google_contacts_sync", "run_powershell_command", "git_workflow",
}

NOTIFY_ONLY = {"build_custom_tool", "build_agent", "deploy_agent", "schedule_agent", "self_maintenance"}


def decision(tool_name: str, args: dict | None = None) -> dict:
    args = args or {}
    action = str(args.get("action", "")).lower()
    if (tool_name == "computer_settings" and action in {"shutdown", "restart"}) or (tool_name == "game_updater" and bool(args.get("shutdown_when_done"))):
        return {"tier": "always_confirm", "reason": "Power actions always require explicit confirmation."}
    if tool_name == "self_maintenance" and action == "self_upgrade":
        return {"tier": "always_confirm", "reason": "Core dependency upgrades require explicit confirmation."}
    if tool_name in ALWAYS_CONFIRM:
        return {"tier": "approval_required", "reason": "This action changes external state or can be difficult to undo."}
    if tool_name in NOTIFY_ONLY:
        return {"tier": "notify_only", "reason": "This action may run, but Friday must report the result."}
    return {"tier": "automatic", "reason": "Read-only or bounded action."}


def requires_confirmation(tool_name: str, args: dict | None = None) -> bool:
    return decision(tool_name, args)["tier"] in {"approval_required", "always_confirm"}
