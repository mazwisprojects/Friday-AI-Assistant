from actions import send_message


def test_send_message_requires_receiver():
    result = send_message.send_message({"receiver": "", "message_text": "hi"})

    assert "specify a recipient" in result.lower()


def test_send_message_requires_message_text():
    result = send_message.send_message({"receiver": "Jane", "message_text": ""})

    assert "specify the message" in result.lower()


def test_send_message_reports_missing_pyautogui(monkeypatch):
    monkeypatch.setattr(send_message, "_PYAUTOGUI", False)

    result = send_message.send_message({"receiver": "Jane", "message_text": "hi"})

    assert "pyautogui is not installed" in result.lower()


def test_resolve_platform_matches_whatsapp_keywords():
    handler = send_message._resolve_platform("whatsapp")

    assert handler is send_message._send_whatsapp


def test_resolve_platform_matches_telegram_alias():
    handler = send_message._resolve_platform("tg")

    assert handler is send_message._send_telegram


def test_resolve_platform_falls_back_to_desktop_send_for_unknown_platform():
    handler = send_message._resolve_platform("SomeApp")

    assert handler is not send_message._send_whatsapp
    assert handler is not send_message._send_telegram


def test_send_message_dispatches_to_resolved_platform_handler(monkeypatch):
    calls = []

    def fake_handler(receiver, message):
        calls.append((receiver, message))
        return f"Message sent to {receiver} via FakePlatform."

    monkeypatch.setattr(send_message, "_PYAUTOGUI", True)
    monkeypatch.setattr(send_message, "_resolve_platform", lambda platform: fake_handler)

    result = send_message.send_message({
        "receiver": "Jane",
        "message_text": "hello",
        "platform": "whatsapp",
    })

    assert calls == [("Jane", "hello")]
    assert "Message sent to Jane" in result
