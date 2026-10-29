"""Light cast cards for the koikano cast world (design 1.2), built mechanically.

    python tools/koikano/build_cast_cards.py [--bible-root DIR] [--corpus DIR] [--only chisa]

Reads, per subject: a B0-B2 bible.json (from tools/koikano/koikano_bible.py --char X) for
identity, address forms and relationships; the corpus character_lines/*.jsonl for the
speech numbers and the example receipts; stage_state.jsonl for the places. Writes
characters/<slug>/card.json.

The speech lines are computed here from the subject's own spoken lines, against the
other cast as the baseline. They do not use the bible's speech_guide rule texts: for a
subject other than 百花 those are 百花-authored prose (docs/reports/2026-10-23_cast_bundles_notebook.md,
finding 1). No age, grade or birthplace is read or written.
"""
import argparse
import collections
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

DEFAULT_CORPUS = r"F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work"
DEFAULT_BIBLES = r"F:\temp\world_mine"

# Pronouns come from each subject's own gender field; no text in this file names one by hand.
PRON = {"she": {"male": False, "subj": "she", "obj": "her", "poss": "her", "label": "she/her", "sex": "female"},
        "he": {"male": True, "subj": "he", "obj": "him", "poss": "his", "label": "he/him", "sex": "male"}}

SUBJECTS = {
    "chisa": {"name": "知紗", "family": "榎本", "dir": "chisa", "reading": "ちさ", "reading_basis": "slug and character row, no printed reading line",
              "gender": "she",
              "gender_basis": [{"id": "a01_01:1856", "anchor": "彼氏いない歴"}],
              "extra_forms": ["知紗せんせー"],
              "club": [
                  {"fact": "General adviser to the small clubs (弱小部の総顧問), in her own words.", "receipt": {"id": "03_01:0669", "anchor": "総顧問"}},
                  {"fact": "Adviser of the literary club (文芸部の顧問).", "receipt": {"id": "01_01:4128", "anchor": "文芸部の顧問"}},
                  {"fact": "Adviser of the student council (生徒会の顧問).", "receipt": {"id": "04_01:2999", "anchor": "生徒会の顧問"}},
                  {"fact": "Regular at the infirmary (保健室の常連); Momoka goes there with her.", "receipt": {"id": "05_01:3677", "anchor": "保健室の常連"}},
              ]},
    "hikaru": {"name": "ひかる", "family": "小野坂", "dir": "hikaru", "reading": "ひかる", "reading_basis": "the name is written in kana",
               "gender": "he",
               "gender_basis": [{"id": "01_01:3836", "anchor": "男が男にモテた"}, {"id": "a01_01:1124", "anchor": "男の水着姿"}],
               # Feminine manner of a boy (the User's brief 10-23 19:41): computed softener rates against the rest of
               # the cast, then hand facts about how he and others read him. Every item carries record receipts.
               "manner_computed": [
                   ("laughs with あはは or はは", r"あはは|はは", "line carries a laugh"),
                   ("softens a line end with a drawn-out ねぇ, なぁ or かぁ", r"(ねぇ|なぁ|かぁ)[…。！？」]*$", "line ends drawn out"),
                   ("closes on a soft check-in (かな, でしょ, よね, じゃない)", r"(かな|でしょ|よね|じゃない)[…。！？」]*$", "line ends on a check-in"),
               ],
               "manner_facts": [
                   {"fact": "Is read as girl-like by others and by 一悟 and keeps the male uniform: 男子の制服着てるのにねぇ.", "receipt": {"id": "01_01:3906", "anchor": "男子の制服着てるのにねぇ"}},
                   {"fact": "Knows he is mistaken for a girl and answers that what 一悟 thinks is what matters.", "receipt": {"id": "b05_01:0418", "anchor": "一悟がどう思うかが重要"}},
                   {"fact": "Plays with it: asks whether 一悟 can see him as a girl too.", "receipt": {"id": "b05_01:0406", "anchor": "僕を女の子としても見れる"}},
                   {"fact": "Takes the joke that he is cuter than the girls and asks if he is a candidate.", "receipt": {"id": "d01_01:0406", "anchor": "僕も一応候補になれる"}},
                   {"fact": "Shrugs off his own looks: he is the one behind the camera.", "receipt": {"id": "01_01:3917", "anchor": "自分が整ってたところで"}},
                   {"fact": "Teases 一悟 with a sung-out name and a poke (い～ちごっ ... えいっ), then laughs it off.", "receipt": {"id": "c03_01:0145", "anchor": "い～ちごっ"}},
                   {"fact": "Is a boy and says so when it counts: male attention is no pleasure to him.", "receipt": {"id": "01_01:3836", "anchor": "男が男にモテた"}},
               ],
               "extra_forms": [],
               "club": [
                   {"fact": "Belongs to the newspaper club (新聞部), which prints the school paper 早久保タイムズ.", "receipt": {"id": "01_01:3928", "anchor": "新聞部"}},
                   {"fact": "Classmate of 一悟 (the player).", "receipt": {"id": "01_01:3739", "anchor": "クラスメイト"}},
                   {"fact": "Works with the culture festival committee (文化祭実行委員会).", "receipt": {"id": "02_01:4098", "anchor": "文化祭実行委員会"}},
               ]},
}
MOMOKA = "百花"
SELF_FORMS = ["私", "わたし", "あたし", "僕", "ぼく", "俺", "おれ", "自分", "うち"]
POLITE = re.compile(r"(です|ます|ません|でした|ました|ございま|ください)")


def rid(scene, line):
    return "%s:%04d" % (scene, int(line))


def load_spoken(corpus, name):
    out = []
    path = os.path.join(corpus, "character_lines", name + ".jsonl")
    with open(path, encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            if d.get("kind") == "spoken":
                out.append((rid(d["scene"], d["source_line"]), d["text"]))
    return out


def body(text):
    t = text.strip().strip("「」『』")
    return t


def ending(text):
    t = re.sub(r"[。！？…、，．\s」』）)~〜♪]+$", "", body(text))
    return t[-2:] if len(t) >= 2 else ""


def stats(lines):
    n = len(lines)
    lens = [len(body(t)) for _, t in lines]
    pol = sum(1 for _, t in lines if POLITE.search(t))
    q = sum(1 for _, t in lines if "？" in t)
    ell = sum(1 for _, t in lines if "…" in t)
    exc = sum(1 for _, t in lines if "！" in t)
    ends = collections.Counter(ending(t) for _, t in lines)
    return {"n": n, "median": statistics.median(lens) if lens else 0, "polite": pol / n if n else 0,
            "q": q / n if n else 0, "ell": ell / n if n else 0, "exc": exc / n if n else 0, "ends": ends}


def pick(lines, rx, k=2):
    """k receipts spread over the subject's lines that match rx."""
    hits = [(i, t) for i, t in lines if rx.search(t)]
    if not hits:
        return []
    step = max(1, len(hits) // k)
    return [{"id": i, "anchor": rx.pattern if len(rx.pattern) <= 6 else rx.search(t).group(0)} for i, t in hits[::step][:k]]


def count_forms(lines, forms):
    forms = sorted(forms, key=len, reverse=True)
    rx = re.compile("|".join(re.escape(f) for f in forms))
    c = collections.Counter()
    first = {}
    for i, t in lines:
        for m in rx.finditer(t):
            c[m.group(0)] += 1
            first.setdefault(m.group(0), i)
    return c, first


def places(corpus, name, scene_filter=None):
    sys.path.insert(0, ROOT)
    from sim.scene import PLACE_BACKGROUNDS
    num2place = {v[2:4]: k for k, v in PLACE_BACKGROUNDS.items()}
    cnt = collections.Counter()
    first = {}
    with open(os.path.join(corpus, "stage_state.jsonl"), encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            if d.get("speaker") != name:
                continue
            bg = ((d.get("stage") or {}).get("bg") or {}).get("id") or ""
            m = re.match(r"BG(\d\d)", bg)
            p = num2place.get(m.group(1)) if m else None
            if p:
                cnt[p] += 1
                first.setdefault(p, (rid(d["scene"], d["source_line"]), bg))
    return cnt, first


def build(slug, spec, args, base):
    corpus = args.corpus
    bible = json.load(open(os.path.join(args.bible_root, spec["dir"], "bible.json"), encoding="utf-8"))
    ident = bible["identity"]
    name = spec["name"]
    lines = load_spoken(corpus, name)
    mom = load_spoken(corpus, MOMOKA)
    inter = bible["interactions"]
    st = stats(lines)

    # self reference, computed
    sc, _ = count_forms(lines, SELF_FORMS + [name])
    top_self = sc.most_common(1)[0][0] if sc else None

    speech = []
    if top_self:
        rx = re.compile(re.escape(top_self))
        n = sum(1 for _, t in lines if rx.search(t))
        speech.append({
            "text": "Self-reference is %s: %d of %d spoken lines. Others used: %s." % (
                top_self, n, st["n"], ", ".join("%s %d" % (k, v) for k, v in sc.most_common(4)[1:]) or "none"),
            "kind": "computed", "pattern": top_self, "n": n, "of": st["n"], "receipts": pick(lines, rx)})
    # register
    pol, bpol = st["polite"], base["polite"]
    if abs(pol - bpol) >= 0.12:
        word = "Polite forms (です, ます, ません ...)" if pol > bpol else "Plain forms, few です or ます"
        n = sum(1 for _, t in lines if POLITE.search(t))
        speech.append({
            "text": "%s on %d of %d lines (%.0f%%); the rest of the cast is at %.0f%%." % (word, n, st["n"], pol * 100, bpol * 100),
            "kind": "computed", "pattern": POLITE.pattern, "n": n, "of": st["n"],
            "receipts": pick(lines, POLITE) if pol > bpol else [dict(r, anchor=None, absent=POLITE.pattern) for r in pick([(i, t) for i, t in lines if not POLITE.search(t)], re.compile(r"。|！|？|…"))]})
    # ending signature
    best = None
    for e, c in st["ends"].most_common(12):
        if c < 12 or not e or not re.search(r"[ぁ-んァ-ヶ]", e):
            continue
        b = base["ends"].get(e, 0) / base["n"]
        r = (c / st["n"]) / b if b else 99
        if r >= 2.5 and (best is None or c > best[1]):
            best = (e, c, r)
    if best:
        e = best[0]
        speech.append({
            "text": "Ends lines on %s: %d lines (%.1f%%), %.1f times the rest of the cast's rate." % (e, best[1], best[1] * 100 / st["n"], best[2]),
            "kind": "computed", "pattern": e, "n": best[1], "of": st["n"],
            "receipts": [{"id": i, "anchor": e} for i, t in lines if ending(t) == e][: 2]})
    # turn length
    ratio = st["median"] / base["median"] if base["median"] else 1
    if ratio <= 0.8 or ratio >= 1.25:
        speech.append({
            "text": "Median turn %d characters, %s than the rest of the cast (%d)." % (st["median"], "shorter" if ratio < 1 else "longer", base["median"]),
            "kind": "computed", "pattern": None, "n": None, "of": st["n"], "receipts": []})
    # ellipsis / question / exclaim, only if far from baseline
    for key, mark, label in (("ell", "…", "ellipsis"), ("q", "？", "question mark"), ("exc", "！", "exclamation")):
        if len(speech) >= 5:
            break
        if base[key] and (st[key] / base[key] >= 1.6 or st[key] / base[key] <= 0.5) and abs(st[key] - base[key]) >= 0.05:
            n = sum(1 for _, t in lines if mark in t)
            speech.append({
                "text": "%s on %d of %d lines (%.0f%%) against %.0f%% for the rest of the cast." % (label, n, st["n"], st[key] * 100, base[key] * 100),
                "kind": "computed", "pattern": mark, "n": n, "of": st["n"], "receipts": pick(lines, re.compile(re.escape(mark)))})
    speech = speech[:5]

    # address forms: how others call the subject, with counts and a first receipt
    they = inter["they_address_her"]
    forms = [f for f in they]
    allcast = {}
    for other in ("百花", "真優", "千奈", "アリス", "真里亜", "知紗", "ひかる", "一悟"):
        if other == name:
            continue
        try:
            allcast[other] = load_spoken(corpus, other)
        except OSError:
            pass
    pool = [x for v in allcast.values() for x in v]
    fcount, ffirst = count_forms(pool, forms)
    addressed_as = [{"form": f, "n": they[f], "receipt": {"id": ffirst.get(f), "anchor": f} if f in ffirst else None}
                    for f in sorted(they, key=lambda k: -they[k])]
    # how the subject addresses others
    her_terms = inter["her_address_terms_overall"]
    addresses = []
    for f in sorted(her_terms, key=lambda k: -her_terms[k]):
        r = next(({"id": i, "anchor": f} for i, t in lines if f in t), None)
        addresses.append({"form": f, "n": her_terms[f], "receipt": r})

    # Momoka: what she calls the subject (computed on her spoken lines) and what the subject calls her
    mfc, mffirst = count_forms(mom, forms + spec["extra_forms"])
    momoka_calls = [{"form": f, "n": n, "receipt": {"id": mffirst[f], "anchor": f}} for f, n in mfc.most_common()]
    rel = inter["relationships"].get(MOMOKA, {})
    sub_calls_momoka = rel.get("her_address_terms", {})
    with_momoka = {
        "scenes_together": rel.get("scenes_together"),
        "subject_lines_to_momoka": rel.get("her_lines_to_them"),
        "subject_starts_exchange": rel.get("exchange_her_starts"),
        "momoka_starts_exchange": rel.get("exchange_they_start"),
        "subject_calls_momoka": [{"form": f, "n": n} for f, n in sorted(sub_calls_momoka.items(), key=lambda kv: -kv[1])],
        "momoka_calls_subject": momoka_calls,
        "momoka_lines_to_subject": len([1 for _ in momoka_calls]) and sum(x["n"] for x in momoka_calls),
    }

    pc, pfirst = places(corpus, name)
    pr = PRON[spec["gender"]]
    manner = None
    if spec.get("manner_computed") or spec.get("manner_facts"):
        manner = []
        for label, pat, what in spec.get("manner_computed", []):
            rx = re.compile(pat)
            hits = [(i, t) for i, t in lines if rx.search(t)]
            bn = sum(1 for _, t in base["lines"] if rx.search(t))
            step = max(1, len(hits) // 2)
            manner.append({
                "text": "%s: %d of %d spoken lines (%.1f%%); the rest of the cast is at %.1f%%." % (
                    label[0].upper() + label[1:], len(hits), len(lines), len(hits) * 100 / len(lines), bn * 100 / len(base["lines"])),
                "kind": "computed", "pattern": pat, "n": len(hits), "of": len(lines),
                "receipts": [{"id": i, "anchor": rx.search(t).group(0)} for i, t in hits[::step][:2]]})
        manner += spec.get("manner_facts", [])
    return {
        "_note": "Light cast card (design 1.2). Mechanical: identity, address and relationships from the B0-B2 bible.json, speech from this subject's own spoken lines against the rest of the cast. Built by tools/koikano/build_cast_cards.py. Receipts are record ids (scene:line) with an anchor string that appears in that line; tools/koikano/check_world_spec.py verifies them. No age, grade, birthplace or parent is read or written.",
        "id": slug,
        "name": {"family": spec["family"], "given": name, "japanese": spec["family"] + name,
                 "reading_ja": spec["reading"], "reading_basis": spec["reading_basis"]},
        "identity": {"spoken_lines": ident["spoken_count"], "scenes": ident["scene_count"],
                     "route": "none: no route of %s own" % pr["poss"],
                     "gender": {"sex": pr["sex"], "pronouns": pr["label"], "fact": "%s is %s; refer to %s as %s." % (
                         name, pr["sex"], name, pr["label"]), "receipts": spec["gender_basis"]},
                     "scenes_with_momoka": with_momoka["scenes_together"]},
        "address": {"others_call_her_or_him": addressed_as, "she_or_he_calls_others": addresses},
        "speech": speech,
        **({"manner": manner} if manner else {}),
        "with_momoka": with_momoka,
        "places_by_lines": [{"place": p, "lines": n, "receipt": {"id": pfirst[p][0], "bg": pfirst[p][1]}} for p, n in pc.most_common(8)],
        "club": spec["club"],
        "holes": [
            "Age, grade, birthday, birthplace, family and appearance: the record gives none as words, and none is emitted.",
            "Reading of the given name, basis: %s." % spec["reading_basis"],
            "Gauge baselines: none measured.",
            "The record gives no timetable, home or route for this person; the week lives in characters/momoka/world/koikano_world.json and holds only receipted facts.",
        ] + (["Momoka's lines name %s %d time(s); the record gives Momoka few forms for %s." % (pr["obj"], sum(x["n"] for x in momoka_calls), pr["obj"])] if sum(x["n"] for x in momoka_calls) < 30 else []),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--bible-root", default=DEFAULT_BIBLES)
    ap.add_argument("--only")
    ap.add_argument("--out-root", default=os.path.join(ROOT, "characters"))
    args = ap.parse_args()
    # baseline: every other cast speaker except the protagonist
    pool = []
    for n in ("真優", "千奈", "アリス", "真里亜", "知紗", "ひかる"):
        pool += load_spoken(args.corpus, n)
    base = stats(pool)
    base["lines"] = pool
    for slug, spec in SUBJECTS.items():
        if args.only and slug != args.only:
            continue
        card = build(slug, spec, args, base)
        d = os.path.join(args.out_root, slug)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "card.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(card, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("card", slug, len(card["speech"]), "speech lines")


if __name__ == "__main__":
    main()
