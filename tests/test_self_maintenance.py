import subprocess
import sys

from actions import self_maintenance as sm


def test_python_install_path_runs_requirements(monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(sm.subprocess, "run", fake_run)
    monkeypatch.setattr(sm, "_missing_python_packages", lambda: ["pytest"])

    result = sm.install_python_dependencies()

    assert result["ok"] is True
    assert any(cmd[:4] == [sys.executable, "-m", "pip", "install"] for cmd in calls)


def test_frontend_install_path_runs_npm_install(monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(sm.subprocess, "run", fake_run)
    monkeypatch.setattr(sm, "_resolve_npm", lambda: "npm")
    monkeypatch.setattr(sm, "_needs_frontend_install", lambda: True)

    result = sm.install_frontend_dependencies()

    assert result["ok"] is True
    assert any(cmd[:2] == ["npm", "install"] for cmd in calls)


def test_run_tests_accepts_single_target(monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="1 passed", stderr="")

    monkeypatch.setattr(sm.subprocess, "run", fake_run)
    monkeypatch.setattr(sm, "_missing_python_packages", lambda packages: [])

    result = sm.self_maintenance({"action": "run_tests", "target": "tests/test_authenticator.py"})

    assert "Backend tests: OK" in result
    assert any(
        cmd[:5] == [sys.executable, "-m", "pytest", "-q", "tests/test_authenticator.py"]
        for cmd in calls
    )
