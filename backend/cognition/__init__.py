"""
F.R.I.D.A.Y Cognitive Architecture - AGI Brain Systems

This package implements the core cognitive capabilities that transform
F.R.I.D.A.Y from a reactive assistant into a proactive AGI system.

Modules:
    reasoning_engine - Multi-step chain-of-thought reasoning
    world_model - Causal understanding and simulation
    identity - Persistent personality and self-model
    proactive_engine - Threat detection and anticipation
    agent_swarm - Multi-agent coordination
    learning_engine - Continuous learning and improvement
    situation_awareness - Deep context understanding
    decision_engine - Autonomous decision making
    knowledge_graph - Structured knowledge with relationships
    emotional_intelligence - Emotion detection and response
    core - Integration layer connecting all systems
"""

from .core import FridayCognition, CognitiveContext, CognitiveResponse
from .reasoning_engine import ReasoningEngine, ReasoningResult, ReasoningStep, SubProblem
from .world_model import WorldModel, Prediction, SimulationResult, Action, Scenario, SimulationPath
from .identity import FridayIdentity, PersonalityProfile, Belief, Experience, Skill
from .proactive_engine import ProactiveEngine, ProactiveAction, Threat
from .agent_swarm import AgentSwarm, Task, TaskResult, BaseAgent
from .learning_engine import LearningEngine, Interaction
from .situation_awareness import SituationAwareness, SituationAssessment
from .decision_engine import DecisionEngine, Decision, Evaluation
from .knowledge_graph import KnowledgeGraph, QueryResult, Entity, Relationship
from .emotional_intelligence import EmotionalIntelligence, EmotionalState

__all__ = [
    "FridayCognition",
    "ReasoningEngine",
    "ReasoningResult",
    "WorldModel",
    "Prediction",
    "SimulationResult",
    "FridayIdentity",
    "PersonalityProfile",
    "ProactiveEngine",
    "ProactiveAction",
    "AgentSwarm",
    "LearningEngine",
    "SituationAwareness",
    "SituationAssessment",
    "DecisionEngine",
    "Decision",
    "KnowledgeGraph",
    "EmotionalIntelligence",
    "EmotionalState",
]
