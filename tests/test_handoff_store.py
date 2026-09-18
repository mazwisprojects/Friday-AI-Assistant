import time

from backend.handoff_store import HandoffStore


def test_handoff_store_survives_reload_and_expires(tmp_path):
    path = tmp_path / "handoffs.json"
    store = HandoffStore(path, ttl_seconds=60)
    store.put("android-phone", {"summary": "Continue this conversation", "created_at": "now"})

    reloaded = HandoffStore(path, ttl_seconds=60)
    assert reloaded.pop("android-phone")["summary"] == "Continue this conversation"
    assert reloaded.pop("android-phone") is None


def test_handoff_store_discards_expired_items(tmp_path):
    path = tmp_path / "handoffs.json"
    store = HandoffStore(path, ttl_seconds=1)
    store.put("desktop", {"summary": "old"})
    store._items["desktop"]["stored_at"] = time.time() - 2
    store._save()

    assert HandoffStore(path, ttl_seconds=1).pop("desktop") is None
