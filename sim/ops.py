import re
"""The operator's view of the machine, as one JSON payload for TALKAPP.

His ask (2026-08-26): the snoops should be visible in the app -- what she
saw and when she last looked -- and in general more stats and data: her
looks at his phone-app, X (posts, likes, follows, the drift), model calls
(how many lately, by role), and the rest, under a separate menu. This
builds it; `channels/talkapp_bot.py` posts it with the state sync and the
hub serves it to the app's "ops" view. Read-only: nothing here moves her.
Commands from that view come back through `App.run_command` (the same
handler as Telegram's slash commands) and their output is posted to the
hub's ops log, never into her chat.
"""
import os
import time
from sensors import x_monitor as xm


def _ago(clock, ts):
    if not ts:
        return "never"
    s = max(0, clock.now_ts() - float(ts))
    if s < 90:
        return f"{int(s)}s ago"
    if s < 5400:
        return f"{int(s / 60)}m ago"
    if s < 172800:
        return f"{s / 3600:.1f}h ago"
    return f"{s / 86400:.1f}d ago"


class Ops:
    def __init__(self, app):
        self.app = app
        self.log = []          # last command results, newest last
        self.started = time.time()

    def note(self, cmd, text):
        self.log.append({"ts": time.time(), "cmd": cmd, "text": str(text)[:6000]})
        self.log = self.log[-40:]

    # ---------------- sections ----------------

    def _gauges(self):
        a = self.app
        st = a.state
        spec = a.config.state.gauges
        rows = []
        for k, v in spec.items():
            rows.append({"gauge": k, "value": round(float(st.gauges.get(k, 0)), 1), "baseline": v["baseline"],
                         "kind": v.get("kind", ""), "writer": "code" if not v.get("model_may_move", True) or v.get("kind") == "derived" else "model+code"})
        out = {"rows": rows, "tags": st.mood_tags()[:600], "register": st.register()[:200],
               "delay_factor": round(st.delay_factor(), 2), "compose_factor": round(st.compose_factor(), 2)}
        try:
            tgt = st.affection_target()
            if tgt is not None:
                out["affection_target"] = round(tgt, 1)
                out["affection_band"] = st.affection_band()
        except Exception:
            pass
        return out

    def _him(self):
        a = self.app
        st = a.state
        key = st._him_key() or "him"
        him = st.relationships.get(key, {}) or {}
        out = {"closeness": him.get("closeness"), "standing": him.get("standing"), "tension": him.get("tension")}
        try:
            out["sentiments"] = {k: round(a.sentiments.live(key, k), 1) for k in ("attachment", "resentment", "respect", "contempt")}
        except Exception:
            pass
        try:
            out["attachment_strategy"] = a.attachment.strategy() or "none"
            out["attachment_threat"] = round(float(a.attachment.threat(a.silent_hours())), 2) if hasattr(a.attachment, "threat") else None
        except Exception:
            pass
        try:
            r = a.ruptures.open_one()
            out["rupture"] = (r.get("what") or r.get("text") or "open")[:120] if r else ""
        except Exception:
            pass
        try:
            out["withholding"] = a.withholding.status_line()[:200] if hasattr(a.withholding, "status_line") else ""
            out["withhold_pressure"] = round(a.withholding.pressure(), 2)
        except Exception:
            pass
        try:
            st_r = a.receipts.status() if a.receipts else None
            out["his_side"] = a.receipts.brief(st_r)[:160] if st_r else ""
        except Exception:
            pass
        try:
            out["silent_hours"] = round(a.silent_hours(), 1)
            ok, why = a.impulse.check(st, a.director.current, a.silent_hours())
            out["impulse"] = f"{'would text' if ok else 'no'}: {why}"[:200]
        except Exception:
            pass
        out["unread_his"] = len(a.store.unread_user_messages())
        try:
            out["delivery_busy"] = bool(a.delivery.busy())
        except Exception:
            pass
        try:
            out["derived"] = a.derive.brief()[:300] if hasattr(a, "derive") and hasattr(a.derive, "brief") else ""
        except Exception:
            pass
        return out

    def _phone(self):
        """Her looks at the app about him: the digest is the only form his
        activity ever reaches her in.

        The digest goes up whole. It used to be cut at 900 characters here,
        which is shorter than most of them (the first character's run about
        1,200-2,900, the second character's up to 6,700), so the operator's
        view showed a sentence stopping mid-word and there was no way to read
        the rest of what she is holding. The panel that draws it scrolls and
        wraps, so the length costs nothing on screen."""
        a = self.app
        today = a.clock.date_str()
        digs = a.store.digests_for_date(today)
        last = a.store.recent_digests(1)
        live = a.store.get("phone_last_live") or {}
        return {"last_look": _ago(a.clock, a.store.get("phone_last_look_ts", 0)),
                "looks_today": len(digs),
                "last_digest": (last[-1]["text"] if last else ""),
                "last_digest_at": _ago(a.clock, last[-1]["ts"]) if last else "never",
                "live": (live.get("text") or "")[:200],
                "curiosity": round(float(a.state.gauges.get("curiosity", 0)), 1),
                "consumed_id": a.store.get("phone_last_consumed_id")}

    def _snoop(self):
        a = self.app
        if a.snoop is None:
            return {}
        today = a.clock.date_str()
        counts = a.store.get("snoop_counts", {}) or {}
        week = [d for d in counts if d >= a.clock.date_str(a.clock.now_ts() - 6 * 86400)]
        try:
            ok, why = a.snoop.eligible(a.state, a.director.current, a.phone)
        except Exception as e:
            ok, why = False, f"{type(e).__name__}"
        events = []
        with a.store.lock:
            rows = a.store.conn.execute("SELECT ts, text FROM events WHERE kind='snoop' ORDER BY ts DESC LIMIT 4").fetchall()
        for ts, text in rows:
            events.append({"at": a.clock.hm(ts), "date": a.clock.date_str(ts), "ago": _ago(a.clock, ts), "text": text[:700]})
        paths = a.store.get("vault_read_paths", []) or []
        c = a.config.vault_snoop
        return {"last": _ago(a.clock, a.store.get("snoop_last_ts", 0)),
                "today": counts.get(today, 0), "week": sum(counts.get(d, 0) for d in week),
                "eligible_now": f"{'yes' if ok else 'no'}: {why}"[:160],
                "notes_read": len(paths), "notes_last": [os.path.basename(p) for p in paths[-6:]],
                "downloads_seen": len(a.store.get("snoop_downloads_seen", []) or []),
                "gap_hours": getattr(c, "min_gap_hours", None),
                "seen": events}

    def _x(self):
        a = self.app
        if a.social is None:
            return {}
        sv = a.config.sensor_view
        today = a.clock.date_str()
        acts = [x for x in xm.her_actions(sv) if not x.get("dry_run")]
        day0 = a.clock.now_ts() - 86400
        def n(kind):
            return sum(1 for x in acts if x.get("kind") in (kind, kind + "_done") and x.get("at", 0) >= day0)
        posts = xm.her_posts(sv, limit=3)
        looks = a.store.get("x_look_counts", {}) or {}
        out = {"last_look": _ago(a.clock, a.social.last_look_ts) if a.social.last_look_ts else "never",
               "looks_today": looks.get(today, 0), "busy": a.social.busy(), "error": (a.social.error or "")[:160],
               "noticed": (a.social.last_noticed or "")[:400],
               "likes_24h": n("like"), "follows_24h": n("follow"), "unfollows_24h": n("unfollow"),
               "posts_24h": sum(1 for x in acts if x.get("kind") == "post" and x.get("at", 0) >= day0),
               "last_posts": [{"at": _ago(a.clock, p.get("at", 0)), "text": (p.get("target") or "")[:140]} for p in posts],
               "queue": len(a.store.get("x_action_queue", []) or []),
               "post_mode": a.posting.mode(),
               "japan": [j["text"] for j in (a.store.get("x_japan", []) or [])[-3:]]}
        try:
            out["drift"] = a.taste.drift()
        except Exception:
            pass
        try:
            out["taste_top"] = a.social.taste_brief(limit=6)[:500]
        except Exception:
            pass
        # the accounts themselves, and why: what she decided (with her reason)
        # and whether it was done; what the drift dropped; what it drops next
        try:
            decided = [x for x in acts if x.get("kind") in ("like", "follow", "unfollow", "repost")]
            done = {(x.get("kind", "").replace("_done", ""), str(x.get("target", "")).lower()) for x in acts if str(x.get("kind", "")).endswith("_done")}
            out["actions_recent"] = [{"at": _ago(a.clock, x.get("at", 0)), "kind": x.get("kind"), "target": str(x.get("target", ""))[:70],
                                      "why": str(x.get("why", ""))[:120], "done": (x.get("kind"), str(x.get("target", "")).lower()) in done,
                                      "drift": bool(x.get("drift"))} for x in decided[-14:]][::-1]
            verd = a.taste.verdicts() if getattr(a, "taste", None) else {}
            unf = [str(x.get("target", "")).lower() for x in acts if x.get("kind") == "unfollow_done"]
            out["dropped"] = [{"handle": h, "why": str((verd.get(h) or verd.get(h.lower()) or {}).get("why", ""))[:80]} for h in unf[-10:]][::-1]
            following = set()
            try:
                following = set(a.curation._following())
            except Exception:
                following = set()
            taste = a.store.get("x_taste", {}) or {}
            # the same protection the drift itself applies, so this list is
            # what will actually happen rather than what the judge wanted
            try:
                prot = a.curation._protected()
            except Exception:
                prot = {}
            nxt = [(v.get("at", 0), h, v.get("why", "")) for h, v in verd.items()
                   if v.get("verdict") == "drop" and (not following or h.lower() in following) and h.lower() not in unf
                   and h.lower() not in prot and (taste.get(h) or {}).get("like", 0) == 0]
            nxt.sort()
            out["drop_next"] = [{"handle": h, "why": str(w)[:80]} for _t, h, w in nxt[:5]]
            try:
                fol = (xm.load_following(sv) or {}).get("accounts", {}) or {}
                seen_l, hers = set(), []
                for h, v in fol.items():
                    if isinstance(v, dict) and v.get("added_by") == "her" and h.lower() not in seen_l:
                        seen_l.add(h.lower())
                        hers.append(h)
                out["hers_only"] = {"follows": hers[-12:], "n": len(hers)}
            except Exception:
                pass
            out["drop_rule"] = (f"the judge's `drop` verdict, oldest first, {a.config.curation.drift_unfollows_per_day} a day; "
                                f"an unfollow she asks for herself needs {a.config.curation.unfollow_min_dislikes} dislikes and no like; "
                                f"never an account he liked or followed, never one that follows the account back, "
                                f"never one that is private")
        except Exception as e:
            out["actions_error"] = f"{type(e).__name__}: {e}"
        return out

    def _watch(self):
        """Her shows, where she is in each, and what she thought when she
        watched (the `experience` role, events `her_thing`)."""
        a = self.app
        wl = getattr(a, "watchlist", None)
        rows = wl.all() if wl else []
        out = {"shows": [{"title": r.get("title"), "ja": r.get("ja"), "ep": r.get("ep"), "total": r.get("total"),
                          "own": bool(r.get("own")), "why": str(r.get("why", ""))[:160],
                          "last": _ago(a.clock, r.get("last_ts", 0)) if r.get("last_ts") else "never"} for r in rows]}
        try:
            due, why = wl.pick_due() if wl else (False, "")
            out["next_pick"] = f"{'due' if due else 'not yet'}: {why}"
        except Exception:
            pass
        grounded = set()
        try:
            with a.store.lock:
                recs = a.store.conn.execute("select title, ep, substr(source,1,60) from recaps order by fetched_at desc limit 8").fetchall()
            out["recaps"] = [f"{r[0]} ep {r[1]}: {r[2]}" for r in recs]
            grounded = {(str(r[0]), str(r[1])) for r in recs}
        except Exception:
            out["recaps"] = []
        try:
            with a.store.lock:
                ev = a.store.conn.execute("select ts, text from events where kind='her_thing' order by ts desc limit 8").fetchall()
            thoughts = []
            for ts, text in ev:
                text = str(text)
                m = re.match(r"^(.*?) ep (\d+) ", text)
                thoughts.append({"at": _ago(a.clock, ts), "text": text[:300],
                                 "grounded": bool(m and (m.group(1), m.group(2)) in grounded)})
            out["thoughts"] = thoughts
        except Exception:
            out["thoughts"] = []
        try:
            nxt = wl.current() if wl else None
            out["next"] = (f"{nxt['title']} ep {nxt.get('ep', 1)}" if nxt else "(list empty)")
        except Exception:
            pass
        return out

    def _mind(self):
        """What she is carrying that the chat does not show: promises on the
        record, the questions she is turning over, what she woke wanting."""
        a = self.app
        out = {}
        try:
            out["promises"] = [f"{r.get('date', '')}{(' ' + r['from_hm']) if r.get('from_hm') else ''} to {r.get('to_name', '?')}: {str(r.get('what', ''))[:70]}"
                               for r in sorted(a.commitments.open(), key=lambda x: str(x.get('date', '')))[:8]]
            done = [r for r in a.commitments.rows() if r.get("status") != "open"][-5:]
            out["settled"] = [f"{r.get('settled', '')} {r.get('status', '')}: {str(r.get('what', ''))[:55]}"
                              + (f" -- {str(r.get('why', ''))[:60]}" if r.get("why") else "") for r in done][::-1]
        except Exception:
            pass
        try:
            qs = a.wonder.rows()
            out["questions_open"] = [str(q.get("text", ""))[:130] for q in qs if q.get("state") == "open"][:6]
            out["questions_settled"] = [f"{(q.get('answer') or {}).get('verdict', q.get('state', ''))}: {str(q.get('text', ''))[:100]}"
                                        for q in qs if q.get("state") in ("answered", "faded")][-4:][::-1]
        except Exception:
            pass
        try:
            mi = a.store.get("morning_intent", {}) or {}
            if mi.get("text"):
                out["morning"] = f"{mi.get('date', '')}: {str(mi.get('text', ''))[:220]}"
        except Exception:
            pass
        try:
            out["goals"] = [str(g.get("what") or g.get("text") or "")[:90] for g in (a.goals.open() or [])[:6]]
        except Exception:
            pass
        return out

    def _checks(self):
        """What the readers say: the seams the day showed, the lines she
        never hears, the flags."""
        a = self.app
        out = {}
        try:
            seams = a.coherence.recent(2)
            out["seams"] = [f"{r.get('date')} s{r.get('severity')} {r.get('kind')} ({r.get('where', '')}): {str(r.get('what', ''))[:160]}"
                            for r in sorted(seams, key=lambda r: (-int(r.get("severity", 1)), r.get("date", "")))[:8]]
            out["seams_read"] = "never" if not a.coherence.rows() else _ago(a.clock, max(float(r.get("ts", 0)) for r in a.coherence.rows()))
        except Exception:
            pass
        try:
            from sim.attention import Attention
            tot = Attention.tally_totals(a.store.get("attention_tally", {}) or {}, 7, a.clock.date_str())
            never, n = [], 0
            for room, srcs in tot.items():
                for src, (off, adm, slot, cov) in srcs.items():
                    n += 1
                    if off - cov >= int(a.config.attention.unheard_min_offers) and adm == 0:
                        never.append(f"{src} ({'him' if room == 'him' else 'them'}: {off - cov} offers)")
            out["unheard"] = never
            out["tally_sources"] = n
        except Exception:
            pass
        try:
            out["flags"] = [f"{f.get('date')} {f.get('what')}" for f in (a.store.get("flags", []) or [])[-5:]]
        except Exception:
            pass
        try:
            rows = a.store.get("model_ab", []) or []
            out["ab"] = (f"{len(rows)} pro/flash pair(s); last: {rows[-1].get('role')} {_ago(a.clock, rows[-1].get('ts', 0))} (/ab)"
                         if rows else "none yet (the judges write one per pro call)")
        except Exception:
            pass
        try:
            today = a.clock.date_str()
            out["stamped_back"] = sum(1 for x in (a.store.get("cast_chat", []) or [])
                                      if x.get("date") == today and "stamped back" in str(x.get("gist", "")))
        except Exception:
            pass
        return out

    def _scenery(self):
        """Borrowed eyes: the base, the watchlist, what went out, the lore."""
        a = self.app
        if a.scenery is None:
            return {}
        sc = getattr(a, "scenery", None)
        if not sc:
            return {}
        rows = sc.rows()
        usable = [r for r in rows if not r.get("rejected") and not r.get("used_ts")]
        by = {}
        for r in usable:
            by[r["place_kind"]] = by.get(r["place_kind"], 0) + 1
        accts = sc.accounts()
        last_run = a.store.get("scenery_last_run_ts")
        sent = [r for r in rows if r.get("used_ts")]
        scene = a.director.current or {}
        kind = sc.place_kind_of(scene)
        try:
            pick, why = sc.pick(scene, a.weather.current(a.clock.now()) if getattr(a, "weather", None) else None)
        except Exception as e:
            pick, why = None, f"{type(e).__name__}: {e}"
        def row(r):
            return {"kind": r["place_kind"], "tod": r["time_of_day"], "season": r["season"], "weather": r["weather"], "q": r.get("quality"),
                    "author": r["author"], "url": r["url"], "caption": (r["caption"] or "")[:140], "img": os.path.basename(r["path"] or ""),
                    "rejected": r.get("rejected") or "", "sent": bool(r.get("used_ts")), "names": r.get("names") or "[]",
                    "region": r.get("region") or "", "event": r.get("event") or ""}
        # the review: what was kept and what was refused, each with its reason,
        # newest first. Reading the tally is not the same as looking at the
        # pictures -- a rule that is too tight looks fine as a number.
        refused = [r for r in rows if r.get("rejected")]
        tally = {}
        for r in refused:
            tally[r["rejected"]] = tally.get(r["rejected"], 0) + 1
        sendable = set(a.config.scenery.send_kinds or []) | {"food"}
        try:
            cover = sc.coverage()
            nq, nwhy, _nev = sc.next_query()
        except Exception as e:
            cover, nq, nwhy = [], "", f"{type(e).__name__}: {e}"
        return {"on_file": len(rows), "usable": len(usable), "sent": len(sent), "by_kind": by,
                "sendable_usable": sum(1 for r in usable if r["place_kind"] in sendable),
                "watchlist": [{"handle": h, "kind": v.get("kind", ""), "why": (v.get("why") or "")[:100], "posts": v.get("last_posts"),
                               "verdict": v.get("verdict", "")} for h, v in accts.items() if v.get("verdict") in ("follow", "place")],
                "judged": len(accts), "skipped": [{"handle": h, "why": (v.get("why") or "")[:90]} for h, v in accts.items() if v.get("verdict") == "skip"][-10:],
                "last_harvest": _ago(a.clock, last_run) if last_run else "never", "running": bool(getattr(sc, "running", False)),
                "sent_today": sc._sent_today(), "scene_kind": kind or "(not a place the base has)",
                "fits_now": (f"{pick['place_kind']} from @{pick['author']}: {pick['caption'][:90]}" if pick else f"nothing: {why}"),
                "next_search": f"{nq} -- {nwhy}",
                "events": [{"name": e["core"], "in_days": e["in_days"], "node": e["node"], "rows": len(sc.event_rows(e["name"]))}
                           for e in (sc.events_soon() or [])],
                "coverage": [{"kind": r["kind"], "route": r["on_route"], "scenes": r["scenes"], "rows": r["have"],
                              "bands": r["per_band"], "missing": r["missing"]} for r in cover],
                "rejections": tally,
                "kept_rows": [row(r) for r in rows if not r.get("rejected")][-12:][::-1],
                "refused_rows": [row(r) for r in refused[-12:]][::-1],
                "last_rows": [row(r) for r in rows[-8:]][::-1],
                "lore": {k: [{"date": x["date"], "caption": x["caption"][:100], "her": x.get("her_caption", "")[:80]} for x in v[-3:]] for k, v in sc.lore().items()}}

    def _eroge(self):
        """What he is reading in a visual novel: the game, since when, how
        many lines this session, and what she has of it."""
        a = self.app
        c = a.config.eroge
        if not c.enabled:
            return {}
        from sensors import eroge_monitor
        out = eroge_monitor.report(a.config)
        last = a.store.get("eroge_last", {}) or {}
        if last:
            out["digest"] = str(last.get("digest") or "")[:900]
            out["digest_at"] = _ago(a.clock, last.get("at", 0))
            out["digest_game"] = str(last.get("title") or "")
            out["read_from_id"] = last.get("first_id")
            out["read_to_id"] = last.get("last_id")
            out["digest_note"] = str(last.get("note") or "")
        vid = out.get("vndb_id")
        if vid and a.retrievals is not None:
            row = a.retrievals.get("vn_card", str(vid), "vndb")
            out["card"] = str((row or {}).get("text") or "")[:900]
        return out

    def _agenda(self):
        """What is coming, joined (sim/agenda.py): today and the days ahead,
        every dated thing with the store it came from. Read-only, like the
        rest of this file -- the join itself decides nothing."""
        return self.app.agenda.panel()

    def _models(self):
        try:
            return self.app.llm.summary()
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def _world(self):
        a = self.app
        s = a.director.current or {}
        today = a.clock.date_str()
        out = {"her_time": a.clock.both(), "scene": f"{s.get('hm', '')} {s.get('location', '')} / {s.get('activity', '')}"[:200],
               "with": s.get("with_who") or s.get("with") or "", "phone_access": s.get("phone_access"),
               "ticks_today": len(a.store.scenes_for_date(today)),
               "run_dir": os.path.basename(str(a.run_dir)) if getattr(a, "run_dir", None) else "",
               "pid": os.getpid(), "uptime_h": round((time.time() - self.started) / 3600, 1)}
        try:
            out["weather"] = a.weather.describe(a.clock.now())[:160]
        except Exception:
            pass
        try:
            m = a.care.measure()
            out["care"] = f"investment {m['investment']}; checking expected {m['checking_expected_per_day']} / actual {m['checking_actual_per_day']} a day (ratio {m['ratio']})"
        except Exception:
            pass
        try:
            out["family"] = a.family.now_line()
        except Exception:
            pass
        try:
            k = a.situation.constraints()
            j = k["journey"]
            out["where"] = (f"on the way {a.situation.name(j['from'])} -> {a.situation.name(j['to'])}, {k['minutes_left']} min left ({k['mode']})" if j
                            else f"{a.situation.name(k['node'])} ({k['mode']})") + f"; fatigue {k['fatigue']:.0f}; typing {k['can_type']}"
        except Exception:
            pass
        try:
            out["japan"] = [i.get("ja", "") for i in a.zeitgeist.items(limit=5)]
        except Exception:
            pass
        try:
            live = a.exchange.live()
            out["exchange_live"] = f"{live['who']} ({live['kind']}, {live['side']} next)" if live else ""
        except Exception:
            pass
        try:
            out["diary_today"] = bool(a.diary.wrote_tonight())
            out["reflections_today"] = (a.store.get("reflect_counts", {}) or {}).get(today, 0) + (a.store.get("reflect_cast_counts", {}) or {}).get(today, 0)
        except Exception:
            pass
        try:
            out["money"] = a.money.balance()
        except Exception:
            pass
        try:
            hz = a.hazards.status_line()[:160] if hasattr(a.hazards, "status_line") else ""
            out["hazards"] = hz
        except Exception:
            pass
        try:
            from sim.worldshare import measure
            m = measure(a.store, today)
            out["him_share_today"] = None if m["composite"] is None else round(m["composite"] * 100)
        except Exception:
            pass
        return out

    def _pick(self):
        """What she would have done with the phone, and how much of the day's
        allowance of asking is left. Logged only; nothing acted on."""
        return self.app.pick.ops()

    def payload(self):
        out = {"at": time.time()}
        for name, fn in (("world", self._world), ("gauges", self._gauges), ("him", self._him), ("phone", self._phone),
                         ("snoop", self._snoop), ("x", self._x), ("scenery", self._scenery), ("watch", self._watch),
                         ("mind", self._mind), ("checks", self._checks), ("models", self._models),
                         ("agenda", self._agenda), ("pick", self._pick),
                         ("eroge", self._eroge)):
            try:
                out[name] = fn()
            except Exception as e:
                out[name] = {"error": f"{type(e).__name__}: {e}"}
        out["log"] = self.log[-12:]
        return out
