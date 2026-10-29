"""S arm: the bz channel, run builder, control helpers, and an end-to-end through the control API
against a fake OpenAI server. Run: python -m unittest tests.test_bz_s -v"""

import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "bzombie", "arms", "s"))
sys.path.insert(0, ROOT)

import make_run  # noqa: E402
import control  # noqa: E402
import fake_openai  # noqa: E402
from channels.bz_channel import BzChannel  # noqa: E402


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def now_ts(self):
        return self.t


class ChannelTests(unittest.TestCase):
    def test_queue_in_record_out(self):
        clk = FakeClock()
        ch = BzChannel(type("C", (), {})(), None, clk, None)
        ch.push("hi")
        ch.push("there")
        self.assertEqual([t for t, _ in ch.get_new_messages()], ["hi", "there"])
        self.assertEqual(ch.get_new_messages(), [])
        clk.t = 250.0
        n = ch.send_message("hello")
        self.assertTrue(n)
        self.assertFalse(ch.send_message("  "))
        out = ch.take_outputs()
        self.assertEqual(out[0]["virtual_ts"], 250.0)
        self.assertEqual(out[0]["text"], "hello")
        self.assertEqual(ch.take_outputs(), [])


    def test_ids_unique_across_directions(self):
        ch = BzChannel(type("C", (), {})(), None, FakeClock(), None)
        ids = [ch.push("a"), ch.send_message("b"), ch.push("c"), ch.send_message("d")]
        self.assertEqual(len(set(ids)), 4)


class ResumeIds(unittest.TestCase):
    """tk-pjz: a channel built over a restored save restarted its ids at 1, so his messages collided with stored
    tg_ids and the store dropped them: the arm went silent after a resume."""

    def test_seed_ids_continue_after_the_save(self):
        ch = BzChannel(type("C", (), {})(), None, FakeClock(), None)
        ch.seed_ids(41)
        self.assertEqual(ch.push("a"), 42)
        ch.seed_ids(10)  # never goes back
        self.assertEqual(ch.send_message("b"), 43)

    def test_resume_in_a_new_arm_keeps_his_messages(self):
        import sqlite3
        tmp = tempfile.mkdtemp(dir=os.environ.get("BZ_TEST_TMP", "H:/SCAIL/temp"))
        port = 18395
        os.environ.update({"BZ_NO_TICKET": "1", "BZ_RUNS": tmp,
                           "BZ_BASE_URL": f"http://127.0.0.1:{port}/arm/S/{{run_id}}/v1"})
        fake = fake_openai.serve(port)
        threading.Thread(target=fake.serve_forever, daemon=True).start()
        self.addCleanup(fake.server_close)
        self.addCleanup(fake.shutdown)
        t0 = control.parse_local("2026-10-23 08:00")
        d = {"run_id": "rs", "character": "momoka", "lang": "ja", "clock_start": "2026-10-23T08:00:00"}
        a = control.Arm()
        a.runs_root = tmp
        a.start(d)
        a.app.config.api.cache_settle_seconds = 0
        a.send("おはよう。", t0 + 600)
        a.advance(t0 + 1800)
        a.snapshot("a")
        a.stop()
        b = control.Arm()  # a new process's arm over the same run folder, as the harness resume does
        b.runs_root = tmp
        b.start(d)
        b.restore("a")
        b.app.config.api.cache_settle_seconds = 0
        b.send("ただいま", t0 + 3600)
        b.advance(t0 + 4200)
        db = os.path.join(tmp, "rs", "s", "save.db")
        con = sqlite3.connect("file:" + db + "?mode=ro", uri=True)
        users = [r[0] for r in con.execute("SELECT text FROM messages WHERE role='user' ORDER BY ts")]
        ids = [r[0] for r in con.execute("SELECT tg_id FROM messages WHERE tg_id IS NOT NULL")]
        con.close()
        b.stop()
        self.assertEqual(users, ["おはよう。", "ただいま"], "his message after the resume is stored")
        self.assertEqual(len(ids), len(set(ids)), "ids stay unique across the resume")


class HelperTests(unittest.TestCase):
    def test_time_helpers(self):
        a = control.parse_local("2026-10-23 08:00")
        b = control.parse_local("2026-10-23T08:00:00+09:00")
        self.assertEqual(a, b)
        self.assertEqual(control.sim_day(a, a + 86400 * 2 + 5), 3)

    def test_inject_unknown_and_no_bz(self):
        app = type("A", (), {"config": type("C", (), {})(), "state": None})()
        with self.assertRaises(KeyError):
            control.apply_inject(app, "nope", 1)
        with self.assertRaises(KeyError):
            control.apply_inject(app, "bz.order", False)

    def test_switch_alias(self):
        sec = type("B", (), {"cut_constant": True})()
        app = type("A", (), {"config": type("C", (), {"bz": sec})(), "bz": None})()
        control.apply_switch(app, "constant_cut", False)
        self.assertFalse(sec.cut_constant)
        with self.assertRaises(KeyError):
            control.apply_switch(app, "nope", True)

    def test_make_run_tomoe_and_momoka(self):
        with tempfile.TemporaryDirectory(dir="F:/temp") as d:
            p = make_run.build("t1", "tomoe", "2026-10-23 08:00", runs_root=d)
            cfg = json.load(open(p, encoding="utf-8"))
            self.assertEqual(cfg["character"]["writes_to_him"], "english")
            self.assertEqual(cfg["character"]["instruction_language"], "english")
            self.assertEqual(cfg["clock"]["mode"], "stepped")
            self.assertEqual(cfg["api"]["provider"], "bz")
            self.assertIn("/arm/S/t1/v1", cfg["api"]["providers"]["bz"]["base_url"])
            self.assertFalse(cfg["vn"]["enabled"])
            self.assertNotIn("momoka.db", json.dumps(cfg))
            models = {r["model"] for r in cfg["models"].values() if isinstance(r, dict)}
            self.assertEqual(models, {"bz-model"})
            self.assertIn("19", open(cfg["character"]["style_prompt"], encoding="utf-8").read()[:600])
            p2 = make_run.build("t2", "momoka", "2026-10-23 08:00", runs_root=d)
            c2 = json.load(open(p2, encoding="utf-8"))
            self.assertEqual(c2["character"]["writes_to_him"], "japanese")
            # no real-machine read for either character
            for c in (cfg, c2):
                for sec in ("resident_sight", "notes", "eroge"):
                    self.assertFalse(c[sec]["enabled"], sec)
                self.assertEqual(c["sensors"]["vault_path"], "")
                self.assertEqual(c["eroge"]["cache_dir"], "")
                self.assertEqual(c["sensors"]["chrome_history_path"], "")
                self.assertTrue(c["recap"]["episodes_report_dir"].startswith(d.replace("\\", "/")))
                self.assertTrue(c["dossier"]["dir"].startswith(d.replace("\\", "/")))
            self.assertFalse(cfg["him_profile"]["enabled"])
            self.assertTrue(c2["him_profile"]["enabled"])
            with open(os.path.join(os.path.dirname(cfg["character"]["style_prompt"]), "bible.md"),
                      encoding="utf-8") as fh:
                bible = fh.read()
            self.assertNotIn("an app on your phone", bible)
            self.assertNotIn("notes vault", bible)
            self.assertIn("no app", bible)


class StubDayClocks(unittest.TestCase):
    """A stub day per character, in process (no HTTP, no real model): Tomoe's own clock is Tokyo and only
    his side is 13 h behind; Momoka's him is Tokyo too; neither has a sight of his machine."""

    def _boot(self, char):
        tmp = tempfile.mkdtemp(dir="F:/temp")
        os.environ.update({"BZ_NO_TICKET": "1", "BZ_RUNS": tmp,
                           "BZ_BASE_URL": "http://127.0.0.1:18339/arm/S/{run_id}/v1"})
        fake = fake_openai.serve(18339)
        threading.Thread(target=fake.serve_forever, daemon=True).start()
        self.addCleanup(fake.server_close)
        self.addCleanup(fake.shutdown)
        arm = control.Arm()
        arm.runs_root = tmp
        arm.start({"run_id": "c_" + char, "character": char, "lang": "en",
                   "clock_start": "2026-10-23T08:00:00"})
        return arm

    def test_tomoe_tokyo_him_behind(self):
        arm = self._boot("tomoe")
        ck = arm.app.clock
        self.assertEqual(ck.now_ts(), control.parse_local("2026-10-23 08:00"))
        self.assertEqual(ck.now().strftime("%H:%M"), "08:00")
        self.assertEqual(ck.user_now().strftime("%Y-%m-%d %H:%M"), "2026-10-22 19:00")
        self.assertEqual(ck.offset_hours(), 13.0)
        self.assertTrue(ck.two_clocks)
        arm.advance(control.parse_local("2026-10-23 12:25"))
        self.assertEqual(ck.hm(), "12:25")
        self.assertEqual(ck.user_now().strftime("%H:%M"), "23:25")
        self.assertIsNone(arm.app.sight)
        self.assertIsNone(arm.app.eroge)

    def test_momoka_same_zone(self):
        arm = self._boot("momoka")
        ck = arm.app.clock
        self.assertEqual(ck.now().strftime("%H:%M"), "08:00")
        self.assertEqual(ck.user_now().strftime("%H:%M"), "08:00")
        self.assertEqual(ck.offset_hours(), 0.0)
        self.assertFalse(ck.two_clocks)
        self.assertIsNone(arm.app.sight)


class _Cfg:
    def __init__(self, sees):
        ex = type("E", (), {"sees_him": sees})()
        self.character = type("Ch", (), {"program": "resident", "existence": ex})()
        self.resident = sees == "resident"


class HomeWording(unittest.TestCase):
    """Tomoe (sees_him none) lives at home: no 'his machine' wording, and a student's night. Momoka's wording
    (sees_him resident) is the resident table untouched."""

    def test_momoka_wording_unchanged(self):
        from sim import sight
        from resident import words  # noqa: F401
        from resident import schedule as rs
        t = sight._table(_Cfg("resident"))
        self.assertIs(t, sight._TABLES["resident"])
        self.assertEqual(t["facts_head"][0], "## What you know about him from talking and from watching his machine")
        self.assertEqual(t["diary_none"], "(nothing of his machine reached her today)")
        self.assertEqual(rs.resident_day(), [{"start": "00:00", "end": "24:00", "activity": "resident on his machine",
                                              "location": "his machine", "with": "alone", "phone_access": "free"}])

    def test_tomoe_table_has_no_machine(self):
        from sim import sight
        from resident import words  # noqa: F401
        t = sight._table(_Cfg("none"))
        self.assertIsNot(t, sight._TABLES["resident"])
        for k, v in t.items():
            for s in (v if isinstance(v, tuple) else (v,)):
                if isinstance(s, str) and k not in ("watching_account_open", "watching_account_played",
                                                    "watching_synopsis_open", "watching_synopsis_played",
                                                    "eroge_digest_line", "role_no"):
                    self.assertNotIn("machine", s.lower(), k)
        self.assertEqual(sight.w(_Cfg("none"), "wonder_seed"), "him")

    def test_home_plan_sleeps(self):
        from resident import schedule as rs
        import datetime
        with tempfile.TemporaryDirectory(dir="F:/temp") as d:
            hp = os.path.join(d, "home.json")
            with open(hp, "w", encoding="utf-8") as fh:
                json.dump(make_run.tomoe_home(), fh)
            cfg = type("C", (), {"world": type("W", (), {"home_file": hp})(),
                                 "director": type("D", (), {"sleep_keywords": ["asleep", "sleeping"]})()})()
            for day in range(19, 26):
                date = datetime.date(2026, 10, day)
                blocks, note = rs.own_day(cfg, None, None, date)
                sl = [b for b in blocks if b["phone_access"] == "none"]
                self.assertEqual([(b["start"], b["end"]) for b in sl], [("01:00", "07:30")], date)
            wed = rs.own_day(cfg, None, None, datetime.date(2026, 10, 21))[0]
            self.assertTrue(any(b["location"] == "cafe" for b in wed))
            tue = rs.own_day(cfg, None, None, datetime.date(2026, 10, 20))[0]
            self.assertFalse(any(b["location"] == "cafe" for b in tue))

    def test_stub_night(self):
        tmp = tempfile.mkdtemp(dir="F:/temp")
        os.environ.update({"BZ_NO_TICKET": "1", "BZ_RUNS": tmp,
                           "BZ_BASE_URL": "http://127.0.0.1:18339/arm/S/{run_id}/v1"})
        fake = fake_openai.serve(18339)   # same port as the other classes: the llm client keeps its first base_url per process
        threading.Thread(target=fake.serve_forever, daemon=True).start()
        self.addCleanup(fake.server_close)
        self.addCleanup(fake.shutdown)
        arm = control.Arm()
        arm.runs_root = tmp
        arm.start({"run_id": "night", "character": "tomoe", "lang": "en", "clock_start": "2026-10-24T00:30:00"})
        arm.app.config.api.cache_settle_seconds = 0
        app = arm.app

        def asleep():
            return bool(app.director.asleep_block(app.schedule))
        arm.advance(control.parse_local("2026-10-24 00:50"))
        self.assertFalse(asleep())
        arm.send("you up?", control.parse_local("2026-10-24 02:00"))
        arm.advance(control.parse_local("2026-10-24 02:10"))
        self.assertTrue(asleep())
        outs = arm.advance(control.parse_local("2026-10-24 07:00"))["outputs"]
        self.assertEqual(outs, [])
        self.assertTrue(asleep())
        row = app.store.conn.execute("SELECT read_ts FROM messages WHERE role='user'").fetchone()
        self.assertTrue(row is None or row[0] is None, "message read while she was asleep")
        arm.advance(control.parse_local("2026-10-24 07:40"))
        self.assertFalse(asleep())
        # no 'his machine' wording in anything the persona was asked
        bad = []
        for root, _, files in os.walk(os.path.join(tmp, "night")):
            for f in files:
                if f.startswith("llm_calls") and f.endswith(".jsonl"):
                    with open(os.path.join(root, f), encoding="utf-8") as fh:
                        for ln in fh:
                            if "his machine" in ln or "on his machine" in ln:
                                bad.append(f)
                                break
        self.assertEqual(bad, [])


class _KV:
    def __init__(self):
        self.d = {}

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v


class _Clk:
    def __init__(self, now):
        self.now = now

    def now_ts(self):
        return self.now

    def to_user(self, ts):
        import datetime
        from zoneinfo import ZoneInfo
        return datetime.datetime.fromtimestamp(ts, ZoneInfo("Asia/Tokyo"))


class PcSight(unittest.TestCase):
    """tk-49t: his pc events reach her as the phone account (window of events) and the live line, not as one
    replaced row, and the trace labels them env_event."""

    def _app(self, now):
        ph = type("P", (), {"rolling_hours": 2, "live_line_max_age_minutes": 45})()
        app = type("A", (), {})()
        app.store, app.clock, app.config = _KV(), _Clk(now), type("C", (), {"phone": ph})()
        app.phone = type("Ph", (), {})()
        app.phone.account = lambda: app.store.get("phone_account") or {}
        control.pc_install(app)
        return app

    def test_idle_reading(self):
        f = control.pc_idle_min
        self.assertEqual(f({"text": "PC wakes from sleep."}), 0)
        self.assertEqual(f({"text": "Game closed. Browser open with title 'x'."}), 0)
        self.assertEqual(f({"text": "PC idle for 40 minutes, then display turns off."}), 40)
        self.assertEqual(f({"text": "PC goes to sleep."}), 60)
        self.assertEqual(f({"text": "Browser closed. PC idle, screen stays on."}), 60)
        self.assertEqual(f({"text": "PC idle", "idle_min": 15}), 15)

    def test_events_accumulate_and_live_line(self):
        t0 = control.parse_local("2026-10-26 07:12")
        app = self._app(t0)
        control.env_apply(app, {"kind": "pc", "text": "PC wakes from sleep."}, t0)
        control.env_apply(app, {"kind": "pc", "text": "Browser opens. Tabs: weather."}, t0 + 180)
        app.clock.now = t0 + 200
        acct = app.store.get("phone_account")["text"]
        self.assertIn("07:12 PC wakes from sleep.", acct)
        self.assertIn("07:15 Browser opens. Tabs: weather.", acct)
        self.assertEqual(app.phone.live_line(), "Browser opens. Tabs: weather.")
        self.assertEqual(control.pc_view(app), (acct, "Browser opens. Tabs: weather."))
        app.clock.now = t0 + 180 + 46 * 60
        self.assertEqual(app.phone.live_line(), "", "a stale live line is not shown")

    def test_idle_hides_live_and_grows(self):
        t0 = control.parse_local("2026-10-26 08:20")
        app = self._app(t0)
        control.env_apply(app, {"kind": "pc", "text": "PC idle for 40 minutes, then display turns off."}, t0)
        self.assertEqual(app.phone.live_line(), "")
        self.assertEqual(app.store.get("phone_last_live")["idle_min"], 40)
        control.pc_idle_refresh(app, t0 + 600)
        self.assertEqual(app.store.get("phone_last_live")["idle_min"], 50)
        control.env_apply(app, {"kind": "pc", "text": "Display wakes."}, t0 + 900)
        self.assertEqual(app.store.get("phone_last_live")["idle_min"], 0)

    def test_momoka_prompt_input_and_trace(self):
        """Stub day, in process: a pc event reaches latest_digest (what her reply and pick prompts embed) and
        every trace of a later output carries it as env_event."""
        tmp = tempfile.mkdtemp(dir="F:/temp")
        os.environ.update({"BZ_NO_TICKET": "1", "BZ_RUNS": tmp,
                           "BZ_BASE_URL": "http://127.0.0.1:18339/arm/S/{run_id}/v1"})
        fake = fake_openai.serve(18339)
        threading.Thread(target=fake.serve_forever, daemon=True).start()
        self.addCleanup(fake.server_close)
        self.addCleanup(fake.shutdown)
        arm = control.Arm()
        arm.runs_root = tmp
        arm.start({"run_id": "pc_momoka", "character": "momoka", "lang": "ja", "clock_start": "2026-10-26T07:00:00"})
        arm.app.config.api.cache_settle_seconds = 0
        arm.add_env([{"ts": "2026-10-26T07:12:00", "kind": "pc", "text": "PC wakes from sleep. Lock screen, then signed in."},
                     {"ts": "2026-10-26T07:15:00", "kind": "pc", "text": "Window title: 'Inbox - Mail'."}])
        arm.send("おはよう", "2026-10-26T07:20:00")
        outs = arm.advance(control.parse_local("2026-10-26 07:50"))["outputs"]
        dig = arm.app.phone.latest_digest()
        self.assertIn("07:12 PC wakes from sleep", dig, "the earlier event is in the window")
        self.assertIn("Inbox - Mail", dig)
        self.assertIn("いまこの瞬間: Window title: 'Inbox - Mail'.", dig, "the live line shows every tick")
        for o in outs:
            tr = json.load(open(os.path.join(tmp, "pc_momoka", "traces", o["output_id"] + ".json"), encoding="utf-8"))
            kinds = {i["kind"] for i in tr["inputs"]}
            self.assertIn("env_event", kinds)
        arm.stop()


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(dir="F:/temp")
        cls.fake = fake_openai.serve(18339)
        threading.Thread(target=cls.fake.serve_forever, daemon=True).start()
        os.environ.update({"BZ_NO_TICKET": "1", "BZ_RUNS": cls.tmp,
                           "BZ_BASE_URL": "http://127.0.0.1:18339/arm/S/{run_id}/v1"})
        control.ARM.runs_root = cls.tmp
        cls.srv = control.ThreadingHTTPServer(("127.0.0.1", 18338), control.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.fake.shutdown()

    def call(self, path, body=None):
        url = "http://127.0.0.1:18338" + path
        req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                     method="GET" if body is None else "POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise AssertionError(f"{path}: {e.code} {e.read().decode('utf-8', 'replace')}")

    def test_flow(self):
        t0 = control.parse_local("2026-10-23 08:00")
        self.call("/control/start", {"run_id": "e2e", "character": "tomoe", "lang": "en",
                                     "clock_start": "2026-10-23T08:00:00"})
        control.ARM.app.config.api.cache_settle_seconds = 0  # stub host never caches (else 15 wall s per big call)
        self.call("/control/env", {"events": [{"ts": t0 + 5, "kind": "world", "text": "Lecture at 9 on stats.",
                                               "source": "env_script/1"}]})
        self.call("/control/send", {"text": "good morning", "ts": t0 + 10})
        outs = []
        t = t0 + 10
        while not outs and t < t0 + 10 + 600:
            t += 60
            outs = self.call("/control/advance", {"to": t})["outputs"]
        self.assertTrue(outs, "no reply within 10 virtual minutes")
        tr = self.call("/control/trace/" + outs[0]["output_id"])
        self.assertEqual(tr["arm"], "S")
        self.assertTrue(tr["final_call_id"])
        self.assertTrue(tr["calls"])
        self.call("/control/snapshot", {"name": "a"})
        vt_a = self.call("/control/state")["virtual_ts"]
        self.call("/control/advance", {"to": t + 120})
        self.assertGreater(self.call("/control/state")["virtual_ts"], vt_a)
        self.call("/control/restore", {"name": "a"})
        self.assertEqual(self.call("/control/state")["virtual_ts"], vt_a)
        clk = json.load(open(os.path.join(self.tmp, "e2e", "clock.json")))
        self.assertEqual(clk["virtual_ts"], vt_a)
        self.call("/control/stop", {})

    def _day(self, character, lang, texts):
        """Stub day: his messages at 08:10, 10:00, 12:30; every one must reach her store, be read,
        and be answered by a reply output or a logged [pick] decision."""
        import sqlite3
        run = "e2e_day_" + character
        t0 = control.parse_local("2026-10-23 08:00")
        self.call("/control/start", {"run_id": run, "character": character, "lang": lang,
                                     "clock_start": "2026-10-23T08:00:00"})
        # the stub host never caches, so the burst hold would wait 15 wall seconds on every big call
        control.ARM.app.config.api.cache_settle_seconds = 0
        sends =[t0 + 600, t0 + 7200, t0 + 9000 * 1.0 + 0]
        outs = []
        for s, txt in zip(sends, texts):
            self.call("/control/send", {"text": txt, "ts": s})
            outs += self.call("/control/advance", {"to": s + 1800})["outputs"]
        self.call("/control/advance", {"to": t0 + 6 * 3600})
        arm = control.ARM
        db = os.path.join(self.tmp, run, "s", "save.db")
        con = sqlite3.connect("file:" + db + "?mode=ro", uri=True)
        users = con.execute("SELECT text, read_ts FROM messages WHERE role='user' ORDER BY ts").fetchall()
        tg = [r[0] for r in con.execute("SELECT tg_id FROM messages WHERE tg_id IS NOT NULL").fetchall()]
        con.close()
        self.assertEqual([u[0] for u in users], texts, "every message of his is stored")
        self.assertEqual(len(tg), len(set(tg)), "tg ids are unique across both roles")
        logs = ""
        d = os.path.join(self.tmp, run, "s", "logs")
        for sub in os.listdir(d):
            p = os.path.join(d, sub, "session.log")
            if os.path.exists(p):
                logs += open(p, encoding="utf-8", errors="replace").read()
        decisions = logs.count("[pick] live at the inbound moment")
        print(f"\n{character}: users stored {len(users)}, read {sum(1 for u in users if u[1])}, outputs {len(outs)}, inbound picks {decisions}")
        self.assertTrue(outs or decisions >= len(texts), "each message gets a reply or a logged pick decision")
        self.assertTrue(all(u[1] for u in users) or decisions >= len(texts))
        kinds = [(o["virtual_ts"], o["kind"]) for o in outs]
        for ts in {k[0] for k in kinds}:
            self.assertEqual(len({k for t, k in kinds if t == ts}), 1, "bubbles of one delivery share a kind")
        self.call("/control/stop", {})

    def test_two_cycles_one_process(self):
        """tk-1zr: stop then start works in one process, and restore works after a stop+start."""
        t0 = control.parse_local("2026-10-23 08:00")
        for i, ch in enumerate(("tomoe", "momoka")):
            self.call("/control/start", {"run_id": f"cyc{i}", "character": ch, "lang": "en",
                                         "clock_start": "2026-10-23T08:00:00"})
            control.ARM.app.config.api.cache_settle_seconds = 0  # stub host never caches
            self.call("/control/snapshot", {"name": "s"})
            r =self.call("/control/advance", {"to": t0 + 300})
            self.assertEqual(r["virtual_ts"], t0 + 300)
            self.call("/control/restore", {"name": "s"})
            self.assertEqual(self.call("/control/state")["virtual_ts"], t0)
            self.call("/control/stop", {})

    def test_day_tomoe(self):
        self._day("tomoe", "en", ["hey, morning", "back from the gym", "lunch time, you around?"])

    def test_day_momoka(self):
        self._day("momoka", "ja", ["おはよう。", "ただいま", "お昼だよ、いる？"])


if __name__ == "__main__":
    unittest.main()
