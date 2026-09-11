"""
Test suite for F.R.I.D.A.Y Cognitive Architecture.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from cognition import (
    FridayCognition, WorldModel, Action, Scenario,
    FridayIdentity, ProactiveEngine, AgentSwarm, LearningEngine,
    Interaction, SituationAwareness, DecisionEngine, KnowledgeGraph,
    EmotionalIntelligence, EmotionalState, CognitiveContext,
)


class TestEmotionalIntelligence:
    @pytest.mark.asyncio
    async def test_detect_frustration(self):
        ei = EmotionalIntelligence()
        emotion = await ei.understand_emotion(text="I'm so frustrated!")
        assert emotion.primary == "frustrated"
        assert emotion.confidence > 0.5

    @pytest.mark.asyncio
    async def test_detect_happiness(self):
        ei = EmotionalIntelligence()
        emotion = await ei.understand_emotion(text="This is great!")
        assert emotion.primary == "happy"

    @pytest.mark.asyncio
    async def test_detect_neutral(self):
        ei = EmotionalIntelligence()
        emotion = await ei.understand_emotion(text="The weather is cloudy")
        assert emotion.primary == "neutral"


class TestSituationAwareness:
    @pytest.mark.asyncio
    async def test_help_request(self):
        sa = SituationAwareness()
        assessment = await sa.assess_situation("Can you help me?")
        assert assessment.deep_intent == "requesting_help"

    @pytest.mark.asyncio
    async def test_creation_request(self):
        sa = SituationAwareness()
        assessment = await sa.assess_situation("Create a document")
        assert assessment.deep_intent == "creation_request"


class TestDecisionEngine:
    @pytest.mark.asyncio
    async def test_simple_decision(self):
        de = DecisionEngine()
        decision = await de.decide("help", ["Help", "Search"], {"urgency": "normal"})
        assert decision.action != ""
        assert decision.confidence > 0

    @pytest.mark.asyncio
    async def test_dangerous_needs_approval(self):
        de = DecisionEngine()
        decision = await de.decide("delete", ["Delete all"], {"urgency": "critical"})
        assert decision.needs_approval is True


class TestLearningEngine:
    @pytest.mark.asyncio
    async def test_learn_success(self):
        le = LearningEngine()
        interaction = Interaction(description="Test", success=True, actions=["test"])
        await le.learn_from_interaction(interaction)
        stats = le.get_learning_stats()
        assert stats["skill_count"] > 0

    @pytest.mark.asyncio
    async def test_acquire_skill(self):
        le = LearningEngine()
        skill = await le.acquire_new_skill("python")
        assert skill is not None
        assert skill.name == "python"


class TestFridayIdentity:
    @pytest.mark.asyncio
    async def test_personality(self):
        identity = FridayIdentity()
        assert "witty" in identity.personality.traits
        assert "loyal" in identity.personality.traits

    @pytest.mark.asyncio
    async def test_self_model(self):
        identity = FridayIdentity()
        model = identity.get_self_model()
        assert model["skill_count"] > 0


class TestWorldModel:
    @pytest.mark.asyncio
    async def test_predict(self):
        wm = WorldModel()
        action = Action(name="deploy", description="Deploy code", effects=["Live"])
        prediction = await wm.predict_outcome(action, {})
        assert prediction.confidence > 0

    @pytest.mark.asyncio
    async def test_simulate(self):
        wm = WorldModel()
        scenario = Scenario(description="Test", actions=[Action(name="a", description="b")])
        result = await wm.simulate_scenario(scenario)
        assert result.recommendation != ""


class TestAgentSwarm:
    @pytest.mark.asyncio
    async def test_agents(self):
        swarm = AgentSwarm()
        status = swarm.get_agent_status()
        assert "security" in status
        assert "research" in status


class TestProactiveEngine:
    @pytest.mark.asyncio
    async def test_scan(self):
        pe = ProactiveEngine()
        pe._last_proactive_scan = 0
        actions = await pe.continuous_scan()
        assert isinstance(actions, list)


class TestKnowledgeGraph:
    @pytest.mark.asyncio
    async def test_add_knowledge(self):
        kg = KnowledgeGraph()
        await kg.add_knowledge({"subject": "Python", "predicate": "is", "object": "language"})
        stats = kg.get_stats()
        assert stats["entity_count"] > 0


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        cognition = FridayCognition()
        await cognition.initialize()
        context = CognitiveContext(user_input="Help me fix this bug")
        response = await cognition.process(context)
        assert response.text != ""
        assert response.confidence > 0
        assert response.situation is not None
        assert response.emotion is not None

    @pytest.mark.asyncio
    async def test_status(self):
        cognition = FridayCognition()
        await cognition.initialize()
        status = cognition.get_status()
        assert status["initialized"] is True

    @pytest.mark.asyncio
    async def test_shutdown(self):
        cognition = FridayCognition()
        await cognition.initialize()
        await cognition.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
