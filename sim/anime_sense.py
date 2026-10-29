import json
import sqlite3
import datetime
import logger
from sim import sight
from sim.anime_kb import open_ro

# Her sense of what he watches, from his episode history (data/mal_history.db,
# kept current by tools/mal_history.py's daemon; read-only here, no browser).
# Three things:
#
#  - the weekly shelf check: once a week, on her day for it, she has looked at
#    his list -- what he is in the middle of, what he left hanging, what he just
#    finished -- and it sits in her head as something to bring up. It lands as a
#    director share_hint, so intent/persona still decide whether and how she
#    says it (she may nag, tease, ask, or decide it's not worth it). Never a
#    scripted broadcast.
#  - his habits as facts: what the analysis knows (when he watches, how fast he
#    finishes, what he likes, his scoring) written into user_facts through
#    memory, so she knows him the way a friend who has watched his list does.
#    Refreshed monthly; near-duplicates reinforce rather than pile up.
#  - the "what is he watching right now" line for her situation, so a mention
#    of a show he is mid-way through is met with where he actually is.

STATUS = {1: "watching", 2: "completed", 3: "on hold", 4: "dropped", 6: "plan to watch"}


class AnimeSense:
    def __init__(self, config, store, clock, memory=None, db_path="data/mal_history.db"):
        self.config = config
        self.store = store
        self.clock = clock
        self.memory = memory
        self.db_path = db_path
        # Whether his anime mirror is actually there. `tools/mal_history.py`'s
        # daemon (`mal_daemon.cmd`) builds `anime`, `anime_detail` and
        # `episodes`; a machine where it has never run has a file at this path
        # with none of those tables, and `shelf` then raised
        # `no such table: anime_detail` through the day hook on every boot.
        # A sense with nothing to read is off, said once, rather than a fault
        # repeated daily.
        self.enabled = self._mirror_present()
        if not self.enabled:
            logger.log(f"[anime] no `anime` table in {db_path}: his mirror has not been built. "
                       "The anime sense is off until the MAL daemon runs "
                       "(mal_daemon.cmd; it needs tools\\mal_history.py login once)")

    def _mirror_present(self):
        """True when the file holds the mirror's own schema."""
        try:
            con = open_ro(self.db_path)
        except Exception:
            return False
        if not con:
            return False
        try:
            return bool(con.execute(
                "select name from sqlite_master where type='table' and name='anime'").fetchone())
        except Exception:
            return False
        finally:
            try:
                con.close()
            except Exception:
                pass

    def _con(self):
        """Read-only on his mirror, or None when there is nothing to read.

        None means "no mirror", and every caller here already handles it: the
        shelf is None, the habits write nothing, the favourites are empty. That
        is what keeps a machine without the daemon quiet instead of raising."""
        if not self.enabled:
            return None
        return open_ro(self.db_path)

    # ---------------- the shelf, as she sees it ----------------

    def shelf(self, stale_days=21):
        """{active:[...], cold:[...], finished_recent:[...], median_pace} from the DB."""
        con = self._con()
        if not con:
            return None
        try:
            now = datetime.datetime.now()
            per = {}
            for aid, ep, w in con.execute("SELECT anime_id,ep,watched_at FROM episodes ORDER BY watched_at"):
                per.setdefault(aid, []).append(datetime.datetime.fromisoformat(w))
            rows = con.execute("""SELECT a.anime_id,a.title,a.watched_episodes,COALESCE(d.api_num_episodes,a.num_episodes),
                d.avg_episode_seconds,a.updated_at,a.status,a.score FROM anime a LEFT JOIN anime_detail d ON d.anime_id=a.anime_id
                WHERE a.status=1""").fetchall()
            active, cold = [], []
            for aid, title, watched, total, secs, upd, st, sc in rows:
                ws = per.get(aid, [])
                last = ws[-1] if ws else (datetime.datetime.fromtimestamp(upd) if upd else None)
                days = (now - last).total_seconds() / 86400 if last else 999
                remaining = max(0, (total or 0) - (watched or 0)) if total else None
                # pace over the last 30 days of its own events
                pace = None
                if len(ws) >= 2:
                    recent = [w for w in ws if (ws[-1] - w).days <= 30]
                    if len(recent) >= 2:
                        span = max(1.0, (recent[-1] - recent[0]).total_seconds() / 86400)
                        pace = len(recent) / span
                item = {"anime_id": aid, "title": title, "watched": watched or 0, "total": total or 0,
                        "remaining": remaining, "days_since": days, "pace": pace,
                        "hours_left": (remaining or 0) * (secs or 1440) / 3600}
                (cold if days > stale_days else active).append(item)
            active.sort(key=lambda x: x["days_since"])
            cold.sort(key=lambda x: -x["days_since"])
            # finished in the last 7 days (completed with a recent last event)
            week_ago = (now - datetime.timedelta(days=7)).isoformat(timespec="minutes")
            fin = con.execute("""SELECT a.anime_id,a.title,a.score,MAX(e.watched_at) FROM anime a JOIN episodes e ON e.anime_id=a.anime_id
                WHERE a.status=2 GROUP BY a.anime_id HAVING MAX(e.watched_at)>=? ORDER BY MAX(e.watched_at) DESC""", (week_ago,)).fetchall()
            finished = [{"anime_id": a, "title": t, "score": s, "when": w[:10]} for a, t, s, w in fin]
            return {"active": active, "cold": cold, "finished_recent": finished}
        finally:
            con.close()

    _ANIME_WORDS = ("anime", "episode", " ep ", " eps", "watching", "watched", "rewatch", "season", "seiyuu", "mal ",
                    "myanimelist", "ova", "opening", " op ", " ed ", "studio", "binge", "finished")

    def anime_in_the_air(self, recent_messages, looked_up=None):
        """Only when anime is what they are talking about: his recent messages
        mention it, name a show he is watching, or the lookup just resolved one.
        Otherwise his list stays out of her head -- she does not carry his
        watchlist into every text."""
        if looked_up and "his history" in str(looked_up.get("source", "")):
            return True
        texts = " ".join((m.get("text") or "").lower() for m in (recent_messages or []))
        if not texts:
            return False
        if any(w in f" {texts} " for w in self._ANIME_WORDS):
            return True
        sh = self.shelf()
        if sh:
            for it in sh["active"] + sh["cold"]:
                for key in self._title_keys(it["title"]):
                    if key in texts:
                        return True
        return False

    @staticmethod
    def _title_keys(title):
        """The full title, its part before a colon, or any distinctive word of
        it ('example-show', 'patlabor', 'megami-sama'): people shorten."""
        import re
        stop = {"season", "second", "first", "third", "movie", "special", "final", "series", "chapter", "part"}
        t = (title or "").lower()
        keys = {t, t.split(":")[0].split(" (")[0].strip()}
        keys |= {w.strip("!?.") for w in re.findall(r"[a-z0-9\-!?.]+", t) if len(w.strip("!?.")) >= 6 and w.strip("!?.") not in stop}
        return {k for k in keys if len(k) >= 5}

    def mentioned(self, text):
        """Did this text of hers touch his list -- an anime word or a shelf
        title? Clears the pending weekly hint as said."""
        t = f" {(text or '').lower()} "
        if any(w in t for w in self._ANIME_WORDS):
            return True
        sh = self.shelf()
        for it in (sh["active"] + sh["cold"] + sh["finished_recent"]) if sh else []:
            for key in self._title_keys(it["title"]):
                if key in t:
                    return True
        return False

    def nag_line(self, ja=False):
        """The pending weekly hint, for the persona's him-block on every
        message she writes today. The share_hint path only ran when SHE
        started a message, and on 2026-08-29 the impulse said no all day
        while they were mid-conversation -- the week's look at his list was
        offered every tick and died unsaid. Saying it, or not, stays hers."""
        c = self.config.anime_sense
        if not c.nag_in_prompt:
            return ""
        p = self.store.get("anime_shelf_hint_pending")
        if not p or not p.get("hint"):
            return ""
        if int(p.get("shown", 0)) >= int(c.nag_shows_max):
            self.store.set("anime_shelf_hint_pending", None)
            logger.log(f"[anime] the shelf hint held the slot {c.nag_shows_max} times unsaid; let go for the week")
            return ""
        return p["hint"]

    def charge_shown(self):
        """The hint held the one slot she reads: that is a showing. Being
        offered and buried at line 39 was not, which is why the count moved
        here from nag_line."""
        p = self.store.get("anime_shelf_hint_pending")
        if p:
            p["shown"] = int(p.get("shown", 0)) + 1
            self.store.set("anime_shelf_hint_pending", p)

    def situation_line(self, ja=False):
        """One line for her situation: what he is in the middle of right now."""
        sh = self.shelf()
        if not sh or not sh["active"]:
            return ""
        parts = []
        for it in sh["active"][:3]:
            if ja:
                parts.append(f"{it['title']}（{it['watched']}/{it['total'] or '?'}"
                             + ("、最後に観たのは{:.0f}日前）".format(it["days_since"]) if it["days_since"] < 30 else "）"))
            else:
                parts.append(f"{it['title']} ({it['watched']}/{it['total'] or '?'}" + (", last ep {:.0f}d ago)".format(it["days_since"]) if it["days_since"] < 30 else ")"))
        s = ("いま彼が観ているアニメ: " if ja else "his anime right now: ") + "; ".join(parts)
        if sh["cold"]:
            s += (f"; ほかに{len(sh['cold'])}本、何週間も止まったまま" if ja else
                  f"; and {len(sh['cold'])} he has left hanging for weeks")
        return s

    # ---------------- the weekly shelf check ----------------

    def shelf_check_due(self, date_str):
        c = self.config.anime_sense
        if not c.enabled or not c.shelf_check_enabled:
            return False
        last = self.store.get("anime_shelf_check_date")
        if last == date_str:
            return False
        d = datetime.date.fromisoformat(date_str)
        if d.weekday() != c.shelf_check_weekday:
            return False
        try:
            if last and (d - datetime.date.fromisoformat(last)).days < c.shelf_check_min_days:
                return False
        except ValueError:
            pass
        return True

    def shelf_check(self, date_str):
        """What she would bring up this week, as a share_hint. Stored so the
        director and persona can see it for the day. Returns the hint or ''."""
        c = self.config.anime_sense
        sh = self.shelf(stale_days=c.stale_days)
        self.store.set("anime_shelf_check_date", date_str)
        if not sh:
            return ""
        bits = []
        # what he's close to finishing (the nag)
        close = [a for a in sh["active"] if a["remaining"] and a["remaining"] <= c.nag_close_eps]
        if close:
            a = close[0]
            bits.append(f"he is {a['remaining']} ep{'s' if a['remaining'] != 1 else ''} from finishing {a['title']} ({a['watched']}/{a['total']})")
        # what he left hanging (the real nag)
        if sh["cold"]:
            cold = sh["cold"][:c.nag_cold_max]
            bits.append("he left hanging: " + ", ".join(
                f"{x['title']} at {x['watched']}/{x['total'] or '?'} ({x['days_since']:.0f} days untouched" + (f", only {x['remaining']} left" if x['remaining'] and x['remaining'] <= 4 else "") + ")"
                for x in cold))
        # what he just finished (something to ask about)
        if sh["finished_recent"]:
            f = sh["finished_recent"][0]
            bits.append(f"he finished {f['title']} on {f['when']}" + (f" and gave it {f['score']}" if f["score"] else " and has not scored it yet"))
        # what's newly started
        fresh = [a for a in sh["active"] if a["watched"] <= 2 and a["days_since"] <= 7]
        if fresh:
            bits.append("he just started " + ", ".join(a["title"] for a in fresh[:2]))
        if not bits:
            return ""
        hint = sight.w(self.config, "anime_list_hint") + "; ".join(bits) + \
               ". the one he abandoned is the one to poke at; the one he finished is the one to ask about"
        rec = {"date": date_str, "hint": hint, "n_active": len(sh["active"]), "n_cold": len(sh["cold"])}
        hist = self.store.get("anime_shelf_checks", [])
        self.store.set("anime_shelf_checks", (hist + [rec])[-12:])
        logger.log(f"[anime] weekly shelf check: {len(sh['active'])} active, {len(sh['cold'])} cold, {len(sh['finished_recent'])} finished this week")
        return hint

    def _declared_favorites(self):
        """His explicit MAL favorites from the `favorites` table (tools/mal_history.py
        favorites), names family-given. {} if not pulled yet."""
        con = self._con()
        if not con:
            return {}
        try:
            if not con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='favorites'").fetchone():
                return {}
            out = {"anime": [], "characters": [], "people": []}
            for kind, name, extra in con.execute("SELECT kind,name,extra FROM favorites ORDER BY kind,position"):
                nm = name.replace(", ", " ") if "," in name else name   # 'Koga, Tomoe' -> 'Koga Tomoe'
                if kind == "anime":
                    out["anime"].append(nm)
                elif kind == "character":
                    out["characters"].append(f"{nm} ({extra[:30]})" if extra else nm)
                elif kind == "people":
                    out["people"].append(nm)
            return out
        except sqlite3.Error:
            return {}
        finally:
            con.close()

    def _seiyuu_affinity(self, con_path, top=6, min_shows=4):
        """Top seiyuu by affinity = log(hours) x score-lift x finish-rate, one
        show counted once per seiyuu (best role weight). Same maths as
        tools/mal_history.py `seiyuu`, kept small here."""
        import math
        from collections import defaultdict
        con = self._con()
        if not con:
            return []
        try:
            dur = {a: (s or 1440) for a, s in con.execute("SELECT anime_id,avg_episode_seconds FROM anime_detail")}
            hours = {a: n * dur.get(a, 1440) / 3600 for a, n in con.execute("SELECT anime_id,COUNT(*) FROM episodes GROUP BY anime_id")}
            his = {a: (st, sc) for a, st, sc in con.execute("SELECT anime_id,status,score FROM anime")}
            best = {}
            for aid, role, va, pid in con.execute("SELECT anime_id,role,jp_va,jp_va_id FROM anime_cast WHERE jp_va IS NOT NULL"):
                if aid not in his:
                    continue
                w = 1.0 if role == "Main" else 0.45
                k = (pid, va, aid)
                if k not in best or w > best[k]:
                    best[k] = w
        except sqlite3.Error:
            return []
        finally:
            con.close()
        agg = defaultdict(lambda: {"h": 0.0, "n": 0, "sc": [], "done": 0, "drop": 0})
        for (pid, va, aid), w in best.items():
            st, sc = his[aid]
            h = hours.get(aid, 0.0)
            if h <= 0 and st != 2:
                continue
            a = agg[va]
            a["h"] += h * w; a["n"] += 1
            if sc:
                a["sc"].append((sc, w))
            if st == 2:
                a["done"] += 1
            elif st == 4:
                a["drop"] += 1
        out = []
        for va, a in agg.items():
            if a["n"] < min_shows:
                continue
            sw = sum(w for _, w in a["sc"]) or 0
            avg = sum(s * w for s, w in a["sc"]) / sw if sw else 7.0
            n = a["done"] + a["drop"]
            fin = a["done"] / n if n else 0.6
            out.append((math.log1p(a["h"]) * (0.5 + (avg - 6.0) / 4.0) * (0.5 + fin), va))
        out.sort(reverse=True)
        return [va for _, va in out[:top]]

    # ---------------- his habits as facts ----------------

    def habits_due(self, date_str):
        c = self.config.anime_sense
        # `self.enabled` first: with no mirror there is nothing to write into
        # her facts about him, and without this the hook reported itself due on
        # every boot and re-tried a write that can only return 0.
        if not self.enabled or not c.enabled or not c.habits_enabled or not self.memory:
            return False
        last = self.store.get("anime_habits_date")
        if not last:
            return True
        try:
            return (datetime.date.fromisoformat(date_str) - datetime.date.fromisoformat(last)).days >= c.habits_every_days
        except ValueError:
            return True

    def habits(self, date_str):
        """Write what the analysis knows about how he watches into user_facts.
        Plain, sourced to 'his anime history'; a friend who has watched his list."""
        con = self._con()
        if not con:
            return 0
        try:
            from collections import defaultdict
            dur = {a: (s or 1440) for a, s in con.execute("SELECT anime_id,avg_episode_seconds FROM anime_detail")}
            ev = con.execute("SELECT anime_id,ep,watched_at FROM episodes ORDER BY watched_at").fetchall()
            if len(ev) < 50:
                return 0
            total_h = sum(dur.get(a, 1440) for a, _, _ in ev) / 3600
            first, last = ev[0][2][:10], ev[-1][2][:10]
            by_hod = defaultdict(float)
            wd = [0.0] * 7
            for a, _, w in ev:
                by_hod[int(w[11:13])] += dur.get(a, 1440)
                try:
                    wd[datetime.date.fromisoformat(w[:10]).weekday()] += dur.get(a, 1440)
                except ValueError:
                    pass
            peak = sorted(by_hod.items(), key=lambda kv: -kv[1])[:3]
            peak_hours = ", ".join(f"{h:02d}:00" for h, _ in sorted(peak))
            names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            top_day = names[max(range(7), key=lambda i: wd[i])]
            # last 90 days pace
            cutoff = (datetime.datetime.now() - datetime.timedelta(days=90)).isoformat(timespec="minutes")
            recent = [e for e in ev if e[2] >= cutoff]
            rh = sum(dur.get(a, 1440) for a, _, _ in recent) / 3600
            # genres by hours
            g_h = defaultdict(float)
            gmap = {}
            for a, g in con.execute("SELECT anime_id,api_genres FROM anime_detail"):
                try:
                    gmap[a] = json.loads(g or "[]")
                except Exception:
                    gmap[a] = []
            for a, _, w in ev:
                for g in gmap.get(a, []):
                    g_h[g] += dur.get(a, 1440)
            top_g = [g for g, _ in sorted(g_h.items(), key=lambda kv: -kv[1])[:5]]
            # pacing, per watch RUN: MAL logs rewatches unmarked, and without
            # splitting them a rewatched favorite reads as a 3-year burn
            from tools.mal_history import split_runs
            per = defaultdict(list)
            for a, e, w in ev:
                per[a].append((e, w))
            spans = []
            n_rewatched = 0
            rewatched = []
            for a, evs in per.items():
                runs = split_runs(evs)
                if len(runs) > 1:
                    n_rewatched += 1
                    rewatched.append((len(runs), a))
                for r in runs:
                    if len(r) >= 6:
                        d0 = datetime.datetime.fromisoformat(r[0][1]); d1 = datetime.datetime.fromisoformat(r[-1][1])
                        spans.append((d1 - d0).total_seconds() / 86400)
            spans.sort()
            rewatched_eg = ""
            try:
                top_rw = [a for _, a in sorted(rewatched, reverse=True)[:4]]
                tmap = dict(con.execute("SELECT anime_id, title FROM anime").fetchall()) if top_rw else {}
                names_rw = [str(tmap.get(a) or "").strip() for a in top_rw]
                names_rw = [n for n in names_rw if n]
                if names_rw:
                    rewatched_eg = "; " + ", ".join(names_rw) + " among them"
            except Exception:
                rewatched_eg = ""
            med = spans[len(spans) // 2] if spans else None
            # scores
            sc = con.execute("SELECT a.score,d.mal_mean FROM anime a JOIN anime_detail d ON d.anime_id=a.anime_id WHERE a.score>0 AND d.mal_mean IS NOT NULL").fetchall()
            tens = con.execute("SELECT title FROM anime WHERE score=10 ORDER BY updated_at DESC LIMIT 6").fetchall()
            n_watching = con.execute("SELECT COUNT(*) FROM anime WHERE status=1").fetchone()[0]
            n_dropped = con.execute("SELECT COUNT(*) FROM anime WHERE status=4").fetchone()[0]
            n_done = con.execute("SELECT COUNT(*) FROM anime WHERE status=2").fetchone()[0]
        finally:
            con.close()
        # the seiyuu he likes: hours x his scores x how often he finishes their shows
        fav_va = self._seiyuu_affinity(con_path=self.db_path, top=6)
        # his DECLARED favorites (MAL profile): the stronger signal, his own hand
        decl = self._declared_favorites()
        facts = [
            (f"His anime history: about {total_h:,.0f} hours of anime logged since {first[:4]}, roughly {rh:.0f} hours in the last three months.", 4),
            (f"His favorite seiyuu, by his own MAL favorites: {', '.join(decl['people'])}. He talks about seiyuu a lot and thinks of Japanese names family-given.", 5) if decl.get("people") else
            (f"The seiyuu he has clearly taken to, going by hours, scores and what he finishes: {', '.join(fav_va)}. He talks about seiyuu a lot and thinks of Japanese names family-given.", 4) if fav_va else None,
            (f"His favorite anime characters, by his own MAL favorites: {', '.join(decl['characters'])}.", 5) if decl.get("characters") else None,
            (f"His all-time favorite anime, by his own MAL favorites: {', '.join(decl['anime'])}.", 5) if decl.get("anime") else None,
            (f"Behaviour and taste differ for him: by hours the seiyuu he watches most are {', '.join(fav_va[:3])}, but he also keeps starting shows for {', '.join([p for p in decl['people'] if p not in fav_va][:2])} and dropping them -- a fan of the person more than the vehicle.", 3)
            if decl.get("people") and fav_va and any(p not in fav_va for p in decl["people"]) else None,
            (f"He watches anime mostly in the evening, {peak_hours} is his peak; {top_day} is his heaviest day.", 4),
            (f"By hours watched his anime leans {', '.join(top_g[:3])}" + (f" (then {', '.join(top_g[3:5])})" if len(top_g) > 3 else "") + ".", 4),
            (f"He is not a binger: a season takes him about {med:.0f} days, he leaves plenty unfinished ({n_watching} watching, {n_dropped} dropped, {n_done} completed) — and he REWATCHES what he loves ({n_rewatched} titles rewatched{rewatched_eg}).", 4) if med else None,
        ]
        if sc:
            import statistics
            diff = statistics.mean(s - m for s, m in sc)
            facts.append((f"He scores anime about {abs(diff):.1f} {'below' if diff < 0 else 'above'} the MAL average; his 10s include {', '.join(t[0] for t in tens[:4])}." if tens else f"He scores anime about {abs(diff):.1f} {'below' if diff < 0 else 'above'} the MAL average.", 3))
        n = 0
        for f in facts:
            if not f:
                continue
            r = self.memory.add_fact(f[0], f[1])
            n += 1
        self.store.set("anime_habits_date", date_str)
        logger.log(f"[anime] {n} habit fact(s) written from his history")
        return n
