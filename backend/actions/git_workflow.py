import subprocess
from pathlib import Path


def _run_git(repo_path: str, *args: str, timeout: int = 120) -> dict:
    repo = str(Path(repo_path).expanduser()) if repo_path else "."
    cmd = ["git", *args]
    result = subprocess.run(
        cmd,
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
        "command": cmd,
    }


def git_status(repo_path: str) -> str:
    result = _run_git(repo_path, "status", "--short", "--branch")
    if not result["ok"]:
        return f"Git status failed: {result['stderr'] or result['stdout'] or 'unknown error'}"
    stdout = result["stdout"]
    return stdout or "Working tree clean."


def create_branch(repo_path: str, branch_name: str) -> str:
    if not branch_name:
        return "No branch name provided."
    result = _run_git(repo_path, "checkout", "-b", branch_name)
    if not result["ok"]:
        return f"Failed to create branch '{branch_name}': {result['stderr'] or result['stdout'] or 'unknown error'}"
    return result["stdout"] or f"Created and switched to branch '{branch_name}'."


def checkout_branch(repo_path: str, branch_name: str) -> str:
    if not branch_name:
        return "No branch name provided."
    result = _run_git(repo_path, "checkout", branch_name)
    if not result["ok"]:
        return f"Failed to switch to branch '{branch_name}': {result['stderr'] or result['stdout'] or 'unknown error'}"
    return result["stdout"] or f"Switched to branch '{branch_name}'."


def diff(repo_path: str) -> str:
    result = _run_git(repo_path, "diff", "--", ".")
    if not result["ok"]:
        return f"Diff failed: {result['stderr'] or result['stdout'] or 'unknown error'}"
    return result["stdout"] or "No local diff found."


def review_diff(repo_path: str, max_chars: int = 4000) -> str:
    changes = diff(repo_path)
    if len(changes) > max_chars:
        changes = changes[:max_chars] + "\n... [truncated]"
    return changes


def commit_changes(repo_path: str, message: str) -> str:
    if not message:
        return "No commit message provided."
    add_result = _run_git(repo_path, "add", "-A")
    if not add_result["ok"]:
        return f"Git add failed: {add_result['stderr'] or add_result['stdout'] or 'unknown error'}"

    commit_result = _run_git(repo_path, "commit", "-m", message)
    if not commit_result["ok"]:
        details = commit_result["stderr"] or commit_result["stdout"] or "nothing to commit"
        if "nothing to commit" in details.lower():
            return "No changes to commit."
        return f"Git commit failed: {details}"

    return commit_result["stdout"] or f"Committed: {message}"


def publish_changes(repo_path: str, message: str) -> str:
    """Commit all current changes and push the current branch safely."""
    if not message.strip():
        return "No commit message provided."
    repo = str(Path(repo_path).expanduser()) if repo_path else "."
    status = _run_git(repo, "status", "--porcelain")
    if not status["ok"]:
        return f"Git status failed: {status['stderr'] or status['stdout']}"
    if not status["stdout"].strip():
        return "Working tree is clean; nothing to publish."
    diff_check = _run_git(repo, "diff", "--check")
    if not diff_check["ok"]:
        return f"Publish stopped because diff validation failed: {diff_check['stderr'] or diff_check['stdout']}"
    committed = commit_changes(repo, message)
    if committed.startswith("Git commit failed") or committed.startswith("No changes"):
        return committed
    pushed = _run_git(repo, "push", timeout=180)
    if not pushed["ok"]:
        return f"Committed locally but push failed: {pushed['stderr'] or pushed['stdout']}"
    return f"{committed}\nPush completed successfully."


def detect_obvious_regressions(repo_path: str) -> str:
    repo = Path(repo_path).expanduser() if repo_path else Path.cwd()
    status = git_status(str(repo))
    if "working tree clean" not in status.lower() and "##" not in status.lower():
        # Lightweight regression checks: ensure all local diffs are not obviously malformed.
        diff_check = _run_git(str(repo), "diff", "--check")
        if not diff_check["ok"]:
            return "Potential regression detected: git diff --check reported whitespace or merge issues.\n" + (diff_check["stderr"] or diff_check["stdout"])

    pytest_path = repo / "pytest.ini"
    if pytest_path.exists():
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "-q"],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            if result.returncode != 0:
                summary = stdout or stderr or "pytest reported failures"
                return f"Potential regression detected: pytest exited with code {result.returncode}.\n{summary[:3000]}"
            return "No obvious regression detected by pytest."
        except Exception as exc:
            return f"Regression check could not run: {exc}"

    return "No obvious regression detected by local Git checks."


def git_workflow(parameters: dict) -> str:
    if not isinstance(parameters, dict):
        return "No parameters provided for git workflow."

    action = str(parameters.get("action", "status")).strip().lower()
    repo_path = parameters.get("repo_path") or parameters.get("path") or "."

    if action == "status":
        return git_status(str(repo_path))
    if action == "create_branch":
        return create_branch(str(repo_path), str(parameters.get("branch_name") or ""))
    if action == "checkout_branch":
        return checkout_branch(str(repo_path), str(parameters.get("branch_name") or ""))
    if action == "diff":
        return diff(str(repo_path))
    if action == "review_diff":
        max_chars = parameters.get("max_chars", 4000)
        try:
            max_chars = int(max_chars)
        except (TypeError, ValueError):
            max_chars = 4000
        return review_diff(str(repo_path), max_chars=max_chars)
    if action == "commit":
        return commit_changes(str(repo_path), str(parameters.get("message") or ""))
    if action in {"push", "publish", "self_publish"}:
        return publish_changes(str(repo_path), str(parameters.get("message") or ""))
    if action == "regression_check":
        return detect_obvious_regressions(str(repo_path))

    return f"Unknown git workflow action: '{action}'"
