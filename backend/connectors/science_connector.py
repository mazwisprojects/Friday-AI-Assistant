"""
Science connector for F.R.I.D.A.Y.

Fetches recent papers and research news from arXiv, normalises them into
ScienceItem models, and publishes on the event bus.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

from backend.models import ScienceItem

logger = logging.getLogger(__name__)

ARXIV_CATEGORIES = {
    "cs.AI": "Artificial Intelligence",
    "cs.CL": "Computation & Language",
    "cs.CV": "Computer Vision",
    "cs.LG": "Machine Learning",
    "cs.RO": "Robotics",
    "physics": "Physics",
    "math": "Mathematics",
    "q-bio": "Quantitative Biology",
    "stat": "Statistics",
}


class ScienceConnector:
    """Fetch and normalise scientific papers from arXiv."""

    def __init__(self, event_bus=None, session: requests.Session | None = None,
                 cache_ttl_seconds: int = 1800):
        self._bus = event_bus
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": "Friday-AI-Assistant/1.0"})
        self._cache_ttl = cache_ttl_seconds
        self._cache: dict[str, tuple[float, list[ScienceItem]]] = {}

    def _get_bus(self):
        if self._bus is None:
            from event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    def fetch_papers(self, category: str = "cs.AI", max_items: int = 8) -> list[ScienceItem]:
        """Fetch recent papers from arXiv for a category."""
        cache_key = f"arxiv:{category}"
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached[0]) < self._cache_ttl:
            return cached[1][:max_items]

        items = []
        try:
            base = "http://export.arxiv.org/api/query"
            params = {
                "search_query": f"cat:{category}",
                "start": 0,
                "max_results": max_items,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
            resp = self._session.get(base, params=params, timeout=20)
            resp.raise_for_status()
            items = self._parse_arxiv_xml(resp.text, category)
        except Exception as exc:
            logger.warning("arXiv fetch failed for %s: %s", category, exc)

        self._cache[cache_key] = (time.time(), items)
        result = items[:max_items]
        if result:
            self._get_bus().publish_simple("science.updated", {
                "category": category, "count": len(result),
                "items": [i.to_dict() for i in result],
            })
        return result

    def fetch_trending(self, max_per_category: int = 3) -> list[ScienceItem]:
        """Fetch recent papers from key AI/tech categories."""
        items: list[ScienceItem] = []
        for cat in ["cs.AI", "cs.LG", "cs.CL", "cs.CV"]:
            try:
                items.extend(self.fetch_papers(cat, max_items=max_per_category))
            except Exception:
                continue
        return items

    @staticmethod
    def _parse_arxiv_xml(xml_text: str, category: str) -> list[ScienceItem]:
        """Parse arXiv Atom XML into ScienceItem list."""
        items = []
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_text)
            ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
            for entry in root.findall("atom:entry", ns):
                title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
                summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")
                authors = [a.findtext("atom:name", "", ns) for a in entry.findall("atom:author", ns)]
                link = ""
                for l in entry.findall("atom:link", ns):
                    if l.get("title") == "pdf":
                        link = l.get("href", "")
                        break
                if not link:
                    link = entry.findid("atom:id", "", ns) if hasattr(entry, 'findid') else ""
                published = entry.findtext("atom:published", "", ns)[:10]
                items.append(ScienceItem(
                    title=title, authors=authors[:5], abstract=summary[:500],
                    url=link, published_at=published, category=category, source="arxiv",
                ))
        except Exception as exc:
            logger.debug("arXiv parse failed: %s", exc)
        return items

    def category_list(self) -> dict[str, str]:
        return dict(ARXIV_CATEGORIES)


_SCIENCE_CONNECTOR: Optional[ScienceConnector] = None


def get_science_connector() -> ScienceConnector:
    global _SCIENCE_CONNECTOR
    if _SCIENCE_CONNECTOR is None:
        _SCIENCE_CONNECTOR = ScienceConnector()
    return _SCIENCE_CONNECTOR
