from action_policy import decision


def test_power_actions_always_require_confirmation():
    assert decision("computer_settings", {"action": "shutdown"})["tier"] == "always_confirm"
    assert decision("game_updater", {"shutdown_when_done": True})["tier"] == "always_confirm"


def test_external_mutations_require_approval():
    assert decision("send_message")["tier"] == "approval_required"
    assert decision("google_calendar_create")["tier"] == "approval_required"
    assert decision("self_maintenance", {"action": "self_upgrade"})["tier"] == "always_confirm"


def test_bounded_reads_are_automatic():
    assert decision("gmail_read")["tier"] == "automatic"
    assert decision("get_system_status")["tier"] == "automatic"
