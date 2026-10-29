"""What he is watching, found out about and read up on while he watches it.

Her anime knowledge already had every piece except the one that joins them.
His list is mirrored locally (700 shows, 3,161 episodes, cast with Japanese
voice actors for 479 of them), a real Japanese あらすじ can be fetched for any
(show, episode) and cached, and she has a record of her own career. Nothing
connected the three: he could watch an episode and she would learn only that a
count on a website went up, because the synopsis fetcher was reachable *only*
from him naming the show in chat.

So this module is the join, and it does four things in order:

  * notices a new episode two ways -- the player's own history, which is the
    moment he starts, and the list, which is minutes later but carries the
    show's id rather than a filename to guess from;
  * fetches the Japanese あらすじ for that episode, off the main thread because
    it opens a browser, cached so a rewatch costs nothing;
  * asks whether SHE IS IN IT, which for this character is not a rare case:
    72 of the shows on his list have her in the cast, and one of the thirteen
    he is part-way through has her in the lead;
  * and when she is, opens the part of her own record that was held back.

**When the result reaches her is the program's, not this module's.** The
notice, the fetch, the digest, the thing known by name and the record it may
open all happen the moment he plays an episode, for every character. What she
is HOLDING is gated on `note_seen()`: a character who is on his machine is
told as it lands and the moment is dated to his play, and a character who
learns what he is doing in snapshots she has to go and fetch is told when she
next fetches one. `current()`, `situation_lines()` and `impulse_bonus()`
answer only for an episode that has reached her, and the freshness and settle
windows are counted from that moment rather than from his play.

That last one is the point of the whole thing and it needs saying plainly.
Her record is pinned to early 2003 and 178 claims about her later career are
withheld, because a character who volunteers what she will do in 2011 is not a
character. **Him watching it is what releases it**, and only the part he
touched: Higurashi opens Furude Rika and nothing else, Nanoha opens Nanoha and
the note about what it did to her career, and the concerts, the singles and
the roles in shows he has never opened stay shut. Her future arrives through
him, one work at a time, rather than by a date on a calendar.

The match is deliberately strict -- a record's words must all appear in the
show and character, or share a long word with the show's own title -- because
the two failure directions are not equal. A record that fails to open is a
thing she does not bring up. A record that opens wrongly is her claiming a
part she never played: on a looser rule, him watching Kashimashi (Kurusu
Tomari, played by someone else) opened her Kurusu Kanako record from a
different show four years later. `Rino Randou` is a known miss in the other
direction, romanised two ways; misses are logged.

spec: PROJECT.md §12.12
"""

import json
from sim import lang
from sim import sight
from sim import wiring
import ntpath
import os
import re
import sqlite3
import threading
import time

import logger
from machine import plays
from sim import resolver as _resolver
from sim import works
from sim.anime_kb import open_ro
from world.clock import daypart as _daypart

# `[Group] Title 05 (BD, 720p) [CRC].mkv`, `Title - 02 (BD ...)[Group].mkv`,
# `Title - S01E26 - Episode Name.mkv` -- the three shapes his own library
# actually uses. Anything that does not reduce to a title on his list is
# dropped without a word: the same folder holds her radio recordings, music
# videos and files called `input.webm`.
_LEAD_GROUP = re.compile(r"^\[[^\]]{1,30}\]\s*")
_BRACKETS = re.compile(r"\([^)]*\)|\[[^\]]*\]")
# The SEASON is captured, not thrown away. His library uses the Plex /
# Sonarr convention where season 00 is the specials season, so
# `Example Show - S00E01 - OVA.mkv` used to answer "episode 1 of Example Show",
# which resolved to the 26-episode television run he had finished three days
# earlier -- and she told him the plot of a work he had not watched.
_SEASON_EP = re.compile(r"\bS(\d{1,2})E(\d{1,3})\b", re.I)
# the same fragment on its own, when the filename carries no `- OVA` word
# after it: then the season-zero number IS the special's number
_S0_EP = re.compile(r"\s*-?\s*S0{1,2}E(\d{1,3})\s*$", re.I)
# the trailing `END` / `FINAL` a release group puts on the last episode is
# part of the numbering, not part of the show's name
_TAIL_MARK = r"(?:v\d)?(?:\s+(?:END|FINAL|FIN|Fin|End))?"
_DASH_EP = re.compile(r"\s-\s*(\d{1,3})" + _TAIL_MARK + r"\s*$")
_TAIL_EP = re.compile(r"\s(\d{1,3})" + _TAIL_MARK + r"\s*$")
_VIDEO = (".mkv", ".mp4", ".avi", ".webm", ".m4v")
# `Title - OVA`, `Title - OAD 2`, `Title - SP1`, `Title - Special`: a special
# with no episode number, which `parse_file` rejects; `parse_special` reads it
_SPECIAL = re.compile(r"\s-\s*(OVA|OAD|ONA|SP|Special)s?\s*(\d{1,2})?\s*$", re.I)
# A FOLDER is a fact about the file and it was being thrown away: `parse_file`
# took `ntpath.basename` and never looked at `D:\Videos\Example Show\OVA\`,
# which says outright which edition the file belongs to. One of these
# segments marks the file as a special; `Season N` gives the season, and
# season zero is the specials season here as it is in the filename.
_DIR_SPECIAL = {"ova": "OVA", "ovas": "OVA", "oad": "OAD", "oads": "OAD",
                "ona": "ONA", "onas": "ONA", "sp": "SP", "sps": "SP",
                "special": "SP", "specials": "SP"}
_DIR_SEASON = re.compile(r"^(?:season\s*|s)(\d{1,2})$", re.I)


def path_marks(name):
    """What the FOLDERS a file sits in say about it: (special kind, season).

    Either may be None. The innermost segment wins, because a path runs from
    the general to the particular: `...\\Example Show\\OVA\\` is an OVA of Example Show whatever the drive is called. A season of 0 is the specials season
    and comes back as a special with no number."""
    kind, season = None, None
    for seg in re.split(r"[\\/]+", str(name or ""))[:-1]:
        s = " ".join(str(seg or "").split()).lower()
        if not s:
            continue
        if s in _DIR_SPECIAL:
            kind, season = _DIR_SPECIAL[s], 0
            continue
        m = _DIR_SEASON.match(s)
        if m:
            n = int(m.group(1))
            season = n
            kind = "SP" if n == 0 else None
    return kind, season

# Words too common to be evidence on their own when a record shares one with a
# show's title. Everything else needs five characters, which is what stops
# `Mine` and `debut` reaching for any title that happens to contain them.
_WEAK = {"the", "and", "season", "movie", "special", "girl", "girls", "story",
         "love", "life", "world", "first", "second", "third", "gaiden"}


def parse_file(name):
    """A player filename as (title, episode), or (None, None).

    Ordinary string work and no lookups, so it is safe to run over the whole
    history on every poll.

    **The whole path is read, not just the basename.** A file under an `OVA`
    or `Specials` folder, or one numbered in season zero, is a SPECIAL and
    this declines it -- `(None, None)` -- so `parse_special` and
    `AnimeKB.resolve_special` get their turn, which is the route that exists
    exactly for that case and never ran while this one answered."""
    base = ntpath.basename(str(name or ""))
    stem, ext = os.path.splitext(base)
    if ext.lower() not in _VIDEO:
        return None, None
    dir_kind, dir_season = path_marks(name)
    if dir_kind:
        return None, None
    # The release group goes first whatever shape follows. Stripping it only
    # on the branch that needed it left a third of his library unresolvable:
    # `[Judas] Kami nomi zo Shiru Sekai - S01E05` matched the season pattern
    # and kept `[Judas]` in the title, which is on nobody's list.
    s = _LEAD_GROUP.sub("", stem)
    m = _SEASON_EP.search(s)
    if m:
        if int(m.group(1)) == 0:
            # season zero is the specials season, not episode 1 of the show
            return None, None
        # `Title - S01E26 - The Future`: the name after the number is the
        # episode's, not the show's
        return _BRACKETS.sub(" ", s[:m.start()]).strip(" -_."), int(m.group(2))
    if dir_season == 0:
        return None, None
    s = _BRACKETS.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" -_.")
    for rx in (_DASH_EP, _TAIL_EP):
        m = rx.search(s)
        if m:
            return s[:m.start()].strip(" -_."), int(m.group(1))
    return None, None


def parse_special(name):
    """A player filename that names a special rather than a numbered episode,
    as (base title, kind, n) -- `Yuyushiki - OVA` is ('Yuyushiki', 'OVA', 1)
    -- or None. His list holds an OVA under its own title (`Yuyushiki:
    Komarasetari, Komarasaretari`), so the base title is a stem for
    `AnimeKB.resolve_special`, not the title itself. The file he opened on
    2026-09-04 15:39 parsed to nothing and the poll never saw it.

    Three ways a file says it is a special, in order: the `- OVA` word at the
    end of the name, a season-zero number (`- S00E01`), and the folder it
    sits in. The season-zero fragment is also STRIPPED off the base title,
    because `Example Show - S00E01` matches no special on his list and
    `Example Show` matches the one he watched."""
    base = ntpath.basename(str(name or ""))
    stem, ext = os.path.splitext(base)
    if ext.lower() not in _VIDEO:
        return None
    dir_kind, dir_season = path_marks(name)
    s = _BRACKETS.sub(" ", _LEAD_GROUP.sub("", stem))
    s = re.sub(r"\s+", " ", s).strip(" -_.")
    kind, n, title = "", 0, ""
    m = _SPECIAL.search(s)
    if m:
        kind, n, title = m.group(1).upper(), int(m.group(2) or 0), s[:m.start()].strip(" -_.")
    else:
        title = s
    # `Example Show - S00E01 - OVA` reduces to `Example Show`, and where no OVA word
    # follows it, the season-zero number is the special's own number
    m0 = _S0_EP.search(title)
    if m0:
        n = n or int(m0.group(1))
        kind = kind or dir_kind or "SP"
        title = title[: m0.start()].strip(" -_.")
    if not kind and dir_kind:
        # the folder is the only marker: an ordinary `Show - 02` inside an
        # `OVA` folder is the second OVA, not episode 2 of the series
        kind = dir_kind
        for rx in (_DASH_EP, _TAIL_EP):
            mm = rx.search(title)
            if mm:
                n = n or int(mm.group(1))
                title = title[: mm.start()].strip(" -_.")
                break
    if not kind or not title:
        return None
    return title, kind, int(n or 1)


def _tokens(s):
    return {t for t in re.split(r"[^a-z0-9]+", str(s or "").lower()) if t}


# His cast mirror stores a character as MAL writes it, `Furude, Rika`, and the
# role in English. Neither belongs in a sentence written to a character who
# works in Japanese.
_ROLE_JA = {"Main": "主演", "Supporting": "脇役"}


def _person_name(name):
    s = str(name or "").strip()
    if "," in s:
        family, _, given = s.partition(",")
        return f"{given.strip()} {family.strip()}".strip()
    return s


class WatchingHim:
    # `resolver` is asked which of several candidate works he opened, and only
    # from the worker thread below (`sim/resolver.py`). None for a character
    # whose config has the role off, and then code's ranking is the whole
    # answer.
    WIRES = ('llm', 'resolver')
    def __init__(self, config, store, clock, anime_kb=None, recap=None,
                 db_path="data/mal_history.db"):
        self.config = config
        self.store = store
        self.clock = clock
        self.anime_kb = anime_kb
        self.recap = recap
        self.db_path = db_path
        self.thread = None
        self.result = None      # the finished episode, consumed by the persona
        self.llm = None         # set by App; the digest role needs it
        self._backfill_paths()
        wiring.declare(self)

    # ---------------- the file he played, put back on the old rows ----------

    # bumped when the recovery itself changes; the marker in the save is what
    # makes the step idempotent, and re-running it is a no-op
    PATH_BACKFILL_VERSION = 1

    def _history_opens(self):
        """`[(epoch, path, episode)]` for every open the player's history
        holds, oldest first. The whole file rather than its tail: this is the
        one caller that is looking backwards."""
        c = self.config.watching
        path = os.path.expandvars(str(getattr(c, "player_history_path", "") or ""))
        if not path or not os.path.exists(path):
            return None
        out = []
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError as e:
            logger.log(f"[watching] the player history not read: {type(e).__name__}")
            return None
        for line in lines:
            stamp, sep, p = line.strip().partition("|")
            if not sep:
                continue
            try:
                ts = float(stamp)
            except ValueError:
                continue
            _t, ep = parse_file(p)
            if not ep:
                sp = parse_special(p)
                ep = sp[2] if sp else 0
            out.append((ts, p, int(ep or 0)))
        return out

    @staticmethod
    def _open_path(opens, at, ep):
        """The file open at this moment, or ''. The open's own epoch is what
        the record of the play was stamped with, so the exact match is the
        answer whenever the history still holds that line; inside a minute of
        it is the fallback, because a record written from his list carries a
        minute rather than a second.

        The filename must parse to the SAME episode number either way. He
        opens several files in a minute and the wrong one would be handed to
        the transcriber as this episode."""
        at = float(at or 0)
        # a stamp that is not a unix time is his list's minute converted, and
        # his list gives no file at all
        if at < 1_000_000_000:
            return ""
        ep = int(ep or 0)
        near = []
        for ts, p, e in opens:
            if ep and e and e != ep:
                continue
            if int(ts) == int(at):
                return p
            if abs(ts - at) <= 60:
                near.append((abs(ts - at), p))
        return min(near)[1] if near else ""

    def _backfill_paths(self):
        """Put the file he played back on the rows written before the row
        carried it, once per save.

        Her record of a play kept the work, the episode and the moment and
        threw the filename away, so the repair pass had nothing to hand the
        transcriber and everything already watched was locked out of ever
        being transcript-anchored. The player's own history still holds the
        open, and the open's epoch is the same number the row is stamped
        with, so the two join."""
        store = self.store
        try:
            mark = store.get("watching_path_backfill", {}) or {}
            if int(mark.get("version", 0) or 0) >= self.PATH_BACKFILL_VERSION:
                return 0
            rows = list(store.get("watching_recent", []) or [])
            last = store.get("watching_last", None) or {}
            held = store.get("watching_held", {}) or {}
            targets = [r for r in rows if isinstance(r, dict) and not r.get("path")]
            if isinstance(last, dict) and last.get("anime_id") and not last.get("path"):
                targets.append(last)
            targets += [v for v in held.values() if isinstance(v, dict) and not v.get("path")]
            if not targets:
                store.set("watching_path_backfill",
                          {"version": self.PATH_BACKFILL_VERSION, "filled": 0})
                return 0
            opens = self._history_opens()
            if opens is None:
                # no history file on this machine: nothing to recover from and
                # nothing to mark, so a later boot with one tries again
                return 0
            filled = 0
            for r in targets:
                p = self._open_path(opens, r.get("at"), r.get("ep"))
                if p:
                    r["path"] = p
                    filled += 1
            if filled:
                store.set("watching_recent", rows)
                if isinstance(last, dict) and last.get("path"):
                    store.set("watching_last", last)
                if held:
                    store.set("watching_held", held)
            store.set("watching_path_backfill",
                      {"version": self.PATH_BACKFILL_VERSION, "filled": filled,
                       "of": len(targets), "at": time.time()})
            if filled:
                logger.log(f"[watching] the file he played was put back on {filled} of "
                           f"{len(targets)} record(s) of a play, from the player's own history; "
                           f"those episodes can be transcribed now")
            return filled
        except Exception as e:
            logger.log(f"[watching] the play files were not put back: {type(e).__name__}")
            return 0

    # ---------------- noticing ----------------

    def _con(self):
        return open_ro(self.db_path)

    def _from_list(self, since_ts):
        """(anime_id, title, ep, watched_at) for episodes the list has logged
        since the cursor. Exact -- it carries the show's own id."""
        con = self._con()
        if not con:
            return []
        try:
            rows = con.execute(
                "SELECT e.anime_id, a.title, e.ep, e.watched_at FROM episodes e "
                "JOIN anime a ON a.anime_id = e.anime_id "
                "WHERE e.watched_at > ? ORDER BY e.watched_at", (since_ts,)).fetchall()
        except sqlite3.Error as e:
            logger.log(f"[watching] his list not read: {type(e).__name__}")
            rows = []
        finally:
            con.close()
        return [(int(r[0]), r[1] or "", int(r[2] or 0), r[3] or "",
                 {"route": "his list", "aid_exact": True}) for r in rows]

    def _from_player(self, since_ts):
        """(anime_id, title, ep, when) for files the player opened since the
        cursor. Earlier than the list by however long he takes to mark it, and
        the only signal at all for a show he never marks."""
        c = self.config.watching
        path = os.path.expandvars(str(getattr(c, "player_history_path", "") or ""))
        if not path or not os.path.exists(path) or not self.anime_kb:
            return []
        out = []
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()[-int(c.player_history_tail):]
        except OSError as e:
            logger.log(f"[watching] the player history not read: {type(e).__name__}")
            return []
        for line in lines:
            if "|" not in line:
                continue
            stamp, _, p = line.strip().partition("|")
            try:
                ts = float(stamp)
            except ValueError:
                continue
            if ts <= since_ts:
                continue
            title, ep = parse_file(p)
            if not title or not ep:
                sp = parse_special(p)
                if not sp:
                    continue
                # a special: the OVA / ONA / special entry of that franchise on
                # his list, never the TV entry the base title would resolve to
                hit = self.anime_kb.resolve_special(sp[0])
                if hit:
                    logger.log(f"[watching] {ntpath.basename(p)}: a {sp[1]} of {sp[0]} -> {hit[1]}")
                    out.append((hit[0], hit[1], sp[2], ts,
                                {"route": "the player", "path": p, "by_title": True,
                                 "kind_hint": "special", "special": sp[1],
                                 "type": (hit[2] if len(hit) > 2 else ""),
                                 "candidates": [{"aid": hit[0], "title": hit[1],
                                                 "type": (hit[2] if len(hit) > 2 else ""),
                                                 "rule": f"the only {sp[1]} of that name on his list"}]}))
                continue
            # The ranking, not the first row sqlite hands back: the episode
            # number rules out an entry that cannot have it, and the folder's
            # season says this is the television run rather than a special.
            # More than one survivor is a question for `sim/resolver.py`, and
            # the worker asks it -- never this poll, which is the loop thread.
            cands = self.anime_kb.resolve_candidates(title, ep=ep, kind="tv")
            if not cands:
                continue
            top = cands[0]
            out.append((top["aid"], top["title"], ep, ts,
                        {"route": "the player", "path": p, "by_title": True,
                         "kind_hint": "tv", "type": top.get("type", ""),
                         "parsed": title, "candidates": cands,
                         "ask": len(cands) > 1}))
        return out

    def poll(self):
        """Cheap, on the loop: the newest episode he has watched that she has
        not been told about, or None. Two local files, no network."""
        c = self.config.watching
        if not c.enabled:
            return None
        # his own record of what the player finished, before anything else:
        # it is the machine's rather than hers, it is written whether or not
        # this poll takes an episode up, and the first call after a boot
        # catches up whatever was played while nothing was running
        self._record_plays()
        cur = self.store.get("watching_cursor", {}) or {}
        if not cur:
            # First run starts HERE, not at the beginning of his history. With
            # an empty cursor the list query matches all 3,161 episodes and
            # the oldest wins the sort, so her first act would have been to
            # read up on something he watched years ago as though he had just
            # put it on.
            import datetime
            self.store.set("watching_cursor", {
                "list": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"),
                "player": time.time()})
            logger.log("[watching] starting from now, not from the start of his history")
            return None
        found = []
        try:
            found += list(self._from_list(str(cur.get("list", ""))))
        except Exception as ex:
            logger.log(f"[watching] list poll failed: {type(ex).__name__}")
        try:
            found += list(self._from_player(float(cur.get("player", 0) or 0)))
        except Exception as ex:
            logger.log(f"[watching] player poll failed: {type(ex).__name__}")
        if not found:
            # nothing new on either route; a batch that arrived earlier may
            # still be owed its reading-up (`_queue_rest`)
            return self._from_queue(self._seen())
        # Move the cursors past everything seen even if only one episode is
        # taken up. What is NOT taken up is no longer thrown away with them:
        # his list logs a session as several rows at one timestamp -- six episodes of one work at one timestamp, four at another --
        # and taking the newest and stepping over the rest lost five plays
        # she was then never told about. The rest go in a queue and are read
        # up one per poll (`_queue_rest`), so the summaries still arrive one
        # at a time rather than six at once, and the range she is shown is
        # right.
        lst = [w for _a, _t, _e, w, _h in found if isinstance(w, str) and w]
        ply = [w for _a, _t, _e, w, _h in found if not isinstance(w, str)]
        self.store.set("watching_cursor", {
            "list": max(lst) if lst else cur.get("list", ""),
            "player": max(ply) if ply else float(cur.get("player", 0) or 0)})
        seen = self._seen()
        # NEWEST first. Taking the oldest unseen meant that on an evening of
        # six episodes she went and read up on the one he watched three hours
        # ago while he was finishing the sixth -- and then had nothing to say
        # about the one he had actually just seen.
        #
        # And an open is not a watch. A file opened for five seconds was
        # fetched, digested and kept as "he watched", so an episode from the
        # player counts only once the position file shows him
        # `min_minutes_in` into it, or it was open that long before he closed
        # it or opened the next file. Until then it is not marked seen, so
        # the next poll looks again.
        # TWO THRESHOLDS, MEASURING DIFFERENT THINGS. `min_minutes_in` is the
        # floor under which an open is not a play at all -- a mis-click, and
        # nothing is said about it. `min_watched_minutes` is the gate on
        # everything that costs money or reaches her, and it is measured in
        # UNPAUSED SECONDS he actually sat through, which is the only number
        # that can tell a watch from a seek to the last minute: the open line
        # is identical either way, and so is the end position.
        floor = float(getattr(c, "min_minutes_in", 0) or 0) * 60
        need = float(getattr(c, "min_watched_minutes", 0) or 0) * 60
        raw = self._now_raw()
        now = self.clock.now_ts()
        opens = sorted(float(w) for _a, _t, _e, w, _h in found if not isinstance(w, str))
        # An open too short to count is remembered by its own clock, never
        # as the episode: "7627:12" in `watching_seen` after a three-second
        # open would have hidden the real watch of episode 12 from both
        # routes, the player's and the list's, for good.
        short = self.store.get("watching_short", []) or []
        # NEWEST FIRST BY REAL TIME. The two routes carry different kinds of
        # stamp -- his list an ISO minute (`2026-09-04T19:47`), the player a
        # unix time -- and comparing them as text put every list row ahead of
        # every player row whatever the clock said, because "1788..." sorts
        # under "2026...". `_when_ts` reads both as seconds. A list row for the
        # SAME watch still wins, and should: it arrives later and carries the
        # work's own id instead of a filename to guess from.
        for aid, title, ep, when, how in sorted(found, key=lambda x: self._when_ts(x[3]), reverse=True):
            key = f"{aid}:{ep}"
            # counted before: within the window it is the same watch (he paused,
            # the list caught up); past it, an open is a rewatch and counts again
            again = key in seen
            if again and now - float(seen[key] or 0) < float(getattr(c, "rewatch_after_hours", 24) or 24) * 3600:
                continue
            # HOW LONG HE HAS BEEN IN IT. Three minutes is what makes an open a
            # watch; a longer floor is what a transcription is worth paying a
            # GPU for, and that decision is made downstream
            # (`sim/transcribe.py`). His list gives no such number at all, and
            # nothing is transcribed off it, which is right: it also gives no
            # file to listen to.
            watched = 0.0
            if (need or floor) and not isinstance(when, str):
                open_ts = int(float(when))
                if f"{key}:{open_ts}" in short:
                    continue
                watched, still_open, by, length = self._watched_for_open(
                    how.get("path", ""), float(when), aid, ep, raw, opens, now)
                if watched < need:
                    if still_open:
                        # HELD, not refused: he is in the file and has not got
                        # far enough yet. The cursor above has already moved
                        # past this open, so put it back to just before -- the
                        # next poll has to find this open again or the episode
                        # is never counted, which is how episode 11 of a show
                        # went unread while he sat through it. The hold itself
                        # goes in the save beside it, because a stop is
                        # TerminateProcess and the next boot must find the
                        # same hold rather than a fetch it never made.
                        self._hold(key, title, ep, float(when), watched, need, by,
                                   how.get("path", ""))
                        cur = self.store.get("watching_cursor", {}) or {}
                        cur["player"] = min(float(cur.get("player", 0) or 0), float(when) - 1)
                        self.store.set("watching_cursor", cur)
                        return None
                    # It ended under the gate. Remembered by its own open and
                    # NEVER marked seen, so the episode is still free to count
                    # when he watches it properly.
                    short = self._settle_short(key, open_ts, title, ep, watched,
                                               length, by, floor, need, short)
                    continue
                self._clear_hold(key)
            # A play whose work came from the FILENAME alone waits a few
            # minutes for his list to name the id, which is exact. Past the
            # window the parse stands; when the id arrives and differs, the id
            # wins and the log names both.
            if how.get("by_title") and not isinstance(when, str):
                held = self._await_id(aid, title, ep, when, how)
                if held is None:
                    return None
                aid, title, how = held
                key = f"{aid}:{ep}"
                if key in seen and now - float(seen.get(key) or 0) < float(
                        getattr(c, "rewatch_after_hours", 24) or 24) * 3600:
                    continue
            self._mark_seen(seen, key)
            self._queue_rest(found, seen, key)
            # WHEN HE PLAYED IT rides with it. The record used to stamp the
            # episode with the moment the fetch finished, and everything that
            # says how long ago he watched -- her line, the freshness window,
            # the grouped block's "yesterday afternoon" -- was measuring from
            # the wrong end: a file opened at 15:39 and read up at 16:32 was
            # 53 minutes younger than it was.
            return {"anime_id": aid, "title": title, "ep": ep, "again": again,
                    "at": self._when_ts(when), "watched": watched, "how": how}
        # nothing in this batch could be taken up (all seen, all too short):
        # keep whatever his list logged and serve the queue
        self._queue_rest(found, seen, "")
        return self._from_queue(seen)

    # ---------------- how much of it he actually watched ----------------

    def _watched_for_open(self, path, open_ts, aid, ep, raw, opens, now):
        """`(seconds watched, still open, who answered, the file's length)`
        for ONE open of the player's history.

        Three answers, best first, and the log says which one decided.

          * The player's own record of the FINISHED play (`mpv_plays.log` via
            `machine/plays.py`): unpaused seconds, exact, and what a skim is
            judged on.
          * The live state file while the file is still in front of him: the
            same number, counted so far.
          * Neither -- an older copy of the script, another player, another
            machine -- and the wall clock between this open and the next is
            all there is. It counts a file left paused as watched, which is
            the fault the other two exist to fix, so it is named when used.
        """
        c = self.config.watching
        try:
            row = plays.for_open(getattr(c, "player_plays_path", ""), open_ts, path)
        except Exception as e:
            logger.log(f"[watching] the player's finished plays not read: {type(e).__name__}")
            row = None
        if row:
            return (float(row.get("watched") or 0), False,
                    f"the player's own record of the play, {row.get('reason') or 'ended'}",
                    float(row.get("length") or 0))
        # A state file nobody has refreshed is nobody watching -- the same
        # rule `now_playing` reads it by. Without it a player killed inside a
        # file leaves `playing: true` standing for ever, and the open it names
        # would be held for ever with it.
        live = bool(raw and raw.get("playing")
                    and (time.time() - float(raw.get("t") or 0)
                         <= float(getattr(c, "now_stale_seconds", 60) or 60)))
        if live and self._raw_is_open(raw, path, open_ts, aid, ep):
            got = raw.get("watched")
            if isinstance(got, (int, float)):
                return float(got), True, "the player, live", float(raw.get("dur") or 0)
            # an older script writes no unpaused count; the position is the
            # best it can say, and it reads a seek to the end as a watch
            return (float(raw.get("pos") or 0), True, "the player's position, live",
                    float(raw.get("dur") or 0))
        later = [o for o in opens if o > float(open_ts)]
        # A state file that is FRESH and says nobody is watching is the player
        # saying the file closed; a stale one says nothing at all.
        quiet = bool(raw and not raw.get("playing")
                     and (time.time() - float(raw.get("t") or 0)
                          <= float(getattr(c, "now_stale_seconds", 60) or 60)))
        if later:
            end, closed = min(later), True
        elif quiet:
            end, closed = float(raw.get("t") or now), True
        else:
            # Nothing has said the file ended, so it has not. With only the
            # clock, "he is still in it" and "he closed it and nothing saw"
            # look identical, and calling it closed would file a play he is
            # part-way through as a skim and lose it for good.
            end, closed = now, False
        return (max(0.0, end - float(open_ts)), not closed,
                "the clock between this open and the next", 0.0)

    @staticmethod
    def _same_path(p):
        return str(p or "").replace("/", "\\").strip().lower()

    def _raw_is_open(self, raw, path, open_ts, aid, ep):
        """Is the file the player has open right now THIS open of the history.

        The state file carries the epoch the file opened at, which is the same
        integer the history line carries, so the two join exactly. The path and
        then the resolved work are what an older script still allows."""
        got = raw.get("opened")
        if isinstance(got, (int, float)) and got:
            return abs(float(got) - float(open_ts)) <= 3.0
        rp, wp = self._same_path(raw.get("path")), self._same_path(path)
        if rp and wp:
            return rp == wp
        return self._raw_is(raw, aid, ep)

    def _hold(self, key, title, ep, open_ts, watched, need, by, path=""):
        """One open being waited on, written to the SAVE.

        A hold that lived on the object would be lost by a stop and the next
        boot would either fetch an episode he skimmed or hold the same open a
        second time. Keyed on the episode, so a poll that finds the same open
        again replaces its row rather than adding one.

        THE FILE HE OPENED RIDES WITH IT from here to the record of the play.
        It is the only thing that can be listened to, and dropping it at the
        hold meant a repair pass months later had nothing to hand the
        transcriber but the episode's number."""
        held = self.store.get("watching_held", {}) or {}
        row = held.get(key) or {}
        held[key] = {"title": title, "ep": int(ep or 0), "at": float(open_ts),
                     "watched": float(watched), "need": float(need),
                     "path": str(path or row.get("path") or ""),
                     "since": float(row.get("since") or self.clock.now_ts())}
        # a hold nobody ever cleared -- the player was killed inside the file,
        # so no play line was written and no open follows it -- is not kept
        cut = self.clock.now_ts() - 48 * 3600
        held = {k: v for k, v in held.items()
                if k == key or float(v.get("since") or 0) >= cut}
        self.store.set("watching_held", held)
        logger.log(f"[watching] {title} ep{ep} is open, {watched / 60:.1f} of the "
                   f"{need / 60:.0f} min it has to run before anything is fetched; "
                   f"held ({by})")

    def _clear_hold(self, key):
        held = self.store.get("watching_held", {}) or {}
        if key in held:
            del held[key]
            self.store.set("watching_held", held)

    def _settle_short(self, key, open_ts, title, ep, watched, length, by, floor, need, short):
        """A play that ended under the gate, and the end of its hold.

        Two different things are recorded with the same mechanism and said
        with different words: under `min_minutes_in` he opened the file and
        closed it, and above that he watched some of it and stopped, which is
        a skim. Neither is marked seen, so the episode still counts when he
        watches it properly; both are remembered by the open's own clock, so
        the record cannot hide a real watch of the same episode."""
        short = (short + [f"{key}:{open_ts}"])[-int(self.config.watching.remember_episodes):]
        self.store.set("watching_short", short)
        self._clear_hold(key)
        if watched < floor:
            logger.log(f"[watching] {title} ep{ep} was open {watched:.0f}s ({by}); not counted")
        else:
            of = f"{length / 60:.0f}" if length > 0 else f"{need / 60:.0f}"
            logger.log(f"[watching] skim: {title} ep{ep}, {watched / 60:.0f} min watched "
                       f"of {of} -- no fetch ({need / 60:.0f} min needed; {by})")
        return short

    # ---------------- his own record of what he played ----------------

    def _record_plays(self):
        """His readable timeline of finished plays, kept up to date by
        whichever process polls first (`machine/plays.py`).

        Not elected to one character and not one file per character: the
        timeline is the machine's, the write is idempotent on the open's own
        epoch, and three processes reaching one play produce one row."""
        c = self.config.watching
        try:
            plays.record_new(
                getattr(c, "player_plays_path", ""),
                getattr(c, "plays_timeline_path", ""),
                float(getattr(c, "min_watched_minutes", 0) or 0) * 60,
                resolve=self._name_of_file,
                tail=int(getattr(c, "player_history_tail", 400) or 400),
                log=logger.log)
        except Exception as e:
            logger.log(f"[plays] his timeline not written: {type(e).__name__}")

    def _name_of_file(self, path):
        """What to call a played file in his timeline: the work and the
        episode as his own list has them, and nothing when the file is not an
        episode of anything -- the same folder holds radio recordings, music
        videos and a file called `input.webm`, and for those the bare filename
        is the honest name, which is what the caller falls back to."""
        title, ep = parse_file(path)
        if title and ep:
            try:
                cands = self.anime_kb.resolve_candidates(title, ep=ep, kind="tv") if self.anime_kb else []
            except Exception:
                cands = []
            return f"{cands[0]['title']} ep{ep}" if cands else f"{title} ep{ep}"
        sp = parse_special(path)
        if sp:
            try:
                hit = self.anime_kb.resolve_special(sp[0]) if self.anime_kb else None
            except Exception:
                hit = None
            return f"{hit[1]} {sp[1]}{sp[2]}" if hit else f"{sp[0]} {sp[1]}{sp[2]}"
        return ""

    # ---------------- a batch, and what it is owed ----------------

    @staticmethod
    def _when_ts(when):
        """One route's stamp as seconds, whichever route wrote it: his list
        writes an ISO minute, the player a unix time."""
        if isinstance(when, str):
            import datetime
            try:
                return datetime.datetime.strptime(when[:16], "%Y-%m-%dT%H:%M").timestamp()
            except (ValueError, TypeError, OSError):
                return 0.0
        try:
            return float(when or 0)
        except (TypeError, ValueError):
            return 0.0

    def _fetched_today(self):
        return int((self.store.get("watching_fetch_counts", {}) or {}).get(self.clock.date_str(), 0) or 0)

    def note_fetch(self):
        """One episode was read up on today. The count is what the day's cap
        is measured against; a week of days is kept and no more."""
        counts = self.store.get("watching_fetch_counts", {}) or {}
        d = self.clock.date_str()
        counts[d] = int(counts.get(d, 0) or 0) + 1
        self.store.set("watching_fetch_counts", dict(sorted(counts.items())[-7:]))

    @staticmethod
    def _first_of_each(rows):
        """The lowest-numbered episode of each work, newest work first: where
        a session has to be cut short, the one worth reading up on is where he
        started, because it is what the rest of the run follows from."""
        firsts = {}
        for r in rows:
            a = r.get("anime_id")
            if a not in firsts or int(r.get("ep") or 0) < int(firsts[a].get("ep") or 0):
                firsts[a] = r
        return sorted(firsts.values(), key=lambda r: -float(r.get("at") or 0))

    def _queue_rest(self, found, seen, taken_key):
        """Everything HIS LIST logged in this poll that was not taken up, kept
        for a reading-up of its own. Returns how many were queued.

        Only the list route. A run in the player arrives one open per poll --
        he is inside each episode for twenty minutes and the poll runs every
        four -- so each is noticed on its own and needs no queue. His list is
        the one that arrives in a lump: it logs a whole session at one minute,
        and the rows behind the newest were the plays she never heard about.

        Past the day's cap the leftovers are not queued at all: they are
        recorded as watched with no synopsis, so the range she is shown still
        covers them and no model call is spent on them."""
        c = self.config.watching
        rows = []
        for aid, title, ep, when, how in found:
            if not isinstance(when, str):
                continue
            key = f"{aid}:{ep}"
            if key == taken_key or key in seen:
                continue
            rows.append({"anime_id": aid, "title": title, "ep": int(ep or 0),
                         "at": self._when_ts(when),
                         "how": {k: v for k, v in (how or {}).items() if k != "candidates"}})
        if not rows:
            return 0
        rows.sort(key=lambda r: -float(r.get("at") or 0))
        uniq, have = [], set()
        for r in rows:
            k = f"{r['anime_id']}:{r['ep']}"
            if k in have:
                continue
            have.add(k)
            uniq.append(r)
        queued = self.store.get("watching_queue", []) or []
        room = max(0, int(getattr(c, "max_fetches_per_day", 8) or 8)
                   - self._fetched_today() - len(queued))
        if room >= len(uniq):
            keep, stubs = uniq, []
        else:
            keep = self._first_of_each(uniq)[:room]
            kept = {f"{r['anime_id']}:{r['ep']}" for r in keep}
            stubs = [r for r in uniq if f"{r['anime_id']}:{r['ep']}" not in kept]
        if keep:
            held = {f"{r.get('anime_id')}:{r.get('ep')}" for r in queued}
            queued = queued + [r for r in keep if f"{r['anime_id']}:{r['ep']}" not in held]
            queued.sort(key=lambda r: -float(r.get("at") or 0))
            self.store.set("watching_queue", queued[: int(getattr(c, "queue_max", 20) or 20)])
        for r in stubs:
            self._stub(r, seen)
        logger.log(f"[watching] his list logged {len(uniq)} more episode(s) in the same batch: "
                   f"{len(keep)} queued to read up, {len(stubs)} recorded without a synopsis")
        return len(keep)

    def _stub(self, row, seen):
        """An episode of a batch the day's cap will not stretch to. It
        happened, it counts towards the range she is told about, and nobody
        reads it up. Marked seen at once so no later poll spends a fetch on
        it, and no network is touched: the display name comes from whichever
        episode of the same work WAS read up on."""
        c = self.config.watching
        ent = self._entry(row.get("anime_id")) or {}
        rec = self.store.get("watching_recent", []) or []
        rec.append({"anime_id": row.get("anime_id"), "title": row.get("title", ""),
                    "ja": "", "ep": int(row.get("ep") or 0),
                    "at": float(row.get("at") or 0), "digest": "", "stub": True,
                    "confidence": "", "parts": [], "again": False,
                    "progress": self.progress(row.get("anime_id")),
                    "media_type": ent.get("type", ""), "total_eps": ent.get("eps", 0),
                    "season": ent.get("season", ""), "resolved_by": "his list"})
        rec.sort(key=lambda r: float(r.get("at") or 0))
        self.store.set("watching_recent", rec[-int(getattr(c, "recent_keep", 24) or 24):])
        self._mark_seen(seen, f"{row.get('anime_id')}:{row.get('ep')}")

    def _from_queue(self, seen):
        """The next episode of a batch that is still owed its reading-up, or
        None. One per poll, so six episodes of one work cost six fetches over
        half an hour rather than six at once."""
        c = self.config.watching
        queued = self.store.get("watching_queue", []) or []
        if not queued:
            return None
        if self._fetched_today() >= int(getattr(c, "max_fetches_per_day", 8) or 8):
            for r in queued:
                if f"{r.get('anime_id')}:{r.get('ep')}" not in seen:
                    self._stub(r, seen)
            self.store.set("watching_queue", [])
            logger.log(f"[watching] today's reading-up cap is spent; the {len(queued)} episode(s) "
                       f"still queued are recorded as watched with no synopsis")
            return None
        while queued:
            row = queued.pop(0)
            self.store.set("watching_queue", queued)
            key = f"{row.get('anime_id')}:{row.get('ep')}"
            if key in seen:
                continue
            self._mark_seen(seen, key)
            logger.log(f"[watching] {row.get('title')} ep{row.get('ep')} was in the same batch; "
                       f"reading it up now, {len(queued)} still queued")
            return {"anime_id": row.get("anime_id"), "title": row.get("title", ""),
                    "ep": int(row.get("ep") or 0), "again": False,
                    "at": float(row.get("at") or 0),
                    "how": dict(row.get("how") or {}, queued=True)}
        return None

    def _list_id_for(self, ep, at, allow=(), title=""):
        """(anime_id, title) his list has logged for THIS watch, or None.
        Exact where the filename is a guess, and typically half an hour later.

        The episode number alone is not enough to say two records are one
        watch: he marks episodes of several shows in an evening and two of
        them can share a number. So the row also has to be one of the works
        the filename could mean, or a title the filename's own title is
        inside."""
        import datetime
        try:
            since = datetime.datetime.fromtimestamp(float(at) - 600).strftime("%Y-%m-%dT%H:%M")
        except (TypeError, ValueError, OSError):
            return None
        ids = {int(a) for a in (allow or []) if a}
        want = re.sub(r"[^a-z0-9]", "", str(title or "").lower())
        for a, t, e, _w, _h in self._from_list(since):
            if int(e or 0) != int(ep or 0):
                continue
            other = re.sub(r"[^a-z0-9]", "", str(t or "").lower())
            near = bool(want and other and len(want) >= 6
                        and (want in other or other in want))
            if int(a) in ids or near:
                return int(a), t
            logger.log(f"[resolver] his list logged mal:{a} ({t}) ep{ep} around the same time, "
                       f"and it is not a work {title!r} could mean; not used")
        return None

    def _await_id(self, aid, title, ep, when, how):
        """The confirm window over a title-only resolution.

        `(aid, title, how)` to go ahead with, or None to wait: the player's
        cursor is put back so the next poll finds this open again, exactly as
        the too-short-open case does."""
        c = self.config.watching
        wait = float(getattr(c, "confirm_minutes", 0) or 0) * 60
        allow = [cd.get("aid") for cd in (how.get("candidates") or [])] + [aid]
        got = self._list_id_for(ep, when, allow=allow,
                                title=how.get("parsed") or title)
        if got and int(got[0]) != int(aid):
            logger.log(f"[resolver] his list names mal:{got[0]} ({got[1]}) for ep{ep}; the "
                       f"filename resolved to mal:{aid} ({title}) -- the id wins")
            return int(got[0]), got[1], dict(how, by_title=False, ask=False,
                                             aid_exact=True, parse_aid=aid,
                                             type=self._type_of(got[0]))
        if got:
            return aid, title, dict(how, by_title=False, ask=False, aid_exact=True)
        if not wait or (self.clock.now_ts() - float(when)) >= wait:
            return aid, title, how
        cur = self.store.get("watching_cursor", {}) or {}
        cur["player"] = min(float(cur.get("player", 0) or 0), float(when) - 1)
        self.store.set("watching_cursor", cur)
        logger.log(f"[watching] {title} ep{ep} was resolved from the filename alone; waiting "
                   f"up to {wait / 60:.0f} min for his list to name the id")
        return None

    def _type_of(self, aid):
        return str((self._entry(aid) or {}).get("type") or "")

    def _entry(self, aid):
        """What his list holds about one work: the edition, the episode count,
        the season. `{}` without a mirror."""
        if not aid or self.anime_kb is None:
            return {}
        try:
            return self.anime_kb.entry(aid) or {}
        except Exception:
            return {}

    def _standing(self, aid):
        """One line of where HE stands with a candidate -- what he has marked
        and scored -- which is most of what separates two editions of one
        franchise: he had finished the 26-episode entry three days before he
        opened the OVA."""
        pr = self.progress(aid)
        if not pr:
            return f"mal:{aid}: nothing marked on his list"
        marked, total, status = pr
        return (f"mal:{aid}: he has marked {marked} of {total or '?'} episode(s)"
                + (", and finished it" if total and marked >= total else ""))

    def _seen(self):
        """{episode key: when it was counted}. The list kept before the clock
        was reads as counted long ago, so an open of one of those is a
        rewatch -- except the one the module still holds, which keeps its
        own time."""
        raw = self.store.get("watching_seen", {}) or {}
        if isinstance(raw, list):
            last = self.store.get("watching_last", None) or {}
            lk = f"{last.get('anime_id')}:{last.get('ep')}"
            raw = {k: (float(last.get("at") or 0) if k == lk else 0.0) for k in raw}
        return raw

    def _mark_seen(self, seen, key):
        seen[key] = self.clock.now_ts()
        keep = sorted(seen.items(), key=lambda kv: float(kv[1] or 0))[-int(self.config.watching.remember_episodes):]
        self.store.set("watching_seen", dict(keep))

    def _now_raw(self):
        """The player's state file as written, playing or not; None if unread."""
        c = self.config.watching
        path = os.path.expandvars(str(getattr(c, "now_playing_path", "") or ""))
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
            return d if isinstance(d, dict) else None
        except (OSError, ValueError):
            return None

    def _raw_is(self, raw, aid, ep):
        """Does the player's file name this show and episode."""
        title, e = parse_file(raw.get("path") or "")
        if not title or e != ep:
            return False
        try:
            hit = self.anime_kb.resolve_strict(title, ep=ep, kind="tv") if self.anime_kb else None
        except Exception:
            hit = None
        if hit:
            return hit[0] == aid
        return bool(title)

    def now_playing(self):
        """Where he is in the file open in front of him, or None.

        Written from inside the player (`tools/mpv/scail_logger.lua`), because
        the obvious answer -- how long since the file opened -- is wrong the
        moment he pauses, and pausing is the state most worth knowing about.
        mpv reports its own `time-pos` and `pause`, so a paused file stops
        moving and says so.

        A state file that has not been refreshed inside `now_stale_seconds` is
        nobody watching: that is what covers the player being killed rather
        than closed, which writes no ending."""
        c = self.config.watching
        path = os.path.expandvars(str(getattr(c, "now_playing_path", "") or ""))
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            return None
        if not isinstance(d, dict) or not d.get("playing"):
            return None
        if time.time() - float(d.get("t", 0) or 0) > float(c.now_stale_seconds):
            return None
        pos, dur = d.get("pos"), d.get("dur")
        if not isinstance(pos, (int, float)) or not isinstance(dur, (int, float)) or dur <= 0:
            return None
        title, ep = parse_file(d.get("path") or "")
        hit = (self.anime_kb.resolve_strict(title, ep=ep, kind="tv")
               if (title and self.anime_kb) else None)
        return {"anime_id": hit[0] if hit else None,
                "title": hit[1] if hit else (title or ""),
                "ep": ep, "pos": float(pos), "dur": float(dur),
                "pct": max(0.0, min(100.0, 100.0 * float(pos) / float(dur))),
                "paused": bool(d.get("paused"))}

    def progress(self, anime_id):
        """Where he is in this series: (watched, total, status). His own list,
        so it is what he has marked rather than what he has played."""
        con = self._con()
        if not con or not anime_id:
            return None
        try:
            r = con.execute("SELECT watched_episodes, num_episodes, status FROM anime "
                            "WHERE anime_id=?", (anime_id,)).fetchone()
        except sqlite3.Error:
            r = None
        finally:
            con.close()
        return (int(r[0] or 0), int(r[1] or 0), int(r[2] or 0)) if r else None

    # ---------------- is she in it ----------------

    def her_parts(self, anime_id):
        """[(character, 'Main'|'Supporting')] for the parts she plays in this
        show, from the cast his own mirror already holds.

        By her PERSON ID where her config gives one, which cannot go wrong.
        The substring match below it is what a character with no id still
        gets, and it is why this was never the authority: `LIKE '%name%'` on
        her given name matches nine other people in the cast rows, and which
        of them answered was down to the order sqlite happened to return.

        This is the second witness, never the first. It only knows the 480 of
        his 701 titles whose cast anybody has mirrored, so on its own it
        answers "not yours" about works she really is in; `sim/works.py`
        asks her own filmography first and uses this to agree."""
        if not anime_id:
            return []
        pid = works.her_person_id(self.config)
        c = self.config.watching
        who = str(getattr(c, "her_seiyuu_name", "") or "").strip()
        if not pid and not who:
            return []
        con = self._con()
        if not con:
            return []
        try:
            if pid:
                rows = con.execute(
                    "SELECT character, role FROM anime_cast WHERE anime_id=? AND jp_va_id=?",
                    (anime_id, int(pid))).fetchall()
            else:
                rows = con.execute(
                    "SELECT character, role FROM anime_cast WHERE anime_id=? AND jp_va LIKE ?",
                    (anime_id, f"%{who}%")).fetchall()
        except (sqlite3.Error, ValueError):
            rows = []
        finally:
            con.close()
        return [(r[0] or "", r[1] or "") for r in rows]

    # ---------------- her future, opened one work at a time ----------------

    def open_her_record(self, title, parts):
        """Add this work and the parts she plays in it to the set of things
        the era gate will let through. Returns the tokens newly added."""
        c = self.config.watching
        if not c.open_her_record:
            return []
        have = self.store.get("lore_contact", []) or []
        add = {" ".join(sorted(_tokens(title)))}
        for ch, _role in parts:
            add.add(" ".join(sorted(_tokens(ch))))
        # kept as sorted token strings so the reader in sim/lore.py does the
        # same normalising on both sides and neither has to know the other's
        # spelling
        new = [a for a in sorted(add) if a and a not in have]
        if new:
            self.store.set("lore_contact", have + new)
            logger.log(f"[watching] her own record opens for: {', '.join(new)}")
        return new

    @staticmethod
    def record_opens(record_title, contact):
        """Does contact with these works release this record?

        Either every word of the record's title appears in the work, or the
        record shares a long word with the work's own title. The second is
        what lets a note *about* a role -- what it did to her career -- come
        with the role, and the length floor is what keeps it from firing on
        a surname two shows happen to share."""
        rt = _tokens(record_title)
        if not rt:
            return False
        for entry in contact or []:
            ct = _tokens(entry)
            if not ct:
                continue
            if rt <= ct:
                return True
            if {t for t in (rt & ct) if len(t) >= 5 and t not in _WEAK}:
                return True
        return False

    # ---------------- reading up on it ----------------

    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def digest(self, item):
        """The important parts of the synopsis, in Japanese, a few hundred
        characters, by the `watching_digest` role. The raw synopsis is a blog
        page -- impressions, headings, other episodes -- and cutting it at a
        character count kept the page's opening and lost the episode's end.
        Empty when there is no synopsis, no model client, or the role failed;
        the caller then falls back to the cut."""
        c = self.config.watching
        s = str(item.get("summary") or "")
        if not s or self.llm is None or self.recap is None:
            return ""
        name = item.get("ja") or item.get("title") or ""
        out, scenes = self.recap.digest_page(self.llm, name, item.get("ep"), s)
        if scenes:
            # the ordered scene list goes on the record beside the digest, not
            # into her line: her line stays what she skimmed
            item["scenes"] = scenes
        if not out:
            return ""
        if out.startswith("なし"):
            # the role read the page and it is not about this episode; the
            # raw text must not reach her as though it were
            logger.log(f"[watching] the page fetched for {name} ep{item.get('ep')} is not about the episode; dropped")
            item["summary"] = ""
            return ""
        return out[: int(c.digest_max_chars)]

    def start(self, item):
        """Fetch the あらすじ for one episode off the main thread. The browser
        it opens is a throwaway profile, so it never contends with her own."""
        c = self.config.watching
        if not c.enabled or self.busy() or not item:
            return False
        self.thread = threading.Thread(target=self._work, args=(item,), daemon=True)
        self.thread.start()
        return True

    def judge(self, ja, ep, scored, anchor="", anchor_kind=""):
        """Which of several digests a viewer would trust: an index into
        `scored`, or -1. One call on the cheap model, comparing the candidates
        with each other and with the anchor. The judge itself lives in
        `sim/recap.py`, so both watching paths ask the same question."""
        if self.recap is None or self.llm is None or not scored:
            return 0 if scored else -1
        rows = [{"url": url, "digest": dg} for text, url, dg in scored]
        best, why, corr = self.recap.judge_candidates(self.llm, ja, ep, rows, anchor, anchor_kind)
        logger.log(f"[watching] judge: {best + 1 if best >= 0 else 'none'} of {len(scored)}"
                   + (f", {len(corr)} agreed" if corr else "") + f" -- {why[:120]}")
        return best

    def _work(self, item):
        try:
            aid, title, ep = item["anime_id"], item["title"], item["ep"]
            # THE ONE PLACE THE RESOLVER'S ROLE MAY BE ASKED about a play: a
            # daemon thread that is already fetching pages. The poll that
            # noticed the file is the loop thread and asks nothing. Code has
            # already dropped every candidate that cannot have this episode
            # and ordered the rest; this is only reached when more than one
            # survived, and code's own answer stands on any failure.
            how = dict(item.get("how") or {})
            if how.get("ask") and self.resolver is not None:
                cands = list(how.get("candidates") or [])
                for cd in cands:
                    cd.setdefault("season", (self._entry(cd.get("aid")) or {}).get("season", ""))
                    cd.setdefault("blurb", (self._entry(cd.get("aid")) or {}).get("synopsis", ""))
                q = f"which work he opened as {how.get('parsed') or title!r} episode {ep}"
                key = ("play|%s|ep%d|%s|%s" % (
                    _resolver.norm(how.get("parsed") or title), int(ep),
                    how.get("kind_hint") or "none",
                    "+".join(str(cd.get("aid")) for cd in cands)))
                cue = (f"the file he opened: {how.get('path') or ''}\n"
                       f"what the filename parses to: {how.get('parsed') or title} "
                       f"episode {ep}\n"
                       f"his list has not logged this episode yet, so there is no id from it\n"
                       + "\n".join(self._standing(cd.get("aid")) for cd in cands))
                chosen, by, unsure = self.resolver.choose_work(q, cands, cue, key)
                if chosen is None and not unsure:
                    logger.log(f"[watching] nothing is fetched for {how.get('parsed') or title} "
                               f"ep{ep}: the resolver says none of the candidates is it")
                    self.result = None
                    return
                if chosen and int(chosen["aid"]) != int(aid):
                    aid, title = int(chosen["aid"]), chosen.get("title") or title
                    how["type"] = chosen.get("type", "")
                    self._mark_seen(self._seen(), f"{aid}:{ep}")
                item["anime_id"], item["title"] = aid, title
            elif how.get("route"):
                # every resolution says so, not only the ones a model was asked
                # about: the only trace of the wrong choice on 2026-09-04 was a
                # line about episode titles in the middle of a fetch
                _resolver.Resolver.say(
                    f"which work he opened as {how.get('parsed') or title!r} episode {ep}",
                    list(how.get("candidates") or []),
                    {"aid": aid, "title": title, "type": how.get("type", "")},
                    by="code",
                    why=("his own list logged it with this id" if how.get("aid_exact")
                         else "the filename, and his list has not logged it yet"))
            mtype = how.get("type") or self._type_of(aid)
            ja = ""
            if self.anime_kb:
                try:
                    ja = self.anime_kb.japanese_title(aid) or ""
                except Exception as e:
                    logger.log(f"[watching] ja title failed: {type(e).__name__}")
            # Is it hers? Her own filmography first and the cast as the
            # second witness (`sim/works.py`), which is what covers the works
            # of hers whose cast nobody has mirrored -- the cast table alone
            # answered "not yours" about parts she really played.
            #
            # THIS IS THE ONE PLACE ALLOWED TO GO AND LOOK. It is off the main
            # thread and already fetching pages, so mirroring a cast nobody
            # has (`role_check.fetch_on_miss`, one page, 0.28 s, no money) is
            # a cost this worker already carries. No reply path fetches:
            # everywhere else, a work nobody has mirrored stays not-checked
            # and she says nothing about it.
            verdict = works.her_part_verdict(self.config, self.anime_kb, [title], aid=aid)
            if (verdict.get("verdict") == "unknown" and aid and self.anime_kb is not None
                    and getattr(self.config.role_check, "fetch_on_miss", False)
                    and works.role_check_on(self.config)
                    and "cast" in str(verdict.get("why") or "")):
                try:
                    self.anime_kb.ensure(aid)
                    verdict = works.her_part_verdict(self.config, self.anime_kb, [title], aid=aid)
                    logger.log(f"[roles] the cast of {aid} was not mirrored; fetched, "
                               f"and the verdict is now {verdict.get('verdict')}")
                except Exception as e:
                    logger.log(f"[roles] the cast of {aid} could not be mirrored: {type(e).__name__}")
            if verdict.get("verdict") == "yes":
                parts = [(c_, b_) for c_, b_, _y in (verdict.get("parts") or [])]
            else:
                parts = self.her_parts(aid)
            summary, digest, scenes, quotes, confidence = "", "", [], [], ""
            account = None
            if self.recap and ja:
                # the id and the edition ride with the entry: the page is
                # filed and found under the WORK, not under a Japanese title
                # two works of his list share
                entry = {"title": title, "ja": ja, "kind": "anime", "ep": ep,
                         "aid": aid, "mtype": mtype,
                         "eps": (self._entry(aid) or {}).get("eps", 0)}
                # One path, in `sim/recap.py`: the cache when it holds a row a
                # judge chose, else the episode's own subtitle file as the
                # anchor, the ranked sources and the search as candidates, one
                # digest each and one judge over all of them. A provisional
                # row -- one candidate, or one nothing corroborated -- is read
                # again rather than trusted, which is how a programme table
                # sat in the cache as an episode's synopsis.
                # the file he opened rides with it: a subtitle already beside
                # it is the first thing looked at, and it is what is listened
                # to when nothing anywhere can be found. This is the worker
                # thread, which is the only place either may happen.
                got = self.recap.synopsis(entry, ep, llm=self.llm, anime_id=aid,
                                          english=title, titles=[title, ja],
                                          video=how.get("path", ""),
                                          watched_seconds=float(item.get("watched") or 0))
                if got:
                    summary = got.get("text") or ""
                    digest = got.get("digest") or ""
                    scenes = got.get("scenes") or []
                    quotes = got.get("quotes") or []
                    confidence = got.get("confidence") or ""
                    # AND THE ACCOUNT: everything read about the episode
                    # merged into one record (`sim/episode_account.py`). It is
                    # what she gets in her situation block when it came out at
                    # watched level; the digest below stays the short line the
                    # opener and the impulse read.
                    account = got.get("account") or None
                    if summary and not digest:
                        # the cache answered; the digest is made once here
                        probe = {"title": title, "ja": ja, "ep": ep, "summary": summary}
                        digest = self.digest(probe)
                        scenes = scenes or probe.get("scenes") or []
                        if not digest:
                            summary = ""
                if digest:
                    digest = digest[: int(self.config.watching.digest_max_chars)]
            elif not ja:
                # the romaji title finds database pages and no あらすじ; better
                # to know the episode happened than to fetch the wrong thing
                logger.log(f"[watching] no Japanese title for {title}; no synopsis fetched")
            if parts:
                self.open_her_record(title, parts)
            ent = self._entry(aid) or {}
            self.result = {"anime_id": aid, "title": title, "ja": ja, "ep": ep,
                           "summary": summary, "parts": parts, "role": verdict,
                           "progress": self.progress(aid),
                           "again": bool(item.get("again")),
                           # which EDITION this is, from his own mirror. Both
                           # Example Show entries are エグザンプル, so the line she
                           # reads has to say OVA or TV or it says nothing at
                           # all about which of them he watched.
                           "media_type": mtype or ent.get("type", ""),
                           "total_eps": ent.get("eps", 0),
                           "season": ent.get("season", ""),
                           "resolved_by": how.get("route", ""),
                           # THE FILE HE PLAYED, AND HOW LONG HE SAT IN IT.
                           # Both were used during the fetch and thrown away
                           # with it, so a repair pass -- reading an episode up
                           # again because its account came out thin -- reached
                           # the transcriber with nothing and logged "there is
                           # no file of his to listen to" about a file that was
                           # still on the disk. Nothing already played could
                           # ever become transcript-anchored.
                           "path": str(how.get("path") or ""),
                           "watched": float(item.get("watched") or 0),
                           # when HE PLAYED it, which the poll hands over;
                           # falling back to now only for a caller with no
                           # play time of its own (an ops re-read)
                           "at": float(item.get("at") or 0) or self.clock.now_ts()}
            # made above, once, off the main thread with the fetch; a persona
            # call should never wait on it
            self.result["digest"] = digest
            # Her line stays the digest; the record is wider than her line.
            # The scenes in order, the exact lines a transcript gives, and how
            # far the row was trusted are kept beside it so a question weeks
            # later ("what happened when the cat went missing") has something
            # to answer from other than the digest again.
            self.result["scenes"] = scenes
            self.result["quotes"] = quotes
            self.result["confidence"] = confidence
            # THE ACCOUNT IS NOT CARRIED ON THE ROW, only how complete it came
            # out. It is 1,500 to 4,000 characters and it lives in the
            # machine's own store keyed on the work and the episode, where
            # every character reads the one copy; putting it on
            # `watching_recent` as well would re-serialise twenty-four of them
            # into one key on every play. The renderer fetches the one it
            # needs by (work, episode), which costs a row read.
            self.result["account_level"] = str((account or {}).get("level") or "")
            # and the show is a thing she knows now, found again by its name
            # long after the episode has left the room: the latest episode's
            # digest under the show's Japanese and romaji titles
            if digest:
                try:
                    from sim.known import KnownThings
                    KnownThings(self.config, self.store, self.clock).merge(
                        f"anime:{aid}", [ja, title], "anime", f"第{ep}話", digest, source="watching", show=ja or title)
                except Exception as e:
                    logger.log(f"[known] not kept: {type(e).__name__}")
            # Kept, not handed over once. He watches an episode and may say
            # nothing for an hour; a one-shot result would be thrown away by
            # whichever turn happened to come first, and being able to talk
            # about it later is the whole request.
            # A REPAIR MUST NOT MOVE THE THING IN THE ROOM. Reading up an
            # episode she was told about hours ago fills that episode's
            # record; it does not make it the newest thing he has watched, and
            # it must not reach her a second time, so the moment it reached
            # her, whether it was recorded without a synopsis on purpose, and
            # how many readings-up it has had are carried across with it.
            prior = self._recent_row(aid, ep)
            # a repair carries no play of its own; what the first notice
            # recorded about the play stands
            for k in ("path", "watched"):
                if not self.result.get(k) and prior.get(k):
                    self.result[k] = prior[k]
            self.result["attempts"] = int(item.get("attempts") or prior.get("attempts") or 1)
            if prior.get("attempted_at"):
                self.result["attempted_at"] = prior["attempted_at"]
            if item.get("repair"):
                for k in ("seen_at", "stub"):
                    if prior.get(k):
                        self.result[k] = prior[k]
                held = self.store.get("watching_last", None) or {}
                if not held or (held.get("anime_id") == aid
                                and int(held.get("ep") or 0) == int(ep or 0)):
                    self.store.set("watching_last", self.result)
            else:
                self.store.set("watching_last", self.result)
            # AND THE ROW BESIDE IT, which is what the grouped block is built
            # from: one entry per episode he has played lately, across works,
            # without the wide parts. It was written and read by nothing until
            # the block existed, so an evening of six came out as one episode.
            # A second reading of the same episode replaces the first rather
            # than sitting beside it.
            recent = [r for r in (self.store.get("watching_recent", []) or [])
                      if not (r.get("anime_id") == aid and int(r.get("ep") or 0) == int(ep or 0))]
            recent.append({k: v for k, v in self.result.items()
                           if k not in ("summary", "scenes", "quotes")})
            recent.sort(key=lambda r: float(r.get("at") or 0))
            self.store.set("watching_recent",
                           recent[-int(getattr(self.config.watching, "recent_keep", 24) or 24):])
            self.note_fetch()
            who = (f"; she is {parts[0][0]} in it" if parts else "")
            logger.log(f"[watching] he watched {ja or title} ep{ep}: "
                       f"{len(self.result.get('summary') or '')} chars of あらすじ, "
                       f"digest {len(self.result.get('digest') or '')} chars, "
                       f"{len(scenes)} scene(s)" + (f", {confidence}" if confidence else "")
                       + (f", the account is {account['level']} ({account['chars']} chars)"
                          if account else ", no account of the episode") + who)
        except Exception as e:
            logger.log(f"[watching] failed: {type(e).__name__}")
            self.result = None

    def _recent_row(self, aid, ep):
        """Her own record of one episode, out of the list the grouped block is
        built from."""
        for r in (self.store.get("watching_recent", []) or []):
            if r.get("anime_id") == aid and int(r.get("ep") or 0) == int(ep or 0):
                return dict(r)
        last = self.store.get("watching_last", None) or {}
        if last.get("anime_id") == aid and int(last.get("ep") or 0) == int(ep or 0):
            return dict(last)
        return {}

    def _page_is_there_now(self, row):
        """Has the machine's shared store got a page for this episode since
        her own reading-up failed? Local, no network, no model: it is the
        cheap half of the repair, and when it answers yes the retry costs a
        lookup rather than a search."""
        if self.recap is None:
            return False
        ja = str(row.get("ja") or "").strip()
        if not ja:
            return False
        try:
            got = self.recap._shared_row(ja, int(row.get("ep") or 0), "anime",
                                         row.get("anime_id"), row.get("media_type") or "")
        except Exception:
            return False
        return bool(got and got.get("text"))

    def owed(self):
        """The next episode she was told he watched and never told what is in,
        as an item for `start`, or None.

        A record with no digest and no raw page is a reading-up that lost a
        race rather than an episode nobody looked at: on 2026-09-07 three
        processes reached one episode inside twenty-three seconds, each ran
        its own search, and the two that found nothing had no way back.

        It is tried again as soon as the machine's shared store holds a page
        for it, and otherwise once `sensors.retrievals_retry_after_minutes`
        have passed, at most `sensors.retrievals_max_retries` times for the
        episode. The count of readings-up begun is written on the record
        HERE, as the item is handed over, which is what stops a search that
        keeps failing from being run every poll for ever.

        A row recorded with no synopsis on purpose -- the day's cap was spent
        -- is not owed anything and is left alone."""
        c = self.config.watching
        if not c.enabled:
            return None
        s = self.config.sensors
        allowed = int(getattr(s, "retrievals_max_retries", 2) or 0)
        if allowed <= 0:
            return None
        after = float(getattr(s, "retrievals_retry_after_minutes", 30) or 0) * 60
        if self._fetched_today() >= int(getattr(c, "max_fetches_per_day", 8) or 8):
            return None
        now = self.clock.now_ts()
        rows = list(self.store.get("watching_recent", []) or [])
        last = self.store.get("watching_last", None) or {}
        if last.get("anime_id") and not any(
                r.get("anime_id") == last.get("anime_id")
                and int(r.get("ep") or 0) == int(last.get("ep") or 0) for r in rows):
            rows.append(dict(last))
        # An episode ANOTHER row already says what happens in is not owed
        # anything. A record written before a reading-up replaced its own row
        # can hold two for one episode, one of them empty, and reading that
        # one up again buys a synopsis she already has: the second character
        # paid for four digests and a judge on Mitsudomoe episode 9 that way.
        told = {(r.get("anime_id"), int(r.get("ep") or 0)) for r in rows
                if r.get("digest") or r.get("summary")}
        for row in sorted(rows, key=lambda r: -float(r.get("at") or 0)):
            # AND AN EPISODE WHOSE ACCOUNT CAME OUT THIN IS OWED ONE TOO. A
            # row used to be settled the moment it had a digest, so an episode
            # read up from a single blog post stayed at a single blog post for
            # ever. What she is handed now is the ACCOUNT, and until that is
            # at watched level the record of the episode is not finished --
            # so the same repair pass that fills an empty row fills a thin
            # one, bounded by the same two numbers (`retrievals_max_retries`,
            # `max_fetches_per_day`) and by the same fact that a show only two
            # people ever wrote about stops improving and is left alone.
            thin = self._account_wanted(row)
            if row.get("stub") or ((row.get("digest") or row.get("summary")) and not thin):
                continue
            if (row.get("anime_id"), int(row.get("ep") or 0)) in told and not thin:
                continue
            if not row.get("anime_id") or not str(row.get("ja") or "").strip():
                continue
            done = int(row.get("attempts") or 1)
            if done > allowed:
                continue
            free = self._page_is_there_now(row)
            if not free:
                since = float(row.get("attempted_at") or row.get("at") or 0)
                if after and (now - since) < after:
                    continue
            self._note_attempt(row.get("anime_id"), int(row.get("ep") or 0), done + 1, now)
            logger.log(f"[watching] {row.get('ja') or row.get('title')} ep{row.get('ep')} was "
                       f"recorded with no synopsis; reading it up again (attempt {done + 1} of "
                       f"{allowed + 1})"
                       + (" (the account of it is not finished)" if thin and row.get("digest") else "")
                       + (" -- the machine's store has a page for it now" if free else
                          f" -- {(now - float(row.get('attempted_at') or row.get('at') or 0)) / 60:.0f} min "
                          f"since the last try"))
            # THE FILE HE PLAYED GOES BACK WITH IT. A repair used to hand the
            # reading-up an empty `how`, so the subtitle path was asked about
            # an episode with no file behind it and answered "there is no file
            # of his to listen to" -- and nothing he had already watched could
            # ever be transcribed, however long the record of it stayed thin.
            # Only a file still on the disk, and the seconds he sat through it,
            # which is what the transcriber's own floor is measured against.
            video = str(row.get("path") or "")
            if video and not os.path.exists(video):
                logger.log(f"[watching] the file he played {row.get('ja') or row.get('title')} "
                           f"ep{row.get('ep')} from is no longer on the disk; the reading-up "
                           f"has the pages only")
                video = ""
            # HOW LONG HE SAT IN IT, which is what the transcriber's own floor
            # is measured against. A row written before the row carried that
            # number still says it: an episode noticed through the player is
            # only recorded once it has passed the same gate, so the gate is
            # the least he watched of it and never more than he did.
            watched = float(row.get("watched") or 0)
            if video and not watched:
                watched = float(getattr(c, "min_watched_minutes", 0) or 0) * 60
            return {"anime_id": row.get("anime_id"), "title": row.get("title", ""),
                    "ep": int(row.get("ep") or 0), "again": False, "repair": True,
                    "at": float(row.get("at") or 0), "watched": watched,
                    "how": {"path": video} if video else {},
                    "attempts": done + 1}
        return None

    def _note_attempt(self, aid, ep, n, when):
        """One more reading-up begun for this episode, on the record before it
        runs."""
        rows = self.store.get("watching_recent", []) or []
        changed = False
        for r in rows:
            if r.get("anime_id") == aid and int(r.get("ep") or 0) == int(ep or 0):
                r["attempts"], r["attempted_at"] = int(n), float(when)
                changed = True
        if changed:
            self.store.set("watching_recent", rows)
        last = self.store.get("watching_last", None) or {}
        if last.get("anime_id") == aid and int(last.get("ep") or 0) == int(ep or 0):
            last["attempts"], last["attempted_at"] = int(n), float(when)
            self.store.set("watching_last", last)

    def impulse_bonus(self):
        """How much this makes her want to say something first, added to the
        impulse score rather than going round it.

        Two restraints, and only the first is new. **Nothing at all while he
        is still watching**: a settle window means an evening of six episodes
        is one reason to speak at the end of it, not six interruptions
        through it. And everything the impulse already refuses on still
        applies -- the daily cap, the cooldown, going cold on him, and
        `he has not answered the last ones` -- which is the honest answer to
        being ignored: she notices what he is doing and says nothing, because
        the same restraint governs this as governs everything else.
        """
        c = self.config.watching
        it = self.current()
        if not it or not c.enabled:
            return 0.0
        key = f"{it.get('anime_id')}:{it.get('ep')}"
        if key in (self.store.get("watching_spoken", []) or []):
            return 0.0
        try:
            # from when it reached HER, which for a character who finds it in
            # a snapshot she went and fetched is her look, not his play
            since = self.clock.now_ts() - float(it.get("seen_at", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
        if since < float(c.settle_minutes) * 60:
            return 0.0
        # The timer above is the fallback for a player that reports nothing --
        # a browser, another machine. When mpv IS reporting, it is better than
        # a timer in both directions: still running means he is mid-episode
        # however long ago this one ended, and the file going quiet means he
        # has stopped even if the window has not passed.
        try:
            np = self.now_playing()
        except Exception:
            np = None
        if np and not np.get("paused"):
            return 0.0
        # her own work is a reason to speak; anything else is a small one, and
        # a series he has just finished is worth a word either way
        pr = it.get("progress") or None
        done = bool(pr and pr[1] and pr[0] >= pr[1])
        if it.get("parts"):
            return float(c.impulse_bonus_hers)
        return float(c.impulse_bonus_finished if done else c.impulse_bonus_any)

    def note_spoken(self):
        """She has reached out while this episode was the thing in the room.
        Whatever she actually said, it does not get to be the reason twice."""
        it = self.store.get("watching_last", None)
        if not it:
            return
        key = f"{it.get('anime_id')}:{it.get('ep')}"
        spoken = self.store.get("watching_spoken", []) or []
        if key not in spoken:
            self.store.set("watching_spoken", (spoken + [key])[-40:])

    def note_seen(self, at_play=False):
        """The episode the module read up on has now reached her.

        WHICH MOMENT that is belongs to the program, not to this library. A
        character who is on his machine sees the file open, so her moment is
        his play itself (`at_play`), and nothing about her changes. A
        character who learns what he is doing in snapshots she has to go and
        fetch comes across it in the next one, and that is her moment: the
        freshness window and the settle window before it can be a reason to
        write first are both counted from here.

        Marked once per episode, so the program may call it every pass.

        **EVERY episode she has not been told about yet is marked, not only
        the newest**, because one look at what he has been doing shows her all
        of it: an evening of six and a day of three works reach her together
        and the grouped block is what she reads them in. They share the moment,
        which is what makes "everything since her last look" a set she can be
        shown at once.

        `watching.discover_hours` is the AGE AT WHICH AN UNSEEN PLAY IS
        DROPPED, not the window the block covers: what she goes and fetches is
        what he has been doing lately, not a transcript of the week. The block
        itself covers everything since her last look at it (`recent`, which
        counts from the moment they reached her). The show is still hers by
        name (`sim/known.py`) whenever he mentions it, whatever this refuses."""
        now = self.clock.now_ts()
        window = float(getattr(self.config.watching, "discover_hours", 0) or 0) * 3600
        marked = []

        def _seen_at(row):
            at = float(row.get("at", 0) or 0)
            if at_play:
                return at or now
            if window and at and (now - at) > window:
                return 0.0
            return now

        it = self.store.get("watching_last", None)
        if it and not it.get("seen_at"):
            seen = _seen_at(it)
            if seen:
                it["seen_at"] = seen
                self.store.set("watching_last", it)
                marked.append((it, seen))
        rec = self.store.get("watching_recent", []) or []
        changed = False
        for row in rec:
            if row.get("seen_at"):
                continue
            seen = _seen_at(row)
            if not seen:
                continue
            row["seen_at"] = seen
            changed = True
            if not (it and row.get("anime_id") == it.get("anime_id")
                    and int(row.get("ep") or 0) == int(it.get("ep") or 0)):
                marked.append((row, seen))
        if changed:
            self.store.set("watching_recent", rec)
        if not marked:
            return False
        for row, seen in marked:
            at = float(row.get("at", 0) or 0)
            logger.log(f"[watching] {row.get('ja') or row.get('title')} ep{row.get('ep')} has reached her"
                       + ("" if at_play else f", {int((now - at) / 60)} min after he played it")
                       + (" (no synopsis; the day's cap)" if row.get("stub") else ""))
        return True

    def current(self):
        """The last episode he watched, once it has reached her and while it
        is still recent enough to be the thing in the room. After that it is
        something that happened, and her ordinary memory carries it or does
        not.

        Recent is counted from when it reached her (`note_seen`), not from his
        play: for a character who finds it hours later those are two different
        times and the one that matters is hers."""
        c = self.config.watching
        if not c.enabled:
            return None
        it = self.store.get("watching_last", None)
        if not it:
            return None
        seen = float(it.get("seen_at", 0) or 0)
        if not seen:
            # read up in the background while she was elsewhere; her program
            # has not put it in front of her yet
            return None
        age = self.clock.now_ts() - seen
        if age > float(c.fresh_hours) * 3600:
            return None
        # an episode fetched before the digest existed gets one on first use,
        # and keeps it
        if it.get("summary") and not it.get("digest") and self.llm is not None:
            dg = self.digest(it)
            if dg:
                it["digest"] = dg
                self.store.set("watching_last", it)
            elif not it.get("summary"):
                # the role rejected the stored page (an episode fetched before
                # pages were judged): keep the rejection and re-read it off
                # the main thread with the judged fetch
                self.store.set("watching_last", it)
                self.start({"anime_id": it.get("anime_id"), "title": it.get("title"), "ep": it.get("ep")})
        return it

    # ---------------- what she can say about it ----------------

    # ---------------- everything he has watched since she last looked -------

    # A part of the day is `world/clock.py`'s word; the preposition in front
    # of it is this line's. "in the {daypart}" is right for four of the eight
    # and wrong for the rest -- "in the the middle of the night", "in the late
    # at night" -- so each has its own form, and a word the clock adds later
    # falls back to the plain one rather than breaking the line. Japanese
    # needs none of this: 「今日の真夜中」 works for every one of them.
    _WHEN_EN = {"the middle of the night": "in the middle of the night",
                "early morning": "first thing in the morning",
                "morning": "in the morning",
                "midday": "around midday",
                "afternoon": "in the afternoon",
                "evening": "in the evening",
                "night": "at night",
                "late at night": "late at night"}

    def played_words(self, ts, ja=False):
        """When he played it, on HER clock, in words: "yesterday, in the
        afternoon".

        Never a stamp and never a count of hours. The block is rebuilt on
        every reply, and a number that ticks would change its bytes every
        time; these words change once a day and once a part of a day, which
        is as often as the fact behind them changes."""
        t = lang.pick(ja)
        try:
            at = float(ts or 0)
        except (TypeError, ValueError):
            at = 0.0
        # A row with no play time on it is one just handed over; the words
        # are never empty, because a line built round them would read
        # "he watched it on his machine, " and stop.
        if not at:
            return t("just now", "いましがた")
        try:
            then = self.clock.to_char(at)
            now = self.clock.now()
        except (ValueError, OSError, OverflowError):
            return t("just now", "いましがた")
        dp = _daypart(then.hour, ja)
        part = dp if ja else self._WHEN_EN.get(dp, f"in the {dp}")
        days = (now.date() - then.date()).days
        if days <= 0:
            return t(f"today, {part}", f"今日の{part}")
        if days == 1:
            return t(f"yesterday, {part}", f"昨日の{part}")
        if days < 7:
            return t(f"{days} days ago, {part}", f"{days}日前の{part}")
        return t("over a week ago", "一週間以上前")

    @staticmethod
    def _gist(text, n):
        """What happens in one episode, in one clause: up to its first full
        stop, cut at `n`. An episode that is not the newest of a run is NAMED,
        not retold -- six digests in a row is a reading list, and what she
        needs is that he sat through a stretch and roughly what was in it."""
        s = " ".join(str(text or "").split())
        if not s:
            return ""
        for stop, keep in (("。", 1), (". ", 1)):
            i = s.find(stop)
            if 0 < i <= n:
                return s[: i + keep]
        return s[:n].rstrip() + ("…" if len(s) > n else "")

    def _arc(self, rows, ja=False):
        """The earlier episodes of a run, in order, one clause each."""
        rows = [r for r in (rows or []) if r]
        if not rows:
            return ""
        t = lang.pick(ja)
        half = int(getattr(self.config.watching, "recent_max_chars", 1200) or 1200) / 2.0
        share = max(60, int(half / max(1, len(rows))))
        bits = []
        for r in sorted(rows, key=lambda x: int(x.get("ep") or 0)):
            n = int(r.get("ep") or 0)
            g = self._gist(r.get("digest"), share)
            bits.append(t(f"ep {n}: {g}", f"第{n}話：{g}") if g else
                        t(f"ep {n}: (he watched it; it was never read up on)",
                          f"第{n}話：（観てはいる。中身は調べていない）"))
        return " / ".join(bits)

    def recent(self):
        """Every episode that has reached her and is still the thing in the
        room, newest play first, one row per (work, episode).

        **This is the window the grouped block covers: everything since her
        last look at it.** One look marks every unseen episode with the same
        moment (`note_seen`), and `watching.fresh_hours` runs from there, so
        what arrived together stays together and leaves together.
        `watching.discover_hours` is a different rule and not this one: it is
        the age past which an unseen play is never marked at all."""
        c = self.config.watching
        if not c.enabled:
            return []
        now = self.clock.now_ts()
        fresh = float(getattr(c, "fresh_hours", 6) or 6) * 3600
        last = self.store.get("watching_last", None) or {}
        rows = list(self.store.get("watching_recent", []) or [])
        if last.get("seen_at") and not any(
                r.get("anime_id") == last.get("anime_id")
                and int(r.get("ep") or 0) == int(last.get("ep") or 0) for r in rows):
            # a stop between the two writes: the record beside it is missing
            # the newest episode, and she should still be shown it
            rows.append(last)
        best = {}
        for r in rows:
            seen = float(r.get("seen_at", 0) or 0)
            if not seen or (now - seen) > fresh:
                continue
            row = dict(r)
            if (last.get("seen_at") and row.get("anime_id") == last.get("anime_id")
                    and int(row.get("ep") or 0) == int(last.get("ep") or 0)):
                # the same episode's live row, which `current()` may have given
                # a digest since this snapshot of it was taken
                row = {k: v for k, v in last.items() if k not in ("scenes", "quotes")}
            key = f"{row.get('anime_id')}:{int(row.get('ep') or 0)}"
            if key not in best or float(row.get("at") or 0) >= float(best[key].get("at") or 0):
                best[key] = row
        return sorted(self._one_play_once(best.values()),
                      key=lambda r: float(r.get("at") or 0), reverse=True)

    def provisional_facts(self, ja=False):
        """`(what he watched, one line about it)` per episode she has been
        shown that her permanent record of him does not hold yet, newest
        first. The name comes back beside the line so the section that places
        it can tell whether a fact it already holds is about the same thing.

        THE HOLE THIS FILLS. What he watched reaches her in the block about
        his watching, which is a window (`watching.fresh_hours`) around the
        moment he was in it -- and it becomes a lasting fact about him at the
        end-of-day compile, which is once a day. Between the two there is a
        stretch of hours where she has been told and has nothing left of it:
        on 2026-09-08 the first character agreed with him that he hardly
        watches anime any more, twelve hours after being shown him playing an
        episode and half an hour before the compile that would have written
        it down (HISTORY.md section 5.16).

        So while the day a play falls on has no compiled record yet, the play
        is offered as a plain sentence for the section of facts about him.
        Nothing is written: the moment the day is compiled these lines stop
        being produced, and what stays is whatever the compile kept. Only
        today and yesterday on her clock, so a day whose compile failed does
        not leave a line standing for ever.
        """
        c = self.config.watching
        if not c.enabled:
            return []
        t = lang.pick(ja)
        rows = list(self.store.get("watching_recent", []) or [])
        last = self.store.get("watching_last", None) or {}
        if last:
            rows.append(last)
        try:
            today = self.clock.to_char(self.clock.now_ts()).date()
        except (ValueError, OSError, OverflowError):
            return []
        compiled, out, done = {}, [], set()
        for r in sorted(rows, key=lambda r: -float(r.get("at") or 0)):
            if not float(r.get("seen_at") or 0):
                continue
            at = float(r.get("at") or 0) or float(r.get("seen_at") or 0)
            try:
                day = self.clock.to_char(at).date()
            except (ValueError, OSError, OverflowError):
                continue
            if not 0 <= (today - day).days <= 1:
                continue
            key = day.isoformat()
            if key not in compiled:
                compiled[key] = self.store.get_day(key) is not None
            if compiled[key]:
                continue
            ep = int(r.get("ep") or 0)
            seen = f"{r.get('anime_id')}:{ep}"
            if seen in done:
                continue
            done.add(seen)
            name = (r.get("ja") or r.get("title")) if ja else (r.get("title") or r.get("ja"))
            if not name:
                continue
            when = self.played_words(r.get("at"), ja=ja)
            out.append((name, t(f"He watched {name}"
                                + (f" episode {ep}" if ep else "") + f" -- {when}.",
                                f"彼は{when}、{name}"
                                + (f"の第{ep}話" if ep else "") + "を観ていた。")))
        return out[: int(getattr(c, "recent_works", 3) or 3)]

    @staticmethod
    def _one_play_once(rows):
        """One play is one row, even when it was filed under two ids.

        A play resolved from the filename is written under the work the
        filename meant, and his list may name a different id half an hour
        later; both rows are in the record. Two entries of his list share the
        Japanese title エグザンプル, so the two rows would come out as two
        works and she would be told he watched the same episode of the same
        show twice in an hour. Same name, same episode number, inside an hour:
        one play, and the later row is the corrected one. A real rewatch is
        days apart and is not touched."""
        out = []
        for r in sorted(rows, key=lambda r: float(r.get("at") or 0)):
            name = str(r.get("ja") or r.get("title") or "")
            ep = int(r.get("ep") or 0)
            at = float(r.get("at") or 0)
            for i, kept in enumerate(out):
                if (str(kept.get("ja") or kept.get("title") or "") == name
                        and int(kept.get("ep") or 0) == ep
                        and abs(at - float(kept.get("at") or 0)) < 3600):
                    out[i] = r
                    break
            else:
                out.append(r)
        return out

    @staticmethod
    def _grouped(rows):
        """The same rows by WORK, newest play first, each work's episodes in
        order. A work with no id on his list is grouped by its title, which is
        what her own watchlist has."""
        works = {}
        for r in rows:
            key = r.get("anime_id") or ("title:" + str(r.get("title") or ""))
            works.setdefault(key, []).append(r)
        out = []
        for key, rs in works.items():
            rs.sort(key=lambda r: int(r.get("ep") or 0))
            out.append({"key": key, "eps": rs,
                        "at": max(float(r.get("at") or 0) for r in rs)})
        out.sort(key=lambda g: -g["at"])
        return out

    @staticmethod
    def _name_of(group):
        """What to call the work: its Japanese title from whichever of its
        episodes was read up on, and its romaji title otherwise. An episode
        recorded without a synopsis has no Japanese title of its own -- the
        poll does not go to the network -- and takes the name from its
        neighbours."""
        for r in reversed(group["eps"]):
            if r.get("ja"):
                return r["ja"]
        for r in reversed(group["eps"]):
            if r.get("title"):
                return r["title"]
        return ""

    def _also_line(self, group, ja=False):
        """One work that is not the newest: what it was, how much of it, when
        on her clock, and one clause of the newest episode of it."""
        t = lang.pick(ja)
        eps = group["eps"]
        newest = eps[-1]
        a, b = int(eps[0].get("ep") or 0), int(eps[-1].get("ep") or 0)
        eps_words = (t(f"episode {a}", f"第{a}話") if a == b else
                     t(f"episodes {a} to {b}", f"第{a}話から第{b}話まで"))
        share = max(80, int(getattr(self.config.watching, "recent_max_chars", 1200) or 1200) // 4)
        gist = self._gist(newest.get("digest"), share) or \
            t("(you know he watched it; it was never read up on)",
              "（観たのは分かる。中身は調べていない）")
        return t(*sight.w2(self.config, "watching_also_opener",
                           n=self._name_of(group), ed=self._edition_words(newest, t),
                           eps=eps_words, when=self.played_words(newest.get("at"), ja=ja))) + gist

    def grouped_lines(self, ja=False):
        """What she is shown about his watching: ONE LINE PER WORK, newest
        play first, over everything that has reached her since her last look.

        Her line used to be the newest episode and nothing else, so an evening
        of six episodes came out as one episode and a day of three works came
        out as the last of them -- the two before it vanished from her block
        the moment the third landed, whether or not she had ever said anything
        about them.

        The newest work keeps the whole shape it has always had, including its
        digest whole: it is the one he has just come out of. Its earlier
        episodes become one clause each after it. Every other work is one
        line: what it was, the episode or the range, when on her clock, and
        one clause of what happened. `watching.recent_works` caps how many
        works, `watching.recent_max_chars` caps what the grouping ADDS to the
        line she already had, and the oldest work goes first."""
        c = self.config.watching
        if not c.enabled:
            return []
        # `current()` is what gives an episode fetched before the digest
        # existed one on first use, so it runs whether or not it is the row
        # this block is built around
        it = self.current()
        rows = self.recent()
        if not rows:
            return self.situation_lines(it, ja=ja) if it else []
        groups = self._grouped(rows)
        if len(groups) == 1 and len(groups[0]["eps"]) == 1:
            # one work, one episode: the line she has always had, byte for byte
            return self.situation_lines(it or groups[0]["eps"][0], ja=ja)
        t = lang.pick(ja)
        budget = int(getattr(c, "recent_max_chars", 1200) or 1200)
        dropped = max(0, len(groups) - int(getattr(c, "recent_works", 3) or 3))
        groups = groups[: int(getattr(c, "recent_works", 3) or 3)]
        eps = groups[0]["eps"]
        newest = eps[-1]
        if (it and it.get("anime_id") == newest.get("anime_id")
                and int(it.get("ep") or 0) == int(newest.get("ep") or 0)):
            newest = it
        run = (int(eps[0].get("ep") or 0), int(eps[-1].get("ep") or 0)) if len(eps) > 1 else None
        out = list(self.situation_lines(newest, ja=ja, run=run, others=eps[:-1]))
        used = len(out[-1]) if (len(eps) > 1 and out) else 0
        for g in groups[1:]:
            line = self._also_line(g, ja=ja)
            if not line or used + len(line) > budget:
                dropped += 1
                continue
            used += len(line)
            out.append(line)
        if dropped:
            out.append(t(f"({dropped} other thing(s) he has watched in the same stretch, further "
                         f"back: you know he has been going through things, not what was in them)",
                         f"（同じ流れでほかにも{dropped}本観ている。もっと前のぶんで、"
                         f"観ているのは分かるが、中身までは知らない）"))
        return out

    def _account_for(self, it):
        """The stored account of one episode when it came out at WATCHED
        level, else None.

        A thinner one is deliberately refused. The wording that goes with an
        account says she knows the episode the way somebody who sat through it
        knows it, and a `read-up` account is one blogger's post again -- so it
        goes back to the digest line, which says out loud that she has only
        read a synopsis. The record is still on file either way; this decides
        only which of the two things she is told she has.

        A read of her save and, at most once per episode, of the machine's --
        no fetch and no model call, because this is the reply path."""
        if self.recap is None or not it:
            return None
        accounts = getattr(self.recap, "accounts", None)
        if accounts is None or not accounts.enabled():
            return None
        ja = str(it.get("ja") or "").strip()
        if not ja or not it.get("ep"):
            return None
        try:
            row = self.recap.account({"ja": ja, "title": it.get("title", ""),
                                      "aid": it.get("anime_id"),
                                      "mtype": it.get("media_type", "")},
                                     int(it.get("ep") or 0))
        except Exception as e:
            logger.log(f"[watching] the account of {ja} ep{it.get('ep')} did not read: "
                       f"{type(e).__name__}")
            return None
        return row if accounts.complete(row) else None

    def _account_wanted(self, row):
        """Whether this episode's record is still short of watched level, and
        the repair pass should therefore read it up again.

        The row carries the level as of its last reading (`account_level`),
        which costs nothing to read; the store is asked only for a row written
        before accounts existed, which is every row on both saves today."""
        if self.recap is None:
            return False
        accounts = getattr(self.recap, "accounts", None)
        if accounts is None or not accounts.enabled():
            return False
        level = str(row.get("account_level") or "")
        if level:
            return level != "watched"
        return self._account_for(row) is None

    def _run_accounts(self, others, ja=False, t=None):
        """The rest of a run he sat through, for the case where the newest
        episode's whole account is in the block.

        The one before it gets its account too (`watching.account_recent`,
        oldest dropped first, under `account_recent_max_chars`); everything
        further back is one clause each in the arc, as it has always been. Six
        episodes in an evening must not put six accounts in one prompt, and
        the arc is what says he sat through a stretch of it."""
        rows = [r for r in (others or []) if r]
        if not rows:
            return []
        c = self.config.watching
        want = max(0, int(getattr(c, "account_recent", 2) or 2) - 1)
        budget = int(getattr(c, "account_recent_max_chars", 6000) or 6000)
        taken = []
        for row in reversed(rows):
            if len(taken) >= want:
                break
            acct = self._account_for(row)
            if not acct:
                continue
            body = self.recap.accounts.situation_text(acct, ja=ja)
            if not body or len(body) > budget:
                break
            budget -= len(body)
            taken.append((row, body))
        out = []
        for row, body in reversed(taken):
            out.append(t(f"and episode {row.get('ep')}, just before it in the same stretch: ",
                         f"同じ流れでその直前の第{row.get('ep')}話: ") + body)
        done = {id(r) for r, _b in taken}
        arc = self._arc([r for r in rows if id(r) not in done], ja=ja)
        if arc:
            out.append(t(f"the episodes before that, in order, in the same stretch: {arc}",
                         f"同じ流れでその前に観た話（順に）: {arc}"))
        return out

    def situation_lines(self, item=None, ja=False, run=None, others=()):
        """The tagged text for her situation: what he watched, what happens in
        it, and her own part if she has one. Wording matters more than usual
        here -- handed a synopsis, a model recites it, and what is wanted is a
        person who has seen the episode.

        `run` is `(first, last)` when he did not stop at one: the opener then
        names the range rather than the single episode, and `others` -- the
        earlier episodes of the same run, in order -- become one line of what
        happened in each, after the newest one's own synopsis. Everything else
        about the line is the same, which is the point of the parameter: a run
        should not be a second renderer with its own drift."""
        t = lang.pick(ja)
        it = item or {}
        if not it:
            return []
        c = self.config.watching
        name = it.get("ja") or it.get("title") or ""
        ep = it.get("ep")
        # Where he is in it, which is most of what there is to say about a
        # person watching something. "Episode 5" alone cannot tell the
        # difference between him trying a series out, being deep in it, and
        # finishing it -- and those are three different conversations.
        pr = it.get("progress") or None
        where = ""
        if pr:
            marked, total, status = int(pr[0] or 0), int(pr[1] or 0), (pr[2] if len(pr) > 2 else 0)
            ep_n = int(ep or 0)
            # He plays ahead of what he marks -- episode 9 open while the list
            # still says 8 -- so the episode in front of him is the better
            # answer to where he is than the number he has got round to
            # ticking. Unless he is a long way BEHIND what he has marked, in
            # which case he is watching it again, and saying "that was the
            # last one, he has finished it" over episode 1 of a rewatch is
            # simply wrong.
            again = total and marked >= total and ep_n and ep_n < total - 1
            watched = max(marked, ep_n)
            if it.get("again") and not again:
                # this one episode counted before, opened again past the
                # window (`watching.rewatch_after_hours`): a rewatch of one
                where = t(" -- he has seen this one before, and is watching it again",
                          " -- 彼はこの話を前に観ていて、いまもう一度観ている")
                again = True
            elif again:
                where = t(f" -- he has seen it before, all {total}, and is going through it again",
                          f" -- 彼は前に全{total}話を観ていて、いまもう一度観ている")
            elif total and watched >= total:
                where = t(f", and that was the last one -- he has finished it ({total} episodes)",
                          f"。これが最終話で、彼は観終わった（全{total}話）")
            elif total:
                left = total - watched
                where = (t(f" -- he is {watched} of {total} in", f" -- 全{total}話のうち{watched}話まで")
                         + (t(", only just started", "、始めたばかり") if watched <= 2 else
                            t(f", {left} left", f"、残り{left}話") if left <= 3 else ""))
            if status == 3 and not again:
                where += t(" (it has been sitting on hold)", "（しばらく止まったまま）")
        # Whether he is still in it right now, which is the one thing the
        # sequence of events cannot say, because he pauses. It also fixes the
        # tense: "he has just watched" is wrong while it is still running.
        #
        # Only for a character who is ON his machine. Where the file has got
        # to this second is a live view of his desk, and a character whose
        # sheet says she learns what he does from snapshots she has to go and
        # fetch has no way to hold it -- she would be telling him she can see
        # his player paused twelve minutes in. The predicate is the sheet's
        # (`existence.sees_him`), the same one `Phone.live_line` reads, and
        # never the program's.
        np = None
        if self.config.resident:
            try:
                np = self.now_playing()
            except Exception:
                np = None
        same = bool(np and np.get("anime_id") and np["anime_id"] == it.get("anime_id")
                    and np.get("ep") == ep)
        if np and not same and np.get("ep") == ep:
            # The file open may not resolve to a show on his list -- his own
            # naming is looser than the matcher -- and then she would say "he
            # has <romaji> paused" one line under "he has <the same show in
            # Japanese> open", which reads as two different programmes.
            a = re.sub(r"[^a-z0-9]", "", str(np.get("title") or "").lower())
            b = re.sub(r"[^a-z0-9]", "", str(it.get("title") or "").lower())
            same = bool(a and b and (a in b or b in a))
        # How it came to be in front of her -- his own machine, or something
        # that told her about it hours afterwards -- is the program's wording
        # (`tomoe/words.py`, `resident/words.py`). The delay is said out loud,
        # because a character who did not see it happen must not talk as
        # though she had just been sitting beside him.
        ago = ""
        try:
            gap = (self.clock.now_ts() - float(it.get("at", 0) or 0)) / 3600.0
        except (TypeError, ValueError):
            gap = 0.0
        if gap >= 0.75:
            ago = (t(f" -- he watched it about {int(round(gap))} hours ago",
                     f" -- 彼が観たのは{int(round(gap))}時間ほど前")
                   if gap < 20 else
                   t(" -- he watched it about a day ago", " -- 彼が観たのは一日ほど前"))
        # WHICH EDITION, in the line itself. MyAnimeList gives the 2006
        # one-episode OVA and the 2007 television run the identical Japanese
        # title エグザンプル, so a line built from the title and the episode
        # number cannot say which of them he watched -- and on 2026-09-04 her
        # first draft had it right from another line and the rewrite lost it.
        # Both programs' wording tables take `{ed}`.
        ed = self._edition_words(it, t)
        when = self.played_words(it.get("at"), ja=ja)
        if run and int(run[0] or 0) != int(run[1] or 0):
            opener = t(*sight.w2(self.config, "watching_run_opener", n=name,
                                 a=int(run[0]), b=int(run[1]), w=where, ago=ago,
                                 ed=ed, when=when))
        else:
            opener = t(*sight.w2(self.config, "watching_opener_open" if same else "watching_opener_played",
                                 n=name, e=ep, w=where, ago=ago, ed=ed, when=when))
        out = [opener + t(*sight.w2(self.config, "watching_unmentioned"))]
        if np and np.get("dur"):
            mins = int(np["pos"] // 60)
            left_s = np["dur"] - np["pos"]
            what = t("it", "それ") if same else (np.get("title") or t("something else", "別の何か"))
            if np.get("paused"):
                out.append(t(f"he has {what} paused right now, {mins} minutes in "
                             f"of {int(np['dur'] // 60)} ({np['pct']:.0f}% through). "
                             f"he stopped it and is doing something else",
                             f"彼はいま{what}を一時停止している。{int(np['dur'] // 60)}分のうち{mins}分"
                             f"（{np['pct']:.0f}%）のところ。止めて別のことをしている"))
            else:
                how_far = (t("and it is nearly over", "もうすぐ終わる") if left_s < 120 else
                           t(f"about {int(left_s // 60)} minutes left", f"残り{int(left_s // 60)}分ほど"))
                out.append(t(f"he is watching {what} right now, {mins} minutes in, "
                             f"{np['pct']:.0f}% through, {how_far}. "
                             f"he is in the middle of it -- he is not sitting "
                             f"waiting for you to say something",
                             f"彼はいま{what}を観ている。{mins}分のところ、{np['pct']:.0f}%、{how_far}。"
                             f"途中なので、あなたが何か言うのを待って座っているわけではない"))
        # Whether it is hers, and whether it is NOT. The second half is the
        # half that was missing: this block emitted a positive when the cast
        # table found a part and said nothing at all otherwise, so a work she
        # has never been in reached her exactly as one nobody had checked
        # did, and on 2026-09-04 she claimed a part in one.
        #
        # The verdict's own wording carries the year and covers the works of
        # hers the cast table misses; the hardcoded pair below it is what a
        # character with a name on the cast rows and no person id still gets.
        parts = it.get("parts") or []
        v = it.get("role") or None
        said = works.verdict_line(self.config, v, name, t) if v else ""
        if said:
            out.append(said)
        elif parts:
            who = "、".join(f"{_person_name(ch)}（{_ROLE_JA.get(role, role)}）"
                            for ch, role in parts[:2])
            out.append(t(f"you are in this one: you play {who} in {name}. "
                         f"it is your own work, so you know it from the inside -- "
                         f"the booth, the direction, what the part asked of you -- "
                         f"and not as a viewer",
                         f"これはあなたが出ている作品。『{name}』で{who}をやっている。"
                         f"自分の仕事なので、観る側としてではなく中から知っている——"
                         f"ブースのこと、演出のつけられ方、その役に求められたこと"))
        # THE ACCOUNT WHEN THERE IS A COMPLETE ONE, and it is not cut. Every
        # scene of the episode in order, the parts, the running jokes, the
        # lines, what it points at (`sim/episode_account.py`). Below it, what
        # this line has always been: the 600-character digest, and the cut of
        # the raw page only when the digest could not be made.
        #
        # The wording is the program's and differs between the two cases,
        # because they are different claims. With the account she knows the
        # episode the way somebody who sat through it knows it and may talk
        # about any part of it; with the digest she has skimmed a synopsis and
        # must say so. The old line said "you have only the synopsis" in both.
        acct = self._account_for(it) if bool(getattr(c, "account_in_prompt", True)) else None
        if acct:
            out.append(t(*sight.w2(self.config,
                                   "watching_account_open" if same else "watching_account_played",
                                   n=name, e=ep, ed=ed))
                       + self.recap.accounts.situation_text(acct, ja=ja))
            out += self._run_accounts(others, ja=ja, t=t)
            return out
        s = str(it.get("digest") or "") or str(it.get("summary") or "")[: int(c.summary_max_chars)]
        if s:
            # It used to say "react to it as something you have seen", and she
            # did: 「ゆかりも見たことあるよ」 about a show from years after her
            # own time, and 「展開まで覚えてるの」 to a man who was seven minutes
            # into the episode. She read this up just now, while he watches;
            # what he says about it is what is in front of him, not memory.
            # And the tense here follows the opener: "he is in the middle of it"
            # was said whether or not he was, and she told a man who had
            # finished the episode half an hour before that she could see his
            # screen paused on it.
            # The synopsis itself is appended rather than formatted into
            # the phrase: it is scraped prose and a stray brace in it would
            # take the whole situation block down.
            out.append(t(*sight.w2(self.config,
                                   "watching_synopsis_open" if same else "watching_synopsis_played",
                                   n=name, e=ep, ed=ed)) + s)
        # THE REST OF THE RUN, as an arc rather than as five more synopses.
        # The newest episode keeps its digest whole because it is the one he
        # has just come out of; what led to it is one clause each, in order,
        # so she can tell that he sat through a stretch of it and roughly what
        # happened in that stretch. No model call: this is on the reply path.
        arc = self._arc(others, ja=ja)
        if arc:
            out.append(t(f"the episodes before it, in order, in the same stretch: {arc}",
                         f"同じ流れでその前に観た話（順に）: {arc}"))
        return out

    # How his own list writes an edition, and how a person says it
    _EDITION = {"tv": ("the TV series", "テレビシリーズ"), "ova": ("the OVA", "OVA"),
                "oad": ("the OAD", "OAD"), "ona": ("the ONA", "ONA"),
                "special": ("the special", "スペシャル"),
                "tv_special": ("the TV special", "テレビスペシャル"),
                "movie": ("the film", "劇場版"), "music": ("the music video", "ミュージックビデオ")}

    def _edition_words(self, it, t):
        """" (the OVA)" or "" -- which edition of a franchise this is, said
        out loud only when it is worth saying.

        A one-episode OVA and a 26-episode television run under one Japanese
        title are two works, and the edition is the only thing in the line
        that separates them. A television series with nothing else beside it
        needs no label, so an entry whose type is `tv` says nothing unless
        the episode count makes it worth stating."""
        mt = str(it.get("media_type") or "").lower()
        pair = self._EDITION.get(mt)
        if not pair or mt in ("tv",):
            return ""
        total = int(it.get("total_eps") or 0)
        if mt == "movie":
            total = 0      # a film's "1 episode" is the film
        en, ja = pair
        season = str(it.get("season") or "")
        bits_en = [en] + ([f"{total} episode" + ("s" if total != 1 else "")] if total else []) \
            + ([season] if season else [])
        ja_season = self._season_ja(season)
        bits_ja = [ja] + ([f"全{total}話"] if total else []) + ([ja_season] if ja_season else [])
        return t(" (" + ", ".join(bits_en) + ")", "（" + "・".join(bits_ja) + "）")

    # his mirror writes a season in English; a line addressed to a character
    # who writes Japanese says it in hers
    _SEASONS = {"winter": "冬", "spring": "春", "summer": "夏", "fall": "秋", "autumn": "秋"}

    @classmethod
    def _season_ja(cls, season):
        m = re.match(r"([a-z]+)\s+(\d{4})", str(season or "").strip().lower())
        if not m or m.group(1) not in cls._SEASONS:
            return str(season or "")
        return f"{m.group(2)}年{cls._SEASONS[m.group(1)]}"
