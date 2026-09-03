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
from datetime import datetime
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
_FAILURE_LOG = _BACKEND_DIR / "tool_failures.json"


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


def dependency_audit() -> dict:
    """Report outdated Python and Node dependencies without changing them."""
    python_result = _run_command([sys.executable, "-m", "pip", "list", "--outdated", "--format", "json"], _PROJECT_ROOT, timeout=180)
    npm = _resolve_npm()
    npm_result = _run_command([npm, "outdated", "--json"], _PROJECT_ROOT, timeout=180) if npm else {"ok": False, "stdout": "", "stderr": "npm was not found"}
    return {"python": python_result, "node": npm_result}


def capability_audit() -> dict:
    """Build a local registry of declared Friday tools and maintenance actions."""
    registry = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "maintenance_actions": ["run_tests", "compile_check", "build_frontend", "full_check", "self_build", "self_heal", "self_upgrade"],
        "backend_modules": sorted(path.stem for path in _BACKEND_DIR.rglob("*.py") if path.name != "__init__.py"),
    }
    try:
        sys.path.insert(0, str(_BACKEND_DIR))
        from tools import tools_list
        registry["tools"] = sorted(tool.get("name") for tool in tools_list[0].get("function_declarations", []) if tool.get("name"))
    except Exception as error:
        registry["tools_error"] = str(error)
    registry_path = _BACKEND_DIR / "capability_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return {"path": str(registry_path), "tool_count": len(registry.get("tools", [])), "module_count": len(registry["backend_modules"])}


def record_tool_failure(tool_name: str, error: str) -> None:
    """Persist small failure counters so future repair runs can prioritize issues."""
    try:
        data = json.loads(_FAILURE_LOG.read_text(encoding="utf-8")) if _FAILURE_LOG.exists() else {}
        entry = data.setdefault(tool_name, {"count": 0, "last_error": ""})
        entry["count"] += 1
        entry["last_error"] = str(error)[:500]
        _FAILURE_LOG.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def deprecation_audit() -> list[str]:
    """Find common deprecated API markers for Friday to review."""
    markers = ("deprecated", "DeprecationWarning", "use-angle", "google.genai", "pyaudio")
    findings = []
    for path in _PROJECT_ROOT.rglob("*.py"):
        if any(part in {".git", "node_modules", "__pycache__", "dist"} for part in path.parts):
            continue
        try:
            for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if any(marker in line for marker in markers):
                    findings.append(f"{path.relative_to(_PROJECT_ROOT)}:{line_number}: {line.strip()}")
        except OSError:
            continue
    return findings[:50]


def self_heal() -> str:
    """Recover dependency/build failures without modifying source code."""
    checks = [compile_check_backend(), run_backend_tests(), build_frontend()]
    if all(result.get("ok") for result in checks):
        return "Self-heal: all checks already pass. No repair was needed."

    backup_dir = _PROJECT_ROOT / ".friday-recovery" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("requirements.txt", "package.json", "package-lock.json"):
        source = _PROJECT_ROOT / filename
        if source.exists():
            shutil.copy2(source, backup_dir / filename)

    python_install = install_python_dependencies()
    frontend_install = install_frontend_dependencies()
    checks_after = [compile_check_backend(), run_backend_tests(), build_frontend()]
    status = "recovered" if all(result.get("ok") for result in checks_after) else "needs source-code repair"
    return "\n".join([
        f"Self-heal: {status}.",
        f"Recovery backup: {backup_dir}",
        f"Dependency repair: Python={'OK' if python_install.get('ok') else 'FAILED'}, Frontend={'OK' if frontend_install.get('ok') else 'FAILED'}",
        f"Final checks: compile={'OK' if checks_after[0].get('ok') else 'FAILED'}, tests={'OK' if checks_after[1].get('ok') else 'FAILED'}, build={'OK' if checks_after[2].get('ok') else 'FAILED'}",
    ])


def self_upgrade() -> str:
    """Refresh declared dependencies, then verify the project."""
    audit = dependency_audit()
    python_result = _run_command([sys.executable, "-m", "pip", "install", "--upgrade", "-r", str(_PROJECT_ROOT / "requirements.txt")], _PROJECT_ROOT, timeout=900)
    npm = _resolve_npm()
    frontend_result = _run_command([npm, "update"], _PROJECT_ROOT, timeout=900) if npm else {"ok": False}
    verification = compile_check_backend()
    registry = capability_audit()
    deprecations = deprecation_audit()
    return "\n".join([
        f"Outdated dependency audit captured: Python={'OK' if audit['python'].get('ok') else 'FAILED'}, Node={'OK' if audit['node'].get('ok') else 'FAILED'}",
        f"Self-upgrade dependencies: Python={'OK' if python_result.get('ok') else 'FAILED'}, Frontend={'OK' if frontend_result.get('ok') else 'FAILED'}",
        f"Post-upgrade backend compile: {'OK' if verification.get('ok') else 'FAILED'}",
        f"Capability registry: {registry['tool_count']} tools, {registry['module_count']} backend modules.",
        f"Deprecation findings: {len(deprecations)}.",
        "Source code and prompts were not changed automatically.",
    ])


def self_build() -> str:
    """Run the complete autonomous maintenance cycle and return a concise report."""
    compile_result = compile_check_backend()
    test_result = run_backend_tests()
    build_result = build_frontend()
    if compile_result.get("ok") and test_result.get("ok") and build_result.get("ok"):
        return "Self-build: healthy. Backend compile, tests, and frontend build all passed."

    recovery_report = self_heal()
    return "\n".join([
        "Self-build: initial verification failed.",
        f"Initial checks: compile={'OK' if compile_result.get('ok') else 'FAILED'}, tests={'OK' if test_result.get('ok') else 'FAILED'}, build={'OK' if build_result.get('ok') else 'FAILED'}",
        recovery_report,
    ])


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
    if action == "self_build":
        return self_build()
    if action == "self_heal":
        return self_heal()
    if action == "self_upgrade":
        return self_upgrade()

    return f"Unknown self_maintenance action: '{action}'"
