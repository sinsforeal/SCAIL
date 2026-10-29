"""The machine writes what it is holding when a reply asks for it.

    python tools/flush_test.py

The collector buffers what it sees of his machine and writes the feed on a
character count or on its heartbeat, so anything he did inside the current
window was invisible to a reply built during it: he opened twenty-four
pictures four minutes before a message and the tags were still in the buffer
(2026-09-04). A bot asks by touching `sensors.telemetry_flush_request_path`.

The collector's side is checked on a temp feed and a temp request file, with
the sources switched off so nothing of his machine is read and no thread of
the collector's own runs: a request over a buffer with something in it writes
one entry whose `flush_reason` is `requested` and clears the file; a request
over an empty buffer writes no entry and clears the file anyway; a request
with no file present does nothing; and the file being removed underneath the
collector is not an error.

The bot's side (`App.request_flush`) is checked against a stand-in for the
collector, on an App object built without its save or its wiring: it returns
True when an entry reaches the feed, returns quietly when the request is
served with nothing to write, and when nobody is listening it gives up after
the wait and says so once an hour rather than once a reply.

`tools/smoke.py` runs this. No model call, no save, nothing of his machine.
"""
import io
import os
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

import json  # noqa: E402
from config import Config  # noqa: E402
from sensors import telemetry_collector  # noqa: E402

fails = []


def check(ok, what, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what + (("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(what)
    return ok


class Quiet(telemetry_collector.TelemetryCollector):
    """The collector with its sources and its own thread switched off.

    Under test is the request file and the entry it produces, not the readers
    of his browser history; a check that read his real machine would be slow,
    would differ from run to run, and would have nothing to do with what it is
    asserting.
    """

    def _poll_sources(self):
        self.polls += 1

    def _run_loop(self):
        pass


def feed_entries(path):
    out = []
    if not os.path.exists(path):
        return out
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def build(tmp):
    c = Config("config.json")
    sv = c.sensor_view
    sv.telemetry_jsonl_path = os.path.join(tmp, "feed.jsonl")
    sv.telemetry_pending_log_path = os.path.join(tmp, "pending.txt")
    sv.telemetry_state_path = os.path.join(tmp, "telemetry_state.json")
    sv.telemetry_flush_request_path = os.path.join(tmp, "flush_request")
    sv.mal_enabled = False
    col = Quiet(sv)
    col.polls = 0
    return sv, col


def ask(sv):
    with io.open(sv.telemetry_flush_request_path, "w", encoding="utf-8") as f:
        f.write("1")


def run(tmp):
    sv, col = build(tmp)
    feed = sv.telemetry_jsonl_path
    req = sv.telemetry_flush_request_path

    print("NO REQUEST FILE")
    check(col.check_flush_request() is False, "nothing is written and nothing is claimed")
    check(feed_entries(feed) == [], "the feed is still empty")

    print("\nA REQUEST OVER A BUFFER WITH SOMETHING IN IT")
    col._has_activity = True
    col._last_chrome_text = "he was reading a page about trains"
    col._estimated_chars = len(col._last_chrome_text)
    ask(sv)
    wrote = col.check_flush_request()
    entries = feed_entries(feed)
    check(wrote is True, "the collector says it wrote")
    check(len(entries) == 1, "one entry reached the feed", f"{len(entries)} entries")
    if entries:
        e = entries[-1]
        check(e.get("flush_reason") == "requested",
              "the entry says it was asked for", str(e.get("flush_reason")))
        check("trains" in (e.get("chrome_telemetry") or ""),
              "it carries what the buffer held")
        check(e.get("id") == 1, "the id counter moved", str(e.get("id")))
    check(not os.path.exists(req), "the request file is gone")
    check(col.polls >= 1, "the sources were re-read before the write", f"{col.polls} poll(s)")
    check(col._has_activity is False, "the buffer was cleared")

    print("\nA REQUEST OVER AN EMPTY BUFFER")
    ask(sv)
    wrote = col.check_flush_request()
    check(wrote is False, "the collector says it wrote nothing")
    check(len(feed_entries(feed)) == 1, "no entry was added", f"{len(feed_entries(feed))} entries")
    check(not os.path.exists(req), "the request file is gone anyway")

    print("\nTHE REQUEST FILE REMOVED UNDERNEATH IT")
    # Two bots ask in the same second and one pass serves both, so the second
    # removal finds nothing there. That is the ordinary case, not an error.
    ask(sv)
    os.remove(req)
    check(col.check_flush_request() is False, "a request that is no longer there is not an error")

    print("\nTWO REQUESTS ONE AFTER THE OTHER")
    col._has_activity = True
    col._last_chrome_text = "he opened twenty-four pictures"
    for _ in range(2):
        ask(sv)
        col.check_flush_request()
    entries = feed_entries(feed)
    check(len(entries) == 2, "the second ask over an emptied buffer added nothing",
          f"{len(entries)} entries")
    check([e["id"] for e in entries] == [1, 2], "no id was written twice",
          str([e["id"] for e in entries]))
    check(not os.path.exists(req), "the request file is gone")

    print("\nTHE PATH IN THE CONFIG")
    check(bool(Config("config.json").sensors.telemetry_flush_request_path),
          "the first character's config names the request file")
    check(float(Config("config.json").sensors.telemetry_flush_wait_seconds) > 0,
          "and how long a reply waits for it")

    col.stop()


def after(delay, fn):
    t = threading.Thread(target=lambda: (time.sleep(delay), fn()), daemon=True)
    t.start()
    return t


def run_bot_side(tmp):
    """The other half: the bot asking, with a stand-in for the collector.

    The App is made without its constructor -- no save, no wiring, no model --
    because what is under test is the ask itself: the file it writes, what it
    waits for, and what it does when nobody answers.
    """
    import scail
    app = scail.App.__new__(scail.App)
    c = Config("config.json")
    sv = c.sensors
    sv.telemetry_jsonl_path = os.path.join(tmp, "bot_feed.jsonl")
    sv.telemetry_flush_request_path = os.path.join(tmp, "bot_request")
    app.config = c
    app.sensors_on = True
    app.replay = None
    app.phone = object()
    app.telemetry_module = telemetry_collector
    req = sv.telemetry_flush_request_path
    feed = sv.telemetry_jsonl_path
    with io.open(feed, "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": 7}) + "\n")

    print("\nTHE BOT ASKS AND AN ENTRY ARRIVES")

    def serve_with_an_entry():
        with io.open(feed, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": 8, "flush_reason": "requested"}) + "\n")
        try:
            os.remove(req)
        except OSError:
            pass

    after(0.6, serve_with_an_entry)
    got = app.request_flush(wait_seconds=3)
    check(got is True, "the ask says something new reached the feed")
    check(not os.path.exists(req), "and the stand-in took the request file")

    print("\nTHE BOT ASKS AND THERE WAS NOTHING TO WRITE")
    after(0.6, lambda: os.remove(req))
    got = app.request_flush(wait_seconds=3)
    check(got is False, "the ask says nothing new arrived")
    check(app._flush_ask_quiet_until == 0.0,
          "and it does not complain: the request was served")

    print("\nTHE BOT ASKS AND NO COLLECTOR IS RUNNING")
    started = time.time()
    got = app.request_flush(wait_seconds=1.5)
    waited = time.time() - started
    check(got is False, "the ask gives up")
    check(1.4 <= waited < 4.0, "after the wait it was given", f"{waited:.1f}s")
    check(os.path.exists(req), "the request stands for whenever the collector comes up")
    check(app._flush_ask_quiet_until > time.time(), "and it said so once")
    was = app._flush_ask_quiet_until
    app.request_flush(wait_seconds=0.6)
    check(app._flush_ask_quiet_until == was,
          "the next reply's ask does not say it again")

    print("\nTHE ASK IS SKIPPED WHERE THERE IS NO MACHINE TO ASK")
    app.sensors_on = False
    os.remove(req)
    check(app.request_flush() is False and not os.path.exists(req),
          "a run with no sensors writes no request file")
    app.sensors_on = True
    app.replay = {"from": "x"}
    check(app.request_flush() is False and not os.path.exists(req),
          "and a replay does not ask either")


def main():
    tmp = tempfile.mkdtemp(prefix="flush_test_")
    try:
        run(tmp)
        run_bot_side(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if fails:
        print(f"FAIL: {len(fails)} check(s): " + "; ".join(fails[:6]))
        return 1
    print("all checks passed: the machine writes what it holds when a reply asks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
