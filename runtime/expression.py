"""Map a mood to Momoka's koikano assets.

The sprite is a base PNG plus a diff PNG composited at an (x, y) offset; the
face is the message-window crop. Both are chosen from the C4 label pass
(`expression_labels.json`) and verified on disk, so an id named here exists.

Her recorded repertoire is smile, worried, sad, talk, neutral, surprise,
excited, laugh. `angry` and `shy` never appear on her lines; they are accepted
as input and mapped to the nearest face she actually has.
"""

import json
import os

try:
    from . import common
except ImportError:
    import common

# mood -> (sprite tag, face id). Every id below was checked on disk.
MOOD_MAP = {
    "happy":     {"sprite": "CD02A002L", "face": "CD02A002", "c4": "smile"},
    "smile":     {"sprite": "CD02A002L", "face": "CD02A002", "c4": "smile"},
    "laugh":     {"sprite": "CD02A009L", "face": "CD02A009", "c4": "laugh"},
    "surprised": {"sprite": "CD02A008L", "face": "CD02A008", "c4": "surprise"},
    "sad":       {"sprite": "CD02A014L", "face": "CD02A014", "c4": "sad"},
    "worried":   {"sprite": "CD02A006L", "face": "CD02A006", "c4": "worried"},
    "angry":     {"sprite": "CD02A014L", "face": "CD02A014", "c4": "sad"},
    "shy":       {"sprite": "CD02A002L", "face": "CD02A002", "c4": "smile"},
    "neutral":   {"sprite": "CD02A010L", "face": "CD02A010", "c4": "neutral"},
    "excited":   {"sprite": "CD02A015L", "face": "CD02A015", "c4": "excited"},
    "talk":      {"sprite": "CD02A003L", "face": "CD02A003", "c4": "talk"},
}
DEFAULT_MOOD = "neutral"
MOODS = list(MOOD_MAP)

# A model that misses the tag is not a failure; her words carry the mood too.
_KEYWORDS = [
    (("嬉しい", "うれし", "たのし", "楽しい", "わーい", "やった", "えへへ"), "happy"),
    (("笑", "わら", "ふふ", "あはは", "うふふ"), "laugh"),
    (("びっくり", "おどろ", "驚", "えっ", "まさか", "すごい"), "surprised"),
    (("かなし", "悲し", "さみし", "寂し", "しょっく", "ざんねん", "残念", "泣"), "sad"),
    (("しんぱい", "心配", "だいじょうぶ", "大丈夫", "どうした", "こわい", "怖い"), "worried"),
    (("むかつ", "腹立", "いやだ", "やだ", "怒"), "angry"),
    (("はずかし", "恥ずか", "てれ", "照れ"), "shy"),
    (("ん。", "うん", "はい"), "neutral"),
]


class Expression:
    def __init__(self, cfg=None):
        self.cfg = cfg or common.load_config()
        a = self.cfg["assets"]
        self.char_dir = common.resolve(a["character_dir"])
        self.inventory = self._load_json(a["inventory"])["sprite_tags"]
        self.labels = self._load_json(a["labels"])["labels"]
        self._sprite_dir = os.path.join(self.char_dir, a["sprite_dir"])
        self._face_dir = os.path.join(self.char_dir, a["face_dir"])

    @staticmethod
    def _load_json(path):
        with open(common.resolve(path), encoding="utf-8") as f:
            return json.load(f)

    def _sprite_file(self, tag):
        return os.path.join(self._sprite_dir, tag.lower() + ".png")

    def _face_file(self, face):
        return os.path.join(self._face_dir, face.lower() + "f.png")

    def resolve(self, mood):
        """The assets for a mood, verified on disk. Falls back to neutral."""
        mood = (mood or "").strip().lower()
        if mood not in MOOD_MAP:
            mood = DEFAULT_MOOD
        entry = MOOD_MAP[mood]
        tag = entry["sprite"]
        spec = self.inventory[tag]
        base_tag, diff_tag = spec["base"], spec.get("diff")
        base = self._sprite_file(base_tag)
        diff = self._sprite_file(diff_tag) if diff_tag else None
        face = self._face_file(entry["face"])
        problems = [p for p, ok in (("base", os.path.exists(base)),
                                    ("diff", diff is None or os.path.exists(diff)),
                                    ("face", os.path.exists(face))) if not ok]
        if problems:
            raise FileNotFoundError(f"assets for mood {mood} missing: {', '.join(problems)}")
        return {
            "mood": mood,
            "c4": entry["c4"],
            "sprite": tag,
            "base": base,
            "base_tag": base_tag,
            "diff": diff,
            "diff_tag": diff_tag,
            "geometry": spec.get("geometry"),
            "face": entry["face"],
            "face_file": face,
        }

    def verify(self):
        """Every mapped mood, checked on disk. Used by the selftest."""
        report = []
        for mood in MOODS:
            try:
                self.resolve(mood)
                report.append((mood, True, MOOD_MAP[mood]["sprite"]))
            except Exception as e:
                report.append((mood, False, str(e)))
        return report


def parse_mood(text):
    """Split a trailing `[mood: x]` tag off her reply; infer if absent."""
    mood = None
    cleaned = text
    for mark in ("[mood:", "[mood：", "【mood:"):
        idx = cleaned.rfind(mark)
        if idx == -1:
            continue
        end = cleaned.find("]", idx)
        if end == -1:
            continue
        value = cleaned[idx + len(mark):end].strip().lower().rstrip("]").strip()
        if value:
            mood = value
            cleaned = (cleaned[:idx] + cleaned[end + 1:]).strip()
        break
    if mood not in MOOD_MAP:
        mood = _infer(cleaned)
    return cleaned.strip(), mood


def _infer(text):
    for words, mood in _KEYWORDS:
        if any(w in text for w in words):
            return mood
    return DEFAULT_MOOD


def instruction():
    """Appended to her system prompt so each reply names its own mood."""
    return (
        "（舞台監督からのメモ。返事の本文だけを書く。最後に、今の気持ちを角括弧で"
        "ひとつ付ける。形は [mood: X]。X は次のどれかひとつ: happy, smile, laugh, "
        "surprised, sad, worried, angry, shy, neutral。本文に mood の話は書かない。）"
    )


if __name__ == "__main__":
    import sys
    ex = Expression()
    ok = True
    for mood, good, note in ex.verify():
        print(f"{'OK ' if good else 'MISS'} {mood:10s} {note}")
        ok = ok and good
    if len(sys.argv) > 1:
        clean, mood = parse_mood(sys.argv[1])
        print("parsed:", repr(clean), "->", mood)
    raise SystemExit(0 if ok else 1)
