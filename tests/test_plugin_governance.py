from agent_builder import AgentBuilder
from actions.agent_dispatcher import AgentDispatcher
from plugin_governance import is_active
from plugin_manager import PluginManager
from tool_builder import ToolBuilder


def test_generated_agent_requires_review_then_activates(tmp_path):
    tools = ToolBuilder(str(tmp_path))
    agents = AgentBuilder(str(tmp_path))
    dispatcher = AgentDispatcher()
    manager = PluginManager(str(tmp_path), tools, agents, dispatcher)
    code = "def run(goal, repo_path, log, cancel_event):\n    return {'ok': True}\n"

    built = agents.build("governed_agent", "Governed agent", code)
    assert built["test"]["smoke_test"]
    assert not is_active(built["agent"])

    proposal = manager.propose("agent", "governed_agent", permissions=["network:read"], dependencies=["requests"])
    assert proposal["status"] == "pending_review"
    reviewed = manager.review("agent", "governed_agent", True)
    assert reviewed["approved"]
    assert dispatcher.registered_agents() == ["governed_agent"]

    score = manager.score("agent", "governed_agent", True)
    assert score["success_rate"] == 1.0


def test_resource_limits_are_bounded(tmp_path):
    builder = AgentBuilder(str(tmp_path))
    code = "def run(goal, repo_path, log, cancel_event):\n    return {'ok': True}\n"

    try:
        builder.build("unsafe_agent", "Unsafe agent", code, governance={"resource_limits": {"timeout_seconds": 99999}})
    except ValueError as error:
        assert "resource limit" in str(error).lower()
    else:
        raise AssertionError("unsafe resource limits were accepted")


def test_unapproved_tool_cannot_execute(tmp_path):
    builder = ToolBuilder(str(tmp_path))
    result = builder.build("governed_tool", "Governed tool", "python_module", config={"code": "def run(arguments):\n    return {'ok': True}\n"})
    assert result["test"]["smoke_test"]
    try:
        builder.execute("governed_tool", {})
    except PermissionError:
        pass
    else:
        raise AssertionError("unapproved tool executed")
