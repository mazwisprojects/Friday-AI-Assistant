AGENT_MANIFEST = {"name": "news_agent", "version": "1.0.0", "enabled": True, "description": "Coordinates news-reporting goals through Friday's news and web tools.", "parameters": {}}

def run(goal, repo_path, log, cancel_event):
    log("Preparing news report")
    return {"ok": not cancel_event.is_set(), "agent": "news_agent", "goal": goal, "next_step": "Use the registered news_reporter plugin or web_search in news mode."}