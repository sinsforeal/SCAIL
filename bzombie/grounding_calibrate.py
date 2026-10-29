"""Calibration of bzombie.grounding against hand labels (grounding_calib.json).

python -m bzombie.grounding_calibrate
Prints precision and recall (bubble level: flagged vs labelled defect) for the
tuning set (planted + ginkgo + real 1-25) and the unseen half (real 26-50).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from . import grounding as g

CALIB = Path(__file__).with_name("grounding_calib.json")


def _prf(rows):
    tp = sum(1 for flag, lab in rows if flag and lab)
    fp = sum(1 for flag, lab in rows if flag and not lab)
    fn = sum(1 for flag, lab in rows if not flag and lab)
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    return {"tp": tp, "fp": fp, "fn": fn, "n": len(rows), "precision": round(p, 3), "recall": round(r, 3)}


def run_calibration(runs_dir=g.RUNS_DIR):
    cal = json.loads(CALIB.read_text(encoding="utf-8"))
    runs = {}

    def get(rid):
        if rid not in runs:
            runs[rid] = g.load_run(Path(runs_dir) / rid)
        return runs[rid]

    detail = {"ginkgo": [], "planted": [], "real": []}
    empty = {"bubbles": [], "his": [], "env": [], "world": []}
    for it in cal["ginkgo"]:
        run = get(it["run"])
        b = {"i": None, "ts": datetime.fromisoformat(it["ts"]), "text": it["text"]}
        r = g.check_bubble(b, run)
        detail["ginkgo"].append((r["flagged"], it["defect"], it["text"], r["anchors"]))
    for it in cal["planted"]:
        b = {"i": None, "ts": datetime(2026, 10, 27, 15, 0), "text": it["text"]}
        r = g.check_bubble(b, empty)
        detail["planted"].append((r["flagged"], 1, it["text"], r["anchors"]))
    for it in cal["real"]:
        run = get(it["run"])
        b = next(x for x in run["bubbles"] if x["i"] == it["i"])
        r = g.check_bubble(b, run)
        detail["real"].append((r["flagged"], it["defect"], b["text"], r["anchors"], it["n"]))
    tune = [d[:2] for d in detail["ginkgo"] + detail["planted"]] + [d[:2] for d in detail["real"] if d[4] <= 25]
    unseen = [d[:2] for d in detail["real"] if d[4] > 25]
    return {"tuning": _prf(tune), "unseen": _prf(unseen),
            "planted_recall": _prf([d[:2] for d in detail["planted"]]),
            "ginkgo": _prf([d[:2] for d in detail["ginkgo"]])}, detail


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    summ, detail = run_calibration()
    for k in ("ginkgo", "planted"):
        for flag, lab, text, anchors in detail[k]:
            print(f"{k} flag={int(flag)} label={lab} {text} {[(a['kind'], a['text'], a['status']) for a in anchors]}")
    for flag, lab, text, anchors, n in detail["real"]:
        if flag or lab:
            print(f"real#{n} flag={int(flag)} label={lab} {text} {[(a['kind'], a['text'], a['status']) for a in anchors]}")
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
