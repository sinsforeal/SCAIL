"""A register fingerprint per speaker and per room, from the record.

`voicecheck` measures dialect and `ONE VOICE` sees only the extreme. Nothing
measured whether Rena-to-Tomoe and Rena-to-the-group are different people,
or whether everyone has flattened into one voice over a fortnight. This
counts, from the stored turns: message length, the sentence-final particles
and markers that carry register in written Japanese (ね よ じゃん さ かな
の w 笑 ！ ？ emoji, the honorific-polite です/ます), per speaker and per kind
of room, and compares rooms and weeks. Pure functions; `tools/voicelint.py
--register` prints it and `/absurd REGISTER` reads it.
"""
import re
import collections

MARKERS = {
    "ね": re.compile(r"ね[〜ー！!。…]?(\s|$|\n)"),
    "よ": re.compile(r"よ[〜ー！!。…]?(\s|$|\n)"),
    "じゃん": re.compile(r"じゃん"),
    "さ": re.compile(r"(?<![ま])さ[〜ー！!。…]?(\s|$|\n)"),
    "かな": re.compile(r"かな[〜ー！!。…]?(\s|$|\n)"),
    "w/笑": re.compile(r"(w+|笑)(\s|$|\n|[。！!])"),
    "！": re.compile(r"[！!]"),
    "？": re.compile(r"[？?]"),
    "です/ます": re.compile(r"(です|ます)[。！!？?]?(\s|$|\n)"),
    "emoji": re.compile(r"[\U0001F300-\U0001FAFF☀-➿]"),
    "〜": re.compile(r"[〜ー]{1,}(\s|$|\n|[！!。])"),
}


def fingerprint(turns):
    """turns: [{who, ja, kind, date}] -> {(who, kind): {n, chars, <marker>: rate}}
    where a rate is markers per message."""
    acc = collections.defaultdict(lambda: {"n": 0, "chars": 0, **{k: 0 for k in MARKERS}})
    for t in turns:
        ja = str(t.get("ja") or "")
        if not ja or ja.startswith("[写真"):
            continue
        key = (t.get("who") or "?", t.get("kind") or "?")
        a = acc[key]
        a["n"] += 1
        a["chars"] += len(ja)
        for k, rx in MARKERS.items():
            a[k] += len(rx.findall(ja))
    out = {}
    for key, a in acc.items():
        n = max(1, a["n"])
        out[key] = {"n": a["n"], "chars": a["chars"] / n, **{k: a[k] / n for k in MARKERS}}
    return out


def room_contrast(fp, min_turns=8):
    """Per speaker: how far their group register is from their one-to-one
    register, as the mean absolute difference of the marker rates. 0 is the
    same person in both rooms; a real teenager is not."""
    out = {}
    whos = {w for (w, _k) in fp}
    for w in whos:
        g, l = fp.get((w, "group")), fp.get((w, "line"))
        if not g or not l or g["n"] < min_turns or l["n"] < min_turns:
            continue
        diffs = [abs(g[k] - l[k]) for k in MARKERS]
        out[w] = {"distance": sum(diffs) / len(diffs), "group_n": g["n"], "line_n": l["n"],
                  "chars_group": g["chars"], "chars_line": l["chars"]}
    return out


def distinctness(fp_or_merged):
    """How far each speaker sits from the cast's mean marker rates. A voice
    is not "drifting" because its numbers moved -- Rena's じゃん, 笑 and emoji
    all rising is her sheet arriving. Flattening is movement TOWARD everyone
    else, and this is the number that says which happened."""
    merged = {}
    for key, v in fp_or_merged.items():
        who = key[0] if isinstance(key, tuple) else key
        a = merged.setdefault(who, {"n": 0, **{k: 0.0 for k in MARKERS}})
        a["n"] += v["n"]
        for k in MARKERS:
            a[k] += v[k] * v["n"]
    for who, a in merged.items():
        n = max(1, a["n"])
        for k in MARKERS:
            a[k] /= n
    if not merged:
        return {}
    mean = {k: sum(a[k] for a in merged.values()) / len(merged) for k in MARKERS}
    return {who: sum(abs(a[k] - mean[k]) for k in MARKERS) / len(MARKERS) for who, a in merged.items()}


def drift(turns, days=7, min_turns=10):
    """Per speaker: the last `days` against the `days` before, all rooms
    together. `moved` is which markers moved by more than half and by more
    than 0.05 per message -- information, not a fault. `flattening` is the
    only fault: their distance from the cast mean fell."""
    dates = sorted({t.get("date") for t in turns if t.get("date")})
    if len(dates) < 2:
        return {}
    last = dates[-1]
    import datetime
    try:
        d0 = datetime.date.fromisoformat(last)
    except ValueError:
        return {}
    cut = (d0 - datetime.timedelta(days=days)).isoformat()
    cut2 = (d0 - datetime.timedelta(days=2 * days)).isoformat()
    now = [t for t in turns if (t.get("date") or "") > cut]
    before = [t for t in turns if cut2 < (t.get("date") or "") <= cut]
    a, b = fingerprint(now), fingerprint(before)
    da, db = distinctness(a), distinctness(b)
    out = {}
    for who in {w for (w, _k) in a} & {w for (w, _k) in b}:
        def merged(fp):
            rows = [v for (w, _k), v in fp.items() if w == who]
            n = sum(r["n"] for r in rows) or 1
            return {"n": n, **{k: sum(r[k] * r["n"] for r in rows) / n for k in MARKERS}}
        ma, mb = merged(a), merged(b)
        if ma["n"] < min_turns or mb["n"] < min_turns:
            continue
        moved = []
        for k in MARKERS:
            x, y = mb[k], ma[k]
            if abs(y - x) > 0.05 and abs(y - x) > 0.5 * max(x, 0.02):
                moved.append(f"{k} {x:.2f}->{y:.2f}")
        near = da.get(who, 0.0) - db.get(who, 0.0)
        out[who] = {"n_now": ma["n"], "n_before": mb["n"], "moved": moved,
                    "distinct_now": da.get(who, 0.0), "distinct_before": db.get(who, 0.0),
                    "flattening": near < -0.01}
    return out
