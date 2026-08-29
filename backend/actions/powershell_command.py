import os
import shutil
import subprocess
from pathlib import Path


def _resolve_powershell() -> str:
    if os.name == "nt":
        return shutil.which("powershell.exe") or shutil.which("powershell") or "powershell"
    if shutil.which("pwsh"):
        return "pwsh"
    if shutil.which("powershell"):
        return "powershell"
    return "powershell"


def run_powershell_command(parameters: dict) -> str:
    """Runs an arbitrary PowerShell command and returns the captured stdout/stderr."""
    if not isinstance(parameters, dict):
        return "No parameters provided for the PowerShell command."

    command = str(parameters.get("command", "")).strip()
    if not command:
        return "No PowerShell command provided."

    timeout = parameters.get("timeout", 120)
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        timeout = 120
    if timeout <= 0:
        timeout = 120

    cwd = parameters.get("cwd")
    run_cwd = str(Path(cwd).expanduser()) if cwd else None

    shell_exe = _resolve_powershell()
    result = subprocess.run(
        [shell_exe, "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=run_cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    lines = [f"Exit code: {result.returncode}"]

    if stdout:
        lines.append(stdout)
    if stderr:
        lines.append(f"stderr:\n{stderr}")
    if result.returncode != 0 and not stdout and not stderr:
        lines.append("PowerShell command failed without output.")

    return "\n".join(lines)
