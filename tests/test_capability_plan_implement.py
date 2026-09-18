"""Approval-gated implementation stage: real builds, real refusals."""
import asyncio
import ast
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_builder import AgentBuilder
from capability_plan_implement import CapabilityImplementer, build_code_prompt, parse_candidate
from capability_plan_store import CapabilityPlanStore, PlanConflict
from plugin_governance import is_active
from tool_builder import ToolBuilder

BACKEND = Path(__file__).resolve().parents[1] / "backend"

PLAN = {"title": "Sample", "goal": "Summarize sample data", "kind": "tool",
        "steps": ["Parse sample"], "risks": ["Incomplete input"],
        "advantages": ["Repeatable report"], "permissions": [],
        "tests": ["Reject invalid input"], "first_run": "Synthetic data", "rollback": "Remove candidate"}

TOOL_CODE = "def run(arguments):\n    return {'ok': True, 'echo': arguments.get('value')}\n"


def scripted(*replies):
    """A generate() that replays scripted provider responses."""
    queue = list(replies)

    def generate(_prompt):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return generate


def candidate(name="sample_tool", code=TOOL_CODE):
    return SimpleNamespace(ok=True, text=json.dumps({"name": name, "description": "Sample", "code": code}))


def implemented(tmp_path, generate, kind="tool", **builders):
    store = CapabilityPlanStore(tmp_path / "plans")
    tools = builders.get("tool_builder", ToolBuilder(str(tmp_path / "backend")))
    agents = builders.get("agent_builder", AgentBuilder(str(tmp_path / "backend")))
    record = store.create({**PLAN, "kind": kind}, owner="device:one")
    record = store.transition(record["id"], 1, "approve", content_hash=record["content_hash"])
    service = CapabilityImplementer(store, generate, tools, agents)
    return service, store, tools, agents, record


def test_approved_plan_is_built_verified_and_left_live(tmp_path):
    service, store, tools, _, record = implemented(tmp_path, scripted(candidate()))
    result = service.implement(record["id"], "device:one", 1, record["content_hash"])

    assert result["ok"], result
    assert result["status"] == "implemented"
    stored = store.get(record["id"])
    assert stored["status"] == "implemented"
    assert stored["execution_available"] is True
    assert stored["implementation"]["verified"] is True
    assert stored["implementation"]["version"] == 1
    assert stored["implementation"]["approval"]["content_hash"] == record["content_hash"]

    # Approval is the security review, so the artifact must be live, not merely saved.
    assert is_active(tools.tools["sample_tool"])
    assert (tmp_path / "backend" / "mytools" / "sample_tool.py").exists()
    assert result["implementation"]["first_run"]["ok"] is True
    assert result["implementation"]["first_run"]["returncode"] == 0
    assert json.loads(tools.execute("sample_tool", {"value": 5})["stdout"]) == {"ok": True, "echo": 5}


def test_agent_plan_is_built_and_smoke_tested(tmp_path):
    code = "def run(goal, repo_path, log, cancel_event):\n    log('smoke')\n    return {'ok': True, 'goal': goal}\n"
    service, store, _, agents, record = implemented(
        tmp_path, scripted(candidate("probe_agent", code)), kind="agent")
    result = service.implement(record["id"], "device:one", 1)

    assert result["ok"], result
    assert store.get(record["id"])["status"] == "implemented"
    assert is_active(agents.agents["probe_agent"])
    assert callable(agents.load_callable("probe_agent"))
    assert result["implementation"]["first_run"] is None
    assert result["implementation"]["smoke_test"]["process_isolated"] is True


def test_failed_build_never_claims_success(tmp_path):
    broken = "def run(arguments):\n    raise ValueError('broken on purpose')\n"
    service, store, tools, _, record = implemented(tmp_path, scripted(candidate(code=broken)))
    result = service.implement(record["id"], "device:one", 1)

    assert not result["ok"]
    assert result["status"] == "failed"
    stored = store.get(record["id"])
    assert stored["status"] == "implement_failed"
    assert stored["execution_available"] is False
    assert stored["implementation"]["verified"] is False
    assert "sample_tool" not in tools.tools
    assert not (tmp_path / "backend" / "mytools" / "sample_tool.py").exists()


def test_unusable_code_output_is_recorded_not_ignored(tmp_path):
    service, store, tools, _, record = implemented(
        tmp_path, scripted(SimpleNamespace(ok=True, text="I cannot help with that")))
    result = service.implement(record["id"], "device:one", 1)

    assert not result["ok"]
    assert result["status"] == "failed"
    assert store.get(record["id"])["implementation"]["stage"] == "code_generation"
    assert not tools.tools


@pytest.mark.parametrize("reply", [SimpleNamespace(ok=False, text=""), RuntimeError("quota exceeded")])
def test_provider_failure_leaves_the_plan_untouched(tmp_path, reply):
    service, store, tools, _, record = implemented(tmp_path, scripted(reply))
    with pytest.raises(RuntimeError, match="nothing was built|Build provider failed"):
        service.implement(record["id"], "device:one", 1)

    stored = store.get(record["id"])
    assert stored["status"] == "approved"
    assert stored["implementation"] is None
    assert not tools.tools


@pytest.mark.parametrize("kind", ["workflow", "app"])
def test_unsupported_kinds_are_refused_without_consulting_the_model(tmp_path, kind):
    def refuse(_prompt):
        raise AssertionError("the model must not be asked to build an unsupported kind")

    service, store, _, _, record = implemented(tmp_path, refuse, kind=kind)
    result = service.implement(record["id"], "device:one", 1)

    assert result["status"] == "unsupported"
    assert "no end-to-end build path" in result["error"]
    stored = store.get(record["id"])
    assert stored["status"] == "approved"
    assert stored["implementation"] is None


def test_missing_builder_is_reported_not_faked(tmp_path):
    service, store, _, _, record = implemented(tmp_path, scripted(candidate()), tool_builder=None)
    result = service.implement(record["id"], "device:one", 1)
    assert result["status"] == "unavailable"
    assert store.get(record["id"])["execution_available"] is False


def test_only_the_exact_approved_version_can_be_built(tmp_path):
    service, store, tools, _, record = implemented(tmp_path, scripted(candidate()))

    with pytest.raises(PlanConflict, match="latest version"):
        service.implement(record["id"], "device:one", 2)
    with pytest.raises(PermissionError, match="another authenticated session"):
        service.implement(record["id"], "device:two", 1)
    with pytest.raises(PlanConflict, match="content hash"):
        service.implement(record["id"], "device:one", 1, "wrong-hash")

    assert store.get(record["id"])["status"] == "approved"
    assert not tools.tools


def test_unapproved_plan_is_refused(tmp_path):
    store = CapabilityPlanStore(tmp_path / "plans")
    record = store.create(PLAN, owner="device:one")
    service = CapabilityImplementer(store, scripted(candidate()), ToolBuilder(str(tmp_path / "backend")), None)

    with pytest.raises(PlanConflict, match="Approve this exact plan version"):
        service.implement(record["id"], "device:one", 1)
    assert not list((tmp_path / "plans").glob("*.tmp"))


class ExpiringBuilder(ToolBuilder):
    """Simulates the user editing or cancelling while the build is running."""

    def __init__(self, backend_dir):
        self.mutate = None
        super().__init__(backend_dir)

    def build(self, *args, **kwargs):
        if self.mutate:
            self.mutate()
        return super().build(*args, **kwargs)


@pytest.mark.parametrize("action,expected", [("edit", "pending"), ("cancel", "cancelled")])
def test_approval_expiring_mid_build_rolls_the_artifact_back(tmp_path, action, expected):
    builder = ExpiringBuilder(str(tmp_path / "backend"))
    service, store, _, _, record = implemented(tmp_path, scripted(candidate()), tool_builder=builder)

    def mutate():
        builder.mutate = None
        if action == "edit":
            store.transition(record["id"], 1, "edit", plan={**PLAN, "goal": "Changed mid-build"})
        else:
            store.transition(record["id"], 1, "cancel")

    builder.mutate = mutate
    result = service.implement(record["id"], "device:one", 1)

    assert not result["ok"]
    assert result["status"] == "reverted"
    assert result["reverted"]["ok"] is True
    assert "sample_tool" not in builder.tools
    assert not (tmp_path / "backend" / "mytools" / "sample_tool.py").exists()
    stored = store.get(record["id"])
    assert stored["implementation"] is None
    assert stored["execution_available"] is False
    assert stored["status"] == expected


def test_rollback_restores_the_previous_working_tool(tmp_path):
    builder = ExpiringBuilder(str(tmp_path / "backend"))
    original = {"approval": "approved", "security_review": "approved"}
    assert builder.build("sample_tool", "Original", "def run(args):\n    return 'original'\n",
                         governance=original)["ok"]
    before = (tmp_path / "backend" / "mytools" / "sample_tool.py").read_bytes()

    service, store, _, _, record = implemented(tmp_path, scripted(candidate()), tool_builder=builder)

    def mutate():
        builder.mutate = None
        store.transition(record["id"], 1, "cancel")

    builder.mutate = mutate
    result = service.implement(record["id"], "device:one", 1)

    assert result["status"] == "reverted"
    assert (tmp_path / "backend" / "mytools" / "sample_tool.py").read_bytes() == before
    assert json.loads(builder.execute("sample_tool", {})["stdout"]) == "original"


FLAKY_CODE = (
    "from pathlib import Path\n"
    "def run(arguments):\n"
    "    marker = Path(__file__).with_suffix('.runs')\n"
    "    runs = int(marker.read_text()) if marker.exists() else 0\n"
    "    marker.write_text(str(runs + 1))\n"
    "    if runs:\n"
    "        raise RuntimeError('later run failed')\n"
    "    return {'ok': True}\n"
)


def test_registered_tool_that_fails_its_first_run_is_rolled_back(tmp_path):
    service, store, tools, _, record = implemented(tmp_path, scripted(candidate(code=FLAKY_CODE)))
    result = service.implement(record["id"], "device:one", 1)

    assert not result["ok"]
    assert result["status"] == "failed"
    assert result["implementation"]["stage"] == "first_run"
    assert result["implementation"]["smoke_test"]["ok"] is True  # staging passed; the live run did not
    assert result["reverted"]["ok"] is True
    assert "sample_tool" not in tools.tools
    assert not (tmp_path / "backend" / "mytools" / "sample_tool.py").exists()
    assert store.get(record["id"])["execution_available"] is False


def test_a_failed_build_can_be_retried_but_a_built_one_cannot(tmp_path):
    broken = "def run(arguments):\n    raise ValueError('first attempt')\n"
    service, store, tools, _, record = implemented(tmp_path, scripted(candidate(code=broken), candidate()))

    assert service.implement(record["id"], "device:one", 1)["status"] == "failed"
    assert store.get(record["id"])["status"] == "implement_failed"
    assert service.implement(record["id"], "device:one", 1)["ok"] is True
    assert store.get(record["id"])["execution_available"] is True

    with pytest.raises(PlanConflict, match="already implemented"):
        service.implement(record["id"], "device:one", 1)
    with pytest.raises(PlanConflict, match="already implemented"):
        store.transition(record["id"], 1, "approve", content_hash=record["content_hash"])
    # Cancelling would claim the live capability is gone; it is not, so refuse.
    with pytest.raises(PlanConflict, match="capability is live"):
        store.transition(record["id"], 1, "cancel")
    assert store.get(record["id"])["status"] == "implemented"
    assert store.get(record["id"])["execution_available"] is True
    assert is_active(tools.tools["sample_tool"])


def test_prompt_carries_the_plan_and_parse_is_strict():
    prompt = build_code_prompt(PLAN)
    assert "Summarize sample data" in prompt
    assert '"kind": "tool"' in prompt
    assert parse_candidate(candidate().text)["name"] == "sample_tool"
    assert parse_candidate("```json\n" + candidate().text + "\n```")["code"] == TOOL_CODE

    for bad in ("not json at all",
                json.dumps({"name": "x"}),
                json.dumps({"name": "9bad", "description": "d", "code": "x"}),
                json.dumps({"name": "ok", "description": "  ", "code": "x"}),
                json.dumps({"name": "ok", "description": "d", "code": "x" * 20001})):
        with pytest.raises(ValueError):
            parse_candidate(bad)


def test_store_refuses_an_implementation_without_approval(tmp_path):
    store = CapabilityPlanStore(tmp_path)
    record = store.create(PLAN, owner="device:one")

    with pytest.raises(PlanConflict, match="Only an approved plan"):
        store.record_implementation(record["id"], 1, {"status": "implemented", "verified": True})
    with pytest.raises(PlanConflict, match="Plan changed"):
        store.record_implementation(record["id"], 7, {"status": "implemented", "verified": True})
    assert store.get(record["id"])["execution_available"] is False


def test_store_only_lets_a_verified_artifact_flip_execution_available(tmp_path):
    store = CapabilityPlanStore(tmp_path)
    record = store.create(PLAN, owner="device:one")
    store.transition(record["id"], 1, "approve", content_hash=record["content_hash"])

    failed = store.record_implementation(record["id"], 1, {"status": "failed", "verified": False, "error": "boom"})
    assert failed["status"] == "implement_failed"
    assert failed["execution_available"] is False
    assert failed["implementation"]["error"] == "boom"

    # "implemented" without verification is a claim, not a result.
    claimed = store.record_implementation(record["id"], 1, {"status": "implemented"})
    assert claimed["status"] == "implement_failed"
    assert claimed["execution_available"] is False

    done = store.record_implementation(record["id"], 1, {"status": "implemented", "verified": True,
                                                         "artifact": "sample_tool"})
    assert done["status"] == "implemented"
    assert done["execution_available"] is True
    assert done["implementation"]["version"] == 1

    edited = store.transition(record["id"], 1, "edit", plan={**PLAN, "goal": "New revision"})
    assert edited["status"] == "pending"
    assert edited["execution_available"] is False


class FakeSocket:
    def __init__(self):
        self.events = []

    def event(self, function):
        return function

    async def emit(self, event, data, room):
        self.events.append((event, data, room))


def socket_handlers(tmp_path):
    from capability_plan_drafts import PlanDraftService

    tree = ast.parse((BACKEND / "server.py").read_text(encoding="utf-8"))
    names = {"_plan_service", "_implement_capability_for_sid", "capability_plan_implement",
             "_implementation_message", "_activate_capability"}
    nodes = [node for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    assert len(nodes) == len(names)
    socket = FakeSocket()
    store = CapabilityPlanStore(tmp_path / "plans")
    backend = tmp_path / "backend"
    ns = {"asyncio": asyncio, "sio": socket, "logger": logging.getLogger(__name__),
          "SETTINGS": {}, "authenticator": None, "capability_plan_store": store,
          "client_sessions": {"one": {"plan_owner": "device:one"}, "two": {"plan_owner": "device:two"}},
          "_plan_draft_service": PlanDraftService(store, lambda _: candidate()),
          "_capability_implementer": CapabilityImplementer(
              store, scripted(candidate()), ToolBuilder(str(backend)), AgentBuilder(str(backend)))}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(BACKEND / "server.py"), "exec"), ns)
    return ns, socket, store, backend


def test_socket_implement_builds_for_the_requesting_device_only(tmp_path):
    ns, socket, store, backend = socket_handlers(tmp_path)
    record = store.create(PLAN, owner="device:one")
    approved = store.transition(record["id"], 1, "approve", content_hash=record["content_hash"])
    payload = {"plan_id": approved["id"], "version": 1, "content_hash": approved["content_hash"]}

    async def flow():
        other = await ns["capability_plan_implement"]("two", payload)
        assert not other["ok"] and "another authenticated session" in other["error"]
        assert not socket.events
        unauthenticated = await ns["capability_plan_implement"]("three", payload)
        assert not unauthenticated["ok"]
        missing = await ns["capability_plan_implement"]("one", {**payload, "version": 4})
        assert not missing["ok"] and "latest version" in missing["error"]
        return await ns["capability_plan_implement"]("one", payload)

    result = asyncio.run(flow())

    assert result["ok"], result
    assert result["message"] == "sample_tool was built, verified and registered, and is live now."
    assert result["activation_error"] is None
    assert all(event[2] == "one" for event in socket.events)
    assert socket.events[-1][0] == "capability_plan"
    assert socket.events[-1][1]["status"] == "implemented"
    assert (backend / "mytools" / "sample_tool.py").exists()


def test_socket_implement_reports_a_failed_build_to_the_same_device(tmp_path):
    ns, socket, store, backend = socket_handlers(tmp_path)
    ns["_capability_implementer"].generate = scripted(
        candidate(code="def run(arguments):\n    raise SystemExit(3)\n"))
    record = store.create(PLAN, owner="device:one")
    approved = store.transition(record["id"], 1, "approve", content_hash=record["content_hash"])

    async def flow():
        return await ns["capability_plan_implement"]("one", {
            "plan_id": approved["id"], "version": 1, "content_hash": approved["content_hash"]})

    result = asyncio.run(flow())

    assert not result["ok"]
    assert result["status"] == "failed"
    assert "nothing new is live" in result["message"]
    assert all(event[2] == "one" for event in socket.events)
    # The card is pushed the honest failed record, not a stale "approved" one.
    assert socket.events[-1][1]["status"] == "implement_failed"
    assert socket.events[-1][1]["execution_available"] is False
    assert not (backend / "mytools" / "sample_tool.py").exists()


def test_socket_pushes_the_current_plan_when_a_build_is_discarded(tmp_path):
    ns, socket, store, backend = socket_handlers(tmp_path)
    record = store.create(PLAN, owner="device:one")
    approved = store.transition(record["id"], 1, "approve", content_hash=record["content_hash"])
    implementer = ns["_capability_implementer"]
    original_build = implementer.tool_builder.build

    def build_then_cancel(*args, **kwargs):
        store.transition(approved["id"], 1, "cancel")
        return original_build(*args, **kwargs)

    implementer.tool_builder.build = build_then_cancel

    async def flow():
        return await ns["capability_plan_implement"]("one", {
            "plan_id": approved["id"], "version": 1, "content_hash": approved["content_hash"]})

    result = asyncio.run(flow())

    assert result["status"] == "reverted"
    assert "rolled back" in result["error"]
    # The device is told the truth: the plan is cancelled and nothing is live.
    assert all(event[2] == "one" for event in socket.events)
    assert socket.events[-1][1]["status"] == "cancelled"
    assert socket.events[-1][1]["execution_available"] is False
    assert not (backend / "mytools" / "sample_tool.py").exists()