from datetime import datetime, timedelta

from memory_manager import MemoryManager


def test_memory_manager_resolves_conflicts_and_keeps_latest_fact(tmp_path):
    manager = MemoryManager(str(tmp_path))

    manager.save_facts([
        {"subject": "user.identity.name", "value": "Alice", "confidence": 0.7, "importance": 0.7},
    ])
    manager.save_facts([
        {"subject": "user.identity.name", "value": "Alicia", "confidence": 0.9, "importance": 0.9},
    ])

    facts = manager.get_facts(limit=20)
    assert any(fact["subject"] == "user.identity.name" and fact["value"] == "Alicia" for fact in facts)
    assert all(fact["value"] != "Alice" for fact in facts if fact["subject"] == "user.identity.name")


def test_memory_manager_ranks_facts_by_importance_and_recency(tmp_path):
    manager = MemoryManager(str(tmp_path))

    manager.save_facts([
        {"subject": "user.preference", "value": "Prefers quiet mornings", "confidence": 0.9, "importance": 0.9},
        {"subject": "fact.trivial", "value": "Had toast for breakfast", "confidence": 0.2, "importance": 0.1},
    ])

    facts = manager.get_facts(limit=10)
    assert any(fact["subject"] == "user.preference" for fact in facts)
    assert all("importance" in fact for fact in facts)
    assert facts[0]["importance"] >= facts[-1]["importance"]


def test_memory_manager_auto_compacts_low_value_facts(tmp_path):
    manager = MemoryManager(str(tmp_path))

    old_timestamp = (datetime.now() - timedelta(days=400)).isoformat(timespec="seconds")
    manager._append_jsonl(manager.facts_file, {
        "timestamp": old_timestamp,
        "subject": "fact.low.value",
        "value": "Low-value stale fact",
        "fact": "Low-value stale fact",
        "confidence": 0.1,
        "importance": 0.05,
        "status": "active",
    })
    manager.save_facts([
        {"subject": "user.identity.name", "value": "User Name", "confidence": 0.95, "importance": 0.9},
    ])

    compacted = manager.compact_low_value_facts(max_facts=1)

    assert compacted["removed_count"] >= 1
    assert manager.get_facts(limit=10)
