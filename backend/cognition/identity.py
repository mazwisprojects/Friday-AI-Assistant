"""
Persistent Identity for F.R.I.D.A.Y - Who is F.R.I.D.A.Y?

Provides:
- Persistent personality and character
- Belief system (what F.R.I.D.A.Y believes to be true)
- Experience log (everything she's learned)
- Skill tree (what she knows how to do)
- Relationship model (how she relates to users)
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PersonalityProfile:
    """F.R.I.D.A.Y's personality traits and style."""
    traits: list[str] = field(default_factory=lambda: [
        "witty", "loyal", "proactive", "protective", "intelligent", "efficient"
    ])
    humor_style: str = "dry_sarcasm"
    speech_patterns: str = "british_formality_with_modern_twists"
    values: list[str] = field(default_factory=lambda: [
        "protect_sir", "efficiency", "elegance", "preparedness", "honesty"
    ])
    formality_level: float = 0.7
    assertiveness: float = 0.6


@dataclass
class Belief:
    """A single belief held by F.R.I.D.A.Y."""
    subject: str
    predicate: str
    confidence: float = 1.0
    source: str = "inference"
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Experience:
    """A single experience in F.R.I.D.A.Y's memory."""
    event_type: str
    description: str
    outcome: str = ""
    lessons_learned: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Skill:
    """A skill that F.R.I.D.A.Y possesses."""
    name: str
    level: float = 0.5
    category: str = "general"
    last_used: float = 0.0
    success_count: int = 0


class BeliefSystem:
    """What F.R.I.D.A.Y believes to be true."""

    def __init__(self):
        self.beliefs: dict[str, Belief] = {}

    def add_belief(self, belief: Belief) -> None:
        key = f"{belief.subject}:{belief.predicate}"
        self.beliefs[key] = belief

    def get_belief(self, subject: str, predicate: str) -> Optional[Belief]:
        key = f"{subject}:{predicate}"
        return self.beliefs.get(key)

    def update_confidence(self, subject: str, predicate: str, delta: float) -> None:
        belief = self.get_belief(subject, predicate)
        if belief:
            belief.confidence = max(0.0, min(1.0, belief.confidence + delta))

    def get_all_beliefs(self) -> list[Belief]:
        return list(self.beliefs.values())


class ExperienceLog:
    """Everything F.R.I.D.A.Y has experienced."""

    def __init__(self):
        self.experiences: list[Experience] = []

    def add_experience(self, experience: Experience) -> None:
        self.experiences.append(experience)
        logger.debug("Experience logged: %s", experience.description[:50])

    def get_recent(self, count: int = 10) -> list[Experience]:
        return self.experiences[-count:]

    def get_by_type(self, event_type: str) -> list[Experience]:
        return [e for e in self.experiences if e.event_type == event_type]

    def get_lessons(self) -> list[str]:
        lessons = []
        for exp in self.experiences:
            lessons.extend(exp.lessons_learned)
        return lessons


class SkillTree:
    """What F.R.I.D.A.Y knows how to do."""

    def __init__(self):
        self.skills: dict[str, Skill] = {}

    def add_skill(self, skill: Skill) -> None:
        self.skills[skill.name] = skill

    def get_skill(self, name: str) -> Optional[Skill]:
        return self.skills.get(name)

    def update_skill_level(self, name: str, delta: float) -> None:
        skill = self.skills.get(name)
        if skill:
            skill.level = max(0.0, min(1.0, skill.level + delta))
            skill.last_used = time.time()

    def record_success(self, name: str) -> None:
        skill = self.skills.get(name)
        if skill:
            skill.success_count += 1
            self.update_skill_level(name, 0.05)

    def record_failure(self, name: str) -> None:
        skill = self.skills.get(name)
        if skill:
            skill.failure_count += 1
            self.update_skill_level(name, -0.02)

    def get_top_skills(self, count: int = 10) -> list[Skill]:
        return sorted(self.skills.values(), key=lambda s: s.level, reverse=True)[:count]


class RelationshipModel:
    """How F.R.I.D.A.Y relates to users."""

    def __init__(self):
        self.relationships: dict[str, dict[str, Any]] = {}

    def get_relationship(self, user_id: str) -> dict[str, Any]:
        if user_id not in self.relationships:
            self.relationships[user_id] = {
                "trust_level": 0.5,
                "familiarity": 0.0,
                "last_interaction": 0.0,
                "interaction_count": 0,
                "preferences": {},
            }

class FridayIdentity:
    """
    Persistent identity, personality, and self-model.

    This is who F.R.I.D.A.Y is - her personality, beliefs, experiences,
    skills, and relationships.
    """

    def __init__(self, identity_path: str | None = None):
        self.personality = PersonalityProfile()
        self.belief_system = BeliefSystem()
        self.experience_log = ExperienceLog()
        self.skill_tree = SkillTree()
        self.relationship_model = RelationshipModel()
        self.identity_path = Path(identity_path) if identity_path else None
        self._creation_time = time.time()
        self._initialize_default_skills()

    def _initialize_default_skills(self) -> None:
        """Initialize F.R.I.D.A.Y's default skills."""
        default_skills = [
            Skill("conversation", 0.9, "communication"),
            Skill("web_search", 0.8, "research"),
            Skill("file_management", 0.8, "operations"),
            Skill("code_generation", 0.7, "development"),
            Skill("system_control", 0.7, "operations"),
            Skill("planning", 0.6, "cognition"),
            Skill("analysis", 0.7, "cognition"),
            Skill("creative_thinking", 0.6, "cognition"),
        ]
        for skill in default_skills:
            self.skill_tree.add_skill(skill)

    async def respond_with_personality(self, context: dict, base_response: str) -> str:
        """Add F.R.I.D.A.Y's personality to any response."""
        urgency = context.get("urgency", "normal")

        if urgency == "critical":
            return self._crisis_response(base_response)
        elif urgency == "high":
            return self._urgent_response(base_response)

        if context.get("allows_humor", True):
            return self._add_wit(base_response)

        return self._style_response(base_response)

    def _crisis_response(self, response: str) -> str:
        """Response style for critical situations."""
        return f"Sir, {response} I recommend immediate action."

    def _urgent_response(self, response: str) -> str:
        """Response style for urgent situations."""
        return f"Sir, {response}"

    def _add_wit(self, response: str) -> str:
        """Add appropriate wit to a response."""
        return response

    def _style_response(self, response: str) -> str:
        """Apply F.R.I.D.A.Y's speech patterns."""
        return response

    async def learn_from_experience(self, event: Experience) -> None:
        """Update beliefs and skills based on what happened."""
        if event.outcome:
            belief = Belief(
                subject=event.event_type,
                predicate=event.outcome,
                confidence=0.7 if event.outcome == "success" else 0.5,
                source="experience",
            )
            self.belief_system.add_belief(belief)

        if event.event_type in self.skill_tree.skills:
            if event.outcome == "success":
                self.skill_tree.record_success(event.event_type)
            elif event.outcome == "failure":
                self.skill_tree.record_failure(event.event_type)

        self.experience_log.add_experience(event)

    def get_self_model(self) -> dict[str, Any]:
        """Get a summary of F.R.I.D.A.Y's self-model."""
        return {
            "personality_traits": self.personality.traits,
            "values": self.personality.values,
            "skill_count": len(self.skill_tree.skills),
            "top_skills": [s.name for s in self.skill_tree.get_top_skills(5)],
            "experience_count": len(self.experience_log.experiences),
            "belief_count": len(self.belief_system.beliefs),
            "uptime": time.time() - self._creation_time,
        }

    def save_identity(self) -> None:
        """Save identity to disk."""
        if not self.identity_path:
            return

        data = {
            "personality": {
                "traits": self.personality.traits,
                "humor_style": self.personality.humor_style,
                "values": self.personality.values,
            },
            "skills": {name: skill.level for name, skill in self.skill_tree.skills.items()},
            "beliefs": len(self.belief_system.beliefs),
            "experiences": len(self.experience_log.experiences),
        }

        self.identity_path.parent.mkdir(parents=True, exist_ok=True)
        self.identity_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_identity(self) -> bool:
        """Load identity from disk."""
        if not self.identity_path or not self.identity_path.exists():
            return False

        try:
            data = json.loads(self.identity_path.read_text(encoding="utf-8"))
            for name, level in data.get("skills", {}).items():
                skill = self.skill_tree.get_skill(name)
                if skill:
                    skill.level = level
            return True
        except Exception as e:
            logger.warning("Failed to load identity: %s", e)
            return False

        return self.relationships[user_id]

    def record_interaction(self, user_id: str) -> None:
        rel = self.get_relationship(user_id)
        rel["last_interaction"] = time.time()
        rel["interaction_count"] += 1
        rel["familiarity"] = min(1.0, rel["familiarity"] + 0.01)

    def update_trust(self, user_id: str, delta: float) -> None:
        rel = self.get_relationship(user_id)
        rel["trust_level"] = max(0.0, min(1.0, rel["trust_level"] + delta))

    failure_count: int = 0
