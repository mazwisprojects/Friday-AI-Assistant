import subprocess

from actions import git_workflow as gw


def test_git_status_returns_branch_and_changes(monkeypatch):
    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None, check=None):
        return subprocess.CompletedProcess(cmd, 0, stdout="## main\n M backend/example.py\n", stderr="")

    monkeypatch.setattr(gw.subprocess, "run", fake_run)

    result = gw.git_status(repo_path="C:/repo")

    assert "## main" in result
    assert "backend/example.py" in result


def test_create_branch_uses_checkout_b(monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None, check=None):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="Switched to a new branch 'feature/test'", stderr="")

    monkeypatch.setattr(gw.subprocess, "run", fake_run)

    result = gw.create_branch(repo_path="C:/repo", branch_name="feature/test")

    assert "feature/test" in result
    assert calls and calls[0][:3] == ["git", "checkout", "-b"]


def test_git_workflow_dispatch_handles_diff(monkeypatch):
    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None, check=None):
        return subprocess.CompletedProcess(cmd, 0, stdout="diff --git a/x b/x\n+hello\n", stderr="")

    monkeypatch.setattr(gw.subprocess, "run", fake_run)

    result = gw.git_workflow({"action": "diff", "repo_path": "C:/repo"})

    assert "diff --git" in result
    assert "+hello" in result
