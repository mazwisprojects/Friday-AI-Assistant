"""Initiative Engine for FRIDAY — self-directed work on goals without being asked, governed against spam."""
from __future__ import annotations
import json, time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "initiative_state.json"
_SETTINGS_FILE = _BACKEND / "settings.json"

DEFAULTS = {
    "enabled": True,
    "interval_minutes": 20,          # how often the loop wakes
    "quiet_start": 23,               # local hour — no initiative from this hour...
    "quiet_end": 8,                  # ...until this hour
    "max_daily_actions": 6,          # hard daily budget
    "goal_nudge_hours": 4,           # min hours between initiative on the same goal
    "approval_reminder_hours": 2,    # remind about pending approvals at most this often
    "user_idle_minutes": 3,          # never interrupt a conversation
}
_KNOWN_KEYS = set(DEFAULTS)

def _load_state() -> dict:
    try:
        state = json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    today = time.strftime("%Y-%m-%d")
    if state.get("actions_date") != today:
        state["actions_date"] = today
        state["actions_count"] = 0
    state.setdefault("actions_date", today)
    state.setdefault("actions_count", 0)
    state.setdefault("goal_last_nudge", {})
    state.setdefault("last_approval_reminder", 0.0)
    return state

def _save_state(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")

def read_settings() -> dict:
    """Merged initiative config: defaults overridden by settings.json['initiative']."""
    cfg = dict(DEFAULTS)
    try:
        raw = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8")).get("initiative") or {}
        cfg.update({k: v for k, v in raw.items() if k in _KNOWN_KEYS})
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return cfg

def write_settings(updates: dict) -> dict:
    """Persist initiative config into settings.json['initiative'] (sanitised) and return it."""
    clean = {k: v for k, v in (updates or {}).items() if k in _KNOWN_KEYS}
    merged = {**read_settings(), **clean}
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8")) if _SETTINGS_FILE.exists() else {}
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data["initiative"] = merged
    try:
        _SETTINGS_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": "Could not write settings: %s" % exc}
    return {"ok": True, "config": merged}

def is_quiet_hour(cfg: dict, now_ts: float = None) -> bool:
    hour = time.localtime(now_ts or time.time()).tm_hour
    start, end = int(cfg.get("quiet_start", 23)), int(cfg.get("quiet_end", 8))
    if start == end:
        return False
    if start > end:                      # wraps midnight, e.g. 23 -> 8
        return hour >= start or hour < end
    return start <= hour < end
def evaluate(active_goals: list, pending_approvals: int, cfg: dict, user_idle_seconds: float,
             now_ts: float = None) -> dict:
    """Pure decision function: should Friday act on his own right now, and on what?

    Governance layers (in order): enabled -> quiet hours -> daily budget -> user-idle guard,
    then per-goal nudge intervals and approval-reminder interval.
    Returns {"act": bool, "reason": str, "initiatives": [{kind, goal_id?, prompt, notify_text}]}
    """
    now_ts = now_ts if now_ts is not None else time.time()
    if not cfg.get("enabled", True):
        return {"act": False, "reason": "disabled", "initiatives": []}
    if is_quiet_hour(cfg, now_ts):
        return {"act": False, "reason": "quiet_hours", "initiatives": []}
    state = _load_state()
    if state["actions_count"] >= int(cfg.get("max_daily_actions", 6)):
        return {"act": False, "reason": "daily_budget_exhausted", "initiatives": []}
    if user_idle_seconds < float(cfg.get("user_idle_minutes", 3)) * 60:
        return {"act": False, "reason": "user_active_recently", "initiatives": []}

    initiatives, nudge_secs = [], float(cfg.get("goal_nudge_hours", 4)) * 3600

    # 1) Pending approvals block Friday's work — highest priority reminder.
    if pending_approvals > 0:
        rem_secs = float(cfg.get("approval_reminder_hours", 2)) * 3600
        if now_ts - state.get("last_approval_reminder", 0.0) >= rem_secs:
            word = "action" if pending_approvals == 1 else "actions"
            initiatives.append({
                "kind": "approval_reminder", "goal_id": None,
                "prompt": ("System Notification (self-initiated, not user speech): %d %s are awaiting the user's "
                           "approval in the OpenClaw window. Politely get his attention: tell him how many %s await "
                           "his decision and that you cannot proceed with them until he approves. Do NOT approve "
                           "anything yourself." % (pending_approvals, word, word)),
                "notify_text": "%d %s awaiting approval" % (pending_approvals, word),
            })

    # 2) Goals: stale, never-started, or due — nudged at most once per goal_nudge_hours.
    candidates = []
    for g in active_goals or []:
        gid = g.get("id", "")
        if not gid or now_ts - state["goal_last_nudge"].get(gid, 0.0) < nudge_secs:
            continue
        never_started = (g.get("progress", 0) == 0 and not g.get("last_journal"))
        if g.get("needs_attention") or never_started or g.get("due"):
            candidates.append(g)
    candidates.sort(key=lambda g: (0 if g.get("needs_attention") else 1, g.get("progress", 0)))
    if candidates:
        g = candidates[0]
        nxt = g.get("next_milestone") or "the next milestone"
        due = " It is due %s." % g["due"] if g.get("due") else ""
        initiatives.append({
            "kind": "goal_work", "goal_id": g["id"],
            "prompt": ("System Notification (self-initiated, not user speech): You are now working autonomously on "
                       "your open goal '%s' (%.0f%% done, next milestone: %s).%s Act on it now with your real tools "
                       "(run_script, build_custom_tool, run_powershell_command, code_helper, whatever fits). Journal "
                       "the outcome with manage_goals action=journal for goal_id=%s. When done, give a brief spoken "
                       "summary addressed to 'Sir' — under three sentences."
                       % (g.get("title", "untitled"), g.get("progress", 0), nxt, due, g["id"])),
            "notify_text": "Working on goal: %s" % g.get("title", "untitled"),
        })

    if not initiatives:
        return {"act": False, "reason": "nothing_actionable", "initiatives": []}
    return {"act": True, "reason": "initiatives_ready", "initiatives": initiatives[:2]}

def record_action(kind: str, goal_id: str = None, now_ts: float = None) -> dict:
    """Book-keeping after an initiative fires: daily budget + nudge timestamps."""
    now_ts = now_ts if now_ts is not None else time.time()
    state = _load_state()
    state["actions_count"] += 1
    if kind == "approval_reminder":
        state["last_approval_reminder"] = now_ts
    if goal_id:
        state["goal_last_nudge"][goal_id] = now_ts
        if len(state["goal_last_nudge"]) > 200:
            keep = sorted(state["goal_last_nudge"].items(), key=lambda kv: -kv[1])[:100]
            state["goal_last_nudge"] = dict(keep)
    _save_state(state)
    return {"ok": True, "actions_today": state["actions_count"]}

def stats() -> dict:
    state = _load_state()
    return {"ok": True, "config": read_settings(), "actions_today": state["actions_count"],
            "daily_budget": int(read_settings().get("max_daily_actions", 6)),
            "goals_nudged": len(state["goal_last_nudge"]),
            "quiet_hours": "%02d:00-%02d:00" % (int(read_settings()["quiet_start"]), int(read_settings()["quiet_end"])),
            "in_quiet_hours_now": is_quiet_hour(read_settings())}

def initiative_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "status")
    if action == "status":
        return stats()
    if action == "enable":
        return write_settings({"enabled": True})
    if action == "disable":
        return write_settings({"enabled": False})
    if action == "configure":
        return write_settings(a.get("config", {}))
    if action == "evaluate":
        return evaluate(a.get("goals", []), int(a.get("pending_approvals", 0)), read_settings(),
                        float(a.get("user_idle_seconds", 9999)))
    return {"ok": False, "error": "Unknown initiative action"}