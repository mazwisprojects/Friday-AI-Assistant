"""Resilience tests: model fallback chains, state sync/restore, ops journal."""
import sys, tempfile, shutil, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from actions import sync_engine as se
from actions import ops_journal as oj
import model_router as mr

_TMP = Path(tempfile.mkdtemp(prefix="friday_resilience_"))
mr._STATE = _TMP / "model_health.json"
mr._SETTINGS_FILE = _TMP / "settings.json"
se._BACKEND = _TMP / "backend"
se._SETTINGS_FILE = se._BACKEND / "settings.json"
oj._JOURNAL = _TMP / "ops_journal.jsonl"


def test_model_router_chains_and_errors():
    chains = mr.chains()
    assert "live" in chains and "flash" in chains and all(chains[t] for t in chains)
    assert mr.is_model_error("404 models/gemini-x not found")
    assert mr.is_model_error("APIError: NOT_FOUND")
    assert not mr.is_model_error("Connection reset by peer")
    entry = mr.record_failure("gemini-test-a", "404 not found")
    assert entry["consecutive"] == 1 and entry["cooldown_until"] > time.time()
    e2 = mr.record_failure("gemini-test-a", "404 not found")
    assert e2["consecutive"] == 2 and e2["cooldown_until"] > entry["cooldown_until"]  # escalates
    e3 = mr.record_failure("gemini-test-b", "Connection reset")                        # non-model error
    assert e3["consecutive"] == 0 and e3["cooldown_until"] <= time.time() + 300


def test_model_router_pick_and_rotate():
    mr.record_failure("gemini-3.6-flash", "404 model not found")   # cool the primary
    picked = mr.pick("flash")
    assert picked != "gemini-3.6-flash"                             # skips cooling model
    nxt = mr.rotate("gemini-3.6-flash", "flash")
    assert nxt != "gemini-3.6-flash"                                # rotates to next candidate
    mr.record_success("gemini-3.6-flash")                           # recovery clears cooldown
    assert mr.pick("flash") == "gemini-3.6-flash"                   # healthy primary wins again
    st = mr.status()
    assert st["ok"] and st["active_flash"]


def test_sync_backup_and_restore():
    (se._BACKEND / "long_term_memory").mkdir(parents=True, exist_ok=True)
    state_file = se._BACKEND / "long_term_memory" / "goals.json"
    state_file.write_text('{"goals": ["original"]}', encoding="utf-8")
    dest = _TMP / "off_machine_backup"
    r = se.configure(str(dest), interval_hours=6)
    assert r["ok"] and r["config"]["dest"] == str(dest)
    b = se.backup_now("test")
    assert b["ok"] and Path(b["archive"]).exists() and b["size_kb"] > 0
    a = se.auto_backup()
    assert not a["backed_up"] and a["reason"] == "interval_not_elapsed"  # just backed up
    state_file.write_text('{"goals": ["corrupted"]}', encoding="utf-8")
    r = se.restore(b["archive"])
    assert r["ok"] and '"original"' in state_file.read_text(encoding="utf-8")
    st = se.status()
    assert st["configured"]  # restore legitimately rolls back last_backup with the snapshot


def test_ops_journal_and_nightly():
    oj.log_entry("tool_audit", "healthy", "all tools passed")
    oj.log_entry("lesson", "warning", "import bug fixed by pinning version")
    r = oj.log_nightly({"tools_ok": ["a", "b"], "tools_failed": ["c"],
                        "backup": {"ok": True, "archive": "x.zip"},
                        "models": {"models": []}, "active_goals": 2, "duration_s": 1.2})
    assert r["ok"] and r["status"] == "degraded" and "2/3" in r["headline"]
    d = oj.digest(days=1)
    assert d["ok"] and d["total"] >= 3 and any("pinning version" in l for l in d["lessons"])


if __name__ == "__main__":
    ok = True
    for fn in (test_model_router_chains_and_errors, test_model_router_pick_and_rotate,
               test_sync_backup_and_restore, test_ops_journal_and_nightly):
        try:
            fn()
            print("PASS", fn.__name__)
        except AssertionError as exc:
            ok = False
            print("FAIL", fn.__name__, exc)
        except Exception as exc:
            ok = False
            print("ERROR", fn.__name__, repr(exc))
    shutil.rmtree(_TMP, ignore_errors=True)
    print("ALL_PASS" if ok else "HAS_FAILURES")
    sys.exit(0 if ok else 1)