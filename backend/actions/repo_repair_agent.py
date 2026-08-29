from actions import git_workflow as git_workflow_module
from actions import self_maintenance as self_maintenance_module


def run(goal: str, repo_path: str, log, cancel_event) -> dict:
    """Inspect a repo, run targeted checks, and report actionable issues.

    This agent never invents code changes: it inspects state, runs tests,
    and produces a concrete report the user (or a follow-up agent) can act on.
    """
    log(f"Starting repo repair agent for goal: {goal}")

    status_report = git_workflow_module.git_status(repo_path)
    log("Collected git status")

    if cancel_event.is_set():
        return {"goal": goal, "cancelled": True}

    compile_report = self_maintenance_module.compile_check_backend()
    log(f"Compile check: {'OK' if compile_report.get('ok') else 'FAILED'}")

    if cancel_event.is_set():
        return {"goal": goal, "cancelled": True}

    test_report = self_maintenance_module.run_backend_tests()
    log(f"Test run: {'OK' if test_report.get('ok') else 'FAILED'}")

    if cancel_event.is_set():
        return {"goal": goal, "cancelled": True}

    verification_report = self_maintenance_module.run_backend_tests()
    log(f"Verification run: {'OK' if verification_report.get('ok') else 'FAILED'}")

    issues = list(dict.fromkeys(
        (compile_report.get("issues") or []) + (test_report.get("issues") or [])
    ))

    all_ok = compile_report.get("ok") and test_report.get("ok") and verification_report.get("ok")
    summary_lines = [
        f"Goal: {goal}",
        f"Compile check: {'OK' if compile_report.get('ok') else 'FAILED'}",
        f"Test run: {'OK' if test_report.get('ok') else 'FAILED'}",
        f"Verification run (re-run): {'OK' if verification_report.get('ok') else 'FAILED'}",
    ]
    if issues:
        summary_lines.append("Issues found:")
        summary_lines.extend(f"  - {issue}" for issue in issues[:20])
    else:
        summary_lines.append("No issues found.")

    return {
        "goal": goal,
        "ok": bool(all_ok),
        "status_report": status_report,
        "compile_report": compile_report,
        "test_report": test_report,
        "verification_report": verification_report,
        "issues": issues,
        "summary": "\n".join(summary_lines),
    }
