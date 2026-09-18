"""Exercise the real build/execute path without external services."""

import json

from tool_builder import ToolBuilder


def test_build_and_execute_returns_run_result(tmp_path):
    builder = ToolBuilder(str(tmp_path))
    result = builder.build(
        "echo_probe",
        "Return the supplied value",
        "def run(arguments):\n    return {'value': arguments.get('value')}\n",
        governance={"approval": "approved", "security_review": "approved"},
    )
    assert result["ok"], result
    assert result["test"]["ok"], result

    execution = builder.execute("echo_probe", {"value": "probe passed"})
    assert execution["ok"], execution
    assert execution["stdout"].strip(), execution
    assert json.loads(execution["stdout"]) == {"value": "probe passed"}


def test_failed_build_is_not_registered(tmp_path):
    builder = ToolBuilder(str(tmp_path))
    result = builder.build("broken", "Broken", "def run(args):\n    raise ValueError('broken')\n")
    assert not result["ok"]
    assert not result["registered"]
    assert "broken" not in builder.tools
    assert not (tmp_path / "mytools" / "broken.py").exists()


def test_failed_replacement_preserves_previous_tool(tmp_path):
    builder = ToolBuilder(str(tmp_path))
    assert builder.build("stable", "Stable", "def run(args):\n    return 42\n")["ok"]
    path = tmp_path / "mytools" / "stable.py"
    before = path.read_bytes()
    manifest = dict(builder.tools["stable"])
    result = builder.build("stable", "Bad replacement", "def run(args):\n    raise ValueError('broken')\n")
    assert not result["ok"]
    assert path.read_bytes() == before
    assert builder.tools["stable"] == manifest


def test_async_run_is_awaited(tmp_path):
    builder = ToolBuilder(str(tmp_path))
    result = builder.build(
        "async_echo", "Async", "async def run(args):\n    return args\n",
        governance={"approval": "approved", "security_review": "approved"},
    )
    assert result["ok"], result
    execution = builder.execute("async_echo", {"value": 7})
    assert execution["ok"]
    assert json.loads(execution["stdout"]) == {"value": 7}


def test_discovery_preserves_disabled_state_and_metadata(tmp_path):
    builder = ToolBuilder(str(tmp_path))
    assert builder.build("disabled", "Description", "return 1")["ok"]
    builder.tools["disabled"]["enabled"] = False
    before = dict(builder.tools["disabled"])
    builder.discover_modules()
    assert builder.tools["disabled"] == before


def test_explicit_failure_result_is_not_success(tmp_path):
    builder = ToolBuilder(str(tmp_path))
    result = builder.build("failure", "Failure", "return {'ok': False, 'error': 'nope'}")
    assert not result["ok"]

