# -*- coding: utf-8 -*-
"""Her feeling, as one of Momoka's koikano expressions.

The channel gets a felt state from the runtime (the reactions band that
`sim/reactions.py` produces, or the words she just said) and this turns it
into a concrete asset pair: a sprite tag (base PNG plus diff PNG composited at
a region) and a face id, both from the C4 label pass
(`koikano_work/inventory/expression_labels.json` and
`expression_inventory.json`). It reads the same tables the renderer does and
verifies every file on disk before it will emit an id, so a tag it names
exists.

The C4 vocabulary is the label pass's own; her recorded faces cover smile,
laugh, surprise, talk, neutral, sad, worried and excited. A feeling outside
that set (angry, nervous, flustered) is drawn as the nearest face she actually
has rather than invented.
"""

import json
import os

try:
    # the same five bands the reaction face is cut from, so the VN face and
    # the app's reaction picture agree about what her mood is doing
    from sim.reactions import BANDS
except Exception:  # imported without the sim package (a standalone view)
    BANDS = (-0.45, -0.15, 0.15, 0.45)

try:
    # the 28 GoEmotions labels -> the C4 faces she has (`sim/emotion.py`). A
    # feeling outside the eight faces is drawn as the nearest one rather than
    # invented, and this is the table that decides which.
    from sim.emotion import GOEMOTION_EXPRESSION
except Exception:  # imported without the sim package (a standalone view)
    GOEMOTION_EXPRESSION = {}

# A feeling may also carry one of the game's overlay pieces -- the heart, the
# question mark, the stars, the sweat drop -- drawn over the sprite. Keyed by
# the GoEmotions label, because that is the finest read the channel has; a
# label with no overlay is drawn plain. The names are the files in
# `png/scene/emotion`; the resolver checks each one is on disk before it emits
# it.
EMOTION_OVERLAY = {
    # warm: a heart (the game's ハート01)
    "love": "heart01",
    "desire": "heart01",
    "caring": "heart01",
    "gratitude": "heart01",
    # bright: a star. star01..03 are the small white sparkles (each with an
    # additive second frame, `star01a` and its like); star04 is the solid
    # yellow star (the game's キラン, a glint) and star05 the four-point
    # sparkle (キラキラ, sparkling).
    "joy": "star01",
    "optimism": "star01",
    "relief": "star01",
    "approval": "star01",
    "amusement": "star03",
    "excitement": "star04",
    "admiration": "star05",
    # something has her attention, or a question. attention01 is the red
    # exclamation -- the game's びっくり, the surprise mark; attention02 is a
    # crown, a win, and belongs to a proud moment, not to surprise.
    "realization": "attention01",
    "surprise": "attention01",
    "pride": "attention02",
    "curiosity": "question01",
    "confusion": "question01",
    # a sweat drop: the uncomfortable and the sharp (the game's 汗). The face
    # carries the rest (disapproval, disgust, grief, remorse, sadness and
    # neutral are drawn plain), so a mark never overstates a quiet line.
    "disappointment": "drop02",
    "nervousness": "drop02",
    "embarrassment": "drop02",
    "anger": "drop02",
    "annoyance": "drop02",
    "fear": "drop02",
}

# feeling -> C4 expression. The keys are the reaction buckets
# (`sim/reactions.py:bucket_for`) plus the C4 vocabulary itself, so both a
# bucket and a raw expression are accepted.
BUCKET_EXPRESSION = {
    "happy": "smile",
    "smile": "smile",
    "laugh": "laugh",
    "surprised": "surprise",
    "surprise": "surprise",
    "excited": "excited",
    "talk": "talk",
    "neutral": "neutral",
    "sad": "sad",
    "cry": "sad",
    "worried": "worried",
    "nervous": "worried",
    "anxious": "worried",
    "scared": "worried",
    "serious": "worried",
    # no glaring face is recorded for her; the downcast one is the nearest
    "angry": "sad",
    "tired": "neutral",
    "sleepy": "neutral",
    # a bashful look is the smile face she has
    "flustered": "smile",
    "shy": "smile",
    "blush": "smile",
    "embarrassed": "smile",
    "other": "neutral",
}

DEFAULT_EXPRESSION = "neutral"
# Costume 02 -- the school uniform -- is the one she is drawn in unless the
# stage manager set another. The costume is the corpus's `set` with the
# character prefix (`CD01`..`CD07`); see `_build`.
DEFAULT_COSTUME = "CD02"

# The nearest expression a costume can actually show, when the feeling's own is
# not labeled in that costume. The original usage-scoped label table left CD07
# with only smile, but the reviewed additions restore its full authored set.
# The fallback must stay INSIDE the costume, or
# the face is drawn from another costume's sprite and the outfit the scene set
# disappears. Ordered nearest first.
EXPRESSION_FALLBACK = {
    "smile": ("neutral",),
    "laugh": ("smile", "excited", "neutral"),
    "surprise": ("excited", "talk", "neutral"),
    "excited": ("surprise", "laugh", "smile"),
    "talk": ("neutral", "smile"),
    "neutral": ("smile",),
    "sad": ("worried", "neutral", "smile"),
    "worried": ("sad", "neutral", "smile"),
}

# Costume 02 is the one she is drawn in for this channel. A preferred id is
# tried first, then any valid face of that expression, so a preferred id that
# ever moves off disk is skipped rather than crashing the view.
PREFERRED = {
    "smile": ("CD02A002", "CD02A001"),
    "laugh": ("CD02A009",),
    "surprise": ("CD02A008",),
    "excited": ("CD02A015",),
    "talk": ("CD02A003",),
    "neutral": ("CD02A010",),
    "sad": ("CD02A014", "CD02A013", "CD02A012", "CD02A005"),
    "worried": ("CD02A006",),
}

# An expression can have several labeled faces in one costume. This table picks
# the pose that fits the expression. Face indexes break a same-pose tie, then
# the lowest remaining index keeps the result stable. The label pass uses these
# nine pose names; a pose a costume does not have is simply skipped.
PREFERRED_POSE = {
    "smile": ("hands_clasped", "hand_at_collar", "none"),
    "laugh": ("hands_clasped", "fists_up", "none"),
    "surprise": ("hand_at_face", "finger_at_mouth", "finger_at_lips", "hands_clasped", "none"),
    "excited": ("fists_up", "hands_clasped", "none"),
    "talk": ("hand_at_collar", "finger_at_chin", "hands_clasped", "none"),
    "neutral": ("none", "hands_clasped"),
    "sad": ("hand_at_face", "none", "hands_clasped"),
    "worried": ("hand_at_forehead", "finger_at_mouth", "hand_at_face", "hands_clasped", "none"),
}

# A model that never names a feeling still wrote one into the words.
_KEYWORDS = [
    (("嬉しい", "うれし", "たのし", "楽しい", "わーい", "やった", "えへへ", "よかった"), "happy"),
    (("笑", "わら", "ふふ", "あはは", "うふふ"), "laugh"),
    (("びっくり", "おどろ", "驚", "えっ", "まさか", "すごい"), "surprised"),
    (("かなし", "悲し", "さみし", "寂し", "ざんねん", "残念", "泣"), "sad"),
    (("しんぱい", "心配", "どうした", "こわい", "怖い", "不安"), "worried"),
    (("むかつ", "腹立", "いやだ", "やだ", "怒"), "angry"),
    (("はずかし", "恥ずか", "てれ", "照れ"), "shy"),
    (("つかれ", "疲れ", "ねむ", "眠"), "tired"),
]


class VnExpression:
    """The verified expression table, and the feeling-to-face lookup."""

    def __init__(self, vn_cfg, root=None):
        c = vn_cfg or {}
        self.root = root or os.getcwd()
        self.character_dir = self._resolve(c.get("character_dir"))
        self.inventory_path = self._resolve(c.get("inventory"))
        self.labels_path = self._resolve(c.get("labels"))
        self.reviewed_labels_path = self._resolve(c.get("reviewed_labels"))
        self.sprite_dir = os.path.join(self.character_dir, c.get("sprite_dir") or "png_sprites")
        self.face_dir = os.path.join(self.character_dir, c.get("face_dir") or "png_faces")
        # the overlay art the feeling may carry, read in place from the game
        self.emotion_dir = self._resolve(c.get("emotion_dir"))
        self.default = str(c.get("default_expression") or DEFAULT_EXPRESSION).lower()
        self.default_costume = str(c.get("default_costume") or DEFAULT_COSTUME).strip()
        self.sprite_tags = {}
        self.labels = {}
        self.faces = {}
        self.faces_by_costume = {}
        self.variants_by_costume = {}
        self.costumes = []
        self.overlays = {}
        self._load()
        self._build()
        self._scan_overlays()

    # ---------------- loading ----------------

    def _resolve(self, path):
        if not path:
            return path
        return path if os.path.isabs(path) else os.path.join(self.root, path)

    def _load(self):
        with open(self.inventory_path, encoding="utf-8") as f:
            self.sprite_tags = json.load(f).get("sprite_tags", {})
        with open(self.labels_path, encoding="utf-8") as f:
            self.labels = json.load(f).get("labels", {})
        reviewed_ids = set()
        if self.reviewed_labels_path:
            with open(self.reviewed_labels_path, encoding="utf-8") as f:
                reviewed = json.load(f).get("labels", {})
            if not isinstance(reviewed, dict):
                raise ValueError("reviewed expression labels must be a map")
            for face_id, row in reviewed.items():
                if face_id in self.labels:
                    raise ValueError(f"reviewed expression already has a source label: {face_id}")
                if not (face_id.startswith("CD") and len(face_id) == 8 and
                        face_id[2:4].isdigit() and face_id[4] == "A" and
                        face_id[5:].isdigit()):
                    raise ValueError(f"reviewed expression has a mismatched id: {face_id}")
                if not isinstance(row, dict) or not row.get("expression") or not row.get("pose"):
                    raise ValueError(f"reviewed expression lacks a label or pose: {face_id}")
                if not (self.sprite_tags.get(face_id + "L") and self._face_file(face_id)):
                    raise FileNotFoundError(f"reviewed expression lacks paired art: {face_id}")
                self.labels[face_id] = {"char": "CD", "set": face_id[2:4],
                                        "kind": "face", **row}
                reviewed_ids.add(face_id)
        # The original label pass covered story-used assets only. One face
        # index names an F portrait and an L/M standing sprite row; carry its
        # reviewed visual label to both sizes. Keep the source JSON untouched.
        for face_id, row in list(self.labels.items()):
            if row.get("char") != "CD" or row.get("kind") != "face":
                continue
            for size in ("L", "M"):
                tag = face_id + size
                spec = self.sprite_tags.get(tag)
                if not spec:
                    raise FileNotFoundError(f"expression lacks a {size} sprite: {face_id}")
                if face_id in reviewed_ids or tag not in self.labels:
                    self.labels[tag] = {
                        "char": "CD", "set": face_id[2:4],
                        "kind": "diff" if spec.get("diff") else "base",
                        "expression": row["expression"], "pose": row.get("pose") or "none",
                        "confidence": row.get("confidence") or "source",
                        "derived_from": face_id,
                    }

    def _face_file(self, face_id):
        for name in (face_id + "F.png", face_id.lower() + "f.png", face_id + ".png"):
            p = os.path.join(self.face_dir, name)
            if os.path.exists(p):
                return p
        return None

    def _sprite_file(self, tag):
        if not tag:
            return None
        p = os.path.join(self.sprite_dir, tag.lower() + ".png")
        return p if os.path.exists(p) else None

    def _scan_overlays(self):
        """Every overlay piece on disk, by name. An overlay is only emitted if
        its file is here, so a piece the corpus does not have is drawn plain."""
        self.overlays = {}
        if not self.emotion_dir or not os.path.isdir(self.emotion_dir):
            return
        for name in os.listdir(self.emotion_dir):
            if name.lower().endswith(".png"):
                self.overlays[name[:-4].lower()] = os.path.join(self.emotion_dir, name)

    def _build(self):
        """Index verified face variants and choose one per feeling and outfit.

        The corpus names the costume as `set` (01..07) and the expression as
        `index`; `meta.label_granularity` says so in as many words. The channel
        draws one costume at a time, and which one is the outfit the stage
        manager set (`sim/stage_manager.py`) or the channel's default."""
        wanted = set(BUCKET_EXPRESSION.values())
        by_costume = {}
        variants = {}
        for face_id, row in self.labels.items():
            if row.get("char") != "CD" or row.get("kind") != "face":
                continue
            raw_expression = str(row.get("expression") or "").lower()
            expression = BUCKET_EXPRESSION.get(raw_expression, raw_expression)
            if expression not in wanted:
                continue
            costume = ("CD" + str(row.get("set") or "").strip()).upper()
            spec = self.sprite_tags.get(face_id + "L")
            if not spec:
                continue
            base_tag = spec.get("base")
            base_file = self._sprite_file(base_tag)
            face_file = self._face_file(face_id)
            if not (base_file and face_file):
                continue
            diff_tag = spec.get("diff")
            diff_file = self._sprite_file(diff_tag) if diff_tag else None
            variant = {
                "expression": expression,
                "raw_expression": raw_expression,
                "c4": expression,
                "pose": str(row.get("pose") or "none").lower(),
                "costume": costume,
                "face": face_id,
                "face_file": face_file,
                "tag": face_id + "L",
                "base_tag": base_tag,
                "base_file": base_file,
                "diff_tag": diff_tag if diff_file else None,
                "diff_file": diff_file,
                "geometry": spec.get("geometry"),
            }
            by_costume.setdefault(costume, {}).setdefault(expression, []).append(variant)
            variants.setdefault(costume, {})[face_id[-3:]] = variant
        self.variants_by_costume = variants
        self.faces_by_costume = {}
        for costume, expressions in by_costume.items():
            table = {}
            for expression, rows in expressions.items():
                # Pick the pose that fits the expression. The existing face
                # index preference breaks a tie between faces in that pose,
                # then the lowest corpus index makes the final choice stable.
                preferred = {
                    face[-3:]: index
                    for index, face in enumerate(PREFERRED.get(expression, ()))
                }
                poses = PREFERRED_POSE.get(expression, ())
                pose_order = {pose: index for index, pose in enumerate(poses)}
                rows = sorted(rows, key=lambda r: r["face"])
                rows = sorted(
                    rows,
                    key=lambda r: (
                        pose_order.get(r["pose"], len(pose_order)),
                        preferred.get(r["face"][-3:], len(preferred)),
                        r["face"],
                    ),
                )
                table[expression] = rows[0]
            self.faces_by_costume[costume] = table
        self.costumes = sorted(self.faces_by_costume)
        self.faces = self.faces_by_costume.get(self.default_costume) or (
            self.faces_by_costume[self.costumes[0]] if self.costumes else {})

    # ---------------- reading a feeling ----------------

    def normalize(self, feeling):
        key = str(feeling or "").strip().lower()
        if key in BUCKET_EXPRESSION:
            return BUCKET_EXPRESSION[key]
        if key in self.faces:
            return key
        return self.default if self.default in self.faces else DEFAULT_EXPRESSION

    def normalize_goemotion(self, label):
        """A 28-label feeling as one of her C4 faces."""
        expr = GOEMOTION_EXPRESSION.get(str(label or "").strip().lower())
        if expr:
            return self.normalize(expr)
        return self.normalize(self.default)

    def band_expression(self, valence):
        """The same cut `sim/reactions.py` makes, as an expression."""
        try:
            v = max(-1.0, min(1.0, float(valence)))
        except (TypeError, ValueError):
            return self.default
        band = sum(1 for b in BANDS if v >= b) - 2
        if band <= -2:
            return self.normalize("sad")
        if band == -1:
            return self.normalize("worried")
        if band >= 1:
            return self.normalize("happy")
        return self.normalize("neutral")

    def infer(self, text):
        for words, feeling in _KEYWORDS:
            if any(w in (text or "") for w in words):
                return self.normalize(feeling)
        return self.normalize(self.default)

    def expression_for(self, signal):
        """The C4 expression for a felt state.

        `signal` may be a string (a bucket or an expression) or a dict with any
        of `expression`, `bucket`, `mood`, `valence` or `text`."""
        if isinstance(signal, dict):
            for key in ("expression", "bucket"):
                got = signal.get(key)
                if got:
                    return self.normalize(got)
            label = signal.get("label")
            if label:
                return self.normalize_goemotion(label)
            mood = signal.get("mood")
            if mood is not None and str(mood).strip():
                return self.normalize(mood)
            if signal.get("valence") is not None:
                return self.band_expression(signal.get("valence"))
            return self.infer(signal.get("text", ""))
        return self.normalize(signal)

    def overlay_for(self, signal):
        """The overlay piece for a feeling, verified on disk, or None."""
        label = ""
        if isinstance(signal, dict):
            label = str(signal.get("label") or "").strip().lower()
        name = EMOTION_OVERLAY.get(label)
        if not name:
            return None
        path = self.overlays.get(name)
        return {"name": name, "file": path} if path else None

    def costume_ids(self):
        """The costumes on disk, as ids the console and the stage can offer."""
        return list(self.costumes)

    def resolve(self, signal, costume=None):
        """The asset dict for a felt state in one costume, verified on disk.

        `costume` is the corpus's set id (01..07). Omitted or unknown, the
        default costume is drawn, so a bad id can never leave her undressed or
        invisible. A feeling the costume does not have falls back to the nearest
        expression IN that costume, never to another costume's sprite."""
        expression = self.expression_for(signal)
        costume = str(costume or self.default_costume).strip().upper()
        table = self.faces_by_costume.get(costume) or self.faces
        chosen = None
        if isinstance(signal, dict) and signal.get("face_index") is not None:
            index = str(signal["face_index"]).strip().zfill(3)
            chosen = self.variants_by_costume.get(costume, {}).get(index)
        if chosen is None:
            chosen = table.get(expression)
        if chosen is None:
            for alt in EXPRESSION_FALLBACK.get(expression, ()):
                if table.get(alt):
                    chosen = table[alt]
                    break
        if chosen is None:
            # A missing feeling still keeps the chosen outfit. Reaching into
            # self.faces here once changed the fairy dress to the default
            # school uniform between dialogue bubbles.
            chosen = (table.get(DEFAULT_EXPRESSION) or table.get("smile") or
                      table.get("talk") or next(iter(table.values()), None))
        if chosen is None:
            raise FileNotFoundError("no koikano expression is available on disk")
        got = dict(chosen)
        # The game has separate @char and @face commands. The standing sprite
        # keeps its authored base/diff pair; a message portrait may be chosen
        # independently when a caller requests one.
        portrait = None
        if isinstance(signal, dict) and signal.get("portrait_id"):
            portrait_id = str(signal["portrait_id"]).strip().upper()
            portrait = self.variants_by_costume.get(portrait_id[:4], {}).get(portrait_id[-3:])
            if portrait and portrait["face"] != portrait_id:
                portrait = None
        elif isinstance(signal, dict) and signal.get("portrait_index") is not None:
            index = str(signal["portrait_index"]).strip().zfill(3)
            portrait = self.variants_by_costume.get(costume, {}).get(index)
        if portrait:
            got["face"] = portrait["face"]
            got["face_file"] = portrait["face_file"]
        overlay = self.overlay_for(signal)
        got["overlay"] = overlay["name"] if overlay else None
        got["overlay_file"] = overlay["file"] if overlay else None
        return got

    # ---------------- selftest ----------------

    def verify(self):
        """Every expression this can emit, checked on disk."""
        report = []
        for expression in sorted(self.faces):
            row = self.faces[expression]
            ok = (os.path.exists(row["base_file"]) and os.path.exists(row["face_file"])
                  and (row["diff_file"] is None or os.path.exists(row["diff_file"])))
            report.append((expression, row["face"], row["pose"], ok))
        return report


if __name__ == "__main__":
    import sys
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config_momoka.json")
    with open(cfg_path, encoding="utf-8") as f:
        block = (json.load(f) or {}).get("vn", {})
    ex = VnExpression(block, root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bad = 0
    for expression, face, pose, ok in ex.verify():
        print(f"{'OK ' if ok else 'MISS'} {expression:10s} {face} {pose}")
        bad += 0 if ok else 1
    print(f"{len(ex.faces)} expression(s), {bad} missing")
    raise SystemExit(1 if bad else 0)
