import json

from backend.google_account import GoogleAccount


def test_old_google_token_is_marked_for_reauthorization(tmp_path, monkeypatch):
    token = {
        "token": "expired-token",
        "refresh_token": "refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "scopes": ["openid"],
    }
    (tmp_path / "google_token.json").write_text(json.dumps(token), encoding="utf-8")
    account = GoogleAccount(str(tmp_path))

    assert account.credentials is None
    assert account.reauthorization_required is True
    assert "reconnect" in account.status()["error"].lower()