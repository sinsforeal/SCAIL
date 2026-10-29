"""Bench default seed (tk-xhv): a branch save gets his live relationship primitives, so he is admitted.
bench_seed.py on a scratch save with her real config and the real Primitives; no arm, no gateway, no spend. The
branch-level wiring (seed.him inject, --stranger) is tested on the stub arm in test_bz_inject.OnStub."""
import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "bzombie", "arms", "s"))
sys.path.insert(0, ROOT)

import bench_seed  # noqa: E402
from test_bz_appraisal import TMPDIR, _Clock  # noqa: E402

LIVE = os.path.join(ROOT, "config_momoka.json")
# a bench snapshot's row for him (H:\SCAIL\...\day1_end\save.db, read once): exposure seeded by the premise, the rest
# earned in the base run, predictability 0.0 because `answered` never fired
BENCH_ROW = {"attention_hers": 94.4, "attention_his": 46.3, "predictability_hers": 0.0, "exposure_hers": 83.9,
             "exposure_his": 9.6, "reciprocity": -10.2, "cost_of_loss": 0.13, "threat": 3.8, "threat_kinds": [],
             "_log": [{"ts": 1.0, "key": "exposure_hers", "from": 0, "to": 83.9, "why": "w", "cause": "c"}],
             "_owed": 9.68}


def make_save(path, row=BENCH_ROW):
    from store import Store
    with contextlib.redirect_stdout(io.StringIO()):
        st = Store(path)
        st.set("primitives", {"him": dict(row)})
        st.conn.commit()
        st.conn.close()


def prims(path, overlays=()):
    """The real Primitives over the save at path, config = her live one with the overlays merged."""
    import control
    from config import Config
    from store import Store
    p = str(Path(path).with_suffix(".json"))
    with open(LIVE, encoding="utf-8") as fh:
        cfg = json.load(fh)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    control.write_overrides(p, {}, list(overlays))
    with contextlib.redirect_stdout(io.StringIO()):
        from sim.primitives import Primitives
        return Primitives(Config(p), Store(path), _Clock(2_000_000.0))


def kv_row(path):
    con = sqlite3.connect("file:" + Path(path).as_posix() + "?mode=ro", uri=True)
    try:
        return json.loads(con.execute("SELECT value FROM kv WHERE key='primitives'").fetchone()[0])["him"]
    finally:
        con.close()


class Seed(unittest.TestCase):
    def test_seed_file_holds_live_values_and_extraction_time(self):
        s = bench_seed.load_seed()
        self.assertTrue(s["extracted"])
        self.assertEqual(s["person_in_live_save"], "him")
        self.assertGreater(s["primitives"]["predictability_hers"], 90)
        self.assertTrue(s["admitted_in_live"])
        self.assertNotIn("_log", s["primitives"])

    def test_default_branch_save_is_seeded_and_admitted(self):
        seed = bench_seed.load_seed()
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            db = os.path.join(tmp, "save.db")
            make_save(db)
            self.assertFalse(prims(db).admitted("him"))   # the save as the bench leaves it: a stranger
            make_save(db)
            changed = bench_seed.apply_to_db(db, 123.0)
            row = kv_row(db)
            for k, v in seed["primitives"].items():
                if k != "threat_kinds":
                    self.assertEqual(row[k], v, k)
            self.assertEqual(row["predictability_hers"], seed["primitives"]["predictability_hers"])
            self.assertIn("predictability_hers", changed)
            self.assertEqual(row["_owed"], 9.68)   # what the seed does not carry stays
            self.assertEqual(row["_log"][-1]["cause"], "bench_seed")
            self.assertEqual(row["_bench_seed"], bench_seed.seed_tag(seed))
            self.assertTrue(prims(db).admitted("him"))

    def test_stranger_keeps_predictability_zero(self):
        """The off switch is the branch not injecting seed.him: the save is untouched and he stays outside."""
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            db = os.path.join(tmp, "save.db")
            make_save(db)
            self.assertEqual(kv_row(db)["predictability_hers"], 0.0)
            self.assertFalse(prims(db).admitted("him"))
            self.assertEqual(kv_row(db)["predictability_hers"], 0.0)
            self.assertNotIn("_admitted", kv_row(db))

    def test_apply_is_idempotent(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            db = os.path.join(tmp, "save.db")
            make_save(db)
            bench_seed.apply_to_db(db, 1.0)
            n = len(kv_row(db)["_log"])
            self.assertEqual(bench_seed.apply_to_db(db, 2.0), {})
            self.assertEqual(len(kv_row(db)["_log"]), n)

    def test_running_store_path(self):
        from store import Store
        seed = bench_seed.load_seed()
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            db = os.path.join(tmp, "save.db")
            make_save(db)
            with contextlib.redirect_stdout(io.StringIO()):
                st = Store(db)
                bench_seed.apply_to_store(st, 5.0)
                got = st.get("primitives")["him"]["predictability_hers"]
                st.conn.close()
            self.assertEqual(got, seed["primitives"]["predictability_hers"])

    def test_arm_inject_seed_him_sets_flag_and_seeds_the_running_store(self):
        import control
        from types import SimpleNamespace

        class KV:
            def __init__(self):
                self.d = {"primitives": {"him": dict(BENCH_ROW)}}

            def get(self, k, default=None):
                return self.d.get(k, default)

            def set(self, k, v):
                self.d[k] = v

        arm = control.Arm()
        arm.app, arm.vt = SimpleNamespace(store=KV()), 9.0
        self.assertFalse(arm.seed_him)
        r = arm.inject("seed.him", True)
        self.assertTrue(arm.seed_him)
        self.assertIn("predictability_hers", r["seeded"])
        self.assertEqual(arm.app.store.d["primitives"]["him"]["predictability_hers"],
                         bench_seed.load_seed()["primitives"]["predictability_hers"])
        self.assertEqual(arm.inject("seed.him", False)["seeded"], [])
        self.assertFalse(arm.seed_him)
        with self.assertRaises(ValueError):
            arm.inject("seed.him", "yes")

    def test_held2_and_held3_overlays_still_admit_with_and_without_seed(self):
        """Both on: held2/held3 keep admit_needs_predictability 0, the seed adds the real value; no conflict."""
        for ov in ("held2", "held3"):
            with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
                db = os.path.join(tmp, "save.db")
                make_save(db)
                p = prims(db, (ov,))
                self.assertEqual(p.config.primitives.admit_needs_predictability, 0.0)
                self.assertTrue(p.admitted("him"))   # the old workaround alone: admitted, predictability still 0
                self.assertEqual(kv_row(db)["predictability_hers"], 0.0)
                make_save(db)
                bench_seed.apply_to_db(db, 1.0)
                p = prims(db, (ov,))
                self.assertTrue(p.admitted("him"))
                self.assertGreater(kv_row(db)["predictability_hers"], 90)


if __name__ == "__main__":
    unittest.main()
