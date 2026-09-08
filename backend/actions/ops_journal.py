"""Ops Journal for FRIDAY — operating hours: records real workloads and what was learned."""
from __future__ import annotations
import json, time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_JOURNAL = _BACKEND / "long_term_memory" / "ops_journal.jsonl"

def log_entry(kind: str, status: str, summary: str, details: dict = None, duration_s: float = None) -> dict:
    """Append one ops record (nightly_ops, tool_audit, model_check, backup, incident, lesson)."""
    entry = {"t": time.time(), "kind": kind, "status": status, "summary": (summary or "")[:400],
             "details": details or {}, "duration_s": duration_s}
    try:
        _JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with _JOURNAL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        from actions import semantic_memory
        semantic_memory.remember("OPS %s [%s]: %s" % (kind, status, summary), kind="ops", source="ops_journal")
    except Exception:
        pass
    return {"ok": True, "kind": kind, "status": status}

def log_nightly(report: dict) -> dict:
    """Compose + log the nightly ops report; returns a headline for notification."""
    ok_tools = report.get("tools_ok", [])
    failed_tools = report.get("tools_failed", [])
    backup = report.get("backup") or {}
    models = report.get("models") or {}
    cooling = [m["model"] for m in models.get("models", []) if m.get("cooling")]
    headline = ("Nightly ops: %d/%d tools healthy, %d active goals, backup %s" % (
        len(ok_tools), len(ok_tools) + len(failed_tools), report.get("active_goals", 0),
        "saved" if backup.get("ok") else "FAILED"))
    status = "degraded" if failed_tools or cooling else "healthy"
    log_entry("nightly_ops", status, headline, {
        "tools_ok": ok_tools, "tools_failed": failed_tools,
        "cooling_models": cooling, "backup": backup.get("archive"),
        "duration_s": report.get("duration_s"),
    }, duration_s=report.get("duration_s"))
    if failed_tools:
        log_entry("lesson", "warning", "Failing tools need attention: %s" % ", ".join(failed_tools[:8]),
                  {"tools": failed_tools})
    return {"ok": True, "headline": headline, "status": status}

def digest(days: float = 1.0) -> dict:
    """Aggregate the recent ops journal: counts by kind/status, recent failures and lessons."""
    cutoff = time.time() - max(0.04, float(days)) * 86400
    entries, by_kind, failures, lessons = [], {}, [], []
    try:
        with _JOURNAL.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("t", 0) >= cutoff:
                    entries.append(e)
    except OSError:
        pass
    for e in entries:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
        if e.get("status") in ("failed", "error", "warning", "degraded"):
            failures.append({"kind": e["kind"], "summary": e["summary"], "t": e["t"]})
        if e.get("kind") == "lesson":
            lessons.append(e["summary"])
    return {"ok": True, "window_days": days, "total": len(entries), "by_kind": by_kind,
            "failures": failures[-10:], "lessons": lessons[-10:]}

def ops_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "digest")
    if action == "digest":
        return digest(float(a.get("days", 1)))
    if action == "log":
        return log_entry(a.get("kind", "incident"), a.get("status", "info"), a.get("summary", ""),
                         a.get("details"), a.get("duration_s"))
    return {"ok": False, "error": "Unknown ops action"}