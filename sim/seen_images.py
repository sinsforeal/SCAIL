import json


# Her side of a picture: that she saw it, when, and what she took from it.
#
# The tag store (sensors/image_tags.py) holds what the image IS -- objective,
# shared, written once, the same row whoever reposts it. This is the other
# half and it belongs in her own save, because it is memory: it fades, it can
# be recalled on a cue, and two girls looking at the same picture do not end
# up carrying the same thing.
#
# Kept deliberately close in shape to self_memories: a line in her words, a
# weight, and the last time it came back to her.


class SeenImages:
    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock
        with self.store.lock:
            self.store.conn.executescript("""
            CREATE TABLE IF NOT EXISTS seen_images (
                id INTEGER PRIMARY KEY, ts REAL, date TEXT,
                img_id TEXT, url TEXT, status_id TEXT, author TEXT,
                noticed TEXT,          -- what she took from it, her words
                tags TEXT,             -- json, copied from the tag store at the time
                weight INTEGER DEFAULT 1,
                last_seen REAL, mentions INTEGER DEFAULT 0);
            CREATE INDEX IF NOT EXISTS idx_seen_images_ts ON seen_images(ts);
            """)
            self.store.conn.commit()

    # ---------------- writing ----------------

    def note(self, img_id, url, noticed, tags=None, status_id="", author="", weight=1):
        now = self.clock.now_ts()
        with self.store.lock:
            self.store.conn.execute(
                "INSERT INTO seen_images (ts,date,img_id,url,status_id,author,noticed,tags,weight,last_seen,mentions) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,0)",
                (now, self.clock.date_str(), img_id, url, status_id, author,
                 str(noticed or "")[:300], json.dumps(tags or [], ensure_ascii=False), weight, now))
            self.store.conn.commit()

    # ---------------- reading ----------------

    def recent(self, n=8):
        with self.store.lock:
            rows = self.store.conn.execute(
                "SELECT * FROM seen_images ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in rows]

    def today(self, limit=3):
        """What she stopped on today, in her words: the pictures still in her
        head from the last scroll. Newest first, the description and whose
        feed it was in; the tags are the machine's vocabulary and never hers."""
        with self.store.lock:
            rows = self.store.conn.execute(
                "SELECT noticed, author FROM seen_images WHERE date = ? AND noticed != '' ORDER BY ts DESC LIMIT ?",
                (self.clock.date_str(), limit)).fetchall()
        return [f"{r['noticed']} (@{r['author']})" if r["author"] else str(r["noticed"]) for r in rows]

    def recall(self, cue_text, days=30, min_overlap=2):
        """An older picture the moment reaches for: the one whose description
        or author shares enough words with what he just wrote. One at most,
        silent otherwise; a hit counts as a mention and refreshes it, the way
        her own memories work. Today's are already in front of her."""
        from sim.textutil import words
        cue = words(cue_text, min_latin=4)
        if len(cue) < 2:
            return None
        now = self.clock.now_ts()
        with self.store.lock:
            rows = self.store.conn.execute(
                "SELECT id, ts, noticed, author FROM seen_images WHERE ts >= ? AND date != ? AND noticed != ''",
                (now - days * 86400, self.clock.date_str())).fetchall()
        best, score = None, 0
        for r in rows:
            own = words(r["noticed"], min_latin=4)
            handle = (r["author"] or "").lower()
            s = len(cue & own) + (2 if handle and handle in {c.lower() for c in cue} else 0)
            if s > score:
                best, score = r, s
        if best is None or score < min_overlap:
            return None
        with self.store.lock:
            self.store.conn.execute("UPDATE seen_images SET last_seen = ?, mentions = mentions + 1 WHERE id = ?", (now, best["id"]))
            self.store.conn.commit()
        return {"noticed": best["noticed"], "author": best["author"], "days": int((now - float(best["ts"])) // 86400)}

    def taste(self, days=30, limit=14):
        """Which tags keep coming back in what she stops on."""
        since = self.clock.now_ts() - days * 86400
        counts = {}
        with self.store.lock:
            rows = self.store.conn.execute(
                "SELECT tags, weight FROM seen_images WHERE ts >= ?", (since,)).fetchall()
        for r in rows:
            try:
                for t in json.loads(r["tags"] or "[]"):
                    counts[t] = counts.get(t, 0) + max(1, int(r["weight"] or 1))
            except ValueError:
                continue
        return sorted(counts.items(), key=lambda kv: -kv[1])[:limit]

    def report(self):
        with self.store.lock:
            n = self.store.conn.execute("SELECT COUNT(*) c FROM seen_images").fetchone()["c"]
        out = [f"{n} picture(s) she has stopped on"]
        for t, c in self.taste():
            out.append(f"  {c:3d}  {t}")
        for r in self.recent(5):
            out.append(f"  {r['date']} @{r['author']}: {(r['noticed'] or '')[:80]}")
        return "\n".join(out)
