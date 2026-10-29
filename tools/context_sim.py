"""Rewind her clock over the record and watch the thread compact under a small target.

The verbatim span is seven days and the cards reach back thirty, and at the
live target (`context.target_tokens`, the one budget over her prompt) the
verbatim span never has to shrink, so the shrinking would never be seen to
work on the live bot. This builds the App on a COPY of a save, pins the clock to a start
time in the past, hides everything after it, and steps forward: at every step
the thread is built as a reply would build it and measured; at every midnight
of her clock the day that ended is compiled into cards (the card call only by
default; `--full-compile` runs the whole timeline compile too); and the two
things that matter are printed as they happen -- where the verbatim cut sits
and how many tokens the history holds, and whether the head of the thread
changed between one build and the next (a cache miss) or only its tail grew.
At the end a few recall probes are run against the cards.

    python tools/context_sim.py --config config.json --db data/world.db --budget 6000 \
        --start "2026-08-29 06:00" --end "2026-09-04 10:00" --step 180 \
        --probe "remember the yukata" --probe "浴衣のこと"

Spends model calls: one `episode_cards` call per simulated day (flash), and the
compile per day with `--full-compile`. Never points at a live save: the db is
copied first (tools/harness.build_on).
"""
import argparse
import datetime
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

import harness  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--db", default="data/world.db")
    ap.add_argument("--budget", type=int, default=30000,
                    help="context.target_tokens for the run: the verbatim span shrinks toward "
                         "thread.verbatim_min_hours when the verbatim days plus the cards do not fit what is "
                         "left of it after the rest of the prompt")
    ap.add_argument("--start", required=True, help="her clock, 'YYYY-MM-DD HH:MM'")
    ap.add_argument("--end", default="", help="her clock; default now")
    ap.add_argument("--step", type=int, default=180, help="minutes per step")
    ap.add_argument("--probe", action="append", default=[], help="a recall cue to run at the end (repeatable)")
    ap.add_argument("--full-compile", action="store_true", help="run the whole timeline compile per day, not only the cards")
    ap.add_argument("--no-model", action="store_true", help="no model calls: cards are not written, the fallback recap lines show")
    ap.add_argument("--keep-cards", action="store_true", help="keep the copy's existing cards instead of clearing them first")
    a = ap.parse_args()

    tmp = os.path.join(tempfile.gettempdir(), f"context_sim_{os.path.basename(a.db)}")
    app = harness.build_on(tmp, a.config, a.db)
    if a.no_model:
        harness.refuse_model(app)
    # the target under test, in the raw dict and the attribute view both
    app.config.raw["context"]["target_tokens"] = a.budget
    try:
        app.config.context.target_tokens = a.budget
    except Exception:
        pass
    last = app.store.get("context_last") or {}
    print(f"target: {app.config.context.target_tokens} tokens; the rest of the prompt at the last call "
          f"{int(last.get('system', 0) or 0) + int(last.get('carried', 0) or 0) + int(last.get('situation', 0) or 0)}; "
          f"ratio {app.memory.ratio():.2f} chars/token")

    tz = app.clock.char_tz
    start = datetime.datetime.strptime(a.start, "%Y-%m-%d %H:%M").replace(tzinfo=tz).timestamp()
    end = datetime.datetime.strptime(a.end, "%Y-%m-%d %H:%M").replace(tzinfo=tz).timestamp() if a.end else datetime.datetime.now(tz).timestamp()
    state = {"now": start}
    app.clock.now_ts = lambda: state["now"]

    app.store.set("thread_window", None)
    if not a.keep_cards:
        with app.store.lock:
            app.store.conn.execute("DELETE FROM episodes")
            app.store.conn.execute("DELETE FROM embeddings WHERE kind='episode'")
            app.store.conn.commit()

    def compile_day(date_str):
        if a.no_model:
            return "no model"
        if a.full_compile:
            from sim import timeline
            timeline.compile_day(app.config, app.llm, app.store, app.clock, date_str, app.state, app.records, app.diet,
                                 app.memory, app.goals, app.self_memory, app.model_of_her,
                                 ledger=getattr(app, "ledger", None), orbit=getattr(app, "orbit", None),
                                 episodes=app.episodes)
            return "compiled"
        n = app.episodes.write(date_str)
        return f"{n} card(s)"

    prev = None
    last_date = None
    rows = []
    head_changes = 0
    steps = 0
    t = start
    while t <= end:
        state["now"] = t
        date = app.clock.date_str(t)
        note = ""
        if last_date is not None and date != last_date:
            note = f"compile {last_date}: {compile_day(last_date)}"
        hist = app.thread.build(now_ts=t)
        toks = sum(app.memory.tokens(m["content"]) for m in hist)
        cards = sum(m["content"].count("(as you remember it)") for m in hist)
        win = app.store.get("thread_window") or {}
        vf = (app.clock.to_char(float(win.get("verbatim_from", t))).strftime("%a %d %b")
              + f" +{win.get('card_days', 0)}c") if win else "?"
        change = "first"
        if prev is not None:
            k = 0
            while k < min(len(prev), len(hist)) and prev[k] == hist[k]:
                k += 1
            if k >= len(prev) - 1:
                change = "tail" if len(hist) != len(prev) or k < len(hist) else "same"
            else:
                change = f"HEAD@{k}/{len(prev)}"
                head_changes += 1
        steps += 1
        rows.append((date, app.clock.hm(t), len(hist), toks, cards, vf, change, note))
        if change.startswith("HEAD") or note or prev is None or steps % 8 == 0:
            print(f"{date} {app.clock.hm(t)}  msgs {len(hist):4d}  ~{toks:6d} tok  cards {cards:3d}  verbatim from {vf}  {change:12s} {note}")
        prev = hist
        last_date = date
        t += a.step * 60

    print(f"\n{steps} builds; the head of the thread changed {head_changes} time(s)"
          f" ({'once a day at most is the design' if head_changes <= len({r[0] for r in rows}) else 'MORE THAN ONCE A DAY: look at the HEAD rows'})")
    print("\nper day (last build of the day): msgs, tokens, cards in the thread, "
          "verbatim from (+N c = days riding as cards)")
    seen = {}
    for r in rows:
        seen[r[0]] = r
    for d, r in seen.items():
        print(f"  {d}  msgs {r[2]:4d}  ~{r[3]:6d} tok  cards {r[4]:3d}  verbatim from {r[5]}")

    print()
    print(app.episodes.report(n=3))
    if a.probe:
        print("\nrecall probes (score, kind, when, text):")
        for q in a.probe:
            hits = app.recall._search(q)
            print(f"  '{q}':")
            for sc, kind, when, body, ov in hits[:5]:
                print(f"    {sc:5.2f} {kind:8s} {when[:34]:34s} {body[:90].replace(chr(10), ' | ')}")
    # what she carries rides whole; this is only its size
    from sim.recall import moment_cue
    cue = moment_cue(app.store, his_text=(a.probe[0] if a.probe else ""))
    app.persona._system(cue_text=cue)
    carried = app.persona.carried_for()
    print(f"\nwhat she carries: ~{app.memory.tokens(carried)} tok, {len(carried.splitlines())} lines (rides whole)")

    if prev:
        print("\nthe thread's head and tail at the end:")
        for m in prev[:2] + prev[-2:]:
            print(f"  {m['role']:9s} {m['content'][:220].replace(chr(10), ' | ')}")


if __name__ == "__main__":
    main()
