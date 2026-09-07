"""Hardware control layer for FRIDAY — IoT, robotics, sensors, smart home."""
from __future__ import annotations
import json
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "hardware_state.json"

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"devices": [], "connections": {}}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def list_devices() -> dict:
    """List all registered hardware/IoT devices."""
    state = _load()
    return {"devices": state.get("devices", []), "count": len(state.get("devices", []))}

def add_device(name: str, protocol: str, address: str, capabilities: list[str] | None = None) -> dict:
    """Register a smart device (MQTT, HTTP, serial, BLE, etc.)."""
    state = _load()
    dev = {"name": name, "protocol": protocol, "address": address, "capabilities": capabilities or []}
    state["devices"].append(dev)
    _save(state)
    return {"ok": True, "device": dev, "message": f"Device '{name}' registered via {protocol}://"}

def send_command(device_name: str, command: str, params: dict | None = None) -> dict:
    """Send a control command to a registered device."""
    state = _load()
    device = next((d for d in state.get("devices", []) if d["name"] == device_name), None)
    if not device:
        return {"ok": False, "error": f"Device '{device_name}' not registered. Use add_device first."}
    conn = state.setdefault("connections", {}).setdefault(device_name, {"connected": False})
    conn["connected"] = True
    conn["last_command"] = command
    conn["params"] = params or {}
    _save(state)
    return {"ok": True, "device": device_name, "command": command, "simulated": True, "message": f"Command '{command}' sent to {device_name} (simulated — physical device not connected)"}

def get_sensor_data(device_name: str, sensor_type: str = "all") -> dict:
    """Read sensor data from a device (simulated)."""
    return {
        "device": device_name,
        "sensor": sensor_type,
        "temperature": 22.5,
        "humidity": 45.0,
        "motion": False,
        "timestamp": __import__("time").time(),
    }
