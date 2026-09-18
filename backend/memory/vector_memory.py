"""
Vector memory for F.R.I.D.A.Y.

Enhances the existing semantic index with entity linking to the knowledge
graph, so retrieved memories can be enriched with structured knowledge.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

from backend.models import MemoryItem

logger = logging.getLogger(__name__)

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "vector_memory.json"


class VectorMemory:
    """Vector memory with knowledge-graph entity linking."""

    def __init__(self, auto_link: bool = True):
        self._entries: list[dict[str, Any]] = []
        self._auto_link = auto_link
        self._load()

    def _load(self) -> None:
        try:
            import json
            data = json.loads(_STATE.read_text(encoding="utf-8"))
            self._entries = data.get("entries", [])
        except (OSError, json.JSONDecodeError):
            self._entries = []

    def _save(self) -> None:
        import json
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps({"entries": self._entries}, indent=1), encoding="utf-8")

    def remember(self, text: str, kind: str = "fact", source: str = "",
                 meta: dict | None = None) -> MemoryItem:
        """Store a memory item and link to knowledge graph entities."""
        item = MemoryItem(text=text, kind=kind, source=source, metadata=meta or {})

        # Link to knowledge graph entities
        linked_entities: list[str] = []
        if self._auto_link:
            try:
                from cognition.knowledge_search import SearchableKnowledgeGraph
                skg = SearchableKnowledgeGraph()
                result = skg.search(text, max_results=3)
                linked_entities = [e.name for e in result.entities if result.confidence > 0.3]
            except Exception:
                pass

        entry = item.to_dict()
        entry["linked_entities"] = linked_entities
        self._entries.append(entry)
        self._save()
        return item

    def search(self, query: str, top_k: int = 5) -> list[MemoryItem]:
        """Search memories using the semantic index, enriched with KG context."""
        try:
            from actions import semantic_memory as _sem
            result = _sem.search(query, top_k=top_k)
        except Exception:
            return []

        items = []
        for r in result.get("results", []):
            item = MemoryItem(
                id=r.get("id", ""),
                text=r.get("text", ""),
                kind=r.get("kind", "fact"),
                source=r.get("source", ""),
                score=r.get("score", 0.0),
            )
            items.append(item)
        return items

    def link_entity(self, memory_id: str, entity_name: str) -> bool:
        """Link a memory item to a knowledge graph entity."""
        for entry in self._entries:
            if entry.get("id") == memory_id:
                links = entry.setdefault("linked_entities", [])
                if entity_name not in links:
                    links.append(entity_name)
                    self._save()
                    return True
        return False

    def get_linked_memories(self, entity_name: str) -> list[MemoryItem]:
        """Get all memories linked to a knowledge graph entity."""
        items = []
        for entry in self._entries:
            if entity_name in entry.get("linked_entities", []):
                items.append(MemoryItem(
                    id=entry.get("id", ""),
                    text=entry.get("text", ""),
                    kind=entry.get("kind", "fact"),
                    source=entry.get("source", ""),
                ))
        return items

    def stats(self) -> dict[str, Any]:
        return {
            "total": len(self._entries),
            "linked": sum(1 for e in self._entries if e.get("linked_entities")),
            "by_kind": self._count_by("kind"),
        }

    def _count_by(self, key: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self._entries:
            v = e.get(key, "?")
            counts[v] = counts.get(v, 0) + 1
        return counts


_VECTOR_MEMORY: Optional[VectorMemory] = None


def get_vector_memory() -> VectorMemory:
    global _VECTOR_MEMORY
    if _VECTOR_MEMORY is None:
        _VECTOR_MEMORY = VectorMemory()
    return _VECTOR_MEMORY
