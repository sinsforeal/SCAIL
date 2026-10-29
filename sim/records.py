import re
import json
import logger
from sim import roster

# The world's memory between ticks: threads (small ongoing things, kept as
# records with a status instead of a six-slot list), cast sheets (who the
# people around her are right now, not just meters), places she keeps going
# back to, and arcs (the showrunner's slow pressures). Everything here is
# cheap text that other prompts read; nothing here calls a model.


def _norm(s):
    return re.sub(r"[^a-z0-9 ]+", "", (s or "").lower()).strip()


def _strip_age(text):
    """The brief decorates threads with '(today)' / '(3d)'; the director echoes it. Remove it."""
    return re.sub(r"\s*\((?:today|\d+d)\)\s*$", "", text.strip()).strip()


def _head(s):
    """The stable part of a thread: what comes before a colon, or the first six words."""
    s = (s or "").split(":")[0]
    return " ".join(_norm(s).split()[:6])


def _sim(a, b):
    """Thread identity is the head; the director rewrites the tail every tick."""
    ha, hb = _head(a), _head(b)
    if ha and ha == hb:
        return 1.0
    if ha and hb and (ha.startswith(hb) or hb.startswith(ha)) and min(len(ha), len(hb)) >= 12:
        return 0.9
    ta, tb = set(_norm(a).split()), set(_norm(b).split())
    if not ta or not tb:
        return 0.0
    j = len(ta & tb) / len(ta | tb)
    sa, sb = set(ha.split()), set(hb.split())
    jh = len(sa & sb) / len(sa | sb) if sa and sb else 0.0
    return max(j, jh)


class Records:
    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock

    # ---------------- threads ----------------

    def _match(self, text, candidates):
        best, score = None, 0.0
        for t in candidates:
            s = 1.0 if _norm(t["text"]) == _norm(text) else _sim(t["text"], text)
            if s > score:
                best, score = t, s
        return best if score >= self.config.threads.match_threshold else None

    def sync_threads(self, open_list, resolved_list, people_hint=""):
        """Reconcile the director's lists with the table. Open ones are touched
        or created; resolved ones are closed; open ones the director dropped go
        dormant (they can resurface) instead of vanishing."""
        now = self.clock.now_ts()
        today = self.clock.date_str()
        cur_open = self.store.threads_by_status("open")
        cur_dormant = self.store.threads_by_status("dormant", 50)
        seen = set()
        for text in open_list:
            text = _strip_age(str(text))
            if not text:
                continue
            m = self._match(text, cur_open) or self._match(text, cur_dormant)
            if m:
                self.store.update_thread(m["id"], now, status="open", text=text)
                seen.add(m["id"])
            else:
                tid = self.store.add_thread(text, now, today, people_hint)
                seen.add(tid)
                # the director often lists two variants of one thread in a tick;
                # the second must see the row the first just made
                cur_open = list(cur_open) + [{"id": tid, "text": text, "status": "open", "updated_ts": now}]
        for text in resolved_list:
            text = _strip_age(str(text))
            m = self._match(text, cur_open) or self._match(text, cur_dormant)
            if m:
                self.store.update_thread(m["id"], now, status="resolved", resolved_date=today)
                seen.add(m["id"])
            else:
                tid = self.store.add_thread(str(text), now, today, people_hint)
                self.store.update_thread(tid, now, status="resolved", resolved_date=today)
        for t in cur_open:
            if t["id"] not in seen:
                self.store.update_thread(t["id"], now, status="dormant")
        self.dedupe_threads()
        # cap the open set: oldest untouched go dormant
        opened = self.store.threads_by_status("open")
        extra = len(opened) - self.config.director.max_open_threads
        if extra > 0:
            for t in sorted(opened, key=lambda x: x["updated_ts"])[:extra]:
                self.store.update_thread(t["id"], now, status="dormant")

    def dedupe_threads(self):
        """Rows with the same head are one thread: keep the most recently touched, drop the rest. Returns how many went."""
        rows = self.store.all_threads() if hasattr(self.store, "all_threads") else []
        by_head = {}
        gone = 0
        for t in sorted(rows, key=lambda x: -(x.get("updated_ts") or 0)):
            h = _head(t["text"])
            if not h:
                continue
            if h in by_head:
                keep = by_head[h]
                # a resolved twin wins over an open one only if it is the newer row (it already is, by sort)
                self.store.delete_thread(t["id"])
                gone += 1
            else:
                by_head[h] = t
        return gone

    def age_threads(self):
        """Nightly: open threads nobody touched for a while go dormant."""
        cutoff = self.clock.now_ts() - self.config.threads.dormant_after_days * 86400
        for t in self.store.threads_by_status("open"):
            if t["updated_ts"] < cutoff:
                self.store.update_thread(t["id"], self.clock.now_ts(), status="dormant")

    def open_thread_texts(self):
        return [t["text"] for t in self.store.threads_by_status("open")]

    def pressing_thread(self, unsaid=0, now_ts=None, bars=None):
        """The thing she has been not-saying to him, once it has sat long
        enough to force itself out.

        Every outlet for `unsaid` was private -- the diary takes 30 off it and
        an X post 12 -- so the pressure vented and the thread never reached
        him. One thread has ever been resolved. This is the other outlet: an
        open thread about him that she has not raised gains pressure with age
        and with how much is going unsaid, and past a threshold it becomes the
        thing her next message is about. Returns the row or None."""
        c = self.config.threads
        now = now_ts or self.clock.now_ts()
        best = None
        for r in (self.store.threads_by_status("open") + self.store.threads_by_status("dormant", 20)):
            if r.get("status") == "resolved":
                continue
            text = r.get("text") or ""
            if not about_him(text, self.config) or not unasked(text):
                continue
            # a thread about something she found by going through his things is
            # not a thing she can raise: asking would admit she looked. Without
            # this the pressure eventually pushes out the one thing she never
            # would say.
            if bars and bars(text):
                continue
            age_days = max(0.0, (now - (r.get("created_ts") or now)) / 86400.0)
            if age_days < c.pressure_after_days:
                continue
            pressure = age_days * c.pressure_per_day + max(0, unsaid - c.pressure_unsaid_ref) * c.pressure_per_unsaid
            if pressure >= c.pressure_threshold and (best is None or pressure > best[0]):
                best = (pressure, r)
        return best[1] if best else None

    def threads_brief(self, keep=None):
        """The small ongoing things, as prompt text.

        `keep(row)` is asked of each thread by a caller that may not be shown
        all of them -- a day planned for a circle of her own, in a world
        somebody else keeps, where a thread about the girls at her school is
        about strangers. Every thread, by default."""
        c = self.config.threads
        today = self.clock.now().date()

        def age(t):
            d = (today - self.clock.to_char(t["created_ts"]).date()).days
            return "today" if d == 0 else f"{d}d"

        def rows(status, limit=None):
            out = self.store.threads_by_status(status) if limit is None \
                else self.store.threads_by_status(status, limit)
            return [t for t in out if keep(t)] if keep else out

        op = rows("open")
        do = rows("dormant", c.dormant_in_prompt)
        re_ = rows("resolved", c.resolved_in_prompt)
        out = ["OPEN: " + ("; ".join(f"{t['text']} ({age(t)})" for t in op) or "(none)")]
        if do:
            out.append("DORMANT (not mentioned lately, may resurface or stay buried): " + "; ".join(t["text"] for t in do))
        if re_:
            out.append("RESOLVED RECENTLY (memory, do not reopen): " + "; ".join(f"{t['text']} ({t.get('resolved_date') or ''})" for t in re_))
        return "\n".join(out)

    # ---------------- cast ----------------

    def cast_sheet(self, rels, meters=True, influence=False):
        """`influence` -- the clear pressure this person puts on her, from
        cast.json -- was dropped here for four months and so reached the
        beat-writer and nothing else. Readers that weigh what a person does
        to her (the state model, the ick, her private mind) ask for it; the
        persona does not, because in her own prompt it would read as
        self-narration ("Rena decides for you")."""
        lines = []
        for name, r in rels.items():
            bits = [r.get("role", "")]
            if influence and r.get("influence"):
                bits.append(f"how they move her: {str(r['influence'])[:160]}")
            if r.get("situation"):
                bits.append(f"now: {r['situation']}")
            if r.get("unresolved"):
                bits.append(f"between them: {r['unresolved']}")
            if r.get("last_seen"):
                bits.append(f"last seen {r['last_seen']}")
            if meters:
                bits.append(f"closeness {r.get('closeness')}, standing {r.get('standing')}, tension {r.get('tension')}")
            if r.get("note") and not r.get("situation"):
                bits.append(r["note"])
            lines.append(f"- {name}: " + " | ".join(b for b in bits if b))
        return "\n".join(lines) or "(nobody yet)"

    def apply_cast(self, rels, updates, new_people, date_str):
        d = self.config.cast_defaults
        n_upd = 0
        for name, u in (updates or {}).items():
            if not isinstance(u, dict):
                continue
            key = self._cast_key(rels, name)
            if not key:
                continue
            # What somebody is going through, and whether she saw them today,
            # is decided by whoever keeps that person. A character who only
            # READS a world holds meters on the people in it and gives none of
            # them a situation: hers cached one for two of the owner's cast on
            # her own compile (`sim/roster.is_own`).
            if not roster.is_own(self.config, key):
                continue
            for f in ("situation", "unresolved"):
                if isinstance(u.get(f), str):
                    rels[key][f] = u[f].strip()[:200]
            if u.get("seen"):
                rels[key]["last_seen"] = date_str
            n_upd += 1
        n_new = 0
        for p in (new_people or []):
            if not isinstance(p, dict) or not p.get("name"):
                continue
            name = str(p["name"]).strip()[:40]
            # cast_defaults is a config Section: attribute access only (d["x"] raised TypeError on the first
            # new person a compile proposed, cl3_s_tomoe 10-23)
            if self._cast_key(rels, name) or len(rels) >= d.max_people:
                continue
            rels[name] = {"role": str(p.get("role", ""))[:120], "closeness": d.closeness, "standing": d.standing,
                          "tension": d.tension, "note": str(p.get("note", ""))[:200], "situation": str(p.get("situation", ""))[:200],
                          "unresolved": "", "last_seen": date_str, "kind": p.get("kind", "person"), "added": date_str}
            n_new += 1
        if n_upd or n_new:
            logger.log(f"[records] cast: {n_upd} updated, {n_new} new")
        return rels

    @staticmethod
    def _cast_key(rels, name):
        n = _norm(name)
        for k in rels:
            if _norm(k) == n or _norm(k).replace("chan", "").strip() == n.replace("chan", "").strip():
                return k
        return None

    # ---------------- places ----------------

    def places(self):
        return self.store.get("places", [])

    def places_brief(self):
        pl = self.places()
        if not pl:
            return "(none recorded yet)"
        return "; ".join(f"{p['name']} ({p.get('note', '')})" if p.get("note") else p["name"] for p in pl[-self.config.places.in_prompt:])

    def apply_places(self, new_places, date_str):
        pl = self.places()
        for p in (new_places or []):
            if not isinstance(p, dict) or not p.get("name"):
                continue
            name = str(p["name"]).strip()[:60]
            hit = next((x for x in pl if _norm(x["name"]) == _norm(name)), None)
            if hit:
                # a day compiled twice is one visit, not two
                if hit.get("last") != date_str:
                    hit["visits"] = hit.get("visits", 1) + 1
                hit["last"] = date_str
                if p.get("note"):
                    hit["note"] = str(p["note"])[:120]
            else:
                pl.append({"name": name, "note": str(p.get("note", ""))[:120], "first": date_str, "last": date_str, "visits": 1})
        pl.sort(key=lambda x: (x.get("last", ""), x.get("visits", 0)))
        self.store.set("places", pl[-self.config.places.max_places:])

    # ---------------- arcs ----------------

    def arcs(self):
        return [a for a in self.store.get("arcs", []) if a.get("status") == "active"]

    def all_arcs(self):
        return self.store.get("arcs", [])

    def set_arcs(self, arcs, retire_titles):
        cur = self.all_arcs()
        today = self.clock.date_str()
        for a in cur:
            if a.get("title") in (retire_titles or []) and a.get("status") == "active":
                a["status"] = "closed"
                a["closed"] = today
        for a in arcs or []:
            if not isinstance(a, dict) or not a.get("title"):
                continue
            hit = next((x for x in cur if _norm(x["title"]) == _norm(a["title"])), None)
            rec = {"title": str(a["title"])[:80], "kind": str(a.get("kind", ""))[:20], "pressure": str(a.get("pressure", ""))[:300],
                   "beats": [{"around": str(b.get("around", "")), "beat": str(b.get("beat", ""))[:200]} for b in (a.get("beats") or []) if isinstance(b, dict)][:6],
                   "status": "active", "opened": hit.get("opened") if hit else today, "notes": (hit or {}).get("notes", [])}
            if hit:
                hit.update(rec)
            else:
                cur.append(rec)
        active = [a for a in cur if a.get("status") == "active"]
        if len(active) > self.config.showrunner.max_arcs:
            for a in active[: len(active) - self.config.showrunner.max_arcs]:
                a["status"] = "closed"
                a["closed"] = today
        self.store.set("arcs", cur[-40:])

    def apply_arc_notes(self, notes, date_str):
        cur = self.all_arcs()
        for n in notes or []:
            if not isinstance(n, dict) or not n.get("title"):
                continue
            hit = next((x for x in cur if _norm(x["title"]) == _norm(n["title"])), None)
            if not hit:
                continue
            if n.get("note"):
                # one note per date: a recompile replaces the day's note
                kept = [x for x in hit.get("notes") or [] if not str(x).startswith(f"{date_str}:")]
                hit["notes"] = (kept + [f"{date_str}: {str(n['note'])[:200]}"])[-10:]
            if n.get("closed"):
                hit["status"] = "closed"
                hit["closed"] = date_str
        self.store.set("arcs", cur)

    def arcs_brief(self, with_beats=True):
        today = self.clock.date_str()
        out = []
        for a in self.arcs():
            s = f"- {a['title']} [{a.get('kind', '')}]: {a.get('pressure', '')}"
            if with_beats and a.get("beats"):
                nxt = [b for b in a["beats"] if (b.get("around") or "") >= today][:2]
                if nxt:
                    s += " | coming: " + "; ".join(f"around {b['around']}: {b['beat']}" for b in nxt)
            if a.get("notes"):
                s += " | lately: " + a["notes"][-1]
            out.append(s)
        return "\n".join(out) or "(no arcs yet)"

    def dump(self):
        return json.dumps({"threads": self.store.threads_by_status("open"), "arcs": self.all_arcs(), "places": self.places()}, ensure_ascii=False, indent=1)

# ---- things she has not said to him ----

_HIM = re.compile(r"\b(he|him|his)\b", re.I)
# the people a thread can be about instead of him: the words for family and
# school, and every name on her roster. The names come from her cast file,
# never from this file -- a list written here was the first character's cast
# for whoever ran the library.
_OTHER_WORDS = ("mom", "mum", "dad", "okaa", "otou", "mother", "father", "teacher", "class")
_OTHERS_CACHE = {}
def _others(config):
    key = id(config)
    hit = _OTHERS_CACHE.get(key)
    if hit is not None:
        return hit
    names = set(_OTHER_WORDS)
    try:
        from sim import roster
        for k in roster.everyone(config):
            rec = roster.rec_of(config, k) or {}
            for n in [k, rec.get("ja", ""), rec.get("reading", "")] + list(rec.get("aliases") or []):
                n = str(n or "").strip().lower()
                if len(n) >= 2:
                    names.add(re.escape(n))
    except Exception:
        pass
    rx = re.compile(r"\b(" + "|".join(sorted(names, key=len, reverse=True)) + r")\b", re.I)
    _OTHERS_CACHE[key] = rx
    return rx


def about_him(text, config=None):
    """Is this thread about him? The threads table stores the scene's company
    in `people`, which is "alone" for every thread that is actually about him,
    so it cannot be used. His threads are the ones written in he/him/his and
    not about somebody named."""
    t = text or ""
    others = _others(config) if config is not None else re.compile(r"\b(" + "|".join(_OTHER_WORDS) + r")\b", re.I)
    return bool(_HIM.search(t)) and not others.search(t)


def unasked(text):
    """Still not raised with him. The director writes the tail of a thread in
    plain words and says so."""
    return bool(re.search(r"unasked|unanswered|unreplied|has not asked|hasn't asked|"
                          r"never asked|still not|not said|unsaid|did not say|dodged",
                          text or "", re.I))
