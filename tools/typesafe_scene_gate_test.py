"""Check the scene classifier's action-specific confidence gates offline."""
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim.scene import (CAMERAS, CAMERA_NOTES, INTERJECTIONS,
                       INTERJECTION_NOTES, MOODS, MOOD_NOTES, SceneDirector,
                       TRANSITIONS, TRANSITION_NOTES)
from typesafe import TypeSafe


class Answers:
    def __init__(self, music_confidence, vocal_confidence):
        self.music_confidence = music_confidence
        self.vocal_confidence = vocal_confidence
        self.questions = None

    def ready(self, name):
        return name == "scene_director"

    def use(self, name):
        return {"threshold": 0.3, "music_threshold": 0.5,
                "vocal_threshold": 0.6}

    def ask(self, name, state, questions):
        self.questions = questions
        assert name == "scene_director"
        assert set(state) == {"scene", "feeling"}
        return {"place": ("his_room", 0.8),
                "camera": ("static", 0.8),
                "transition": ("cut", 0.8),
                "mood": ("warm", 0.8),
                "bgm": ("BGM16", self.music_confidence),
                "interjection": ("(sighs)", self.vocal_confidence)}

    def choice(self, answers, qid):
        return answers[qid]


def main():
    assert set(CAMERA_NOTES) == set(CAMERAS)
    assert set(TRANSITION_NOTES) == set(TRANSITIONS)
    assert set(MOOD_NOTES) == set(MOODS)
    assert set(INTERJECTION_NOTES) == set(INTERJECTIONS)
    raw = {"typesafe": {"uses": {"scene_director": {
        "enabled": True, "threshold": 0.3,
        "music_threshold": 0.5, "vocal_threshold": 0.6}}}}
    cfg = SimpleNamespace(raw=raw, typesafe=SimpleNamespace(enabled=True))
    assert TypeSafe(cfg).use("scene_director")["vocal_threshold"] == 0.6

    cfg = SimpleNamespace(scene_director=SimpleNamespace(enabled=True, use_model=False),
                          vn=SimpleNamespace(), character=SimpleNamespace(name_ja="百花"))
    low = Answers(0.49, 0.59)
    director = SceneDirector(cfg, typesafe=low)
    result = director._ask_typesafe({"location": "his room"}, "warm", "his room")
    assert result["place"] == "his_room"
    assert result["bgm"] == "" and result["interjection"] == ""
    assert "long breath" in low.questions["interjection"]["criteria"]["(sighs)"]
    assert "let code" in low.questions["bgm"]["criteria"]["none"]
    high = Answers(0.5, 0.6)
    director.typesafe = high
    result = director._ask_typesafe({"location": "his room"}, "warm", "his room")
    assert result["bgm"] == "BGM16" and result["interjection"] == "(sighs)"
    print("typesafe scene gates: pass")


if __name__ == "__main__":
    main()
