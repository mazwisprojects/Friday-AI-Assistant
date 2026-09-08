"""Goal Engine for FRIDAY — persistent long-horizon goals with milestones, journaling, and auto-resume."""
from __future__ import annotations
import json, time, uuid
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "goals.json"
_VALID_STATUS = ("active", "paused", "done", "failed", "cancelled")

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"goals": []}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")

def _find(state: dict, goal_id: str):
    return next((g for g in state["goals"] if g["id"] == goal_id), None)

def _recompute_progress(goal: dict) -> None:
    ms = goal.get("milestones", [])
    goal["progress"] = round(100.0 * sum(1 for m in ms if m.get("done")) / len(ms), 1) if ms else 0.0

def create_goal(title: str, description: str = "", milestones: list = None, due: str = None) -> dict:
    """Create a persistent goal; milestones is a list of strings."""
    if not (title or "").strip():
        return {"ok": False, "error": "Goal needs a title"}
    state = _load()
    goal = {
        "id": "g_" + uuid.uuid4().hex[:8],
        "title": title.strip(), "description": description or "",
        "status": "active", "due": due,
        "milestones": [{"i": i, "text": str(m), "done": False} for i, m in enumerate(milestones or [])],
        "progress": 0.0, "journal": [], "created_at": time.time(), "updated_at": time.time(),
    }
    state["goals"].insert(0, goal)
    _save(state)
    return {"ok": True, "goal_id": goal["id"], "goal": goal}

def list_goals(status: str = "active") -> dict:
    state = _load()
    goals = state["goals"]
    if status and status != "all":
        goals = [g for g in goals if g["status"] == status]
    return {"ok": True, "goals": goals, "count": len(goals)}

def update_milestone(goal_id: str, index: int, done: bool = True) -> dict:
    state = _load()
    goal = _find(state, goal_id)
    if not goal:
        return {"ok": False, "error": "Goal not found", "goal_id": goal_id}
    ms = goal.get("milestones", [])
    if not 0 <= int(index) < len(ms):
        return {"ok": False, "error": "Milestone index out of range", "valid": list(range(len(ms)))}
    ms[int(index)]["done"] = bool(done)
    _recompute_progress(goal)
    goal["updated_at"] = time.time()
    if goal["progress"] == 100.0 and goal["status"] == "active":
        goal["status"] = "done"
    _save(state)
    return {"ok": True, "goal_id": goal_id, "progress": goal["progress"], "status": goal["status"]}
def journal(goal_id: str, entry: str) -> dict:
    state = _load()
    goal = _find(state, goal_id)
    if not goal:
        return {"ok": False, "error": "Goal not found"}
    goal.setdefault("journal", []).append({"t": time.time(), "entry": (entry or "")[:500]})
    goal["updated_at"] = time.time()
    _save(state)
    return {"ok": True, "goal_id": goal_id, "journal_entries": len(goal["journal"])}

def set_status(goal_id: str, status: str) -> dict:
    if status not in _VALID_STATUS:
        return {"ok": False, "error": "Invalid status", "valid": list(_VALID_STATUS)}
    state = _load()
    goal = _find(state, goal_id)
    if not goal:
        return {"ok": False, "error": "Goal not found"}
    goal["status"] = status
    goal["updated_at"] = time.time()
    _save(state)
    return {"ok": True, "goal_id": goal_id, "status": status}

def tick(stale_hours: float = 24.0) -> dict:
    """What goals need attention right now? Called on startup/reconnect for auto-resume."""
    state = _load()
    now = time.time()
    active = [g for g in state["goals"] if g["status"] == "active"]
    out = []
    for g in active:
        next_ms = next((m["text"] for m in g.get("milestones", []) if not m.get("done")), None)
        stale = (now - g.get("updated_at", 0)) > stale_hours * 3600
        out.append({"id": g["id"], "title": g["title"], "progress": g["progress"],
                    "next_milestone": next_ms, "due": g.get("due"),
                    "needs_attention": stale, "last_journal": (g.get("journal") or [{}])[-1].get("entry")})
    return {"ok": True, "active_goals": out, "count": len(out)}

def context() -> str:
    """Compact goal context injected into startup/reconnect memory."""
    active = tick().get("active_goals", [])
    if not active:
        return ""
    lines = ["OPEN GOALS (resume working on these when relevant):"]
    for g in active[:8]:
        due = ", due %s" % g["due"] if g.get("due") else ""
        nxt = ", next: %s" % g["next_milestone"] if g.get("next_milestone") else ""
        flag = " [STALE - needs attention]" if g["needs_attention"] else ""
        lines.append("- [%s] %s (%.0f%% done%s)%s%s" % (g["id"], g["title"], g["progress"], nxt, due, flag))
    return "\n".join(lines)

def stats() -> dict:
    state = _load()
    by_status = {}
    for g in state["goals"]:
        by_status[g["status"]] = by_status.get(g["status"], 0) + 1
    return {"ok": True, "total": len(state["goals"]), "by_status": by_status}

def goals_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "")
    if action == "create":
        return create_goal(a.get("title", ""), a.get("description", ""), a.get("milestones", []), a.get("due"))
    if action == "list":
        return list_goals(a.get("status", "active"))
    if action == "milestone":
        return update_milestone(a.get("goal_id", ""), int(a.get("index", 0)), bool(a.get("done", True)))
    if action == "journal":
        return journal(a.get("goal_id", ""), a.get("entry", ""))
    if action == "status":
        return set_status(a.get("goal_id", ""), a.get("status", "paused"))
    if action == "tick":
        return tick(float(a.get("stale_hours", 24)))
    if action == "context":
        return {"ok": True, "context": context()}
    if action == "stats":
        return stats()
    return {"ok": False, "error": "Unknown goals action"}