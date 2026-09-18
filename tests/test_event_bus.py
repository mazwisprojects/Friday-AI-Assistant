"""Tests for the central application event bus."""
import asyncio
import pytest
from backend.event_bus import FridayEvent, FridayEventBus, get_event_bus


class TestFridayEvent:
    def test_create_event(self):
        event = FridayEvent(topic="test", payload={"key": "value"})
        assert event.topic == "test"
        assert event.payload["key"] == "value"
        assert event.id
        assert event.priority == "info"


class TestFridayEventBus:
    def test_publish_and_stats(self):
        bus = FridayEventBus()
        event = FridayEvent(topic="test", payload={"a": 1})
        assert bus.publish(event) is True
        assert bus.published_count == 1
        assert bus.stats()["published"] == 1

    def test_publish_simple(self):
        bus = FridayEventBus()
        assert bus.publish_simple("news.updated", {"count": 5}) is True

    def test_subscribe_and_receive(self):
        bus = FridayEventBus()
        received = []
        bus.subscribe("test", lambda e: received.append(e))
        bus.publish_simple("test", {"x": 1})
        assert len(received) == 1
        assert received[0].payload["x"] == 1

    def test_unsubscribe(self):
        bus = FridayEventBus()
        received = []
        unsub = bus.subscribe("test", lambda e: received.append(e))
        bus.publish_simple("test")
        assert len(received) == 1
        unsub()
        bus.publish_simple("test")
        assert len(received) == 1  # No new event received

    def test_dedupe(self):
        bus = FridayEventBus(cooldown_seconds=60)
        bus.publish_simple("test", dedupe_key="same")
        bus.publish_simple("test", dedupe_key="same")
        assert bus.published_count == 1
        assert bus.suppressed_count == 1

    def test_close(self):
        bus = FridayEventBus()
        bus.close()
        assert bus.publish(FridayEvent(topic="x")) is False

    @pytest.mark.asyncio
    async def test_drain(self):
        bus = FridayEventBus()
        results = []

        async def handler(event):
            results.append(event)

        async def run():
            task = asyncio.create_task(bus.drain(handler))
            bus.publish_simple("test", {"val": 42})
            await asyncio.sleep(0.01)
            bus.close()
            await task

        await run()
        assert len(results) == 1
        assert results[0].payload["val"] == 42


class TestGetEventBus:
    def test_singleton(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2
