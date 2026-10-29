#!/usr/bin/env python3
"""Cross-subject control for the koikano bibles (CM 4.6: the cheapest strong test).

For each subject S two detectors are scored on every subject T's spoken lines:

  rules       the gate's Bernoulli Naive Bayes detector on S's own rule markers
              (tools/koikano/markers/<slug>.json; 百花 and --default-markers use the default 13),
              S's marker rates against the pooled rates of the other four subjects
              (so it is S's rule set vs "not S").  Marker counts differ per subject.
              Cell = share of T's lines the detector calls S (score >= 0).
  mechanisms  S's B3 mechanisms (kb.mechanism_specs(S), so it reads tools/koikano/b3/<slug>.py
              when present; offers_self is skipped for everyone but 百花).
              Cell = share of T's lines matching at least one of S's mechanisms.

Pass rule, per subject and per detector: the own cell exceeds every other subject's cell by
margin m, where m = max(0.05, 2 * sqrt(p1(1-p1)/n1 + p2(1-p2)/n2)).  That is two standard
errors of the difference of two independent rates (about 95%), so a gap inside m could be
sampling noise; the 0.05 floor keeps a tiny-n pair from passing on a hair.

Default: S's rates fitted on all of S's lines and scored on all of S's lines (the shipped,
full-corpus bible).  --leak-free: rates fitted on S's build block, own cell scored on S's
holdout scenes only (kb.select_holdout, the gate's selection).  Other subjects' lines are
always all their spoken lines.

    python tools/koikano/cross_control.py --out F:\\temp\\gate_split\\cross_full.json
    python tools/koikano/cross_control.py --leak-free --out F:\\temp\\gate_split\\cross_leakfree.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import koikano_bible as kb
import koikano_bible_gate as g
import markers_io

SUBJECTS = ["百花", "真優", "千奈", "アリス", "真里亜"]


def margin(p1, n1, p2, n2):
    return max(0.05, 2 * math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2))


def self_form(name, texts):
    return max([(f, sum(t.count(f) for t in texts)) for f in [name] + kb.FIRST_PERSON_FORMS],
               key=lambda fc: fc[1])[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default=kb.DEFAULT_CORPUS)
    ap.add_argument("--leak-free", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--default-markers", action="store_true",
                    help="score every subject on the gate's default 13 markers (the old matrix)")
    a =ap.parse_args(argv)

    records = list(kb.read_jsonl(os.path.join(a.corpus, "koikano_work", "game_logic.jsonl")))
    bands = kb.phase_bands(list(dict.fromkeys(r["scene"] for r in records)))
    talk = [r for r in records if r["kind"] == "@Talk" and r["file"] != "macro.ks" and r["raw_name"] != kb.INNER_MARKER]
    lines = {s: [r for r in talk if r["speaker"] == s] for s in SUBJECTS}
    hold = {s: set(kb.select_holdout(records, s, bands)) for s in SUBJECTS}

    result = {"mode": "leak-free" if a.leak_free else "full-corpus", "subjects": SUBJECTS,
              "n_lines": {s: len(lines[s]) for s in SUBJECTS}, "rules": {}, "mechanisms": {}, "pass": {}}
    for kind in ("rules", "mechanisms"):
        result[kind] = {s: {} for s in SUBJECTS}
    for S in SUBJECTS:
        own_fit = [r for r in lines[S] if r["scene"] not in hold[S]] if a.leak_free else lines[S]
        own_eval = [r for r in lines[S] if r["scene"] in hold[S]] if a.leak_free else lines[S]
        evals = {T: (own_eval if T == S else lines[T]) for T in SUBJECTS}
        others = [r for T in SUBJECTS if T != S for r in lines[T]]
        g.SELF_FORM = self_form(S, [r["text"] for r in own_fit])
        own_markers = {} if a.default_markers else markers_io.load(kb.SLUGS[S])
        g.RULE_MARKERS.clear()
        for i, pat in own_markers.items():
            g.RULE_MARKERS["rule%02d" % i] = pat
        ph = g.marker_rates(own_fit)
        pc = g.marker_rates(others)
        specs = [x for x in kb.mechanism_specs(S) if not (x.get("matcher") == "offers_self" and S != kb.DEFAULT_CHAR)]
        per_mech = {x["key"]: {} for x in specs}
        for T in SUBJECTS:
            rows = evals[T]
            n = len(rows)
            rh = sum(1 for r in rows if g.nb_score(r["text"], ph, pc) >= 0)
            hits = [[g.mech_matches(x, r["text"]) for x in specs] for r in rows]
            mh = sum(1 for h in hits if any(h))
            result["rules"][S][T] = {"hits": rh, "n": n, "rate": round(rh / n, 4)}
            result["mechanisms"][S][T] = {"hits": mh, "n": n, "rate": round(mh / n, 4)}
            for i, x in enumerate(specs):
                c = sum(1 for h in hits if h[i])
                per_mech[x["key"]][T] = round(c / n, 4)
        result["mechanisms"][S]["_per_mechanism"] = per_mech
        result["mechanisms"][S]["_own_beats_all_others"] = sum(
            1 for k, v in per_mech.items() if all(v[S] > v[T] for T in SUBJECTS if T != S))
        result["mechanisms"][S]["_n_mechanisms"] = len(specs)
        result["rules"][S]["_self_form"] = g.SELF_FORM
        result["rules"][S]["_n_markers"] = len(own_markers) or len(g.NB_FEATURES)
        result["rules"][S]["_marker_source"] = "own (markers/%s.json)" % kb.SLUGS[S] if own_markers else "default 13"
        for kind in ("rules", "mechanisms"):
            row = result[kind][S]
            own = row[S]
            gaps = {}
            for T in SUBJECTS:
                if T == S:
                    continue
                m = margin(own["rate"], own["n"], row[T]["rate"], row[T]["n"])
                gaps[T] = {"gap": round(own["rate"] - row[T]["rate"], 4), "margin": round(m, 4),
                           "ok": own["rate"] - row[T]["rate"] >= m}
            row["_gaps"] = gaps
            result["pass"].setdefault(kind, {})[S] = all(v["ok"] for v in gaps.values())

    for kind in ("rules", "mechanisms"):
        print("%s (%s): rows = subject's detector, columns = whose lines; own cell marked *" % (kind, result["mode"]))
        print("  %-8s" % "" + "".join("%-9s" % t for t in SUBJECTS) + "pass")
        for S in SUBJECTS:
            cells = "".join("%-9s" % (("%.3f" % result[kind][S][T]["rate"]) + ("*" if T == S else "")) for T in SUBJECTS)
            print("  %-8s%s%s" % (S, cells, "PASS" if result["pass"][kind][S] else "FAIL"))
        print("  subjects passing: %d of %d" % (sum(result["pass"][kind].values()), len(SUBJECTS)))
    for S in SUBJECTS:
        m = result["mechanisms"][S]
        print("%s mechanisms with own rate above every other subject's: %d of %d" % (S, m["_own_beats_all_others"], m["_n_mechanisms"]))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
