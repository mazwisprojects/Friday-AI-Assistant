AGENT_MANIFEST = {"name": "code_review_agent", "version": "1.0.0", "enabled": True, "description": "Reviews code goals for correctness, regressions, and test gaps.", "parameters": {}}

def run(goal, repo_path, log, cancel_event):
    log("Reviewing code goal")
    return {"ok": not cancel_event.is_set(), "agent": "code_review_agent", "goal": goal, "repo_path": repo_path, "next_step": "Inspect the diff and run focused tests."}