AGENT_MANIFEST = {"name": "flight_watch_agent", "version": "1.0.0", "enabled": True, "description": "Monitors flight-search goals and reports price-check follow-ups.", "parameters": {}}

def run(goal, repo_path, log, cancel_event):
    log("Reviewing flight watch goal")
    return {"ok": not cancel_event.is_set(), "agent": "flight_watch_agent", "goal": goal, "next_step": "Use find_flights and schedule future checks when route details are available."}