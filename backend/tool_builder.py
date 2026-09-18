"""Friday's unlimited tool factory.

No templates. No manifests. No operations. No limits.
Friday writes code, tests it, fixes it, deploys it, registers it.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import logging
import re
import subprocess
import sys
import tempfile
import traceback


_TOOL_RUNNER = """
import asyncio, inspect, json, runpy, sys
namespace = runpy.run_path(sys.argv[1], run_name='friday_tool')
run = namespace.get('run')
if not callable(run):
    raise TypeError('Tool must define a callable run(arguments)')
arguments = json.loads(sys.stdin.read() or '{}')
result = run(arguments)
if inspect.isawaitable(result):
    result = asyncio.run(result)
if result is not None:
    print(json.dumps(result))
if isinstance(result, dict) and result.get('ok') is False:
    sys.exit(1)
"""

from pathlib import Path
from typing import Any
from plugin_governance import is_active, normalize_governance

logger = logging.getLogger(__name__)


class ToolBuilder:
    """Pure code-based tool building. No templates. No limits."""

    def __init__(self, backend_dir: str):
        self.backend_dir = Path(backend_dir)
        self.registry_path = self.backend_dir / "custom_tools.json"
        self.tools_dir = self.backend_dir / "mytools"
        self.tools: dict[str, dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        if not self.registry_path.exists():
            return
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            self.tools = data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.exception("Could not load custom tools")

    def discover_modules(self) -> None:
        if not self.tools_dir.exists():
            return
        for module_path in self.tools_dir.glob("*.py"):
            if module_path.name == "__init__.py":
                continue
            name = module_path.stem
            code = module_path.read_text(encoding="utf-8")
            existing = self.tools.get(name)
            if existing is not None:
                # Discovery must not erase approvals, schemas, or quarantine state.
                existing["code"] = code
                existing["module_path"] = f"mytools/{module_path.name}"
                continue
            self.tools[name] = {
                "name": name,
                "description": f"Custom tool: {name}",
                "code": code,
                "module_path": f"mytools/{module_path.name}",
                "enabled": True,
            }
        self._save()

    def build(self, name: str, description: str, code: str = "", parameters: dict | None = None, **kwargs) -> dict:
        """Build a tool from raw code. No templates. No limits."""
        tool_name = self._normalise_name(name)
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        module_path = self.tools_dir / f"{tool_name}.py"
        if code == "python_module" and isinstance(kwargs.get("config"), dict):
            code = kwargs["config"].get("code", "")
        wrapped_code = self._wrap_code(code)
        try:
            compile(wrapped_code, str(module_path), "exec")
        except SyntaxError as exc:
            return {"ok": False, "name": tool_name, "registered": False,
                    "test": {"ok": False, "error": str(exc)}}
        previous = module_path.read_bytes() if module_path.exists() else None
        module_path.write_text(wrapped_code, encoding="utf-8")
        test_result = self._test_module(tool_name, module_path)
        if not test_result.get("ok"):
            if previous is None:
                module_path.unlink()
            else:
                module_path.write_bytes(previous)
            return {"ok": False, "name": tool_name, "registered": False,
                    "test": test_result, "previous_preserved": previous is not None}
        self.tools[tool_name] = {
            "name": tool_name,
            "description": description,
            "code": wrapped_code,
            "validated_code": wrapped_code,
            "parameters": parameters or {},
            "module_path": f"mytools/{module_path.name}",
            "enabled": True,
            "governance": normalize_governance(kwargs.get("governance")),
            "test_result": test_result,
        }
        self._save()
        return {"ok": True, "name": tool_name, "path": str(module_path), "test": test_result, "registered": True}

    def _test_module(self, name: str, module_path: Path) -> dict:
        try:
            result = subprocess.run(
                [sys.executable, "-c", _TOOL_RUNNER, str(module_path.resolve())],
                capture_output=True, text=True, timeout=30,
                cwd=str(self.backend_dir),
                input="{}",
            )
            return {"ok": result.returncode == 0, "smoke_test": result.returncode == 0, "returncode": result.returncode, "stdout": result.stdout[-1000:] if result.stdout else "", "stderr": result.stderr[-1000:] if result.stderr else ""}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Test timed out after 30 seconds"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def execute(self, name: str, arguments: dict | None = None) -> dict:
        arguments = arguments or {}
        tool = self.tools.get(name)
        if not tool:
            return {"ok": False, "error": f"Tool '{name}' not found"}
        if not is_active(tool):
            raise PermissionError(f"Tool '{name}' requires approval and security review")
        module_path_str = tool.get("module_path")
        if not module_path_str:
            return {"ok": False, "error": f"Tool '{name}' has no module_path — it may not be executable"}
        module_path = self.backend_dir / module_path_str
        if not module_path.exists():
            return {"ok": False, "error": f"Module file not found: {module_path} (tool '{name}')"}
        try:
            result = subprocess.run(
                [sys.executable, "-c", _TOOL_RUNNER, str(module_path.resolve())],
                capture_output=True, text=True, timeout=60,
                cwd=str(self.backend_dir),
                input=json.dumps(arguments),
            )
            return {"ok": result.returncode == 0, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Execution timed out after 60 seconds"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def debug_and_fix(self, name: str, error: str) -> dict:
        """Restore validated source drift; never infer imports or invent code.

        A traceback must point at this active tool. The saved candidate is
        compiled and smoke-tested in a temporary file before the live file is
        replaced. A subprocess is not a security sandbox.
        """
        failure = {"ok": False, "fixed": False}
        tool = self.tools.get(name)
        if not tool or not is_active(tool):
            return {**failure, "error": "Tool missing or not active"}
        candidate_path = None
        try:
            module_path = (self.backend_dir / tool["module_path"]).resolve()
            if not module_path.is_relative_to(self.tools_dir.resolve()):
                return {**failure, "error": "Repair path is outside mytools"}
            frames = re.findall(r'File "([^"]+)", line (\d+)', str(error))
            if not frames:
                return {**failure, "error": "No traceback frame; manual review required"}
            filename, line = frames[-1]
            frame_path = Path(filename)
            if not frame_path.is_absolute():
                frame_path = self.backend_dir / frame_path
            diagnostic = {"file": filename, "line": int(line),
                          "exception": str(error).strip().splitlines()[-1]}
            failure["diagnostic"] = diagnostic
            if frame_path.resolve() != module_path:
                return {**failure, "error": "Innermost failure is outside this tool"}
            original = module_path.read_bytes()
            candidate = tool.get("validated_code")
            if not isinstance(candidate, str) or candidate == original.decode("utf-8").replace("\r\n", "\n"):
                return {**failure, "error": "No validated source drift to restore; manual review required"}
            compile(candidate, str(module_path), "exec")
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".py",
                                             dir=module_path.parent, delete=False) as staged:
                candidate_path = Path(staged.name)
                staged.write(candidate)
            test_result = self._test_module(name, candidate_path)
            if not test_result.get("ok"):
                return {**failure, "test": test_result, "error": "Candidate failed validation"}
            if module_path.read_bytes() != original:
                return {**failure, "error": "Source changed during validation"}
            previous_manifest = dict(tool)
            candidate_path.replace(module_path)
            try:
                tool.update(code=candidate, test_result=test_result)
                self._save()
            except Exception:
                module_path.write_bytes(original)
                self.tools[name] = previous_manifest
                raise
            return {"ok": True, "fixed": True, "test": test_result,
                    "diagnostic": diagnostic, "strategy": "restore_validated_source"}
        except Exception as exc:
            return {**failure, "error": str(exc)}
        finally:
            if candidate_path is not None:
                candidate_path.unlink(missing_ok=True)

    def revert(self, name: str, previous_manifest: dict | None) -> dict:
        """Undo a just-registered tool.

        Used when the approval behind a build expired before the artifact could
        be recorded (the plan was edited or cancelled mid-build). Without this a
        rejected candidate would stay live with nothing pointing at it.
        """
        module_path = self.tools_dir / f"{name}.py"
        if previous_manifest is None:
            module_path.unlink(missing_ok=True)
            self.tools.pop(name, None)
        else:
            previous = dict(previous_manifest)
            code = previous.get("code")
            if isinstance(code, str):
                module_path.write_text(code, encoding="utf-8")
            self.tools[name] = previous
        self._save()
        return {"ok": True, "name": name, "restored_previous": previous_manifest is not None}

    def list_tools(self) -> list[dict]:
        return [{"name": name, "description": tool.get("description", ""), "enabled": tool.get("enabled", True)} for name, tool in self.tools.items()]

    def declarations(self) -> list[dict]:
        return [{"name": name, "description": tool.get("description", ""), "parameters": {"type": "OBJECT", "properties": tool.get("parameters", {})}} for name, tool in self.tools.items() if tool.get("enabled", True)]

    def _save(self) -> None:
        self.registry_path.write_text(json.dumps(self.tools, indent=2, default=str), encoding="utf-8")

    def _load_and_instantiate(self, name: str, module_path: Path) -> Any:
        """Load a tool module from disk and return its run() callable.

        Raises on any failure (import error, syntax error, missing run()).
        The caller (load_all_tools) handles logging and failure recording.
        """
        try:
            ast.parse(module_path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            raise SyntaxError(f"Tool {name} has a syntax error: {exc}") from exc

        spec = importlib.util.spec_from_file_location(f"friday_tool_{name}", module_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not create import spec for tool {name}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        run = getattr(module, "run", None)
        if not callable(run):
            raise AttributeError(f"Tool {name} has no callable run() function")
        return run

    def load_all_tools(self) -> list[str]:
        """Load all active tools, returning list of successfully loaded names.

        Each tool is loaded with graceful degradation — one failure does not
        break the others.
        """
        loaded = []
        for name, manifest in self.tools.items():
            if not is_active(manifest):
                continue
            try:
                module_path = self.backend_dir / manifest["module_path"]
                if not module_path.exists():
                    logger.warning("Tool %s: module file missing at %s", name, module_path)
                    continue
                self._load_and_instantiate(name, module_path)
                loaded.append(name)
            except Exception as exc:
                logger.warning("Tool %s failed to load: %s", name, exc)
        return loaded

    @staticmethod
    def _normalise_name(name: str) -> str:
        value = "".join(char if char.isalnum() or char == "_" else "_" for char in name.strip().lower())
        if not value or not value[0].isalpha():
            raise ValueError("Tool name must start with a letter")
        return value

    def _wrap_code(self, code: str) -> str:
        stripped = code.strip()
        if "def run(" in stripped:
            return stripped
        wrapped = f"def run(args=None):\n    args = args or {{}}\n{self._indent(stripped)}\n"
        # When executed as a script (testing or running), parse JSON from stdin
        # and call run() with the arguments.
        return (
            wrapped
            + "\n\nif __name__ == \"__main__\":\n"
            + "    import json, sys\n"
            + "    try:\n"
            + "        arguments = json.load(sys.stdin) if sys.stdin.isatty() else json.loads(sys.stdin.read())\n"
            + "    except Exception:\n"
            + "        arguments = {}\n"
            + "    result = run(arguments)\n"
            + "    if result is not None:\n"
            + "        print(json.dumps(result))\n"
        )

    @staticmethod
    def _indent(code: str) -> str:
        lines = code.split("\n")
        return "\n".join(f"    {line}" if line.strip() else line for line in lines)