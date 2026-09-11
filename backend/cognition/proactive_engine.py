"""
Proactive Engine for F.R.I.D.A.Y - Anticipate, don't react.

Provides:
- Threat detection and mitigation
- Need prediction
- Opportunity scanning
- Continuous monitoring
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Threat:
    """A detected threat."""
    id: str
    name: str
    description: str
    severity: float = 0.5
    source: str = "scan"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProactiveAction:
    """An action F.R.I.D.A.Y can take proactively."""
    type: str  # threat_mitigation, need_fulfillment, opportunity
    description: str
    urgency: str = "normal"
    recommended_action: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ThreatDetector:
    """Detect potential threats from REAL system state (P1.4).

    Scans: system_monitor (CPU/RAM/temp), background_monitor (disk/monitors),
    and cybersecurity state file — the infrastructure that friday.py already
    polls, now feeding the brain instead of being isolated.
    """

    THREAT_PATTERNS = {
        "security": ["unauthorized access", "suspicious activity", "failed login"],
        "system": ["disk full", "memory high", "cpu overload"],
        "data": ["corruption detected", "backup failed", "sync error"],
    }

    # Real sensor thresholds (percent where a threat is flagged)
    CPU_HIGH = 90.0
    RAM_HIGH = 92.0
    TEMP_HIGH = 85.0
    DISK_HIGH = 90.0

    async def scan(self, context: dict | None = None) -> list[Threat]:
        """Scan real system state for threats."""
        context = context or {}
        threats = []
        seen = set()

        def _add(name, description, severity, source, meta=None):
            key = f"{source}:{name}"
            if key not in seen:
                seen.add(key)
                threats.append(Threat(
                    id=f"threat_{source}_{len(seen)}",
                    name=name, description=description,
                    severity=float(severity), source=source,
                    metadata=meta or {},
                ))

        # --- Sensor 1: system_monitor (CPU / RAM / temp) ---
        try:
            import asyncio
            from actions import system_monitor as _sm
            status = await asyncio.to_thread(_sm.get_system_status)
            cpu = float(status.get("cpu_percent") or 0)
            ram = float(status.get("ram_percent") or 0)
            temp = float(status.get("cpu_temp_c") or 0)
            if cpu >= self.CPU_HIGH:
                _add("cpu_overload", f"CPU at {cpu:.0f}%", 0.7 + cpu / 1000, "system_monitor",
                     {"cpu_percent": cpu})
            if ram >= self.RAM_HIGH:
                _add("memory_high", f"RAM at {ram:.0f}%", 0.7 + ram / 1000, "system_monitor",
                     {"ram_percent": ram})
            if temp >= self.TEMP_HIGH:
                _add("thermal_threat", f"CPU temperature {temp:.0f}C", 0.8, "system_monitor",
                     {"cpu_temp_c": temp})
        except Exception as e:
            logger.debug("System monitor sensor failed: %s", e)

        # --- Sensor 2: background_monitor (disk / monitors / alerts) ---
        try:
            import asyncio
            from actions import background_monitor as _bm
            alerts = await asyncio.to_thread(_bm.check_all)
            for alert in (alerts or [])[:10]:
                _add("monitor_alert", str(alert)[:200], 0.7, "background_monitor",
                     {"alert": str(alert)[:150]})
            monitors = await asyncio.to_thread(_bm.list_monitors)
            if monitors:
                # Low priority, informational
                _add("monitors_active", f"{len(monitors)} monitors active", 0.2,
                     "background_monitor", {"monitors": monitors})
        except Exception as e:
            logger.debug("Background monitor sensor failed: %s", e)

        # --- Sensor 3: cybersecurity state (vulnerabilities / findings) ---
        try:
            from actions import cybersecurity as _cy
            state = _cy._load()
            vulns = state.get("vulnerabilities", []) or []
            for v in vulns[:5]:
                sev = str(v.get("severity", "MEDIUM")).upper()
                score = {"CRITICAL": 0.95, "HIGH": 0.85, "MEDIUM": 0.6}.get(sev, 0.5)
                _add("vulnerability", str(v.get("description", sev))[:200], score,
                     "cybersecurity", {"id": v.get("id"), "severity": sev})
        except Exception as e:
            logger.debug("Cybersecurity sensor failed: %s", e)

        # --- Sensor 4: disk space ---
        try:
            import asyncio
            from pathlib import Path
            import shutil
            total, used, free = await asyncio.to_thread(
                shutil.disk_usage, str(Path.home()))
            disk_pct = used / total * 100
            if disk_pct >= self.DISK_HIGH:
                _add("disk_full", f"Disk {disk_pct:.0f}% full", 0.7 + disk_pct / 1000,
                     "system_monitor", {"disk_percent": round(disk_pct, 1)})
        except Exception as e:
            logger.debug("Disk sensor failed: %s", e)

        return threats


class NeedPredictor:
    """Predict what the user will need (P1.4: real signals from goals + schedule)."""

    async def predict(self, context: dict | None = None) -> list[dict[str, Any]]:
        """Predict upcoming needs from active goals, pending tasks, and time context."""
        context = context or {}
        predictions = []

        # Signal 1: active goals that haven't been touched recently
        try:
            from actions import goal_engine
            goals = goal_engine.list_active() or []
            for g in goals[:5]:
                title = (g.get("title") or g.get("goal") or "untitled")[:80]
                due = g.get("due_date") or g.get("deadline") or ""
                predictions.append({
                    "description": f"Active goal: {title}",
                    "action": f"Check on goal '{title}' progress",
                    "confidence": 0.85,
                    "source": "goal_engine",
                    "due": due,
                })
        except Exception as e:
            logger.debug("Goal signal failed: %s", e)

        # Signal 2: recurring patterns from semantic memory (time-based)
        try:
            import time as _time
            from actions import semantic_memory as _sem
            now = _time.localtime()
            date_hint = ("morning" if now.tm_hour < 12 else
                         "afternoon" if now.tm_hour < 18 else "evening")
            hits = _sem.search(date_hint, top_k=3, kind="chat") or {}
            for h in hits.get("results", [])[:2]:
                predictions.append({
                    "description": f"Recent context ({date_hint}): {h.get('text', '')[:80]}",
                    "action": "Recall relevant context",
                    "confidence": 0.6,
                    "source": "semantic_memory",
                })
        except Exception as e:
            logger.debug("Pattern signal failed: %s", e)

        return predictions


class OpportunityScanner:
    """Scan for opportunities (P1.4: self-improvement + tool health signals)."""

    async def scan(self, context: dict | None = None) -> list[dict[str, Any]]:
        """Scan for improvement opportunities from real system signals."""
        context = context or {}
        opportunities = []

        # Signal 1: underused/available tools worth surfacing
        try:
            from actions import ops_journal
            stats = ops_journal.stats() or {}
            recent_kinds = stats.get("recent_kinds") or []
            if recent_kinds:
                opportunities.append({
                    "description": f"Recent ops activity: {', '.join(recent_kinds[:4])}",
                    "action": "Summarize latest operations",
                    "value": 0.6,
                    "source": "ops_journal",
                })
        except Exception as e:
            logger.debug("Ops signal failed: %s", e)

        # Signal 2: model health — opportunity to reconfigure if models are cooling
        try:
            from model_router import status as _mr_status
            st = _mr_status() or {}
            cooling = [m.get("model") for m in st.get("models", []) if m.get("cooling")]
            if cooling:
                opportunities.append({
                    "description": f"{len(cooling)} model(s) in cooldown: {', '.join(cooling[:3])}",
                    "action": "Reconfigure model routing",
                    "value": 0.75,
                    "source": "model_router",
                })
        except Exception as e:
            logger.debug("Model health signal failed: %s", e)

        return opportunities


class ProactiveEngine:
    """Anticipate needs, threats, and opportunities."""

    def __init__(self):
        self.threat_detector = ThreatDetector()
        self.need_predictor = NeedPredictor()
        self.opportunity_scanner = OpportunityScanner()
        self._scan_interval = 300  # 5 minutes
        self._last_scan = 0.0

    async def continuous_scan(self, context: dict | None = None) -> list[ProactiveAction]:
        """Continuously scan for things that need attention."""
        context = context or {}
        actions = []

        # 1. Threat Detection
        threats = await self.threat_detector.scan(context)
        for threat in threats:
            if threat.severity > 0.5:
                actions.append(ProactiveAction(
                    type="threat_mitigation",
                    description=f"Threat detected: {threat.name}",
                    urgency="high" if threat.severity > 0.8 else "normal",
                    recommended_action=f"Mitigate: {threat.name}",
                    confidence=threat.severity,
                ))

        # 2. Need Prediction
        predicted_needs = await self.need_predictor.predict(context)
        for need in predicted_needs:
            if need.get("confidence", 0) > 0.8:
                actions.append(ProactiveAction(
                    type="need_fulfillment",
                    description=need.get("description", ""),
                    recommended_action=need.get("action", ""),
                    confidence=need.get("confidence", 0),
                ))

        # 3. Opportunity Scanning
        opportunities = await self.opportunity_scanner.scan(context)
        for opp in opportunities:
            if opp.get("value", 0) > 0.5:
                actions.append(ProactiveAction(
                    type="opportunity",
                    description=opp.get("description", ""),
                    recommended_action=opp.get("action", ""),
                    confidence=opp.get("value", 0),
                ))

        return actions

    async def evaluate_situation(self, situation: dict) -> list[ProactiveAction]:
        """Evaluate a situation and recommend proactive actions."""
        actions = []

        if situation.get("urgency") == "critical":
            actions.append(ProactiveAction(
                type="immediate_response",
                description="Critical situation detected",
                urgency="critical",
                recommended_action="Take immediate action",
                confidence=0.9,
            ))

        return actions
