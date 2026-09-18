from actions import code_helper


def test_code_helper_write_action_delegates_to_write_helper(monkeypatch):
    calls = []
    monkeypatch.setattr(code_helper, "_write_action", lambda description, language, output_path, player: calls.append((description, language, output_path)) or "Code written.")

    result = code_helper.code_helper({
        "action": "write",
        "description": "a function that adds two numbers",
        "language": "python",
        "output_path": "add.py",
    })

    assert result == "Code written."
    assert calls == [("a function that adds two numbers", "python", "add.py")]


def test_code_helper_edit_action_delegates_to_edit_helper(monkeypatch):
    calls = []
    monkeypatch.setattr(code_helper, "_edit_action", lambda file_path, instruction, player: calls.append((file_path, instruction)) or "Code edited.")

    result = code_helper.code_helper({
        "action": "edit",
        "file_path": "main.py",
        "description": "add logging",
    })

    assert result == "Code edited."
    assert calls == [("main.py", "add logging")]


def test_code_helper_auto_detects_intent(monkeypatch):
    monkeypatch.setattr(code_helper, "_detect_intent", lambda description, file_path, code: "explain")
    monkeypatch.setattr(code_helper, "_explain_action", lambda file_path, code, player: "Explanation done.")

    result = code_helper.code_helper({"action": "auto", "description": "what does this do"})

    assert result == "Explanation done."


def test_execution_uses_exit_code_not_output(tmp_path):
    path = tmp_path / "probe.py"
    path.write_text("raise SystemExit(7)\n", encoding="utf-8")
    result = code_helper._run_file(path, [], 5)
    assert not result["ok"]
    assert result["returncode"] == 7
    path.write_text("print('error count: 0')\n", encoding="utf-8")
    assert code_helper._run_file(path, [], 5)["ok"]


def test_timeout_is_explicit_failure(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise code_helper.subprocess.TimeoutExpired(args[0], 1, output=b"partial")
    monkeypatch.setattr(code_helper.subprocess, "run", timeout)
    result = code_helper._run_file(tmp_path / "probe.py", [], 1)
    assert not result["ok"]
    assert result["timed_out"]
    assert result["stdout"] == "partial"


def test_build_does_not_write_untested_final_candidate(tmp_path, monkeypatch):
    path = tmp_path / "probe.py"
    source = "raise SystemExit(7)\n"
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(code_helper, "_write", lambda *args: (source, path))
    fixes = []
    def fix(*args):
        fixes.append(args)
        return source
    monkeypatch.setattr(code_helper, "_fix_code", fix)
    report = code_helper._build("probe", "python", str(path), [], 5)
    assert "unable" in report
    assert len(fixes) == code_helper.MAX_BUILD_ATTEMPTS - 1


def test_run_action_remains_text(tmp_path):
    path = tmp_path / "probe.py"
    path.write_text("raise SystemExit(7)\n", encoding="utf-8")
    report = code_helper._run_action(str(path), [], 5, None)
    assert isinstance(report, str)
    assert "FAILED" in report
    assert "7" in report


def test_build_tests_repaired_candidate(tmp_path, monkeypatch):
    path = tmp_path / "probe.py"
    source = "raise SystemExit(7)\n"
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(code_helper, "_write", lambda *args: (source, path))
    monkeypatch.setattr(code_helper, "_fix_code", lambda *args: "print('error count: 0')\n")
    report = code_helper._build("probe", "python", str(path), [], 5)
    assert "Build complete" in report
    assert "2 attempts" in report
    assert "error count: 0" in report


def test_build_stops_when_repair_cannot_be_saved(tmp_path, monkeypatch):
    path = tmp_path / "probe.py"
    source = "raise SystemExit(7)\n"
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(code_helper, "_write", lambda *args: (source, path))
    monkeypatch.setattr(code_helper, "_fix_code", lambda *args: "print('fixed')\n")
    def deny_write(*args, **kwargs):
        raise PermissionError("read only")
    monkeypatch.setattr(type(path), "write_text", deny_write)
    report = code_helper._build("probe", "python", str(path), [], 5)
    assert "Could not fix code" in report
    assert "read only" in report
    assert path.read_text(encoding="utf-8") == source
