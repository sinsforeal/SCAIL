"""MyAnimeList episode-level watch history: backfill, live watch, and analysis.

MAL's API and RSS give list state and coarse "recently watched" items, but not
the per-episode timestamps ("Ep 13, watched on 05/10/2024 at 12:26"). Those
live behind the logged-in Edit -> History panel, served by
`ajaxtb.php?detailedaid=<id>`. This tool drives a logged-in Chrome (Selenium,
its own profile `F:/Chrome_Profiles/SCAIL_mal` -- never another program's
`<chrome-profiles>/tv`, and never the account profile) to read that
panel for every anime, into a
SQLite DB tied to the real anime (id, titles, studios, genres...). It also
watches the public /history page for new episodes as they happen and enriches
them with the exact minute, so the bot can know precisely when he watched an
episode -- and so he has his own data to analyse.

    python tools/mal_history.py login              # open Chrome, log into MAL once (persists)
    python tools/mal_history.py sync               # refresh the anime table (public, no login)
    python tools/mal_history.py backfill           # scrape every anime's episode history
    python tools/mal_history.py backfill --statuses 2 --limit 20
    python tools/mal_history.py daemon                 # forever: list sync + new episodes + periodic
                                                       #   panel reconcile (run.cmd launches this)
    python tools/mal_history.py export                 # CSV: data/mal_export/{episodes,anime}.csv
    python tools/mal_history.py report                 # personal analysis over the DB
    python tools/mal_history.py report --anime "16bit"

The DB is `data/mal_history.db`. Times are as MAL renders them (his MAL profile
timezone); the raw string is kept alongside every row.
"""

import os
import re
import sys
import time
import json
import html
import io
import sqlite3
import collections
import datetime
import argparse
import urllib.error
import urllib.request

USERNAME = os.environ.get("SCAIL_MAL_USER", "")
PROFILE_DIR = r"F:\Chrome_Profiles\SCAIL_mal"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mal_history.db")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
STATUS = {1: "watching", 2: "completed", 3: "on_hold", 4: "dropped", 6: "plan_to_watch"}
AJAXTB = "https://myanimelist.net/ajaxtb.php?keepThis=true&detailedaid={id}&TB_iframe=true"
HISTORY = "https://myanimelist.net/history/{user}/anime"
LOADJSON = "https://myanimelist.net/animelist/{user}/load.json?status=7&offset={off}"

EP_RE = re.compile(r"Ep\s+(\d+),\s*watched on\s+(\d{1,2}/\d{1,2}/\d{4})\s+at\s+(\d{1,2}:\d{2})", re.I)


# --------------------------------------------------------------------------- DB

def db(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS anime (
        anime_id INTEGER PRIMARY KEY,
        title TEXT, title_eng TEXT, media_type TEXT, num_episodes INTEGER,
        status INTEGER, score INTEGER, watched_episodes INTEGER,
        genres TEXT, studios TEXT, demographics TEXT,
        start_date TEXT, finish_date TEXT, tags TEXT, notes TEXT,
        updated_at INTEGER, last_scraped INTEGER, history_count INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS episodes (
        anime_id INTEGER, ep INTEGER, watched_at TEXT, raw TEXT, source TEXT,
        scraped_at INTEGER,
        PRIMARY KEY (anime_id, ep, watched_at)
    );
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
    CREATE INDEX IF NOT EXISTS idx_ep_time ON episodes(watched_at);
    -- per-title detail from the official API v2 (exact episode duration,
    -- studios, the full genre/theme/demographic set, source, season, MAL mean)
    CREATE TABLE IF NOT EXISTS anime_detail (
        anime_id INTEGER PRIMARY KEY,
        avg_episode_seconds INTEGER, api_genres TEXT, studios TEXT, source TEXT,
        season_year INTEGER, season TEXT, mal_mean REAL, rating TEXT,
        api_media_type TEXT, api_num_episodes INTEGER, fetched_at INTEGER
    );
    """)
    # WHEN THE PAGE WAS READ, for a row whose label was relative. "Yesterday,
    # 6:05 PM" means nothing without the day it was read on, and a row
    # written before this column existed cannot be checked against anything.
    cols = {r[1] for r in con.execute("PRAGMA table_info(episodes)")}
    if "scraped_at" not in cols:
        con.execute("ALTER TABLE episodes ADD COLUMN scraped_at INTEGER")
    con.commit()
    return con


# --------------------------------------------------------------------- log

def open_log(path):
    """Point stdout and stderr at a file for the rest of the run.

    The daemon runs as `pythonw` with no console, and the launcher's `>>`
    redirect binds to cmd's `start` rather than to the process it detaches, so
    every line printed between 2026-08-27 and 2026-09-04 was written to a
    handle that goes nowhere. Eight days of `poll error:` lines are simply
    gone, and the one question anybody wanted the log for -- did the fetches
    fail, and when -- could not be answered from it.

    Line-buffered and utf-8, because a title on his list is not ASCII and a
    crash in the encoder would take the daemon with it. Kept as a tee when
    there IS a console, so running it in the foreground still shows its work.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        fh = io.open(path, "a", encoding="utf-8", errors="replace", buffering=1)
    except OSError as e:
        print(f"[daemon] the log {path} could not be opened: {type(e).__name__}", flush=True)
        return None

    class _Tee:
        def write(self, text):
            fh.write(text)
            try:
                if _console:
                    _console.write(text)
            except Exception:
                pass
            return len(text)

        def flush(self):
            fh.flush()
            try:
                if _console:
                    _console.flush()
            except Exception:
                pass

        def isatty(self):
            return False

    _console = None
    try:
        # pythonw's stdout is not a usable stream; a console python's is
        if sys.stdout is not None and sys.stdout.fileno() >= 0:
            _console = sys.stdout
    except Exception:
        _console = None
    tee = _Tee()
    sys.stdout = sys.stderr = tee
    print("=" * 70)
    print(f"[daemon] pid {os.getpid()} starting at "
          f"{datetime.datetime.now().isoformat(timespec='seconds')}; logging to {path}")
    return tee


# ------------------------------------------------------------- outage watcher

# The community wrapper in front of MyAnimeList. NOTHING in this project reads
# data from it and nothing may be made to: it has answered 504 on every path
# that needs a live fetch since 2026-08-28 while MyAnimeList's own origin
# answered the equivalent page in under a second throughout
# (`data/retired/20260904_jikan_504/REPORT.md`). This is the one request that
# ever goes to it, and its answer is recorded and never used.
#
# The path has to be one the wrapper CANNOT serve out of its own cache, or the
# probe reports "up" while every real path fails -- which is what happened
# during the outage: `/anime/1` returned 200 from cache while the searches and
# the cast endpoints all returned 504. A one-letter search rotated by the hour
# is a distinct cache key every hour and the same 26 keys over a day, so the
# wrapper is asked for genuinely fresh work without being asked for much.
JIKAN_WATCH = "https://api.jikan.moe/v4/anime?limit=1&q={q}"
JIKAN_UA = "SCAIL/1.0 outage watcher (one request an hour, no retry; data comes from myanimelist.net)"


def jikan_watch(con, min_interval=3600.0):
    """At most one request an hour: is the wrapper answering yet?

    Records `jikan_status` (the HTTP code, or the exception type), the time,
    and `jikan_state` (up / down) in the mirror's `meta` table, and prints one
    line only when the state has CHANGED, so the log carries the day the
    outage began and the day it ended and nothing in between. Never raises:
    the poll it is called from must not lose a cycle over this."""
    try:
        last = float(meta_get(con, "jikan_checked_at", 0) or 0)
    except (TypeError, ValueError):
        last = 0.0
    now = time.time()
    if now - last < min_interval:
        return None
    q = chr(ord("a") + int(now // 3600) % 26)
    status, state = "", "down"
    try:
        req = urllib.request.Request(JIKAN_WATCH.format(q=q), headers={"User-Agent": JIKAN_UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            status = str(r.status)
            state = "up" if 200 <= r.status < 300 else "down"
    except urllib.error.HTTPError as e:
        status = str(e.code)
    except Exception as e:
        status = type(e).__name__
    was = meta_get(con, "jikan_state", "")
    try:
        meta_set(con, "jikan_status", status)
        meta_set(con, "jikan_checked_at", int(now))
        meta_set(con, "jikan_state", state)
    except sqlite3.Error as e:
        print(f"  jikan watch not recorded: {type(e).__name__}: {e}", flush=True)
    if state != was:
        since = ""
        if was:
            since = f" (it was {was} until now)"
        print(f"[jikan] the wrapper is {state.upper()} -- /anime?q={q} answered {status}{since}. "
              f"Nothing here reads it; MyAnimeList's own pages are the source.", flush=True)
    return state


def meta_get(con, key, default=None):
    r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r[0] if r else default


def meta_set(con, key, value):
    con.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
    con.commit()


# ----------------------------------------------------------------- list (public)

def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def fetch_list(username=USERNAME):
    """The site's own list JSON (all statuses, paged by 300). No login."""
    out, off = [], 0
    while True:
        page = json.loads(_get(LOADJSON.format(user=username, off=off)))
        if not isinstance(page, list) or not page:
            break
        out.extend(page)
        if len(page) < 300:
            break
        off += 300
    return out


def _note_status(con, anime_id, title, new_status, watched):
    """Record a status change before it is overwritten.

    The anime table holds only what is true now, so watching -> dropped, and
    the quieter one where a show he was watching turns up in plan_to_watch
    again with five episodes behind it, both vanished the moment they
    happened. Only transitions are stored, so this stays small."""
    con.execute("""CREATE TABLE IF NOT EXISTS status_log (
        anime_id INTEGER, title TEXT, was INTEGER, now INTEGER,
        watched INTEGER, at TEXT)""")
    row = con.execute("SELECT status FROM anime WHERE anime_id=?", (anime_id,)).fetchone()
    old = row[0] if row else None
    if old is None or old == new_status:
        return None
    con.execute("INSERT INTO status_log (anime_id,title,was,now,watched,at) VALUES (?,?,?,?,?,?)",
                (anime_id, title, old, new_status, watched,
                 datetime.datetime.now().isoformat(timespec="seconds")))
    return (old, new_status)


def sync_anime(con, username=USERNAME, verbose=True):
    entries = fetch_list(username)
    n = 0
    moved = []
    for e in entries:
        ch = _note_status(con, e.get("anime_id"), e.get("anime_title"),
                          e.get("status"), e.get("num_watched_episodes"))
        if ch:
            moved.append((e.get("anime_title"), STATUS.get(ch[0], ch[0]), STATUS.get(ch[1], ch[1])))
        con.execute("""
            INSERT INTO anime (anime_id,title,title_eng,media_type,num_episodes,status,score,
                watched_episodes,genres,studios,demographics,start_date,finish_date,tags,notes,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(anime_id) DO UPDATE SET
                title=excluded.title, title_eng=excluded.title_eng, media_type=excluded.media_type,
                num_episodes=excluded.num_episodes, status=excluded.status, score=excluded.score,
                watched_episodes=excluded.watched_episodes, genres=excluded.genres, studios=excluded.studios,
                demographics=excluded.demographics, start_date=excluded.start_date, finish_date=excluded.finish_date,
                tags=excluded.tags,
                -- An empty incoming note means "this fetch could not see it",
                -- not "he deleted it". `comments` only comes back on the
                -- LOGGED-IN fetch; the plain one omits the field entirely for
                -- all 698 entries. Writing it straight through wiped all 81
                -- notes the moment an unauthenticated sync ran, and since
                -- `mal_monitor.poll_notes` keys on a hash of the text, the
                -- refill would then have been reported to her as him writing
                -- every one of them again. A stale note costs nothing; a lost
                -- one costs the only record of what he thought of a series.
                notes=CASE WHEN TRIM(COALESCE(excluded.notes,'')) <> ''
                           THEN excluded.notes ELSE anime.notes END,
                updated_at=excluded.updated_at
        """, (
            e.get("anime_id"), e.get("anime_title"), e.get("anime_title_eng"),
            e.get("anime_media_type_string"), e.get("anime_num_episodes"), e.get("status"),
            e.get("score"), e.get("num_watched_episodes"),
            json.dumps([g.get("name") if isinstance(g, dict) else g for g in (e.get("genres") or [])], ensure_ascii=False),
            json.dumps([s.get("name") if isinstance(s, dict) else s for s in (e.get("anime_studios") or [])], ensure_ascii=False),
            json.dumps([d.get("name") if isinstance(d, dict) else d for d in (e.get("demographics") or [])], ensure_ascii=False),
            e.get("start_date_string"), e.get("finish_date_string"),
            # `tags` is a list like genres and studios above. `json.dumps(x or "")`
            # turned an empty list into the string '""', which is what all 698
            # rows held; a real tag would have been stored as a bare string too.
            json.dumps([t.get("name") if isinstance(t, dict) else t for t in (e.get("tags") or [])], ensure_ascii=False),
            # MAL calls the per-entry note `comments`. There is no `notes` key in
            # the list JSON at all, so this read "" on every sync and blanked the
            # column -- the only reason the DB held any was that the much slower
            # panel reconcile refilled it afterwards. Between a sync and a
            # reconcile every note was gone, and `mal_monitor.poll_notes` hashes
            # the text, so that blank-and-refill would have reported the same
            # note to her as new each time round.
            (e.get("comments") or "")[:500],
            e.get("updated_at"),
        ))
        n += 1
    con.commit()
    if verbose:
        print(f"[sync] {n} anime in the list -> DB")
        for title, was, now in moved[:12]:
            print(f"  ~ {title[:44]}: {was} -> {now}")
    return n


# ----------------------------------------------------------------- ajaxtb parse

def parse_episode_history(text_or_html):
    """From the ajaxtb panel body -> [(ep:int, watched_at:iso, raw:str)]. Tolerant
    of markup: strips tags, then reads 'Ep N, watched on MM/DD/YYYY at HH:MM'."""
    if not text_or_html or "Not logged in" in text_or_html:
        return None if (text_or_html or "").strip() == "Not logged in" else []
    text = re.sub(r"<[^>]+>", " ", text_or_html)
    text = html.unescape(text)
    rows = []
    for m in EP_RE.finditer(text):
        ep = int(m.group(1))
        mm, dd, yy = m.group(2).split("/")
        hh, mi = m.group(3).split(":")
        try:
            dt = datetime.datetime(int(yy), int(mm), int(dd), int(hh), int(mi))
        except ValueError:
            continue
        rows.append((ep, dt.isoformat(timespec="minutes"), m.group(0).strip()))
    return rows


# --------------------------------------------------------------- history (public)

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


# THE PUBLIC HISTORY PAGE IS ON MYANIMELIST'S OWN CLOCK, NOT HIS. It is
# fetched without a login, so the site renders every time in its own timezone;
# the panel behind the login renders his account's, which is this machine's.
# The two are three hours apart on every row where both exist (112 of them),
# and his player settles which is true: Mitsudomoe episode 13 opened at 20:30:16 and the panel says 21:05, while the page said 6:05 PM.
# The same three hours is why a relative label lands a day out: "Yesterday" on
# the page means the SITE's yesterday, so between midnight here and midnight
# there this machine's yesterday is a day later, and 34 rows were filed a day
# late with the identical label beside the correct one.
MAL_SITE_TZ = "America/Los_Angeles"
SITE_BEHIND_LOCAL_HOURS = 3.0      # only used if the zone database is missing


def _site_zone():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(MAL_SITE_TZ)
    except Exception:
        return None


def _site_now(now=None):
    """(now on MAL's clock, now here). What its page means by "Today" is the
    first; the second is what a time on its clock has to be converted to."""
    local = (now or datetime.datetime.now())
    if local.tzinfo is None:
        local = local.astimezone()
    zone = _site_zone()
    if zone is None:
        return local.replace(tzinfo=None) - datetime.timedelta(hours=SITE_BEHIND_LOCAL_HOURS), local
    return local.astimezone(zone).replace(tzinfo=None), local


def _site_to_local(site_naive, local_now):
    """A time on MAL's clock, as the same moment on this machine's."""
    zone = _site_zone()
    if zone is None:
        return site_naive + datetime.timedelta(hours=SITE_BEHIND_LOCAL_HOURS)
    return site_naive.replace(tzinfo=zone).astimezone(local_now.tzinfo).replace(tzinfo=None)


def _resolve_history_time(when, now=None):
    """MAL history renders relative/short times: 'Today, 1:19 PM',
    'Yesterday, ...', 'Aug 16, 4:13 PM' (this year), or 'MM-DD-YY, H:MM AM'.

    Every one of them is resolved against the SITE's own calendar and clock
    and then converted to this machine's, which is the clock every other
    stamp in this store and in the bots is on."""
    site, local_now = _site_now(now)
    when = when.replace("\xa0", " ").strip()
    dt = None
    m = re.match(r"(Today|Yesterday),?\s+(\d{1,2}):(\d{2})\s*([AP]M)", when, re.I)
    if m:
        base = site.date() - datetime.timedelta(days=1 if m.group(1).lower() == "yesterday" else 0)
        h = int(m.group(2)) % 12 + (12 if m.group(4).upper() == "PM" else 0)
        dt = datetime.datetime(base.year, base.month, base.day, h, int(m.group(3)))
    if dt is None:
        m = re.match(r"([A-Za-z]{3})\s+(\d{1,2}),?\s+(\d{1,2}):(\d{2})\s*([AP]M)", when)
        if m and m.group(1).title() in _MONTHS:
            mo, dd = _MONTHS[m.group(1).title()], int(m.group(2))
            h = int(m.group(3)) % 12 + (12 if m.group(5).upper() == "PM" else 0)
            dt = datetime.datetime(site.year, mo, dd, h, int(m.group(4)))
            if dt > site + datetime.timedelta(days=1):   # month-name with no year: last year
                dt = dt.replace(year=site.year - 1)
    if dt is None:
        m = re.match(r"(\d{1,2})-(\d{1,2})-(\d{2}),?\s+(\d{1,2}):(\d{2})\s*([AP]M)", when)
        if m:
            mo, dd, yy = int(m.group(1)), int(m.group(2)), 2000 + int(m.group(3))
            h = int(m.group(4)) % 12 + (12 if m.group(6).upper() == "PM" else 0)
            dt = datetime.datetime(yy, mo, dd, h, int(m.group(5)))
    if dt is None:
        return None
    return _site_to_local(dt, local_now).isoformat(timespec="minutes")


def parse_history_page(page, now=None):
    """Public /history/<user>/anime -> [(anime_id, ep, watched_at_iso_or_None, raw)]."""
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        a = re.search(r"/anime(?:\.php\?id=|/)(\d+)", tr)
        ep = re.search(r"ep\.\s*<strong>\s*(\d+)", tr, re.S)
        tm = re.search(r'align="right"[^>]*>\s*&nbsp;([^<]+)', tr)
        if a and ep and tm:
            when = html.unescape(tm.group(1)).strip()
            rows.append((int(a.group(1)), int(ep.group(1)), _resolve_history_time(when, now), when))
    return rows


# --------------------------------------------------------------------- selenium

def migrate_episode_stamps(con, dry=True, out=print):
    """Bring the rows written before the site's clock was understood into
    line with the panel's, and take out the duplicates one watch produced.

    Two rules, in this order.

    1. A row from the public history page for a (work, episode) the LOGGED-IN
       PANEL also has is dropped. The panel is the stamp of record -- it is
       rendered on his account's clock, which is this machine's -- and the
       page's row was a second row for one watch, three hours early and
       sometimes a day out.
    2. A page row the panel does NOT have keeps its watch and moves to the
       right clock: its stored time was read as though the page had been
       rendered here, so it is re-read as a time on the site's clock and
       converted. Where a relative label was read between local midnight and
       the site's, the same label produced two rows a day apart; the earlier
       of the two is the one taken from the aligned reading, and the later is
       dropped.

    Every row that changes is printed with its stamp before and after.
    Returns (dropped, moved). `dry=True` changes nothing."""
    rows = con.execute("SELECT anime_id, ep, watched_at, raw, source, scraped_at FROM episodes "
                       "ORDER BY anime_id, ep, watched_at").fetchall()
    panel = {(a, e) for a, e, _w, _r, s, _t in rows if s == "ajaxtb"}
    dropped, moved = 0, 0
    for aid, ep, watched, raw, source, _stamp in rows:
        if source == "ajaxtb" or (aid, ep) not in panel:
            continue
        title = con.execute("SELECT title FROM anime WHERE anime_id=?", (aid,)).fetchone()
        keeps = sorted(w for a, e, w, _r, s, _t in rows if s == "ajaxtb" and a == aid and e == ep)
        out(f"  drop  {str(title[0] if title else aid)[:36]:36s} ep {ep:>3}  "
            f"{watched}  ({raw})  -> the panel has it at {', '.join(keeps)}")
        dropped += 1
        if not dry:
            con.execute("DELETE FROM episodes WHERE anime_id=? AND ep=? AND watched_at=? AND source=?",
                        (aid, ep, watched, source))
    # What the panel never had: one row per label, on the right clock. Only a
    # row with no scrape stamp on it, because that is what "written before
    # the site's clock was understood" looks like from here -- a row three
    # hours out is not distinguishable from a correct one by reading it, so
    # running this twice would move it twice. Every row the corrected code
    # writes carries the moment its page was read.
    left = [r for r in rows if r[4] != "ajaxtb" and (r[0], r[1]) not in panel and not r[5]]
    seen = {}
    for aid, ep, watched, raw, source, _stamp in left:
        key = (aid, ep, raw)
        if key in seen:
            title = con.execute("SELECT title FROM anime WHERE anime_id=?", (aid,)).fetchone()
            out(f"  drop  {str(title[0] if title else aid)[:36]:36s} ep {ep:>3}  "
                f"{watched}  ({raw})  -> the same label already read on {seen[key]}")
            dropped += 1
            if not dry:
                con.execute("DELETE FROM episodes WHERE anime_id=? AND ep=? AND watched_at=? AND source=?",
                            (aid, ep, watched, source))
            continue
        seen[key] = watched
        try:
            stored = datetime.datetime.fromisoformat(watched)
        except (TypeError, ValueError):
            continue
        fixed = _site_to_local(stored, datetime.datetime.now().astimezone()
                               ).isoformat(timespec="minutes")
        if fixed == watched:
            continue
        title = con.execute("SELECT title FROM anime WHERE anime_id=?", (aid,)).fetchone()
        out(f"  move  {str(title[0] if title else aid)[:36]:36s} ep {ep:>3}  "
            f"{watched}  ->  {fixed}  ({raw})")
        moved += 1
        if not dry:
            con.execute("UPDATE episodes SET watched_at=?, scraped_at=? WHERE anime_id=? "
                        "AND ep=? AND watched_at=? AND source=?",
                        (fixed, int(time.time()), aid, ep, watched, source))
    if not dry:
        con.commit()
    out(f"  {dropped} row(s) dropped, {moved} row(s) moved"
        + ("  (nothing written: this was a dry run)" if dry else ""))
    return dropped, moved


def cmd_migrate_stamps(args):
    """`python tools/mal_history.py migrate-stamps [--apply]`. THE DAEMON MUST
    BE STOPPED: it writes this table every five minutes."""
    con = db()
    n = con.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    print(f"[migrate] {n} episode row(s) in {DB_PATH}")
    if getattr(args, "backup", ""):
        import csv
        with io.open(args.backup, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["anime_id", "ep", "watched_at", "raw", "source"])
            w.writerows(con.execute("SELECT anime_id,ep,watched_at,raw,source FROM episodes "
                                    "ORDER BY anime_id, ep, watched_at"))
        print(f"[migrate] the table as it stands, copied to {args.backup}")
    migrate_episode_stamps(con, dry=not args.apply)
    print(f"[migrate] {con.execute('SELECT COUNT(*) FROM episodes').fetchone()[0]} row(s) now")


def _extension_dir():
    """Ad blocker path from config.json, so the bot and this tool agree."""
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "config.json"), "r", encoding="utf-8") as fh:
            return json.load(fh).get("sensors", {}).get("chrome_extension_dir", "")
    except Exception:
        return ""


def make_driver(headless=False, profile=PROFILE_DIR):
    from selenium import webdriver
    # Whatever happened to the last run, this one owns the profile. `quit()` in
    # a finally covers a clean exit and a Ctrl-C; it does not cover the console
    # window being closed or a force-kill, and neither of those runs Python's
    # exit path at all. The daemon's Chrome had been up since 2026-08-20 across
    # several restarts of everything around it, holding the profile lock.
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from sensors import chrome_reaper
        chrome_reaper.kill(profile, log=print)
    except Exception as e:
        print(f"[chrome] could not reap the old profile: {type(e).__name__}: {e}")
    opts = webdriver.ChromeOptions()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"user-agent={UA}")
    opts.add_argument(f"user-data-dir={profile}")
    # same ad blocker as the X scraper: MAL serves ads inside the pages this
    # reads, and a blocked request is one that never becomes data
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from sensors import chrome_ext
        chrome_ext.apply(opts, _extension_dir(), profile, log=print)
    except Exception as e:
        print(f"[chrome] extension not applied: {type(e).__name__}")
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1280,900")
    driver = webdriver.Chrome(options=opts)
    driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    try:
        from sensors import chrome_ext as _ce
        _ce.settle(driver, log=print)
    except Exception:
        pass
    return driver


def _fetch_in_page(driver, url, timeout=20):
    """Fetch a URL from within the myanimelist.net origin, reusing the login
    cookies, without a full navigation."""
    driver.set_script_timeout(timeout)
    js = ("var cb=arguments[arguments.length-1];"
          "fetch(arguments[0],{credentials:'include'})"
          ".then(r=>r.text()).then(t=>cb(t)).catch(e=>cb('FETCHERR:'+e));")
    return driver.execute_async_script(js, url)


def _is_logged_in_nonav(driver):
    """Check login without navigating the window (so a login in progress is not
    disturbed): fetch the panel from within the current MAL-origin page."""
    try:
        body = _fetch_in_page(driver, AJAXTB.format(id=1))
    except Exception:
        return False
    return not (body or "").strip().startswith("Not logged in")


def logged_in(driver):
    driver.get("https://myanimelist.net/")
    time.sleep(2)
    return _is_logged_in_nonav(driver)


# --------------------------------------------------------------------- commands

def cmd_login(args):
    driver = make_driver(headless=False)
    try:
        driver.get("https://myanimelist.net/login.php")
        print("A Chrome window opened on the MAL login page.", flush=True)
        print("Log in as yourself in that window; I'm watching for it (no keypress needed).", flush=True)
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            time.sleep(6)
            if _is_logged_in_nonav(driver):
                print("LOGIN OK — session saved to the profile; future runs reuse it.", flush=True)
                return
            print(f"  ...waiting for login ({int(deadline - time.time())}s left)", flush=True)
        print("Timed out waiting for login. Re-run: python tools/mal_history.py login", flush=True)
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def _upsert_episodes(con, anime_id, rows, source, scraped_at=None):
    """One row per (work, episode) watch, and the LIST'S OWN PANEL is the
    stamp of record.

    The panel is read behind the login, so its times are on his account's
    clock, which is this machine's; the public history page is read without
    one and its times are the site's, three hours behind. Both used to be
    inserted, and the primary key carries the stamp, so one watch became two
    rows -- Mitsudomoe episode 13 at 21:05 from the panel and at 18:05 from
    the page. So a page row is not written where the panel has one, and a
    panel row takes any page row for that episode out with it.

    The panel can hold two rows for one episode legitimately (he marked it
    twice), and both are kept: it is the source of record and that is what it
    recorded."""
    added = 0
    stamp = int(scraped_at if scraped_at is not None else time.time())
    for ep, watched_at, raw in rows:
        if source == "ajaxtb":
            con.execute("DELETE FROM episodes WHERE anime_id=? AND ep=? AND source='history'",
                        (anime_id, int(ep)))
        elif con.execute("SELECT 1 FROM episodes WHERE anime_id=? AND ep=? AND source='ajaxtb'",
                         (anime_id, int(ep))).fetchone():
            continue
        cur = con.execute(
            "INSERT OR IGNORE INTO episodes(anime_id,ep,watched_at,raw,source,scraped_at) "
            "VALUES(?,?,?,?,?,?)",
            (anime_id, ep, watched_at, raw, source, stamp))
        added += cur.rowcount
    con.commit()
    return added


def cmd_backfill(args):
    con = db()
    if not args.no_sync:
        sync_anime(con)
    statuses = [int(s) for s in args.statuses.split(",")] if args.statuses else [2, 4, 1, 3, 6]
    q = ("SELECT anime_id,title,status,watched_episodes,updated_at,last_scraped,history_count "
         "FROM anime WHERE status IN (%s)" % ",".join("?" * len(statuses)))
    todo = con.execute(q, statuses).fetchall()
    # scrape those with progress first; skip fully-scraped-and-unchanged unless --force
    work = []
    for aid, title, status, watched, updated, last_scraped, hcount in todo:
        if not args.force and last_scraped and (updated or 0) <= (int(last_scraped) if last_scraped else 0) and hcount:
            continue
        if (watched or 0) == 0 and status != 2:
            continue
        work.append((aid, title, status, watched))
    if args.limit:
        work = work[:args.limit]
    print(f"[backfill] {len(work)} anime to scrape (of {len(todo)} in statuses {statuses})")
    if not work:
        return
    driver = make_driver(headless=args.headless)
    try:
        if not logged_in(driver):
            print("Not logged in. Run:  python tools/mal_history.py login")
            return
        for i, (aid, title, status, watched) in enumerate(work, 1):
            try:
                body = _fetch_in_page(driver, AJAXTB.format(id=aid))
                rows = parse_episode_history(body)
                if rows is None:
                    print("  ! session dropped mid-run; re-run `login`")
                    break
                added = _upsert_episodes(con, aid, rows, "ajaxtb")
                con.execute("UPDATE anime SET last_scraped=?, history_count=? WHERE anime_id=?",
                            (int(time.time()), len(rows), aid))
                con.commit()
                print(f"  [{i}/{len(work)}] {str(title)[:45]:45s} eps_logged={len(rows):3d} (+{added} new)")
            except Exception as e:
                print(f"  [{i}/{len(work)}] {str(title)[:45]:45s} ERROR {e}")
            time.sleep(args.delay + (0.6 if i % 7 == 0 else 0))  # polite, mild jitter
    finally:
        driver.quit()
    total = con.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    print(f"[backfill] done. {total} episode rows total.")


def cmd_watch(args):
    con = db()
    print(f"[watch] polling the public history page every {args.interval}s; Ctrl-C to stop.")
    driver = None
    try:
        while True:
            try:
                sync_anime(con, verbose=False)
                page = _get(HISTORY.format(user=USERNAME))
                seen = parse_history_page(page)
                fresh = []
                for aid, ep, watched_at, raw in seen:
                    if watched_at and not con.execute(
                            "SELECT 1 FROM episodes WHERE anime_id=? AND ep=? AND watched_at=?",
                            (aid, ep, watched_at)).fetchone():
                        fresh.append((aid, ep, watched_at, raw))
                if fresh and args.enrich:
                    # exact minute from ajaxtb for the changed anime (needs login)
                    if driver is None:
                        driver = make_driver(headless=True)
                        if not logged_in(driver):
                            print("  (not logged in; using public-page times. run `login` for exact minutes)")
                    for aid in {a for a, _, _, _ in fresh}:
                        try:
                            rows = parse_episode_history(_fetch_in_page(driver, AJAXTB.format(id=aid)))
                            if rows:
                                _upsert_episodes(con, aid, rows, "ajaxtb")
                        except Exception:
                            pass
                for aid, ep, watched_at, raw in fresh:
                    _upsert_episodes(con, aid, [(ep, watched_at, raw)], "history")
                    t = con.execute("SELECT title FROM anime WHERE anime_id=?", (aid,)).fetchone()
                    print(f"  [{watched_at}] {t[0] if t else aid} ep {ep}")
                meta_set(con, "watch_last_ts", int(time.time()))
            except Exception as e:
                print(f"  poll error: {e}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[watch] stopped.")
    finally:
        if driver:
            driver.quit()


def _reconcile(con, driver, delay=1.4, force=False, verbose=True):
    """Re-scrape the panel for every anime whose list row changed since we last
    scraped it (or all if force). This is what makes the DB authoritative even
    when the public-history poll was down: nothing relies on the shallow page."""
    rows = con.execute("SELECT anime_id,title,status,watched_episodes,updated_at,last_scraped FROM anime").fetchall()
    work = []
    for aid, title, status, watched, updated, last in rows:
        if (watched or 0) == 0 and status != 2:
            continue
        if force or not last or (updated or 0) > int(last or 0):
            work.append((aid, title))
    if verbose:
        print(f"[reconcile] {len(work)} anime changed since last scrape", flush=True)
    added_total = 0
    for i, (aid, title) in enumerate(work, 1):
        try:
            rows_ = parse_episode_history(_fetch_in_page(driver, AJAXTB.format(id=aid)))
            if rows_ is None:
                print("  ! session dropped; run `login`", flush=True)
                return added_total, False
            added = _upsert_episodes(con, aid, rows_, "ajaxtb")
            added_total += added
            con.execute("UPDATE anime SET last_scraped=?, history_count=? WHERE anime_id=?",
                        (int(time.time()), len(rows_), aid))
            con.commit()
            if verbose and added:
                print(f"  {str(title)[:45]:45s} +{added} episode(s)", flush=True)
        except Exception as e:
            print(f"  {str(title)[:45]:45s} ERROR {e}", flush=True)
        time.sleep(delay)
    return added_total, True


def _daemon_alive(pid):
    """Is the pid in the lock file actually another daemon.

    The old check was `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` and
    treated any handle as proof of life. **OpenProcess succeeds on a process
    that has already exited** while its kernel object is still referenced, so a
    force-killed daemon looked alive to the next one: the restart printed
    "already running (pid 13880); exiting", refused to start, and left the
    orphaned Chrome holding the profile. That is the whole of the "it orphans
    MAL on restart" complaint -- the restart never happened.

    psutil is already a dependency and gets this right, and the cmdline check
    is the other half: pids are recycled, and an unrelated process landing on
    the old number would otherwise block the daemon forever."""
    if not pid:
        return False
    try:
        import psutil
        p = psutil.Process(pid)
        if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
            return False
        return "mal_history" in " ".join(p.cmdline() or [])
    except Exception:
        return False


def _close_orphan_chrome(profile=PROFILE_DIR):
    """A daemon that died leaves Chrome holding the profile, and the next
    Chrome cannot start on a locked one -- it fails with "DevToolsActivePort
    file doesn't exist", which reads like a Chrome crash and is not. Kill only
    the ones on OUR profile; never another program's or Tomoe's."""
    if not profile:
        return 0
    # `sensors/chrome_reaper.py` owns this now. The version here matched the
    # profile's basename against the whole command line and killed chrome.exe
    # only, so **chromedriver survived** and went on holding the lock, and it
    # ran on a stale lock file alone -- a daemon force-killed with its lock
    # intact left everything standing. The reaper matches the exact
    # --user-data-dir value rather than a substring, takes the whole tree, and
    # clears the singleton files a killed Chrome leaves behind. The exact match
    # is what keeps a reap off a browser that is not this one's: it mattered
    # most when these profiles were named as extensions of another program's own, and it is the rule whatever they are called.
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from sensors import chrome_reaper
        return chrome_reaper.kill(profile, log=lambda m: print(f"[daemon] {m}", flush=True))
    except Exception as e:
        print(f"[daemon] orphan cleanup failed: {type(e).__name__}: {e}", flush=True)
        return 0


def cmd_reap(args):
    """Kill the browser the daemon left behind, and say what the lock file says.

    A daemon stopped with `Stop-Process -Force` runs no exit path, so its
    headless Chrome and the chromedriver above it survive holding this tool's
    profile, and the next Chrome cannot start on a locked one. The next daemon
    start already reaps them (it finds the lock file naming a pid that is gone),
    but a stop that is never followed by a start would leave them running for
    as long as nobody looked. `restart.cmd` calls this while the daemon is
    down."""
    killed = _close_orphan_chrome()
    print("[reap] %d leftover process(es) killed on %s" % (killed, PROFILE_DIR))
    lock = DB_PATH + ".daemon.lock"
    if not os.path.exists(lock):
        print("[reap] no lock file: nothing claims to be the daemon")
        return
    try:
        pid = int(open(lock).read().strip() or 0)
    except Exception:
        print("[reap] the lock file cannot be read; the next start will take it over")
        return
    if _daemon_alive(pid):
        print("[reap] the daemon is still running (pid %d); its own Chrome was left alone" % pid)
    else:
        print("[reap] the lock names pid %d, which is gone; the next start takes it over" % pid)


def _refresh_subtitle_mirror():
    """The clone of the subtitle archive, brought up to date once a day.

    The path is read out of the config FILE rather than through the project's
    config machinery: this daemon is the machine's and has no character, and
    building a character's config here would print her name into the machine's
    log. Every failure is swallowed by type -- the list mirror's own work must
    not stop because a git remote was unreachable."""
    try:
        import json as _json
        root = ""
        for name in ("config.json", "config_yukarin.json"):
            p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), name)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as fh:
                    root = ((_json.load(fh).get("recap") or {}).get("subtitles_local_mirror") or "")
                if root:
                    break
        if not root:
            return
        if not os.path.isabs(root):
            root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), root)
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from sim.subtitles import refresh_local_mirror
        refresh_local_mirror(root, log=lambda m: print(f"  {m}", flush=True))
    except Exception as e:
        print(f"  the subtitle mirror was not refreshed ({type(e).__name__})", flush=True)


def _build_dossiers():
    """One file per finished play, joining the player's log with this mirror
    and the machine's retrieval store (`machine/dossier.py`, `docs/dossiers.md`).

    It is called from HERE and not from a character's loop because three
    character processes tail the same media player: built there it would be
    built three times, in three saves, by three programs. This daemon is the
    one process per machine, and the join it makes is the machine's -- what a
    character MADE of a play stays in her own save.

    Every failure is swallowed by type, like the subtitle mirror above it: the
    list mirror's own work must not stop because a page did not answer."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from machine import dossier
        for p in dossier.sweep(log=lambda m: print(f"  {m}", flush=True)):
            print(f"  dossier: {p}", flush=True)
    except Exception as e:
        print(f"  no dossier built this cycle ({type(e).__name__})", flush=True)


def cmd_daemon(args):
    """Runs forever: every --interval s, sync list updates + poll the public
    history page; every --reconcile h, re-scrape the panel for changed anime.
    Single instance (lock file). This is what run.cmd launches alongside the bot.

    It writes its own log (`--log`, default `logs/mal_daemon.log`) rather than
    trusting the launcher's redirect, which never reached it: see
    `open_log`."""
    if getattr(args, "log", ""):
        open_log(args.log)
    lock = DB_PATH + ".daemon.lock"
    stale_lock = os.path.exists(lock)
    if os.path.exists(lock):
        try:
            pid = int(open(lock).read().strip() or 0)
            if _daemon_alive(pid):
                print(f"[daemon] already running (pid {pid}); exiting.", flush=True)
                return
            print(f"[daemon] the lock names pid {pid}, which is gone; taking it over.", flush=True)
            stale_lock = True
        except Exception:
            pass
    with open(lock, "w") as f:
        f.write(str(os.getpid()))
    # and on the way out, for the exits Python actually sees: a normal return,
    # an unhandled exception, SIGTERM, and the console close button. A /F kill
    # still reaches none of these, which is why make_driver reaps on the way in
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from sensors import chrome_reaper
        chrome_reaper.install_exit_handler(PROFILE_DIR, log=lambda m: print(f"[daemon] {m}", flush=True))
    except Exception as e:
        print(f"[daemon] exit handler not installed: {type(e).__name__}: {e}", flush=True)
    if stale_lock:
        # the lock was there but its owner was not: a daemon died. Its Chrome
        # is probably still holding the profile, which stops ours from starting
        _close_orphan_chrome()
    con = db()
    driver = None
    last_recon = 0.0
    print(f"[daemon] every {args.interval}s: list sync + history poll; panel reconcile every {args.reconcile}h. Ctrl-C to stop.", flush=True)
    try:
        while True:
            t0 = time.time()
            try:
                sync_anime(con, verbose=False)
                # public history page -> new episode events (exact minute via panel below)
                page = _get(HISTORY.format(user=USERNAME))
                fresh = []
                for aid, ep, watched_at, raw in parse_history_page(page):
                    if watched_at and not con.execute(
                            "SELECT 1 FROM episodes WHERE anime_id=? AND ep=? AND watched_at=?",
                            (aid, ep, watched_at)).fetchone():
                        fresh.append((aid, ep, watched_at, raw))
                need_recon = (time.time() - last_recon) >= args.reconcile * 3600
                if fresh or need_recon:
                    if driver is None:
                        driver = make_driver(headless=True)
                        if not logged_in(driver):
                            print("[daemon] not logged in; run `login`. Using public-page times only.", flush=True)
                            driver.quit(); driver = None
                    if driver is not None:
                        if fresh:
                            for aid in {a for a, _, _, _ in fresh}:
                                try:
                                    r = parse_episode_history(_fetch_in_page(driver, AJAXTB.format(id=aid)))
                                    if r:
                                        _upsert_episodes(con, aid, r, "ajaxtb")
                                        con.execute("UPDATE anime SET last_scraped=?, history_count=? WHERE anime_id=?", (int(time.time()), len(r), aid))
                                        con.commit()
                                except Exception:
                                    pass
                        if need_recon:
                            _reconcile(con, driver, verbose=True)
                            last_recon = time.time()
                # his declared favorites, refreshed with each reconcile (public page, no login)
                if need_recon:
                    try:
                        f = parse_favorites(_get(FAVORITES_URL.format(user=USERNAME)))
                        con.executescript("CREATE TABLE IF NOT EXISTS favorites (kind TEXT, item_id INTEGER, name TEXT, extra TEXT, position INTEGER, fetched_at INTEGER, PRIMARY KEY (kind, item_id));")
                        con.execute("DELETE FROM favorites")
                        now_ = int(time.time())
                        for i, (x, t) in enumerate(f["anime"]):
                            con.execute("INSERT INTO favorites VALUES('anime',?,?,?,?,?)", (x, t, "", i, now_))
                        for i, (x, n, frm) in enumerate(f["characters"]):
                            con.execute("INSERT INTO favorites VALUES('character',?,?,?,?,?)", (x, n, frm, i, now_))
                        for i, (x, n) in enumerate(f["people"]):
                            con.execute("INSERT INTO favorites VALUES('people',?,?,?,?,?)", (x, n, "", i, now_))
                        con.commit()
                    except Exception as e:
                        print(f"  favorites refresh failed: {e}", flush=True)
                for aid, ep, watched_at, raw in fresh:
                    _upsert_episodes(con, aid, [(ep, watched_at, raw)], "history")
                    t = con.execute("SELECT title FROM anime WHERE anime_id=?", (aid,)).fetchone()
                    print(f"  [{watched_at}] {t[0] if t else aid} ep {ep}", flush=True)
                # And the machine's other archive of television: the clone of
                # the subtitle mirror, pulled at most once a day. It is here
                # because this is where the machine's periodic fetches live,
                # and because a pull of a fifteen-gigabyte working tree is not
                # something either character's loop should ever wait behind.
                _refresh_subtitle_mirror()
                # ...and the other thing this machine keeps about television:
                # a file per play he has finished, joining this mirror with
                # his player's log and the machine's retrieval store. Here for
                # the same reason the subtitle clone is: it is the machine's
                # periodic work, and one process doing it is the point.
                _build_dossiers()
                meta_set(con, "daemon_last_ts", int(time.time()))
                # and, at most once an hour, whether the outage in front of
                # MyAnimeList is over. Its own try/except: a poll must not
                # lose a cycle because a third party did not answer.
                jikan_watch(con, min_interval=args.jikan_watch_seconds)
                # and a few titles' worth of anime_detail, at most every
                # --detail-enrich-minutes -- see _enrich_due for why cast is
                # not also done here.
                _enrich_due(con, min_interval=args.detail_enrich_minutes * 60,
                            batch=args.detail_enrich_batch)
            except Exception as e:
                print(f"  poll error: {type(e).__name__}: {e}", flush=True)
            time.sleep(max(5, args.interval - (time.time() - t0)))
    except KeyboardInterrupt:
        print("\n[daemon] stopped.", flush=True)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        # quit() can hang or half-finish; the reaper is what makes "stopped"
        # mean the profile is free for the next start
        try:
            from sensors import chrome_reaper
            chrome_reaper.kill(PROFILE_DIR, log=print)
        except Exception:
            pass
        try:
            os.remove(lock)
        except OSError:
            pass


def _client_id():
    """The MAL API v2 client id: root config.json's sensors.mal_client_id first,
    then config_momoka.json as a fallback.

    Root config.json is a generic scaffold and has shipped with this field
    empty; config_momoka.json carries the real id (this checkout has one
    character, so her config is where the id actually lives). Neither file
    is written here -- read-only fallback, in that order."""
    root = os.path.join(os.path.dirname(DB_PATH), "..")
    for name in ("config.json", "config_momoka.json"):
        try:
            cfg = os.path.join(root, name)
            cid = json.load(open(cfg, encoding="utf-8"))["sensors"].get("mal_client_id", "") or ""
            if cid:
                return cid
        except Exception:
            continue
    return ""


_ENRICH_FIELDS = "id,title,media_type,num_episodes,average_episode_duration,start_season,source,rating,mean,genres,studios"


def _enrich_ids(con, cid, ids, delay=0.35, log=None):
    """Fetch anime_detail for exactly these ids from the API v2, in order.
    Shared by `cmd_enrich` (the manual, all-titles pass) and the daemon's own
    throttled slice of the same work (`_enrich_due`, below) so the request
    and the upsert are written once. Returns (ok, err)."""
    ok = err = 0
    for aid in ids:
        url = f"https://api.myanimelist.net/v2/anime/{aid}?fields={_ENRICH_FIELDS}"
        try:
            req = urllib.request.Request(url, headers={"X-MAL-CLIENT-ID": cid, "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read())
            ss = d.get("start_season") or {}
            con.execute("""INSERT INTO anime_detail(anime_id,avg_episode_seconds,api_genres,studios,source,
                season_year,season,mal_mean,rating,api_media_type,api_num_episodes,fetched_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(anime_id) DO UPDATE SET avg_episode_seconds=excluded.avg_episode_seconds,
                api_genres=excluded.api_genres, studios=excluded.studios, source=excluded.source,
                season_year=excluded.season_year, season=excluded.season, mal_mean=excluded.mal_mean,
                rating=excluded.rating, api_media_type=excluded.api_media_type,
                api_num_episodes=excluded.api_num_episodes, fetched_at=excluded.fetched_at""",
                (aid, d.get("average_episode_duration"),
                 json.dumps([g.get("name") for g in d.get("genres", [])], ensure_ascii=False),
                 json.dumps([s.get("name") for s in d.get("studios", [])], ensure_ascii=False),
                 d.get("source"), ss.get("year"), ss.get("season"), d.get("mean"), d.get("rating"),
                 d.get("media_type"), d.get("num_episodes"), int(time.time())))
            con.commit()
            ok += 1
        except Exception as e:
            err += 1
            if log:
                log(f"  {aid}: ERROR {e}")
        time.sleep(delay)
    return ok, err


def cmd_enrich(args):
    """Per-title detail from the official API v2: exact average episode duration
    (watch time needs it -- a movie is not 24 min), studios, the full genre /
    theme / demographic set, source, season, MAL mean. Idempotent; only titles
    not yet fetched (or all with --force)."""
    cid = args.client_id or _client_id()
    if not cid:
        print("no MAL API client id (set sensors.mal_client_id in config.json, or pass --client-id)")
        return
    con = db()
    if args.force:
        ids = [r[0] for r in con.execute("SELECT anime_id FROM anime ORDER BY anime_id")]
    else:
        ids = [r[0] for r in con.execute(
            "SELECT a.anime_id FROM anime a LEFT JOIN anime_detail d ON d.anime_id=a.anime_id "
            "WHERE d.anime_id IS NULL ORDER BY a.anime_id")]
    if args.limit:
        ids = ids[:args.limit]
    print(f"[enrich] {len(ids)} title(s) to fetch from the MAL API", flush=True)
    # 50 at a time so a long run still says something while it works, same
    # cadence the old inline loop printed at
    ok = err = 0
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        o, e = _enrich_ids(con, cid, chunk, delay=args.delay, log=lambda m: print(m, flush=True))
        ok += o; err += e
        print(f"  [{min(i + 50, len(ids))}/{len(ids)}] ok={ok} err={err}", flush=True)
    print(f"[enrich] done: {ok} fetched, {err} errors.", flush=True)


def _enrich_due(con, min_interval=1800.0, batch=5, delay=0.35):
    """A few titles' anime_detail per daemon cycle, at most every
    `min_interval` seconds -- the daemon's own throttled slice of `enrich`,
    so a title added to the list today has a detail row within a day or two
    instead of waiting for someone to run `enrich` by hand again.

    Small batch and its own client id lookup (falls back to
    config_momoka.json, see `_client_id`), and every failure swallowed by
    type, same as `jikan_watch` above it: the list mirror's own work must
    not stop because the API did not answer. `cast` (character/seiyuu data)
    is NOT done here -- it is a public-page scrape at ~1 req/s per title,
    much slower than this API call, and nothing reads anime_cast on the
    daemon's own critical path the way anime_detail feeds watch-time math;
    it stays a manual `cast` run."""
    if min_interval <= 0:
        return
    try:
        last = float(meta_get(con, "detail_enrich_at", 0) or 0)
    except (TypeError, ValueError):
        last = 0.0
    now = time.time()
    if now - last < min_interval:
        return
    meta_set(con, "detail_enrich_at", int(now))
    try:
        cid = _client_id()
        if not cid:
            return
        ids = [r[0] for r in con.execute(
            "SELECT a.anime_id FROM anime a LEFT JOIN anime_detail d ON d.anime_id=a.anime_id "
            "WHERE d.anime_id IS NULL ORDER BY a.anime_id LIMIT ?", (batch,))]
        if not ids:
            return
        ok, err = _enrich_ids(con, cid, ids, delay=delay, log=lambda m: print(f"  [detail]{m}", flush=True))
        if ok or err:
            print(f"  [detail] {ok} title(s) enriched, {err} error(s) this cycle", flush=True)
    except Exception as e:
        print(f"  [detail] not enriched this cycle ({type(e).__name__})", flush=True)


def cmd_export(args):
    """CSV of the master data: one row per episode event joined to its anime,
    plus an anime-level CSV."""
    import csv
    con = db()
    out_dir = args.out or os.path.join(os.path.dirname(DB_PATH), "mal_export")
    os.makedirs(out_dir, exist_ok=True)
    ep_path = os.path.join(out_dir, "episodes.csv")
    an_path = os.path.join(out_dir, "anime.csv")
    with open(ep_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["anime_id", "title", "title_eng", "media_type", "status", "my_score", "mal_mean", "num_episodes",
                    "ep", "watched_at", "date", "time", "hour", "weekday", "duration_min", "genres", "studios",
                    "material_source", "season", "event_source", "raw"])
        q = ("SELECT e.anime_id,a.title,a.title_eng,COALESCE(d.api_media_type,a.media_type),a.status,a.score,d.mal_mean,"
             "a.num_episodes,e.ep,e.watched_at,e.source,e.raw,d.avg_episode_seconds,d.api_genres,d.studios,d.source,"
             "d.season_year,d.season FROM episodes e LEFT JOIN anime a ON a.anime_id=e.anime_id "
             "LEFT JOIN anime_detail d ON d.anime_id=e.anime_id ORDER BY e.watched_at, e.anime_id, e.ep")
        n = 0
        for aid, t, te, mt, st, sc, mm, ne, ep, wa, src, raw, secs, gen, stu, msrc, sy, ss in con.execute(q):
            try:
                wd = datetime.date.fromisoformat(wa[:10]).strftime("%a")
            except Exception:
                wd = ""
            def j(x):
                try:
                    return "; ".join(json.loads(x or "[]"))
                except Exception:
                    return ""
            w.writerow([aid, t, te, mt, STATUS.get(st, st), sc, mm, ne, ep, wa, wa[:10], wa[11:16], wa[11:13], wd,
                        round(secs / 60, 1) if secs else "", j(gen), j(stu), msrc or "",
                        f"{ss} {sy}" if sy else "", src, raw])
            n += 1
    with open(an_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["anime_id", "title", "title_eng", "media_type", "status", "my_score", "mal_mean", "watched_episodes",
                    "num_episodes", "duration_min", "total_watched_hours", "genres", "studios", "material_source",
                    "season", "start_date", "finish_date", "tags", "notes", "episode_events", "first_watched", "last_watched"])
        q = ("SELECT a.anime_id,a.title,a.title_eng,COALESCE(d.api_media_type,a.media_type),a.status,a.score,d.mal_mean,"
             "a.watched_episodes,a.num_episodes,d.avg_episode_seconds,d.api_genres,d.studios,d.source,d.season_year,d.season,"
             "a.start_date,a.finish_date,a.tags,a.notes,COUNT(e.ep),MIN(e.watched_at),MAX(e.watched_at) "
             "FROM anime a LEFT JOIN anime_detail d ON d.anime_id=a.anime_id LEFT JOIN episodes e ON e.anime_id=a.anime_id "
             "GROUP BY a.anime_id ORDER BY a.title")
        m = 0
        for (aid, t, te, mt, st, sc, mm, we, ne, secs, gen, stu, msrc, sy, ss, sd, fd, tags, notes, nev, fw, lw) in con.execute(q):
            def j(x):
                try:
                    return "; ".join(json.loads(x or "[]"))
                except Exception:
                    return ""
            w.writerow([aid, t, te, mt, STATUS.get(st, st), sc, mm, we, ne,
                        round(secs / 60, 1) if secs else "", round((we or 0) * (secs or 0) / 3600, 2),
                        j(gen), j(stu), msrc or "", f"{ss} {sy}" if sy else "", sd, fd, tags, notes, nev, fw, lw])
            m += 1
    print(f"[export] {n} episode rows -> {ep_path}", flush=True)
    print(f"[export] {m} anime rows    -> {an_path}", flush=True)


def split_runs(events):
    """Split one anime's episode events into watch RUNS. MAL's history logs
    rewatches unmarked; the tell is the episode number resetting (ep 3 after
    ep 13). A new run starts when the ep falls two or more below the current
    run's max AND at least two days have passed (bulk logs stamp several eps
    in one minute, sometimes out of order -- ties sort by ep, and a same-week
    correction is not a rewatch). Returns [[(ep, watched_at), ...], ...] in
    time order; run 0 is the original watch (often a single bulk-logged
    terminal ep for shows watched before the list existed)."""
    events = sorted(events, key=lambda x: (x[1], x[0]))
    runs = []
    cur = []
    run_max = -1
    last_w = None
    for ep, w in events:
        gap_days = 0.0
        if last_w:
            try:
                gap_days = (datetime.datetime.fromisoformat(w) - datetime.datetime.fromisoformat(last_w)).total_seconds() / 86400
            except ValueError:
                pass
        if cur and ep <= run_max - 2 and gap_days >= 2:
            runs.append(cur)
            cur = []
            run_max = -1
        cur.append((ep, w))
        run_max = max(run_max, ep)
        last_w = w
    if cur:
        runs.append(cur)
    return runs


def _fmt_h(seconds):
    h = seconds / 3600.0
    if h >= 48:
        return f"{h:,.0f} h ({h/24:.1f} days)"
    return f"{h:,.1f} h"


def _bar(v, mx, w=36):
    return "#" * int(w * v / mx) if mx else ""


def cmd_report(args):
    con = db()
    if args.detail:
        return cmd_report_detail(con, args)
    if args.anime:
        like = f"%{args.anime}%"
        hits = con.execute("SELECT anime_id,title FROM anime WHERE title LIKE ? OR title_eng LIKE ?", (like, like)).fetchall()
        if not hits:
            print("no match."); return
        for aid, title in hits[:8]:
            eps = con.execute("SELECT ep,watched_at,source FROM episodes WHERE anime_id=? ORDER BY watched_at", (aid,)).fetchall()
            print(f"\n{title}  (id {aid}) -- {len(eps)} episode events")
            for ep, when, src in eps:
                print(f"  ep {ep:>3}  {when}  [{src}]")
        return
    n_anime = con.execute("SELECT COUNT(*) FROM anime").fetchone()[0]
    n_scraped = con.execute("SELECT COUNT(*) FROM anime WHERE history_count>0").fetchone()[0]
    n_eps = con.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    span = con.execute("SELECT MIN(watched_at),MAX(watched_at) FROM episodes").fetchone()
    print(f"anime in list: {n_anime}  | with episode history: {n_scraped}  | episode events: {n_eps}")
    if span[0]:
        print(f"span: {span[0][:10]} -> {span[1][:10]}")
    print("\nby year:")
    for yr, c in con.execute("SELECT substr(watched_at,1,4) y, COUNT(*) FROM episodes GROUP BY y ORDER BY y"):
        print(f"  {yr}: {c:5d} episodes  " + "#" * min(60, c // 5))
    print("\nby hour of day:")
    hrs = dict(con.execute("SELECT substr(watched_at,12,2) h, COUNT(*) FROM episodes GROUP BY h").fetchall())
    mx = max([int(v) for v in hrs.values()] or [1])
    for h in range(24):
        c = int(hrs.get(f"{h:02d}", 0))
        print(f"  {h:02d}:00  {c:4d}  " + "#" * int(40 * c / mx))
    print("\nby weekday (Mon..Sun):")
    wd = [0] * 7
    for (w,) in con.execute("SELECT watched_at FROM episodes"):
        try:
            wd[datetime.date.fromisoformat(w[:10]).weekday()] += 1
        except ValueError:
            pass
    for i, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        print(f"  {name} {wd[i]:5d}  " + "#" * (wd[i] // max(1, max(wd) // 40)))
    print("\nbiggest single-day binges:")
    for day, c in con.execute("SELECT substr(watched_at,1,10) d, COUNT(*) c FROM episodes GROUP BY d ORDER BY c DESC LIMIT 8"):
        print(f"  {day}: {c} episodes")


def cmd_report_detail(con, args):
    """The detailed analysis: total watch time (per-episode duration from the
    API), time and habits over time, genres by hours, studios, pacing, scores.
    Watch time is computed from the dated episode events (what he sat through,
    when); the list-based figure (watched_episodes x duration) is the cross-check
    that also counts bulk-logged episodes."""
    from collections import Counter, defaultdict
    have_detail = con.execute("SELECT COUNT(*) FROM anime_detail").fetchone()[0]
    if not have_detail:
        print("no API detail yet -- run:  python tools/mal_history.py enrich")
        return
    # per-title duration (seconds), fall back by media type if the API had none
    dur = {}
    for aid, s, mt in con.execute("SELECT d.anime_id,d.avg_episode_seconds,COALESCE(d.api_media_type,a.media_type) "
                                  "FROM anime_detail d JOIN anime a ON a.anime_id=d.anime_id"):
        if not s:
            s = {"movie": 100 * 60, "tv": 24 * 60, "ova": 25 * 60, "ona": 12 * 60, "special": 15 * 60, "music": 4 * 60}.get(
                (mt or "").lower(), 24 * 60)
        dur[aid] = s
    title = dict(con.execute("SELECT anime_id,title FROM anime"))
    genres = {}
    for aid, g in con.execute("SELECT anime_id,api_genres FROM anime_detail"):
        try:
            genres[aid] = json.loads(g or "[]")
        except Exception:
            genres[aid] = []
    studios = {}
    for aid, s in con.execute("SELECT anime_id,studios FROM anime_detail"):
        try:
            studios[aid] = json.loads(s or "[]")
        except Exception:
            studios[aid] = []

    events = con.execute("SELECT anime_id,ep,watched_at FROM episodes ORDER BY watched_at").fetchall()
    n_ev = len(events)
    ev_secs = sum(dur.get(a, 24 * 60) for a, _, _ in events)
    # list-based total: every episode MAL says he watched, whether or not it has an event
    list_secs = 0
    for aid, w, st in con.execute("SELECT anime_id,watched_episodes,status FROM anime"):
        list_secs += (w or 0) * dur.get(aid, 24 * 60)
    print("=" * 72)
    print("TOTAL WATCH TIME")
    print("=" * 72)
    print(f"  from dated episode events : {_fmt_h(ev_secs)}   ({n_ev:,} events, {len(set(a for a,_,_ in events))} titles)")
    print(f"  from the list (all eps)   : {_fmt_h(list_secs)}   (watched_episodes x duration; includes bulk-logged eps)")
    first = events[0][2][:10] if events else "?"
    last = events[-1][2][:10] if events else "?"
    try:
        days = (datetime.date.fromisoformat(last) - datetime.date.fromisoformat(first)).days + 1
        print(f"  span {first} -> {last} ({days} days): {ev_secs/3600/days*60:.0f} min/day average, "
              f"{ev_secs/3600/(days/7):.1f} h/week")
    except Exception:
        pass

    # ---- over time: hours by year and by month
    by_year = defaultdict(float); by_month = defaultdict(float); ev_year = Counter()
    for a, _, w in events:
        by_year[w[:4]] += dur.get(a, 1440); by_month[w[:7]] += dur.get(a, 1440); ev_year[w[:4]] += 1
    print("\n" + "=" * 72); print("HOURS BY YEAR"); print("=" * 72)
    mx = max(by_year.values()) if by_year else 1
    for y in sorted(by_year):
        print(f"  {y}: {by_year[y]/3600:6.0f} h  ({ev_year[y]:4d} eps)  {_bar(by_year[y], mx)}")
    print("\n" + "=" * 72); print("HOURS BY MONTH (last 24)"); print("=" * 72)
    months = sorted(by_month)[-24:]
    mx = max(by_month[m] for m in months) if months else 1
    for m in months:
        print(f"  {m}: {by_month[m]/3600:5.0f} h  {_bar(by_month[m], mx)}")

    # ---- habits: hour of day & weekday, by HOURS, and how it shifted year to year
    print("\n" + "=" * 72); print("WHEN YOU WATCH (hours of watch time by hour of day)"); print("=" * 72)
    by_hod = defaultdict(float)
    for a, _, w in events:
        by_hod[int(w[11:13])] += dur.get(a, 1440)
    mx = max(by_hod.values()) if by_hod else 1
    for h in range(24):
        print(f"  {h:02d}:00  {by_hod[h]/3600:6.1f} h  {_bar(by_hod[h], mx)}")
    print("\n  peak hour by year (when the habit sits):")
    yh = defaultdict(lambda: defaultdict(float))
    for a, _, w in events:
        yh[w[:4]][int(w[11:13])] += dur.get(a, 1440)
    for y in sorted(yh):
        top = sorted(yh[y].items(), key=lambda kv: -kv[1])[:3]
        print(f"    {y}: " + ", ".join(f"{h:02d}:00 ({s/3600:.0f}h)" for h, s in top))
    print("\n" + "=" * 72); print("WEEKDAY (hours)"); print("=" * 72)
    wd = [0.0] * 7
    for a, _, w in events:
        try:
            wd[datetime.date.fromisoformat(w[:10]).weekday()] += dur.get(a, 1440)
        except ValueError:
            pass
    mx = max(wd) or 1
    for i, nm in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        print(f"  {nm} {wd[i]/3600:6.1f} h  {_bar(wd[i], mx)}")

    # ---- genres by hours (API set: genres + themes + demographics)
    print("\n" + "=" * 72); print("GENRES / THEMES BY HOURS WATCHED (a title counts toward each of its tags)"); print("=" * 72)
    gh = defaultdict(float); gt = Counter()
    for a, _, w in events:
        for g in genres.get(a, []):
            gh[g] += dur.get(a, 1440)
    for aid in set(a for a, _, _ in events):
        for g in genres.get(aid, []):
            gt[g] += 1
    top = sorted(gh.items(), key=lambda kv: -kv[1])[:22]
    mx = top[0][1] if top else 1
    for g, s in top:
        print(f"  {g:18s} {s/3600:6.0f} h  {gt[g]:3d} titles  {_bar(s, mx)}")
    print("\n  genre mix by year (top 5 each, share of that year's hours):")
    yg = defaultdict(lambda: defaultdict(float))
    for a, _, w in events:
        for g in genres.get(a, []):
            yg[w[:4]][g] += dur.get(a, 1440)
    for y in sorted(yg):
        tot = by_year[y] or 1
        top = sorted(yg[y].items(), key=lambda kv: -kv[1])[:5]
        print(f"    {y}: " + ", ".join(f"{g} {s/tot*100:.0f}%" for g, s in top))

    # ---- studios
    print("\n" + "=" * 72); print("STUDIOS BY HOURS"); print("=" * 72)
    sh = defaultdict(float); st_n = Counter()
    for a, _, w in events:
        for s in studios.get(a, []):
            sh[s] += dur.get(a, 1440)
    for aid in set(a for a, _, _ in events):
        for s in studios.get(aid, []):
            st_n[s] += 1
    top = sorted(sh.items(), key=lambda kv: -kv[1])[:15]
    mx = top[0][1] if top else 1
    for s, secs in top:
        print(f"  {s:22s} {secs/3600:6.0f} h  {st_n[s]:3d} titles  {_bar(secs, mx)}")

    # ---- media type & source
    print("\n" + "=" * 72); print("BY MEDIA TYPE / SOURCE (hours)"); print("=" * 72)
    mt_h = defaultdict(float); src_h = defaultdict(float)
    mtd = dict(con.execute("SELECT anime_id,COALESCE(api_media_type,'?') FROM anime_detail"))
    srcd = dict(con.execute("SELECT anime_id,COALESCE(source,'?') FROM anime_detail"))
    for a, _, w in events:
        mt_h[mtd.get(a, "?")] += dur.get(a, 1440); src_h[srcd.get(a, "?")] += dur.get(a, 1440)
    print("  media: " + ", ".join(f"{k} {v/3600:.0f}h" for k, v in sorted(mt_h.items(), key=lambda kv: -kv[1])))
    print("  source: " + ", ".join(f"{k} {v/3600:.0f}h" for k, v in sorted(src_h.items(), key=lambda kv: -kv[1])[:8]))

    # ---- pacing: per watch RUN (rewatches split off -- MAL logs them
    # unmarked, and a rewatched favorite otherwise looks like a 3-year burn)
    print("\n" + "=" * 72); print("PACING (per watch run; rewatches counted separately)"); print("=" * 72)
    per = defaultdict(list)
    for a, e, w in events:
        per[a].append((e, w))
    spans = []
    rewatched = []
    for a, evs in per.items():
        runs = split_runs(evs)
        if len(runs) > 1:
            rewatched.append((len(runs) - 1, title.get(a, a), [r[0][1][:10] for r in runs]))
        for r in runs:
            if len(r) >= 6:
                try:
                    d0 = datetime.datetime.fromisoformat(r[0][1]); d1 = datetime.datetime.fromisoformat(r[-1][1])
                    spans.append(((d1 - d0).total_seconds() / 86400, len(r), title.get(a, a)))
                except Exception:
                    pass
    spans.sort()
    if spans:
        med = spans[len(spans) // 2][0]
        print(f"  watch runs with 6+ logged eps: {len(spans)}; median first->last span {med:.1f} days")
        same_day = sum(1 for s, n, _ in spans if s < 1)
        print(f"  finished within a day: {same_day} ({same_day/len(spans)*100:.0f}%)  |  over a month: {sum(1 for s,_,_ in spans if s>30)}  |  over a year: {sum(1 for s,_,_ in spans if s>365)}")
        print("  slowest single runs:")
        for s, n, t in spans[-5:][::-1]:
            print(f"    {t[:48]:48s} {s:6.0f} days, {n} eps")
    if rewatched:
        rewatched.sort(reverse=True)
        print(f"\n  REWATCHED ({len(rewatched)} titles -- the strongest love signal there is):")
        for n, t, starts in rewatched[:15]:
            print(f"    {t[:44]:44s} {n} rewatch(es): runs started {', '.join(starts)}")
    print("\n  biggest single days (hours):")
    bd = defaultdict(float); bde = Counter()
    for a, _, w in events:
        bd[w[:10]] += dur.get(a, 1440); bde[w[:10]] += 1
    for d_, s in sorted(bd.items(), key=lambda kv: -kv[1])[:8]:
        print(f"    {d_}: {s/3600:5.1f} h ({bde[d_]} eps)")
    # streaks
    days_set = sorted(set(w[:10] for _, _, w in events))
    best = cur = 1; bstart = bend = cstart = days_set[0] if days_set else None
    for i in range(1, len(days_set)):
        a_ = datetime.date.fromisoformat(days_set[i - 1]); b_ = datetime.date.fromisoformat(days_set[i])
        if (b_ - a_).days == 1:
            cur += 1
        else:
            cur = 1; cstart = days_set[i]
        if cur > best:
            best = cur; bstart = cstart; bend = days_set[i]
    print(f"\n  longest daily watch streak: {best} days ({bstart} -> {bend})  |  distinct watch days: {len(days_set)}")

    # ---- your scores vs MAL
    print("\n" + "=" * 72); print("YOUR SCORES VS MAL"); print("=" * 72)
    rows = con.execute("SELECT a.score,d.mal_mean,a.title FROM anime a JOIN anime_detail d ON d.anime_id=a.anime_id "
                       "WHERE a.score>0 AND d.mal_mean IS NOT NULL").fetchall()
    if rows:
        import statistics
        diffs = [s - m for s, m, _ in rows]
        print(f"  scored titles: {len(rows)} | your mean {statistics.mean(s for s,_,_ in rows):.2f} vs MAL mean {statistics.mean(m for _,m,_ in rows):.2f} "
              f"| avg difference {statistics.mean(diffs):+.2f}")
        dist = Counter(s for s, _, _ in rows)
        print("  your score distribution: " + ", ".join(f"{k}:{dist[k]}" for k in sorted(dist)))
        rows.sort(key=lambda r: r[0] - r[1])
        print("  you liked far MORE than MAL: " + "; ".join(f"{t[:28]} ({s} vs {m:.1f})" for s, m, t in rows[-4:][::-1]))
        print("  you liked far LESS than MAL: " + "; ".join(f"{t[:28]} ({s} vs {m:.1f})" for s, m, t in rows[:4]))
    print()



def cadence(con, min_gaps=2):
    """How fast he watches a thing, and what that predicts.

    He does not decide to drop a show. He slows down, stops, and the official
    status catches up months later or never -- so the gap between episodes is
    a better read on what he has abandoned than the status field is. Measured
    on the latest run only, so an old rewatch does not flatten the picture,
    and gaps under half an hour are ignored because a bulk-logged batch is not
    a cadence."""
    import statistics
    ep = collections.defaultdict(list)
    for r in con.execute("SELECT anime_id, ep, watched_at FROM episodes WHERE watched_at IS NOT NULL"):
        ep[r["anime_id"]].append((r["ep"], r["watched_at"]))
    now = datetime.datetime.now()
    out = {}
    for r in con.execute("SELECT anime_id,title,status,watched_episodes,num_episodes FROM anime"):
        events = ep.get(r["anime_id"])
        if not events or len(events) < 3:
            continue
        times = []
        for _, w in split_runs(events)[-1]:
            try:
                times.append(datetime.datetime.fromisoformat(w))
            except ValueError:
                pass
        times.sort()
        gaps = [(b - a).total_seconds() / 86400.0 for a, b in zip(times, times[1:])]
        gaps = [g for g in gaps if g > 0.02]
        if len(gaps) < min_gaps:
            continue
        med = statistics.median(gaps)
        since = (now - times[-1]).total_seconds() / 86400.0
        out[r["anime_id"]] = {
            "title": r["title"], "status": r["status"], "status_name": STATUS.get(r["status"], "?"),
            "median_gap": med, "gaps": len(gaps), "since": since,
            "stall": since / med if med else 0.0,
            "watched": r["watched_episodes"], "total": r["num_episodes"],
            "last": times[-1].date().isoformat(),
        }
    return out


def cmd_cadence(args):
    import statistics
    con = db()
    # db() returns plain tuples; this report reads rows by name
    con.row_factory = sqlite3.Row
    shows = cadence(con)
    by = collections.defaultdict(list)
    for s in shows.values():
        by[s["status_name"]].append(s)
    print(f"{len(shows)} show(s) with enough history to have a cadence\n")
    print("HOW FAST HE WATCHES, BY WHAT BECAME OF IT")
    for st, v in sorted(by.items(), key=lambda x: -len(x[1])):
        med = statistics.median([x["median_gap"] for x in v])
        print(f"  {st:14s} n={len(v):3d}   median gap {med:6.2f} d")
    print("\n  He binges what he finishes and grazes what he abandons, so the gap")
    print("  between episodes reads his interest better than the status does.")

    print("\nSAYS HE IS WATCHING IT, HAS NOT TOUCHED IT")
    live = sorted([s for s in shows.values() if s["status"] == 1],
                  key=lambda x: -x["stall"])
    for s in live:
        if s["stall"] < args.stall:
            continue
        print(f"  {s['title'][:44]:44s} ep {s['watched']:>3}/{str(s['total'] or '?'):<4} "
              f"every {s['median_gap']:5.1f}d, nothing for {s['since']:6.1f}d  ({s['stall']:5.1f}x)")

    print("\nWENT BACK ON THE SHELF WITH EPISODES ALREADY WATCHED")
    for r in con.execute("SELECT title, watched_episodes, num_episodes FROM anime "
                         "WHERE status=6 AND watched_episodes > 0 ORDER BY watched_episodes DESC"):
        print(f"  {r['title'][:44]:44s} ep {r['watched_episodes']}/{r['num_episodes'] or '?'}")

    try:
        moves = con.execute("SELECT title, was, now, watched, at FROM status_log "
                            "ORDER BY at DESC LIMIT 15").fetchall()
    except sqlite3.OperationalError:
        moves = []
    print("\nSTATUS CHANGES SINCE THIS STARTED RECORDING" if moves else
          "\n(no status changes recorded yet: the log starts at the next sync)")
    for m in moves:
        print(f"  {m['at'][:16]}  {m['title'][:40]:40s} {STATUS.get(m['was'], m['was'])} -> "
              f"{STATUS.get(m['now'], m['now'])} at ep {m['watched']}")

def cmd_cast(args):
    """Fetch the cast (characters + JP voice actors) for every anime he has
    watched, into anime_cast via AnimeKB. Public MAL pages, ~1 req/s,
    idempotent (skips anime whose cast is already cached)."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import logger as _lg
    _lg.log = lambda *a, **k: None
    from sim.anime_kb import AnimeKB
    kb = AnimeKB(None, DB_PATH, _client_id())
    con = db()
    have = {r[0] for r in con.execute("SELECT DISTINCT anime_id FROM anime_cast")}
    ids = [r[0] for r in con.execute("SELECT anime_id FROM anime WHERE status=2 OR watched_episodes>0 ORDER BY anime_id")]
    todo = [i for i in ids if i not in have]
    if args.limit:
        todo = todo[:args.limit]
    print(f"[cast] {len(todo)} anime to fetch ({len(have)} cached)", flush=True)
    ok = 0
    for i, aid in enumerate(todo, 1):
        try:
            rows = kb._fetch_cast(aid)
            con.execute("DELETE FROM anime_cast WHERE anime_id=?", (aid,))
            con.executemany("INSERT OR REPLACE INTO anime_cast VALUES(?,?,?,?,?,?)", rows)
            con.execute("INSERT INTO anime_kb(anime_id,cast_fetched_at) VALUES(?,?) ON CONFLICT(anime_id) DO UPDATE SET cast_fetched_at=excluded.cast_fetched_at", (aid, int(time.time())))
            con.commit()
            ok += 1
        except Exception as e:
            print(f"  {aid}: ERROR {type(e).__name__}", flush=True)
        if i % 40 == 0:
            print(f"  [{i}/{len(todo)}] ok={ok}", flush=True)
        time.sleep(args.delay)
    print(f"[cast] done: {ok} fetched.", flush=True)


def cmd_seiyuu(args):
    """Which voice actors he actually likes, from what he watched: for every
    seiyuu in the cast of a show he has episodes of, weight by his hours on
    that show (main role full, supporting half), his score, and whether he
    finished or dropped it. Affinity = the mix; the list is sorted by it."""
    from collections import defaultdict
    con = db()
    dur = {a: (s or 1440) for a, s in con.execute("SELECT anime_id,avg_episode_seconds FROM anime_detail")}
    hours = defaultdict(float)
    for a, n in con.execute("SELECT anime_id,COUNT(*) FROM episodes GROUP BY anime_id"):
        hours[a] = n * dur.get(a, 1440) / 3600
    his = {a: (st, sc, w, tot) for a, st, sc, w, tot in con.execute("SELECT anime_id,status,score,watched_episodes,num_episodes FROM anime")}
    title = dict(con.execute("SELECT anime_id,title FROM anime"))
    cast = con.execute("SELECT anime_id,character,role,jp_va,jp_va_id FROM anime_cast WHERE jp_va IS NOT NULL").fetchall()
    if not cast:
        print("no cast cached yet -- run:  python tools/mal_history.py cast")
        return
    # one seiyuu can voice several characters in one show: count each SHOW
    # once (its best role weight), not each character row
    best = {}   # (pid, va, aid) -> (wgt, ch)
    for aid, ch, role, va, pid in cast:
        if aid not in his:
            continue
        wgt = 1.0 if role == "Main" else 0.45
        k = (pid, va, aid)
        if k not in best or wgt > best[k][0]:
            best[k] = (wgt, ch)
    agg = defaultdict(lambda: {"hours": 0.0, "shows": set(), "main": 0, "sup": 0, "scores": [], "done": 0, "dropped": 0, "roles": []})
    for (pid, va, aid), (wgt, ch) in best.items():
        st, sc, w, tot = his[aid]
        h = hours.get(aid, 0.0)
        if h <= 0 and not (st == 2):
            continue
        a = agg[(pid, va)]
        a["hours"] += h * wgt
        a["shows"].add(aid)
        a["main" if wgt == 1.0 else "sup"] += 1
        if sc:
            a["scores"].append((sc, wgt))
        if st == 2:
            a["done"] += 1
        elif st == 4:
            a["dropped"] += 1
        a["roles"].append((h * wgt, ch, title.get(aid, aid), sc, st))
    rows = []
    for (pid, va), a in agg.items():
        if len(a["shows"]) < args.min_shows:
            continue
        sw = sum(w for _, w in a["scores"]) or 0
        avg_sc = sum(s * w for s, w in a["scores"]) / sw if sw else None
        n = a["done"] + a["dropped"]
        finish = a["done"] / n if n else None
        # affinity: hours (log-damped) x score lift x finish rate
        import math
        score_lift = ((avg_sc or 7.0) - 6.0) / 4.0            # 6->0, 10->1
        fin = finish if finish is not None else 0.6
        aff = math.log1p(a["hours"]) * (0.5 + score_lift) * (0.5 + fin)
        rows.append((aff, va, pid, a))
    rows.sort(key=lambda r: -r[0])
    print(f"seiyuu he has spent time with: {len(agg)} (shown: >= {args.min_shows} shows)\n")
    print("=" * 96)
    print("SEIYUU HE LIKES (affinity = hours x how he scores their shows x how often he finishes them)")
    print("=" * 96)
    for aff, va, pid, a in rows[:args.top]:
        sw = sum(w for _, w in a["scores"]) or 0
        avg_sc = sum(s * w for s, w in a["scores"]) / sw if sw else None
        n = a["done"] + a["dropped"]
        top_roles = sorted(a["roles"], key=lambda r: -r[0])[:3]
        roles_s = "; ".join(f"{ch} ({t[:26]}" + (f", {sc}" if sc else "") + ")" for _, ch, t, sc, st in top_roles)
        print(f"  {va:22s} aff {aff:5.2f} | {a['hours']:5.1f} h over {len(a['shows']):2d} shows ({a['main']} main) | his avg {avg_sc:.1f}" if avg_sc else
              f"  {va:22s} aff {aff:5.2f} | {a['hours']:5.1f} h over {len(a['shows']):2d} shows ({a['main']} main) | unscored", end="")
        print(f" | finished {a['done']}/{n}" if n else "", end="")
        print(f"\n      {roles_s}")
    # the other end: hours sunk but dropped / low scores
    print("\n" + "=" * 96)
    print("SEIYUU HE KEEPS DROPPING OR SCORING LOW (a lot of exposure, little love)")
    print("=" * 96)
    # genuinely low love: a real drop RATE (not just volume) or a low average
    def _avg(a):
        sw = sum(w for _, w in a["scores"]) or 0
        return sum(s * w for s, w in a["scores"]) / sw if sw else None
    bad = []
    for aff, va, pid, a in rows:
        n = a["done"] + a["dropped"]
        drop_rate = a["dropped"] / n if n else 0
        avg_sc = _avg(a)
        if a["hours"] >= 5 and n >= 4 and (drop_rate >= 0.3 or (avg_sc is not None and avg_sc < 6.6)):
            bad.append((drop_rate, avg_sc, va, a))
    bad.sort(key=lambda r: (-r[0], r[1] or 9))
    for drop_rate, avg_sc, va, a in bad[:12]:
        n = a["done"] + a["dropped"]
        print(f"  {va:22s} {a['hours']:5.1f} h over {len(a['shows']):2d} shows | dropped {a['dropped']}/{n} ({drop_rate*100:.0f}%) | his avg {f'{avg_sc:.1f}' if avg_sc else '-'}")
    print()


FAVORITES_URL = "https://myanimelist.net/profile/{user}/favorites"


def parse_favorites(page):
    """Public /profile/<user>/favorites -> {anime:[(id,title)], characters:[(id,name,from_title)], people:[(id,name)]}.
    His explicit, deliberate favorites -- a stronger signal than anything inferred."""
    out = {"anime": [], "characters": [], "people": []}
    def titles(kind, seg):
        return re.findall(r'<div class="title"><a href="https://myanimelist\.net/' + kind + r'/(\d+)/[^"]*">([^<]+)</a></div>', seg)
    # sections are headed <h5>Anime</h5> / <h5>Characters</h5> / <h5>People</h5>
    def segment(h5):
        i = page.find(f"<h5>{h5}</h5>")
        if i < 0:
            return ""
        j = page.find("<h5>", i + 5)
        return page[i:j if j > 0 else len(page)]
    out["anime"] = [(int(i), html.unescape(t).strip()) for i, t in titles("anime", segment("Anime"))]
    # characters: every box has a title anchor and then the show it's from
    # (fn-grey2), in the same order -- walk them as a stream
    cseg = segment("Character")   # MAL's header is singular
    stream = re.findall(r'<div class="title"><a href="https://myanimelist\.net/character/(\d+)/[^"]*">([^<]+)</a></div>'
                        r'|<a class="fn-grey2" href="[^"]*">\s*([^<]+?)\s*</a>', cseg)
    cur = None
    for cid, name, frm in stream:
        if cid:
            if cur:
                out["characters"].append(cur)
            cur = [int(cid), html.unescape(name).strip(), ""]
        elif cur is not None and frm:
            cur[2] = html.unescape(frm).strip()
    if cur:
        out["characters"].append(cur)
    out["characters"] = [tuple(c) for c in out["characters"]]
    out["people"] = [(int(i), html.unescape(t).strip()) for i, t in titles("people", segment("People"))]
    return out


def cmd_favorites(args):
    """Pull his explicit MAL favorites (anime, characters, people) into the DB
    (table `favorites`), and cross them against the behavioural seiyuu
    affinity so the two signals can be read together."""
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS favorites (
        kind TEXT, item_id INTEGER, name TEXT, extra TEXT, position INTEGER, fetched_at INTEGER,
        PRIMARY KEY (kind, item_id)
    );""")
    page = _get(FAVORITES_URL.format(user=USERNAME))
    f = parse_favorites(page)
    now = int(time.time())
    con.execute("DELETE FROM favorites")
    for i, (aid, t) in enumerate(f["anime"]):
        con.execute("INSERT INTO favorites VALUES('anime',?,?,?,?,?)", (aid, t, "", i, now))
    for i, (cid, n, frm) in enumerate(f["characters"]):
        con.execute("INSERT INTO favorites VALUES('character',?,?,?,?,?)", (cid, n, frm, i, now))
    for i, (pid, n) in enumerate(f["people"]):
        con.execute("INSERT INTO favorites VALUES('people',?,?,?,?,?)", (pid, n, "", i, now))
    con.commit()
    print(f"[favorites] anime {len(f['anime'])}, characters {len(f['characters'])}, people {len(f['people'])} -> DB\n")
    print("FAVORITE ANIME:      " + "; ".join(t for _, t in f["anime"]))
    print("FAVORITE CHARACTERS: " + "; ".join(f"{n} ({frm[:22]})" for _, n, frm in f["characters"]))
    print("FAVORITE SEIYUU:     " + "; ".join(n for _, n in f["people"]))
    # cross against behavioural affinity
    fav_people = {pid for pid, _ in f["people"]}
    if con.execute("SELECT COUNT(*) FROM anime_cast").fetchone()[0]:
        print("\n=== declared favorite seiyuu vs his behaviour (hours / drops / avg score on their shows) ===")
        dur = {a: (s or 1440) for a, s in con.execute("SELECT anime_id,avg_episode_seconds FROM anime_detail")}
        hours = {a: n * dur.get(a, 1440) / 3600 for a, n in con.execute("SELECT anime_id,COUNT(*) FROM episodes GROUP BY anime_id")}
        his = {a: (st, sc) for a, st, sc in con.execute("SELECT anime_id,status,score FROM anime")}
        for pid, name in f["people"]:
            shows = {}
            for aid, role in con.execute("SELECT anime_id,role FROM anime_cast WHERE jp_va_id=?", (pid,)):
                if aid in his:
                    shows[aid] = max(shows.get(aid, 0), 1.0 if role == "Main" else 0.45)
            h = sum(hours.get(a, 0) * w for a, w in shows.items())
            done = sum(1 for a in shows if his[a][0] == 2); drop = sum(1 for a in shows if his[a][0] == 4)
            sc = [his[a][1] for a in shows if his[a][1]]
            avg = sum(sc) / len(sc) if sc else None
            print(f"  {name:22s} {h:6.1f} h over {len(shows):3d} shows | finished {done}, dropped {drop} | his avg {f'{avg:.1f}' if avg else '-'}")


def cmd_watching(args):
    """What he is currently watching, and an estimate of when each finishes,
    from his own pacing: the title's recent eps/day (from its logged events),
    falling back to his global median pace, with a staleness flag for shows he
    has not touched in a while (the honest part: a cold show has no ETA)."""
    from statistics import median
    con = db()
    now = datetime.datetime.now()

    # global pace: across all series with enough events, median eps per active day
    # in their last stretch, as the fallback for titles with no rhythm yet
    per = {}
    for aid, ep, w in con.execute("SELECT anime_id,ep,watched_at FROM episodes ORDER BY watched_at"):
        per.setdefault(aid, []).append(datetime.datetime.fromisoformat(w))
    paces = []
    for aid, ws in per.items():
        if len(ws) >= 6:
            span_days = max(1.0, (ws[-1] - ws[0]).total_seconds() / 86400)
            paces.append(len(ws) / span_days)
    global_pace = median(paces) if paces else 0.5   # eps per calendar day
    stale_days = args.stale

    rows = con.execute("""SELECT a.anime_id,a.title,a.watched_episodes,COALESCE(d.api_num_episodes,a.num_episodes),
        d.avg_episode_seconds,COALESCE(d.api_media_type,a.media_type),a.updated_at
        FROM anime a LEFT JOIN anime_detail d ON d.anime_id=a.anime_id WHERE a.status=1""").fetchall()
    out = []
    for aid, title, watched, total, secs, mt, upd in rows:
        watched = watched or 0
        total = total or 0
        secs = secs or 24 * 60
        ws = per.get(aid, [])
        last = ws[-1] if ws else (datetime.datetime.fromtimestamp(upd) if upd else None)
        days_since = (now - last).total_seconds() / 86400 if last else None
        remaining = max(0, total - watched) if total else None
        # per-title pace: eps over the recent window (last 30 days of its events), else lifetime
        pace = None; basis = ""
        if len(ws) >= 2:
            recent = [w for w in ws if (ws[-1] - w).days <= 30]
            if len(recent) >= 2:
                span = max(1.0, (recent[-1] - recent[0]).total_seconds() / 86400)
                pace = len(recent) / span; basis = f"own pace, last {len(recent)} eps"
            else:
                span = max(1.0, (ws[-1] - ws[0]).total_seconds() / 86400)
                pace = len(ws) / span; basis = f"own pace, {len(ws)} eps lifetime"
        if not pace or pace <= 0:
            pace = global_pace; basis = "your median pace"
        eta = None
        if remaining is not None and remaining > 0:
            eta_days = remaining / pace
            eta = now + datetime.timedelta(days=eta_days)
        hours_left = remaining * secs / 3600 if remaining is not None else None
        out.append(dict(aid=aid, title=title, watched=watched, total=total, remaining=remaining,
                        hours_left=hours_left, last=last, days_since=days_since, pace=pace, basis=basis,
                        eta=eta, stale=(days_since is not None and days_since > stale_days), mt=mt, secs=secs))

    active = [o for o in out if not o["stale"]]
    cold = [o for o in out if o["stale"]]
    active.sort(key=lambda o: (o["eta"] or now + datetime.timedelta(days=9999)))
    cold.sort(key=lambda o: -(o["days_since"] or 0))

    print(f"currently watching: {len(out)} titles  |  your median pace across series: {global_pace:.2f} eps/day  |  stale after {stale_days} days\n")
    print("=" * 78); print("ACTIVE (touched recently) — ETA from your pace on each"); print("=" * 78)
    tot_hours = 0
    for o in active:
        rem = f"{o['remaining']} left" if o['remaining'] is not None else "? left"
        hl = f"{o['hours_left']:.1f} h" if o['hours_left'] is not None else "?"
        tot_hours += o['hours_left'] or 0
        eta_s = o['eta'].strftime("%a %b %d") if o['eta'] else ("done?" if o['remaining'] == 0 else "?")
        eta_in = f"(~{(o['eta']-now).days}d)" if o['eta'] else ""
        print(f"  {o['title'][:40]:40s} {o['watched']:>3}/{o['total'] or '?':<3} {rem:>8}  {hl:>7}  "
              f"last {o['days_since']:.0f}d ago  pace {o['pace']:.2f}/d  -> ETA {eta_s} {eta_in}")
        print(f"      basis: {o['basis']}")
    print(f"\n  total remaining in active shows: {tot_hours:.1f} h")
    if cold:
        print("\n" + "=" * 78); print(f"COLD (untouched > {stale_days} days) — no honest ETA; these are the drop candidates"); print("=" * 78)
        for o in cold:
            rem = f"{o['remaining']} left" if o['remaining'] is not None else "? left"
            hl = f"{o['hours_left']:.1f} h" if o['hours_left'] is not None else "?"
            print(f"  {o['title'][:40]:40s} {o['watched']:>3}/{o['total'] or '?':<3} {rem:>8}  {hl:>7}  "
                  f"last {o['days_since']:.0f}d ago  (if resumed at your median pace: ~{(o['remaining'] or 0)/global_pace:.0f}d to finish)")
    print()


def main():
    ap = argparse.ArgumentParser(description="MyAnimeList episode-history backfill / watch / analysis")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lg = sub.add_parser("login")
    lg.add_argument("--timeout", type=int, default=600, help="seconds to wait for you to log in")
    sub.add_parser("sync")
    b = sub.add_parser("backfill")
    b.add_argument("--statuses", default="", help="comma list, e.g. 2,4,1 (default all)")
    b.add_argument("--limit", type=int, default=0)
    b.add_argument("--delay", type=float, default=1.6, help="seconds between anime")
    b.add_argument("--headless", action="store_true")
    b.add_argument("--no-sync", action="store_true")
    b.add_argument("--force", action="store_true", help="re-scrape even if unchanged")
    w = sub.add_parser("watch")
    w.add_argument("--interval", type=int, default=300)
    w.add_argument("--enrich", action="store_true", help="also fetch exact minute via login")
    dm = sub.add_parser("daemon", help="run forever: list sync + history poll + periodic panel reconcile")
    dm.add_argument("--interval", type=int, default=300, help="seconds between polls")
    dm.add_argument("--reconcile", type=float, default=6.0, help="hours between full panel reconciles")
    dm.add_argument("--log", default=os.path.join(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__))), "logs", "mal_daemon.log"),
                    help="where the daemon writes its own lines; empty for stdout only. Its "
                         "output went nowhere for eight days because the launcher redirect "
                         "binds to cmd's start rather than to the process it detaches")
    dm.add_argument("--jikan-watch-seconds", type=float, default=3600.0,
                    dest="jikan_watch_seconds",
                    help="how often at most to ask whether the outage in front of MyAnimeList "
                         "is over. Recorded in the mirror's meta table and read by nothing; "
                         "0 asks on every poll, a huge number never asks")
    dm.add_argument("--detail-enrich-minutes", type=float, default=30.0,
                    dest="detail_enrich_minutes",
                    help="how often at most to fetch a small batch of missing anime_detail "
                         "rows from the API v2, throttled so new titles fill in without a "
                         "manual `enrich` run; 0 disables")
    dm.add_argument("--detail-enrich-batch", type=int, default=5,
                    dest="detail_enrich_batch",
                    help="how many titles' anime_detail to fetch per throttled pass")
    sub.add_parser("reap", help="kill the Chrome/chromedriver a force-killed daemon left on its profile")
    ex = sub.add_parser("export", help="CSV of episodes + anime")
    ex.add_argument("--out", default="", help="output dir (default data/mal_export)")
    en = sub.add_parser("enrich", help="per-title detail from the MAL API (duration, studios, full genres...)")
    en.add_argument("--client-id", default="", help="MAL API client id (default: config.json sensors.mal_client_id)")
    en.add_argument("--limit", type=int, default=0)
    en.add_argument("--delay", type=float, default=0.35, help="seconds between API calls")
    en.add_argument("--force", action="store_true", help="re-fetch all titles")
    r = sub.add_parser("report")
    r.add_argument("--anime", default="")
    r.add_argument("--detail", action="store_true", help="full analysis: watch time, habits over time, genres, studios, pacing, scores")
    wt = sub.add_parser("watching", help="what you're watching now + ETA to finish each, from your own pace")
    wt.add_argument("--stale", type=int, default=21, help="days untouched before a show counts as cold")
    cd = sub.add_parser("cadence", help="how fast he watches, what he has quietly abandoned, and status changes")
    cd.add_argument("--stall", type=float, default=3.0,
                    help="how many times its own median gap counts as abandoned (default 3)")
    cd.set_defaults(func=cmd_cadence)
    cs = sub.add_parser("cast", help="fetch cast + JP voice actors for every watched anime (public MAL pages)")
    cs.add_argument("--limit", type=int, default=0)
    cs.add_argument("--delay", type=float, default=1.0)
    sy = sub.add_parser("seiyuu", help="which voice actors you like, from your hours/scores/completion")
    sy.add_argument("--top", type=int, default=30)
    sy.add_argument("--min-shows", type=int, default=3)
    sub.add_parser("favorites", help="your explicit MAL favorites (anime/characters/people) -> DB, crossed with behaviour")
    ms = sub.add_parser("migrate-stamps", help="one row per watch on this machine's clock: drop the "
                                               "public page's duplicate of a row the panel has, move "
                                               "the rest off the site's clock. STOP THE DAEMON FIRST")
    ms.add_argument("--apply", action="store_true", help="write it; without this it only prints")
    ms.add_argument("--backup", default="", help="write the table as it stands to this CSV first")
    args = ap.parse_args()
    if args.cmd == "migrate-stamps":
        cmd_migrate_stamps(args)
    elif args.cmd == "login":
        cmd_login(args)
    elif args.cmd == "sync":
        sync_anime(db())
    elif args.cmd == "backfill":
        cmd_backfill(args)
    elif args.cmd == "watch":
        cmd_watch(args)
    elif args.cmd == "daemon":
        cmd_daemon(args)
    elif args.cmd == "reap":
        cmd_reap(args)
    elif args.cmd == "export":
        cmd_export(args)
    elif args.cmd == "enrich":
        cmd_enrich(args)
    elif args.cmd == "report":
        cmd_report(args)
    elif args.cmd == "watching":
        cmd_watching(args)
    elif args.cmd == "cadence":
        cmd_cadence(args)
    elif args.cmd == "cast":
        cmd_cast(args)
    elif args.cmd == "seiyuu":
        cmd_seiyuu(args)
    elif args.cmd == "favorites":
        cmd_favorites(args)


if __name__ == "__main__":
    main()
