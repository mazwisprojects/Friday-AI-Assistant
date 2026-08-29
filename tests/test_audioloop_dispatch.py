import asyncio

import pytest

from friday import AudioLoop


@pytest.fixture
def audio_loop():
    loop = AudioLoop(authenticated=True)
    yield loop


def test_start_action_plan_creates_steps_for_known_tool(audio_loop):
    audio_loop.start_action_plan("send_message", {})

    assert audio_loop._active_plan is not None
    assert audio_loop._active_plan["title"] == "SEND MESSAGE"
    assert audio_loop._active_plan["steps"][0]["status"] == "active"
    assert audio_loop._active_plan["steps"][1]["status"] == "pending"


def test_start_action_plan_ignores_unknown_tool(audio_loop):
    audio_loop.start_action_plan("some_unregistered_tool", {})

    assert audio_loop._active_plan is None


def test_update_plan_step_notifies_callback(audio_loop):
    updates = []
    audio_loop.on_plan_update = updates.append
    audio_loop.start_action_plan("send_message", {})

    audio_loop._update_plan_step(1, "active")

    assert updates
    assert updates[-1]["steps"][1]["status"] == "active"


def test_finish_action_plan_marks_all_steps_done_on_success(audio_loop):
    audio_loop.start_action_plan("send_message", {})

    audio_loop.finish_action_plan(success=True)

    assert audio_loop._active_plan is None


def test_finish_action_plan_marks_pending_steps_cancelled(audio_loop):
    audio_loop.start_action_plan("send_message", {})
    captured = {}

    def capture(plan):
        captured["plan"] = plan

    audio_loop.on_plan_update = capture
    audio_loop._active_plan_snapshot_before_finish = None

    # Re-create plan manually to inspect state right before it's cleared
    audio_loop._active_plan = {"title": "X", "steps": [
        {"label": "a", "status": "active"},
        {"label": "b", "status": "pending"},
    ]}
    audio_loop.finish_action_plan(success=False, cancelled=True)

    assert captured["plan"]["steps"][0]["status"] == "cancelled"
    assert captured["plan"]["steps"][1]["status"] == "cancelled"


def test_update_permissions_merges_new_values(audio_loop):
    audio_loop.update_permissions({"send_message": False})

    assert audio_loop.permissions["send_message"] is False


def test_set_paused_updates_flag(audio_loop):
    audio_loop.set_paused(True)

    assert audio_loop.paused is True


def test_resolve_tool_confirmation_sets_future_result():
    async def run_test():
        loop = AudioLoop(authenticated=True)
        future = asyncio.get_event_loop().create_future()
        loop._pending_confirmations["req-1"] = future

        loop.resolve_tool_confirmation("req-1", True)

        assert future.done()
        assert future.result() is True

    asyncio.run(run_test())


def test_resolve_tool_confirmation_ignores_unknown_request_id(audio_loop):
    # Should not raise even though the id was never registered.
    audio_loop.resolve_tool_confirmation("does-not-exist", True)


def test_cancel_pending_confirmations_resolves_all_as_denied():
    async def run_test():
        loop = AudioLoop(authenticated=True)
        future_one = asyncio.get_event_loop().create_future()
        future_two = asyncio.get_event_loop().create_future()
        loop._pending_confirmations["a"] = future_one
        loop._pending_confirmations["b"] = future_two

        loop.cancel_pending_confirmations()

        assert future_one.result() is False
        assert future_two.result() is False
        assert loop._pending_confirmations == {}

    asyncio.run(run_test())


def test_check_tool_preconditions_requires_authentication():
    loop = AudioLoop(authenticated=False)

    result = loop.check_tool_preconditions("read_file", {"path": "notes.txt"})

    assert result == "Authentication is required before using tools."


def test_check_tool_preconditions_requires_path_for_read_file(audio_loop):
    result = audio_loop.check_tool_preconditions("read_file", {"path": ""})

    assert "requires a file path" in result


def test_check_tool_preconditions_rejects_write_outside_project(audio_loop):
    result = audio_loop.check_tool_preconditions("write_file", {"path": "../../escape.txt"})

    assert "outside the active project" in result


def test_check_tool_preconditions_allows_write_inside_project(audio_loop):
    result = audio_loop.check_tool_preconditions("write_file", {"path": "notes.txt"})

    assert result is None


def test_check_tool_preconditions_requires_existing_file_for_process_file(audio_loop):
    result = audio_loop.check_tool_preconditions("process_file", {"file_path": "does_not_exist.xyz"})

    assert "not found" in result


def test_check_tool_preconditions_rejects_past_reminder_datetime(audio_loop):
    result = audio_loop.check_tool_preconditions("set_reminder", {"date": "2000-01-01", "time": "10:00"})

    assert "must be in the future" in result


def test_check_tool_preconditions_rejects_invalid_reminder_format(audio_loop):
    result = audio_loop.check_tool_preconditions("set_reminder", {"date": "not-a-date", "time": "10:00"})

    assert "valid date" in result
