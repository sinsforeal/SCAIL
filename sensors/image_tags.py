"""The tag store: what an image IS, kept once and shared.

Her vision descriptions were thrown away after a single use -- held in memory
on the look's thread, handed to the social read, and gone. So the same picture
was paid for again every time it came past, a restart between the scroll and
the read lost the lot, and nothing she had ever looked at could be recalled.

This is the objective half, and it is deliberately not hers. An image is a
row: its tags, what it is, who posted it. Keyed by a hash of the URL so the
same picture is never sent to a model twice, whoever reposts it.

The tags are booru-style on purpose. His own image activity is already
classified in that vocabulary (data/gelbooru/ground_truth.json, 20k tags), so
tagging hers in the same space makes the two comparable -- what she keeps
stopping on and what he keeps looking at become the same kind of fact, which
they were never able to be while one side was prose.

Her side of it -- that she saw this, when, and what she took from it -- lives
in her own save, because that is memory and it fades. See sim/seen_images.py.
"""
import hashlib
import json
import os
import sqlite3
import time

DEFAULT_PATH = "data/x_images.db"


def img_id(url):
    return hashlib.sha1((url or "").encode("utf-8", "replace")).hexdigest()[:16]


class ImageTags:
    def __init__(self, path=DEFAULT_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.executescript("""
        CREATE TABLE IF NOT EXISTS images (
            img_id TEXT PRIMARY KEY,
            url TEXT, status_id TEXT, author TEXT,
            subject TEXT,          -- one line: what it is
            tags TEXT,             -- json list, booru style, lower_snake
            characters TEXT,       -- json list
            series TEXT,           -- json list
            rating TEXT,           -- safe / suggestive / explicit
            model TEXT, tagged_at REAL,
            times_seen INTEGER DEFAULT 0, last_seen REAL);
        CREATE INDEX IF NOT EXISTS idx_images_author ON images(author);
        CREATE TABLE IF NOT EXISTS tag_counts (
            tag TEXT PRIMARY KEY, n INTEGER DEFAULT 0, last REAL);
        """)
        self.con.commit()

    # ---------------- reading ----------------

    def get(self, url):
        r = self.con.execute("SELECT * FROM images WHERE img_id=?", (img_id(url),)).fetchone()
        return dict(r) if r else None

    def tags_for(self, url):
        row = self.get(url)
        if not row:
            return []
        try:
            return json.loads(row["tags"] or "[]")
        except ValueError:
            return []

    def note_seen(self, url):
        self.con.execute("UPDATE images SET times_seen=times_seen+1, last_seen=? WHERE img_id=?",
                         (time.time(), img_id(url)))
        self.con.commit()

    # ---------------- writing ----------------

    def put(self, url, data, status_id="", author="", model=""):
        """`data` is what the tagger returned: subject, tags, characters,
        series, rating."""
        def _list(k):
            v = data.get(k) or []
            if isinstance(v, str):
                v = [x.strip() for x in v.replace(",", " ").split() if x.strip()]
            return [str(x).strip().lower().replace(" ", "_")[:48] for x in v][:40]

        tags = _list("tags")
        now = time.time()
        self.con.execute("""
            INSERT INTO images (img_id,url,status_id,author,subject,tags,characters,series,rating,
                                model,tagged_at,times_seen,last_seen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)
            ON CONFLICT(img_id) DO UPDATE SET
                subject=excluded.subject, tags=excluded.tags, characters=excluded.characters,
                series=excluded.series, rating=excluded.rating, model=excluded.model,
                tagged_at=excluded.tagged_at, times_seen=images.times_seen+1, last_seen=excluded.last_seen
        """, (img_id(url), url, status_id, author, str(data.get("subject", ""))[:200],
              json.dumps(tags, ensure_ascii=False),
              json.dumps(_list("characters"), ensure_ascii=False),
              json.dumps(_list("series"), ensure_ascii=False),
              str(data.get("rating", "") or "")[:12], model, now, now))
        for t in tags:
            self.con.execute("INSERT INTO tag_counts (tag,n,last) VALUES (?,1,?) "
                             "ON CONFLICT(tag) DO UPDATE SET n=n+1, last=excluded.last", (t, now))
        self.con.commit()
        return tags

    # ---------------- what it adds up to ----------------

    def top_tags(self, limit=25):
        return [(r["tag"], r["n"]) for r in self.con.execute(
            "SELECT tag,n FROM tag_counts ORDER BY n DESC LIMIT ?", (limit,))]

    def stats(self):
        n = self.con.execute("SELECT COUNT(*) c FROM images").fetchone()["c"]
        seen = self.con.execute("SELECT COALESCE(SUM(times_seen),0) s FROM images").fetchone()["s"]
        tags = self.con.execute("SELECT COUNT(*) c FROM tag_counts").fetchone()["c"]
        return {"images": n, "times_seen": seen, "distinct_tags": tags,
                "saved_calls": max(0, seen - n)}
