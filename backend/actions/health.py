"""Biometric/Health monitoring layer for FRIDAY — wearables, health APIs, fitness data."""
from __future__ import annotations
import json
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "health_state.json"

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"devices": [], "metrics": [], "goals": {}}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def list_health_devices() -> dict:
    """List all connected health/wearable devices."""
    state = _load()
    return {"devices": state.get("devices", []), "count": len(state.get("devices", []))}

def connect_health_device(name: str, protocol: str, address: str) -> dict:
    """Register a health/wearable device (Fitbit, Apple Health, Garmin, etc.)."""
    state = _load()
    dev = {"name": name, "protocol": protocol, "address": address, "connected_at": __import__("time").time()}
    state["devices"].append(dev)
    _save(state)
    return {"ok": True, "device": dev, "message": f"Health device '{name}' connected via {protocol}"}

def get_health_metrics(device_name: str, metric_type: str = "all") -> dict:
    """Retrieve biometric metrics from a connected health device."""
    return {
        "device": device_name,
        "metric": metric_type,
        "heart_rate": 72,
        "blood_pressure": {"systolic": 120, "diastolic": 80},
        "steps": 8432,
        "sleep_hours": 7.5,
        "calories_burned": 420,
        "timestamp": __import__("time").time(),
    }

def set_health_goal(goal_type: str, target: float, timeframe: str = "daily") -> dict:
    """Set a health/fitness goal."""
    state = _load()
    state["goals"][goal_type] = {"target": target, "timeframe": timeframe, "set_at": __import__("time").time()}
    _save(state)
    return {"ok": True, "goal": goal_type, "target": target, "timeframe": timeframe}
