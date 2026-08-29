import subprocess

from actions import powershell_command as pc


def test_run_powershell_command_executes_command(monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None, shell=None):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="hello", stderr="warning")

    monkeypatch.setattr(pc.subprocess, "run", fake_run)

    result = pc.run_powershell_command({
        "command": "Write-Output 'hello'",
        "cwd": "C:/Temp",
        "timeout": 25,
    })

    assert "Exit code: 0" in result
    assert "hello" in result
    assert calls
    assert calls[0][1:4] == ["-NoProfile", "-NonInteractive", "-Command"]
    assert "Write-Output 'hello'" in calls[0][-1]
