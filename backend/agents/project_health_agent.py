AGENT_MANIFEST = {"name": "project_health_agent", "version": "1.0.0", "enabled": True, "description": "Checks project health through compilation, tests, and build validation.", "parameters": {}}

def run(goal, repo_path, log, cancel_event, context=None):
    import subprocess
    from pathlib import Path
    log("Running project health checks")
    if cancel_event.is_set():
        return {"ok": False, "agent": "project_health_agent", "status": "cancelled"}
    root = Path(repo_path).resolve()
    checks = []
    commands = [("python_compile", ["python", "-m", "compileall", "-q", "backend"]), ("frontend_build", ["npm.cmd", "run", "build"])]
    for name, command in commands:
        if cancel_event.is_set():
            return {"ok": False, "agent": "project_health_agent", "status": "cancelled", "checks": checks}
        try:
            result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=120)
            checks.append({"name": name, "ok": result.returncode == 0, "output": (result.stdout or result.stderr)[-2000:]})
        except (OSError, subprocess.TimeoutExpired) as error:
            checks.append({"name": name, "ok": False, "output": str(error)})
    return {"ok": all(check["ok"] for check in checks), "agent": "project_health_agent", "repo_path": str(root), "checks": checks}