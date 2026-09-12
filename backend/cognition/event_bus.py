"""
Cognitive Event Bus for F.R.I.D.A.Y — background brain → live voice bridge (P4.1).

Background cognition (threat scans, approval escalations, swarm completions)
runs on timers and background tasks; the Live voice session is a single
connection that only exists while connected. This bus is the bridge:

- Producers publish from anywhere in the event loop without blocking.
- The session consumer (friday.drain_cognitive_events) drains events and only
  speaks the ones worth interrupting for; 'info' events are logged for
  observability without chatter.
- The bus is process-wide (get_bus()), so it survives Live reconnects: events
  published while offline simply wait in the bounded queue for the next
  session's drain task.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class CognitiveEvent:
    """One background-cognition event headed for the live session (or the log)."""
    topic: str                     # threat | approval_needed | swarm_result | opportunity | custom
    summary: str                   # one human-readable line, safe to speak verbatim
    priority: str = "info"         # info | important | urgent
    payload: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str = ""           # same key within cooldown window -> suppressed
    created_ts: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


class CognitiveEventBus:
    """Bounded, non-blocking pub/sub connecting background cognition to the voice loop.

    Design rules:
    - publish() NEVER blocks or raises. When the queue is full the OLDEST pending
      event is dropped (keep-newest) so a chatty background can never stall the brain.
    - Cooldown dedupe: events sharing a dedupe_key are suppressed within the window
      so recurring sensors don't make Friday repeat herself every scan.
    - drain() consumes until close(); handler exceptions never kill the consumer.
    - Thread producers should marshal through loop.call_soon_threadsafe(bus.publish, ev).
    """

    def __init__(self, maxsize: int = 64, cooldown_seconds: float = 600.0):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers: list[Callable[[CognitiveEvent], Any]] = []
        self._recent: dict[str, float] = {}
        self._cooldown = float(cooldown_seconds)
        self._closed = False
        self.published_count = 0
        self.dropped_count = 0
        self.suppressed_count = 0

    # ---------- producers ----------

    def publish(self, event: CognitiveEvent) -> bool:
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
            # opportunistic GC so the dedupe map can't grow unbounded
            if len(self._recent) > 512:
                cutoff = now - max(self._cooldown * 8, 600.0)
                self._recent = {k: t for k, t in self._recent.items() if t >= cutoff}
        if self._queue.full():
            try:
                self._queue.get_nowait()
                self.dropped_count += 1
            except asyncio.QueueEmpty:
                pass
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            self.dropped_count += 1
            return False
        self.published_count += 1
        for cb in list(self._subscribers):
            try:
                result = cb(event)
                if asyncio.iscoroutine(result):
                    asyncio.get_running_loop().create_task(result)
            except Exception:
                logger.debug("cognitive event subscriber failed", exc_info=True)
        return True

    def subscribe(self, callback: Callable[[CognitiveEvent], Any]) -> Callable[[], None]:
        """Fan-out on publish (sync or async callback). Returns an unsubscribe fn."""
        self._subscribers.append(callback)

        def _unsubscribe() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return _unsubscribe

    # ---------- consumers ----------

    def pending(self) -> list[CognitiveEvent]:
        """Snapshot of queued events without consuming (flush-on-reconnect)."""
        items: list[CognitiveEvent] = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        for event in items:
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                self.dropped_count += 1
                break
        return items

    async def drain(self, handler: Callable[[CognitiveEvent], Any]) -> None:
        """Consume events forever, awaiting handler(event) for each.

        Exits when close() is called or the enclosing task is cancelled.
        Handler exceptions are logged, never propagated.
        """
        while True:
            event = await self._queue.get()
            if event is None:          # close() sentinel
                break
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug("cognitive event handler failed", exc_info=True)

    def close(self) -> None:
        """Stop accepting events and unblock drain()."""
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
            "closed": self._closed,
        }


_BUS: Optional[CognitiveEventBus] = None


def get_bus() -> CognitiveEventBus:
    """Process-wide bus. Survives Live reconnects: the cognition core re-attaches
    to the same instance each session, so events published while offline are
    still delivered when the next drain task starts."""
    global _BUS
    if _BUS is None:
        _BUS = CognitiveEventBus()
    return _BUS