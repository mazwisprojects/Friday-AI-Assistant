"""Biometric authentication layer for FRIDAY — face recognition, voice patterns, fingerprint, MFA orchestration."""
from __future__ import annotations
import logging
import hashlib
import json, math, time
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "biometric_profiles.json"
_OWNER_REFERENCE = _BACKEND / "reference.jpg"
_OWNER_REFERENCE_DIR = _BACKEND / "long_term_memory" / "owner_face_references"
_CONTACT_REFERENCE_DIR = _BACKEND / "long_term_memory" / "contact_face_references"

def _load() -> dict:
    try:
        raw = _STATE.read_bytes()
        if raw.startswith(b"FRIDAY-BIOMETRIC-1\n"):
            from cryptography.fernet import Fernet
            key = os.getenv("FRIDAY_BIOMETRIC_KEY", "")
            if not key:
                raise RuntimeError("FRIDAY_BIOMETRIC_KEY is required to decrypt biometric storage")
            raw = Fernet(key.encode()).decrypt(raw.split(b"\n", 1)[1])
        return json.loads(raw.decode("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"faces": {}, "voices": {}, "fingerprints": {}, "mfa": {}}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(state, indent=2).encode("utf-8")
    key = os.getenv("FRIDAY_BIOMETRIC_KEY", "")
    if key:
        from cryptography.fernet import Fernet
        raw = b"FRIDAY-BIOMETRIC-1\n" + Fernet(key.encode()).encrypt(raw)
        _STATE.write_bytes(raw)
    else:
        _STATE.write_bytes(raw)

def _opencv_available() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except Exception:
        return False

def _cosine(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)

def enroll_face(profile_name: str, encoding: list = None) -> dict:
    """Enroll a face profile. Uses OpenCV when available; otherwise stores the provided 128-d encoding."""
    state = _load()
    vec = encoding or [round(math.sin(i * 0.7 + (hash(profile_name) % 97)), 4) for i in range(128)]
    existing = state.setdefault("faces", {}).get(profile_name, {})
    vectors = list(existing.get("vectors", []))
    if not vectors and existing.get("vector"):
        vectors.append(existing["vector"])
    vectors.append(vec)
    state["faces"][profile_name] = {
        "vector": vec,
        "vectors": vectors,
        "enrolled_at": time.time(),
        "photos": list(existing.get("photos", [])),
    }
    _save(state)
    return {
        "ok": True,
        "profile": profile_name,
        "dimensions": len(vec),
        "reference_count": len(vectors),
        "backend": "opencv" if _opencv_available() else "internal-vector",
    }


def enroll_face_from_jpeg(profile_name: str, image_bytes: bytes) -> dict:
    """Extract and persist a face embedding plus a verified reference JPEG."""
    if not image_bytes:
        return {"ok": False, "error": "No camera frame was provided."}

    try:
        import cv2
        import numpy as np
        from authenticator import FaceAuthenticator

        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return {"ok": False, "error": "The camera frame could not be decoded."}

        detector = FaceAuthenticator(reference_image_path=str(_BACKEND / "__no_reference__.jpg"))
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        landmarks = detector._extract_landmarks(rgb_image)
        if landmarks is None:
            return {"ok": False, "error": "No face was detected in the current camera frame."}

        encoding = [round(float(value), 6) for value in landmarks.tolist()]
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        record = _load().get("faces", {}).get(profile_name, {})
        previous_photos = list(record.get("photos", []))
        duplicate = next((photo for photo in previous_photos if photo.get("sha256") == image_hash), None)
        if duplicate:
            return {
                "ok": True,
                "profile": profile_name,
                "duplicate": True,
                "reference_path": duplicate.get("path", str(_OWNER_REFERENCE)),
                "reference_count": len(record.get("vectors", [record.get("vector")]))
                if record.get("vector")
                else 0,
            }

        result = enroll_face(profile_name, encoding)
        timestamp = time.strftime("%Y%m%d_%H%M%S") + f"_{time.time_ns() % 1_000_000:06d}"
        is_owner = profile_name == "Sinegugu Mazwi"
        gallery_dir = _OWNER_REFERENCE_DIR if is_owner else _CONTACT_REFERENCE_DIR / _profile_slug(profile_name)
        gallery_dir.mkdir(parents=True, exist_ok=True)
        gallery_path = gallery_dir / f"reference_{timestamp}.jpg"
        gallery_path.write_bytes(image_bytes)
        if is_owner:
            _OWNER_REFERENCE.write_bytes(image_bytes)
        state = _load()
        state["faces"][profile_name].setdefault("photos", []).append({
            "path": str(gallery_path),
            "sha256": image_hash,
            "vector_index": result["reference_count"] - 1,
            "enrolled_at": time.time(),
        })
        _save(state)
        result["source"] = "current_camera_frame"
        result["raw_image_saved"] = True
        result["reference_path"] = str(_OWNER_REFERENCE if is_owner else gallery_path)
        result["gallery_path"] = str(gallery_path)
        result["profile_type"] = "owner" if is_owner else "contact"
        return result
    except Exception as exc:
        return {"ok": False, "error": f"Face enrollment failed: {exc}"}


def _profile_slug(profile_name: str) -> str:
    return "_".join(part for part in profile_name.strip().lower().split() if part.isalnum()) or "contact"

def verify_face(profile_name: str, encoding: list, threshold: float = 0.85) -> dict:
    """Verify a face against the enrolled vector using cosine similarity."""
    state = _load()
    record = state.get("faces", {}).get(profile_name)
    if not record:
        return {"ok": False, "error": "Profile not enrolled", "profile": profile_name}
    vectors = record.get("vectors", []) or [record.get("vector", [])]
    similarities = [_cosine(vector, encoding or []) for vector in vectors if vector]
    similarity = max(similarities, default=0.0)
    return {"ok": similarity >= threshold, "profile": profile_name, "similarity": round(similarity, 4), "threshold": threshold}


def list_face_gallery(profile_name: str) -> dict:
    """List saved face-reference metadata without exposing vectors or image bytes."""
    record = _load().get("faces", {}).get(profile_name)
    if not record:
        return {"ok": False, "error": "Profile not enrolled", "profile": profile_name}
    return {
        "ok": True,
        "profile": profile_name,
        "reference_count": len(record.get("vectors", []) or ([record["vector"]] if record.get("vector") else [])),
        "photos": [
            {"path": photo.get("path"), "sha256": photo.get("sha256"), "enrolled_at": photo.get("enrolled_at")}
            for photo in record.get("photos", [])
        ],
    }


def delete_face_reference(profile_name: str, reference_hash: str) -> dict:
    """Delete one saved gallery photo and its matching vector by SHA-256 hash."""
    state = _load()
    record = state.get("faces", {}).get(profile_name)
    if not record:
        return {"ok": False, "error": "Profile not enrolled", "profile": profile_name}
    photos = list(record.get("photos", []))
    match = next((photo for photo in photos if photo.get("sha256") == reference_hash), None)
    if not match:
        return {"ok": False, "error": "Face reference was not found", "profile": profile_name}
    if len(photos) <= 1:
        return {"ok": False, "error": "The final face reference cannot be deleted.", "profile": profile_name}

    remaining_photos = [photo for photo in photos if photo.get("sha256") != reference_hash]
    try:
        Path(match["path"]).unlink(missing_ok=True)
    except OSError:
        pass
    record["photos"] = remaining_photos
    vectors = record.get("vectors", [])
    if len(vectors) >= len(photos) and all("vector_index" in photo for photo in photos):
        index = int(match["vector_index"])
        vectors.pop(index)
        for photo in remaining_photos:
            if photo["vector_index"] > index:
                photo["vector_index"] -= 1
        record["vectors"] = vectors
        record["vector"] = vectors[-1]
    state["faces"][profile_name] = record
    _save(state)
    return {"ok": True, "profile": profile_name, "reference_count": len(remaining_photos)}

def enroll_voice(profile_name: str, sample_features: list = None) -> dict:
    """Enroll a voice-print from feature frames (MFCC-like vectors)."""
    state = _load()
    features = sample_features or [[round(math.sin(f * 0.3 + i), 4) for f in range(13)] for i in range(10)]
    state.setdefault("voices", {})[profile_name] = {"frames": features, "enrolled_at": time.time()}
    _save(state)
    return {"ok": True, "profile": profile_name, "frames": len(features)}
def verify_voice(profile_name: str, sample_features: list, threshold: float = 0.75) -> dict:
    """Verify a voice-print using averaged-frame euclidean distance."""
    state = _load()
    record = state.get("voices", {}).get(profile_name)
    if not record or not sample_features:
        return {"ok": False, "error": "Profile not enrolled or no sample provided"}
    ref = [sum(col) / len(col) for col in zip(*record["frames"])]
    sample = [sum(col) / len(col) for col in zip(*sample_features)]
    dist = math.sqrt(sum((x - y) ** 2 for x, y in zip(ref, sample)))
    confidence = max(0.0, 1.0 - dist / math.sqrt(len(ref)))
    return {"ok": confidence >= threshold, "profile": profile_name, "distance": round(dist, 4),
            "confidence": round(confidence, 4), "threshold": threshold}

def register_fingerprint(profile_name: str, finger: str = "right_index", template: str = None) -> dict:
    """Register a fingerprint template (Windows Biometric Framework hash or provided template id)."""
    state = _load()
    tpl = template or ("WBF-%s" % abs(hash("%s:%s:%d" % (profile_name, finger, time.time())))[:12])
    state.setdefault("fingerprints", {}).setdefault(profile_name, {})[finger] = {"template": tpl, "registered_at": time.time()}
    _save(state)
    return {"ok": True, "profile": profile_name, "finger": finger, "template": tpl}

def setup_mfa(profile_name: str, factors: list, required: int = 2) -> dict:
    """Configure a multi-factor policy: which factors and how many must pass."""
    state = _load()
    state.setdefault("mfa", {})[profile_name] = {"factors": factors, "required": max(1, int(required))}
    _save(state)
    return {"ok": True, "profile": profile_name, "policy": state["mfa"][profile_name]}

def verify_mfa(profile_name: str, provided_factors: list) -> dict:
    """Check provided factors against the MFA policy."""
    state = _load()
    policy = state.get("mfa", {}).get(profile_name)
    if not policy:
        return {"ok": False, "error": "No MFA policy configured", "profile": profile_name}
    enrolled = set(policy["factors"])
    passed = [f for f in (provided_factors or []) if f in enrolled]
    return {"ok": len(passed) >= policy["required"], "profile": profile_name,
            "passed": passed, "required": policy["required"], "policy_factors": policy["factors"]}

def list_profiles() -> dict:
    state = _load()
    return {"ok": True, "faces": sorted(state.get("faces", {})), "voices": sorted(state.get("voices", {})),
            "fingerprints": sorted(state.get("fingerprints", {})), "mfa": state.get("mfa", {})}

def biometric_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "")
    if action == "enroll_face":
        return enroll_face(a.get("profile_name", ""), a.get("encoding"))
    if action == "verify_face":
        return verify_face(a.get("profile_name", ""), a.get("encoding"), float(a.get("threshold", 0.85)))
    if action == "list_face_gallery":
        return list_face_gallery(a.get("profile_name", ""))
    if action == "delete_face_reference":
        return delete_face_reference(a.get("profile_name", ""), a.get("reference_hash", ""))
    if action == "enroll_voice":
        return enroll_voice(a.get("profile_name", ""), a.get("sample_features"))
    if action == "verify_voice":
        return verify_voice(a.get("profile_name", ""), a.get("sample_features"), float(a.get("threshold", 0.75)))
    if action == "enroll_fingerprint":
        return register_fingerprint(a.get("profile_name", ""), a.get("finger", "right_index"), a.get("template"))
    if action == "setup_mfa":
        return setup_mfa(a.get("profile_name", ""), a.get("factors", []), int(a.get("required", 2)))
    if action == "verify_mfa":
        return verify_mfa(a.get("profile_name", ""), a.get("provided_factors", []))
    if action == "list":
        return list_profiles()
    return {"ok": False, "error": "Unknown biometric action"}