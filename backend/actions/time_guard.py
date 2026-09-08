"""Time Guard for FRIDAY — automatic snapshots before self-modification, one-command revert."""
from __future__ import annotations
import json, shutil, time, hashlib
from pathlib import Path
from datetime import datetime

_BACKEND = Path(__file__).resolve().parent.parent
_SNAP_ROOT = _BACKEND / "long_term_memory" / "snapshots"
_MAX_SNAPSHOTS = 50

def _sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()

def guard(path, label: str = "auto") -> dict:
    """Snapshot a single file before it is modified. Returns None if the file doesn't exist yet."""
    src = Path(path)
    if not src.exists() or not src.is_file():
        return None
    sid = "%s_%s" % (datetime.now().strftime("%Y%m%d-%H%M%S-%f"), label)
    snap_dir = _SNAP_ROOT / sid
    data_dir = snap_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    dest = data_dir / src.name
    try:
        shutil.copy2(src, dest)
    except OSError:
        return None  # file locked (antivirus) — proceed without snapshot rather than blocking the edit
    manifest = {"id": sid, "label": label, "created_at": time.time(),
                "original_path": str(src), "file": dest.name, "sha1": _sha1(src), "size": src.stat().st_size}
    (snap_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    prune()
    return {"snapshot_id": sid, "path": str(src)}

def list_snapshots() -> dict:
    snaps = []
    if _SNAP_ROOT.exists():
        for d in sorted(_SNAP_ROOT.iterdir(), reverse=True):
            m = d / "manifest.json"
            if m.exists():
                try:
                    snaps.append(json.loads(m.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    continue
    return {"ok": True, "snapshots": snaps[:100], "total": len(snaps)}

def restore(snapshot_id: str) -> dict:
    snap_dir = _SNAP_ROOT / snapshot_id
    mpath = snap_dir / "manifest.json"
    if not mpath.exists():
        return {"ok": False, "error": "Snapshot not found", "snapshot_id": snapshot_id}
    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}
    data = snap_dir / "data" / manifest["file"]
    if not data.exists():
        return {"ok": False, "error": "Snapshot data missing"}
    target = Path(manifest["original_path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(data, target)
    except OSError as exc:
        return {"ok": False, "error": "Restore failed (file locked?): %s" % exc}
    return {"ok": True, "restored": manifest["original_path"], "snapshot_id": snapshot_id}

def undo_last() -> dict:
    snaps = list_snapshots().get("snapshots", [])
    if not snaps:
        return {"ok": False, "error": "No snapshots to undo"}
    return restore(snaps[0]["id"])

def prune(max_keep: int = _MAX_SNAPSHOTS) -> dict:
    if not _SNAP_ROOT.exists():
        return {"pruned": 0}
    dirs = sorted((d for d in _SNAP_ROOT.iterdir() if d.is_dir()), key=lambda d: d.name)
    removed = 0
    for d in dirs[:-max_keep] if len(dirs) > max_keep else []:
        shutil.rmtree(d, ignore_errors=True)
        removed += 1
    return {"pruned": removed}

def time_guard_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "")
    if action == "guard":
        return {"ok": True, "snapshot": guard(a.get("path", ""), a.get("label", "manual"))}
    if action == "list":
        return list_snapshots()
    if action == "restore":
        return restore(a.get("snapshot_id", ""))
    if action == "undo_last":
        return undo_last()
    return {"ok": False, "error": "Unknown time_guard action"}