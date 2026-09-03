"""Local Google OAuth connection for Friday's personal productivity features."""

from __future__ import annotations

import os
from pathlib import Path

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


class GoogleAccount:
    """Owns a local Google OAuth token and the explicitly approved scopes."""

    SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/contacts",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.token_path = self.base_dir / "google_token.json"
        configured_path = os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS")
        self.client_secret_path = Path(configured_path) if configured_path else self.base_dir / "google_client_secret.json"
        self.credentials: Credentials | None = None
        self.load_credentials()

    def load_credentials(self) -> None:
        self.credentials = None
        if not self.token_path.exists():
            return
        try:
            credentials = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)
            granted_scopes = set(credentials.scopes or [])
            if not set(self.SCOPES).issubset(granted_scopes):
                print("[GOOGLE] Stored token needs renewed permissions.")
                return
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                self._save(credentials)
            if credentials.valid:
                self.credentials = credentials
        except Exception as exc:
            print(f"[GOOGLE] Could not load local token: {exc}")

    def connect(self) -> dict:
        if not self.client_secret_path.exists():
            raise FileNotFoundError(
                "Google OAuth is not configured. Download a Desktop OAuth client JSON file from Google Cloud "
                "and save it as backend/google_client_secret.json."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), self.SCOPES)
        self.credentials = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True)
        self._save(self.credentials)
        return self.status()

    def disconnect(self) -> dict:
        self.credentials = None
        if self.token_path.exists():
            self.token_path.unlink()
        return self.status()

    def status(self) -> dict:
        return {
            "connected": bool(self.credentials and self.credentials.valid),
            "scopes": ["Gmail (read/drafts)", "Calendar (create/read/update/delete)", "Contacts (read/write)", "Drive (read)"],
        }

    def read_emails(self, query: str = "is:unread", limit: int = 10) -> list[dict]:
        """Read message headers and plain-text snippets from Gmail."""
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Google account is not connected")
        service = build("gmail", "v1", credentials=self.credentials, cache_discovery=False)
        response = service.users().messages().list(userId="me", q=query, maxResults=max(1, min(limit, 25))).execute()
        emails = []
        for item in response.get("messages", []):
            message = service.users().messages().get(userId="me", id=item["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"]).execute()
            headers = {header["name"].lower(): header["value"] for header in message.get("payload", {}).get("headers", [])}
            emails.append({
                "id": message.get("id"),
                "from": headers.get("from", ""),
                "subject": headers.get("subject", "(no subject)"),
                "date": headers.get("date", ""),
                "snippet": message.get("snippet", ""),
            })
        return emails

    def create_calendar_event(self, title: str, date: str, time: str, duration_minutes: int = 30, description: str = "") -> dict:
        """Create an event on the user's primary Google Calendar."""
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Google account is not connected or needs to be reconnected")
        from datetime import datetime, timedelta

        start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end = start + timedelta(minutes=max(1, min(duration_minutes, 1440)))
        service = build("calendar", "v3", credentials=self.credentials, cache_discovery=False)
        event = service.events().insert(
            calendarId="primary",
            body={
                "summary": title,
                "description": description,
                "start": {"dateTime": start.isoformat(), "timeZone": "Africa/Johannesburg"},
                "end": {"dateTime": end.isoformat(), "timeZone": "Africa/Johannesburg"},
            },
        ).execute()
        return {"id": event.get("id"), "summary": event.get("summary"), "html_link": event.get("htmlLink")}

    def list_calendar_events(self, query: str = "", days: int = 7, limit: int = 25) -> list[dict]:
        from datetime import datetime, timedelta, timezone
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Google account is not connected or needs to be reconnected")
        service = build("calendar", "v3", credentials=self.credentials, cache_discovery=False)
        now = datetime.now(timezone.utc)
        response = service.events().list(
            calendarId="primary", timeMin=now.isoformat(), timeMax=(now + timedelta(days=max(1, min(days, 90)))).isoformat(),
            q=query or None, maxResults=max(1, min(limit, 100)), singleEvents=True, orderBy="startTime",
        ).execute()
        return [{"id": item.get("id"), "summary": item.get("summary", "(untitled)"), "start": item.get("start", {}), "end": item.get("end", {}), "description": item.get("description", ""), "html_link": item.get("htmlLink")} for item in response.get("items", [])]

    def update_calendar_event(self, event_id: str, title: str | None = None, date: str | None = None, time: str | None = None, duration_minutes: int = 30, description: str | None = None) -> dict:
        from datetime import datetime, timedelta
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Google account is not connected or needs to be reconnected")
        service = build("calendar", "v3", credentials=self.credentials, cache_discovery=False)
        event = service.events().get(calendarId="primary", eventId=event_id).execute()
        if title is not None:
            event["summary"] = title
        if description is not None:
            event["description"] = description
        if date and time:
            start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            end = start + timedelta(minutes=max(1, min(duration_minutes, 1440)))
            event["start"] = {"dateTime": start.isoformat(), "timeZone": "Africa/Johannesburg"}
            event["end"] = {"dateTime": end.isoformat(), "timeZone": "Africa/Johannesburg"}
        updated = service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
        return {"id": updated.get("id"), "summary": updated.get("summary"), "html_link": updated.get("htmlLink")}

    def delete_calendar_event(self, event_id: str) -> None:
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Google account is not connected or needs to be reconnected")
        build("calendar", "v3", credentials=self.credentials, cache_discovery=False).events().delete(calendarId="primary", eventId=event_id).execute()

    def create_recurring_event(self, title: str, date: str, time: str, recurrence: str, duration_minutes: int = 30, description: str = "") -> dict:
        from datetime import datetime, timedelta
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Google account is not connected or needs to be reconnected")
        start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end = start + timedelta(minutes=max(1, min(duration_minutes, 1440)))
        event = build("calendar", "v3", credentials=self.credentials, cache_discovery=False).events().insert(
            calendarId="primary", body={"summary": title, "description": description, "start": {"dateTime": start.isoformat(), "timeZone": "Africa/Johannesburg"}, "end": {"dateTime": end.isoformat(), "timeZone": "Africa/Johannesburg"}, "recurrence": [recurrence]}
        ).execute()
        return {"id": event.get("id"), "summary": event.get("summary"), "html_link": event.get("htmlLink")}

    def read_gmail_thread(self, thread_id: str) -> list[dict]:
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Google account is not connected")
        service = build("gmail", "v1", credentials=self.credentials, cache_discovery=False)
        thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
        messages = []
        for message in thread.get("messages", []):
            headers = {header["name"].lower(): header["value"] for header in message.get("payload", {}).get("headers", [])}
            messages.append({"id": message.get("id"), "from": headers.get("from", ""), "to": headers.get("to", ""), "subject": headers.get("subject", ""), "date": headers.get("date", ""), "snippet": message.get("snippet", "")})
        return messages

    def create_gmail_draft(self, to: str, subject: str, body: str, thread_id: str = "") -> dict:
        import base64
        from email.message import EmailMessage
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Google account is not connected")
        message = EmailMessage()
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft_body = {"message": {"raw": raw}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id
        draft = build("gmail", "v1", credentials=self.credentials, cache_discovery=False).users().drafts().create(userId="me", body=draft_body).execute()
        return {"id": draft.get("id"), "message_id": draft.get("message", {}).get("id")}

    def read_contacts(self, query: str = "", limit: int = 25) -> list[dict]:
        """Read contacts from the connected Google account."""
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Google account is not connected")
        service = build("people", "v1", credentials=self.credentials, cache_discovery=False)
        contacts = []
        search = query.strip().lower()
        page_token = None
        while len(contacts) < limit:
            response = service.people().connections().list(
                resourceName="people/me",
                pageSize=min(100, limit - len(contacts)),
                pageToken=page_token,
                personFields="names,emailAddresses,phoneNumbers,organizations",
            ).execute()
            for person in response.get("connections", []):
                names = person.get("names", [])
                emails = person.get("emailAddresses", [])
                phones = person.get("phoneNumbers", [])
                organizations = person.get("organizations", [])
                contact = {
                    "name": names[0].get("displayName", "") if names else "",
                    "emails": [item.get("value", "") for item in emails],
                    "phones": [item.get("value", "") for item in phones],
                    "organization": organizations[0].get("name", "") if organizations else "",
                }
                haystack = " ".join([contact["name"], *contact["emails"], *contact["phones"], contact["organization"]]).lower()
                if not search or search in haystack:
                    contacts.append(contact)
                    if len(contacts) >= limit:
                        break
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return contacts

    def create_contact(self, name: str, email: str = "", phone: str = "") -> dict:
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Google account is not connected or needs to be reconnected")
        body = {"names": [{"givenName": name}]}
        if email:
            body["emailAddresses"] = [{"value": email}]
        if phone:
            body["phoneNumbers"] = [{"value": phone}]
        person = build("people", "v1", credentials=self.credentials, cache_discovery=False).people().createContact(body=body).execute()
        return {"resource_name": person.get("resourceName"), "name": name}

    def list_drive_files(self, query: str = "trashed = false", limit: int = 25) -> list[dict]:
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Google account is not connected or needs to be reconnected")
        response = build("drive", "v3", credentials=self.credentials, cache_discovery=False).files().list(
            q=query, pageSize=max(1, min(limit, 100)), orderBy="modifiedTime desc",
            fields="files(id,name,mimeType,modifiedTime,webViewLink,size)",
        ).execute()
        return response.get("files", [])

    def sync_snapshot(self, limit: int = 25) -> dict:
        """Refresh a local, non-secret snapshot of connected Google data."""
        import json
        snapshot = {
            "emails": self.read_emails("is:unread", limit),
            "calendar": self.list_calendar_events("", 30, limit),
            "contacts": self.read_contacts("", limit),
            "drive": self.list_drive_files(limit=limit),
        }
        snapshot_path = self.base_dir / "google_sync.json"
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"emails": len(snapshot["emails"]), "calendar": len(snapshot["calendar"]), "contacts": len(snapshot["contacts"]), "drive": len(snapshot["drive"]), "path": str(snapshot_path)}

    def _save(self, credentials: Credentials) -> None:
        self.token_path.write_text(credentials.to_json(), encoding="utf-8")