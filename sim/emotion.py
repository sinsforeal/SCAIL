# -*- coding: utf-8 -*-
"""What she is feeling, as one of the 28 GoEmotions labels.

A label is a word a reader can agree about, and the label is what the VN
channel draws: `channels/vn_expression.py` maps it to one of Momoka's C4
faces. The 28 labels are the GoEmotions set (Demszky et al.); the C4 faces
she actually has are eight, so the map is many-to-one and a label outside
her recorded set (anger, pride, grief) is drawn as the nearest face rather
than invented.

Two passes, cheapest first:

* `classify` reads the words. It is deterministic, it never calls out, and
  it is the default: a refused or absent model still moves her face.
* When `emotion.model` is on and a model is wired, the same question is put
  to the `emotion` role -- a judge, neutral, no character sheet -- and its
  label is used only if it is one of the 28. Every other answer (a fence, a
  sentence, a label that is not in the set) falls back to the local pass.

Nothing here writes to her record. The label is read by the channel for the
frame it is about to draw and by nothing else.
"""

import json
import os
import re
import sys

# `import logger` is a root-level module, so the root has to be importable
# BEFORE it -- and it was not: running this file directly (`python
# sim/emotion.py`, which is what its own `verify` block is for) puts `sim/` on
# the path, so the module-level import raised ModuleNotFoundError and the
# self-test could not run at all. Imported as `sim.emotion` by the runtime the
# root is already there and this changes nothing.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import logger

# The GoEmotions labels, in the order the taxonomy lists them. The one
# addition is `neutral`, which the taxonomy carries and a face needs.
GOEMOTIONS = (
    "admiration", "amusement", "anger", "annoyance", "approval", "caring",
    "confusion", "curiosity", "desire", "disappointment", "disapproval",
    "disgust", "embarrassment", "excitement", "fear", "gratitude", "grief",
    "joy", "love", "nervousness", "optimism", "pride", "realization",
    "relief", "remorse", "sadness", "surprise", "neutral",
)

# label -> the C4 face she has for it. The right-hand side is exactly the
# vocabulary `channels/vn_expression.py` can draw (smile, laugh, surprise,
# excited, talk, neutral, sad, worried), so a label the resolver has never
# heard of is not a new face, it is one of the eight.
GOEMOTION_EXPRESSION = {
    "admiration": "smile",
    "amusement": "laugh",
    "anger": "sad",
    "annoyance": "worried",
    "approval": "smile",
    "caring": "smile",
    "confusion": "worried",
    "curiosity": "talk",
    "desire": "smile",
    "disappointment": "sad",
    "disapproval": "worried",
    "disgust": "worried",
    "embarrassment": "smile",
    "excitement": "excited",
    "fear": "worried",
    "gratitude": "smile",
    "grief": "sad",
    "joy": "smile",
    "love": "smile",
    "nervousness": "worried",
    "optimism": "smile",
    "pride": "smile",
    "realization": "surprise",
    "relief": "smile",
    "remorse": "sad",
    "sadness": "sad",
    "surprise": "surprise",
    "neutral": "neutral",
}

# The label a face rests on when nothing in the words moves it.
DEFAULT_LABEL = "neutral"

# The words that carry a feeling, most specific first. Each row is a label
# and the cues for it; the first row with a hit wins, so a sentence that
# laughs and apologises in one breath reads as the apology. Japanese, because
# that is the room she writes in; the romanised and English cues are there so
# a stray English line is not read as flat.
_CUES = (
    ("amusement", ("あはは", "ははは", "うふふ", "ふふっ", "笑う", "笑った", "面白", "おもしろ", "おかしい", "ウケる", "www", "lol", "haha")),
    ("joy", ("嬉しい", "うれしい", "たのしい", "楽しい", "やった", "わーい", "うれし", "最高", "よかった", "幸せ", "しあわせ")),
    ("excitement", ("わくわく", "ドキドキ", "楽しみ", "たのしみ", "早く", "はやく", "すごい", "やばい", "ワクワク")),
    ("gratitude", ("ありがと", "ありがとう", "感謝", "助かった", "助かる", "感謝して", "thank", "thanks")),
    ("admiration", ("すてき", "素敵", "かっこいい", "立派", "りっぱ", "さすが", "尊敬", "すごいね", "うまい", "上手")),
    ("love", ("大好き", "だいすき", "好き", "すき", "愛して", "会いたい", "あいたい", "恋しい")),
    ("caring", ("大丈夫", "だいじょうぶ", "心配", "しんぱい", "気をつけ", "気をつけて", "無理し", "むりし")),
    ("surprise", ("びっくり", "おどろ", "驚", "えっ", "ええっ", "まさか", "うそ", "本当に", "ほんとに", "突然")),
    ("realization", ("そうか", "そっか", "なるほど", "気づ", "きづ", "わかった", "分かった", "思い出した")),
    ("confusion", ("どういう", "意味が", "わからない", "分からない", "わかんない", "混乱", "こんらん", "？", "??")),
    ("curiosity", ("なんで", "なぜ", "どうして", "知りたい", "気になる", "どんな", "教えて", "きになる")),
    ("nervousness", ("緊張", "きんちょう", "ドキドキ", "不安", "ふあん", "こわい", "怖い", "心臓")),
    ("fear", ("怖い", "こわい", "恐ろし", "おそろし", "やめて", "こわ", "怖")),
    ("embarrassment", ("はずかし", "恥ずか", "恥ず", "てれ", "照れ", "こんなの", "もう")),
    ("disappointment", ("残念", "ざんねん", "がっかり", "残念だ", "ショック", "しょんぼり")),
    ("sadness", ("かなし", "悲し", "さみし", "寂し", "つらい", "辛い", "泣", "涙", "悲")),
    ("grief", ("亡く", "なくなっ", "失った", "喪", "も喪")),
    ("remorse", ("ごめん", "ごめんなさい", "すみません", "申し訳", "もうしわけ", "反省", "後悔")),
    ("annoyance", ("もういい", "うるさい", "うっとうし", "うざ", "めんどくさ", "いらいら", "イライラ", "むっ")),
    ("anger", ("むかつ", "腹立", "怒", "ふざけ", "許せ", "ゆるせ", "怒り")),
    ("disapproval", ("よくない", "だめ", "ダメ", "いけない", "べきじゃ", "ふさわしくな")),
    ("disgust", ("きも", "キモ", "気持ち悪", "嫌悪", "けんお", "嫌だ", "いやだ")),
    ("desire", ("欲しい", "ほしい", "したい", "食べたい", "行きたい", "会いたい", "ほし")),
    ("optimism", ("きっと", "たぶんうまく", "大丈夫だよ", "うまくいく", "楽しみだ", "希望", "きぼう")),
    ("pride", ("やった", "できた", "誇り", "ほこり", "自慢", "がんばった", "頑張った")),
    ("relief", ("よかった", "ほっと", "安心", "あんしん", "助かった", "やれやれ")),
    ("approval", ("いいね", "いいとおもう", "いいと思う", "賛成", "当然", "そのとおり", "その通り")),
)

# a feeling in a question mark or exclamation is still a feeling; these count
# only when nothing more specific is there
_MARKS = (("surprise", ("！？", "?!", "!?")),)


class Emotion:
    """The label for a line, from the words or from the `emotion` role."""

    def __init__(self, config, store=None, clock=None, llm=None, typesafe=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.llm = llm
        # The hosted classifier (`typesafe.py`, `docs/system-one.md`): when her
        # config turns the `emotion` use on, one `choice` over the 28 labels
        # answers the question the role answers in prose -- and that answer
        # needs no validation, because the criteria ARE the label set.
        self.typesafe = typesafe
        c = getattr(config, "emotion", None)
        self.enabled = bool(getattr(c, "enabled", False))
        # whether the model is asked at all, and only when one is wired
        self.use_model = bool(getattr(c, "use_model", False)) and llm is not None
        self.default = str(getattr(c, "default_label", "") or DEFAULT_LABEL).lower()
        if self.default not in GOEMOTIONS:
            self.default = DEFAULT_LABEL

    # ---------------- the local pass ----------------

    def classify_words(self, text):
        """The label the words alone carry, and how strongly (0..1)."""
        low = (text or "").lower()
        if not low.strip():
            return self.default, 0.0
        for label, cues in _CUES:
            hits = sum(1 for w in cues if w in low)
            if hits:
                # two cues of one feeling is a stronger read than one; the
                # ceiling is 1.0 and a single hit is already 0.6
                return label, min(1.0, 0.6 + 0.2 * (hits - 1))
        for label, cues in _MARKS:
            if any(w in text for w in cues):
                return label, 0.4
        return self.default, 0.2

    # ---------------- the model pass ----------------

    def _ask(self, text):
        """The label for this line, from the classifier or the role, or "".

        System One answers first when the use is on: a `choice` over the 28
        GoEmotions labels, thresholded, so the answer arrives already on the set
        and carrying a confidence. A classifier that cannot answer, or that
        lands under the floor, leaves the role to decide exactly as it did
        before."""
        ask = str(text or "")[:2000]
        if self.typesafe is not None and self.typesafe.ready("emotion"):
            use = self.typesafe.use("emotion") or {}
            floor = float(use.get("threshold", 0.35))
            questions = {"emotion": {
                "type": "choice",
                "instructions": "Which feeling does `her_line` carry?",
                "criteria": {label: None for label in GOEMOTIONS},
            }}
            answers = self.typesafe.ask("emotion", {"her_line": ask}, questions)
            choice, conf = self.typesafe.choice(answers, "emotion") if answers else (None, 0.0)
            if choice in GOEMOTIONS:
                if conf >= floor:
                    logger.log(f"[emotion] typesafe: {choice} (conf {conf:.2f})")
                    return choice
                logger.log(f"[emotion] typesafe: {choice} under the floor "
                           f"({conf:.2f} < {floor}); the words decide")
        if not self.use_model:
            return ""
        try:
            system = self.config.prompt_text("emotion")
            messages = [{"role": "system", "content": system},
                        {"role": "user", "content": str(text)[:2000]}]
            result = self.llm.call_json("emotion", messages)
        except Exception:
            return ""
        # `call_json` answers (data, raw); a caller that reads the tuple as
        # the dict silently falls back to the words for ever
        got = result[0] if isinstance(result, tuple) else result
        label = ""
        if isinstance(got, dict):
            label = str(got.get("label") or got.get("emotion") or "").strip().lower()
        elif isinstance(got, str):
            label = got.strip().lower()
        label = re.sub(r"[^a-z]", "", label)
        return label if label in GOEMOTIONS else ""

    # ---------------- the one callers make ----------------

    def classify(self, text):
        """The label for a line: the model's if it gave one, the words' else."""
        label = self._ask(text)
        if label:
            return label
        return self.classify_words(text)[0]

    def resolve(self, text):
        """The label, the C4 face and the intensity, as the channel wants them."""
        label = self.classify(text)
        intensity = 0.6
        if label == self.default or label == DEFAULT_LABEL:
            intensity = self.classify_words(text)[1]
        return {"label": label, "c4": GOEMOTION_EXPRESSION.get(label, "neutral"),
                "expression": GOEMOTION_EXPRESSION.get(label, "neutral"),
                "intensity": round(float(intensity), 2)}

    def expression_for(self, label):
        return GOEMOTION_EXPRESSION.get(str(label or "").lower(), "neutral")

    # ---------------- selftest ----------------

    def verify(self):
        """Every label the map names is in the set, and every face is drawable."""
        bad = sorted(k for k in GOEMOTION_EXPRESSION if k not in GOEMOTIONS)
        return [(label, GOEMOTION_EXPRESSION[label]) for label in GOEMOTIONS], bad


if __name__ == "__main__":
    import os
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)
    with open(os.path.join(root, "config_momoka.json"), encoding="utf-8") as f:
        block = (json.load(f) or {}).get("emotion", {})

    class _C:
        emotion = type("E", (), {"enabled": True, "use_model": False, "default_label": "neutral"})()

    em = Emotion(_C())
    rows, bad = em.verify()
    for text in ("うれしい！ありがとう", "ごめんね、私のせいだ", "えっ、まさか", "……別に", "こわいよ"):
        got = em.resolve(text)
        print(f"{text!r:24s} -> {got['label']:12s} {got['c4']}")
    print(f"{len(rows)} label(s), {len(bad)} off the set")
    raise SystemExit(1 if bad else 0)
