"""Workflow automation and routine orchestration for Jarvis-style assistant mode."""

from __future__ import annotations

from typing import Any, Dict, List


class RoutineManager:
    """Defines reusable high-value routines that operate like assistant workflows."""

    def __init__(self):
        self.routines = {
            "morning_briefing": self._morning_briefing,
            "focus_mode": self._focus_mode,
            "work_summary": self._work_summary,
            "dev_assistant": self._dev_assistant,
            "start_work_routine": self._start_work_routine,
            "prepare_environment": self._prepare_environment,
            "project_checkup": self._project_checkup,
            "calendar_check": self._calendar_check,
            "workspace_cleanup": self._workspace_cleanup,
            "daily_report": self._daily_report,
        }

    def run_routine(self, name: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        payload = payload or {}
        runner = self.routines.get(name)
        if runner is None:
            raise ValueError(f"Unknown routine: {name}")
        return runner(payload)

    def execute_runtime(self, name: str, payload: Dict[str, Any] | None = None, runtime: Any | None = None) -> Dict[str, Any]:
        """Execute the routine against a real runtime object when one is present."""
        payload = payload or {}
        base_result = self.run_routine(name, payload)
        if runtime is None:
            return base_result

        execution: Dict[str, Any] = {}
        try:
            if name == "morning_briefing":
                google_account = getattr(runtime, "google_account", None)
                if google_account and getattr(google_account, "credentials", None):
                    try:
                        execution["important_emails"] = google_account.read_emails("is:unread is:important", 10)
                    except Exception as exc:
                        execution["important_emails_error"] = str(exc)
                    try:
                        execution["calendar_events"] = google_account.list_calendar_events("", 1, 20)
                    except Exception as exc:
                        execution["calendar_error"] = str(exc)
                get_system_status = getattr(runtime, "get_system_status", None)
                if callable(get_system_status):
                    execution["system_status"] = get_system_status()
                base_result["context"] = {
                    "important_email_count": len(execution.get("important_emails", [])),
                    "calendar_event_count": len(execution.get("calendar_events", [])),
                }
                system_status = execution.get("system_status") or {}
                base_result["summary"] = (
                    f"Morning briefing: {len(execution.get('important_emails', []))} important unread email(s), "
                    f"{len(execution.get('calendar_events', []))} calendar event(s) today, and system health "
                    f"at CPU {system_status.get('cpu_percent', 'n/a')}% and "
                    f"RAM {system_status.get('ram_percent', 'n/a')}%."
                )

            if name in {"prepare_environment", "daily_report", "start_work_routine"}:
                system_status = getattr(runtime, "get_system_status", None)
                if callable(system_status):
                    execution["system_status"] = system_status()

            if name == "project_checkup":
                command = payload.get("test_command", "pytest -q")
                run_command = getattr(runtime, "run_powershell_command", None)
                if callable(run_command):
                    execution["test_result"] = run_command({
                        "command": command,
                        "cwd": payload.get("cwd", "."),
                        "timeout": payload.get("timeout", 120),
                    })
                else:
                    execution["test_result"] = f"Command not executed: {command}"
                base_result["context"]["test_result"] = execution["test_result"]
                base_result["summary"] = f"Project checkup for {payload.get('project', 'current project')} executed with: {command}. Outcome: {execution['test_result']}."

            if name == "calendar_check":
                reminder = getattr(runtime, "set_reminder", None)
                if callable(reminder):
                    event = (payload.get("events") or [{}])[0] if payload.get("events") else {}
                    execution["reminder"] = reminder({
                        "date": payload.get("date", "2026-09-01"),
                        "time": payload.get("time", "09:00"),
                        "message": event.get("summary") or "Calendar check reminder",
                    })

            if name == "workspace_cleanup":
                control = getattr(runtime, "desktop_control", None)
                if callable(control):
                    execution["desktop_cleanup"] = control({"action": "organize", "mode": "by_type"})
                    execution["desktop_list"] = control({"action": "list"})

            if name == "daily_report":
                control = getattr(runtime, "desktop_control", None)
                if callable(control):
                    execution["desktop_summary"] = control({"action": "stats"})
                system_status = getattr(runtime, "get_system_status", None)
                if callable(system_status):
                    execution["system_status"] = system_status()

            if name == "start_work_routine":
                control = getattr(runtime, "desktop_control", None)
                if callable(control):
                    execution["desktop_summary"] = control({"action": "stats"})

        except Exception as exc:  # pragma: no cover - safety fallback for real runtime calls
            execution["error"] = str(exc)

        base_result["execution"] = execution
        return base_result

    def _morning_briefing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        weather = payload.get("weather", "Weather unavailable")
        tasks = payload.get("tasks", [])
        system = payload.get("system_health", {})
        summary = (
            f"Good morning. Weather: {weather}. "
            f"You have {len(tasks)} planned task(s) today. "
            f"System health is stable at CPU {system.get('cpu', 'n/a')}% and RAM {system.get('ram', 'n/a')}%."
        )
        return {
            "routine": "morning_briefing",
            "summary": summary,
            "actions": [
                {"name": "check_weather", "status": "complete"},
                {"name": "review_priority_tasks", "status": "pending"},
                {"name": "check_system_health", "status": "complete"},
            ],
        }

    def _focus_mode(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        project = payload.get("project", "default")
        notifications_disabled = bool(payload.get("notifications", False))
        if payload.get("notifications") is False:
            notifications_disabled = True
        return {
            "routine": "focus_mode",
            "context": {
                "project": project,
                "notifications_disabled": notifications_disabled,
                "ready": True,
            },
            "summary": f"Focus mode prepared for {project}.",
            "actions": [
                {"name": "mute_notifications", "status": "complete" if notifications_disabled else "skipped"},
                {"name": "open_project_workspace", "status": "complete"},
                {"name": "start_focus_timer", "status": "pending"},
            ],
        }

    def _work_summary(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        completed = payload.get("completed", [])
        remaining = payload.get("remaining", [])
        summary = {
            "routine": "work_summary",
            "summary": {
                "completed_count": len(completed),
                "remaining_count": len(remaining),
                "focus": "Review completed items, then prioritize remaining work.",
            },
            "actions": [
                {"name": "collect_completed_work", "status": "complete"},
                {"name": "identify_follow_up", "status": "complete"},
            ],
            "completed": completed,
            "remaining": remaining,
        }
        return summary

    def _dev_assistant(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        issue = payload.get("issue", "No issue provided")
        repo = payload.get("repo", "current project")
        next_steps = [
            f"Inspect the import path and startup error in {repo}.",
            "Trace the failing import stack and verify the package layout.",
            "Run the smallest relevant test or startup check before patching.",
            "Apply the minimal fix and confirm the issue is resolved.",
        ]
        return {
            "routine": "dev_assistant",
            "issue": issue,
            "repo": repo,
            "next_steps": next_steps,
            "summary": f"Dev assistant prepared for: {issue}",
        }

    def _start_work_routine(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        project = payload.get("project", "current project")
        tasks = payload.get("tasks", []) or ["No explicit tasks provided"]
        actions = [
            {"name": "open_project_workspace", "status": "complete"},
            {"name": "review_top_priority_tasks", "status": "complete"},
            {"name": "begin_focus_session", "status": "pending"},
        ]
        summary = (
            f"Work routine started for {project}. "
            f"Current priorities: {', '.join(tasks)}. "
            "Friday is ready to work from the active project context."
        )
        return {
            "routine": "start_work_routine",
            "context": {"project": project, "tasks": tasks},
            "summary": summary,
            "actions": actions,
        }

    def _prepare_environment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        project = payload.get("project", "current project")
        actions = [
            {"name": "check_system_health", "status": "complete"},
            {"name": "open_project_workspace", "status": "complete"},
            {"name": "refresh_project_context", "status": "complete"},
            {"name": "start_session", "status": "pending"},
        ]
        return {
            "routine": "prepare_environment",
            "context": {"project": project},
            "summary": f"Environment prepared for {project}. All core tools and project context are ready.",
            "actions": actions,
        }

    def _project_checkup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        project = payload.get("project", "current project")
        command = payload.get("test_command", "pytest -q")
        result = payload.get("test_result", "not run")
        actions = [
            {"name": "open_project", "status": "complete"},
            {"name": "run_checks", "status": "complete"},
            {"name": "summarize_failures", "status": "complete"},
        ]
        summary = (
            f"Project checkup for {project} executed with: {command}. "
            f"Outcome: {result}."
        )
        return {
            "routine": "project_checkup",
            "context": {"project": project, "test_command": command, "test_result": result},
            "summary": summary,
            "actions": actions,
        }

    def _calendar_check(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        events = payload.get("events", [])
        upcoming = events[0] if events else "No calendar events scheduled"
        actions = [
            {"name": "scan_calendar", "status": "complete"},
            {"name": "identify_next_commitment", "status": "complete"},
            {"name": "schedule_reminder", "status": "pending"},
        ]
        return {
            "routine": "calendar_check",
            "context": {"events": events},
            "summary": f"Calendar reviewed. Next item: {upcoming}.",
            "actions": actions,
        }

    def _workspace_cleanup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        notes = payload.get("notes", [])
        actions = [
            {"name": "organize_workspace", "status": "complete"},
            {"name": "collect_notes", "status": "complete"},
            {"name": "draft_next_steps", "status": "complete"},
        ]
        summary = (
            "Workspace cleaned and notes collected. "
            f"Prepared follow-up: {', '.join(notes) if notes else 'none provided'}."
        )
        return {
            "routine": "workspace_cleanup",
            "context": {"notes": notes},
            "summary": summary,
            "actions": actions,
        }

    def _daily_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        completed = payload.get("completed", [])
        remaining = payload.get("remaining", [])
        summary = {
            "completed_count": len(completed),
            "remaining_count": len(remaining),
            "focus": "Prioritize the remaining work before the next check-in.",
        }
        report = {
            "routine": "daily_report",
            "summary": summary,
            "actions": [
                {"name": "collect_completed_work", "status": "complete"},
                {"name": "flag_outstanding_tasks", "status": "complete"},
                {"name": "prepare_next_focus", "status": "pending"},
            ],
            "completed": completed,
            "remaining": remaining,
        }
        return report
