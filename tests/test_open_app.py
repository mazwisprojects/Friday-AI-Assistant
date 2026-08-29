from actions import open_app


def test_open_app_requires_app_name():
    result = open_app.open_app({"app_name": ""})

    assert "no application name" in result.lower()


def test_open_app_reports_unsupported_os(monkeypatch):
    monkeypatch.setattr(open_app, "_SYSTEM", "PlanNine")

    result = open_app.open_app({"app_name": "chrome"})

    assert "unsupported operating system" in result.lower()


def test_open_app_returns_success_message_when_launcher_succeeds(monkeypatch):
    monkeypatch.setattr(open_app, "_OS_LAUNCHERS", {open_app._SYSTEM: lambda name: True})

    result = open_app.open_app({"app_name": "chrome"})

    assert "opened chrome" in result.lower()


def test_open_app_gives_web_alternative_hint_for_messaging_apps(monkeypatch):
    monkeypatch.setattr(open_app, "_OS_LAUNCHERS", {open_app._SYSTEM: lambda name: False})

    result = open_app.open_app({"app_name": "whatsapp"})

    assert "web instead" in result.lower()


def test_open_app_generic_failure_message_for_unknown_app(monkeypatch):
    monkeypatch.setattr(open_app, "_OS_LAUNCHERS", {open_app._SYSTEM: lambda name: False})

    result = open_app.open_app({"app_name": "SomeRandomApp"})

    assert "could not open somerandomapp" in result.lower()


def test_open_app_normalizes_known_aliases():
    normalized = open_app._normalize("google chrome")

    assert normalized == open_app._APP_ALIASES["chrome"][open_app._SYSTEM]
