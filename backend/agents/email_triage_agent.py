AGENT_MANIFEST = {"name": "email_triage_agent", "version": "1.0.0", "enabled": True, "description": "Triages email-related goals and identifies priority follow-up work.", "parameters": {}}

def run(goal, repo_path, log, cancel_event, context=None):
    log("Reading unread and important Gmail messages")
    if cancel_event.is_set():
        return {"ok": False, "agent": "email_triage_agent", "status": "cancelled"}
    account = getattr(context, "google_account", None)
    if not account:
        return {"ok": True, "agent": "email_triage_agent", "status": "awaiting_google_connection", "goal": goal}
    query = "is:unread"
    if any(word in goal.lower() for word in ("important", "priority")):
        query += " is:important"
    emails = account.read_emails(query=query, limit=25)
    important = [email for email in emails if "important" in email.get("snippet", "").lower() or "urgent" in email.get("subject", "").lower()]
    log(f"Found {len(emails)} unread messages")
    return {"ok": True, "agent": "email_triage_agent", "query": query, "emails": emails, "important": important, "count": len(emails)}