AGENT_MANIFEST = {"name": "tool_builder_agent", "version": "1.0.0", "enabled": True, "description": "Designs and verifies new Friday tool plugins.", "parameters": {}}

def run(goal, repo_path, log, cancel_event):
    log("Planning custom tool")
    return {"ok": not cancel_event.is_set(), "agent": "tool_builder_agent", "goal": goal, "next_step": "Use build_custom_tool followed by test_custom_tool."}