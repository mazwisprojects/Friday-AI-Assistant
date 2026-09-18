from system_prompt import CHAR_BUDGET, build_system_prompt


def test_prompt_preserves_required_sections_with_large_runtime_input():
    capabilities = [
        {"name": f"runtime_tool_{index}", "description": "runtime capability " * 20}
        for index in range(50)
    ]
    prompt = build_system_prompt(
        capabilities=capabilities,
        extra_context="runtime context " * 5000,
    )

    assert len(prompt) <= CHAR_BUDGET
    for section in ("IDENTITY:", "OWNER IDENTITY", "RELATIONSHIP:", "VOICE (this is a live, spoken conversation):", "VISION:", "COGNITION:", "EPISTEMICS:", "MEMORY:", "SAFETY:"):
        assert section in prompt


def test_prompt_includes_runtime_capability_description():
    prompt = build_system_prompt(
        capabilities=[{"name": "inspect_current_view", "description": "Inspect the current camera frame."}],
    )

    assert "inspect_current_view: Inspect the current camera frame." in prompt
