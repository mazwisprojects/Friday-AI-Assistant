"""Regression coverage for agent replacement and validation failures."""
import copy
import threading

import pytest

from agent_builder import AgentBuilder


GOOD = "def run(goal, repo_path, log, cancel_event):\n    return {'ok': True, 'value': 42}\n"


@pytest.mark.parametrize("bad", [
    "def run(goal, repo_path, log, cancel_event):\n    raise ValueError('broken')\n",
    "def run(goal, repo_path, log, cancel_event):\n    return {'ok': False}\n",
])
def test_failed_replacement_preserves_working_agent(tmp_path, bad):
    builder = AgentBuilder(str(tmp_path))
    builder.build("stable", "Working", GOOD)
    path = tmp_path / "agents" / "stable.py"
    original = path.read_bytes()
    registry = builder.registry_path.read_bytes()
    manifest = copy.deepcopy(builder.agents)
    with pytest.raises(ValueError, match="smoke test failed"):
        builder.build("stable", "Replacement", bad)
    assert path.read_bytes() == original
    assert builder.registry_path.read_bytes() == registry
    assert builder.agents == manifest
    assert builder.load_callable("stable")("test", str(tmp_path), lambda _: None, threading.Event())["value"] == 42


def test_failed_new_agent_leaves_no_registration(tmp_path):
    builder = AgentBuilder(str(tmp_path))
    with pytest.raises(ValueError, match="smoke test failed"):
        builder.build("broken", "Broken", "def run(goal, repo_path, log, cancel_event):\n    raise ValueError('broken')\n")
    assert builder.agents == {}
    assert not (tmp_path / "agents" / "broken.py").exists()
    assert not builder.registry_path.exists()


def test_candidate_is_staged_before_registration(tmp_path, monkeypatch):
    builder = AgentBuilder(str(tmp_path))
    observed = []

    def reject(name, path, timeout=10):
        observed.append(path)
        assert name not in builder.agents
        assert not (tmp_path / "agents" / f"{name}.py").exists()
        assert path.is_file()
        return {"ok": False, "error": "candidate rejected"}

    monkeypatch.setattr(builder, "_test_path", reject)
    with pytest.raises(ValueError, match="candidate rejected"):
        builder.build("candidate", "Staging probe", GOOD)
    assert len(observed) == 1
    assert not observed[0].exists()
    assert not builder.registry_path.exists()


def test_child_process_timeout_is_failure(tmp_path):
    builder = AgentBuilder(str(tmp_path))
    candidate = tmp_path / "slow.py"
    candidate.write_text(
        "import time\ndef run(goal, repo_path, log, cancel_event):\n"
        "    time.sleep(30)\n    return {'ok': True}\n", encoding="utf-8")
    result = builder._test_path("slow", candidate, timeout=0.5)
    assert result["ok"] is False
    assert "timed out" in result["error"]
    assert not builder.agents


def test_successful_smoke_test_is_process_isolated(tmp_path):
    result = AgentBuilder(str(tmp_path)).build("sample", "Sample", GOOD)
    assert result["test"]["ok"] is True
    assert result["test"]["process_isolated"] is True

