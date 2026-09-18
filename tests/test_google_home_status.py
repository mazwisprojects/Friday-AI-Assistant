from backend.google_home import GoogleHomeBridge


class FakeCredentials:
    valid = True


class FakeAccount:
    credentials = FakeCredentials()


def test_google_home_status_does_not_raise_when_api_is_unavailable(monkeypatch):
    bridge = GoogleHomeBridge(FakeAccount())

    def unavailable_service():
        raise RuntimeError("insufficient authentication scopes")

    monkeypatch.setattr(bridge, "_smart_home_service", unavailable_service)

    status = bridge.status()

    assert status["connected"] is True
    assert status["ready"] is False
    assert status["device_count"] == 0
    assert "insufficient authentication scopes" in status["error"]