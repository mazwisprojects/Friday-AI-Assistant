"""Unified notification delivery with cooldowns and multiple output channels."""

from __future__ import annotations

import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class NotificationManager:
    def __init__(self, on_hud=None, on_voice=None, desktop_enabled=True, cooldown_seconds=900):
        self.on_hud = on_hud
        self.on_voice = on_voice
        self.desktop_enabled = desktop_enabled
        self.cooldown_seconds = cooldown_seconds
        self._last_sent = defaultdict(float)

    async def notify(self, category: str, title: str, message: str, priority: str = "normal") -> bool:
        key = f"{category}:{title}:{message}"
        now = time.monotonic()
        if now - self._last_sent[key] < self.cooldown_seconds:
            return False
        self._last_sent[key] = now
        event = {"category": category, "title": title, "message": message, "priority": priority}
        if self.on_hud:
            result = self.on_hud(event)
            if hasattr(result, "__await__"):
                await result
        if self.desktop_enabled:
            self._desktop_notify(title, message)
        if self.on_voice:
            result = self.on_voice(message, priority)
            if hasattr(result, "__await__"):
                await result
        return True

    @staticmethod
    def _desktop_notify(title: str, message: str) -> None:
        try:
            from plyer import notification
            # Windows NOTIFYICONDATAW caps the title at 63 and the body at 256
            # characters. Longer strings raise ValueError inside plyer's own
            # notification thread, where no except can catch them, so clip
            # before calling.
            notification.notify(
                title=f"FRIDAY | {title}"[:63],
                message=str(message)[:250],
                timeout=10,
            )
        except Exception as exc:
            logger.warning("Desktop notification unavailable: %s", exc)
