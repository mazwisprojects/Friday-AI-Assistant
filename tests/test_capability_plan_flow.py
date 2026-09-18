"""Handler contract tests without importing hardware or starting server services."""
import ast
import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from capability_plan_drafts import PlanDraftService, build_prompt, parse_draft
from capability_plan_store import CapabilityPlanStore


PLAN = {"title": "Sample", "goal": "Summarize sample data", "kind": "tool",
        "steps": ["Parse sample"], "risks": ["Incomplete input"],
        "advantages": ["Repeatable report"], "permissions": [],
        "tests": ["Reject invalid input"], "first_run": "Synthetic data", "rollback": "Remove candidate"}
BACKEND = Path(__file__).resolve().parents[1] / "backend"


class FakeSocket:
    def __init__(self):
        self.events = []

    def event(self, function):
        return function

    async def emit(self, event, data, room):
        self.events.append((event, data, room))


def handlers(tmp_path, generate):
    tree = ast.parse((BACKEND / "server.py").read_text(encoding="utf-8"))
    names = {"_plan_service", "_draft_capability_for_sid", "capability_plan_request", "capability_plan_decision"}
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    assert len(nodes) == len(names)
    socket = FakeSocket()
    store = CapabilityPlanStore(tmp_path)
    ns = {"asyncio": asyncio, "sio": socket, "logger": logging.getLogger(__name__),
          "SETTINGS": {}, "authenticator": None,
          "client_sessions": {"one": {"plan_owner": "owner-a"}, "two": {"plan_owner": "owner-b"}},
          "_plan_draft_service": PlanDraftService(store, generate)}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(BACKEND / "server.py"), "exec"), ns)
    return ns, socket, store


def test_socket_draft_edit_approve_and_cancel(tmp_path):
    prompts = []
    def generate(prompt):
        prompts.append(prompt)
        return SimpleNamespace(ok=True, text=json.dumps({**PLAN, "goal": f"Revision {len(prompts)}"}))
    ns, socket, store = handlers(tmp_path, generate)
    async def flow():
        first = await ns["capability_plan_request"]("one", {"request": "Create sample report"})
        assert first["ok"]
        record = first["record"]
        assert store.get(record["id"])["status"] == "pending"
        decision = {"plan_id": record["id"], "version": 1, "action": "approve", "content_hash": record["content_hash"]}
        assert not (await ns["capability_plan_decision"]("two", decision))["ok"]
        assert (await ns["capability_plan_decision"]("one", decision))["record"]["status"] == "approved"
        edited = await ns["capability_plan_request"]("one", {"request": "Add another sample", "plan_id": record["id"], "version": 1})
        assert edited["record"]["version"] == 2
        assert edited["record"]["approval"] is None
        assert "reassess ALL" in prompts[1]
        assert not (await ns["capability_plan_decision"]("one", decision))["ok"]
        result = await ns["capability_plan_decision"]("one", {"plan_id": record["id"], "version": 2, "action": "cancel"})
        assert result["record"]["status"] == "cancelled"
        assert all(event[2] == "one" for event in socket.events)
        assert not result["record"]["execution_available"]
    asyncio.run(flow())


def test_socket_auth_and_provider_failure(tmp_path):
    ns, socket, store = handlers(tmp_path, lambda _: SimpleNamespace(ok=False, text=""))
    assert not asyncio.run(ns["capability_plan_request"]("unknown", {"request": "sample"}))["ok"]
    assert not asyncio.run(ns["capability_plan_request"]("one", {"request": "sample"}))["ok"]
    assert not socket.events
    assert not list(tmp_path.iterdir())


def test_prompt_braces_and_strict_parse():
    assert '"title"' in build_prompt("Create {sample}")
    assert "Create {sample}" in build_prompt("Create {sample}")
    assert parse_draft("```json\n" + json.dumps(PLAN) + "\n```") == PLAN
    with pytest.raises(ValueError):
        parse_draft("Untrusted commentary " + json.dumps(PLAN))


def test_actual_live_build_precondition_blocks_direct_builds():
    tree = ast.parse((BACKEND / "friday.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AudioLoop")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "check_tool_preconditions")
    ns = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(BACKEND / "friday.py"), "exec"), ns)
    for name in ("build_agent", "build_custom_tool", "build_hardware_tool"):
        assert "plan_capability" in ns[method.name](SimpleNamespace(authenticated=True), name, {})


@pytest.mark.parametrize("token,provided,paired,peer,expected", [
    ("secret", "secret", False, "203.0.113.1", "server_token_owner"),
    ("secret", "wrong", False, "127.0.0.1", None),
    ("secret", "", True, "203.0.113.1", "device:"),
    ("", "", False, "203.0.113.1", None),
    ("", "", False, "127.0.0.1", "local-session:one"),
])
def test_actual_connection_owner_assignment(token, provided, paired, peer, expected):
    import hmac
    tree = ast.parse((BACKEND / "server.py").read_text(encoding="utf-8"))
    connect = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "connect")
    start = next(i for i, n in enumerate(connect.body) if isinstance(n, ast.Import) and n.names[0].name == "hashlib")
    nodes = connect.body[start:start + 2]
    ns = {"SERVER_TOKEN": token, "provided_token": provided, "device_allowed": paired,
          "device_token": "verified-device-token", "hmac": hmac, "sid": "one",
          "client_sessions": {"one": {"device_id": "spoofed-other-device"}},
          "environ": {"asgi.scope": {"client": (peer, 12345)}}}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(BACKEND / "server.py"), "exec"), ns)
    owner = ns["client_sessions"]["one"].get("plan_owner")
    assert owner is None if expected is None else owner.startswith(expected)

