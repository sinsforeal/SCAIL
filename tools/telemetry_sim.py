"""Replay the telemetry feed through the phone pipeline and measure what survives.

The feed is rich and the digest is three sentences, and until this existed
there was no way to see where in between the information went. It replays the
real caps -- `phone.max_backlog_entries`, `max_entries_per_look`,
`max_raw_chars` -- over the whole feed as a series of looks, and reports what
reaches the model rather than what was collected.

No LLM: everything up to `llm.call("phone", ...)` is deterministic, and that is
the part worth measuring.

    python tools/telemetry_sim.py                 the whole feed
    python tools/telemetry_sim.py --last 40       the last 40 entries
    python tools/telemetry_sim.py --sample 2      print look #2's kept text

What to read. `truncated` is the share of formatted text thrown away by
`max_raw_chars`; it is cut from the front, so what is lost is the oldest and
not the least interesting. `noise` is the share of her budget spent on window
lines carrying no title -- a terminal repainting its own title once a second
produced one session per second, and 53% of every session ever recorded was
WindowsTerminal.exe. `browsing kept/lost` counts the lines that name a site,
which is the closest thing to a measure of whether the look was worth taking.
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger

logger.log = lambda m: None
logger.log_llm = lambda *a, **k: None

from config import Config
from sensors import telemetry_collector as tc

SITE = re.compile(r"\b[a-z0-9-]+\.(com|net|org|io|ai|co|tv|gg|dev|app|me|xyz|sh|fi)\b|Google Search|Search$", re.I)
WINDOW = re.compile(r"^\[\d\d:\d\d(?:-\d\d:\d\d)?\]\s+(\S+)\s+\(")


def profile(text):
    """What this block of context actually consists of."""
    lines = [l for l in text.splitlines() if l.strip()]
    windows = [l for l in lines if WINDOW.match(l)]
    # a window line with nothing after the duration is a bare app switch: it
    # says he had a window focused and nothing whatever about what he was doing
    bare = [l for l in windows if re.match(r"^\[[\d:\-]+\]\s+\S+\s+\([^)]*\)\s*$", l)]
    browsing = [l for l in lines if SITE.search(l)]
    procs = collections.Counter()
    for l in windows:
        m = WINDOW.match(l)
        if m:
            procs[m.group(1)] += 1
    return {"chars": len(text), "lines": len(lines), "windows": len(windows),
            "bare": len(bare), "bare_chars": sum(len(l) + 1 for l in bare),
            "browsing": len(browsing), "procs": procs}


def run(entries, cfg, look_times, sample=None, verbose=False):
    p = cfg.phone
    sv = cfg.sensor_view
    opts = {"gap_seconds": sv.image_window_gap_minutes * 60,
            "summarize_min": sv.image_window_summarize_min,
            "max_detailed": sv.image_context_max_detailed,
            "max_windows": sv.image_max_windows_per_look,
            "max_age_hours": 10 ** 6}   # the feed is replayed, so age is not the question
    # Driven by the times she actually looked, read off the digests table. A
    # fixed cadence would answer a different question: how much a look loses
    # depends entirely on how much has piled up behind it, and what piles up is
    # a fact about her schedule and his hours, not about the caps.
    looks = []
    n = 0
    queue = list(entries)
    for look_ts in look_times:
        pending = [e for e in queue if float(e.get("unix_time") or 0) <= look_ts]
        if not pending:
            continue
        n += 1
        batch = pending[-p.max_backlog_entries:] if len(pending) > p.max_backlog_entries else pending
        dropped_old = len(pending) - len(batch)
        batch = batch[: p.max_entries_per_look]
        eaten = set(id(e) for e in pending[:len(batch) + dropped_old])
        queue = [e for e in queue if id(e) not in eaten]
        merged = tc.merge_entries(batch)
        if not merged:
            continue
        raw = tc.format_telemetry_for_context(merged, opts, sv, None)
        kept = raw[-p.max_raw_chars:]
        full, cut = profile(raw), profile(kept)
        looks.append({"n": n, "ids": (batch[0]["id"], batch[-1]["id"]), "dropped_old": dropped_old,
                      "full": full, "kept": cut})
        if sample == n:
            print("=" * 92)
            print("LOOK %d, ids %d..%d -- exactly what the phone model would be handed" % (n, batch[0]["id"], batch[-1]["id"]))
            print("=" * 92)
            print(kept)
            print("=" * 92)
    if not looks:
        print("nothing to replay")
        return None

    print("%-5s %-12s %9s %9s %7s %7s %8s %8s" %
          ("look", "ids", "formatted", "kept", "trunc", "lines", "bare", "browsing"))
    for L in looks:
        f, k = L["full"], L["kept"]
        trunc = 100.0 * (f["chars"] - k["chars"]) / max(1, f["chars"])
        if verbose or len(looks) <= 30:
            print("%-5d %-12s %9s %9s %6.0f%% %7d %7d %4d/%-4d" %
                  (L["n"], "%d-%d" % L["ids"], f"{f['chars']:,}", f"{k['chars']:,}", trunc,
                   k["lines"], k["bare"], k["browsing"], f["browsing"] - k["browsing"]))

    tot_full = sum(L["full"]["chars"] for L in looks)
    tot_kept = sum(L["kept"]["chars"] for L in looks)
    tot_bare = sum(L["kept"]["bare_chars"] for L in looks)
    br_kept = sum(L["kept"]["browsing"] for L in looks)
    br_all = sum(L["full"]["browsing"] for L in looks)
    procs = collections.Counter()
    for L in looks:
        procs.update(L["kept"]["procs"])
    print()
    print("%d look(s) over %d entries" % (len(looks), len(entries)))
    print("  formatted            %12s chars" % f"{tot_full:,}")
    print("  actually read        %12s chars   (%.0f%% of it thrown away by max_raw_chars)"
          % (f"{tot_kept:,}", 100.0 * (tot_full - tot_kept) / max(1, tot_full)))
    print("  of what she reads:   %12s chars are bare window switches with no title  (%.0f%%)"
          % (f"{tot_bare:,}", 100.0 * tot_bare / max(1, tot_kept)))
    print("  browsing lines       %12s reached her, %s were formatted  (%.0f%% survived)"
          % (f"{br_kept:,}", f"{br_all:,}", 100.0 * br_kept / max(1, br_all)))
    print("  her budget goes to:  " + ", ".join(f"{k} {v}" for k, v in procs.most_common(6)))
    return {"formatted": tot_full, "read": tot_kept, "bare_chars": tot_bare,
            "browsing_kept": br_kept, "browsing_all": br_all, "looks": len(looks)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, default=0, help="only the last N feed entries")
    ap.add_argument("--sample", type=int, default=0, help="print this look's kept text")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    cfg = Config("config.json")
    path = cfg.sensors.telemetry_jsonl_path
    entries = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except ValueError:
                    pass
    if a.last:
        entries = entries[-a.last:]
    from store import Store
    looks = [float(d["ts"]) for d in Store(cfg.logging.db_path).recent_digests(500)]
    print("replaying %d feed entries through the real caps "
          "(backlog %d, per look %d, raw chars %s), driven by her %d real looks\n"
          % (len(entries), cfg.phone.max_backlog_entries, cfg.phone.max_entries_per_look,
             f"{cfg.phone.max_raw_chars:,}", len(looks)))
    run(entries, cfg, looks, sample=a.sample or None, verbose=a.verbose)


if __name__ == "__main__":
    main()
