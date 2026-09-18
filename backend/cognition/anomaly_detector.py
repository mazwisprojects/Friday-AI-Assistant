"""
Anomaly detector for F.R.I.D.A.Y.

Correlates events from the bus and system metrics to detect unusual patterns
in system behaviour, user activity, and security.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Any, Optional

from backend.models import AnomalyEvent

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detect anomalies from event streams and system metrics."""

    def __init__(self, event_bus=None, window_seconds: int = 3600):
        self._bus = event_bus
        self._window = window_seconds
        self._events: deque[tuple[float, str, dict]] = deque()
        self._anomalies: list[AnomalyEvent] = []
        self._rate_baselines: dict[str, deque[tuple[float, int]]] = defaultdict(deque)
        self._metric_history: dict[str, deque[tuple[float, float]]] = defaultdict(deque)
        self._alerted: set[str] = set()

    def _get_bus(self):
        if self._bus is None:
            from event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    def record_event(self, topic: str, payload: dict[str, Any] | None = None) -> None:
        """Record an event for pattern analysis."""
        now = time.time()
        self._events.append((now, topic, payload or {}))
        self._rate_baselines[topic].append((now, 1))
        self._prune_old(now)
        self._check_rate_anomaly(topic, now)

    def record_metric(self, name: str, value: float) -> None:
        """Record a numeric metric for threshold analysis."""
        now = time.time()
        self._metric_history[name].append((now, value))
        self._check_metric_anomaly(name, value, now)

    def _check_rate_anomaly(self, topic: str, now: float) -> None:
        """Detect unusual event rates."""
        window_start = now - 300
        recent = [t for t, _ in self._rate_baselines[topic] if t > window_start]
        rate = len(recent)
        if rate > 50 and topic not in self._alerted:
            self._alerted.add(topic)
            anomaly = AnomalyEvent(
                category="behaviour",
                title=f"High event rate: {topic}",
                description=f"{rate} events of type '{topic}' in 5 minutes",
                severity="warning",
            )
            self._anomalies.append(anomaly)
            self._get_bus().publish_simple("anomaly.detected", anomaly.to_dict())

    def _check_metric_anomaly(self, name: str, value: float, now: float) -> None:
        """Detect metric threshold breaches using z-score."""
        history = self._metric_history.get(name)
        if not history or len(history) < 10:
            return
        values = [v for _, v in history]
        mean = sum(values) / len(values)
        std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
        if std > 0 and abs(value - mean) > 3 * std:
            key = f"metric:{name}"
            if key not in self._alerted:
                self._alerted.add(key)
                anomaly = AnomalyEvent(
                    category="performance",
                    title=f"Metric anomaly: {name}",
                    description=f"{name}={value:.1f} (mean={mean:.1f}, std={std:.1f})",
                    severity="warning",
                )
                self._anomalies.append(anomaly)
                self._get_bus().publish_simple("anomaly.detected", anomaly.to_dict())

    def _prune_old(self, now: float) -> None:
        cutoff = now - self._window
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

    def get_anomalies(self, since: float = 0, severity: str | None = None) -> list[AnomalyEvent]:
        from datetime import datetime
        since_str = datetime.fromtimestamp(since).isoformat() if since else "1970-01-01T00:00:00"
        result = [a for a in self._anomalies if a.detected_at >= since_str]
        if severity:
            result = [a for a in result if a.severity == severity]
        return result

    def get_event_rate(self, topic: str, window_seconds: int = 300) -> float:
        now = time.time()
        recent = [t for t, _ in self._rate_baselines.get(topic, []) if t > now - window_seconds]
        return len(recent) / max(1, window_seconds)

    def acknowledge(self, anomaly_id: str) -> bool:
        for a in self._anomalies:
            if a.id == anomaly_id:
                a.acknowledged = True
                return True
        return False

    def stats(self) -> dict[str, Any]:
        return {
            "total_anomalies": len(self._anomalies),
            "unacknowledged": sum(1 for a in self._anomalies if not a.acknowledged),
            "by_category": self._count_by("category"),
            "by_severity": self._count_by("severity"),
            "tracked_topics": len(self._rate_baselines),
        }

    def _count_by(self, key: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for a in self._anomalies:
            v = getattr(a, key, "?")
            counts[v] = counts.get(v, 0) + 1
        return counts


_DETECTOR: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    global _DETECTOR
    if _DETECTOR is None:
        _DETECTOR = AnomalyDetector()
    return _DETECTOR
