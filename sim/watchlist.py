import logger

# What she is watching, with a cursor. His MAL shelf is his; this is hers:
# a few shows she is working through, each at an episode, advancing when she
# watches. It exists so the "watching" experience has a REAL title and
# episode (stable, not re-picked by the model each time), which is what the
# recap fetch keys on -- and so he can seed "she is watching this now".
#
# kv `watchlist`: [{title, ja, kind: anime|drama, ep, total, added, last_ts}]
# spec: docs/recap.md


class Watchlist:
    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock
        self._seed_once()

    def _seed_once(self):
        if self.store.get("watchlist") is not None:
            return
        seed = []
        for row in (self.config.watchlist.seed or []):
            seed.append({"title": row.get("title", ""), "ja": row.get("ja", row.get("title", "")),
                         "kind": row.get("kind", "anime"), "ep": int(row.get("ep", 1)),
                         "total": int(row.get("total", 0)), "added": self.clock.date_str(), "last_ts": 0})
        self.store.set("watchlist", seed)
        if seed:
            logger.log(f"[watchlist] seeded {len(seed)} show(s)")

    def all(self):
        return self.store.get("watchlist", []) or []

    def _save(self, rows):
        self.store.set("watchlist", rows)

    def unfinished(self):
        return [r for r in self.all() if not r.get("total") or int(r.get("ep", 1)) <= int(r["total"])]

    def current(self):
        """The show she would put on next: an unfinished one, the one she has
        not touched for the longest (so she rotates rather than binges one)."""
        rows = self.unfinished()
        if not rows:
            return None
        rows.sort(key=lambda r: float(r.get("last_ts", 0)))
        return dict(rows[0])

    def advance(self, title):
        """She watched an episode of this show: move its cursor on, stamp it."""
        rows = self.all()
        for r in rows:
            if r.get("title") == title:
                if r.get("total") and int(r.get("ep", 1)) >= int(r["total"]):
                    r["last_ts"] = self.clock.now_ts()
                    break
                r["ep"] = int(r.get("ep", 1)) + 1
                r["last_ts"] = self.clock.now_ts()
                break
        self._save(rows)

    def add(self, title, ja="", kind="anime", ep=1, total=0):
        rows = self.all()
        if any(r.get("title") == title for r in rows):
            return f"already watching {title}"
        rows.append({"title": title, "ja": ja or title, "kind": kind, "ep": int(ep),
                     "total": int(total), "added": self.clock.date_str(), "last_ts": 0})
        self._save(rows)
        return f"added {title} ({kind}) at ep {ep}"

    def remove(self, title):
        rows = [r for r in self.all() if r.get("title") != title]
        self._save(rows)
        return f"removed {title}"

    def set_ep(self, title, ep):
        rows = self.all()
        for r in rows:
            if r.get("title") == title:
                r["ep"] = int(ep)
        self._save(rows)
        return f"{title} -> ep {ep}"

    # ---------------- a show of her own ----------------

    def queries(self):
        """What she would type into X search about her own shows: the
        Japanese titles. Joined to the taste sheet's queries by
        `Taste.queries`, so her searches seek her own things."""
        return [str(r.get("ja") or r.get("title") or "").strip() for r in self.unfinished() if (r.get("ja") or r.get("title"))]

    def pick_due(self):
        c = self.config.watchlist
        if not bool(getattr(c, "pick_enabled", True)):
            return False, "off"
        open_ = self.unfinished()
        if len(open_) >= int(getattr(c, "max_open", 3) or 3):
            return False, f"{len(open_)} unfinished already"
        last = float(self.store.get("watch_pick_ts", 0) or 0)
        every = float(getattr(c, "pick_every_days", 7) or 7) * 86400
        if len(open_) >= int(getattr(c, "keep_min", 2) or 2) and self.clock.now_ts() - last < every:
            return False, f"picked {int((self.clock.now_ts() - last) / 86400)} day(s) ago; {len(open_)} unfinished"
        return True, "short of shows or a week since the last pick"

    @staticmethod
    def _bare(title):
        """A title without the dressing a model uses to slip past a list:
        parentheticals, 're-watch', 'season 2', 'S2', 'part 1'."""
        import re as _re
        t = str(title or "").lower()
        t = _re.sub(r"\([^)]*\)", " ", t)
        t = _re.sub(r"\b(re-?watch|rewatch|season\s*\d+|s\d+|part\s*\d+|\d+(st|nd|rd|th)\s+season|the movie)\b", " ", t)
        t = _re.sub(r"[^a-z0-9 ]+", " ", t)
        return _re.sub(r"\s+", " ", t).strip()

    def _on_his_list(self, title, ja, kb):
        """On his list, strictly and then by containment: 'Bocchi the Rock!
        (Re-watch)' is Bocchi the Rock!, and another season of a show he
        watched is his show."""
        if kb is None:
            return False
        bare = self._bare(title)
        try:
            if kb.resolve_strict(title) or kb.resolve_strict(bare) or (ja and kb.resolve_strict(ja)):
                return True
            for _aid, _t, ntitle, neng in kb.his_titles():
                for n in (ntitle, neng):
                    n = self._bare(n)
                    if n and len(n) >= 6 and (n in bare or bare in n) and min(len(n), len(bare)) / max(len(n), len(bare)) >= 0.5:
                        return True
        except Exception:
            return False
        return False

    def pick_own(self, llm, sources, kb=None, force=False):
        """One `watch_pick` call: a show she would watch, from her own corner
        -- her sheet, the accounts she keeps liking, what is going round.
        His list is context, not a fence (his call, 2026-08-31): a pick that
        is also his is marked `his` and kept -- what is refused is only a
        duplicate of her own list. The pick lands at episode 1 marked
        `own`."""
        due, why = self.pick_due()
        if not due and not force:
            return None, why
        his_txt = ""
        his = []
        if kb is not None:
            try:
                his = kb.his_titles()
                his_txt = "\n".join(f"- {t}" for _a, t, _n, _e in his[:400])
            except Exception:
                his = []
        have = [f"- {r.get('title')} ({r.get('ja')}) ep {r.get('ep')}/{r.get('total') or '?'}" for r in self.all()]
        user = (f"WHAT HE HAS WATCHED (context, not a fence: overlap is normal -- he shows her things -- but the pick is for HER reasons, never because it is his):\n{his_txt or '(unknown)'}\n\n"
                f"HER TASTE SHEET:\n{sources.get('sheet', '') or '(none)'}\n\n"
                f"WHAT SHE HAS BEEN INTO LATELY:\n{sources.get('diet', '') or '(nothing recorded)'}\n\n"
                # what is going round is her program's, and her school is
                # in it: a character whose program supplies no such source
                # gets no section rather than a heading over "(nothing)"
                + (f"GOING ROUND (Japan, her school, her timeline):\n{sources.get('around', '') or '(nothing)'}\n\n"
                   if "around" in sources else "")
                + f"WATCHING ALREADY:\n" + ("\n".join(have) or "(nothing)") + "\n")
        tried = []
        for attempt in range(int(getattr(self.config.watchlist, "pick_tries", 4) or 4)):
            ask = user + (("\nALREADY ON HER LIST -- pick something else: " + ", ".join(tried) + "\n") if tried else "")
            data, _raw = llm.call_json("watch_pick", [{"role": "system", "content": self.config.prompt_text("watch_pick")},
                                                       {"role": "user", "content": ask}])
            if not isinstance(data, dict) or not str(data.get("title", "") or "").strip():
                logger.log("[watchlist] pick: no usable answer")
                return None, "no usable answer"
            title = str(data.get("title", "")).strip()[:80]
            ja = str(data.get("ja", "") or title).strip()[:80]
            kind = str(data.get("kind", "anime") or "anime").strip().lower()[:10]
            try:
                total = max(0, int(data.get("total", 0) or 0))
            except (TypeError, ValueError):
                total = 0
            why = str(data.get("why", "") or "").strip()[:400]
            if any(r.get("title", "").lower() == title.lower() or (ja and r.get("ja") == ja) for r in self.all()):
                tried.append(title)
                continue
            on_his = bool(his) and self._on_his_list(title, ja, kb)
            rows = self.all()
            rows.append({"title": title, "ja": ja, "kind": kind if kind in ("anime", "drama") else "anime", "ep": 1,
                         "total": total, "added": self.clock.date_str(), "last_ts": 0, "own": True,
                         "his": bool(on_his), "why": why})
            self._save(rows)
            self.store.set("watch_pick_ts", self.clock.now_ts())
            log = list(self.store.get("watch_pick_log", []) or [])
            log.append({"ts": self.clock.now_ts(), "date": self.clock.date_str(), "title": title, "ja": ja, "why": why})
            self.store.set("watch_pick_log", log[-40:])
            logger.log(f"[watchlist] hers: {title} ({ja}, {kind}" + (f", {total} eps" if total else "")
                       + (", also on his list" if on_his else "") + f") -- {why[:80]}")
            return rows[-1], "picked"
        return None, "every pick was already on her list"

    def report(self):
        rows = self.all()
        if not rows:
            return "watchlist empty"
        out = []
        for r in rows:
            tot = f"/{r['total']}" if r.get("total") else ""
            out.append(f"- {r['title']} ({r['kind']}) ep {r.get('ep', 1)}{tot}"
                       + (f" [ja: {r['ja']}]" if r.get("ja") and r["ja"] != r["title"] else "")
                       + (" -- hers" if r.get("own") else " -- seed")
                       + (f": {r['why'][:100]}" if r.get("why") else ""))
        due, why = self.pick_due()
        return "watchlist:\n" + "\n".join(out) + f"\nnext pick of her own: {'due' if due else 'not yet'} ({why})"
