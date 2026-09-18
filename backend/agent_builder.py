"""Factory and loader for verified Friday background-agent plugins."""

from __future__ import annotations

import logging

import ast
import importlib.util
import json
import tempfile
import threading
import subprocess
import sys

_AGENT_TEST_RUNNER = """
import contextlib, json, os, runpy, sys, threading
try:
    with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        namespace = runpy.run_path(sys.argv[1], run_name='friday_agent_test')
        result = namespace['run']('Smoke test: validate this agent contract only.',
                                  os.getcwd(), lambda _: None, threading.Event())
        if not isinstance(result, dict):
            raise ValueError('Agent run() must return a dictionary')
        if result.get('ok') is False:
            raise ValueError('Agent run() reported failure: ' + str(result.get('error', 'ok=False'))[:1000])
    print(json.dumps({'ok': True, 'result_keys': sorted(str(key) for key in result)[:100]}))
except BaseException as exc:
    print(json.dumps({'ok': False, 'error': (type(exc).__name__ + ': ' + str(exc))[:2000]}))
    sys.exit(1)
"""
from pathlib import Path
from typing import Any
from plugin_governance import is_active, normalize_governance, validate_limits
from agent_sandbox import validate_source

logger = logging.getLogger(__name__)


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
            logger.exception("Could not load custom agents")
        self._prune_orphans()

    def _prune_orphans(self) -> None:
        """Drop registry entries whose module file no longer exists.

        Keeps the live registry consistent with the agents directory so that
        startup registration, declarations, and scheduling never reference a
        module that cannot be loaded.
        """
        orphans = [
            name for name, manifest in self.agents.items()
            if not (self.backend_dir / manifest.get("module_path", f"agents/{name}.py")).exists()
        ]
        if not orphans:
            return
        for name in orphans:
            logger.warning("Pruning orphaned agent registry entry %s (module file missing)", name)
            self.agents.pop(name, None)
        try:
            self._save()
        except OSError:
            logger.exception("Could not save pruned agent registry")

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
                logger.exception("Skipping invalid agent %s", path.name)
        if changed:
            self._save()

    def build(self, name: str, description: str, code: str, parameters: dict | None = None, governance: dict | None = None) -> dict:
        agent_name = self._normalise_name(name)
        manifest = {
            "name": agent_name,
            "version": "1.0.0",
            "enabled": True,
            "description": description.strip(),
            "parameters": parameters or {},
            "governance": normalize_governance(governance),
        }
        validate_limits(manifest["governance"])
        self._validate(manifest)
        compile(code, f"<agent:{agent_name}>", "exec")
        validate_source(code)
        if "def run(" not in code:
            raise ValueError("Agent code must define run(goal, repo_path, log, cancel_event)")
        module_path = self.agents_dir / f"{agent_name}.py"
        # Validate outside the live registry. A failing candidate never replaces
        # code that another caller could load while the smoke test is running.
        with tempfile.TemporaryDirectory(prefix="friday-agent-stage-") as staging:
            candidate = Path(staging) / "candidate.py"
            candidate.write_text(self._module_source(manifest, code), encoding="utf-8")
            smoke_test = self._test_path(agent_name, candidate)
        if not smoke_test["ok"]:
            raise ValueError(f"Agent smoke test failed: {smoke_test['error']}")
        previous = self.agents.get(agent_name)
        previous_bytes = module_path.read_bytes() if module_path.exists() else None
        previous_registry = self.registry_path.read_bytes() if self.registry_path.exists() else None
        try:
            self.agents[agent_name] = {**manifest, "module_path": f"agents/{agent_name}.py", "line_count": len(code.splitlines())}
            self._write_module(manifest, code)
            self._save()
        except Exception:
            if previous is not None:
                self.agents[agent_name] = previous
            else:
                self.agents.pop(agent_name, None)
            if previous_bytes is not None:
                module_path.write_bytes(previous_bytes)
            else:
                module_path.unlink(missing_ok=True)
            if previous_registry is not None:
                self.registry_path.write_bytes(previous_registry)
            else:
                self.registry_path.unlink(missing_ok=True)
            raise
        return {"registered": True, "agent": self.agents[agent_name], "module": str(module_path), "verified": True, "test": smoke_test}

    def revert(self, name: str, previous_manifest: dict | None, previous_bytes: bytes | None) -> dict:
        """Undo a just-registered agent.

        The caller snapshots the module bytes before building so that a rejected
        candidate can be removed or replaced with the exact previous source when
        the approval behind it expired mid-build.
        """
        module_path = self.agents_dir / f"{name}.py"
        if previous_bytes is None:
            module_path.unlink(missing_ok=True)
        else:
            module_path.write_bytes(previous_bytes)
        if previous_manifest is None:
            self.agents.pop(name, None)
        else:
            self.agents[name] = previous_manifest
        self._save()
        return {"ok": True, "name": name, "restored_previous": previous_manifest is not None}

    def test(self, name: str) -> dict:
        manifest = self.agents.get(name)
        if not manifest:
            return {"ok": False, "error": f"Agent is not registered: {name}"}
        path = self.backend_dir / manifest.get("module_path", f"agents/{name}.py")
        return self._test_path(name, path)

    def _test_path(self, name: str, path: Path, timeout: float = 10) -> dict:
        """Crash/timeout isolation only; not a security sandbox for hostile code."""
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
            validate_source(source)
            tree = ast.parse(source, filename=str(path))
            has_run = any(isinstance(node, ast.FunctionDef) and node.name == "run" for node in tree.body)
            if not has_run:
                raise ValueError("Agent run() entry point is missing")
            with tempfile.TemporaryDirectory(prefix="friday-agent-test-") as test_repo:
                completed = subprocess.run(
                    [sys.executable, "-I", "-c", _AGENT_TEST_RUNNER, str(path.resolve())],
                    cwd=test_repo, capture_output=True, text=True, timeout=timeout,
                    encoding="utf-8", errors="replace",
                )
            try:
                result = json.loads(completed.stdout)
            except (ValueError, TypeError):
                raise ValueError(f"Agent test returned no valid result (exit {completed.returncode})")
            if completed.returncode != 0 or not isinstance(result, dict) or result.get("ok") is not True:
                raise ValueError(result.get("error", "Agent process failed") if isinstance(result, dict) else "Invalid test result")
            return {"ok": True, "name": name, "line_count": len(source.splitlines()),
                    "smoke_test": True, "result_keys": result["result_keys"], "process_isolated": True}
        except subprocess.TimeoutExpired:
            return {"ok": False, "name": name, "error": "Agent smoke test timed out"}
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
        return [{"name": name, "description": manifest["description"], "parameters": {"type": "OBJECT", "properties": manifest.get("parameters", {})}} for name, manifest in self.agents.items() if is_active(manifest)]

    def _save(self) -> None:
        self.registry_path.write_text(json.dumps(self.agents, indent=2), encoding="utf-8")

    @staticmethod
    def _module_source(manifest: dict, code: str) -> str:
        return ("# Generated by Friday's verified agent builder.\n"
                f"AGENT_MANIFEST = {manifest!r}\n\n" + code.rstrip() + "\n")

    def _write_module(self, manifest: dict, code: str) -> Path:
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        path = self.agents_dir / f"{manifest['name']}.py"
        path.write_text(self._module_source(manifest, code), encoding="utf-8")
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
