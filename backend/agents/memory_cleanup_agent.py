AGENT_MANIFEST = {"name": "memory_cleanup_agent", "version": "1.0.0", "enabled": True, "description": "Coordinates memory cleanup, compaction, and retention review goals.", "parameters": {}}

def run(goal, repo_path, log, cancel_event):
    log("Reviewing memory cleanup goal")
    return {"ok": not cancel_event.is_set(), "agent": "memory_cleanup_agent", "goal": goal, "next_step": "Use compact_memory and memory summary tools."}