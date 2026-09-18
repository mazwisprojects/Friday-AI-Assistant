"""
Daily briefing agent for F.R.I.D.A.Y.

Assembles a morning briefing from weather, news, tasks, calendar, and
system health. Can be triggered on a schedule or on demand.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from backend.models import DailyBriefing, BriefingItem

logger = logging.getLogger(__name__)


class DailyBriefingAgent:
    """Assemble and publish daily briefings."""

    def __init__(self, event_bus=None):
        self._bus = event_bus

    def _get_bus(self):
        if self._bus is None:
            from backend.event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    async def _fetch_weather(self, location: str) -> Optional[BriefingItem]:
        """Fetch weather for the briefing."""
        try:
            from backend.actions import weather_report as wr
            data = await asyncio.to_thread(wr.get_weather_data, location)
            return BriefingItem(
                category="weather", title=f"Weather in {data.get('city', location)}",
                content=data.get("summary", ""), items=[data],
            )
        except Exception as exc:
            logger.debug("Weather fetch failed: %s", exc)
            return None

    async def _fetch_news_summary(self) -> Optional[BriefingItem]:
        """Fetch top news for the briefing."""
        try:
            from backend.connectors import get_news_connector
            nc = get_news_connector()
            items = await asyncio.to_thread(nc.fetch_headlines, "bbc-news", 5)
            if items:
                return BriefingItem(
                    category="news", title="Top Headlines",
                    content=f"{len(items)} headline(s)",
                    items=[i.to_dict() for i in items],
                )
        except Exception as exc:
            logger.debug("News fetch failed: %s", exc)
        return None

    def _fetch_tasks(self, task_manager) -> Optional[BriefingItem]:
        """Fetch open tasks for the briefing."""
        try:
            open_tasks = task_manager.list("open")
            overdue = task_manager.overdue()
            if open_tasks or overdue:
                items = [{"title": t.get("title"), "due": t.get("due"),
                          "priority": t.get("priority"), "overdue": t in overdue}
                         for t in (open_tasks or [])]
                return BriefingItem(
                    category="tasks", title="Your Tasks",
                    content=f"{len(open_tasks)} open, {len(overdue)} overdue",
                    priority="high" if overdue else "normal", items=items,
                )
        except Exception as exc:
            logger.debug("Task fetch failed: %s", exc)
        return None

    async def _fetch_calendar(self, google_account) -> Optional[BriefingItem]:
        """Fetch upcoming calendar events."""
        try:
            status = google_account.status()
            if not status.get("connected"):
                logger.debug("Google account not connected, skipping calendar")
                return None
            events = await asyncio.to_thread(google_account.list_calendar_events, "", 5, 5)
            if events:
                return BriefingItem(
                    category="calendar", title="Upcoming Events",
                    content=f"{len(events)} event(s) today",
                    items=events,
                )
        except Exception as exc:
            logger.debug("Calendar fetch failed: %s", exc)
        return None

    def _fetch_system_health(self) -> Optional[BriefingItem]:
        """Fetch system health summary."""
        try:
            from backend.actions import system_monitor as sm
            status = sm.get_system_status()
            if status:
                return BriefingItem(
                    category="system", title="System Health",
                    content=f"CPU: {status.get('cpu_percent', '?')}%, RAM: {status.get('ram_percent', '?')}%",
                    items=[status],
                )
        except Exception as exc:
            logger.debug("System health fetch failed: %s", exc)
        return None

    async def generate_briefing(self, location="Johannesburg",
                                task_manager=None,
                                anomaly_detector=None,
                                google_account=None) -> DailyBriefing:
        """Generate a complete daily briefing."""
        sections: list[BriefingItem] = []
        weather = await self._fetch_weather(location)
        if weather:
            sections.append(weather)
        news = await self._fetch_news_summary()
        if news:
            sections.append(news)
        if task_manager:
            tasks = self._fetch_tasks(task_manager)
            if tasks:
                sections.append(tasks)
        if google_account:
            calendar = await self._fetch_calendar(google_account)
            if calendar:
                sections.append(calendar)
        anomalies: list[dict[str, Any]] = []
        if anomaly_detector:
            anomalies = [a.to_dict() for a in anomaly_detector.get_anomalies(severity="warning")]
            if anomalies:
                sections.append(BriefingItem(
                    category="anomalies", title="Anomalies",
                    content=f"{len(anomalies)} anomaly warning(s)",
                    priority="high" if any(a.get("severity") == "critical" for a in anomalies) else "normal",
                    items=anomalies,
                ))
        system = self._fetch_system_health()
        if system:
            sections.append(system)
        summary_parts = []
        for s in sections:
            if s.category == "weather" and s.items:
                summary_parts.append(f"Weather: {s.content}")
            elif s.category == "news":
                summary_parts.append(f"News: {s.items[0]['title'] if s.items else 'updated'}")
            elif s.category == "tasks":
                summary_parts.append(f"Tasks: {len(s.items)} open")
            elif s.category == "anomalies":
                summary_parts.append(f"Anomalies: {len(s.items)} warning(s)")
        briefing = DailyBriefing(
            sections=sections, anomalies=anomalies,
            summary="; ".join(summary_parts) if summary_parts else "No updates available.",
        )
        self._get_bus().publish_simple("briefing.ready", briefing.to_dict(), priority="important")
        return briefing


_BRIEFING_AGENT: Optional[DailyBriefingAgent] = None


def get_daily_briefing_agent() -> DailyBriefingAgent:
    global _BRIEFING_AGENT
    if _BRIEFING_AGENT is None:
        _BRIEFING_AGENT = DailyBriefingAgent()
    return _BRIEFING_AGENT

    def _fetch_system_health(self) -> Optional[BriefingItem]:
        """Fetch system health summary."""
        try:
            from backend.actions import system_monitor as sm
            status = sm.get_system_status()
            if status:
                return BriefingItem(
                    category="system", title="System Health",
                    content=f"CPU: {status.get('cpu_percent', '?')}%, RAM: {status.get('ram_percent', '?')}%",
                    items=[status],
                )
        except Exception as exc:
            logger.debug("System health fetch failed: %s", exc)
        return None