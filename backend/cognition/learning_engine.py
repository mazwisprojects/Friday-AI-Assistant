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
        return mistake

    def derive_lesson(self, mistake: Mistake) -> str:
        """Ask the LLM for a durable lesson from a mistake; heuristic fallback."""
        try:
            from model_router import generate_response
            prompt = (
                "Derive ONE short, durable lesson from this failure so the same "
                "mistake is never repeated. Be specific and actionable.\n\n"
                f"Failure: {mistake.description[:400]}\n"
                f"Context: {mistake.context[:300]}\n\n"
                'Return ONLY JSON: {"lesson": "..."}'
            )
            response = generate_response(prompt, "lite")
            if getattr(response, "ok", False):
                import json as _json, re as _re
                match = _re.search(r"\{.*\}", (response.text or ""), _re.DOTALL)
                if match:
                    lesson = _json.loads(match.group(0)).get("lesson", "")
                    if lesson:
                        return str(lesson)
        except Exception as e:
            logger.debug("Lesson derivation failed: %s", e)
        return f"Avoid repeating: {mistake.description[:120]}"

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

    def get_lessons(self, limit: int = 20) -> list[str]:
        """All derived lessons (most recent first), for injecting into session context."""
        return [m.lesson for m in reversed(self.mistakes) if m.lesson and m.lesson != "To be derived"][:limit]


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
        return strategy["success"] / total if total > 0 else 0.5

    def best_actions(self, limit: int = 5) -> list[str]:
        """Actions with the highest proven success rates (min 2 attempts)."""
        scored = []
        for action, s in self.strategies.items():
            total = s["success"] + s["failure"]
            if total >= 2:
                scored.append((s["success"] / total, action))
        scored.sort(reverse=True)
        return [a for _, a in scored[:limit]]

    def to_dict(self) -> dict[str, Any]:
        return {"strategies": self.strategies}

    def load_dict(self, data: dict[str, Any]) -> None:
        self.strategies = {str(k): v for k, v in (data.get("strategies") or {}).items() if isinstance(v, dict)}

class LearningEngine:
    """Continuous learning and improvement.

    P0.2: all learned state (skills, mistakes, strategies, meta-learner) is
    persisted to JSON on mutation and loaded on init — Friday stops repeating
    mistakes across restart, because the lessons survive.
    """

    def __init__(self, storage_path: str | None = None):
        self.skill_library = SkillLibrary()
        self.mistake_journal = MistakeJournal()
        self.strategy_evolution = StrategyEvolution()
        self.meta_learner = MetaLearner()
        self.storage_path = storage_path
        if storage_path:
            self.load()

    # ---------- persistence (P0.2) ----------

    def _resolve_storage(self):
        if self.storage_path:
            return self.storage_path
        try:
            from pathlib import Path
            p = Path(__file__).resolve().parent.parent / "long_term_memory" / "learning_state.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            return str(p)
        except Exception:
            return None

    def save(self, storage_path: str | None = None) -> bool:
        """Persist learning state to JSON."""
        path = self._resolve_storage() if storage_path is None else storage_path
        if not path:
            return False
        try:
            import json
            data = {
                "skills": [
                    {"name": s.name, "level": s.level, "category": s.category,
                     "created_at": s.created_at, "last_used": s.last_used,
                     "success_count": s.success_count, "failure_count": s.failure_count,
                     "metadata": s.metadata}
                    for s in self.skill_library.skills.values()
                ],
                "mistakes": [
                    {"id": m.id, "description": m.description, "context": m.context,
                     "lesson": m.lesson, "timestamp": m.timestamp, "resolved": m.resolved}
                    for m in self.mistake_journal.mistakes
                ],
                "strategies": self.strategy_evolution.strategies,
                "meta": self.meta_learner.approach_effectiveness,
            }
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=1)
            return True
        except Exception as e:
            logger.debug("Learning state save failed: %s", e)
            return False

    def load(self, storage_path: str | None = None) -> bool:
        """Load learning state from JSON (no-op on missing/corrupt)."""
        path = self._resolve_storage() if storage_path is None else storage_path
        if not path:
            return False
        try:
            import json, os
            if not os.path.exists(path):
                return False
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.skill_library.skills = {
                s["name"]: Skill(
                    name=s["name"], level=float(s.get("level", 0.5)),
                    category=s.get("category", "general"),
                    created_at=float(s.get("created_at", 0)),
                    last_used=float(s.get("last_used", 0)),
                    success_count=int(s.get("success_count", 0)),
                    failure_count=int(s.get("failure_count", 0)),
                    metadata=s.get("metadata", {}),
                )
                for s in data.get("skills", []) if isinstance(s, dict) and s.get("name")
            }
            self.mistake_journal.mistakes = [
                Mistake(
                    id=m.get("id", ""), description=m.get("description", ""),
                    context=m.get("context", ""), lesson=m.get("lesson", ""),
                    timestamp=float(m.get("timestamp", 0)),
                    resolved=bool(m.get("resolved", False)),
                )
                for m in data.get("mistakes", []) if isinstance(m, dict)
            ]
            self.strategy_evolution.strategies = {
                str(k): v for k, v in (data.get("strategies") or {}).items() if isinstance(v, dict)
            }
            self.meta_learner.approach_effectiveness = {
                str(k): float(v) for k, v in (data.get("meta") or {}).items()
            }
            return True
        except Exception as e:
            logger.debug("Learning state load failed: %s", e)
            return False

    def get_lessons(self, limit: int = 10) -> list[str]:
        """Durable lessons learned — injectable into session memory so Friday
        actually stops repeating mistakes in future conversations."""
        return self.mistake_journal.get_lessons(limit=limit)

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
            mistake = self.mistake_journal.record(interaction)
            try:
                mistake.lesson = await self.mistake_journal.derive_lesson(mistake)
            except Exception as e:
                logger.debug("Lesson derivation failed: %s", e)
                mistake.lesson = f"Avoid repeating: {mistake.description[:120]}"

        await self.strategy_evolution.evolve(interaction)
        await self.meta_learner.update(interaction)
        self.save()

    async def acquire_new_skill(self, skill_requirement: str) -> Optional[Skill]:
        """Autonomously learn a new skill when needed."""
        existing = self.skill_library.search(skill_requirement)
        if existing:
            return existing

        new_skill = Skill(name=skill_requirement, level=0.1)
        self.skill_library.add(new_skill)
        self.save()
        return new_skill

    def get_learning_stats(self) -> dict[str, Any]:
        """Get learning statistics."""
        return {
            "skill_count": len(self.skill_library.skills),
            "mistake_count": len(self.mistake_journal.mistakes),
            "unresolved_mistakes": len(self.mistake_journal.get_unresolved()),
            "best_approach": self.meta_learner.get_best_approach(),
            "lessons": self.get_lessons(limit=5),
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
