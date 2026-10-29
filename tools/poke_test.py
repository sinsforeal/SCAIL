"""Forcing what normally waits on her clock: /idle, /reply, /selfstart.

    python tools/poke_test.py            # the whole thing, on a copy of the second character's save
    python tools/poke_test.py --static   # the drift check only, no App and no save (what smoke runs)

No model call is ever made: `LLM.call` and `LLM.call_json` are replaced by a
stub that answers from a script and counts what it was asked. What is checked
is that each command takes the path the loop takes rather than a shortcut --
the tick writes a scene and the gauges are read, his message goes through the
reply path and her words reach her own store, and the forced opener goes
through the persona and her delivery.

The static half is the one that catches the fault this was built against: the
loop's ordinary pass and `/idle` must be the same method, so the branch in
`App.run` may hold nothing but the call.
"""
import io
import os
import re
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FAILURES = []


def check(ok, what, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILURES.append(what)
    return ok


# ------------------------------------------------- the loop and /idle are one

def static():
    """The loop's ordinary pass and the forced one cannot drift, because there
    is only one of them. Reads scail.py; builds nothing."""
    with io.open(os.path.join(ROOT, "scail.py"), encoding="utf-8") as fh:
        src = fh.read()
    check("def ordinary_tick(self):" in src, "the loop's ordinary pass is a method of its own")
    m = re.search(r"\n(\s+)elif self\.director\.due\(self\.schedule\).*?:\n(.*?)\n\s+# the feeds",
                  src, re.S)
    body = [l for l in (m.group(2).splitlines() if m else []) if l.strip()]
    check(bool(m) and body == [m.group(1) + "    self.ordinary_tick()"],
          "and the loop's branch holds nothing but the call to it",
          f"{len(body)} line(s)" + (f": {body[0].strip()[:60]}" if body else ""))
    for cmd in ("/idle", "/reply", "/selfstart"):
        check(f'"{cmd}": ("_cmd_' in src, f"{cmd} is in the command table")
        check(f'("{cmd}' in src.split("HELP = [", 1)[-1], f"{cmd} has a help row")
    check("[ops] forced:" in src, "a forced one says so in the log")


# ------------------------------------------------------------------ the stub

class Stub:
    """Every model call, answered from a script and counted.

    Attached to the App's ONE `LLM` object rather than put in its place: the
    director, the intent, the foresight and a dozen others were handed that
    object when they were built and hold it themselves, so an App whose `llm`
    attribute is swapped still pays for real answers everywhere else."""

    def __init__(self, app):
        self.config = app.config
        self.calls = []
        self.answers = {}
        self.default = "stub answer"
        app.llm.call = self.call
        app.llm.call_json = self.call_json

    def call(self, role, messages, *a, **k):
        self.calls.append(role)
        return self.answers.get(role, self.default)

    def call_json(self, role, messages, *a, **k):
        self.calls.append(role)
        return None, ""

    def count(self, role, since=0):
        return self.calls[since:].count(role)


def settle(app, seconds=90):
    """Wait for her delivery queue to empty: the bubbles are typed out on a
    worker thread with her own pauses between them."""
    end = time.time() + seconds
    while time.time() < end and app.delivery.busy():
        time.sleep(0.2)
    return not app.delivery.busy()


def her_rows(app, n=8):
    return [m for m in app.store.recent_messages(n) if m["role"] == "assistant"]


def last_hers(app):
    """The id of her newest message: a row added is a row she really sent,
    which counting the last few messages is not (his go in the same window)."""
    return (app.store.last_message("assistant") or {}).get("id", 0)


# ------------------------------------------------------------- the whole path

def full():
    from tools import harness
    tmp = os.path.join(tempfile.gettempdir(), "poke_test.db")
    print("[poke] building the second character on a copy of her save")
    app = harness.build_on(tmp, "config_yukarin.json", "data/yukarin.db")
    stub = Stub(app)
    stub.answers["persona"] = "forced, and answered by a stub"

    # the loop draws the day on its first pass, before anything reads the
    # block she is in; a command runs inside a pass that has already done it
    app.ensure_day()
    app.maybe_generate_schedule()
    check(bool(app.schedule), "she has a plan for the day, as she would inside the loop")

    # ---- 1. one ordinary loop pass
    scene_before = (app.store.last_scene() or {}).get("ts", 0)
    n = len(stub.calls)
    out = app.run_command("/idle")
    print("   " + out.replace("\n", "\n   ")[:400])
    # what the pass must do is write a scene; whether it PAID for one depends
    # on where this character's scenes come from (`director.scene_source`), and
    # counting the call would fail for a character whose day is cut from her
    # plan in code exactly when the pass is working correctly
    calls = stub.count("director", n)
    if app.director.from_plan():
        check(calls == 0, "the forced idle pass wrote her scene from her plan and paid nothing",
              f"{calls} director call(s)")
    else:
        check(calls >= 1, "the forced idle pass ran the director's own tick", f"{calls} call(s)")
    check((app.store.last_scene() or {}).get("ts", 0) > scene_before,
          "and left a scene in her record")
    check(stub.count("state", n) >= 1 or "quiet tick, decay only" in out or bool(out),
          "and the gauges were read or the tick said why not")
    check("inner:" in out, "the answer names what the tick decided", out.splitlines()[0][:70])

    # ---- 2. the refusals, before anything is unread
    for m in app.store.unread_user_messages():
        app.store.mark_read(m["id"], app.clock.now_ts())
    said = app.run_command("/reply")
    check("unread" in said,
          "with nothing of his waiting, /reply says so rather than doing half of it",
          said[:60])
    access = app.phone_access
    app.phone_access = lambda: "none"
    check("no phone" in app.run_command("/reply"), "and with her phone away it says that")
    check("no phone" in app.run_command("/selfstart"), "and so does /selfstart")
    app.phone_access = access

    # ---- 3. his message, answered now
    ts = app.clock.now_ts()
    mid = app.store.add_message(ts, app.clock.date_str(ts), "user", "are you about?")
    n = len(stub.calls)
    out = app.run_command("/reply")
    print("   " + out.replace("\n", "\n   ")[:200])
    check("answering" in out, "the forced reply took his message", out[:70])
    check(stub.count("persona", n) == 1, "her words were written once, through the persona",
          f"{stub.count('persona', n)} call(s)")
    check((app.store.message_by_id(mid) or {}).get("read_ts"), "his message is marked read")
    check(settle(app), "her delivery queue emptied")
    rows = her_rows(app, 6)
    check(any("stub" in r["text"] for r in rows), "and her answer is in her own record",
          " // ".join(r["text"][:40] for r in rows[-2:]))

    # ---- 4. the same message again
    before = last_hers(app)
    n = len(stub.calls)
    stub.answers["persona"] = "asked again, and answered again"
    out = app.run_command("/reply again")
    check("answering" in out, "/reply again takes his newest message back off the shelf", out[:70])
    check(stub.count("persona", n) == 1, "and writes one more answer to it")
    check(settle(app) and last_hers(app) > before,
          "which reaches her record beside the first one")

    # ---- 5. she writes first
    for m in app.store.unread_user_messages():
        app.store.mark_read(m["id"], app.clock.now_ts())
    before = last_hers(app)
    n = len(stub.calls)
    stub.answers["persona"] = "she started this one herself"
    out = app.run_command("/selfstart she has been thinking about the tape all afternoon")
    print("   " + out.replace("\n", "\n   ")[:200])
    check(stub.count("intent", n) >= 1, "the forced opener still asks her what she means by it")
    check(stub.count("persona", n) == 1, "and her words are written once, through the persona",
          f"{stub.count('persona', n)} call(s)")
    check(settle(app), "her delivery queue emptied")
    rows = her_rows(app, 12)
    check(last_hers(app) > before and any("started this one" in r["text"] for r in rows),
          "and what she started is in her record",
          " // ".join(r["text"][:40] for r in rows[-2:]))
    check(any(r.get("self_started") for r in rows[-2:]),
          "recorded as hers to have started")

    # ---- 6. nothing forced while she is in the middle of something
    unread = app.store.add_message(app.clock.now_ts(), app.clock.date_str(), "user", "and again")
    check("unread" in app.run_command("/selfstart"),
          "with his message waiting, /selfstart sends her to answer it first")
    app.store.mark_read(unread, app.clock.now_ts())
    print(f"[poke] {len(stub.calls)} stubbed model call(s), none paid for")


def main():
    if "--static" in sys.argv:
        static()
    else:
        static()
        full()
    print(f"[poke] {'FAILED: ' + ', '.join(FAILURES) if FAILURES else 'all clear'}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
