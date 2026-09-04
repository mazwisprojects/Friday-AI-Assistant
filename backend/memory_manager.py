import json
import hashlib
import os
import re
import shutil
import threading
import time
from contextlib import contextmanager
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

    MAX_MESSAGE_BYTES = 2 * 1024 * 1024
    MAX_UPLOAD_BYTES = 25 * 1024 * 1024
    MAX_UPLOAD_STORAGE_BYTES = 1024 * 1024 * 1024
    UPLOAD_RETENTION_DAYS = 30
    BACKUP_EVERY_WRITES = 100
    COMPACTION_RECENT_MESSAGES = 50

    def __init__(self, workspace_root: str, upload_retention_days: int = UPLOAD_RETENTION_DAYS, max_upload_storage_bytes: int = MAX_UPLOAD_STORAGE_BYTES):
        self.root_dir = Path(workspace_root) / "long_term_memory"
        self.transcript_dir = self.root_dir / "transcripts"
        self.index_file = self.root_dir / "memory_index.jsonl"
        self.facts_file = self.root_dir / "facts.jsonl"
        self.profile_file = self.root_dir / "profile.json"
        self.project_summaries_file = self.root_dir / "project_summaries.json"
        self.upload_dir = self.root_dir / "uploads"
        self.temporary_upload_dir = self.upload_dir / "temporary"
        self.permanent_upload_dir = self.upload_dir / "permanent"
        self.upload_index_file = self.upload_dir / "index.jsonl"
        self.lock_file = self.root_dir / ".memory.lock"
        self.backup_dir = self.root_dir / "backups"
        self._lock = threading.Lock()
        self._write_count = 0
        self.upload_retention_days = max(1, int(upload_retention_days))
        self.max_upload_storage_bytes = max_upload_storage_bytes

        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        self.temporary_upload_dir.mkdir(parents=True, exist_ok=True)
        self.permanent_upload_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file.touch(exist_ok=True)
        if self.lock_file.stat().st_size == 0:
            self.lock_file.write_bytes(b"0")

    @contextmanager
    def _file_lock(self):
        lock_handle = self.lock_file.open("a+")
        try:
            if os.name == "nt":
                import msvcrt
                lock_handle.seek(0)
                msvcrt.locking(lock_handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                if os.name == "nt":
                    import msvcrt
                    lock_handle.seek(0)
                    msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            finally:
                lock_handle.close()

    @staticmethod
    def _flush_and_sync(file_handle):
        file_handle.flush()
        os.fsync(file_handle.fileno())

    def _backup_if_due(self):
        self._write_count += 1
        if self._write_count % self.BACKUP_EVERY_WRITES != 0:
            return
        backup_path = self.backup_dir / datetime.now().strftime("memory_%Y%m%d_%H%M%S")
        backup_path.mkdir(parents=True, exist_ok=True)
        for source in (self.index_file, self.facts_file, self.upload_index_file):
            if source.exists():
                shutil.copy2(source, backup_path / source.name)

    def _append_jsonl(self, path: Path, entry: dict):
        with path.open("a", encoding="utf-8", newline="") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._flush_and_sync(file)
        self._backup_if_due()

    def _atomic_write_json(self, path: Path, payload: dict):
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
            self._flush_and_sync(file)
        temporary.replace(path)

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict]:
        if not path.exists():
            return []
        records = []
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                try:
                    record = json.loads(line)
                    if isinstance(record, dict):
                        records.append(record)
                except json.JSONDecodeError:
                    # Ignore incomplete/corrupt records and keep recoverable history.
                    continue
        return records

    def _today_file(self) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.transcript_dir / f"{date_str}.txt"

    def append_message(self, sender: str, text: str, project: str = None):
        """Appends a message to today's transcript file and the global index."""
        if not text or not text.strip():
            return
        if len(text.encode("utf-8")) > self.MAX_MESSAGE_BYTES:
            raise ValueError("Message exceeds the 2 MB memory limit.")

        timestamp = datetime.now().isoformat(timespec="seconds")

        transcript_line = f"[{timestamp}] {sender}: {text.strip()}\n"
        entry = {
            "timestamp": timestamp,
            "sender": sender,
            "text": text,
            "project": project,
        }
        with self._lock, self._file_lock():
            with open(self._today_file(), "a", encoding="utf-8", newline="") as f:
                f.write(transcript_line)
                self._flush_and_sync(f)

            # Machine-readable index for later search/retrieval
            self._append_jsonl(self.index_file, entry)

    @staticmethod
    def _normalize_confidence(value) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 1.0
        return max(0.0, min(1.0, parsed))

    @staticmethod
    def _normalize_importance(value) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, parsed))

    @staticmethod
    def _fact_score(record: dict) -> float:
        timestamp = record.get("timestamp")
        age_days = 0.0
        if timestamp:
            try:
                age_days = max(0.0, (datetime.now() - MemoryManager._parse_timestamp(timestamp)).total_seconds() / 86400.0)
            except Exception:
                age_days = 0.0
        recency = 1.0 / (1.0 + age_days / 365.0)
        confidence = MemoryManager._normalize_confidence(record.get("confidence", 1.0))
        importance = MemoryManager._normalize_importance(record.get("importance", 0.5))
        return (importance * 3.0) + (confidence * 2.0) + (recency * 2.0)

    def save_facts(self, facts: list, source: str = "", project: str = None):
        """Append facts and supersede older values for the same subject."""
        candidates = []
        for item in facts:
            if isinstance(item, str):
                fact_text = item.strip()
                candidate = {
                    "subject": self._subject_from_text(fact_text),
                    "value": fact_text,
                    "confidence": 1.0,
                    "importance": 0.5,
                }
            elif isinstance(item, dict):
                candidate = {
                    "subject": str(item.get("subject", "")).strip().lower(),
                    "value": str(item.get("value", "")).strip(),
                    "confidence": self._normalize_confidence(item.get("confidence", 1.0)),
                    "importance": self._normalize_importance(item.get("importance", 0.5)),
                }
            else:
                continue
            if candidate["subject"] == "user.identity.name" and source.strip() and not MemoryManager._contains_explicit_name_claim(source):
                continue
            if candidate["subject"] and candidate["value"] and len(candidate["value"]) <= 500 and not self._looks_like_secret(candidate["value"]):
                candidates.append(candidate)

        if not candidates:
            return

        timestamp = datetime.now().isoformat(timespec="seconds")
        with self._lock, self._file_lock():
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
                            if "importance" not in record:
                                record["importance"] = self._normalize_importance(record.get("confidence", 0.5))
                            if "confidence" not in record:
                                record["confidence"] = 1.0
                            records.append(record)
                        except json.JSONDecodeError:
                            continue

            with open(self.facts_file, "a", encoding="utf-8", newline="") as f:
                for candidate in candidates:
                    subject = candidate["subject"]
                    value = candidate["value"]
                    current = next((record for record in reversed(records) if record.get("subject") == subject and record.get("status", "active") == "active"), None)
                    if current and current.get("value", "").strip().lower() == value.lower():
                        continue
                    if current:
                        current_score = self._fact_score(current)
                        candidate_score = self._fact_score({
                            "timestamp": timestamp,
                            "confidence": candidate["confidence"],
                            "importance": candidate["importance"],
                        })
                        if current_score >= candidate_score:
                            continue
                        current["status"] = "superseded"
                        current["superseded_at"] = timestamp
                    record = {
                        "timestamp": timestamp,
                        "subject": subject,
                        "value": value,
                        "fact": value,
                        "confidence": candidate.get("confidence", 1.0),
                        "importance": candidate.get("importance", 0.5),
                        "status": "active",
                        "source": source,
                        "project": project,
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    self._flush_and_sync(f)
                    records.append(record)
                    self._backup_if_due()

    @staticmethod
    def _contains_explicit_name_claim(source: str) -> bool:
        """Only accept a name when the user explicitly identifies it as their name."""
        lowered = source.lower()
        return bool(re.search(r"\b(my name is|call me|i am called)\b", lowered))

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
        """Returns durable facts ranked by importance, confidence, and recency."""
        if not self.facts_file.exists():
            return []

        records_by_subject = {}
        for record in self._read_jsonl(self.facts_file):
            subject = record.get("subject") or self._subject_from_text(record.get("fact", ""))
            if subject not in records_by_subject:
                records_by_subject[subject] = record
            else:
                incumbent = records_by_subject[subject]
                if self._fact_score(record) >= self._fact_score(incumbent):
                    records_by_subject[subject] = record

        facts = list(records_by_subject.values())
        if active_only:
            facts = [record for record in facts if record.get("status", "active") == "active"]
        facts = sorted(facts, key=self._fact_score, reverse=True)
        return facts[:limit]

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

        return self._read_jsonl(self.index_file)[-limit:]

    def get_profile(self) -> dict:
        if not self.profile_file.exists():
            return {}
        try:
            return json.loads(self.profile_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def get_project_summaries(self) -> dict:
        if not self.project_summaries_file.exists():
            return {}
        try:
            return json.loads(self.project_summaries_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def compact_profile(self, project_summaries: dict | None = None, user_summary: str = "") -> dict:
        """Write a small derived context while preserving all raw memory forever."""
        facts = self.get_facts(limit=500)
        profile = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "active_facts": [
                {
                    "subject": fact.get("subject", ""),
                    "value": fact.get("value", fact.get("fact", "")),
                    "confidence": fact.get("confidence", 1.0),
                    "importance": fact.get("importance", self._normalize_importance(fact.get("confidence", 0.5))),
                }
                for fact in facts
            ],
            "user_summary": user_summary[:5000],
            "user_profile": self.learn_user_profile(),
        }
        summaries = project_summaries if project_summaries is not None else self.get_project_summaries()
        with self._lock, self._file_lock():
            self._atomic_write_json(self.profile_file, profile)
            self._atomic_write_json(self.project_summaries_file, summaries)
        return profile

    def learn_user_profile(self) -> dict:
        """Derive a compact profile from the strongest durable facts."""
        facts = self.get_facts(limit=50)
        profile = {"facts": {}}
        for fact in facts:
            subject = str(fact.get("subject", "")).strip()
            if not subject:
                continue
            profile["facts"][subject] = {
                "value": fact.get("value", fact.get("fact", "")),
                "confidence": self._normalize_confidence(fact.get("confidence", 1.0)),
                "importance": self._normalize_importance(fact.get("importance", 0.5)),
                "updated_at": fact.get("timestamp"),
            }
        return profile

    def compact_low_value_facts(self, max_facts: int = 50, stale_days: int = 90, min_importance: float = 0.25) -> dict:
        """Remove stale facts that are low value and no longer useful."""
        if not self.facts_file.exists():
            return {"removed_count": 0, "remaining_count": 0}

        records = self._read_jsonl(self.facts_file)
        active_records = [record for record in records if record.get("status", "active") == "active"]
        if not active_records:
            return {"removed_count": 0, "remaining_count": 0}

        active_records.sort(key=self._fact_score, reverse=True)
        keep = []
        remove_count = 0
        for record in active_records:
            age_days = 0.0
            timestamp = record.get("timestamp")
            if timestamp:
                age_days = max(0.0, (datetime.now() - self._parse_timestamp(timestamp)).total_seconds() / 86400.0)
            importance = self._normalize_importance(record.get("importance", 0.5))
            if age_days > stale_days and importance < min_importance:
                remove_count += 1
                record["status"] = "superseded"
                record["superseded_at"] = datetime.now().isoformat(timespec="seconds")
                continue
            keep.append(record)

        if len(keep) > max_facts:
            # Trim the weakest facts while preserving strongest ones.
            for record in sorted(keep[max_facts:], key=self._fact_score):
                record["status"] = "superseded"
                record["superseded_at"] = datetime.now().isoformat(timespec="seconds")
                remove_count += 1
            keep = keep[:max_facts]

        with self._lock, self._file_lock():
            with open(self.facts_file, "w", encoding="utf-8", newline="") as f:
                for record in records:
                    if record.get("status") == "superseded" and record in active_records:
                        record["status"] = "superseded"
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    self._flush_and_sync(f)

        return {"removed_count": remove_count, "remaining_count": len(keep)}

    def get_compact_context(self, recent_limit: int = 20) -> str:
        """Return compact profile plus a small raw tail for session startup."""
        profile = self.get_profile()
        summaries = self.get_project_summaries()
        lines = ["Compact long-term memory:"]
        for fact in profile.get("active_facts", []):
            lines.append(f"- {fact.get('subject')}: {fact.get('value')}")
        if profile.get("user_summary"):
            lines.append(f"User summary: {profile['user_summary']}")
        for project, summary in summaries.items():
            lines.append(f"Project {project}: {summary}")
        recent = self.get_recent_messages(limit=recent_limit)
        if recent:
            lines.append("Recent messages:")
            lines.extend(f"[{item.get('sender')}] {item.get('text')}" for item in recent)
        return "\n".join(lines)

    def messages_for_compaction(self, keep_recent: int = COMPACTION_RECENT_MESSAGES) -> list[dict]:
        messages = self._read_jsonl(self.index_file)
        return messages[:-keep_recent] if len(messages) > keep_recent else []

    @staticmethod
    def _parse_timestamp(value: str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except (TypeError, ValueError):
            return datetime.min

    @staticmethod
    def _subject_aliases(query: str) -> set[str]:
        aliases = {
            "name": "user.identity.name",
            "my name": "user.identity.name",
            "girlfriend": "user.relationship.partner",
            "boyfriend": "user.relationship.partner",
            "partner": "user.relationship.partner",
            "wife": "user.relationship.partner",
            "husband": "user.relationship.partner",
        }
        return {subject for phrase, subject in aliases.items() if phrase in query.lower()}

    def search(self, query: str, limit: int = 20, project: str = None):
        """Rank lifetime memory by subject, phrase, tokens, recency, confidence, and project."""
        if not query.strip():
            return []

        normalized_query = " ".join(query.lower().strip().split())
        terms = [term for term in re.findall(r"[\w'-]+", normalized_query) if len(term) > 1]
        if not terms:
            return []
        subject_aliases = self._subject_aliases(normalized_query)
        now = datetime.now()

        fact_matches = []
        for fact in self.get_facts(limit=limit):
            subject = fact.get("subject", "").lower()
            value = fact.get("value", fact.get("fact", "")).lower()
            haystack = f"{subject} {value}"
            token_hits = sum(term in haystack for term in terms)
            phrase_match = normalized_query in value or normalized_query in haystack
            subject_match = subject in subject_aliases
            if token_hits == 0 and not subject_match:
                continue
            age_days = max(0.0, (now - self._parse_timestamp(fact.get("timestamp"))).total_seconds() / 86400)
            recency = 1.0 / (1.0 + age_days / 365.0)
            confidence = max(0.0, min(1.0, float(fact.get("confidence", 1.0))))
            score = token_hits / len(terms) * 5.0
            if phrase_match:
                score += 6.0
            if subject_match:
                score += 10.0
            if project and fact.get("project") == project:
                score += 2.0
            score += recency * 2.0 + confidence * 2.0
            fact_matches.append((score, {**fact, "sender": "FACT", "text": fact.get("value", fact.get("fact", ""))}))

        message_matches = []
        if self.index_file.exists():
            for entry in self._read_jsonl(self.index_file):
                haystack = f"{entry.get('sender', '')} {entry.get('text', '')}".lower()
                token_hits = sum(term in haystack for term in terms)
                phrase_match = normalized_query in entry.get("text", "").lower()
                if token_hits == 0:
                    continue
                age_days = max(0.0, (now - self._parse_timestamp(entry.get("timestamp"))).total_seconds() / 86400)
                score = token_hits / len(terms) * 4.0 + (4.0 if phrase_match else 0.0)
                if project and entry.get("project") == project:
                    score += 2.0
                score += 1.0 / (1.0 + age_days / 365.0)
                message_matches.append((score, entry))

        ranked = sorted(fact_matches + message_matches, key=lambda item: item[0], reverse=True)
        return [{**entry, "relevance_score": round(score, 3)} for score, entry in ranked[:limit]]

    def upload_storage_bytes(self) -> int:
        return sum(
            path.stat().st_size
            for upload_root in (self.temporary_upload_dir, self.permanent_upload_dir)
            for path in upload_root.rglob("*")
            if path.is_file() and not path.name.endswith(".tmp")
        )

    def store_upload(self, filename: str, content: bytes, mime_type: str = "application/octet-stream", permanent: bool = False) -> dict:
        if len(content) > self.MAX_UPLOAD_BYTES:
            raise ValueError("File is too large. Maximum size is 25 MB.")
        if self.upload_storage_bytes() + len(content) > self.max_upload_storage_bytes:
            raise ValueError("Upload storage limit reached. Forget old uploads before adding another file.")

        safe_name = Path(filename).name or "uploaded_file"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target_dir = self.permanent_upload_dir if permanent else self.temporary_upload_dir
        target = target_dir / f"{timestamp}_{safe_name}"
        temporary = target.with_suffix(target.suffix + ".tmp")
        with self._lock, self._file_lock():
            with temporary.open("wb") as file:
                file.write(content)
                self._flush_and_sync(file)
            temporary.replace(target)
            metadata = {
                "filename": safe_name,
                "path": str(target),
                "mime_type": mime_type,
                "size": len(content),
                "permanent": permanent,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            self._append_jsonl(self.upload_index_file, metadata)
        return metadata

    def list_uploads(self, include_temporary: bool = True) -> list[dict]:
        records = self._read_jsonl(self.upload_index_file)
        active = []
        for record in records:
            if Path(record.get("path", "")).exists() and (include_temporary or record.get("permanent")):
                active.append(record)
        return active

    def save_upload(self, path: str) -> str:
        source = Path(path).resolve()
        if not source.is_file() or not source.is_relative_to(self.upload_dir.resolve()):
            return "Upload not found or path is outside the upload directory."
        destination = self.permanent_upload_dir / source.name
        if self.upload_storage_bytes() + source.stat().st_size > self.max_upload_storage_bytes:
            return "Upload storage limit reached. Forget old uploads before saving this file permanently."
        with self._lock, self._file_lock():
            shutil.copy2(source, destination)
            self._append_jsonl(self.upload_index_file, {
                "filename": destination.name,
                "path": str(destination),
                "mime_type": "application/octet-stream",
                "size": destination.stat().st_size,
                "permanent": True,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            })
        return str(destination)

    def forget_uploads(self, path: str | None = None, temporary_only: bool = False) -> str:
        targets = [Path(path).resolve()] if path else [Path(record["path"]).resolve() for record in self.list_uploads(True)]
        removed = 0
        with self._lock, self._file_lock():
            for target in targets:
                if not target.is_relative_to(self.upload_dir.resolve()):
                    continue
                if temporary_only and not target.is_relative_to(self.temporary_upload_dir.resolve()):
                    continue
                if target.is_file():
                    target.unlink()
                    removed += 1
        return f"Forgot {removed} uploaded file(s)."

    def cleanup_expired_uploads(self) -> str:
        cutoff = time.time() - self.upload_retention_days * 86400
        removed = 0
        for record in self.list_uploads(include_temporary=True):
            path = Path(record["path"])
            if not record.get("permanent") and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        return f"Cleaned up {removed} expired temporary upload(s)."
