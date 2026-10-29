"""What was fetched about the WORLD, kept once for the whole machine.

Two characters run beside each other over one library, and until now each of
them paid separately for the same facts. Both watch his media player, so an
episode he played was searched for, fetched, digested and judged twice --
four to six model calls each -- because the cache was a table in each
character's own save. Both would have cached the same visual novel's database
card under their own key. A page he made her curious about was fetched twice.

The rule this file is the machine half of: **a file shared between two
characters must belong to the machine, not to a person** (`tools/isolation.py`).
What an episode of a television programme contains, what a page says, what a
game's database entry holds -- that is the world, it is the same for everybody
looking, and one fetch should serve both. What a character MADE of it -- that
she read it, when, what she took from it, what she said about it -- is memory,
it fades, and it stays in her own save. The precedent is the image tag store
(`sensors/image_tags.py`): what a picture IS, kept once, keyed on the picture.

A row is `(pool, key, model)`:

* `pool` is the kind of retrieval -- an episode page, a page condensed, a
  verdict between candidates, a web search, a game's card;
* `key` names the THING, never the character -- a show and an episode number,
  a URL, a normalised title, a database id;
* `model` is the model that wrote the text, so re-digesting with another model
  is a new row rather than a silent overwrite. It is `""` for a plain fetch
  with no model in it.

Two processes reach the same key at the same moment often enough to matter
(he plays an episode and both bots poll his player within the same minute),
so a fetch is CLAIMED before it starts. The claimant fetches; anybody else
waits for the row and then reads it. A claim older than `stale_seconds` is
taken over, because a bot is stopped with `Stop-Process -Force` and leaves its
claims behind.
"""
import json
import os
import sqlite3
import threading
import time

DEFAULT_PATH = "data/retrievals.db"


def character_id(config):
    """The name the machine files a fetch under: the same string the hub
    registers her by (`channels/talkapp_bot.py`), so a log line here and a
    log line there name the same character."""
    try:
        return "".join(str(config.character.name).lower().split()) or "unknown"
    except Exception:
        return "unknown"


class Retrievals:
    def __init__(self, path=DEFAULT_PATH, by="", stale_seconds=600.0,
                 wait_seconds=120.0, poll_seconds=1.0, log=None):
        self.path = path
        self.by = str(by or "unknown")
        self.stale_seconds = float(stale_seconds)
        self.wait_seconds = float(wait_seconds)
        self.poll_seconds = max(0.05, float(poll_seconds))
        self._log = log
        self.lock = threading.RLock()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        # WAL so the other character's process can read while this one writes;
        # busy_timeout so a write that meets a write waits instead of raising
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA busy_timeout=15000")
        self.con.executescript("""
        CREATE TABLE IF NOT EXISTS retrievals (
            kind TEXT, key TEXT, model TEXT,
            text TEXT, source TEXT, meta TEXT,
            fetched_at REAL, judged INTEGER DEFAULT 0, by TEXT,
            PRIMARY KEY (kind, key, model));
        CREATE INDEX IF NOT EXISTS idx_retrievals_kind ON retrievals(kind);
        CREATE TABLE IF NOT EXISTS inflight (
            kind TEXT, key TEXT, started REAL, by TEXT,
            PRIMARY KEY (kind, key));
        """)
        # `failed` says the claimant searched and came back with nothing, so
        # everybody waiting on it stops waiting NOW and goes and looks for
        # itself, rather than waiting the timeout out for a row that is never
        # coming. Added to a store that already exists.
        cols = {r[1] for r in self.con.execute("PRAGMA table_info(inflight)")}
        if "failed" not in cols:
            self.con.execute("ALTER TABLE inflight ADD COLUMN failed INTEGER DEFAULT 0")
        self.con.commit()

    def log(self, msg):
        if self._log:
            try:
                self._log(msg)
            except Exception:
                pass

    # ---------------- reading ----------------

    @staticmethod
    def _row(r):
        if r is None:
            return None
        d = dict(r)
        meta = d.get("meta")
        if isinstance(meta, str) and meta:
            try:
                d["meta"] = json.loads(meta)
            except ValueError:
                d["meta"] = {}
        else:
            d["meta"] = meta or {}
        return d

    def get(self, kind, key, model="", ttl=None):
        """The stored row for one thing, or None. `ttl` in seconds treats an
        older row as absent, for a retrieval that goes out of date."""
        if not key:
            return None
        with self.lock:
            r = self.con.execute(
                "SELECT * FROM retrievals WHERE kind=? AND key=? AND model=?",
                (str(kind), str(key), str(model or ""))).fetchone()
        row = self._row(r)
        if row and ttl is not None and (time.time() - float(row.get("fetched_at") or 0)) > float(ttl):
            return None
        return row

    def have(self, kind, key, model=""):
        return self.get(kind, key, model) is not None

    # ---------------- writing ----------------

    def put(self, kind, key, text, model="", source="", meta=None, judged=0,
            fetched_at=None, by=None):
        """Write what was fetched, the moment it exists. Never held on an
        object until the end of a run: a stop is `Stop-Process -Force`."""
        if not key:
            return None
        now = float(fetched_at if fetched_at is not None else time.time())
        with self.lock:
            self.con.execute("""
                INSERT INTO retrievals (kind,key,model,text,source,meta,fetched_at,judged,by)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(kind,key,model) DO UPDATE SET
                    text=excluded.text, source=excluded.source, meta=excluded.meta,
                    fetched_at=excluded.fetched_at, judged=excluded.judged, by=excluded.by
            """, (str(kind), str(key), str(model or ""), str(text or ""), str(source or ""),
                  json.dumps(meta or {}, ensure_ascii=False), now, int(judged or 0),
                  str(by or self.by)))
            self.con.commit()
        return self.get(kind, key, model)

    def put_if_newer(self, kind, key, text, model="", source="", meta=None, judged=0,
                     fetched_at=None, by=None):
        """The same write, but it loses to a row that is already newer. This is
        what a migration out of a character's own save uses: two saves may both
        hold a row for one episode and the later fetch is the better one."""
        have = self.get(kind, key, model)
        if have and float(have.get("fetched_at") or 0) >= float(fetched_at or 0):
            return None
        return self.put(kind, key, text, model=model, source=source, meta=meta,
                        judged=judged, fetched_at=fetched_at, by=by)

    def drop(self, kind, key, model=""):
        """Take a row out. What this is for: a page that turned out not to be
        about the episode it was filed under. Dropping it here as well as in
        her save is what stops the other character being handed it."""
        with self.lock:
            cur = self.con.execute(
                "DELETE FROM retrievals WHERE kind=? AND key=? AND model=?",
                (str(kind), str(key), str(model or "")))
            self.con.commit()
        return cur.rowcount or 0

    # ---------------- the claim ----------------

    def _claim(self, kind, key):
        """Take the right to fetch this key. (True, None) when it is ours;
        (False, row) when somebody else holds it.

        Three claims are ours to take: nobody holds it, we hold it already,
        and the holder is stale -- a bot is stopped with `Stop-Process
        -Force` and leaves its claims behind. A claim marked `failed` is the
        fourth: the last process to try it searched and found nothing, which
        is an invitation to try rather than a reason to wait."""
        now = time.time()
        with self.lock:
            cur = self.con.execute(
                "INSERT OR IGNORE INTO inflight (kind,key,started,by,failed) VALUES (?,?,?,?,0)",
                (str(kind), str(key), now, self.by))
            self.con.commit()
            if cur.rowcount:
                return True, None
            r = self.con.execute("SELECT * FROM inflight WHERE kind=? AND key=?",
                                 (str(kind), str(key))).fetchone()
        if r is None:
            # it was cleared between the insert and the read: try once more
            return self._claim(kind, key)
        held = dict(r)
        if (held.get("by") == self.by or int(held.get("failed") or 0)
                or (now - float(held.get("started") or 0)) >= self.stale_seconds):
            with self.lock:
                self.con.execute(
                    "UPDATE inflight SET started=?, by=?, failed=0 WHERE kind=? AND key=?",
                    (now, self.by, str(kind), str(key)))
                self.con.commit()
            return True, held
        return False, held

    # The three calls a caller that does its own fetching uses. `sim/recap.py`
    # holds the claim across a whole reading-up -- a web search, four page
    # fetches, a digest each and one judge -- because the thing that must
    # happen once for the machine is the SEARCH, and the store is not written
    # until the end of all of it.

    def claim(self, kind, key):
        """(True, None) when the right to go and look is ours, (False, the
        claim) when somebody else is already looking."""
        return self._claim(kind, key)

    def finish(self, kind, key, text, model="", source="", meta=None, judged=0, by=None):
        """The answer and the release, in one transaction: a waiter can never
        see the claim gone and the row not there yet."""
        if not key:
            return None
        now = time.time()
        with self.lock:
            # One commit for the two statements: the connection opens its
            # transaction on the insert and closes it here, so no reader can
            # see the claim gone with the row not yet written.
            try:
                self.con.execute("""
                    INSERT INTO retrievals (kind,key,model,text,source,meta,fetched_at,judged,by)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(kind,key,model) DO UPDATE SET
                        text=excluded.text, source=excluded.source, meta=excluded.meta,
                        fetched_at=excluded.fetched_at, judged=excluded.judged, by=excluded.by
                """, (str(kind), str(key), str(model or ""), str(text or ""), str(source or ""),
                      json.dumps(meta or {}, ensure_ascii=False), now, int(judged or 0),
                      str(by or self.by)))
                self.con.execute("DELETE FROM inflight WHERE kind=? AND key=?",
                                 (str(kind), str(key)))
                self.con.commit()
            except Exception:
                self.con.rollback()
                raise
        return self.get(kind, key, model)

    def fail(self, kind, key, why=""):
        """The claimant looked and found nothing. The claim is left in place
        with a mark on it, so anybody waiting stops now instead of waiting
        out the timeout, and the next process to reach the key takes it
        over."""
        with self.lock:
            self.con.execute(
                "UPDATE inflight SET failed=1, started=? WHERE kind=? AND key=?",
                (time.time(), str(kind), str(key)))
            self.con.commit()
        self.log(f"[retrievals] {kind} {self._short(key)}: {self.by} found nothing"
                 + (f" ({why})" if why else "") + "; anybody waiting may go ahead")

    def wait_for(self, kind, key, model="", ttl=None, held=None, timeout=None):
        """Somebody else is looking: wait for what they find. The row, or None
        when it never came and this process should go and look itself."""
        return self._wait_for(kind, key, model, ttl, held, timeout=timeout)

    def _take_over(self, kind, key):
        with self.lock:
            self.con.execute("UPDATE inflight SET started=?, by=? WHERE kind=? AND key=?",
                             (time.time(), self.by, str(kind), str(key)))
            self.con.commit()

    def release(self, kind, key):
        with self.lock:
            self.con.execute("DELETE FROM inflight WHERE kind=? AND key=?",
                             (str(kind), str(key)))
            self.con.commit()

    def sweep_claims(self):
        """Claims left behind by a process that was killed mid-fetch. Called at
        boot: a claim of this character's own is hers to drop, because she is
        starting now and is fetching nothing."""
        with self.lock:
            cur = self.con.execute(
                "DELETE FROM inflight WHERE by=? OR started < ? OR failed=1",
                (self.by, time.time() - self.stale_seconds))
            self.con.commit()
        return cur.rowcount or 0

    # ---------------- one call, whoever gets there first ----------------

    def get_or_fetch(self, kind, key, fetch_fn, model="", ttl=None, wait=True):
        """The stored row, or one fetch by whichever process gets there first.

        `fetch_fn()` returns the answer: a string, or a dict of
        `{text, source, meta, judged, model}`. Anything falsy means the fetch
        found nothing -- the claim is dropped and nothing is written, so the
        other process may try. The row is written the moment the answer
        exists.

        The returned row carries `reused`: False when this process fetched it,
        True when it came out of the store."""
        if not key:
            return None
        row = self.get(kind, key, model, ttl=ttl)
        if row:
            self._say_reused(kind, key, row)
            row["reused"] = True
            return row
        mine, held = self._claim(kind, key)
        if not mine:
            if not wait:
                return None
            waited = self._wait_for(kind, key, model, ttl, held)
            if waited is not None:
                return waited
            self._take_over(kind, key)
        try:
            got = fetch_fn()
        except Exception:
            self.fail(kind, key, "the fetch raised")
            raise
        if not got:
            self.fail(kind, key)
            return None
        if not isinstance(got, dict):
            got = {"text": str(got)}
        text = got.get("text") or ""
        if not text:
            self.fail(kind, key)
            return None
        row = self.finish(kind, key, text, model=got.get("model", model) or model,
                          source=got.get("source", ""), meta=got.get("meta"),
                          judged=got.get("judged", 0))
        self.log(f"[retrievals] {kind} {self._short(key)}: fetched by {self.by}")
        if row is not None:
            row["reused"] = False
        return row

    def _wait_for(self, kind, key, model, ttl, held, timeout=None):
        """Somebody else is fetching this. Poll for the row until it lands or
        the wait runs out; None when it never came and this process should go
        and look itself.

        Three ways it ends. The row arrives, which is the point. The claim is
        marked failed -- the claimant searched and found nothing -- and this
        one goes ahead at once rather than waiting the timeout out. Or the
        claim is simply gone, which is either a finished write this poll has
        not seen yet or a process that died: the store is read ONCE more
        before giving up, because the write and the release are one
        transaction and a claim that has gone means the row is already
        there."""
        who = str((held or {}).get("by") or "the other character")
        wait = float(self.wait_seconds if timeout is None else timeout)
        t0 = time.time()
        while (time.time() - t0) < wait:
            time.sleep(self.poll_seconds)
            row = self.get(kind, key, model, ttl=ttl)
            if row:
                self.log(f"[retrievals] {kind} {self._short(key)}: waited "
                         f"{time.time() - t0:.0f}s for {who}'s fetch")
                row["reused"] = True
                return row
            with self.lock:
                still = self.con.execute(
                    "SELECT by, failed FROM inflight WHERE kind=? AND key=?",
                    (str(kind), str(key))).fetchone()
            if still is None or int(dict(still).get("failed") or 0):
                row = self.get(kind, key, model, ttl=ttl)
                if row:
                    self.log(f"[retrievals] {kind} {self._short(key)}: waited "
                             f"{time.time() - t0:.0f}s for {who}'s fetch")
                    row["reused"] = True
                    return row
                return None
        self.log(f"[retrievals] {kind} {self._short(key)}: {who} has held it for "
                 f"{wait:.0f}s; going ahead")
        return None

    def _say_reused(self, kind, key, row):
        who = str(row.get("by") or "")
        age = time.time() - float(row.get("fetched_at") or 0)
        if who and who != self.by:
            self.log(f"[retrievals] {kind} {self._short(key)}: reused "
                     f"(fetched by {who} {age / 60.0:.0f}m ago)")

    @staticmethod
    def _short(key):
        s = str(key or "")
        return s if len(s) <= 70 else s[:67] + "..."

    # ---------------- what it adds up to ----------------

    def counts(self):
        with self.lock:
            return {r["kind"]: r["n"] for r in self.con.execute(
                "SELECT kind, COUNT(*) n FROM retrievals GROUP BY kind ORDER BY 2 DESC")}

    def by_character(self):
        with self.lock:
            return {(r["by"] or "?"): r["n"] for r in self.con.execute(
                "SELECT by, COUNT(*) n FROM retrievals GROUP BY by ORDER BY 2 DESC")}

    def total(self):
        with self.lock:
            return int(self.con.execute("SELECT COUNT(*) c FROM retrievals").fetchone()["c"])

    def report(self):
        """For `/kb` and the smoke run: what the machine has fetched, by pool
        and by who paid for it."""
        out = ["what the machine has fetched about the world (shared, one fetch for both):"]
        counts = self.counts()
        out += [f"  {k}: {n}" for k, n in counts.items()] or ["  (empty)"]
        who = self.by_character()
        if who:
            out.append("  fetched by: " + ", ".join(f"{k} {n}" for k, n in who.items()))
        with self.lock:
            n = int(self.con.execute("SELECT COUNT(*) c FROM inflight").fetchone()["c"])
        if n:
            out.append(f"  {n} fetch(es) claimed and not finished")
        return "\n".join(out)
