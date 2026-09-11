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
    ActionRegistry, ActionSpec,
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
class TestActionRegistry:
    """P1.3: decision engine maps to the REAL tool registry."""

    def test_registry_loads_real_tools(self):
        registry = ActionRegistry()
        assert len(registry.tools) > 50
        assert "web_search" in registry.tools
        assert "gmail_read" in registry.tools
        assert "write_file" in registry.tools

    def test_risk_classification(self):
        registry = ActionRegistry()
        assert registry.is_autonomous("web_search") is True
        assert registry.risk_for("write_file") == "high"
        assert registry.risk_for("self_modify") == "high"

    def test_to_spec(self):
        registry = ActionRegistry()
        spec = registry.to_spec("web_search", description="Find docs", confidence=0.6)
        assert spec.tool == "web_search"
        assert spec.autonomous is True

    def test_suggest_maps_intent_to_tools(self):
        registry = ActionRegistry()
        suggestions = registry.suggest("search_request")
        assert "web_search" in suggestions


class TestDecisionActionMapping:
    """P1.3: Decision -> {tool, params} executable by the tool pipeline."""

    @pytest.mark.asyncio
    async def test_decision_resolves_to_real_tool(self):
        de = DecisionEngine()
        decision = await de.decide(
            "search_request", ["Respond to: search_request", "web_search"],
            {"urgency": "normal"},
        )
        assert decision.tool != ""
        assert decision.tool in de.registry.tools

    @pytest.mark.asyncio
    async def test_autonomous_tool_needs_no_approval(self):
        de = DecisionEngine()
        decision = await de.decide(
            "search_request", ["web_search"], {"urgency": "normal"})
        assert decision.needs_approval is False
        assert decision.autonomous is True

    @pytest.mark.asyncio
    async def test_high_risk_tool_requires_approval(self):
        de = DecisionEngine()
        decision = await de.decide(
            "write", ["write_file"], {"urgency": "normal"})
        assert decision.needs_approval is True
class TestKnowledgeGraphPersistence:
    """P0.2: knowledge graph survives restarts via JSON persistence."""

    @pytest.mark.asyncio
    async def test_save_load_roundtrip(self):
        path = __import__("tempfile").mkdtemp() + "/kg.json"
        kg1 = KnowledgeGraph(storage_path=path)
        await kg1.add_knowledge({"subject": "Python", "predicate": "is", "object": "language"})
        assert kg1.get_stats()["entity_count"] > 0

        kg2 = KnowledgeGraph(storage_path=path)
        assert kg2.get_stats()["entity_count"] > 0
        assert any(e.name == "Python" for e in kg2.graph.entities.values())

    @pytest.mark.asyncio
    async def test_dedupe_ids(self):
        kg = KnowledgeGraph(storage_path=__import__("tempfile").mkdtemp() + "/kg.json")
        await kg.add_knowledge({"subject": "Python", "predicate": "is", "object": "language"})
        await kg.add_knowledge({"subject": "Python", "predicate": "is", "object": "language"})
        names = [e.name for e in kg.graph.entities.values()]
        assert names.count("Python") == 1


class TestLearningEnginePersistence:
    """P0.2: lessons + skills survive restarts."""

    def test_save_load_roundtrip(self):
        path = __import__("tempfile").mkdtemp() + "/learn.json"
        le1 = LearningEngine(storage_path=path)
        if not le1.skill_library.get("python"):
            from cognition.learning_engine import Skill
            le1.skill_library.add(Skill(name="python", level=0.5))
        le1.mistake_journal.mistakes.append(le1.mistake_journal.record(
            Interaction(description="Failed deploy", success=False, actions=["deploy"])))
        for m in le1.mistake_journal.mistakes:
            m.lesson = "Use backup before deploy"
        le1.save()

        le2 = LearningEngine(storage_path=path)
        assert le2.skill_library.get("python") is not None
        lessons = le2.get_lessons()
        assert any("backup" in l for l in lessons)

    def test_pristine_load_missing_file(self):
        le = LearningEngine(storage_path=__import__("tempfile").mkdtemp() + "/missing.json")
        assert le.get_learning_stats()["skill_count"] == 0


class TestProactiveEngineSensors:
    """P1.4: proactive engine uses real-ish sensors without failing when offline."""

    @pytest.mark.asyncio
    async def test_scan_never_crashes_offline(self):
        pe = ProactiveEngine()
        threats = await pe.threat_detector.scan({})
        assert isinstance(threats, list)

    @pytest.mark.asyncio
    async def test_continuous_scan_returns_list(self):
        pe = ProactiveEngine()
        actions = await pe.continuous_scan({})
        assert isinstance(actions, list)
class TestCognitiveMemory:
    """P0.2: durable lessons + KG context are injectable into the session."""

    @pytest.mark.asyncio
    async def test_memory_directive_empty_on_fresh(self):
        cognition = FridayCognition(workspace_root=__import__("tempfile").mkdtemp())
        await cognition.initialize()
        directive = cognition.get_memory_directive()
        assert directive == ""

    @pytest.mark.asyncio
    async def test_kg_context_after_learning(self):
        cognition = FridayCognition(workspace_root=__import__("tempfile").mkdtemp())
        await cognition.initialize()
        await cognition.add_knowledge({"subject": "Jane", "predicate": "is", "object": "engineer"})
        ctx = cognition.get_kg_context()
        assert "Jane" in ctx


class TestNightlyConsolidation:
    """P2.7: nightly consolidation persists + mirrors lessons."""

    @pytest.mark.asyncio
    async def test_consolidate_daily(self):
        cognition = FridayCognition(workspace_root=__import__("tempfile").mkdtemp())
        await cognition.initialize()
        await cognition.add_knowledge({"subject": "Project X", "predicate": "is", "object": "active"})
        result = await cognition.consolidate_daily()
        assert result["ok"] is True
        assert "entities" in result["summary"]


class TestAgentSwarmDispatcher:
    """P2.6: swarm bridges to the real agent_dispatcher."""

    @pytest.mark.asyncio
    async def test_dispatcher_bridge(self):
        swarm = AgentSwarm()
        assert hasattr(swarm, "dispatcher")

    @pytest.mark.asyncio
    async def test_complex_task_returns_synthesis(self):
        swarm = AgentSwarm()
        result = await swarm.handle_complex_task("Summarize system status")
        assert "success_count" in result


class TestScenarioRehearsal:
    """P3.11: high-risk decisions rehearse scenarios through the world model."""

    @pytest.mark.asyncio
    async def test_simulate_scenario_returns_result(self):
        wm = WorldModel()
        scenario = Scenario(
            description="Deploy risky change",
            actions=[Action(name="write_file", description="Write config change",
                            effects=["Config updated"], risks=["System broken"])],
        )
        result = await wm.simulate_scenario(scenario, iterations=20)
        assert result.recommendation != ""
        assert len(result.paths) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
