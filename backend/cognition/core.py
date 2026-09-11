"""
F.R.I.D.A.Y Cognitive Core - Integration layer connecting all brain systems.

This is the central nervous system that coordinates all cognitive capabilities:
- Reasoning Engine for deep thinking
- World Model for causal understanding
- Identity for persistent self
- Proactive Engine for anticipation
- Agent Swarm for multi-agent coordination
- Learning Engine for continuous improvement
- Situation Awareness for context understanding
- Decision Engine for autonomous action
- Knowledge Graph for structured knowledge
- Emotional Intelligence for empathy
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .reasoning_engine import ReasoningEngine, ReasoningResult
from .world_model import WorldModel, Action, Scenario, Prediction, SimulationResult
from .identity import FridayIdentity, Experience
from .proactive_engine import ProactiveEngine, ProactiveAction
from .agent_swarm import AgentSwarm, Task
from .learning_engine import LearningEngine, Interaction
from .situation_awareness import SituationAwareness, SituationAssessment
from .decision_engine import DecisionEngine, Decision
from .knowledge_graph import KnowledgeGraph
from .emotional_intelligence import EmotionalIntelligence, EmotionalState

logger = logging.getLogger(__name__)


@dataclass
class CognitiveContext:
    """Context for cognitive processing."""
    user_input: str = ""
    conversation_history: list[dict] = field(default_factory=list)
    system_state: dict[str, Any] = field(default_factory=dict)
    user_id: str = "default"
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CognitiveResponse:
    """Response from cognitive processing."""
    text: str = ""
    confidence: float = 0.0
    reasoning: Optional[ReasoningResult] = None
    situation: Optional[SituationAssessment] = None
    decision: Optional[Decision] = None
    emotion: Optional[EmotionalState] = None
    actions_taken: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

class FridayCognition:
    """
    Central cognitive system for F.R.I.D.A.Y.

    Coordinates all brain systems to provide AGI-level capabilities.
    """

    def __init__(
        self,
        llm_client=None,
        identity_path: str | None = None,
        workspace_root: str | None = None,
    ):
        # Core cognitive systems
        self.reasoning_engine = ReasoningEngine(llm_client=llm_client)
        self.world_model = WorldModel(llm_client=llm_client)
        self.identity = FridayIdentity(identity_path=identity_path)
        self.proactive_engine = ProactiveEngine()
        self.agent_swarm = AgentSwarm()
        self.learning_engine = LearningEngine()
        self.situation_awareness = SituationAwareness()
        self.decision_engine = DecisionEngine()
        self.knowledge_graph = KnowledgeGraph()
        self.emotional_intelligence = EmotionalIntelligence()

        # State
        self.workspace_root = Path(workspace_root) if workspace_root else None
        self._initialized = False
        self._last_proactive_scan = 0.0
        self._proactive_scan_interval = 300  # 5 minutes

    async def initialize(self) -> None:
        """Initialize all cognitive systems."""
        logger.info("Initializing F.R.I.D.A.Y cognitive systems...")
        self.identity.load_identity()
        self._initialized = True
        logger.info("F.R.I.D.A.Y cognitive systems initialized")

    async def process(self, context: CognitiveContext) -> CognitiveResponse:
        """
        Process user input through all cognitive systems.

        This is the main entry point for cognitive processing.
        """
        if not self._initialized:
            await self.initialize()

        response = CognitiveResponse()

        # Step 1: Assess the situation
        situation = await self.situation_awareness.assess_situation(
            context.user_input,
            metadata=context.metadata,
        )
        response.situation = situation

        # Step 2: Understand emotion
        emotion = await self.emotional_intelligence.understand_emotion(
            text=context.user_input,
            context={"urgency": situation.urgency, **context.metadata},
        )
        response.emotion = emotion

        # Step 3: Reason about the query (for complex queries)
        reasoning = None
        if self._should_reason(situation):
            reasoning = await self.reasoning_engine.reason(
                context.user_input,
                context={
                    "situation": situation.deep_intent,
                    "emotion": emotion.primary,
                    "history": context.conversation_history[-5:],
                },
            )
            response.reasoning = reasoning

        # Step 4: Make a decision
        options = await self._generate_options(situation, context)
        decision = await self.decision_engine.decide(
            situation.deep_intent,
            options,
            context={"urgency": situation.urgency, "emotion": emotion.primary},
        )
        response.decision = decision

        # Step 5: Generate response
        base_response = await self._generate_base_response(
            context, situation, reasoning, decision
        )

        # Step 6: Adapt response with emotional intelligence
        adapted_response = await self.emotional_intelligence.adapt_response(
            base_response, emotion
        )

        # Step 7: Add personality
        final_response = await self.identity.respond_with_personality(
            {"urgency": situation.urgency, "allows_humor": emotion.primary not in ("sad", "anxious")},
            adapted_response,
        )

        response.text = final_response
        response.confidence = reasoning.confidence if reasoning else 0.7

        # Step 8: Learn from this interaction
        await self._learn_from_interaction(context, response)

        return response

    def _should_reason(self, situation: SituationAssessment) -> bool:
        """Determine if deep reasoning is needed."""
        complex_intents = {"problem_solving", "creation_request", "search_request"}
        if situation.deep_intent in complex_intents:
            return True
        if situation.urgency in ("high", "critical"):
            return True
        return False

    async def _generate_options(
        self, situation: SituationAssessment, context: CognitiveContext
    ) -> list[str]:
        """Generate possible response options."""
        options = [f"Respond to: {situation.deep_intent}"]
        if situation.urgency == "critical":
            options.append("Take immediate action")
            options.append("Alert user immediately")
        if situation.deep_intent == "requesting_help":
            options.append("Provide step-by-step help")
            options.append("Search for solutions")
        return options

    async def _generate_base_response(
        self,
        context: CognitiveContext,
        situation: SituationAssessment,
        reasoning: Optional[ReasoningResult],
        decision: Decision,
    ) -> str:
        """Generate the base response."""
        if reasoning and reasoning.confidence > 0.6:
            return reasoning.conclusion

        responses = {
            "requesting_help": "I'm here to help. What do you need?",
            "creation_request": "I'd be happy to help create that. Let me get started.",
            "search_request": "Let me search for that information.",
            "problem_solving": "Let me analyze this problem and find a solution.",
            "information_request": "Here's what I know about that.",
            "action_request": "I'll take care of that right away.",
            "termination_request": "Understood. Stopping now.",
            "urgent_request": "I'm on it immediately.",
            "general_conversation": "I'm listening. What's on your mind?",
        }

        return responses.get(situation.deep_intent, "How can I help you?")

    async def _learn_from_interaction(
        self, context: CognitiveContext, response: CognitiveResponse
    ) -> None:
        """Learn from the current interaction."""
        interaction = Interaction(
            description=context.user_input[:200],
            success=True,
            actions=[response.decision.action] if response.decision else [],
            outcome="completed",
            metadata={
                "situation": response.situation.deep_intent if response.situation else "",
                "emotion": response.emotion.primary if response.emotion else "",
            },
        )

        await self.learning_engine.learn_from_interaction(interaction)

        experience = Experience(
            event_type="interaction",
            description=context.user_input[:200],
            outcome="success",
            lessons_learned=[],
        )
        await self.identity.learn_from_experience(experience)

    async def shutdown(self) -> None:
        """Shutdown cognitive systems and save state."""
        logger.info("Shutting down F.R.I.D.A.Y cognitive systems...")
        self.identity.save_identity()
        logger.info("F.R.I.D.A.Y cognitive systems shutdown complete")

    async def proactive_scan(self) -> list[ProactiveAction]:
        """Run proactive scan for threats, needs, and opportunities."""
        now = time.time()
        if now - self._last_proactive_scan < self._proactive_scan_interval:
            return []

        self._last_proactive_scan = now
        context = {"identity": self.identity.get_self_model()}
        actions = await self.proactive_engine.continuous_scan(context)
        logger.info("Proactive scan found %d actions", len(actions))
        return actions

    async def simulate_scenario(self, scenario_description: str) -> SimulationResult:
        """Simulate a scenario for planning."""
        scenario = Scenario(
            description=scenario_description,
            actions=[Action(name="default", description="Default action")],
        )
        return await self.world_model.simulate_scenario(scenario)

    async def learn(self, interaction: Interaction) -> None:
        """Learn from an interaction."""
        await self.learning_engine.learn_from_interaction(interaction)

    async def add_knowledge(self, fact: dict[str, Any]) -> None:
        """Add knowledge to the knowledge graph."""
        await self.knowledge_graph.add_knowledge(fact)

    async def query_knowledge(self, query: str) -> Any:
        """Query the knowledge graph."""
        return await self.knowledge_graph.query(query)

    def get_status(self) -> dict[str, Any]:
        """Get status of all cognitive systems."""
        return {
            "initialized": self._initialized,
            "identity": self.identity.get_self_model(),
            "learning": self.learning_engine.get_learning_stats(),
            "knowledge_graph": self.knowledge_graph.get_stats(),
            "agent_swarm": self.agent_swarm.get_agent_status(),
        }
