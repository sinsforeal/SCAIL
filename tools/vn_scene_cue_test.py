"""Check that verified weather and sound cues reach the VN scene frame."""
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from channels.vn_bot import VnInterface  # noqa: E402
from sim.scene import DEFAULT_BGM_DIR, DEFAULT_SE_DIR  # noqa: E402


class Store:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


def main():
    channel = VnInterface.__new__(VnInterface)
    channel.store = Store()
    channel._lock = threading.Lock()
    channel._prepared_emotions = {}
    channel._used_vocal_cue = ""
    channel._bg_override = None
    channel._bgm_override = None
    channel.bgm_dir = DEFAULT_BGM_DIR
    channel.se_dir = DEFAULT_SE_DIR
    channel.frame_dir = os.path.join(os.path.dirname(os.path.dirname(DEFAULT_SE_DIR)),
                                     "png", "scene", "frame")
    channel._bgm_loop_points = lambda name: None
    channel._standby_scene = lambda: None
    scene = {"place": "school_gate", "bg": "BG01a01", "bgm": "BGM03",
             "snow": True, "se": "SE074", "cue_id": "event-1",
             "interjection": "(sighs)", "vocal_cue_id": "beat-1"}
    channel.scene_provider = lambda: scene
    state = channel._scene_state()
    assert state["snow"] and len(state["snow_urls"]) == 4
    assert state["se_url"] == "/asset/se/SE074.ogg"
    assert state["cue_id"] == "event-1"
    assert channel.take_vocal_cue() == "(sighs)"
    assert channel.take_vocal_cue() == ""
    channel.prepare_emotion("test line", "sadness")
    channel.emotion_provider = lambda text: "joy"
    assert channel._signal_for("test line")["label"] == "sadness"
    assert channel._signal_for("test line")["label"] == "joy"
    print("vn scene cues: pass")


if __name__ == "__main__":
    main()
