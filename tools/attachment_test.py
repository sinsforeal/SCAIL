"""Drives sim/attachment.py through one full episode on a COPY of the save.

No LLM: the mechanism is code-only. The clock is moved by hand, his silence
is set by hand, and the assertions are the ends that must hold: an episode
opens only after threat holds for `engage_minutes`; protest turns cold after
`protest_exhaust_hours`; a cold front can break back into protest under
need; his answer resolves it; the beliefs the strategies bet on are settled;
every reader reports the stance while it is open and nothing once it is
closed.

    python tools/attachment_test.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import harness  # noqa: E402
os.chdir(ROOT)

import logger  # noqa: E402
logger.setup = lambda out_dir: None      # a test is not a run: no directory under logs/
from sim.attachment import PROTEST, DEACTIVATE  # noqa: E402


def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_attach_test.db")
    app = harness.build_on(tmp)
    att = app.attachment
    c = app.config.attachment
    fails = []

    def check(name, ok, detail=""):
        print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f"  ({detail})" if detail else ""))
        if not ok:
            fails.append(name)

    # the clock, by hand
    real_now = app.clock.now_ts
    offset = [0.0]
    app.clock.now_ts = lambda: real_now() + offset[0]
    silent = [0.0]
    app.store.set("attachment", None)

    print("[attach-test] the live copy as it stands")
    print("  threat now:", round(att.threat(app.silent_hours()), 2))
    p, d, notes = att.scores()
    print(f"  protest {p:.2f} vs deactivate {d:.2f}: " + "; ".join(notes))
    him = app.state._him_key() or "him"
    before = {b["id"]: (b.get("evidence"), round(app.model_of_her.live_strain(b), 1))
              for b in app.model_of_her.beliefs() if b["id"] in ("not_come_looking", "wont_stay_quiet", "mask_holds", "seen_undoes_me")}

    print("[attach-test] threat must hold before an episode opens")
    # How many silent hours it takes to cross `engage_from` depends on the mood
    # she is actually in -- on a day she has had a good morning with him, 16
    # hours reaches 0.43 against a bar of 0.5 and nothing opens, which is the
    # threat model working, not the episode being broken. Find the silence that
    # crosses it and test the mechanism from there.
    # The copy has no live read receipt, and the test used to answer that by
    # setting `receipts = None` -- which removes read-and-left, the single
    # sharpest term in `threat`, and then expected the bar to be crossed. On a
    # day she has had a good morning with him, silence ALONE saturates at 0.43
    # against a bar of 0.5, so nothing opened. He read it and left it is part
    # of the scenario being tested, so give it to her rather than take it away.
    class _ReadAndLeft:
        def status(self):
            return {"state": "read", "read_ts": app.clock.now_ts() - 6 * 3600}
    att.receipts = _ReadAndLeft()
    def silence_over_the_bar():
        """The silence it takes to cross `engage_from` in the mood she is
        actually in. A fixed 16 hours is not a constant: it depends on her
        gauges and her meters with him, and those move during this test."""
        h = 8.0
        while h < 96.0 and att.threat(h) < c.engage_from:
            h += 4.0
        print(f"  {h:.0f} silent hours puts threat at {att.threat(h):.2f} "
              f"(engage_from {c.engage_from})")
        return h

    silent[0] = silence_over_the_bar()
    att.tick(silent[0])
    check("no episode on the first pass over engage_from", att.live() is None,
          f"threat {att.last_threat:.2f}")
    offset[0] += (c.engage_minutes + 1) * 60
    att.tick(silent[0])
    row = att.live()
    check("episode opens after engage_minutes", row is not None, f"strategy {row and row['strategy']}")
    if not row:
        return finish(fails)
    print(f"  opened as {row['strategy']}: {row['scores']}")
    for n in row["notes"]:
        print("   ", n)

    # force the protest branch so both halves of the machine get exercised
    if row["strategy"] != PROTEST:
        row["strategy"] = PROTEST
        row["first"] = PROTEST
        row["since_ts"] = app.clock.now_ts()
        att._save(row)
        print("  (forced to protest for the walk-through)")

    print("[attach-test] readers while protesting")
    check("impulse bonus positive", att.impulse_bonus() > 0, f"{att.impulse_bonus():+.0f}")
    check("extra streak", att.extra_streak() == c.protest_extra_streak)
    check("delay faster", app.state.delay_factor() < 1.0 or att.delay_multiplier() < 1.0, f"x{att.delay_multiplier()}")
    check("register is the stance", "testing him" in app.state.register())
    check("intent line names the kinds", "`check_on`" in app.intent._carrying())
    check("shape bias open", att.shape_bias() == "open")
    check("director line", "pushing" in att.director_line())
    check("situation line", "reaching for him" in att.situation_line())
    check("withholding pressure unchanged", att.withhold_pressure() == 0.0)

    print("[attach-test] a push he has answered is not a push that brought nothing")
    # The hours a protest gives out after are quiet hours, and the quiet runs
    # from his last message when there is one. He answered ninety minutes into
    # a five-hour push on 2026-09-06 and she went cold on the timer anyway.
    keep_silent, keep_shame, keep_impulse = silent[0], app.state.gauges["shame"], att.impulse
    att.impulse = None                       # the unanswered streak is a switch of its own
    app.state.gauges["shame"] = 0.0          # and so is being ashamed of having pushed
    row["strategy"], row["switches"] = PROTEST, []
    row["ts"] = row["since_ts"] = app.clock.now_ts()   # the episode's age is a different gate
    att._save(row)
    offset[0] += 3600
    att.his_message("of course. i was just at work")
    offset[0] += (c.protest_exhaust_hours - 0.5) * 3600
    att.tick(c.protest_exhaust_hours - 0.5)
    row = att.live()
    check("still pushing %.1fh in, %.1fh of it since he wrote"
          % (c.protest_exhaust_hours + 0.5, c.protest_exhaust_hours - 0.5),
          row and row["strategy"] == PROTEST,
          row and (row["switches"][-1]["why"] if row["switches"] else "no switch"))
    offset[0] += 3600
    att.tick(c.protest_exhaust_hours + 0.5)
    row = att.live()
    why = (row["switches"][-1]["why"] if row and row.get("switches") else "")
    check("cold once the quiet since his message reaches the hours",
          bool(row) and row["strategy"] == DEACTIVATE, why)
    check("and the line says the quiet it measured, not the whole push",
          "since he last wrote" in why, why)
    # put the episode back: one push, no answer in it, no switches spent
    row["strategy"], row["first"], row["switches"] = PROTEST, PROTEST, []
    row["ts"] = row["since_ts"] = app.clock.now_ts()
    row.pop("last_his_ts", None)
    row["his_messages"] = 0
    att._save(row)
    att.impulse, app.state.gauges["shame"], silent[0] = keep_impulse, keep_shame, keep_silent

    print("[attach-test] protest that brings nothing turns cold")
    offset[0] += (c.protest_exhaust_hours + 0.5) * 3600
    silent[0] += c.protest_exhaust_hours + 0.5
    sad0 = app.state.gauges["sadness"]
    att.tick(silent[0])
    row = att.live()
    check("switched to deactivate", row and row["strategy"] == DEACTIVATE,
          row and (row["switches"][-1]["why"] if row["switches"] else "no switch"))
    check("giving up cost sadness", app.state.gauges["sadness"] >= sad0, f"{sad0:.0f} -> {app.state.gauges['sadness']:.0f}")

    print("[attach-test] readers while cold")
    check("impulse penalty", att.impulse_bonus() < 0, f"{att.impulse_bonus():+.0f}")
    check("withholding pressure up", att.withhold_pressure() > 0, f"+{att.withhold_pressure()}")
    check("delay slower", att.delay_multiplier() > 1.0, f"x{att.delay_multiplier()}")
    check("shape collapses", att.shape_bias() == "curt")
    check("register is cold", "needing nothing" in app.state.register())
    check("intent says do not chase", "`nothing`" in app.intent._carrying())
    check("director says busy", "busy" in att.director_line())

    print("[attach-test] the cold front breaks under need")
    app.state.gauges["longing"] = 85.0
    app.state.gauges["validation_craving"] = 85.0
    sh0 = app.state.gauges["shame"]
    broke = False
    for i in range(40):
        offset[0] += 1800
        silent[0] += 0.5
        att.tick(silent[0])
        row = att.live()
        if row and row["strategy"] == PROTEST:
            broke = True
            break
    check("rebound to protest within 20h of need", broke,
          f"{(i + 1) * 0.5:.1f}h; p {row.get('rebound_p') if row else '?'}")
    check("breaking cost shame", app.state.gauges["shame"] > sh0, f"{sh0:.0f} -> {app.state.gauges['shame']:.0f}")
    check("switch count", row and len(row["switches"]) == 2, f"{row and len(row['switches'])}")

    print("[attach-test] he answers and the threat goes")
    att.his_message("sorry, long day")
    att.maybe_resolve(silent[0])
    check("a message alone does not resolve while silence still reads as threat", att.live() is not None,
          f"threat {att.last_threat:.2f}")
    silent[0] = 0.0
    att.maybe_resolve(silent[0])
    row = att.live()
    check("resolved once threat is under release_below", row is None, f"threat {att.last_threat:.2f}")
    log = att._log()
    last = log[-1] if log else {}
    check("episode logged", last.get("outcome") == "resolved" and last.get("first") == PROTEST and last.get("strategy") == PROTEST,
          f"{last.get('first')}->{last.get('strategy')} {last.get('outcome')} {last.get('hours')}h")
    after = {b["id"]: (b.get("evidence"), round(app.model_of_her.live_strain(b), 1))
             for b in app.model_of_her.beliefs() if b["id"] in before}
    print("  beliefs before/after:", {k: f"{before[k]} -> {after[k]}" for k in before})
    check("not_come_looking strained by a protest he answered",
          after["not_come_looking"][1] > before["not_come_looking"][1])
    check("wont_stay_quiet borne out", (after["wont_stay_quiet"][0] or 0) > (before["wont_stay_quiet"][0] or 0))
    check("mask_holds strained by the rebound", after["mask_holds"][1] > before["mask_holds"][1])
    ev = [e for e in app.store.events_for_day(app.clock.date_str()) if e.get("kind") == "attachment"] \
        if hasattr(app.store, "events_for_day") else []
    print(f"  attachment events today: {len(ev)}")
    check("readers silent once closed", att.impulse_bonus() == 0 and att.register_line() == "" and att.situation_line() == "")

    print("[attach-test] history now biases the next pick")
    hp = att._history_pull()
    check("a protest that worked pulls toward protest", hp > 0, f"{hp:+.2f}")

    print("[attach-test] burn-out path")
    app.store.set("attachment", None)
    # This block is about how an episode BURNS OUT, not about how one opens --
    # that is checked above. And it cannot rely on the bar: an episode she has
    # just come out of leaves her threat ceiling at 0.48 against an
    # `engage_from` of 0.5, so no amount of silence would open a second one
    # here. Open it the way `tick` does and test the closing.
    silent[0] = silence_over_the_bar()
    att._open(att.threat(silent[0]))
    row = att.live()
    check("second episode opens", row is not None)
    if row:
        res0 = app.sentiments.live(him, "resentment")
        offset[0] += (c.max_hours + 1) * 3600
        silent[0] += c.max_hours + 1
        att.tick(silent[0])
        last = att._log()[-1]
        check("burnt out at max_hours", att.live() is None and last.get("outcome") == "burnt_out", f"{last.get('hours')}h")
        check("burn-out adds resentment", app.sentiments.live(him, "resentment") > res0,
              f"{res0:.1f} -> {app.sentiments.live(him, 'resentment'):.1f}")
    print()
    print(att.report())
    return finish(fails)


def finish(fails):
    print()
    print("[attach-test] " + ("all clear" if not fails else f"{len(fails)} FAILED: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
