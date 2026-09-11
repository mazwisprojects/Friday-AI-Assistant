"""
Action Registry for F.R.I.D.A.Y — maps decisions to the REAL tool registry.

The Decision Engine no longer scores abstract strings; it scores concrete
`{tool, params}` actions drawn from the actual 106 registered tools. This is
what turns "I'll take care of that" into her actually doing it.

Safe/autonomous classification lets the decision engine act without approval
for low-risk actions, and escalate to Sir for destructive or irreversible ones.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Tools that are safe to run autonomously (read/informational, non-destructive).
# Anything not listed here requires approval.
_AUTONOMOUS_TOOLS = {
    "get_local_time", "get_weather", "get_system_status", "get_print_status",
    "discover_printers", "web_search", "search_memory", "semantic_search",
    "gmail_read", "gmail_thread_read", "google_calendar_list",
    "google_calendar_availability", "google_contacts_read", "google_drive_list",
    "read_file", "read_directory", "list_projects", "execution_history",
    "model_router", "manage_monitors", "list_smart_devices", "openclaw_capabilities",
    "test_custom_tool", "test_agent", "manage_goals", "run_routine",
    "manage_tasks", "manage_snapshots", "manage_uploads", "run_custom_tool",
}

# Destructive / irreversible tools that ALWAYS require explicit approval.
_HIGH_RISK_TOOLS = {
    "undo_last_action", "self_modify", "self_maintenance", "git_workflow",
    "computer_control", "desktop_control", "browser_control", "run_powershell_command",
    "run_script", "write_file", "manage_files", "process_file",
    "google_calendar_delete", "google_calendar_update", "gmail_create_draft",
    "contacts_manager", "manage_sync", "run_web_agent", "deploy_agent",
    "schedule_agent", "build_agent", "build_project", "create_project",
    "print_stl", "game_updater", "open_application", "generate_cad",
    "generate_cad_prototype", "iterate_cad", "send_message", "set_reminder",
    "initiative_control", "critic_loop", "sync_google_services",
}


@dataclass
class ActionSpec:
    """A concrete, executable action."""
    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    risk_level: str = "low"       # low | medium | high | critical
    autonomous: bool = False      # can run without approval
    confidence: float = 0.5


class ActionRegistry:
    """Lazily enumerate and classify the real F.R.I.D.A.Y tool registry."""

    def __init__(self):
        self._tools: list[str] | None = None
        self._tool_metadata: dict[str, dict] = {}

    def _load_tools(self) -> list[str]:
        """Lazy-load the real tool names from tools.py (no import at init)."""
        if self._tools is not None:
            return self._tools
        try:
            import tools  # backend root on sys.path
            declarations = tools.tools_list[0]["function_declarations"]
            self._tools = sorted(d.get("name", "") for d in declarations if d.get("name"))
            for d in declarations:
                name = d.get("name")
                if name:
                    desc = d.get("description", "")
                    self._tool_metadata[name] = {"description": desc[:200]}
        except Exception as e:
            logger.warning("Could not load tool registry: %s", e)
            self._tools = []
        return self._tools

    @property
    def tools(self) -> list[str]:
        return self._load_tools()

    def exists(self, tool: str) -> bool:
        return tool in self._load_tools()

    def risk_for(self, tool: str) -> str:
        if tool in _HIGH_RISK_TOOLS:
            return "high"
        if tool in _AUTONOMOUS_TOOLS:
            return "low"
        return "medium"

    def is_autonomous(self, tool: str) -> bool:
        """True if this tool can run without explicit approval."""
        return tool in _AUTONOMOUS_TOOLS

    def description_for(self, tool: str) -> str:
        self._load_tools()
        return self._tool_metadata.get(tool, {}).get("description", "")

    def suggest(self, intent: str) -> list[str]:
        """Map a situation intent to candidate real tools."""
        intent = (intent or "").lower()
        mapping = {
            "search_request": ["web_search", "semantic_search"],
            "information_request": ["search_memory", "web_search"],
            "creation_request": ["write_file", "create_project", "generate_cad"],
            "action_request": ["run_routine", "manage_tasks"],
            "requesting_help": ["read_file", "web_search"],
            "urgent_request": ["get_system_status", "send_message"],
        }
        for key, tools in mapping.items():
            if key in intent:
                return [t for t in tools if self.exists(t)]
        return []

    def to_spec(self, tool: str, description: str = "", confidence: float = 0.5) -> ActionSpec:
        """Wrap a tool name into an ActionSpec with real risk/autonomy classification."""
        tool = tool.strip()
        if not self.exists(tool):
            tool = next((t for t in self.tools if tool.lower() in t.lower()), tool)
        return ActionSpec(
            tool=tool,
            description=description or self.description_for(tool) or f"Use {tool}",
            risk_level=self.risk_for(tool),
            autonomous=self.is_autonomous(tool),
            confidence=confidence,
        )

    def available_action_summary(self) -> dict[str, Any]:
        """Summary for diagnostics: total, autonomous, high-risk counts."""
        tools = self._load_tools()
        return {
            "total_tools": len(tools),
            "autonomous": sorted(t for t in tools if t in _AUTONOMOUS_TOOLS),
            "high_risk": sorted(t for t in tools if t in _HIGH_RISK_TOOLS),
        }


# Process-wide singleton — lazy-loads the real registry on first use.
registry = ActionRegistry()
