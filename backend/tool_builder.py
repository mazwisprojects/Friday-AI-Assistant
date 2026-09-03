"""Approved custom-tool factory for Friday.

Custom tools are declarative manifests. They are validated, smoke-tested, persisted,
and executed only through approved operation templates.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import requests


class ToolBuilder:
    APPROVED_OPERATIONS = {"http_json_get", "readonly_powershell", "python_module"}

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
            print(f"[TOOLS] Could not load custom tools: {exc}")

    def build(self, name: str, description: str, operation: str, parameters: dict | None = None, config: dict | None = None) -> dict:
        tool_name = self._normalise_name(name)
        if operation not in self.APPROVED_OPERATIONS:
            raise ValueError(f"Unsupported tool template: {operation}")
        manifest = {
            "name": tool_name,
            "description": description.strip(),
            "operation": operation,
            "parameters": parameters or {},
            "config": config or {},
        }
        self._validate(manifest)
        smoke_test = self.test(manifest)
        if not smoke_test["ok"]:
            raise ValueError(f"Tool smoke test failed: {smoke_test['error']}")
        self.tools[tool_name] = manifest
        module_path = self._write_module(manifest)
        self._save()
        return {"registered": True, "tool": manifest, "module": str(module_path), "test": smoke_test}

    def register_declaration(self, manifest: dict) -> None:
        self._validate(manifest)
        self.tools[manifest["name"]] = manifest
        self._save()

    def test(self, manifest: dict) -> dict:
        try:
            self._validate(manifest)
            operation = manifest["operation"]
            if operation == "http_json_get":
                url = manifest["config"].get("url")
                if not url or not url.startswith("https://"):
                    raise ValueError("http_json_get requires an HTTPS config.url")
            elif operation == "readonly_powershell":
                command = manifest["config"].get("command", "")
                self._validate_powershell(command)
            elif operation == "python_module":
                code = manifest["config"].get("code", "")
                if code:
                    compile(code, f"<custom-tool:{manifest['name']}>", "exec")
                    line_count = len(code.splitlines())
                else:
                    module_path = self.tools_dir / f"{manifest['name']}.py"
                    if not module_path.exists():
                        raise ValueError(f"Generated module is missing: {module_path}")
                    compile(module_path.read_text(encoding="utf-8"), str(module_path), "exec")
                    line_count = int(manifest.get("config", {}).get("line_count", 0))
                return {"ok": True, "name": manifest["name"], "line_count": line_count}
            return {"ok": True, "name": manifest["name"]}
        except Exception as exc:
            return {"ok": False, "name": manifest.get("name"), "error": str(exc)}

    def execute(self, name: str, arguments: dict | None = None) -> Any:
        manifest = self.tools.get(name)
        if not manifest:
            raise ValueError(f"Custom tool is not registered: {name}")
        arguments = arguments or {}
        operation = manifest["operation"]
        if operation == "http_json_get":
            url = manifest["config"]["url"].format(**arguments)
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        if operation == "readonly_powershell":
            command = manifest["config"]["command"]
            self._validate_powershell(command)
            result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True, timeout=30)
            return {"returncode": result.returncode, "stdout": result.stdout[-6000:], "stderr": result.stderr[-2000:]}
        if operation == "python_module":
            module_path = self.tools_dir / f"{name}.py"
            if not module_path.exists():
                raise ValueError(f"Generated module is missing: {module_path}")
            result = subprocess.run([sys.executable, str(module_path)], input=json.dumps(arguments), capture_output=True, text=True, timeout=60)
            return {"returncode": result.returncode, "stdout": result.stdout[-6000:], "stderr": result.stderr[-2000:]}
        raise ValueError(f"Unsupported tool template: {operation}")

    def declarations(self) -> list[dict]:
        declarations = []
        for manifest in self.tools.values():
            declarations.append({
                "name": manifest["name"],
                "description": manifest["description"],
                "parameters": {"type": "OBJECT", "properties": manifest["parameters"]},
            })
        return declarations

    def _save(self) -> None:
        registry_tools = {}
        for name, manifest in self.tools.items():
            saved_manifest = dict(manifest)
            config = dict(saved_manifest.get("config", {}))
            if saved_manifest.get("operation") == "python_module" and "code" in config:
                config.pop("code")
                config["module_path"] = f"mytools/{name}.py"
                config["line_count"] = len(manifest["config"].get("code", "").splitlines())
            saved_manifest["config"] = config
            registry_tools[name] = saved_manifest
        self.registry_path.write_text(json.dumps(registry_tools, indent=2), encoding="utf-8")

    def _write_module(self, manifest: dict) -> Path:
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        module_path = self.tools_dir / f"{manifest['name']}.py"
        module_path.write_text(
            "# Generated by Friday's verified custom-tool builder.\n"
            f"TOOL_MANIFEST = {manifest!r}\n\n"
            "def describe():\n"
            "    return TOOL_MANIFEST.copy()\n",
            encoding="utf-8",
        )
        if manifest["operation"] == "python_module":
            module_manifest = dict(manifest)
            module_config = dict(module_manifest.get("config", {}))
            module_config.pop("code", None)
            module_manifest["config"] = module_config
            module_path.write_text(
                "# Generated by Friday's verified custom-tool builder.\n"
                f"TOOL_MANIFEST = {module_manifest!r}\n\n"
                "def describe():\n"
                "    return TOOL_MANIFEST.copy()\n\n"
                "if __name__ == '__main__':\n"
                "    import json\n"
                "    arguments = json.loads(input())\n"
                + textwrap.indent(manifest["config"]["code"], "    ") + "\n",
                encoding="utf-8",
            )
        return module_path

    @staticmethod
    def _normalise_name(name: str) -> str:
        value = "".join(char if char.isalnum() or char == "_" else "_" for char in name.strip().lower())
        if not value or not value[0].isalpha():
            raise ValueError("Tool name must start with a letter")
        return value

    @classmethod
    def _validate(cls, manifest: dict) -> None:
        if not manifest.get("name") or not manifest.get("description"):
            raise ValueError("Tool name and description are required")
        if manifest.get("operation") not in cls.APPROVED_OPERATIONS:
            raise ValueError("Tool operation is not approved")
        if not isinstance(manifest.get("parameters", {}), dict) or not isinstance(manifest.get("config", {}), dict):
            raise ValueError("Tool parameters and config must be objects")

    @staticmethod
    def _validate_powershell(command: str) -> None:
        blocked = ("remove-item", "del ", "format-volume", "stop-computer", "restart-computer", "invoke-expression", "iex ", "start-process")
        lowered = command.lower()
        if not command or any(token in lowered for token in blocked):
            raise ValueError("Only non-destructive read-only PowerShell commands are allowed")