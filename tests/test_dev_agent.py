from actions import dev_agent


def test_dev_agent_requires_description():
    result = dev_agent.dev_agent({"description": ""})

    assert "describe the project" in result.lower()


def test_dev_agent_delegates_to_build_project(monkeypatch):
    calls = []

    def fake_build_project(**kwargs):
        calls.append(kwargs)
        return "Project built successfully."

    monkeypatch.setattr(dev_agent, "_build_project", fake_build_project)

    result = dev_agent.dev_agent({
        "description": "a simple calculator app",
        "language": "python",
        "project_name": "calc",
    })

    assert result == "Project built successfully."
    assert calls[0]["description"] == "a simple calculator app"
    assert calls[0]["language"] == "python"
    assert calls[0]["project_name"] == "calc"
