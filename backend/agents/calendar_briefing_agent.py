AGENT_MANIFEST = {"name": "calendar_briefing_agent", "version": "1.0.0", "enabled": True, "description": "Prepares calendar-focused briefings and meeting follow-ups.", "parameters": {}}

def run(goal, repo_path, log, cancel_event, context=None):
    log("Reading upcoming calendar events")
    if cancel_event.is_set():
        return {"ok": False, "agent": "calendar_briefing_agent", "status": "cancelled"}
    account = getattr(context, "google_account", None)
    if not account:
        return {"ok": True, "agent": "calendar_briefing_agent", "status": "awaiting_google_connection", "goal": goal}
    events = account.list_calendar_events(days=2, limit=25)
    log(f"Found {len(events)} upcoming events")
    return {"ok": True, "agent": "calendar_briefing_agent", "events": events, "next_event": events[0] if events else None}