"""
Searchable knowledge graph for F.R.I.D.A.Y.

Wraps the existing KnowledgeGraph with full-text search, vector similarity,
and entity linking so the assistant can query structured knowledge with
natural language.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from .knowledge_graph import KnowledgeGraph, Entity, Relationship, QueryResult

logger = logging.getLogger(__name__)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


class SearchableKnowledgeGraph:
    """Full-text + vector search over the knowledge graph."""

    def __init__(self, storage_path: str | None = None):
        self.kg = KnowledgeGraph(storage_path=storage_path)
        self._build_index()

    def _build_index(self) -> None:
        """Build inverted index for full-text search."""
        self._index: dict[str, set[str]] = {}  # token -> set(entity_id)
        for entity in self.kg.graph.entities.values():
            text = entity.name + " " + entity.entity_type + " " + \
                   (entity.description or "") + " " + \
                   " ".join(entity.tags or []) + " " + \
                   str(entity.properties)
            for token in _tokens(text):
                self._index.setdefault(token, set()).add(entity.id)

    # ---------- mutations ----------

    def add_entity(self, name: str, entity_type: str = "thing",
                   description: str = "", properties: dict | None = None,
                   tags: list[str] | None = None) -> Entity:
        """Add an entity to the graph."""
        entity = Entity(
            id=name.lower().replace(" ", "_")[:40],
            name=name, entity_type=entity_type, description=description,
            properties=properties or {}, tags=tags or [],
        )
        self.kg.graph.add_node(entity)
        self.kg.save()
        self._build_index()
        return entity

    def add_relation(self, source_name: str, target_name: str,
                     relationship_type: str = "related_to",
                     confidence: float = 1.0) -> Optional[Relationship]:
        """Add a relationship between two entities (by name)."""
        sid = source_name.lower().replace(" ", "_")[:40]
        tid = target_name.lower().replace(" ", "_")[:40]
        if sid not in self.kg.graph.entities or tid not in self.kg.graph.entities:
            return None
        rel = Relationship(
            source_id=sid, target_id=tid,
            relationship_type=relationship_type, confidence=confidence,
        )
        self.kg.graph.add_edge(rel)
        self.kg.save()
        return rel

    # ---------- search ----------

    def search(self, query: str, max_results: int = 10) -> QueryResult:
        """Full-text search over entities."""
        qtokens = _tokens(query)
        if not qtokens:
            return QueryResult()

        # Score entities by token overlap
        scores: dict[str, float] = {}
        for token in qtokens:
            for eid in self._index.get(token, set()):
                scores[eid] = scores.get(eid, 0) + 1.0

        # Boost by entity name match
        qlower = query.lower()
        for eid, score in scores.items():
            entity = self.kg.graph.entities.get(eid)
            if entity and qlower in entity.name.lower():
                scores[eid] = score + 5.0

        ranked = sorted(scores.items(), key=lambda x: -x[1])[:max_results]
        entities = [self.kg.graph.entities[eid] for eid, _ in ranked if eid in self.kg.graph.entities]
        relationships = []
        for entity in entities:
            relationships.extend(self.kg.graph.get_relationships(entity.id))

        return QueryResult(
            entities=entities,
            relationships=relationships,
            inferences=[f"Found {len(entities)} entities matching '{query}'"],
            confidence=min(1.0, len(entities) / max(1, max_results)),
        )

    def find_entity(self, name: str) -> Optional[Entity]:
        """Find an entity by exact or partial name match."""
        nlower = name.lower()
        for entity in self.kg.graph.entities.values():
            if nlower == entity.name.lower() or nlower in entity.name.lower():
                return entity
        return None

    def get_related(self, entity_name: str, max_depth: int = 2) -> list[dict[str, Any]]:
        """Get entities related to the given entity."""
        entity = self.find_entity(entity_name)
        if not entity:
            return []
        visited: set[str] = set()
        related: list[dict[str, Any]] = []
        frontier = [entity.id]
        for _ in range(max_depth):
            next_frontier: list[str] = []
            for eid in frontier:
                if eid in visited:
                    continue
                visited.add(eid)
                for rel in self.kg.graph.get_relationships(eid):
                    other = rel.target_id if rel.source_id == eid else rel.source_id
                    if other not in visited:
                        other_entity = self.kg.graph.entities.get(other)
                        if other_entity:
                            related.append({
                                "entity": other_entity,
                                "relationship": rel.relationship_type,
                                "confidence": rel.confidence,
                            })
                            next_frontier.append(other)
            frontier = next_frontier
        return related

    def get_stats(self) -> dict[str, Any]:
        base = self.kg.get_stats()
        base["indexed_tokens"] = len(self._index)
        return base

    def get_all_entities(self) -> list[Entity]:
        return list(self.kg.graph.entities.values())
