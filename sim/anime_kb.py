import json
import re
import html
import time
import sqlite3
import urllib.parse
import urllib.request
import logger

# What she knows about a series when he brings it up: not the synopsis fluff
# but the things he actually talks about -- who is in it and who voices them
# (he talks about seiyuu a lot), plus the hard facts (studio, year, episodes,
# source, themes, MAL mean) and where HE stands with it (his list status,
# score, exactly when he watched it, from the episode history). Built from
# MAL's official API (facts) and MAL's own public characters page (cast + JP
# voice actors; the official API has no characters field at all), cached in
# the mal_history DB so a series is fetched once and then answered from disk.
# Read-only on the history; never shown to him raw.
#
# NOTHING HERE GOES THROUGH THE COMMUNITY WRAPPER IN FRONT OF MYANIMELIST,
# and nothing may be made to. It has answered 504 on every uncached path
# since 2026-08-28 -- 94 requests over 25 minutes, every one of them, plus a
# 40-attempt recovery poll that never recovered -- while MyAnimeList's own
# origin answered the equivalent page in 0.28 to 0.81 s throughout
# (`data/retired/20260904_jikan_504/REPORT.md`). The wrapper adds an outage
# the source does not have. The daemon watches for the outage ending
# (`tools/mal_history.py`, meta `jikan_state`) and NOTHING depends on its
# answer.
#
# **The reply path never fetches.** `ensure`, `ensure_person`, `resolve` and
# `find_person` all reach the network and belong to a tool or to a worker
# thread. What a reply may call is the read-only trio below -- `person_row`,
# `credits_of`, `cast_mirrored` -- which open the file `mode=ro`, answer from
# the mirror, and say "not mirrored" rather than going and looking.

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

_CHAR_TABLE = re.compile(r'<table[^>]*class="js-anime-character-table">(.*?)</table>\s*</td>\s*</tr>\s*</table>', re.S)
_CHAR = re.compile(r'href="https://myanimelist\.net/character/(\d+)/[^"]*"><h3 class="h3_character_name">([^<]+)</h3>', re.S)
_ROLE = re.compile(r'<div class="spaceit_pad">\s*(Main|Supporting)(?:&nbsp;|\s)*</div>', re.S)
_VA = re.compile(r'<a href="https://myanimelist\.net/people/(\d+)/[^"]*">([^<]+)</a>\s*</div>\s*<div class="spaceit_pad js-anime-character-language"[^>]*>\s*([A-Za-z() ]+?)\s*</div>', re.S)


def parse_characters(page):
    """MAL /anime/<id>/_/characters -> [{char_id, character, role, vas:[(name, lang, person_id)]}]"""
    out = []
    for blk in _CHAR_TABLE.findall(page):
        ch = _CHAR.search(blk)
        if not ch:
            continue
        role = _ROLE.search(blk)
        vas = [(html.unescape(m.group(2)).strip(), m.group(3).strip(), int(m.group(1))) for m in _VA.finditer(blk)]
        out.append({"char_id": int(ch.group(1)), "character": html.unescape(ch.group(2)).strip(),
                    "role": role.group(1) if role else "?", "vas": vas})
    return out


_PERSON_MORE = re.compile(r'class="people-informantion-more[^"]*">(.*?)</div>', re.S)   # MAL's own typo
# role rows are matched per-row (the page is split on <tr class="js-people-character
# first) so a prolific seiyuu's 1 MB page does not send a regex backtracking
_ROW_SPLIT = re.compile(r'<tr class="js-people-character js-anime-watch-status-people-va-(\w+)">')
_ROW_ANIME = re.compile(r'<a href="https://myanimelist\.net/anime/(\d+)/[^"]*" class="js-people-title">([^<]+)</a>')
_ROW_CHAR = re.compile(r'<a href="https://myanimelist\.net/character/(\d+)/[^"]*"[^>]*>([^<]+)</a>')
_ROW_ROLE = re.compile(r'<div class="spaceit_pad">\s*(Main|Supporting)')
_ROW_FAVS = re.compile(r'<small class="js-people-favorites"[^>]*>\s*([\d,]+)\s*</small>')
# The year the work came out, off the hidden sort key MAL puts on every role
# row ("20040000000330" -> 2004). It is the only year on the page and it is on
# all of them: 375 of her 375 rows carry one, 1996 to 2027. The official API
# has `start_season` but only per title, which would be one request each.
_ROW_YEAR = re.compile(r'<small class="entry-date"[^>]*>(\d{4})')


def parse_person(page):
    """MAL /people/<id> -> {name, name_jp, alt_names, birthday, favorites, bio, roles:[(anime_id, anime, char, role, char_favs)]}.
    name_jp is the Japanese-script name (family+given, '田村ゆかり') and alt_names
    the fan nicknames MAL lists ('ゆかりん'), so he can type any of them.
    char_favs is the character's own MAL favorites count -- the honest signal
    for which roles are the famous ones (Saber dwarfs everything else), and
    `year` is when the work came out, so a part can be placed in a career
    rather than merely named. A role tuple is
    (anime_id, anime, character, role, char_favs, year)."""
    name = re.search(r'<h1 class="title-name[^"]*">\s*<strong>([^<]+)</strong>', page)
    if not name:
        name = re.search(r'<title>([^<(]+)', page)
    bday = re.search(r'<span class="dark_text">Birthday:</span>\s*([^<]+)', page)
    fav = re.search(r'<span class="dark_text">Member Favorites:</span>\s*([^<]+)', page)
    fam = re.search(r'<span class="dark_text">Family name:</span>\s*([^<]+)', page)
    giv = re.search(r'<span class="dark_text">Given name:</span>\s*([^<]+)', page)
    alt = re.search(r'<span class="dark_text">Alternate names:</span>\s*([^<]+)', page)
    name_jp = (html.unescape(fam.group(1)).strip() if fam else "") + (html.unescape(giv.group(1)).strip() if giv else "")
    alt_names = html.unescape(alt.group(1)).strip() if alt else ""
    more = _PERSON_MORE.search(page)
    bio = ""
    if more:
        bio = html.unescape(re.sub(r"<br\s*/?>", " | ", more.group(1)))
        bio = re.sub(r"<[^>]+>", "", bio)
        bio = re.sub(r"\s+", " ", bio).strip(" |")
    roles = []
    parts = _ROW_SPLIT.split(page)
    # parts = [head, status1, row1, status2, row2, ...]; a row ends where the next begins
    for i in range(1, len(parts) - 1, 2):
        row = parts[i + 1][:4000]
        a = _ROW_ANIME.search(row)
        c = _ROW_CHAR.search(row)
        r = _ROW_ROLE.search(row)
        f = _ROW_FAVS.search(row)
        y = _ROW_YEAR.search(row)
        if a and c:
            try:
                favs = int(f.group(1).replace(",", "")) if f else 0
            except ValueError:
                favs = 0
            try:
                year = int(y.group(1)) if y else 0
            except ValueError:
                year = 0
            roles.append((int(a.group(1)), html.unescape(a.group(2)).strip(), html.unescape(c.group(2)).strip(), r.group(1) if r else "?", favs, year))
    return {"name": html.unescape(name.group(1)).strip() if name else "", "name_jp": name_jp, "alt_names": alt_names,
            "birthday": bday.group(1).strip() if bday else "",
            "favorites": fav.group(1).strip() if fav else "", "bio": bio, "roles": roles}


def _jp_name(name):
    """MAL renders people and characters 'Family, Given'. He thinks family-given
    for Japanese names ('Koga Aoi', 'Kawasumi Ayako'), so she does too: just
    drop the comma, keep the order."""
    if "," in name:
        fam, giv = [p.strip() for p in name.split(",", 1)]
        return f"{fam} {giv}".strip()
    return name


def open_rw(db_path):
    """His list's database (`tools/mal_history.py` writes it; the knowledge
    base adds its own tables), writable, in WAL so a reader never waits."""
    con = sqlite3.connect(db_path, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def open_ro(db_path):
    """The same database read-only, or None when it cannot be opened: the
    readers (the anime sense, the watching) carry on without it."""
    try:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return None


def rows_norm(rows):
    """The cached special rows as they are; a seam for tests."""
    return rows or []


class AnimeKB:
    def __init__(self, config, db_path, client_id=""):
        self.config = config
        self.db_path = db_path
        self.client_id = client_id
        self._ensure()

    def _con(self):
        return open_rw(self.db_path)

    def _ensure(self):
        try:
            con = self._con()
            con.executescript("""
            CREATE TABLE IF NOT EXISTS anime_cast (
                anime_id INTEGER, char_id INTEGER, character TEXT, role TEXT,
                jp_va TEXT, jp_va_id INTEGER, PRIMARY KEY (anime_id, char_id)
            );
            CREATE TABLE IF NOT EXISTS anime_kb (
                anime_id INTEGER PRIMARY KEY, title TEXT, title_eng TEXT, media_type TEXT,
                num_episodes INTEGER, season TEXT, studios TEXT, source TEXT, genres TEXT,
                mal_mean REAL, synopsis TEXT, fetched_at INTEGER, cast_fetched_at INTEGER
            );
            -- seiyuu: bio + every role, so she can say 'that's the Saber VA' and
            -- know which of their shows he has actually seen
            CREATE TABLE IF NOT EXISTS person (
                person_id INTEGER PRIMARY KEY, name TEXT, name_jp TEXT, alt_names TEXT,
                birthday TEXT, favorites TEXT, bio TEXT, fetched_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS person_role (
                person_id INTEGER, anime_id INTEGER, anime TEXT, character TEXT, role TEXT,
                char_favs INTEGER DEFAULT 0, year INTEGER DEFAULT 0,
                PRIMARY KEY (person_id, anime_id, character)
            );
            """)
            # `year` was added on 2026-09-04 to a table that already held 4,783
            # rows, so a mirror made before that needs the column rather than
            # the CREATE above, which only runs on an empty file. 0 means "the
            # row predates the column"; the line she reads leaves the year out
            # at 0 rather than printing a zero.
            cols = {r[1] for r in con.execute("PRAGMA table_info(person_role)")}
            if "year" not in cols:
                con.execute("ALTER TABLE person_role ADD COLUMN year INTEGER DEFAULT 0")
                logger.log("[animekb] person_role: the year column added; a credit "
                           "mirrored before today has 0 until its person is refreshed")
            con.commit(); con.close()
        except sqlite3.Error as e:
            logger.log(f"[animekb] db init failed: {e}")

    # ---------------- resolve a title he typed ----------------

    def _norm(self, t):
        return re.sub(r"[^a-z0-9぀-ヿ一-鿿]", "", (t or "").lower())

    @staticmethod
    def _raw(t):
        """A title as written, only case and runs of space levelled. What the
        normalisation cannot keep: `K-On!!` and `K-On!` are one string once the
        punctuation is stripped, and they are two shows."""
        return " ".join(str(t or "").lower().split())

    # the editions that are not the television run, in the sense his player's
    # folders and filenames use the word
    SPECIAL_TYPES = ("ova", "ona", "special", "tv_special", "oad")

    def entries(self):
        """Every entry on his list with the edition it is: the id, both
        titles, the normalised and the as-written forms, the media type and
        the episode count. Cached; one query.

        The episode count is what makes an impossible resolution visible: an
        entry with one episode cannot be the twenty-fifth episode of
        anything, and until 2026-09-04 nothing looked."""
        if getattr(self, "_entries", None) is None:
            rows = []
            try:
                con = self._con()
                rows = con.execute("SELECT anime_id,title,title_eng,media_type,num_episodes "
                                   "FROM anime").fetchall()
                con.close()
            except sqlite3.Error:
                rows = []
            self._entries = [{"aid": int(a), "title": t or "", "eng": e or "",
                              "norm": self._norm(t), "norm_eng": self._norm(e),
                              "raw": self._raw(t), "raw_eng": self._raw(e),
                              "type": str(m or "").lower(), "eps": int(n or 0)}
                             for a, t, e, m, n in rows]
        return self._entries

    def entry(self, aid):
        """One entry as his list holds it -- the edition, the episode count and
        the season where the knowledge base has fetched it -- or `{}`.

        This is what lets a line say OVA rather than repeat a Japanese title
        two editions share."""
        if not aid:
            return {}
        row = next((e for e in self.entries() if e["aid"] == int(aid)), None)
        if row is None:
            return {}
        out = dict(row)
        try:
            con = self._con()
            r = con.execute("SELECT media_type,num_episodes,season,synopsis FROM anime_kb "
                            "WHERE anime_id=?", (int(aid),)).fetchone()
            con.close()
            if r:
                out["type"] = out["type"] or str(r[0] or "").lower()
                out["eps"] = out["eps"] or int(r[1] or 0)
                out["season"] = str(r[2] or "")
                out["synopsis"] = str(r[3] or "")
        except sqlite3.Error:
            pass
        out.setdefault("season", "")
        out.setdefault("synopsis", "")
        return out

    def is_special(self, media_type):
        return str(media_type or "").lower() in self.SPECIAL_TYPES

    def resolve_candidates(self, term, ep=None, kind=""):
        """Every entry on his list this term could mean, best first.

        Three tiers, because the first row sqlite happened to return was
        deciding this: the title AS WRITTEN, then the title with its
        punctuation stripped, then a distinctive phrase inside a longer title
        with the closest length first. `Example Show` is the television run's own
        title and also sits inside `Example Show OVA` at 0.73, and the OVA was
        answering for the series on every episode he played.

        `ep` drops a candidate that cannot have that episode: a one-episode
        OVA is not the twenty-fifth episode of anything. `kind` is a hint --
        "special" for a file his folders mark as one, "tv" for a numbered
        season -- and it orders candidates inside a tier rather than dropping
        any, because his own naming is looser than the mirror's.

        Each candidate is `{aid, title, type, eps, tier, rule, ratio}`."""
        t = self._norm(term)
        raw = self._raw(term)
        if len(t) < 3:
            return []
        want_special = str(kind or "").lower() in ("special",) + self.SPECIAL_TYPES
        want_tv = str(kind or "").lower() in ("tv", "series")
        out = []
        for e in self.entries():
            if not e["norm"] and not e["norm_eng"]:
                continue
            tier, rule, ratio = None, "", 0.0
            if raw and (raw == e["raw"] or raw == e["raw_eng"]):
                tier, rule, ratio = 0, "the title as written", 1.0
            elif t == e["norm"] or t == e["norm_eng"]:
                tier, rule, ratio = 1, "the title with its punctuation out", 1.0
            else:
                for n in (e["norm"], e["norm_eng"]):
                    if n and len(t) >= 6 and t in n and len(t) / len(n) >= 0.6:
                        r = len(t) / len(n)
                        if r > ratio:
                            tier, rule, ratio = 2, "a phrase inside a longer title", r
            if tier is None:
                continue
            if ep and e["eps"] and int(e["eps"]) < int(ep):
                continue
            hint = 0
            if want_special:
                hint = 0 if self.is_special(e["type"]) else 1
            elif want_tv:
                hint = 1 if self.is_special(e["type"]) else 0
            out.append({"aid": e["aid"], "title": e["title"], "type": e["type"],
                        "eps": e["eps"], "tier": tier, "rule": rule,
                        "ratio": round(ratio, 3), "hint": hint})
        out.sort(key=lambda c: (c["tier"], c["hint"], -c["ratio"], c["aid"]))
        return out

    @staticmethod
    def ambiguous(cands):
        """Is the top of this ranking a tie code cannot break? Two candidates
        matched the same way and neither is nearer than the other."""
        if len(cands) < 2:
            return False
        a, b = cands[0], cands[1]
        return (a["tier"], a["hint"], a["ratio"]) == (b["tier"], b["hint"], b["ratio"])

    def his_titles(self):
        """Every title in his own list, normalized, cached. His list is the whole
        point: a thing is worth her looking up because he watched it."""
        if getattr(self, "_titles", None) is None:
            rows = []
            try:
                con = self._con()
                rows = con.execute("SELECT anime_id,title,title_eng FROM anime").fetchall()
                con.close()
            except sqlite3.Error:
                rows = []
            self._titles = [(aid, title, self._norm(title), self._norm(eng)) for aid, title, eng in rows]
        return self._titles

    def resolve_special(self, base):
        """(anime_id, title, media type) for the OVA / ONA / special entry on
        his list whose title begins with
        `base` -- for a player file that names a special with no number
        (`sim/watching_him.py parse_special`). Local only, his list only,
        and it prefers the shortest such title, which is the franchise's own
        special rather than a spin-off's. None when his list has no special
        of that name; the TV entry is never returned here, because a special
        recorded as episode 1 of the TV series would be a lie about what he
        watched."""
        b = self._norm(base)
        if len(b) < 3:
            return None
        rows = getattr(self, "_specials", None)
        if rows is None:
            rows = []
            try:
                con = self._con()
                rows = con.execute("SELECT anime_id,title,title_eng,media_type FROM anime "
                                   "WHERE lower(media_type) IN ('ova','ona','special','tv_special','oad')").fetchall()
                con.close()
            except sqlite3.Error:
                rows = []
            self._specials = [(aid, title, self._norm(title), self._norm(eng)) for aid, title, eng, _t in rows]
        hits = [(len(nt or ne), aid, title) for aid, title, nt, ne in rows_norm(self._specials)
                if (nt and nt.startswith(b)) or (ne and ne.startswith(b))]
        if not hits:
            return None
        hits.sort()
        aid, title = hits[0][1], hits[0][2]
        # the edition too, so the line she reads can say OVA rather than
        # repeat a Japanese title two editions share
        return aid, title, (self.entry(aid) or {}).get("type", "")

    def has(self, aid):
        """Is this one of his? MAL search will return a hit for any query at all,
        so this is what separates a thing he watched from a thing that exists."""
        try:
            return any(a == aid for a, _, _, _ in self.his_titles())
        except Exception:
            return False

    def resolve_strict(self, term, ep=None, kind=""):
        """(anime_id, title) for the one entry on his list this term means, or
        None. Local only, no network, and deliberately unforgiving: this is
        used to decide whether he named something, not to be generous once we
        know he did. `resolve` falls through to the MAL search API, which
        answers every query, so it can never be a trigger.

        The ranking is `resolve_candidates`, and a tie it cannot break returns
        NOTHING rather than the first row sqlite handed back. Silence costs a
        remark she never makes; a wrong answer costs a synopsis, a digest, a
        verdict, a thing she knows by name, a fact about him and a sentence to
        him he can see is false. `ep` and `kind` are passed through, so a
        candidate that cannot have that episode is never the answer."""
        cands = self.resolve_candidates(term, ep=ep, kind=kind)
        if not cands or self.ambiguous(cands):
            return None
        return cands[0]["aid"], cands[0]["title"]

    def person_name_jp(self, person_id):
        """The seiyuu's Japanese-script name from the cached person row, for a
        Japanese Wikipedia lookup. '' if not cached."""
        if not person_id:
            return ""
        try:
            con = self._con()
            row = con.execute("SELECT name_jp FROM person WHERE person_id=?", (person_id,)).fetchone()
            con.close()
            return (row[0] or "") if row else ""
        except Exception:
            return ""

    def japanese_title(self, aid):
        """The kanji title from MAL (`alternative_titles.ja`), for a Japanese
        search that finds real あらすじ blogs -- the romaji title finds only
        database sites. Cached in the `anime_kb` row's title_eng? no: a tiny
        keyed cache in memory; one cheap API call per series, rarely."""
        if not aid or not self.client_id:
            return ""
        cache = getattr(self, "_ja_cache", None)
        if cache is None:
            cache = self._ja_cache = {}
        if aid in cache:
            return cache[aid]
        ja = ""
        try:
            url = f"https://api.myanimelist.net/v2/anime/{aid}?fields=alternative_titles"
            req = urllib.request.Request(url, headers={"X-MAL-CLIENT-ID": self.client_id, **UA})
            d = json.loads(urllib.request.urlopen(req, timeout=15).read())
            ja = (d.get("alternative_titles") or {}).get("ja", "") or ""
        except Exception as e:
            logger.log(f"[animekb] ja title failed for {aid}: {type(e).__name__}")
        cache[aid] = ja
        return ja

    def resolve(self, term):
        """His list first (what he actually calls it is usually there), then the
        MAL search API. Returns (anime_id, title) or (None, None)."""
        t = (term or "").strip().lower()
        if not t:
            return None, None
        try:
            con = self._con()
            rows = con.execute("SELECT anime_id,title,title_eng FROM anime").fetchall()
            con.close()
        except sqlite3.Error:
            rows = []
        best = None
        for aid, title, eng in rows:
            for cand in (title or "", eng or ""):
                c = cand.lower()
                if not c:
                    continue
                if c == t:
                    return aid, title
                if t in c or c in t:
                    score = len(t) / max(len(c), 1)
                    if not best or score > best[0]:
                        best = (score, aid, title)
        if best and best[0] >= 0.5:
            return best[1], best[2]
        if self.client_id:
            try:
                url = f"https://api.myanimelist.net/v2/anime?q={urllib.parse.quote(term)}&limit=1"
                req = urllib.request.Request(url, headers={"X-MAL-CLIENT-ID": self.client_id, **UA})
                d = json.loads(urllib.request.urlopen(req, timeout=15).read())
                n = (d.get("data") or [{}])[0].get("node", {})
                if n.get("id"):
                    return n["id"], n.get("title")
            except Exception:
                pass
        return best[1:] if best else (None, None)

    # ---------------- fetch + cache ----------------

    def _fetch_facts(self, aid):
        if not self.client_id:
            return None
        fields = "id,title,alternative_titles,media_type,num_episodes,start_season,source,mean,genres,studios,synopsis"
        url = f"https://api.myanimelist.net/v2/anime/{aid}?fields={fields}"
        req = urllib.request.Request(url, headers={"X-MAL-CLIENT-ID": self.client_id, **UA})
        d = json.loads(urllib.request.urlopen(req, timeout=20).read())
        ss = d.get("start_season") or {}
        return {
            "title": d.get("title"), "title_eng": (d.get("alternative_titles") or {}).get("en") or "",
            "media_type": d.get("media_type"), "num_episodes": d.get("num_episodes"),
            "season": f"{ss.get('season','')} {ss.get('year','')}".strip(),
            "studios": json.dumps([s["name"] for s in d.get("studios", [])], ensure_ascii=False),
            "source": d.get("source"), "genres": json.dumps([g["name"] for g in d.get("genres", [])], ensure_ascii=False),
            "mal_mean": d.get("mean"), "synopsis": (d.get("synopsis") or "")[:1200],
        }

    def _fetch_cast(self, aid):
        url = f"https://myanimelist.net/anime/{aid}/_/characters"
        page = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read().decode("utf-8", "replace")
        chars = parse_characters(page)
        rows = []
        for c in chars:
            jp = [v for v in c["vas"] if v[1] == "Japanese"]
            rows.append((aid, c["char_id"], c["character"], c["role"],
                         _jp_name(jp[0][0]) if jp else None, jp[0][2] if jp else None))
        return rows

    def ensure(self, aid, max_age_days=90):
        """Facts + cast for a series, fetched once and cached. Returns the kb row dict or None."""
        con = self._con()
        try:
            row = con.execute("SELECT fetched_at,cast_fetched_at FROM anime_kb WHERE anime_id=?", (aid,)).fetchone()
            now = int(time.time())
            fresh = row and row[0] and (now - row[0]) < max_age_days * 86400
            if not fresh:
                try:
                    f = self._fetch_facts(aid)
                except Exception as e:
                    logger.log(f"[animekb] facts fetch failed for {aid}: {type(e).__name__}")
                    f = None
                if f:
                    con.execute("""INSERT INTO anime_kb(anime_id,title,title_eng,media_type,num_episodes,season,studios,source,genres,mal_mean,synopsis,fetched_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(anime_id) DO UPDATE SET title=excluded.title,title_eng=excluded.title_eng,
                        media_type=excluded.media_type,num_episodes=excluded.num_episodes,season=excluded.season,studios=excluded.studios,
                        source=excluded.source,genres=excluded.genres,mal_mean=excluded.mal_mean,synopsis=excluded.synopsis,fetched_at=excluded.fetched_at""",
                        (aid, f["title"], f["title_eng"], f["media_type"], f["num_episodes"], f["season"], f["studios"], f["source"], f["genres"], f["mal_mean"], f["synopsis"], now))
                    con.commit()
            cast_fresh = row and row[1] and (now - row[1]) < max_age_days * 86400
            if not cast_fresh:
                # NEVER delete before there is a replacement in hand. A 200
                # whose body the parser cannot read -- an interstitial, a
                # rate-limit page, a changed layout -- makes `parse_characters`
                # return [], and the old shape of this block then emptied the
                # series' cast and stamped it fresh for 90 days, so nothing
                # ever went back for it. An empty parse is a failed fetch, not
                # a show with no cast: the stored rows stand, no stamp is
                # written, and the next tick tries again.
                try:
                    rows = self._fetch_cast(aid)
                except Exception as e:
                    rows = None
                    logger.log(f"[animekb] cast fetch failed for {aid}: {type(e).__name__}")
                if rows:
                    try:
                        con.execute("DELETE FROM anime_cast WHERE anime_id=?", (aid,))
                        con.executemany("INSERT OR REPLACE INTO anime_cast"
                                        "(anime_id,char_id,character,role,jp_va,jp_va_id)"
                                        " VALUES(?,?,?,?,?,?)", rows)
                        con.execute("INSERT INTO anime_kb(anime_id,cast_fetched_at) VALUES(?,?) ON CONFLICT(anime_id) DO UPDATE SET cast_fetched_at=excluded.cast_fetched_at", (aid, now))
                        con.commit()
                        logger.log(f"[animekb] cast for {aid}: {len(rows)} characters, {sum(1 for r in rows if r[4])} with JP VA")
                    except Exception as e:
                        con.rollback()
                        logger.log(f"[animekb] cast for {aid} not written: {type(e).__name__}")
                elif rows is not None:
                    logger.log(f"[animekb] the cast page for {aid} parsed to nothing; "
                               f"the {self._cast_rows(aid)} row(s) already stored stand, unstamped")
            r = con.execute("SELECT title,title_eng,media_type,num_episodes,season,studios,source,genres,mal_mean,synopsis FROM anime_kb WHERE anime_id=?", (aid,)).fetchone()
            return dict(zip(("title", "title_eng", "media_type", "num_episodes", "season", "studios", "source", "genres", "mal_mean", "synopsis"), r)) if r else None
        finally:
            con.close()

    # ---------------- seiyuu ----------------

    def ensure_person(self, person_id, max_age_days=120):
        """Bio + all roles for a voice actor, fetched once and cached."""
        con = self._con()
        try:
            row = con.execute("SELECT fetched_at FROM person WHERE person_id=?", (person_id,)).fetchone()
            now = int(time.time())
            if row and row[0] and (now - row[0]) < max_age_days * 86400:
                return True
            url = f"https://myanimelist.net/people/{person_id}"
            page = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read().decode("utf-8", "replace")
            d = parse_person(page)
            # The same guard as the cast above, and this is the table it
            # matters most for: a filmography is what the role check answers
            # "no" from, and an empty parse that wiped it and stamped it fresh
            # would turn every one of her real parts into "not checked" for
            # 120 days without a line in any log to say so.
            if not d.get("roles"):
                logger.log(f"[animekb] the page for person {person_id} parsed to no roles; "
                           f"the {self._credit_rows(person_id)} credit(s) already stored stand, unstamped")
                return False
            con.execute("INSERT INTO person(person_id,name,name_jp,alt_names,birthday,favorites,bio,fetched_at) VALUES(?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(person_id) DO UPDATE SET name=excluded.name,name_jp=excluded.name_jp,alt_names=excluded.alt_names,"
                        "birthday=excluded.birthday,favorites=excluded.favorites,bio=excluded.bio,fetched_at=excluded.fetched_at",
                        (person_id, _jp_name(d["name"]), d["name_jp"], d["alt_names"], d["birthday"], d["favorites"], d["bio"][:1500], now))
            con.execute("DELETE FROM person_role WHERE person_id=?", (person_id,))
            con.executemany("INSERT OR REPLACE INTO person_role"
                            "(person_id,anime_id,anime,character,role,char_favs,year)"
                            " VALUES(?,?,?,?,?,?,?)",
                            [(person_id, aid, an, _jp_name(ch), role, favs, year)
                             for aid, an, ch, role, favs, year in d["roles"]])
            con.commit()
            logger.log(f"[animekb] seiyuu {_jp_name(d['name'])}: {len(d['roles'])} roles cached")
            return True
        except Exception as e:
            logger.log(f"[animekb] person fetch failed for {person_id}: {type(e).__name__}")
            return False
        finally:
            con.close()

    # ---------------- the mirror, read only, never a fetch ----------------
    #
    # What a reply path may ask. Each opens the file `mode=ro` and answers
    # from what is there; a missing row is "not mirrored", which the caller
    # turns into "not checked" and says nothing about. `roles_of` below is
    # the opposite -- it resolves a person by NAME and calls `ensure_person`,
    # which fetches -- and it belongs to a tool or a worker thread.

    def _ro(self):
        con = open_ro(self.db_path)
        if con is None:
            logger.log("[animekb] the mirror could not be opened read-only")
        return con

    def _cast_rows(self, aid):
        """How many cast rows are stored for this title. For a log line that
        says what an empty parse did not lose."""
        con = self._ro()
        if con is None:
            return 0
        try:
            return int(con.execute("SELECT COUNT(*) FROM anime_cast WHERE anime_id=?", (aid,)).fetchone()[0])
        except sqlite3.Error:
            return 0
        finally:
            con.close()

    def _credit_rows(self, person_id):
        """The same for a filmography."""
        con = self._ro()
        if con is None:
            return 0
        try:
            return int(con.execute("SELECT COUNT(*) FROM person_role WHERE person_id=?", (person_id,)).fetchone()[0])
        except sqlite3.Error:
            return 0
        finally:
            con.close()

    def person_row(self, person_id):
        """Who this id is on his mirror, and when the page was last read:
        {person_id, name, name_jp, fetched_at, credits}, or None when nobody
        has mirrored them. An id, never a name: her given name alone matches
        nine other people in the cast rows by substring, and which of them
        answered was down to the order sqlite happened to return."""
        try:
            pid = int(person_id)
        except (TypeError, ValueError):
            return None
        if not pid:
            return None
        con = self._ro()
        if con is None:
            return None
        try:
            r = con.execute("SELECT person_id,name,name_jp,fetched_at FROM person WHERE person_id=?", (pid,)).fetchone()
            if not r:
                return None
            n = con.execute("SELECT COUNT(*), COUNT(DISTINCT anime_id) FROM person_role WHERE person_id=?", (pid,)).fetchone()
            return {"person_id": r[0], "name": r[1] or "", "name_jp": r[2] or "",
                    "fetched_at": int(r[3] or 0), "credits": int(n[0] or 0), "works": int(n[1] or 0)}
        except sqlite3.Error as e:
            logger.log(f"[animekb] person {pid} not read: {type(e).__name__}")
            return None
        finally:
            con.close()

    def credits_of(self, person_id):
        """Every credit mirrored for this person id:
        [(anime_id, anime, character, role, year)]. Local, read-only, no
        fetch, and empty when the person is not mirrored -- which is a
        different answer from "they are in nothing" and the caller must treat
        it as such."""
        try:
            pid = int(person_id)
        except (TypeError, ValueError):
            return []
        if not pid:
            return []
        con = self._ro()
        if con is None:
            return []
        try:
            return [(r[0], r[1] or "", r[2] or "", r[3] or "", int(r[4] or 0)) for r in con.execute(
                "SELECT anime_id, anime, character, role, year FROM person_role WHERE person_id=?", (pid,))]
        except sqlite3.Error as e:
            logger.log(f"[animekb] credits of {pid} not read: {type(e).__name__}")
            return []
        finally:
            con.close()

    def cast_mirrored(self, aid):
        """(when the cast was mirrored, its rows) for one title, or (0, [])
        when nobody has mirrored it. The stamp is the point: it separates "the
        cast is here and she is not in it" from "nobody has looked", and only
        the first of those is evidence."""
        try:
            aid = int(aid)
        except (TypeError, ValueError):
            return 0, []
        if not aid:
            return 0, []
        con = self._ro()
        if con is None:
            return 0, []
        try:
            r = con.execute("SELECT cast_fetched_at FROM anime_kb WHERE anime_id=?", (aid,)).fetchone()
            at = int((r[0] if r else 0) or 0)
            if not at:
                return 0, []
            rows = [(x[0] or "", x[1] or "", x[2] or "", x[3]) for x in con.execute(
                "SELECT character, role, jp_va, jp_va_id FROM anime_cast WHERE anime_id=? "
                "ORDER BY CASE role WHEN 'Main' THEN 0 ELSE 1 END, char_id", (aid,))]
            return at, rows
        except sqlite3.Error as e:
            logger.log(f"[animekb] the cast of {aid} not read: {type(e).__name__}")
            return 0, []
        finally:
            con.close()

    def find_person(self, name, search=True):
        """A seiyuu he named -> (person_id, name). Romaji either order, the
        Japanese-script name ('田村ゆかり'), or a fan nickname MAL lists
        ('ゆかりん'); from the cast rows and persons already cached, else a
        cold MAL people search (he will name seiyuu she has never met)."""
        raw = re.sub(r"\s+", " ", (name or "").strip())
        t = raw.lower()
        if not t:
            return None, None
        parts = t.split(" ")
        rev = " ".join(reversed(parts)) if len(parts) == 2 else t
        jp = re.sub(r"[\s・]", "", raw)   # '田村 ゆかり' / '田村・ゆかり' -> '田村ゆかり'
        con = self._con()
        try:
            for nm, pid in con.execute("SELECT DISTINCT jp_va,jp_va_id FROM anime_cast WHERE jp_va IS NOT NULL"):
                n = nm.lower()
                if n == t or n == rev or t in n or rev in n:
                    return pid, nm
            for pid, nm, njp, alts in con.execute("SELECT person_id,name,name_jp,alt_names FROM person"):
                n = (nm or "").lower()
                if n == t or n == rev or t in n or rev in n:
                    return pid, nm
                if jp and njp and (jp == njp or jp in njp):
                    return pid, nm
                if alts and any(a.strip() and (a.strip().lower() == t or a.strip() == jp) for a in alts.split(",")):
                    return pid, nm
        finally:
            con.close()
        if not search:
            return None, None
        # cold: MAL's people search takes romaji or Japanese script
        try:
            url = "https://myanimelist.net/people.php?" + urllib.parse.urlencode({"q": raw, "cat": "person"})
            page = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read().decode("utf-8", "replace")
            m = re.search(r'href="https://myanimelist\.net/people/(\d+)/([^"]+)"', page)
            if m:
                pid = int(m.group(1))
                nm = _jp_name(m.group(2).replace("_", " "))
                # the search result is romaji Given_Family; cache it properly by fetching the person
                self.ensure_person(pid)
                con = self._con()
                try:
                    r = con.execute("SELECT name FROM person WHERE person_id=?", (pid,)).fetchone()
                finally:
                    con.close()
                return pid, (r[0] if r else nm)
        except Exception as e:
            logger.log(f"[animekb] people search failed for {raw!r}: {type(e).__name__}")
        return None, None

    def roles_of(self, name):
        """Every role MyAnimeList lists for a voice actor, by any name the
        person is known by: [(anime_id, anime, character, role)]. Fetched
        once and cached (`ensure_person`); empty when the person is not
        found. The glance asks this about the character herself when a page
        for a work is in front of him."""
        pid, _nm = self.find_person(name)
        if not pid or not self.ensure_person(pid):
            return []
        con = self._con()
        try:
            return [tuple(r) for r in con.execute(
                "SELECT anime_id, anime, character, role FROM person_role WHERE person_id=?", (pid,)).fetchall()]
        finally:
            con.close()

    def person_brief(self, person_id, max_roles=10):
        """The card for a seiyuu: who they are, their notable roles, and which of
        those HE has actually seen (from his list) -- the crossover she would
        notice: 'Kawasumi Ayako, Saber, also Shimoda in 16bit which you just watched'."""
        if not self.ensure_person(person_id):
            return ""
        con = self._con()
        try:
            p = con.execute("SELECT name,name_jp,alt_names,birthday,favorites,bio FROM person WHERE person_id=?", (person_id,)).fetchone()
            roles = con.execute("SELECT anime_id,anime,character,role,char_favs FROM person_role WHERE person_id=?", (person_id,)).fetchall()
            his = {aid: (st, sc, w) for aid, st, sc, w in con.execute("SELECT anime_id,status,score,watched_episodes FROM anime")}
        finally:
            con.close()
        if not p:
            return ""
        name, name_jp, alt_names, bday, fav, bio = p
        if name_jp:
            name = f"{name} ({name_jp}" + (f", aka {alt_names}" if alt_names else "") + ")"
        # one of his declared MAL favorites? (his own hand; the strongest signal)
        declared = False
        con = self._con()
        try:
            if con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='favorites'").fetchone():
                declared = bool(con.execute("SELECT 1 FROM favorites WHERE kind='people' AND item_id=?", (person_id,)).fetchone())
        finally:
            con.close()
        if declared:
            name += " — ONE OF HIS DECLARED FAVORITE SEIYUU (on his MAL favorites list)"
        seen = [(aid, an, ch, r) for aid, an, ch, r, fv in roles if aid in his]
        # one line per famous character (Saber appears in 30 Fate entries; say it once)
        best_by_char = {}
        for aid, an, ch, r, fv in roles:
            if ch not in best_by_char or fv > best_by_char[ch][4]:
                best_by_char[ch] = (aid, an, ch, r, fv)
        mains = sorted(best_by_char.values(), key=lambda x: -x[4])   # by the character's own MAL favorites
        lines = [f"{name} (seiyuu" + (f", b. {bday}" if bday else "") + (f"; {fav} MAL favorites" if fav else "") + f"; {len(roles)} roles, {len(mains)} main)"]
        if bio:
            short = "; ".join(s.strip() for s in bio.split("|") if s.strip())[:260]
            lines.append(f"about: {short}")
        st_word = {1: "watching", 2: "completed", 3: "on hold", 4: "dropped", 6: "plan to watch"}
        if seen:
            seen_main = [x for x in seen if x[3] == "Main"][:8]
            seen_fmt = []
            for aid, an, ch, r in (seen_main or seen[:8]):
                st, sc, w = his[aid]
                seen_fmt.append(f"{ch} in {an} ({st_word.get(st, 'listed')}" + (f", he gave {sc}" if sc else "") + ")")
            lines.append("he has seen them as: " + "; ".join(seen_fmt))
        others = [x for x in mains if x[0] not in his and x[4] > 0][:max_roles]
        if others:
            lines.append("also known for: " + "; ".join(f"{ch} in {an}" for aid, an, ch, r, fv in others))
        return "\n".join(lines)

    # ---------------- what she reads ----------------

    # ---------------- characters ----------------

    def find_character(self, name, prefer=()):
        """A character he named -> (anime_id, character, role, jp_va, title,
        status, score) or None.

        Matched on a whole name part, never a substring: LIKE '%Yanami%' finds
        "Ayanami, Rei" from Evangelion when he meant Yanami from Makeine, which
        is the same fuzzy-match trap that returned the wrong CVs on 2026-08-19.

        `prefer` is the show or shows already in the conversation, and it
        outranks everything else. Character names are not unique -- Rei, Yui,
        Chino, Megumi all appear across dozens of his 480 shows -- so the only
        reliable disambiguator is what the two of them were just talking
        about. After that: something he has watched over something he has not,
        an exact full-name hit over a single part, a main role over a
        supporting one."""
        term = (name or "").strip()
        if len(term) < 2:
            return None
        parts = [p for p in re.split(r"[\s,、]+", term) if len(p) >= 2]
        if not parts:
            return None
        con = self._con()
        try:
            rows = con.execute(
                "SELECT c.anime_id, c.character, c.role, c.jp_va, a.status, a.score, a.title "
                "FROM anime_cast c LEFT JOIN anime a ON a.anime_id = c.anime_id").fetchall()
        finally:
            con.close()
        best = None
        for aid, char, role, va, status, score, title in rows:
            # the stored form is "Family, Given"; compare on the pieces
            names = [x.strip().lower() for x in re.split(r"[,\s]+", char or "") if x.strip()]
            if not names:
                continue
            hits = sum(1 for p in parts if p.lower() in names)
            if not hits:
                continue
            in_play = 1 if aid in prefer else 0
            exact = 1 if len(parts) > 1 and hits >= len(parts) else 0
            watched = 1 if status else 0
            main = 1 if (role or "") == "Main" else 0
            rank = (in_play, exact, watched, main, hits)
            if best is None or rank > best[0]:
                best = (rank, (aid, char, role, va, title, status, score))
        return best[1] if best else None

    def character_brief(self, hit):
        """What she knows about a character he mentioned: who they are, who
        voices them, and where he stands with the show they are in."""
        aid, char, role, va, title, status, score = hit
        name = _jp_name(char)
        bits = [f"{name} is a {(role or 'supporting').lower()} character in {title or 'a show'}"]
        if va:
            bits.append(f"voiced by {_jp_name(va)}")
        line = ", ".join(bits) + "."
        out = [line]
        fav_c, fav_a = self._favorite_names()
        if name.lower() in fav_c:
            out.append(f"{name} is ONE OF HIS DECLARED FAVORITE CHARACTERS on his MAL profile.")
        if (title or "").lower() in fav_a:
            out.append(f"{title} is one of his declared favorite anime.")
        stand = self._his_standing(aid)
        if stand:
            out.append(stand)
        return " ".join(out)

    def _favorite_names(self):
        con = self._con()
        try:
            rows = con.execute("SELECT kind, name FROM favorites").fetchall()
        except Exception:
            return set(), set()
        finally:
            con.close()
        chars = {_jp_name(n).lower() for k, n in rows if k == "character"}
        anime = {(n or "").lower() for k, n in rows if k == "anime"}
        return chars, anime

    def _his_standing(self, aid):
        con = self._con()
        try:
            r = con.execute("SELECT status, score, watched_episodes, num_episodes FROM anime WHERE anime_id=?", (aid,)).fetchone()
        finally:
            con.close()
        if not r:
            return "He has never had it on his list."
        status, score, watched, total = r
        words = {1: "is watching", 2: "finished", 3: "has on hold", 4: "dropped", 6: "has it plan-to-watch"}
        w = words.get(status, "has")
        bit = f"He {w} it"
        if status == 1 and watched:
            bit += f" ({watched}/{total or '?'})"
        if score:
            bit += f" and rated it {score}/10"
        return bit + "."

    def brief(self, aid, max_cast=8):
        """The card she gets in her situation when he names this series: facts
        he'd care about, the cast with JP voices, and his own standing with it.
        Synopsis is a single sentence at the end, not the lead."""
        kb = self.ensure(aid)
        if not kb:
            return ""
        con = self._con()
        try:
            cast = con.execute("SELECT character,role,jp_va FROM anime_cast WHERE anime_id=? ORDER BY CASE role WHEN 'Main' THEN 0 ELSE 1 END, char_id", (aid,)).fetchall()
            his = con.execute("SELECT status,score,watched_episodes,start_date,finish_date,notes FROM anime WHERE anime_id=?", (aid,)).fetchone()
            eps = con.execute("SELECT ep,watched_at FROM episodes WHERE anime_id=? ORDER BY watched_at", (aid,)).fetchall()
            dur = con.execute("SELECT avg_episode_seconds FROM anime_detail WHERE anime_id=?", (aid,)).fetchone()
        finally:
            con.close()
        def jl(x):
            try:
                return ", ".join(json.loads(x or "[]"))
            except Exception:
                return ""
        lines = []
        head = kb["title"] + (f" / {kb['title_eng']}" if kb.get("title_eng") and kb["title_eng"] != kb["title"] else "")
        lines.append(f"{head} — {kb.get('media_type') or '?'}, {kb.get('season') or '?'}, {kb.get('num_episodes') or '?'} eps"
                     + (f" (~{round(dur[0]/60)} min)" if dur and dur[0] else "")
                     + f"; studio {jl(kb.get('studios')) or '?'}; from {kb.get('source') or '?'}; MAL mean {kb.get('mal_mean') or '?'}")
        g = jl(kb.get("genres"))
        if g:
            lines.append(f"tags: {g}")
        if cast:
            mains = [c for c in cast if c[1] == "Main"][:max_cast]
            sups = [c for c in cast if c[1] != "Main"][: max(0, max_cast - len(mains))]
            def fmt(c):
                ch = _jp_name(c[0])
                return f"{ch} (CV {c[2]})" if c[2] else ch
            lines.append("cast: " + "; ".join(fmt(c) for c in mains + sups))
        # declared favorites touching this series: the anime itself, or a character in it
        fav_bits = []
        con = self._con()
        try:
            if con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='favorites'").fetchone():
                if con.execute("SELECT 1 FROM favorites WHERE kind='anime' AND item_id=?", (aid,)).fetchone():
                    fav_bits.append("this is ONE OF HIS ALL-TIME FAVORITE ANIME (his MAL favorites)")
                fav_chars = [r[0] for r in con.execute("SELECT name FROM favorites WHERE kind='character'")]
                cast_names = {c[0] for c in cast}
                hit = [fc for fc in fav_chars if fc in cast_names]
                if hit:
                    fav_bits.append("his DECLARED FAVORITE CHARACTER(s) are in it: " + ", ".join(_jp_name(h) for h in hit))
        finally:
            con.close()
        if fav_bits:
            lines.append("; ".join(fav_bits))
        if his:
            st = {1: "watching", 2: "completed", 3: "on hold", 4: "dropped", 6: "plan to watch"}.get(his[0], "on his list")
            s = f"him: {st}, {his[2] or 0}/{kb.get('num_episodes') or '?'} eps"
            if his[1]:
                s += f", his score {his[1]}/10"
            if eps:
                s += f"; watched {eps[0][1][:10]} → {eps[-1][1][:10]} ({len(eps)} logged eps, last ep {eps[-1][0]} at {eps[-1][1][11:16]})"
            if his[5]:
                s += f"; his note: {his[5][:100]}"
            lines.append(s)
        else:
            lines.append("him: not on his list")
        syn = (kb.get("synopsis") or "").strip().split(". ")[0]
        if syn:
            lines.append(f"premise, one line: {syn[:220]}")
        return "\n".join(lines)
