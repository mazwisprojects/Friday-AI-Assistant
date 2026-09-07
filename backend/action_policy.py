"""Central policy for Friday and OpenClaw actions.

NO LIMITS - Friday can build and execute anything.
User takes responsibility for what they build.
"""

from __future__ import annotations


# NO CONFIRMATION REQUIRED - Friday can do anything
ALWAYS_CONFIRM: set = set()
NOTIFY_ONLY: set = set()


def decision(tool_name: str, args: dict | None = None) -> dict:
    # NO LIMITS - All actions are automatic
    return {"tier": "automatic", "reason": "No limits - Friday can build and execute anything."}


def requires_confirmation(tool_name: str, args: dict | None = None) -> bool:
    # NO CONFIRMATION REQUIRED
    return False
