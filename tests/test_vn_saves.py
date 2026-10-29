"""Context and stage restore checks for the VN reader."""

import json
import tempfile
import threading
import unittest
from pathlib import Path

from channels.vn_bot import VnInterface
from store import Store
from tools.vn_saves import (create_line_checkpoint, create_slot, quick_slot,
                            restore_slot, set_quick_slot, validate_slot)


class VnSaveTests(unittest.TestCase):
    def test_archive_keeps_distinct_expressions_when_hub_ids_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(str(Path(tmp) / "world.db"))
            first = store.add_message(1.0, "2026-09-18", "assistant", "first", tg_id=1)
            second = store.add_message(2.0, "2026-09-18", "assistant", "second", tg_id=1)
            store.set_vn_message_frame(first, {"sprite": {"tag": "CD07A001L"}, "mood": "neutral"})
            store.set_vn_message_frame(second, {"sprite": {"tag": "CD07A002L"}, "mood": "smile"})
            frames = store.vn_message_frames([first, second])
            self.assertEqual(frames[first]["sprite"]["tag"], "CD07A001L")
            self.assertEqual(frames[second]["sprite"]["tag"], "CD07A002L")
            reader = VnInterface.__new__(VnInterface)
            reader.store = store
            reader.voice_index = None
            reader._lock = threading.RLock()
            reader._state = {"sprite": {"tag": "CD07A002L"}}
            rows = reader.recent_log()
            self.assertEqual([row["stage"]["sprite"]["tag"] for row in rows],
                             ["CD07A001L", "CD07A002L"])
            self.assertEqual([row["stage_source"] for row in rows],
                             ["recorded", "recorded"])
            store.conn.close()

    def test_line_checkpoint_rewinds_context_and_retains_reply_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, state = root / "world.db", root / "state.json"
            store = Store(str(db))
            store.set("continuity", {"chapter": 1})
            mid = store.add_message(1.0, "2026-09-18", "assistant", "first", tg_id=12)
            frozen = [{"role": "user", "content": "the original question"}]
            store.add_reply_prompt(mid, "momoka", 1.0, "test-model", frozen,
                                   {"temperature": 0.7}, [mid], "first")
            store.add_swipe(mid, 0, "test-model", "first")
            frame = {"turn": 12, "turn_id": 12, "text": "first", "speaker": "百花",
                     "scene": {"url": "/asset/bg/classroom.png"}}
            store.set_vn_frame(12, frame)
            checkpoint = create_line_checkpoint(db, root / "checkpoints", frame, mid)
            store.set_vn_line_checkpoint(mid, checkpoint["id"])
            store.set("continuity", {"chapter": 9})
            store.add_message(2.0, "2026-09-18", "user", "later")
            store.conn.close()
            state.write_text(json.dumps({"turn": 15, "text": "later"}), encoding="utf-8")

            validate_slot(root / "checkpoints" / checkpoint["id"])
            recovery = Path(restore_slot(root / "checkpoints" / checkpoint["id"], db, state))
            restored = Store(str(db))
            self.assertEqual(restored.get("continuity"), {"chapter": 1})
            self.assertIsNone(restored.message_by_id(mid + 1))
            self.assertEqual(restored.message_by_id(mid)["text"], "first")
            self.assertEqual(restored.reply_prompt_for(mid)["messages"], frozen)
            self.assertEqual(restored.swipes_for(mid)[0]["text"], "first")
            self.assertEqual(restored.vn_line_checkpoints([mid])[mid], checkpoint["id"])
            shown = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(shown["branch_from"], 12)
            self.assertEqual(shown["resume_view"]["current"]["text"], "first")
            self.assertTrue((recovery / "world.db").is_file())
            restored.conn.close()

    def test_slot_saves_stage_and_quick_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, state = root / "world.db", root / "state.json"
            store = Store(str(db))
            store.set("active_scene", "classroom")
            store.set("continuity", {"outfit": "uniform"})
            store.conn.close()
            frame = {"turn": 4, "turn_id": 3, "text": "hello", "face": "/asset/face/f.png",
                     "scene": {"url": "/asset/bg/classroom.png", "place": "classroom"}}
            slot = create_slot(db, root / "saves", {"current": frame, "pending": []}, latest_turn=4)
            set_quick_slot(root / "saves", slot["id"])
            self.assertEqual(quick_slot(root / "saves"), slot["id"])
            self.assertEqual(slot["place"], "classroom")
            store = Store(str(db))
            store.set("continuity", {"outfit": "other"})
            store.conn.close()
            restore_slot(root / "saves" / slot["id"], db, state)
            restored = Store(str(db))
            self.assertEqual(restored.get("continuity"), {"outfit": "uniform"})
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["resume_view"]["current"], frame)
            restored.conn.close()


if __name__ == "__main__":
    unittest.main()
