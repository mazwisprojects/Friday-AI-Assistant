from actions import computer_control


def test_computer_control_requires_action():
    result = computer_control.computer_control({"action": ""})

    assert "no action specified" in result.lower()


def test_computer_control_wait_action_sleeps_and_confirms(monkeypatch):
    calls = []
    monkeypatch.setattr(computer_control.time, "sleep", lambda seconds: calls.append(seconds))

    result = computer_control.computer_control({"action": "wait", "seconds": 2})

    assert calls == [2]
    assert "wait" in result.lower() or "2" in result


def test_computer_control_type_action_uses_type_helper(monkeypatch):
    monkeypatch.setattr(computer_control, "_type", lambda text: f"Typed: {text}")

    result = computer_control.computer_control({"action": "type", "text": "hello"})

    assert "Typed: hello" in result


def test_computer_control_unknown_action_reports_error():
    result = computer_control.computer_control({"action": "not_a_real_action"})

    assert "unknown" in result.lower() or "not" in result.lower()
