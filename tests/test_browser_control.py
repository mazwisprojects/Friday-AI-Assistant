from actions import browser_control


def test_browser_control_switch_requires_target():
    result = browser_control.browser_control({"action": "switch"})

    assert "please specify a browser" in result.lower()


def test_browser_control_list_browsers_reports_none_active():
    result = browser_control.browser_control({"action": "list_browsers"})

    assert "no active browser sessions" in result.lower()


def test_browser_control_close_without_target_reports_error(monkeypatch):
    monkeypatch.setattr(browser_control._registry, "_active_browser", None)

    result = browser_control.browser_control({"action": "close"})

    assert "no browser specified" in result.lower()


def test_browser_control_search_without_session_uses_native_open(monkeypatch):
    monkeypatch.setattr(browser_control._registry, "has", lambda browser: False)
    calls = []
    monkeypatch.setattr(browser_control, "_open_native", lambda url, browser: calls.append(url) or "Opened search page.")
    monkeypatch.setattr(browser_control._registry, "note_native_url", lambda url: None)

    result = browser_control.browser_control({"action": "search", "query": "python tutorials"})

    assert result == "Opened search page."
    assert calls
