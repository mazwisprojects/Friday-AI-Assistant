"""Factory and loader for verified Friday background-agent plugins."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from typing import Any


class AgentBuilder:
    def __init__(self, backend_dir: str):
        self.backend_dir = Path(backend_dir)
        self.agents_dir = self.backend_dir / "agents"
        self.registry_path = self.backend_dir / "custom_agents.json"
        self.agents: dict[str, dict[str, Any]] = {}
        self.load()
        self.discover_modules()

    def load(self) -> None:
        if not self.registry_path.exists():
            return
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            self.agents = data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[AGENTS] Could not load custom agents: {exc}")

    def discover_modules(self) -> None:
        if not self.agents_dir.exists():
            return
        changed = False
        for path in self.agents_dir.glob("*.py"):
            if path.name.startswith("__") or path.name == "agent_dispatcher.py":
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                manifest = None
                has_run = False
                for node in tree.body:
                    if isinstance(node, ast.FunctionDef) and node.name == "run":
                        has_run = True
                    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "AGENT_MANIFEST" for target in node.targets):
                        manifest = ast.literal_eval(node.value)
                if not isinstance(manifest, dict) or not has_run:
                    continue
                self._validate(manifest)
                manifest = dict(manifest)
                manifest["module_path"] = f"agents/{path.name}"
                manifest["line_count"] = len(path.read_text(encoding="utf-8").splitlines())
                self.agents.setdefault(manifest["name"], manifest)
                changed = True
            except (OSError, SyntaxError, ValueError, MemoryError) as exc:
                print(f"[AGENTS] Skipping invalid agent {path.name}: {exc}")
        if changed:
            self._save()

    def build(self, name: str, description: str, code: str, parameters: dict | None = None) -> dict:
        agent_name = self._normalise_name(name)
        manifest = {
            "name": agent_name,
            "version": "1.0.0",
            "enabled": True,
            "description": description.strip(),
            "parameters": parameters or {},
        }
        self._validate(manifest)
        compile(code, f"<agent:{agent_name}>", "exec")
        if "def run(" not in code:
            raise ValueError("Agent code must define run(goal, repo_path, log, cancel_event)")
        self.agents[agent_name] = {**manifest, "module_path": f"agents/{agent_name}.py", "line_count": len(code.splitlines())}
        module_path = self._write_module(manifest, code)
        self._save()
        return {"registered": True, "agent": self.agents[agent_name], "module": str(module_path), "verified": True}

    def test(self, name: str) -> dict:
        manifest = self.agents.get(name)
        if not manifest:
            return {"ok": False, "error": f"Agent is not registered: {name}"}
        path = self.backend_dir / manifest.get("module_path", f"agents/{name}.py")
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
            tree = ast.parse(source, filename=str(path))
            has_run = any(isinstance(node, ast.FunctionDef) and node.name == "run" for node in tree.body)
            if not has_run:
                raise ValueError("Agent run() entry point is missing")
            return {"ok": True, "name": name, "line_count": len(source.splitlines())}
        except Exception as exc:
            return {"ok": False, "name": name, "error": str(exc)}

    def load_callable(self, name: str):
        manifest = self.agents.get(name)
        if not manifest:
            raise ValueError(f"Agent is not registered: {name}")
        path = (self.backend_dir / manifest.get("module_path", f"agents/{name}.py")).resolve()
        if path.parent != self.agents_dir.resolve():
            raise ValueError("Agent module must remain inside backend/agents")
        spec = importlib.util.spec_from_file_location(f"friday_agent_{name}", path)
        if not spec or not spec.loader:
            raise ValueError(f"Could not load agent module: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        run = getattr(module, "run", None)
        if not callable(run):
            raise ValueError("Agent module must expose callable run")
        return run

    def declarations(self) -> list[dict]:
        return [{"name": name, "description": manifest["description"], "parameters": {"type": "OBJECT", "properties": manifest.get("parameters", {})}} for name, manifest in self.agents.items() if manifest.get("enabled", True)]

    def _save(self) -> None:
        self.registry_path.write_text(json.dumps(self.agents, indent=2), encoding="utf-8")

    def _write_module(self, manifest: dict, code: str) -> Path:
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        path = self.agents_dir / f"{manifest['name']}.py"
        path.write_text(
            "# Generated by Friday's verified agent builder.\n"
            f"AGENT_MANIFEST = {manifest!r}\n\n"
            + code.rstrip() + "\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _normalise_name(name: str) -> str:
        value = "".join(char if char.isalnum() or char == "_" else "_" for char in name.strip().lower())
        if not value or not value[0].isalpha():
            raise ValueError("Agent name must start with a letter")
        return value

    @staticmethod
    def _validate(manifest: dict) -> None:
        if not manifest.get("name") or not manifest.get("description"):
            raise ValueError("Agent name and description are required")
        if not isinstance(manifest.get("parameters", {}), dict):
            raise ValueError("Agent parameters must be an object")
