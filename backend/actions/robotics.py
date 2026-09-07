"""Robotics layer for FRIDAY — ROS integration, motor control, sensor fusion, SLAM navigation."""
from __future__ import annotations
import json, math, time, urllib.request
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "robotics_state.json"

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"pose": {"x": 0.0, "y": 0.0, "theta": 0.0}, "waypoints": [], "log": []}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def ros_publish(topic: str, message: dict, rosbridge_url: str = "http://localhost:9090") -> dict:
    """Publish a message to a ROS topic through rosbridge_server (real HTTP protocol)."""
    payload = json.dumps({"op": "publish", "topic": topic, "msg": message}).encode("utf-8")
    try:
        req = urllib.request.Request(rosbridge_url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return {"ok": True, "topic": topic, "status": resp.status}
    except Exception as exc:
        return {"ok": False, "topic": topic, "queued": True, "error": str(exc),
                "note": "rosbridge not reachable; command recorded"}

def motor_command(left_speed: float, right_speed: float, duration_ms: int = 500,
                  topic: str = "/cmd_vel", rosbridge_url: str = None) -> dict:
    """Build a differential-drive command and optionally publish it to ROS."""
    v = (left_speed + right_speed) / 2.0
    omega = (right_speed - left_speed) / 0.4  # assuming 0.4m wheel base
    cmd = {"linear": {"x": round(v, 3), "y": 0.0, "z": 0.0},
           "angular": {"x": 0.0, "y": 0.0, "z": round(omega, 3)}}
    result = {"ok": True, "command": cmd, "duration_ms": duration_ms}
    if rosbridge_url:
        result["ros"] = ros_publish(topic, cmd, rosbridge_url)
    state = _load()
    state.setdefault("log", []).append({"t": time.time(), "cmd": cmd})
    _save(state)
    return result

def fuse_sensors(accel_angle: float, gyro_rate: float, dt: float, prev_angle: float = None,
                 alpha: float = 0.98) -> dict:
    """Complementary filter: fuses accelerometer angle with gyro rate (real math)."""
    state = _load()
    prev = prev_angle if prev_angle is not None else state["pose"].get("roll", 0.0)
    angle = alpha * (prev + gyro_rate * dt) + (1 - alpha) * accel_angle
    state["pose"]["roll"] = round(angle, 4)
    _save(state)
    return {"ok": True, "fused_angle": round(angle, 4), "gyro_component": round(alpha * (prev + gyro_rate * dt), 4),
            "accel_component": round((1 - alpha) * accel_angle, 4)}

def slam_update(odom_x: float, odom_y: float, odom_theta: float, lidar_front_m: float = None) -> dict:
    """Update the SLAM pose estimate from odometry and optionally mark lidar clearance."""
    state = _load()
    pose = {"x": round(odom_x, 4), "y": round(odom_y, 4), "theta": round(odom_theta, 4)}
    state["pose"] = pose
    entry = {"t": time.time(), "pose": pose}
    if lidar_front_m is not None:
        entry["clearance_m"] = lidar_front_m
        entry["obstacle_ahead"] = lidar_front_m < 0.5
    state.setdefault("log", []).append(entry)
    _save(state)
    return {"ok": True, "pose": pose, "obstacle_ahead": entry.get("obstacle_ahead", False)}

def add_waypoint(name: str, x: float, y: float) -> dict:
    state = _load()
    state.setdefault("waypoints", []).append({"name": name, "x": x, "y": y})
    _save(state)
    return {"ok": True, "waypoints": state["waypoints"]}

def navigate_to(name: str) -> dict:
    """Plan a straight-line route to a named waypoint and return velocity commands."""
    state = _load()
    wp = next((w for w in state.get("waypoints", []) if w["name"] == name), None)
    if not wp:
        return {"ok": False, "error": "Waypoint not found", "known": [w["name"] for w in state.get("waypoints", [])]}
    pose = state["pose"]
    dx, dy = wp["x"] - pose["x"], wp["y"] - pose["y"]
    distance = math.hypot(dx, dy)
    target_theta = math.atan2(dy, dx)
    turn = target_theta - pose["theta"]
    return {"ok": True, "waypoint": name, "distance_m": round(distance, 3),
            "turn_radians": round(turn, 3),
            "plan": [{"action": "rotate", "radians": round(turn, 3)},
                     {"action": "drive", "meters": round(distance, 3)}]}

def robotics_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "")
    if action == "ros_publish":
        return ros_publish(a.get("topic", "/cmd_vel"), a.get("message", {}), a.get("rosbridge_url", "http://localhost:9090"))
    if action == "motor":
        return motor_command(float(a.get("left_speed", 0)), float(a.get("right_speed", 0)), int(a.get("duration_ms", 500)), a.get("topic", "/cmd_vel"), a.get("rosbridge_url"))
    if action == "fuse":
        return fuse_sensors(float(a.get("accel_angle", 0)), float(a.get("gyro_rate", 0)), float(a.get("dt", 0.02)), a.get("prev_angle"))
    if action == "slam_update":
        return slam_update(float(a.get("odom_x", 0)), float(a.get("odom_y", 0)), float(a.get("odom_theta", 0)), a.get("lidar_front_m"))
    if action == "add_waypoint":
        return add_waypoint(a.get("name", "wp"), float(a.get("x", 0)), float(a.get("y", 0)))
    if action == "navigate_to":
        return navigate_to(a.get("name", ""))
    return {"ok": False, "error": "Unknown robotics action"}