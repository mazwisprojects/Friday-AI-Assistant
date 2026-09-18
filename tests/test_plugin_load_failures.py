"""Load failures must reach maintenance without blocking healthy plugins."""
import json

from actions import self_maintenance as sm
from plugin_manager import PluginManager
from tool_builder import ToolBuilder


def test_load_failure_is_recorded_and_healthy_tool_still_loads(tmp_path, monkeypatch):
    failure_log = tmp_path / "tool_failures.json"
    monkeypatch.setattr(sm, "_FAILURE_LOG", failure_log)
    tools_dir = tmp_path / "mytools"
    tools_dir.mkdir()
    (tools_dir / "broken.py").write_text("raise ValueError('load failed')\n", encoding="utf-8")
    (tools_dir / "healthy.py").write_text("def run(arguments):\n    return 42\n", encoding="utf-8")
    builder = ToolBuilder(str(tmp_path))
    builder.tools = {
        "broken": {"module_path": "mytools/broken.py"},
        "healthy": {"module_path": "mytools/healthy.py"},
    }
    manager = PluginManager(str(tmp_path), builder, None, None)

    result = manager.load_all_tools()

    assert result == {"loaded": ["healthy"], "failed": ["broken"]}
    failures = json.loads(failure_log.read_text(encoding="utf-8"))
    assert failures["broken"]["count"] == 1
    assert failures["broken"]["resolved"] is False
    assert "Traceback" in failures["broken"]["last_error"]
    assert "ValueError: load failed" in failures["broken"]["last_error"]
    assert "healthy" not in failures
