"""castworld: plan validation, beat timing, presence, world_log shape vs bzombie/grounding.py, no age/grade,
一悟 never given lines. A fake chat stands in for the gateway; a small fixture stands in for koikano_world.json."""
import json
import re
import shutil
import sys
import tempfile
import unittest
from datetime import date as Date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bzombie import grounding  # noqa: E402
from castworld import check, spec as specmod  # noqa: E402
from castworld.bench import WorldRunner  # noqa: E402
from castworld.engine import Owner  # noqa: E402
from castworld.store import Store  # noqa: E402

RAW = {
    "her": {"key": "momoka", "name": "百花", "home_place": "her_room", "sick_rate": 0.0},
    "places": {"club_room": {"ja": "部室"}, "her_room": {"ja": "百花の部屋"}, "hallway": {"ja": "廊下"},
               "meeting_room": {"ja": "会議室"}},
    "cast": {
        "sena": {"name": "千奈", "voice": ["おっとり"], "week": {"fri": ["放課後 club_room 稽古"]}},
        "maria": {"name": "真里亜", "voice": ["丁寧"], "light": True},
        "mayu": {"name": "真優", "voice": ["元気"]},
    },
}
DATE = "2026-10-30"  # a Friday


def beat(time, place, present, kind="club", gist="稽古をした", tags=("台本",)):
    return {"time": time, "place": place, "present": present, "kind": kind, "gist": gist, "tags": list(tags)}


GOOD_BEATS = [
    beat("07:50", "hallway", ["maria", "mayu"], "chat", "真里亜と真優が廊下で話した"),
    beat("16:00", "club_room", ["momoka", "sena", "mayu"], "club", "部室で稽古をした"),
    beat("17:30", "meeting_room", ["maria"], "meeting", "真里亜が会議室で資料を運んだ"),
    beat("19:00", "her_room", ["momoka", "maria"], "home", "部屋で真里亜がミルクを温めた", ["ミルク"]),
    beat("12:10", "shrine", ["sena"], "outing", "神社に寄った"),                       # unknown place
    beat("13:00", "club_room", ["sena", "x_stranger"], "club", "知らない人がいた"),     # unknown roster id
    beat("14:00", "club_room", ["momoka", "ichigo"], "club", "一悟と練習"),             # protagonist id
    beat("15:00", "club_room", ["sena"], "club", "高校二年生の千奈が練習した"),         # grade
]


class Fake:
    def __init__(self, beats=None, turn_lines=None):
        self.beats = GOOD_BEATS if beats is None else beats
        self.turn_lines = turn_lines
        self.n = 0

    def __call__(self, text):
        self.n += 1
        if "ビート" in text and "【場所" in text:
            return json.dumps({"beats": self.beats}, ensure_ascii=False)
        if "やりとり" in text:
            keys = re.search(r"この場にいる人: (.*)", text).group(1)
            who = "sena" if "sena" in keys else ("maria" if "maria" in keys else "mayu")
            lines = self.turn_lines or [{"who": who, "text": "今日もよろしくね"}]
            return json.dumps({"lines": lines}, ensure_ascii=False)
        if "一日を" in text:
            return json.dumps({"line": "いつもの一日だった"}, ensure_ascii=False)
        if "別の場所" in text or "話します" in text:
            return json.dumps({"text": "さっき会議室で資料を運んでたんだって"}, ensure_ascii=False)
        return "{}"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir="F:/temp"))
        self.spec = specmod.normalize(RAW)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def owner(self, fake=None, seed=1):
        return Owner(self.spec, Store(self.tmp / "castworld.db"), fake or Fake(), seed=seed)


class TestValidation(Base):
    def test_unknown_ids_dropped_not_repaired(self):
        o = self.owner()
        beats = o.plan_day(DATE)
        self.assertEqual(len(beats), 4)
        reasons = " | ".join(d["reason"] for d in o.drops)
        self.assertIn("unknown place id 'shrine'", reasons)
        self.assertIn("unknown roster id 'x_stranger'", reasons)
        self.assertIn("protagonist id", reasons)
        self.assertIn("age or grade", reasons)
        self.assertEqual(len(o.drops), 4)
        for b in beats:
            self.assertIn(b["place"], self.spec["places"])

    def test_sick_day_her_only_at_home(self):
        raw = json.loads(json.dumps(RAW))
        raw["her"]["sick_rate"] = 1.0
        self.spec = specmod.normalize(raw)
        o = self.owner()
        beats = o.plan_day(DATE)
        for b in beats:
            if "momoka" in b["present"]:
                self.assertEqual(b["place"], "her_room")
        self.assertTrue(any("sick day" in d["reason"] for d in o.drops))

    def test_beat_count_bounds(self):
        o = self.owner()
        n = o.beat_count(o.draws(DATE))
        self.assertTrue(6 <= n <= 10)


class TestDay(Base):
    def test_timing_presence_calls(self):
        fake = Fake()
        o = self.owner(fake)
        res = o.run_day(DATE)
        times = [b["time"] for b in res["beats"]]
        self.assertEqual(times, sorted(times))
        # scenes only for beats with her present: 2 beats (16:00 club, 19:00 her_room)
        her_beats = [b for b in res["beats"] if "momoka" in b["present"]]
        self.assertEqual(len(her_beats), 2)
        self.assertTrue(4 <= res["calls"]["cast_turn"] <= 6)
        self.assertEqual(res["calls"]["plan_day"], 1)
        self.assertLessEqual(res["calls"].get("gossip", 0), 1)
        # one life per person with a beat: sena, maria, mayu
        self.assertEqual(res["calls"]["write_life"], 3)
        for e in res["events"]:
            self.assertEqual(e["kind"], "world")
            self.assertTrue(e["ts"].startswith(DATE))
            self.assertRegex(e["text"], r"^\[\d\d:\d\d · [^·]+ · [^\]]+\] .+")
        club = [e for e in res["events"] if "部室" in e["text"]]
        self.assertTrue(all(e["ts"] >= f"{DATE}T16:00:00" for e in club))

    def test_gossip_gated_and_once(self):
        o = self.owner()
        res = o.run_day(DATE)
        heard = [r for r in res["world_log"] if r["kind"] == "heard"]
        self.assertEqual(len(heard), 1)
        self.assertEqual(res["calls"]["gossip"], 1)
        # no missed beat with a teller who later meets her: no gossip call
        o2 = self.owner(Fake(beats=[beat("16:00", "club_room", ["momoka", "sena"])]), seed=2)
        r2 = o2.run_day("2026-10-31")
        self.assertEqual(r2["calls"].get("gossip", 0), 0)

    def test_no_age_grade_anywhere(self):
        res = self.owner().run_day(DATE)
        blob = json.dumps(res["world_log"], ensure_ascii=False) + " ".join(e["text"] for e in res["events"])
        self.assertFalse(specmod.has_age_grade(blob))

    def test_ichigo_never_given_lines(self):
        fake = Fake(turn_lines=[{"who": "ichigo", "text": "行こう"}, {"who": "一悟", "text": "うん"},
                                {"who": "sena", "text": "一悟くんは来ないの？"}])
        res = self.owner(fake).run_day(DATE)
        for e in res["events"]:
            self.assertNotRegex(e["text"].split("]")[0], "一悟|ichigo")
        self.assertTrue(any("protagonist" in d["reason"] for d in res["drops"] if d["what"] == "line"))

    def test_bad_lines_dropped(self):
        fake = Fake(turn_lines=[{"who": "sena", "text": "[Fri 16:00] こんにちは"},
                                {"who": "mayu", "text": "高校二年の私が言うよ"},
                                {"who": "momoka", "text": "百花の台詞"}])
        res = self.owner(fake).run_day(DATE)
        self.assertEqual([e for e in res["events"] if e["ts"][11:13] in ("16", "19") and "[16" in e["text"][:4]
                          and "こんにちは" in e["text"]], [])
        self.assertGreaterEqual(len(res["drops"]), 4)


class TestCheck(unittest.TestCase):
    def test_check_line(self):
        cast = {"sena"}
        self.assertEqual(check.check_line("sena", "「おはよう」", ["sena"], cast), ("おはよう", None))
        self.assertIsNone(check.check_line("ichigo", "おはよう", ["ichigo"], cast)[0])
        self.assertIsNone(check.check_line("sena", "おはよう", ["maria"], cast)[0])
        self.assertIsNone(check.check_line("sena", "hello there", ["sena"], cast)[0])
        self.assertIsNone(check.check_line("sena", "<tag>おはよう", ["sena"], cast)[0])
        for bad in ("十七歳だよ", "一年生だから", "高校二年", "学年が違う"):
            self.assertTrue(specmod.has_age_grade(bad), bad)
        self.assertFalse(specmod.has_age_grade("部室で稽古した"))


class TestRealSpec(unittest.TestCase):
    """The landed spec file (characters/momoka/world/koikano_world.json)."""

    def setUp(self):
        self.sp = specmod.load(ROOT / "characters" / "momoka" / "world" / "koikano_world.json")

    def test_shape(self):
        sp = self.sp
        self.assertEqual(set(sp["cast"]), {"mayu", "sena", "alice", "maria", "chisa", "hikaru"})
        self.assertEqual(len(sp["places"]), 28)
        self.assertEqual(sp["her"]["sick_rate"], 0.2)
        self.assertIn(sp["her"]["home_place"], sp["places"])
        self.assertTrue(sp["cast"]["chisa"]["light"] and sp["cast"]["chisa"]["attention"] == 40)
        for k, c in sp["cast"].items():
            self.assertTrue(c["week"]["mon"], k)
            self.assertEqual(set(c["week"]), set(specmod.WEEKDAYS))
        raw = json.loads((ROOT / "characters" / "momoka" / "world" / "koikano_world.json").read_text(encoding="utf-8"))
        for r in raw["rows"].values():
            for f in r["week"]:
                if f.get("place"):
                    self.assertIn(f["place"], sp["places"])
        for a in raw["anchors"]:
            for pid in a["place_ids"]:
                self.assertIn(pid, sp["places"])

    def test_no_age_grade_in_plans(self):
        for c in self.sp["cast"].values():
            self.assertFalse(specmod.has_age_grade(" ".join(sum(c["week"].values(), []))))

    def test_sick_school_days_only(self):
        self.assertTrue(self.sp["her"]["sick_school_days_only"])
        sick = []
        for i in range(400):
            d = (Date(2026, 1, 5) + timedelta(days=i)).isoformat()
            o = Owner.__new__(Owner)
            o.spec, o.seed = self.sp, 7
            sick.append((Date.fromisoformat(d).weekday(), o.her_today(d)["sick"]))
        self.assertFalse(any(s for wd, s in sick if wd >= 5))
        weekdays = [s for wd, s in sick if wd < 5]
        self.assertTrue(0.12 < sum(weekdays) / len(weekdays) < 0.28)


class TestBench(Base):
    def test_world_log_reads_in_grounding_and_resume(self):
        fake = Fake()
        wr = WorldRunner(self.tmp, "t_run", {}, seed=1, chat=fake, spec=self.spec)
        evs = wr.day(0, DATE)
        n_calls = fake.n
        self.assertTrue(evs and all(e["kind"] == "world" and e["source"] == "castworld/day_0" for e in evs))
        # resume: a saved day is reused, no new call
        self.assertEqual(wr.day(0, DATE), evs)
        self.assertEqual(fake.n, n_calls)
        wr.close()
        # grounding.py reads the run folder
        (self.tmp / "transcript.jsonl").write_text(
            json.dumps({"i": 0, "virtual_ts": f"{DATE}T20:00:00", "who": "her", "text": "今日は部室で稽古したよ。"},
                       ensure_ascii=False) + "\n", encoding="utf-8")
        run = grounding.load_run(self.tmp)
        self.assertEqual(len(run["world"]), 5)  # 4 kept beats + 1 heard row
        for w in run["world"]:
            self.assertIsNotNone(w["ts"])
            for k in ("place", "present", "kind", "tags", "gist"):
                self.assertIn(k, w)
        lived = [w for w in run["world"] if grounding._is_her(w) and w["kind"] != "heard"]
        self.assertEqual(len(lived), 2)
        self.assertTrue(any(w["kind"] == "heard" for w in run["world"]))
        res = grounding.check_run(self.tmp)
        self.assertTrue(res["world_log"])


if __name__ == "__main__":
    unittest.main()
