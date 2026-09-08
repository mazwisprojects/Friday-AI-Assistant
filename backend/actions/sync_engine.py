"""Sync Engine for FRIDAY — ships his brain state off-machine so a second machine can rebuild him.

Backups zip long-term memory + tool/agent registries + settings (never .env secrets) to a
configurable destination: a USB/NAS path, an SMB share of the second PC, or a cloud-synced
folder (OneDrive/Drive). Restore rebuilds a fresh install into a working Friday.
"""
from __future__ import annotations
import json, time, zipfile
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_SETTINGS_FILE = _BACKEND / "settings.json"
_KEEP = 10
_DEFAULTS = {"dest": "", "interval_hours": 6, "keep": _KEEP, "last_backup": 0.0}

def _load_cfg() -> dict:
    cfg = dict(_DEFAULTS)
    try:
        raw = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8")).get("sync") or {}
        cfg.update({k: v for k, v in raw.items() if k in _DEFAULTS})
    except (OSError, json.JSONDecodeError):
        pass
    return cfg

def _save_cfg(cfg: dict) -> None:
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8")) if _SETTINGS_FILE.exists() else {}
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data["sync"] = cfg
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")

def _collect_paths() -> list:
    """State files that define Friday's mind. Excludes snapshots/backups (too big, regenerable)."""
    ltm = _BACKEND / "long_term_memory"
    paths = []
    for sub in ("transcripts", "uploads"):
        d = ltm / sub
        if d.exists():
            paths.append(d)
    for name in ("goals.json", "semantic_index.json", "facts.jsonl", "memory_index.jsonl", "profile.json",
                 "project_summaries.json", "biometric_profiles.json", "initiative_state.json",
                 "critic_history.json", "model_health.json", "agent_schedules.json", "ops_journal.jsonl"):
        p = ltm / name
        if p.exists():
            paths.append(p)
    for name in ("custom_tools.json", "custom_agents.json", "capability_registry.json",
                 "settings.json", "capability_proposals.json", "autonomy_pipeline.json"):
        p = _BACKEND / name
        if p.exists():
            paths.append(p)
    return paths
def backup_now(tag: str = "manual") -> dict:
    """Zip Friday's state to the configured destination."""
    cfg = _load_cfg()
    dest = Path(cfg["dest"]) if cfg["dest"] else _BACKEND / "long_term_memory" / "backups"
    try:
        dest.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        archive = dest / f"friday_state_{stamp}_{tag}.zip"
        collected = _collect_paths()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in collected:
                try:
                    zf.write(p, p.relative_to(_BACKEND))
                except (OSError, ValueError):
                    continue
        cfg["last_backup"] = time.time()
        _save_cfg(cfg)
        keep = int(cfg.get("keep", _KEEP))
        old = sorted(dest.glob("friday_state_*.zip"))
        for stale in old[:-keep] if len(old) > keep else []:
            try:
                stale.unlink()
            except OSError:
                pass
        return {"ok": True, "archive": str(archive), "size_kb": round(archive.stat().st_size / 1024, 1),
                "files": len(collected), "dest": str(dest)}
    except OSError as exc:
        return {"ok": False, "error": "Backup failed (dest unreachable?): %s" % exc}

def auto_backup() -> dict:
    """Backup only if the configured interval has elapsed (called by the maintenance loop)."""
    cfg = _load_cfg()
    if not cfg.get("dest"):
        return {"backed_up": False, "reason": "sync destination not configured"}
    if time.time() - float(cfg.get("last_backup", 0.0)) < float(cfg.get("interval_hours", 6)) * 3600:
        return {"backed_up": False, "reason": "interval_not_elapsed"}
    res = backup_now("auto")
    return {"backed_up": bool(res.get("ok")), "archive": res.get("archive", ""), "result": res}

def restore(archive_path: str) -> dict:
    """Restore a state archive into the backend (overwrites current state files)."""
    archive = Path(archive_path)
    if not archive.exists():
        return {"ok": False, "error": "Archive not found", "path": archive_path}
    restored = 0
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            for name in zf.namelist():
                target = (_BACKEND / name).resolve()
                if _BACKEND.resolve() not in target.parents and target != _BACKEND.resolve():
                    continue  # zip-slip guard
                zf.extract(name, _BACKEND)
                restored += 1
        return {"ok": True, "restored_files": restored, "from": str(archive),
                "note": "Restart the backend to load the restored state"}
    except (OSError, zipfile.BadZipFile) as exc:
        return {"ok": False, "error": str(exc)}

def configure(dest: str, interval_hours: float = 6, keep: int = _KEEP) -> dict:
    cfg = {**_load_cfg(), "dest": str(dest or ""), "interval_hours": max(1, float(interval_hours)),
           "keep": max(3, int(keep))}
    _save_cfg(cfg)
    return {"ok": True, "config": cfg}

def status() -> dict:
    cfg = _load_cfg()
    last = cfg.get("last_backup", 0.0)
    return {"ok": True, "config": cfg, "configured": bool(cfg.get("dest")),
            "last_backup_age_hours": round((time.time() - last) / 3600, 1) if last else None,
            "due": bool(cfg.get("dest")) and (time.time() - last) >= float(cfg.get("interval_hours", 6)) * 3600}

def manage_sync(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "status")
    if action == "status":
        return status()
    if action == "configure":
        return configure(a.get("dest", ""), float(a.get("interval_hours", 6)), int(a.get("keep", _KEEP)))
    if action == "backup_now":
        return backup_now(a.get("tag", "manual"))
    if action == "restore":
        return restore(a.get("archive", ""))
    return {"ok": False, "error": "Unknown sync action"}