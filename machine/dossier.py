"""One file per play, joining everything the machine already knows about it.

Every piece of this was already on disk and nothing joined them. The media
player writes a line when a file is opened and another when it ends; the
MyAnimeList mirror holds the list, the dated episode watches, the cast and the
declared favourites; the machine's retrieval store holds the episode index in
three scripts, the page a judge chose for that episode, the digest made from
it and the ordered scenes. Answering "what did he just watch, and what is his
history with it" meant opening four stores by hand. This writes it out once
per play instead.

**It is the machine's and runs once.** Three character processes tail the same
media-player history, so a dossier built inside a character's loop would be
built three times, in three saves, by three programs. It is built by the
MyAnimeList mirror daemon (`tools/mal_history.py daemon`), which is the one
process per machine, and an already-built play is skipped on its open time,
so a restart mid-day rebuilds nothing.

**It is built after the play ENDS.** How far he got and how long he was
actually in it are only known then, and a file opened and closed inside ten
minutes is not a play at all: it gets a line in the rolling file and no
dossier. The numbers come from the end-of-play record the player writes,
read through `machine/plays.py`, which is the only definition of that format.
Where the player has recorded no end, the estimate is the gap to the next file
opened -- the same rule the character-side watcher falls back on -- and the
dossier says which of the two it was, because a number nobody can tell the
provenance of is worse than no number.

**Nothing here writes the list mirror.** The daemon owns that file and holds
it open; the two page reads this module makes -- an actor's filmography and a
missing premiere date -- are cached in its own store beside the build markers
(`data/dossiers.db`), so the command-line door can be used while the daemon is
running without two processes writing one database.

Manual door, which is also how it is tested:

    python -m machine.dossier --last            # the newest finished play
    python -m machine.dossier --last 3          # the newest three
    python -m machine.dossier --epoch 1788834607
    python -m machine.dossier --path "...\\Show - S01E03.mkv"
    python -m machine.dossier --list            # what has been built

spec: docs/dossiers.md
"""

import argparse
import datetime
import hashlib
import json
import ntpath
import os
import re
import sqlite3
import sys
import time
import urllib.request

# A browser-shaped header, because MyAnimeList's own origin is what is read
# here. The community wrapper in front of it is never used: it has answered
# 504 on every uncached path since 2026-08-28 while the origin answered in
# under a second (`sim/anime_kb.py`, `data/retired/20260904_jikan_504/`).
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATUS_WORD = {1: "watching", 2: "completed", 3: "on hold", 4: "dropped",
               6: "plan to watch", 0: "not on your list"}



# ---------------- settings ----------------

try:
    from config import DEFAULTS as _DEFAULTS
except Exception:                                   # config.py is not importable
    _DEFAULTS = {}


def settings():
    """What this module runs on: the defaults in `config.py`, with whatever a
    config FILE on disk says over the top.

    The daemon that calls this has no character and must not build one -- a
    Config would print a character's name into the machine's log -- so the
    file is read as JSON, first one wins, exactly as the daemon's subtitle
    mirror refresh does."""
    out = dict(_DEFAULTS.get("dossier") or {})
    sensors = dict(_DEFAULTS.get("sensors") or {})
    for name in sorted(f for f in os.listdir(ROOT)
                       if f == "config.json" or (f.startswith("config_") and f.endswith(".json"))):
        try:
            with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        out.update({k: v for k, v in (d.get("dossier") or {}).items() if v is not None})
        for k, v in (d.get("sensors") or {}).items():
            if k in ("mal_history_db", "retrievals_db", "mal_client_id") and v:
                sensors[k] = v
        break
    out.setdefault("enabled", True)
    out.setdefault("dir", "reports/dossiers")
    out.setdefault("db_path", "data/dossiers.db")
    out.setdefault("last_n", 10)
    out.setdefault("min_watched_minutes", 10.0)
    out.setdefault("hours_before", 6.0)
    out.setdefault("hours_after", 6.0)
    out.setdefault("per_cycle_cap", 3)
    out.setdefault("cast_detail_cap", 9)
    out.setdefault("actor_list_cap", 12)
    out.setdefault("actor_fetch_cap", 3)
    out.setdefault("premiere_fetch_cap", 2)
    out.setdefault("fetch_delay_seconds", 1.5)
    out.setdefault("fetch_ttl_days", 120)
    out.setdefault("fetch_timeout_seconds", 25)
    out["mirror_db"] = sensors.get("mal_history_db") or "data/mal_history.db"
    out["retrievals_db"] = sensors.get("retrievals_db") or "data/retrievals.db"
    out["mal_client_id"] = sensors.get("mal_client_id") or ""
    # The log of every file opened belongs to the player and is already named
    # once, in the section the character-side watcher reads; naming it twice
    # is two things to keep in step.
    watching = dict(_DEFAULTS.get("watching") or {})
    out["player_history"] = os.path.expandvars(
        str(watching.get("player_history_path") or "%APPDATA%/mpv/mpv_history.log"))
    out["player_plays"] = os.path.expandvars(
        str(watching.get("player_plays_path") or "%APPDATA%/mpv/mpv_plays.log"))
    return out


def _abs(path):
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


# ---------------- the two local logs the player writes ----------------

def opens(history_path, limit=0):
    """[(epoch, path)] for every file the player has opened, oldest first.

    Ordinary string work on a local file, so it is safe to read whole: the
    log is a quarter of a megabyte after three years."""
    try:
        with open(history_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return []
    if limit:
        lines = lines[-int(limit):]
    out = []
    for line in lines:
        stamp, sep, p = line.strip().partition("|")
        if not sep:
            continue
        try:
            out.append((float(stamp), p))
        except ValueError:
            continue
    out.sort(key=lambda r: r[0])
    return out


def plays(plays_path):
    """Every play the player has FINISHED, oldest first, or [] when it has
    recorded none. `machine/plays.py` is the reader and the format's only
    definition; this module never parses that log itself."""
    try:
        from machine import plays as _plays
    except ImportError:
        return []
    try:
        return sorted(_plays.read(plays_path, tail=800),
                      key=lambda r: int(r.get("opened") or 0))
    except Exception:
        return []


def play_for(open_epoch, cfg):
    """What is known about one play: the record the player wrote when it
    ended, or an estimate built from the next file it opened.

    `source` says which, and every line that quotes a duration says it too --
    a number nobody can tell the provenance of is worse than no number."""
    want = float(open_epoch)
    hist = opens(cfg["player_history"])
    path = next((p for ts, p in hist if abs(ts - want) <= 2.0), "")
    try:
        from machine import plays as _plays
        row = _plays.for_open(cfg["player_plays"], want, file_path=path)
    except ImportError:
        row = None
    except Exception:
        row = None
    if row:
        return {"open": float(row.get("opened") or want), "end": float(row.get("ended") or 0),
                "path": row.get("path") or path, "length": float(row.get("length") or 0),
                "end_pos": float(row.get("time") or 0),
                "watched": float(row.get("watched") or 0), "reason": row.get("reason") or "",
                "source": "the player's own end-of-play record"}
    later = [ts for ts, _p in hist if ts > want + 1]
    end = min(later) if later else time.time()
    return {"open": want, "end": end, "path": path, "length": 0.0, "end_pos": 0.0,
            "watched": max(0.0, end - want), "reason": "",
            # No end recorded and nothing opened after it: he may still be in
            # it. Nothing is written for such a play, because the floor that
            # separates a play from a skim is measured on a number that is
            # still growing, and a marker written now would stand for good.
            "running": not later,
            "source": "estimated from the gap to the next file opened; the player has "
                      "recorded no end for this play"}


# ---------------- the mirror, read only ----------------

def _ro(path):
    try:
        return sqlite3.connect(f"file:{_abs(path)}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return None


def _jl(s):
    try:
        v = json.loads(s or "[]")
        return [str(x) for x in v] if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


def _stamp(ts, fmt="%Y-%m-%d %H:%M"):
    try:
        return datetime.datetime.fromtimestamp(float(ts)).strftime(fmt)
    except (ValueError, TypeError, OSError):
        return "?"


def _hms(seconds):
    s = int(max(0.0, float(seconds or 0)))
    return f"{s // 3600}h{(s % 3600) // 60:02d}m" if s >= 3600 else f"{s // 60}m{s % 60:02d}s"


_SEASON_ORDER = {"winter": 0, "spring": 1, "summer": 2, "fall": 3, "autumn": 3}


def _premiere_order(premiere):
    """(year, season) for sorting a franchise by when each entry came out.

    A broadcast season is written `fall 2007`, which sorts alphabetically into
    a nonsense order -- autumn before spring before winter, every year mixed
    together -- so the year is read out of it and the season turned into its
    place in the year. A date (`2024-10-05`) sorts on its own, and an entry
    with neither goes last, which is where an unannounced sequel belongs."""
    s = str(premiere or "").strip().lower()
    m = re.match(r"^(\d{4})-(\d{2})", s)
    if m:
        return int(m.group(1)), (int(m.group(2)) - 1) // 3
    y = re.search(r"(\d{4})", s)
    if not y:
        return 9999, 9
    season = next((v for k, v in _SEASON_ORDER.items() if k in s), 9)
    return int(y.group(1)), season


def _slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return (s or "play")[:60]


# ---------------- the build store: markers and the two cached fetches ----------------

class Store:
    """What has been built, and the two pages this module is allowed to read.

    Its own file rather than the list mirror. The mirror belongs to the daemon,
    which holds it open and writes it every cycle; the command-line door here
    is a second process, and two writers over one database is the fault this
    project has a machine-owned store to avoid."""

    def __init__(self, path):
        self.path = _abs(path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.con = sqlite3.connect(self.path, timeout=15)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA busy_timeout=15000")
        self.con.executescript("""
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS built (
            open_epoch INTEGER PRIMARY KEY, path TEXT, anime_id INTEGER, ep INTEGER,
            title TEXT, watched REAL, kind TEXT, file TEXT, built_at REAL, note TEXT);
        -- an actor's page, read at most `actor_fetch_cap` times per play
        CREATE TABLE IF NOT EXISTS person_page (
            person_id INTEGER PRIMARY KEY, name TEXT, name_jp TEXT, birthday TEXT,
            favorites TEXT, bio TEXT, roles TEXT, fetched_at REAL);
        -- a work's own facts, for the entries his list has no premiere date for
        CREATE TABLE IF NOT EXISTS anime_extra (
            anime_id INTEGER PRIMARY KEY, start_date TEXT, season TEXT, studios TEXT,
            num_episodes INTEGER, media_type TEXT, air_status TEXT, fetched_at REAL);
        """)
        self.con.commit()

    def close(self):
        try:
            self.con.close()
        except sqlite3.Error:
            pass

    def horizon(self, candidates, last_n):
        """The oldest play a SWEEP will look at, fixed the first time one runs.

        Without it, the first pass on a machine meets every file the player has
        ever opened -- three years of them -- and writes a dossier for each. A
        cold start begins where the rolling file begins and nothing older is
        ever considered again, which is the same decision the character-side
        watcher makes about his history and for the same reason. The
        command-line door ignores it: any play can still be built by hand."""
        r = self.con.execute("SELECT value FROM meta WHERE key='horizon'").fetchone()
        if r:
            try:
                return float(r[0])
            except (TypeError, ValueError):
                pass
        built = self.con.execute("SELECT MIN(open_epoch) FROM built").fetchone()
        if built and built[0]:
            h = float(built[0])
        else:
            ordered = sorted(float(x) for x in candidates)
            h = ordered[-int(last_n)] if len(ordered) >= int(last_n) else 0.0
        self.con.execute("INSERT OR REPLACE INTO meta (key,value) VALUES ('horizon', ?)", (str(h),))
        self.con.commit()
        return h

    def is_built(self, open_epoch):
        r = self.con.execute("SELECT 1 FROM built WHERE open_epoch=?",
                             (int(open_epoch),)).fetchone()
        return r is not None

    def mark(self, open_epoch, **row):
        """Written the moment the file exists, never held until the end of a
        run: a stop is `Stop-Process -Force`."""
        self.con.execute(
            "INSERT INTO built (open_epoch,path,anime_id,ep,title,watched,kind,file,built_at,note) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(open_epoch) DO UPDATE SET "
            "path=excluded.path, anime_id=excluded.anime_id, ep=excluded.ep, title=excluded.title, "
            "watched=excluded.watched, kind=excluded.kind, file=excluded.file, "
            "built_at=excluded.built_at, note=excluded.note",
            (int(open_epoch), str(row.get("path") or ""), int(row.get("anime_id") or 0),
             int(row.get("ep") or 0), str(row.get("title") or ""), float(row.get("watched") or 0),
             str(row.get("kind") or ""), str(row.get("file") or ""), time.time(),
             str(row.get("note") or "")))
        self.con.commit()

    def recent(self, n):
        return [dict(r) for r in self.con.execute(
            "SELECT * FROM built ORDER BY open_epoch DESC LIMIT ?", (int(n),))]

    def person(self, pid, ttl_days):
        r = self.con.execute("SELECT * FROM person_page WHERE person_id=?", (int(pid),)).fetchone()
        if not r:
            return None
        if (time.time() - float(r["fetched_at"] or 0)) > float(ttl_days) * 86400:
            return None
        d = dict(r)
        try:
            d["roles"] = json.loads(r["roles"] or "[]")
        except (ValueError, TypeError):
            d["roles"] = []
        return d

    def put_person(self, pid, d):
        self.con.execute(
            "INSERT INTO person_page (person_id,name,name_jp,birthday,favorites,bio,roles,fetched_at) "
            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(person_id) DO UPDATE SET name=excluded.name, "
            "name_jp=excluded.name_jp, birthday=excluded.birthday, favorites=excluded.favorites, "
            "bio=excluded.bio, roles=excluded.roles, fetched_at=excluded.fetched_at",
            (int(pid), d.get("name", ""), d.get("name_jp", ""), d.get("birthday", ""),
             d.get("favorites", ""), (d.get("bio") or "")[:1500],
             json.dumps(d.get("roles") or [], ensure_ascii=False), time.time()))
        self.con.commit()

    def extra(self, aid, ttl_days):
        r = self.con.execute("SELECT * FROM anime_extra WHERE anime_id=?", (int(aid),)).fetchone()
        if not r:
            return None
        if (time.time() - float(r["fetched_at"] or 0)) > float(ttl_days) * 86400:
            return None
        return dict(r)

    def put_extra(self, aid, d):
        self.con.execute(
            "INSERT INTO anime_extra (anime_id,start_date,season,studios,num_episodes,media_type,"
            "air_status,fetched_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(anime_id) DO UPDATE SET "
            "start_date=excluded.start_date, season=excluded.season, studios=excluded.studios, "
            "num_episodes=excluded.num_episodes, media_type=excluded.media_type, "
            "air_status=excluded.air_status, fetched_at=excluded.fetched_at",
            (int(aid), d.get("start_date", ""), d.get("season", ""),
             json.dumps(d.get("studios") or [], ensure_ascii=False),
             int(d.get("num_episodes") or 0), d.get("media_type", ""),
             d.get("air_status", ""), time.time()))
        self.con.commit()


# ---------------- the two cheap fetches ----------------

def fetch_person(pid, store, cfg, log):
    """One actor's page from MyAnimeList's own origin, into this module's own
    store. The mirror holds a filmography for thirteen people; every other
    credited actor answers "what else has she done" out of his own list alone,
    which is the gap this closes.

    A failure is logged by exception TYPE. The message of a network exception
    quotes the URL it failed on, and those URLs have carried a token."""
    try:
        from sim.anime_kb import parse_person
    except ImportError as e:
        log(f"[dossier] the person parser is not importable: {type(e).__name__}")
        return None
    url = f"https://myanimelist.net/people/{int(pid)}"
    try:
        req = urllib.request.Request(url, headers=UA)
        page = urllib.request.urlopen(
            req, timeout=float(cfg["fetch_timeout_seconds"])).read().decode("utf-8", "replace")
    except Exception as e:
        log(f"[dossier] the page for person {pid} was not read: {type(e).__name__}")
        return None
    try:
        d = parse_person(page)
    except Exception as e:
        log(f"[dossier] the page for person {pid} did not parse: {type(e).__name__}")
        return None
    if not d.get("roles"):
        # An empty parse is a failed fetch, not an actor with no roles: nothing
        # is stored, so the next build tries again rather than caching a hole
        # for the whole time-to-live.
        log(f"[dossier] the page for person {pid} parsed to no roles; nothing cached")
        return None
    row = {"name": d.get("name", ""), "name_jp": d.get("name_jp", ""),
           "birthday": d.get("birthday", ""), "favorites": d.get("favorites", ""),
           "bio": d.get("bio", ""),
           "roles": [{"aid": r[0], "anime": r[1], "character": r[2], "role": r[3],
                      "char_favs": r[4], "year": r[5]} for r in d.get("roles") or []]}
    store.put_person(int(pid), row)
    log(f"[dossier] person {pid} ({row['name']}): {len(row['roles'])} credit(s) cached")
    return row


def fetch_anime_extra(aid, store, cfg, log):
    """A work's premiere date, studio and episode count from the list site's
    own interface, into this module's own store. What it is for: an entry he
    has marked plan-to-watch has no dates on his list at all, so a sequel
    everybody is waiting for reads as a blank in the franchise table."""
    cid = str(cfg.get("mal_client_id") or "")
    if not cid:
        log("[dossier] no list-site client id on disk; the premiere date stays blank")
        return None
    fields = "id,title,start_date,start_season,studios,num_episodes,media_type,status"
    url = f"https://api.myanimelist.net/v2/anime/{int(aid)}?fields={fields}"
    try:
        req = urllib.request.Request(url, headers={"X-MAL-CLIENT-ID": cid, **UA})
        d = json.loads(urllib.request.urlopen(
            req, timeout=float(cfg["fetch_timeout_seconds"])).read())
    except Exception as e:
        log(f"[dossier] the facts for {aid} were not read: {type(e).__name__}")
        return None
    ss = d.get("start_season") or {}
    row = {"start_date": d.get("start_date") or "",
           "season": f"{ss.get('season', '')} {ss.get('year', '')}".strip(),
           "studios": [s.get("name") for s in d.get("studios") or [] if s.get("name")],
           "num_episodes": d.get("num_episodes") or 0,
           "media_type": d.get("media_type") or "", "air_status": d.get("status") or ""}
    store.put_extra(int(aid), row)
    log(f"[dossier] {aid}: premiere {row['start_date'] or row['season'] or 'still unannounced'}")
    return row


# ---------------- what the retrieval store holds about the episode ----------------

def episode_material(aid, ep, media_type, cfg):
    """The episode index in three scripts, the page a judge chose, the digest
    made from it, the ordered scenes, how far the row was trusted and which
    sources agreed. All of it out of the machine's retrieval store
    (`machine/retrievals.py`), read-only: a dossier never fetches a page and
    never spends a model call."""
    out = {"titles": {}, "text": "", "source": "", "digest": "", "digest_model": "",
           "scenes": [], "confidence": "", "candidates": [], "reason": "", "anchor": "",
           "fetched_at": 0, "by": ""}
    con = _ro(cfg["retrievals_db"])
    if con is None:
        return out
    try:
        r = con.execute("SELECT text FROM retrievals WHERE kind='recap' AND key=?",
                        (f"eptitles|mal:{int(aid)}|ep0",)).fetchone()
        if r:
            try:
                idx = json.loads(r[0] or "{}")
                out["titles"] = idx.get(str(int(ep))) or {}
            except (ValueError, TypeError):
                pass
        # The row is filed under the WORK and its EDITION, because two entries
        # on his list share a Japanese title; the plain-title form is the older
        # key and is read only when the id-aware one is not there.
        keys = [f"anime|mal:{int(aid)}|{str(media_type or 'any').lower()}|ep{int(ep)}",
                f"anime|mal:{int(aid)}|any|ep{int(ep)}"]
        row = None
        for k in keys:
            row = con.execute(
                "SELECT text, source, meta, fetched_at, judged, by FROM retrievals "
                "WHERE kind='recap' AND key=?", (k,)).fetchone()
            if row:
                break
        if row:
            out["text"] = row[0] or ""
            out["source"] = row[1] or ""
            out["fetched_at"] = float(row[3] or 0)
            out["by"] = row[5] or ""
            try:
                meta = json.loads(row[2] or "{}")
            except (ValueError, TypeError):
                meta = {}
            out["scenes"] = meta.get("scenes") or []
            out["confidence"] = meta.get("confidence") or ("judged" if row[4] else "provisional")
            out["candidates"] = meta.get("candidates") or []
            out["reason"] = meta.get("reason") or ""
            out["anchor"] = meta.get("anchor") or ""
            name = meta.get("ja") or meta.get("title") or ""
            # The digest is filed under the PAGE it was made from, so it is
            # found by hashing the text above the same way the maker did.
            if name and out["text"]:
                key = "%s|ep%s|%s" % (name, int(ep), hashlib.sha1(
                    out["text"][:8000].encode("utf-8", "replace")).hexdigest()[:16])
                d = con.execute("SELECT text, model FROM retrievals WHERE kind='page_digest' "
                                "AND key=?", (key,)).fetchone()
                if d:
                    out["digest"] = d[0] or ""
                    out["digest_model"] = d[1] or ""
    except sqlite3.Error:
        pass
    finally:
        con.close()
    return out


# ---------------- the join ----------------

class Builder:
    def __init__(self, cfg=None, log=print):
        self.cfg = cfg or settings()
        self.log = log
        self.store = Store(self.cfg["db_path"])
        self.mirror = _ro(self.cfg["mirror_db"])
        self.fetched_people = 0
        self.fetched_extras = 0
        self._kb = None

    def close(self):
        self.store.close()
        if self.mirror is not None:
            try:
                self.mirror.close()
            except sqlite3.Error:
                pass

    def kb(self):
        """The title resolver the character-side watcher uses, so a filename
        resolves to the same work here as it does there. No client id, so it
        can reach nothing."""
        if self._kb is None:
            from sim.anime_kb import AnimeKB
            self._kb = AnimeKB(None, _abs(self.cfg["mirror_db"]), "")
        return self._kb

    # ---- resolving the file ----

    def resolve(self, path):
        """(anime_id, title, ep, how) for a played file, or (0, '', 0, why).

        The same two readings the character-side watcher makes and in the same
        order: a numbered episode of a television run, then a special named by
        its folder or its filename."""
        from sim.watching_him import parse_file, parse_special
        title, ep = parse_file(path)
        if title and ep:
            cands = self.kb().resolve_candidates(title, ep=ep, kind="tv")
            if cands:
                return (int(cands[0]["aid"]), cands[0]["title"], int(ep),
                        "the filename, ranked against your list")
            return 0, "", int(ep), f"{title!r} is on nothing in your list"
        sp = parse_special(path)
        if sp:
            hit = self.kb().resolve_special(sp[0])
            if hit:
                return int(hit[0]), hit[1], int(sp[2]), f"a {sp[1]} of {sp[0]}"
            return 0, "", int(sp[2]), f"no {sp[1]} of {sp[0]!r} is on your list"
        return 0, "", 0, "the filename does not read as an episode"

    # ---- his list ----

    def anime_row(self, aid):
        if self.mirror is None or not aid:
            return {}
        r = self.mirror.execute(
            "SELECT anime_id,title,title_eng,media_type,num_episodes,status,score,"
            "watched_episodes,studios,genres,start_date,finish_date,notes,updated_at "
            "FROM anime WHERE anime_id=?", (int(aid),)).fetchone()
        if not r:
            return {}
        keys = ("anime_id", "title", "title_eng", "media_type", "num_episodes", "status",
                "score", "watched", "studios", "genres", "start_date", "finish_date",
                "notes", "updated_at")
        d = dict(zip(keys, r))
        d["studios"] = _jl(d["studios"])
        d["genres"] = _jl(d["genres"])
        det = self.mirror.execute(
            "SELECT studios, season, season_year, mal_mean, source, avg_episode_seconds, "
            "api_num_episodes FROM anime_detail WHERE anime_id=?", (int(aid),)).fetchone()
        if det:
            d["studios"] = d["studios"] or _jl(det[0])
            d["season"] = " ".join(str(x) for x in (det[1], det[2]) if x)
            d["mal_mean"] = det[3]
            d["source"] = det[4]
            d["avg_seconds"] = det[5] or 0
        d.setdefault("season", "")
        d.setdefault("mal_mean", None)
        d.setdefault("source", "")
        d.setdefault("avg_seconds", 0)
        return d

    def completed(self, row):
        """Was the show already finished on your list before this play.

        NOT the list site's rewatching flag, which is only ever true when he
        has gone to the site and marked it so, and which this mirror does not
        carry a column for at all. What answers the question is the standing:
        marked completed, or every episode marked watched. A play of a
        thirteen-of-thirteen show read as a first watch until this was
        computed rather than read off the flag."""
        if not row:
            return False, "not on your list"
        status = int(row.get("status") or 0)
        watched, total = int(row.get("watched") or 0), int(row.get("num_episodes") or 0)
        if status == 2:
            return True, "marked completed"
        if total and watched >= total:
            return True, f"{watched} of {total} episodes marked"
        return False, f"{STATUS_WORD.get(status, 'listed')}, {watched} of {total or '?'} marked"

    def favourite_rank(self, kind, item_id):
        """Where this sits in your declared favourites on the list site, or 0.
        Your own hand, and the strongest signal on the whole mirror."""
        if self.mirror is None or not item_id:
            return 0
        try:
            r = self.mirror.execute("SELECT position FROM favorites WHERE kind=? AND item_id=?",
                                    (kind, int(item_id))).fetchone()
        except sqlite3.Error:
            return 0
        return int(r[0]) + 1 if r else 0

    def episode_watches(self, aid):
        if self.mirror is None or not aid:
            return []
        return [(int(r[0]), r[1] or "", r[2] or "") for r in self.mirror.execute(
            "SELECT ep, watched_at, source FROM episodes WHERE anime_id=? ORDER BY watched_at",
            (int(aid),))]

    def overall_mean(self):
        if self.mirror is None:
            return 0.0
        r = self.mirror.execute("SELECT AVG(score), COUNT(*) FROM anime WHERE score > 0").fetchone()
        return (float(r[0] or 0), int(r[1] or 0)) if r else (0.0, 0)

    # ---- the franchise ----

    def _norm(self, t):
        return re.sub(r"[^a-z0-9]", "", str(t or "").lower())

    def siblings(self, aid, title):
        """The other entries of the same franchise on your list.

        The mirror holds no relation rows, so the grouping is by title stem:
        the SHORTEST title on your list that the played title starts with is
        the franchise's own name, and everything starting with that name is in
        it. A sequel resolves to the same stem as the first season, which is
        what puts them in one table."""
        if self.mirror is None:
            return []
        rows = [(int(r[0]), r[1] or "") for r in self.mirror.execute("SELECT anime_id, title FROM anime")]
        me = self._norm(title)
        if len(me) < 4:
            return []
        prefixes = sorted((self._norm(t) for _a, t in rows
                           if self._norm(t) and me.startswith(self._norm(t))), key=len)
        stem = next((p for p in prefixes if len(p) >= 6), me)
        out = []
        for a, t in rows:
            n = self._norm(t)
            if not n or not n.startswith(stem):
                continue
            row = self.anime_row(a)
            extra = self.store.extra(a, self.cfg["fetch_ttl_days"]) or {}
            premiere = (row.get("season") or extra.get("season") or "").strip()
            if extra.get("start_date"):
                premiere = extra["start_date"]
            out.append({"aid": a, "title": t, "status": int(row.get("status") or 0),
                        "score": int(row.get("score") or 0),
                        "watched": int(row.get("watched") or 0),
                        "eps": int(row.get("num_episodes") or 0) or int(extra.get("num_episodes") or 0),
                        "studios": row.get("studios") or _jl(extra.get("studios")),
                        "premiere": premiere, "mine": a == aid})
        out.sort(key=lambda r: _premiere_order(r["premiere"]) + (r["aid"],))
        return out

    def fill_premieres(self, sibs):
        """Look up the works in the franchise your list has no date for, newest
        first and capped. What this is for: a sequel you have marked
        plan-to-watch carries no dates on a list at all."""
        cap = int(self.cfg["premiere_fetch_cap"] or 0)
        added = []
        for s in sorted(sibs, key=lambda r: -r["aid"]):
            if self.fetched_extras >= cap:
                break
            if s["premiere"]:
                continue
            if self.store.extra(s["aid"], self.cfg["fetch_ttl_days"]) is not None:
                continue
            if self.fetched_extras:
                time.sleep(float(self.cfg["fetch_delay_seconds"]))
            got = fetch_anime_extra(s["aid"], self.store, self.cfg, self.log)
            self.fetched_extras += 1
            if got:
                s["premiere"] = got.get("start_date") or got.get("season") or ""
                s["studios"] = s["studios"] or got.get("studios") or []
                s["eps"] = s["eps"] or int(got.get("num_episodes") or 0)
                s["air_status"] = got.get("air_status") or ""
                added.append(s)
        return added

    # ---- the cast ----

    def cast(self, aid):
        """One row per credited actor: what they play here, where they sit in
        your declared favourites, every other show of theirs on your list with
        your score, and the mean of those scores against your overall."""
        if self.mirror is None or not aid:
            return []
        rows = [dict(zip(("char_id", "character", "role", "va", "pid"), r))
                for r in self.mirror.execute(
                    "SELECT char_id, character, role, jp_va, jp_va_id FROM anime_cast "
                    "WHERE anime_id=? ORDER BY CASE role WHEN 'Main' THEN 0 ELSE 1 END, char_id",
                    (int(aid),))]
        by_person = {}
        for r in rows:
            pid = int(r["pid"] or 0)
            if not pid:
                continue
            p = by_person.setdefault(pid, {"pid": pid, "name": r["va"] or "", "parts": []})
            p["parts"].append((r["character"] or "", r["role"] or ""))
        overall, scored_n = self.overall_mean()
        out = []
        for pid, p in by_person.items():
            p["main"] = any(role == "Main" for _c, role in p["parts"])
            p["favourite"] = self.favourite_rank("people", pid)
            others = []
            for a, t, ch, role, st, sc in self.mirror.execute(
                    "SELECT DISTINCT c.anime_id, a.title, c.character, c.role, a.status, a.score "
                    "FROM anime_cast c JOIN anime a ON a.anime_id = c.anime_id "
                    "WHERE c.jp_va_id=? AND c.anime_id<>?", (pid, int(aid))):
                others.append({"aid": int(a), "title": t or "", "character": ch or "",
                               "role": role or "", "status": int(st or 0), "score": int(sc or 0)})
            others.sort(key=lambda r: (-r["score"], r["title"]))
            p["yours"] = others
            scores = [o["score"] for o in others if o["score"] > 0]
            p["mean"] = round(sum(scores) / len(scores), 2) if scores else 0.0
            p["scored"] = len(scores)
            p["overall"] = round(overall, 2)
            p["overall_n"] = scored_n
            p["mirrored"] = self.person_credits(pid)
            out.append(p)
        out.sort(key=lambda p: (0 if p["main"] else 1, -len(p["yours"])))
        return out

    def person_credits(self, pid):
        """The actor's whole filmography where somebody has mirrored it:
        (where it came from, [credits]). ('', []) is "nobody has looked",
        which is a different answer from "she has done nothing else" and the
        page says so."""
        cached = self.store.person(pid, self.cfg["fetch_ttl_days"])
        if cached and cached.get("roles"):
            return "read from the list site for this dossier", cached
        if self.mirror is not None:
            rows = [{"aid": int(r[0]), "anime": r[1] or "", "character": r[2] or "",
                     "role": r[3] or "", "char_favs": int(r[4] or 0), "year": int(r[5] or 0)}
                    for r in self.mirror.execute(
                        "SELECT anime_id, anime, character, role, char_favs, year "
                        "FROM person_role WHERE person_id=?", (int(pid),))]
            if rows:
                p = self.mirror.execute(
                    "SELECT name, name_jp, birthday, favorites, bio FROM person WHERE person_id=?",
                    (int(pid),)).fetchone()
                return "already on the list mirror", {
                    "name": (p[0] if p else "") or "", "name_jp": (p[1] if p else "") or "",
                    "birthday": (p[2] if p else "") or "", "favorites": (p[3] if p else "") or "",
                    "bio": (p[4] if p else "") or "", "roles": rows}
        return "", {}

    def fill_actors(self, cast):
        """Read the pages of the leads whose filmography nobody has mirrored,
        capped and spaced out. Main roles first, because those are the actors a
        question about the episode is going to be about."""
        cap = int(self.cfg["actor_fetch_cap"] or 0)
        want = [p for p in cast if not p["mirrored"][0]]
        want.sort(key=lambda p: (0 if p["main"] else 1, -len(p["yours"])))
        for p in want:
            if self.fetched_people >= cap:
                break
            if self.fetched_people:
                time.sleep(float(self.cfg["fetch_delay_seconds"]))
            got = fetch_person(p["pid"], self.store, self.cfg, self.log)
            self.fetched_people += 1
            if got:
                p["mirrored"] = ("read from the list site for this dossier", got)
        return [p for p in want if p["mirrored"][0]]

    # ---- the hours around it ----

    def around(self, at, path):
        """What else the player was opened on either side of this play, and
        every earlier play of the same FOLDER, which is what says whether a run
        is under way and whether this file has been through before."""
        c = self.cfg
        lo = float(at) - float(c["hours_before"]) * 3600
        hi = float(at) + float(c["hours_after"]) * 3600
        hist = opens(c["player_history"])
        near = [(ts, p) for ts, p in hist if lo <= ts <= hi and abs(ts - float(at)) > 1]
        folder = ntpath.dirname(str(path or ""))
        same_folder = [(ts, p) for ts, p in hist
                       if folder and ntpath.dirname(p) == folder and abs(ts - float(at)) > 1]
        same_file = [ts for ts, p in hist if p == path and abs(ts - float(at)) > 1]
        return near, same_folder, same_file

    # ---- writing it out ----

    def build(self, open_epoch, force=False):
        """One play, joined and written. Returns the path written, or ''.

        A play under the floor is not a play: it is marked as a skim so the
        rolling file can say it happened and no dossier is written for it."""
        c = self.cfg
        at = float(open_epoch)
        if not force and self.store.is_built(at):
            return ""
        play = play_for(at, c)
        path = play.get("path") or ""
        if not path:
            self.log(f"[dossier] no file opened at {_stamp(at)}")
            return ""
        if play.get("running"):
            self.log(f"[dossier] {ntpath.basename(path)} has no recorded end and nothing was "
                     f"opened after it; left for the next pass")
            return ""
        aid, title, ep, how = self.resolve(path)
        watched = float(play.get("watched") or 0)
        floor = float(c["min_watched_minutes"]) * 60
        if watched < floor:
            self.store.mark(at, path=path, anime_id=aid, ep=ep, title=title, watched=watched,
                            kind="skim", file=ntpath.basename(path),
                            note=f"{_hms(watched)} in it, under the {c['min_watched_minutes']:g}-minute floor")
            self.log(f"[dossier] {ntpath.basename(path)} was watched {_hms(watched)}; "
                     f"a skim, not a play -- no dossier")
            self.write_rolling()
            return ""
        if not aid:
            # The same folder holds music, radio recordings, camera clips and
            # files called `input.webm`. A file that is on nothing in his list
            # has no episode, no cast and no history to join, so it is listed
            # and no dossier is written for it.
            self.store.mark(at, path=path, anime_id=0, ep=ep, title="", watched=watched,
                            kind="other", file=ntpath.basename(path), note=how)
            self.log(f"[dossier] {ntpath.basename(path)}: {how}; no dossier")
            self.write_rolling()
            return ""
        # the caps on the two page reads are per PLAY, not per sweep
        self.fetched_people = self.fetched_extras = 0
        text, name = self.render(at, play, path, aid, title, ep, how)
        out_dir = _abs(c["dir"])
        os.makedirs(out_dir, exist_ok=True)
        dest = os.path.join(out_dir, name)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.store.mark(at, path=path, anime_id=aid, ep=ep, title=title, watched=watched,
                        kind="dossier", file=name, note=play.get("source", ""))
        self.log(f"[dossier] {name}")
        self.write_rolling()
        return dest

    def render(self, at, play, path, aid, title, ep, how):
        c = self.cfg
        row = self.anime_row(aid)
        done, standing = self.completed(row)
        mat = episode_material(aid, ep, row.get("media_type") or "", c) if aid else {}
        near, same_folder, same_file = self.around(at, path)
        sibs = self.siblings(aid, row.get("title") or title) if aid else []
        new_dates = self.fill_premieres(sibs) if sibs else []
        cast = self.cast(aid) if aid else []
        read_now = self.fill_actors(cast) if cast else []
        watches = self.episode_watches(aid) if aid else []
        fav_anime = self.favourite_rank("anime", aid)

        L = []
        head = row.get("title") or title or ntpath.basename(path)
        L.append(f"# {head} — episode {ep}" if ep else f"# {head}")
        L.append("")
        L.append(f"Played {_stamp(at, '%A %d %B %Y, %H:%M')}. Everything below was already on "
                 f"disk; this file is the join. Built {_stamp(time.time())}.")
        L.append("")

        # ---- the play ----
        L.append("## The play")
        L.append("")
        L.append(f"- **File** `{path}`")
        L.append(f"- **Opened** {_stamp(at)}  ·  **ended** {_stamp(play.get('end'))}")
        length = float(play.get("length") or 0)
        pos = float(play.get("end_pos") or 0)
        watched = float(play.get("watched") or 0)
        line = f"- **Watched** {_hms(watched)}"
        if length:
            line += f" of {_hms(length)}, ending at {_hms(pos)} ({100.0 * pos / length:.0f}% in)"
        line += f"  ·  _{play.get('source')}_"
        L.append(line)
        if play.get("reason"):
            L.append(f"- **Ended because** {play['reason']}")
        L.append(f"- **Resolved to** {row.get('title') or title or 'nothing on your list'}"
                 + (f" (mal:{aid})" if aid else "") + f" — {how}")
        L.append(f"- **Already finished on your list:** "
                 f"{'yes' if done else 'no'} — {standing}")
        L.append("- **The list site's own rewatching flag:** not on this mirror. It is only "
                 "ever true while you have gone to the site and marked the entry as being "
                 "rewatched, so it answers a question about what you clicked rather than "
                 "about what you have seen; the standing above is the answer to that one.")
        if same_file:
            L.append(f"- **This exact file has been opened {len(same_file)} time(s) before**, "
                     f"last {_stamp(max(same_file))}")
        L.append("")
        if near:
            L.append(f"**Around it** — what the player opened in the "
                     f"{c['hours_before']:g} hours before and {c['hours_after']:g} after:")
            L.append("")
            for ts, p in near:
                gap = (ts - at) / 3600.0
                when = f"{abs(gap):.1f} h {'after' if gap > 0 else 'before'}"
                L.append(f"- `{_stamp(ts, '%H:%M')}` ({when}) {self.describe(p)}")
            L.append("")
        else:
            L.append(f"Nothing else was opened in the {c['hours_before']:g} hours before or "
                     f"{c['hours_after']:g} after.")
            L.append("")
        if same_folder:
            L.append(f"**The same folder** — {len(same_folder)} other play(s) of "
                     f"`{ntpath.basename(ntpath.dirname(path))}`:")
            L.append("")
            for ts, p in same_folder[-12:]:
                L.append(f"- `{_stamp(ts)}` {ntpath.basename(p)}")
            L.append("")

        # ---- the episode ----
        L.append("## The episode")
        L.append("")
        t3 = mat.get("titles") or {}
        if t3:
            L.append(f"- **English** {t3.get('en') or '—'}")
            L.append(f"- **Romaji** {t3.get('romaji') or '—'}")
            L.append(f"- **Japanese** {t3.get('ja') or '—'}")
            for k, word in (("en", "English"), ("romaji", "romaji"), ("ja", "Japanese")):
                if not t3.get(k):
                    L.append(f"- The {word} title is not in the cached episode index.")
        else:
            L.append("The cached episode index holds no titles for this work; nothing has read "
                     "its episode list.")
        L.append("")
        if mat.get("digest"):
            L.append("**The digest** (what the page was condensed to, in Japanese"
                     + (f", by `{mat['digest_model']}`" if mat.get("digest_model") else "") + "):")
            L.append("")
            L.append("> " + mat["digest"].replace("\n", " "))
            L.append("")
        elif mat.get("text"):
            L.append("No digest is stored for this episode; the page it would have been made "
                     "from is below.")
            L.append("")
        if mat.get("scenes"):
            L.append("**The scenes, in order:**")
            L.append("")
            for i, s in enumerate(mat["scenes"], 1):
                L.append(f"{i}. {s}")
            L.append("")
        if mat.get("confidence"):
            L.append(f"- **Confidence** {mat['confidence']}"
                     + (f" — {mat['reason']}" if mat.get("reason") else ""))
        if mat.get("candidates"):
            agreed = [x for x in mat["candidates"] if str(x.get("verdict")) == "agreed"]
            L.append(f"- **Sources** {len(mat['candidates'])} read, {len(agreed)} agreed with "
                     f"the one chosen:")
            for x in mat["candidates"]:
                L.append(f"    - {x.get('verdict', '?')}: {x.get('source', '?')} — "
                         f"{x.get('url', '')}")
        if mat.get("anchor"):
            L.append(f"- **Measured against** {mat['anchor']}")
        if mat.get("text"):
            L.append(f"- **The page itself** ({mat.get('source')}, read "
                     f"{_stamp(mat.get('fetched_at'))}"
                     + (f", by {mat['by']}" if mat.get("by") else "") + "):")
            L.append("")
            L.append("> " + " ".join(mat["text"].split())[:1200])
        if not mat.get("text") and not mat.get("titles"):
            L.append("Nothing about this episode is in the machine's retrieval store.")
        L.append("")

        # ---- the show ----
        L.append("## Your history with the show")
        L.append("")
        if row:
            bits = [STATUS_WORD.get(int(row.get("status") or 0), "listed"),
                    f"{row.get('watched') or 0} of {row.get('num_episodes') or '?'} episodes"]
            if row.get("score"):
                bits.append(f"your score {row['score']}/10")
            if fav_anime:
                bits.append(f"**number {fav_anime} in your declared favourite anime**")
            L.append("- " + "  ·  ".join(bits))
            facts = []
            if row.get("season"):
                facts.append(row["season"])
            if row.get("studios"):
                facts.append("studio " + ", ".join(row["studios"]))
            if row.get("source"):
                facts.append(f"from {row['source']}")
            if row.get("mal_mean"):
                facts.append(f"site mean {row['mal_mean']}")
            if facts:
                L.append("- " + "  ·  ".join(facts))
            if row.get("notes"):
                L.append(f"- Your note: {row['notes'][:200]}")
        else:
            L.append("- This work is not on your list.")
        L.append("")
        if watches:
            L.append(f"**Dated episode watches on your list** ({len(watches)}):")
            L.append("")
            for e, when, src in watches:
                L.append(f"- episode {e} — {when} ({src})")
        else:
            L.append("**Dated episode watches on your list:** none. The list carries the "
                     "count but no per-episode dates for this work.")
        L.append("")
        if sibs:
            L.append("**The franchise on your list** — grouped by title stem, because the "
                     "mirror holds no relation rows:")
            L.append("")
            L.append("| entry | status | your score | episodes | studio | premiere |")
            L.append("|---|---|---|---|---|---|")
            for s in sibs:
                mark = " ←" if s["mine"] else ""
                L.append("| %s%s | %s | %s | %s | %s | %s |" % (
                    s["title"], mark, STATUS_WORD.get(s["status"], "listed"),
                    s["score"] or "—", s["eps"] or "—",
                    ", ".join(s["studios"]) or "—", s["premiere"] or "—"))
            L.append("")
            if new_dates:
                L.append("Premiere dates read from the list site for this dossier: "
                         + "; ".join(f"{s['title']} — {s['premiere'] or 'still unannounced'}"
                                     for s in new_dates))
                L.append("")
        L.append("")

        # ---- the cast ----
        L.append("## The cast")
        L.append("")
        if not cast:
            L.append("Nobody has mirrored the cast of this work.")
        else:
            mean_all, n_all = self.overall_mean()
            L.append(f"Your overall mean is **{mean_all:.2f}** over {n_all} scored entries. "
                     f"The mean beside each actor is over the shows of theirs you have scored.")
            L.append("")
            L.append("| actor | plays here | favourite | your shows | your mean | vs overall |")
            L.append("|---|---|---|---|---|---|")
            for p in cast:
                parts = "; ".join(f"{ch} ({role.lower()})" for ch, role in p["parts"])
                fav = f"#{p['favourite']}" if p["favourite"] else "—"
                delta = (p["mean"] - mean_all) if p["scored"] else 0.0
                L.append("| %s | %s | %s | %d | %s | %s |" % (
                    p["name"] or f"person {p['pid']}", parts, fav, len(p["yours"]),
                    f"{p['mean']:.2f} over {p['scored']}" if p["scored"] else "—",
                    f"{delta:+.2f}" if p["scored"] else "—"))
            L.append("")
            detail = cast[:int(c["cast_detail_cap"])]
            if len(cast) > len(detail):
                L.append(f"Below: the {len(detail)} of them with the largest part in this "
                         f"episode or the most of your list behind them. The other "
                         f"{len(cast) - len(detail)} are in the table above and nowhere else.")
                L.append("")
            for p in detail:
                L.append("### " + (p["name"] or ("person %d" % p["pid"])))
                L.append("")
                bits = ["plays " + "; ".join(f"{ch} ({role.lower()})" for ch, role in p["parts"])]
                if p["favourite"]:
                    bits.append(f"**number {p['favourite']} in your declared favourite people**")
                L.append("- " + "  ·  ".join(bits))
                where, who = p["mirrored"]
                if who.get("birthday") or who.get("favorites"):
                    L.append("- " + "  ·  ".join(
                        x for x in (f"born {who.get('birthday')}" if who.get("birthday") else "",
                                    f"{who.get('favorites')} site favourites"
                                    if who.get("favorites") else "") if x))
                if who.get("bio"):
                    L.append(f"- {' '.join(str(who['bio']).split())[:300]}")
                if p["yours"]:
                    shown = p["yours"][:int(c["actor_list_cap"])]
                    L.append(f"- **Also on your list ({len(p['yours'])}"
                             + (f", best {len(shown)} shown" if len(shown) < len(p["yours"]) else "")
                             + "):**")
                    for o in shown:
                        L.append("    - %s — %s (%s%s)" % (
                            o["title"], o["character"],
                            STATUS_WORD.get(o["status"], "listed"),
                            f", you gave {o['score']}" if o["score"] else ", unscored"))
                else:
                    L.append("- Nothing else of theirs is on your list.")
                if where:
                    roles = who.get("roles") or []
                    yours = {o["aid"] for o in p["yours"]} | {aid}
                    rest = sorted((r for r in roles if int(r.get("aid") or 0) not in yours),
                                  key=lambda r: -int(r.get("char_favs") or 0))
                    L.append(f"- **Whole filmography:** {len(roles)} credit(s), {where}. "
                             f"{len(rest)} of them are works you do not have listed"
                             + (":" if rest else "."))
                    for r in rest[:8]:
                        L.append("    - %s — %s (%s%s)" % (
                            r.get("anime", ""), r.get("character", ""), r.get("role", "?"),
                            f", {r['year']}" if r.get("year") else ""))
                else:
                    L.append("- **Whole filmography:** nobody has mirrored one. What is above "
                             "is your own list and nothing beyond it.")
                L.append("")

        # ---- what is missing ----
        L.append("## What is missing on disk")
        L.append("")
        gaps = []
        no_film = [p for p in cast if not p["mirrored"][0]]
        if no_film:
            gaps.append("%d of the %d credited actors have no bio and no filmography on the "
                        "mirror (%s%s). For those, \"what else has she done\" is your own list "
                        "and nothing more." % (
                            len(no_film), len(cast),
                            ", ".join(p["name"] or str(p["pid"]) for p in no_film[:6]),
                            ", …" if len(no_film) > 6 else ""))
        if read_now:
            gaps.append("Read for this dossier: "
                        + "; ".join(f"{p['name']} ({len(p['mirrored'][1].get('roles') or [])} credits)"
                                    for p in read_now) + ".")
        blank = [s for s in sibs if not s["premiere"]]
        if blank:
            gaps.append("No premiere date on disk for: "
                        + ", ".join(f"{s['title']} ({STATUS_WORD.get(s['status'], 'listed')})"
                                    for s in blank)
                        + ". A plan-to-watch entry carries no dates on a list at all; one "
                          "call to the list site fills it.")
        if not watches:
            gaps.append("The list has no dated episode watches for this work, so when you "
                        "watched it the first time is not answerable from here.")
        if not mat.get("text"):
            gaps.append("No page for this episode is in the retrieval store, so there is no "
                        "digest and no scene list.")
        if not gaps:
            gaps.append("Nothing. Everything this file joins was on disk.")
        for g in gaps:
            L.append(f"- {g}")
        L.append("")

        name = "%s_%s.md" % (_stamp(at, "%Y-%m-%d_%H%M"),
                             _slug(f"{row.get('title') or title or ntpath.basename(path)}"
                                   + (f"-ep{ep}" if ep else "")))
        return "\n".join(L) + "\n", name

    def describe(self, path):
        """One played file in a line: the work it resolves to, or the filename
        when it resolves to nothing -- the same folder holds music, recordings
        and files called `input.webm`."""
        try:
            aid, title, ep, _how = self.resolve(path)
        except Exception:
            aid, title, ep = 0, "", 0
        if aid and ep:
            return f"{title} episode {ep}"
        if aid:
            return title
        return ntpath.basename(path)

    # ---- the rolling file ----

    def write_rolling(self):
        """The last N plays in one file, rebuilt whole every time so it never
        drifts from the store it is written out of. A skim is a line here and
        has no dossier of its own."""
        c = self.cfg
        rows = self.store.recent(int(c["last_n"]))
        out_dir = _abs(c["dir"])
        os.makedirs(out_dir, exist_ok=True)
        L = [f"# The last {int(c['last_n'])} plays", "",
             f"Rebuilt {_stamp(time.time())} from `{c['db_path']}`. A play under "
             f"{c['min_watched_minutes']:g} minutes watched is a _skim_ and a file that is on "
             f"nothing in your list is _other_: both are listed and neither has a dossier.", "",
             "| played | what | watched | dossier |", "|---|---|---|---|"]
        for r in rows:
            what = r.get("title") or ntpath.basename(r.get("path") or "") or "?"
            if r.get("ep"):
                what += f" episode {r['ep']}"
            link = (f"[{r.get('file')}]({r.get('file')})" if r.get("kind") == "dossier"
                    else f"_{r.get('kind') or 'none'}_")
            L.append("| %s | %s | %s | %s |" % (
                _stamp(r.get("open_epoch")), what, _hms(r.get("watched")), link))
        if not rows:
            L.append("| — | nothing built yet | — | — |")
        L.append("")
        dest = os.path.join(out_dir, "last-ten.md")
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write("\n".join(L) + "\n")
        return dest


# ---------------- the door the daemon comes in by ----------------

def sweep(cfg=None, log=print, limit=200):
    """Every finished play the store has no row for, oldest first and a few
    per call.

    This is what the mirror daemon calls once a cycle. A play still open is
    left alone: how far he got is only known when it ends, and the floor that
    separates a play from a skim is measured on that number.

    A few per call because the first ever call meets a backlog of everything
    the player has ever opened, and each play may read up to three actors'
    pages. The daemon comes back every five minutes, so an evening's plays are
    caught up within the hour and nothing is read in a burst.

    Returns the paths written."""
    cfg = cfg or settings()
    if not cfg.get("enabled", True):
        return []
    b = Builder(cfg, log)
    written = []
    try:
        finished = plays(cfg["player_plays"])
        if finished:
            candidates = [float(r.get("opened") or 0) for r in finished]
        else:
            # No end-of-play record on this machine yet: a file counts as
            # finished once a later one has been opened, which is the same
            # rule the character-side watcher falls back on.
            hist = opens(cfg["player_history"])
            candidates = [ts for ts, _p in hist[:-1]]
        floor = b.store.horizon(candidates, cfg["last_n"])
        todo = [ts for ts in sorted(candidates)[-int(limit):]
                if ts >= floor and not b.store.is_built(ts)]
        for ts in todo[: int(cfg.get("per_cycle_cap", 3) or 3)]:
            try:
                got = b.build(ts)
            except Exception as e:
                log(f"[dossier] the play at {_stamp(ts)} was not built: {type(e).__name__}: {e}")
                continue
            if got:
                written.append(got)
    finally:
        b.close()
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--last", nargs="?", const=1, type=int,
                    help="build the newest N finished plays (default 1)")
    ap.add_argument("--epoch", type=float, help="build the play that opened at this unix time")
    ap.add_argument("--path", help="build the newest play of this file")
    ap.add_argument("--sweep", action="store_true", help="every finished play not built yet")
    ap.add_argument("--list", action="store_true", help="what has been built")
    ap.add_argument("--force", action="store_true", help="rebuild one that is already there")
    ap.add_argument("--no-fetch", action="store_true",
                    help="read nothing over the network; leave the two gaps as gaps")
    args = ap.parse_args(argv)

    cfg = settings()
    if args.no_fetch:
        cfg["actor_fetch_cap"], cfg["premiere_fetch_cap"] = 0, 0
    b = Builder(cfg, print)
    try:
        if args.list:
            for r in b.store.recent(int(cfg["last_n"])):
                print("%s  %-34s %-8s %s" % (_stamp(r["open_epoch"]),
                                             (r["title"] or ntpath.basename(r["path"] or ""))[:34],
                                             _hms(r["watched"]), r["file"] or r["kind"]))
            return 0
        if args.sweep:
            b.close()
            for p in sweep(cfg, print):
                print(p)
            return 0
        wanted = []
        if args.epoch:
            wanted = [float(args.epoch)]
        elif args.path:
            hits = [ts for ts, p in opens(cfg["player_history"]) if p == args.path]
            wanted = hits[-1:]
            if not wanted:
                print(f"the player has never opened {args.path}")
                return 1
        else:
            n = int(args.last or 1)
            finished = plays(cfg["player_plays"])
            if finished:
                wanted = [float(r["open"]) for r in finished][-n:]
            else:
                hist = opens(cfg["player_history"])
                wanted = [ts for ts, _p in hist[:-1]][-n:]
        for ts in wanted:
            got = b.build(ts, force=args.force)
            print(got or "(no dossier)")
    finally:
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
