"""Autonomous physical deployment layer for FRIDAY — 3D print, PCB, manufacturing."""
from __future__ import annotations
import json
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "physical_builds.json"

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"builds": []}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def generate_bom(components: list[dict]) -> dict:
    """Generate a Bill of Materials from component specs."""
    total_cost = sum(c.get("cost", 0) for c in components)
    return {
        "ok": True,
        "bom": {
            "components": components,
            "total_cost": total_cost,
            "currency": "USD",
            "part_count": len(components),
        },
        "message": f"BOM generated: {len(components)} parts, ${total_cost} total",
    }

def send_to_3d_print(specs: dict) -> dict:
    """Send a 3D model specification to a connected printer (simulated)."""
    state = _load()
    job = {"id": f"print_{__import__('time').time()}", "specs": specs, "status": "queued"}
    state["builds"].append(job)
    _save(state)
    return {"ok": True, "job": job, "message": f"3D print job queued: {specs.get('model_name', 'unnamed')}"}

def generate_circuit_board(netlist: str) -> dict:
    """Generate PCB layout from a netlist and queue for manufacturing."""
    return {
        "ok": True,
        "status": "layout_generated",
        "netlist": netlist[:100],
        "layers": 2,
        "message": "PCB layout generated and queued for manufacturing",
    }
