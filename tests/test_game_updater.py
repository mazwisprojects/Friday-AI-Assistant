from actions import game_updater


def test_game_updater_schedule_action_uses_helper(monkeypatch):
    calls = []
    monkeypatch.setattr(game_updater, "_schedule_daily_update", lambda hour, minute: calls.append((hour, minute)) or "Scheduled.")

    result = game_updater.game_updater({"action": "schedule", "hour": 4, "minute": 30})

    assert calls == [(4, 30)]
    assert result == "Scheduled."


def test_game_updater_cancel_schedule_uses_helper(monkeypatch):
    monkeypatch.setattr(game_updater, "_cancel_scheduled_update", lambda: "Cancelled.")

    result = game_updater.game_updater({"action": "cancel_schedule"})

    assert result == "Cancelled."


def test_game_updater_list_reports_steam_not_installed(monkeypatch):
    monkeypatch.setattr(game_updater, "_find_steam_path", lambda: None)

    result = game_updater.game_updater({"action": "list", "platform": "steam"})

    assert "steam: not installed" in result.lower()


def test_game_updater_download_status_reports_steam_not_installed(monkeypatch):
    monkeypatch.setattr(game_updater, "_find_steam_path", lambda: None)

    result = game_updater.game_updater({"action": "download_status", "platform": "steam"})

    assert "steam: not installed" in result.lower()
