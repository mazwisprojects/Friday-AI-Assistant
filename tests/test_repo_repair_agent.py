from actions import repo_repair_agent


def test_repo_repair_agent_runs_inspect_test_verify_loop(monkeypatch):
    calls = []

    def fake_git_status(repo_path):
        calls.append(("status", repo_path))
        return "## main\n M backend/example.py"

    def fake_compile_check():
        calls.append(("compile",))
        return {"ok": True, "issues": []}

    def fake_run_tests(*args, **kwargs):
        calls.append(("tests",))
        return {"ok": True, "issues": []}

    monkeypatch.setattr(repo_repair_agent.git_workflow_module, "git_status", fake_git_status)
    monkeypatch.setattr(repo_repair_agent.self_maintenance_module, "compile_check_backend", fake_compile_check)
    monkeypatch.setattr(repo_repair_agent.self_maintenance_module, "run_backend_tests", fake_run_tests)

    import threading
    cancel_event = threading.Event()
    logs = []

    result = repo_repair_agent.run("fix failing tests", "C:/repo", logs.append, cancel_event)

    assert result["ok"] is True
    assert "Goal: fix failing tests" in result["summary"]
    assert any(c[0] == "status" for c in calls)
    assert calls.count(("tests",)) == 2
    assert logs


def test_repo_repair_agent_reports_issues_when_tests_fail(monkeypatch):
    def fake_git_status(repo_path):
        return "## main"

    def fake_compile_check():
        return {"ok": True, "issues": []}

    def fake_run_tests(*args, **kwargs):
        return {"ok": False, "issues": ["FAILED tests/test_x.py::test_y"]}

    monkeypatch.setattr(repo_repair_agent.git_workflow_module, "git_status", fake_git_status)
    monkeypatch.setattr(repo_repair_agent.self_maintenance_module, "compile_check_backend", fake_compile_check)
    monkeypatch.setattr(repo_repair_agent.self_maintenance_module, "run_backend_tests", fake_run_tests)

    import threading
    cancel_event = threading.Event()

    result = repo_repair_agent.run("fix failing tests", "C:/repo", lambda msg: None, cancel_event)

    assert result["ok"] is False
    assert "FAILED tests/test_x.py::test_y" in result["issues"]


def test_repo_repair_agent_stops_early_when_cancelled(monkeypatch):
    def fake_git_status(repo_path):
        return "## main"

    monkeypatch.setattr(repo_repair_agent.git_workflow_module, "git_status", fake_git_status)

    import threading
    cancel_event = threading.Event()
    cancel_event.set()

    result = repo_repair_agent.run("goal", "C:/repo", lambda msg: None, cancel_event)

    assert result.get("cancelled") is True
