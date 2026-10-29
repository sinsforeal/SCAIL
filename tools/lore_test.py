"""Does she reach for the right thing she knows, and stay quiet otherwise.

Retrieval has two ways to be wrong and they cost differently. Fetching nothing
when he asks the name of her own programme makes her a person with no past.
Fetching something on every turn makes her a person who always has a fact to
tell you, which is worse, because silence is the design.

So the cases come in pairs: messages that must produce a named record, and
messages that must produce nothing. Each case prints the top match and its
score whether it passed or not, because the number is the evidence and a table
of ticks is not.

It reads the record file and the phrase file off disk and touches no save at
all: the store is stubbed, so suppression is off and a case does not fail
because that record happened to be offered in the real conversation an hour
ago.

    python tools/lore_test.py            # the whole set
    python tools/lore_test.py --gate     # again with the era gate forced on
    python tools/lore_test.py --off      # again with it forced off
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

import logger  # noqa: E402
from config import Config  # noqa: E402
from sim.lore import Lore  # noqa: E402

# The last three exchanges of the real conversation from her save on
# 2026-09-01, ending with him listing what she looks like to him and her
# answering the one word she did not know. Copied here rather than read from
# the live database, so the case stays the same case next month.
REAL = "\n".join([
    "まあ、ゆかりんは家事が嫌いなタイプだと思ってたんだけどね。",
    "なんでそう思ったの？",
    "違うかい？そういうイメージがあるんです",
    "嫌いってわけじゃないよ。ただ、好きでもないだけ。\nゆかりのこと、どういうイメージなの？",
    "声優アイドル\nステージを輝いている\nリーパン\n上手の歌\n高い声",
    "リーパンって、なに？ それだけわかんない。\n…ステージで輝いてる、って。そう見えてるんだ。",
])

# what she must be reminded of, and by which record
FIRE = [
    ("黒うさぎってどんな番組なの？", "yk.career.kuro-usagi"),
    ("デビューっていつだったの？", "yk.role.debut"),
    ("パソコン使えるの？", "yk.trait.filthy-computer-cannot-fix"),
    ("なのはってアニメ知ってる？", "yk.role.nanoha"),
    ("弟いるんだっけ？", "yk.biography.younger-brother-six-years"),
    ("ひぐらし観てる", "yk.role.furude-rika"),
    (REAL, ("yk.career.six-or-seven-years-voice-actor", "yk.trait.hologram",
            "yk.person.live-behind-scenes", "yk.career.kuro-usagi")),
    # added: the ways these actually come up
    ("いたずら黒うさぎ、まだやってるの？", "yk.career.kuro-usagi"),
    ("ほっちゃんとは仲いいの？", ("yk.person.hocchan", "yk.career.yamato-nadeshiko-horie-yui",
                        "yk.biography.yamato-nadeshiko")),
    ("蛍光灯切れたままなんだけど", ("yk.trait.fluorescent-tube-never-changed", "yk.person.light-bulb")),
    ("コーヒー飲む？", "yk.trait.cannot-drink-coffee"),
    ("福岡出身だっけ", ("yk.biography.from-fukuoka", "yk.trait.fukuoka")),
    ("注射こわい", ("yk.trait.frightened-injections", "yk.trait.injection")),
    ("誕生日いつ？", ("yk.biography.born-twenty-seventh", "yk.biography.february-27")),
    ("納豆好き？", ("yk.trait.natto", "yk.trait.called-bad-eater-performs")),
    ("津田さんって誰？", ("yk.person.manager-tsuda", "yk.trait.tsuda")),
    ("桃鉄やろうよ", "yk.trait.momotetsu-king-bonbi"),
    ("お酒飲めるの？", "yk.trait.does-drink"),
    ("免許持ってる？", "yk.biography.driving-licence"),
    ("運動してる？", ("yk.trait.hates-exercise-keeps-meaning-swim", "yk.trait.indoor")),
    ("ジョジョ読んでる", "yk.role.jojo"),
    ("ネギの話ほんと？", ("yk.career.paid-spring-onions", "yk.trait.negi")),
]

# what must leave her with nothing to say
SILENT = [
    "おはよう",
    "腹減った",
    "これめっちゃ面白いわ",
    "うん、そうだね。今日はちょっと疲れた",
    # added: ordinary turns that the old scorer fired on, and near misses
    "今どこにいるの？",
    "そっか、わかった",
    "ちょっと出かけてくる",
    "眠い。もう寝るわ",
    "静かにしてて",              # 静かに contains かに
    "アメリカの話でさ",           # アメリカ contains リカ
    "なんかいい感じだね",
    "うーん、どうだろうね。まあいいや",
    "明日も仕事？",
    "写真送るね",
]


class _Store(dict):
    """The record is read from disk; nothing else here touches a save."""

    def get(self, k, default=None):
        return default

    def set(self, k, v):
        pass


class _Clock:
    def now_ts(self):
        return 0.0


def _lore(gate=None):
    c = Config(os.path.join(ROOT, "config_yukarin.json"))
    if gate is not None:
        c.lore.era_gate = gate
    lore = Lore(c, _Store(), _Clock())
    return lore


def _top(lore, cue):
    """The best match and its score, without offering it or noting it."""
    lore._load()
    said = str(cue).lower()
    best = None
    for r in lore._recs:
        hit = [k for k in r["keys"] if k in said]
        if not hit:
            continue
        hit = [k for k in hit if not any(k != o and k in o for o in hit)]
        s = sum(lore._weight.get(k, 1.0) for k in hit)
        if best is None or (s, r["rank"]) > (best[0], best[1]):
            best = (s, r["rank"], r["id"], hit)
    return best


def opened_by_him():
    """A work she cannot know yet, and the one thing that opens it.

    With the era gate on she has nothing to say about a 2006 series, which is
    the gate working. When he watches it the record is released and only that
    one is (`sim/watching_him.py`), so the same message that got nothing
    before now gets her part in it.
    """
    class _Watched(_Store):
        def get(self, k, default=None):
            return ["furude rika"] if k == "lore_contact" else default

    print("\nOPENED BY WHAT HE HAS WATCHED  (era gate on)")
    for label, store in (("before he watches it", _Store()), ("after he watches it", _Watched())):
        lore = _lore(True)
        lore.store = store
        out = lore.lines("ひぐらし観てる")
        print("  %-22s %s" % (label, str(out[0])[:80] if out else "(nothing)"))


def run(gate=None):
    lore = _lore(gate)
    floor = float(lore.config.lore.min_score)
    print("era gate %s, %s, floor %.2f\n"
          % ("on" if lore.config.lore.era_gate else "off",
             lore.config.lore.triggers_file, floor))
    tp = fn = 0
    print("MUST FIRE")
    print("  %-34s %-8s %-46s %s" % ("what he says", "score", "top match", "verdict"))
    for cue, want in FIRE:
        want = (want,) if isinstance(want, str) else want
        best = _top(lore, cue)
        shown = cue if len(cue) < 32 else cue[:14].replace("\n", " ") + "…" + cue[-15:].replace("\n", " ")
        if best is None or best[0] < floor:
            fn += 1
            print("  %-34s %-8s %-46s MISS (nothing)" % (shown, "-", "-"))
            continue
        ok = best[2] in want
        tp += 1 if ok else 0
        fn += 0 if ok else 1
        print("  %-34s %-8.2f %-46s %s" % (shown, best[0], best[2],
                                           "ok" if ok else "WRONG RECORD, wanted " + want[0]))
    fp = tn = 0
    print("\nMUST STAY SILENT")
    print("  %-34s %-8s %-46s %s" % ("what he says", "score", "top match", "verdict"))
    for cue in SILENT:
        best = _top(lore, cue)
        if best is None or best[0] < floor:
            tn += 1
            print("  %-34s %-8s %-46s ok" % (cue, "-", "-"))
        else:
            fp += 1
            print("  %-34s %-8.2f %-46s FIRED on %s" % (cue, best[0], best[2], "/".join(best[3])))
    prec = tp / float(tp + fp) if (tp + fp) else 0.0
    rec = tp / float(len(FIRE)) if FIRE else 0.0
    print("\n%d of %d fired with the right record, %d of %d stayed quiet"
          % (tp, len(FIRE), tn, len(SILENT)))
    print("precision %.2f, recall %.2f" % (prec, rec))
    return tp, fn, fp, tn


if __name__ == "__main__":
    logger.log = lambda *a, **k: None
    if "--gate" in sys.argv:
        run(True)
    elif "--off" in sys.argv:
        run(False)
    else:
        run(None)
    opened_by_him()
