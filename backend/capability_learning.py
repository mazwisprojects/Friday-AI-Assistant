"""Runtime learning loop for governed Friday capabilities."""

from __future__ import annotations

import ast
import logging
import json
import time
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)


class CapabilityLearning:
    def __init__(self, backend_dir: str, ledger, plugin_manager):
        self.backend_dir = Path(backend_dir)
        self.ledger = ledger
        self.plugin_manager = plugin_manager
        self.proposals_path = self.backend_dir / "capability_proposals.json"
        self.accepted_path = self.backend_dir / "accepted_findings.json"
        self._accepted = self._load_accepted()
        self._quarantined = set()

    def inspect(self) -> dict:
        entries = self.ledger.list(500)
        proposals = self._load_proposals()
        usage = Counter(entry.get("name") for entry in entries if entry.get("name"))
        failures = Counter(entry.get("name") for entry in entries if entry.get("status") == "failed" and entry.get("name"))
        known_names = {item.get("name") for item in proposals}
        new_proposals = []
        for name, count in usage.items():
            if count < 3 or name in known_names:
                continue
            priority = "high" if count >= 10 else "normal"
            proposal = {"name": name, "kind": "workflow", "reason": f"Capability used {count} times; consider a governed reusable workflow.", "usage_count": count, "priority": priority, "status": "pending_review"}
            proposals.append(proposal)
            known_names.add(name)
            new_proposals.append(proposal)
        if new_proposals:
            self._save_proposals(proposals)
        expired = self.plugin_manager.expire()
        security = self.security_scan()
        self._score_plugins(entries)
        self._quarantine_repeated_failures(failures)
        self._quarantine_security_findings(security)
        # Surface every stored pending proposal, not only patterns discovered in
        # this cycle: otherwise anything persisted by an earlier run stays
        # invisible here and the autonomy pipeline can never assign it an id,
        # leaving the approval queue permanently un-approvable.
        pending = [item for item in proposals if item.get("status") == "pending_review"]
        return {"usage": dict(usage), "failures": dict(failures), "proposals": pending, "expired": expired, "security": security}

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
        accepted = self._accepted
        return [
            finding for finding in findings
            if f"{finding.get('path')}:{finding.get('value')}" not in accepted
        ][:100]

    def accept_finding(self, finding_path: str, finding_value: str) -> None:
        """Record a human review decision so this finding is no longer reported.

        This is the governed escape hatch: a real person reviewed the risky
        import/call and accepted the risk, so the pipeline can move forward.
        The decision is persisted so the finding stays resolved across restarts.
        """
        if not finding_path or not finding_value:
            raise ValueError("Security finding path and value are required")
        self._accepted.add(f"{finding_path}:{finding_value}")
        self._save_accepted()

    def _load_accepted(self) -> set[str]:
        if not self.accepted_path.exists():
            return set()
        try:
            data = json.loads(self.accepted_path.read_text(encoding="utf-8"))
            if isinstance(data, list) and all(isinstance(item, str) for item in data):
                return set(data)
        except (OSError, json.JSONDecodeError):
            pass
        return set()

    def _save_accepted(self) -> None:
        self.accepted_path.write_text(
            json.dumps(sorted(self._accepted), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def mark_pattern_status(self, name: str, status: str) -> None:
        """Record where a learned pattern stands in the governance lifecycle.

        Once the autonomy pipeline has minted a proposal for a pattern
        ("proposed") or a human has approved it ("approved"), the pattern must
        stop being surfaced by inspect(): the pipeline, not the raw learning
        store, is the source of truth for what still awaits review. Without
        this sync the supervisor keeps re-raising already-governed patterns as
        fresh approval requests forever.
        """
        if not name or not status:
            raise ValueError("Pattern name and status are required")
        proposals = self._load_proposals()
        updated = False
        for item in proposals:
            if item.get("name") == name and item.get("status") != status:
                item["status"] = status
                item["status_updated_at"] = time.time()
                updated = True
        if updated:
            self._save_proposals(proposals)

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
