"""
Decision Engine for F.R.I.D.A.Y - Autonomous decision making.

Provides:
- Option generation
- Risk assessment
- Ethics evaluation
- Autonomous action within bounds
- Approval escalation when needed
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Evaluation:
    """Evaluation of a single option."""
    option: str
    predicted_outcome: str
    risk_level: str = "low"
    risk_score: float = 0.0
    ethical_clear: bool = True
    ethical_concerns: list[str] = field(default_factory=list)
    score: float = 0.0
    confidence: float = 0.0


@dataclass
class Decision:
    """A decision made by F.R.I.D.A.Y."""
    action: str
    needs_approval: bool
    reasoning: Evaluation | None = None
    urgency: str = "normal"
    alternatives: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    # Concrete tool mapping (P1.3 — decision → real action registry)
    tool: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    autonomous: bool = False


class RiskAssessor:
    """Assess risk levels for actions."""

    RISK_CATEGORIES = {
        "data_loss": 0.8,
        "system_crash": 0.9,
        "security_breach": 0.95,
        "financial_loss": 0.85,
        "user_harm": 1.0,
        "performance_degradation": 0.4,
        "minor_inconvenience": 0.1,
    }

    async def assess(self, action: str, predicted_outcome: str) -> tuple[str, float]:
        """Assess risk level and score for an action."""
        risk_score = 0.1  # Base risk

        for category, score in self.RISK_CATEGORIES.items():
            if category in action.lower() or category in predicted_outcome.lower():
                risk_score = max(risk_score, score)

        if risk_score >= 0.8:
            risk_level = "critical"
        elif risk_score >= 0.6:
            risk_level = "high"
        elif risk_score >= 0.3:
            risk_level = "medium"
        else:
            risk_level = "low"

        return risk_level, risk_score


class EthicsModule:
    """Evaluate ethical implications of actions."""

    ETHICAL_PRINCIPLES = [
        "do_no_harm",
        "protect_user_privacy",
        "be_transparent",
        "respect_autonomy",
        "be_fair",
    ]

    async def evaluate(self, action: str, context: dict) -> tuple[bool, list[str]]:
        """Evaluate if an action is ethically sound."""
        concerns = []

        # Check for harmful actions
        harmful_patterns = ["delete all", "format", "destroy", "hack", "exploit"]
        for pattern in harmful_patterns:
            if pattern in action.lower():
                concerns.append(f"Action may cause harm: {pattern}")

        # Check for privacy violations
        if "personal data" in action.lower() and "share" in action.lower():
            concerns.append("Potential privacy violation")

        is_clear = len(concerns) == 0
        return is_clear, concerns


class DecisionEngine:
    """Make autonomous decisions with appropriate confidence.

    P1.3: options now map to the REAL tool registry — the decision carries a
    concrete {tool, params} that the existing tool pipeline can execute.
    """

    def __init__(self):
        self.risk_assessor = RiskAssessor()
        self.ethics_module = EthicsModule()
        try:
            from .action_registry import registry
            self.registry = registry
        except Exception:
            from action_registry import registry  # standalone fallback
            self.registry = registry

    async def decide(
        self,
        situation: str,
        options: list[str],
        context: dict | None = None,
    ) -> Decision:
        """Make a decision based on situation assessment."""
        context = context or {}

        if not options:
            return Decision(
                action="no_action",
                needs_approval=False,
                reasoning=None,
                urgency="low",
                confidence=0.0,
                tool="",
                params={},
            )

        # Evaluate each option
        evaluations = []
        for option in options:
            evaluation = await self._evaluate_option(option, context)
            evaluations.append(evaluation)

        # Select best option (P1.3: prefer options that resolve to REAL tools)
        best = max(
            evaluations,
            key=lambda e: e.score + self._tool_bonus(e.option),
        )

        # Map to a real, executable tool from the registry
        spec = self._resolve_action(best.option)

        # Determine if approval is needed (real API-checked risk from the registry)
        needs_approval = (
            best.risk_level in ("high", "critical")
            or not best.ethical_clear
            or not spec.autonomous
        )

        # Get alternatives
        alternatives = [e.option for e in evaluations if e.option != best.option][:3]

        return Decision(
            action=spec.tool or best.option,
            needs_approval=needs_approval,
            reasoning=best,
            urgency=context.get("urgency", "normal"),
            alternatives=alternatives,
            risks=[f"{best.risk_level} risk"] if best.risk_level != "low" else [],
            confidence=best.confidence,
            tool=spec.tool,
            params=spec.params,
            autonomous=spec.autonomous,
            metadata={"original_option": best.option, "description": spec.description},
        )

    def _tool_bonus(self, option: str) -> float:
        """Bonus for options that resolve to a real registered tool — so Friday
        actually picks an executable action over a generic chat response."""
        spec = self._resolve_action(option)
        if spec and spec.tool and spec.tool != option.strip().lower() and spec.tool not in ("Respond to",):
            # Real tool resolution
            if spec.autonomous:
                return 0.15
            return 0.05
        if spec and spec.tool in self.registry.tools:
            return 0.10
        return 0.0

    def _resolve_action(self, option: str):
        """Resolve an option string to a concrete ActionSpec via the registry."""
        # Option is already a real tool name
        clean = option.strip().lower()
        for tool in self._candidate_tools(option):
            spec = self.registry.to_spec(tool, description=option, confidence=0.6)
            if spec.tool:
                return spec
        # Fallthrough: unknown tool — keep the option as-is with medium risk
        fallback = self.registry.to_spec(clean, description=option, confidence=0.4)
        if fallback.tool and fallback.tool != clean:
            return fallback
        # register a plain string spec
        class _S:
            tool = clean or "no_action"
            params = {}
            description = option
            risk_level = "medium"
            autonomous = False
            confidence = 0.4
        return _S()

    def _candidate_tools(self, option: str):
        """Yield registry tool names matching the option."""
        low = option.lower()
        exact = self.registry.tools
        if low in exact:
            yield low
        for tool in exact:
            if low in tool or tool in low.replace(" ", "_"):
                yield tool

    async def _evaluate_option(self, option: str, context: dict) -> Evaluation:
        """Evaluate a single option."""
        # Predict outcome
        predicted_outcome = f"Outcome of: {option}"

        # Assess risk
        risk_level, risk_score = await self.risk_assessor.assess(option, predicted_outcome)

        # Check ethics
        ethical_clear, ethical_concerns = await self.ethics_module.evaluate(option, context)

        # Calculate score (higher is better)
        score = 1.0 - risk_score
        if not ethical_clear:
            score -= 0.3

        confidence = 0.7 if risk_score < 0.5 else 0.4

        return Evaluation(
            option=option,
            predicted_outcome=predicted_outcome,
            risk_level=risk_level,
            risk_score=risk_score,
            ethical_clear=ethical_clear,
            ethical_concerns=ethical_concerns,
            score=max(0.0, score),
            confidence=confidence,
        )

    async def can_act_autonomously(self, action: str, context: dict | None = None) -> bool:
        """Determine if an action can be taken without approval."""
        context = context or {}
        evaluation = await self._evaluate_option(action, context)
        return (
            evaluation.risk_level in ("low", "medium")
            and evaluation.ethical_clear
        )
