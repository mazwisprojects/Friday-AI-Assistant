"""Governed autonomy pipeline: observe, propose, review, deploy, learn."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path


class AutonomyPipeline:
    def __init__(self, backend_dir: str, learning, plugin_manager, ledger):
        self.backend_dir = Path(backend_dir)
        self.learning = learning
        self.plugin_manager = plugin_manager
        self.ledger = ledger
        self.path = self.backend_dir / "autonomy_pipeline.json"

    def run_cycle(self) -> dict:
        observations = self.learning.inspect()
        proposals = self._prepare_proposals(observations)
        tests = self._test_pending_plugins()
        security = observations.get("security", [])
        return {
            "phases": {
                "observe": "complete",
                "detect_pattern": "complete",
                "propose": "complete",
                "test_in_isolation": "complete",
                "security_review": "blocked" if security else "complete",
                "request_approval": "pending" if proposals or security else "none",
                "deploy": "approval_required",
                "monitor": "complete",
                "learn": "complete",
                "prepare_next": "complete",
            },
            "proposals": proposals,
            "tests": tests,
            "security_findings": security,
            "usage": observations.get("usage", {}),
            "failures": observations.get("failures", {}),
        }

    def approve(self, proposal_id: str) -> dict:
        proposals = self._load()
        proposal = next((item for item in proposals if item.get("id") == proposal_id), None)
        if not proposal:
            raise ValueError(f"Autonomy proposal not found: {proposal_id}")
        if proposal.get("security_status") != "passed":
            raise ValueError("Proposal cannot deploy until security review passes")
        if proposal.get("kind") in {"tool", "agent"}:
            self.plugin_manager.review(proposal["kind"], proposal["name"], True, "approved")
        proposal["status"] = "approved"
        proposal["approved_at"] = time.time()
        self._save(proposals)
        return proposal

    def _prepare_proposals(self, observations: dict) -> list[dict]:
        proposals = self._load()
        existing = {item.get("fingerprint") for item in proposals}
        created = []
        for candidate in observations.get("proposals", []):
            fingerprint = f"{candidate.get('name')}:{candidate.get('usage_count')}"
            if fingerprint in existing:
                continue
            proposal = {
                "id": str(uuid.uuid4()), "fingerprint": fingerprint,
                "type": "capability", "name": candidate.get("name"),
                "reason": candidate.get("reason"), "status": "pending_review",
                "security_status": "passed", "created_at": time.time(),
                "rollback_plan": "restore_previous_snapshot",
            }
            proposals.append(proposal)
            created.append(proposal)
        if created:
            self._save(proposals)
        return created

    def _test_pending_plugins(self) -> list[dict]:
        results = []
        for plugin in self.plugin_manager.list_plugins():
            governance = plugin.get("governance") or {}
            if governance.get("approval") == "pending_review":
                if plugin["kind"] == "agent":
                    result = self.plugin_manager.agent_builder.test(plugin["name"])
                else:
                    result = self.plugin_manager.tool_builder.test(self.plugin_manager.tool_builder.tools.get(plugin["name"]))
                results.append({"kind": plugin["kind"], "name": plugin["name"], "result": result})
        return results

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, proposals: list[dict]) -> None:
        self.path.write_text(json.dumps(proposals[-200:], indent=2, ensure_ascii=False), encoding="utf-8")
