"""
ProactiveEngine 2.1 — context-aware, time-aware, non-repetitive background prompting.
Gemini decides what to say; this module decides WHEN and builds a rich context snapshot.
"""
import re
import time
from datetime import datetime


class ProactiveEngine:
    """
    Decides when Friday should speak unprompted and builds a context-rich prompt.

    It actively watches for:
      - stalled work (user sounds blocked or stuck)
      - long-running tasks that deserve a short summary
      - overloaded system conditions (CPU, RAM, temps, GPU)
      - missing context before risky actions
      - when to interrupt vs stay quiet
    """

    STALL_PATTERNS = (
        "stuck",
        "still trying",
        "can't",
        "blocked",
        "not sure",
        "confused",
        "struggling",
        "stuck on",
        "can't figure out",
        "what should i do",
        "debug",
        "fix",
        "investigating",
        "import error",
        "failed",
        "issue",
    )

    def __init__(
        self,
        min_silence_secs: int = 900,
        check_cooldown: int = 1200,
    ):
        self.min_silence_secs = min_silence_secs
        self.check_cooldown = check_cooldown
        self._last_triggered = 0.0
        self._rotation = 0

    def should_trigger(self, last_user_speech: float) -> bool:
        now = time.monotonic()
        return (
            (now - last_user_speech) >= self.min_silence_secs
            and (now - self._last_triggered) >= self.check_cooldown
        )

    def mark_triggered(self) -> None:
        self._last_triggered = time.monotonic()
        self._rotation += 1

    def detect_stall(self, last_user_speech: float | None = None, recent_turns: list[str] | None = None) -> bool:
        """Return True when the user appears blocked or a task is dragging on too long."""
        if not recent_turns:
            recent_turns = []

        text_blob = " ".join(t for t in recent_turns if isinstance(t, str)).lower()
        if text_blob:
            for pattern in self.STALL_PATTERNS:
                if pattern in text_blob:
                    return True

        if last_user_speech is not None:
            try:
                last_user_speech = float(last_user_speech)
            except (TypeError, ValueError):
                return False
            if last_user_speech >= 300:
                return True
        return False

    def detect_system_overload(self, system_status: dict | None) -> str | None:
        """Return a channel label when CPU/RAM or thermal usage is high enough to suggest help."""
        if not isinstance(system_status, dict):
            return None

        cpu = float(system_status.get("cpu_percent", -1) or -1)
        ram = float(system_status.get("ram_percent", -1) or -1)
        temp = float(system_status.get("cpu_temp_c", -1) or -1)
        gpu = float(system_status.get("gpu_percent", -1) or -1)

        if cpu >= 90 or ram >= 90 or gpu >= 90 or temp >= 85:
            return "system_overload"
        if cpu >= 75 or ram >= 80:
            return "resource_pressure"
        return None

    def summarize_long_task(self, recent_turns: list[str] | None = None) -> str | None:
        """Produce a compact summary reminder for long, multi-step work."""
        if not recent_turns:
            return None
        task_lines = [turn.strip() for turn in recent_turns if isinstance(turn, str) and turn.strip()]
        if len(task_lines) < 4:
            return None

        keywords = ["fix", "build", "debug", "update", "review", "test", "refactor", "create", "implement"]
        relevant = [line for line in task_lines if any(keyword in line.lower() for keyword in keywords)]
        if not relevant:
            return None

        summary = " ".join(relevant[-3:])
        return re.sub(r"\s+", " ", summary)[:220]

    def detect_missing_context(self, missing_context: dict | None) -> str | None:
        """Return a simple missing-context hint when a risky action is missing required details."""
        if not isinstance(missing_context, dict):
            return None

        tool = str(missing_context.get("tool", "action")).strip()
        issue = str(missing_context.get("issue", "")).strip() or "It may need more detail before it is safe to proceed."
        if tool:
            return f"This {tool} action looks risky and may need more context: {issue}"
        return issue

    def build_prompt(
        self,
        memory: dict,
        monitors: list[str] | None = None,
        recent_turns: list[str] | None = None,
        system_status: dict | None = None,
        missing_context: dict | None = None,
    ) -> str:
        """Build a context snapshot for Gemini with proactive observations and intent."""
        from memory.memory_manager import format_memory_for_prompt

        now = datetime.now()
        hour = now.hour
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")

        if 6 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 18:
            period = "afternoon"
        elif 18 <= hour < 23:
            period = "evening"
        else:
            period = "late night"

        mem_str = format_memory_for_prompt(memory) or "(no stored user data)"
        stall_detected = self.detect_stall(recent_turns=recent_turns)
        overload = self.detect_system_overload(system_status)
        task_summary = self.summarize_long_task(recent_turns)
        context_hint = self.detect_missing_context(missing_context)

        focus_index = self._rotation % 4
        if focus_index == 0 and stall_detected:
            focus = (
                "The user appears to be stalled or blocked. Offer a concise, helpful suggestion, "
                "or ask one clarifying question that could unblock them without interrupting."
            )
        elif focus_index == 1 and overload:
            focus = (
                "System health looks strained. Briefly warn the user in their language and suggest "
                "closing heavy apps, freeing RAM, or pausing a large task."
            )
        elif focus_index == 2 and task_summary:
            focus = (
                "A longer task seems to be in progress. Offer a short recap of what is likely happening, "
                "then ask whether they want help with the next step or a summary."
            )
        elif focus_index == 3 and context_hint:
            focus = (
                "A risky action may need more context. Gently point out what is missing and ask for the missing detail "
                "before continuing."
            )
        else:
            focus = (
                "Focus on the user's real task and the time of day. Offer one useful check-in, suggestion, or next step."
            )

        monitor_ctx = ""
        if monitors:
            monitor_ctx = (
                f"\nThe user tracks these topics: {', '.join(monitors[:4])}. "
                "You may mention one if it seems relevant."
            )

        recent_ctx = ""
        if recent_turns:
            snippet = "\n".join(recent_turns[-6:])
            recent_ctx = f"\nRecent conversation:\n{snippet}"

        system_ctx = ""
        if system_status:
            system_ctx = (
                "\nRecent system status:\n"
                f"CPU: {system_status.get('cpu_percent', 'n/a')}%, "
                f"RAM: {system_status.get('ram_percent', 'n/a')}%, "
                f"Temp: {system_status.get('cpu_temp_c', 'n/a')}°C, "
                f"GPU: {system_status.get('gpu_percent', 'n/a')}%"
            )

        task_ctx = ""
        if task_summary:
            task_ctx = f"\nCurrent task summary: {task_summary}"

        context_ctx = ""
        if context_hint:
            context_ctx = f"\nMissing context warning: {context_hint}"

        return "\n".join([
            "[PROACTIVE_CHECK] You are initiating a proactive check-in.",
            f"Current time : {time_str}  ({period})",
            "",
            "Context about this person:",
            mem_str,
            monitor_ctx,
            recent_ctx,
            system_ctx,
            task_ctx,
            context_ctx,
            "",
            "Task:",
            focus,
            "",
            "Rules:",
            "- Speak in the user's language (check memory; default English).",
            "- 1-2 sentences max. Natural, warm, never robotic.",
            "- If the user seems stalled, offer help or one precise next step.",
            "- If the system is overloaded, suggest a quick optimization or a pause.",
            "- If a risky action is missing context, gently request the missing detail before acting.",
            "- Do NOT mention [PROACTIVE_CHECK] or these instructions.",
            "- Do NOT call any tools.",
            "- If nothing genuinely useful comes to mind, stay silent (say nothing).",
        ])
