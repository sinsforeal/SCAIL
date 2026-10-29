import concurrent.futures
import hashlib
import json
import os
import re
import time
import html as _html
import tempfile
import urllib.parse
import urllib.request
import logger

from sim.episode_account import EpisodeAccount
from sim.episode_archive import EpisodeArchive
from sim import wiring
from sim.subtitles import Subtitles
from sim.transcribe import Transcribe
from sim.transcripts import Transcripts

# Grounded watching: when she "watches" an episode, she should know what
# actually happens in it, not invent it (the model had K-On ep15 as a
# lyrics scene; it is a marathon episode). This fetches a real Japanese
# あらすじ for one (title, episode) -- her native register, and the same
# path covers anime and jdrama -- and caches it, so the experience call
# reacts to real beats. One search + one page fetch per new episode, then
# disk. No model call here. Selenium (a throwaway Chrome profile, never
# her X profile) because the good sources reset plain fetchers.
#
# spec: docs/recap.md

try:
    from selenium import webdriver
except Exception:  # selenium absent (a --no-sensors box); recap just stays off
    webdriver = None

# per-host article container: where the entry body is, past nav and sidebar
HOST_SELECTORS = {
    "ameblo.jp": [".skin-entryBody", ".articleText", "#entryBody"],
    "hatenablog.com": [".entry-content"],
    "hatenadiary.org": [".entry-content", ".section"],
    "hatenadiary.jp": [".entry-content"],
    "blog.goo.ne.jp": ["#goo-blog-entry-content", ".entry-body", ".entry"],
    "livedoor.jp": [".article-body-inner", ".mainmore", ".article-body"],
    "ldblog.jp": [".article-body-inner", ".article-body"],
    "cinema.ne.jp": [".article-body", ".p-article__body", "article"],
    "dramataro.com": [".entry-content", "article"],
    "cinematoday.jp": [".article-body"],
}
GENERIC_SELECTORS = [".entry-content", "article", ".article-body", ".post-content", "#main", "main"]

# an episode's running order -- the parts in order, the eyecatches, the theme
# songs, the cast, the next-episode preview -- names the right episode and
# describes none of it, so the section test passes and the digest role
# restates the table as events. These are its own headings.
RUNNING_ORDER_MARKS = ("構成", "パート 内容", "アイキャッチ", "オープニングテーマ",
                       "エンディングテーマ", "次回予告", "キャスト", "主題歌", "分類")

# every recap Chrome uses a throwaway profile under this temp prefix, so a
# sweep can find and reap the ones a killed-mid-fetch bot left behind
PROFILE_PREFIX = "recap_"


class Recap:
    # `retrievals` is the machine's store of what has been fetched about the
    # world (`machine/retrievals.py`): the page for an episode, the verdict
    # between candidate pages, a series' premise, a person's bio. Both
    # characters read and write it, so a page is fetched and digested once;
    # what she made of it stays in her own save.
    #
    # `anime_kb` is his own mirror of MyAnimeList, and it is here for one
    # reason: the EDITION of a work, which is part of the name a page is filed
    # under. MyAnimeList gives the 2006 one-episode OVA and the 2007
    # television run the identical Japanese title エグザンプル, so a key built
    # from the title alone made them one thing, and the television series'
    # first episode was served as the OVA's to both characters.
    WIRES = ('retrievals', 'anime_kb')

    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock
        self._ensure_table()
        # every key below is read with a default, so this module runs against a
        # config from before the patch that adds them
        # (data/retired/<ts>_summaries_build/patch_config.py)
        self.archive = EpisodeArchive(getattr(config.recap, "archive_dir", "data/recaps"),
                                      enabled=bool(getattr(config.recap, "archive_enabled", True)))
        self.subtitles = Subtitles(config, store, clock, archive=self.archive)
        # and the last resort, when nothing anywhere holds the episode's own
        # words: his own transcriber, on this machine, on the file he played
        self.transcribe = Transcribe(config, store, clock, archive=self.archive)
        self.transcripts = Transcripts(config, store, clock, subtitles=self.subtitles,
                                       archive=self.archive)
        # and the record the whole reading-up is FOR: every surviving digest,
        # the transcript and the blurb merged into one account of the episode,
        # written once for the machine (`sim/episode_account.py`). The judge
        # above answers which single page to trust; this answers what happened
        # in the episode, and the second question is not the first one.
        self.accounts = EpisodeAccount(config, store, clock, archive=self.archive)
        try:
            logger.log(self.transcribe.boot_line())
        except Exception:
            pass
        try:
            self.sweep_orphans(log=logger.log)
        except Exception:
            pass
        wiring.declare(self)

    # Columns added since the table was first written. `judged` says a reader
    # chose this page among several candidates; the four beside it say what
    # was decided and why, so the next reader does not have to guess:
    # `confidence` is provisional / judged / anchored, `candidates` the URLs
    # fetched with each one's verdict, `reason` the judge's line, `anchor` the
    # URL of the transcript or official blurb it was measured against, and
    # `scenes` the ordered scene list the record keeps for recall.
    # `aid` is the work's MyAnimeList id, added 2026-09-04 for the same reason
    # the shared key carries one: `ja` and `ep` were the whole name of a row,
    # and two works of this list share a Japanese title. A row from before it
    # has NULL there and is still read by a caller with no id (her own
    # watchlist has none), so nothing that was reachable stopped being.
    COLUMNS = (("judged", "INTEGER DEFAULT 0"), ("confidence", "TEXT"),
               ("candidates", "TEXT"), ("reason", "TEXT"), ("anchor", "TEXT"),
               ("scenes", "TEXT"), ("archive", "TEXT"), ("aid", "INTEGER"))

    def _ensure_table(self):
        try:
            with self.store.lock:
                self.store.conn.execute(
                    "CREATE TABLE IF NOT EXISTS recaps ("
                    "id INTEGER PRIMARY KEY, title TEXT, ja TEXT, kind TEXT, ep INTEGER, "
                    "text TEXT, source TEXT, fetched_at INTEGER, judged INTEGER DEFAULT 0)")
                # A row without these is a first-passing-page accept, which is
                # how a programme table sat in the cache as an episode's
                # synopsis; it reads as provisional and is read again rather
                # than trusted forever. Both live saves are missing every one
                # of them until the bot they belong to is restarted, which is
                # what runs this.
                cols = [r[1] for r in self.store.conn.execute("PRAGMA table_info(recaps)")]
                for name, decl in self.COLUMNS:
                    if name not in cols:
                        self.store.conn.execute(f"ALTER TABLE recaps ADD COLUMN {name} {decl}")
                self.store.conn.commit()
        except Exception as e:
            logger.log(f"[recap] table init failed: {type(e).__name__}: {e}")

    # ---------------- the cache: hers, and the machine's ----------------
    #
    # Two stores answer a question about a page. The machine's
    # (`machine/retrievals.py`) holds what was FETCHED -- the text, where it
    # came from, and the verdict a judge reached on it -- once for both
    # characters, because a television episode is the same episode whoever is
    # watching. Her save's `recaps` table is her own record of what she has
    # been TOLD: the row she read, when she read it, how far it was trusted.
    # When the machine's copy answers a question her save cannot, the row is
    # copied into her save too, so what she knows is hers and not the
    # machine's -- and nothing is fetched to do it.

    SHARED_POOL = "recap"

    @staticmethod
    def _pool_kind(kind, ep):
        """What a row is filed under, never blank: an episode row is `anime`
        whether or not the caller said so, which is what lets one character's
        row be found by the other."""
        k = str(kind or "").strip()
        return k or ("anime" if int(ep or 0) else "thing")

    @classmethod
    def _shared_key(cls, kind, key, ep, aid=None, mtype=""):
        """What the machine's store calls this thing. It names the THING and
        never the character: a show and an episode number, a person, a work.

        **With an id it names the id and the edition** --
        `anime|mal:1480|ova|ep1` -- because a title is not a name for a work:
        the OVA and the television run of Example Show have the same Japanese
        title, both hashed to `anime|エグザンプル|ep1`, and the one row that
        existed was the series'. Without an id the old form stands, which is
        what her own watchlist (which carries no ids) still writes and
        reads."""
        pool = cls._pool_kind(kind, ep)
        if aid:
            return "%s|mal:%d|%s|ep%d" % (pool, int(aid),
                                          str(mtype or "any").strip().lower(), int(ep or 0))
        return "%s|%s|ep%d" % (pool, str(key or "").strip(), int(ep or 0))

    def _edition(self, aid, mtype=""):
        """The edition a key is filed under, from one place: what the caller
        was told, else his own mirror. Two callers naming the same work must
        produce the same key, so this never guesses from a title."""
        mt = str(mtype or "").strip().lower()
        if mt or not aid or self.anime_kb is None:
            return mt or "any"
        try:
            return str((self.anime_kb.entry(aid) or {}).get("type") or "").lower() or "any"
        except Exception:
            return "any"

    def _entry_titles(self, aid):
        """What his own list calls this work: the romaji title and the English
        one. An archive files a show under whichever romanisation its uploader
        used, so a lookup that knows only one of them misses a show that is
        there. No network: this is the local mirror."""
        if not aid or self.anime_kb is None:
            return []
        try:
            row = self.anime_kb.entry(aid) or {}
        except Exception:
            return []
        return [row.get("title", ""), row.get("eng", "")]

    def _resolves_to(self, title, aid):
        """Could a row filed under this title be about a work OTHER than the
        one asked for? Used on a row written before keys carried ids: it is
        read only when his own list holds exactly one entry of that name and
        that entry is the one asked about."""
        if not aid or self.anime_kb is None or not str(title or "").strip():
            return False
        try:
            cands = self.anime_kb.resolve_candidates(title)
        except Exception:
            return False
        return len(cands) == 1 and int(cands[0]["aid"]) == int(aid)

    @staticmethod
    def _conf_of(row):
        """How far a row may be trusted, for a row from either store. A row
        written before the column existed says only judged or not."""
        c = str((row or {}).get("confidence") or "")
        if c in ("provisional", "judged", "anchored"):
            return c
        return "judged" if (row or {}).get("judged") else "provisional"

    RANK = {"anchored": 3, "judged": 2, "provisional": 1}

    def _local_row(self, key, ep, kind=None, aid=None):
        """Her own row for (key, ep), or None.

        With an id, a row that carries a DIFFERENT id is not this thing and is
        never returned; a row with none (written before the column, or by her
        own watchlist, which has no ids) still answers, and a row that names
        the id asked for is preferred over one that names nothing."""
        try:
            with self.store.lock:
                have = {r[1] for r in self.store.conn.execute("PRAGMA table_info(recaps)")}
                cols = ["text", "source", "fetched_at"] + [c for c, _ in self.COLUMNS if c in have]
                sql = f"SELECT {','.join(cols)} FROM recaps WHERE ja=? AND ep=?"
                args = [key, int(ep)]
                if kind:
                    sql += " AND kind=?"
                    args.append(kind)
                order = " ORDER BY id DESC LIMIT 1"
                if aid and "aid" in have:
                    sql += " AND (aid=? OR aid IS NULL)"
                    args.append(int(aid))
                    order = " ORDER BY (aid IS NULL), id DESC LIMIT 1"
                r = self.store.conn.execute(sql + order, args).fetchone()
        except Exception:
            return None
        if not r:
            return None
        d = dict(zip(cols, r))
        for j in ("candidates", "scenes"):
            if isinstance(d.get(j), str) and d[j]:
                try:
                    d[j] = json.loads(d[j])
                except ValueError:
                    d[j] = []
        d["mine"] = True
        d.setdefault("confidence", "provisional")
        return d

    def _shared_row(self, key, ep, kind=None, aid=None, mtype=""):
        """The machine's row for this thing, shaped like one of hers.

        The id-aware key first. A row still under the plain-title key is read
        only when it cannot be about another edition -- when his list holds
        exactly one entry of that name and it is the one asked for -- so the
        page that was filed under a title two works share can never be served
        for the other one again."""
        if self.retrievals is None or not key:
            return None
        try:
            r = None
            if aid:
                r = self.retrievals.get(
                    self.SHARED_POOL, self._shared_key(kind, key, ep, aid, self._edition(aid, mtype)))
            if r is None:
                old = self.retrievals.get(self.SHARED_POOL, self._shared_key(kind, key, ep))
                if old and aid:
                    title = (old.get("meta") or {}).get("title") or ""
                    if self._resolves_to(title, aid):
                        r = old
                    else:
                        logger.log(f"[resolver] the stored page under {self._shared_key(kind, key, ep)} "
                                   f"was filed under a title, not an id; not used for mal:{aid}")
                else:
                    r = old
        except Exception as e:
            logger.log(f"[recap] the machine's store did not answer: {type(e).__name__}")
            return None
        if not r or not r.get("text"):
            return None
        meta = r.get("meta") or {}
        d = {"text": r["text"], "source": r.get("source") or "",
             "fetched_at": int(r.get("fetched_at") or 0),
             "judged": int(r.get("judged") or 0),
             "title": meta.get("title") or "", "mine": False, "by": r.get("by") or ""}
        for c, _decl in self.COLUMNS:
            if c in meta:
                d[c] = meta[c]
        d.setdefault("confidence", "provisional")
        return d

    def _best(self, key, ep, kind=None, aid=None, mtype=""):
        """Hers or the machine's, whichever is worth more: a row a judge chose
        beats one nobody judged, and between two of the same standing the
        later fetch wins."""
        rows = [r for r in (self._local_row(key, ep, kind, aid),
                            self._shared_row(key, ep, kind, aid, mtype)) if r]
        if not rows:
            return None
        rows.sort(key=lambda r: (self.RANK.get(self._conf_of(r), 0),
                                 int(r.get("fetched_at") or 0),
                                 1 if r.get("mine") else 0), reverse=True)
        return rows[0]

    def _adopt(self, row, key, ep, kind=None, aid=None, mtype=""):
        """The machine's copy answered and her save has no row for it: write
        one. Nothing is fetched -- the text is copied -- and the date is now,
        because now is when she was told."""
        if row is None or row.get("mine"):
            return
        if self._local_row(key, ep, kind, aid) is not None:
            return
        entry = {"title": row.get("title") or key, "ja": key,
                 "kind": self._pool_kind(kind, ep), "ep": int(ep or 0),
                 "aid": aid, "mtype": mtype}
        self._store(entry, int(ep or 0), row.get("text") or "", row.get("source") or "",
                    judged=int(row.get("judged") or 0), confidence=self._conf_of(row),
                    candidates=row.get("candidates") or (), reason=str(row.get("reason") or ""),
                    anchor=str(row.get("anchor") or ""), scenes=row.get("scenes") or (),
                    archive=str(row.get("archive") or ""), share=False)

    def _from_shared(self, key, ep, kind=None, aid=None, mtype=""):
        """The machine's row for this episode, shaped like what `synopsis`
        returns, and written into her own record on the way past.

        This is what a character who waited for somebody else's search gets
        back. She was told the same thing at the same moment; what is hers is
        the record of having been told it, which `_adopt` writes."""
        row = self._shared_row(key, ep, kind, aid, mtype)
        if not row or not row.get("text"):
            return None
        self._adopt(row, key, ep, kind, aid, mtype)
        # and the account she was told at the same moment, copied into her own
        # record the same way: waiting for another character's reading-up and
        # then coming away with only the page would leave her the one
        # character on the machine who does not know the episode
        acct = self.accounts.row(key, int(ep or 0), aid=aid, retrievals=self.retrievals,
                                 shared_key=self._shared_key(kind, key, ep, aid,
                                                             self._edition(aid, mtype))) \
            if self.accounts.enabled() else None
        return {"text": row["text"], "source": row.get("source", ""),
                "digest": "", "scenes": row.get("scenes") or [],
                "confidence": self._conf_of(row), "reason": row.get("reason", ""),
                "anchor": row.get("anchor", ""), "candidates": row.get("candidates") or [],
                "account": acct}

    def cached(self, key, ep, kind=None, aid=None, mtype=""):
        row = self._best(key, ep, kind, aid, mtype)
        if not row or not row.get("text"):
            return None
        self._adopt(row, key, ep, kind, aid, mtype)
        return (row["text"], row.get("source") or "")

    def confidence(self, key, ep, kind=None, aid=None, mtype=""):
        """What the cached row for (key, ep) is worth, in one word.

        * `provisional` -- one candidate, or one no other candidate
          corroborated, or a row from before any of this. Read once so an
          episode is never blank, and refetched on the next read.
        * `judged` -- chosen among at least two candidates, with at least one
          other agreeing on the scenes it names.
        * `anchored` -- judged, and it agreed with the transcript or the
          official blurb. Trusted without a re-read.

        `''` when there is no row at all, in either store."""
        row = self._best(key, ep, kind, aid, mtype)
        return self._conf_of(row) if row else ""

    def judged(self, key, ep, kind=None, aid=None, mtype=""):
        """Whether the cached page for (key, ep) may be trusted without being
        read again: judged among candidates, or anchored to a transcript."""
        return self.confidence(key, ep, kind, aid, mtype) in ("judged", "anchored")

    def row(self, key, ep, kind=None, aid=None, mtype=""):
        """The whole cached row for (key, ep): the text, where it came from,
        what was decided and why. `None` if there is none in either store."""
        row = self._best(key, ep, kind, aid, mtype)
        if not row:
            return None
        self._adopt(row, key, ep, kind, aid, mtype)
        d = {k: v for k, v in row.items() if k not in ("mine", "by")}
        d.setdefault("confidence", "provisional")
        return d

    def _store(self, entry, ep, text, source, judged=0, confidence="", candidates=(),
               reason="", anchor="", scenes=(), archive="", share=True):
        # the machine's copy first: it is the one that saves the other
        # character a fetch, and a bot is stopped without warning
        if share:
            self._share(entry, ep, text, source, judged=judged, confidence=confidence,
                        candidates=candidates, reason=reason, anchor=anchor,
                        scenes=scenes, archive=archive)
        cols = [r[0] for r in self.COLUMNS]
        try:
            with self.store.lock:
                have = {r[1] for r in self.store.conn.execute("PRAGMA table_info(recaps)")}
                extra = [c for c in cols if c in have]
                vals = {"judged": int(judged),
                        "confidence": confidence or ("judged" if judged else "provisional"),
                        "candidates": json.dumps(list(candidates or ()), ensure_ascii=False),
                        "reason": str(reason or "")[:400], "anchor": str(anchor or "")[:300],
                        "scenes": json.dumps(list(scenes or ()), ensure_ascii=False),
                        "archive": str(archive or "")[:200],
                        "aid": (int(entry.get("aid")) if entry.get("aid") else None)}
                names = "title,ja,kind,ep,text,source,fetched_at" + ("," + ",".join(extra) if extra else "")
                marks = ",".join("?" * (7 + len(extra)))
                self.store.conn.execute(
                    f"INSERT INTO recaps({names}) VALUES({marks})",
                    (entry.get("title", ""), entry.get("ja", ""), entry.get("kind", ""),
                     int(ep), text[:4000], source, int(self.clock.now_ts()),
                     *[vals[c] for c in extra]))
                self.store.conn.commit()
        except Exception as e:
            logger.log(f"[recap] store failed: {type(e).__name__}: {e}")

    def _share(self, entry, ep, text, source, judged=0, confidence="", candidates=(),
               reason="", anchor="", scenes=(), archive=""):
        """Write what was fetched into the machine's one store, so the other
        character never fetches it. A row a judge chose is never overwritten by
        one nobody judged."""
        if self.retrievals is None or not text:
            return
        key = (entry.get("ja") or entry.get("title") or "").strip()
        if not key:
            return
        kind = self._pool_kind(entry.get("kind"), ep)
        aid = int(entry["aid"]) if entry.get("aid") else None
        mt = self._edition(aid, entry.get("mtype", ""))
        try:
            skey = self._shared_key(kind, key, ep, aid, mt)
            have = self.retrievals.get(self.SHARED_POOL, skey)
            if have and int(have.get("judged") or 0) and not int(judged):
                return
            self.retrievals.put(
                self.SHARED_POOL, skey, text[:4000], source=source, judged=int(judged),
                meta={"title": entry.get("title", ""), "ja": entry.get("ja", ""),
                      "kind": kind, "ep": int(ep or 0),
                      "aid": aid, "media_type": (mt if aid else ""),
                      "confidence": confidence or ("judged" if judged else "provisional"),
                      "candidates": list(candidates or ()),
                      "reason": str(reason or "")[:400], "anchor": str(anchor or "")[:300],
                      "scenes": list(scenes or ()), "archive": str(archive or "")[:200]})
        except Exception as e:
            logger.log(f"[recap] the machine's copy was not written: {type(e).__name__}")

    def _unshare(self, key, ep, kind=None, text=None, aid=None, mtype=""):
        """Drop the machine's copy of a page that turned out not to be about
        this episode, so the other character is never handed it. Only when it
        is the same text: the other may have found a better page since."""
        if self.retrievals is None:
            return
        try:
            skey = self._shared_key(kind, key, ep, aid, self._edition(aid, mtype) if aid else "")
            have = self.retrievals.get(self.SHARED_POOL, skey)
            if have and (text is None or (have.get("text") or "") == text):
                self.retrievals.drop(self.SHARED_POOL, skey)
                logger.log(f"[recap] the machine's copy of {skey} dropped with hers")
        except Exception as e:
            logger.log(f"[recap] the machine's copy was not dropped: {type(e).__name__}")

    # ---------------- the public call ----------------

    EP_RE = re.compile(
        r"(?:\bs\d+\s*e\s*(\d{1,3})\b)"          # S1E8
        r"|(?:\b(?:ep|episode|epi)\s*\.?\s*#?\s*(\d{1,3})\b)"  # ep 8 / episode 8
        r"|(?:第?\s*(\d{1,3})\s*話)"              # 8話 / 第8話
        r"|(?:#\s*(\d{1,3})\b)", re.I)            # #8

    @classmethod
    def episode_in(cls, text):
        """The episode number he named in a message, or None. '4話', 'ep 8',
        'S1E8', 'episode 12', '#3' -- not a bare number (too many false hits)."""
        m = cls.EP_RE.search(text or "")
        if not m:
            return None
        for g in m.groups():
            if g:
                try:
                    n = int(g)
                    return n if 1 <= n <= 999 else None
                except ValueError:
                    return None
        return None

    def series_overview(self, title, ja=""):
        """A fuller Japanese premise/overview of a whole series (its setup,
        who is in it, what it is about), cached at ep 0. For when HE mentions
        a series -- she should know more than the cast card. None on failure."""
        key = (ja or title or "").strip()
        return self._kb_overview("series", key, ja, "series",
                                 self.config.recap.overview_query.format(title=key), title=title)

    # sections that come AFTER the premise/bio, by subject -- everything up to
    # the first of these is what she wants (the lead + 概要/あらすじ, or a
    # person's 人物/来歴)
    STOPS = {
        "series": ["登場人物", "各話", "スタッフ", "放送", "エピソード", "主題歌",
                   "音楽", "書誌情報", "脚注", "出典", "関連項目", "外部リンク", "キャスト"],
        "seiyuu": ["出演", "作品", "ディスコグラフィ", "ディスコグラフィー", "受賞",
                   "参加作品", "タイアップ", "脚注", "出典", "関連項目", "外部リンク"],
        "eroge": ["登場人物", "システム", "スタッフ", "主題歌", "設定", "評価",
                  "スピンオフ", "関連商品", "脚注", "出典", "関連項目", "外部リンク"],
    }

    def _wikipedia_intro(self, driver, ja, stops=None):
        """The Japanese Wikipedia article's lead + premise, as its <p>
        paragraphs, before the character list / discography / staff. '' if the
        article is missing or a disambiguation. Works off the content region
        and paragraph tags, not the whole giant mw-parser-output div (which
        defeats a shallow container grab)."""
        url = "https://ja.wikipedia.org/wiki/" + urllib.parse.quote(ja, safe="")
        html = self._page_source(driver, url, need=8000)
        if not html or "ウィキペディアには同名" in html:
            return ""
        i = html.find('id="mw-content-text"')
        if i < 0:
            return ""
        region = html[i:]
        stops = stops or self.STOPS["series"]
        # cut at the first stop-word that is a SECTION HEADING (its Wikipedia
        # anchor id `id="出演..."`), not any occurrence -- a bare `region.find`
        # matched "出演" inside the infobox and truncated the lead
        cut = len(region)
        for m in stops:
            k = region.find('id="' + m)
            if 0 < k < cut:
                cut = k
        region = region[:cut]
        out = []
        for p in re.findall(r"<p\b[^>]*>(.*?)</p>", region, re.S):
            t = self._strip(p)
            # Wikipedia leaks inline reference JSON into the text
            # (`"}},"i":0}}]}">`); drop those blobs and the ref/edit marks
            t = re.sub(r'"?\}\}.*?\]\}">|\{["\[].*?\}\}?', "", t)
            t = re.sub(r"\[\s*編集\s*\]|\[\s*\d+\s*\]|\[要出典\]|\[\s*注釈\s*\d+\s*\]", "", t)
            t = re.sub(r"\s{2,}", " ", t).strip()
            if len(t) >= 30:
                out.append(t)
        return "\n".join(out).strip()

    # ---------------- the knowledge base: people and works ----------------

    def _kb_overview(self, kind, key, ja, wiki_stops, search_query, title=None):
        """One path for a whole subject (a series, a seiyuu, an eroge): the
        Japanese Wikipedia lead first (its premise; official story pages
        are nav-heavy, and a direct fetch is not subject to blocked_hosts,
        which filters search results), a search fallback, cached in
        `recaps` under `kind` and reused forever. None if nothing usable.
        `title` is what the cached row is filed under when it is not the
        key (a series keeps its English title)."""
        c = self.config.recap
        if not c.enabled or not key:
            return None
        hit = self.cached(key, 0, kind)
        if hit:
            return hit[0]
        if webdriver is None:
            return None
        entry = {"title": title or key, "ja": key, "kind": kind, "ep": 0}
        try:
            driver = self._open()
            try:
                if ja:
                    w = self._wikipedia_intro(driver, ja, self.STOPS.get(wiki_stops))
                    if w and len(w) >= c.min_chars:
                        text = w[:c.max_chars]
                        self._store(entry, 0, text, "ja.wikipedia.org")
                        logger.log(f"[recap] {kind} {key}: {len(text)} chars from ja.wikipedia")
                        return text
                for u in self._search(driver, search_query)[:c.candidates_max]:
                    if any(b in u for b in c.blocked_hosts):
                        continue
                    html = self._page_source(driver, u)
                    if not html:
                        continue
                    body = self._extract(html, u)
                    if body and len(body) >= c.min_chars:
                        text = body[:c.max_chars]
                        self._store(entry, 0, text, u)
                        logger.log(f"[recap] {kind} {key}: {len(text)} chars from {u}")
                        return text
            finally:
                self._close(driver)
        except Exception as e:
            logger.log(f"[recap] {kind} failed for {key}: {type(e).__name__}: {e}")
        return None

    def person_overview(self, name, ja=""):
        """A seiyuu's Japanese Wikipedia bio (who they are, career), for when he
        names a voice actor -- richer than the MAL role list."""
        key = (ja or name or "").strip()
        return self._kb_overview("seiyuu", key, ja, "seiyuu",
                                 self.config.recap.seiyuu_query.format(name=key))

    def work_overview(self, title, ja="", kind="eroge"):
        """A Japanese overview of a game / visual novel / eroge, for when he
        names one or she snoops one -- its premise and what it is."""
        key = (ja or title or "").strip()
        return self._kb_overview(kind, key, ja or title, "eroge",
                                 self.config.recap.work_query.format(title=key))

    def report(self, limit=40):
        """The knowledge base she has built, for /kb: what has been fetched and
        cached, by kind, so repeat mentions are free."""
        try:
            with self.store.lock:
                rows = self.store.conn.execute(
                    "SELECT kind, COUNT(*), MAX(fetched_at) FROM recaps GROUP BY kind ORDER BY 2 DESC").fetchall()
                recent = self.store.conn.execute(
                    "SELECT kind, ja, ep, length(text), source FROM recaps ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        except Exception as e:
            return f"kb read failed: {e}"
        out = ["knowledge base (cached, reused; no re-fetch):"]
        out += [f"  {k}: {n}" for k, n, _ in rows] or ["  (empty)"]
        if self.retrievals is not None:
            try:
                out.append(self.retrievals.report())
            except Exception:
                pass
        out.append("recent:")
        for k, ja, ep, ln, src in recent:
            tag = f" ep{ep}" if ep else ""
            out.append(f"  [{k}] {ja}{tag} -- {ln}c from {(src or '')[:40]}")
        return "\n".join(out)

    def recap_for(self, entry, ep=None, avoid=(), llm=None, anime_id=None, english=""):
        """The あらすじ for (this show, this episode), from cache or the web.
        Returns the Japanese text, or None if nothing usable was found (the
        caller then lets the model do what it did before). Never raises.

        `avoid` is a set of source URLs a caller has already judged useless
        (sim/watching_him.py asks its digest role about each page); those are
        skipped, and a cached row from one of them is a miss.

        **With a model client it is the judged path.** Her own watching used
        to take the first page that passed the section test, store it and
        trust it forever: four of the nine episode rows in the two saves came
        that way and none of them had ever been compared with anything. Given
        `llm` this goes through `synopsis` -- several candidates, one judge,
        an anchor -- exactly as his watching does. Without one it is the old
        single-page path, and what it stores is marked provisional so the next
        read fetches again."""
        c = self.config.recap
        avoid = set(avoid or ())
        if not c.enabled:
            return None
        ep = int(ep if ep is not None else entry.get("ep", 1) or 1)
        ja = (entry.get("ja") or entry.get("title") or "").strip()
        if not ja:
            return None
        # the id, from the caller or from the entry itself, so a page is
        # filed and found under the work rather than under a title two works
        # may share
        if anime_id and not entry.get("aid"):
            entry = dict(entry, aid=anime_id)
        aid = int(entry["aid"]) if entry.get("aid") else None
        mtype = entry.get("mtype", "")
        if llm is not None:
            got = self.synopsis(entry, ep, llm=llm, anime_id=anime_id, english=english,
                                avoid=avoid)
            return (got or {}).get("text") or None
        hit = self.cached(ja, ep, aid=aid, mtype=mtype)
        if hit and hit[1] in avoid:
            hit = None
        if hit and self._episode_slice(hit[0], ep, self.slice_titles(aid, ja, ep)):
            return hit[0]
        if hit:
            # A cached page with no section for this episode is not a synopsis
            # of it, whatever the row says: the first fetch for みつどもえ ep9
            # accepted a bookstore page for volume 9 of the manga, and it sat
            # in the cache as the episode. Delete it and go again.
            logger.log(f"[recap] cached text for {ja} ep{ep} has no episode section ({hit[1]}); refetching")
            try:
                with self.store.lock:
                    self.store.conn.execute("DELETE FROM recaps WHERE ja=? AND ep=? AND text=?", (ja, int(ep), hit[0]))
                    self.store.conn.commit()
            except Exception as e:
                logger.log(f"[recap] could not drop the bad row: {type(e).__name__}")
            self._unshare(ja, ep, text=hit[0], aid=aid, mtype=mtype)
        if webdriver is None:
            return None
        try:
            text, source = self._harvest(entry, ja, ep, avoid=avoid)
        except Exception as e:
            logger.log(f"[recap] harvest failed for {ja} ep{ep}: {type(e).__name__}: {e}")
            return None
        if text and len(text) >= c.min_chars:
            self._store(entry, ep, text, source)
            logger.log(f"[recap] {ja} ep{ep}: {len(text)} chars from {source}")
            return text
        logger.log(f"[recap] {ja} ep{ep}: nothing usable found")
        return None

    def recap_candidates(self, entry, ep, n=3, avoid=(), anime_id=None, english=""):
        """Compatibility shape for a caller that wants only the text and the
        URL. `candidates` is the one with the verdicts on it."""
        return [(c["text"], c["url"]) for c in
                self.candidates(entry, ep, n=n, avoid=avoid, anime_id=anime_id, english=english)
                if not c.get("anchor_only")]

    def candidates(self, entry, ep, n=4, avoid=(), anime_id=None, english="", want=0,
                   tried_max=0, page_chars=0):
        """The candidate set for one episode: a fixed source list first,
        search second.

        Each candidate is `{text, url, rank, source, anchor_only}`. Nothing is
        stored -- the caller digests each, judges them against each other and
        against an anchor, and stores the winner with `remember`.

        The two keyless English sources and the series' episode titles are
        fetched in parallel with each other and with the browser, so the
        browser is no longer in the critical path for the first candidates.
        A page too short to be a digest is kept and marked `anchor_only`: the
        official あらすじ is never wrong and never complete, which makes it the
        right fact check and the wrong thing to summarise.

        `want` and `tried_max` override the config's two caps for a caller
        that needs a WIDER set than the judge does. The judge picks one page
        and four candidates is plenty for that; the account merges all of
        them, and a running gag or a background reference is usually carried
        by exactly one 感想 post out of six, so the account's caller asks for
        more (`recap.account_candidates`)."""
        c = self.config.recap
        ja = (entry.get("ja") or entry.get("title") or "").strip()
        if not ja or not c.enabled:
            return []
        ep = int(ep)
        avoid = set(avoid or ())
        want = int(want or getattr(c, "candidates_target", n) or n)
        # how much of each page is carried back. `max_chars` was chosen for
        # what is STORED as the winning synopsis; the account reads the pages
        # themselves, and a joke two thirds of the way down a fan post is past
        # 2,200 characters more often than not.
        keep = int(page_chars or c.max_chars)
        anchor_max = int(getattr(c, "anchor_max_chars", 300) or 300)
        # below this a slice is the page's furniture, not even an anchor
        anchor_min = int(getattr(c, "anchor_min_chars", c.min_chars) or c.min_chars)
        show_key = self.archive.show_key(anime_id, ja, entry.get("title", ""))
        out = []
        titles = {}
        pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=int(getattr(c, "fetch_workers", 4) or 4))
        futs = {}
        try:
            if anime_id:
                futs["list"] = pool.submit(self.list_site_episode, anime_id, ep)
                futs["titles"] = pool.submit(self.episode_titles, anime_id, entry)
            if english:
                futs["wiki"] = pool.submit(self.wikipedia_episodes, english, entry)
            blogs = self._search_pages(entry, ja, ep, want, avoid, tried_max=tried_max)
            if "titles" in futs:
                try:
                    titles = futs["titles"].result(timeout=30) or {}
                except Exception:
                    titles = {}
            if "list" in futs:
                failed = ""
                try:
                    text, url, html = futs["list"].result(timeout=30)
                except Exception as e:
                    text, url, html, failed = "", "", "", type(e).__name__
                # SAY WHEN IT GIVES NOTHING. This source was dropped in
                # silence: a page with no synopsis of its own, or one that
                # answered an error, left no line at all, so the only way to
                # tell whether it had been read was to open the archive and
                # count what was in it (one episode). By
                # exception TYPE and never the URL -- the fetch that failed
                # names the address it failed on, and an address can carry a
                # key.
                if failed or not text or len(text) < anchor_min:
                    logger.log(f"[recap] his list's episode page for ep{ep} gave "
                               + (f"nothing ({failed})" if failed else
                                  f"{len(text)} character(s), under the {anchor_min} an anchor needs"))
                if text and len(text) >= anchor_min and url not in avoid:
                    self.archive.save(show_key, ep, "html", html or "", url=url, ext=".html",
                                      show=entry.get("title", ""), ja=ja)
                    self.archive.save(show_key, ep, "page", text, url=url,
                                      show=entry.get("title", ""), ja=ja)
                    out.append({"text": text[:keep], "url": url, "rank": 1,
                                "source": "list site episode page",
                                "anchor_only": len(text) < anchor_max})
            if "wiki" in futs:
                try:
                    eps = futs["wiki"].result(timeout=30) or {}
                except Exception:
                    eps = {}
                s = str(eps.get(ep) or eps.get(str(ep)) or "").strip()
                url = str(getattr(c, "wikipedia_list_title", "List of {title} episodes")
                          ).format(title=english)
                url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(url.replace(" ", "_"))
                if s and len(s) >= anchor_min and url not in avoid:
                    self.archive.save(show_key, ep, "page", s, url=url,
                                      show=entry.get("title", ""), ja=ja)
                    out.append({"text": s[:keep], "url": url, "rank": 2,
                                "source": "English episode list",
                                "anchor_only": len(s) < anchor_max})
        finally:
            pool.shutdown(wait=False)
        total = self._total_episodes(entry, anime_id)
        for text, url, html in blogs:
            if len(out) >= want:
                break
            if titles and self.wrong_episode(text, ep, titles):
                logger.log(f"[recap] {url[:70]}: names another episode's title; out")
                continue
            if self.past_the_end(text, ep, total):
                logger.log(f"[recap] {url[:70]}: it names a later episode or previews a next "
                           f"one, and this work has {total} episode(s); out")
                continue
            self.archive.save(show_key, ep, "html", html, url=url, ext=".html",
                              show=entry.get("title", ""), ja=ja)
            self.archive.save(show_key, ep, "page", text, url=url,
                              show=entry.get("title", ""), ja=ja)
            out.append({"text": text[:keep], "url": url, "rank": 3,
                        "source": "Japanese page", "anchor_only": len(text) < anchor_max})
        return out

    def _search_pages(self, entry, ja, ep, want, avoid=(), tried_max=0):
        """The Japanese search, unchanged in shape: [(sliced text, url, html)].

        A page under `min_chars` is kept when it has a section for this
        episode -- that is the official blurb, and it is the anchor rather
        than a candidate."""
        c = self.config.recap
        if webdriver is None:
            return []
        out = []
        driver = None
        ep_titles = self.slice_titles(entry.get("aid"), ja, ep)
        try:
            driver = self._open()
            urls = self._search(driver, c.query_template.format(title=ja, ep=ep))
            tried = 0
            cap = int(tried_max or c.candidates_max)
            for u in urls:
                if len(out) >= want or tried >= cap:
                    break
                if any(b in u for b in c.blocked_hosts) or u in avoid:
                    continue
                tried += 1
                html = self._page_source(driver, u)
                if not html:
                    continue
                body = self._extract(html, u)
                sliced, why = self._slice_and_why(body, ep, ep_titles,
                                                  self.page_heading(html))
                if not sliced:
                    # THE FORM IT FAILED ON, not "no section": every widening
                    # of this test has come from reading these lines, and
                    # "no section for ep7" says nothing about what was looked
                    # for or what the page had instead.
                    logger.log(f"[recap] {u[:80]}: not about ep{ep} -- {why}")
                    continue
                # Short is fine -- the official blurb is 200-250 characters and
                # is the anchor rather than a candidate -- but a slice that is
                # only the page's own heading is neither. A page that had not
                # finished arriving gave 37 characters and stood as the anchor.
                # A slice under `min_chars` was never a synopsis and is not
                # an anchor either: the official blurb, which is what the
                # anchor is for, measures 200 to 250 characters. Below it are
                # the page's own furniture -- a title bar with an advertising
                # strip under it came to 172 characters and stood as the
                # anchor four real candidates were measured against, and a
                # site that had not finished loading gave 37.
                if len(sliced) < int(getattr(c, "anchor_min_chars", c.min_chars) or c.min_chars):
                    logger.log(f"[recap] {u[:80]}: {len(sliced)} characters for ep{ep}; "
                               f"too little to be even an anchor")
                    continue
                out.append((sliced, u, html))
            return out
        except Exception as e:
            logger.log(f"[recap] candidates failed for {ja} ep{ep}: {type(e).__name__}")
            return out
        finally:
            if driver is not None:
                self._close(driver)

    def remember(self, entry, ep, text, source, confidence="judged", candidates=(),
                 reason="", anchor="", scenes=(), show_key="", archive=""):
        """Store a synopsis a reader chose among several candidates, with what
        was decided and why, and drop any row for the same episode that this
        one is at least as good as -- so the choice is what the cache answers
        with rather than whatever passed first, and her save holds ONE row per
        episode rather than a pile.

        It used to drop only the rows nobody had judged, so a second reading
        of an episode she had already been told about sat down beside the
        first: on 2026-09-07 the third character adopted the machine's judged
        row for みなみけ ep3, read the episode up again a moment later, and
        her save kept both, identical (HISTORY.md section 5.15). A row that is
        WORTH MORE than this one is still left alone -- a provisional reading
        must not replace an anchored one."""
        ja = (entry.get("ja") or entry.get("title") or "").strip()
        aid = int(entry["aid"]) if entry.get("aid") else None
        rank = self.RANK.get(confidence, 0) or (2 if confidence in ("judged", "anchored") else 1)
        try:
            with self.store.lock:
                have = {r[1] for r in self.store.conn.execute("PRAGMA table_info(recaps)")}
                cols = ["id"] + [c for c in ("judged", "confidence") if c in have]
                sql = f"SELECT {','.join(cols)} FROM recaps WHERE ja=? AND ep=?"
                args = [ja, int(ep)]
                if aid and "aid" in have:
                    # never another edition's row: a page about the OVA is not
                    # an unjudged page about the series
                    sql += " AND (aid=? OR aid IS NULL)"
                    args.append(aid)
                old = [dict(zip(cols, r)) for r in self.store.conn.execute(sql, args)]
                gone = [r["id"] for r in old if self.RANK.get(self._conf_of(r), 1) <= rank]
                if gone:
                    self.store.conn.execute(
                        "DELETE FROM recaps WHERE id IN (%s)" % ",".join("?" * len(gone)), gone)
                self.store.conn.commit()
        except Exception as e:
            logger.log(f"[recap] could not drop the row this reading replaces: {type(e).__name__}")
        self._store(entry, int(ep), text, source,
                    judged=1 if confidence in ("judged", "anchored") else 0,
                    confidence=confidence, candidates=candidates, reason=reason,
                    anchor=anchor, scenes=scenes, archive=archive)
        if show_key:
            self.archive.note_choice(show_key, ep, url=source, confidence=confidence,
                                     reason=reason, anchor=anchor,
                                     candidates=[c.get("url", "") if isinstance(c, dict) else c
                                                 for c in (candidates or ())])

    # ---------------- digesting, judging, and the whole path ----------------

    def digest_page(self, llm, name, ep, text):
        """One page condensed by the `watching_digest` role: (digest, scenes).

        The scenes list is one line per scene or sketch, in order, and comes
        out of the same call rather than a second one. The digest is what she
        reads; the scenes go on the record, where recall can quote one.

        The call goes through the machine's store, keyed on the page itself.
        The role reads a page about an episode of a television programme and
        says what happens in it: that is the world, the prompt names nobody,
        and the second character reading the same page pays nothing for it.
        A digest by another model is a different row."""
        if llm is None or not text:
            return "", []
        if self.retrievals is None:
            got = self._digest_call(llm, name, ep, text)
            return ((got or {}).get("text") or "",
                    ((got or {}).get("meta") or {}).get("scenes") or [])
        key = "%s|ep%s|%s" % (name, ep, hashlib.sha1(
            str(text)[:8000].encode("utf-8", "replace")).hexdigest()[:16])
        row = self.retrievals.get_or_fetch(
            "page_digest", key, lambda: self._digest_call(llm, name, ep, text),
            model=self._role_model("watching_digest"))
        if not row:
            return "", []
        return row.get("text") or "", (row.get("meta") or {}).get("scenes") or []

    def _role_model(self, role):
        """The model a role runs on, so a page digested by one model is never
        read as though another had written it."""
        try:
            return str((self.config.model(role) or {}).get("model") or "")
        except Exception:
            return ""

    def _digest_call(self, llm, name, ep, text):
        """The one paid call behind `digest_page`. None means it came back with
        nothing, and nothing is stored, so the next reader may try again."""
        try:
            data, raw = llm.call_json("watching_digest", [
                {"role": "system", "content": self.config.prompt_text("watching_digest")},
                {"role": "user", "content": f"『{name}』第{ep}話\n\n{text[:8000]}"}])
        except Exception as e:
            logger.log(f"[recap] digest failed: {type(e).__name__}")
            return None
        if not isinstance(data, dict):
            # the role answered in prose; that answer is the digest, and there
            # are no scenes rather than invented ones
            dg = " ".join(str(raw or "").split())
            return {"text": dg, "meta": {"scenes": []}} if dg else None
        dg = " ".join(str(data.get("digest") or "").split())
        if str(data.get("about") or "").lower() in ("false", "no") or data.get("about") is False:
            # the page is not about this episode. That is a true answer about
            # the page and it is kept: nobody should pay to learn it twice.
            return {"text": "なし", "meta": {"scenes": []}}
        if not dg:
            return None
        scenes = [" ".join(str(s).split())[:200] for s in (data.get("scenes") or [])
                  if str(s or "").strip()][:20]
        return {"text": dg, "meta": {"scenes": scenes}}

    def judge_candidates(self, llm, ja, ep, scored, anchor="", anchor_kind=""):
        """Which candidate a viewer would trust, compared with each other and
        with the anchor: (index, why, corroborated).

        `corroborated` is the list of other candidates the judge says agreed
        with the winner, and it is what makes a row worth trusting: a single
        candidate agrees with nobody and stays provisional.

        The verdict is about the pages and not about her, so it goes in the
        machine's store keyed on the exact question asked -- the show, the
        episode, the anchor and every candidate digest in order. The second
        character comparing the same pages reads the answer."""
        if llm is None or not scored:
            return (0 if scored else -1), "", []
        body = "\n\n".join(
            f"[{i + 1}] source: {s.get('url', '')}\n{s.get('digest', '')}"
            for i, s in enumerate(scored))
        head = f"『{ja}』第{ep}話\n\n"
        if anchor:
            head += ("ANCHOR (" + (anchor_kind or "the official blurb") +
                     "). It is usually INCOMPLETE, so covering more than it is not a fault; "
                     "contradicting it on a stated outcome is:\n" + anchor[:2500] + "\n\n")
        if self.retrievals is None:
            return self._judge_result(self._judge_call(llm, head + body, len(scored)), scored)
        key = "%s|ep%s|%s" % (ja, ep, hashlib.sha1(
            (head + body).encode("utf-8", "replace")).hexdigest()[:16])
        row = self.retrievals.get_or_fetch(
            "digest_verdict", key, lambda: self._judge_call(llm, head + body, len(scored)),
            model=self._role_model("digest_judge"))
        return self._judge_result(row, scored)

    @staticmethod
    def _judge_result(row, scored):
        """A stored verdict read back as (index, why, corroborated). No row
        means the call failed, and the first candidate is taken, which is what
        this did before there was a store."""
        if not row:
            return 0, "", []
        meta = row.get("meta") or {}
        try:
            best = int(meta.get("best", 0))
        except (TypeError, ValueError):
            best = 0
        if best < -1 or best >= len(scored):
            best = 0
        corr = []
        for x in (meta.get("corroborated") or []):
            try:
                k = int(x)
            except (TypeError, ValueError):
                continue
            if 0 <= k < len(scored) and k != best:
                corr.append(k)
        return best, str(row.get("text") or ""), corr

    def _judge_call(self, llm, prompt, n):
        """The one paid call behind `judge_candidates`."""
        try:
            data, _raw = llm.call_json("digest_judge", [
                {"role": "system", "content": self.config.prompt_text("digest_judge")},
                {"role": "user", "content": prompt}])
        except Exception as e:
            logger.log(f"[recap] judge failed: {type(e).__name__}; taking the first")
            return None
        try:
            best = int((data or {}).get("best", 1)) - 1
        except (TypeError, ValueError):
            best = 0
        why = str((data or {}).get("why", ""))[:200]
        corr = []
        for x in ((data or {}).get("corroborated") or []):
            try:
                k = int(x) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= k < n and k != best:
                corr.append(k)
        if best < -1 or best >= n:
            best = 0
        # a row with no text is not stored at all, so a verdict that came with
        # no reason still says what was chosen
        return {"text": why or "(the judge gave no reason)",
                "meta": {"best": best, "corroborated": corr}}

    def synopsis(self, entry, ep, llm=None, anime_id=None, english="", avoid=(),
                 titles=(), video="", watched_seconds=0):
        """The whole path for one episode: cache, transcript, candidates,
        digests, one judge, one row.

        Returns `{text, source, digest, scenes, confidence, reason, anchor,
        candidates}` or None. Both watching paths go through this -- his,
        which notices a file opening, and her own, which used to take the
        first page that passed the section test and trust it forever."""
        c = self.config.recap
        if not c.enabled:
            return None
        ep = int(ep)
        ja = (entry.get("ja") or entry.get("title") or "").strip()
        if not ja:
            return None
        avoid = set(avoid or ())
        if anime_id and not entry.get("aid"):
            entry = dict(entry, aid=anime_id)
        # HER OWN WATCHING HAS NO ID and his list may still know one. A show on
        # her own list carries a title and nothing else, so the two sources
        # that need an id -- the episode page on his list's site and the
        # episode-title cross-check -- were out of reach for everything she
        # watched. The ranking answers nothing when the top two tie, so a
        # title that could be two works of his leaves the path exactly as it
        # was (`docs/resolver.md`).
        if not entry.get("aid") and not anime_id and self.anime_kb is not None:
            try:
                hit = self.anime_kb.resolve_strict(entry.get("title", "") or ja, ep=ep)
                if hit:
                    anime_id = int(hit[0])
                    entry = dict(entry, aid=anime_id)
                    logger.log(f"[recap] {entry.get('title') or ja} is mal:{anime_id} on his "
                               f"list; the English sources are reachable for it")
            except Exception as e:
                logger.log(f"[recap] no id for {entry.get('title') or ja} ({type(e).__name__})")
        aid = int(entry["aid"]) if entry.get("aid") else None
        mtype = entry.get("mtype", "")
        show_key = self.archive.show_key(anime_id, ja, entry.get("title", ""))
        # and the work's OTHER names, for the archives, which file a show under
        # whichever romanisation their uploader used: his list calls one work
        # `Makeine: Too Many Losing Heroines!` and the archive calls it
        # `Make Heroine ga Oosugiru!`, and nothing matched.
        names = list(titles or [])
        ent = self._entry_titles(aid)
        names += [n for n in ent if n and n not in names]
        have = self.row(ja, ep, aid=aid, mtype=mtype)
        # WHAT SHE ALREADY HAS, kept in hand for the whole call. Reading an
        # episode up again to finish its account is a search, and a search can
        # come back with nothing for reasons that have nothing to do with the
        # episode -- an engine rate-limiting a second browser, a host down for
        # a minute. Returning None then would take away the page she was
        # already told about and blank the line in her situation block, which
        # is a worse answer than the one this call was trying to improve.
        fallback = None
        if have and have.get("source") not in avoid and have.get("text"):
            # A ROW A JUDGE CHOSE IS THE END OF THE LOOKUP. The section test
            # asks whether a PAGE has a part about this episode, and it is
            # applied where a raw page is accepted from the cache. A row
            # written by `remember` is not a raw page: it is the candidate a
            # judge picked, already cut to this episode, and its `scenes` are
            # the digest of that one episode. The English episode list has no
            # 第3話 anywhere in it, so the test said no to a row two readers
            # had agreed on, the third character read みなみけ ep3 a second
            # time and her save ended up with the row twice (2026-09-07). A
            # judged row with no scenes on it is old enough to have been
            # written before the scene list existed, and still gets the test.
            trusted = have.get("confidence") in ("judged", "anchored") and (
                have.get("scenes")
                or self._episode_slice(have["text"], ep, self.slice_titles(aid, ja, ep)))
            # AND THE ACCOUNT IS WHAT COMPLETENESS MEANS NOW. A judged page is
            # one page: it settles which source to trust and it does not
            # settle what happened in the episode. So a cached row ends the
            # lookup only when the account beside it is at watched level, and
            # an episode read up before accounts existed is read up once more
            # -- once, because the account is then stored for the machine and
            # every character after that reads it without fetching anything.
            acct = self.account(entry, ep, aid=aid, mtype=mtype) \
                if self.accounts.enabled() else None
            if trusted:
                fallback = {"text": have["text"], "source": have.get("source", ""),
                            "digest": "", "scenes": have.get("scenes") or [],
                            "confidence": have["confidence"], "reason": have.get("reason", ""),
                            "anchor": have.get("anchor", ""),
                            "candidates": have.get("candidates") or [], "account": acct}
                # nobody to pay for a merge, or the account is already at
                # watched level: this is the end of the lookup, as it was
                needed = self.accounts.enabled() and llm is not None
                if not needed or self.accounts.complete(acct):
                    return fallback
                # AND THE READINGS ARE COUNTED FOR THE MACHINE. Each character
                # allowed herself `sensors.retrievals_max_retries` attempts at
                # an episode whose account was not finished, so three
                # processes spent up to nine readings on one episode of one
                # show and the ninth was no better than the third. The count
                # rides on the account itself, which every character reads.
                tries = int((acct or {}).get("tries") or 0)
                cap = int(getattr(c, "account_max_tries", 0) or 0)
                if cap and tries >= cap:
                    logger.log(f"[recap] {ja} ep{ep}: the account of it is "
                               f"{(acct or {}).get('level') or 'missing'} after {tries} "
                               f"reading(s) for the machine; it is left alone")
                    return fallback
                logger.log(f"[recap] {ja} ep{ep}: the page is {have['confidence']} but the "
                           f"account of the episode is {(acct or {}).get('level') or 'missing'}; "
                           f"reading it up once more (reading {tries + 1} of {cap or 'any'} "
                           f"for the machine)")
            else:
                logger.log(f"[recap] the cached page for {ja} ep{ep} is "
                           f"{have.get('confidence') or 'provisional'}; reading again")
        # ONE READING-UP PER EPISODE FOR THE WHOLE MACHINE. What has to happen
        # once is the SEARCH, not one fetch of one address: the candidate set
        # comes from a live search per process, and three processes searching
        # for the same episode get three different sets. On 2026-09-07 three
        # characters reached episode 5 of one show inside twenty-three
        # seconds; the first one's search found a page with a section for it,
        # the second one's found five pages without one, and because the
        # machine's store is written only after a search succeeds, the second
        # was nine seconds too early to read the first one's page and her
        # record of that episode is still empty. So the claim is taken here,
        # before the search, and held until the page is stored.
        kind = self._pool_kind(entry.get("kind"), ep)
        skey = self._shared_key(kind, ja, ep, aid, self._edition(aid, mtype))
        args = (entry, ep, llm, anime_id, english, avoid, ja, aid, mtype,
                show_key, names, video, watched_seconds)
        r = self.retrievals
        if r is None:
            return self._read_up(*args) or fallback
        mine, held = r.claim(self.SHARED_POOL, skey)
        if not mine:
            who = str((held or {}).get("by") or "another character")
            logger.log(f"[recap] {ja} ep{ep}: {who} is reading it up now; waiting for her page "
                       f"rather than running a second search")
            if r.wait_for(self.SHARED_POOL, skey, held=held) is not None:
                got = self._from_shared(ja, ep, kind, aid, mtype)
                if got:
                    return got
            # she found nothing, or she is still at it past the timeout: take
            # the claim over and look for a page of our own
            mine, held = r.claim(self.SHARED_POOL, skey)
        try:
            out = self._read_up(*args)
        except Exception:
            r.fail(self.SHARED_POOL, skey, "the reading-up raised")
            raise
        if out and out.get("text"):
            # `remember` wrote the machine's copy on the way through, so the
            # claim goes only now, with the row already there for a waiter
            r.release(self.SHARED_POOL, skey)
        else:
            r.fail(self.SHARED_POOL, skey, "nothing usable was found")
        if not (out and out.get("text")) and fallback:
            logger.log(f"[recap] {ja} ep{ep}: the reading-up found nothing this time; "
                       f"what she already had stands")
        return out or fallback

    def account(self, entry, ep, aid=None, mtype=""):
        """The stored account of one episode -- everything read about it,
        merged -- or None. Reads the machine's copy when her save has none and
        writes it into her save on the way past, the same as a page does."""
        ja = (entry.get("ja") or entry.get("title") or "").strip()
        if not ja or not ep:
            return None
        aid = aid or (int(entry["aid"]) if entry.get("aid") else None)
        skey = self._shared_key("anime", ja, ep, aid, self._edition(aid, mtype) if aid else "")
        return self.accounts.row(ja, int(ep), aid=aid, retrievals=self.retrievals,
                                 shared_key=skey)

    def _build_account(self, entry, ep, llm, digests, anchor_text, anchor_url,
                       anchor_kind, anchor_row, show_key, ja, aid, mtype, english,
                       ep_title=""):
        """One account of the episode out of everything that was read for it.

        Called at every exit of `_read_up` that has material, including the
        two where no web page survived: an episode whose only source is its
        own subtitle file still has an account, and it is a better one than an
        episode with four blog posts and no transcript."""
        if not self.accounts.enabled() or llm is None:
            return None
        try:
            return self.accounts.build(
                entry, ep, llm, digests=digests, anchor_text=anchor_text,
                anchor_url=anchor_url, anchor_kind=anchor_kind, transcript=anchor_row,
                show_key=show_key, retrievals=self.retrievals,
                shared_key=self._shared_key("anime", ja, ep, aid,
                                            self._edition(aid, mtype) if aid else ""),
                ep_title=ep_title, english=english)
        except Exception as e:
            logger.log(f"[account] {ja} ep{ep}: the merge raised: {type(e).__name__}")
            return None

    def _read_up(self, entry, ep, llm, anime_id, english, avoid, ja, aid, mtype,
                 show_key, names, video, watched_seconds):
        """The reading-up itself, under the claim: the episode's own subtitle
        file as the anchor, the ranked sources and the search as candidates,
        one digest each, one judge over all of them, and one stored row.

        Split out of `synopsis` so that the whole of it happens once for the
        machine rather than once per character."""
        # the transcript first: it is the anchor, and the fallback digest when
        # no web candidate survives
        anchor_text, anchor_url, anchor_kind, anchor_row = "", "", "", None
        try:
            anchor_row = self.transcripts.anchor(
                entry, ep, titles=names, show_key=show_key, anime_id=anime_id, llm=llm,
                video=video, watched_seconds=watched_seconds,
                transcribe=self.transcribe, retrievals=self.retrievals,
                shared_key=self._shared_key("anime", ja, ep, aid=aid, mtype=mtype))
        except Exception as e:
            logger.log(f"[recap] transcript failed: {type(e).__name__}")
        if anchor_row and anchor_row.get("account"):
            anchor_text = anchor_row["account"]
            anchor_url = anchor_row.get("source", "")
            anchor_kind = "the episode's own subtitle file, as an account of its scenes in order"
        # A WIDER SET THAN THE JUDGE NEEDS. Four candidates settle "which page
        # would a viewer trust"; they do not settle "what happens in the
        # episode", because a running gag or a background reference is
        # typically named by one 感想 post out of six and by none of the rest.
        # The judge still sees all of them and still picks one.
        cands = self.candidates(entry, ep, avoid=avoid, anime_id=anime_id, english=english,
                                want=int(getattr(self.config.recap, "account_candidates", 0) or 0)
                                if self.accounts.enabled() else 0,
                                tried_max=int(getattr(self.config.recap, "account_tried_max", 0) or 0)
                                if self.accounts.enabled() else 0,
                                page_chars=int(getattr(self.config.recap, "account_page_chars", 0) or 0)
                                if self.accounts.enabled() else 0)
        if not anchor_text:
            shorts = [x for x in cands if x.get("anchor_only")]
            if shorts:
                # the FULLEST short page, not the shortest: an anchor is a
                # fact check, and more of the episode checks more of it
                pick = max(shorts, key=lambda x: len(x["text"]))
                anchor_text, anchor_url = pick["text"], pick["url"]
                anchor_kind = "the official blurb"
        scored = []
        for x in cands:
            if x.get("anchor_only") and x["url"] == anchor_url:
                continue
            dg, scenes = self.digest_page(llm, ja, ep, x["text"])
            if not dg or dg.startswith("なし"):
                logger.log(f"[recap] {x['url'][:70]}: not about ep{ep}; out")
                continue
            self.archive.save(show_key, ep, "digest", dg, url=x["url"],
                              show=entry.get("title", ""), ja=ja)
            scored.append({**x, "digest": dg, "scenes": scenes})
        if not scored:
            if anchor_text and anchor_row:
                # nothing on the web survived and the episode's own dialogue
                # did: the transcript's account is the honest answer
                self.remember(entry, ep, anchor_text, anchor_url, confidence="anchored",
                              candidates=[{"url": x["url"], "verdict": "no digest"} for x in cands],
                              reason="no web candidate survived; the transcript's own account",
                              anchor=anchor_url, scenes=anchor_row.get("scenes") or [],
                              show_key=show_key)
                acct = self._build_account(entry, ep, llm, [], anchor_text, anchor_url,
                                           anchor_kind, anchor_row, show_key, ja, aid,
                                           mtype, english)
                return {"text": anchor_text, "source": anchor_url, "digest": anchor_text,
                        "scenes": anchor_row.get("scenes") or [], "confidence": "anchored",
                        "reason": "the transcript's own account", "anchor": anchor_url,
                        "candidates": [x["url"] for x in cands], "account": acct}
            if anchor_text and anchor_url:
                # the official blurb was the only thing found. It is never
                # wrong and never complete, so it is a thin true answer and
                # provisional: read again next time, when the search may have
                # more. Setting it aside as the anchor and then storing
                # nothing would be worse than what this replaced.
                dg, sc = self.digest_page(llm, ja, ep, anchor_text)
                if dg and not dg.startswith("なし"):
                    self.remember(entry, ep, anchor_text, anchor_url, confidence="provisional",
                                  candidates=[{"url": anchor_url, "verdict": "the only candidate"}],
                                  reason="the official blurb, and nothing else was found",
                                  anchor="", scenes=sc, show_key=show_key)
                    logger.log(f"[recap] {ja} ep{ep}: only the official blurb; kept provisionally")
                    acct = self._build_account(
                        entry, ep, llm,
                        [{"url": anchor_url, "source": "the official blurb",
                          "digest": dg, "scenes": sc}],
                        anchor_text, anchor_url, "the official blurb", None,
                        show_key, ja, aid, mtype, english)
                    return {"text": anchor_text, "source": anchor_url, "digest": dg,
                            "scenes": sc, "confidence": "provisional",
                            "reason": "the official blurb, and nothing else was found",
                            "anchor": "", "candidates": [anchor_url], "account": acct}
            logger.log(f"[recap] {ja} ep{ep}: nothing usable found")
            return None
        best, why, corr = (0, "one candidate", []) if len(scored) == 1 else \
            self.judge_candidates(llm, ja, ep, scored, anchor_text, anchor_kind)
        if best < 0:
            logger.log(f"[recap] {ja} ep{ep}: the judge rejected all {len(scored)} digest(s)")
            return None
        win = scored[best]
        if anchor_text:
            conf = "anchored"
        elif len(scored) > 1 and corr:
            conf = "judged"
        else:
            conf = "provisional"
        verdicts = [{"url": x["url"], "rank": x.get("rank"), "source": x.get("source", ""),
                     "verdict": ("chosen" if i == best else
                                 "agreed" if i in corr else "not chosen")}
                    for i, x in enumerate(scored)]
        self.archive.save(show_key, ep, "judge",
                          json.dumps({"best": win["url"], "why": why, "confidence": conf,
                                      "anchor": anchor_url, "candidates": verdicts},
                                     ensure_ascii=False, indent=1),
                          url=win["url"], ext=".json", show=entry.get("title", ""), ja=ja)
        scenes = win.get("scenes") or (anchor_row.get("scenes") if anchor_row else []) or []
        self.remember(entry, ep, win["text"], win["url"], confidence=conf, candidates=verdicts,
                      reason=why, anchor=anchor_url, scenes=scenes, show_key=show_key)
        logger.log(f"[recap] {ja} ep{ep}: {len(cands)} page(s) read, {len(scored)} about it, "
                   f"kept {win['url'][:70]} ({conf})")
        # AND THE ACCOUNT, out of every digest rather than out of the winner.
        # This is the last thing the reading-up does, so a failure in it
        # leaves the row and the digest exactly as they were before it existed.
        acct = self._build_account(entry, ep, llm, scored, anchor_text, anchor_url,
                                   anchor_kind, anchor_row, show_key, ja, aid, mtype, english)
        return {"text": win["text"], "source": win["url"], "digest": win["digest"],
                "scenes": scenes, "confidence": conf, "reason": why, "anchor": anchor_url,
                "candidates": verdicts, "account": acct,
                "quotes": (anchor_row or {}).get("quotes") or []}

    def character_page(self, name, show, query_template, hosts):
        """A fan-encyclopedia article about a character: (text, full name, url).

        The URL of a pixiv dictionary article is its title, URL-encoded, so the
        full name comes free with the hit (丸井みつば from /a/%E4%B8%B8...).
        Cached in `recaps` as kind "character" under "show:name", text and
        source; the caller condenses it and caches nothing of its own."""
        c = self.config.recap
        key = f"{show}:{name}"
        hit = self.cached(key, 0, "character")
        if hit:
            full = urllib.parse.unquote(hit[1].rsplit("/", 1)[-1]) if hit[1] else name
            return hit[0], full, hit[1]
        if webdriver is None or not c.enabled:
            return "", "", ""
        query = query_template.format(show=show, name=name)
        driver = self._open()
        try:
            urls = self._search(driver, query)
            for u in urls:
                if not any(h in u for h in hosts):
                    continue
                html = self._page_source(driver, u)
                if not html:
                    continue
                body = self._extract(html, u)
                if body and len(body) >= c.min_chars:
                    self._store({"title": name, "ja": key, "kind": "character"}, 0, body[:9000], u)
                    full = urllib.parse.unquote(u.rsplit("/", 1)[-1])
                    logger.log(f"[recap] character {name} ({show}): {len(body)} chars from {u}")
                    return body[:9000], full, u
            return "", "", ""
        finally:
            self._close(driver)

    # ---------------- the machinery ----------------

    def _harvest(self, entry, ja, ep, avoid=()):
        c = self.config.recap
        query = c.query_template.format(title=ja, ep=ep)
        ep_titles = self.slice_titles(entry.get("aid"), ja, ep)
        driver = self._open()
        try:
            urls = self._search(driver, query)
            if not urls:
                # a whole-series page has no episode number; try the bare title
                urls = self._search(driver, f"{ja} {c.series_suffix}")
            tried = 0
            for u in urls:
                if tried >= c.candidates_max:
                    break
                if any(b in u for b in c.blocked_hosts) or u in avoid:
                    continue
                tried += 1
                html = self._page_source(driver, u)
                if not html:
                    continue
                body = self._extract(html, u)
                sliced, why = self._slice_and_why(body, ep, ep_titles,
                                                  self.page_heading(html))
                # The whole body used to be accepted when no episode section
                # was found, which is how a manga volume's bookstore page was
                # stored as an episode synopsis. No section, no synopsis; the
                # next candidate gets its turn.
                if not sliced:
                    logger.log(f"[recap] {u[:80]}: not about ep{ep} -- {why}")
                    continue
                if len(sliced) >= c.min_chars:
                    return sliced[:c.max_chars], u
            return None, ""
        finally:
            self._close(driver)

    def _open(self):
        profile = tempfile.mkdtemp(prefix=PROFILE_PREFIX)
        o = webdriver.ChromeOptions()
        if getattr(self.config.recap, "headless", True):
            o.add_argument("--headless=new")
        o.add_argument("--disable-blink-features=AutomationControlled")
        o.add_experimental_option("excludeSwitches", ["enable-automation"])
        o.add_experimental_option("useAutomationExtension", False)
        o.add_argument("--no-sandbox")
        o.add_argument("--disable-dev-shm-usage")
        o.add_argument("--disable-gpu")
        o.add_argument("--window-size=1280,3200")
        o.page_load_strategy = "none"
        o.add_argument("user-data-dir=" + profile)
        o.add_argument("user-agent=" + self.config.recap.user_agent)
        d = webdriver.Chrome(options=o)
        d.set_page_load_timeout(self.config.recap.page_timeout_seconds)
        d._recap_profile = profile     # so _close reaps this exact tree and dir
        try:
            d.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        except Exception:
            pass
        return d

    def _close(self, driver):
        """quit() covers the clean path; then kill any Chrome/chromedriver
        still bound to THIS temp profile (headless Chrome orphans renderers,
        and a bot killed mid-fetch never runs quit at all), and remove the
        temp profile dir. Without this the throwaway profiles pile up as
        forever-running headless Chrome and disk dirs."""
        profile = getattr(driver, "_recap_profile", "")
        try:
            driver.quit()
        except Exception:
            pass
        if profile:
            try:
                from sensors import chrome_reaper
                chrome_reaper.kill(profile, log=lambda m: None)
            except Exception:
                pass
            try:
                import shutil
                shutil.rmtree(profile, ignore_errors=True)
            except Exception:
                pass

    @staticmethod
    def sweep_orphans(log=None):
        """Kill any recap Chrome left by a fetch that was killed before _close
        (a bot restart mid-fetch), and remove its temp dir. Reap on the way
        in: called from __init__ so a fresh bot owns a clean slate."""
        base = tempfile.gettempdir()
        n = 0
        try:
            import shutil
            from sensors import chrome_reaper
            for name in os.listdir(base):
                profile = os.path.join(base, name)
                # a profile is a DIRECTORY. The test's own scratch db and any
                # stray file share the prefix, rmtree does nothing to a file,
                # and the count then reported the same six every boot forever.
                if not name.startswith(PROFILE_PREFIX) or not os.path.isdir(profile):
                    continue
                try:
                    chrome_reaper.kill(profile, log=lambda m: None)
                except Exception:
                    pass
                shutil.rmtree(profile, ignore_errors=True)
                if not os.path.exists(profile):
                    n += 1
        except Exception:
            pass
        if n and log:
            log(f"[recap] swept {n} orphaned recap Chrome profile(s)")
        return n

    # ---------------- the ranked sources, fetched without a browser ----------------
    #
    # Three of the four best sources are a plain keyless HTTP GET and need no
    # Chrome at all, so they are fetched in parallel and the browser is only
    # ever in the critical path for the Japanese blog search. Two of them are
    # on `blocked_hosts` today and the ban is lifted for exactly these two
    # pages, by his approval in `docs/episode-summaries-plan.md`: the ban was
    # written to keep a romaji title off database pages with no prose, and an
    # episode page is the exception. Japanese Wikipedia stays banned, and
    # correctly -- its episode table has title, writer, storyboard and air
    # date, and no summary column at all.

    def _http(self, url, limit=1_200_000, accept="text/html"):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": self.config.recap.user_agent, "Accept": accept,
                "Accept-Language": "en,ja;q=0.8"})
            with urllib.request.urlopen(
                    req, timeout=float(getattr(self.config.recap, "http_timeout_seconds", 20))) as fh:
                return fh.read(limit).decode("utf-8", "replace")
        except Exception as e:
            # by exception TYPE only: a failing URL is quoted in the message
            # and a URL can carry a token
            logger.log(f"[recap] keyless fetch failed ({type(e).__name__})")
            return ""

    @staticmethod
    def _meta(html, prop):
        m = re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="(.*?)"' % re.escape(prop),
                      html or "", re.S)
        if not m:
            m = re.search(r'<meta[^>]+content="(.*?)"[^>]+(?:property|name)="%s"' % re.escape(prop),
                          html or "", re.S)
        return _html.unescape(m.group(1)).strip() if m else ""

    def list_site_episode(self, anime_id, ep):
        """The episode page on his own list's site: the synopsis is the page's
        own description meta tag, one regex and no container walk. English,
        and scene by scene on a multi-sketch show, which is the case every
        Japanese source has been thin on. It names its upstream in the text
        (`(Source: Wikipedia)`), which says how complete to expect it to be."""
        if not anime_id:
            return "", "", ""
        url = str(getattr(self.config.recap, "list_episode_url",
                          "https://myanimelist.net/anime/{id}/_/episode/{ep}")
                  ).format(id=int(anime_id), ep=int(ep))
        html = self._http(url)
        if not html:
            return "", url, ""
        text = self._meta(html, "og:description")
        # the site prefixes its own title line on some pages
        text = re.sub(r"^Looking for information on .*?\?\s*", "", text).strip()
        return text, url, html

    @classmethod
    def page_heading(cls, html):
        """What the page CALLS ITSELF: the social-card title, the document
        title and the first two headings, run together.

        `_extract` returns the article container, and on every blog engine his
        search finds, the container starts under the post's headline -- so the
        number of the episode, which the headline almost always carries, was
        thrown away before the section test ever saw the page."""
        if not html:
            return ""
        bits = [cls._meta(html, "og:title")]
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
        if m:
            bits.append(m.group(1))
        bits += re.findall(r"(?is)<h1[^>]*>(.*?)</h1>", html)[:2]
        out = []
        for b in bits:
            t = " ".join(_html.unescape(re.sub(r"(?s)<[^>]+>", " ", b or "")).split())
            if t and t not in out:
                out.append(t)
        return " | ".join(out)[:400]

    def cached_episode_titles(self, anime_id):
        """`{episode: [subtitle, ...]}` for one series FROM WHAT IS ALREADY ON
        FILE, and nothing fetched.

        The slice test runs inside a search loop and on the reply path, where
        a request nobody asked for would be a fetch the caller did not ask
        for. `episode_titles` is the one that goes and looks; this reads what
        that left behind."""
        if not anime_id:
            return {}
        hit = self.cached(f"mal:{int(anime_id)}", 0, "eptitles")
        if not hit:
            return {}
        try:
            raw = json.loads(hit[0])
        except (ValueError, TypeError):
            return {}
        out = {}
        for k, row in (raw or {}).items():
            try:
                n = int(k)
            except (TypeError, ValueError):
                continue
            names = [str((row or {}).get(f) or "").strip()
                     for f in ("ja", "romaji", "en")]
            names = [t for t in names if len(t) >= self.SUBTITLE_MIN_CHARS]
            if names:
                out[n] = names
        return out

    def slice_titles(self, anime_id, ja="", ep=0):
        """The subtitles the episode-slice test may recognise: the series'
        episode index as it is on file, and this episode's own title off the
        account of it, which is where a Japanese part title ends up for a
        series whose index carries English only."""
        out = self.cached_episode_titles(anime_id)
        if not (ja and ep) or self.accounts is None:
            return out
        try:
            row = self.accounts.row(ja, int(ep), aid=anime_id, adopt=False)
        except Exception:
            row = None
        title = str((row or {}).get("ep_title") or "").strip()
        if len(title) >= self.SUBTITLE_MIN_CHARS:
            have = list(out.get(int(ep)) or [])
            # a part title is written 「A／B」 as often as not, and each half is
            # what a post's own heading carries
            for t in [title] + [x.strip() for x in re.split(r"[／/]", title)]:
                if len(t) >= self.SUBTITLE_MIN_CHARS and t not in have:
                    have.append(t)
            out[int(ep)] = have
        return out

    def episode_titles(self, anime_id, entry=None):
        """Every episode's English, romaji and Japanese subtitle for one
        series, from one request, cached under kind `eptitles`.

        This is what answers the case nothing catches today: a page whose
        number matches and whose episode is another series' -- a bookstore
        listing for volume 9 of the manga was once accepted as episode 9, and
        only the missing-section test caught it, by luck. It also gives the
        search a better query for a show whose numbering is ambiguous across
        seasons."""
        if not anime_id:
            return {}
        key = f"mal:{int(anime_id)}"
        hit = self.cached(key, 0, "eptitles")
        if hit:
            try:
                return {int(k): v for k, v in json.loads(hit[0]).items()}
            except (ValueError, AttributeError):
                pass
        url = str(getattr(self.config.recap, "list_episode_index_url",
                          "https://myanimelist.net/anime/{id}/_/episode")).format(id=int(anime_id))
        html = self._http(url)
        if not html:
            return {}
        out = {}
        for block in html.split('<tr class="episode-list-data">')[1:]:
            m = re.search(r'class="episode-number[^"]*"[^>]*data-raw="(\d+)"', block)
            if not m:
                continue
            n = int(m.group(1))
            en = re.search(r'class="episode-title[^"]*">\s*<a[^>]*>(.*?)</a>', block, re.S)
            other = re.search(r'<span class="di-ib">(.*?)</span>', block, re.S)
            romaji, ja = "", ""
            if other:
                t = _html.unescape(re.sub(r"<[^>]+>", "", other.group(1))).replace("\xa0", " ").strip()
                mm = re.match(r"(.*?)\s*\((.*)\)\s*$", t, re.S)
                romaji, ja = (mm.group(1).strip(), mm.group(2).strip()) if mm else (t, "")
            out[n] = {"en": _html.unescape(re.sub(r"<[^>]+>", "", en.group(1))).strip() if en else "",
                      "romaji": romaji, "ja": ja}
        if out:
            self._store({"title": (entry or {}).get("title", ""), "ja": key, "kind": "eptitles"},
                        0, json.dumps(out, ensure_ascii=False), url)
            logger.log(f"[recap] episode titles for {anime_id}: {len(out)} episode(s)")
        return out

    _WIKI_TAGS = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>|\{\{[^{}]*\}\}|'''|''|<[^>]+>", re.S)

    def _wikitext(self, url):
        """One article's wikitext, or '' when there is no such article."""
        raw = self._http(url, accept="application/json")
        try:
            data = json.loads(raw or "{}")
        except ValueError:
            return ""
        if "error" in data:
            return ""
        return (((data.get("parse") or {}).get("wikitext") or {}).get("*")) or ""

    @staticmethod
    def _wiki_norm(s):
        """A heading or a title reduced to what the two have in common: the
        year in brackets, the italics and the spacing go, the season marks
        (`!!`, `♪♪`, `2`) stay, because they are the difference between two
        series in one article."""
        s = re.sub(r"''+", "", str(s or ""))
        s = re.sub(r"\([^)]*\)", " ", s)
        return re.sub(r"[^0-9a-z!♪×]+", "", s.lower())

    @classmethod
    def _wiki_section(cls, body):
        """{episode: summary} for one section of an episode-list article."""
        out = {}
        for block in re.split(r"\{\{\s*Episode list", body, flags=re.I)[1:]:
            block = block.split("\n}}")[0]
            fields = {}
            for m in re.finditer(r"\n\s*\|\s*([A-Za-z0-9]+)\s*=\s*(.*?)(?=\n\s*\||\Z)", block, re.S):
                fields[m.group(1)] = m.group(2).strip()
            num = fields.get("EpisodeNumber2") or fields.get("EpisodeNumber") or ""
            summary = fields.get("ShortSummary") or ""
            if not num.strip().isdigit() or not summary:
                continue
            summary = cls._WIKI_TAGS.sub("", summary)
            summary = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", summary)
            summary = re.sub(r"\s+", " ", _html.unescape(summary)).strip()
            if summary:
                out[int(num.strip())] = summary
        return out

    def wikipedia_episodes(self, english_title, entry=None):
        """English Wikipedia's `List of <show> episodes`, as {episode: summary}.

        The article carries every episode, so one request serves a whole
        series and it is cached under kind `wikieps`. The summary column runs
        60 to 120 words with outcomes, which is the other source that named
        every scene in order for every episode checked."""
        title = str(english_title or "").strip()
        if not title:
            return {}
        key = f"wiki:{title.lower()}"
        hit = self.cached(key, 0, "wikieps")
        if hit:
            try:
                return {int(k): v for k, v in json.loads(hit[0]).items()}
            except (ValueError, AttributeError):
                pass
        form = str(getattr(self.config.recap, "wikipedia_list_title",
                           "List of {title} episodes"))
        api = str(getattr(self.config.recap, "wikipedia_api",
                          "https://en.wikipedia.org/w/api.php"))
        text, url = "", ""
        # His list writes a title with spaces the article does not have
        # (`Yuru Yuri♪♪` against `YuruYuri`), and a season's article is often
        # the first season's with a section per season -- so the spaceless
        # form and the base title get a try, and the section match below is
        # what keeps the right season.
        base = re.sub(r"(♪+|!!+|:?\s*(2nd|3rd|4th)\s+Season|\s+S\d)\s*$", "",
                      title, flags=re.I).replace(" ", "")
        # AND THE SHOW'S OWN ARTICLE, last. A series short enough not to have
        # an episode-list article of its own keeps its episode table in the
        # main article, and this source was then simply absent for it: on
        # 2026-09-08 エグザンプル had no `List of ... episodes` article
        # under any of the three forms, so the only English summary of its
        # episodes -- one that names every scene with its outcome -- was never
        # read for any of them. `_wiki_section` finds the same
        # `{{Episode list}}` templates wherever in an article they sit.
        pages = [form.format(title=n) for n in (title, title.replace(" ", ""), base)]
        pages += [title, title.replace(" ", "")]
        seen_pages = set()
        for page in pages:
            if page in seen_pages:
                continue
            seen_pages.add(page)
            url = (api + "?action=parse&prop=wikitext&format=json&redirects=1&page="
                   + urllib.parse.quote(page))
            text = self._wikitext(url)
            if text:
                break
        if not text:
            logger.log(f"[recap] no English episode list for {title}")
            self._store({"title": title, "ja": key, "kind": "wikieps"}, 0, "{}", url)
            return {}
        # ONE ARTICLE, SEVERAL SERIES. `List of YuruYuri episodes` carries
        # five, each with its own section and its own episode 1, so reading
        # the whole article gives episode 3 of whichever section came last --
        # a short spin-off's sports tournament in place of the season's
        # Valentine episode. So the article is read section by section, and a
        # section is used only when its heading is this show; when several
        # sections carry the number and none is this show, nothing is
        # returned, because the wrong episode is worse than no episode.
        sections = []
        heads = list(re.finditer(r"(?m)^(={2,})\s*(.+?)\s*\1\s*$", text))
        for i, h in enumerate(heads):
            body = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
            sections.append((h.group(2), body))
        if not sections:
            sections = [("", text)]
        parsed = []
        pulled = 0
        for head, body in sections:
            eps = self._wiki_section(body)
            if not eps and pulled < 3:
                # a list article that transcludes one sub-article per season
                # (`{{:K-On!!}}`) has no summaries of its own at all
                m = re.search(r"\{\{:\s*([^}|\n]+?)\s*\}\}", body)
                if m:
                    pulled += 1
                    sub = self._wikitext(
                        api + "?action=parse&prop=wikitext&format=json&redirects=1&page="
                        + urllib.parse.quote(m.group(1)))
                    eps = self._wiki_section(sub) if sub else {}
            if eps:
                parsed.append((head, eps))
        out = {}
        if len(parsed) == 1:
            out = parsed[0][1]
        elif parsed:
            want = self._wiki_norm(title)
            hit = [e for h, e in parsed if self._wiki_norm(h) == want]
            if not hit:
                hit = [e for h, e in parsed
                       if want and self._wiki_norm(h).startswith(want)
                       and len(self._wiki_norm(h)) <= len(want) + 6]
            if len(hit) == 1:
                out = hit[0]
            else:
                logger.log(f"[recap] the English episode list for {title} covers "
                           f"{len(parsed)} series and none of its sections is this one; not used")
        self._store({"title": title, "ja": key, "kind": "wikieps"}, 0,
                    json.dumps(out, ensure_ascii=False), url)
        logger.log(f"[recap] English episode list for {title}: {len(out)} episode(s)")
        return out

    def _total_episodes(self, entry, anime_id=None):
        """How many episodes this work has, from his own mirror: 0 when
        nobody knows. It is the one fact that makes a page's own numbering
        checkable."""
        try:
            n = int(entry.get("eps") or 0)
        except (TypeError, ValueError):
            n = 0
        aid = anime_id or entry.get("aid")
        if not n and aid and self.anime_kb is not None:
            try:
                n = int((self.anime_kb.entry(aid) or {}).get("eps") or 0)
            except Exception:
                n = 0
        return n

    # `第2話「...」` / `episode 2` -- another episode's number named in a page
    _EP_MARK = re.compile(r"第\s*(\d{1,3})\s*話|\bep(?:isode)?\.?\s*(\d{1,3})\b", re.I)
    # what a page says when it is about to preview the NEXT episode
    _NEXT_MARKS = ("次回予告", "次回、", "次回は", "つづく", "to be continued")

    @classmethod
    def past_the_end(cls, text, ep, total):
        """True when a page names an episode this work does not have.

        The existing guard (`wrong_episode`) only fires when a page names
        ANOTHER episode of the same entry by its subtitle, so a namesake's
        episode 1 passes it -- which is exactly what happened on 2026-09-04:
        the page fetched for a one-episode OVA was the television series'
        first episode and ended in a preview of its second. A work with one
        episode has no next episode and no episode 2, and that is arithmetic
        rather than a judgement."""
        if not text or not total or int(total) <= 0:
            return False
        total = int(total)
        if int(ep or 0) > total:
            return True
        head = str(text)
        for m in cls._EP_MARK.finditer(head):
            for g in m.groups():
                if not g:
                    continue
                try:
                    n = int(g)
                except ValueError:
                    continue
                if 0 < n <= 999 and n > total:
                    return True
        if total == 1 and any(mk in head for mk in cls._NEXT_MARKS):
            return True
        return False

    @staticmethod
    def wrong_episode(text, ep, titles):
        """True when a page's number matches and its episode does not.

        The page names an episode subtitle beside the number; if that subtitle
        belongs to a DIFFERENT episode of this series and this episode's own
        subtitle is nowhere in the page, the page is about another episode --
        or another series whose episode N shares the number and nothing
        else."""
        if not text or not titles:
            return False
        mine = titles.get(int(ep)) or titles.get(str(ep)) or {}
        own = [str(mine.get(k) or "").strip() for k in ("ja", "en", "romaji")]
        own = [t for t in own if len(t) >= 4]
        if any(t and t in text for t in own):
            return False
        head = text[:400]
        for n, row in titles.items():
            if int(n) == int(ep):
                continue
            for k in ("ja", "en"):
                t = str((row or {}).get(k) or "").strip()
                if len(t) >= 6 and t in head:
                    return True
        return False

    def _search(self, driver, query):
        """Bing first, then DuckDuckGo HTML; the organic result URLs in order."""
        c = self.config.recap
        for engine in c.search_engines:
            url = engine.format(q=urllib.parse.quote(query))
            html = self._page_source(driver, url, marker=None, need=c.search_min_html)
            if not html:
                continue
            urls = self._result_links(html)
            if urls:
                return urls
        return []

    @staticmethod
    def _result_links(html):
        out, seen = [], set()
        # bing: <li class="b_algo"> ... <h2><a href="URL"> ; ddg: class="result__a" (href in either order) or uddg=
        for m in re.finditer(r'<a\b[^>]*\bclass="[^"]*result__a[^"]*"[^>]*>', html):
            hm = re.search(r'href="(https?://[^"]+)"', m.group(0))
            if hm:
                out.append(_html.unescape(hm.group(1)))
        for m in re.finditer(r'uddg=([^&"]+)', html):
            try:
                out.append(urllib.parse.unquote(m.group(1)))
            except Exception:
                pass
        for m in re.finditer(r'<h2>\s*<a[^>]+href="(https?://[^"]+)"', html):
            out.append(_html.unescape(m.group(1)))
        clean = []
        for u in out:
            u = u.split("#")[0]
            host = urllib.parse.urlparse(u).netloc
            if not host or "bing.com" in host or "duckduckgo.com" in host or "microsoft" in host:
                continue
            if u in seen:
                continue
            seen.add(u)
            clean.append(u)
        return clean

    def _page_source(self, driver, url, marker=None, need=None):
        c = self.config.recap
        need = need if need is not None else c.page_min_html
        try:
            driver.get(url)
        except Exception:
            pass
        html = ""
        still = 0
        for i in range(c.poll_max):
            time.sleep(c.poll_seconds)
            try:
                h = driver.page_source
            except Exception:
                break
            grew = len(h) > len(html)
            if grew:
                html = h
            if "ERR_NAME_NOT_RESOLVED" in html or "can’t be reached" in html:
                return ""
            if len(html) >= need and (marker is None or marker in html):
                break
            # A small page can never reach the threshold, so it used to cost
            # the full poll budget every time -- 15.6 seconds for an old
            # show's official episode page, which is 9 KB of plain HTML and
            # complete on the first poll. The threshold was standing in for
            # "the page has finished arriving"; two polls with no growth say
            # that directly.
            still = 0 if grew else still + 1
            # ...but a page that has not started arriving has also stopped
            # growing. A site that redirects or renders late sat at 3.4 KB
            # for two polls and was taken as finished, and the episode's
            # section came out as its own title, 37 characters, which then
            # stood as the anchor. So the break needs a few polls behind it
            # and a page big enough to be a page.
            if (still >= int(getattr(c, "poll_settle", 2) or 2)
                    and i >= int(getattr(c, "poll_min", 4) or 4) - 1
                    and len(html) >= int(getattr(c, "poll_min_html", 8000) or 8000)):
                break
        return html

    def _extract(self, html, url):
        host = urllib.parse.urlparse(url).netloc
        sels = []
        for h, s in HOST_SELECTORS.items():
            if h in host:
                sels = list(s)
                break
        sels += GENERIC_SELECTORS
        for sel in sels:
            block = self._first_block(html, sel)
            if block and len(block) >= 200:
                return block
        return self._strip(html)

    def _first_block(self, html, selector):
        """A cheap container grab by class/id/tag (no live DOM: the html is a
        string we already have). class '.x' -> first element carrying x."""
        if selector.startswith("."):
            cls = re.escape(selector[1:])
            m = re.search(r'<(\w+)[^>]*class="[^"]*\b' + cls + r'\b[^"]*"[^>]*>', html)
        elif selector.startswith("#"):
            idv = re.escape(selector[1:])
            m = re.search(r'<(\w+)[^>]*id="' + idv + r'"[^>]*>', html)
        else:
            m = re.search(r'<(' + re.escape(selector) + r')[\s>]', html)
        if not m:
            return ""
        tag = m.group(1)
        # from the match, walk tags to find the matching close (shallow nest ok)
        start = m.end()
        depth = 1
        pos = start
        pat = re.compile(r'</?' + tag + r'[\s>]', re.I)
        for mm in pat.finditer(html, start):
            depth += 1 if html[mm.start():mm.start() + 2].lower() != "</" else -1
            if depth == 0:
                pos = mm.start()
                break
        else:
            pos = min(len(html), start + 40000)
        return self._strip(html[start:pos])

    @staticmethod
    def _strip(html):
        html = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<nav.*?</nav>"
                      r"|<aside.*?</aside>|<footer.*?</footer>|<header.*?</header>", " ", html)
        txt = re.sub(r"(?s)<[^>]+>", " ", html)
        txt = _html.unescape(txt)
        txt = re.sub(r"[ \t　]+", " ", txt)
        txt = re.sub(r"\n\s*\n+", "\n", txt)
        return txt.strip()

    @classmethod
    def _running_order(cls, seg):
        """True when the slice is the episode's running order rather than an
        account of it: three or more of a programme table's own headings and
        almost no sentences. Measured on the rows already fetched for one
        show -- the four blog pages carry none of the headings and a full
        stop every 44 to 120 characters, the table carries eight headings and
        one full stop in 683. Both conditions, so a post that happens to
        quote the preview and the ending theme is not thrown away."""
        if not seg:
            return False
        marks = sum(1 for m in RUNNING_ORDER_MARKS if m in seg)
        return marks >= 3 and seg.count("。") <= len(seg) / 200.0

    # the blog furniture a post ends at; the first five are lists of OTHER
    # articles, so finding one at the top means the slice is the sidebar
    CHROME = ("最近の記事", "最新記事", "最近のコメント", "最新コメント", "月別アーカイブ",
              "プロフィール", "カテゴリ", "アーカイブ", "トラックバック", "コメント(", "コメント（",
              "この広告", "リンクフリー", "関連記事", "スポンサーサイト", "Powered by",
              "この記事へのコメント")

    # every episode marker in a body, whatever episode it names: 第12話,
    # １２話, episode 12, ep 12, #12, #012, EP12
    _MARK = re.compile(r"第?\s*(\d{1,3})\s*話"
                       r"|\b(?:episode|epis|epi|ep)\s*\.?\s*#?\s*(\d{1,3})\b"
                       r"|#\s*(\d{1,3})\b", re.I)
    _DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
    # Full-width digits and the full-width hash written half-width, ONE
    # CHARACTER FOR ONE, so every offset in the flattened text still points at
    # the same place in the original and a slice cut on it is the same slice.
    # `７話` and `＃０７` are how a Japanese 感想 post writes its own number as
    # often as not.
    _WIDE = str.maketrans("０１２３４５６７８９＃", "0123456789#")

    @classmethod
    def _flat(cls, text):
        return str(text or "").translate(cls._WIDE)

    @classmethod
    def _ep_markers(cls, text, ep_titles=None):
        """[(start, end, episode number)] for every episode marker in the body,
        in order. A bare `2話` whose digit follows another digit is the tail of
        `第12話` and is not a marker of its own.

        AN EPISODE'S OWN SUBTITLE IS A MARKER TOO. A whole-series post with a
        section per episode heads each one however it likes, and a good few
        head them with the subtitle and no number at all; without it the
        section for this episode either could not be found or ran on into the
        next episode's. `ep_titles` is `{episode: [subtitle, ...]}` and comes
        from what is already on file, never from a fetch.

        `その2` is deliberately NOT a marker here. This list also decides where
        one episode's section ENDS, and on a blog `その2` is the second half of
        the post far more often than it is episode 2; a slice cut there loses
        the rest of the episode. It counts in `_names_episode`, which only
        answers whether a page is about an episode and cuts nothing."""
        flat = cls._flat(text)
        out = []
        for m in cls._MARK.finditer(flat):
            g = m.group(1) or m.group(2) or m.group(3)
            if not g:
                continue
            if m.start() > 0 and flat[m.start()] not in "第#" and flat[m.start() - 1].isdigit():
                continue
            try:
                n = int(g)
            except ValueError:
                continue
            if 1 <= n <= 999:
                out.append((m.start(), m.end(), n))
        for n, names in (ep_titles or {}).items():
            for name in names:
                name = str(name or "").strip()
                if len(name) < cls.SUBTITLE_MIN_CHARS:
                    continue
                at = 0
                while True:
                    j = text.find(name, at)
                    if j < 0:
                        break
                    out.append((j, j + len(name), int(n)))
                    at = j + len(name)
        out.sort()
        return out

    # A subtitle shorter than this is not evidence: `Bath` and `雨` appear in
    # any post about any episode.
    SUBTITLE_MIN_CHARS = 4

    # Every way a page says which episode it is about, once the text has been
    # flattened. Wider than `_MARK` because none of these cuts anything: they
    # answer "is this page about episode n" and no more.
    _FORMS = (("第{n}話", r"第\s*0*{n}\s*話"),
              ("{n}話", r"(?<!\d)0*{n}\s*話"),
              ("#{n}", r"#\s*0*{n}(?!\d)"),
              ("EP{n}", r"\b(?:episode|epis|epi|ep)\s*\.?\s*#?\s*0*{n}(?!\d)"),
              ("その{n}", r"その\s*0*{n}(?!\d)"))

    @classmethod
    def _names_episode(cls, text, ep, subtitles=()):
        """Which form says this text is about episode `ep`, or ''.

        `第7話` was the whole test, and a 感想 post is titled `#07`, `７話`,
        `07話`, `Episode 7` or by the episode's own subtitle at least as often.
        On three readings of one episode this refused two thirds of what the
        search found."""
        if not text:
            return ""
        flat = cls._flat(text)
        n = int(ep or 0)
        if n:
            for label, rx in cls._FORMS:
                if re.search(rx.format(n=n), flat, re.I):
                    return label.format(n=n)
        for s in subtitles or ():
            s = str(s or "").strip()
            if len(s) >= cls.SUBTITLE_MIN_CHARS and s in text:
                return f"its subtitle 「{s}」"
        return ""

    @classmethod
    def _season_page(cls, text, ep, total=0):
        """A page carrying markers for most of a series rather than an account
        of one episode: an index, a nav strip, a season page. Reported so the
        answer is *slice it better*, not *skip it* -- the official あらすじ
        page for one episode carries a nav strip of all thirteen titles, and
        skipping it lost the only never-wrong source there is."""
        eps = {n for _s, _e, n in cls._ep_markers(text)}
        if len(eps) < 4:
            return False
        return len(eps) > (int(total) / 2.0 if total else 5)

    def _episode_slice(self, text, ep, ep_titles=None, page_title=""):
        """This episode's section of a page, or ''. `_slice_and_why` with the
        refusal thrown away, for the callers that only want the text."""
        return self._slice_and_why(text, ep, ep_titles, page_title)[0]

    def _slice_and_why(self, text, ep, ep_titles=None, page_title=""):
        """`(this episode's section of a page, why there is none)`.

        **The first occurrence of the marker is usually the navigation.** A
        page for one episode of a 2010 show opens with a strip listing all
        thirteen episode titles, so slicing at the first `第12話` ran from one
        nav entry to the next and gave thirteen characters -- under
        `min_chars`, so the page was dropped and the 249 characters of
        official あらすじ two paragraphs below were never seen. So every
        occurrence is scored and the best one is sliced at: an occurrence with
        another episode's marker right behind it is an index entry and is set
        aside, and among what is left the one with the most prose after it
        wins.

        **AND WHERE THE BODY SAYS NOTHING, THE PAGE'S OWN HEADING DOES.** The
        article container an extractor picks (`.article-body-inner`,
        `.entry-content`) starts UNDER the post's headline, and on a 感想 post
        the headline is where the number lives: five of the pages fetched for
        one episode of one show in September 2026 were headed
        `エグザンプル 第6話「宿はなし／Secret Paradise」 感想` and had no
        number anywhere in the body at all. So the heading is the second place
        looked at, and a page taken on the strength of its heading has to
        describe some scenes to be kept -- which is what refuses a shop's
        listing page for the same episode, whose heading is perfect and whose
        body is prices and service copy."""
        if not text:
            return "", "the page came back empty"
        ep = int(ep)
        own = list((ep_titles or {}).get(ep) or ())
        marks = self._ep_markers(text, ep_titles)
        here = [(s, e) for s, e, n in marks if n == ep]
        if not here:
            return self._by_heading(text, ep, own, page_title)
        gap = int(getattr(self.config.recap, "index_entry_gap", 40) or 40)
        cap = int(self.config.recap.max_chars)
        scored = []
        for s, e in here:
            nxt = next((ms for ms, _me, n in marks if ms >= e and n != ep), -1)
            end = nxt if nxt > s else len(text)
            body = text[e:min(end, e + cap)]
            index_entry = bool(nxt > 0 and (nxt - e) <= gap)
            sentences = body.count("。") + body.count("！") + body.count("？")
            scored.append((index_entry, -sentences, -len(body), s, end))
        # a non-index occurrence beats every index entry; then prose beats
        # length, and length beats position
        scored.sort()
        _idx_entry, _ns, _nl, idx, end = scored[0]
        seg = text[idx:end] if end > idx else text[idx:idx + cap]
        if len(seg) > cap:
            seg = seg[:cap]
        # Ending at ANY other episode's marker is tighter than the old rule,
        # which ended only at the next episode's, and a post that mentions an
        # earlier episode in passing would now be cut at the mention. Where
        # the tight rule leaves too little to be a synopsis, the old one gets
        # its turn rather than the page being lost.
        if len(seg) < int(self.config.recap.min_chars):
            nxt = next((ms for ms, _me, n in marks if ms > idx and n == ep + 1), -1)
            alt = text[idx:nxt] if nxt > idx else text[idx:idx + cap]
            if len(alt) > len(seg):
                seg = alt[:cap]
        # A slice that opens in the blog's own lists of other articles IS
        # those lists: the episode marker was the page's title and what
        # follows it is the sidebar. One such archive of article titles and
        # dates reached the digest role, which wrote a plot out of nothing.
        for m in self.CHROME[:5]:
            j = seg.find(m)
            if 0 <= j < 100:
                return "", "the section for it opens in the blog's list of other articles"
        out = self._end_at_chrome(seg)
        # A page about the right episode that describes none of it is not a
        # synopsis of it either, and it is the harder case: the section test
        # passes, so it used to be accepted and restated as events.
        if self._running_order(out):
            return "", "it is the episode's running order and not an account of it"
        return out, ""

    def _end_at_chrome(self, seg):
        """A blog post's body ends where its chrome begins. Without this a
        short post ran 2,200 characters into the author's profile, recent
        posts and comments, and the digest role read a baseball blog's sidebar
        as the episode. The first marker after a hundred characters ends it."""
        cut = len(seg)
        for m in self.CHROME:
            j = seg.find(m, 100)
            if 0 <= j < cut:
                cut = j
        return seg[:cut].strip()

    def _by_heading(self, text, ep, own, page_title):
        """`(the whole post, why not)` for a page whose BODY names no episode.

        The page's own heading is asked instead, in every form a post writes
        its number in and by the episode's own subtitle. Two refusals stand
        over it: a body that is an index of the whole series is not one
        episode's post whatever the heading says, and a page that describes no
        scenes is not an account of the episode -- which is the shop listing,
        whose heading names the episode correctly and whose body is a price
        and a button."""
        form = self._names_episode(page_title, ep, own)
        if not form:
            return "", (f"nothing in it or its heading says 第{ep}話, {ep}話, #{ep:02d}, "
                        f"EP{ep} or その{ep}"
                        + (f", and neither names 「{own[0]}」" if own else
                           ", and no subtitle for it is on file"))
        if self._season_page(text, ep):
            return "", (f"its heading says {form} and its body is an index of the "
                        f"whole series")
        cap = int(self.config.recap.max_chars)
        out = self._end_at_chrome(text[:cap])
        if self._running_order(out):
            return "", f"its heading says {form} and its body is the running order"
        need = int(getattr(self.config.recap, "slice_min_sentences", 3) or 0)
        short = int(getattr(self.config.recap, "slice_min_chars", 600) or 0)
        enders = sum(out.count(c) for c in "。！？")
        if (need and enders < need) or (short and len(out) < short):
            return "", (f"its heading says {form} and its body has {enders} sentence(s) "
                        f"in {len(out)} characters -- a listing, not an account")
        return out, ""
