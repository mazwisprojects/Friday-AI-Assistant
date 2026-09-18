"""Tests for the anomaly detector."""
import time
import pytest
from backend.cognition.anomaly_detector import AnomalyDetector
from backend.models import AnomalyEvent


class TestAnomalyDetector:
    def test_record_event(self):
        detector = AnomalyDetector()
        detector.record_event("test.topic", {"key": "val"})
        assert detector.get_event_rate("test.topic") > 0

    def test_rate_anomaly(self):
        detector = AnomalyDetector()
        for _ in range(55):
            detector.record_event("flood.topic")
        anomalies = detector.get_anomalies()
        assert len(anomalies) >= 1
        assert anomalies[0].category == "behaviour"

    def test_metric_anomaly(self):
        detector = AnomalyDetector()
        for i in range(20):
            detector.record_metric("cpu", 50.0 + i)
        # Anomalous value far from mean
        detector.record_metric("cpu", 500.0)
        anomalies = detector.get_anomalies()
        metric_anomalies = [a for a in anomalies if a.title.startswith("Metric")]
        assert len(metric_anomalies) >= 1

    def test_no_anomaly_for_normal_data(self):
        detector = AnomalyDetector()
        for _ in range(5):
            detector.record_event("normal.topic")
        assert len(detector.get_anomalies()) == 0

    def test_acknowledge(self):
        detector = AnomalyDetector()
        for _ in range(55):
            detector.record_event("flood.topic")
        anomalies = detector.get_anomalies()
        assert len(anomalies) > 0
        result = detector.acknowledge(anomalies[0].id)
        assert result is True
        assert anomalies[0].acknowledged is True

    def test_stats(self):
        detector = AnomalyDetector()
        detector.record_event("test.topic")
        stats = detector.stats()
        assert "tracked_topics" in stats
        assert stats["tracked_topics"] >= 1

    def test_get_anomalies_by_severity(self):
        detector = AnomalyDetector()
        for _ in range(55):
            detector.record_event("flood.topic")
        warnings = detector.get_anomalies(severity="warning")
        assert len(warnings) >= 1
        critical = detector.get_anomalies(severity="critical")
        assert len(critical) == 0
