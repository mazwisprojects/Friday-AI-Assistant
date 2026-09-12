"""Model Router for FRIDAY — automatic fallback across Gemini models when one 404s or dies.

No more model-unavailability powerlessness: every tier (live voice, flash text, lite
parsing, CAD) has an ordered fallback chain, failure cooldowns with escalation, and a
healthy-model picker. Chains are configurable in settings.json['model_routing'].
"""
from __future__ import annotations
import logging
import json, os, time
from pathlib import Path
from types import SimpleNamespace

logger = logging.getLogger(__name__)

_BACKEND = Path(__file__).resolve().parent
_STATE = _BACKEND / "long_term_memory" / "model_health.json"
_SETTINGS_FILE = _BACKEND / "settings.json"
_COOLDOWN_BASE = 3600.0      # 1h after first model error
_COOLDOWN_MAX = 6 * 3600.0   # cap escalation at 6h
_OTHER_ERROR_COOLDOWN = 120.0

try:
    from config import MAIN_GEMINI_MODEL, FACT_GEMINI_MODEL, CAD_GEMINI_MODEL
except Exception:  # standalone/test use
    MAIN_GEMINI_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
    FACT_GEMINI_MODEL = "models/gemini-3.5-flash-lite"
    CAD_GEMINI_MODEL = "gemini-3.1-pro-preview"

DEFAULT_CHAINS = {
    "live": [MAIN_GEMINI_MODEL, "gemini-2.0-flash-live-001", "gemini-live-2.5-flash-preview"],
    "flash": ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"],
    "lite": [FACT_GEMINI_MODEL, "gemini-2.0-flash-lite"],
    "cad": [CAD_GEMINI_MODEL, "gemini-2.5-pro"],
    # P4.3: background cognition (emotion refinement, lesson derivation, future
    # nightly rollups) — pro-led for deeper reasoning, flash fallback when pro
    # models are cooling. Override in settings.json['model_routing']['background'].
    "background": [CAD_GEMINI_MODEL, "gemini-2.5-pro", "gemini-3.6-flash", "gemini-2.5-flash"],
}

def _load_health() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

def _save_health(health: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(health, indent=1), encoding="utf-8")

def chains() -> dict:
    """Configured chains: settings.json['model_routing'] overrides defaults (deduped, non-empty)."""
    merged = {tier: [m for m in dict.fromkeys(models) if m] for tier, models in DEFAULT_CHAINS.items()}
    try:
        raw = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8")).get("model_routing") or {}
        for tier, models in raw.items():
            if isinstance(models, list) and models:
                merged[tier] = [m for m in dict.fromkeys(str(x) for x in models) if m]
    except (OSError, json.JSONDecodeError):
        pass
    return merged

def is_model_error(error_text: str) -> bool:
    t = (error_text or "").lower()
    return any(k in t for k in ("404", "not found", "not_found", "unsupported", "is not supported",
                                "permission denied", "does not have access", "no access to model",
                                "model_terminated", "deprecated"))

def record_failure(model: str, error: str = "") -> dict:
    """Cooldown escalates per consecutive model error (1h -> 6h); other errors get 2 minutes."""
    health = _load_health()
    entry = health.get(model) or {"consecutive": 0, "last_fail_ts": 0.0, "cooldown_until": 0.0, "last_error": ""}
    if is_model_error(error):
        entry["consecutive"] = int(entry.get("consecutive", 0)) + 1
        cooldown = min(_COOLDOWN_BASE * (2 ** (entry["consecutive"] - 1)), _COOLDOWN_MAX)
    else:
        entry["consecutive"] = 0
        cooldown = _OTHER_ERROR_COOLDOWN
    entry["last_fail_ts"] = time.time()
    entry["cooldown_until"] = entry["last_fail_ts"] + cooldown
    entry["last_error"] = (error or "")[:300]
    health[model] = entry
    _save_health(health)
    return entry

def record_success(model: str) -> dict:
    health = _load_health()
    entry = health.get(model) or {}
    entry.update({"consecutive": 0, "cooldown_until": 0.0, "last_success_ts": time.time()})
    health[model] = entry
    _save_health(health)
    return entry

def _healthy(chain: list, now: float = None) -> list:
    now = now if now is not None else time.time()
    health = _load_health()
    return [m for m in chain if (health.get(m, {}).get("cooldown_until", 0.0) or 0.0) <= now]

def pick(tier: str = "flash", preferred: str = None) -> str:
    """First healthy model in the tier chain; least-cooled fallback if everything is cooling."""
    chain = chains().get(tier) or []
    if preferred and preferred in chain:
        chain = [preferred] + [m for m in chain if m != preferred]
    healthy = _healthy(chain)
    if healthy:
        return healthy[0]
    if not chain:
        return preferred or ""
    health = _load_health()
    return min(chain, key=lambda m: health.get(m, {}).get("cooldown_until", 0.0))

def rotate(current: str, tier: str = "live") -> str:
    """Next healthy model after `current` in the chain (for live-session fallback)."""
    chain = chains().get(tier) or []
    if current in chain:
        chain = chain[chain.index(current) + 1:] + chain[:chain.index(current)]
    for model in _healthy(chain):
        if model != current:
            return model
    return current
def generate_response(contents, tier: str = "flash", config=None):
    """Text generation with automatic fallback. Returns an object with .text/.model/.attempts.

    Drop-in replacement for `client.models.generate_content(model=X, contents=Y)` call sites:
    each candidate model is tried in chain order; failures are recorded with cooldowns so
    dead models are skipped automatically until they recover.
    """
    chain = chains().get(tier) or [""]
    attempts = []
    for model in _healthy(chain):
        try:
            from google import genai
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            resp = client.models.generate_content(model=model, contents=contents, config=config)
            record_success(model)
            return SimpleNamespace(text=resp.text, candidates=getattr(resp, "candidates", None),
                                   model=model, attempts=attempts, ok=True)
        except Exception as exc:
            attempts.append({"model": model, "error": str(exc)[:200]})
            record_failure(model, str(exc))
    return SimpleNamespace(text="", model=None, attempts=attempts, ok=False)

def status() -> dict:
    health = _load_health()
    now = time.time()
    models = []
    for model, e in health.items():
        cooling = (e.get("cooldown_until", 0.0) or 0.0) > now
        models.append({"model": model, "cooling": cooling,
                       "cooldown_remaining_min": round(max(0.0, (e.get("cooldown_until", 0.0) or 0.0) - now) / 60, 1),
                       "consecutive_failures": e.get("consecutive", 0),
                       "last_error": e.get("last_error", ""), "last_success_ts": e.get("last_success_ts")})
    models.sort(key=lambda m: m["model"])
    return {"ok": True, "chains": chains(), "models": models,
            "active_live": pick("live"), "active_flash": pick("flash")}

def test_models(tier: str = "flash") -> dict:
    """Ping every model in a tier chain with a tiny request; reports per-model health."""
    results = []
    for model in chains().get(tier, []):
        try:
            from google import genai
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            resp = client.models.generate_content(model=model, contents="Reply with the single word: ok")
            ok = bool(resp.text)
            record_success(model)
            results.append({"model": model, "ok": ok, "error": ""})
        except Exception as exc:
            record_failure(model, str(exc))
            results.append({"model": model, "ok": False, "error": str(exc)[:200]})
    return {"ok": True, "tier": tier, "results": results,
            "healthy": [r["model"] for r in results if r["ok"]]}

def configure(tier: str, models: list) -> dict:
    """Persist a tier chain into settings.json['model_routing']."""
    if tier not in DEFAULT_CHAINS or not isinstance(models, list) or not models:
        return {"ok": False, "error": "Need a valid tier and a non-empty model list",
                "valid_tiers": list(DEFAULT_CHAINS)}
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8")) if _SETTINGS_FILE.exists() else {}
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    routing = data.setdefault("model_routing", {})
    routing[tier] = [str(m) for m in models if str(m).strip()]
    _SETTINGS_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
    return {"ok": True, "tier": tier, "chain": routing[tier]}

def router_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "status")
    if action == "status":
        return status()
    if action == "test":
        return test_models(a.get("tier", "flash"))
    if action == "configure":
        return configure(a.get("tier", "flash"), a.get("models", []))
    if action == "pick":
        return {"ok": True, "model": pick(a.get("tier", "flash"), a.get("preferred"))}
    return {"ok": False, "error": "Unknown model_router action"}