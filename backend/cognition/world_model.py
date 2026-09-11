"""
World Model for F.R.I.D.A.Y - Causal understanding and simulation.

Provides:
- Causal graph for understanding cause-and-effect
- Prediction engine for outcome forecasting
- Scenario simulation (Monte Carlo)
- System models for different domains
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CausalNode:
    """A node in the causal graph."""
    id: str
    name: str
    description: str
    node_type: str = "event"
    probability: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CausalEdge:
    """An edge in the causal graph (cause -> effect)."""
    cause_id: str
    effect_id: str
    strength: float = 1.0
    relationship: str = "causes"
    conditions: list[str] = field(default_factory=list)


@dataclass
class Prediction:
    """A prediction about future outcomes."""
    action: str
    likely_outcomes: list[str]
    risks: list[str]
    confidence: float
    timeframe: str = "immediate"
    assumptions: list[str] = field(default_factory=list)


@dataclass
class SimulationPath:
    """A single path in a Monte Carlo simulation."""
    steps: list[str]
    probability: float
    outcome: str
    is_success: bool


@dataclass
class SimulationResult:
    """Result of a scenario simulation."""
    scenario: str
    paths: list[SimulationPath]
    best_case: SimulationPath
    worst_case: SimulationPath
    most_likely: SimulationPath
    black_swans: list[SimulationPath]
    recommendation: str


@dataclass
class Action:
    """An action that can be taken."""
    name: str
    description: str
    preconditions: list[str] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    """A scenario to simulate."""
    description: str
    initial_conditions: list[str] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    objectives: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)


class CausalGraph:
    """Graph-based causal reasoning."""

    def __init__(self):
        self.nodes: dict[str, CausalNode] = {}
        self.edges: list[CausalEdge] = []

    def add_node(self, node: CausalNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: CausalEdge) -> None:
        self.edges.append(edge)

    def get_effects(self, node_id: str) -> list[CausalEdge]:
        return [e for e in self.edges if e.cause_id == node_id]

    def get_causes(self, node_id: str) -> list[CausalEdge]:
        return [e for e in self.edges if e.effect_id == node_id]

    def trace_effects(self, start_node_id: str, depth: int = 5) -> list[str]:
        """Trace all effects from a starting node."""
        visited = set()
        effects = []

        def _trace(node_id: str, current_depth: int):
            if current_depth >= depth or node_id in visited:
                return
            visited.add(node_id)
            for edge in self.get_effects(node_id):
                effect_node = self.nodes.get(edge.effect_id)
                if effect_node:
                    effects.append(effect_node.description)
                    _trace(edge.effect_id, current_depth + 1)

        _trace(start_node_id, 0)
        return effects


class PredictionEngine:
    """Engine for predicting outcomes."""

    async def simulate(self, effects: list[str], context: dict) -> list[str]:
        """Simulate outcomes from a list of effects."""
        outcomes = []
        for effect in effects:
            outcomes.append(f"Result of: {effect}")
        return outcomes

    async def run_monte_carlo(
        self, scenario: Scenario, iterations: int = 100
    ) -> list[SimulationPath]:
        """Run Monte Carlo simulation on a scenario.

        P0.1: when an LLM is reachable, step success probabilities come from a
        realistic scenario tree; otherwise falls back to random sampling.
        """
        # Ask the LLM once for realistic per-action success probabilities
        action_probs = await self._llm_scenario_model(scenario)

        paths = []
        for i in range(iterations):
            path = await self._simulate_path(scenario, action_probs)
            paths.append(path)
        return paths

    async def _llm_scenario_model(self, scenario: Scenario) -> dict[str, float]:
        """Realistic success probabilities per action from the LLM (empty = random)."""
        if not scenario.actions:
            return {}
        try:
            import asyncio, json, re
            from model_router import generate_response
            actions_desc = "; ".join(
                f"{a.name}: {a.description[:100]}" for a in scenario.actions[:6])
            prompt = (
                "Rate the realistic probability each action succeeds in this scenario. "
                "Be concrete and conservative (most actions fail more than 50% in the "
                "real world).\n\n"
                f"Scenario: {scenario.description[:300]}\n"
                f"Actions: {actions_desc}\n\n"
                'Return ONLY JSON: {"action_success_rates": {"<action name>": 0.00-1.00, ...}}'
            )
            response = await asyncio.to_thread(generate_response, prompt, "flash")
            raw = (getattr(response, "text", "") or "").strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return {}
            parsed = json.loads(match.group(0))
            rates = {
                str(k).strip().lower(): max(0.05, min(0.98, float(v)))
                for k, v in parsed.get("action_success_rates", {}).items()
            }
            # Only keep entries for actions we actually simulate
            known = {a.name.strip().lower() for a in scenario.actions}
            return {k: v for k, v in rates.items() if k in known}
        except Exception as e:
            logger.debug("LLM scenario model failed: %s", e)
            return {}

    async def _simulate_path(self, scenario: Scenario,
                             action_probs: dict[str, float] | None = None) -> SimulationPath:
        """Simulate a single path through a scenario.

        Uses LLM-informed probabilities when provided; random otherwise.
        """
        action_probs = action_probs or {}
        steps = []
        probability = 1.0
        is_success = True

        for action in scenario.actions:
            # LLM-informed probability, else random sampling
            success_prob = action_probs.get(
                action.name.strip().lower(),
                0.7 + (random.random() * 0.3),
            )
            if random.random() < success_prob:
                steps.append(f"SUCCESS: {action.name}")
                probability *= success_prob
            else:
                steps.append(f"FAILED: {action.name}")
                probability *= (1 - success_prob)
                is_success = False

        return SimulationPath(
            steps=steps,
            probability=probability,
            outcome="completed",
            is_success=is_success
        )

class WorldModel:
    """
    Causal understanding of how the world works.

    Provides:
    - Causal graph for cause-and-effect reasoning
    - Prediction engine for outcome forecasting
    - Scenario simulation for planning
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.causal_graph = CausalGraph()
        self.prediction_engine = PredictionEngine()
        self.system_models: dict[str, Any] = {}
        self._initialize_default_causality()

    def _initialize_default_causality(self) -> None:
        """Initialize default causal knowledge."""
        defaults = [
            CausalNode("security_breach", "Security Breach", "Unauthorized access to systems"),
            CausalNode("data_loss", "Data Loss", "Important data is lost or corrupted"),
            CausalNode("system_failure", "System Failure", "Critical system stops working"),
            CausalNode("user_harm", "User Harm", "User is physically or financially harmed"),
        ]
        for node in defaults:
            self.causal_graph.add_node(node)

    async def predict_outcome(self, action: Action, context: dict) -> Prediction:
        """Predict what will happen if we take this action."""
        effects = action.effects.copy()

        if self.llm_client:
            try:
                llm_effects = await self._llm_predict(action, context)
                effects.extend(llm_effects)
            except Exception as e:
                logger.debug("LLM prediction failed: %s", e)

        risks = action.risks.copy()
        if "system" in action.name.lower():
            risks.append("Potential system instability")

        confidence = self._calculate_confidence(action, context)

        return Prediction(
            action=action.name,
            likely_outcomes=effects,
            risks=risks,
            confidence=confidence,
            timeframe=context.get("timeframe", "immediate"),
            assumptions=["Standard operating conditions"],
        )

    async def simulate_scenario(self, scenario: Scenario, iterations: int = 100) -> SimulationResult:
        """Run 'what-if' simulations (Sokovia scenario planning)."""
        paths = await self.prediction_engine.run_monte_carlo(scenario, iterations=iterations)

        if not paths:
            return SimulationResult(
                scenario=scenario.description,
                paths=[],
                best_case=SimulationPath([], 0, "unknown", False),
                worst_case=SimulationPath([], 0, "unknown", False),
                most_likely=SimulationPath([], 0, "unknown", False),
                black_swans=[],
                recommendation="Insufficient data for simulation",
            )

        best_case = max(paths, key=lambda p: p.probability)
        worst_case = min(paths, key=lambda p: p.probability)
        most_likely = sorted(paths, key=lambda p: p.probability)[len(paths) // 2]
        black_swans = [p for p in paths if p.probability < 0.1 and not p.is_success]

        success_rate = sum(1 for p in paths if p.is_success) / len(paths)
        if success_rate > 0.8:
            recommendation = "Proceed - high probability of success"
        elif success_rate > 0.5:
            recommendation = "Proceed with caution - moderate risk"
        else:
            recommendation = "Reconsider - high risk of failure"

        return SimulationResult(
            scenario=scenario.description,
            paths=paths,
            best_case=best_case,
            worst_case=worst_case,
            most_likely=most_likely,
            black_swans=black_swans,
            recommendation=recommendation,
        )

    async def _llm_predict(self, action: Action, context: dict) -> list[str]:
        """Use LLM for deeper prediction (real causal analysis, not placeholders)."""
        prompt = (
            "Predict the realistic consequences of this action. Be concrete and causal.\n\n"
            f"Action: {action.name}\nDescription: {action.description}\n"
            f"Preconditions: {action.preconditions}\n"
            f"Context: {json.dumps(context, default=str)[:800]}\n\n"
            'Return ONLY JSON: {"effects": ["effect 1", "effect 2"], "risks": ["risk 1"]}'
        )
        try:
            from model_router import generate_response
            response = await asyncio.to_thread(generate_response, prompt, "flash")
            if not getattr(response, "ok", False):
                return []
            raw = (response.text or "").strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return []
            parsed = json.loads(match.group(0))
            effects = [str(e) for e in parsed.get("effects", [])][:6]
            action.risks.extend(str(r) for r in parsed.get("risks", [])[:4])
            return effects
        except Exception as e:
            logger.debug("LLM prediction failed: %s", e)
            return []

    def _calculate_confidence(self, action: Action, context: dict) -> float:
        """Calculate confidence in a prediction."""
        base_confidence = 0.7
        if action.preconditions:
            base_confidence += 0.1
        if context.get("historical_data"):
            base_confidence += 0.1
        return min(base_confidence, 1.0)
