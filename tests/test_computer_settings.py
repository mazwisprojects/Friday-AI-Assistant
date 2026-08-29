from actions import computer_settings


def test_computer_settings_requires_pyautogui(monkeypatch):
    monkeypatch.setattr(computer_settings, "_PYAUTOGUI", False)

    result = computer_settings.computer_settings({"action": "volume_up"})

    assert "pyautogui is not installed" in result.lower()


def test_computer_settings_no_action_reports_error(monkeypatch):
    monkeypatch.setattr(computer_settings, "_PYAUTOGUI", True)

    result = computer_settings.computer_settings({"action": ""})

    assert "no action could be determined" in result.lower()


def test_computer_settings_volume_set_uses_helper(monkeypatch):
    monkeypatch.setattr(computer_settings, "_PYAUTOGUI", True)
    calls = []
    monkeypatch.setattr(computer_settings, "volume_set", lambda value: calls.append(value))

    result = computer_settings.computer_settings({"action": "volume_set", "value": 42})

    assert calls == [42]
    assert "42" in result


def test_computer_settings_dangerous_action_requires_confirmation(monkeypatch):
    monkeypatch.setattr(computer_settings, "_PYAUTOGUI", True)
    monkeypatch.setattr(computer_settings, "_DANGEROUS_ACTIONS", {"shutdown"})

    result = computer_settings.computer_settings({"action": "shutdown"})

    assert "confirm" in result.lower()
