import glob
import io
import json
import os
import re
import shutil
import sqlite3
import tempfile
import time

import logger

# What is read in a visual novel, taken out of the text hooker's
# own files (Luna Translator). Three things this needs are already on his disk,
# on disk, and none of them needs the program to be running:
#
#   * one SQLite file per game under `eroge.cache_dir`, named
#     `<title>_<unix time the game was added>_<uuid>.sqlite`, holding every
#     line the hook has caught in the order he read them. It is a CACHE, not a
#     log -- a line he re-reads adds no row -- so the row id answers "how far
#     into text he has not seen before has he got" and never "is he playing";
#   * `savegame.db` under `eroge.userconfig_dir`, whose `game_word_count` is
#     one row per hooked line with a wall-clock time on it. That is the
#     timestamp the per-game record does not carry, and it is what "since
#     when" and "how many lines this session" come out of;
#   * `savegamedata_*.json` beside it: the title, the executable, the
#     visual-novel-database id, the developer, and the cast's names with the
#     readings he set for them. The join between the two files is the
#     `<unix>_<uuid>` half of the record's filename, matched as a string.
#
# READ-ONLY, always, and nothing under his eroge directory is ever opened for
# writing. Both databases are journal mode `delete` with no write-ahead log, so
# a reader can meet the writer's commit lock for a fraction of a second; that
# is what the temporary copy below is for, and the copy goes to the system
# temporary directory and is deleted, never under the project.
#
# This module returns lines, sessions and identities. It knows nothing about
# digests, situations or characters, and it filters nothing on content : what is done with the raw
# text is its caller's decision, and its caller never stores it.

# A bad hook emits junk: one file's newest rows are `UserData\ImaImo018.sud`
# and another's are `の` and `のつ覚え`. A length floor plus "it must contain
# kana or kanji" drops those, and neither is a dial worth having in config --
# they are properties of a broken hook, not of how much she is told.
_MIN_LINE_CHARS = 4
_JP = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")

# Luna emits a merged block for some hooks: one row whose text is the
# concatenation of the nine before it. Left in, it repeats a whole minute of
# dialogue inside one line. A row is a merged block when it contains a recent
# row's text in full AND is at least twice as long -- the length test is what
# stops a bare `「……」` swallowing the ordinary line that quotes it.
_AGGREGATE_LOOKBACK = 15
_AGGREGATE_MIN_PART = 12

# How long a run of lines arriving faster than `eroge.skip_lines_per_second`
# has to be before it is him holding the skip button rather than one text box
# firing twice. Measured on his own history: the longest naturally occurring
# fast run in 29,110 intervals across seven games is eight lines.
_SKIP_MIN_LINES = 10

_BUSY_MS = 3000


def _uri(path):
    return "file:" + str(path).replace("\\", "/") + "?mode=ro"


def _rows(path, sql, args=()):
    """Rows out of a database another program owns.

    A read-only connection first; if the writer holds the commit lock, a
    temporary copy in the system temporary directory, read and then deleted.
    Never a read-write open: that would create a journal file beside his data.
    An unreadable file is an empty answer and one log line naming the
    exception's type."""
    if not path or not os.path.exists(path):
        return []
    try:
        con = sqlite3.connect(_uri(path), uri=True)
        try:
            con.execute("pragma busy_timeout = %d" % _BUSY_MS)
            return con.execute(sql, args).fetchall()
        finally:
            con.close()
    except sqlite3.Error as e:
        logger.log(f"[eroge] {os.path.basename(path)} is held ({type(e).__name__}); reading a copy")
    tmp = ""
    try:
        fd, tmp = tempfile.mkstemp(prefix="scail_eroge_", suffix=".sqlite")
        os.close(fd)
        shutil.copyfile(path, tmp)
        con = sqlite3.connect(_uri(tmp), uri=True)
        try:
            return con.execute(sql, args).fetchall()
        finally:
            con.close()
    except (sqlite3.Error, OSError) as e:
        logger.log(f"[eroge] {os.path.basename(path)} not read: {type(e).__name__}")
        return []
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass


def _dirs(config):
    c = config.eroge
    return (os.path.expandvars(str(c.cache_dir or "")),
            os.path.expandvars(str(c.userconfig_dir or "")))


def _save_db(config):
    return os.path.join(_dirs(config)[1], "savegame.db")


def _library_file(config):
    """The newest `savegamedata_<version>.json` in his translator's config
    directory. Globbed rather than named, so the file survives him updating
    the program."""
    _cache, uc = _dirs(config)
    if not uc or not os.path.isdir(uc):
        return ""
    files = sorted(glob.glob(os.path.join(uc, "savegamedata_*.json")), key=os.path.getmtime)
    return files[-1] if files else ""


def _library(config):
    """(games by key, the order he added them). The file is a two-element
    list: an ordering of keys, then a dictionary keyed the same way."""
    path = _library_file(config)
    if not path:
        return {}, []
    try:
        with io.open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError) as e:
        logger.log(f"[eroge] the game library was not read: {type(e).__name__}")
        return {}, []
    if not (isinstance(d, list) and len(d) >= 2 and isinstance(d[1], dict)):
        logger.log("[eroge] the game library is not the shape this reads")
        return {}, []
    order = [str(k) for k in (d[0] or []) if isinstance(k, str)]
    return d[1], order


def _internal_ids(config):
    """{the record's key: the id the event stream uses}."""
    rows = _rows(_save_db(config), "select gameinternalid, gameuid from gameinternalid_v2")
    return {str(uid): int(gid) for gid, uid in rows if uid}


def _cast(entry):
    """The cast as the translator holds them: the name as the game writes it
    and the reading he set beside it. Both are things he might type, and both
    are what makes a mention of one of them find the game weeks later."""
    out, seen = [], set()
    for row in entry.get("namemap2") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("key") or "").strip()
        reading = str(row.get("value") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append({"name": name, "reading": reading})
    return out


def _vndb_id(entry):
    try:
        v = int(entry.get("vid") or 0)
    except (TypeError, ValueError):
        return None
    return v or None


def games(config):
    """Every game on file, newest first:

    [{key, internal_id, title, exe, vndb_id, developer, cast, created_ts,
      chars_read}]

    `key` is the translator's own `<unix>_<uuid>`, which is what joins the
    three files and what a caller remembers a cursor against."""
    lib, order = _library(config)
    if not lib:
        return []
    ids = _internal_ids(config)
    keys = [k for k in order if k in lib] + [k for k in lib if k not in order]
    out = []
    for key in keys:
        g = lib.get(key) or {}
        if not isinstance(g, dict):
            continue
        devs = [str(d) for d in (g.get("developers") or []) if d]
        try:
            chars = int(g.get("statistic_wordcount") or 0)
        except (TypeError, ValueError):
            chars = 0
        out.append({
            "key": str(key),
            "internal_id": ids.get(str(key)),
            "title": str(g.get("title") or ""),
            "exe": str(g.get("gamepath") or ""),
            "vndb_id": _vndb_id(g),
            "developer": devs[0] if devs else "",
            "cast": _cast(g),
            "created_ts": float(g.get("createtime") or 0),
            "chars_read": chars,
        })
    out.sort(key=lambda r: -float(r.get("created_ts") or 0))
    return out


def record_file(config, game_key):
    """The per-game record for one key, or "". The filename is the title, the
    key and `.sqlite`, so the key is matched as a suffix of the stem and a
    title with an underscore in it cannot confuse the split."""
    cache, _uc = _dirs(config)
    if not cache or not os.path.isdir(cache) or not game_key:
        return ""
    tail = "_" + str(game_key) + ".sqlite"
    for f in glob.glob(os.path.join(cache, "*.sqlite")):
        if os.path.basename(f).endswith(tail):
            return f
    return ""


def now_playing(config, within_minutes=None):
    """Is he in a game, which one, and since when -- or None.

    None when nothing has been hooked in the last `eroge.stale_minutes`. The
    same gap ends a session, so a resume looks exactly like a start and needs
    no distinguishing: the stream simply begins again.

    `within_minutes` widens only how recent the last line has to be, never the
    gap that cuts the session -- which is what a report or a check uses to ask
    for the LAST session rather than the live one. Widening both would run
    yesterday evening and this afternoon together into one twenty-hour sitting.

    This is the event stream's answer and not the record's: the record only
    changes when he reaches text he has not seen before, so a two-hour replay
    of a route he has already read would look like a stop."""
    c = config.eroge
    gap = float(c.stale_minutes) * 60.0
    fresh = float(within_minutes if within_minutes is not None else c.stale_minutes) * 60.0
    db = _save_db(config)
    rows = _rows(db, "select gameinternalid, max(time) from game_word_count group by gameinternalid")
    best = None
    for gid, last in rows:
        try:
            gid, last = int(gid), float(last or 0)
        except (TypeError, ValueError):
            continue
        if last and (best is None or last > best[1]):
            best = (gid, last)
    if best is None:
        return None
    gid, last = best
    now = time.time()
    if now - last > fresh:
        return None
    times = [float(t) for (t,) in _rows(
        db, "select time from game_word_count where gameinternalid=? and time>=? order by time",
        (gid, last - 86400.0)) if t]
    start, lines = last, 0
    for t in reversed(times):
        if start - t > gap:
            break
        start, lines = t, lines + 1
    entry = next((g for g in games(config) if g.get("internal_id") == gid), None) or {}
    return {"key": entry.get("key", ""), "internal_id": gid,
            "title": entry.get("title", ""), "vndb_id": entry.get("vndb_id"),
            "exe": entry.get("exe", ""),
            "since_ts": start, "last_line_ts": last,
            "lines_this_session": lines,
            "minutes": (last - start) / 60.0}


def lines_since(config, game_key, last_id=0, max_lines=None):
    """The Japanese he has reached since the remembered id, and the new mark:
    ([{id, text}], last_id).

    `origin` and never `source`: `source` strips the speaker's name, and the
    speaker is most of what makes a run of lines legible as a scene. The
    machine-translation column is not read at all -- the Japanese line is the
    input, and a machine translation of it is a worse one.

    Because the record never stores a line twice, everything past the mark is
    precisely text he has not seen before. Past `max_lines` the NEWEST are
    kept and the mark still moves past everything; `max_lines` None is
    uncapped. What the digest is written from is `latest_scene` rather than
    this -- this is the plain primitive, and what the check reads."""
    cap = int(max_lines or 0)
    path = record_file(config, game_key)
    mark = int(last_id or 0)
    if not path:
        return [], mark
    rows = _rows(path, "select id, origin from artificialtrans where id > ? order by id", (mark,))
    kept, mark = _clean(rows, mark)
    if cap and len(kept) > cap:
        logger.log(f"[eroge] {len(kept)} new line(s) past the mark; the newest {cap} taken")
        kept = kept[-cap:]
    return kept, mark


def read_window(events, cursor=0, skip_lps=1.0, max_raw_chars=16000):
    """Where his current stretch of READING begins, how many lines it is, and
    why it begins there: (cursor, lines, note).

    A pure function over one sitting's line events -- `[(wall-clock time,
    characters in the line)]`, ascending -- so it can be checked against his
    real stream and against made-up runs. `cursor` is an index into that list
    and the answer never moves backwards past it.

    There is no timer here and no scene inference. A pause of an hour with the
    game open does not move the cursor. Two things do:

    **A skip run.** Holding the skip button hooks lines at a rate no reader
    produces. Measured over his whole history -- 29,110 intervals inside
    sittings across seven games -- the median gap between consecutive lines is
    5.0 seconds, the first percentile is 1.19 seconds, and 99.4% of intervals
    are slower than one line a second. So a stretch arriving faster than
    `skip_lps` is not reading, it is excluded entirely and never summarised,
    and the cursor moves to the first line after it. A single fast pair is a
    text box that fired twice rather than a skip, so a run has to be at least
    `_SKIP_MIN_LINES` long: the longest naturally occurring fast run in those
    29,110 intervals is eight lines, and the floor is above it.

    **The window overflowing.** Past `max_raw_chars` of read text the cursor
    moves forward until what is left fits, taken from the end. That is also
    what catches "something weird" -- a hooked menu, a line repeating in a
    storm -- without needing to know what the weird thing was.

    `note` is "" for a clean stretch, "skipped" when a skip run set the
    cursor, "ran long" when the overflow did."""
    rows = [(float(t), int(w or 0)) for t, w in (events or []) if t is not None]
    n = len(rows)
    if not n:
        return max(int(cursor or 0), 0), 0, ""
    fast = 1.0 / max(float(skip_lps), 1e-6)
    skip = [False] * n
    i = 0
    while i < n - 1:
        j = i
        while j < n - 1 and (rows[j + 1][0] - rows[j][0]) < fast:
            j += 1
        if j - i + 1 >= _SKIP_MIN_LINES:
            for k in range(i, j + 1):
                skip[k] = True
        i = j + 1
    start = min(max(int(cursor or 0), 0), n)
    note = ""
    last_skip = max((k for k in range(start, n) if skip[k]), default=-1)
    if last_skip >= 0:
        start = last_skip + 1
        note = "skipped"
    budget = int(max_raw_chars)
    used = sum(rows[k][1] + 1 for k in range(start, n))
    while start < n - 1 and used > budget:
        used -= rows[start][1] + 1
        start += 1
        note = "ran long"
    return start, n - start, note


def read_lines(config, playing, cursor=0):
    """The lines of his current stretch of reading, with the speaker:
    {lines, chars, note, cursor, first_id, last_id}.

    `cursor` in and `cursor` out are indices into the sitting's own event
    list, which is stable while the sitting lasts; `first_id` is the record's
    id for the first line of the stretch, which is what a caller keys a cached
    digest on and what the operator's view shows.

    How many lines the stretch is comes from the event stream, which has the
    wall-clock times; the lines themselves come from the record, which has no
    times at all. The two are matched by counting back from the newest, which
    is exact for a stretch he read forwards and errs by a few lines of what
    came before when he re-read something -- which costs nothing, because the
    answer is an account of what is happening rather than a boundary."""
    out = {"lines": [], "chars": 0, "note": "", "cursor": max(int(cursor or 0), 0),
           "first_id": 0, "last_id": 0}
    if not playing or not playing.get("key"):
        return out
    c = config.eroge
    events = _rows(_save_db(config),
                   "select time, wordcount from game_word_count where gameinternalid=? "
                   "and time>=? order by time", (playing["internal_id"], playing["since_ts"] - 0.5))
    out["cursor"], want, out["note"] = read_window(
        events, cursor, c.skip_lines_per_second, c.max_raw_chars)
    path = record_file(config, playing["key"])
    if not path or want <= 0:
        return out
    rows = _rows(path, "select id, origin from artificialtrans order by id desc limit ?",
                 (want + 20,))
    kept, out["last_id"] = _clean(list(reversed(rows)), 0)
    kept = kept[-want:]
    # The budget is settled here, on the text that will actually be handed
    # over, and not on the event stream's own count of it: the stream counts
    # the line with the speaker's name stripped off, and the name is what the
    # record keeps and what makes the run legible. Over 690 lines that
    # difference was 3,177 characters, and the first run went out at 19,177
    # against a ceiling of 16,000.
    budget = int(config.eroge.max_raw_chars)
    used, drop = 0, 0
    for k, line in enumerate(reversed(kept)):
        if used + len(line["text"]) + 1 > budget and k:
            drop = len(kept) - k
            break
        used += len(line["text"]) + 1
    if drop:
        kept = kept[drop:]
        out["note"] = "ran long"
        out["cursor"] += drop
    out["lines"] = kept
    out["chars"] = sum(len(k["text"]) + 1 for k in kept)
    out["first_id"] = kept[0]["id"] if kept else 0
    return out


def _clean(rows, mark=0):
    """(id, origin) rows in reading order as usable lines, and the newest id.

    Two filters, neither a dial in config, because both are properties of a
    broken hook rather than of how much she is told: a length floor with a
    "must contain kana or kanji" test for the junk, and the merged-block test
    for a row that repeats a recent one inside itself."""
    kept = []
    for rid, origin in rows:
        try:
            rid = int(rid)
        except (TypeError, ValueError):
            continue
        mark = max(mark, rid)
        text = " ".join(str(origin or "").split())
        if len(text) < _MIN_LINE_CHARS or not _JP.search(text):
            continue
        if any(len(k["text"]) >= _AGGREGATE_MIN_PART and len(text) >= 2 * len(k["text"])
               and k["text"] in text for k in kept[-_AGGREGATE_LOOKBACK:]):
            continue
        kept.append({"id": rid, "text": text})
    return kept, mark


def report(config):
    """The operator's view of the reader: whether he is in a game now, which,
    since when, and one row per game on file. No model, no store."""
    c = config.eroge
    cache, uc = _dirs(config)
    out = {"enabled": bool(c.enabled),
           "cache_dir": cache, "userconfig_dir": uc,
           "cache_readable": bool(cache and os.path.isdir(cache)),
           "library_file": os.path.basename(_library_file(config)),
           "stale_minutes": float(c.stale_minutes),
           "scene_gap_minutes": float(c.scene_gap_minutes),
           "skip_lines_per_second": float(c.skip_lines_per_second)}
    rows = games(config)
    out["games"] = [{"title": g["title"], "vndb_id": g["vndb_id"],
                     "developer": g["developer"], "cast": len(g["cast"]),
                     "chars_read": g["chars_read"]} for g in rows]
    live = now_playing(config)
    last = live or now_playing(config, within_minutes=60 * 24 * 30)
    out["playing_now"] = bool(live)
    if last:
        out["title"] = last["title"]
        out["vndb_id"] = last["vndb_id"]
        out["since"] = time.strftime("%m-%d %H:%M", time.localtime(last["since_ts"]))
        out["last_line"] = time.strftime("%m-%d %H:%M", time.localtime(last["last_line_ts"]))
        out["minutes"] = round(last["minutes"], 1)
        out["lines_this_session"] = last["lines_this_session"]
        rl = read_lines(config, last)
        out["read_lines"] = len(rl["lines"])
        out["read_chars"] = rl["chars"]
        out["read_from_id"] = rl["first_id"]
        out["read_note"] = rl["note"]
    else:
        out["title"] = ""
    return out
