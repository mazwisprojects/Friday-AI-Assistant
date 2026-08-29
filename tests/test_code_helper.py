from actions import code_helper


def test_code_helper_write_action_delegates_to_write_helper(monkeypatch):
    calls = []
    monkeypatch.setattr(code_helper, "_write_action", lambda description, language, output_path, player: calls.append((description, language, output_path)) or "Code written.")

    result = code_helper.code_helper({
        "action": "write",
        "description": "a function that adds two numbers",
        "language": "python",
        "output_path": "add.py",
    })

    assert result == "Code written."
    assert calls == [("a function that adds two numbers", "python", "add.py")]


def test_code_helper_edit_action_delegates_to_edit_helper(monkeypatch):
    calls = []
    monkeypatch.setattr(code_helper, "_edit_action", lambda file_path, instruction, player: calls.append((file_path, instruction)) or "Code edited.")

    result = code_helper.code_helper({
        "action": "edit",
        "file_path": "main.py",
        "description": "add logging",
    })

    assert result == "Code edited."
    assert calls == [("main.py", "add logging")]


def test_code_helper_auto_detects_intent(monkeypatch):
    monkeypatch.setattr(code_helper, "_detect_intent", lambda description, file_path, code: "explain")
    monkeypatch.setattr(code_helper, "_explain_action", lambda file_path, code, player: "Explanation done.")

    result = code_helper.code_helper({"action": "auto", "description": "what does this do"})

    assert result == "Explanation done."
