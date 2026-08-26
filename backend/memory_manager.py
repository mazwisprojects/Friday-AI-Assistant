import json
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path


class MemoryManager:
    """Global, non-project-scoped conversation memory.

    Every message from every project/session is appended here so nothing
    is ever lost, even if a project is deleted or the 'temp' project is
    wiped on startup. Writes go to two places:
      - long_term_memory/transcripts/<YYYY-MM-DD>.txt  (human-readable, append-only)
      - long_term_memory/memory_index.jsonl            (machine-readable, append-only)
    """

    def __init__(self, workspace_root: str):
        self.root_dir = Path(workspace_root) / "long_term_memory"
        self.transcript_dir = self.root_dir / "transcripts"
        self.index_file = self.root_dir / "memory_index.jsonl"
        self.facts_file = self.root_dir / "facts.jsonl"
        self._lock = threading.Lock()

        self.transcript_dir.mkdir(parents=True, exist_ok=True)

    def _today_file(self) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.transcript_dir / f"{date_str}.txt"

    def append_message(self, sender: str, text: str, project: str = None):
        """Appends a message to today's transcript file and the global index."""
        if not text or not text.strip():
            return

        timestamp = datetime.now().isoformat(timespec="seconds")

        transcript_line = f"[{timestamp}] {sender}: {text.strip()}\n"
        entry = {
            "timestamp": timestamp,
            "sender": sender,
            "text": text,
            "project": project,
        }
        with self._lock:
            with open(self._today_file(), "a", encoding="utf-8") as f:
                f.write(transcript_line)

            # Machine-readable index for later search/retrieval
            with open(self.index_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def save_facts(self, facts: list[str], source: str = ""):
        """Appends durable facts while filtering secrets and exact duplicates."""
        cleaned = {
            fact.strip() for fact in facts
            if isinstance(fact, str)
            and fact.strip()
            and len(fact.strip()) <= 500
            and not self._looks_like_secret(fact)
        }
        if not cleaned:
            return

        timestamp = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            existing = set()
            if self.facts_file.exists():
                with open(self.facts_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            fact = json.loads(line).get("fact", "").strip().lower()
                            if fact:
                                existing.add(fact)
                        except json.JSONDecodeError:
                            continue

            with open(self.facts_file, "a", encoding="utf-8") as f:
                for fact in sorted(cleaned):
                    if fact.lower() in existing:
                        continue
                    f.write(json.dumps({
                        "timestamp": timestamp,
                        "fact": fact,
                        "source": source,
                    }, ensure_ascii=False) + "\n")

    @staticmethod
    def _looks_like_secret(fact: str) -> bool:
        """Reject common credentials even if the model accidentally returns one."""
        lowered = fact.lower()
        secret_terms = (
            "password", "passcode", "api key", "apikey", "token", "secret",
            "private key", "access key", "verification code",
        )
        return any(term in lowered for term in secret_terms) or bool(
            re.search(r"(?:sk-|AIza|ghp_|xox[baprs]-)[A-Za-z0-9_-]{12,}", fact)
        )

    def get_facts(self, limit: int = 100):
        """Returns durable facts, newest first, without deleting older facts."""
        if not self.facts_file.exists():
            return []

        facts = []
        with open(self.facts_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    facts.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return facts[-limit:]

    def list_transcript_files(self):
        """Returns all daily transcript filenames, oldest first."""
        files = sorted(self.transcript_dir.glob("*.txt"))
        return [f.name for f in files]

    def read_transcript(self, date_str: str) -> str:
        """Reads a specific day's transcript, e.g. '2026-08-24'."""
        file_path = self.transcript_dir / f"{date_str}.txt"
        if not file_path.exists():
            return ""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_recent_messages(self, limit: int = 20):
        """Returns the last 'limit' messages across all conversations, ever."""
        if not self.index_file.exists():
            return []

        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"[MemoryManager] [ERR] Failed to read index: {e}")
            return []

        history = []
        for line in lines[-limit:]:
            try:
                history.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return history

    def search(self, query: str, limit: int = 20):
        """Simple keyword search over the entire lifetime of the index."""
        if not query.strip():
            return []

        terms = query.lower().split()
        fact_matches = []
        for fact in self.get_facts(limit=limit):
            haystack = fact.get("fact", "").lower()
            if all(term in haystack for term in terms):
                fact_matches.append({**fact, "sender": "FACT", "text": fact.get("fact", "")})

        message_matches = []
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    haystack = f"{entry.get('sender', '')} {entry.get('text', '')}".lower()
                    if all(term in haystack for term in terms):
                        message_matches.append(entry)

        return (fact_matches[-limit:] + message_matches[-limit:])[:limit]
