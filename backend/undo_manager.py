import json
import shutil
import threading
import time
from pathlib import Path


class UndoManager:
    """Persistent stack of reversible local actions."""

    def __init__(self, workspace_root: str):
        self.root_dir = Path(workspace_root) / "long_term_memory" / "undo"
        self.backup_dir = self.root_dir / "backups"
        self.records_file = self.root_dir / "records.jsonl"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, action: str, data: dict) -> None:
        entry = {"timestamp": time.time(), "action": action, "data": data}
        with self._lock, self.records_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def record_file_write(self, path: str) -> None:
        target = Path(path).resolve()
        if target.exists() and target.is_file():
            backup = self.backup_dir / f"{int(time.time() * 1000000)}_{target.name}"
            shutil.copy2(target, backup)
            self.record("restore_file", {"path": str(target), "backup": str(backup)})
        else:
            self.record("delete_file", {"path": str(target)})

    def record_deleted(self, path: str) -> None:
        target = Path(path).resolve()
        if not target.exists():
            return
        backup = self.backup_dir / f"{int(time.time() * 1000000)}_{target.name}"
        if target.is_dir():
            shutil.copytree(target, backup)
        else:
            shutil.copy2(target, backup)
        self.record("restore_deleted", {"path": str(target), "backup": str(backup)})

    def record_move(self, source: str, destination: str) -> None:
        self.record("move_file", {"source": source, "destination": destination})

    def record_copy(self, destination: str) -> None:
        self.record("delete_file", {"path": destination})

    def record_rename(self, old_path: str, new_path: str) -> None:
        self.record("rename_file", {"old_path": old_path, "new_path": new_path})

    def record_wallpaper(self, previous_path: str | None) -> None:
        self.record("restore_wallpaper", {"path": previous_path})

    def record_project_switch(self, previous_project: str) -> None:
        self.record("switch_project", {"project": previous_project})

    def record_setting(self, action: str, value) -> None:
        self.record("restore_setting", {"action": action, "value": value})

    def undo_last(self, desktop_module=None, computer_settings_module=None, project_manager=None) -> str:
        if not self.records_file.exists():
            return "There is no reversible action to undo."

        with self._lock:
            lines = [line for line in self.records_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            if not lines:
                return "There is no reversible action to undo."
            record = json.loads(lines[-1])
            self.records_file.write_text("\n".join(lines[:-1]) + ("\n" if len(lines) > 1 else ""), encoding="utf-8")

        action = record.get("action")
        data = record.get("data", {})
        try:
            if action == "restore_file":
                shutil.copy2(data["backup"], data["path"])
                return f"Restored {Path(data['path']).name}."
            if action == "delete_file":
                target = Path(data["path"])
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink(missing_ok=True)
                return f"Removed the item created by the last action: {target.name}."
            if action == "restore_deleted":
                target = Path(data["path"])
                backup = Path(data["backup"])
                if target.exists():
                    return f"Cannot restore {target.name}; a file already exists there."
                if backup.is_dir():
                    shutil.copytree(backup, target)
                else:
                    shutil.copy2(backup, target)
                return f"Restored deleted item: {target.name}."
            if action == "move_file":
                shutil.move(data["destination"], data["source"])
                return f"Moved {Path(data['destination']).name} back to its original location."
            if action == "rename_file":
                Path(data["new_path"]).rename(data["old_path"])
                return f"Renamed {Path(data['new_path']).name} back to {Path(data['old_path']).name}."
            if action == "restore_wallpaper":
                if desktop_module and data.get("path"):
                    return desktop_module.set_wallpaper(data["path"])
                return "The previous wallpaper could not be restored because its original path is unavailable."
            if action == "switch_project" and project_manager:
                success, message = project_manager.switch_project(data["project"])
                return message if success else f"Could not restore the previous project: {message}"
            if action == "restore_setting" and data.get("value") is not None:
                if computer_settings_module:
                    return computer_settings_module.computer_settings({
                        "action": data["action"],
                        "value": data["value"],
                    })
                return "The settings module is unavailable."
        except Exception as error:
            return f"Undo failed: {error}"

        return f"The last action ({action}) is not reversible yet."
