"""Does the behaviour the author meant actually turn up in what these people say?

Each person on the roster was written from a personality type, and the type
was never told to any model: it was translated into mechanisms, and the
mechanisms into observable markers. This counts the markers in the record of
that person's own turns and prints, per person and per axis, how the two
poles' counts fall.

No model call, no network, and the save is a copy (`tools/harness.py`, which
goes through SQLite's own backup). The type file is `cast.types_file`, and
**this tool is the only thing in the tree allowed to open it** -- `tools/
smoke.py` fails if anything under `sim/`, `persona/`, `tomoe/`, `resident/`,
`scail.py` or a prompt reads it.

WHAT THIS CAN SHOW: whether the behaviour the author described appears, and
roughly at the rate meant -- a person written to open rooms who opens none
in a hundred turns is a mechanism that did not land, and that is worth
knowing and is fixable in her file.

WHAT THIS CANNOT SHOW: that anybody "is" a type. A marker count is not a
type. The markers are the author's own operationalisation, counted on his
own material, so the count agrees with the author by construction and could
not do otherwise; there is one coder and no second one, so there is no
agreement figure; the poles are not scaled against each other, so "favours
E" means only "more of the markers listed under E than under I", not a
position on a dimension; and no published norm applies to invented teenagers
in a simulated chat, so none is cited. This is a check that a described
behaviour is present, and nothing beyond it.

    python tools/cast_type_test.py
    python tools/cast_type_test.py --types tools/fixtures/cast_types_fixture.json
"""
import argparse
import collections
import io
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from tools import harness  # noqa: E402

# The four axes, and the letter each pole is written with. The keys are the
# axis names a types file uses.
AXES = (("EI", "E", "I"), ("SN", "S", "N"), ("TF", "T", "F"), ("JP", "J", "P"))

TIME_RE = re.compile(r"(\d{1,2}\s*[:：]\s*\d{2}|\d{1,2}\s*時|明日|あした|今日|きょう|明後日|週末|土曜|日曜|月曜|火曜|水曜|木曜|金曜)")
QUESTION_RE = re.compile(r"[?？]")

# Markers that are a fact about the SHAPE of a turn rather than a string in
# it. Anything a types file names that is not in here is counted as a literal
# substring of the Japanese, which is the other half of what a marker may be.
# A marker that looks structural and is not in this table would count zero
# forever without saying so, so the tool names it.
STRUCTURAL = {
    "opens the exchange": lambda t, c: c["first"],
    "answers last": lambda t, c: c["last"],
    "asks a question back": lambda t, c: bool(QUESTION_RE.search(t)),
    "names a time": lambda t, c: bool(TIME_RE.search(t)),
    "sends more than one message in a row": lambda t, c: c["in_a_row"] > 1,
    "one-word reply": lambda t, c: len(t.strip()) <= 6,
    "a long message": lambda t, c: len(t.strip()) >= 60,
    "sends a stamp": lambda t, c: t.strip().startswith("[スタンプ"),
    "sends a picture": lambda t, c: t.strip().startswith("[写真"),
}


def load_types(path):
    """The types file: per roster key, or wrapped under `types` beside a
    `_note` (the shape the content was written in)."""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, dict) and isinstance(d.get("types"), dict):
        d = d["types"]
    return {k: v for k, v in d.items() if not str(k).startswith("_")}


def axes_of(entry):
    """The axes of one person's entry, whichever of the two shapes it uses:
    `axes: {EI: {behaviour, markers: {E: [...], I: [...]}}}`, or a top-level
    `markers: {EI: {E: [...], I: [...]}}` beside the lines."""
    out = {}
    axes = entry.get("axes") or {}
    top = entry.get("markers") or {}
    for name, pos, neg in AXES:
        a = axes.get(name) or {}
        if isinstance(a, str):
            # the shape the content was written in: the axis is its one line
            # of behaviour, and the markers sit beside the axes, per axis
            a = {"line": a}
        markers = a.get("markers") or top.get(name) or {}
        line = a.get("behaviour") or a.get("line") or entry.get(name) or ""
        out[name] = (str(line), {pos: list(markers.get(pos) or []),
                                 neg: list(markers.get(neg) or [])})
    return out


def turns_of(store, config):
    """key -> [(text, context)] for every turn in the record, by speaker.

    The context is what a structural marker needs and a substring does not:
    where the turn sat in its exchange, and how many of that person's turns
    ran together at that point."""
    from sim import roster, talks
    out = collections.defaultdict(list)
    for _when, _who, _kind, turns, _gist in talks.search_rows(store):
        turns = [t for t in (turns or []) if (t.get("ja") or "").strip()]
        for i, t in enumerate(turns):
            key = roster.key_of(config, t.get("who", ""))
            run = 1
            j = i - 1
            while j >= 0 and roster.key_of(config, turns[j].get("who", "")) == key:
                run += 1
                j -= 1
            out[key].append((t["ja"].strip(),
                             {"first": i == 0, "last": i == len(turns) - 1, "in_a_row": run}))
    return out


QUOTED_RE = re.compile(r"「([^」]+)」")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")

# The recurring structural facts the content wrote, by the keyword that
# names each; a marker that carries one of these keys is counted by the rule
# and not by its text. The English keys are the fixture's vocabulary.
KEYWORDS = [
    (("三通続けて", "続けて二通", "連投"), lambda t, c: c["in_a_row"] > 1),
    (("自分から話を始める", "自分から長く話す"), lambda t, c: c["first"]),
    (("話を振られてから",), lambda t, c: not c["first"]),
    (("一行で終える", "一行返して", "短い、けれど", "台所からの一言"), lambda t, c: "\n" not in t.strip() and len(t.strip()) <= 30),
    (("絵文字なし",), lambda t, c: not EMOJI_RE.search(t)),
    (("！が二つ以上",), lambda t, c: t.count("！") + t.count("!") >= 2),
    (("！を使う",), lambda t, c: ("！" in t) or ("!" in t)),
    (("句読点が少ない",), lambda t, c: (t.count("、") + t.count("。")) <= 1 and len(t.strip()) >= 12),
    (("スタンプではなく言葉",), lambda t, c: not t.strip().startswith("[スタンプ")),
    (("写真やスクショ",), lambda t, c: ("[写真" in t) or ("スクショ" in t)),
    (("時刻・回数・順番", "店名・時刻・値段・駅名", "時間・場所・持ち物", "場所と時間を先に決めて", "時刻を", "時間を書かずに"), lambda t, c: bool(TIME_RE.search(t)) or bool(re.search(r"\d+(円|駅|人|回|分|時)", t))),
    (("返事が遅く、中身がある", "一対一のときだけ長くなる"), lambda t, c: len(t.strip()) >= 60),
    (("先に謝る", "謝る必要のないところで謝る"), lambda t, c: any(w in t for w in ("ごめん", "すみません", "悪い"))),
    (("褒めない",), lambda t, c: not any(w in t for w in ("すごい", "えらい", "上手", "かわいい", "いいね"))),
    (("？", "「〜でしょ？」", "同意を取りにいく"), lambda t, c: bool(QUESTION_RE.search(t))),
]


def count(marker, turns, unknown):
    """Turns that show this marker, or None when nothing here can count it.

    A marker in the fixture's English vocabulary is a rule in STRUCTURAL. A
    Japanese marker counts by the forms quoted inside it (any of them in the
    turn), or by the keyword rule its wording carries, and a marker with
    neither is uncounted: it goes to `unknown` and prints as such, because a
    zero here would read as "the behaviour is absent" when the tool simply
    cannot see it."""
    fn = STRUCTURAL.get(marker)
    if fn is not None:
        return sum(1 for t, c in turns if fn(t, c))
    quoted = QUOTED_RE.findall(marker)
    if quoted:
        forms = [q for q in quoted if not q.startswith("〜")]
        return sum(1 for t, _c in turns if any(q in t for q in forms))
    for keys, rule in KEYWORDS:
        if any(k in marker for k in keys):
            return sum(1 for t, c in turns if rule(t, c))
    if marker.isascii():
        unknown.add(marker)
        return 0
    unknown.add(marker)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--types", default="", help="a types file to read instead of cast.types_file")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--db", default="data/world.db")
    args = ap.parse_args()

    harness.refuse_model_before_build()
    tmp = os.path.join(tempfile.gettempdir(), "scail_cast_types.db")
    app = harness.build_on(tmp, args.config, args.db)
    cfg = app.config

    path = args.types or str(getattr(cfg.cast, "types_file", "") or "")
    types = load_types(path)
    if not types:
        print("\nNothing to measure. The type file is the author's; when it exists this reads it.")
        return 0
    print("\n  the types file: %s" % path)

    by_key = turns_of(app.store, cfg)
    from sim import roster
    unknown = set()
    people = [k for k in types if not str(k).startswith("_")]
    print("  %d person/people in it, %d with turns in the record\n"
          % (len(people), sum(1 for k in people if by_key.get(roster.key_of(cfg, k)))))

    for who in people:
        entry = types[who] or {}
        key = roster.key_of(cfg, who)
        turns = by_key.get(key, [])
        intended = str(entry.get("type") or "????").upper()
        print("  %s  --  the author wrote her as %s, %d turns in the record" % (who, intended, len(turns)))
        if not turns:
            print("      nothing of hers in the record yet\n")
            continue
        read = ""
        for i, (name, pos, neg) in enumerate(AXES):
            line, markers = axes_of(entry)[name]
            ca = [count(m, turns, unknown) for m in markers[pos]]
            cb = [count(m, turns, unknown) for m in markers[neg]]
            a = sum(x for x in ca if x is not None)
            b = sum(x for x in cb if x is not None)
            skipped = sum(1 for x in ca + cb if x is None)
            if skipped:
                print("      %s  (%d marker(s) this tool cannot count; see the list at the end)" % (name, skipped))
            if not markers[pos] and not markers[neg]:
                read += "?"
                print("      %s  no markers written for this axis" % name)
                continue
            favours = pos if a > b else (neg if b > a else "?")
            read += favours
            want = intended[i] if len(intended) > i else "?"
            agree = "  <-- not the pole the author wrote" if favours != want and favours != "?" else ""
            print("      %s  %s %-4d   %s %-4d   the counts favour %s%s"
                  % (name, pos, a, neg, b, favours, agree))
            if line:
                print("          %s: %s" % (want, line[:100]))
        print("      counts read %s against the %s the author wrote\n" % (read, intended))

    if unknown:
        print("  %d marker(s) with no Japanese in them and no entry in the structural table --"
              % len(unknown))
        print("  each of these counts zero for ever and reads as absent behaviour:")
        for m in sorted(unknown):
            print("      %s" % m)
        print("  the table holds: " + ", ".join(sorted(STRUCTURAL)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
