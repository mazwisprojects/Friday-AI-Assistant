"""
Learning Engine for F.R.I.D.A.Y - Continuous learning and improvement.

Provides:
- Skill library management
- Mistake journaling
- Strategy evolution
- Meta-learning (learning how to learn)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A learned skill."""
    name: str
    level: float = 0.5
    category: str = "general"
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Mistake:
    """A recorded mistake."""
    id: str = ""
    description: str = ""
    context: str = ""
    lesson: str = ""
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False


@dataclass
class Interaction:
    """A recorded interaction."""
    id: str = ""
    description: str = ""
    success: bool = True
    actions: list[str] = field(default_factory=list)
    outcome: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class SkillLibrary:
    """Library of learned skills."""

    def __init__(self):
        self.skills: dict[str, Skill] = {}

    def add(self, skill: Skill) -> None:
        self.skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        return self.skills.get(name)

    def search(self, requirement: str) -> Optional[Skill]:
        """Search for a skill matching a requirement."""
        for skill in self.skills.values():
            if requirement.lower() in skill.name.lower():
                return skill
        return None

    def reinforce(self, skill_name: str) -> None:
        """Reinforce a skill after successful use."""
        skill = self.skills.get(skill_name)
        if skill:
            skill.success_count += 1
            skill.level = min(1.0, skill.level + 0.02)
            skill.last_used = time.time()


class MistakeJournal:
    """Journal of mistakes and lessons."""

    def __init__(self):
        self.mistakes: list[Mistake] = []

    def record(self, interaction: Interaction) -> None:
        """Record a mistake from a failed interaction."""
        mistake = Mistake(
            description=interaction.description,
            context=str(interaction.actions),
            lesson="To be derived",
        )
        self.mistakes.append(mistake)

    def get_unresolved(self) -> list[Mistake]:
        """Get unresolved mistakes."""
        return [m for m in self.mistakes if not m.resolved]

    def resolve(self, mistake_id: str, lesson: str) -> None:
        """Mark a mistake as resolved with a lesson."""
        for mistake in self.mistakes:
            if mistake.id == mistake_id:
                mistake.resolved = True
                mistake.lesson = lesson
                break


class StrategyEvolution:
    """Evolve strategies over time."""

    def __init__(self):
        self.strategies: dict[str, dict[str, Any]] = {}

    async def evolve(self, interaction: Interaction) -> None:
        """Evolve strategies based on interaction outcome."""
        for action in interaction.actions:
            if action not in self.strategies:
                self.strategies[action] = {"success": 0, "failure": 0}

            if interaction.success:
                self.strategies[action]["success"] += 1
            else:
                self.strategies[action]["failure"] += 1

    def get_best_strategy(self, action: str) -> float:
        """Get success rate for an action."""
        strategy = self.strategies.get(action)
        if not strategy:
            return 0.5
        total = strategy["success"] + strategy["failure"]

class LearningEngine:
    """Continuous learning and improvement."""

    def __init__(self):
        self.skill_library = SkillLibrary()
        self.mistake_journal = MistakeJournal()
        self.strategy_evolution = StrategyEvolution()
        self.meta_learner = MetaLearner()

    async def learn_from_interaction(self, interaction: Interaction) -> None:
        """Learn from every interaction."""
        if interaction.success:
            for action in interaction.actions:
                # Auto-discover skills from successful actions
                existing = self.skill_library.search(action)
                if existing:
                    self.skill_library.reinforce(action)
                else:
                    new_skill = Skill(name=action, level=0.3)
                    self.skill_library.add(new_skill)

        if not interaction.success:
            await self.mistake_journal.record(interaction)

        await self.strategy_evolution.evolve(interaction)
        await self.meta_learner.update(interaction)

    async def acquire_new_skill(self, skill_requirement: str) -> Optional[Skill]:
        """Autonomously learn a new skill when needed."""
        existing = self.skill_library.search(skill_requirement)
        if existing:
            return existing

        new_skill = Skill(name=skill_requirement, level=0.1)
        self.skill_library.add(new_skill)
        return new_skill

    def get_learning_stats(self) -> dict[str, Any]:
        """Get learning statistics."""
        return {
            "skill_count": len(self.skill_library.skills),
            "mistake_count": len(self.mistake_journal.mistakes),
            "unresolved_mistakes": len(self.mistake_journal.get_unresolved()),
            "best_approach": self.meta_learner.get_best_approach(),
        }

        return strategy["success"] / total if total > 0 else 0.5


class MetaLearner:
    """Learn how to learn better."""

    def __init__(self):
        self.learning_rate = 0.1
        self.approach_effectiveness: dict[str, float] = {}

    async def update(self, interaction: Interaction) -> None:
        """Update meta-learning based on interaction."""
        approach = interaction.metadata.get("approach", "default")
        if approach not in self.approach_effectiveness:
            self.approach_effectiveness[approach] = 0.5

        current = self.approach_effectiveness[approach]
        if interaction.success:
            self.approach_effectiveness[approach] = min(1.0, current + 0.05)
        else:
            self.approach_effectiveness[approach] = max(0.0, current - 0.02)

    def get_best_approach(self) -> str:
        """Get the most effective learning approach."""
        if not self.approach_effectiveness:
            return "default"
        return max(self.approach_effectiveness, key=self.approach_effectiveness.get)
