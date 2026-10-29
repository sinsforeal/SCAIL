"""The episode's transcript, and the account of it the judge measures against.

A downloaded subtitle file (`sim/subtitles.py`) is what was said, in order.
It is not a synopsis: twenty-four minutes is three to five hundred lines of
speech with no stage directions, and a model asked to summarise that writes a
plot out of dialogue and gets the visual gags wrong. So the file is turned
into a **scenes-in-order account** by one cheap call (`transcript_digest`),
and that account is what the judge holds the web candidates against -- and the
fallback digest when no web candidate survives.

Table `transcripts`, keyed on (show, episode), beside `recaps`:

    ja, show, ep, source, provenance, n_lines, lines (json), account,
    scenes (json), quotes (json), status, fetched_at, archive, origin,
    gpu_seconds

`status` is `ok` when a file was parsed, `miss` when the archives have none.
A miss is a row too, so a show with no file is not looked for on every tick;
`provenance` records whether the file was a broadcast caption rip, a
streaming rip or a fan listening transcript, and a caption rip always
outranks the rest. `origin` is a different fact and the one a person asks
first: whether the file was already beside his video, came out of the clone
of the archive on this machine, was fetched, or was made here by the
transcriber -- and `gpu_seconds` is what the last of those cost.

**And all of it is readable outside SQL.** Every attempt that resolves is one
line in `recap.transcripts_report` (`reports/transcripts.md`, append-only, the
machine's), and each save's own rows are caught up into it once at
construction, because the file did not exist while every transcript so far was
made.

spec: docs/recap.md
"""
import json

import logger
from machine import episode_reports


class Transcripts:
    def __init__(self, config, store, clock, subtitles=None, archive=None, llm=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.subtitles = subtitles
        self.archive = archive
        self.llm = llm
        self._ensure_table()
        self._catch_up_log()

    def _c(self, key, default):
        # read with a default: the keys arrive with the config patch
        return getattr(self.config.recap, key, default)

    def _ensure_table(self):
        try:
            with self.store.lock:
                self.store.conn.execute(
                    "CREATE TABLE IF NOT EXISTS transcripts ("
                    "id INTEGER PRIMARY KEY, ja TEXT, show TEXT, ep INTEGER, source TEXT, "
                    "provenance TEXT, n_lines INTEGER, lines TEXT, account TEXT, scenes TEXT, "
                    "quotes TEXT, status TEXT, fetched_at INTEGER, archive TEXT, origin TEXT, "
                    "gpu_seconds REAL)")
                # every column added since, backfilled the same way `recaps`
                # is: a save built before this runs gains them at construction
                cols = [r[1] for r in self.store.conn.execute("PRAGMA table_info(transcripts)")]
                for name, decl in (("ja", "TEXT"), ("show", "TEXT"), ("ep", "INTEGER"),
                                   ("source", "TEXT"), ("provenance", "TEXT"),
                                   ("n_lines", "INTEGER"), ("lines", "TEXT"),
                                   ("account", "TEXT"), ("scenes", "TEXT"),
                                   ("quotes", "TEXT"), ("status", "TEXT"),
                                   ("fetched_at", "INTEGER"), ("archive", "TEXT"),
                                   # WHERE the file came from, beside what kind
                                   # of subtitle it is: `provenance` says
                                   # broadcast / streaming / fan / whisper and
                                   # says nothing about whether it was already
                                   # beside his video, and the readable log is
                                   # asked the second question
                                   ("origin", "TEXT"), ("gpu_seconds", "REAL")):
                    if name not in cols:
                        self.store.conn.execute(f"ALTER TABLE transcripts ADD COLUMN {name} {decl}")
                self.store.conn.execute(
                    "CREATE INDEX IF NOT EXISTS transcripts_key ON transcripts(ja, ep)")
                self.store.conn.commit()
        except Exception as e:
            logger.log(f"[transcript] table init failed: {type(e).__name__}: {e}")

    # ---------------- the store ----------------

    def row(self, ja, ep):
        try:
            with self.store.lock:
                r = self.store.conn.execute(
                    "SELECT source, provenance, n_lines, lines, account, scenes, quotes, status, "
                    "fetched_at, archive, origin, gpu_seconds FROM transcripts "
                    "WHERE ja=? AND ep=? ORDER BY id DESC LIMIT 1",
                    (ja, int(ep))).fetchone()
        except Exception:
            return None
        if not r:
            return None
        return {"source": r[0], "provenance": r[1], "n_lines": r[2] or 0,
                "lines": json.loads(r[3] or "[]") if r[3] else [],
                "account": r[4] or "", "scenes": json.loads(r[5] or "[]") if r[5] else [],
                "quotes": json.loads(r[6] or "[]") if r[6] else [],
                "status": r[7] or "", "fetched_at": r[8] or 0, "archive": r[9] or "",
                "origin": r[10] or "", "gpu_seconds": float(r[11] or 0)}

    def _save(self, ja, show, ep, **kw):
        try:
            with self.store.lock:
                self.store.conn.execute(
                    "DELETE FROM transcripts WHERE ja=? AND ep=?", (ja, int(ep)))
                self.store.conn.execute(
                    "INSERT INTO transcripts(ja,show,ep,source,provenance,n_lines,lines,account,"
                    "scenes,quotes,status,fetched_at,archive,origin,gpu_seconds) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ja, show, int(ep), kw.get("source", ""), kw.get("provenance", ""),
                     int(kw.get("n_lines", 0)), json.dumps(kw.get("lines", []), ensure_ascii=False),
                     kw.get("account", ""), json.dumps(kw.get("scenes", []), ensure_ascii=False),
                     json.dumps(kw.get("quotes", []), ensure_ascii=False),
                     kw.get("status", "ok"), int(self.clock.now_ts()), kw.get("archive", ""),
                     kw.get("origin", ""), float(kw.get("gpu_seconds", 0) or 0)))
                self.store.conn.commit()
        except Exception as e:
            logger.log(f"[transcript] store failed: {type(e).__name__}: {e}")

    # ---------------- the account ----------------

    @staticmethod
    def render(lines, max_chars=24000):
        """The transcript as a prompt reads it: `[mm:ss] speaker: line`, cut at
        a ceiling from the END rather than the start, so the episode's ending
        -- the outcome a wrong digest invents -- is never the part dropped."""
        out = []
        for r in lines or []:
            t = int(float(r.get("start") or 0))
            who = (r.get("speaker") or "").strip()
            out.append(f"[{t // 60:02d}:{t % 60:02d}] " + (f"{who}: " if who else "") + str(r.get("text") or ""))
        body = "\n".join(out)
        if len(body) <= max_chars:
            return body
        head = int(max_chars * 0.55)
        return body[:head] + "\n…\n" + body[-(max_chars - head):]

    def account(self, ja, ep, lines, provenance="", llm=None):
        """One `transcript_digest` call: the scenes in the order they happen,
        each with its outcome, from what was said. Returns (account, scenes,
        quotes).

        The model client is a PARAMETER, never an attribute set after the
        fact: this module is built by `sim/recap.py`, which has no client of
        its own, and each caller passes the one it holds."""
        llm = llm if llm is not None else self.llm
        if llm is None or not lines:
            return "", [], []
        body = self.render(lines, int(self._c("transcript_prompt_chars", 24000)))
        user = (f"『{ja}』第{ep}話\n"
                f"({len(lines)} lines"
                + (f", {provenance} caption rip" if provenance in ("broadcast", "streaming") else
                   ", a fan listening transcript") + ")\n\n" + body)
        try:
            data, raw = llm.call_json("transcript_digest", [
                {"role": "system", "content": self.config.prompt_text("transcript_digest")},
                {"role": "user", "content": user}])
        except Exception as e:
            logger.log(f"[transcript] the account failed: {type(e).__name__}")
            return "", [], []
        if not isinstance(data, dict):
            # a role that answered in prose rather than JSON still answered;
            # the account is the answer and there are no scenes
            text = " ".join(str(raw or "").split())
            return text[: int(self._c("transcript_account_chars", 1600))], [], []
        acct = " ".join(str(data.get("account") or "").split())
        scenes = [str(s)[:200] for s in (data.get("scenes") or []) if str(s or "").strip()][:20]
        quotes = [str(q)[:160] for q in (data.get("quotes") or []) if str(q or "").strip()][:8]
        return acct[: int(self._c("transcript_account_chars", 1600))], scenes, quotes

    # ---------------- the one public call ----------------

    def anchor(self, entry, ep, titles=(), show_key="", anime_id=None, llm=None,
               video="", watched_seconds=0, transcribe=None, retrievals=None,
               shared_key=""):
        """The transcript's account for this episode, finding the file the
        first time and reusing it forever after. Returns the row, or None.

        `video` is the file he opened: a subtitle already beside it is the
        first thing looked at, and it is also what is transcribed when nothing
        anywhere can be found. A recorded miss is honoured for the fetching --
        the archives are asked once a day at most -- but a miss recorded
        before there was a transcriber does not stop one being made."""
        ja = (entry.get("ja") or entry.get("title") or "").strip()
        if not ja or not ep or not self.subtitles or not self.subtitles.enabled():
            return None
        have = self.row(ja, ep)
        if have and have.get("status") == "ok":
            if not have.get("account") and have.get("lines") and (llm or self.llm) is not None:
                acct, scenes, quotes = self.account(ja, ep, have["lines"], have.get("provenance", ""), llm=llm)
                if acct:
                    have.update({"account": acct, "scenes": scenes, "quotes": quotes})
                    self._save(ja, entry.get("title", ""), ep, **have)
            return have if have.get("account") else None
        stale_miss = False
        if have and have.get("status") == "miss":
            age = self.clock.now_ts() - float(have.get("fetched_at") or 0)
            if age < float(self._c("subtitles_retry_hours", 24)) * 3600:
                stale_miss = True
        # A RECORDED MISS MUST NOT BLOCK THE FILE BESIDE HIS VIDEO. The miss
        # is there to stop the ARCHIVES being asked on every tick, and
        # `Subtitles.fetch` looks beside his video before it spends the day's
        # attempt, so calling it costs nothing when there is a video: with a
        # sidecar it returns it, without one it hits its own daily gate and
        # returns None exactly as skipping it would. Skipping it outright
        # locked the machine out of a file it had just made itself -- a
        # transcription writes the .srt beside his video, and the next reading
        # of that episode refused to look at it for twenty-four hours.
        if stale_miss and video:
            stale_miss = False
        want = list(titles or []) + [entry.get("title", ""), ja]
        got = None
        if not stale_miss:
            got = self.subtitles.fetch(want, ep, show_key=show_key or ja,
                                       show=entry.get("title", ""), ja=ja, video=video)
        if not got and transcribe is not None:
            # NOTHING COULD BE FOUND, so the episode is listened to. Not a
            # fetch and not gated with the fetches: it is minutes of a GPU,
            # and its own gate is how long he has been in the episode
            # (`sim/transcribe.py`).
            got = transcribe.for_episode(video, watched_seconds, show_key=show_key or ja,
                                         ep=ep, show=entry.get("title", ""), ja=ja,
                                         shared_key=shared_key, retrievals=retrievals)
        if not got:
            if not stale_miss:
                self._save(ja, entry.get("title", ""), ep, status="miss")
                self._note({"ja": ja, "show": entry.get("title", ""), "ep": int(ep),
                            "status": "miss", "fetched_at": int(self.clock.now_ts())})
            return None
        acct, scenes, quotes = self.account(ja, ep, got["lines"], got.get("provenance", ""), llm=llm)
        arch = got.get("archived", "")
        if self.archive and show_key and got.get("lines"):
            self.archive.save(show_key, ep, "transcript",
                              json.dumps(got["lines"], ensure_ascii=False, indent=1),
                              url=got.get("source", ""), ext=".json",
                              note=f"{got.get('provenance')}, {len(got['lines'])} lines",
                              show=entry.get("title", ""), ja=ja)
            if acct:
                self.archive.save(show_key, ep, "digest", acct, url=got.get("source", ""),
                                  name="transcript", note="transcript_digest",
                                  show=entry.get("title", ""), ja=ja)
        row = {"source": got.get("source", ""), "provenance": got.get("provenance", ""),
               "n_lines": len(got.get("lines") or []), "lines": got.get("lines") or [],
               "account": acct, "scenes": scenes, "quotes": quotes, "status": "ok",
               "archive": arch, "origin": got.get("origin", ""),
               "gpu_seconds": float(got.get("gpu_seconds") or 0)}
        self._save(ja, entry.get("title", ""), ep, **row)
        self._note(dict(row, ja=ja, show=entry.get("title", ""), ep=int(ep),
                        fetched_at=int(self.clock.now_ts())))
        logger.log(f"[transcript] {ja} ep{ep}: {row['n_lines']} lines, "
                   f"{len(acct)} chars of account, {len(scenes)} scene(s)")
        return row if acct else None

    def _note(self, row):
        """One attempt in the readable log (`recap.transcripts_report`)."""
        path = str(self._c("transcripts_report", "") or "")
        if not path:
            return ""
        try:
            return episode_reports.note_transcript(
                path, row, by=str(getattr(self.config.character, "name", "") or ""))
        except Exception as e:
            logger.log(f"[subs] the transcript log was not written: {type(e).__name__}")
            return ""

    def _catch_up_log(self):
        """Everything her own table already holds, into the readable log, once
        per save at construction.

        The log did not exist while every transcript so far was made and the
        answers are all still in the saves, so waiting for the next attempt
        would have left the file empty for days. HER OWN TABLE AND NO OTHER: a
        character never reads another character's save, and the three of them
        each catching up her own rows into one append-only file -- de-duplicated
        on the show, the episode, where the file came from and the file's name
        -- comes to the same thing as one pass over all three."""
        path = str(self._c("transcripts_report", "") or "")
        if not path or self.store.get("transcripts_report_caught_up", 0):
            return 0
        rows = list(self._all_rows())
        self.store.set("transcripts_report_caught_up", 1)
        if not rows:
            return 0
        try:
            episode_reports.note_transcript(
                path, rows[-1], also=rows[:-1],
                by=str(getattr(self.config.character, "name", "") or ""))
        except Exception as e:
            logger.log(f"[subs] the transcript log was not caught up: {type(e).__name__}")
            return 0
        logger.log(f"[subs] {len(rows)} transcript attempt(s) of hers went into {path}")
        return len(rows)

    def _all_rows(self):
        """Every attempt her own table holds, oldest first, without the lines
        -- the log wants the count and the last timestamp, not the dialogue."""
        try:
            with self.store.lock:
                rows = self.store.conn.execute(
                    "SELECT ja, show, ep, source, provenance, n_lines, status, fetched_at, "
                    "origin, gpu_seconds, lines FROM transcripts ORDER BY fetched_at, id"
                ).fetchall()
        except Exception as e:
            logger.log(f"[subs] her own transcript rows were not read: {type(e).__name__}")
            return ()
        out = []
        for r in rows:
            try:
                lines = json.loads(r[10] or "[]") if r[10] else []
            except ValueError:
                lines = []
            out.append({"ja": r[0] or "", "show": r[1] or "", "ep": int(r[2] or 0),
                        "source": r[3] or "", "provenance": r[4] or "",
                        "n_lines": int(r[5] or 0), "status": r[6] or "",
                        "fetched_at": int(r[7] or 0), "origin": r[8] or "",
                        "gpu_seconds": float(r[9] or 0), "lines": lines})
        return out

    def report(self, limit=20):
        try:
            with self.store.lock:
                rows = self.store.conn.execute(
                    "SELECT ja, ep, status, provenance, n_lines, length(account) "
                    "FROM transcripts ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
                n = self.store.conn.execute(
                    "SELECT status, COUNT(*) FROM transcripts GROUP BY status").fetchall()
        except Exception as e:
            return f"transcripts unreadable: {type(e).__name__}"
        out = ["transcripts: " + (", ".join(f"{s or '?'} {c}" for s, c in n) or "(none)")]
        for ja, ep, st, pv, nl, la in rows:
            out.append(f"  {ja} ep{ep}: {st}" + (f", {pv}, {nl} lines, account {la}c" if st == "ok" else ""))
        return "\n".join(out)
