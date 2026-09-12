"""
Agent Swarm for F.R.I.D.A.Y - Multi-agent coordination.

Provides:
- Specialized agent types
- Task decomposition and assignment
- Parallel execution
- Result synthesis
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from .event_bus import CognitiveEvent

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """A task to be executed."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    task_type: str = "general"
    priority: int = 0
    status: str = "pending"
    result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of task execution."""
    task_id: str
    success: bool
    result: Any = None
    error: str = ""
    execution_time: float = 0.0


class BaseAgent:
    """Base class for specialized agents."""

    def __init__(self, name: str, agent_type: str):
        self.name = name
        self.agent_type = agent_type
        self.status = "idle"
        self._task_history: list[TaskResult] = []

    async def execute(self, task: Task) -> TaskResult:
        """Execute a task."""
        self.status = "working"
        try:
            result = await self._process(task)
            self.status = "idle"
            return TaskResult(task_id=task.id, success=True, result=result)
        except Exception as e:
            self.status = "failed"
            return TaskResult(task_id=task.id, success=False, error=str(e))

    async def _process(self, task: Task) -> Any:
        """Process the task - override in subclasses."""
        return f"Processed by {self.name}: {task.description}"


class SecurityAgent(BaseAgent):
    """Handles security-related tasks."""

    def __init__(self):
        super().__init__("SecurityAgent", "security")

    async def _process(self, task: Task) -> Any:
        """Process security task."""
        return {"status": "secured", "threats_found": 0}


class ResearchAgent(BaseAgent):
    """Handles research and information gathering."""

    def __init__(self):
        super().__init__("ResearchAgent", "research")

    async def _process(self, task: Task) -> Any:
        """Process research task."""
        return {"findings": [], "sources": []}


class OperationsAgent(BaseAgent):
    """Handles operational tasks."""

    def __init__(self):
        super().__init__("OperationsAgent", "operations")

    async def _process(self, task: Task) -> Any:
        """Process operations task."""
        return {"status": "completed", "actions_taken": []}


class AnalysisAgent(BaseAgent):
    """Handles analysis tasks."""

    def __init__(self):
        super().__init__("AnalysisAgent", "analysis")

    async def _process(self, task: Task) -> Any:
        """Process analysis task."""
        return {"insights": [], "confidence": 0.0}


class SwarmCoordinator:
    """Coordinates multiple agents."""

    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent with the coordinator."""
        self.agents[agent.agent_type] = agent

    def get_agent(self, agent_type: str) -> Optional[BaseAgent]:
        """Get an agent by type."""
        return self.agents.get(agent_type)

    async def decompose(self, task_description: str) -> list[Task]:
        """Decompose a complex task into sub-tasks."""
        return [Task(description=task_description)]

    async def synthesize(self, results: list[TaskResult]) -> dict[str, Any]:
        """Synthesize results from multiple agents."""
        return {
            "success_count": sum(1 for r in results if r.success),
            "failure_count": sum(1 for r in results if not r.success),
            "results": [r.result for r in results],
        }


class AgentSwarm:
    """Coordinate multiple specialized agents.

    P2.6: in addition to the in-memory cognitive agents, the swarm bridges to
    the REAL agent_dispatcher registry (repo_repair, dev_agent, plugins) — so
    complex tasks run through actual background agents instead of shells.
    """

    def __init__(self, event_bus=None):
        self.coordinator = SwarmCoordinator()
        self._initialize_agents()
        self.event_bus = event_bus  # P4.1: publishes completions for the live bridge
        self.dispatcher = None
        try:
            from actions import agent_dispatcher as _ad
            self.dispatcher = _ad.dispatcher
        except Exception as e:
            logger.debug("agent_dispatcher unavailable: %s", e)

    def _initialize_agents(self) -> None:
        """Initialize default agents."""
        self.coordinator.register_agent(SecurityAgent())
        self.coordinator.register_agent(ResearchAgent())
        self.coordinator.register_agent(OperationsAgent())
        self.coordinator.register_agent(AnalysisAgent())

    async def handle_complex_task(self, task_description: str) -> dict[str, Any]:
        """Break down complex tasks and coordinate agents."""
        # Decompose task
        sub_tasks = await self.coordinator.decompose(task_description)

        # Execute tasks
        results = []
        for sub in sub_tasks:
            # Select best agent
            agent = self._select_agent(sub)
            if agent:
                result = await agent.execute(sub)
                results.append(result)

        # If the real dispatcher has registered agents and the task is
        # long-running, offer delegation to a real background agent.
        delegated = None
        if self.dispatcher:
            try:
                registered = self.dispatcher.registered_agents()
                if registered and ("delegate" in task_description.lower()
                                   or "fix" in task_description.lower()
                                   or "repair" in task_description.lower()):
                    # Prefer the most relevant registered type
                    chosen = next(
                        (t for t in registered if t in task_description.lower()),
                        registered[0])
                    delegated = {
                        "agent_id": self.dispatcher.deploy_agent(
                            chosen, goal=task_description, repo_path="."),
                        "agent_type": chosen,
                    }
                    if delegated["agent_id"]:
                        results.append({
                            "task_id": "delegated",
                            "success": True,
                            "result": delegated,
                        })
            except Exception as e:
                logger.debug("Dispatcher delegation failed: %s", e)

        # Synthesize results
        output = await self.coordinator.synthesize(results)
        if delegated:
            output["delegated"] = delegated

        # P4.1: completions reach the live bridge as 'info' (logged, not spoken —
        # the session consumer decides what's worth interrupting Sir for).
        if self.event_bus is not None:
            try:
                self.event_bus.publish(CognitiveEvent(
                    topic="swarm_result",
                    summary=f"Swarm task complete: {task_description[:100]}",
                    priority="info",
                    payload={
                        "success_count": output.get("success_count", 0),
                        "delegated": bool(output.get("delegated")),
                    },
                    dedupe_key=f"swarm:{task_description[:60]}",
                ))
            except Exception:
                logger.debug("Swarm event publish failed", exc_info=True)
        return output

    def _select_agent(self, task: Task) -> Optional[BaseAgent]:
        """Select the best agent for a task."""
        type_mapping = {
            "security": "security",
            "research": "research",
            "analysis": "analysis",
            "operations": "operations",
        }
        agent_type = type_mapping.get(task.task_type, "operations")
        return self.coordinator.get_agent(agent_type)

    def get_agent_status(self) -> dict[str, str]:
        """Get status of all agents."""
        return {name: agent.status for name, agent in self.coordinator.agents.items()}
