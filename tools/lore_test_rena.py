"""Does the promoted character reach for the right thing she knows, and stay
quiet otherwise.

`tools/lore_test.py` is the same test for the second character; this is its
pattern against `data/rena/records.json`, `data/rena/memories.json` and the one
phrase file that answers for both (`data/rena/triggers.json`).

Retrieval has two ways to be wrong and they cost differently. Fetching nothing
when somebody asks about her own brother makes her a person with no past.
Fetching something on every turn makes her a person who always has a fact to
tell you, which is worse, because silence is the design.

So the cases come in pairs: messages that must produce a named record, and
messages that must produce nothing. Each case prints the top match and its
score whether it passed or not, because the number is the evidence and a table
of ticks is not. It reads the three files off disk and touches no save: the
store is stubbed, so suppression is off and a case does not fail because that
record happened to be offered an hour ago.

    python tools/lore_test_rena.py
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

CONFIG = os.path.join(ROOT, "config_rena.json")

# What must be reached for, and by which record. A tuple means any of them is
# the right answer: her festival is on a standing record and on a memory of the
# same evening, and either is a true thing to be reminded of.
FIRE = [
    ("お兄さんいるんだっけ？", "rn.household.brother-keita"),
    ("妹の熱、下がった？", ("rn.summer.sisters-fever", "rn.memory.sister-ill",
                    "rn.memory.the-fever-log")),
    ("水曜のダンス教室ってどこでやってるの？", ("rn.week.dance-wednesday",
                             "rn.memory.dance-class-starts")),
    ("大塚の浴衣祭りどうだった？", ("rn.summer.otsuka-festival", "rn.memory.the-festival")),
    ("江古田から通ってるんだよね", "rn.self.commute"),
    ("門限って何時なの？", "rn.household.mother-2015-text"),
    ("スタンプだけ返されるとどう思う？", "rn.group.sticker-is-not-a-reaction"),
    ("プリン分けてあげたことある？", ("rn.group.the-pudding", "rn.taste.pudding",
                        "rn.memory.the-pudding")),
    ("たい焼き好きなんだっけ", ("rn.place.taiyaki", "rn.memory.the-taiyaki")),
    ("集合何時にする？", "rn.group.she-runs-it"),
    ("お小遣いいくらもらってるの", "rn.money.allowance"),
    ("中野のおじいちゃんち、日曜行くの？", "rn.household.sunday-nakano"),
    ("詩織ちゃん元気？", "rn.household.sister-shiori"),
    ("祭りの写真、まだ届いてないんだけど", ("rn.summer.four-days-of-photos",
                            "rn.memory.chasing-the-photos",
                            "rn.memory.the-photos-arrive")),
    ("遠距離の人の話、ほんとだと思う？", "rn.group.the-far-away-man"),
    ("スマホ取り上げられたの？", ("rn.household.phone-taken-23", "rn.memory.grounded")),
]

# What must leave her with nothing to say. Ordinary turns, and the near misses
# a short cue phrase invites: a one-kanji meeting place, a common apology, a
# nickname that is a substring of half the language.
SILENT = [
    "おはよう",
    "腹減った",
    "これめっちゃ面白いわ",
    "うん、そうだね。今日はちょっと疲れた",
    "今どこにいるの？",
    "そっか、わかった",
    "ちょっと出かけてくる",
    "眠い。もう寝るわ",
    "静かにしてて",
    "ごめんね、返すの遅くなった",
    "なんかいい感じだね",
    "うーん、どうだろうね。まあいいや",
    "明日も学校？",
    "写真送るね",
    "子どもの頃の話でさ",
    "それはあやしいと思うけどな",
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


def _lore():
    c = Config(CONFIG)
    return Lore(c, _Store(), _Clock())


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


def run():
    lore = _lore()
    floor = float(lore.config.lore.min_score)
    print("%s + %s, floor %.2f, %d record(s) reachable by name\n"
          % (lore.config.lore.file, lore.config.lore.memory_file, floor, len(lore._recs)))
    tp = fn = 0
    print("MUST FIRE")
    print("  %-34s %-8s %-42s %s" % ("what is said to her", "score", "top match", "verdict"))
    for cue, want in FIRE:
        want = (want,) if isinstance(want, str) else want
        best = _top(lore, cue)
        shown = cue if len(cue) < 32 else cue[:14] + "…" + cue[-15:]
        if best is None or best[0] < floor:
            fn += 1
            print("  %-34s %-8s %-42s MISS (nothing)" % (shown, "-", "-"))
            continue
        ok = best[2] in want
        tp += 1 if ok else 0
        fn += 0 if ok else 1
        print("  %-34s %-8.2f %-42s %s" % (shown, best[0], best[2],
                                           "ok" if ok else "WRONG RECORD, wanted " + want[0]))
    fp = tn = 0
    print("\nMUST STAY SILENT")
    print("  %-34s %-8s %-42s %s" % ("what is said to her", "score", "top match", "verdict"))
    for cue in SILENT:
        best = _top(lore, cue)
        if best is None or best[0] < floor:
            tn += 1
            print("  %-34s %-8s %-42s ok" % (cue, "-", "-"))
        else:
            fp += 1
            print("  %-34s %-8.2f %-42s FIRED on %s" % (cue, best[0], best[2], "/".join(best[3])))
    prec = tp / float(tp + fp) if (tp + fp) else 0.0
    rec = tp / float(len(FIRE)) if FIRE else 0.0
    print("\n%d of %d fired with the right record, %d of %d stayed quiet"
          % (tp, len(FIRE), tn, len(SILENT)))
    print("precision %.2f, recall %.2f" % (prec, rec))
    return tp, fn, fp, tn


if __name__ == "__main__":
    logger.log = lambda *a, **k: None
    tp, fn, fp, tn = run()
    sys.exit(0 if (fn == 0 and fp == 0) else 1)
