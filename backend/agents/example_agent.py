"""Reference format for a Friday-generated background agent."""

AGENT_MANIFEST = {
    "name": "example_agent",
    "description": "Example background agent that reports its received goal.",
    "parameters": {}
}


def run(goal, repo_path, log, cancel_event):
    log(f"Received goal: {goal}")
    if cancel_event.is_set():
        return {"cancelled": True}
    return {"ok": True, "goal": goal, "repo_path": repo_path}
