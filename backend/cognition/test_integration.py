"""
P4 integration tests — the seams, not just the units.

Covers:
- P4.1 event bus: publish/drain/dedupe/overflow/close semantics
- P4.2 end-to-end offline chain: sensor threat -> proactive scan -> event bus ->
  session formatting; decision -> real tool -> learning
- P4.3 background tier: pro-led chain exists, cognition LLM calls use it
- Degradation: a model outage (404 / no API key) never breaks the brain

Everything is OFFLINE: model_router.generate_response is monkeypatched to raise,
so no test can touch the network even when GEMINI_API_KEY is set.
"""
import asyncio
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from cognition import FridayCognition, CognitiveContext, Interaction, LearningEngine
from cognition.learning_engine import Mistake
from cognition.event_bus import CognitiveEvent, CognitiveEventBus, get_bus
from cognition.proactive_engine import Threat


def _tmp_root():
    return tempfile.mkdtemp(prefix="friday_cog_it_")


@pytest.fixture
def no_llm(monkeypatch):
    """Simulate a model outage for one test — cognition must degrade, not die."""
    import model_router

    def _dead(*args, **kwargs):
        raise RuntimeError("404: model not found")

    monkeypatch.setattr(model_router, "generate_response", _dead)


class TestEventBus:
    def test_publish_and_pending_snapshot(self):
        bus = CognitiveEventBus()
        assert bus.publish(CognitiveEvent(
            topic="threat", summary="CPU at 95%", priority="urgent")) is True
        events = bus.pending()
        assert len(events) == 1 and events[0].topic == "threat"
        # snapshot does NOT consume
        assert len(bus.pending()) == 1

    @pytest.mark.asyncio
    async def test_drain_delivers_and_close_stops(self):
        bus = CognitiveEventBus()
        seen = []

        async def handler(event):
            seen.append(event.summary)

        task = asyncio.create_task(bus.drain(handler))
        await asyncio.sleep(0.02)
        bus.publish(CognitiveEvent(topic="threat", summary="first", priority="urgent"))
        await asyncio.sleep(0.05)
        bus.close()
        await asyncio.wait_for(task, timeout=1.0)
        assert seen == ["first"]

    def test_dedupe_cooldown_suppresses_repeats(self):
        bus = CognitiveEventBus(cooldown_seconds=120.0)

        def make():
            return CognitiveEvent(topic="threat", summary="disk full",
                                  priority="important", dedupe_key="threat:disk")

        assert bus.publish(make()) is True
        assert bus.publish(make()) is False
        assert bus.published_count == 1
        assert bus.suppressed_count == 1

    def test_overflow_keeps_newest(self):
        bus = CognitiveEventBus(maxsize=2)
        for i in range(5):
            assert bus.publish(CognitiveEvent(
                topic="threat", summary=f"e{i}", priority="info")) is True
        summaries = [e.summary for e in bus.pending()]
        assert summaries == ["e3", "e4"]
        assert bus.dropped_count == 3

    @pytest.mark.asyncio
    async def test_handler_crash_does_not_kill_consumer(self):
        bus = CognitiveEventBus()
        seen = []

        async def handler(event):
            if event.summary == "boom":
                raise ValueError("handler bug")
            seen.append(event.summary)

        task = asyncio.create_task(bus.drain(handler))
        await asyncio.sleep(0.02)
        bus.publish(CognitiveEvent(topic="threat", summary="boom", priority="urgent"))
        await asyncio.sleep(0.05)
        bus.publish(CognitiveEvent(topic="threat", summary="after", priority="urgent"))
        await asyncio.sleep(0.05)
        bus.close()
        await asyncio.wait_for(task, timeout=1.0)
        assert seen == ["after"]

    def test_get_bus_is_singleton(self):
        assert get_bus() is get_bus()


class TestProactiveToSessionChain:
    """P4.2: the full background path — sensor threat -> bus -> decision -> learning."""

    @pytest.mark.asyncio
    async def test_threat_flows_from_scan_to_bus(self, no_llm, monkeypatch):
        cognition = FridayCognition(workspace_root=_tmp_root())
        await cognition.initialize()
        bus = CognitiveEventBus(cooldown_seconds=0.0)
        cognition.event_bus = bus

        async def fake_scan(context=None):
            return [Threat(id="t1", name="cpu_overload",
                           description="Threat detected: cpu_overload",
                           severity=0.9, source="system_monitor")]

        monkeypatch.setattr(cognition.proactive_engine.threat_detector, "scan", fake_scan)

        actions = await cognition.proactive_scan()
        assert actions and actions[0].type == "threat_mitigation"

        events = bus.pending()
        threat_events = [e for e in events if e.topic == "threat"]
        assert threat_events, "threat was not published to the event bus"
        event = threat_events[0]
        assert event.priority == "urgent"
        assert "cpu_overload" in event.summary
        # Must match inject_runtime_event's delivery format exactly.
        assert f"System Notification ({event.priority}): {event.summary}".startswith(
            "System Notification (urgent)")

    @pytest.mark.asyncio
    async def test_decision_resolves_real_tool_and_learns(self, no_llm):
        cognition = FridayCognition(workspace_root=_tmp_root())
        await cognition.initialize()

        decision = await cognition.decision_engine.decide(
            "urgent_request", ["get_system_status"], {"urgency": "critical"})
        assert decision.tool == "get_system_status"
        assert decision.needs_approval is False  # read-only, registry-classified autonomous

        await cognition.learn(Interaction(
            description="Mitigated cpu_overload via system status check",
            success=True, actions=["get_system_status"], outcome="completed"))
        stats = cognition.learning_engine.get_learning_stats()
        assert stats["skill_count"] > 0

    @pytest.mark.asyncio
    async def test_approval_escalation_published(self, no_llm, monkeypatch):
        from cognition.decision_engine import Decision

        cognition = FridayCognition(workspace_root=_tmp_root())
        await cognition.initialize()
        bus = CognitiveEventBus(cooldown_seconds=0.0)
        cognition.event_bus = bus

        async def fake_decide(situation, options, context=None):
            return Decision(action="write_file", needs_approval=True,
                            urgency="critical", tool="write_file",
                            risks=["high risk"])

        monkeypatch.setattr(cognition.decision_engine, "decide", fake_decide)

        response = await cognition.process(CognitiveContext(user_input="update the config"))
        assert response is not None
        approval = [e for e in bus.pending() if e.topic == "approval_needed"]
        assert approval and approval[0].priority == "urgent"
        assert "write_file" in approval[0].summary


class TestDegradation:
    """When the model tier 404s (or no key), the brain still works end to end."""

    @pytest.mark.asyncio
    async def test_process_survives_model_outage(self, no_llm):
        cognition = FridayCognition(workspace_root=_tmp_root())
        await cognition.initialize()

        response = await cognition.process(CognitiveContext(
            user_input="I'm so frustrated, the build is broken again!"))
        assert response is not None
        assert response.emotion is not None
        assert response.emotion.primary == "frustrated"  # regex path, zero network
        assert isinstance(response.actions_taken, list)

    @pytest.mark.asyncio
    async def test_swarm_completion_publishes_event(self, no_llm):
        cognition = FridayCognition(workspace_root=_tmp_root())
        await cognition.initialize()
        bus = CognitiveEventBus(cooldown_seconds=0.0)
        cognition.event_bus = bus
        cognition.agent_swarm.event_bus = bus

        result = await cognition.agent_swarm.handle_complex_task("Analyze system logs")
        assert "success_count" in result
        assert any(e.topic == "swarm_result" for e in bus.pending())

    def test_cognition_uses_process_bus(self):
        cognition = FridayCognition(workspace_root=_tmp_root())
        assert cognition.event_bus is get_bus()


class TestBackgroundTier:
    """P4.3: background cognition routes through the pro-led chain."""

    def test_background_chain_is_pro_led_with_flash_fallback(self):
        import model_router
        chain = model_router.chains().get("background", [])
        assert chain, "background tier missing from chains()"
        assert "pro" in chain[0].lower()
        assert any("flash" in m.lower() for m in chain[1:])

    def test_background_pick_returns_a_model(self):
        import model_router
        assert model_router.pick("background")

    @pytest.mark.asyncio
    async def test_lesson_derivation_uses_background_tier(self, monkeypatch):
        import model_router
        tiers = []

        def _spy(contents, tier="flash", config=None):
            tiers.append(tier)
            return SimpleNamespace(text='{"lesson": "pin the version"}', ok=True)

        monkeypatch.setattr(model_router, "generate_response", _spy)
        lesson = await LearningEngine().mistake_journal.derive_lesson(
            Mistake(description="deploy broke", context="no backup"))
        assert tiers == ["background"]
        assert lesson == "pin the version"

    @pytest.mark.asyncio
    async def test_emotion_refinement_uses_background_tier(self, monkeypatch):
        import model_router
        from cognition.emotional_intelligence import EmotionalIntelligence
        tiers = []

        def _spy(contents, tier="flash", config=None):
            tiers.append(tier)
            return SimpleNamespace(
                text='{"primary": "anxious", "intensity": 0.7, '
                     '"secondary": "", "confidence": 0.8}',
                ok=True)

        monkeypatch.setattr(model_router, "generate_response", _spy)
        # Ambiguous text so the regex path finds nothing and the LLM path runs.
        detector = EmotionalIntelligence().emotion_detector
        state = await detector._llm_emotion("hmm, well, maybe...")
        assert tiers == ["background"]
        assert state is not None and state.primary == "anxious"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])