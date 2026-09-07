"""Energy management layer for FRIDAY — solar geometry, battery management, smart grid, EV charging."""
from __future__ import annotations
import json, math, time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "energy_state.json"

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"readings": [], "charge_plans": []}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def solar_position(lat: float, lon: float, day_of_year: int, hour_local: float) -> dict:
    """Real solar geometry (Cooper declination + hour angle) -> elevation/azimuth."""
    decl = 23.44 * math.sin(math.radians(360.0 / 365.0 * (284 + day_of_year)))
    solar_hour = hour_local + lon / 15.0  # crude solar time from local time + longitude
    hour_angle = 15.0 * (solar_hour - 12.0)
    phi, delta, h = math.radians(lat), math.radians(decl), math.radians(hour_angle)
    sin_elev = math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.cos(h)
    elevation = math.degrees(math.asin(max(-1, min(1, sin_elev))))
    az = math.degrees(math.atan2(-math.cos(delta) * math.sin(h),
                                 math.sin(delta) * math.cos(phi) - math.cos(delta) * math.sin(phi) * math.cos(h)))
    azimuth = (az + 360) % 360
    return {"ok": True, "declination_deg": round(decl, 2), "elevation_deg": round(elevation, 2),
            "azimuth_deg": round(azimuth, 1), "daylight": elevation > 0}

def solar_output(array_kw: float, lat: float, lon: float, day_of_year: int, hour_local: float,
                 efficiency: float = 0.2, cloud_factor: float = 1.0) -> dict:
    """Estimate PV output from the sun's elevation (real geometry + derating)."""
    pos = solar_position(lat, lon, day_of_year, hour_local)
    elevation = max(0.0, pos["elevation_deg"])
    output_kw = array_kw * efficiency * 5.0 * (math.sin(math.radians(elevation)) if elevation > 0 else 0.0) * cloud_factor
    return {"ok": True, "elevation_deg": pos["elevation_deg"], "estimated_output_kw": round(output_kw, 3),
            "cloud_factor": cloud_factor}

def battery_soc(current_series_amps: list, capacity_ah: float, dt_seconds: float, start_soc: float = 100.0) -> dict:
    """Coulomb-counting SoC from a current time series (positive = charging)."""
    if capacity_ah <= 0 or not current_series_amps:
        return {"ok": False, "error": "Need capacity_ah and a current series"}
    delta_ah = sum(float(i) for i in current_series_amps) * dt_seconds / 3600.0
    soc = max(0.0, min(100.0, start_soc + 100.0 * delta_ah / capacity_ah))
    state = _load()
    state.setdefault("readings", []).append({"t": time.time(), "soc": round(soc, 2), "delta_ah": round(delta_ah, 3)})
    _save(state)
    return {"ok": True, "soc_percent": round(soc, 2), "delta_ah": round(delta_ah, 3),
            "net_energy_wh": round(delta_ah * 12.0, 1), "trend": "charging" if delta_ah > 0 else "discharging" if delta_ah < 0 else "idle"}
def grid_balance(loads_kw: dict, sources_kw: dict, source_costs: dict = None) -> dict:
    """Greedy smart-grid allocation: match loads to cheapest available sources."""
    remaining = {s: float(v) for s, v in (sources_kw or {}).items()}
    costs = source_costs or {}
    allocation, unmet = {}, 0.0
    for load, demand in sorted((loads_kw or {}).items(), key=lambda kv: -kv[1]):
        need = float(demand)
        for src in sorted(remaining, key=lambda s: costs.get(s, 0)):
            if need <= 0:
                break
            take = min(need, remaining[src])
            if take > 0:
                allocation.setdefault(load, []).append({"source": src, "kw": round(take, 3)})
                remaining[src] -= take
                need -= take
        if need > 0:
            unmet += need
            allocation.setdefault(load, []).append({"source": "grid_shortfall", "kw": round(need, 3)})
    total_cost = sum(allocation[l][i].get("kw", 0) * costs.get(allocation[l][i]["source"], 0)
                     for l in allocation for i in range(len(allocation[l])))
    return {"ok": True, "allocation": allocation, "unmet_kw": round(unmet, 3),
            "estimated_cost_units": round(total_cost, 3), "spare_capacity_kw": round(sum(remaining.values()), 3)}

def ev_charge_plan(battery_kwh: float, target_soc_percent: float, charger_kw: float,
                   hourly_tariff: list, deadline_hour: int = None) -> dict:
    """Optimal EV charging schedule: cheapest tariff hours first (real optimization)."""
    target_energy = battery_kwh * max(0.0, min(100.0, target_soc_percent)) / 100.0
    deadline = deadline_hour if deadline_hour is not None else len(hourly_tariff)
    window = list(enumerate(hourly_tariff[:max(0, deadline)]))
    hours_by_price = sorted(window, key=lambda hv: hv[1])
    remaining, schedule = target_energy, {}
    for hour, price in hours_by_price:
        if remaining <= 0:
            break
        energy = min(charger_kw * 1.0, remaining)  # 1-hour slots
        schedule[hour] = round(energy, 3)
        remaining -= energy
    cost = sum(energy * hourly_tariff[hour] for hour, energy in schedule.items())
    plan = {"ok": True, "energy_needed_kwh": round(target_energy, 3),
            "schedule_hourly_kw": schedule, "estimated_cost": round(cost, 3),
            "hours_used": len(schedule), "unmet_kwh": round(max(0.0, remaining), 3),
            "deadline_hour": deadline}
    state = _load()
    state.setdefault("charge_plans", []).append({"t": time.time(), **plan})
    _save(state)
    return plan

def energy_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "")
    if action == "solar_position":
        return solar_position(float(a.get("lat", 0)), float(a.get("lon", 0)), int(a.get("day_of_year", 1)), float(a.get("hour_local", 12)))
    if action == "solar_output":
        return solar_output(float(a.get("array_kw", 5)), float(a.get("lat", 0)), float(a.get("lon", 0)), int(a.get("day_of_year", 1)), float(a.get("hour_local", 12)), float(a.get("efficiency", 0.2)), float(a.get("cloud_factor", 1.0)))
    if action == "battery_soc":
        return battery_soc(a.get("current_series_amps", []), float(a.get("capacity_ah", 100)), float(a.get("dt_seconds", 1)), float(a.get("start_soc", 100)))
    if action == "grid_balance":
        return grid_balance(a.get("loads_kw", {}), a.get("sources_kw", {}), a.get("source_costs"))
    if action == "ev_charge_plan":
        return ev_charge_plan(float(a.get("battery_kwh", 60)), float(a.get("target_soc_percent", 80)), float(a.get("charger_kw", 7)), a.get("hourly_tariff", []), a.get("deadline_hour"))
    return {"ok": False, "error": "Unknown energy action"}