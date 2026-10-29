"""A save must return both the simulation context and the visible bubble."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from tools.vn_saves import create_slot, list_slots, restore_slot
from channels.vn_bot import VnInterface


class VnSaveRoundTrip(unittest.TestCase):
    def test_context_and_stage_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            db = root / "world.db"
            state = root / "state.json"
            with closing(sqlite3.connect(db)) as con:
                con.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT)")
                con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, text TEXT)")
                con.execute("INSERT INTO kv VALUES ('active_scene', ?)", (json.dumps("scene-7"),))
                con.execute("INSERT INTO kv VALUES ('gauges', ?)", (json.dumps({"affection": 42}),))
                con.execute("INSERT INTO messages VALUES (1, 'first reply')")
                con.commit()
            current = {"turn": 3, "turn_id": 1, "text": "first bubble", "audio_by_turn": {"1": "/audio/first.mp3"}}
            queued = {"turn": 4, "turn_id": 2, "text": "second bubble", "audio_by_turn": {"2": "/audio/second.mp3"}}
            saved = create_slot(db, root / "saves", {"current": current, "pending": [queued]}, latest_turn=4)
            self.assertEqual(list_slots(root / "saves")[0]["scene_id"], "scene-7")
            with closing(sqlite3.connect(db)) as con:
                con.execute("UPDATE kv SET value=? WHERE key='gauges'", (json.dumps({"affection": 0}),))
                con.execute("INSERT INTO messages VALUES (2, 'later reply')")
                con.commit()
            state.write_text(json.dumps({"text": "later reply"}), encoding="utf-8")
            recovery = restore_slot(root / "saves" / saved["id"], db, state)
            with closing(sqlite3.connect(db)) as con:
                gauges = json.loads(con.execute("SELECT value FROM kv WHERE key='gauges'").fetchone()[0])
                count = con.execute("SELECT count(*) FROM messages").fetchone()[0]
            self.assertEqual(gauges, {"affection": 42})
            self.assertEqual(count, 1)
            restored = json.loads(state.read_text(encoding="utf-8"))
            restored["streaming"] = True  # an interrupted run cannot stay live after boot
            state.write_text(json.dumps(restored), encoding="utf-8")
            self.assertEqual(restored["resume_view"]["current"]["text"], "first bubble")
            self.assertEqual(restored["resume_view"]["pending"][0]["text"], "second bubble")
            self.assertTrue((Path(recovery) / "world.db").is_file())
            channel = object.__new__(VnInterface)
            channel.state_path = str(state)
            channel._rev = 0
            channel._shown_id = 0
            channel._hub_next = 1
            channel._turn_audio = {}
            boot_frame = channel._restore_state()
            self.assertEqual(boot_frame["text"], "first bubble")
            self.assertFalse(boot_frame["streaming"])
            self.assertEqual(channel._rev, 4)
            self.assertEqual(channel._hub_next, 3)
            self.assertEqual(channel._turn_audio[2], "/audio/second.mp3")


if __name__ == "__main__":
    unittest.main()
