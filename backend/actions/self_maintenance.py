"""Self-maintenance actions: run backend tests, compile-check the backend, build the
frontend, and install missing dependencies. Surfaces errors/warnings for the user
to review rather than silently auto-fixing code.
"""
import compileall
import io
import json
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path


def _missing_python_packages(packages: list[str]) -> list[str]:
    missing = []
    for package in packages:
        try:
            __import__(package)
        except Exception:
            missing.append(package)
    return missing

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_MAX_OUTPUT_CHARS = 6000


def _truncate(text: str, limit: int = _MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated, {len(text) - limit} more characters]"


def _run_command(cmd: list[str], cwd: Path, timeout: int = 300) -> dict:
    try:
        result = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": _truncate(result.stdout or ""),
            "stderr": _truncate(result.stderr or ""),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": f"Command timed out after {timeout}s: {' '.join(cmd)}"}
    except FileNotFoundError as error:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": f"Command not found: {error}"}
    except Exception as error:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": f"Failed to run command: {error}"}


def _extract_issues(text: str) -> list[str]:
    """Pull out lines that look like errors/warnings/failures for a quick summary."""
    issues = []
    markers = ("error", "failed", "failure", "warning", "traceback", "exception")
    for line in text.splitlines():
        lowered = line.strip().lower()
        if any(marker in lowered for marker in markers) and line.strip():
            issues.append(line.strip())
    return issues[:40]


def _needs_frontend_install() -> bool:
    return not (_PROJECT_ROOT / "node_modules").exists()


def run_backend_tests(args: str = "", target: str | None = None) -> dict:
    """Runs the Python test suite with the current interpreter.

    Accepts either a pytest-style argument string or a single target path/file.
    """
    missing = _missing_python_packages(["pytest"])
    if missing:
        install_result = install_python_dependencies()
        if not install_result["ok"]:
            return {
                "ok": False,
                "returncode": install_result["returncode"],
                "stdout": install_result.get("stdout", ""),
                "stderr": install_result.get("stderr", ""),
                "issues": install_result.get("issues", ["Missing Python dependencies prevented pytest execution"]),
            }

    cmd = [sys.executable, "-m", "pytest", "-q"]
    if target:
        cmd.append(target)
    elif args:
        cmd.extend(args.split())
    result = _run_command(cmd, cwd=_PROJECT_ROOT, timeout=600)
    result["issues"] = _extract_issues(result["stdout"] + "\n" + result["stderr"])
    return result


def compile_check_backend() -> dict:
    """Byte-compiles every backend .py file to catch syntax errors without running them."""
    buffer = io.StringIO()
    ok = True
    try:
        with redirect_stdout(buffer):
            ok = compileall.compile_dir(
                str(_BACKEND_DIR), quiet=1, force=True, workers=0
            )
    except Exception as error:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": str(error), "issues": [str(error)]}

    output = buffer.getvalue()
    return {
        "ok": bool(ok),
        "returncode": 0 if ok else 1,
        "stdout": _truncate(output),
        "stderr": "",
        "issues": _extract_issues(output),
    }


def _resolve_npm() -> str | None:
    npm = shutil.which("npm")
    if npm:
        return npm
    windows_default = Path("C:/Program Files/nodejs/npm.cmd")
    if windows_default.exists():
        return str(windows_default)
    return None


def build_frontend() -> dict:
    """Runs the production Vite build for the React frontend."""
    npm = _resolve_npm()
    if not npm:
        return {
            "ok": False, "returncode": -1, "stdout": "", "issues": ["npm was not found on PATH"],
            "stderr": "npm was not found. Install Node.js or set FRIDAY_NPM_PATH.",
        }
    if _needs_frontend_install():
        install_result = install_frontend_dependencies()
        if not install_result["ok"]:
            return {
                "ok": False,
                "returncode": install_result["returncode"],
                "stdout": install_result.get("stdout", ""),
                "stderr": install_result.get("stderr", ""),
                "issues": install_result.get("issues", ["Frontend dependencies were missing and could not be installed"]),
            }
    result = _run_command([npm, "run", "build"], cwd=_PROJECT_ROOT, timeout=600)
    result["issues"] = _extract_issues(result["stdout"] + "\n" + result["stderr"])
    return result


def install_python_dependencies() -> dict:
    """Installs/updates Python packages from requirements.txt into the current interpreter."""
    requirements = _PROJECT_ROOT / "requirements.txt"
    if not requirements.exists():
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": "requirements.txt not found.", "issues": ["requirements.txt not found"]}
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements)]
    result = _run_command(cmd, cwd=_PROJECT_ROOT, timeout=900)
    result["issues"] = _extract_issues(result["stdout"] + "\n" + result["stderr"])
    return result


def install_frontend_dependencies() -> dict:
    """Runs npm install for the frontend."""
    npm = _resolve_npm()
    if not npm:
        return {
            "ok": False, "returncode": -1, "stdout": "", "issues": ["npm was not found on PATH"],
            "stderr": "npm was not found. Install Node.js or set FRIDAY_NPM_PATH.",
        }
    result = _run_command([npm, "install"], cwd=_PROJECT_ROOT, timeout=900)
    result["issues"] = _extract_issues(result["stdout"] + "\n" + result["stderr"])
    return result


def _summarize(name: str, result: dict) -> str:
    status = "OK" if result.get("ok") else "FAILED"
    lines = [f"{name}: {status}"]
    issues = result.get("issues") or []
    if issues:
        lines.append("Issues found:")
        lines.extend(f"  - {issue}" for issue in issues[:15])
    elif not result.get("ok"):
        stderr = (result.get("stderr") or "").strip()
        if stderr:
            lines.append(stderr[:1500])
    return "\n".join(lines)


def self_maintenance(parameters: dict) -> str:
    """Dispatcher: action in {run_tests, compile_check, build_frontend,
    install_python_deps, install_frontend_deps, full_check}."""
    action = (parameters or {}).get("action", "full_check").lower().strip()
    args = parameters.get("args", "") if parameters else ""
    target = parameters.get("target") if parameters else None

    if action == "run_tests":
        return _summarize("Backend tests", run_backend_tests(args, target=target))
    if action == "compile_check":
        return _summarize("Backend compile check", compile_check_backend())
    if action == "build_frontend":
        return _summarize("Frontend build", build_frontend())
    if action == "install_python_deps":
        return _summarize("Python dependency install", install_python_dependencies())
    if action == "install_frontend_deps":
        return _summarize("Frontend dependency install", install_frontend_dependencies())
    if action == "full_check":
        if _missing_python_packages(["pytest"]):
            install_python_dependencies()
        if _needs_frontend_install():
            install_frontend_dependencies()
        parts = [
            _summarize("Backend compile check", compile_check_backend()),
            _summarize("Backend tests", run_backend_tests()),
            _summarize("Frontend build", build_frontend()),
        ]
        return "\n\n".join(parts)

    return f"Unknown self_maintenance action: '{action}'"
