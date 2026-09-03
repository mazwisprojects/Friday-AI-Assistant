"""Management layer for Friday's generated tools and background agents."""

from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime
from pathlib import Path


class PluginManager:
    def __init__(self, backend_dir: str, tool_builder, agent_builder, dispatcher):
        self.backend_dir = Path(backend_dir)
        self.tool_builder = tool_builder
        self.agent_builder = agent_builder
        self.dispatcher = dispatcher
        self._lock = threading.RLock()
        self.versions_dir = self.backend_dir / ".friday-plugin-versions"

    def list_plugins(self) -> list[dict]:
        with self._lock:
            plugins = []
            for name, manifest in self.tool_builder.tools.items():
                plugins.append({"name": name, "kind": "tool", "enabled": manifest.get("enabled", True), "version": manifest.get("version", "1.0.0")})
            for name, manifest in self.agent_builder.agents.items():
                plugins.append({"name": name, "kind": "agent", "enabled": manifest.get("enabled", True), "version": manifest.get("version", "1.0.0"), "status": next((entry.get("status") for entry in self.dispatcher.list_agents() if entry.get("agent_type") == name), "idle")})
            return sorted(plugins, key=lambda plugin: (plugin["kind"], plugin["name"]))

    def set_enabled(self, kind: str, name: str, enabled: bool) -> dict:
        with self._lock:
            registry = self.tool_builder.tools if kind == "tool" else self.agent_builder.agents if kind == "agent" else None
            if registry is None or name not in registry:
                raise ValueError(f"Plugin not found: {kind}/{name}")
            registry[name]["enabled"] = enabled
            if kind == "tool":
                self.tool_builder._save()
            else:
                self.agent_builder._save()
                if enabled:
                    self.dispatcher.register_agent(name, self.agent_builder.load_callable(name))
                else:
                    self.dispatcher.unregister_agent(name)
            return {"name": name, "kind": kind, "enabled": enabled}

    def health(self) -> dict:
        return {"plugins": self.list_plugins(), "tool_failures": self._read_failure_log()}

    def snapshot(self, label: str = "manual") -> dict:
        """Create a local rollback snapshot of plugin modules and registries."""
        with self._lock:
            safe_label = "".join(char if char.isalnum() or char in "-_" else "_" for char in label)[:40] or "manual"
            snapshot_dir = self.versions_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_label}"
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            for source in (self.tool_builder.tools_dir, self.agent_builder.agents_dir):
                if source.exists():
                    shutil.copytree(source, snapshot_dir / source.name, dirs_exist_ok=True)
            for source in (self.tool_builder.registry_path, self.agent_builder.registry_path):
                if source.exists():
                    shutil.copy2(source, snapshot_dir / source.name)
            return {"snapshot": str(snapshot_dir), "created_at": datetime.now().isoformat(timespec="seconds"), "plugins": len(self.list_plugins())}

    def list_snapshots(self) -> list[dict]:
        if not self.versions_dir.exists():
            return []
        return [{"name": path.name, "path": str(path)} for path in sorted(self.versions_dir.iterdir(), reverse=True) if path.is_dir()]

    def rollback(self, snapshot_name: str) -> dict:
        with self._lock:
            snapshot_dir = (self.versions_dir / snapshot_name).resolve()
            if snapshot_dir.parent != self.versions_dir.resolve() or not snapshot_dir.is_dir():
                raise ValueError(f"Plugin snapshot not found: {snapshot_name}")
            current = self.snapshot("before_rollback")
            for directory, target in ((snapshot_dir / "mytools", self.tool_builder.tools_dir), (snapshot_dir / "agents", self.agent_builder.agents_dir)):
                if directory.exists():
                    shutil.copytree(directory, target, dirs_exist_ok=True)
            for source, target in ((snapshot_dir / self.tool_builder.registry_path.name, self.tool_builder.registry_path), (snapshot_dir / self.agent_builder.registry_path.name, self.agent_builder.registry_path)):
                if source.exists():
                    shutil.copy2(source, target)
            self.tool_builder.tools.clear()
            self.tool_builder.load()
            self.tool_builder.discover_modules()
            self.agent_builder.agents.clear()
            self.agent_builder.load()
            self.agent_builder.discover_modules()
            return {"rolled_back_to": snapshot_name, "safety_snapshot": current["snapshot"], "plugins": len(self.list_plugins())}

    def _read_failure_log(self) -> dict:
        path = self.backend_dir / "tool_failures.json"
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}
