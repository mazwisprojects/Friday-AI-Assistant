"""Persistent scheduler for generated and built-in Friday agents."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path


class AgentScheduler:
    def __init__(self, root: str, dispatcher):
        self.path = Path(root) / "long_term_memory" / "agent_schedules.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.dispatcher = dispatcher
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, schedules: list[dict]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(schedules, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def schedule(self, agent_type: str, goal: str, interval_seconds: int, repo_path: str = ".") -> dict:
        if interval_seconds < 30:
            raise ValueError("Agent schedule interval must be at least 30 seconds")
        schedule = {"id": str(uuid.uuid4()), "agent_type": agent_type, "goal": goal, "repo_path": repo_path, "interval_seconds": interval_seconds, "next_run": time.time() + interval_seconds, "enabled": True}
        with self._lock:
            schedules = self._load()
            schedules.append(schedule)
            self._save(schedules)
        return schedule

    def list(self) -> list[dict]:
        with self._lock:
            return self._load()

    def cancel(self, schedule_id: str) -> bool:
        with self._lock:
            schedules = self._load()
            remaining = [schedule for schedule in schedules if schedule.get("id") != schedule_id]
            changed = len(remaining) != len(schedules)
            if changed:
                self._save(remaining)
            return changed

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(5):
            now = time.time()
            with self._lock:
                schedules = self._load()
                changed = False
                for schedule in schedules:
                    if schedule.get("enabled") and schedule.get("next_run", 0) <= now:
                        try:
                            self.dispatcher.deploy_agent(schedule["agent_type"], schedule["goal"], schedule.get("repo_path", "."))
                            schedule["last_run"] = now
                            schedule["next_run"] = now + max(30, int(schedule["interval_seconds"]))
                        except Exception as exc:
                            schedule["last_error"] = str(exc)
                            schedule["next_run"] = now + max(30, int(schedule["interval_seconds"]))
                        changed = True
                if changed:
                    self._save(schedules)
