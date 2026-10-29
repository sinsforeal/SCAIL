"""Director face choice is a native pair on opening, then line emotion resumes."""
import json
import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from channels.vn_bot import VnInterface  # noqa: E402
from sim.scene import SceneDirector  # noqa: E402
from sim.stage_manager import StageManager  # noqa: E402


class Store:
    def __init__(self):
        self.values = {"vn_costume_override": "CD07"}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class Answers:
    def __init__(self):
        self.index = "16"
        self.confidence = 0.9
        self.questions = None

    def ready(self, name):
        return True

    def use(self, name):
        return {"threshold": 0.3}

    def ask(self, name, state, questions):
        self.questions = questions
        return {"place": ("her_room", 0.9), "camera": ("static", 0.9),
                "transition": ("cut", 0.9), "mood": ("warm", 0.9),
                "bgm": ("none", 0.9), "interjection": ("none", 0.9),
                "face_index": (self.index, self.confidence)}

    def choice(self, answers, key):
        return answers.get(key, (None, 0.0))


def main():
    with open(os.path.join(ROOT, "config_momoka.json"), encoding="utf-8") as f:
        vn = json.load(f)["vn"]
    cfg = SimpleNamespace(raw={"vn": vn},
                          scene_director=SimpleNamespace(enabled=True, use_model=False),
                          vn=SimpleNamespace(), character=SimpleNamespace(name_ja="百花"))
    store = Store()
    answers = Answers()
    director = SceneDirector(cfg, store=store, typesafe=answers)
    assert len(director.face_options()) == 16
    assert "smile" in director.face_options()["16"]
    scene = {"location": "her room", "activity": "talking"}
    first = director.run(scene, mood="warm")
    assert "face_index" in answers.questions
    assert first["face_index"] == "16" and first["face_cue_id"]

    channel = VnInterface.__new__(VnInterface)
    channel.store = store
    channel._mood_override = ""
    channel._used_face_cue = ""
    channel.scene_provider = director.current
    opening = channel._opening_face_signal({"expression": "neutral"})
    assert director.expressions.resolve(opening, costume="CD07")["tag"] == "CD07A016L"
    assert channel._opening_face_signal({"expression": "surprise"}) == {"expression": "surprise"}
    assert director.expressions.resolve({"expression": "surprise"}, costume="CD07")["costume"] == "CD07"

    answers.index = "8"
    again = director.run(scene, mood="warm")
    assert again["face_index"] == "16" and again["face_cue_id"] == first["face_cue_id"]
    beat = director.run({**scene, "emotional_beat": "a surprise"}, mood="warm")
    assert beat["face_index"] == "8" and beat["face_cue_id"] != first["face_cue_id"]
    assert channel._opening_face_signal({"expression": "neutral"})["face_index"] == "8"

    director.run({**scene, "emotional_beat": "a second surprise"}, mood="warm")
    channel._mood_override = "romantic"
    held = channel._opening_face_signal({"expression": "neutral"})
    assert "face_index" not in held
    channel._mood_override = ""
    assert "face_index" not in channel._opening_face_signal({"expression": "neutral"})

    answers.index = "16"
    answers.confidence = 0.49
    low = director._ask_typesafe(scene, "warm", "her room")
    assert low["face_index"] == ""

    manager = StageManager.__new__(StageManager)
    manager.scene = director
    proposal = manager.resolve({"outfit": "CD07", "face_index": "16"})
    assert proposal["face_index"] == "16"
    assert manager.resolve({"outfit": "CD07", "face_index": "99"})["face_index"] == ""
    director.request = {"bg": director.places["her_room"], "place": "her_room",
                        "outfit": "CD05", "face_index": "16"}
    directed = director.run(scene, mood="warm")
    assert directed["face_index"] == "16" and directed["face_cue_id"]
    print("director expression: 16 catalog entries, opening cue, held scene, new beat, and validation pass")


if __name__ == "__main__":
    main()
