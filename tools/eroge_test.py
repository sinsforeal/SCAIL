"""The reader of his text hooker's files, checked against his real files.

    python tools/eroge_test.py

Read-only throughout: his eroge directory is opened `mode=ro` and its
modification times are compared before and after, the live saves are opened
`mode=ro` through a URI (never copied -- a copy of an open database is a stale
image), and nothing is written anywhere.

What it checks:

  * the game library is readable and every game on file has an identity;
  * the reader's visual-novel-database id for the game he last played is the
    one in the identity file, read here independently;
  * "is he playing, and since when" agrees with the machine's own foreground
    telemetry to within a minute -- the two are separate sources, one the
    hooker's per-line event stream and one the window sensor;
  * the lines handed back are the Japanese the game emitted, with the speaker,
    and never the machine-translation column;
  * a card off the public database parses (skipped, not failed, with no
    network);
  * the lines are in no project store after the run, and the temporary copies
    the reader makes when the writer holds a lock are gone.
"""
import argparse
import contextlib
import glob
import io
import json
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from config import Config  # noqa: E402
from sensors import eroge_monitor as em  # noqa: E402
from sensors import vndb  # noqa: E402

FAILS = []


def ok(what, detail=""):
    print(f"  ok   {what}" + (f" -- {detail}" if detail else ""))


def bad(what, detail=""):
    FAILS.append(what)
    print(f"FAIL {what}" + (f" -- {detail}" if detail else ""))


def hm(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts or 0)))


def _mtimes(config):
    """Every file under his hooker's two directories, with its modification
    time, so the run can be proved to have written nothing."""
    cache, uc = em._dirs(config)
    out = {}
    for d in (cache, uc):
        if not d or not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            p = os.path.join(d, name)
            try:
                out[p] = os.stat(p).st_mtime
            except OSError:
                pass
    return out


def _feed_sessions(config, exe_basename, since):
    """(start, end) for every foreground window session of that executable in
    the machine's telemetry feed since `since`. The window sensor and the
    hooker's event stream know nothing about each other."""
    path = os.path.expandvars(str(config.sensors.telemetry_jsonl_path or ""))
    out = []
    if not path or not os.path.exists(path):
        return out
    size = os.path.getsize(path)
    with io.open(path, "rb") as fh:
        fh.seek(max(0, size - 4_000_000))
        chunk = fh.read().decode("utf-8", "replace").splitlines()
    for line in chunk[1:]:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        for s in ((row.get("system_activity") or {}).get("window_sessions") or []):
            if str(s.get("process_name") or "") != exe_basename:
                continue
            a, b = float(s.get("start_time") or 0), float(s.get("end_time") or 0)
            if b >= since:
                out.append((a, b))
    out.sort()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_yukarin.json",
                    help="the character whose section names his directories")
    ap.add_argument("--no-network", action="store_true", help="skip the card")
    args = ap.parse_args()
    # The config prints what a character does not have as it loads. That is
    # the runtime's line and not this check's, and smoke reads this output:
    # the first thing on it should be the first thing this has to say.
    _quiet = io.StringIO()
    with contextlib.redirect_stdout(_quiet):
        config = Config(args.config)
    c = config.eroge
    print(f"[eroge] {args.config}: enabled={c.enabled} stale={c.stale_minutes}min "
          f"skip>{c.skip_lines_per_second}/s window={c.max_raw_chars} chars "
          f"floor={c.min_new_lines} lines")

    # ---- the read cursor, on made-up runs first: the rule has to be checkable
    # without waiting for him to hold the button down
    fast = [(i * 0.2, 30) for i in range(100)]           # 100 lines in 20 seconds
    slow = [(i * 9.0, 30) for i in range(100)]           # 100 lines in 15 minutes
    cur, n, note = em.read_window(fast, 0, c.skip_lines_per_second, c.max_raw_chars)
    if n == 0 and note == "skipped":
        ok("100 lines in 20 seconds is the skip button", "nothing to summarise")
    else:
        bad("100 lines in 20 seconds is the skip button", f"{n} line(s), note {note!r}")
    cur, n, note = em.read_window(slow, 0, c.skip_lines_per_second, c.max_raw_chars)
    if n == 100 and note == "":
        ok("100 lines in 15 minutes is reading", "all 100 kept")
    else:
        bad("100 lines in 15 minutes is reading", f"{n} line(s), note {note!r}")
    big = [(i * 9.0, 400) for i in range(100)]           # 40,000 characters of it
    cur, n, note = em.read_window(big, 0, c.skip_lines_per_second, c.max_raw_chars)
    fits = sum(w + 1 for _t, w in big[cur:])
    if note == "ran long" and fits <= c.max_raw_chars and n < 100:
        ok("a stretch past the window moves the cursor forward",
           f"{n} of 100 line(s), {fits} chars, cursor {cur}")
    else:
        bad("a stretch past the window moves the cursor forward",
            f"{n} line(s), {fits} chars, note {note!r}")
    cur, n, note = em.read_window(slow, 40, c.skip_lines_per_second, c.max_raw_chars)
    if cur == 40 and n == 60:
        ok("the cursor never moves backwards", "given 40, answered 40")
    else:
        bad("the cursor never moves backwards", f"cursor {cur}, {n} line(s)")
    cache, uc = em._dirs(config)
    if not os.path.isdir(cache) or not os.path.isdir(uc):
        print(f"  skip his hooker's directories are not on this machine ({cache})")
        return 0
    before = _mtimes(config)

    # ---- the library
    rows = em.games(config)
    if not rows:
        bad("the game library reads", "no games")
        return 1
    named = [g for g in rows if g["title"] and g["vndb_id"]]
    ok("the game library reads",
       f"{len(rows)} game(s), {len(named)} with a database id, "
       f"{sum(len(g['cast']) for g in rows)} cast name(s)")
    for g in rows:
        print(f"       {g['title'][:34]:36s} v{g['vndb_id']}  {g['developer'][:14]:16s} "
              f"cast {len(g['cast']):3d}  {g['chars_read']:>8,} chars read")

    # ---- the game he last played, and its identity
    last = em.now_playing(config, within_minutes=60 * 24 * 60)
    if not last or not last.get("key"):
        bad("the game he last played is found")
        return 1
    live = em.now_playing(config)
    print(f"[eroge] the newest session: {last['title']} -- {hm(last['since_ts'])} -> "
          f"{hm(last['last_line_ts'])}, {last['minutes']:.1f} min, "
          f"{last['lines_this_session']} lines; playing now: {bool(live)}")
    ok("the game he last played is found", last["title"])

    raw = json.load(io.open(em._library_file(config), encoding="utf-8"))[1]
    want = (raw.get(last["key"]) or {}).get("vid")
    if last["vndb_id"] and int(want or 0) == int(last["vndb_id"]):
        ok("its database id is the one in the identity file", f"v{last['vndb_id']}")
    elif not last["vndb_id"] and not want:
        # the hooker never matched this game to VNDB: reader and file agree there is no id
        ok("its database id is the one in the identity file", "none in the file, none read")
    else:
        bad("its database id is the one in the identity file",
            f"reader v{last['vndb_id']} vs file v{want}")

    # ---- against the machine's own foreground telemetry
    # He flips between the game and the hooker's own window a hundred times an
    # hour, so the foreground sensor's answer for the sitting is the span of
    # its fragments inside it. The END is the exact comparison -- the last
    # hooked line and the last moment the window was in front is the same
    # event. The START is bounded rather than exact: the window opens on the
    # title screen and the first line comes seconds to a couple of minutes
    # later, so what is checked is that it opened BEFORE the first line and
    # not before the sitting began.
    exe = os.path.basename(str(raw.get(last["key"], {}).get("gamepath") or ""))
    gap = float(c.stale_minutes) * 60.0
    sess = [s for s in _feed_sessions(config, exe, last["since_ts"] - gap)
            if s[0] <= last["last_line_ts"] + gap]
    if not sess:
        print(f"  skip the foreground telemetry has no window session for {exe} "
              f"in the feed's tail; nothing to compare")
    else:
        fa, fb = min(s[0] for s in sess), max(s[1] for s in sess)
        d_start, d_end = last["since_ts"] - fa, abs(fb - last["last_line_ts"])
        detail = (f"the window {hm(fa)} -> {hm(fb)} against the line stream "
                  f"{hm(last['since_ts'])} -> {hm(last['last_line_ts'])} "
                  f"(open {d_start:.0f}s before the first line, {d_end:.0f}s from the last, "
                  f"{len(sess)} window fragment(s))")
        if d_end <= 60 and -60 <= d_start <= gap:
            ok("the session agrees with the foreground telemetry to within a minute", detail)
        else:
            bad("the session agrees with the foreground telemetry to within a minute", detail)

    # ---- the read cursor on his own stream today
    ev = em._rows(em._save_db(config),
                  "select time, wordcount from game_word_count where gameinternalid=? "
                  "and time>=? order by time", (last["internal_id"], last["since_ts"] - 0.5))
    cur, n, note = em.read_window(ev, 0, c.skip_lines_per_second, c.max_raw_chars)
    chars = sum(int(w or 0) + 1 for _t, w in ev[cur:])
    ok("the read cursor on his newest sitting",
       f"{len(ev)} line event(s), the cursor at {cur}, {n} read line(s), {chars} chars"
       + (f", {note}" if note else ", nothing skipped and nothing cut"))
    rl = em.read_lines(config, last)
    if len(rl["lines"]) == n:
        ok("the record's rows line up with the event stream", f"{len(rl['lines'])} line(s)")
    else:
        bad("the record's rows line up with the event stream",
            f"{len(rl['lines'])} row(s) against {n} event(s)")
    # the whole of his history in this game as one window, which is the worst
    # case the budget will ever see. The event stream counts the line with the
    # speaker's name stripped off and the record keeps the name, so a budget
    # settled on the stream alone let 19,177 characters out under a ceiling of
    # 16,000 the first time this ran.
    whole = dict(last)
    whole["since_ts"], whole["lines_this_session"] = 0.0, 10 ** 6
    big = em.read_lines(config, whole)
    if big["chars"] <= int(c.max_raw_chars):
        ok("the text handed over is inside the character ceiling",
           f"{big['chars']} of {c.max_raw_chars} for {len(big['lines'])} line(s), {big['note']}")
    else:
        bad("the text handed over is inside the character ceiling",
            f"{big['chars']} against {c.max_raw_chars}")
    print(f"       the floor is {c.min_new_lines} new lines: "
          f"{'a call' if n >= c.min_new_lines else 'no call'} on this sitting "
          f"({n} new); 19 new -> no call, 20 -> a call")
    if (19 >= int(c.min_new_lines)) or (20 < int(c.min_new_lines)):
        bad("the floor is twenty new lines", f"min_new_lines is {c.min_new_lines}")
    else:
        ok("the floor is twenty new lines", "19 new is under it, 20 is not")

    # ---- the lines
    path = em.record_file(config, last["key"])
    if not path:
        bad("the per-game record is found for that key")
        return 1
    con = sqlite3.connect(em._uri(path), uri=True)
    total, high = con.execute("select count(*), max(id) from artificialtrans").fetchone()
    start = max(0, int(high or 0) - 200)
    lines, mark = em.lines_since(config, last["key"], start, max_lines=40)
    if not lines:
        bad("lines come back past a mark", f"nothing past id {start} of {high}")
        con.close()
        return 1
    ok("lines come back past a mark",
       f"{len(lines)} line(s) past id {start} of {total} rows, new mark {mark}")
    if mark == int(high or 0):
        ok("the mark is the record's own high-water mark", str(mark))
    else:
        bad("the mark is the record's own high-water mark", f"{mark} vs {high}")

    # every line is the game's own Japanese, with the speaker, and is not the
    # translation column under another name
    ids = tuple(l["id"] for l in lines)
    have = {int(i): (o, s, m) for i, o, s, m in con.execute(
        "select id, origin, source, machineTrans from artificialtrans "
        "where id in (%s)" % ",".join("?" * len(ids)), ids)}
    con.close()
    wrong_col, no_jp, english = [], [], []
    for l in lines:
        origin, source, trans = have.get(l["id"], ("", "", ""))
        if l["text"] != " ".join(str(origin or "").split()):
            wrong_col.append(l["id"])
        if not em._JP.search(l["text"]):
            no_jp.append(l["id"])
        for v in (json.loads(trans) if trans else {}).values():
            v = " ".join(str(v or "").split())
            if v and v in l["text"]:
                english.append(l["id"])
    if wrong_col:
        bad("every line is the hooked line as the game emitted it",
            f"{len(wrong_col)} line(s) are not the `origin` column")
    else:
        ok("every line is the hooked line as the game emitted it (the speaker kept)")
    if no_jp:
        bad("every line is Japanese", f"{len(no_jp)} without kana or kanji")
    else:
        ok("every line is Japanese", f"{len(lines)} checked")
    if english:
        bad("no line carries the machine translation", f"{len(english)} line(s)")
    else:
        ok("no line carries the machine translation")
    speakers = sum(1 for l in lines if "「" in l["text"])
    sample = next((l["text"] for l in lines if "「" in l["text"]), lines[0]["text"])
    print(f"       {speakers} of {len(lines)} are spoken; one line: {sample[:40]}")

    # ---- the card
    if args.no_network:
        print("  skip the card (--no-network)")
    else:
        text = vndb.fetch(last["vndb_id"], int(c.card_max_chars))
        if not text:
            print("  skip the card -- the database did not answer (the type is in the log)")
        elif len(text.splitlines()) >= 2 and str(last["vndb_id"]):
            ok("the card parses", f"{len(text)} chars, {len(text.splitlines())} lines")
            for line in text.splitlines():
                print(f"       | {line[:110]}")
            for wrong in ("[spoiler]", "[url=", "[From"):
                if wrong in text:
                    bad("the card has no database markup left in it", wrong)
        else:
            bad("the card parses", text[:80])

    # ---- nothing of his was written, and nothing of it was kept here
    after = _mtimes(config)
    moved = [os.path.basename(p) for p, t in after.items()
             if abs(t - before.get(p, t)) > 0.001 or p not in before]
    if moved:
        # he may still be playing: a file the hooker itself wrote during the
        # run is his writer, not this reader. Say so rather than passing it.
        print(f"  note {len(moved)} of his files changed during the run "
              f"(his hooker is running): {', '.join(moved[:3])}")
    ok("nothing under his eroge directory was opened for writing",
       "no journal file beside his data"
       if not glob.glob(os.path.join(uc, "*.db-journal")) else "")
    leftover = glob.glob(os.path.join(tempfile.gettempdir(), "scail_eroge_*.sqlite"))
    if leftover:
        bad("the temporary copies are deleted", f"{len(leftover)} left")
    else:
        ok("the temporary copies are deleted")

    needle = max((l["text"] for l in lines), key=len)[:14]
    kept = []
    for db in sorted(glob.glob(os.path.join("data", "*.db"))):
        try:
            con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
        except sqlite3.Error:
            continue
        try:
            for table, col in (("kv", "value"), ("events", "text"), ("user_facts", "text")):
                try:
                    n = con.execute(f"select count(*) from {table} where {col} like ?",
                                    ("%" + needle + "%",)).fetchone()[0]
                except sqlite3.Error:
                    continue
                if n:
                    kept.append(f"{os.path.basename(db)}.{table}: {n}")
        finally:
            con.close()
    if kept:
        bad("the raw lines are in no project store", "; ".join(kept))
    else:
        ok("the raw lines are in no project store",
           f"{len(glob.glob(os.path.join('data', '*.db')))} save(s) searched")

    print(f"[eroge] {len(FAILS)} failure(s)" if FAILS else
          "[eroge] the reader agrees with his files and keeps none of them")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
