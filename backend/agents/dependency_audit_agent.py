AGENT_MANIFEST = {"name": "dependency_audit_agent", "version": "1.0.0", "enabled": True, "description": "Audits outdated dependencies, deprecated API usage, and capability regressions, and reports what a self-upgrade would change.", "parameters": {}}


def run(goal, repo_path, log, cancel_event, context=None):
    import json
    from actions import self_maintenance

    log("Auditing outdated dependencies")
    if cancel_event.is_set():
        return {"ok": False, "agent": "dependency_audit_agent", "status": "cancelled"}

    audit = self_maintenance.dependency_audit()
    deprecations = self_maintenance.deprecation_audit()

    # Use the same path self_maintenance.capability_audit() always writes to, regardless of repo_path.
    registry_path = self_maintenance._BACKEND_DIR / "capability_registry.json"
    previous_tools: set[str] = set()
    if registry_path.exists():
        try:
            previous_tools = set(json.loads(registry_path.read_text(encoding="utf-8")).get("tools", []))
        except (OSError, ValueError):
            pass

    capability = self_maintenance.capability_audit()
    current_registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
    current_tools = set(current_registry.get("tools", []))
    lost_tools = sorted(previous_tools - current_tools) if previous_tools else []

    def _count(result: dict, is_object: bool) -> int:
        try:
            data = json.loads(result.get("stdout") or "")
        except (ValueError, TypeError):
            return 0
        if is_object:
            return len(data) if isinstance(data, dict) else 0
        return len(data) if isinstance(data, list) else 0

    outdated_python = _count(audit["python"], is_object=False)
    outdated_node = _count(audit["node"], is_object=True)
    deprecation_count = len(deprecations)

    summary_parts = [
        f"{outdated_python} outdated Python package(s), {outdated_node} outdated Node package(s), "
        f"{deprecation_count} deprecation finding(s)."
    ]
    if lost_tools:
        summary_parts.append(f"{len(lost_tools)} tool(s) disappeared since the last audit: {', '.join(lost_tools[:5])}.")
    summary_parts.append("Say 'self-upgrade' to review and apply.")
    summary = " ".join(summary_parts)
    log(summary)
    return {
        "ok": True, "agent": "dependency_audit_agent",
        "outdated_python_count": outdated_python, "outdated_node_count": outdated_node,
        "deprecation_count": deprecation_count, "lost_tools": lost_tools,
        "tool_count": capability.get("tool_count", 0), "module_count": capability.get("module_count", 0),
        "summary": summary,
        "needs_attention": (outdated_python + outdated_node + deprecation_count + len(lost_tools)) > 0,
    }
