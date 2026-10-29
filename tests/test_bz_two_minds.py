"""Two minds in one run (tk-1pl): PeerHub, House, the channel verbs, make_run contacts, and a stub two-arm run.
Temp VAR only; the stub arms inherit BZ_VAR. No spend."""
import os
import sys
import tempfile
import unittest

if "bzombie.common" in sys.modules:
    os.environ["BZ_VAR"] = str(sys.modules["bzombie.common"].VAR)
else:
    os.environ["BZ_VAR"] = tempfile.mkdtemp(prefix="bzt2m_", dir=r"H:\SCAIL\temp" if os.path.isdir(r"H:\SCAIL\temp") else None)

import shutil  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from bzombie import common, llm  # noqa: E402
from bzombie.common import PROFILES, read_json, read_jsonl, run_dir, write_json  # noqa: E402
from bzombie.harness import driver  # noqa: E402
from bzombie.harness import peers as hpeers  # noqa: E402

llm.backend = llm.canned
write_json(PROFILES / "tomoe.json", {"voice": "stub"})
write_json(PROFILES / "momoka.json", {"voice": "stub"})
STUB = [sys.executable, "-m", "bzombie.harness.stub_arm", "--port", "{port}", "--arm", "{arm}"]


def cfg(run_id, **kw):
    c = {"run_id": run_id, "arm": "S", "character": "momoka", "lang": "ja", "model": "stub", "cap_usd": 1,
         "sim_days": 1, "clock_start": "2026-11-02T00:00:00", "seed": 7, "use_limits": False, "arm_cmd": STUB,
         "step_s": 3600, "peer_step_s": 600, "him_via": "claude", "arm_port": 18371,  # live runs hold 18331-18339
         "peers": [{"character": "tomoe", "lang": "en"}]}
    c.update(kw)
    return c


def tearDownModule():
    from bzombie.harness.armclient import Arm
    for port in list(range(18361, 18370)):
        try:
            Arm(port).stop()
        except Exception:
            pass
    v = str(common.VAR)
    if os.path.basename(v).startswith("bzt2m_"):
        shutil.rmtree(v, ignore_errors=True)


class Units(unittest.TestCase):
    def test_hub_files_and_serves_mail(self):
        d = Path(tempfile.mkdtemp(dir=str(common.VAR)))
        h = hpeers.PeerHub(d / "hub.jsonl", ["a", "b"])
        r1 = h.relay("a", "b", "hi", 1.0, "2026-11-02T10:00:00")
        r2 = h.relay("b", "a", "yo", 2.0, "2026-11-02T10:01:00")
        h.relay("a", "nobody", "x", 3.0, "2026-11-02T10:02:00")
        self.assertEqual((r1["id"], r2["id"]), (1, 2))
        self.assertEqual([m["text"] for m in h.mail("b")], ["hi"])
        self.assertEqual(h.mail("b", after=1), [])
        self.assertFalse(h.rows[2]["known"])
        again = hpeers.PeerHub(d / "hub.jsonl", ["a", "b"])  # a resume reads the log
        self.assertEqual(len(again.rows), 3)
        again.truncate(1)
        self.assertEqual(len(hpeers.PeerHub(d / "hub.jsonl", ["a", "b"]).rows), 1)

    def test_house_tells_the_others_once_per_change(self):
        rooms = {"house": {"ja": "家", "en": "the house"}, "maid_room": {"ja": "メイドの部屋", "en": "the maid room"}}
        h = hpeers.House(rooms, outside=["town"])
        nm = {"ja": {"m": "百花", "t": "朋絵"}, "en": {"m": "Momoka", "t": "Tomoe"}}
        lg = {"m": "ja", "t": "en"}
        self.assertEqual(h.update("m", "house", nm, lg), [])  # nobody else placed yet
        ev = dict(h.update("t", "maid_room", nm, lg))
        self.assertIn("朋絵", ev["m"])
        self.assertEqual(h.update("t", "maid_room", nm, lg), [])  # no change, no line
        self.assertEqual(h.update("t", "somewhere free text", nm, lg), [])  # unknown place says nothing
        out = dict(h.update("t", "town", nm, lg))
        self.assertIn("家を出ている", out["m"])
        self.assertEqual(h.update("m", "house", nm, lg), [])

    def test_channel_peer_verbs(self):
        from channels.bz_channel import BzChannel
        conf = SimpleNamespace(character=SimpleNamespace(name="Momoka"))
        ch = BzChannel(conf)
        self.assertEqual(ch.hub_id, "momoka")
        self.assertTrue(ch.peer_send("maria", "おはよう"))
        self.assertFalse(ch.peer_send("maria", "  "))
        out = ch.take_peer_out()
        self.assertEqual((out[0]["to"], out[0]["from"], out[0]["text"]), ("maria", "momoka", "おはよう"))
        self.assertEqual(ch.take_peer_out(), [])
        ch.peer_in([{"id": 1, "from": "maria", "text": "a"}, {"id": 2, "from": "maria", "text": "b"}])
        ch.peer_in([{"id": 2, "from": "maria", "text": "b"}])  # delivered once
        self.assertEqual([m["id"] for m in ch.peer_updates(after=0)], [1, 2])
        self.assertEqual([m["id"] for m in ch.peer_updates(after=1)], [2])

    def test_make_run_writes_peer_contacts(self):
        from bzombie.arms.s import make_run
        minds = [{"key": "momoka"}, {"key": "tomoe"}]
        self.assertEqual(make_run.peer_contact_rows(minds, "momoka", "ja")[0]["name"], "朋絵")
        self.assertEqual(make_run.peer_contact_rows(minds, "tomoe", "en")[0], {"id": "momoka", "name": "Momoka", "language": ""})
        root = tempfile.mkdtemp(dir=str(common.VAR))
        p = make_run.build("t_mr", "tomoe", "2026-11-02 08:00", runs_root=root, role="peer",
                           peer_contacts=make_run.peer_contact_rows(minds, "tomoe", "en"))
        c = read_json(p)
        self.assertTrue(c["peer_talk"]["enabled"])
        self.assertEqual(c["peer_talk"]["contacts"][0]["id"], "momoka")
        self.assertEqual(c["world"]["user_timezone"], "Asia/Tokyo")
        home = read_json(c["world"]["home_file"])
        ids = {b["location"] for b in home["plan"]["mon"]}
        self.assertTrue(ids <= set(make_run.HOUSE["rooms"]), ids)
        with self.assertRaises(ValueError):
            make_run.build("t_mr2", "nobody", "2026-11-02 08:00", runs_root=root)

    def test_make_run_maria_peer(self):
        from bzombie.arms.s import make_run
        minds = [{"key": "momoka"}, {"key": "maria"}]
        rows = make_run.peer_contact_rows(minds, "maria", "ja")
        self.assertEqual(rows[0]["id"], "momoka")
        self.assertEqual(rows[0]["name"], "お嬢様")   # her own address for 百花 (her cast.json)
        self.assertEqual(make_run.peer_contact_rows(minds, "momoka", "ja")[0]["name"], "真里亜")
        root = tempfile.mkdtemp(dir=str(common.VAR))
        p = read_json(make_run.build("t_maria", "maria", "2026-11-02 08:00", runs_root=root, role="peer",
                                     peer_key="maria", peer_contacts=rows))
        c = p
        self.assertEqual(c["peer_talk"]["contacts"][0]["id"], "momoka")
        self.assertEqual(c["character"]["name_ja"], "真里亜")
        self.assertEqual(c["character"]["writes_to_him"], "japanese")
        self.assertFalse(c["character"]["existence"]["in_world"])
        self.assertEqual(c["world"]["user_timezone"], "Asia/Tokyo")
        bible = Path(c["character"]["style_prompt"]).parent / "bible.md"
        src = Path(make_run.MARIA_DIR) / "prompts"
        self.assertEqual(bible.read_text(encoding="utf-8"), (src / "bible.md").read_text(encoding="utf-8"))
        self.assertEqual(Path(c["character"]["style_prompt"]).read_text(encoding="utf-8"),
                         (src / "style.md").read_text(encoding="utf-8"))
        self.assertEqual(read_json(c["world"]["character_file"])["id"], "maria")
        self.assertEqual(read_json(c["character"]["neutral_file"])["id"], "maria")
        self.assertTrue(Path(c["character"]["cast_file"]).exists())
        self.assertEqual(c["quality"]["caps"]["phrases"]["うふふ"], 2)
        for sec in ("vn", "tts"):
            self.assertFalse(c[sec]["enabled"])
        home = read_json(c["world"]["home_file"])
        ids = {b["location"] for d in make_run.WEEKDAYS for b in home["plan"][d]}
        self.assertTrue(ids <= set(make_run.HOUSE["rooms"]), ids)
        self.assertEqual({r["id"] for r in home["home"]["rooms"]}, set(make_run.HOUSE["rooms"]))
        self.assertNotIn("Tomoe", Path(c["character"]["style_prompt"]).read_text(encoding="utf-8"))
        self.assertNotIn("Test card", bible.read_text(encoding="utf-8"))

    def test_ticket_name_per_arm(self):
        from unittest import mock
        from bzombie.arms.s import control
        seen = []

        def fake_run(cmd, **kw):
            seen.append(cmd[cmd.index("--who") + 1])
            return SimpleNamespace(returncode=0, stdout="ok t1")
        for key in ("", "maria"):
            st = control.Arm()
            st.run_id, st.peer_key = "r9", key
            with mock.patch.dict(os.environ, {"BZ_NO_TICKET": "0"}), mock.patch.object(control, "LIMITS", __file__), \
                    mock.patch.object(control.subprocess, "run", fake_run):
                st._ticket()
        self.assertEqual(seen, ["scail/bz_s_r9", "scail/bz_s_r9#maria"])

    def test_config_checks(self):
        driver.load_config(cfg("t_ok"))
        with self.assertRaises(ValueError):
            driver.load_config(cfg("t_dup", peers=[{"character": "momoka"}]))
        with self.assertRaises(ValueError):
            driver.load_config(cfg("t_p", arm="P"))


class StubRun(unittest.TestCase):
    def test_two_arm_stub_run(self):
        c = driver.load_config(cfg("t_two"))
        driver.init_run(c)
        driver.drive("t_two")
        st = read_json(run_dir("t_two") / "state.json")
        self.assertEqual(st["status"], "done", st)
        rd = run_dir("t_two")
        tr = read_jsonl(rd / "transcript.jsonl")
        whos = {e["who"] for e in tr}
        self.assertTrue({"him", "her", "env", "peer:momoka", "peer:tomoe"} <= whos, whos)
        peer = [e for e in tr if e["who"].startswith("peer:")]
        self.assertTrue(all(e["kind"] == "peer" and e["to"] in ("momoka", "tomoe") and e["hub_id"] for e in peer))
        self.assertEqual([e["i"] for e in tr], list(range(len(tr))))
        self.assertTrue(any(e["who"] == "env" and e.get("source", "").startswith("house:") for e in tr))
        cc = read_json(rd / "config.json")
        pp = cc["peer_ports"]["tomoe"]
        self.assertTrue(18361 <= pp <= 18369 and not 18331 <= pp <= 18339, pp)
        self.assertEqual(len(read_jsonl(rd / "peer_hub.jsonl")), len(peer))
        self.assertTrue((rd / "peers" / "tomoe").is_dir())


if __name__ == "__main__":
    unittest.main()
