import json
import hashlib
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

    def save_facts(self, facts: list, source: str = ""):
        """Append facts and supersede older values for the same subject."""
        candidates = []
        for item in facts:
            if isinstance(item, str):
                fact_text = item.strip()
                candidate = {"subject": self._subject_from_text(fact_text), "value": fact_text}
            elif isinstance(item, dict):
                candidate = {
                    "subject": str(item.get("subject", "")).strip().lower(),
                    "value": str(item.get("value", "")).strip(),
                    "confidence": item.get("confidence", 1.0),
                }
            else:
                continue
            if candidate["subject"] and candidate["value"] and len(candidate["value"]) <= 500 and not self._looks_like_secret(candidate["value"]):
                candidates.append(candidate)

        if not candidates:
            return

        timestamp = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            records = []
            if self.facts_file.exists():
                with open(self.facts_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            record = json.loads(line)
                            if "subject" not in record:
                                record = {
                                    **record,
                                    "subject": self._subject_from_text(record.get("fact", "")),
                                    "value": record.get("fact", ""),
                                    "status": "active",
                                }
                            records.append(record)
                        except json.JSONDecodeError:
                            continue

            with open(self.facts_file, "a", encoding="utf-8") as f:
                for candidate in candidates:
                    subject = candidate["subject"]
                    value = candidate["value"]
                    current = next((record for record in reversed(records) if record.get("subject") == subject and record.get("status", "active") == "active"), None)
                    if current and current.get("value", "").strip().lower() == value.lower():
                        continue
                    if current:
                        current["status"] = "superseded"
                        current["superseded_at"] = timestamp
                    record = {
                        "timestamp": timestamp,
                        "subject": subject,
                        "value": value,
                        "fact": value,
                        "confidence": candidate.get("confidence", 1.0),
                        "status": "active",
                        "source": source,
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    records.append(record)

    @staticmethod
    def _subject_from_text(fact: str) -> str:
        lowered = fact.lower()
        if "girlfriend" in lowered or "boyfriend" in lowered or "partner" in lowered:
            return "user.relationship.partner"
        if "user's name" in lowered or "user is" in lowered or "full name" in lowered:
            return "user.identity.name"
        digest = hashlib.sha256(lowered.encode("utf-8")).hexdigest()[:16]
        return f"fact.{digest}"

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

    def get_facts(self, limit: int = 100, active_only: bool = True):
        """Returns durable facts, optionally excluding superseded records."""
        if not self.facts_file.exists():
            return []

        records_by_subject = {}
        with open(self.facts_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    subject = record.get("subject") or self._subject_from_text(record.get("fact", ""))
                    records_by_subject[subject] = record
                except json.JSONDecodeError:
                    continue
        facts = list(records_by_subject.values())
        if active_only:
            facts = [record for record in facts if record.get("status", "active") == "active"]
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
            haystack = f"{fact.get('subject', '')} {fact.get('value', fact.get('fact', ''))}".lower()
            if all(term in haystack for term in terms):
                fact_matches.append({**fact, "sender": "FACT", "text": fact.get("value", fact.get("fact", ""))})

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
