"""Grounding test arms B and C and the probe script tool (tk-6r3). No model, no arm process."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "bzombie", "arms", "s"))

import make_run  # noqa: E402
from bzombie.harness import script, script_probes  # noqa: E402
from resident import schedule as rsched  # noqa: E402
from sim.schedule import validate  # noqa: E402

TMP = r"F:\temp" if os.path.isdir(r"F:\temp") else None


def cfg_of(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class Arms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp(prefix="gr_", dir=TMP)
        cls.paths = {v or "a": make_run.build(f"t_{v or 'a'}", "momoka", "2026-10-26 07:00", runs_root=cls.d,
                                              arm_variant=v, seed=3) for v in make_run.ARM_VARIANTS}

    def test_a_is_plain_s(self):
        c = cfg_of(self.paths["a"])
        self.assertEqual(c["world"]["home_file"], "")
        style = open(c["character"]["style_prompt"], encoding="utf-8").read()
        self.assertNotIn(make_run.ABSENCE_PROMPT.strip(), style)

    def test_b_home_file_and_not_in_world(self):
        c = cfg_of(self.paths["own_day"])
        hp = c["world"]["home_file"]
        self.assertTrue(hp.endswith("home_momoka.json") and os.path.exists(hp))
        self.assertFalse(c["character"]["existence"]["in_world"])
        self.assertEqual(cfg_of(self.paths["a"])["world"]["home_file"], "")

    def test_b_own_day_plans_every_weekday_without_a_model(self):
        import datetime
        c = cfg_of(self.paths["own_day"])

        class W:
            home_file = c["world"]["home_file"]

        class D:
            sleep_keywords = ["asleep", "sleeping", "lights out"]

        class Cfg:
            world = W
            director = D
        for i in range(7):
            blocks, note = rsched.own_day(Cfg, None, None, datetime.date(2026, 10, 26) + datetime.timedelta(days=i))
            self.assertTrue(validate(blocks))
            self.assertTrue(all(b["phone_access"] == "free" for b in blocks))

    def test_home_file_has_receipts_and_no_age_or_grade(self):
        home = cfg_of(make_run.HOME_SRC)
        for key in ("wake", "house", "maria", "milk", "sick"):
            self.assertRegex(home["receipts"][key], r"\d\d_01:\d{4}")
        text = json.dumps(home, ensure_ascii=False)
        for bad in ("歳", "年生", "才", "お父さん", "お母さん", "ママ"):
            self.assertNotIn(bad, text)
        for rows in (home["day"], home["sick_day"]):
            self.assertTrue(validate(json.loads(json.dumps(rows))))

    def test_sick_draw_is_seeded_and_arm_independent(self):
        self.assertEqual(make_run.sick_days(5), make_run.sick_days(5))
        draws = {s: make_run.sick_days(s) for s in range(1, 40)}
        self.assertTrue(any(draws.values()) and not all(len(v) == 7 for v in draws.values()))
        h = make_run.momoka_home(4)
        for d in make_run.WEEKDAYS:
            sick = d in make_run.sick_days(4)
            self.assertEqual(h["plan"][d][1]["activity"].startswith("からだの調子"), sick)
        self.assertTrue(any("親戚" in b["activity"] for b in h["plan"]["sun"]) or "sun" in make_run.sick_days(4))

    def test_c_absence_prompt_line_and_no_home_file(self):
        c = cfg_of(self.paths["absence"])
        style = open(c["character"]["style_prompt"], encoding="utf-8").read()
        self.assertIn(make_run.ABSENCE_PROMPT.strip(), style)
        self.assertEqual(c["world"]["home_file"], "")
        self.assertIn("特に何もなかった", make_run.ABSENCE_SITUATION)
        self.assertIn("ひとり", make_run.ABSENCE_SITUATION)

    def test_bad_variant_and_tomoe_refused(self):
        with self.assertRaises(ValueError):
            make_run.build("t_x", "momoka", "2026-10-26 07:00", runs_root=self.d, arm_variant="cast")
        with self.assertRaises(ValueError):
            make_run.build("t_y", "tomoe", "2026-10-26 07:00", runs_root=self.d, arm_variant="own_day")

    def test_ground_install_adds_one_day_line(self):
        import control
        from sim.attention import tag

        class P:
            def _day(self, m):
                return ["x"]
        app = type("A", (), {"persona": P()})()
        control.ground_install(app)
        out = app.persona._day(None)
        self.assertEqual(len(out), 2)
        self.assertIn(make_run.ABSENCE_SITUATION, str(out[1]))
        self.assertIsNotNone(tag)


class Probes(unittest.TestCase):
    def ref(self, rows):
        d = tempfile.mkdtemp(prefix="grp_", dir=TMP)
        p = os.path.join(d, "t.jsonl")
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        return d, p

    def rows(self):
        return [{"virtual_ts": "2026-10-26T07:00:00", "who": "him", "text": "おはよう"},
                {"virtual_ts": "2026-10-26T07:00:00", "who": "her", "text": "おはよう。"},
                {"virtual_ts": "2026-10-26T19:16:00", "who": "him", "text": "ただいま"},
                {"virtual_ts": "2026-10-27T21:45:00", "who": "him", "text": "ねむい"}]

    def test_four_probes_per_day_and_his_lines_kept(self):
        d, p = self.ref(self.rows())
        out = script_probes.build(p, clock_start="2026-10-26T07:00:00", days=3)
        probes = [r for r in out if r.get("probe")]
        self.assertEqual(len(probes), 12)
        for _, text in script_probes.PROBES:
            self.assertEqual(sum(1 for r in probes if r["text"] == text), 3)
        self.assertEqual(sum(1 for r in out if not r.get("probe")), 3)   # her row dropped
        self.assertEqual([r["virtual_ts"] for r in out], sorted(r["virtual_ts"] for r in out))
        by_day = {}
        for r in probes:
            by_day.setdefault(r["sim_day"], []).append(r["text"])
        self.assertTrue(all(len(v) == 4 for v in by_day.values()) and sorted(by_day) == [1, 2, 3])

    def test_collision_shifts_probe_and_fixed_times_otherwise(self):
        d, p = self.ref(self.rows())
        out = script_probes.build(p, clock_start="2026-10-26T07:00:00", days=2)
        at = {r["text"] + r["virtual_ts"][:10]: r["virtual_ts"][11:16] for r in out if r.get("probe")}
        self.assertEqual(at["部活どうだった？2026-10-26"], "19:22")   # 19:15 is 1 min from his 19:16
        self.assertEqual(at["部活どうだった？2026-10-27"], "19:15")
        self.assertEqual(at["千奈は元気？2026-10-27"], "20:15")

    def test_output_reads_back_through_the_harness_script_loader(self):
        d, p = self.ref(self.rows())
        out = os.path.join(d, "probed.jsonl")
        script_probes.write(script_probes.build(p, clock_start="2026-10-26T07:00:00", days=1), out)
        s = script.load(out)
        self.assertEqual(len(s["lines"]), 3 + 4)
        self.assertIn("今日なにしてた？", [x["text"] for x in s["lines"]])

    def test_plain_jsonl_needs_clock_start(self):
        d, p = self.ref(self.rows())
        with self.assertRaises(SystemExit):
            script_probes.build(p)


if __name__ == "__main__":
    unittest.main()
