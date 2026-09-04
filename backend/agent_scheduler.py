"""Persistent scheduler for generated and built-in Friday agents."""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


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

    def schedule(self, agent_type: str, goal: str, interval_seconds: int, repo_path: str = ".", max_retries: int = 3) -> dict:
        if interval_seconds < 30:
            raise ValueError("Agent schedule interval must be at least 30 seconds")
        schedule = {"id": str(uuid.uuid4()), "agent_type": agent_type, "goal": goal, "repo_path": repo_path, "interval_seconds": interval_seconds, "next_run": time.time() + interval_seconds, "enabled": True, "max_retries": max(0, min(int(max_retries), 10)), "retry_count": 0, "last_status": "never_run"}
        with self._lock:
            schedules = self._load()
            schedules.append(schedule)
            self._save(schedules)
        return schedule

    def schedule_daily(self, key: str, agent_type: str, goal: str, hour: int, minute: int = 0, repo_path: str = ".") -> dict:
        return self._schedule_calendar(key, agent_type, goal, "daily", hour, minute, None, repo_path)

    def schedule_weekly(self, key: str, agent_type: str, goal: str, weekday: int, hour: int, minute: int = 0, repo_path: str = ".") -> dict:
        return self._schedule_calendar(key, agent_type, goal, "weekly", hour, minute, weekday, repo_path)

    def ensure_default_workflows(self) -> list[dict]:
        """Install standard Friday workflows exactly once, using Johannesburg time."""
        defaults = [
            ("morning_briefing", "daily", "daily_planning_agent", "Prepare the morning briefing from calendar, email, and tasks.", 7, 0, None),
            ("email_triage", "interval", "email_triage_agent", "Triage new and important emails.", 0, 0, 900),
            ("calendar_reminders", "interval", "calendar_briefing_agent", "Check upcoming meetings and send reminders.", 0, 0, 300),
            ("project_health", "daily", "project_health_agent", "Run the daily project health report.", 18, 0, None),
            ("flight_watch", "daily", "flight_watch_agent", "Check saved flight-watch goals for price changes.", 9, 0, None),
            ("morning_news", "daily", "news_agent", "Prepare the morning news report.", 7, 15, None),
            ("printer_monitor", "interval", "printer_monitor_agent", "Check printer completion and print status.", 0, 0, 120),
            ("smart_home_nightly", "daily", "smart_home_agent", "Run the nightly smart-home check-in.", 21, 0, None),
            ("memory_cleanup", "weekly", "memory_cleanup_agent", "Run weekly memory cleanup and compaction review.", 20, 0, 6),
            ("dependency_audit", "weekly", "project_health_agent", "Run weekly dependency and deprecation audit.", 10, 0, 5),
        ]
        created = []
        for key, schedule_type, agent_type, goal, hour, minute, extra in defaults:
            if schedule_type == "interval":
                created.append(self._schedule_interval(key, agent_type, goal, extra))
            elif schedule_type == "daily":
                created.append(self.schedule_daily(key, agent_type, goal, hour, minute))
            else:
                created.append(self.schedule_weekly(key, agent_type, goal, extra, hour, minute))
        return created

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

    def set_enabled(self, schedule_id: str, enabled: bool) -> bool:
        with self._lock:
            schedules = self._load()
            for schedule in schedules:
                if schedule.get("id") == schedule_id:
                    schedule["enabled"] = bool(enabled)
                    self._save(schedules)
                    return True
        return False

    def run_now(self, schedule_id: str) -> dict:
        with self._lock:
            schedules = self._load()
            schedule = next((item for item in schedules if item.get("id") == schedule_id), None)
            if not schedule:
                raise ValueError(f"Schedule not found: {schedule_id}")
            agent_id = self.dispatcher.deploy_agent(schedule["agent_type"], schedule["goal"], schedule.get("repo_path", "."))
            schedule["last_agent_id"] = agent_id
            schedule["last_run"] = time.time()
            schedule["last_status"] = "running"
            self._save(schedules)
            return {"schedule_id": schedule_id, "agent_id": agent_id, "status": "running"}

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
                            agent_id = self.dispatcher.deploy_agent(schedule["agent_type"], schedule["goal"], schedule.get("repo_path", "."))
                            schedule["last_run"] = now
                            schedule["last_agent_id"] = agent_id
                            schedule["last_status"] = "running"
                            schedule["retry_count"] = 0
                            schedule["next_run"] = self._next_run(schedule, now)
                        except Exception as exc:
                            schedule["last_error"] = str(exc)
                            schedule["last_status"] = "failed"
                            schedule["retry_count"] = int(schedule.get("retry_count", 0)) + 1
                            retry_delay = min(3600, 60 * (2 ** min(schedule["retry_count"], 5)))
                            if schedule["retry_count"] <= int(schedule.get("max_retries", 3)):
                                schedule["next_run"] = now + retry_delay
                            else:
                                schedule["enabled"] = False
                            if schedule["retry_count"] > int(schedule.get("max_retries", 3)):
                                schedule["next_run"] = self._next_run(schedule, now)
                        changed = True
                if changed:
                    self._save(schedules)

    def _schedule_interval(self, key: str, agent_type: str, goal: str, interval_seconds: int) -> dict:
        return self._schedule_once({"key": key, "agent_type": agent_type, "goal": goal, "repo_path": ".", "interval_seconds": interval_seconds, "next_run": time.time() + interval_seconds, "enabled": True})

    def _schedule_calendar(self, key: str, agent_type: str, goal: str, schedule_type: str, hour: int, minute: int, weekday: int | None, repo_path: str) -> dict:
        schedule = {"key": key, "agent_type": agent_type, "goal": goal, "repo_path": repo_path, "schedule_type": schedule_type, "hour": hour, "minute": minute, "weekday": weekday, "enabled": True}
        schedule["next_run"] = self._next_run(schedule, time.time())
        return self._schedule_once(schedule)

    def _schedule_once(self, schedule: dict) -> dict:
        with self._lock:
            schedules = self._load()
            existing = next((item for item in schedules if item.get("key") == schedule["key"]), None)
            if existing:
                return existing
            schedule["id"] = str(uuid.uuid4())
            schedules.append(schedule)
            self._save(schedules)
        return schedule

    @staticmethod
    def _next_run(schedule: dict, now_timestamp: float) -> float:
        if schedule.get("schedule_type") not in {"daily", "weekly"}:
            return now_timestamp + max(30, int(schedule.get("interval_seconds", 3600)))
        now = datetime.fromtimestamp(now_timestamp, ZoneInfo("Africa/Johannesburg"))
        target = now.replace(hour=int(schedule["hour"]), minute=int(schedule.get("minute", 0)), second=0, microsecond=0)
        if schedule.get("schedule_type") == "weekly":
            target += timedelta(days=(int(schedule.get("weekday", 0)) - target.weekday()) % 7)
        if target <= now:
            target += timedelta(days=7 if schedule.get("schedule_type") == "weekly" else 1)
        return target.timestamp()
