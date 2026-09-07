"""Probe: does startup agent registration work against the real backend store?"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "backend"))

from agent_builder import AgentBuilder
from actions.agent_dispatcher import AgentDispatcher
from plugin_manager import PluginManager
from tool_builder import ToolBuilder

backend = ROOT / "backend"
dispatcher = AgentDispatcher()
tools = ToolBuilder(str(backend))
agents = AgentBuilder(str(backend))
manager = PluginManager(str(backend), tools, agents, dispatcher)
result = manager.register_startup_agents()
print(f"registered ({len(result['registered'])}): {sorted(result['registered'])}")
print(f"skipped ({len(result['skipped'])}): {result['skipped']}")

schedules = json.loads((ROOT / "long_term_memory" / "agent_schedules.json").read_text(encoding="utf-8"))
enabled = [s["agent_type"] for s in schedules if s.get("enabled")]
disabled = [s["agent_type"] for s in schedules if not s.get("enabled")]
print(f"schedules enabled ({len(enabled)}): {sorted(set(enabled))}")
print(f"schedules disabled ({len(disabled)}): {sorted(set(disabled))}")
known = dispatcher.registered_agents()
missing = sorted({s["agent_type"] for s in schedules if s.get("enabled") and s["agent_type"] not in known})
print(f"enabled schedules whose agent is NOT registered: {missing}")
print("REGISTRATION_OK" if not missing else "REGISTRATION_GAP")
