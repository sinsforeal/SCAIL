"""Check approved director music and vocal cues reach the scene pass."""
import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scail import App  # noqa: E402
from sim.scene import SceneDirector  # noqa: E402
from sim.stage_manager import StageManager  # noqa: E402


class Store:
    def __init__(self):
        self.values = {}
    def register_scene(self, *args, **kwargs):
        pass
    def set_active_scene(self, scene_id):
        pass


def main():
    config = SimpleNamespace(scene_director=SimpleNamespace(enabled=True, use_model=False),
                             vn=SimpleNamespace(), character=SimpleNamespace(name_ja="character"))
    scene = SceneDirector(config)
    manager = StageManager.__new__(StageManager)
    manager.scene = scene
    proposal = manager.resolve({"text": "a sad opening", "place": "her_room",
                                "bgm": "BGM13", "interjection": "(sighs)"})
    assert proposal["bgm"] == "BGM13" and proposal["interjection"] == "(sighs)"
    assert manager.resolve({"interjection": "(robot-noise)"})["interjection"] == ""
    app = App.__new__(App)
    app.stage_manager = SimpleNamespace(enabled=True)
    app.clock = SimpleNamespace(now_ts=lambda: 1700000000, now=lambda: None)
    app.store = Store()
    app.scene = scene
    app.schedule = {}
    app.director = SimpleNamespace(apply_directive=lambda *args: {"location": "her_room"})
    app.tg = SimpleNamespace(set_scene=lambda bg, directed=False: assert_directed(bg, directed),
                             set_costume=lambda outfit, redraw=True: assert_costume_redraw(redraw))
    app.force_scene_turn = lambda *args: None
    app._scene_urge = lambda *args: ""
    app.apply_director_scene(proposal)
    assert scene.request["bgm"] == "BGM13"
    assert scene.request["interjection"] == "(sighs)"
    print("stage manager cues: pass")


def assert_directed(bg, directed):
    assert bg == "BG18a01" and directed is True


def assert_costume_redraw(redraw):
    assert redraw is False


if __name__ == "__main__":
    main()
