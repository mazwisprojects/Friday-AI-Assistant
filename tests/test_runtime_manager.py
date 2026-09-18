import asyncio

from backend.runtime_manager import RuntimeManager


class FakeRuntime:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


def test_runtime_manager_keeps_device_sessions_isolated():
    async def scenario():
        manager = RuntimeManager()
        desktop = FakeRuntime()
        phone = FakeRuntime()
        desktop_task = asyncio.create_task(asyncio.sleep(60))
        phone_task = asyncio.create_task(asyncio.sleep(60))

        manager.add("desktop", "desktop", desktop, desktop_task)
        manager.add("phone", "android", phone, phone_task)

        assert manager.get("desktop").audio_loop is desktop
        assert manager.get("phone").audio_loop is phone
        assert manager.stop("phone") is True
        assert phone.stopped is True
        assert desktop.stopped is False
        assert manager.get("desktop") is not None
        assert manager.get("phone") is None
        desktop_task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await desktop_task

    asyncio.run(scenario())


def test_desktop_and_phone_can_run_independent_sessions():
    async def scenario():
        manager = RuntimeManager()
        desktop_runtime = FakeRuntime()
        phone_runtime = FakeRuntime()
        desktop_task = asyncio.create_task(asyncio.sleep(60))
        phone_task = asyncio.create_task(asyncio.sleep(60))

        manager.add("desktop", "desktop", desktop_runtime, desktop_task)
        manager.add("android-phone", "android", phone_runtime, phone_task)

        assert {runtime.device_id for runtime in manager.all()} == {"desktop", "android-phone"}
        assert manager.get("desktop").device_type == "desktop"
        assert manager.get("android-phone").device_type == "android"
        assert manager.get("desktop").audio_loop is not manager.get("android-phone").audio_loop

        assert manager.stop("android-phone") is True
        assert phone_runtime.stopped is True
        assert desktop_runtime.stopped is False
        assert manager.get("desktop") is not None

        desktop_task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await desktop_task

    asyncio.run(scenario())