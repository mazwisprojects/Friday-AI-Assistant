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
    """Make autonomous decisions with appropriate confidence."""

    def __init__(self):
        self.risk_assessor = RiskAssessor()
        self.ethics_module = EthicsModule()

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
            )

        # Evaluate each option
        evaluations = []
        for option in options:
            evaluation = await self._evaluate_option(option, context)
            evaluations.append(evaluation)

        # Select best option
        best = max(evaluations, key=lambda e: e.score)

        # Determine if approval is needed
        needs_approval = (
            best.risk_level in ("high", "critical")
            or not best.ethical_clear
        )

        # Get alternatives
        alternatives = [e.option for e in evaluations if e.option != best.option][:3]

        return Decision(
            action=best.option,
            needs_approval=needs_approval,
            reasoning=best,
            urgency=context.get("urgency", "normal"),
            alternatives=alternatives,
            risks=[f"{best.risk_level} risk"],
            confidence=best.confidence,
        )

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
