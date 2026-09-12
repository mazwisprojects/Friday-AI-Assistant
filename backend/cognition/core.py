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
from .event_bus import CognitiveEvent, CognitiveEventBus, get_bus

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
        self.llm_client = llm_client
        self.reasoning_engine = ReasoningEngine(llm_client=llm_client)
        self.world_model = WorldModel(llm_client=llm_client)
        self.identity = FridayIdentity(identity_path=identity_path)
        # P4.1: process-wide event bus (survives Live reconnects) + swarm wiring
        self.event_bus = get_bus()
        self.proactive_engine = ProactiveEngine()
        self.agent_swarm = AgentSwarm(event_bus=self.event_bus)
        self.situation_awareness = SituationAwareness()
        self.decision_engine = DecisionEngine()
        self.emotional_intelligence = EmotionalIntelligence()

        # State
        self.workspace_root = Path(workspace_root) if workspace_root else None
        self._initialized = False
        self._last_proactive_scan = 0.0
        self._proactive_scan_interval = 300  # 5 minutes

        # P0.2: persisted brain — knowledge graph + learning engine load from disk
        self._state_dir = None
        if self.workspace_root:
            self._state_dir = self.workspace_root / "long_term_memory"
            self._state_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_graph = KnowledgeGraph(
            storage_path=str(self._state_dir / "knowledge_graph.json") if self._state_dir else None)
        self.learning_engine = LearningEngine(
            storage_path=str(self._state_dir / "learning_state.json") if self._state_dir else None)

    async def initialize(self) -> None:
        """Initialize all cognitive systems."""
        logger.info("Initializing F.R.I.D.A.Y cognitive systems...")
        self.identity.load_identity()
        # P0.2: persisted brain surfaces durable state automatically via storage_path
        self._initialized = True
        logger.info(
            "F.R.I.D.A.Y cognitive systems initialized "
            "(lessons=%d, kg_entities=%d)",
            len(self.learning_engine.get_lessons(limit=50)),
            self.knowledge_graph.get_stats()["entity_count"],
        )

    def get_memory_directive(self) -> str:
        """Build a durable-lessons directive for injection into the Live session,
        so Friday actually stops repeating mistakes in future conversations."""
        lessons = self.learning_engine.get_lessons(limit=10)
        if not lessons:
            return ""
        lines = "\n".join(f"- {l}" for l in lessons)
        return (
            "System Notification: Lessons learned from past mistakes (follow these "
            "in this conversation):\n" + lines + "\n"
        )

    def get_kg_context(self, limit: int = 20) -> str:
        """Summarize the knowledge graph entities as compact context."""
        stats = self.knowledge_graph.get_stats()
        entities = list(self.knowledge_graph.graph.entities.values())
        if not entities:
            return ""
        lines = "\n".join(
            f"- {e.name} ({e.entity_type})" for e in entities[:limit])
        return f"Known knowledge ({stats['entity_count']} entities, {stats['relationship_count']} relations):\n{lines}\n"

    # ---------- P4.1: event bridge (background cognition -> live session) ----------

    def publish_event(self, topic: str, summary: str, priority: str = "info",
                      payload: dict[str, Any] | None = None, dedupe_key: str = "") -> bool:
        """Publish a background-cognition event onto the process-wide bus.

        Non-blocking and exception-safe: a failing bus can never break cognition.
        """
        try:
            return self.event_bus.publish(CognitiveEvent(
                topic=topic,
                summary=summary,
                priority=priority,
                payload=payload or {},
                dedupe_key=dedupe_key,
            ))
        except Exception:
            logger.debug("publish_event failed", exc_info=True)
            return False

    async def process(self, context: CognitiveContext) -> CognitiveResponse:
        """
        Process user input through all cognitive systems.

        This is the main entry point for cognitive processing.
        """
        if not self._initialized:
            await self.initialize()

        response = CognitiveResponse()

        # Steps 1-2 (P3.9 parallel cognition): situation + emotion run concurrently,
        # because they're independent reads over the same input.
        if context.metadata.get("parallel", True):
            situation_task = self.situation_awareness.assess_situation(
                context.user_input, metadata=context.metadata)
            emotion_task = self.emotional_intelligence.understand_emotion(
                text=context.user_input,
                context={"urgency": "unknown", **context.metadata},
            )
            situation, emotion = await asyncio.gather(situation_task, emotion_task)
        else:
            situation = await self.situation_awareness.assess_situation(
                context.user_input, metadata=context.metadata)
            emotion = await self.emotional_intelligence.understand_emotion(
                text=context.user_input,
                context={"urgency": situation.urgency, **context.metadata},
            )
        response.situation = situation
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

        # Step 4: Make a decision (maps to a REAL tool from the action registry)
        options = await self._generate_options(situation, context)
        decision = await self.decision_engine.decide(
            situation.deep_intent,
            options,
            context={"urgency": situation.urgency, "emotion": emotion.primary},
        )
        response.decision = decision

        # Step 4.4 (P4.1): high-urgency decisions that need Sir's approval flow to
        # the live session via the event bus so Friday can ask out loud, even when
        # this turn was triggered by background cognition.
        if decision.needs_approval and decision.urgency in ("high", "critical"):
            self.publish_event(
                topic="approval_needed",
                summary=f"Need your approval: {decision.action}",
                priority="urgent",
                payload={"tool": decision.tool or "", "risks": list(decision.risks or [])},
                dedupe_key=f"approval:{decision.action[:80]}",
            )

        # Step 4.5 (P3.11 scenario rehearsal): for high/critical decisions on real
        # tools, simulate the outcome before committing so Friday knows what will
        # happen — not just hope.
        if decision.tool and decision.urgency in ("high", "critical") or (
                decision.risk_level if hasattr(decision, "risk_level") else "") in ("high", "critical"):
            try:
                rehearsal = await self.world_model.simulate_scenario(Scenario(
                    description=f"{decision.action}: {context.user_input[:150]}",
                    actions=[Action(name=decision.tool, description=decision.action)],
                    objectives=[situation.deep_intent],
                ))
                response.metadata["rehearsal"] = {
                    "recommendation": rehearsal.recommendation,
                    "success_rate": round(
                        sum(1 for p in rehearsal.paths if p.is_success) /
                        max(1, len(rehearsal.paths)), 2),
                }
            except Exception as e:
                logger.debug("Scenario rehearsal failed: %s", e)

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
        """Generate possible response options — mapped to REAL tools (P1.3)."""
        try:
            from .action_registry import registry as _reg
        except Exception:
            _reg = None

        options = [f"Respond to: {situation.deep_intent}"]
        if _reg:
            # Real tool suggestions from the registry based on intent
            for tool in _reg.suggest(situation.deep_intent):
                options.append(tool)
        if situation.urgency == "critical":
            options.append("Take immediate action")
            options.append("Alert user immediately")
        if situation.deep_intent == "requesting_help":
            options.append("Provide step-by-step help")
            if _reg and _reg.exists("web_search"):
                options.append("web_search")
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
        # P0.2: persist the brain on shutdown too (defense in depth)
        self.knowledge_graph.save()
        self.learning_engine.save()
        logger.info("F.R.I.D.A.Y cognitive systems shutdown complete")

    async def proactive_scan(self) -> list[ProactiveAction]:
        """Run proactive scan for threats, needs, and opportunities."""
        now = time.time()
        if now - self._last_proactive_scan < self._proactive_scan_interval:
            return []

        self._last_proactive_scan = now
        context = {
            "identity": self.identity.get_self_model(),
            "knowledge_graph": self.knowledge_graph.get_stats(),
            "learning": self.learning_engine.get_learning_stats(),
        }
        actions = await self.proactive_engine.continuous_scan(context)
        logger.info("Proactive scan found %d actions", len(actions))

        # P4.1: threats stream to the live session via the event bus (push, not
        # pull) — the initiative loop no longer has to be the only delivery path.
        for action in actions:
            if action.type != "threat_mitigation":
                continue
            severity = float(getattr(action, "confidence", 0.0) or 0.0)
            self.publish_event(
                topic="threat",
                summary=action.description,
                priority="urgent" if severity >= 0.8 else "important",
                payload={
                    "recommended_action": action.recommended_action,
                    "severity": severity,
                },
                dedupe_key=f"threat:{action.description[:80]}",
            )
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
        """Add knowledge to the knowledge graph (also mirrors to semantic memory)."""
        # P1.5: mirror durable facts into the vector semantic memory too
        try:
            from actions import semantic_memory as _sem
            text = fact.get("text") or fact.get("value") or fact.get("name") or ""
            if text:
                _sem.remember(str(text)[:700], kind="knowledge", source="knowledge_graph")
        except Exception:
            pass
        await self.knowledge_graph.add_knowledge(fact)

    async def query_knowledge(self, query: str) -> Any:
        """Query the knowledge graph (enriched with semantic memory hits)."""
        return await self.knowledge_graph.query(query)

    async def consolidate_daily(self) -> dict[str, Any]:
        """P2.7 nightly consolidation — episodic → semantic/durable memory.

        Saves the day's state, mirrors lessons into semantic memory, and returns
        a summary for the ops digest.
        """
        self.knowledge_graph.save()
        self.learning_engine.save()
        lessons = self.learning_engine.get_lessons(limit=10)
        try:
            from actions import semantic_memory as _sem
            for lesson in lessons:
                _sem.remember(f"LESSON: {lesson}", kind="lesson", source="nightly_consolidation")
            kg_stats = self.knowledge_graph.get_stats()
            learning_stats = self.learning_engine.get_learning_stats()
            summary = (
                f"Cognitive consolidation: {kg_stats['entity_count']} entities, "
                f"{kg_stats['relationship_count']} relations, "
                f"{learning_stats['skill_count']} skills, "
                f"{learning_stats['mistake_count']} mistakes, "
                f"{len(lessons)} mirrored lessons."
            )
            return {"ok": True, "summary": summary, "lessons": lessons}
        except Exception as e:
            logger.warning("Daily consolidation partial failure: %s", e)
            return {"ok": False, "summary": "Consolidation failed", "error": str(e)}

    def get_status(self) -> dict[str, Any]:
        """Get status of all cognitive systems."""
        return {
            "initialized": self._initialized,
            "identity": self.identity.get_self_model(),
            "learning": self.learning_engine.get_learning_stats(),
            "knowledge_graph": self.knowledge_graph.get_stats(),
            "agent_swarm": self.agent_swarm.get_agent_status(),
            "registry": self.decision_engine.registry.available_action_summary() if self.decision_engine.registry else None,
        }
