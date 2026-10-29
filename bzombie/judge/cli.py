"""python -m bzombie.judge calibrate | match | splice. Output is ASCII json so a cp932 console never chokes."""
from __future__ import annotations

import argparse
import json
import sys

from . import runner


def _list(v):
    out = []
    for x in v or []:
        out += [y for y in x.split(",") if y]
    return out or None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m bzombie.judge")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--workers", type=int, default=4, help="parallel judge calls")
        p.add_argument("--claude-cap-usd", type=float, default=10.0)
        p.add_argument("--criteria", nargs="*", help="criterion ids (space or comma separated)")

    c = sub.add_parser("calibrate")
    common(c)
    c.add_argument("--lang", choices=["ja", "en"])
    c.add_argument("--ids", nargs="*", help="only these defects.json entry ids")
    c.add_argument("--stamp", help="resume or name a calibration folder")
    c.add_argument("--defects", help="alternative defects.json")
    m = sub.add_parser("match")
    common(m)
    m.add_argument("--a", required=True, help="run_id or run_id~branch_id")
    m.add_argument("--b", required=True)
    m.add_argument("--character", required=True, choices=sorted(runner.LANG))
    m.add_argument("--match-id")
    m.add_argument("--seed", type=int)
    s = sub.add_parser("splice")
    common(s)
    s.add_argument("--run", required=True, help="a finished run_id or run_id~branch_id")
    s.add_argument("--per-criterion", type=int, default=2)
    s.add_argument("--ids", nargs="*")
    s.add_argument("--seed", type=int)
    s.add_argument("--stamp")
    s.add_argument("--defects")
    a = ap.parse_args(argv)
    crit = _list(a.criteria)
    if a.cmd == "calibrate":
        code, out = runner.calibrate(crit, a.lang, _list(a.ids), a.stamp, a.workers, a.claude_cap_usd, a.defects)
    elif a.cmd == "match":
        code, out = runner.match(a.a, a.b, a.character, a.match_id, a.seed, crit, a.workers, a.claude_cap_usd)
    else:
        code, out = runner.splice(a.run, a.per_criterion, crit, _list(a.ids), a.seed, a.stamp, a.workers,
                                  a.claude_cap_usd, a.defects)
    if out:
        print(json.dumps({"match_id": out["match_id"], "summary": out["summary"], "calibration": out["calibration"]
                          if a.cmd != "match" else len(out["calibration"])}, ensure_ascii=True)[:6000])
    return code


if __name__ == "__main__":
    sys.exit(main())
