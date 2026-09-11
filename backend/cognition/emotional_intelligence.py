"""
Emotional Intelligence for F.R.I.D.A.Y - Understand and respond to emotions.

Provides:
- Emotion detection from text and voice
- Empathy engine
- Response adaptation
"""
from __future__ import annotations

import asyncio
import json
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
        """Analyze text for emotional content: regex fast path, LLM on miss/low signal."""
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

        # Regex found nothing definitive — escalate to LLM for nuanced detection
        # (sarcasm, mixed feelings, implied emotion) that keywords can't catch.
        llm_state = await self._llm_emotion(text)
        if llm_state:
            return llm_state
        return EmotionalState(primary="neutral", confidence=0.5)

    async def _llm_emotion(self, text: str) -> EmotionalState | None:
        """LLM-assisted emotion classification. Returns None when unavailable."""
        try:
            from model_router import generate_response
            prompt = (
                "Classify the emotional state of this message. Consider phrasing, "
                "punctuation, sarcasm, and implied feeling.\n\n"
                f"Message: {text[:800]}\n\n"
                'Return ONLY JSON: {"primary": "frustrated|happy|sad|anxious|confused|'
                'excited|grateful|urgent|neutral", "intensity": 0.0-1.0, '
                '"secondary": "<secondary emotion or empty>", "confidence": 0.0-1.0}'
            )
            response = await asyncio.to_thread(generate_response, prompt, "lite")
            if not getattr(response, "ok", False):
                return None
            match = re.search(r"\{.*\}", (response.text or "").strip(), re.DOTALL)
            if not match:
                return None
            parsed = json.loads(match.group(0))
            primary = str(parsed.get("primary", "neutral")).lower()
            if primary == "neutral":
                return EmotionalState(primary="neutral", confidence=0.6)
            return EmotionalState(
                primary=primary,
                secondary=str(parsed.get("secondary", ""))[:40],
                intensity=float(parsed.get("intensity", 0.6)),
                confidence=float(parsed.get("confidence", 0.7)),
                metadata={"source": "llm"},
            )
        except Exception as e:
            logger.debug("LLM emotion detection unavailable: %s", e)
            return None

    # ---------- P3.10: voice-tone emotion from raw PCM audio ----------

    def analyze_voice_bytes(self, pcm: bytes, sample_rate: int = 24000) -> EmotionalState:
        """Analyze raw PCM audio (int16 little-endian) for arousal/energy cues.

        No heavy ML deps: RMS loudness + peak ratio + zero-crossing rate give a
        real, defensible signal for loud/excited vs. soft/calm delivery. The Live
        API transmits 24kHz int16 PCM by default.
        """
        if not pcm or not isinstance(pcm, (bytes, bytearray)):
            return EmotionalState(primary="neutral", confidence=0.3,
                                  metadata={"source": "voice", "feature": "none"})
        n = len(pcm) // 2
        if n < 8:
            return EmotionalState(primary="neutral", confidence=0.3,
                                  metadata={"source": "voice", "feature": "none"})
        try:
            import struct
            samples = struct.unpack(f"<{n}h", pcm[: n * 2])
        except Exception:
            return EmotionalState(primary="neutral", confidence=0.3,
                                  metadata={"source": "voice", "feature": "none"})
        peak = max(abs(s) for s in samples) / 32768.0
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5 / 32768.0
        crossings = sum(
            1 for i in range(1, len(samples)) if (samples[i] >= 0) != (samples[i - 1] >= 0)
        )
        zcr = crossings / max(1, len(samples) - 1)

        # Arousal scoring: loud + high zero-crossing => excited/frustrated/urgent
        loudness = min(1.0, rms * 4.0)
        arousal = min(1.0, loudness * 0.7 + zcr * 0.3)
        if peak < 0.05:
            emotion, conf, intensity = "neutral", 0.4, 0.1
        elif arousal >= 0.6:
            emotion, conf, intensity = "excited", 0.7, arousal
        elif loudness < 0.25 and zcr < 0.1:
            emotion, conf, intensity = "calm", 0.6, 0.3
        else:
            emotion, conf, intensity = "neutral", 0.5, arousal
        return EmotionalState(
            primary=emotion, confidence=conf, intensity=round(intensity, 2),
            metadata={"source": "voice", "rms": round(rms, 4), "peak": round(peak, 4),
                      "zcr": round(zcr, 4), "arousal": round(arousal, 2)},
        )

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
            if isinstance(voice_data, (bytes, bytearray)):
                voice_emotion = self.emotion_detector.analyze_voice_bytes(bytes(voice_data))
            else:
                voice_emotion = await self.analyze_voice(voice_data)

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
        """Analyze voice for emotional content (P3.10: raw PCM → arousal cues).

        Accepts raw PCM bytes (analysed via analyze_voice_bytes) or pre-computed
        dict features.
        """
        if isinstance(voice_data, (bytes, bytearray)):
            return self.emotion_detector.analyze_voice_bytes(bytes(voice_data))
        if isinstance(voice_data, dict):
            # Pre-computed features: honour explicit emotion or arousal score
            if voice_data.get("emotion"):
                return EmotionalState(
                    primary=str(voice_data["emotion"]),
                    confidence=float(voice_data.get("confidence", 0.6)),
                    intensity=float(voice_data.get("intensity", 0.5)),
                    metadata={"source": "voice", **voice_data},
                )
        return EmotionalState(primary="neutral", confidence=0.3)

    async def analyze_context(self, context: dict[str, Any]) -> EmotionalState:
        """Analyze context for emotional cues."""
        if context.get("urgency") == "critical":
            return EmotionalState(primary="urgent", intensity=0.8, confidence=0.6)
        return EmotionalState(primary="neutral", confidence=0.4)
