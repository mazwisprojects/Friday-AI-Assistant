"""Small persistent task store for Friday and generated agents."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path


class TaskManager:
    def __init__(self, root: str):
        self.path = Path(root) / "long_term_memory" / "tasks.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, tasks: list[dict]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)

    def create(self, title: str, due: str = "", priority: str = "normal", project: str = "", notes: str = "") -> dict:
        if not title.strip():
            raise ValueError("Task title is required")
        task = {"id": str(uuid.uuid4()), "title": title.strip(), "due": due.strip(), "priority": priority.lower(), "project": project.strip(), "notes": notes.strip(), "status": "open", "created_at": datetime.now().isoformat(timespec="seconds")}
        with self._lock:
            tasks = self._load()
            tasks.append(task)
            self._save(tasks)
        return task

    def list(self, status: str = "") -> list[dict]:
        with self._lock:
            tasks = self._load()
        return [task for task in tasks if not status or task.get("status") == status]

    def complete(self, task_id: str) -> dict:
        with self._lock:
            tasks = self._load()
            for task in tasks:
                if task.get("id") == task_id:
                    task["status"] = "completed"
                    task["completed_at"] = datetime.now().isoformat(timespec="seconds")
                    self._save(tasks)
                    return task
        raise ValueError(f"Task not found: {task_id}")

    def overdue(self) -> list[dict]:
        now = datetime.now()
        overdue = []
        for task in self.list("open"):
            try:
                if task.get("due") and datetime.fromisoformat(task["due"]) < now:
                    overdue.append(task)
            except ValueError:
                continue
        return overdue

    def manage(self, action: str, **kwargs) -> dict | list:
        action = action.lower().strip()
        if action == "create":
            return self.create(kwargs.get("title", ""), kwargs.get("due", ""), kwargs.get("priority", "normal"), kwargs.get("project", ""), kwargs.get("notes", ""))
        if action == "list":
            return self.list(kwargs.get("status", ""))
        if action == "complete":
            return self.complete(kwargs.get("task_id", ""))
        if action == "overdue":
            return self.overdue()
        raise ValueError(f"Unknown task action: {action}")
