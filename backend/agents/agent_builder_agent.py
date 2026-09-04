AGENT_MANIFEST = {"name": "agent_builder_agent", "version": "1.0.0", "enabled": True, "description": "Designs and verifies new Friday background-agent plugins.", "parameters": {}}

def run(goal, repo_path, log, cancel_event):
    log("Planning background agent")
    return {"ok": not cancel_event.is_set(), "agent": "agent_builder_agent", "goal": goal, "next_step": "Use build_agent, test_agent, then deploy_agent."}