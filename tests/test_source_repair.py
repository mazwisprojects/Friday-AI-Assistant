"""Bounded source recovery, isolated from the running backend and installers."""
import copy
import json

import pytest

from actions import self_maintenance as sm
from tool_builder import ToolBuilder


@pytest.fixture
def repair_tool(tmp_path):
    builder = ToolBuilder(str(tmp_path))
    assert builder.build(
        "probe", "Repair probe", "def run(args):\n    return 42\n",
        governance={"approval": "approved", "security_review": "approved"},
    )["ok"]
    path = tmp_path / "mytools" / "probe.py"
    path.write_text("def run(args):\n    return missing_symbol\n", encoding="utf-8")
    error = builder._test_module("probe", path)["stderr"]
    return builder, path, error


def test_restore_validated_source_after_discovery(repair_tool):
    builder, path, error = repair_tool
    expected = builder.tools["probe"]["validated_code"]
    builder.discover_modules()
    builder = ToolBuilder(str(builder.backend_dir))
    result = builder.debug_and_fix("probe", error)
    assert result["ok"] and result["fixed"], result
    assert result["diagnostic"]["line"] == 2
    assert path.read_text(encoding="utf-8") == expected
    assert json.loads(builder.execute("probe")["stdout"]) == 42
    assert list(path.parent.glob("*.py")) == [path]


@pytest.mark.parametrize("case", ["candidate_fails", "disabled", "external_frame", "no_snapshot", "no_frame"])
def test_rejected_repair_preserves_source_and_registry(repair_tool, case):
    builder, path, error = repair_tool
    if case == "candidate_fails":
        builder.tools["probe"]["validated_code"] = "def run(args):\n    raise ValueError('still broken')\n"
    elif case == "disabled":
        builder.tools["probe"]["enabled"] = False
    elif case == "external_frame":
        error += '\n  File "outside.py", line 3, in helper\nValueError: external\n'
    elif case == "no_snapshot":
        del builder.tools["probe"]["validated_code"]
    else:
        error = "NameError: name 'os' is not defined"
    builder._save()
    original = path.read_bytes()
    registry = builder.registry_path.read_bytes()
    manifest = copy.deepcopy(builder.tools)
    result = builder.debug_and_fix("probe", error)
    assert not result["ok"] and not result["fixed"]
    assert path.read_bytes() == original
    assert builder.registry_path.read_bytes() == registry
    assert builder.tools == manifest
    assert list(path.parent.glob("*.py")) == [path]


def test_repair_tests_staged_file_before_replacement(repair_tool, monkeypatch):
    builder, path, error = repair_tool
    original = path.read_bytes()
    test_module = builder._test_module

    def check_staging(name, candidate):
        assert candidate != path
        assert path.read_bytes() == original
        return test_module(name, candidate)

    monkeypatch.setattr(builder, "_test_module", check_staging)
    assert builder.debug_and_fix("probe", error)["fixed"]


def test_prioritized_failures_and_corrupt_log(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "_BACKEND_DIR", tmp_path)
    monkeypatch.setattr(sm, "_FAILURE_LOG", tmp_path / "failures.json")
    sm._FAILURE_LOG.write_text("not json", encoding="utf-8")
    sm.record_tool_failure("low", "NameError: low")
    sm.record_tool_failure("high", "NameError: high")
    sm.record_tool_failure("high", "NameError: high")
    calls = []

    def repair(self, name, error):
        calls.append(name)
        return {"ok": name == "high", "fixed": name == "high"}

    monkeypatch.setattr(ToolBuilder, "debug_and_fix", repair)
    results = sm.attempt_source_fixes({"ok": True})
    assert calls == ["high", "low"]
    assert len(results) == 2
    data = sm._read_tool_failures()
    assert data["high"]["resolved"]
    assert not data["low"]["resolved"]
    assert data["high"]["count"] == 2
    sm.record_tool_failure("high", "x" * 7000 + "NameError: tail")
    assert not sm._read_tool_failures()["high"]["resolved"]
    assert sm._read_tool_failures()["high"]["last_error"].endswith("NameError: tail")


def test_self_heal_restores_tool_and_skips_installers(repair_tool, monkeypatch):
    builder, path, error = repair_tool
    monkeypatch.setattr(sm, "_BACKEND_DIR", builder.backend_dir)
    monkeypatch.setattr(sm, "_PROJECT_ROOT", builder.backend_dir)
    monkeypatch.setattr(sm, "_FAILURE_LOG", builder.backend_dir / "failures.json")
    sm.record_tool_failure("probe", error)
    calls = []

    def check():
        calls.append("check")
        return {"ok": True}

    def no_install():
        pytest.fail("Source recovery must not install dependencies")

    for name in ("compile_check_backend", "run_backend_tests", "build_frontend"):
        monkeypatch.setattr(sm, name, check)
    for name in ("install_python_dependencies", "install_frontend_dependencies"):
        monkeypatch.setattr(sm, name, no_install)
    report = sm.self_heal()
    assert "Self-heal: recovered" in report
    assert "Source fixes applied: 1" in report
    assert len(calls) == 6
    assert sm._read_tool_failures()["probe"]["resolved"]
    assert path.read_text(encoding="utf-8") == builder.tools["probe"]["validated_code"]



def test_registry_save_failure_rolls_back(repair_tool, monkeypatch):
    builder, path, error = repair_tool
    original = path.read_bytes()
    manifest = copy.deepcopy(builder.tools)

    def fail_save():
        raise OSError("disk unavailable")

    monkeypatch.setattr(builder, "_save", fail_save)
    result = builder.debug_and_fix("probe", error)
    assert not result["ok"] and not result["fixed"]
    assert path.read_bytes() == original
    assert builder.tools == manifest


def test_unchanged_source_does_not_claim_repair(repair_tool):
    builder, path, error = repair_tool
    path.write_text(builder.tools["probe"]["validated_code"], encoding="utf-8")
    assert not builder.debug_and_fix("probe", error)["fixed"]


def test_self_heal_reports_unresolved_without_installing(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sm, "_BACKEND_DIR", tmp_path)
    monkeypatch.setattr(sm, "_FAILURE_LOG", tmp_path / "failures.json")
    sm.record_tool_failure("unknown", "NameError: unknown")
    for name in ("compile_check_backend", "run_backend_tests", "build_frontend"):
        monkeypatch.setattr(sm, name, lambda: {"ok": True})

    def no_install():
        pytest.fail("Passing checks must not install dependencies")

    for name in ("install_python_dependencies", "install_frontend_dependencies"):
        monkeypatch.setattr(sm, name, no_install)
    report = sm.self_heal()
    assert "needs manual intervention" in report
    assert "unresolved failures: 1" in report
