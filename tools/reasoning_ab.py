"""Re-run recorded voice-role calls with reasoning off, medium and high.

The point is to see what thinking changes in a role that writes somebody's
speech, on the exact bytes the bot sent. Every case names a run directory (or
its zip) and a line number in `llm_calls.jsonl`; the `messages` from that
record go back through the bot's own client, so the payload -- provider, host
order, temperature, the JSON re-ask -- is what production sends. The only
difference between conditions is `thinking` and `effort` on the role's model
entry, set on the in-memory config of an App built over a COPY of the save;
nothing on disk is touched.

    python tools/reasoning_ab.py --out data/retired/<ts>_reasoning_ab

The answers land in `answers.json` beside the report. Costs cents.
"""
import argparse
import json
import os
import sys
import tempfile
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# tag, source run (dir or .zip), 1-based line in llm_calls.jsonl, one line on why
CASES = [
    ("turn_rena_repeat", "logs/2026-09-03_07-54-01.zip", 26,
     "group chat, Rena's third turn; the prompt lists her own three bubbles and "
     "forbids repeating them"),
    ("turn_hinako_probe", "logs/2026-09-03_07-54-01.zip", 2,
     "group chat, Hinako answering Tomoe's pointed 'do you only want to go with me?'"),
    ("turn_rena_latest", "logs/2026-09-03_23-27-22", 29,
     "group chat, Rena settling a purikura date and asking about tomorrow's obi"),
    ("reply_group_repeat", "logs/2026-09-03_07-54-01.zip", 27,
     "group chat, Tomoe's third reply in the same thread"),
    ("reply_group_carrying", "logs/2026-09-03_23-27-22", 18,
     "group chat, Tomoe replying while carrying a rumination about Aya's unread message"),
    ("reply_inperson_mother", "logs/2026-09-03_18-19-30.zip", 1,
     "in person with her mother; the original answer did not parse as JSON"),
]

CONDITIONS = [("off", False, None), ("medium", True, "medium"), ("high", True, "high")]


def record(src, line_no):
    path = os.path.join(ROOT, src)
    if path.endswith(".zip"):
        z = zipfile.ZipFile(path)
        name = [n for n in z.namelist() if n.endswith("llm_calls.jsonl")][0]
        fh = z.open(name)
    else:
        fh = open(os.path.join(path, "llm_calls.jsonl"), "rb")
    for i, line in enumerate(fh, 1):
        if i == line_no:
            return json.loads(line.decode("utf-8"))
    raise SystemExit(f"no line {line_no} in {src}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="", help="comma-separated case tags")
    args = ap.parse_args()
    out_dir = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    os.makedirs(out_dir, exist_ok=True)

    cases = [c for c in CASES if not args.only or c[0] in args.only.split(",")]

    from tools import harness
    # per-process, so two of these can run side by side
    tmp = os.path.join(tempfile.gettempdir(), f"reasoning_ab_{os.getpid()}.db")
    app = harness.build_on(tmp)

    # every attempt's receipt, including a JSON re-ask
    attempts = []
    inner = app.llm.call

    def wrapped(role, messages, max_tokens=None, **kw):
        text = inner(role, messages, max_tokens, **kw)
        attempts.append({"usage": dict(app.llm.last_usage or {}),
                         "seconds": round(app.llm._last_dt, 2),
                         "chars": len(text or "")})
        return text
    app.llm.call = wrapped

    results = []
    for tag, src, line_no, why in cases:
        rec = record(src, line_no)
        role = rec["role"]
        entry = app.config.raw["models"][role]
        base = dict(entry)
        row = {"tag": tag, "role": role, "src": src, "line": line_no, "why": why,
               "original": {"content": rec.get("content"), "usage": rec.get("usage"),
                            "seconds": rec.get("seconds"), "wall": rec.get("wall"),
                            "served_by": rec.get("served_by")},
               "runs": {}}
        for cond, thinking, effort in CONDITIONS:
            entry.clear()
            entry.update(base)
            entry["thinking"] = thinking
            if effort:
                entry["effort"] = effort
            del attempts[:]
            t0 = time.time()
            data, raw = app.llm.call_json(role, rec["messages"])
            wall = round(time.time() - t0, 2)
            row["runs"][cond] = {
                "data": data, "raw": raw, "wall": wall, "attempts": list(attempts),
                "reasoning_tokens": sum(int(((a["usage"].get("completion_tokens_details") or {})
                                             or {}).get("reasoning_tokens") or 0) for a in attempts),
                "completion_tokens": sum(int(a["usage"].get("completion_tokens") or 0) for a in attempts),
                "prompt_tokens": sum(int(a["usage"].get("prompt_tokens") or 0) for a in attempts),
                "cost": round(sum(float(a["usage"].get("cost") or 0) for a in attempts), 6),
                "n_attempts": len(attempts),
            }
            r = row["runs"][cond]
            print(f"{tag:22s} {role:11s} {cond:6s} {wall:6.1f}s "
                  f"think={r['reasoning_tokens']:5d} out={r['completion_tokens']:5d} "
                  f"${r['cost']:.5f} attempts={r['n_attempts']}", flush=True)
        entry.clear()
        entry.update(base)
        results.append(row)

    with open(os.path.join(out_dir, "answers.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    total = sum(r["runs"][c]["cost"] for r in results for c, _, _ in CONDITIONS if c in r["runs"])
    print(f"\n{len(results)} cases x {len(CONDITIONS)} conditions; ${total:.4f}")
    print(os.path.join(out_dir, "answers.json"))


if __name__ == "__main__":
    main()
