"""The EPISODE ACCOUNT: what somebody who watched the episode would know.

The pipeline in `sim/recap.py` reads several pages about one episode, condenses
each into a digest, and keeps the ONE a judge picked. That winner is a
synopsis: a few hundred characters, one writer's reading of the episode, and by
the time it reaches a character it has been cut again to
`watching.digest_max_chars` -- 600 characters of a single fan post. It answers
"what was that episode about". It cannot answer "what did she say when she
dropped the cup", because the individual jokes are exactly what a 600-character
paraphrase drops.

So the losers are no longer thrown away. Everything read about the episode --
every surviving digest with its scene list, the episode's own subtitle file
read as an account of its scenes, and the official blurb -- goes to ONE role
(`episode_account`, `prompts/episode_account.txt`) which merges them into a
single Japanese account: every scene in order with how it comes out, the named
parts, the running gags, the lines worth remembering, what the episode points
at, and what no source settled. That account is the record.

**Three things follow from it being a record rather than a line she reads.**

- It is the MACHINE's. An episode of a television programme is the same episode
  whoever watched it, so the account is written once, into
  `machine/retrievals.py` under the pool below and under the same key the
  fetched page uses, and every character on the machine reads it without
  fetching or paying for anything. Her own save keeps her copy in
  `episode_accounts`, which is her record of having been told it.
- It is not cut to 600 characters. A separate short digest already exists for
  the opener and the impulse; the account is the whole thing, and what it
  costs is a longer cached prompt.
- It is never rebuilt once it is COMPLETE. `level` says how complete it came
  out and `sources` says what it was built from, so a rebuild is a decision
  somebody can make ("this one came out thin") rather than something that
  happens on every read. `docs/recap.md` section 3e.

Nothing here holds a model client: `Recap` has none either, and every paid call
in this file takes the client as an argument from whichever module holds one.

spec: docs/recap.md section 3e
"""
import json
import time

import logger
from machine import episode_reports


class EpisodeAccount:
    # the machine's store, beside the pool the fetched page is filed under, and
    # keyed the same way -- the work's id and edition where there is one, the
    # title where there is not (`Recap._shared_key`)
    SHARED_POOL = "episode_account"

    # How complete an account came out, worst first. `watched` is the standard
    # the whole of this exists for: every scene in order, merged from more than
    # one person's account of the episode or checked against the episode's own
    # dialogue. Below it are two honest answers rather than a failure -- an
    # episode nothing carries much about is still better known than one nobody
    # read up at all.
    LEVELS = ("thin", "read-up", "watched")

    def __init__(self, config, store, clock, archive=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.archive = archive
        self._ensure_table()

    def _c(self, key, default):
        # read with a default, so this module runs against a config from before
        # the patch that adds its keys
        return getattr(self.config.recap, key, default)

    def enabled(self):
        return bool(self._c("account_enabled", True))

    # ---------------- her own record ----------------

    # A TABLE OF ITS OWN, not columns on `recaps`. `Recap.remember` DELETES the
    # rows a new reading replaces, so an account carried on the winning page's
    # row would be thrown away by the next reading-up of the same episode --
    # which is the moment it is most wanted, because a re-read is what happens
    # when the first one came out thin.
    DDL = ("CREATE TABLE IF NOT EXISTS episode_accounts ("
           "id INTEGER PRIMARY KEY, ja TEXT, show TEXT, english TEXT, ep INTEGER, aid INTEGER, "
           "ep_title TEXT, account TEXT, scenes TEXT, parts TEXT, gags TEXT, quotes TEXT, "
           "refs TEXT, endcard TEXT, missing TEXT, level TEXT, sources TEXT, "
           "anchor_kind TEXT, chars INTEGER, built_at INTEGER, model TEXT, archive TEXT, "
           "tries INTEGER)")

    COLUMNS = (("ja", "TEXT"), ("show", "TEXT"), ("english", "TEXT"), ("ep", "INTEGER"),
               ("aid", "INTEGER"), ("ep_title", "TEXT"), ("account", "TEXT"),
               ("scenes", "TEXT"), ("parts", "TEXT"), ("gags", "TEXT"), ("quotes", "TEXT"),
               ("refs", "TEXT"), ("endcard", "TEXT"), ("missing", "TEXT"), ("level", "TEXT"),
               ("sources", "TEXT"), ("anchor_kind", "TEXT"), ("chars", "INTEGER"),
               ("built_at", "INTEGER"), ("model", "TEXT"), ("archive", "TEXT"),
               # how many readings-up this episode has had FOR THE MACHINE.
               # Counted here rather than per character: the three processes
               # each allowed themselves three attempts at the same episode,
               # so one episode of one show cost up to nine readings and the
               # last of them was no better than the second.
               ("tries", "INTEGER"))

    # what is stored as JSON and read back as a list
    _LISTS = ("scenes", "parts", "gags", "quotes", "refs", "missing", "sources")

    def _ensure_table(self):
        try:
            with self.store.lock:
                self.store.conn.execute(self.DDL)
                cols = [r[1] for r in self.store.conn.execute("PRAGMA table_info(episode_accounts)")]
                for name, decl in self.COLUMNS:
                    if name not in cols:
                        self.store.conn.execute(
                            f"ALTER TABLE episode_accounts ADD COLUMN {name} {decl}")
                self.store.conn.execute(
                    "CREATE INDEX IF NOT EXISTS episode_accounts_key ON episode_accounts(ja, ep)")
                self.store.conn.commit()
        except Exception as e:
            logger.log(f"[account] table init failed: {type(e).__name__}: {e}")

    def _local(self, ja, ep, aid=None):
        """Her own row for this episode, or None. A row that names a DIFFERENT
        work's id is not this episode: two entries of his list share the
        Japanese title エグザンプル, which is the same reason the fetched
        page's key carries an id."""
        try:
            with self.store.lock:
                sql = "SELECT * FROM episode_accounts WHERE ja=? AND ep=?"
                args = [str(ja or ""), int(ep or 0)]
                order = " ORDER BY id DESC LIMIT 1"
                if aid:
                    sql += " AND (aid=? OR aid IS NULL)"
                    args.append(int(aid))
                    order = " ORDER BY (aid IS NULL), id DESC LIMIT 1"
                cur = self.store.conn.execute(sql + order, args)
                names = [d[0] for d in cur.description]
                r = cur.fetchone()
        except Exception:
            return None
        if not r:
            return None
        return self._shape(dict(zip(names, r)))

    def _shape(self, d):
        """A stored row read back: the JSON columns as lists, and `references`
        under the name the prompt and the report use. The column is `refs`
        because `references` is a reserved word in SQLite's grammar and an
        unquoted one fails the CREATE."""
        for k in self._LISTS:
            v = d.get(k)
            if isinstance(v, str) and v:
                try:
                    d[k] = json.loads(v)
                except ValueError:
                    d[k] = []
            elif v is None:
                d[k] = []
        d["references"] = d.get("refs") or []
        d.setdefault("level", "thin")
        d["tries"] = int(d.get("tries") or 0)
        return d

    def standing(self, row):
        """How much of the episode an account is: how complete it came out
        first, then how much of it there is.

        ONE MEASURE FOR BOTH STORES AND THE BUILD. Comparing the completeness
        word alone let a shorter merge replace a longer one of the same
        standing -- エグザンプル ep6 went from 687 characters to 667 on
        2026-09-08 at 17:27 and again at 17:31, in two processes, with both
        readings called `read-up` -- which is the only-add rule broken by the
        one case it was written for."""
        lvl = str((row or {}).get("level") or "thin")
        i = self.LEVELS.index(lvl) if lvl in self.LEVELS else 0
        return (i, int((row or {}).get("chars") or 0)
                or len(str((row or {}).get("account") or "")))

    def _save(self, row):
        # THE SAME RULE HER OWN SAVE HAS TO OBEY AS THE MACHINE'S. `_share`
        # already refuses to write a thinner account over a fuller one; when
        # only that side refused, the machine kept the good account of
        # エグザンプル ep7 and her save took the thin rebuild, so the two
        # stores disagreed about the same episode and which one she was handed
        # depended on which was read first.
        old = self._local(row.get("ja"), row.get("ep"), row.get("aid"))
        if old and old.get("account"):
            if self.standing(old) > self.standing(row):
                logger.log(f"[account] her own record of {row.get('ja')} ep{row.get('ep')} is "
                           f"{old.get('level')} ({self.standing(old)[1]} chars); this "
                           f"{row.get('level')} one of {self.standing(row)[1]} is not written "
                           f"over it")
                return
        try:
            with self.store.lock:
                self.store.conn.execute(
                    "DELETE FROM episode_accounts WHERE ja=? AND ep=? AND "
                    "(aid IS ? OR aid IS NULL)",
                    (row.get("ja") or "", int(row.get("ep") or 0),
                     int(row["aid"]) if row.get("aid") else None))
                cols = [c for c, _ in self.COLUMNS]
                vals = []
                for c in cols:
                    v = row.get("references") if c == "refs" else row.get(c)
                    if c in self._LISTS:
                        v = json.dumps(list(v or ()), ensure_ascii=False)
                    elif c in ("ep", "chars", "built_at"):
                        v = int(v or 0)
                    elif c == "aid":
                        v = int(v) if v else None
                    else:
                        v = str(v or "")
                    vals.append(v)
                self.store.conn.execute(
                    "INSERT INTO episode_accounts(%s) VALUES(%s)" % (
                        ",".join(cols), ",".join("?" * len(cols))), vals)
                self.store.conn.commit()
        except Exception as e:
            logger.log(f"[account] store failed: {type(e).__name__}: {e}")

    # ---------------- the machine's copy ----------------

    def _shared(self, retrievals, shared_key):
        if retrievals is None or not shared_key:
            return None
        try:
            r = retrievals.get(self.SHARED_POOL, shared_key)
        except Exception as e:
            logger.log(f"[account] the machine's store did not answer: {type(e).__name__}")
            return None
        if not r or not r.get("text"):
            return None
        d = dict(r.get("meta") or {})
        d["account"] = r["text"]
        d.setdefault("built_at", int(r.get("fetched_at") or 0))
        d["references"] = d.get("references") or d.get("refs") or []
        d["refs"] = d["references"]
        for k in self._LISTS:
            if not isinstance(d.get(k), list):
                d[k] = list(d.get(k) or ())
        d.setdefault("level", "thin")
        d["tries"] = int(d.get("tries") or 0)
        return d

    def _share(self, retrievals, shared_key, row):
        """Write the account into the machine's one store, so no other
        character pays for it. A COMPLETE account is never overwritten by a
        thinner one: a second character reaching the episode with a worse
        candidate set must not cost the first one's work."""
        if retrievals is None or not shared_key or not row.get("account"):
            return
        try:
            have = retrievals.get(self.SHARED_POOL, shared_key)
            if have:
                held = dict(have.get("meta") or {})
                held.setdefault("account", have.get("text") or "")
                if self.standing(held) > self.standing(row):
                    logger.log(f"[account] the machine already holds a "
                               f"{held.get('level') or 'thin'} account of "
                               f"{self.standing(held)[1]} chars for {shared_key}; this "
                               f"{row.get('level')} one of {self.standing(row)[1]} is not "
                               f"written over it")
                    return
            meta = {k: row.get(k) for k in
                    ("ja", "show", "english", "ep", "aid", "ep_title", "level", "anchor_kind",
                     "chars", "built_at", "model", "archive", "endcard", "tries")}
            for k in self._LISTS:
                meta[k] = list(row.get(k) or ())
            meta["references"] = list(row.get("references") or ())
            retrievals.put(self.SHARED_POOL, shared_key, row["account"],
                           source=str(row.get("archive") or ""), judged=1, meta=meta)
        except Exception as e:
            logger.log(f"[account] the machine's copy was not written: {type(e).__name__}")

    # ---------------- reading ----------------

    def row(self, ja, ep, aid=None, retrievals=None, shared_key="", adopt=True):
        """The account for one episode: hers, else the machine's, and the
        machine's is copied into her save on the way past -- nothing is
        fetched to do it, and being told a thing is what her own record is
        for. `None` when neither store holds one."""
        mine = self._local(ja, ep, aid)
        theirs = self._shared(retrievals, shared_key)
        if mine and theirs:
            # the fuller of the two, and between two of the same standing the
            # one written later
            pick = max((mine, theirs), key=lambda r: (
                self.LEVELS.index(r.get("level") or "thin") if r.get("level") in self.LEVELS else 0,
                int(r.get("built_at") or 0)))
        else:
            pick = mine or theirs
        if pick is None:
            return None
        if adopt and pick is theirs:
            self._save(dict(pick, ja=pick.get("ja") or ja, ep=int(ep or 0),
                            aid=pick.get("aid") or aid))
        return pick

    def complete(self, row):
        """Whether this account is at the standard the whole of this exists
        for, and therefore never rebuilt on its own."""
        return bool(row) and str(row.get("level") or "") == "watched"

    def situation_text(self, row, ja=True):
        """The account as it goes into a prompt: the prose, then the scenes in
        order, then the parts, the gags, the lines and what the episode points
        at. Not cut -- an account cut in half is a synopsis again, which is
        what this replaces -- but bounded by what was stored.

        `ja` is the language the LABELS are in and never the account, which is
        Japanese always: a character who writes English to him still reads a
        Japanese record of a Japanese programme, the same way her own diary
        is hers. The rendering per `character.writes_to_him` is the caller's."""
        if not row or not row.get("account"):
            return ""
        t = (lambda a, b: b) if ja else (lambda a, b: a)
        out = [str(row["account"]).strip()]
        for head_en, head_ja, key in (
                ("scene by scene, in order", "順に、場面ごと", "scenes"),
                ("the parts", "パート", "parts"),
                ("the running jokes in it", "この話の繰り返しネタ", "gags"),
                ("lines from it", "この話のせりふ", "quotes"),
                ("what it points at", "作中で触れているもの", "references")):
            rows = [str(x).strip() for x in (row.get(key) or []) if str(x or "").strip()]
            if rows:
                out.append(t(head_en, head_ja) + ": " + " / ".join(rows))
        if row.get("endcard"):
            out.append(t("how it ends", "終わり方") + ": " + str(row["endcard"]))
        return "\n".join(out)

    # ---------------- building one ----------------

    def _level(self, chars, scenes, used_web, anchored):
        """How complete an account came out, from what went into it and not
        from how it reads. Two ways to reach the top: more than one person's
        account of the episode agreeing, or the episode's own dialogue behind
        it. One source and no transcript can produce a long confident account
        out of one blogger's misreading, and it is exactly that case this word
        exists to name."""
        if (chars >= int(self._c("account_min_chars", 900))
                and scenes >= int(self._c("account_min_scenes", 3))
                and (anchored or used_web >= 2)):
            return "watched"
        if chars >= int(self._c("account_thin_chars", 400)) and (anchored or used_web >= 1):
            return "read-up"
        return "thin"

    def build(self, entry, ep, llm, digests=(), anchor_text="", anchor_url="",
              anchor_kind="", transcript=None, show_key="", retrievals=None,
              shared_key="", ep_title="", english=""):
        """Merge everything read about one episode into one account, store it,
        and write its page. Returns the row, or None.

        `digests` is every surviving candidate -- `{url, source, digest,
        scenes}` -- and not only the one the judge chose: the judge answers
        "which single page would a viewer trust", and this answers "what
        happened in the episode", which is a different question and is
        answered better by all of them than by the best of them."""
        if not self.enabled() or llm is None:
            return None
        ja = (entry.get("ja") or entry.get("title") or "").strip()
        if not ja or not ep:
            return None
        # WHAT WAS ALREADY ASSEMBLED IS A SOURCE. A reading-up gets whatever
        # the search returns THAT MINUTE, and two searches for one episode do
        # not return the same pages: the second reading of エグザンプル
        # ep7 came back with the episode's own subtitle file, which the first
        # had not had, and without the one post that named the pool the shop's
        # staff recognise, which the first had. Merging from scratch each time
        # made the record a lottery over search results. So the account on
        # file goes in with the pages, and the merge can only add to it.
        prior = self.row(ja, int(ep), aid=int(entry["aid"]) if entry.get("aid") else None,
                         retrievals=retrievals, shared_key=shared_key, adopt=False)
        material, sources = self._material(ja, ep, digests, anchor_text, anchor_url,
                                           anchor_kind, transcript, ep_title, prior)
        if not material:
            logger.log(f"[account] {ja} ep{ep}: nothing was read about it; no account")
            return None
        data = self._call(llm, ja, ep, material)
        if not data:
            return None
        acct = " ".join(str(data.get("account") or "").split())
        if not acct:
            logger.log(f"[account] {ja} ep{ep}: the merge came back with no account")
            return None
        acct = acct[: int(self._c("account_max_chars", 4000))]
        scenes = [" ".join(str(s).split())[:300] for s in (data.get("scenes") or [])
                  if str(s or "").strip()][:24]
        # EVERY SOURCE THAT HAS EVER CONTRIBUTED, not only this reading's. The
        # account carries what the earlier pages said, so the record has to
        # carry which pages those were -- otherwise a second reading that
        # found one page would file an account built on five as "one source",
        # and the completeness word would fall back down every time it was
        # improved.
        seen_urls = {s.get("url") for s in sources if s.get("url")}
        for s in ((prior or {}).get("sources") or []):
            if isinstance(s, dict) and s.get("url") and s["url"] not in seen_urls \
                    and s.get("kind") not in self.NOT_INDEPENDENT:
                seen_urls.add(s["url"])
                sources.append(dict(s, note="from an earlier reading"))
        used_web = sum(1 for s in sources
                       if s.get("used") and s.get("kind") not in self.NOT_INDEPENDENT)
        # and whether the episode's own dialogue is behind this account, which
        # once true stays true: the transcript's account went into the file
        # this one is built on, and a later reading that cannot find the
        # subtitle again has not un-anchored the record.
        prior_anchor = str((prior or {}).get("anchor_kind") or "")
        anchored = (any(s.get("kind") == "transcript" for s in sources)
                    or "subtitle" in prior_anchor)
        anchor_kind = anchor_kind or prior_anchor
        row = {
            "ja": ja, "show": entry.get("title", ""), "english": english or entry.get("title", ""),
            "ep": int(ep), "aid": int(entry["aid"]) if entry.get("aid") else None,
            "ep_title": str(ep_title or ""), "account": acct, "scenes": scenes,
            "parts": self._lines(data.get("parts"), 12),
            "gags": self._lines(data.get("gags"), 12),
            "quotes": self._lines(data.get("quotes"), 10, 240),
            "references": self._lines(data.get("references"), 12, 300),
            "endcard": " ".join(str(data.get("endcard") or "").split())[:300],
            "missing": self._lines(data.get("missing"), 10),
            "sources": sources, "anchor_kind": anchor_kind or "",
            "chars": len(acct), "built_at": int(time.time()),
            "model": self._model(),
            # where everything that went into it is kept, from the archive's
            # own naming rather than from a path written out again here
            "archive": (self.archive.dir_for(show_key, ep)
                        if (self.archive and show_key) else ""),
        }
        row["refs"] = row["references"]
        row["level"] = self._level(len(acct), len(scenes), used_web, anchored)
        # ONE MORE READING OF THIS EPISODE, counted for the machine and not for
        # the character who paid for it, so the three processes between them
        # stop where one process would (`recap.account_max_tries`).
        row["tries"] = int((prior or {}).get("tries") or 0) + 1
        # A REBUILD THAT CAME OUT WORSE IS NOT THE ANSWER. It is kept in the
        # archive, because how a reading went is worth being able to argue
        # with, and it does not become the record or the page.
        #
        # WORSE MEANS SHORTER AT THE SAME STANDING, with no slack. The slack
        # here was a fifth of the length, and a merge that came out 3 per cent
        # shorter went through it twice on 2026-09-08 and took twenty
        # characters off the record of エグザンプル ep6 -- which is the
        # only-add rule broken by the exact case it exists for.
        if prior and prior.get("account") and self.standing(prior) > self.standing(row):
            if self.archive and show_key:
                self.archive.save(show_key, ep, "account",
                                  json.dumps(row, ensure_ascii=False, indent=1), ext=".json",
                                  name="account", note=f"{row['level']}, not kept",
                                  show=entry.get("title", ""), ja=ja)
            logger.log(f"[account] {ja} ep{ep}: this reading came out {row['level']}, "
                       f"{len(acct)} chars, against the {prior['level']} account of "
                       f"{len(str(prior['account']))} already on file; the one on file stands")
            # the reading still happened, so the count of them has to move or
            # the same episode is read up for ever
            kept = dict(prior, tries=row["tries"])
            self._share(retrievals, shared_key, kept)
            self._save(dict(kept, ja=ja, ep=int(ep)))
            return kept
        self._share(retrievals, shared_key, row)
        self._save(row)
        if self.archive and show_key:
            self.archive.save(show_key, ep, "account",
                              json.dumps(row, ensure_ascii=False, indent=1), ext=".json",
                              name="account", note=f"{row['level']}, {row['chars']} chars",
                              show=entry.get("title", ""), ja=ja)
        self.write_report(row)
        logger.log(f"[account] {ja} ep{ep}: {row['chars']} chars, {len(scenes)} scene(s), "
                   f"{len(row['gags'])} gag(s), {len(row['references'])} reference(s), "
                   f"merged from {used_web} page(s)"
                   + (" and the episode's own dialogue" if anchored else "")
                   + f" -- {row['level']}")
        return row

    @staticmethod
    def _lines(rows, n, cap=200):
        return [" ".join(str(x).split())[:cap] for x in (rows or []) if str(x or "").strip()][:n]

    def _model(self):
        try:
            return str((self.config.model("episode_account") or {}).get("model") or "")
        except Exception:
            return ""

    # kinds that are not an independent reader of the episode, and therefore
    # do not count towards the two-readers-agreeing half of `watched`: the
    # account this one is being built on top of, and the anchor, which is
    # either the transcript again or the blurb the pages were checked against
    NOT_INDEPENDENT = ("the account already on file", "anchor", "transcript")

    def _material(self, ja, ep, digests, anchor_text, anchor_url, anchor_kind,
                  transcript, ep_title, prior=None):
        """What the merge role is shown, and the record of what went into it.

        The transcript first because it settles contradictions, then the
        anchor, then every digest numbered. A source with nothing in it is
        listed as read and not used, which is how the page can say four
        sources were read and two carried anything."""
        parts, sources = [], []
        head = f"『{ja}』第{ep}話"
        if ep_title:
            head += f"「{ep_title}」"
        parts.append(head)
        if prior and prior.get("account"):
            body = [str(prior["account"])]
            for label, key in (("場面（順に）", "scenes"), ("パート", "parts"),
                               ("繰り返しネタ", "gags"), ("せりふ", "quotes"),
                               ("作中で触れているもの", "references")):
                rows = [str(x) for x in (prior.get(key) or []) if str(x or "").strip()]
                if rows:
                    body.append(label + ":\n" + "\n".join(f"- {x}" for x in rows))
            if prior.get("endcard"):
                body.append("終わり方: " + str(prior["endcard"]))
            parts.append(
                "THE ACCOUNT ALREADY ON FILE for this episode, assembled from earlier readings "
                "of other pages. Everything in it was taken from a source then, and those sources "
                "are not in front of you now. KEEP ALL OF IT unless something below contradicts it "
                "on a stated outcome; your account must not be shorter or poorer than this one. "
                "The sources below are here to ADD to it and to correct it, not to replace it:\n"
                + "\n\n".join(body))
            sources.append({"kind": "the account already on file", "url": "",
                            "chars": len(str(prior["account"])), "used": True,
                            "note": str(prior.get("level") or "")})
        if transcript and transcript.get("account"):
            body = [str(transcript["account"])]
            if transcript.get("scenes"):
                body.append("場面（字幕から、順に）:\n" + "\n".join(
                    f"- {s}" for s in transcript["scenes"]))
            if transcript.get("quotes"):
                body.append("字幕からの実際のせりふ:\n" + "\n".join(
                    f"- {q}" for q in transcript["quotes"]))
            parts.append("TRANSCRIPT ACCOUNT (the episode's own subtitle file; ground truth for "
                         "what was said and how a scene comes out, blind to everything visual):\n"
                         + "\n\n".join(body))
            sources.append({"kind": "transcript", "url": transcript.get("source", ""),
                            "chars": len(str(transcript["account"])), "used": True,
                            "note": transcript.get("provenance", "")})
        if anchor_text:
            parts.append(f"ANCHOR ({anchor_kind or 'the official blurb'}; short, never wrong, "
                         f"never complete):\n{anchor_text}")
            sources.append({"kind": "anchor", "url": anchor_url,
                            "chars": len(anchor_text), "used": True})
        n = 0
        for d in digests or ():
            text = str(d.get("digest") or "").strip()
            # THE PAGE ITSELF, NOT ONLY ITS DIGEST. A digest is 200 to 500
            # characters made out of a 2,200-character post, and what it drops
            # first is exactly what this account is for: the individual jokes,
            # the line somebody quoted, the background the writer recognised.
            # Merging six compressions can only produce a seventh. The digest
            # rides with the page as the reading of it that already passed the
            # is-this-about-the-episode test, and the page is what the detail
            # comes out of.
            page = str(d.get("text") or "").strip()
            rec = {"kind": d.get("source") or "page", "url": d.get("url", ""),
                   "chars": len(page) or len(text), "used": False}
            if not text or text.startswith("なし"):
                sources.append(rec)
                continue
            n += 1
            rec["used"] = True
            sources.append(rec)
            block = [f"SOURCE [{n}] ({rec['kind']}, {rec['url']})",
                     "その記事の要旨: " + text]
            if d.get("scenes"):
                block.append("その記事が挙げる場面（順に）:\n" + "\n".join(
                    f"- {s}" for s in d["scenes"]))
            if page:
                block.append("その記事の本文:\n" + page)
            parts.append("\n".join(block))
        if n == 0 and not (transcript and transcript.get("account")) and not anchor_text:
            return "", sources
        return "\n\n".join(parts), sources

    def _call(self, llm, ja, ep, material):
        """The one paid call. It is NOT put through the machine's
        get-or-fetch: the account is already shared under its own key by
        `_share`, and a second key on the exact bytes of the material would
        only save the case where two characters assembled byte-identical
        material, which the claim in `Recap.synopsis` already prevents."""
        try:
            data, raw = llm.call_json("episode_account", [
                {"role": "system", "content": self.config.prompt_text("episode_account")},
                {"role": "user", "content": material}])
        except Exception as e:
            logger.log(f"[account] the merge failed: {type(e).__name__}")
            return None
        if isinstance(data, dict):
            return data
        # the role answered in prose. That answer is the account and there are
        # no scenes, rather than scenes invented to fill the shape.
        text = " ".join(str(raw or "").split())
        return {"account": text} if text else None

    # ---------------- the readable view ----------------

    def write_report(self, row):
        """The episode's own page under `recap.episodes_report_dir`, and the
        index over all of them. The MACHINE's, like the archive it names."""
        root = str(self._c("episodes_report_dir", "") or "")
        if not root or not row:
            return ""
        try:
            episode_reports.dump_json(root, row)
            return episode_reports.write(root, row)
        except Exception as e:
            logger.log(f"[account] the page was not written: {type(e).__name__}")
            return ""

    # ---------------- ops ----------------

    def report(self, limit=30):
        try:
            with self.store.lock:
                rows = self.store.conn.execute(
                    "SELECT ja, ep, level, chars, length(scenes), built_at FROM episode_accounts "
                    "ORDER BY built_at DESC LIMIT ?", (int(limit),)).fetchall()
                n = self.store.conn.execute(
                    "SELECT level, COUNT(*) FROM episode_accounts GROUP BY level").fetchall()
        except Exception as e:
            return f"episode accounts unreadable: {type(e).__name__}"
        out = ["episode accounts: " + (", ".join(f"{l or '?'} {c}" for l, c in n) or "(none)")]
        for ja, ep, level, chars, _sl, at in rows:
            when = time.strftime("%m-%d %H:%M", time.localtime(at)) if at else "?"
            out.append(f"  {ja} ep{ep}: {level}, {chars}c, {when}")
        return "\n".join(out)
