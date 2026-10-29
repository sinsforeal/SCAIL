"""Where her voice comes from: synthesis, an exact recording, or a near miss.

    python tools/vn_voice_test.py

The VN channel plays a recorded koikano clip instead of synthesising a line
when her line is one she said on tape. That used to be a boolean (exact on,
plus an optional fuzzy near miss); it is now one of three modes
(`channels/vn_voice.py`): `tts` never plays from tape, `exact` plays only a
line she said verbatim, `approximate` also plays a near miss. This checks the
matcher, the guards that keep a wrong clip from playing, and the migration of
the old boolean in the save and the config.

No model call, no save, no corpus: a temp index and temp clip files.
"""
import io
import json
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

from channels.vn_voice import VoiceIndex, VOICE_MODES, voice_mode  # noqa: E402
from channels.vn_bot import VnInterface  # noqa: E402

fails = []


def check(ok, what, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what + (("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(what)
    return ok


# The recorded lines, and the clips they stand for. `あああああ` appears twice
# with the pause in a different place: both are the same words, and both are
# the same distance from a query with no pause, so the margin rule refuses
# them together and plays either alone.
LINES = {
    "また明日ね": "MMK000001",
    "今日は本当に楽しかったよ": "MMK000003",
    "……っ": "MMK000004",
    "はい": "MMK000005",
    "今日は本当に楽しかったね": "MMK000006",
    "明日の3時に会いましょう": "MMK000007",
    "あああああ、あああああ": "MMK000008",
    "ああああああ、ああああ": "MMK000009",
}


def build(tmp, lines=None, name="voice_index.json"):
    lines = LINES if lines is None else lines
    clips = os.path.join(tmp, "clips")
    os.makedirs(clips, exist_ok=True)
    for clip in lines.values():
        open(os.path.join(clips, clip + ".ogg"), "wb").close()
    index = os.path.join(tmp, name)
    with io.open(index, "w", encoding="utf-8") as f:
        json.dump({"by_text": lines}, f, ensure_ascii=False)
    return VoiceIndex(index, clips)


class FakeStore(object):
    def __init__(self, d):
        self.d = dict(d)

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v


class FakeConfig(object):
    def __init__(self, raw):
        self.raw = raw


def mode_for(raw, store=None):
    c = VnInterface.__new__(VnInterface)
    c.config = FakeConfig(raw)
    c.store = FakeStore(store or {})
    return c._stored_voice_mode()


def run_matcher(tmp):
    idx = build(tmp)

    print("THE MODE, AND THE OLD BOOLEAN IT REPLACES")
    check(voice_mode(None, False) == "exact", "no mode and no boolean is exact")
    check(voice_mode(None, True) == "approximate", "the old boolean on is approximate")
    check(voice_mode("tts") == "tts", "an explicit mode is itself")
    try:
        voice_mode("bogus")
        check(False, "an unknown mode is refused")
    except ValueError:
        check(True, "an unknown mode is refused")

    print("\nTTS ONLY: NEVER FROM TAPE")
    check(idx.lookup("また明日ね", mode="tts") is None, "an exact recorded line is not played")
    check(idx.resolve("また明日ね", mode="tts") is None, "nor resolved to a file")
    check(idx.resolve("また明日ね", clip_id="MMK000001", mode="tts") is None,
          "nor is a clip id she named")
    check(idx.resolve("MMK000001", mode="tts") is None, "nor an id written as the line")

    print("\nEXACT: A LINE SHE SAID VERBATIM")
    check(idx.lookup("また明日ね", mode="exact") == "MMK000001", "the exact line plays")
    check(idx.lookup("今日は、本当に楽しかったよ", mode="exact") is None,
          "a pause added to the line is not the line")
    check(idx.lookup("はい", mode="exact") == "MMK000005", "a real short utterance plays")

    print("\nAPPROXIMATE: A PAUSE-ONLY NEAR MISS")
    check(idx.lookup("今日は、本当に楽しかったよ", mode="approximate") == "MMK000003",
          "the same words with a pause added play")
    check(idx.lookup("今日は本当に楽しかったわ", mode="approximate") is None,
          "a changed particle (ね/よ/わ) is a different sentence")
    check(idx.lookup("明日の4時に会いましょう", mode="approximate") is None,
          "a changed number is a different sentence")
    check(idx.lookup("ああああああああああ", mode="approximate") is None,
          "two candidates the same distance away refuse the match")

    lone = build(tmp, {"あああああ、あああああ": "MMK000008"}, name="one.json")
    check(lone.lookup("ああああああああああ", mode="approximate") == "MMK000008",
          "the same line with no rival plays")

    print("\nA TINY FRAGMENT IS NEVER A SENTENCE")
    check(idx.lookup("……っ", mode="exact") is None, "the fragment misses in exact")
    check(idx.lookup("……っ", mode="approximate") is None, "and in approximate")
    check(idx.resolve("……っ", mode="exact") is None, "and resolves to nothing")
    check(idx.lookup("っ", mode="approximate") is None, "a bare sokuon misses too")

    print("\nA CLIP ID IS A REQUEST ONLY WHEN THE LINE IS THE ID")
    check(idx.resolve("MMK000001", mode="exact") == idx.clip_path("MMK000001"),
          "an id written as the line plays")
    check(idx.resolve("MMK000001と言った", mode="exact") is None,
          "an id merely inside a sentence is not a request")
    check(idx.resolve("また明日ね", clip_id="MMK000001", mode="exact")
          == idx.clip_path("MMK000001"), "an id named outright wins over the text")

    print("\nTHE TWO RESOLVERS AGREE")
    for line in ("また明日ね", "今日は、本当に楽しかったよ", "……っ"):
        for mode in VOICE_MODES:
            path = idx.resolve(line, mode=mode)
            hit = idx.lookup(line, mode=mode)
            check(path == (idx.clip_path(hit) if hit else None),
                  f"{mode}: {line!r} resolves the same as it looks up")

    print("\nTHE MODE IN THE SAVE AND THE CONFIG")
    check(mode_for({"tts": {}}) == "exact", "no config key is exact")
    check(mode_for({"tts": {"voice_mode": "tts"}}) == "tts", "the config's mode is used")
    check(mode_for({"tts": {"clip_partial": True}}) == "approximate",
          "the old boolean on seeds approximate")
    check(mode_for({"tts": {"clip_partial": False}}) == "exact",
          "the old boolean off seeds exact")
    check(mode_for({"tts": {"voice_mode": "bogus"}}) == "exact",
          "an unknown config mode falls back to exact")
    check(mode_for({"tts": {}}, {"vn_voice_mode": "tts"}) == "tts",
          "the page's last choice wins over the config")
    check(mode_for({"tts": {}}, {"vn_clip_partial": True}) == "approximate",
          "a save written before the mode comes back as approximate")
    check(mode_for({"tts": {"voice_mode": "approximate"}},
                   {"vn_voice_mode": "bogus"}) == "approximate",
          "an unknown saved mode falls back to the config's")

    print("\nTHE CONTROL REFUSES AN UNKNOWN MODE")
    c = VnInterface.__new__(VnInterface)
    c.config = FakeConfig({"tts": {}})
    c.store = FakeStore({})
    c._lock = threading.Lock()
    c._state = None
    c._auto_voice = False
    c._quality_on = False
    c._voice_mode = "exact"
    c._voice_source = None
    c._voice_clip = None
    got = c.set_control({"voice_mode": "approximate"})
    check(got.get("voice_mode") == "approximate", "a known mode is taken")
    c.set_control({"voice_mode": "bogus"})
    check(c._voice_mode == "approximate", "an unknown mode leaves the mode alone")


def main():
    tmp = tempfile.mkdtemp(prefix="vn_voice_test_")
    try:
        run_matcher(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if fails:
        print(f"FAIL: {len(fails)} check(s): " + "; ".join(fails[:6]))
        return 1
    print("all checks passed: her voice comes from synthesis, an exact recording, or a pause-only near miss")
    return 0


if __name__ == "__main__":
    sys.exit(main())