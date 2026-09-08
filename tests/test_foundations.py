"""Foundation layer tests: semantic memory, time guard, self-critic, goal engine."""
import sys, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from actions import semantic_memory as sm
from actions import time_guard as tg
from actions import self_critic as sc
from actions import goal_engine as ge

_TMP = Path(tempfile.mkdtemp(prefix="friday_foundations_"))
sm._STATE = _TMP / "semantic.json"
sm._st_model = False  # force offline hash embeddings
tg._SNAP_ROOT = _TMP / "snapshots"
sc._STATE = _TMP / "critic.json"
ge._STATE = _TMP / "goals.json"


def test_semantic_memory():
    r = sm.remember("The user's car is a red 2019 BMW X3", kind="fact", source="test")
    assert r["ok"] and r["count"] == 1
    sm.remember("Friday loves building Python tools", kind="fact", source="test")
    sm.remember("The project deadline is next Monday", kind="decision", source="test")
    r = sm.search("what car does he drive", top_k=3)
    assert r["ok"] and r["results"] and "BMW" in r["results"][0]["text"]
    r = sm.search("deadline timing", kind="decision")
    assert r["ok"] and "deadline" in r["results"][0]["text"].lower()
    for i in range(10):  # buffered chat ingestion: 10th message triggers flush
        sm.ingest_chat("FRIDAY", "chat message %d about quantum physics" % i, project="test")
    r = sm.search("quantum physics chat")
    assert r["ok"] and any("quantum" in x["text"] for x in r["results"])
    st = sm.stats()
    assert st["ok"] and st["total"] >= 13 and st["backend"] == "hash256"


def test_time_guard():
    f = _TMP / "target_module.py"
    f.write_text("VALUE = 1\n", encoding="utf-8")
    snap1 = tg.guard(str(f), "test")
    assert snap1 and snap1["snapshot_id"]
    f.write_text("VALUE = 2\n", encoding="utf-8")
    snap2 = tg.guard(str(f), "test")
    assert snap2 and snap2["snapshot_id"]
    f.write_text("VALUE = 3\n", encoding="utf-8")
    r = tg.undo_last()
    assert r["ok"] and f.read_text(encoding="utf-8") == "VALUE = 2\n"
    r = tg.restore(snap1["snapshot_id"])
    assert r["ok"] and f.read_text(encoding="utf-8") == "VALUE = 1\n"
    lst = tg.list_snapshots()
    assert lst["ok"] and lst["total"] >= 2


def test_self_critic():
    r = sc.run_check("adder", "print(2 + 3)", expects=["5"])
    assert r["passed"] and r["iteration"] == 1
    bad = "import nonexistent_module_xyz"
    r = sc.run_check("importer", bad)
    assert not r["passed"] and "nonexistent_module_xyz" in r["error_analysis"]["advice"]
    r = sc.run_check("importer", bad)
    assert r["no_progress"] and "previous_attempt" in r
    r = sc.run_check("importer", "import nonexistent_module_xyz  # v2")
    assert not r["passed"] and not r.get("no_progress")
    assert sc.history("importer")["total"] >= 3
    assert sc.record("importer", "learned: check package exists first", "reflection")["ok"]
    r = sc.run_check("adder", "print('hello')", expects=["5"])
    assert not r["passed"] and r["error_analysis"]["advice"]


def test_goal_engine():
    r = ge.create_goal("Fix the driver", "kernel module", ["reproduce bug", "patch code", "test"], due="2026-12-01")
    gid = r["goal_id"]
    assert r["ok"] and len(r["goal"]["milestones"]) == 3
    t = ge.tick()
    assert t["count"] == 1 and t["active_goals"][0]["next_milestone"] == "reproduce bug"
    assert ge.journal(gid, "reproduced the bug")["ok"]
    assert ge.update_milestone(gid, 0, True)["progress"] > 33
    r = ge.update_milestone(gid, 1, True)
    assert r["progress"] > 66 and r["status"] == "active"
    r = ge.update_milestone(gid, 2, True)
    assert r["progress"] == 100.0 and r["status"] == "done"
    assert "OPEN GOALS" not in ge.context()
    ge.create_goal("Second goal", milestones=["a", "b"])
    assert "Second goal" in ge.context()


if __name__ == "__main__":
    ok = True
    for fn in (test_semantic_memory, test_time_guard, test_self_critic, test_goal_engine):
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