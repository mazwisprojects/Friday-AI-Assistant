"""Persistent execution history for Friday tools and background agents."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path


class ExecutionLedger:
    def __init__(self, root: str, limit: int = 500):
        self.path = Path(root) / "long_term_memory" / "execution_ledger.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.limit = limit
        self._lock = threading.RLock()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, entries: list[dict]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(entries[-self.limit:], indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        temporary.replace(self.path)

    def start(self, kind: str, name: str, goal: str = "", provider: str = "friday", arguments: dict | None = None) -> str:
        entry_id = str(uuid.uuid4())
        entry = {"id": entry_id, "kind": kind, "name": name, "goal": goal, "provider": provider, "arguments": arguments or {}, "started_at": time.time(), "finished_at": None, "status": "running", "result_summary": "", "error": None}
        with self._lock:
            entries = self._load()
            entries.append(entry)
            self._save(entries)
        return entry_id

    def finish(self, entry_id: str, status: str, result=None, error: str | None = None) -> None:
        with self._lock:
            entries = self._load()
            for entry in entries:
                if entry.get("id") == entry_id:
                    entry.update({"status": status, "finished_at": time.time(), "result_summary": str(result)[-4000:] if result is not None else "", "error": error})
                    break
            self._save(entries)

    def mark_scored(self, entry_id: str) -> None:
        with self._lock:
            entries = self._load()
            for entry in entries:
                if entry.get("id") == entry_id:
                    entry["scored"] = True
                    break
            self._save(entries)

    def list(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return self._load()[-max(1, min(limit, self.limit)):]
