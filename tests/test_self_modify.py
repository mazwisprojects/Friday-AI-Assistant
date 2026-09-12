"""Tests for the self-modification layer (backend/actions/self_modify.py)."""
import json
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND / "backend"))

from actions import self_modify  # noqa: E402
from action_policy import decision  # noqa: E402


class _Patcher:
    """Minimal attribute patcher so tests run under pytest and standalone."""

    def __init__(self, module):
        self._module = module
        self._saved = {}

    def set(self, name, value):
        if name not in self._saved:
            self._saved[name] = getattr(self._module, name)
        setattr(self._module, name, value)

    def restore(self):
        for name, value in self._saved.items():
            setattr(self._module, name, value)


def test_read_edit_replace():
    # Self-managed temp dir: pytest's tmp_path factory trips antivirus file locks on this machine.
    with tempfile.TemporaryDirectory() as td:
        _run_read_edit_replace(Path(td))


def _run_read_edit_replace(tmp_path):
    mod = tmp_path / "demo_tool.py"
    mod.write_text(
        "import json\n\n\ndef run(args=None):\n    value = 1\n    return value\n",
        encoding="utf-8",
    )
    patcher = _Patcher(self_modify)
    patcher.set("_find_module", lambda name: mod)
    try:
        result = self_modify.read_source("demo_tool")
        assert result["ok"] and "def run" in result["code"]

        result = self_modify.edit_source("demo_tool", "value = 1", "value = 41 + 1")
        assert result["ok"], result
        assert "41 + 1" in mod.read_text(encoding="utf-8")

        assert not self_modify.edit_source("demo_tool", "NOT-PRESENT", "x")["ok"]

        broken = self_modify.edit_source("demo_tool", "41 + 1", "def broken(:")
        assert not broken["ok"] and "Syntax" in broken["error"]

        result = self_modify.replace_function(
            "demo_tool", "run", "value = 42\nreturn args or value"
        )
        assert result["ok"], result
        code = mod.read_text(encoding="utf-8")
        assert "def run(args=None):" in code, code  # signature must be preserved
        namespace = {}
        exec(compile(code, str(mod), "exec"), namespace)
        assert namespace["run"]({"x": 1}) == {"x": 1}
        assert namespace["run"]() == 42

        result = self_modify.add_import("demo_tool", "import os")
        assert result["ok"], result
        result = self_modify.add_import("demo_tool", "import os")
        assert result["ok"] and "already present" in result["message"]
        compile(mod.read_text(encoding="utf-8"), str(mod), "exec")
    finally:
        patcher.restore()


def test_patch_config_and_update_memory():
    with tempfile.TemporaryDirectory() as td:
        _run_patch_config(Path(td))


def _run_patch_config(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(
        json.dumps({"voice": {"model": "old"}, "quiet_mode": False}),
        encoding="utf-8",
    )
    patcher = _Patcher(self_modify)
    patcher.set("_find_json", lambda name: cfg)
    try:
        result = self_modify.patch_config("settings", "voice.model", "gemini-new")
        assert result["ok"] and result["old"] == "old" and result["new"] == "gemini-new"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert data["voice"]["model"] == "gemini-new"
        assert data["quiet_mode"] is False

        assert self_modify.patch_config("settings", "new.deep.key", 7)["ok"]
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert data["new"]["deep"]["key"] == 7

        result = self_modify.update_memory("quiet", True)
        assert result["ok"] and result["updated"][0]["key"] == "quiet_mode"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert data["quiet_mode"] is True

        assert not self_modify.update_memory("does-not-match", 1)["ok"]
    finally:
        patcher.restore()


def test_missing_targets(tmp_path=None):
    patcher = _Patcher(self_modify)
    patcher.set("_find_module", lambda name: None)
    patcher.set("_find_json", lambda name: None)
    try:
        assert not self_modify.read_source("nope")["ok"]
        assert not self_modify.edit_source("nope", "a", "b")["ok"]
        assert not self_modify.replace_function("nope", "run", "pass")["ok"]
        assert not self_modify.add_import("nope", "import os")["ok"]
        assert not self_modify.patch_config("nope", "a.b", 1)["ok"]
        assert not self_modify.update_memory("anything", 1)["ok"]
    finally:
        patcher.restore()


def test_repair_source_requires_confirmation_and_rolls_back_failed_verification():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        mod = root / "repair_target.py"
        mod.write_text("VALUE = 1\n", encoding="utf-8")
        audit = root / "repair_audit.jsonl"
        snapshots = root / "snapshots"
        from actions import time_guard

        patcher = _Patcher(self_modify)
        guard_patcher = _Patcher(time_guard)
        patcher.set("_find_module", lambda name: mod)
        patcher.set("_REPAIR_AUDIT", audit)
        patcher.set("_PROJECT_ROOT", root)
        guard_patcher.set("_SNAP_ROOT", snapshots)
        try:
            assert decision("self_modify", {"action": "repair_source"})["tier"] == "always_confirm"
            applied = self_modify.repair_source("repair_target", "VALUE = 1", "VALUE = 2")
            assert applied["ok"] and "VALUE = 2" in mod.read_text(encoding="utf-8")

            failed = self_modify.repair_source(
                "repair_target", "VALUE = 2", "VALUE = 3", "tests/test_file_that_does_not_exist.py"
            )
            assert not failed["ok"] and failed["restore"]["ok"]
            assert "VALUE = 2" in mod.read_text(encoding="utf-8")
            entries = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
            assert entries[-2]["status"] == "applied"
            assert entries[-1]["status"] == "rolled_back"
        finally:
            guard_patcher.restore()
            patcher.restore()


if __name__ == "__main__":
    failures = 0
    for test in (test_read_edit_replace, test_patch_config_and_update_memory, test_missing_targets):
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
    print("RESULT:", "ALL_PASS" if failures == 0 else f"{failures} FAILED")
    sys.exit(1 if failures else 0)
