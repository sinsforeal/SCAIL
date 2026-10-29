"""Is a character who runs herself actually working, right now.

    python tools/agent_audit.py rena
    python tools/agent_audit.py rena --days 3 --verbose

The read-only audit of a RUNNING character, as a tool. It was a day of hand
work the first time (`data/retired/20260907_203328_rena_audit/REPORT.md`), and
everything it found was runtime behaviour that three structural checks had
passed. This asks the same questions of the same places every time, in about a
second, so the second day of a promoted character costs a command rather than
an afternoon.

It reads and never writes. Live saves are opened through a
`file:...?mode=ro` URI and never copied, because a file copy of an open
database returns a stale image; her config is copied to a scratch file before
a `Config` is built on it, because building one backfills the file it is
given; the run directories are read where they lie, zipped ones through
`zipfile`; nothing is started, nothing is stopped and no process is touched.

What it reports, one line each:

  the process, matched by her own row's command-line pattern; her
  registration with the hub and whether his phone lists her; every ask the
  owner's process sent her matched to the answer her process paid for;
  the beats the owner planned per person per day, hers among them; how old
  the newest row in her owner-side queue is; her record of a room against
  the world file's own rows for the same turns; anything a switched-off
  section has written into her save; her gauges against her config; what is
  left in her save about a man she may have no chat with; a person the
  owner's record has carried the same thing for three days running; a log
  line repeating faster than anything real; tracebacks and error lines; and
  what she has spent by role since her newest boot.

`ok` is what it should be, `WARN` is worth a look, `FAIL` is broken. Exit 1 on
any FAIL. What it cannot tell you is whether she is any good: every question
here is mechanical, and whether her words are believable is a read
(`docs/agent-character.md`, the limits at the end).
"""
import argparse
import collections
import datetime
import glob
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# the one table of what a section owns, kept in the rehearsal so the two
# tools cannot disagree about which key belongs to what
from tools.agent_rehearsal import SECTION_KEYS, NO_HIM_KV  # noqa: E402

ROWS = []
STAMP = re.compile(r"^\[\d\d:\d\d:\d\d\]\s*")
TIME = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\]")


def row(state, what, detail=""):
    ROWS.append((state, what, detail))
    print("  %-4s %-58s %s" % (state, what, detail))


def ok(what, detail=""):
    row("ok", what, detail)


def warn(what, detail=""):
    row("WARN", what, detail)


def fail(what, detail=""):
    row("FAIL", what, detail)


# ------------------------------------------------------------------ reading

def ro(path):
    """A live save, opened read-only. Never a copy: a file copy of an open
    database returns whatever was flushed last, which is not what the process
    is running on."""
    p = os.path.abspath(path).replace("\\", "/")
    return sqlite3.connect("file:%s?mode=ro" % p, uri=True)


def kv(con, key, default=None):
    try:
        r = con.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    except sqlite3.Error:
        return default
    if not r:
        return default
    try:
        return json.loads(r[0])
    except (TypeError, ValueError):
        return r[0]


def kv_keys(con):
    try:
        return {r[0] for r in con.execute("SELECT key FROM kv").fetchall()}
    except sqlite3.Error:
        return set()


def config_of(row_):
    """Her config, built on a COPY. `Config` backfills the file it is handed,
    and an audit that wrote to her live config would be changing the thing it
    came to read."""
    import logger
    logger.log = lambda m, to_console=True: None
    src = os.path.join(ROOT, row_["config"])
    d = tempfile.mkdtemp(prefix="scail_audit_")
    dst = os.path.join(d, os.path.basename(src))
    with io.open(src, encoding="utf-8") as fh:
        blob = fh.read()
    with io.open(dst, "w", encoding="utf-8") as fh:
        fh.write(blob)
    from config import Config
    out, sys.stdout = sys.stdout, io.StringIO()
    try:
        return Config(path=dst)
    finally:
        sys.stdout = out


def runs_for(hub_id, limit=0):
    """(name, [lines]) for every run directory belonging to this character,
    newest first. Two bots write into one `logs/`, and a run says whose it is
    in the line where it registers with the hub."""
    want = "registered '%s'" % hub_id
    out = []
    live = sorted((d for d in glob.glob(os.path.join("logs", "*")) if os.path.isdir(d)),
                  key=os.path.getmtime, reverse=True)
    for d in live:
        p = os.path.join(d, "session.log")
        if not os.path.exists(p):
            continue
        text = io.open(p, encoding="utf-8", errors="replace").read()
        if want in text:
            out.append((d, text.split("\n")))
    for z in sorted(glob.glob(os.path.join("logs", "*.zip")), reverse=True):
        try:
            zf = zipfile.ZipFile(z)
        except zipfile.BadZipFile:
            continue
        for n in zf.namelist():
            if not n.endswith("session.log"):
                continue
            text = zf.read(n).decode("utf-8", "replace")
            if want in text:
                out.append((z, text.split("\n")))
    out.sort(key=lambda x: os.path.basename(x[0]), reverse=True)
    return out[:limit] if limit else out


def calls_for(hub_id, since_day=""):
    """Every model call this character has paid for, newest run first, as the
    parsed rows of her own `llm_calls.jsonl`."""
    want = "registered '%s'" % hub_id
    rows = []
    for d in sorted(glob.glob(os.path.join("logs", "*")), reverse=True):
        if os.path.isdir(d):
            sp, lp = os.path.join(d, "session.log"), os.path.join(d, "llm_calls.jsonl")
            if not os.path.exists(sp) or not os.path.exists(lp):
                continue
            if want not in io.open(sp, encoding="utf-8", errors="replace").read():
                continue
            src = io.open(lp, encoding="utf-8", errors="replace")
        elif d.endswith(".zip"):
            try:
                zf = zipfile.ZipFile(d)
            except zipfile.BadZipFile:
                continue
            names = zf.namelist()
            sn = next((n for n in names if n.endswith("session.log")), "")
            ln = next((n for n in names if n.endswith("llm_calls.jsonl")), "")
            if not sn or not ln:
                continue
            if want not in zf.read(sn).decode("utf-8", "replace"):
                continue
            src = io.TextIOWrapper(zf.open(ln), encoding="utf-8", errors="replace")
        else:
            continue
        for line in src:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if since_day and str(r.get("wall", ""))[:10] < since_day:
                continue
            r["_run"] = os.path.basename(d)
            rows.append(r)
    return rows


def processes():
    """Every running command line on the machine. Read-only: the audit says
    what is up and touches none of it."""
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | ForEach-Object "
             "{ $_.ProcessId.ToString() + '|' + $_.CommandLine }"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    out = []
    for line in (p.stdout or "").split("\n"):
        pid, _, cmd = line.partition("|")
        if pid.strip().isdigit() and cmd.strip():
            out.append((int(pid), cmd.strip()))
    return out


# ------------------------------------------------------------------ the checks

def check_process(r, procs):
    pat = re.compile(r["match"])
    hits = [(pid, c) for pid, c in procs if pat.search(c)]
    if not hits:
        fail("her process is up and matched by her own row's pattern",
             "nothing matches %r" % r["match"])
    elif len(hits) > 1:
        fail("her process is up and matched by her own row's pattern",
             "%d processes match: %s" % (len(hits), ", ".join(str(p) for p, _ in hits)))
    else:
        ok("her process is up and matched by her own row's pattern",
           "pid %d" % hits[0][0])
    return hits


def check_hub(r, cfg):
    from sim import existence
    hidden_wanted = not existence.has_chat(cfg)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=5) as fh:
            health = json.loads(fh.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        fail("the hub knows her", "the hub did not answer (%s)" % type(e).__name__)
        health = {}
    if health:
        if r["hub_id"] in (health.get("chars") or []):
            ok("the hub knows her", "as %r, beside %s"
               % (r["hub_id"], ", ".join(c for c in health["chars"] if c != r["hub_id"])))
        else:
            fail("the hub knows her", "the hub lists %s" % ", ".join(health.get("chars") or []))
    path = os.path.join(ROOT, "data", "talkapp", "state.json")
    try:
        with io.open(path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        warn("his phone lists her only if she has a chat with him", "no hub state file to read")
        return
    c = (state.get("chars") or {}).get(r["hub_id"]) or {}
    if not c:
        fail("his phone lists her only if she has a chat with him",
             "the hub's own store has no row for %r" % r["hub_id"])
        return
    # `hidden` is written only when it is set, so absent means false
    hidden = bool(c.get("hidden"))
    detail = ("hidden %s, %d in her peer mailbox, %d row(s) in a chat with him"
              % (hidden, len(c.get("peer_in") or []), len(c.get("log") or [])))
    if hidden == hidden_wanted:
        ok("his phone lists her only if she has a chat with him", detail)
    else:
        fail("his phone lists her only if she has a chat with him",
             detail + "; her sheet says with_him %r"
             % str(getattr(cfg.character.existence, "with_him", "")))


def check_asks(r, owner_row, days):
    """Every ask the owner sent her, matched to what her process did with it.

    The owner's log says when it asked and when it gave up; hers says what she
    paid for and whether she chose to say nothing. Matched by the clock,
    because the two processes write into two files and nothing carries an id
    across."""
    asked = []
    gave_up = 0
    pat = re.compile(r"asked '%s' with" % re.escape(r["hub_id"]))
    # a deadline line names the speaker it gave up on, so a world with two
    # promoted characters in it does not count one's deadline against the
    # other
    forms = [f for f in (r["name"], r["key"], r["hub_id"]) if f]
    dead = re.compile(r"did not write .*within \d+s")
    for name, lines in runs_for(owner_row["hub_id"]):
        day = os.path.basename(name)[:10]
        for line in lines:
            if pat.search(line):
                m = TIME.match(line)
                asked.append((day, m.group(0) if m else "", line))
            elif dead.search(line) and any(f.lower() in line.lower() for f in forms):
                gave_up += 1
    turns = silent = 0
    for name, lines in runs_for(r["hub_id"]):
        for line in lines:
            if "[room] her ->" in line:
                turns += 1
            elif "had nothing to say" in line or "nothing to open" in line:
                silent += 1
    paid = [c for c in calls_for(r["hub_id"]) if c.get("role") == "peer_reply"]
    detail = ("%d asked, %d turn(s) of hers went back, %d silence(s), %d ran to a deadline; "
              "%d peer_reply call(s) paid for"
              % (len(asked), turns, silent, gave_up, len(paid)))
    if not asked:
        warn("the owner's process asks her, and her process answers",
             "no ask on record in any of the owner's runs")
    elif gave_up and gave_up >= len(asked):
        fail("the owner's process asks her, and her process answers", detail)
    elif gave_up:
        warn("the owner's process asks her, and her process answers", detail)
    else:
        ok("the owner's process asks her, and her process answers", detail)
    return asked


def check_beats(r, owner_con, her_name_forms):
    """How many beats the owner planned for each person, over the days its
    save still holds. A promoted character with none is the fault the audit
    found: the girl whose whole character is deciding where everybody goes had
    opened nothing for two days."""
    seen = []
    for key in ("cast_beats", "cast_beats_prev"):
        rec = kv(owner_con, key) or {}
        if not isinstance(rec, dict) or not rec.get("date"):
            continue
        by = collections.Counter(str(b.get("who") or "") for b in (rec.get("beats") or []))
        seen.append((rec["date"], by))
    if not seen:
        warn("the owner's planner gives her beats like everybody else",
             "the owner's save holds no planned day")
        return
    lines = []
    hers_total = 0
    for date, by in sorted(seen):
        hers = sum(n for who, n in by.items() if who in her_name_forms)
        hers_total += hers
        lines.append("%s: %d beat(s), %d hers" % (date, sum(by.values()), hers))
    detail = "; ".join(lines)
    if hers_total:
        ok("the owner's planner gives her beats like everybody else", detail)
    else:
        fail("the owner's planner gives her beats like everybody else",
             detail + " -- she is never asked to open anything")


def check_queue(her_con, cfg):
    """How old the newest row in her owner-side queue is. A row there is a
    turn waiting for the room's OWNER to file, and in her save it is a turn
    nothing will ever drain."""
    rows = kv(her_con, "room_in") or []
    if not rows:
        ok("her owner-side queue is empty", "0 row(s)")
        return
    newest = max(float(x.get("ts") or 0) for x in rows)
    age = time.time() - newest
    wait = float(getattr(cfg.exchange, "agent_beat_deadline_seconds", 600) or 600)
    detail = "%d row(s), the newest %d minute(s) old" % (len(rows), age / 60)
    if age > wait:
        fail("her owner-side queue is empty, or draining", detail)
    else:
        warn("her owner-side queue is empty, or draining", detail)


def check_record(cfg, her_con, world_path, verbose):
    """Her copy of a room against the world file's own rows for the same
    turns. The world file is the authority: the owner writes every turn of a
    room it keeps, and her record is the copy the relay left her."""
    if not world_path or not os.path.exists(world_path):
        warn("her record of a room says who really said each turn", "no world file to read")
        return
    seen = kv(her_con, "peer_rooms") or {}
    mine = {}
    for rm, blob in (seen.items() if isinstance(seen, dict) else []):
        for t in ((blob or {}).get("turns") or []):
            k = (str(rm), str(t.get("hm") or ""), str(t.get("ja") or "")[:40])
            mine[k] = str(t.get("who") or "")
    if not mine:
        warn("her record of a room says who really said each turn",
             "her record of the rooms she is in is empty")
        return
    con = ro(world_path)
    theirs = {}
    try:
        for r in con.execute("SELECT room, hm, ja, who FROM rooms").fetchall():
            theirs[(str(r[0]), str(r[1]), str(r[2])[:40])] = str(r[3])
    except sqlite3.Error:
        pass
    finally:
        con.close()
    shared = [k for k in mine if k in theirs]
    # The world file spells a person by her roster key and her own record
    # spells her by the Japanese name the record uses, so the two are
    # compared through the roster, which resolves every form of a name. A
    # comparison on the strings reported nine turns in the wrong mouth that
    # were the same girl under two spellings.
    bad = [(k, mine[k], theirs[k]) for k in shared
           if not _same_name(cfg, mine[k], theirs[k])]
    detail = "%d turn(s) of hers, %d of them the world file also has, %d in the wrong mouth" \
             % (len(mine), len(shared), len(bad))
    if bad:
        k, got, want = bad[0]
        fail("her record of a room says who really said each turn",
             detail + "; first: %s %s her record says %s, the world file says %s"
             % (k[0], k[1], got, want))
        if verbose:
            for k, got, want in bad[1:8]:
                print("         %s %s  %s -> %s" % (k[0], k[1], got, want))
    elif not shared:
        warn("her record of a room says who really said each turn",
             detail + " -- nothing to compare")
    else:
        ok("her record of a room says who really said each turn", detail)


def _same_name(cfg, a, b):
    a, b = str(a).strip(), str(b).strip()
    if not a or not b or a == b:
        return True
    try:
        from sim import roster
        if roster.same(cfg, a, b):
            return True
    except Exception:
        pass
    return a in b or b in a


def check_off_sections(cfg, her_con, since_ts):
    """Anything a switched-off section has left in her save, and whether it is
    still being written.

    Two different things live in one save and they need different answers. A
    row a section wrote BEFORE it was switched off is residue: it should be
    retired, but nothing is producing it. A row whose own stamp is newer than
    her last boot is a section that is off and still running, which is the
    fault. The table of what a section owns is the rehearsal's, so the check
    before she starts and the check after she has been running ask about the
    same keys."""
    off = []
    for sect in sorted(SECTION_KEYS):
        s = getattr(cfg, sect, None)
        if s is not None and getattr(s, "enabled", True) is False:
            off.append(sect)
    have = kv_keys(her_con)
    live, stale = [], []
    for sect in off:
        for k in SECTION_KEYS[sect]["kv"]:
            if k not in have:
                continue
            (live if _newer_than(kv(her_con, k), since_ts) else stale).append("%s: %s" % (sect, k))
        for t in SECTION_KEYS[sect]["tables"]:
            try:
                n = her_con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
            except sqlite3.Error:
                continue
            if n:
                stale.append("%s: %d row(s) in %s" % (sect, n, t))
    if live:
        fail("no section that is switched off is still writing to her save",
             "%d row(s) written since her newest boot: %s" % (len(live), "; ".join(live[:6])))
    elif stale:
        warn("no section that is switched off is still writing to her save",
             "nothing written since her boot, but %d row(s) of a switched-off section are "
             "still in the save and nothing has retired them: %s"
             % (len(stale), "; ".join(sorted(stale)[:6])))
    else:
        ok("no section that is switched off is still writing to her save",
           "%d section(s) off, nothing of theirs is there" % len(off))


def _newer_than(value, since_ts):
    """Does this stored value carry a stamp later than `since_ts`.

    A kv row is JSON of whatever shape its owner chose, so the stamp is
    looked for rather than read from a known field: a float that is a
    plausible epoch time, or a date in the machine's own format. A value with
    no stamp at all cannot be dated and is treated as old, which is the safe
    way round: it is reported as residue rather than as a live write."""
    if since_ts <= 0 or value in (None, "", [], {}):
        return False
    day = datetime.datetime.fromtimestamp(since_ts).strftime("%Y-%m-%d")
    blob = json.dumps(value, ensure_ascii=False, default=str)
    for m in re.finditer(r"\b\d{10}(?:\.\d+)?\b", blob):
        try:
            if float(m.group(0)) >= since_ts:
                return True
        except ValueError:
            pass
    # A bare date is a day and not a moment, so it can only say "after the
    # day she booted on", never "since 23:00 tonight". Counting the boot day
    # itself as newer reported three keys last written this morning as writes
    # made by a section switched off tonight.
    for m in re.finditer(r"\b(20\d\d-\d\d-\d\d)\b", blob):
        if m.group(1) > day:
            return True
    return False


def check_gauges(cfg, her_con):
    spec = set((cfg.state.gauges or {}).keys())
    stored = set((kv(her_con, "gauges") or {}).keys())
    extra, missing = sorted(stored - spec), sorted(spec - stored)
    if extra:
        fail("her store holds the gauges her config builds and no others",
             "%d in the store, %d in her config; nothing builds: %s"
             % (len(stored), len(spec), ", ".join(extra)))
    elif missing:
        warn("her store holds the gauges her config builds and no others",
             "%d declared her store has not written yet: %s" % (len(missing),
                                                                ", ".join(missing[:5])))
    else:
        ok("her store holds the gauges her config builds and no others",
           "%d gauge(s)" % len(stored))


def check_him_residue(cfg, her_con):
    from sim import existence
    if existence.has_chat(cfg) and existence.sees_him(cfg):
        ok("nothing of his is left in a save that should hold none of it",
           "she has a chat with him and a window on his machine; the question is not hers")
        return
    have = kv_keys(her_con)
    left = sorted(k for k in NO_HIM_KV if k in have)
    qs = kv(her_con, "questions") or []
    sent = kv(her_con, "sentiments") or {}
    him = [k for k in (sent if isinstance(sent, dict) else {}) if str(k).lower() == "him"]
    watch = [w for w in (kv(her_con, "watchlist") or []) if isinstance(w, dict) and w.get("his")]
    bits = []
    if left:
        bits.append("%d kv row(s): %s" % (len(left), ", ".join(left)))
    if qs:
        bits.append("%d open question(s) about him" % len(qs))
    if him:
        bits.append("a sentiment row on him")
    if watch:
        bits.append("%d watchlist title(s) flagged as his" % len(watch))
    if bits:
        fail("nothing of his is left in a save that should hold none of it", "; ".join(bits))
    else:
        ok("nothing of his is left in a save that should hold none of it",
           "%d key(s) checked, the questions, the sentiments and the watchlist" % len(NO_HIM_KV))


def check_carry(owner_con, her_name_forms):
    """A person the owner's record has carried the same thing for three days
    running. A carry is what somebody is still holding from yesterday, and the
    same sentence three days in a row is a day that is not moving."""
    lives = kv(owner_con, "cast_life") or {}
    streaks = []
    for who, rowsd in (lives.items() if isinstance(lives, dict) else []):
        carries = [str((x or {}).get("carry") or "").strip() for x in (rowsd or [])][-6:]
        run, best, prev = 0, 0, None
        for c in carries:
            if c and c == prev:
                run += 1
            else:
                run = 1 if c else 0
            prev = c
            best = max(best, run)
        if best >= 3:
            streaks.append("%s: the same thing %d day(s) running" % (who, best))
    if streaks:
        warn("nobody in the owner's record is carrying the same thing three days running",
             "; ".join(streaks[:5]))
    else:
        ok("nobody in the owner's record is carrying the same thing three days running",
           "%d person(s) with a day of their own on record" % len(lives))


def check_spin(r, minutes=10, limit=20):
    """A log line repeating faster than anything real. The presence-beat
    refusal ran once every five seconds for seven minutes with nobody at that
    table getting a turn, and nothing said so."""
    runs = runs_for(r["hub_id"], limit=1) + runs_for(_owner_key_hub(), limit=1)
    worst = None
    for name, lines in runs:
        buckets = collections.defaultdict(collections.Counter)
        for line in lines:
            m = TIME.match(line)
            if not m:
                continue
            mins = int(m.group(1)) * 60 + int(m.group(2))
            text = STAMP.sub("", line).strip()
            text = re.sub(r"\d+", "#", text)[:110]
            if not text:
                continue
            buckets[mins // minutes][text] += 1
        for _b, counter in buckets.items():
            for text, n in counter.items():
                if n > limit and (worst is None or n > worst[1]):
                    worst = (os.path.basename(name), n, text)
    if worst:
        warn("no log line is repeating faster than anything real",
             "%s: %d times in %d minutes -- %s" % (worst[0], worst[1], minutes, worst[2][:70]))
    else:
        ok("no log line is repeating faster than anything real",
           "checked the newest run of each of the two, in %d-minute windows" % minutes)


def _owner_key_hub():
    return _OWNER["hub_id"] if _OWNER else ""


def check_errors(r):
    runs = runs_for(r["hub_id"])
    tb = errs = 0
    where = ""
    for name, lines in runs:
        for line in lines:
            if "Traceback (most recent call last)" in line:
                tb += 1
                where = where or os.path.basename(name)
            elif "[error]" in line or "[loop] error:" in line:
                errs += 1
                where = where or os.path.basename(name)
    detail = "%d traceback(s), %d error line(s) over %d run(s)%s" % (
        tb, errs, len(runs), (" -- first in " + where) if where else "")
    if tb:
        fail("no traceback and no error line in her runs", detail)
    elif errs:
        warn("no traceback and no error line in her runs", detail)
    else:
        ok("no traceback and no error line in her runs", detail)


def check_cost(r, verbose):
    """What she has spent, by role, since her newest boot. Priced the way
    `tools/llmstats.py` prices it: the host's own figure when the receipt
    carries one, the slug's rates otherwise."""
    runs = runs_for(r["hub_id"], limit=1)
    if not runs:
        warn("what she has spent since her newest boot", "no run of hers on disk")
        return
    newest = os.path.basename(runs[0][0]).replace(".zip", "")
    rows = [c for c in calls_for(r["hub_id"]) if c.get("_run", "").replace(".zip", "") == newest]
    from tools import llmstats
    by = collections.defaultdict(lambda: [0, 0.0])
    for c in rows:
        usd, _how = llmstats._cost(c, c.get("usage") or {})
        b = by[c.get("role", "?")]
        b[0] += 1
        b[1] += usd
    total = sum(v[1] for v in by.values())
    top = sorted(by.items(), key=lambda kv_: -kv_[1][1])[:5]
    ok("what she has spent since her newest boot",
       "$%.4f over %d call(s) in %s; %s" % (total, len(rows), newest,
                                            ", ".join("%s %d ($%.4f)" % (k, v[0], v[1])
                                                      for k, v in top) or "nothing yet"))
    if verbose:
        for k, v in sorted(by.items(), key=lambda kv_: -kv_[1][1]):
            print("         %-16s %3d calls  $%.5f" % (k, v[0], v[1]))


# ------------------------------------------------------------------------ run

_OWNER = None


def audit(key, days=3, verbose=False):
    global _OWNER
    from tools import registry
    rows = registry.characters()
    r = next((x for x in rows if x["key"] == key), None)
    if not r:
        raise SystemExit("[audit] %r is not in the register (%s)"
                         % (key, ", ".join(x["key"] for x in rows)))
    man = {}
    p = os.path.join(ROOT, "characters", key, "bundle.json")
    if os.path.exists(p):
        man = json.load(io.open(p, encoding="utf-8"))
    world = man.get("world") or {}
    world_id = str(world.get("id") or "")
    for x in rows:
        b = os.path.join(ROOT, "characters", x["key"], "bundle.json")
        if x["key"] == key or not os.path.exists(b):
            continue
        w = (json.load(io.open(b, encoding="utf-8")).get("world") or {})
        if str(w.get("id") or "") == world_id and w.get("owner"):
            _OWNER = x
            break

    print("[audit] %s (%s), %s" % (r["name"], key,
                                   "a reader of the world %r, which %s keeps"
                                   % (world_id, _OWNER["key"]) if _OWNER
                                   else "no other registered character keeps her world"))
    print("[audit] read-only: her save and the world file through mode=ro URIs, her config "
          "on a copy, the runs where they lie")
    print()

    cfg = config_of(r)
    her_con = ro(os.path.join(ROOT, r["db"]))
    owner_con = ro(os.path.join(ROOT, _OWNER["db"])) if _OWNER else None
    world_path = os.path.join(ROOT, "data", "worlds", world_id, "world.db") if world_id else ""

    try:
        check_process(r, processes())
        check_hub(r, cfg)
        if _OWNER:
            check_asks(r, _OWNER, days)
            forms = _name_forms(cfg, r)
            check_beats(r, owner_con, forms)
            check_carry(owner_con, forms)
        else:
            warn("the owner's process asks her, and her process answers",
                 "she reads nobody's world")
        check_queue(her_con, cfg)
        check_record(cfg, her_con, world_path, verbose)
        check_off_sections(cfg, her_con, _booted_ts(r))
        check_gauges(cfg, her_con)
        check_him_residue(cfg, her_con)
        check_spin(r)
        check_errors(r)
        check_cost(r, verbose)
    finally:
        her_con.close()
        if owner_con:
            owner_con.close()

    print()
    bad = [x for x in ROWS if x[0] == "FAIL"]
    soft = [x for x in ROWS if x[0] == "WARN"]
    print("[audit] %d ok, %d WARN, %d FAIL" % (len(ROWS) - len(bad) - len(soft),
                                               len(soft), len(bad)))
    for state, what, _d in ROWS:
        if state in ("FAIL", "WARN"):
            print("   %-4s %s" % (state, what))
    return 1 if bad else 0


def _booted_ts(r):
    """When her newest run started, machine local. A run directory is named
    for the wall clock the process opened it at, sometimes with a letter after
    it when two started inside one second."""
    runs = runs_for(r["hub_id"], limit=1)
    if not runs:
        return 0.0
    name = os.path.basename(runs[0][0]).replace(".zip", "")
    try:
        return datetime.datetime.strptime(name[:19], "%Y-%m-%d_%H-%M-%S").timestamp()
    except ValueError:
        return 0.0


def _name_forms(cfg, r):
    """Every form of her name the owner's record might spell her by."""
    ch = cfg.character
    out = {str(getattr(ch, "name", "") or ""), str(getattr(ch, "name_ja", "") or ""),
           r["name"], r["key"]}
    try:
        from sim import roster
        me = roster.key_of(cfg, ch.name)
        out |= {me, roster.record_name(cfg, me)}
    except Exception:
        pass
    return {x for x in out if x}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("key", help="a registered character who runs herself")
    ap.add_argument("--days", type=int, default=3, help="how far back to read the runs")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    return audit(args.key, days=args.days, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
