"""Tests for the searchable knowledge graph."""
import os
import pytest
import tempfile
from pathlib import Path
from backend.cognition.knowledge_search import SearchableKnowledgeGraph


class TestSearchableKnowledgeGraph:
    def test_add_entity(self):
        with tempfile.TemporaryDirectory() as tmp:
            skg = SearchableKnowledgeGraph(storage_path=str(Path(tmp) / "kg.json"))
            entity = skg.add_entity("Python", "language", "A programming language")
            assert entity.name == "Python"
            assert entity.id == "python"

    def test_add_relation(self):
        with tempfile.TemporaryDirectory() as tmp:
            skg = SearchableKnowledgeGraph(storage_path=str(Path(tmp) / "kg.json"))
            skg.add_entity("Python", "language")
            skg.add_entity("Django", "framework")
            rel = skg.add_relation("Python", "Django", "used_by")
            assert rel is not None
            assert rel.relationship_type == "used_by"

    def test_add_relation_missing_entity(self):
        with tempfile.TemporaryDirectory() as tmp:
            skg = SearchableKnowledgeGraph(storage_path=str(Path(tmp) / "kg.json"))
            skg.add_entity("Python", "language")
            rel = skg.add_relation("Python", "Nonexistent", "uses")
            assert rel is None

    def test_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            skg = SearchableKnowledgeGraph(storage_path=str(Path(tmp) / "kg.json"))
            skg.add_entity("Python", "language", "A programming language")
            skg.add_entity("JavaScript", "language", "Web language")
            result = skg.search("python language")
            assert len(result.entities) >= 1

    def test_search_empty_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            skg = SearchableKnowledgeGraph(storage_path=str(Path(tmp) / "kg.json"))
            result = skg.search("")
            assert len(result.entities) == 0

    def test_find_entity(self):
        with tempfile.TemporaryDirectory() as tmp:
            skg = SearchableKnowledgeGraph(storage_path=str(Path(tmp) / "kg.json"))
            skg.add_entity("Python", "language")
            found = skg.find_entity("Python")
            assert found is not None
            assert found.name == "Python"

    def test_find_entity_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            skg = SearchableKnowledgeGraph(storage_path=str(Path(tmp) / "kg.json"))
            skg.add_entity("Python", "language")
            found = skg.find_entity("pyth")
            assert found is not None

    def test_get_related(self):
        with tempfile.TemporaryDirectory() as tmp:
            skg = SearchableKnowledgeGraph(storage_path=str(Path(tmp) / "kg.json"))
            skg.add_entity("Python", "language")
            skg.add_entity("Django", "framework")
            skg.add_entity("Flask", "framework")
            skg.add_relation("Python", "Django", "used_by")
            skg.add_relation("Python", "Flask", "used_by")
            related = skg.get_related("Python")
            assert len(related) == 2

    def test_get_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            skg = SearchableKnowledgeGraph(storage_path=str(Path(tmp) / "kg.json"))
            skg.add_entity("Python", "language")
            stats = skg.get_stats()
            assert stats["entity_count"] == 1
            assert stats["indexed_tokens"] > 0
