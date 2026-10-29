"""Her face in the app: a reaction image from the episodes, changed when
her mood crosses a band.

The images come from `tools/reactions.py` (PROJECT 5.96): frames of her from
the actual anime, framed, sorted by expression into buckets, and curated by
hand -- a row whose file he deleted is gone, a row he moved carries his
bucket as `label`. This module only reads that database.

Rule (his, 2026-08-26): one reaction each time her mood crosses a threshold.
Mood valence is the same number `State.mood_state` reads (the mood gauge
against its baseline over `state.mood_from.max_swing`), cut into five bands
at -0.45 / -0.15 / 0.15 / 0.45. When the band changes since the last tick,
one image goes out; which bucket is decided by what is up at that moment
(anger, sadness, anxiety, awkwardness, fatigue, surprise), the band alone
otherwise. A surprise crossing (`surprise` gauge over `surprise_from`) is
its own threshold. Never the same image twice inside `repeat_days`.

The image is copied to data/talkapp/reactions/ and the hub serves it as her
icon (`/reaction/<file>`); the app swaps the header avatar and notes the
bucket beside the presence line. It is not a message: nothing enters her
chat, nothing is said. `/reaction [now|BUCKET|off]` from the ops bar.
"""
import os
from sim import wiring
import json
import random
import shutil
import sqlite3
import time

import logger

BANDS = (-0.45, -0.15, 0.15, 0.45)


class Reactions:
    WIRES = ('sender',)
    def __init__(self, config, store, clock, state):
        self.config = config
        self.store = store
        self.clock = clock
        self.state = state
        self.c = config.reactions
        self.root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(self.root, "data", "reactions", self.c.character, "reactions.db")
        self.out_dir = os.path.join(self.root, "data", "talkapp", "reactions")
        self.sender = None    # set by scail: (path, bucket, ts, quiet) -> bool, the sticker in his chat
        wiring.declare(self)

    # ---------------- reading her ----------------

    def valence(self):
        c = self.config.state.mood_from
        base = float(self.config.state.gauges["mood"]["baseline"])
        return max(-1.0, min(1.0, (float(self.state.gauges.get("mood", base)) - base) / c.max_swing))

    def band(self, v=None):
        v = self.valence() if v is None else v
        return sum(1 for b in BANDS if v >= b) - 2       # -2 .. 2

    def bucket_for(self, band):
        """What is up decides the face; the band alone otherwise."""
        g = self.state.gauges
        c = self.c
        if g.get("surprise", 0) >= c.surprise_from:
            return "surprised"
        if band <= -2:
            if g.get("anger", 0) >= c.anger_from:
                return "angry"
            if g.get("sadness", 0) >= c.sadness_from:
                return "sad"
            if g.get("energy", 50) <= c.tired_below or g.get("fatigue", 0) >= c.fatigue_from:
                return "tired"
            return "sad"
        if band == -1:
            if g.get("anger", 0) >= c.anger_from:
                return "angry"
            if g.get("anxiety", 0) >= c.anxiety_from:
                return "nervous"
            if g.get("awkwardness", 0) >= c.awkward_from or g.get("shame", 0) >= c.awkward_from:
                return "flustered"
            if g.get("energy", 50) <= c.tired_below or g.get("fatigue", 0) >= c.fatigue_from:
                return "tired"
            return "sad" if g.get("sadness", 0) >= c.sadness_from * 0.7 else "neutral"
        if band >= 1:
            if g.get("awkwardness", 0) >= c.awkward_from:
                return "flustered"
            return "happy"
        return "neutral"

    # ---------------- the database ----------------

    def rows(self, bucket):
        if not os.path.exists(self.db_path):
            return []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(reactions)").fetchall()}
            col = "COALESCE(label, bucket)" if "label" in cols else "bucket"
            rs = conn.execute(f"SELECT id, path, {col} AS b, bucket_score, rating FROM reactions WHERE {col}=?", (bucket,)).fetchall()
        finally:
            conn.close()
        out = []
        for r in rs:
            p = os.path.join(self.root, r["path"]) if r["path"] else ""
            if p and os.path.exists(p):
                out.append({"id": r["id"], "path": p, "bucket": r["b"], "score": r["bucket_score"] or 0.0, "rating": r["rating"]})
        return out

    def counts(self):
        if not os.path.exists(self.db_path):
            return {}
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(reactions)").fetchall()}
            col = "COALESCE(label, bucket)" if "label" in cols else "bucket"
            return {r["b"]: r["n"] for r in conn.execute(f"SELECT {col} AS b, count(*) AS n FROM reactions GROUP BY b")}
        finally:
            conn.close()

    def pick(self, bucket, learned=False):
        """One image of that face not shown inside `repeat_days`; a bucket
        with nothing left falls back to neutral, then to anything.

        `learned` weights the draw by how often she has reached for that
        picture for that feeling before (kv `sticker_weight`), so the ones she
        uses become the ones she uses -- a vocabulary rather than a shuffle.
        The automatic mood-band reaction does not use it; only the sticker she
        puts down herself."""
        now = self.clock.now_ts()
        recent = {x["id"] for x in self.store.get("reactions_log", []) if now - x["ts"] < self.c.repeat_days * 86400}
        w = (self.store.get("sticker_weight", {}) or {}) if learned else {}
        for b in (bucket, "neutral"):
            cands = [r for r in self.rows(b) if r["id"] not in recent]
            if not cands:
                continue
            if not w:
                return random.choice(cands)
            weights = [1.0 + float((w.get(str(r["id"])) or {}).get(b, 0)) for r in cands]
            return random.choices(cands, weights=weights, k=1)[0]
        return None

    # ---------------- the one she puts down herself ----------------

    def chosen(self, bucket, why="she put it there"):
        """A sticker SHE chose, in a reply to him -- not the automatic one the
        mood band produces.

        His rule (2026-08-27): a sticker is how she expresses a mood, it is not
        a favourite, and it is not something he places. Putting one down adds
        +1 to that image's weight for that feeling, so the picture she reaches
        for when she is tired slowly becomes HER tired face rather than a
        random frame of one. The weight is per (image, bucket) and lives in kv
        `sticker_weight`.

        Returns the row sent, or None."""
        bucket = str(bucket or "").strip().lower()
        if bucket not in self.buckets():
            logger.log(f"[sticker] she asked for '{bucket}', which is not a face she has")
            return None
        row = self.pick(bucket, learned=True)
        if not row:
            logger.log(f"[sticker] nothing left in '{bucket}' to send")
            return None
        w = self.store.get("sticker_weight", {}) or {}
        key = str(row["id"])
        per = w.get(key) or {}
        per[bucket] = float(per.get(bucket, 0)) + 1.0
        w[key] = per
        self.store.set("sticker_weight", w)
        # published the same way the automatic reaction is, so the app's
        # header picture and her chat agree about what her face is doing
        os.makedirs(self.out_dir, exist_ok=True)
        fname = f"{row['id']:06d}.jpg"
        shutil.copy2(row["path"], os.path.join(self.out_dir, fname))
        if self.sender:
            try:
                self.sender(row["path"], row["bucket"], None, False, auto=True)
            except Exception as e:
                logger.log(f"[sticker] not sent: {type(e).__name__}: {e}")
                return None
        rec = {"ts": self.clock.now_ts(), "wall": time.time(), "id": row["id"],
               "bucket": row["bucket"], "wanted": bucket, "band": self.band(),
               "mood": round(self.valence(), 2), "file": fname, "why": why,
               "surprised": False, "chosen": True}
        self.store.set("reactions_log", (self.store.get("reactions_log", []) + [rec])[-400:])
        self.store.set("reaction_last", rec)
        logger.log(f"[sticker] she sent her {bucket} face (#{row['id']}, "
                   f"weight {per[bucket]:.0f} for {bucket}): {why}")
        return row

    def buckets(self):
        try:
            con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            out = {r[0] for r in con.execute("select distinct bucket from reactions") if r[0]}
            con.close()
            return out
        except Exception:
            return set()

    # ---------------- the tick ----------------

    def tick(self, force_bucket=None, why=""):
        """Called every loop. One reaction when the band changed since the
        last tick (or a surprise crossing); nothing otherwise."""
        if not self.c.enabled and not force_bucket:
            return None
        # only while he is actually there. Her mood wanders all day and her
        # face followed it into an empty room: five changes overnight, each one
        # pushed at him as a sticker. His call -- it does not need to update
        # unless he is talking to her. Nothing is recorded while he is away, so
        # the first tick after he comes back moves her face once, to now.
        if not force_bucket:
            mins = float(getattr(self.c, "active_minutes", 20) or 20)
            try:
                last = max([float(m["ts"]) for m in (self.store.recent_messages(4) or [])] or [0])
            except Exception:
                last = 0
            if not last or (self.clock.now_ts() - last) > mins * 60:
                return None
        v = self.valence()
        band = self.band(v)
        g = self.state.gauges
        surprised = g.get("surprise", 0) >= self.c.surprise_from
        prev = self.store.get("reaction_band", None)
        last = self.store.get("reaction_last", {}) or {}
        crossed = prev is not None and band != prev
        surprise_cross = surprised and not last.get("surprised")
        # a mood pinned in one band for a day still changes face: what is up
        # (anger, then sadness, then nothing but tiredness) is a threshold too
        want = self.bucket_for(band)
        # ...and a face comes back DOWN as well as up. Refusing `neutral` here
        # meant that once she had gone nervous or sad she stayed that way until
        # the band itself crossed: one night her face went nervous and was still nervous hours of ordinary chat later, with her mood back at neutral the whole time.
        # `min_gap_minutes` (20) is what stops the churn this was guarding
        # against, and it was already doing it.
        face_changed = prev is not None and bool(last.get("file")) and want != last.get("wanted")
        self.store.set("reaction_band", band)
        if force_bucket:
            bucket = force_bucket
            why = why or "forced"
        elif crossed or surprise_cross or face_changed:
            bucket = want
            why = (f"mood {v:+.2f} band {prev}->{band}" if crossed else
                   f"surprise {g.get('surprise', 0):.0f}" if surprise_cross else f"mood {v:+.2f}, {last.get('wanted')} -> {want}")
        else:
            if prev is None:
                # the first tick after a boot only records the band; no face changes for a restart
                self.store.set("reaction_last", dict(last, surprised=surprised))
            return None
        if not force_bucket and time.time() - float(last.get("wall", 0)) < self.c.min_gap_minutes * 60:
            self.store.set("reaction_last", dict(last, surprised=surprised))
            return None
        row = self.pick(bucket)
        if not row:
            logger.log(f"[reaction] {why}: wanted {bucket}, nothing on file")
            return None
        os.makedirs(self.out_dir, exist_ok=True)
        fname = f"{row['id']:06d}.jpg"
        shutil.copy2(row["path"], os.path.join(self.out_dir, fname))
        rec = {"ts": self.clock.now_ts(), "wall": time.time(), "id": row["id"], "bucket": row["bucket"], "wanted": bucket,
               "band": band, "mood": round(v, 2), "file": fname, "why": why, "surprised": surprised}
        log = (self.store.get("reactions_log", []) + [rec])[-400:]
        self.store.set("reactions_log", log)
        self.store.set("reaction_last", rec)
        logger.log(f"[reaction] {why}: {row['bucket']} #{row['id']}" + (f" (wanted {bucket})" if row["bucket"] != bucket else ""))
        if self.sender and self.c.sticker:
            try:
                self.sender(row["path"], row["bucket"], None, False, auto=True)
            except Exception as e:
                logger.log(f"[reaction] sticker not sent: {type(e).__name__}: {e}")
        return rec

    def backfill(self, hours=24):
        """The crossings of the last `hours`, from the recorded states
        (`state_log`, written when something happened), each given a face
        and a sticker at its own time. Once; a crossing already in the log
        is skipped."""
        since = self.clock.now_ts() - hours * 3600
        with self.store.lock:
            rows = self.store.conn.execute("SELECT ts, gauges FROM state_log WHERE ts >= ? ORDER BY ts", (since,)).fetchall()
        c = self.config.state.mood_from
        base = float(self.config.state.gauges["mood"]["baseline"])
        done = {round(x["ts"]) for x in self.store.get("reactions_log", [])}
        prev_band, prev_bucket = None, None
        last_ts = 0
        out = []
        saved = dict(self.state.gauges)
        try:
            for r in rows:
                try:
                    g = json.loads(r["gauges"]) if isinstance(r["gauges"], str) else dict(r["gauges"])
                except (ValueError, TypeError):
                    continue
                v = max(-1.0, min(1.0, (float(g.get("mood", base)) - base) / c.max_swing))
                band = self.band(v)
                self.state.gauges.update({k: g.get(k, saved.get(k, 0)) for k in saved})
                bucket = self.bucket_for(band)
                # the first recorded state seeds a face when nothing has been shown yet
                changed = (prev_band is None and not self.store.get("reactions_log", []) and bucket != "neutral") or                     (prev_band is not None and (band != prev_band or (bucket != prev_bucket and bucket != "neutral")))
                if changed and r["ts"] - last_ts >= self.c.min_gap_minutes * 60 and round(r["ts"]) not in done:
                    row = self.pick(bucket)
                    if row:
                        fname = f"{row['id']:06d}.jpg"
                        rec = {"ts": r["ts"], "wall": r["ts"], "id": row["id"], "bucket": row["bucket"], "wanted": bucket, "band": band,
                               "mood": round(v, 2), "file": fname, "why": f"backfill: mood {v:+.2f} band {prev_band}->{band}, {prev_bucket} -> {bucket}", "surprised": False}
                        self.store.set("reactions_log", (self.store.get("reactions_log", []) + [rec])[-400:])
                        if self.sender and self.c.sticker:
                            self.sender(row["path"], row["bucket"], r["ts"], True)
                        out.append(rec)
                        last_ts = r["ts"]
                prev_band, prev_bucket = band, bucket
        finally:
            self.state.gauges.update(saved)
        self.store.set("reactions_log", sorted(self.store.get("reactions_log", []), key=lambda x: x["ts"]))
        if out and not (self.store.get("reaction_last", {}) or {}).get("file"):
            # the last backfilled face is her face now, until the next crossing
            last = out[-1]
            os.makedirs(self.out_dir, exist_ok=True)
            src = next((r["path"] for r in self.rows(last["bucket"]) if r["id"] == last["id"]), None)
            if src:
                shutil.copy2(src, os.path.join(self.out_dir, last["file"]))
                self.store.set("reaction_last", dict(last, wall=time.time() - self.c.min_gap_minutes * 60))
        logger.log(f"[reaction] backfill: {len(out)} crossing(s) in the last {hours}h from {len(rows)} recorded state(s)")
        return out

    def clear(self):
        self.store.set("reaction_last", {})
        return "cleared; the avatar is the plain one until the next crossing"

    def current(self):
        """What the app should show: the last reaction, or nothing."""
        last = self.store.get("reaction_last", {}) or {}
        if not last.get("file"):
            return None
        return {"file": last["file"], "bucket": last["bucket"], "ts": last["ts"], "why": last.get("why", "")}

    def report(self):
        cnt = self.counts()
        v = self.valence()
        last = self.store.get("reaction_last", {}) or {}
        lines = [f"reactions: {sum(cnt.values())} on file for {self.c.character}: " + ", ".join(f"{k} {n}" for k, n in sorted(cnt.items(), key=lambda kv: -kv[1])),
                 f"  now: mood {v:+.2f}, band {self.band(v)}, would want {self.bucket_for(self.band(v))}",
                 "  showing: " + (f"{last['bucket']} #{last['id']} since {time.strftime('%H:%M', time.localtime(last['wall']))} ({last.get('why', '')})" if last.get("file") else "nothing (plain avatar)")]
        for x in (self.store.get("reactions_log", []) or [])[-8:]:
            lines.append(f"  {time.strftime('%m-%d %H:%M', time.localtime(x['wall']))} {x['bucket']:10s} #{x['id']} mood {x['mood']:+.2f} {x['why']}")
        return "\n".join(lines)
