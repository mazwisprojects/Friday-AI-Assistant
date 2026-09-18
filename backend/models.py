"""
Normalized data models for F.R.I.D.A.Y — unified dataclasses for all entities.

Provides a single source of truth for the shapes flowing through the event bus,
connectors, agents, and persistence layers. Every module that produces or
consumes structured data imports from here so the contract is explicit.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class FridayModel:
    """Base class with dict/JSON round-tripping."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        import json
        try:
            return json.dumps(self.to_dict(), default=str, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            logger.warning("Could not serialize %s to JSON: %s", type(self).__name__, exc)
            return "{}"


# ──────────────────────────────────────────────
#  Content items (news, science, weather)
# ──────────────────────────────────────────────

@dataclass
class NewsItem(FridayModel):
    """A single news article from a trusted source."""
    title: str
    source: str
    url: str
    id: str = field(default_factory=_new_id)
    summary: str = ""
    published_at: str = ""
    category: str = "general"
    confidence: float = 1.0
    fetched_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScienceItem(FridayModel):
    """A scientific paper or research finding."""
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    url: str = ""
    id: str = field(default_factory=_new_id)
    published_at: str = ""
    category: str = "general"
    source: str = "arxiv"
    fetched_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WeatherItem(FridayModel):
    """Normalised weather report."""
    location: str = ""
    temperature: float = 0.0
    apparent_temperature: float = 0.0
    condition: str = ""
    humidity: int = 0
    wind_speed: float = 0.0
    high: float = 0.0
    low: float = 0.0
    rain_chance: int = 0
    forecast: list[dict[str, Any]] = field(default_factory=list)
    fetched_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────
#  Device & local entities
# ──────────────────────────────────────────────

@dataclass
class LocalDevice(FridayModel):
    """A discovered local device."""
    device_id: str = field(default_factory=_new_id)
    name: str = ""
    device_type: str = "unknown"
    address: str = ""
    status: str = "unknown"
    capabilities: list[str] = field(default_factory=list)
    last_seen: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PairedDevice(FridayModel):
    """A device that has completed pairing."""
    device_id: str = ""
    name: str = ""
    platform: str = "unknown"
    model: str = ""
    status: str = "online"
    battery: Optional[int] = None
    network: Optional[str] = None
    paired_at: str = ""
    last_seen: str = ""


@dataclass
class KnowledgeEntity(FridayModel):
    """A node in the knowledge graph."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    entity_type: str = "thing"
    description: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


@dataclass
class KnowledgeRelation(FridayModel):
    """An edge in the knowledge graph."""
    source_id: str = ""
    target_id: str = ""
    relationship_type: str = "related_to"
    confidence: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────
#  Memory / vector store
# ──────────────────────────────────────────────

@dataclass
class MemoryItem(FridayModel):
    """A single vectorised memory entry."""
    id: str = field(default_factory=_new_id)
    text: str = ""
    kind: str = "fact"
    source: str = ""
    score: float = 0.0
    created_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────
#  Briefing & anomaly
# ──────────────────────────────────────────────

@dataclass
class BriefingItem(FridayModel):
    """One section of a scheduled briefing."""
    category: str = ""
    title: str = ""
    content: str = ""
    priority: str = "normal"
    items: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DailyBriefing(FridayModel):
    """A scheduled daily briefing."""
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_now_iso)
    sections: list[BriefingItem] = field(default_factory=list)
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""


@dataclass
class AnomalyEvent(FridayModel):
    """A detected anomaly in system or behaviour."""
    id: str = field(default_factory=_new_id)
    category: str = ""
    title: str = ""
    description: str = ""
    severity: str = "info"
    detected_at: str = field(default_factory=_now_iso)
    acknowledged: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────
#  Automation
# ──────────────────────────────────────────────

@dataclass
class AutomationTask(FridayModel):
    """A controlled computer-automation task."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    status: str = "pending"
    risk_score: int = 0
    steps: list[dict[str, Any]] = field(default_factory=list)
    requires_approval: bool = True
    created_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

