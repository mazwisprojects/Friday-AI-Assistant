"""
Situation Awareness for F.R.I.D.A.Y - Deep context understanding.

Provides:
- Context analysis (what's being said)
- Intent decoding (what's really meant)
- Emotion detection (how is the user feeling)
- Urgency assessment (how critical is this)
- Hidden context detection (what's not being said)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class EmotionalState:
    """Detected emotional state."""
    primary: str = "neutral"
    secondary: str = ""
    intensity: float = 0.5
    confidence: float = 0.0


@dataclass
class SituationAssessment:
    """Complete situation assessment."""
    surface_context: str = ""
    deep_intent: str = ""
    emotion: EmotionalState = field(default_factory=EmotionalState)
    urgency: str = "normal"
    hidden_context: list[str] = field(default_factory=list)
    recommended_approach: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ContextAnalyzer:
    """Analyze surface context from input."""

    async def analyze(self, text: str, metadata: dict | None = None) -> str:
        """Extract surface context from text."""
        if not text:
            return ""
        return text[:200]


class IntentDecoder:
    """Decode deep intent from surface text."""

    INTENT_PATTERNS = {
        r"\b(help|assist|support)\b": "requesting_help",
        r"\b(create|make|build|generate)\b": "creation_request",
        r"\b(find|search|look for|where)\b": "search_request",
        r"\b(fix|repair|debug|solve)\b": "problem_solving",
        r"\b(explain|what|how|why)\b": "information_request",
        r"\b(do|execute|run|perform)\b": "action_request",
        r"\b(stop|cancel|end|quit)\b": "termination_request",
        r"\b(urgent|asap|immediately|emergency)\b": "urgent_request",
    }

    async def decode(self, text: str, surface_context: str) -> str:
        """Decode the real intent behind the words."""
        text_lower = text.lower()
        for pattern, intent in self.INTENT_PATTERNS.items():
            if re.search(pattern, text_lower):
                return intent
        return "general_conversation"


class EmotionDetector:
    """Detect emotional state from input."""

    EMOTION_PATTERNS = {
        "frustrated": [r"\b(frustrat|annoy|irritat|angry|mad)\b", r"!{2,}", r"\b(ugh|argh|damn)\b"],
        "happy": [r"\b(happy|glad|great|excellent|awesome|love)\b", r"\b(:D|:\)|<3)\b"],
        "sad": [r"\b(sad|upset|disappointed|depressed|down)\b"],
        "anxious": [r"\b(worried|nervous|anxious|scared|afraid|panic)\b"],
        "confused": [r"\b(confused|lost|don't understand|unclear)\b"],
        "urgent": [r"\b(urgent|emergency|asap|immediately|now)\b"],
    }

    async def detect_text_emotion(self, text: str) -> EmotionalState:
        """Detect emotion from text."""
        if not text:
            return EmotionalState()

        text_lower = text.lower()
        for emotion, patterns in self.EMOTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    intensity = 0.7 if emotion in ("urgent", "frustrated") else 0.5
                    return EmotionalState(primary=emotion, intensity=intensity, confidence=0.7)

        return EmotionalState(primary="neutral", confidence=0.5)


class UrgencyAssessor:
    """Assess urgency of a situation."""

    URGENCY_INDICATORS = {
        "critical": [r"\b(emergency|critical|life.?threatening|danger)\b"],
        "high": [r"\b(urgent|asap|immediately|important|serious)\b"],
        "normal": [r"\b(please|could you|would you)\b"],
        "low": [r"\b(whenever|no rush|at your convenience)\b"],
    }

    async def assess(self, text: str, intent: str, emotion: EmotionalState) -> str:
        """Assess urgency level."""
        text_lower = text.lower()
        for level, patterns in self.URGENCY_INDICATORS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return level
        if emotion.primary in ("urgent", "anxious") and emotion.intensity > 0.6:
            return "high"
        return "normal"


class SituationAwareness:
    """Deep understanding of current situation."""

    def __init__(self):
        self.context_analyzer = ContextAnalyzer()
        self.intent_decoder = IntentDecoder()
        self.emotion_detector = EmotionDetector()
        self.urgency_assessor = UrgencyAssessor()

    async def assess_situation(self, text: str, metadata: dict | None = None) -> SituationAssessment:
        """Build deep understanding of current situation."""
        metadata = metadata or {}

        surface = await self.context_analyzer.analyze(text, metadata)
        intent = await self.intent_decoder.decode(text, surface)
        emotion = await self.emotion_detector.detect_text_emotion(text)
        urgency = await self.urgency_assessor.assess(text, intent, emotion)
        hidden = await self._detect_hidden_context(text, surface, intent)
        approach = self._determine_approach(intent, emotion, urgency)

        return SituationAssessment(
            surface_context=surface,
            deep_intent=intent,
            emotion=emotion,
            urgency=urgency,
            hidden_context=hidden,
            recommended_approach=approach,
            confidence=0.7,
            metadata=metadata,
        )

    async def _detect_hidden_context(self, text: str, surface: str, intent: str) -> list[str]:
        """Detect what's not being explicitly said."""
        hidden = []
        if "problem" in text.lower() and "urgent" not in text.lower():
            hidden.append("Possible underlying urgency not explicitly stated")
        if text.endswith("..."):
            hidden.append("User may be hesitant or uncertain")
        return hidden

    def _determine_approach(self, intent: str, emotion: EmotionalState, urgency: str) -> str:
        """Determine the best approach for this situation."""
        if urgency == "critical":
            return "immediate_action"
        if emotion.primary == "frustrated":
            return "patient_support"
        if emotion.primary == "confused":
            return "clear_explanation"
        if intent == "requesting_help":
            return "helpful_assistance"
        if intent == "creation_request":
            return "creative_collaboration"
        return "conversational"
