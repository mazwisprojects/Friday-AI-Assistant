import json
import threading
from pathlib import Path


class ContactsManager:
    """Persistent local contacts shared by all Friday projects and sessions."""

    def __init__(self, workspace_root: str):
        self.contacts_file = Path(workspace_root) / "long_term_memory" / "contacts.json"
        self.contacts_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _load(self) -> dict:
        if not self.contacts_file.exists():
            return {}
        try:
            with self.contacts_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, contacts: dict) -> None:
        temporary_file = self.contacts_file.with_suffix(".tmp")
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(contacts, file, indent=2, ensure_ascii=False)
        temporary_file.replace(self.contacts_file)

    @staticmethod
    def _key(name: str) -> str:
        return " ".join(name.strip().lower().split())

    def add_or_update(self, name: str, recipient: str, platform: str = "whatsapp") -> str:
        name_key = self._key(name)
        platform_key = self._key(platform) or "whatsapp"
        if not name_key or not recipient.strip():
            return "A contact name and recipient are required."

        with self._lock:
            contacts = self._load()
            contact = contacts.setdefault(name_key, {"name": name.strip(), "channels": {}})
            contact["name"] = name.strip()
            contact.setdefault("channels", {})[platform_key] = recipient.strip()
            self._save(contacts)
        return f"Saved {name.strip()} for {platform_key}."

    def remove(self, name: str, platform: str = "") -> str:
        name_key = self._key(name)
        platform_key = self._key(platform)
        with self._lock:
            contacts = self._load()
            contact = contacts.get(name_key)
            if not contact:
                return f"Contact not found: {name}"
            if platform_key:
                channels = contact.get("channels", {})
                if platform_key not in channels:
                    return f"No {platform_key} entry found for {contact.get('name', name)}."
                del channels[platform_key]
                if not channels:
                    del contacts[name_key]
            else:
                del contacts[name_key]
            self._save(contacts)
        return f"Removed {name}."

    def list_contacts(self) -> list[dict]:
        contacts = self._load()
        return [
            {"name": value.get("name", key), "channels": value.get("channels", {})}
            for key, value in sorted(contacts.items())
        ]

    def find(self, name: str) -> dict | None:
        name_key = self._key(name)
        contacts = self._load()
        if name_key in contacts:
            return contacts[name_key]
        for key, contact in contacts.items():
            if name_key in key or key in name_key:
                return contact
        return None

    def resolve(self, name: str, platform: str = "whatsapp") -> str | None:
        contact = self.find(name)
        if not contact:
            return None
        channels = contact.get("channels", {})
        platform_key = self._key(platform) or "whatsapp"
        return channels.get(platform_key) or channels.get("whatsapp")

    def format_contacts(self) -> str:
        contacts = self.list_contacts()
        if not contacts:
            return "No contacts saved."
        lines = []
        for contact in contacts:
            channels = ", ".join(
                f"{platform}: {recipient}"
                for platform, recipient in contact["channels"].items()
            )
            lines.append(f"{contact['name']}: {channels}")
        return "Saved contacts:\n" + "\n".join(lines)
