"""AR/Holographic interface layer for FRIDAY — spatial UI, gesture control."""
from __future__ import annotations
import json
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "ar_state.json"

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"windows": [], "gestures": [], "tracking": {}}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def create_ar_window(name: str, position: dict | None = None, size: dict | None = None, content: str = "") -> dict:
    """Create a spatial AR window at a 3D position."""
    state = _load()
    win = {
        "name": name,
        "position": position or {"x": 0, "y": 0, "z": -1},
        "size": size or {"width": 400, "height": 300},
        "content": content,
        "visible": True,
        "created_at": __import__("time").time(),
    }
    state["windows"].append(win)
    _save(state)
    return {"ok": True, "window": win, "message": f"AR window '{name}' created in space"}

def move_ar_window(name: str, new_position: dict) -> dict:
    """Move an AR window to a new 3D position."""
    state = _load()
    win = next((w for w in state.get("windows", []) if w["name"] == name), None)
    if not win:
        return {"ok": False, "error": f"AR window '{name}' not found"}
    win["position"] = new_position
    _save(state)
    return {"ok": True, "window": name, "position": new_position}

def handle_gesture(gesture: str, target: str | None = None) -> dict:
    """Handle a hand-gesture input event."""
    state = _load()
    event = {"gesture": gesture, "target": target, "timestamp": __import__("time").time()}
    state["gestures"].append(event)
    _save(state)
    if gesture == "pinch":
        return {"ok": True, "action": f"Selected {target}", "type": "selection"}
    if gesture == "swipe_left":
        return {"ok": True, "action": "Navigate back", "type": "navigation"}
    if gesture == "swipe_right":
        return {"ok": True, "action": "Navigate forward", "type": "navigation"}
    return {"ok": True, "action": f"Gesture '{gesture}' acknowledged", "type": "generic"}
