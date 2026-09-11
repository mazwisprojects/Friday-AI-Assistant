"""
Knowledge Graph for F.R.I.D.A.Y - Structured knowledge with relationships.

Provides:
- Entity and relationship storage
- Graph-based reasoning
- Inference engine
- Query interface
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """An entity in the knowledge graph."""
    id: str
    name: str
    entity_type: str = "thing"
    properties: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Relationship:
    """A relationship between entities."""
    source_id: str
    target_id: str
    relationship_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class QueryResult:
    """Result of a knowledge graph query."""
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    inferences: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class GraphDatabase:
    """In-memory graph database."""

    def __init__(self):
        self.entities: dict[str, Entity] = {}
        self.relationships: list[Relationship] = []

    def add_node(self, entity: Entity) -> None:
        self.entities[entity.id] = entity

    def add_edge(self, relationship: Relationship) -> None:
        self.relationships.append(relationship)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self.entities.get(entity_id)

    def get_relationships(self, entity_id: str) -> list[Relationship]:
        return [
            r for r in self.relationships
            if r.source_id == entity_id or r.target_id == entity_id
        ]

    def find_relevant(self, query: str) -> list[Entity]:
        """Find entities relevant to a query."""
        relevant = []
        query_lower = query.lower()
        for entity in self.entities.values():
            if query_lower in entity.name.lower():
                relevant.append(entity)
        return relevant


class GraphReasoner:
    """Reason over the knowledge graph."""

    async def reason(self, entities: list[Entity], query: str) -> QueryResult:
        """Reason over a set of entities."""
        inferences = []
        for entity in entities:
            if entity.entity_type == "person":
                inferences.append(f"{entity.name} is a person")
        return QueryResult(
            entities=entities,
            relationships=[],
            inferences=inferences,
            confidence=0.7 if entities else 0.0,
        )


class InferenceEngine:
    """Infer new knowledge from existing knowledge."""

    async def infer(self, graph: GraphDatabase) -> list[Entity]:
        """Infer new entities from existing knowledge."""
        new_entities = []
        
        # Simple inference: create "related" entities from relationships
        for rel in graph.relationships:
            source = graph.get_entity(rel.source_id)
            target = graph.get_entity(rel.target_id)
            
            if source and target:
                # Infer a relationship-based entity
                inferred = Entity(
                    id=f"inferred_{source.name}_{target.name}",
                    name=f"{source.name} {rel.relationship_type} {target.name}",
                    entity_type="inferred",
                    properties={"source": source.name, "target": target.name}
                )
                new_entities.append(inferred)
        
        return new_entities


class KnowledgeGraph:
    """Structured knowledge with relationships and reasoning.

    P0.2: the graph is persisted to JSON on every mutation and loaded on init,
    so knowledge survives restarts instead of dying with the process.
    """

    def __init__(self, storage_path: str | None = None):
        self.graph = GraphDatabase()
        self.reasoner = GraphReasoner()
        self.inference_engine = InferenceEngine()
        self.storage_path = storage_path
        if storage_path:
            self.load()

    # ---------- persistence (P0.2) ----------

    def _resolve_storage(self):
        if self.storage_path:
            return self.storage_path
        try:
            from pathlib import Path
            p = Path(__file__).resolve().parent.parent / "long_term_memory" / "knowledge_graph.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            return str(p)
        except Exception:
            return None

    def save(self, storage_path: str | None = None) -> bool:
        """Persist graph to JSON."""
        path = self._resolve_storage() if storage_path is None else storage_path
        if not path:
            return False
        try:
            import json
            data = {
                "entities": [
                    {"id": e.id, "name": e.name, "type": e.entity_type,
                     "properties": e.properties, "metadata": e.metadata}
                    for e in self.graph.entities.values()
                ],
                "relationships": [
                    {"source_id": r.source_id, "target_id": r.target_id,
                     "type": r.relationship_type, "properties": r.properties,
                     "confidence": r.confidence}
                    for r in self.graph.relationships
                ],
            }
            data["entities"].sort(key=lambda e: e["id"])
            data["relationships"].sort(key=lambda r: (r["source_id"], r["target_id"], r["type"]))
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=1)
            return True
        except Exception as e:
            logger.debug("Knowledge graph save failed: %s", e)
            return False

    def load(self, storage_path: str | None = None) -> bool:
        """Load graph from JSON (keeps existing in-memory data on failure)."""
        path = self._resolve_storage() if storage_path is None else storage_path
        if not path:
            return False
        try:
            import json, os
            if not os.path.exists(path):
                return False
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.graph.entities = {
                e["id"]: Entity(
                    id=e["id"], name=e["name"], entity_type=e.get("type", "thing"),
                    properties=e.get("properties", {}), metadata=e.get("metadata", {}),
                )
                for e in data.get("entities", [])
            }
            self.graph.relationships = [
                Relationship(
                    source_id=r["source_id"], target_id=r["target_id"],
                    relationship_type=r.get("type", "related_to"),
                    properties=r.get("properties", {}), confidence=r.get("confidence", 1.0),
                )
                for r in data.get("relationships", [])
            ]
            return True
        except Exception as e:
            logger.debug("Knowledge graph load failed: %s", e)
            return False

    async def add_knowledge(self, fact: dict[str, Any]) -> None:
        """Add knowledge with relationships."""
        entities = await self._extract_entities(fact)
        relationships = await self._extract_relationships(fact)

        # Merge entities (dedupe by id — update name/type if it already exists)
        for entity in entities:
            existing = self.graph.get_entity(entity.id)
            if existing:
                existing.name = entity.name or existing.name
                existing.properties.update(entity.properties)
            else:
                self.graph.add_node(entity)

        for rel in relationships:
            # Skip duplicates (same triplet)
            dup = any(
                r.source_id == rel.source_id and r.target_id == rel.target_id
                and r.relationship_type == rel.relationship_type
                for r in self.graph.relationships
            )
            if not dup:
                self.graph.add_edge(rel)

        new_knowledge = await self.inference_engine.infer(self.graph)
        for inferred in new_knowledge:
            if not self.graph.get_entity(inferred.id):
                self.graph.add_node(inferred)

        self.save()

    async def query(self, query: str) -> QueryResult:
        """Query the knowledge graph."""
        parsed = await self._parse_query(query)
        relevant = self.graph.find_relevant(parsed)
        result = await self.reasoner.reason(relevant, parsed)

        # P1.5: enrich with semantic memory hits (vector search over past chats/facts)
        try:
            from actions import semantic_memory as _sem
            hits = _sem.search(query, top_k=5)
            if hits.get("ok"):
                memories = [
                    h.get("text", "") for h in hits.get("results", [])
                    if isinstance(h, dict) and h.get("text")
                ]
                result.metadata = getattr(result, "metadata", {})
                result.metadata["semantic_memories"] = memories[:5]
                if not relevant and memories:
                    result.confidence = 0.6
        except Exception:
            pass
        return result

    async def _extract_entities(self, fact: dict[str, Any]) -> list[Entity]:
        """Extract entities from a fact."""
        entities = []
        # Subject/person/place/topic extraction
        for key in ("subject", "entity", "name", "person", "topic"):
            if key in fact and fact[key]:
                val = str(fact[key])[:120]
                etype = "person" if key in ("person",) else (
                    "place" if key in ("place",) else (
                        "thing" if key in ("topic", "entity") else "concept"))
                entities.append(Entity(
                    id=f"entity_{val.lower().replace(' ', '_')}",
                    name=val,
                    entity_type=etype,
                    properties={"text": fact.get("text", "")[:200]},
                ))
                break  # at most one subject entity per call

        # Object entity (for subject-predicate-object triples)
        for key in ("object", "value", "target"):
            if key in fact and fact[key]:
                val = str(fact[key])[:120]
                entities.append(Entity(
                    id=f"entity_{val.lower().replace(' ', '_')}",
                    name=val,
                    entity_type="thing",
                    properties={"value": fact.get("value", "")[:200]},
                ))
                break
        return entities

    async def _extract_relationships(self, fact: dict[str, Any]) -> list[Relationship]:
        """Extract relationships from a fact."""
        relationships = []
        if "subject" in fact and "object" in fact:
            relationships.append(Relationship(
                source_id=f"entity_{fact['subject']}",
                target_id=f"entity_{fact['object']}",
                relationship_type=fact.get("predicate", "related_to"),
            ))
        return relationships

    async def _parse_query(self, query: str) -> str:
        """Parse a natural language query."""
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "what", "who", "how"}
        words = query.lower().split()
        key_terms = [w for w in words if w not in stop_words]
        return " ".join(key_terms)

    def get_stats(self) -> dict[str, int]:
        """Get knowledge graph statistics."""
        return {
            "entity_count": len(self.graph.entities),
            "relationship_count": len(self.graph.relationships),
        }

    async def infer(self, graph: GraphDatabase) -> list[Entity]:
        """Infer new entities and relationships."""
        inferred = []
        return inferred
