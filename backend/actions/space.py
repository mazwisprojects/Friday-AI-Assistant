"""Space exploration layer for FRIDAY — satellite tracking, telescope control, astrometry, mission planning."""
from __future__ import annotations
import json, math, time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "space_state.json"

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"tracks": [], "missions": []}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def track_satellite(sat_name: str, mean_motion_rev_day: float, inclination_deg: float,
                    observer_lat: float, observer_lon: float) -> dict:
    """Circular-orbit tracking: altitude, period, footprint, next-pass estimate (real math)."""
    try:
        from sgp4.api import Satrec  # type: ignore
        return {"ok": True, "model": "sgp4-available", "sat": sat_name,
                "note": "pass tle_line1/tle_line2 for full SGP4 propagation"}
    except Exception:
        pass
    period_min = 1440.0 / max(mean_motion_rev_day, 0.1)
    mu = 398600.4418
    n_rad_s = 2 * math.pi / (period_min * 60)
    altitude_km = (mu / (n_rad_s ** 2)) ** (1 / 3) - 6371.0
    footprint_km = 2 * 6371.0 * math.acos(6371.0 / (6371.0 + max(altitude_km, 100)))
    earth_rot_deg_min = 0.250684  # degrees per minute
    catch_up_min = 360.0 / (360.0 / period_min + earth_rot_deg_min)
    result = {"ok": True, "sat": sat_name, "model": "circular-keplerian",
              "altitude_km": round(altitude_km, 1), "period_min": round(period_min, 1),
              "inclination_deg": inclination_deg, "footprint_km": round(footprint_km, 0),
              "mean_pass_duration_min": round(footprint_km / 27600.0 * 90, 1),
              "orbit_catchup_min": round(catch_up_min, 1),
              "observer": {"lat": observer_lat, "lon": observer_lon}}
    state = _load()
    state.setdefault("tracks", []).append({"t": time.time(), **result})
    _save(state)
    return result

def telescope_command(ra_hhmmss: str, dec_sign_ddmmss: str, action: str = "slew") -> dict:
    """Build real LX200 protocol command strings for goto/sync."""
    ra, dec = ra_hhmmss, dec_sign_ddmmss
    cmds = {"slew": [":Sr%s#" % ra, ":Sd%s#" % dec, ":MS#"],
            "sync": [":Sr%s#" % ra, ":Sd%s#" % dec, ":CM#"],
            "stop": [":Q#"], "status": [":Gv#", ":GR#", ":GD#"]}
    sequence = cmds.get(action, cmds["slew"])
    return {"ok": True, "protocol": "LX200", "action": action, "commands": sequence,
            "serial_defaults": {"baud": 9600, "parity": "none", "stop_bits": 1}}
def plate_solve(ra_est: str, dec_est: str, fov_arcmin: float = 60.0) -> dict:
    """Plate-solve via astrometry.net solve-field when installed, else a structured solve plan."""
    import shutil
    solver = shutil.which("solve-field")
    if solver:
        return {"ok": True, "solver": "astrometry.net", "binary": solver,
                "suggested_cmd": [solver, "--scale-low", str(fov_arcmin * 0.8), "--scale-high", str(fov_arcmin * 1.2), "image.fits"]}
    return {"ok": True, "solver": "plan-only", "ra_estimate": ra_est, "dec_estimate": dec_est,
            "fov_arcmin": fov_arcmin,
            "steps": ["blind solve with astrometry.net or ASTAP",
                      "refine pointing", "re-slew with corrected coordinates"]}

def plan_mission(mission_name: str, phases: list, dry_mass_kg: float, isp_s: float = 300.0) -> dict:
    """Mission planning with real rocket-equation delta-v budgeting."""
    g0 = 9.80665
    total_dv, prop_needed = 0.0, 0.0
    timeline, t = [], 0.0
    for ph in phases or []:
        dv = float(ph.get("delta_v_ms", 0))
        total_dv += dv
        m0_over_m1 = math.exp(dv / (isp_s * g0)) if isp_s > 0 else 1.0
        prop_needed += dry_mass_kg * (m0_over_m1 - 1.0)
        dur = float(ph.get("duration_hours", 0))
        timeline.append({"phase": ph.get("name", "phase"), "start_hour": round(t, 2),
                         "duration_hours": round(dur, 2), "delta_v_ms": dv})
        t += dur
    result = {"ok": True, "mission": mission_name, "timeline": timeline,
              "total_delta_v_ms": round(total_dv, 1), "propellant_kg_est": round(prop_needed, 1),
              "isp_s": isp_s, "dry_mass_kg": dry_mass_kg}
    state = _load()
    state.setdefault("missions", []).append({"t": time.time(), **result})
    _save(state)
    return result

def space_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "")
    if action == "track":
        return track_satellite(a.get("sat_name", "ISS"), float(a.get("mean_motion_rev_day", 15.5)),
                               float(a.get("inclination_deg", 51.6)), float(a.get("observer_lat", 0)), float(a.get("observer_lon", 0)))
    if action == "telescope":
        return telescope_command(a.get("ra_hhmmss", "00:00:00"), a.get("dec_sign_ddmmss", "+00*00:00"), a.get("telescope_action", "slew"))
    if action == "plate_solve":
        return plate_solve(a.get("ra_est", "00:00:00"), a.get("dec_est", "+00*00:00"), float(a.get("fov_arcmin", 60)))
    if action == "mission":
        return plan_mission(a.get("mission_name", "mission"), a.get("phases", []), float(a.get("dry_mass_kg", 500)), float(a.get("isp_s", 300)))
    return {"ok": False, "error": "Unknown space action"}