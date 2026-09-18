"""Tests for normalized data models."""
import pytest
from backend.models import (
    NewsItem, ScienceItem, WeatherItem, LocalDevice, PairedDevice,
    KnowledgeEntity, KnowledgeRelation, MemoryItem, BriefingItem,
    DailyBriefing, AnomalyEvent, AutomationTask,
)


class TestNewsItem:
    def test_create_news_item(self):
        item = NewsItem(title="Test", source="bbc", url="http://example.com")
        assert item.title == "Test"
        assert item.source == "bbc"
        assert item.id
        assert item.confidence == 1.0

    def test_to_dict(self):
        item = NewsItem(title="Test", source="bbc", url="http://x.com")
        d = item.to_dict()
        assert d["title"] == "Test"
        assert d["source"] == "bbc"
        assert "id" in d


class TestScienceItem:
    def test_create_science_item(self):
        item = ScienceItem(title="AI Breakthrough", authors=["A. Smith"])
        assert item.title == "AI Breakthrough"
        assert item.source == "arxiv"


class TestWeatherItem:
    def test_create_weather_item(self):
        item = WeatherItem(location="Johannesburg", temperature=25.0, condition="sunny")
        assert item.location == "Johannesburg"
        assert item.temperature == 25.0


class TestLocalDevice:
    def test_create_device(self):
        dev = LocalDevice(name="Living Room Light", device_type="smart_bulb", address="192.168.1.5")
        assert dev.name == "Living Room Light"
        assert dev.status == "unknown"


class TestPairedDevice:
    def test_create_paired_device(self):
        dev = PairedDevice(device_id="phone-1", name="My Phone", platform="android")
        assert dev.platform == "android"
        assert dev.status == "online"


class TestKnowledgeEntity:
    def test_create_entity(self):
        ent = KnowledgeEntity(name="Python", entity_type="language")
        assert ent.name == "Python"
        assert ent.entity_type == "language"


class TestKnowledgeRelation:
    def test_create_relation(self):
        rel = KnowledgeRelation(source_id="a", target_id="b", relationship_type="uses")
        assert rel.relationship_type == "uses"
        assert rel.confidence == 1.0


class TestMemoryItem:
    def test_create_memory(self):
        item = MemoryItem(text="The user prefers Python", kind="fact")
        assert item.text == "The user prefers Python"
        assert item.kind == "fact"


class TestBriefingItem:
    def test_create_briefing_item(self):
        item = BriefingItem(category="weather", title="Weather", content="Sunny, 25C")
        assert item.category == "weather"


class TestDailyBriefing:
    def test_create_briefing(self):
        briefing = DailyBriefing(summary="All clear")
        assert briefing.summary == "All clear"
        assert briefing.sections == []


class TestAnomalyEvent:
    def test_create_anomaly(self):
        anomaly = AnomalyEvent(category="system", title="High CPU", severity="warning")
        assert anomaly.severity == "warning"
        assert anomaly.acknowledged is False


class TestAutomationTask:
    def test_create_task(self):
        task = AutomationTask(name="Open browser", risk_score=20)
        assert task.name == "Open browser"
        assert task.status == "pending"
