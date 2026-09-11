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
    """Structured knowledge with relationships and reasoning."""

    def __init__(self):
        self.graph = GraphDatabase()
        self.reasoner = GraphReasoner()
        self.inference_engine = InferenceEngine()

    async def add_knowledge(self, fact: dict[str, Any]) -> None:
        """Add knowledge with relationships."""
        entities = await self._extract_entities(fact)
        relationships = await self._extract_relationships(fact)

        for entity in entities:
            self.graph.add_node(entity)

        for rel in relationships:
            self.graph.add_edge(rel)

        new_knowledge = await self.inference_engine.infer(self.graph)
        for inferred in new_knowledge:
            self.graph.add_node(inferred)

    async def query(self, query: str) -> QueryResult:
        """Query the knowledge graph."""
        parsed = await self._parse_query(query)
        relevant = self.graph.find_relevant(parsed)
        result = await self.reasoner.reason(relevant, parsed)
        return result

    async def _extract_entities(self, fact: dict[str, Any]) -> list[Entity]:
        """Extract entities from a fact."""
        entities = []
        if "subject" in fact:
            entities.append(Entity(
                id=f"entity_{fact['subject']}",
                name=fact["subject"],
                entity_type="thing",
            ))
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
