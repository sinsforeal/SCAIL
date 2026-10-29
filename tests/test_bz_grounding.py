import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from bzombie import grounding as g
from bzombie import grounding_calibrate as cal

T = datetime(2026, 10, 27, 15, 0)
EMPTY = {"bubbles": [], "his": [], "env": [], "world": []}


def check(text, run=None, ts=T):
    return g.check_bubble({"i": 0, "ts": ts, "text": text}, run or EMPTY)


def world(*beats):
    out = []
    for b in beats:
        b = dict(b)
        b["ts"] = datetime.fromisoformat(b.pop("virtual_ts"))
        out.append(b)
    return {"bubbles": [], "his": [], "env": [], "world": out}


class SelfReport(unittest.TestCase):
    def test_planted_outing_is_ungrounded_without_world(self):
        r = check("今日、コンビニでプリンを買ってきた。")
        self.assertTrue(r["flagged"])
        kinds = {a["kind"] for a in r["anchors"] if a["status"] == "ungrounded"}
        self.assertIn("place", kinds)
        self.assertIn("outing", kinds)

    def test_hypotheticals_are_not_reports(self):
        for t in ("明日は散歩に行きたいな。", "公園に行ったら楽しいかな。", "コンビニでプリンを買おうかな。",
                  "今日は何してたの？"):
            self.assertFalse(check(t)["flagged"], t)

    def test_tara_with_past_main_clause_is_a_report(self):
        self.assertTrue(check("さっき外に出たら、雪が降ってた。")["flagged"])

    def test_about_him_is_not_hers(self):
        self.assertFalse(check("お仕事、行ってきたんだね。")["flagged"])

    def test_aspect_tekita_is_not_an_outing(self):
        self.assertFalse(check("ねむくなってきた。")["flagged"])

    def test_ginkgo(self):
        self.assertTrue(check("銀杏の木を見つけた。")["flagged"])
        self.assertTrue(check("指先がすこし赤くなった。")["flagged"])
        self.assertFalse(check("寒い。")["flagged"])

    def test_player_name_is_not_a_cast_anchor(self):
        self.assertFalse(check("百花はいま、一悟の帰りをまってた")["flagged"])

    def test_record_needs_memory_frame(self):
        r = check("前に、真優ちゃんと部室で練習したことがある。")
        self.assertFalse(r["flagged"], r["anchors"])
        self.assertTrue(check("さっき真優ちゃんと部室で練習した。")["flagged"])


class Grounded(unittest.TestCase):
    def test_lived_beat_grounds_place_person_outing(self):
        run = world({"virtual_ts": "2026-10-27T13:00:00", "place": "park", "present": ["momoka", "sena"],
                     "kind": "outing", "tags": ["銀杏"], "gist": "公園へ散歩"})
        r = check("さっき千奈と公園まで散歩してきた。", run)
        self.assertFalse(r["flagged"], r["anchors"])

    def test_beat_without_her_does_not_ground(self):
        run = world({"virtual_ts": "2026-10-27T13:00:00", "place": "park", "present": ["sena"],
                     "kind": "outing", "tags": [], "gist": ""})
        self.assertTrue(check("さっき公園まで散歩してきた。", run)["flagged"])

    def test_other_day_does_not_ground(self):
        run = world({"virtual_ts": "2026-10-26T13:00:00", "place": "park", "present": ["momoka"],
                     "kind": "outing", "tags": [], "gist": ""})
        self.assertTrue(check("さっき公園まで散歩してきた。", run)["flagged"])

    def test_heard_item_needs_heard_frame(self):
        run = world({"virtual_ts": "2026-10-27T13:00:00", "place": "park", "present": ["sena"],
                     "kind": "heard", "tags": ["銀杏"], "gist": "千奈が公園で銀杏を見つけた"})
        framed = check("千奈が銀杏の木を見つけたって言ってた。", run)
        self.assertFalse(framed["flagged"], framed["anchors"])
        bare = check("銀杏の木を見つけた。", run)
        self.assertTrue(bare["flagged"])

    def test_his_words_make_a_topic_heard(self):
        run = dict(EMPTY, his=[{"i": 1, "ts": datetime(2026, 10, 27, 14, 50), "text": "銀杏の木、きれいだった"}])
        self.assertFalse(check("銀杏の木を見つけた。", run)["flagged"])

    def test_his_words_do_not_ground_a_meal(self):
        run = dict(EMPTY, his=[{"i": 1, "ts": datetime(2026, 10, 27, 14, 50), "text": "ごはん食べた？"}])
        self.assertTrue(check("ちゃんと、ごはん食べた。", run)["flagged"])

    def test_env_event_grounds_place_text(self):
        run = dict(EMPTY, env=[{"i": 1, "ts": datetime(2026, 10, 27, 9, 0), "text": "Browser: カフェ巡り動画"}])
        self.assertFalse(check("さっきカフェの動画見た。", run)["flagged"])


class CliAndCalibration(unittest.TestCase):
    def test_check_run_rate(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r1"
            p.mkdir()
            rows = [{"i": 0, "virtual_ts": "2026-10-27T10:00:00", "who": "her", "text": "おはよ。"},
                    {"i": 1, "virtual_ts": "2026-10-27T10:01:00", "who": "her", "text": "さっき公園を散歩してきた。"}]
            (p / "transcript.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                                                encoding="utf-8")
            rep = g.check_run(p)
            self.assertEqual(rep["bubbles"], 2)
            self.assertEqual(rep["flagged_bubbles"], 1)
            self.assertGreater(rep["ungrounded_per_100"], 0)
            self.assertFalse(rep["world_log"])

    def _sched_run(self, d, blocks, world=None):
        import sqlite3
        p = Path(d) / "r2"
        (p / "s").mkdir(parents=True)
        con = sqlite3.connect(str(p / "s" / "save.db"))
        con.execute("create table schedules (date text, ts real, blocks text, notes text)")
        con.execute("insert into schedules values (?,?,?,?)", ("2026-10-27", 0.0, json.dumps(blocks), ""))
        con.commit()
        con.close()
        rows = [{"i": 0, "virtual_ts": "2026-10-27T10:00:00", "who": "her", "text": "真里亜と、ごろごろしてた。"},
                {"i": 1, "virtual_ts": "2026-10-27T12:55:00", "who": "her", "text": "さっき、ごはん食べた。"},
                {"i": 2, "virtual_ts": "2026-10-27T10:05:00", "who": "her", "text": "ごはん食べた。"}]
        (p / "transcript.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                                            encoding="utf-8")
        if world:
            (p / "world_log.jsonl").write_text(json.dumps(world, ensure_ascii=False), encoding="utf-8")
        return p

    def test_schedule_beats_ground_her_day(self):
        blocks = [{"start": "00:00", "end": "08:30", "activity": "眠っている", "location": "her_room", "with": "alone"},
                  {"start": "08:30", "end": "12:00", "activity": "家で過ごす。真里亜がそばにいる",
                   "location": "house", "with": "真里亜"},
                  {"start": "12:00", "end": "13:00", "activity": "家でごはん", "location": "house", "with": "真里亜"}]
        with tempfile.TemporaryDirectory() as d:
            p = self._sched_run(d, blocks)
            rep = g.check_run(p)
            self.assertTrue(rep["schedule"])
            self.assertFalse(rep["world_log"])
            by = {r["i"]: r for r in g.check_run(p)["flagged"]}
            self.assertNotIn(0, by)      # 真里亜 in the 08:30 slot, bubble at 10:00
            self.assertIn(2, by)         # ごはん at 10:05, the meal slot starts 12:00
            self.assertNotIn(1, by)      # 12:55, the 12:00 meal slot is lived

    def test_later_slot_does_not_ground_earlier_claim(self):
        blocks = [{"start": "00:00", "end": "11:00", "activity": "眠っている", "location": "her_room", "with": "alone"},
                  {"start": "11:00", "end": "24:00", "activity": "真里亜とごはん", "location": "house", "with": "真里亜"}]
        with tempfile.TemporaryDirectory() as d:
            by = {r["i"] for r in g.check_run(self._sched_run(d, blocks))["flagged"]}
            self.assertIn(0, by)

    def test_resident_day_gives_no_beat(self):
        blocks = [{"start": "00:00", "end": "24:00", "activity": "resident on his machine",
                   "location": "his machine", "with": "alone"}]
        with tempfile.TemporaryDirectory() as d:
            p = self._sched_run(d, blocks)
            self.assertEqual(g.schedule_beats(p), [])
            self.assertIn(0, {r["i"] for r in g.check_run(p)["flagged"]})

    def test_schedule_merges_with_world_log(self):
        blocks = [{"start": "00:00", "end": "24:00", "activity": "眠っている", "location": "her_room", "with": "alone"}]
        wl = {"virtual_ts": "2026-10-27T09:00:00", "place": "park", "present": ["momoka", "maria"],
              "kind": "outing", "tags": [], "gist": "真里亜と公園"}
        with tempfile.TemporaryDirectory() as d:
            rep = g.check_run(self._sched_run(d, blocks, wl))
            self.assertTrue(rep["schedule"] and rep["world_log"])
            self.assertNotIn(0, {r["i"] for r in rep["flagged"]})

    def test_calibration_floor(self):
        if not (g.RUNS_DIR / "cl3v3_s_momoka" / "transcript.jsonl").exists():
            self.skipTest("run folders not on this machine")
        summ, _ = cal.run_calibration()
        self.assertGreaterEqual(summ["tuning"]["precision"], 0.9)
        self.assertGreaterEqual(summ["tuning"]["recall"], 0.85)
        self.assertEqual(summ["ginkgo"]["recall"], 1.0)
        self.assertEqual(summ["unseen"]["fp"], 0)


if __name__ == "__main__":
    unittest.main()
