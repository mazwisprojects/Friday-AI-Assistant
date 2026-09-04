"""Always-on, human-governed supervisor for Friday's safe autonomous work."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SupervisorReport:
    observations: list[str] = field(default_factory=list)
    notifications: list[dict] = field(default_factory=list)
    approvals_needed: list[dict] = field(default_factory=list)


class AutonomySupervisor:
    """Correlates runtime state and emits bounded actions without bypassing approval."""

    def __init__(self, task_manager, dispatcher, scheduler, system_monitor, notify: Callable, learning=None, pipeline=None):
        self.task_manager = task_manager
        self.dispatcher = dispatcher
        self.scheduler = scheduler
        self.system_monitor = system_monitor
        self.notify = notify
        self.learning = learning
        self.pipeline = pipeline
        self._last_alert: dict[str, float] = {}
        self._last_audit = 0.0

    def inspect(self) -> SupervisorReport:
        report = SupervisorReport()
        self._observe_tasks(report)
        self._observe_agents(report)
        self._observe_system(report)
        self._observe_schedules(report)
        self._observe_learning(report)
        return report

    def _observe_learning(self, report: SupervisorReport) -> None:
        if not self.learning and not self.pipeline:
            return
        result = self.pipeline.run_cycle() if self.pipeline and time.monotonic() - self._last_audit >= 900 else (self.learning.inspect() if self.learning else {})
        if self.pipeline:
            self._last_audit = time.monotonic()
        if result["proposals"]:
            report.approvals_needed.extend(result["proposals"])
            report.observations.append(f"{len(result['proposals'])} capability proposal(s) await review")
        if result["security"]:
            report.approvals_needed.extend(result["security"])
            report.observations.append(f"{len(result['security'])} security regression finding(s) need review")
        if result["expired"]:
            report.observations.append(f"{len(result['expired'])} capability lease(s) expired")

    def _observe_tasks(self, report: SupervisorReport) -> None:
        overdue = self.task_manager.overdue()
        if overdue:
            report.observations.append(f"{len(overdue)} task(s) are overdue")
            self._notify_once(report, "overdue_tasks", "Overdue tasks", f"{len(overdue)} task(s) need attention.", "high")

    def _observe_agents(self, report: SupervisorReport) -> None:
        agents = self.dispatcher.list_agents()
        failed = [agent for agent in agents if agent.get("status") == "failed"]
        if failed:
            report.observations.append(f"{len(failed)} background agent(s) failed")
            self._notify_once(report, "failed_agents", "Agent failure", f"{failed[-1].get('agent_type', 'Background agent')} failed. Review execution history.", "high")

    def _observe_system(self, report: SupervisorReport) -> None:
        try:
            status = self.system_monitor.check()
        except Exception as error:
            report.observations.append(f"System monitor unavailable: {error}")
            return
        if status:
            report.observations.append(status)
            self._notify_once(report, "system_health", "System health", status, "high")

    def _observe_schedules(self, report: SupervisorReport) -> None:
        enabled = [item for item in self.scheduler.list() if item.get("enabled")]
        report.observations.append(f"{len(enabled)} scheduled workflow(s) enabled")
        disabled = [item for item in self.scheduler.list() if not item.get("enabled")]
        if disabled:
            report.observations.append(f"{len(disabled)} scheduled workflow(s) disabled")

    def request_approval(self, action: str, reason: str, details: Any = None) -> dict:
        approval = {"action": action, "reason": reason, "details": details}
        return approval

    def _notify_once(self, report: SupervisorReport, key: str, title: str, message: str, priority: str = "normal") -> None:
        now = time.monotonic()
        if now - self._last_alert.get(key, 0) < 900:
            return
        self._last_alert[key] = now
        report.notifications.append({"category": "autonomy", "title": title, "message": message, "priority": priority})
