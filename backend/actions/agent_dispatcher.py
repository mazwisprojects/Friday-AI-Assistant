import threading
import time
import uuid

from actions import repo_repair_agent


class AgentDispatcher:
    """Runs long tasks as independent background agents so the caller never blocks.

    Each deployed agent runs on its own thread. Progress and results are polled
    via get_status()/list_agents() instead of waiting on the deploy call.
    """

    def __init__(self):
        self._registry = {}
        self._agents = {}
        self._lock = threading.Lock()

    def register_agent(self, agent_type: str, function):
        self._registry[agent_type] = function

    def _run(self, agent_id: str, agent_type: str, function, goal: str, repo_path: str, cancel_event: threading.Event):
        entry = self._agents[agent_id]

        def log(message: str):
            with self._lock:
                entry["log"].append({"time": time.time(), "message": message})

        try:
            result = function(goal, repo_path, log, cancel_event)
            with self._lock:
                entry["status"] = "cancelled" if cancel_event.is_set() else "done"
                entry["result"] = result
                entry["finished_at"] = time.time()
        except Exception as error:
            with self._lock:
                entry["status"] = "failed"
                entry["error"] = str(error)
                entry["finished_at"] = time.time()

    def deploy_agent(self, agent_type: str, goal: str, repo_path: str = ".") -> str:
        function = self._registry.get(agent_type)
        if function is None:
            raise ValueError(f"Unknown agent type: '{agent_type}'")

        agent_id = str(uuid.uuid4())
        cancel_event = threading.Event()
        with self._lock:
            self._agents[agent_id] = {
                "id": agent_id,
                "agent_type": agent_type,
                "goal": goal,
                "repo_path": repo_path,
                "status": "running",
                "result": None,
                "error": None,
                "log": [],
                "started_at": time.time(),
                "finished_at": None,
                "_cancel_event": cancel_event,
            }

        thread = threading.Thread(
            target=self._run,
            args=(agent_id, agent_type, function, goal, repo_path, cancel_event),
            daemon=True,
        )
        thread.start()
        return agent_id

    def get_status(self, agent_id: str) -> dict:
        with self._lock:
            entry = self._agents.get(agent_id)
            if not entry:
                return {"status": "unknown", "error": f"No agent found with id '{agent_id}'"}
            return {k: v for k, v in entry.items() if not k.startswith("_")}

    def list_agents(self) -> list:
        with self._lock:
            return [{k: v for k, v in entry.items() if not k.startswith("_")} for entry in self._agents.values()]

    def cancel(self, agent_id: str) -> bool:
        with self._lock:
            entry = self._agents.get(agent_id)
            if not entry:
                return False
            entry["_cancel_event"].set()
            return True


dispatcher = AgentDispatcher()
dispatcher.register_agent("repo_repair", repo_repair_agent.run)


def agent_dispatcher_action(parameters: dict, dispatcher: AgentDispatcher = dispatcher) -> dict:
    """Tool-facing dispatch for deploy/status/list/cancel actions."""
    if not isinstance(parameters, dict):
        return {"error": "No parameters provided."}

    action = str(parameters.get("action", "")).strip().lower()

    if action == "deploy":
        agent_type = str(parameters.get("agent_type", "")).strip()
        goal = str(parameters.get("goal", "")).strip()
        repo_path = str(parameters.get("repo_path", ".") or ".")
        try:
            agent_id = dispatcher.deploy_agent(agent_type, goal=goal, repo_path=repo_path)
        except ValueError as error:
            return {"error": str(error)}
        return {"agent_id": agent_id, "status": "running"}

    if action == "status":
        agent_id = str(parameters.get("agent_id", "")).strip()
        return dispatcher.get_status(agent_id)

    if action == "list":
        return {"agents": dispatcher.list_agents()}

    if action == "cancel":
        agent_id = str(parameters.get("agent_id", "")).strip()
        cancelled = dispatcher.cancel(agent_id)
        return {"cancelled": cancelled}

    return {"error": f"Unknown agent_dispatcher action: '{action}'"}
