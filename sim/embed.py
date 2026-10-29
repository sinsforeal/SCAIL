"""Sentence embeddings for retrieval, local, on his GPU.

The record is searched by words (`sim/textutil.words`: Latin words, CJK
bigrams), which is exact and cheap and cannot see that 「浴衣のこと」 and
"the yukata evening" are the same thing, or that a paraphrase names an
evening whose card used other words. A multilingual sentence embedding
can. One small model (`embed.model`, multilingual-e5 by default: query and
passage prefixes, normalised vectors, so cosine is a dot product), loaded
on first use, vectors kept in the save in a side table keyed by what they
are of, so nothing is embedded twice and a pool that has never been asked
costs nothing.

This is a scorer, not a store of meaning: every reader combines the cosine
with the pool's own score (a fact's fade, a card's age) and with the word
overlap, and there is a floor under which a cosine counts for nothing --
which is what makes the rest a signal.

**The floor is measured on the save it is used on, once per boot**
(`_calibrate`), because it is not the same number on two saves: a Japanese
cue against Japanese rows sits about 0.06 higher than an English cue against
English rows, so the hand-set 0.80 that leaves 9% of the first character's
facts above it left 100% of the second character's own memories above it and
counted her whole pool as a hit on every cue. Each pool takes a sample of
real cues from this save's record, scores them against a sample of its own
stored vectors, and puts its floor a margin above the 90th percentile of
that. `embed.min_cos` and `cos_by_pool` are the fallback for a pool with too
few rows to measure, and `embed.calibrate` false restores them everywhere.

Off (`embed.enabled` false, or the library missing) every reader falls back
to words alone and says so once.
"""
import os
import sqlite3

# numpy's OpenBLAS commits a 32 MB buffer per hardware thread at import (488 MB private on this box, 6 MB with one
# thread). The arrays here are a few hundred rows of 1024 floats, so one thread is the same answer. Set before numpy loads.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")   # not OMP: torch's local path reads that one

import numpy as np

import logger


def cued(embed, kind, items, cue_text, word_scores, write=False, load=False,
         row_words=None, cue_words=None, cap=None, stats=None):
    """One retrieval score per row of a pool: the word score it already has
    plus the cosine of the cue against it, and a row the words missed joins
    on its cosine alone once that clears `embed.min_cos`.

    `items` is [(ref, text)] for every row a cue may reach, so a pool is
    embedded under one kind and nothing is embedded twice; `word_scores` is
    {ref: score} for the rows the words hit. Returns {str(ref): score}. With
    embeddings off, the model not loaded, or an empty cue it hands back the
    word scores unchanged, which is what the pools did before there was a
    cosine at all.

    **Two rules over the rows that arrive on a cosine ALONE**, because six of
    six such rows judged against their cues were wrong, and two of them
    reached her mouth:

    * `row_words` / `cue_words` -- a row the words never found must still
      share one content word with the moment (`embed.require_shared_word`).
      Every wrong row shared nothing at all with its cue; requiring one word
      would have stopped all six. It is weaker than the word search's own
      test, so a row it nearly found still gets in on its meaning.
    * `cap` -- at most this many cosine-only rows per call, the strongest
      first. A run of them used to take every slot the reader had and leave
      the word hit out.

    `stats` is a dict the caller may pass to be told what happened: `kept`,
    `cosine_only`, `no_word`, `over_cap`."""
    out = {str(r): float(s) for r, s in (word_scores or {}).items() if s}
    st = stats if isinstance(stats, dict) else {}
    st.setdefault("cosine_only", 0)
    st.setdefault("no_word", 0)
    st.setdefault("over_cap", 0)
    if embed is None or not items or not str(cue_text or "").strip():
        return out
    q = embed.query(cue_text, load=load)
    if q is None:
        return out
    want_word = bool(getattr(embed.config.embed, "require_shared_word", False)) and cue_words
    lonely = []
    for ref, v in embed.vectors(kind, items, write=write).items():
        sc = embed.score(embed.cosine(q, v), kind, ref=ref)
        if sc <= 0:
            continue
        if str(ref) in out:
            out[str(ref)] += sc
            continue
        st["cosine_only"] += 1
        if want_word and not ((row_words or {}).get(str(ref)) or set()) & set(cue_words):
            st["no_word"] += 1
            continue
        lonely.append((sc, str(ref)))
    lonely.sort(reverse=True)
    if cap is not None and len(lonely) > int(cap):
        st["over_cap"] += len(lonely) - int(cap)
        lonely = lonely[: int(cap)]
    for sc, ref in lonely:
        out[ref] = out.get(ref, 0.0) + sc
    st["kept"] = len(lonely)
    return out


class _RemoteModel:
    """Client of an OpenAI-style embeddings endpoint (bzombie gateway or
    tools/embed_server.py). Standard library only."""

    def __init__(self, url, timeout=30.0):
        self.url = url
        self.timeout = timeout

    def _post(self, texts, kind):
        import json
        import urllib.request
        body = json.dumps({"model": "multilingual-e5-small", "input": texts,
                           "input_type": kind}).encode("utf-8")
        last = None
        for _ in range(2):
            try:
                req = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    d = json.loads(r.read().decode("utf-8"))
                rows = sorted(d["data"], key=lambda x: x.get("index", 0))
                if len(rows) != len(texts):
                    raise ValueError(f"{len(rows)} vectors for {len(texts)} texts")
                return [x["embedding"] for x in rows]
            except Exception as e:
                last = e
        raise last

    def ping(self):
        try:
            self._post(["ping"], "query")
            return True
        except Exception:
            return False

    def encode(self, texts, kind, batch_size=32):
        bs = max(1, int(batch_size))
        out = []
        for i in range(0, len(texts), bs):
            out.extend(self._post(texts[i:i + bs], kind))
        arr = np.asarray(out, dtype=np.float32).reshape(len(texts), -1)
        n = np.linalg.norm(arr, axis=1, keepdims=True)
        return arr / np.maximum(n, 1e-12)


class Embeddings:
    def __init__(self, config, store):
        self.config = config
        self.store = store
        self._model = None
        self._failed = False
        # the measured floor and full-weight point per pool, filled once per
        # boot by `_calibrate`; a pool that is not in here is on the config's
        self._floors = {}
        # and each row's own mean cosine over those same cues, per pool:
        # {pool: ({ref: mean}, the pool's mean)}. Half the cosine belongs to
        # the row rather than to the cue, and subtracting the row's own mean
        # is what stops a row that is close to everything from answering
        # everything (`score`).
        self._means = {}
        self._ensure()

    def _ensure(self):
        with self.store.lock:
            self.store.conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    kind TEXT, ref TEXT, model TEXT, dim INTEGER, vec BLOB,
                    PRIMARY KEY (kind, ref, model))""")
            self.store.conn.commit()

    # ---------------- the model ----------------

    def available(self):
        c = self.config.embed
        if not c.enabled or self._failed:
            return False
        return self._load() is not None

    def loaded(self):
        """Is the model in memory already? The persona runs on the loop
        thread, so it asks for meaning only when the answer is free: the
        first load of the model takes seconds and the backfill thread is
        what pays for it."""
        return self._model is not None

    def _load(self):
        if self._model is not None:
            return self._model
        if self._failed:
            return None
        url = str(getattr(self.config.embed, "url", "") or "").strip()
        if url:
            # shared service: no torch, no sentence_transformers in this process
            self._model = _RemoteModel(url, float(getattr(self.config.embed, "url_timeout", 30) or 30))
            if not self._model.ping():
                self._model = None
                self._failed = True
                logger.log(f"[embed] off: {url} unreachable")
                return None
            logger.log(f"[embed] {self.config.embed.model} via {url}")
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = SentenceTransformer(self.config.embed.model, device=device)
            logger.log(f"[embed] {self.config.embed.model} on {device}")
        except Exception as e:
            self._failed = True
            logger.log(f"[embed] off: {type(e).__name__}: {str(e)[:120]}")
            return None
        return self._model

    def _encode(self, texts, prefix):
        m = self._load()
        if m is None:
            return None
        if isinstance(m, _RemoteModel):
            # the service adds the e5 prefix from input_type (gateway contract)
            kind = "query" if prefix.startswith("query") else "passage"
            try:
                arr = m.encode([str(t or "")[:2000] for t in texts], kind,
                               int(self.config.embed.batch_size))
            except Exception as e:
                self._model = None
                self._failed = True
                logger.log(f"[embed] off: {type(e).__name__}: {str(e)[:120]}")
                return None
            return arr
        pre = prefix if "e5" in str(self.config.embed.model).lower() else ""
        arr = m.encode([pre + str(t or "")[:2000] for t in texts], normalize_embeddings=True,
                       batch_size=int(self.config.embed.batch_size), show_progress_bar=False)
        return np.asarray(arr, dtype=np.float32)

    # ---------------- vectors of the record ----------------

    def vectors(self, kind, items, write=True):
        """`items`: [(ref, text)]. The stored vector for each, the missing ones
        embedded now and kept. Returns {ref: vec} (refs as str).

        `write=False` reads what is already stored and embeds nothing: for a
        caller on the loop thread, where encoding a pool of a few hundred
        rows would be paid for by his next reply. The backfill thread is the
        writer (`App._backfill_vectors`), and a row written while she is
        running is embedded by whoever wrote it."""
        if not items or not self.config.embed.enabled or self._failed:
            return {}
        if write and not self.available():
            return {}
        model = str(self.config.embed.model)
        refs = [str(r) for r, _ in items]
        out = {}
        with self.store.lock:
            q = ",".join("?" * len(refs))
            rows = self.store.conn.execute(
                f"SELECT ref, dim, vec FROM embeddings WHERE kind=? AND model=? AND ref IN ({q})",
                (kind, model, *refs)).fetchall()
        for r in rows:
            out[str(r["ref"])] = np.frombuffer(r["vec"], dtype=np.float16).astype(np.float32)
        missing = [(str(r), t) for r, t in items if str(r) not in out and str(t or "").strip()] if write else []
        if missing:
            vecs = self._encode([t for _, t in missing], "passage: ")
            if vecs is not None:
                with self.store.lock:
                    for (ref, _), v in zip(missing, vecs):
                        out[ref] = v
                        self.store.conn.execute(
                            "INSERT OR REPLACE INTO embeddings(kind, ref, model, dim, vec) VALUES (?,?,?,?,?)",
                            (kind, ref, model, int(v.shape[0]), v.astype(np.float16).tobytes()))
                    self.store.conn.commit()
                logger.log(f"[embed] {len(missing)} {kind} vector(s) written")
        # the writer is the backfill thread and the compile, never the loop
        # thread, so this is where the encoding of the calibration cues can
        # be paid for
        if write:
            try:
                self._calibrate(kind)
            except Exception as e:
                logger.log(f"[embed] {kind}: no floor measured, the configured one stands: "
                           f"{type(e).__name__}: {str(e)[:80]}")
        return out

    def forget(self, kind, refs):
        """Drop the vectors of rows that were rewritten (a day recompiled)."""
        if not refs:
            return
        with self.store.lock:
            q = ",".join("?" * len(refs))
            self.store.conn.execute(f"DELETE FROM embeddings WHERE kind=? AND ref IN ({q})", (kind, *[str(r) for r in refs]))
            self.store.conn.commit()

    def query(self, text, load=True):
        """The vector of a cue, or None when embeddings are off. `load=False`
        answers None rather than loading the model, for a caller that must
        not block."""
        if not str(text or "").strip() or not self.config.embed.enabled or self._failed:
            return None
        if not load and not self.loaded():
            return None
        if not self.available():
            return None
        v = self._encode([text], "query: ")
        return None if v is None else v[0]

    @staticmethod
    def cosine(q, vec):
        return float(np.dot(q, vec))

    # ---------------- the floor, measured on this save ----------------

    def _configured(self, pool):
        """The floor and the full-weight point the config gives a pool."""
        c = self.config.embed
        pair = (dict(getattr(c, "cos_by_pool", {}) or {}).get(str(pool or "")) or
                [c.min_cos, c.top_cos])
        return float(pair[0]), float(pair[1])

    def _cues(self, n):
        """A sample of real cues from this save's own record: what he wrote and
        what she wrote, which is most of what a moment cue is made of
        (`sim/recall.moment_cue`). Spread over the record rather than taken
        from the end, so one evening's subject does not stand for the save."""
        try:
            # the whole record, not the scene she is in: this samples cues for
            # the embedding calibration, and a directed scene must not narrow it
            rows = self.store.recent_messages(2000, scene_id="*") or []
        except Exception:
            return []
        texts = [t for t in (str(r["text"] or "").strip() for r in rows) if len(t) >= 12]
        if len(texts) <= n:
            return texts
        step = max(1, len(texts) // n)
        return texts[::step][:n]

    def _calibrate(self, pool):
        """This pool's floor, measured once per boot on this save's own rows.

        The pair that has to be measured is the one the retrieval actually
        makes: a CUE, asked with the query prefix, against a stored row, which
        was written with the passage prefix. Pairing stored vectors with each
        other reads 0.04 to 0.08 too high and by a different amount per pool,
        so a floor taken from that would switch retrieval off; encoding a
        row's own text as the question overshoots too, because a whole row is
        a far better question than a real moment is.

        The floor goes a margin above the `calibrate_pct`th percentile of that
        distribution and the full-weight point keeps the band width the config
        gives the pool, so a pool whose rows all sit high stops saturating at
        `weight` instead of scoring every row full marks. Too few rows or too
        few cues and the configured pair stands and the pool tries again on
        the next boot."""
        c = self.config.embed
        if pool in self._floors or not bool(c.calibrate):
            return
        with self.store.lock:
            rows = self.store.conn.execute(
                "SELECT ref, vec FROM embeddings WHERE kind=? AND model=? LIMIT ?",
                (pool, str(c.model), int(c.calibrate_sample))).fetchall()
        cues = self._cues(int(c.calibrate_cues))
        if len(rows) < int(c.calibrate_min_rows) or len(cues) < int(c.calibrate_min_cues):
            return
        q = self._encode(cues, "query: ")
        if q is None:
            return
        M = np.stack([np.frombuffer(r["vec"], dtype=np.float16).astype(np.float32) for r in rows])
        grid = np.asarray(q @ M.T)          # one row per cue, one column per row
        pairs = grid.ravel()
        floor0, top0 = self._configured(pool)
        floor = float(np.percentile(pairs, float(c.calibrate_pct))) + float(c.calibrate_margin)
        top = floor + max(0.01, top0 - floor0)
        self._floors[pool] = (floor, top)
        # the same pass measures how central each row is: its mean cosine
        # against these unrelated cues, against the pool's own mean
        per_row = grid.mean(axis=0)
        self._means[pool] = ({str(r["ref"]): float(m) for r, m in zip(rows, per_row)},
                             float(pairs.mean()))
        spread = float(per_row.max() - per_row.min()) if len(per_row) else 0.0
        logger.log(f"[embed] {pool}: floor {floor0:.2f} -> {floor:.3f}, full weight "
                   f"{top0:.2f} -> {top:.3f} ({int(c.calibrate_pct)}th percentile of "
                   f"{len(cues)} cue(s) against {len(rows)} row(s), median {np.median(pairs):.3f}"
                   + (f"; each row's own mean subtracted, and they span {spread:.3f}"
                      if bool(getattr(c, "center_rows", False)) else "") + ")")

    def centred(self, cos, pool="", ref=None):
        """This cosine with the ROW's own average taken out.

        A row's mean cosine over unrelated cues varies by 0.035 across a pool
        whose whole scoring band is 0.07 wide, so the most central rows
        answered cues they had nothing to do with. Subtracting the row's own
        mean and adding the pool's back keeps the numbers on the scale the
        floor was measured on, and leaves only the part of the cosine that is
        about THIS cue. A row written since the measurement has no mean and
        is scored as it stands."""
        if not bool(getattr(self.config.embed, "center_rows", False)) or ref is None:
            return cos
        got = self._means.get(str(pool or ""))
        if not got:
            return cos
        means, pool_mean = got
        m = means.get(str(ref))
        return cos if m is None else float(cos) - (m - pool_mean)

    def score(self, cos, pool="", ref=None):
        """A cosine as a retrieval score: nothing under the pool's floor,
        rising to `weight` at its top and capped there.

        The pool's own measured floor if it has one (`_calibrate`, once per
        boot on this save's rows), otherwise the configured pair -- `min_cos`
        and `top_cos`, or the pool's own entry in `embed.cos_by_pool`, which a
        pool of one-line rows has because a sentence has less to be unlike
        than a paragraph does and both ends of the range come down with it."""
        c = self.config.embed
        floor, top = self._floors.get(str(pool or "")) or self._configured(pool)
        cos = self.centred(cos, pool, ref)
        if cos <= floor:
            return 0.0
        return float(c.weight) * min(1.0, (cos - floor) / max(1e-6, top - floor))

    def report(self):
        with self.store.lock:
            rows = self.store.conn.execute("SELECT kind, COUNT(*) FROM embeddings GROUP BY kind").fetchall()
        state = "off" if not self.config.embed.enabled else ("failed" if self._failed else ("loaded" if self._model else "not loaded yet"))
        floors = ("; floors measured on this save: "
                  + ", ".join(f"{k} {v[0]:.3f}-{v[1]:.3f}" for k, v in sorted(self._floors.items()))
                  ) if self._floors else "; floors as configured (nothing measured yet)"
        return (f"embeddings: {self.config.embed.model} ({state}); "
                + (", ".join(f"{r[0]} {r[1]}" for r in rows) or "nothing embedded") + floors)
