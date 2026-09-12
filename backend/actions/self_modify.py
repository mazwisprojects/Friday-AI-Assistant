"""Self-Modification Layer for FRIDAY — edit tools, agents, configs, memories on the fly."""
from __future__ import annotations
import json
import difflib
import logging
import re
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_BACKEND = Path(__file__).resolve().parent.parent
_ACTIONS = _BACKEND / "actions"
_AGENTS = _BACKEND / "agents"
_MYTOOLS = _BACKEND / "mytools"
_MEMORY = _BACKEND / "long_term_memory"
_PROJECT_ROOT = _BACKEND.parent
_REPAIR_AUDIT = _MEMORY / "repair_audit.jsonl"


def _audit_repair(entry: dict) -> None:
    _MEMORY.mkdir(parents=True, exist_ok=True)
    with _REPAIR_AUDIT.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def _find_module(name: str) -> Path | None:
    """Locate a module by name across actions, agents, mytools, backend root."""
    candidates = [
        _ACTIONS / f"{name}.py",
        _AGENTS / f"{name}.py",
        _MYTOOLS / f"{name}.py",
        _BACKEND / f"{name}.py",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _find_json(name: str) -> Path | None:
    """Locate a JSON config file by name."""
    candidates = [
        _BACKEND / f"{name}.json",
        _MEMORY / f"{name}.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def edit_source(name: str, old_text: str, new_text: str) -> dict:
    """Replace text in any module's source code."""
    path = _find_module(name)
    if not path:
        return {"ok": False, "error": f"Module '{name}' not found"}
    code = path.read_text(encoding="utf-8")
    if old_text not in code:
        return {"ok": False, "error": f"Text not found in {name}"}
    new_code = code.replace(old_text, new_text, 1)
    try:
        compile(new_code, str(path), "exec")
    except SyntaxError as e:
        return {"ok": False, "error": f"Syntax error in replacement: {e}"}
    snapshot = None
    try:
        from actions import time_guard
        snapshot = time_guard.guard(str(path), "edit_source")
    except Exception:
        pass
    path.write_text(new_code, encoding="utf-8")
    return {"ok": True, "name": name, "message": f"Edited {name}", "snapshot": snapshot}


def repair_source(name: str, old_text: str, new_text: str, test_target: str = "") -> dict:
    """Apply an approved source repair, verify it, and roll it back on failure."""
    path = _find_module(name)
    repair_id = f"repair-{int(time.time() * 1000000)}"
    if not path:
        return {"ok": False, "repair_id": repair_id, "error": f"Module '{name}' not found"}
    if not old_text or old_text not in path.read_text(encoding="utf-8"):
        return {"ok": False, "repair_id": repair_id, "error": f"Text not found in {name}"}
    if test_target and (Path(test_target).is_absolute() or not test_target.replace("\\", "/").startswith("tests/")):
        return {"ok": False, "repair_id": repair_id, "error": "test_target must be a relative path under tests/"}

    original = path.read_text(encoding="utf-8")
    updated = original.replace(old_text, new_text, 1)
    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True), updated.splitlines(keepends=True),
        fromfile=str(path), tofile=str(path),
    ))
    snapshot = None
    audit = {"repair_id": repair_id, "name": name, "path": str(path), "test_target": test_target, "status": "proposed", "created_at": time.time()}
    try:
        from actions import time_guard
        snapshot = time_guard.guard(str(path), "repair_source")
        if not snapshot:
            audit["status"] = "rejected"
            audit["error"] = "Could not create mandatory recovery snapshot"
            _audit_repair(audit)
            return {"ok": False, "repair_id": repair_id, "error": audit["error"], "diff": diff}

        compile(updated, str(path), "exec")
        path.write_text(updated, encoding="utf-8")
        verification = {"ok": True, "compile": True}
        if test_target:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", test_target],
                cwd=str(_PROJECT_ROOT), capture_output=True, text=True, timeout=600,
            )
            verification.update({"ok": result.returncode == 0, "returncode": result.returncode, "stdout": result.stdout[-3000:], "stderr": result.stderr[-3000:]})
        if not verification["ok"]:
            restored = time_guard.restore(snapshot["snapshot_id"])
            audit.update({"status": "rolled_back", "verification": verification, "restore": restored})
            _audit_repair(audit)
            return {"ok": False, "repair_id": repair_id, "error": "Verification failed; repair rolled back", "diff": diff, "verification": verification, "restore": restored}
        audit.update({"status": "applied", "verification": verification, "snapshot": snapshot})
        _audit_repair(audit)
        return {
            "ok": True,
            "repair_id": repair_id,
            "diff": diff,
            "snapshot": snapshot,
            "verification": verification,
            "restart_required": path.name in {"friday.py", "server.py"},
        }
    except Exception as error:
        restore = None
        if snapshot:
            try:
                restore = time_guard.restore(snapshot["snapshot_id"])
            except Exception as restore_error:
                logger.exception("Repair rollback failed")
                restore = {"ok": False, "error": str(restore_error)}
        audit.update({"status": "rolled_back", "error": str(error), "restore": restore})
        _audit_repair(audit)
        return {"ok": False, "repair_id": repair_id, "error": str(error), "diff": diff, "restore": restore}


def read_source(name: str) -> dict:
    """Read the source code of any tool, agent, or action module."""
    path = _find_module(name)
    if not path:
        return {"ok": False, "error": f"Module '{name}' not found"}
    code = path.read_text(encoding="utf-8")
    return {"ok": True, "name": name, "path": str(path), "code": code}


def replace_function(name: str, func_name: str, new_body: str) -> dict:
    """Replace an entire function definition in a module."""
    path = _find_module(name)
    if not path:
        return {"ok": False, "error": f"Module '{name}' not found"}
    code = path.read_text(encoding="utf-8")
    pattern = rf"(def {re.escape(func_name)}\(.*?\n)(.*?)(\n\ndef |\nclass |\Z)"
    match = re.search(pattern, code, re.DOTALL)
    if not match:
        return {"ok": False, "error": f"Function '{func_name}' not found in {name}"}
    signature = match.group(1)  # Preserve the original def line (parameters, defaults)
    tail = match.group(3)
    indent_body = "\n".join("    " + line for line in new_body.strip().split("\n"))
    replacement = f"{signature}{indent_body}{tail}"
    new_code = code[:match.start()] + replacement + code[match.end():]
    try:
        compile(new_code, str(path), "exec")
    except SyntaxError as e:
        return {"ok": False, "error": f"Syntax error: {e}"}
    snapshot = None
    try:
        from actions import time_guard
        snapshot = time_guard.guard(str(path), "replace_function")
    except Exception:
        pass
    path.write_text(new_code, encoding="utf-8")
    return {"ok": True, "name": name, "func": func_name, "message": "Function replaced", "snapshot": snapshot}


def patch_config(name: str, key: str, value) -> dict:
    """Update a value in any JSON config file (models, prompts, settings, etc)."""
    path = _find_json(name)
    if not path:
        return {"ok": False, "error": f"Config '{name}' not found"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "error": f"Invalid JSON in {path}"}
    keys = key.split(".")
    d = data
    for k in keys[:-1]:
        if k not in d or not isinstance(d[k], dict):
            d[k] = {}
        d = d[k]
    old_value = d.get(keys[-1])
    d[keys[-1]] = value
    snapshot = None
    try:
        from actions import time_guard
        snapshot = time_guard.guard(str(path), "patch_config")
    except Exception:
        pass
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"ok": True, "config": name, "key": key, "old": old_value, "new": value, "snapshot": snapshot}


def update_memory(query: str, new_value) -> dict:
    """Update a memory/config entry matching query string."""
    updated = []
    for name in ["capability_registry", "plugin_permissions", "tool_permissions", "settings"]:
        path = _find_json(name)
        if path:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for k, v in data.items():
                        if query.lower() in str(k).lower():
                            data[k] = new_value
                            updated.append({"file": path.name, "key": k})
            except (json.JSONDecodeError, OSError):
                continue
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if not updated:
        return {"ok": False, "error": f"No entries matching '{query}'"}
    return {"ok": True, "updated": updated}


def add_import(name: str, import_statement: str) -> dict:
    """Add an import statement to any module."""
    path = _find_module(name)
    if not path:
        return {"ok": False, "error": f"Module '{name}' not found"}
    code = path.read_text(encoding="utf-8")
    if import_statement in code:
        return {"ok": True, "message": "Import already present"}
    lines = code.split("\n")
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            insert_at = i + 1
    lines.insert(insert_at, import_statement)
    new_code = "\n".join(lines)
    try:
        compile(new_code, str(path), "exec")
    except SyntaxError as e:
        return {"ok": False, "error": f"Syntax error: {e}"}
    snapshot = None
    try:
        from actions import time_guard
        snapshot = time_guard.guard(str(path), "add_import")
    except Exception:
        pass
    path.write_text(new_code, encoding="utf-8")
    return {"ok": True, "message": f"Added import to {name}", "snapshot": snapshot}

