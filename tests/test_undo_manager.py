from pathlib import Path

from undo_manager import UndoManager


def test_undo_last_reports_when_no_actions_recorded(tmp_path):
    manager = UndoManager(str(tmp_path))

    result = manager.undo_last()

    assert "no reversible action" in result.lower()


def test_record_file_write_backs_up_existing_file_and_undo_restores_it(tmp_path):
    manager = UndoManager(str(tmp_path))
    target = tmp_path / "file.txt"
    target.write_text("original content")

    manager.record_file_write(str(target))
    target.write_text("modified content")

    result = manager.undo_last()

    assert "Restored" in result
    assert target.read_text() == "original content"


def test_record_file_write_for_new_file_marks_it_for_deletion_on_undo(tmp_path):
    manager = UndoManager(str(tmp_path))
    target = tmp_path / "new_file.txt"

    manager.record_file_write(str(target))
    target.write_text("newly created")

    result = manager.undo_last()

    assert "Removed" in result
    assert not target.exists()


def test_record_deleted_and_undo_restores_file(tmp_path):
    manager = UndoManager(str(tmp_path))
    target = tmp_path / "to_delete.txt"
    target.write_text("keep me")

    manager.record_deleted(str(target))
    target.unlink()

    result = manager.undo_last()

    assert "Restored deleted item" in result
    assert target.exists()
    assert target.read_text() == "keep me"


def test_undo_restore_deleted_fails_if_target_already_exists(tmp_path):
    manager = UndoManager(str(tmp_path))
    target = tmp_path / "conflict.txt"
    target.write_text("original")

    manager.record_deleted(str(target))
    # File still exists (was never actually deleted in this scenario)

    result = manager.undo_last()

    assert "already exists" in result.lower()


def test_record_move_and_undo_moves_file_back(tmp_path):
    manager = UndoManager(str(tmp_path))
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("data")
    source.rename(destination)

    manager.record_move(str(source), str(destination))

    result = manager.undo_last()

    assert "Moved" in result
    assert source.exists()
    assert not destination.exists()


def test_record_rename_and_undo_renames_back(tmp_path):
    manager = UndoManager(str(tmp_path))
    old_path = tmp_path / "old_name.txt"
    new_path = tmp_path / "new_name.txt"
    old_path.write_text("data")
    old_path.rename(new_path)

    manager.record_rename(str(old_path), str(new_path))

    result = manager.undo_last()

    assert "Renamed" in result
    assert old_path.exists()
    assert not new_path.exists()


def test_undo_only_pops_most_recent_action(tmp_path):
    manager = UndoManager(str(tmp_path))
    first_target = tmp_path / "first.txt"
    second_target = tmp_path / "second.txt"

    manager.record_file_write(str(first_target))
    first_target.write_text("first")
    manager.record_file_write(str(second_target))
    second_target.write_text("second")

    manager.undo_last()

    assert not second_target.exists()
    assert first_target.exists()

    manager.undo_last()

    assert not first_target.exists()


def test_undo_restore_wallpaper_uses_desktop_module(tmp_path):
    manager = UndoManager(str(tmp_path))
    manager.record_wallpaper("C:/wallpapers/old.jpg")

    calls = []

    class FakeDesktopModule:
        @staticmethod
        def set_wallpaper(path):
            calls.append(path)
            return f"Wallpaper set to {path}"

    result = manager.undo_last(desktop_module=FakeDesktopModule())

    assert calls == ["C:/wallpapers/old.jpg"]
    assert "Wallpaper set to" in result


def test_undo_restore_setting_uses_computer_settings_module(tmp_path):
    manager = UndoManager(str(tmp_path))
    manager.record_setting("volume_set", 42)

    calls = []

    class FakeSettingsModule:
        @staticmethod
        def computer_settings(params):
            calls.append(params)
            return "Volume restored"

    result = manager.undo_last(computer_settings_module=FakeSettingsModule())

    assert calls == [{"action": "volume_set", "value": 42}]
    assert result == "Volume restored"


def test_undo_switch_project_uses_project_manager(tmp_path):
    manager = UndoManager(str(tmp_path))
    manager.record_project_switch("previous_project")

    class FakeProjectManager:
        @staticmethod
        def switch_project(name):
            return True, f"Switched to {name}"

    result = manager.undo_last(project_manager=FakeProjectManager())

    assert result == "Switched to previous_project"
