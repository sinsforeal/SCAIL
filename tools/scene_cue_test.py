"""Offline checks for scene cue timing and verified corpus IDs."""
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim.scene import SceneDirector


def main():
    cfg = SimpleNamespace(
        scene_director=SimpleNamespace(enabled=True, use_model=False),
        vn=SimpleNamespace(), character=SimpleNamespace(name_ja="百花"))
    director = SceneDirector(cfg)
    assert {"SE074", "SE119", "SE123_b"} <= director.sounds
    assert "calm warmth" in director.bgm_options()["BGM16"]
    base = {"location": "outside the school gate", "activity": "waiting",
            "setting": "indoors", "weather": "snowing"}
    first = director.run(base, "neutral")
    assert first["snow"] and first["se"] == ""
    assert director.run(base, "warm")["bgm"] == first["bgm"]
    pat = dict(base, events=[{"id": "e1", "text": "pats her head"}],
               emotional_beat="she confesses")
    changed = director.run(pat, "warm")
    assert changed["se"] == "SE074" and changed["cue_id"]
    assert changed["bgm"] == director.bgm_for("warm")
    repeated = director.run(pat, "tense")
    assert repeated["se"] == "SE074" and repeated["cue_id"] == changed["cue_id"]
    assert repeated["bgm"] == changed["bgm"]
    assert director.current()["cue_id"] == changed["cue_id"]
    assert director.run(base, "warm")["se"] == ""
    again = director.run(pat, "warm")
    assert again["se"] == "SE074" and again["cue_id"] != changed["cue_id"]
    assert director.run(dict(base, weather="not snowing"), "warm")["snow"] is False
    assert director.run(dict(base, location="her room"), "warm")["snow"] is False
    for indoor in ("indoors_ac", "bath", "transit"):
        assert director.run(dict(base, location="her room", setting=indoor), "warm")["snow"] is False
    director.weather = SimpleNamespace(describe=lambda now: "snow, -2C")
    director.clock = SimpleNamespace(now=lambda: None, now_ts=lambda: 1)
    assert director.run(dict(base, weather=""), "warm")["snow"] is True
    director.weather = None
    director.last = None
    held = director.run({"location": "his room", "activity": "talking"}, "neutral")
    turning = director.run({"location": "his room", "activity": "confession"}, "sad")
    assert turning["bgm"] == director.bgm_for("sad") != held["bgm"]
    assert director.run({"location": "his room", "activity": "confession"}, "warm")["bgm"] == turning["bgm"]
    assert "emotional_beat: confession" in director._cue_brief(
        {"emotional_beat": "confession", "events": [{"text": "a kiss"}], "weather": "snowing"}, "room")
    director.last = None
    director.request = dict(base, bg=director.default_bg, interjection="(sighs)")
    vocal = director.run(base, "neutral")
    assert vocal["interjection"] == "(sighs)" and vocal["vocal_cue_id"]
    director.request = dict(base, bg=director.default_bg, interjection="(sighs)")
    same = director.run(base, "neutral")
    assert same["vocal_cue_id"] == vocal["vocal_cue_id"]
    print("scene cues: pass")


if __name__ == "__main__":
    main()
