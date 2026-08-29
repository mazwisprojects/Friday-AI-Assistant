from actions import desktop


def test_desktop_control_wallpaper_requires_path():
    result = desktop.desktop_control({"action": "wallpaper", "path": ""})

    assert "no image path provided" in result.lower()


def test_desktop_control_wallpaper_url_requires_url():
    result = desktop.desktop_control({"action": "wallpaper_url", "url": ""})

    assert "no url provided" in result.lower()


def test_desktop_control_wallpaper_calls_set_wallpaper(monkeypatch):
    calls = []
    monkeypatch.setattr(desktop, "set_wallpaper", lambda path: calls.append(path) or "Wallpaper set.")

    result = desktop.desktop_control({"action": "wallpaper", "path": "C:/images/wall.jpg"})

    assert calls == ["C:/images/wall.jpg"]
    assert result == "Wallpaper set."


def test_desktop_control_organize_uses_mode_parameter(monkeypatch):
    calls = []
    monkeypatch.setattr(desktop, "organize_desktop", lambda mode: calls.append(mode) or "Organized.")

    desktop.desktop_control({"action": "organize", "mode": "by_date"})

    assert calls == ["by_date"]


def test_desktop_control_task_without_description_asks_for_clarification(monkeypatch):
    result = desktop.desktop_control({"action": "task"})

    assert "describe what you want to do" in result.lower()
