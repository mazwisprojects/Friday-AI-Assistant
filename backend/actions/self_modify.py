"""Self-Modification Layer for FRIDAY — edit tools, agents, configs, memories on the fly."""
from __future__ import annotations
import json
import re
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_ACTIONS = _BACKEND / "actions"
_AGENTS = _BACKEND / "agents"
_MYTOOLS = _BACKEND / "mytools"
_MEMORY = _BACKEND / "long_term_memory"


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

