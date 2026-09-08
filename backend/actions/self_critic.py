"""Self-Critic Loop for FRIDAY — execute-check-reflect harness with iteration memory (Reflexion pattern)."""
from __future__ import annotations
import hashlib, json, re, subprocess, time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "critic_history.json"

_ADVICE = [
    (r"ModuleNotFoundError: No module named '([\w.]+)'", "Install it (pip install {0}) or rewrite without it."),
    (r"ImportError: cannot import name '(\w+)'", "'{0}' does not exist in that module — check the spelling/API."),
    (r"IndentationError|TabError", "Fix inconsistent indentation (use 4 spaces throughout)."),
    (r"SyntaxError", "Fix the syntax at the reported line; re-read the code before retrying."),
    (r"NameError: name '(\w+)'", "Define or import '{0}' before use."),
    (r"KeyError: (.+)$", "Guard the missing key with .get() and a default value."),
    (r"TypeError: (.+)$", "Wrong argument type/count — check the function signature at the traceback frame."),
    (r"FileNotFoundError", "The path doesn't exist — use an absolute path or create it first."),
    (r"PermissionError", "File locked (antivirus/another process) — retry once, then write to a temp path."),
    (r"TimeoutExpired|timed out", "Workload too heavy or an infinite loop — reduce scope or raise timeout."),
]

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"runs": {}}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")

def _analyse(stderr: str, rc: int) -> dict:
    text = (stderr or "").strip() or ("process exited with code %d" % rc)
    lines = text.splitlines()
    for pattern, advice in _ADVICE:
        flags = 0 if pattern == r"Traceback" else re.IGNORECASE
        m = re.search(pattern, text, flags)
        if m:
            hint = advice
            if m.groups():
                try:
                    hint = advice.format(*m.groups())
                except Exception:
                    pass
            return {"error_tail": lines[-3:], "matched": pattern, "advice": hint}
    return {"error_tail": lines[-3:], "matched": None, "advice": "Unknown failure — re-read the traceback bottom-up."}

def run_check(name: str, code: str, language: str = "python", expects: list = None, timeout: int = 25) -> dict:
    """Execute code, assert expected outputs, analyse failures, and remember the attempt."""
    state = _load()
    hist = state["runs"].setdefault(name, [])
    sha = hashlib.sha1((code or "").encode()).hexdigest()[:12]
    prev_fail = next((h for h in reversed(hist) if h.get("code_sha1") == sha and not h.get("ok")), None)
    no_progress = prev_fail is not None
    iteration = len(hist) + 1

    checks, ok, error_analysis, stdout, stderr = [], True, None, "", ""
    if language in ("python", "py"):
        try:
            compile(code, "<critic>", "exec")
            checks.append({"check": "syntax", "passed": True})
        except SyntaxError as exc:
            checks.append({"check": "syntax", "passed": False, "detail": str(exc)})
            ok = False
            error_analysis = _analyse("SyntaxError: %s" % exc, 1)
    if ok:
        try:
            if language in ("python", "py"):
                args = ["python", "-c", code]
            elif language in ("node", "javascript", "js"):
                args = ["node", "-e", code]
            elif language in ("powershell", "ps1"):
                args = ["powershell", "-NoProfile", "-Command", code]
            else:
                return {"ok": False, "error": "Unsupported language: %s" % language}
            proc = subprocess.run(args, capture_output=True, text=True, timeout=int(timeout), cwd=str(_BACKEND))
            stdout, stderr = proc.stdout or "", proc.stderr or ""
            checks.append({"check": "execution", "passed": proc.returncode == 0, "rc": proc.returncode})
            if proc.returncode != 0:
                ok = False
                error_analysis = _analyse(stderr, proc.returncode)
        except subprocess.TimeoutExpired:
            ok = False
            error_analysis = _analyse("TimeoutExpired", 124)
            checks.append({"check": "execution", "passed": False, "detail": "timed out after %ss" % timeout})
    if ok and expects:
        for exp in expects:
            hit = str(exp).lower() in stdout.lower()
            checks.append({"check": "expect", "value": exp, "passed": hit})
            if not hit:
                ok = False
        if not ok:
            error_analysis = {"error_tail": stdout.strip().splitlines()[-3:], "matched": None,
                              "advice": "Code ran but output did not contain the expected values — print them or fix the logic."}
    entry = {"t": time.time(), "iteration": iteration, "code_sha1": sha, "ok": ok,
             "error": (error_analysis or {}).get("matched"), "advice": (error_analysis or {}).get("advice")}
    hist.append(entry)
    state["runs"][name] = hist[-20:]
    _save(state)
    result = {"ok": True, "passed": ok, "task": name, "iteration": iteration,
              "checks": checks, "stdout_tail": stdout.strip().splitlines()[-5:]}
    if error_analysis:
        result["error_analysis"] = error_analysis
    if no_progress:
        result["no_progress"] = True
        result["warning"] = "Identical failing code was submitted before — change the approach, not just the formatting."
        result["previous_attempt"] = prev_fail
    return result
def record(name: str, note: str, status: str = "info") -> dict:
    """Log a reflection note for a task (what was tried, what was learned)."""
    state = _load()
    state["runs"].setdefault(name, []).append({"t": time.time(), "note": (note or "")[:400], "status": status})
    state["runs"][name] = state["runs"][name][-20:]
    _save(state)
    return {"ok": True, "task": name, "iterations": len(state["runs"][name])}

def history(name: str) -> dict:
    state = _load()
    runs = state["runs"].get(name, [])
    return {"ok": True, "task": name, "attempts": runs[-10:], "total": len(runs)}

def reset(name: str) -> dict:
    state = _load()
    state["runs"].pop(name, None)
    _save(state)
    return {"ok": True, "task": name}

def critic_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "")
    if action == "run_check":
        return run_check(a.get("name", "task"), a.get("code", ""), a.get("language", "python"),
                         a.get("expects", []), int(a.get("timeout", 25)))
    if action == "record":
        return record(a.get("name", "task"), a.get("note", ""), a.get("status", "info"))
    if action == "history":
        return history(a.get("name", "task"))
    if action == "reset":
        return reset(a.get("name", "task"))
    return {"ok": False, "error": "Unknown critic action"}