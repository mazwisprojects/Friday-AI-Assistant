"""
Emotional Intelligence for F.R.I.D.A.Y - Understand and respond to emotions.

Provides:
- Emotion detection from text and voice
- Empathy engine
- Response adaptation
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
    metadata: dict[str, Any] = field(default_factory=dict)


class EmotionDetector:
    """Detect emotions from various inputs."""

    EMOTION_PATTERNS = {
        "frustrated": {
            "patterns": [r"frustrat|annoy|irritat|angry|mad|furious", r"!{2,}", r"ugh|argh|damn|hell"],
            "intensity": 0.7,
        },
        "happy": {
            "patterns": [r"happy|glad|great|excellent|awesome|love|wonderful", r"(:D|:\)|<3|;)"],
            "intensity": 0.6,
        },
        "sad": {
            "patterns": [r"sad|upset|disappointed|depressed|down|miserable"],
            "intensity": 0.6,
        },
        "anxious": {
            "patterns": [r"worried|nervous|anxious|scared|afraid|panic|stress"],
            "intensity": 0.7,
        },
        "confused": {
            "patterns": [r"confused|lost|don't understand|unclear|puzzled"],
            "intensity": 0.5,
        },
        "excited": {
            "patterns": [r"excited|thrilled|eager|enthusiastic|pumped"],
            "intensity": 0.7,
        },
        "grateful": {
            "patterns": [r"thank|grateful|appreciate|cheers"],
            "intensity": 0.5,
        },
    }

    async def analyze_text(self, text: str) -> EmotionalState:
        """Analyze text for emotional content."""
        if not text:
            return EmotionalState()

        text_lower = text.lower()
        for emotion, data in self.EMOTION_PATTERNS.items():
            for pattern in data["patterns"]:
                try:
                    if re.search(pattern, text_lower):
                        return EmotionalState(
                            primary=emotion,
                            intensity=data["intensity"],
                            confidence=0.75,
                        )
                except re.error:
                    # Skip invalid regex patterns
                    continue
        return EmotionalState(primary="neutral", confidence=0.5)

    async def analyze_context(self, context: dict[str, Any] | None) -> EmotionalState:
        """Analyze context for emotional cues."""
        if not context:
            return EmotionalState()
        
        context_str = " ".join(str(v) for v in context.values())
        return await self.analyze_text(context_str)

class EmpathyEngine:
    """Generate empathetic responses."""

    async def add_patience(self, response: str) -> str:
        return f"I understand this can be frustrating. {response}"

    async def add_comfort(self, response: str) -> str:
        return f"I'm here to help. {response}"

    async def add_calm(self, response: str) -> str:
        return f"Let's take this one step at a time. {response}"

    async def add_enthusiasm(self, response: str) -> str:
        return f"Wonderful! {response}"

    async def add_reassurance(self, response: str) -> str:
        return f"Don't worry, I've got this. {response}"


class ResponseAdapter:
    """Adapt responses based on emotional state."""

    async def adapt(self, response: str, emotion: EmotionalState) -> str:
        """Adapt a response based on emotional state."""
        if emotion.primary == "frustrated":
            return await self._adapt_for_frustration(response, emotion)
        elif emotion.primary == "sad":
            return await self._adapt_for_sadness(response, emotion)
        elif emotion.primary == "anxious":
            return await self._adapt_for_anxiety(response, emotion)
        elif emotion.primary == "happy":
            return await self._adapt_for_happiness(response, emotion)
        return response

    async def _adapt_for_frustration(self, response: str, emotion: EmotionalState) -> str:
        if emotion.intensity > 0.7:
            return f"I completely understand your frustration. Let me fix this right away. {response}"
        return f"I see this is frustrating. {response}"

    async def _adapt_for_sadness(self, response: str, emotion: EmotionalState) -> str:
        return f"I'm sorry you're feeling this way. {response}"

    async def _adapt_for_anxiety(self, response: str, emotion: EmotionalState) -> str:
        return f"I understand your concern. Let me help. {response}"

    async def _adapt_for_happiness(self, response: str, emotion: EmotionalState) -> str:
        return f"I'm glad! {response}"


class EmotionalIntelligence:
    """Understand and respond to emotions."""

    def __init__(self):
        self.emotion_detector = EmotionDetector()
        self.empathy_engine = EmpathyEngine()
        self.response_adapter = ResponseAdapter()

    async def understand_emotion(
        self,
        text: str = "",
        voice_data: Any = None,
        context: dict[str, Any] | None = None,
    ) -> EmotionalState:
        """Detect emotional state from multiple inputs."""
        text_emotion = await self.emotion_detector.analyze_text(text)

        voice_emotion = EmotionalState()
        if voice_data:
            voice_emotion = await self.emotion_detector.analyze_voice(voice_data)

        context_emotion = await self.emotion_detector.analyze_context(context or {})

        emotions = [text_emotion, voice_emotion, context_emotion]
        valid_emotions = [e for e in emotions if e.confidence > 0.3]

        if not valid_emotions:
            return EmotionalState(primary="neutral", confidence=0.3)

        best = max(valid_emotions, key=lambda e: e.confidence)
        return best

    async def adapt_response(self, response: str, emotion: EmotionalState) -> str:
        """Adapt response based on emotional state."""
        return await self.response_adapter.adapt(response, emotion)

    async def generate_empathetic_response(
        self,
        base_response: str,
        text: str = "",
        context: dict[str, Any] | None = None,
    ) -> str:
        """Generate a response with emotional intelligence."""
        emotion = await self.understand_emotion(text, None, context)
        adapted = await self.adapt_response(base_response, emotion)
        return adapted


    async def analyze_voice(self, voice_data: Any) -> EmotionalState:
        """Analyze voice for emotional content."""
        return EmotionalState(primary="neutral", confidence=0.3)

    async def analyze_context(self, context: dict[str, Any]) -> EmotionalState:
        """Analyze context for emotional cues."""
        if context.get("urgency") == "critical":
            return EmotionalState(primary="urgent", intensity=0.8, confidence=0.6)
        return EmotionalState(primary="neutral", confidence=0.4)
