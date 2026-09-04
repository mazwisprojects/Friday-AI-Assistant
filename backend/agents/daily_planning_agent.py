AGENT_MANIFEST = {"name": "daily_planning_agent", "version": "1.0.0", "enabled": True, "description": "Builds a daily plan from tasks, calendar events, and priorities.", "parameters": {}}

def run(goal, repo_path, log, cancel_event, context=None):
    log("Combining open tasks and calendar commitments")
    if cancel_event.is_set():
        return {"ok": False, "agent": "daily_planning_agent", "status": "cancelled"}
    tasks = getattr(context, "task_manager", None)
    account = getattr(context, "google_account", None)
    open_tasks = tasks.list("open") if tasks else []
    events = account.list_calendar_events(days=7, limit=50) if account else []
    ranked = sorted(open_tasks, key=lambda item: {"urgent": 0, "high": 1, "normal": 2, "low": 3}.get(item.get("priority"), 2))
    log(f"Prepared plan from {len(ranked)} tasks and {len(events)} events")
    return {"ok": True, "agent": "daily_planning_agent", "tasks": ranked, "calendar": events, "overdue": tasks.overdue() if tasks else [], "goal": goal}