"""Plan lifecycle regressions; writes stay inside temporary directories."""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from capability_plan_store import CapabilityPlanStore, PlanConflict


@pytest.fixture
def plan():
    return {"title": "Local report", "goal": "Summarize sample data", "kind": "tool",
            "steps": ["Parse sample"], "risks": ["Incomplete input"],
            "advantages": ["Repeatable summaries"], "permissions": [],
            "tests": ["Reject invalid input"], "first_run": "Synthetic data",
            "rollback": "Remove candidate"}


def test_persistence_and_approval_loop(tmp_path, plan):
    store = CapabilityPlanStore(tmp_path)
    original = store.create(plan)
    assert original["status"] == "pending"
    assert CapabilityPlanStore(tmp_path).get(original["id"]) == original
    approved = store.transition(original["id"], 1, "approve", content_hash=original["content_hash"])
    assert approved["status"] == "approved"
    assert approved["execution_available"] is False
    assert store.transition(original["id"], 1, "approve", content_hash=original["content_hash"]) == approved
    revised = {**plan, "goal": "Summarize two samples"}
    edited = store.transition(original["id"], 1, "edit", plan=revised)
    assert edited["version"] == 2
    assert edited["status"] == "pending"
    assert edited["approval"] is None
    assert edited["history"][0]["approval"] == approved["approval"]
    assert edited["history"][0]["plan"] == plan
    with pytest.raises(PlanConflict, match="latest version"):
        store.transition(original["id"], 1, "approve", content_hash=original["content_hash"])
    with pytest.raises(PlanConflict, match="content hash"):
        store.transition(original["id"], 2, "approve", content_hash=original["content_hash"])
    store.transition(original["id"], 2, "cancel")
    with pytest.raises(PlanConflict, match="Cancelled"):
        store.transition(original["id"], 2, "edit", plan=plan)


def test_concurrent_edits_reject_stale_revision(tmp_path, plan):
    store = CapabilityPlanStore(tmp_path)
    record = store.create(plan)
    def edit(_):
        try:
            store.transition(record["id"], 1, "edit", plan=plan)
            return "saved"
        except PlanConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, range(2))) == ["conflict", "saved"]
    assert store.get(record["id"])["version"] == 2


def test_atomic_write_failure_preserves_previous_plan(tmp_path, plan, monkeypatch):
    store = CapabilityPlanStore(tmp_path)
    original = store.create(plan)
    def fail(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr(type(tmp_path), "replace", fail)
    with pytest.raises(OSError, match="disk unavailable"):
        store.transition(original["id"], 1, "edit", plan=plan)
    assert store.get(original["id"]) == original
    assert not list(tmp_path.glob("*.tmp"))


def test_corrupt_content_fails_closed(tmp_path, plan):
    store = CapabilityPlanStore(tmp_path)
    record = store.create(plan)
    record["plan"]["goal"] = "Unexpected change"
    (tmp_path / f"{record['id']}.json").write_text(json.dumps(record))
    with pytest.raises(PlanConflict, match="hash"):
        store.get(record["id"])


@pytest.mark.parametrize("field,value", [("tests", []), ("kind", "shell"), ("risks", "none"), ("goal", "")])
def test_invalid_plan_not_saved(tmp_path, plan, field, value):
    plan[field] = value
    with pytest.raises(ValueError):
        CapabilityPlanStore(tmp_path).create(plan)
    assert not list(tmp_path.iterdir())


def test_path_traversal_rejected(tmp_path):
    with pytest.raises(ValueError, match="Invalid plan ID"):
        CapabilityPlanStore(tmp_path).get("../settings")


def test_http_review_flow_when_dependencies_available(tmp_path, plan):
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from capability_plan_api import create_plan_router

    app = fastapi.FastAPI()
    store = CapabilityPlanStore(tmp_path)
    token = ["test-token"]
    app.include_router(create_plan_router(store, lambda: token[0]))
    with TestClient(app) as client:
        assert client.post("/api/capability-plans", json=plan).status_code == 401
        headers = {"Authorization": "Bearer test-token"}
        response = client.post("/api/capability-plans", json=plan, headers=headers)
        assert response.status_code == 201
        record = response.json()
        url = f"/api/capability-plans/{record['id']}"
        assert client.get(url, headers=headers).json() == store.get(record["id"])
        response = client.post(url + "/approve", headers=headers,
                               json={"version": 1, "content_hash": "wrong"})
        assert response.status_code == 409
        response = client.post(url + "/approve", headers=headers,
                               json={"version": 1, "content_hash": record["content_hash"]})
        assert response.json()["status"] == "approved"
        assert response.json()["execution_available"] is False
        response = client.post(url + "/edit", headers=headers, json={"version": 1, "plan": plan})
        assert response.json()["approval"] is None
        assert response.json()["version"] == 2
        assert client.post(url + "/implement", headers=headers, json={"version": 2}).status_code == 422
        token[0] = ""
        assert client.get(url, headers=headers).status_code == 503
