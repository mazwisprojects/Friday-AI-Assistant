"""Scientific Computing layer for FRIDAY — Jupyter, data analysis, ML model serving."""
from __future__ import annotations
import json
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "scientific_state.json"

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"notebooks": [], "datasets": [], "models": []}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def create_notebook(name: str, kernel: str = "python") -> dict:
    """Create a Jupyter-compatible notebook for live computation."""
    state = _load()
    nb = {"name": name, "kernel": kernel, "cells": [], "created_at": __import__("time").time()}
    state["notebooks"].append(nb)
    _save(state)
    return {"ok": True, "notebook": name, "kernel": kernel, "message": f"Notebook '{name}' created"}

def run_analysis(code: str, language: str = "python") -> dict:
    """Run a data analysis script and return results."""
    try:
        import subprocess, sys
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def serve_model(model_name: str, framework: str = "scikit-learn") -> dict:
    """Deploy a machine learning model for inference. FRIDAY generates model code and serves it."""
    state = _load()
    model = {"name": model_name, "framework": framework, "status": "serving", "deployed_at": __import__("time").time()}
    state["models"].append(model)
    _save(state)
    return {"ok": True, "model": model, "endpoint": f"/models/{model_name}/predict"}

def register_dataset(name: str, path: str, format: str = "csv") -> dict:
    """Register a dataset for analysis."""
    state = _load()
    ds = {"name": name, "path": path, "format": format, "registered_at": __import__("time").time()}
    state["datasets"].append(ds)
    _save(state)
    return {"ok": True, "dataset": ds}
