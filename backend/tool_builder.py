"""Friday's unlimited tool factory.

No templates. No manifests. No operations. No limits.
Friday writes code, tests it, fixes it, deploys it, registers it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from plugin_governance import is_active, normalize_governance


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
        wrapped_code = self._wrap_code(code)
        module_path.write_text(wrapped_code, encoding="utf-8")
        test_result = self._test_module(tool_name, module_path)
        self.tools[tool_name] = {
            "name": tool_name,
            "description": description,
            "code": wrapped_code,
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
                [sys.executable, str(module_path)],
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
        module_path = self.backend_dir / tool["module_path"]
        if not module_path.exists():
            return {"ok": False, "error": f"Module file not found: {module_path}"}
        try:
            result = subprocess.run(
                [sys.executable, str(module_path)],
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
        tool = self.tools.get(name)
        if not tool:
            return {"ok": False, "error": f"Tool '{name}' not found"}
        code = tool.get("code", "")
        fixed = code
        if "NameError" in error and "is not defined" in error:
            import re
            match = re.search(r"name '(\w+)' is not defined", error)
            if match:
                undefined = match.group(1)
                fixed = f"import {undefined}\n{fixed}"
        if "IndentationError" in error:
            lines = fixed.split("\n")
            fixed = "\n".join(line.rstrip() for line in lines)
        module_path = self.backend_dir / tool["module_path"]
        module_path.write_text(fixed, encoding="utf-8")
        test_result = self._test_module(name, module_path)
        tool["code"] = fixed
        tool["test_result"] = test_result
        self.tools[name] = tool
        self._save()
        return {"ok": test_result.get("ok", False), "fixed": fixed != code, "test": test_result}

    def list_tools(self) -> list[dict]:
        return [{"name": name, "description": tool.get("description", ""), "enabled": tool.get("enabled", True)} for name, tool in self.tools.items()]

    def declarations(self) -> list[dict]:
        return [{"name": name, "description": tool.get("description", ""), "parameters": {"type": "OBJECT", "properties": tool.get("parameters", {})}} for name, tool in self.tools.items() if tool.get("enabled", True)]

    def _save(self) -> None:
        self.registry_path.write_text(json.dumps(self.tools, indent=2, default=str), encoding="utf-8")

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
        return f"def run(args=None):\n    args = args or {{}}\n{self._indent(stripped)}\n"

    @staticmethod
    def _indent(code: str) -> str:
        lines = code.split("\n")
        return "\n".join(f"    {line}" if line.strip() else line for line in lines)