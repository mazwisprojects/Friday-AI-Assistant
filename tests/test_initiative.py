"""Initiative Engine tests — governance, quiet hours, budgets, nudges."""
import sys, tempfile, shutil, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from actions import initiative as it

_TMP = Path(tempfile.mkdtemp(prefix="friday_initiative_"))
it._STATE = _TMP / "state.json"
it._SETTINGS_FILE = _TMP / "settings.json"


def _goal(gid, title="Fix driver", progress=0, needs_attention=True, last_journal=None, due=None):
    return {"id": gid, "title": title, "progress": progress, "needs_attention": needs_attention,
            "next_milestone": "patch code", "last_journal": last_journal, "due": due}


def test_quiet_hours_wrap():
    cfg = it.read_settings()
    assert cfg["enabled"] and cfg["interval_minutes"] == 20          # defaults
    noon = time.mktime(time.strptime("2026-09-08 12:00", "%Y-%m-%d %H:%M"))
    night = time.mktime(time.strptime("2026-09-08 02:00", "%Y-%m-%d %H:%M"))
    assert not it.is_quiet_hour(cfg, noon)
    assert it.is_quiet_hour(cfg, night)                              # 23->8 wraps midnight


def test_evaluate_acts_on_stale_goal():
    cfg = it.read_settings()
    noon = time.mktime(time.strptime("2026-09-08 12:00", "%Y-%m-%d %H:%M"))
    plan = it.evaluate([_goal("g1")], 0, cfg, user_idle_seconds=9999, now_ts=noon)
    assert plan["act"] and plan["initiatives"][0]["kind"] == "goal_work"
    assert "Fix driver" in plan["initiatives"][0]["prompt"] and "patch code" in plan["initiatives"][0]["prompt"]
    it.record_action("goal_work", "g1", now_ts=noon)
    plan = it.evaluate([_goal("g1")], 0, cfg, 9999, noon + 60)       # nudge interval blocks repeat
    assert not plan["act"] and plan["reason"] == "nothing_actionable"


def test_governance_layers():
    cfg = it.read_settings()
    noon = time.mktime(time.strptime("2026-09-08 12:00", "%Y-%m-%d %H:%M"))
    p = it.evaluate([_goal("g2")], 0, cfg, user_idle_seconds=10, now_ts=noon)     # user just spoke
    assert not p["act"] and p["reason"] == "user_active_recently"
    it.write_settings({"enabled": False})
    p = it.evaluate([_goal("g2")], 0, it.read_settings(), 9999, noon)
    assert not p["act"] and p["reason"] == "disabled"
    it.write_settings({"enabled": True})
    for i in range(it.DEFAULTS["max_daily_actions"]):                # burn the daily budget
        it.record_action("goal_work", "g%d" % i, now_ts=noon)
    p = it.evaluate([_goal("gz")], 0, cfg, 9999, noon)
    assert not p["act"] and p["reason"] == "daily_budget_exhausted"


def test_approval_reminder_priority():
    it._save_state({"actions_date": "2000-01-01", "actions_count": 0,
                    "goal_last_nudge": {}, "last_approval_reminder": 0.0})  # fresh budget
    cfg = it.read_settings()
    noon = time.mktime(time.strptime("2026-09-08 12:00", "%Y-%m-%d %H:%M"))
    plan = it.evaluate([_goal("g9")], 3, cfg, 9999, noon)
    kinds = [i["kind"] for i in plan["initiatives"]]
    assert kinds[0] == "approval_reminder" and "goal_work" in kinds
    assert "3 actions" in plan["initiatives"][0]["prompt"]
    assert len(plan["initiatives"]) <= 2


def test_write_settings_sanitises():
    r = it.write_settings({"interval_minutes": 45, "bogus_key": 1})
    assert r["ok"] and r["config"]["interval_minutes"] == 45 and "bogus_key" not in r["config"]


if __name__ == "__main__":
    ok = True
    for fn in (test_quiet_hours_wrap, test_evaluate_acts_on_stale_goal, test_governance_layers,
               test_approval_reminder_priority, test_write_settings_sanitises):
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