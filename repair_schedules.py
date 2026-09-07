"""One-time schedule repair after enabling startup agent registration.

- Deletes the auto-generated workflow_* wrapper schedules (they duplicate the
  default workflows or wrap test-fixture targets that do not exist).
- Deletes the ungoverned 'self_upgrade' schedule Friday created for itself.
- Enables and resets every schedule whose agent type resolves to a real
  backend/agents module; leaves the rest disabled and reports them.
"""
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).parent
SCHEDULES = ROOT / "long_term_memory" / "agent_schedules.json"
AGENTS_DIR = ROOT / "backend" / "agents"

known_agents = {path.stem for path in AGENTS_DIR.glob("*.py") if not path.stem.startswith("__")}
schedules = json.loads(SCHEDULES.read_text(encoding="utf-8"))
shutil.copy2(SCHEDULES, SCHEDULES.with_suffix(".json.bak"))

kept, deleted, left_disabled = [], [], []
kept_schedules = []
for schedule in schedules:
    agent_type = schedule.get("agent_type", "")
    if agent_type.startswith("workflow_"):
        deleted.append(f"{agent_type} (auto-generated wrapper)")
        continue
    if agent_type == "self_upgrade":
        deleted.append(f"{agent_type} (ungoverned self-modification schedule, nonexistent target)")
        continue
    if agent_type in known_agents:
        schedule["enabled"] = True
        schedule["retry_count"] = 0
        schedule["last_status"] = "never_run"
        schedule.pop("last_error", None)
        kept.append(agent_type)
        kept_schedules.append(schedule)
        continue
    schedule["enabled"] = False
    left_disabled.append(f"{agent_type}: {schedule.get('last_error', 'unknown target')}")
    kept_schedules.append(schedule)

for attempt in range(4):
    try:
        temporary = SCHEDULES.with_suffix(".tmp")
        temporary.write_text(json.dumps(kept_schedules, indent=2), encoding="utf-8")
        temporary.replace(SCHEDULES)
        break
    except PermissionError:
        if attempt == 3:
            raise
        time.sleep(0.1 * (attempt + 1))

print(f"known agent modules: {sorted(known_agents)}")
print(f"enabled+reset schedules ({len(kept)}): {sorted(set(kept))}")
print(f"deleted schedules ({len(deleted)}): {deleted}")
print(f"left disabled ({len(left_disabled)}): {left_disabled or 'none'}")
