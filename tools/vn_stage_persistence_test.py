"""Check that manual VN stage choices survive a fresh channel object.

    python tools/vn_stage_persistence_test.py
"""
import io
import os
import shutil
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from channels.vn_bot import VnInterface  # noqa: E402


class Store:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class Expression:
    default = "neutral"

    @staticmethod
    def costume_ids():
        return ["CD02", "CD07"]


def channel(store, bg_dir, bgm_dir):
    c = VnInterface.__new__(VnInterface)
    c.store = store
    c.bg_dir = bg_dir
    c.bgm_dir = bgm_dir
    c.expr = Expression()
    c._lock = threading.Lock()
    c._state = {"mood": "neutral", "scene": {}}
    c._scene_state = lambda: {"bg": "BG01A01", "bgm": "BGM03"}
    c._set_face = lambda signal: None
    c._write_state = lambda: None
    c._notify = lambda state: None
    c._bg_override = None
    c._bgm_override = None
    c._mood_override = ""
    c._costume_override = None
    c._scene_request = None
    c._scene_notice_request = None
    c._director_request = None
    return c


def main():
    tmp = tempfile.mkdtemp(prefix="vn_stage_persistence_")
    try:
        bg_dir = os.path.join(tmp, "bg")
        bgm_dir = os.path.join(tmp, "bgm")
        os.makedirs(bg_dir)
        os.makedirs(bgm_dir)
        open(os.path.join(bg_dir, "bg01a01.png"), "wb").close()
        open(os.path.join(bgm_dir, "BGM02.ogg"), "wb").close()
        store = Store()
        first = channel(store, bg_dir, bgm_dir)
        assert first.set_scene("bg01a01") == "BG01A01"
        assert first.set_track("bgm02") == "BGM02"
        assert first.set_costume("cd07") == "CD07"
        assert store.values == {"vn_background_override": "BG01A01",
                                "vn_track_override": "BGM02",
                                "vn_costume_override": "CD07"}

        restarted = channel(store, bg_dir, bgm_dir)
        restarted._bg_override = restarted._stored_background_override()
        restarted._costume_override = restarted._stored_costume_override()
        restarted._bgm_override = restarted._stored_track_override()
        assert restarted._bg_override == "BG01A01"
        assert restarted._costume_override == "CD07"
        assert restarted._bgm_override == "BGM02"
        assert restarted._scene_pick(restarted._bg_override)["bg"] == "BG01A01"

        restarted.queue_director({"bg": "BG01A01"})
        assert restarted._bg_override is None
        assert restarted._bgm_override is None
        assert store.get("vn_background_override") is None
        assert store.get("vn_track_override") is None
        assert store.get("vn_costume_override") == "CD07"
        # An approved scene draws at once without creating a second manual
        # request that would overwrite its chosen music on the next poll.
        restarted.set_scene("bg01a01", directed=True)
        assert restarted._scene_request is None
        assert restarted._scene_notice_request is None
        assert store.get("vn_background_override") is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("all checks passed: manual stage choices resume, and a director scene clears stale background and music")
    return 0


if __name__ == "__main__":
    sys.exit(main())
