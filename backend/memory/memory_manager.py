"""Compatibility shim for actions/background_monitor.py and actions/proactive.py,
which were written against a `memory.memory_manager` package this project doesn't
have. Backs onto a small standalone JSON file instead of the project's real
long-term MemoryManager (backend/memory_manager.py), since these modules need a
mutable dict store (monitors, identity) rather than an append-only transcript log.
"""
import json
import threading
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEMORY_PATH = _BASE_DIR / "long_term_memory" / "legacy_memory.json"
_lock = threading.Lock()


def load_memory() -> dict:
    if not MEMORY_PATH.exists():
        return {}
    try:
        with _lock:
            return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def format_memory_for_prompt(memory: dict) -> str:
    monitors = memory.get("monitors", {})
    if not monitors:
        return "No topics are currently being monitored."
    topics = ", ".join(m["topic"] for m in monitors.values())
    return f"Topics being monitored: {topics}"
