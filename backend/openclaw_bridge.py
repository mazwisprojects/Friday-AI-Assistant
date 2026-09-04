"""Gemini-backed orchestration bridge for Friday's tools and agents."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from typing import Any

from google import genai
from tools import tools_list


class OpenClawBridge:
    """Coordinates text planning and background delegation without replacing Gemini Live."""

    def __init__(self, plugin_manager, dispatcher, api_key: str | None = None):
        self.plugin_manager = plugin_manager
        self.dispatcher = dispatcher
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = os.getenv("FRIDAY_ORCHESTRATOR_MODEL", "gemini-2.5-flash")
        self.tool_executor = None

    def set_tool_executor(self, executor) -> None:
        """Attach Friday's guarded core-tool executor after AudioLoop starts."""
        self.tool_executor = executor

    def status(self) -> dict:
        reachable = False
        try:
            with socket.create_connection(("127.0.0.1", int(os.getenv("OPENCLAW_GATEWAY_PORT", "18789"))), timeout=1):
                reachable = True
        except OSError:
            pass
        return {
            "available": bool(self.api_key),
            "reachable": reachable,
            "provider": "gemini",
            "model": self.model,
            "plugins": len(self.plugin_manager.list_plugins()),
            "agents": len(self.dispatcher.list_agents()),
        }

    def capabilities(self) -> dict:
        return {
            "friday_tools": self.tool_catalog(),
            "plugins": self.plugin_manager.list_plugins(),
            "agents": self.dispatcher.list_agents(),
            "health": self.plugin_manager.health(),
        }

    @staticmethod
    def tool_catalog() -> list[dict]:
        """Expose Friday's registered core tools to the external orchestrator."""
        return [
            {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {}).get("properties", {}),
            }
            for tool in tools_list[0].get("function_declarations", [])
            if tool.get("name") not in {"openclaw_plan", "openclaw_capabilities", "openclaw_delegate"}
        ]

    def should_route(self, text: str) -> bool:
        """Route deliberate multi-step reasoning to OpenClaw, not live voice chat."""
        normalized = " ".join(text.lower().split())
        patterns = (
            "analyze this project", "analyse this project", "build a new tool",
            "create a background agent", "plan my day", "investigate this error",
            "review my code", "summarize many files", "summarise many files",
            "create a plugin", "monitor flight prices", "find patterns in my emails",
        )
        return any(pattern in normalized for pattern in patterns)

    def plan(self, goal: str) -> dict:
        if not goal.strip():
            raise ValueError("A goal is required")
        context = json.dumps(self.capabilities(), ensure_ascii=False, default=str)[:20000]
        prompt = (
            "You are Friday's task orchestrator. Create a concise execution plan for the user's goal. "
            "Use only listed Friday tools, plugins, and agents. Do not invent capabilities. Return ONLY JSON with this shape: "
            "{\"goal\":\"...\",\"steps\":[{\"tool\":\"registered_tool_name\",\"arguments\":{},\"reason\":\"...\"}],\"needs_user_input\":false}.\n\n"
            f"Available capabilities:\n{context}\n\nUser goal: {goal}"
        )
        raw = self._run_openclaw(prompt)
        if raw is None:
            if not self.api_key:
                raise RuntimeError("Neither OpenClaw nor GEMINI_API_KEY is configured")
            response = genai.Client(api_key=self.api_key).models.generate_content(model=self.model, contents=prompt)
            raw = (response.text or "{}").strip().strip("`")
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Orchestrator returned invalid JSON: {exc}") from exc
        if not isinstance(plan, dict) or not isinstance(plan.get("steps", []), list):
            raise RuntimeError("Orchestrator returned an invalid plan")
        return plan

    def validate_plan(self, plan: dict) -> dict:
        if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list):
            raise ValueError("OpenClaw plan must contain a steps list")
        known_tools = {entry["name"] for entry in self.tool_catalog()}
        known_agents = set(self.dispatcher.registered_agents())
        validated = []
        for index, step in enumerate(plan["steps"]):
            if not isinstance(step, dict) or not isinstance(step.get("tool"), str):
                raise ValueError(f"OpenClaw step {index + 1} is invalid")
            tool = step["tool"]
            arguments = step.get("arguments", {})
            if not isinstance(arguments, dict):
                raise ValueError(f"OpenClaw step {index + 1} arguments must be an object")
            if tool not in known_tools and tool not in known_agents:
                raise ValueError(f"OpenClaw requested unregistered capability: {tool}")
            validated.append({"tool": tool, "arguments": arguments, "reason": step.get("reason", "")})
        return {"goal": plan.get("goal", ""), "steps": validated, "needs_user_input": bool(plan.get("needs_user_input", False))}

    def execute_plan(self, plan: dict, repo_path: str = ".") -> dict:
        """Execute a validated plan through Friday's guarded tool boundary."""
        validated = self.validate_plan(plan)
        agent_types = set(self.dispatcher.registered_agents())
        results = []
        for step in validated["steps"]:
            tool = step["tool"]
            args = step["arguments"]
            if tool in agent_types:
                agent_id = self.dispatcher.deploy_agent(tool, args.get("goal", validated["goal"]), args.get("repo_path", repo_path))
                results.append({"tool": tool, "status": "running", "agent_id": agent_id})
            elif tool in self.plugin_manager.tool_builder.tools:
                results.append({"tool": tool, "status": "completed", "result": self.plugin_manager.tool_builder.execute(tool, args)})
            elif self.tool_executor:
                results.append({"tool": tool, "status": "completed", "result": self.tool_executor(tool, args)})
            else:
                raise RuntimeError("Friday's live tool executor is not ready")
        return {"goal": validated["goal"], "results": results, "validated": True}

    @staticmethod
    def _run_openclaw(prompt: str) -> str | None:
        """Use the installed OpenClaw Gateway CLI when its local identity is paired."""
        command = os.getenv("FRIDAY_OPENCLAW_COMMAND") or shutil.which("openclaw") or shutil.which("openclaw.cmd") or "openclaw"
        for attempt in range(1, 3):
            try:
                result = subprocess.run(
                    [command, "agent", "--agent", os.getenv("OPENCLAW_AGENT", "main"), "--message", prompt, "--json", "--timeout", "45"],
                    capture_output=True, text=True, timeout=60, check=False,
                )
                if result.returncode == 0:
                    payload = json.loads(result.stdout)
                    if payload.get("ok") is not False:
                        return payload.get("result", {}).get("text") or payload.get("text") or "{}"
                print(f"[OPENCLAW] attempt {attempt}/2 failed: {(result.stderr or result.stdout).strip()[:300]}")
            except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                print(f"[OPENCLAW] attempt {attempt}/2 unavailable: {exc}")
        print("[OPENCLAW] bounded retries exhausted; using Gemini fallback")
        return None

    def delegate(self, agent_type: str, goal: str, repo_path: str = ".") -> dict:
        if agent_type not in {entry.get("agent_type") for entry in self.dispatcher.list_agents()}:
            raise ValueError(f"Agent is not registered: {agent_type}")
        agent_id = self.dispatcher.deploy_agent(agent_type, goal, repo_path)
        return {"agent_id": agent_id, "agent_type": agent_type, "status": "running"}
