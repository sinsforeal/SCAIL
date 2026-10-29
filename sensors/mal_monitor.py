import os
import json

import atomic
import time
import datetime
import hashlib
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
import logger

# His MyAnimeList. Two public sources, no auth: the list JSON the site itself
# loads (paged by 300) and the "recently watched" RSS. The list is cached to
# disk and refreshed on an interval; new RSS items since the last poll become
# a line in the telemetry entry so they reach her through the phone digest.

STATUS = {1: "watching", 2: "completed", 3: "on hold", 4: "dropped", 6: "plan to watch"}
UA = {"User-Agent": "Mozilla/5.0"}


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_list_api(username, client_id):
    # Official v2 endpoint. Returns the same shape the site JSON uses so the
    # readers below do not care which source filled the cache.
    out = []
    url = (f"https://api.myanimelist.net/v2/users/{username}/animelist?limit=1000&nsfw=true"
           "&fields=list_status{status,score,num_episodes_watched,is_rewatching,updated_at,start_date,finish_date,comments,tags},num_episodes,media_type,genres")
    while url:
        req = urllib.request.Request(url, headers={"X-MAL-CLIENT-ID": client_id, **UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            page = json.loads(r.read())
        for d in page.get("data", []):
            node = d.get("node", {})
            ls = d.get("list_status", {})
            st = {"watching": 1, "completed": 2, "on_hold": 3, "dropped": 4, "plan_to_watch": 6}.get(ls.get("status"), 0)
            upd = ls.get("updated_at", "")
            try:
                upd_ts = datetime.datetime.fromisoformat(upd.replace("Z", "+00:00")).timestamp() if upd else 0
            except ValueError:
                upd_ts = 0
            out.append({
                "status": st, "score": ls.get("score", 0), "num_watched_episodes": ls.get("num_episodes_watched", 0),
                "created_at": upd_ts, "updated_at": upd_ts, "anime_title": node.get("title", "?"),
                "anime_num_episodes": node.get("num_episodes", 0), "anime_id": node.get("id"),
                "anime_media_type_string": node.get("media_type", ""),
                "genres": node.get("genres", []),
                "start_date_string": ls.get("start_date"), "finish_date_string": ls.get("finish_date"),
                "comments": (ls.get("comments") or "")[:200], "tags": ls.get("tags") or [], "is_rewatching": bool(ls.get("is_rewatching"))
            })
        url = page.get("paging", {}).get("next")
    return out


def fetch_list(username):
    out = []
    offset = 0
    while True:
        page = json.loads(_get(f"https://myanimelist.net/animelist/{username}/load.json?status=7&offset={offset}"))
        if not isinstance(page, list):
            break
        out.extend(page)
        if len(page) < 300:
            break
        offset += 300
    return out


def fetch_rss(username):
    root = ET.fromstring(_get(f"https://myanimelist.net/rss.php?type=rwe&u={username}"))
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        desc = (it.findtext("description") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        try:
            ts = datetime.datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %z").timestamp()
        except ValueError:
            ts = 0
        items.append({"title": title, "desc": desc, "ts": ts, "key": f"{title}|{desc}|{pub}"})
    return items


class MalMonitor:
    def __init__(self, config):
        self.enabled = bool(config.mal_enabled and config.mal_username)
        self.username = config.mal_username
        self.client_id = config.mal_client_id
        self.list_path = config.mal_list_path
        self.state_path = config.mal_state_path
        self.poll_seconds = config.mal_poll_minutes * 60
        self.refresh_seconds = config.mal_list_refresh_hours * 3600
        self.history_enabled = bool(getattr(config, "mal_history_enabled", False))
        self.history_db = getattr(config, "mal_history_db", "data/mal_history.db")
        self.history_max_events = getattr(config, "mal_history_max_events", 8)
        self.notes_max_events = getattr(config, "mal_notes_max_events", 5)
        self.notes_max_chars = getattr(config, "mal_notes_max_chars", 400)
        self._last_poll = 0
        self._seen = set()
        self._hist_watermark = None
        self._notes_seen = None
        self._list = []
        self._list_fetched = 0
        self._load()

    def _load(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    st = json.load(f)
                self._seen = set(st.get("seen", []))
                self._hist_watermark = st.get("hist_watermark")
                ns = st.get("notes_seen")
                self._notes_seen = set(ns) if ns is not None else None
            except Exception:
                pass
        if os.path.exists(self.list_path):
            try:
                with open(self.list_path, "r", encoding="utf-8") as f:
                    blob = json.load(f)
                self._list = blob.get("entries", [])
                self._list_fetched = blob.get("fetched_at", 0)
            except Exception:
                pass

    def _save_state(self):
        atomic.write_json(self.state_path,
                          {"seen": sorted(self._seen)[-500:], "hist_watermark": self._hist_watermark,
                           "notes_seen": (sorted(self._notes_seen)[-2000:]
                                          if self._notes_seen is not None else None)})

    def poll_episodes(self):
        """New per-episode watches from the mal_history DB (built by
        tools/mal_history.py) since the last look, as a digest line. Read-only;
        on first sight it just records the tip so the backfill is not dumped."""
        if not self.history_enabled or not os.path.exists(self.history_db):
            return ""
        try:
            con = sqlite3.connect(f"file:{self.history_db}?mode=ro", uri=True, timeout=5)
        except sqlite3.Error:
            return ""
        try:
            tip = con.execute("SELECT MAX(watched_at) FROM episodes").fetchone()[0]
            if not tip:
                return ""
            if self._hist_watermark is None:
                self._hist_watermark = tip
                self._save_state()
                return ""
            rows = con.execute(
                "SELECT e.watched_at, e.ep, a.title FROM episodes e "
                "LEFT JOIN anime a ON a.anime_id=e.anime_id "
                "WHERE e.watched_at > ? ORDER BY e.watched_at",
                (self._hist_watermark,)).fetchall()
        except sqlite3.Error:
            return ""
        finally:
            con.close()
        if not rows:
            return ""
        # one line per (title, ep), newest kept, capped
        seen, uniq = set(), []
        for watched_at, ep, title in rows:
            k = (title, ep)
            if k in seen:
                continue
            seen.add(k)
            uniq.append((watched_at, ep, title or "?"))
        self._hist_watermark = max(r[0] for r in rows)
        self._save_state()
        uniq = uniq[-self.history_max_events:]
        lines = ["MYANIMELIST EPISODES (exactly when he watched, from his history):"]
        for watched_at, ep, title in uniq:
            hm = watched_at[11:16] if len(watched_at) >= 16 else watched_at
            day = watched_at[:10]
            lines.append(f"- {title} episode {ep} at {hm} on {day}")
        logger.log(f"[MAL] {len(uniq)} new episode event(s) for her digest")
        return "\n".join(lines)

    def poll_notes(self):
        """Notes he has written or changed on an anime since the last look.

        `tools/mal_history.py` writes `anime.notes` on every list sync, so the
        data was already arriving; nothing watched it. A note was a snapshot
        with no event -- the only reader was the series card `lookup.py` builds,
        so she saw one only if he named that exact series in a message.

        Keyed on a hash of the text rather than a timestamp, because a note is
        edited in place: that way a rewrite fires again and an untouched note
        never does. First sight seeds the set and emits nothing, so the years of
        notes already on his list are not dumped into her lap."""
        if not self.history_enabled or not os.path.exists(self.history_db):
            return ""
        try:
            con = sqlite3.connect(f"file:{self.history_db}?mode=ro", uri=True, timeout=5)
        except sqlite3.Error:
            return ""
        try:
            rows = con.execute(
                "SELECT anime_id, title, notes, status, score FROM anime "
                "WHERE notes IS NOT NULL AND TRIM(notes) <> ''").fetchall()
        except sqlite3.Error:
            return ""
        finally:
            con.close()
        current = {}
        for aid, title, notes, status, score in rows:
            text = (notes or "").strip()
            if not text:
                continue
            key = f"{aid}:{hashlib.sha1(text.encode('utf-8', 'replace')).hexdigest()[:12]}"
            current[key] = (title or "?", text, status, score)
        if self._notes_seen is None:
            # first sight: everything he has ever written is old news
            self._notes_seen = set(current)
            self._save_state()
            logger.log(f"[MAL] {len(current)} existing anime note(s) marked as already known")
            return ""
        fresh = [(k, v) for k, v in current.items() if k not in self._notes_seen]
        if not fresh:
            return ""
        self._notes_seen |= set(current)
        self._save_state()
        fresh = fresh[-self.notes_max_events:]
        lines = ["MYANIMELIST NOTES (what he just wrote on his own list entry, in his words):"]
        for _k, (title, text, status, score) in fresh:
            st = STATUS.get(status, "on his list")
            bit = f" ({st}" + (f", he gave it {score}/10" if score else "") + ")"
            lines.append(f'- {title}{bit}: "{text[:self.notes_max_chars]}"')
        logger.log(f"[MAL] {len(fresh)} new/edited anime note(s) for her digest")
        return "\n".join(lines)

    def refresh_list(self, force=False):
        if not self.enabled:
            return self._list
        if not force and (time.time() - self._list_fetched) < self.refresh_seconds and self._list:
            return self._list
        try:
            if self.client_id:
                self._list = fetch_list_api(self.username, self.client_id)
            else:
                self._list = fetch_list(self.username)
            self._list_fetched = time.time()
            atomic.write_json(self.list_path,
                              {"fetched_at": self._list_fetched, "entries": self._list})
            logger.log(f"[MAL] list refreshed: {len(self._list)} entries")
        except Exception as e:
            logger.log(f"[MAL] list fetch failed: {e}")
        return self._list

    def poll(self):
        """Returns text describing new RSS activity since last poll, or ''."""
        if not self.enabled or (time.time() - self._last_poll) < self.poll_seconds:
            return ""
        self._last_poll = time.time()
        self.refresh_list()
        try:
            items = fetch_rss(self.username)
        except Exception as e:
            logger.log(f"[MAL] rss fetch failed: {e}")
            return ""
        first_run = not self._seen
        new = [it for it in items if it["key"] not in self._seen]
        for it in items:
            self._seen.add(it["key"])
        self._save_state()
        if first_run or not new:
            return ""
        lines = ["MYANIMELIST ACTIVITY (he updated his anime list):"]
        for it in sorted(new, key=lambda x: x["ts"]):
            when = datetime.datetime.fromtimestamp(it["ts"]).strftime("%H:%M") if it["ts"] else "?"
            lines.append(f"- [{when}] {it['title']}: {it['desc']}")
        return "\n".join(lines)

    # ---------- readers ----------

    def search_list(self, term):
        """Titles on his list matching the term, as lines she could read off the shelf."""
        t = (term or "").lower().strip()
        if not t:
            return []
        out = []
        for e in self.refresh_list() or []:
            title = str(e.get("anime_title", ""))
            if t in title.lower() or title.lower() in t:
                st = {1: "watching", 2: "completed", 3: "on hold", 4: "dropped", 6: "plan to watch"}.get(e.get("status"), "listed")
                out.append(f"{title}: on his list as {st}, {e.get('num_watched_episodes', 0)}/{e.get('anime_num_episodes') or '?'} eps" + (f", his score {e['score']}/10" if e.get("score") else ""))
        return out

    def shelf_summary(self, watching_max=10, completed_max=12, t=None):
        """His list as she reads it. `t(english, japanese)` is the caller's
        wording picker (`sim.lang.say`): the same summary is put in front of
        HER, in the language she is addressed in, and in front of the
        continuity editor, which is machinery, so the caller says which. The
        default is English, which is what the editor gets and what this
        returned before the switch existed. The titles are titles and do not
        move in either."""
        entries = self.refresh_list()
        if not entries:
            return ""
        t = t or (lambda en, jp: en)
        watching = [e for e in entries if e.get("status") == 1]
        watching.sort(key=lambda e: e.get("updated_at", 0), reverse=True)
        completed = [e for e in entries if e.get("status") == 2]
        completed.sort(key=lambda e: e.get("updated_at", 0), reverse=True)
        lines = [t(f"his anime list has {len(entries)} titles ({len(completed)} completed).",
                   f"彼のアニメリストには{len(entries)}本入っている（うち{len(completed)}本は観終わり）。")]
        if watching:
            lines.append(t("currently watching: ", "いま観ている途中: ") + "; ".join(
                f"{e['anime_title']} ({e.get('num_watched_episodes', 0)}/{e.get('anime_num_episodes') or '?'})" for e in watching[:watching_max]))
        if completed:
            def fin(e):
                s = e["anime_title"] + (f" ({e['score']}/10)" if e.get("score") else "")
                if e.get("comments"):
                    s += t(f" [his note: {e['comments'][:60]}]", f"（彼のメモ: {e['comments'][:60]}）")
                return s
            lines.append(t("recently finished: ", "最近観終わったもの: ")
                         + "; ".join(fin(e) for e in completed[:completed_max]))
        return "\n".join(lines)

    def latest_watching(self, n=3, t=None):
        """The most recently touched 'watching' entries with progress and when: what she would have seen last.

        `t` as in `shelf_summary`: this line goes into her situation block
        when anime is what they are talking about, so the words around the
        titles are the ones she is addressed in."""
        entries = self.refresh_list()
        t = t or (lambda en, jp: en)
        watching = [e for e in entries if e.get("status") == 1 and e.get("updated_at")]
        watching.sort(key=lambda e: e.get("updated_at", 0), reverse=True)
        out = []
        for e in watching[:n]:
            when = datetime.datetime.fromtimestamp(e["updated_at"]).strftime("%b %d")
            got, all_ = e.get("num_watched_episodes", 0), e.get("anime_num_episodes") or "?"
            out.append(t(f"{e['anime_title']} at ep {got}/{all_} (updated {when})",
                         f"『{e['anime_title']}』{got}/{all_}話まで（{when}に動いた）"))
        return "; ".join(out)

    def recap(self, start_date, end_date):
        """Plain recap of list changes between two dates (inclusive), local time."""
        entries = self.refresh_list()
        s = datetime.datetime.combine(start_date, datetime.time.min).timestamp()
        e = datetime.datetime.combine(end_date, datetime.time.max).timestamp()
        touched = [x for x in entries if s <= x.get("updated_at", 0) <= e]
        touched.sort(key=lambda x: x.get("updated_at", 0))
        if not touched:
            return f"no list activity between {start_date} and {end_date}."
        finished, progressed, added, other = [], [], [], []
        for x in touched:
            day = datetime.datetime.fromtimestamp(x["updated_at"]).strftime("%m-%d")
            title = x.get("anime_title", "?")
            eps = x.get("num_watched_episodes", 0)
            total = x.get("anime_num_episodes") or "?"
            st = x.get("status")
            if st == 2:
                score = f", scored {x['score']}" if x.get("score") else ""
                finished.append(f"{day} finished {title} ({total} eps{score})")
            elif st == 1:
                if s <= x.get("created_at", 0) <= e and eps == 0:
                    added.append(f"{day} started {title}")
                else:
                    progressed.append(f"{day} {title} at ep {eps}/{total}")
            elif st == 6:
                added.append(f"{day} added {title} to plan to watch")
            else:
                other.append(f"{day} {title}: {STATUS.get(st, st)} at ep {eps}/{total}")
        parts = [f"MAL recap {start_date} to {end_date}: {len(touched)} titles touched."]
        if finished:
            parts.append("finished:\n  " + "\n  ".join(finished))
        if progressed:
            parts.append("in progress:\n  " + "\n  ".join(progressed))
        if added:
            parts.append("new:\n  " + "\n  ".join(added))
        if other:
            parts.append("other:\n  " + "\n  ".join(other))
        return "\n".join(parts)
