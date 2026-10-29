"""Not answering on purpose, and what happens to his message afterwards.

    python tools/withhold_test.py

On a COPY of the save, with the one call that decides stubbed and the clock
moved by hand. What it drives:

  a `silence` consumes his message while she holds it -- it is marked read
  and her reply queue does not have it;

  the hold runs out with him still quiet and the message goes back into the
  queue, once, so the pick and her reply plan are asked about it again;

  building the App again on the same file -- what a restart does -- does not
  put it back a second time, and neither does another pass of the tick;

  a hold he wrote into, and a hold he broke, hand nothing back: the newer
  message is already in front of her, and a message that ended the hold is
  not one she was silent on.
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
logger.log = lambda m, to_console=True: print("   log:", m[:140])

FAILS = []


def check(label, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILS.append(label)
    return bool(ok)


def _say(store, clock, role, text, ts, read_ts=None):
    with store.lock:
        store.conn.execute("INSERT INTO messages(ts,date,role,text,read_ts) VALUES(?,?,?,?,?)",
                           (ts, clock.date_str(ts), role, text, read_ts))
        store.conn.commit()
        return store.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _silence(app, minutes, why="he can sit with it"):
    """The decision, with the one call that makes it stubbed."""
    real = app.llm.call_json
    app.llm.call_json = lambda role, messages, max_tokens=None: (
        ({"choice": "silence", "minutes": minutes, "why": why, "breaks_if": "if he says sorry"}, "")
        if role == "withhold" else real(role, messages, max_tokens))
    try:
        row = app.withholding.decide(app.store.unread_user_messages(), {"location": "her room"})
    finally:
        app.llm.call_json = real
    # what `App.maybe_reply` does with a silence: he sees it read and nothing
    # after it (scail.py, the withholding gate)
    if row:
        for m in app.store.unread_user_messages():
            app.store.mark_read(m["id"], app.clock.now_ts())
    return row


def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_withhold_test.db")
    app = harness.build_on(tmp)
    store, wh = app.store, app.withholding
    real_now = app.clock.now_ts
    offset = [0.0]
    app.clock.now_ts = lambda: real_now() + offset[0]
    now = app.clock.now_ts()

    # a clean board: nothing of his left unread from the save this was copied
    # from, and no hold running
    for m in store.unread_user_messages():
        store.mark_read(m["id"], now - 7200)
    store.set("withholding", None)
    store.set("withholding_handed_back", [])
    check("silence_hands_back is on", app.config.withholding.silence_hands_back is True)

    print("[withhold-test] a silence consumes his message while she holds it")
    _say(store, app.clock, "assistant", "the last thing she said before any of this", now - 600)
    mid = _say(store, app.clock, "user", "Of course. I was just at work.", now - 300)
    check("his message is in her queue", [m["id"] for m in store.unread_user_messages()] == [mid])
    offset[0] += 60
    row = _silence(app, 45)
    check("she decided on a silence", bool(row) and row["kind"] == "silence", row and row["why"])
    check("...and his message is out of the queue", store.unread_user_messages() == [])
    check("...and her situation block says she is not going to answer it",
          "not going to answer it later" in wh.situation_line())

    print("[withhold-test] the clock runs out with him still quiet")
    offset[0] += 46 * 60
    wh.tick()
    row = store.get("withholding") or {}
    back = store.unread_user_messages()
    check("the hold is over and the record says why", row.get("done")
          and row.get("released") == "ran out with him still quiet; his message goes back to her",
          row.get("released"))
    check("his message is back in her queue, and only his",
          [m["id"] for m in back] == [mid], ", ".join(str(m["id"]) for m in back))
    check("the row and the log both carry the hand-back",
          row.get("handed_back") == [mid] and bool((wh._log() or [{}])[-1].get("handed_back")),
          str(row.get("handed_back")))
    check("she is told it is still sitting there and that he has not written since",
          "still sitting there unanswered" in wh.situation_line()
          and "45 minutes" in wh.situation_line(), wh.situation_line()[:90])

    print("[withhold-test] once, and only once")
    offset[0] += 600
    wh.tick()
    check("another pass hands nothing back a second time",
          [m["id"] for m in store.unread_user_messages()] == [mid]
          and store.get("withholding_handed_back") == [mid])
    app2 = harness.build_on(tmp, copy=False)
    app2.clock.now_ts = lambda: real_now() + offset[0]
    app2.recover_lost_reply()
    app2.withholding.tick()
    check("and building her again on the same save -- what a restart does -- does not either",
          [m["id"] for m in app2.store.unread_user_messages()] == [mid]
          and app2.store.get("withholding_handed_back") == [mid],
          ", ".join(str(m["id"]) for m in app2.store.unread_user_messages()))
    check("the hold is still the one that ended, not a new one", app2.withholding.live() is None)

    print("[withhold-test] a hold he wrote into hands nothing back")
    store.set("withholding", None)
    offset[0] += 600
    _say(store, app.clock, "assistant", "something about something else", app.clock.now_ts())
    offset[0] += 60
    old = _say(store, app.clock, "user", "you free later?", app.clock.now_ts())
    store.mark_read(mid, app.clock.now_ts())        # the first one is dealt with
    offset[0] += 60
    row = _silence(app, 30)
    check("a second silence, on the newer message", bool(row) and store.unread_user_messages() == [])
    offset[0] += 600
    newer = _say(store, app.clock, "user", "hello?", app.clock.now_ts())
    offset[0] += 25 * 60
    wh.tick()
    row = store.get("withholding") or {}
    unread = [m["id"] for m in store.unread_user_messages()]
    check("the hold ended on its clock", row.get("done"), row.get("released"))
    check("...and the one she was silent on stayed consumed: the newer one is already in front of her",
          unread == [newer] and not row.get("handed_back"),
          "unread: " + ", ".join(str(i) for i in unread))

    print("[withhold-test] a hold he broke hands nothing back")
    store.mark_read(newer, app.clock.now_ts())
    store.set("withholding", None)
    offset[0] += 600
    _say(store, app.clock, "assistant", "whatever she said next", app.clock.now_ts())
    offset[0] += 60
    third = _say(store, app.clock, "user", "did you get my message", app.clock.now_ts())
    offset[0] += 60
    check("a third silence", bool(_silence(app, 60)))
    offset[0] += 300
    check("he says the thing that undoes it", wh.broken_by("sorry, that came out wrong") is True)
    row = store.get("withholding") or {}
    check("...and the message he broke it with is what she answers, not the one she sat on",
          store.unread_user_messages() == [] and not row.get("handed_back")
          and row.get("released") == "he said the thing that undid it", row.get("released"))
    print("   (his breaking message arrives unread through the app's own path; "
          "id %d stays consumed)" % third)

    print()
    print(wh.report())
    print()
    print("[withhold-test] " + ("all clear" if not FAILS else f"{len(FAILS)} FAILED: " + ", ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
