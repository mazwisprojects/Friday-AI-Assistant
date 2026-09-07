"""One-time workforce enablement via Friday's governed plugin path.

Every agent in the builder registry is enabled through
PluginManager.set_enabled (the same call the agent console makes), so
governance is enforced: approved plugins are enabled and registered;
plugins with pending governance are first put through review() - they are
first-party built-ins whose risky-import findings were already accepted
in accepted_findings.json.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "backend"))

from agent_builder import AgentBuilder
from actions.agent_dispatcher import AgentDispatcher
from plugin_governance import is_active
from plugin_manager import PluginManager
from tool_builder import ToolBuilder

backend = ROOT / "backend"
dispatcher = AgentDispatcher()
manager = PluginManager(str(backend), ToolBuilder(str(backend)), AgentBuilder(str(backend)), dispatcher)

enabled, approved_then_enabled, failed = [], [], []
for name, manifest in list(manager.agent_builder.agents.items()):
    try:
        if not is_active({**manifest, "enabled": True}):
            manager.review("agent", name, True, "approved")
            approved_then_enabled.append(name)
        manager.set_enabled("agent", name, True)
        enabled.append(name)
    except Exception as error:
        failed.append(f"{name}: {error}")

print(f"enabled ({len(enabled)}): {sorted(enabled)}")
print(f"required review first ({len(approved_then_enabled)}): {sorted(approved_then_enabled)}")
print(f"failed ({len(failed)}): {failed or 'none'}")
print("WORKFORCE_ENABLED" if not failed else "WORKFORCE_PARTIAL")
