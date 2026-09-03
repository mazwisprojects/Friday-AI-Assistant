"""Tests for Friday's live vision (continuous webcam streaming to the Gemini Live session)."""
import asyncio
import time

import pytest

from friday import AudioLoop, VIDEO_SEND_INTERVAL


@pytest.fixture
def audio_loop():
    loop = AudioLoop(authenticated=True)
    yield loop


class FakeSession:
    """Stands in for a Gemini Live session; records incoming send() payloads."""

    def __init__(self):
        self.sent = []

    async def send(self, input, end_of_turn=True):
        data = input.get("data", input) if isinstance(input, dict) else input
        self.sent.append(data)


# ── set_live_video ───────────────────────────────────────────────────────


def test_live_video_disabled_by_default(audio_loop):
    assert audio_loop.live_video_enabled is False
    assert audio_loop._last_sent_image_data is None
    assert audio_loop._latest_image_payload is None


def test_set_live_video_toggles_flag(audio_loop):
    audio_loop.set_live_video(True)
    assert audio_loop.live_video_enabled is True

    audio_loop.set_live_video(False)
    assert audio_loop.live_video_enabled is False


def test_set_live_video_disabled_resets_dedup_state(audio_loop):
    audio_loop.live_video_enabled = True
    audio_loop._last_sent_image_data = "abc123"

    audio_loop.set_live_video(False)

    assert audio_loop.live_video_enabled is False
    assert audio_loop._last_sent_image_data is None


# ── _should_send_video_frame ─────────────────────────────────────────────


def test_should_send_requires_session(audio_loop):
    audio_loop.live_video_enabled = True
    audio_loop._latest_image_payload = {"mime_type": "image/jpeg", "data": "AAA"}
    audio_loop.session = None
    assert audio_loop._should_send_video_frame(time.monotonic()) is False


def test_should_send_requires_enabled(audio_loop):
    audio_loop.live_video_enabled = False
    audio_loop.session = object()
    audio_loop._latest_image_payload = {"mime_type": "image/jpeg", "data": "AAA"}
    assert audio_loop._should_send_video_frame(time.monotonic()) is False


def test_should_send_requires_frame_available(audio_loop):
    audio_loop.live_video_enabled = True
    audio_loop.session = object()
    audio_loop._latest_image_payload = None
    assert audio_loop._should_send_video_frame(time.monotonic()) is False


def test_should_send_true_when_ready(audio_loop):
    audio_loop.live_video_enabled = True
    audio_loop.session = object()
    audio_loop._latest_image_payload = {"mime_type": "image/jpeg", "data": "AAA"}
    assert audio_loop._should_send_video_frame(time.monotonic()) is True


def test_should_send_dedups_identical_frames(audio_loop):
    audio_loop.live_video_enabled = True
    audio_loop.session = object()
    audio_loop._latest_image_payload = {"mime_type": "image/jpeg", "data": "AAA"}
    audio_loop._last_sent_image_data = "AAA"
    assert audio_loop._should_send_video_frame(time.monotonic()) is False


def test_should_send_respects_min_interval(audio_loop):
    audio_loop.live_video_enabled = True
    audio_loop.session = object()
    audio_loop._latest_image_payload = {"mime_type": "image/jpeg", "data": "AAA"}
    audio_loop._last_sent_image_data = "OLD"
    audio_loop._last_video_sent_time = time.monotonic()  # just sent
    # Even with a brand-new frame, we must wait out the Live-API image interval.
    assert audio_loop._should_send_video_frame(time.monotonic()) is False
    assert VIDEO_SEND_INTERVAL >= 1.0  # Gemini Live: max 1 image/second


def test_should_send_true_after_interval_elapsed(audio_loop):
    audio_loop.live_video_enabled = True
    audio_loop.session = object()
    audio_loop._latest_image_payload = {"mime_type": "image/jpeg", "data": "AAA"}
    audio_loop._last_sent_image_data = "OLD"
    audio_loop._last_video_sent_time = time.monotonic() - (VIDEO_SEND_INTERVAL + 0.1)
    assert audio_loop._should_send_video_frame(time.monotonic()) is True


def test_should_send_respects_pause(audio_loop):
    audio_loop.live_video_enabled = True
    audio_loop.session = object()
    audio_loop._latest_image_payload = {"mime_type": "image/jpeg", "data": "AAA"}
    audio_loop.paused = True
    assert audio_loop._should_send_video_frame(time.monotonic()) is False


# ── _send_live_video loop ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_live_video_forwards_new_frames(audio_loop):
    audio_loop.live_video_enabled = True
    audio_loop.session = FakeSession()
    audio_loop._latest_image_payload = {"mime_type": "image/jpeg", "data": "AAA"}
    audio_loop._last_video_sent_time = time.monotonic() - (VIDEO_SEND_INTERVAL + 1)

    task = asyncio.create_task(audio_loop._send_live_video())
    try:
        # New frame is forwarded.
        await asyncio.sleep(0.4)
        assert audio_loop.session.sent == ["AAA"]
        assert audio_loop._last_sent_image_data == "AAA"

        # Byte-identical frame is deduped and NOT resent.
        audio_loop.session.sent.clear()
        audio_loop._latest_image_payload = {"mime_type": "image/jpeg", "data": "AAA"}
        audio_loop._last_video_sent_time = time.monotonic() - (VIDEO_SEND_INTERVAL + 1)
        await asyncio.sleep(0.4)
        assert audio_loop.session.sent == []

        # A genuinely new frame is forwarded.
        audio_loop.session.sent.clear()
        audio_loop._latest_image_payload = {"mime_type": "image/jpeg", "data": "BBB"}
        audio_loop._last_video_sent_time = time.monotonic() - (VIDEO_SEND_INTERVAL + 1)
        await asyncio.sleep(0.4)
        assert audio_loop.session.sent == ["BBB"]
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_send_live_video_quiet_when_disabled(audio_loop):
    audio_loop.live_video_enabled = False
    audio_loop.session = FakeSession()
    audio_loop._latest_image_payload = {"mime_type": "image/jpeg", "data": "AAA"}

    task = asyncio.create_task(audio_loop._send_live_video())
    try:
        await asyncio.sleep(0.4)
        assert audio_loop.session.sent == []

        # Enabling mid-flight starts forwarding.
        audio_loop.set_live_video(True)
        await asyncio.sleep(0.4)
        assert audio_loop.session.sent == ["AAA"]
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_send_live_video_quiet_when_no_session(audio_loop):
    audio_loop.live_video_enabled = True
    audio_loop.session = None
    audio_loop._latest_image_payload = {"mime_type": "image/jpeg", "data": "AAA"}

    task = asyncio.create_task(audio_loop._send_live_video())
    try:
        await asyncio.sleep(0.3)
        # Nothing to send into until a session exists.
        assert audio_loop._latest_image_payload is not None
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
