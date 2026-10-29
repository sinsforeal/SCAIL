"""The minimal loop: his line in, her reply out, on screen with a face and a voice.

One turn: send the running message list to the model with her bible and style
as the system prompt, take her reply, pull the mood tag off it (or infer one),
render the audio, and write the whole turn to `state.json` for the view.

No memory, no cast, no world, no peers, no sensors, no phone: this is one
character and one conversation.
"""

import datetime
import json
import os
import sys

try:
    from . import common, expression, llm, voice
except ImportError:
    import common
    import expression
    import llm
    import voice

HISTORY_KEEP = 40


def sprite_url(tag):
    return f"/asset/sprite/{tag.lower()}.png"


def face_url(face):
    return f"/asset/face/{face.lower()}f.png"


def audio_url(path):
    return "/audio/" + os.path.basename(path)


def clip_url(clip_id):
    return f"/asset/clip/{str(clip_id).upper()}.ogg"


class App:
    def __init__(self, cfg=None):
        self.cfg = cfg or common.load_config()
        self.character = self.cfg["character"]
        self.llm = llm.LLM(self.cfg)
        self.ex = expression.Expression(self.cfg)
        self.voice = voice.Voice(self.cfg)
        self.system = common.system_prompt(self.cfg, expression.instruction())
        self.messages = []
        self.turn_count = 0
        self.data_dir = common.resolve(self.cfg["paths"]["data_dir"])
        self.state_path = common.resolve(self.cfg["paths"]["state_file"])
        os.makedirs(self.data_dir, exist_ok=True)
        self._load()

    # ---- persistence -------------------------------------------------

    def _history_path(self):
        return os.path.join(self.data_dir, "conversation.json")

    def _load(self):
        path = self._history_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.messages = list(data.get("messages") or [])
            self.turn_count = int(data.get("turns") or 0)
        except Exception:
            self.messages, self.turn_count = [], 0

    def _save(self):
        self._write_json(self._history_path(),
                         {"turns": self.turn_count, "messages": self.messages[-HISTORY_KEEP:]})

    def _write_json(self, path, obj):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    # ---- one turn ----------------------------------------------------

    def turn(self, user_text, clip=None):
        user_text = (user_text or "").strip()
        if not user_text:
            raise ValueError("empty line")
        self.messages.append({"role": "user", "content": user_text})
        reply = self.llm.chat(self.messages, system=self.system)
        text, mood = expression.parse_mood(reply)
        if not text:
            text = reply.strip()
        assets = self.ex.resolve(mood)
        audio = None
        audio_error = None
        try:
            audio = self.voice.speak(text, clip=clip)
        except Exception as e:
            audio_error = f"{type(e).__name__}: {e}"
        self.messages.append({"role": "assistant", "content": reply})
        self.turn_count += 1
        self._save()
        state = {
            "character": self.character["name"],
            "full": self.character["full"],
            "updated": datetime.datetime.now().isoformat(timespec="seconds"),
            "turn": self.turn_count,
            "speaker": self.character["name"],
            "text": text,
            "mood": mood,
            "c4": assets["c4"],
            "sprite": {
                "tag": assets["sprite"],
                "base": sprite_url(assets["base_tag"]),
                "diff": sprite_url(assets["diff_tag"]) if assets["diff_tag"] else None,
                "geometry": assets["geometry"],
            },
            "face": face_url(assets["face"]),
            "audio": audio_url(audio) if audio else None,
            "audio_error": audio_error,
            "user_text": user_text,
        }
        self._write_json(self.state_path, state)
        return state

    def current_state(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None


def main(argv):
    cfg = common.load_config()
    app = App(cfg)
    lines = [a for a in argv if not a.startswith("--")]
    if lines:
        state = app.turn(" ".join(lines))
        print(f"[{state['speaker']}] ({state['mood']}) {state['text']}")
        print(f"  audio: {state['audio'] or state['audio_error']}")
        return 0
    print(f"{app.character['full']} — type a line, blank to quit.")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            break
        try:
            state = app.turn(line)
        except Exception as e:
            print(f"! {type(e).__name__}: {e}")
            continue
        print(f"[{state['speaker']}] ({state['mood']}) {state['text']}")
        if state["audio_error"]:
            print(f"  voice failed: {state['audio_error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
