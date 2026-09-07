from autonomy_supervisor import AutonomySupervisor


class FakeTasks:
    def overdue(self):
        return []


class FakeDispatcher:
    def __init__(self, agents=None):
        self._agents = agents or []

    def list_agents(self):
        return self._agents


class FakeSystemMonitor:
    def check(self):
        return None


class FakeScheduler:
    def __init__(self, schedules):
        self._schedules = schedules

    def list(self):
        return self._schedules


def test_auto_disabled_schedule_is_notified_once():
    schedules = [{
        "id": "sched-1", "key": "email_triage", "agent_type": "email_triage_agent",
        "enabled": False, "last_status": "failed", "retry_count": 4, "max_retries": 3,
        "last_error": "boom",
    }]
    supervisor = AutonomySupervisor(FakeTasks(), FakeDispatcher(), FakeScheduler(schedules), FakeSystemMonitor(), notify=None)

    first = supervisor.inspect()
    second = supervisor.inspect()

    disabled_notifications = [item for item in first.notifications if item["category"] == "schedule_disabled"]
    assert len(disabled_notifications) == 1
    assert "email_triage" in disabled_notifications[0]["message"]
    assert not [item for item in second.notifications if item["category"] == "schedule_disabled"]


def test_manually_disabled_schedule_is_not_reported_as_failure():
    schedules = [{
        "id": "sched-2", "key": "printer_monitor", "agent_type": "printer_monitor_agent",
        "enabled": False, "last_status": "never_run", "retry_count": 0, "max_retries": 3,
    }]
    supervisor = AutonomySupervisor(FakeTasks(), FakeDispatcher(), FakeScheduler(schedules), FakeSystemMonitor(), notify=None)

    report = supervisor.inspect()

    assert not [item for item in report.notifications if item["category"] == "schedule_disabled"]


def test_dependency_audit_findings_are_notified_once():
    agents = [{
        "id": "audit-1", "agent_type": "dependency_audit_agent", "status": "done",
        "result": {"needs_attention": True, "summary": "3 outdated Python package(s) found."},
    }]
    dispatcher = FakeDispatcher(agents)
    supervisor = AutonomySupervisor(FakeTasks(), dispatcher, FakeScheduler([]), FakeSystemMonitor(), notify=None)

    first = supervisor.inspect()
    second = supervisor.inspect()

    audit_notifications = [item for item in first.notifications if item["category"] == "dependency_audit"]
    assert len(audit_notifications) == 1
    assert "outdated" in audit_notifications[0]["message"]
    assert not [item for item in second.notifications if item["category"] == "dependency_audit"]


def test_dependency_audit_with_no_findings_is_not_notified():
    agents = [{
        "id": "audit-2", "agent_type": "dependency_audit_agent", "status": "done",
        "result": {"needs_attention": False, "summary": "Nothing outdated."},
    }]
    dispatcher = FakeDispatcher(agents)
    supervisor = AutonomySupervisor(FakeTasks(), dispatcher, FakeScheduler([]), FakeSystemMonitor(), notify=None)

    report = supervisor.inspect()

    assert not [item for item in report.notifications if item["category"] == "dependency_audit"]
