"""One-time sync: learning-store patterns whose pipeline proposals are approved
stop being reported as pending review, plus a live verification that the
supervisor's data source (learning.inspect()) is now quiet."""
import json
import time
from pathlib import Path

BACKEND = Path(__file__).parent / "backend"
pipeline_path = BACKEND / "autonomy_pipeline.json"
proposals_path = BACKEND / "capability_proposals.json"

approved_names = set()
if pipeline_path.exists():
    for item in json.loads(pipeline_path.read_text(encoding="utf-8")):
        if item.get("status") == "approved" and item.get("name"):
            approved_names.add(item["name"])

patterns = json.loads(proposals_path.read_text(encoding="utf-8")) if proposals_path.exists() else []
changed = 0
for pattern in patterns:
    if pattern.get("name") in approved_names and pattern.get("status") != "approved":
        pattern["status"] = "approved"
        pattern["status_updated_at"] = time.time()
        changed += 1

proposals_path.write_text(json.dumps(patterns, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"approved pipeline names: {sorted(approved_names)}")
print(f"patterns updated: {changed} / {len(patterns)}")

# Live verification of the exact source the supervisor polls every 30s.
from capability_learning import CapabilityLearning
from execution_ledger import ExecutionLedger


class ReadOnlyPlugins:
    def list_plugins(self):
        return []

    def expire(self):
        return []


learning = CapabilityLearning(str(BACKEND), ExecutionLedger(str(BACKEND)), ReadOnlyPlugins())
result = learning.inspect()
print(f"inspect().proposals now: {result['proposals']}")
print(f"inspect().security now: {result['security']}")
print("SUPERVISOR_SOURCE_QUIET" if not result["proposals"] and not result["security"] else "STILL_NOISY")
