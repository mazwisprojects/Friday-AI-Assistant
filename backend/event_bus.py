"""
Central Application Event Bus for F.R.I.D.A.Y.

Extends the cognitive event bus pattern into a process-wide, typed application
bus. Every subsystem (connectors, agents, supervisor, automation) publishes
here; consumers subscribe by topic. The bus is non-blocking, bounded, and
survives Live reconnects.

Topics:
    news.updated        - fresh news items ingested
    science.updated     - new science items
    weather.updated     - weather report ready
    device.discovered   - local device found
    device.paired       - companion device paired
    device.heartbeat    - companion heartbeat received
    memory.ingested     - new memory item stored
    knowledge.updated   - knowledge graph mutated
    briefing.ready      - daily briefing assembled
    anomaly.detected    - anomaly found
    automation.request  - automation task proposed
    automation.approved - automation task approved
    automation.completed - automation task finished
    system.health       - subsystem health snapshot
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class FridayEvent:
    """One application event."""
    topic: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: str = "info"
    dedupe_key: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: float = field(default_factory=time.time)


class FridayEventBus:
    """Process-wide, bounded, non-blocking pub/sub bus."""

    def __init__(self, maxsize: int = 128, cooldown_seconds: float = 300.0):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._recent: dict[str, float] = {}
        self._cooldown = float(cooldown_seconds)
        self._closed = False
        self.published_count = 0
        self.dropped_count = 0
        self.suppressed_count = 0

    def publish(self, event: FridayEvent) -> bool:
        """Publish without blocking. Returns True if accepted."""
        if self._closed or event is None:
            return False
        now = time.time()
        if event.dedupe_key:
            last = self._recent.get(event.dedupe_key)
            if last is not None and (now - last) < self._cooldown:
                self.suppressed_count += 1
                return False
            self._recent[event.dedupe_key] = now
            if len(self._recent) > 1024:
                cutoff = now - max(self._cooldown * 8, 600.0)
                self._recent = {k: t for k, t in self._recent.items() if t >= cutoff}
        if self._queue.full():
            try:
                self._queue.get_nowait()
                self.dropped_count += 1
                logger.debug("Bus queue full; dropped the oldest event (total dropped=%s)", self.dropped_count)
            except asyncio.QueueEmpty:
                pass
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            self.dropped_count += 1
            return False
        self.published_count += 1
        for cb in list(self._subscribers.get(event.topic, [])):
            try:
                result = cb(event)
                if asyncio.iscoroutine(result):
                    asyncio.get_running_loop().create_task(result)
            except Exception:
                logger.debug("event subscriber failed for %s", event.topic, exc_info=True)
        return True

    def publish_simple(self, topic: str, payload: dict[str, Any] | None = None,
                       priority: str = "info", dedupe_key: str = "") -> bool:
        """Convenience: build and publish in one call."""
        return self.publish(FridayEvent(
            topic=topic, payload=payload or {},
            priority=priority, dedupe_key=dedupe_key,
        ))


    def subscribe(self, topic: str, callback: Callable[[FridayEvent], Any]) -> Callable[[], None]:
        """Subscribe to a topic. Returns an unsubscribe fn."""
        self._subscribers[topic].append(callback)

        def _unsubscribe() -> None:
            if callback in self._subscribers.get(topic, []):
                self._subscribers[topic].remove(callback)

        return _unsubscribe

    def subscribers(self, topic: str) -> list[Callable]:
        return list(self._subscribers.get(topic, []))

    async def drain(self, handler: Callable[[FridayEvent], Any]) -> None:
        """Consume events forever, awaiting handler(event) for each."""
        while True:
            event = await self._queue.get()
            if event is None:
                break
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug("event handler failed", exc_info=True)

    def close(self) -> None:
        self._closed = True
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

    def stats(self) -> dict[str, Any]:
        return {
            "queued": self._queue.qsize(),
            "published": self.published_count,
            "dropped": self.dropped_count,
            "suppressed": self.suppressed_count,
            "topics": {t: len(cbs) for t, cbs in self._subscribers.items()},
            "closed": self._closed,
        }


_BUS: Optional[FridayEventBus] = None


def get_event_bus() -> FridayEventBus:
    """Process-wide bus instance."""
    global _BUS
    if _BUS is None:
        _BUS = FridayEventBus()
    return _BUS
