"""Global communications layer for FRIDAY — ham radio, APRS packet radio, satellite downlink planning."""
from __future__ import annotations
import json, math, time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "comms_state.json"

_MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....",
    "I": "..", "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.",
    "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--",
    "?": "..--..", "/": "-..-.", "=": "-...-", ":": "---...", "'": ".----.", "-": "-....-",
}
_MORSE_REV = {v: k for k, v in _MORSE.items()}

# Real amateur radio band plan (portion) — frequency MHz -> band name
_BANDS = [
    (1.8, "160m"), (3.5, "80m"), (7.0, "40m"), (10.1, "30m"), (14.0, "20m"),
    (18.068, "17m"), (21.0, "15m"), (24.89, "12m"), (28.0, "10m"), (50.0, "6m"),
    (144.0, "2m"), (420.0, "70cm"), (1240.0, "23cm"),
]

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"transmissions": [], "passes": []}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def _aprs_lat(lat: float) -> str:
    hemi = "N" if lat >= 0 else "S"
    lat = abs(lat)
    d = int(lat); m = (lat - d) * 60
    return "%02d%05.2f%s" % (d, m, hemi)

def _aprs_lon(lon: float) -> str:
    hemi = "E" if lon >= 0 else "W"
    lon = abs(lon)
    d = int(lon); m = (lon - d) * 60
    return "%03d%05.2f%s" % (d, m, hemi)

def aprs_frame(callsign: str, lat: float, lon: float, ssid: int = 9, comment: str = "FRIDAY") -> dict:
    """Build a real uncompressed APRS position report (AX.25 UI frame payload)."""
    src = "%s-%d" % (callsign.upper(), ssid)
    payload = "@%sz%s>%s%s%s" % (
        time.strftime("%H%M%S", time.gmtime()),
        _aprs_lat(lat), "\\", _aprs_lon(lon), ">%s" % comment if comment else "")
    frame = "%s>APFRID,TCPIP*:%s" % (src, payload)
    state = _load()
    state.setdefault("transmissions", []).append({"t": time.time(), "frame": frame})
    _save(state)
    return {"ok": True, "frame": frame, "payload": payload,
            "protocol": "AX.25 UI / APRS 1.01", "suggested_freq_mhz": 144.39}
def morse_encode(text: str) -> dict:
    letters = " ".join(_MORSE.get(ch.upper(), "/") if ch != " " else "/" for ch in (text or ""))
    return {"ok": True, "morse": letters}

def morse_decode(morse: str) -> dict:
    words = (morse or "").split(" / ")
    decoded = " ".join("".join(_MORSE_REV.get(l, "?") for l in w.split()) for w in words)
    return {"ok": True, "text": decoded}

def satellite_pass(sat_name: str, mean_motion_rev_day: float, inclination_deg: float,
                   observer_lat: float, observer_lon: float) -> dict:
    """Estimate passes with a circular-orbit Keplerian model (real orbital math)."""
    period_min = 1440.0 / max(mean_motion_rev_day, 0.1)
    mu = 398600.4418  # km^3/s^2
    n_rad_s = 2 * math.pi / (period_min * 60)
    altitude_km = (mu / (n_rad_s ** 2)) ** (1 / 3) - 6371.0
    footprint_km = 2 * 6371.0 * math.acos(6371.0 / (6371.0 + max(altitude_km, 100)))
    passes_per_day = 86400.0 / (period_min * 60) * (footprint_km / 40075.0)
    result = {"ok": True, "model": "circular-keplerian", "sat": sat_name,
              "inclination_deg": inclination_deg,
              "altitude_km": round(altitude_km, 1), "period_min": round(period_min, 1),
              "footprint_km": round(footprint_km, 0), "visible_passes_per_day_est": round(passes_per_day, 1),
              "observer": {"lat": observer_lat, "lon": observer_lon}}
    state = _load()
    state.setdefault("passes", []).append({"t": time.time(), **result})
    _save(state)
    return result

def downlink_plan(sat_name: str, frequency_mhz: float, duration_min: int = 10) -> dict:
    """Plan a downlink session with doppler shift estimates at rise/zenith/set."""
    c_kms = 299792.458
    v_kms = 7.5  # LEO orbital speed approx
    doppler_khz = frequency_mhz * 1000 * (v_kms / c_kms)
    band = next((name for lo, name in sorted(_BANDS, reverse=True) if frequency_mhz >= lo), "out-of-amateur-band")
    plan = {"ok": True, "sat": sat_name, "frequency_mhz": frequency_mhz, "band": band,
            "duration_min": duration_min,
            "doppler": {"rise_khz": round(doppler_khz, 2), "zenith_khz": 0.0, "set_khz": round(-doppler_khz, 2)},
            "note": "tune from +doppler at rise to -doppler at set"}
    state = _load()
    state.setdefault("passes", []).append({"t": time.time(), **plan})
    _save(state)
    return plan

def band_plan() -> dict:
    return {"ok": True, "bands": [{"lower_mhz": lo, "band": name} for lo, name in _BANDS]}

def comms_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "")
    if action == "aprs":
        return aprs_frame(a.get("callsign", "N0CALL"), float(a.get("lat", 0)), float(a.get("lon", 0)), int(a.get("ssid", 9)), a.get("comment", "FRIDAY"))
    if action == "morse_encode":
        return morse_encode(a.get("text", ""))
    if action == "morse_decode":
        return morse_decode(a.get("morse", ""))
    if action == "satellite_pass":
        return satellite_pass(a.get("sat_name", "ISS"), float(a.get("mean_motion_rev_day", 15.5)), float(a.get("inclination_deg", 51.6)), float(a.get("observer_lat", 0)), float(a.get("observer_lon", 0)))
    if action == "downlink_plan":
        return downlink_plan(a.get("sat_name", "ISS"), float(a.get("frequency_mhz", 145.8)), int(a.get("duration_min", 10)))
    if action == "band_plan":
        return band_plan()
    return {"ok": False, "error": "Unknown comms action"}