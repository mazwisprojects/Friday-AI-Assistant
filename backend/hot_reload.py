"""Hot-reload engine for Friday's dynamic capabilities.

Enables building, registering, and executing tools and agents at runtime
without restarting the backend.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any


class CapabilityEngine:
    def __init__(self, backend_dir, tool_builder, agent_builder, dispatcher):
        self.backend_dir = Path(backend_dir)
        self.tool_builder = tool_builder
        self.agent_builder = agent_builder
        self.dispatcher = dispatcher
        self._execution_log = []
        self._log_lock = threading.Lock()

    def refresh_tools(self):
        self.tool_builder.tools.clear()
        self.tool_builder.load()
        self.tool_builder.discover_modules()
        decs = self.tool_builder.declarations()
        return {"tools": list(self.tool_builder.tools.keys()), "declarations": decs, "count": len(decs)}

    def refresh_agents(self):
        self.agent_builder.agents.clear()
        self.agent_builder.load()
        self.agent_builder.discover_modules()
        reg, skip = [], []
        from plugin_governance import is_active
        for name, manifest in self.agent_builder.agents.items():
            try:
                if not is_active(manifest):
                    skip.append(name); continue
                self.dispatcher.register_agent(name, self.agent_builder.load_callable(name))
                reg.append(name)
            except Exception as e:
                skip.append(f"{name}: {e}")
        return {"registered": reg, "skipped": skip}

    def run_script(self, language, code, arguments=None, timeout=60):
        arguments = arguments or {}
        lang = language.lower().strip()
        self._log("run_script", {"language": lang, "code_len": len(code)})
        try:
            if lang in ("python", "python3", "py"):
                return self._run_python(code, arguments, timeout)
            if lang in ("powershell", "ps", "ps1"):
                return self._run_powershell(code, arguments, timeout)
            if lang in ("node", "nodejs", "js", "javascript"):
                return self._run_node(code, arguments, timeout)
            if lang in ("cmd", "batch", "bat", "shell"):
                return self._run_cmd(code, arguments, timeout)
            return {"ok": False, "error": f"Unsupported language {lang}. Use: python, powershell, node, cmd"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _run_python(self, code, arguments, timeout):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(f"_FRIDAY_ARGS = {json.dumps(arguments, ensure_ascii=False)}\nARGS = _FRIDAY_ARGS\n")
            f.write(code)
            f.write("\n\nif 'run' in dir() and callable(run):\n    _result = run(ARGS)\n    if _result is not None:\n        import json\n        print('\\n___FRIDAY_RESULT___')\n        print(json.dumps(_result, ensure_ascii=False, default=str))\n")
            tmp = f.name
        try:
            r = subprocess.run([sys.executable, tmp], capture_output=True, text=True, timeout=timeout, cwd=str(self.backend_dir))
            return self._parse_result(r, "python")
        finally:
            os.unlink(tmp) if os.path.exists(tmp) else None

    def _parse_result(self, result, language):
        output = result.stdout
        parsed = None
        marker = "___FRIDAY_RESULT___"
        if marker in output:
            parts = output.split(marker)
            output = parts[0].strip()
            try:
                parsed = json.loads(parts[1].strip())
            except json.JSONDecodeError:
                parsed = parts[1].strip()
        return {"ok": result.returncode == 0, "stdout": output, "stderr": result.stderr, "result": parsed, "returncode": result.returncode, "language": language}

    def _run_powershell(self, code, arguments, timeout):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ps1", delete=False, encoding="utf-8") as f:
            f.write(f"$FRIDAY_ARGS = @'\n{json.dumps(arguments, ensure_ascii=False)}\n'@ | ConvertFrom-Json\n")
            f.write(code)
            tmp = f.name
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tmp], capture_output=True, text=True, timeout=timeout, cwd=str(self.backend_dir))
            return {"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode, "language": "powershell"}
        finally:
            os.unlink(tmp) if os.path.exists(tmp) else None

    def _run_node(self, code, arguments, timeout):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(f"const ARGS = {json.dumps(arguments, ensure_ascii=False)};\n")
            f.write(code)
            f.write("\n\nif (typeof run === 'function') {\n    const _r = run(ARGS);\n    if (_r !== undefined) { console.log('\\n___FRIDAY_RESULT___'); console.log(JSON.stringify(_r)); }\n}\n")
            tmp = f.name
        try:
            r = subprocess.run(["node", tmp], capture_output=True, text=True, timeout=timeout, cwd=str(self.backend_dir))
            return self._parse_result(r, "node")
        finally:
            os.unlink(tmp) if os.path.exists(tmp) else None

    def _run_cmd(self, code, arguments, timeout):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".bat", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp = f.name
        try:
            r = subprocess.run(["/c", tmp], capture_output=True, text=True, timeout=timeout, cwd=str(self.backend_dir), shell=True)
            return {"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode, "language": "cmd"}
        finally:
            os.unlink(tmp) if os.path.exists(tmp) else None

    def write_action(self, name, code):
        action_name = self.tool_builder._normalise_name(name)
        actions_dir = self.backend_dir / "actions"
        actions_dir.mkdir(exist_ok=True)
        module_path = actions_dir / f"{action_name}.py"
        try:
            compile(code, str(module_path), "exec")
        except SyntaxError as e:
            return {"ok": False, "error": f"Syntax error: {e}"}
        snapshot = None
        try:
            from actions import time_guard
            snapshot = time_guard.guard(str(module_path), "write_action") if module_path.exists() else None
        except Exception:
            snapshot = None
        module_path.write_text(f'"""Auto-generated action module: {action_name}."""\n\n' + code.rstrip() + "\n", encoding="utf-8")
        return {"ok": True, "module": action_name, "path": str(module_path), "snapshot": snapshot}

    def _log(self, action, data):
        with self._log_lock:
            self._execution_log.append({"action": action, "data": data})
            if len(self._execution_log) > 500:
                self._execution_log = self._execution_log[-500:]

    def get_log(self, limit=50):
        with self._log_lock:
            return self._execution_log[-limit:]

    def full_refresh(self):
        return {"tools": self.refresh_tools(), "agents": self.refresh_agents()}