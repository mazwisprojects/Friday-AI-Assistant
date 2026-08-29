from pathlib import Path

from project_manager import ProjectManager


def test_init_creates_temp_project(tmp_path):
    manager = ProjectManager(str(tmp_path))

    assert manager.current_project == "temp"
    assert manager.get_current_project_path().exists()
    assert (manager.get_current_project_path() / "cad").exists()


def test_create_project_creates_subfolders(tmp_path):
    manager = ProjectManager(str(tmp_path))

    success, message = manager.create_project("MyProject")

    assert success is True
    project_path = manager.projects_dir / "MyProject"
    assert project_path.exists()
    assert (project_path / "cad").exists()
    assert (project_path / "browser").exists()


def test_create_project_rejects_duplicate(tmp_path):
    manager = ProjectManager(str(tmp_path))
    manager.create_project("MyProject")

    success, message = manager.create_project("MyProject")

    assert success is False
    assert "already exists" in message


def test_create_project_sanitizes_unsafe_characters(tmp_path):
    manager = ProjectManager(str(tmp_path))

    manager.create_project("../../evil")

    assert not (manager.projects_dir / ".." / ".." / "evil").resolve().exists()
    escaped_outside = tmp_path.parent.parent / "evil"
    assert not escaped_outside.exists()


def test_switch_project_updates_current_project(tmp_path):
    manager = ProjectManager(str(tmp_path))
    manager.create_project("MyProject")

    success, message = manager.switch_project("MyProject")

    assert success is True
    assert manager.current_project == "MyProject"


def test_switch_project_fails_for_missing_project(tmp_path):
    manager = ProjectManager(str(tmp_path))

    success, message = manager.switch_project("DoesNotExist")

    assert success is False
    assert manager.current_project == "temp"


def test_list_projects_includes_created_projects(tmp_path):
    manager = ProjectManager(str(tmp_path))
    manager.create_project("Alpha")
    manager.create_project("Beta")

    projects = manager.list_projects()

    assert "Alpha" in projects
    assert "Beta" in projects
    assert "temp" in projects


def test_log_chat_appends_jsonl_entry(tmp_path):
    manager = ProjectManager(str(tmp_path))

    manager.log_chat("User", "Hello there")

    history = manager.get_recent_chat_history(limit=5)
    assert len(history) == 1
    assert history[0]["sender"] == "User"
    assert history[0]["text"] == "Hello there"


def test_get_recent_chat_history_respects_limit(tmp_path):
    manager = ProjectManager(str(tmp_path))
    for i in range(5):
        manager.log_chat("User", f"Message {i}")

    history = manager.get_recent_chat_history(limit=2)

    assert len(history) == 2
    assert history[-1]["text"] == "Message 4"


def test_get_recent_chat_history_returns_empty_when_no_log(tmp_path):
    manager = ProjectManager(str(tmp_path))

    assert manager.get_recent_chat_history() == []


def test_save_cad_artifact_copies_file_into_project(tmp_path):
    manager = ProjectManager(str(tmp_path))
    source_file = tmp_path / "output.stl"
    source_file.write_text("fake stl data")

    dest_path = manager.save_cad_artifact(str(source_file), "a cool widget")

    assert dest_path is not None
    assert Path(dest_path).exists()
    assert Path(dest_path).parent.name == "cad"


def test_save_cad_artifact_returns_none_for_missing_source(tmp_path):
    manager = ProjectManager(str(tmp_path))

    result = manager.save_cad_artifact(str(tmp_path / "missing.stl"), "widget")

    assert result is None


def test_get_project_context_lists_files_and_reads_text(tmp_path):
    manager = ProjectManager(str(tmp_path))
    (manager.get_current_project_path() / "notes.txt").write_text("hello world")

    context = manager.get_project_context()

    assert "notes.txt" in context
    assert "hello world" in context


def test_get_project_context_skips_large_files(tmp_path):
    manager = ProjectManager(str(tmp_path))
    large_file = manager.get_current_project_path() / "big.txt"
    large_file.write_text("x" * 200)

    context = manager.get_project_context(max_file_size=100)

    assert "too large" in context
