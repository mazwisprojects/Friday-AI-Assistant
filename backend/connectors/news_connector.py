"""
Trusted news connector for F.R.I.D.A.Y.

Fetches headlines from vetted sources via RSS and DuckDuckGo, normalises them
into NewsItem models, and publishes on the event bus.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests
from backend.models import NewsItem

logger = logging.getLogger(__name__)

TRUSTED_SOURCES = {
    "reuters": {"trust": 0.95, "rss": "https://feeds.reuters.com/reuters/topNews"},
    "bbc-news": {"trust": 0.93, "rss": "https://feeds.bbci.co.uk/news/rss.xml"},
    "associated-press": {"trust": 0.92, "rss": "https://rsshub.app/apnews/topics/apf-topnews"},
    "the-guardian": {"trust": 0.88, "rss": "https://www.theguardian.com/world/rss"},
    "al-jazeera": {"trust": 0.85, "rss": "https://www.aljazeera.com/xml/rss/all.xml"},
    "techcrunch": {"trust": 0.80, "rss": "https://techcrunch.com/feed/"},
    "ars-technica": {"trust": 0.82, "rss": "https://feeds.arstechnica.com/arstechnica/index"},
    "mit-review": {"trust": 0.85, "rss": "https://www.technologyreview.com/feed/"},
}


class NewsConnector:
    """Fetch, normalise, and publish news from trusted sources."""

    def __init__(self, event_bus=None, session=None, cache_ttl_seconds=600):
        self._bus = event_bus
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": "Friday-AI-Assistant/1.0"})
        self._cache_ttl = cache_ttl_seconds
        self._cache: dict[str, tuple[float, list[NewsItem]]] = {}

    def _get_bus(self):
        if self._bus is None:
            from event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    def fetch_headlines(self, source="bbc-news", max_items=10):
        """Fetch headlines from a single trusted RSS source."""
        cache_key = f"rss:{source}"
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached[0]) < self._cache_ttl:
            return cached[1][:max_items]
        cfg = TRUSTED_SOURCES.get(source)
        if not cfg:
            return []
        items = []
        try:
            resp = self._session.get(cfg["rss"], timeout=15)
            resp.raise_for_status()
            items = self._parse_rxml(resp.text, source, cfg["trust"])
        except Exception as exc:
            logger.warning("RSS fetch failed for %s: %s", source, exc)
        self._cache[cache_key] = (time.time(), items)
        result = items[:max_items]
        if result:
            self._get_bus().publish_simple("news.updated", {
                "source": source, "count": len(result),
                "items": [i.to_dict() for i in result],
            })
        return result

    def fetch_category(self, category, max_items=8):
        """Fetch news for a category using DuckDuckGo."""
        cache_key = f"ddg:{category}"
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached[0]) < self._cache_ttl:
            return cached[1][:max_items]
        items = []
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                for r in ddgs.news(f"{category} news", max_results=max_items):
                    items.append(NewsItem(
                        title=r.get("title", ""), source=r.get("source", "duckduckgo"),
                        url=r.get("url", ""), summary=r.get("body", ""),
                        category=category, confidence=0.7, published_at=r.get("date", ""),
                    ))
        except Exception as exc:
            logger.warning("DDG news failed: %s", exc)
        self._cache[cache_key] = (time.time(), items)
        result = items[:max_items]
        if result:
            self._get_bus().publish_simple("news.updated", {
                "source": "duckduckgo", "category": category,
                "count": len(result), "items": [i.to_dict() for i in result],
            })
        return result

    def fetch_all(self, max_per_source=5):
        """Fetch headlines from all trusted RSS sources."""
        all_items: list[NewsItem] = []
        for source in TRUSTED_SOURCES:
            try:
                all_items.extend(self.fetch_headlines(source, max_items=max_per_source))
            except Exception:
                continue
        return all_items

    @staticmethod
    def _parse_rxml(xml_text, source, trust):
        """Parse RSS/Atom XML into NewsItem list."""
        items = []
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_text)
            for item in root.iter("item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                if not title:
                    continue
                items.append(NewsItem(
                    title=title, source=source, url=link,
                    summary=item.findtext("description", "")[:300],
                    published_at=item.findtext("pubDate", ""), confidence=trust,
                ))
            if not items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall("atom:entry", ns):
                    title = entry.findtext("atom:title", "", ns).strip()
                    link_el = entry.find("atom:link", ns)
                    link = link_el.get("href", "") if link_el is not None else ""
                    if not title:
                        continue
                    items.append(NewsItem(
                        title=title, source=source, url=link,
                        summary=entry.findtext("atom:summary", "", ns)[:300],
                        published_at=entry.findtext("atom:updated", "", ns), confidence=trust,
                    ))
        except Exception as exc:
            logger.debug("RSS parse failed for %s: %s", source, exc)
        return items

    def source_list(self):
        return {name: cfg["trust"] for name, cfg in TRUSTED_SOURCES.items()}


_NEWS_CONNECTOR: Optional[NewsConnector] = None


def get_news_connector() -> NewsConnector:
    global _NEWS_CONNECTOR
    if _NEWS_CONNECTOR is None:
        _NEWS_CONNECTOR = NewsConnector()
    return _NEWS_CONNECTOR

