"""What a finished room writes down: the promise it kept, the summary it keeps, and what she said to whom today.

    python tools/room_record_test.py

Three faults reached the record on 2026-09-08 and all three are about the
moment a conversation ends. No model call and no network: the App is built on
a copy of the save with every model call refused, and the three checks drive
the real functions.

1. A promise to SEND somebody something was settled at the next morning's
   compile, so sending the photograph at 16:01 left the promise open all
   evening; the judge was then shown it as still outstanding and the chooser
   was offered it four more times. It is settled where it is kept, before the
   judge is asked, and the judge's list of what she still owes that person is
   empty by the time it goes out.

2. The summary of a conversation was assigned before the check that any bubble
   survived the filter, so a room whose only bubble was deleted stored a
   sentence saying what she said in it. And that round -- the one that produced
   literally nothing -- was the one round never counted as having produced
   nothing, because the branch returned first.

3. Her memory of what she has said to whom did not cross conversations, so one
   character confirmed the same arrangement seven times in six rooms. One line
   per finished room, under everybody she said it to, thrown away at midnight.
"""
import io
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from tools import harness  # noqa: E402

FAILURES = []


def check(what, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what)
    if detail:
        print("       " + str(detail)[:220])
    if not ok:
        FAILURES.append(what)


def a_friend(app):
    """One of her own people, as the record names her."""
    from sim import roster
    for key in roster.own_keys(app.config):
        if key == "him" or roster.same(app.config, key, "him") or roster.is_family(app.config, key):
            continue
        if roster.agent_of(app.config, key):
            continue          # she writes her own turns; this room is not written here
        return roster.record_name(app.config, key), key
    raise SystemExit("this character has nobody of her own to talk to")


# ---------------------------------------------------------------- 1
def promise_settles_where_it_is_kept(app):
    print("\n1. A PROMISE TO SEND SOMETHING CLOSES WHERE THE CHAT CARRIES IT")
    name, key = a_friend(app)
    today = app.clock.date_str()
    rows = [r for r in app.commitments.rows() if r.get("id") != "TESTSEND"]
    rows.append({"id": "TESTSEND", "made": today, "hm": "09:00", "to": key, "to_name": name,
                 "what": "send her the yukata photo", "kind": "send", "date": today,
                 "from_hm": "", "to_hm": "", "yen": 0, "reserved": 0, "funded": True,
                 "source": "this check", "event": "", "status": "open", "history": []})
    app.commitments.save(rows)
    # The judge is not asked at all once she has made `max_new_per_day`
    # promises today, and the row this check injects counts towards that. On
    # 2026-09-09 the live save already held five made that morning against a
    # cap of six, so the sixth was the harness's own row: the call returned
    # before the judge, the block came back empty, and the check failed on the
    # hour of the day it happened to run at rather than on anything about the
    # code. The rate limit is not what is under test here, so it is lifted for
    # the length of this check -- the same reason the check below looks for
    # the promise it settled rather than for an empty list.
    app.config.commitments.max_new_per_day = 10 ** 6
    rec = {"date": today, "hm": "16:00", "who": name, "kind": "line",
           "ended_hm": "16:02", "gist": "she sent the photo", "about_him": "",
           "turns": [{"who": name, "ja": "写真まだ？", "hm": "16:00"},
                     {"who": app.config.character.name, "ja": "[写真: 浴衣]", "hm": "16:01"},
                     {"who": name, "ja": "ありがと！", "hm": "16:02"}],
           "moves": [], "stale": 0, "long_bubbles": 0}
    chat = list(app.store.get("cast_chat", []) or []) + [rec]
    app.store.set("cast_chat", chat)

    # what the judge is handed, captured rather than answered
    seen = {}

    def fake_json(role, messages, **kw):
        seen["role"] = role
        seen["user"] = [m for m in messages if m["role"] == "user"][-1]["content"]
        return {}, ""

    app.llm.call_json = fake_json
    app.commitments.from_exchange(rec)

    row = [r for r in app.commitments.rows() if r.get("id") == "TESTSEND"][0]
    check("the promise she has just kept is closed, not carried into the evening",
          row.get("status") == "kept", f"{row.get('status')}: {row.get('why', '')}")
    block = ""
    if seen.get("user"):
        for part in seen["user"].split("\n\n"):
            if "OPEN COMMITMENTS TO THIS PERSON" in part:
                block = part
    # WHAT THIS CHECKS IS THE PROMISE IT JUST SETTLED, not the length of the
    # list. It asked for "(none)" in the block, which made it a check on
    # whatever the running character happened to owe this friend at the moment
    # the harness ran: on 2026-09-08 she had agreed to meet Hinako at the
    # ticket gate, that agreement was legitimately open, and the check failed
    # on a save it does not control. The fault it exists for is a KEPT promise
    # still being offered to the judge.
    check("and the promise she has just kept is not on the judge's list of what "
          "she still owes this person",
          bool(block) and "TESTSEND" not in block,
          block[:160] or "(the judge was never asked)")
    check("nothing else about her is offered to it as still outstanding",
          "yukata" not in block.lower(), block[:160])


# ---------------------------------------------------------------- 2
def a_deleted_bubble_writes_nothing(app):
    print("\n2. A ROUND WHOSE ONLY BUBBLE THE FILTER DELETED")
    name, _key = a_friend(app)
    today = app.clock.date_str()
    now = app.clock.now_ts()
    keep = "what the room came to two rounds ago"
    rec = {"date": today, "hm": "20:00", "who": name, "kind": "line",
           "turns": [{"who": name, "ja": "マリオカート、フルでやろうや", "hm": "20:00", "ts": now - 60}],
           "gist": keep, "about_him": "", "rounds": 1, "side": "hers",
           "started_ts": now - 60, "next_ts": now - 1, "stale": 0, "stale_run": 0,
           "salience": 2, "skipped": 0}
    app.store.set("exchange_live", rec)

    def dropped_everything(*a, **k):
        # what `_clean` does when the filter takes every bubble of hers: the
        # count is on the engine and the summary comes back with no turns
        app.exchange._dropped = 1
        return [], "she promises that this time she will actually do it", ""

    app.exchange._her_turns = dropped_everything
    # She is not in the middle of writing to him. This builds on a copy of the
    # live save, so a message of his that is recent enough makes her busy with
    # him, and then the room pushes her turn back and this section never
    # reaches the branch it is about -- red for a whole morning after he wrote
    # to her at 10:27.
    app.exchange._busy_with_him = lambda: False
    if app.cast_psych:
        app.cast_psych.leave_it = lambda *a, **k: (False, "")
    out = app.exchange.tick({"phone_access": "free", "location": "her room", "activity": "sitting"})
    check("the room closes and the record keeps the summary it already had",
          bool(out) and out.get("gist") == keep,
          (out or {}).get("gist"))
    check("nothing of hers is in it", bool(out) and len(out.get("turns") or []) == 1,
          f"{len((out or {}).get('turns') or [])} turn(s)")
    check("and the round that produced nothing is counted as a round that added nothing",
          bool(out) and int(out.get("stale", 0)) == 1, (out or {}).get("stale"))


# ---------------------------------------------------------------- 3
def what_she_said_today(app):
    print("\n3. WHAT SHE HAS SAID TO WHOM TODAY, ACROSS ROOMS")
    name, _key = a_friend(app)
    me = app.config.character.name
    today = app.clock.date_str()
    app.store.set("said_today", None)
    for hm, gist in (("17:30", "confirms Thursday at ten at the ticket gate"),
                     ("18:40", "confirms Thursday at ten again, and the drawings")):
        app.said_today.note_room({"date": today, "hm": hm, "who": name, "kind": "line",
                                  "gist": gist,
                                  "turns": [{"who": me, "ja": "木曜10時ね", "hm": hm}]})
    rows = app.said_today.for_person(name)
    check("two finished rooms with one person land two lines under her name",
          len(rows) == 2, "; ".join(r["gist"] for r in rows))
    check("and the call that writes her next turn is shown them",
          app.said_today.block(name).count("Thursday at ten") == 2,
          app.said_today.block(name)[:180])
    check("...and so is the moment she is asked what she does with the phone",
          any(name in l for l in app.said_today.lines_for_pick()),
          "; ".join(app.said_today.lines_for_pick())[:180])

    app.said_today.cool(name, minutes=120, why="this check")
    check("a person she went to with nothing is off the list, with the time she comes back",
          app.said_today.cooled_until(name) > app.clock.now_ts(),
          app.said_today.cool_line(name))
    check("and the room refuses to open while she is",
          "not again before" in app.exchange.open_with_reason(name, {"phone_access": "free"}),
          app.exchange.open_with_reason(name, {"phone_access": "free"}))

    class Tomorrow:
        def __init__(self, clock):
            self._c = clock

        def date_str(self, *a, **k):
            import datetime
            return (datetime.date.fromisoformat(self._c.date_str()) +
                    datetime.timedelta(days=1)).isoformat()

        def __getattr__(self, n):
            return getattr(self._c, n)

    real = app.said_today.clock
    app.said_today.clock = Tomorrow(real)
    check("a new date is a new page", app.said_today.for_person(name) == []
          and app.said_today.cooled_until(name) == 0, "")
    app.said_today.clock = real


def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_room_record_test.db")
    app = harness.build_on(tmp)
    harness.refuse_model(app)
    promise_settles_where_it_is_kept(app)
    a_deleted_bubble_writes_nothing(app)
    what_she_said_today(app)
    print("")
    if FAILURES:
        print("[test] %d FAILED: %s" % (len(FAILURES), "; ".join(FAILURES)))
        return 1
    print("[test] all clear")
    return 0


if __name__ == "__main__":
    sys.exit(main())
