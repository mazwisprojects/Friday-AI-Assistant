"""One-shot: materialize stored capability patterns into real, approvable proposals.

Reads the same source the runtime uses (capability_proposals.json via the
learning layer's contract) and drives AutonomyPipeline.run_cycle() so every
pending pattern is minted with a UUID and persisted to autonomy_pipeline.json.
Run:  python materialize_proposals.py
"""
import json
import os
import sys

sys.path.insert(0, "backend")
from autonomy_pipeline import AutonomyPipeline  # noqa: E402

BACKEND = os.path.abspath("backend")
PROPOSALS_STORE = os.path.join(BACKEND, "capability_proposals.json")


class ShimLearning:
    """Supplies exactly what CapabilityLearning.inspect() returns for proposals."""

    def inspect(self):
        with open(PROPOSALS_STORE, encoding="utf-8") as fh:
            data = json.load(fh)
        pending = [
            item for item in data
            if item.get("status", "pending_review") == "pending_review"
        ]
        return {
            "usage": {}, "failures": {}, "proposals": pending,
            "expired": [], "security": [],
        }


class ShimPlugins:
    def list_plugins(self):
        return []


def main():
    pipeline = AutonomyPipeline(BACKEND, ShimLearning(), ShimPlugins(), None)
    result = pipeline.run_cycle()
    proposals = result["proposals"]
    print(f"MATERIALIZED {len(proposals)} pending proposal(s):")
    for proposal in proposals:
        print(f"  {proposal['id']}  {proposal['name']}  [{proposal['status']}]")
    print(f"Stored in: {pipeline.path}")


if __name__ == "__main__":
    main()
