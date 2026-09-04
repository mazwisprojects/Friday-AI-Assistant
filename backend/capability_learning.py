"""Runtime learning loop for governed Friday capabilities."""

from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path


class CapabilityLearning:
    def __init__(self, backend_dir: str, ledger, plugin_manager):
        self.backend_dir = Path(backend_dir)
        self.ledger = ledger
        self.plugin_manager = plugin_manager
        self.proposals_path = self.backend_dir / "capability_proposals.json"
        self._quarantined = set()

    def inspect(self) -> dict:
        entries = self.ledger.list(500)
        proposals = self._load_proposals()
        usage = Counter(entry.get("name") for entry in entries if entry.get("name"))
        failures = Counter(entry.get("name") for entry in entries if entry.get("status") == "failed" and entry.get("name"))
        pattern_proposals = []
        for name, count in usage.items():
            if count < 3 or name in {item.get("name") for item in proposals}:
                continue
            priority = "high" if count >= 10 else "normal"
            proposal = {"name": name, "kind": "workflow", "reason": f"Capability used {count} times; consider a governed reusable workflow.", "usage_count": count, "priority": priority, "status": "pending_review"}
            proposals.append(proposal)
            pattern_proposals.append(proposal)
        if pattern_proposals:
            self._save_proposals(proposals)
        expired = self.plugin_manager.expire()
        security = self.security_scan()
        self._score_plugins(entries)
        self._quarantine_repeated_failures(failures)
        self._quarantine_security_findings(security)
        return {"usage": dict(usage), "failures": dict(failures), "proposals": pattern_proposals, "expired": expired, "security": security}

    def _quarantine_repeated_failures(self, failures: Counter) -> None:
        for name, count in failures.items():
            if count >= 3 and name not in self._quarantined:
                try:
                    self.plugin_manager.dispatcher.quarantine_agent(name)
                    self._quarantined.add(name)
                except AttributeError:
                    pass

    def _quarantine_security_findings(self, findings: list[dict]) -> None:
        for finding in findings:
            path = Path(finding.get("path", ""))
            if path.parent.name == "agents" and path.stem not in self._quarantined:
                try:
                    self.plugin_manager.dispatcher.quarantine_agent(path.stem)
                    self._quarantined.add(path.stem)
                except AttributeError:
                    pass

    def security_scan(self) -> list[dict]:
        findings = []
        risky_modules = {"subprocess", "socket", "ctypes", "winreg"}
        risky_calls = {"eval", "exec", "compile", "system", "Popen"}
        for directory in (self.backend_dir / "mytools", self.backend_dir / "agents"):
            if not directory.exists():
                continue
            for path in directory.glob("*.py"):
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if alias.name.split(".")[0] in risky_modules:
                                    findings.append({"path": str(path), "line": node.lineno, "kind": "risky_import", "value": alias.name})
                        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in risky_modules:
                            findings.append({"path": str(path), "line": node.lineno, "kind": "risky_import", "value": node.module})
                        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in risky_calls:
                            findings.append({"path": str(path), "line": node.lineno, "kind": "risky_call", "value": node.func.id})
                except (OSError, SyntaxError) as error:
                    findings.append({"path": str(path), "kind": "scan_error", "value": str(error)})
        return findings[:100]

    def _score_plugins(self, entries: list[dict]) -> None:
        plugin_names = {(item["kind"], item["name"]) for item in self.plugin_manager.list_plugins()}
        for kind, name in plugin_names:
            relevant = [entry for entry in entries if entry.get("name") == name]
            for entry in relevant:
                if entry.get("scored"):
                    continue
                if entry.get("status") in {"done", "completed"}:
                    try:
                        self.plugin_manager.score(kind, name, True)
                    except ValueError:
                        pass
                    self.ledger.mark_scored(entry["id"])
                elif entry.get("status") == "failed":
                    try:
                        self.plugin_manager.score(kind, name, False)
                    except ValueError:
                        pass
                    self.ledger.mark_scored(entry["id"])

    def _load_proposals(self) -> list[dict]:
        if not self.proposals_path.exists():
            return []
        try:
            data = json.loads(self.proposals_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save_proposals(self, proposals: list[dict]) -> None:
        self.proposals_path.write_text(json.dumps(proposals[-200:], indent=2, ensure_ascii=False), encoding="utf-8")
