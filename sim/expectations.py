"""Expectations of him: signed, checkable, with a due time and a source.

His ask (2026-08-26): everything that predicted him predicted one thing
(whether he answers this message, `foresight.py`) or described him (the
beliefs, the facts, the rhythm). Nothing held "he said he would watch it
tonight" as a thing that comes due, gets checked against the record, and
costs something when it does not happen -- his promises had no weight
while hers (`commitments.py`) had a stake and a settle. Nothing noticed
"he is always on the charts at this hour and today he is not". And the
`risk` foresight named was never scored.

One object, four sources, all settled by code off the record:

- `do`: he said he would do a thing (watch, read, send, call, tell, be
  back). The `expect_him` call names it, when it is due (his local time),
  how she could know (`by`: a message of his, the app, either) and the
  words that would show it, and which belief of hers it rests on. Kept
  when a message or a digest after the promise carries the words before
  the deadline (plus a grace); missed when the deadline passes.
- `around`: mirrored from `rhythm_said` (he said when he would be about);
  kept if he spoke or was at the machine inside the window, missed if not.
- what foresight said might land badly is foresight's own to score
  (`sim/foresight.py`, `score_risks`); it was mirrored here as rows once,
  and seventy-nine of eighty rows on a save were that mirror.
- `habit`: learned once a day at the compile from a week of digests
  (`habits_him`: what, hours of his day, words); each day the window is
  checked against the digests that covered it. Missed is a small event
  she can notice; kept is nothing, because expected.

Effects are code. Kept `do`: confirm the belief, a little relief. Missed
`do` / `around`: strain the belief, resentment toward him, tension, an
event, and the row is **raisable** -- a line in her situation block until
she brings it up (her own later message carries the words) or it ages
out. This is the one place his word is held to the record the way hers
is. Nothing here predicts what she hopes; it records what she was told and
what she has learned, and settles it. `/expect [now]`.
"""
import datetime
from sim import lang
from sim import chattext
import logger
from sim import sight


class Expectations:
    def __init__(self, config, llm, store, clock, state, model_of_him=None, sentiments=None, rhythm=None, receipts=None,
                 typesafe=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.model_of_him = model_of_him
        self.sentiments = sentiments
        self.rhythm = rhythm
        self.receipts = receipts
        # The hosted classifier (`typesafe.py`, `docs/system-one.md`): when her
        # config turns the `expect_him` and `habits_him` uses on, they supply
        # `found`, the confidence per commitment, and the confidence per habit.
        # The `what`/`quote`/`words`/`window` extraction stays the role's, so
        # these are chained calls made after the role returns.
        self.typesafe = typesafe

    def _commitments_typesafe(self, user, expectations):
        """(found, [confidence or None, ...]) for the commitments the role just
        extracted. found is `no`/`yes`/None."""
        ts = self.typesafe
        if ts is None or not ts.ready("expect_him"):
            return None, []
        use = ts.use("expect_him") or {}
        floor = float(use.get("threshold", 0.5))
        questions = {"found": {
            "type": "choice",
            "instructions": "Does his message contain anything that is a commitment or a stated "
                            "intention she could later hold him to -- he will watch, read or send a "
                            "thing, call, tell her something, be back by a time, do a thing "
                            "tomorrow? Not moods, not opinions, not `maybe`s with nothing attached.",
            "criteria": {"yes": "he committed to something", "no": "nothing of the kind"}}}
        for i, e in enumerate(expectations):
            questions["conf_%d" % i] = {
                "type": "score",
                "instructions": "Commitment: %s (his words: %s). How confident are you that this is "
                                "really a commitment and not a figure of speech?" % (
                                    str(e.get("what") or "")[:120], str(e.get("quote") or "")[:80]),
                "criteria": ["not at all", "unlikely", "maybe", "probable", "certain"]}
        answers = ts.ask("expect_him", {"his message and the calendar": user}, questions)
        if not answers:
            return None, []
        f, fconf = ts.choice(answers, "found")
        if fconf is None or fconf < floor:
            return None, []
        if f == "no":
            logger.log(f"[expect] typesafe: nothing he could be held to (conf {fconf:.2f})")
            return "no", []
        confs = []
        for i in range(len(expectations)):
            v, conf = ts.score(answers, "conf_%d" % i)
            if isinstance(v, (int, float)) and conf is not None and conf >= floor:
                confs.append(round(max(0.0, min(1.0, float(v) / 4.0)), 2))
            else:
                confs.append(None)
        logger.log(f"[expect] typesafe: {len(expectations)} commitment(s), "
                   + ", ".join("-" if c is None else "%.2f" % c for c in confs))
        return "yes", confs

    def _habit_conf_typesafe(self, user, habits):
        """One confidence per habit the role just learned, or None, on the same
        shape as above."""
        ts = self.typesafe
        if ts is None or not habits or not ts.ready("habits_him"):
            return None
        use = ts.use("habits_him") or {}
        floor = float(use.get("threshold", 0.5))
        questions = {}
        for i, h in enumerate(habits):
            questions["conf_%d" % i] = {
                "type": "score",
                "instructions": "Habit: %s (window %s, days %s). How confident can she be, from the "
                                "week of digests, that this is a real habit of his?" % (
                                    str(h.get("what") or "")[:100], h.get("hours"), h.get("days")),
                "criteria": ["very unsure", "doubtful", "possible", "likely", "solid"]}
        answers = ts.ask("habits_him", {"the week of digests and the habits she already expects": user}, questions)
        if not answers:
            return None
        out = []
        for i in range(len(habits)):
            v, conf = ts.score(answers, "conf_%d" % i)
            if isinstance(v, (int, float)) and conf is not None and conf >= floor:
                out.append(round(max(0.0, min(1.0, float(v) / 4.0)), 2))
            else:
                out.append(None)
        logger.log("[expect] habits typesafe: " + ", ".join("-" if c is None else "%.2f" % c for c in out))
        return out

    # ---------------- store ----------------

    def rows(self):
        return self.store.get("expectations", [])

    def _save(self, rows):
        self.store.set("expectations", rows[-self.config.expect.keep:])

    def _him(self):
        return self.state._him_key() or "him"

    def _his_local(self, ts):
        try:
            return self.clock.to_user(ts)
        except Exception:
            return datetime.datetime.fromtimestamp(ts)

    def _calendar_lines(self):
        now = self.clock.user_now()
        out = [f"HIS LOCAL TIME NOW: {now.strftime('%A %Y-%m-%d %H:%M')} (hers: {self.clock.now().strftime('%A %H:%M')})"]
        for i in range(0, 7):
            d = now.date() + datetime.timedelta(days=i)
            out.append(f"  {d.strftime('%A %Y-%m-%d')}" + (" (today)" if i == 0 else " (tomorrow)" if i == 1 else ""))
        return "\n".join(out)

    # ---------------- source 1: what he said ----------------

    def hear(self, text):
        c = self.config.expect
        if not c.enabled or not text or len(text) < c.min_chars:
            return []
        low = text.lower()
        if not any(w in low for w in c.trigger_words):
            return []
        beliefs = self.model_of_him.brief() if self.model_of_him else "(none)"
        msgs = self.store.recent_messages(8)
        chat = chattext.lines(msgs[:-1], chars=200, stamps=False) or "(nothing before this)"
        user = (f"{self._calendar_lines()}\n\nTHE CHAT JUST BEFORE:\n{chat}\n\nHIS MESSAGE NOW:\n{text[:1500]}\n\n"
                f"WHAT SHE HAS DECIDED ABOUT HIM (an expectation can rest on one of these, by id):\n{beliefs}\n")
        data, raw = self.llm.call_json("expect_him", [{"role": "system", "content": self.config.prompt_text("expect_him")},
                                                      {"role": "user", "content": user}])
        if not isinstance(data, dict) or not data.get("found"):
            return []
        # The classifier's reading of whether there is a commitment at all, and
        # a confidence per commitment the role extracted; the words stay the
        # role's.
        jfound, jconfs = self._commitments_typesafe(user, data.get("expectations") or [])
        if jfound == "no":
            return []
        now = self.clock.now_ts()
        rows = self.rows()
        added = []
        for i, f in enumerate((data.get("expectations") or [])[: c.max_per_message]):
            try:
                what = str(f.get("what", "")).strip()[:160]
                if not what:
                    continue
                conf = float(f.get("confidence", 0.6) or 0.6)
                if i < len(jconfs) and jconfs[i] is not None:
                    conf = jconfs[i]
                if conf < c.min_confidence:
                    continue
                due = None
                if f.get("due_in_minutes") not in (None, "", "null"):
                    due = now + float(f["due_in_minutes"]) * 60
                elif f.get("due_at"):
                    try:
                        tz = self.clock.user_now().tzinfo
                        due = datetime.datetime.strptime(str(f["due_at"])[:16], "%Y-%m-%d %H:%M").replace(tzinfo=tz).timestamp()
                    except Exception:
                        due = None
                if due is None:
                    continue
                if due - now > c.max_days_ahead * 86400 or due < now - 3600:
                    continue
                words = [str(w).strip().lower() for w in (f.get("words") or []) if str(w).strip()][:8]
                by = str(f.get("by", "any") or "any").lower()
                by = by if by in ("message", "app", "any") else "any"
                row = {"id": f"e{int(now)}{len(rows) + len(added)}", "ts": now, "kind": "do", "what": what,
                       "quote": str(f.get("quote", ""))[:200], "due_ts": due, "by": by, "words": words,
                       "belief": str(f.get("belief", "") or "")[:40], "confidence": round(conf, 2),
                       "state": "open", "raised": False}
                if any(o["kind"] == "do" and o["state"] == "open" and o["what"].lower() == what.lower() for o in rows):
                    continue
                rows.append(row)
                added.append(row)
                logger.log(f"[expect] he said: {what} -- due {self._his_local(due).strftime('%a %H:%M')} his time"
                           f" (by {by}, words {words[:4]}, rests on {row['belief'] or 'nothing'})")
            except Exception as e:
                logger.log(f"[expect] row dropped: {type(e).__name__}: {e}")
        if added:
            self._save(rows)
        return added

    # ---------------- source 2: rhythm_said, mirrored ----------------

    def _mirror_said(self, rows):
        c = self.config.expect
        seen = {r.get("said_ts") for r in rows if r["kind"] == "around"}
        added = 0
        for s in self.store.get("rhythm_said", []):
            if s.get("direction", 1) < 0 or s.get("said_ts") in seen:
                continue
            rows.append({"id": f"a{int(s['said_ts'])}", "ts": s["said_ts"], "said_ts": s["said_ts"], "kind": "around",
                         "what": "be around" + (f' ("{s.get("quote", "")[:60]}")' if s.get("quote") else ""),
                         "quote": s.get("quote", ""), "start_ts": s["start_ts"], "due_ts": s["end_ts"], "by": "any", "words": [],
                         "belief": c.around_belief, "confidence": s.get("confidence", 0.6), "state": "open", "raised": False})
            added += 1
        return added

    # ---------------- source 3: habits ----------------

    def learn_habits(self, days=None):
        """Once a day at the compile: what he does with his day, from a week
        of digests, as windows with words the digest would carry."""
        c = self.config.expect
        if not c.enabled or not c.habits_enabled:
            return []
        days = days or c.habits_days
        now = self.clock.now_ts()
        lines = []
        with self.store.lock:
            rows = self.store.conn.execute("SELECT ts, from_ts, to_ts, text FROM digests WHERE ts >= ? ORDER BY ts", (now - days * 86400,)).fetchall()
        for r in rows:
            a = self._his_local(float(r["from_ts"] or r["ts"]))
            b = self._his_local(float(r["to_ts"] or r["ts"]))
            lines.append(f"[{a.strftime('%a %H:%M')}-{b.strftime('%H:%M')} his time] {str(r['text'])[:700]}")
        if len(lines) < c.habits_min_digests:
            return self.store.get("habits_him", [])
        old = self.store.get("habits_him", [])
        user = (f"{self._calendar_lines()}\n\n{sight.w(self.config, 'expect_days_label')} (last {days} days, his local time):\n" + "\n".join(lines[-60:])
                + "\n\nHABITS SHE ALREADY EXPECTS (keep, adjust or drop; a habit with no evidence this week is dropped):\n"
                + ("\n".join(f"- {h['what']} {h['hours']} words {h['words']}" for h in old) or "(none)"))
        data, raw = self.llm.call_json("habits_him", [{"role": "system", "content": self.config.prompt_text("habits_him")},
                                                      {"role": "user", "content": user}])
        if not isinstance(data, dict):
            return old
        # The classifier's confidence per habit stands over the role's; the
        # window, `days` and `words` stay the role's.
        jconfs = self._habit_conf_typesafe(user, data.get("habits") or [])
        out = []
        for i, h in enumerate((data.get("habits") or [])[: c.habits_max]):
            try:
                hours = [int(h["hours"][0]) % 24, int(h["hours"][1]) % 24]
                words = [str(w).strip().lower() for w in (h.get("words") or []) if str(w).strip()][:8]
                if not words:
                    continue
                days_ = h.get("days") or "any"
                conf = float(h.get("confidence", 0.6) or 0.6)
                if jconfs and i < len(jconfs) and jconfs[i] is not None:
                    conf = jconfs[i]
                out.append({"what": str(h.get("what", "")).strip()[:120], "hours": hours, "days": days_, "words": words,
                            "confidence": round(conf, 2), "since": self.clock.date_str()})
            except Exception:
                continue
        self.store.set("habits_him", out)
        logger.log(f"[expect] his habits, from {len(lines)} digests: " + ("; ".join(f"{h['what']} ({h['hours'][0]:02d}-{h['hours'][1]:02d})" for h in out) or "none"))
        return out

    def _check_habits(self, rows):
        """Each habit whose window ended today (his day) is checked once
        against the digests that covered it."""
        c = self.config.expect
        habits = self.store.get("habits_him", [])
        if not habits:
            return 0
        now = self.clock.now_ts()
        his = self._his_local(now)
        done = self.store.get("habits_checked", {})
        today = his.strftime("%Y-%m-%d")
        n = 0
        for h in habits:
            key = f"{today}:{h['what'][:40]}"
            if key in done:
                continue
            days = h.get("days", "any")
            if days != "any" and isinstance(days, list) and his.weekday() not in [int(d) for d in days]:
                done[key] = "n/a"
                continue
            a, b = h["hours"]
            start = his.replace(hour=a, minute=0, second=0, microsecond=0)
            end = his.replace(hour=b, minute=0, second=0, microsecond=0)
            if b <= a:
                end += datetime.timedelta(days=1)
            if now < end.timestamp() + c.habit_grace_minutes * 60:
                continue
            with self.store.lock:
                cov = self.store.conn.execute("SELECT text FROM digests WHERE to_ts >= ? AND from_ts <= ?",
                                              (start.timestamp(), end.timestamp())).fetchall()
            if not cov:
                done[key] = "unclear"
                continue
            text = " ".join(str(r["text"]).lower() for r in cov)
            hit = any(w in text for w in h["words"])
            done[key] = "kept" if hit else "missed"
            n += 1
            if not hit:
                ev = f"he was not {h['what']} today ({a:02d}-{b:02d} his time), which he usually is"
                self.store.add_event(now, self.clock.date_str(), "expect", ev, 2)
                if "curiosity" in self.state.gauges:
                    self.state._warm("curiosity", c.habit_miss_curiosity, 80)
                logger.log(f"[expect] habit missed: {ev}")
        self.store.set("habits_checked", {k: v for k, v in done.items() if k.startswith(today)})
        return n

    # ---------------- settling ----------------

    def _his_messages_since(self, ts):
        with self.store.lock:
            return self.store.conn.execute("SELECT ts, text FROM messages WHERE role='user' AND ts > ? ORDER BY ts", (ts,)).fetchall()

    def _her_messages_since(self, ts):
        with self.store.lock:
            return self.store.conn.execute("SELECT ts, text FROM messages WHERE role='assistant' AND ts > ? ORDER BY ts", (ts,)).fetchall()

    def _digests_since(self, ts):
        with self.store.lock:
            return self.store.conn.execute("SELECT ts, text FROM digests WHERE ts > ? ORDER BY ts", (ts,)).fetchall()

    def _evidence(self, r, until):
        words = r.get("words") or []
        if r["by"] in ("message", "any"):
            for m in self._his_messages_since(r["ts"]):
                if m["ts"] > until:
                    break
                low = str(m["text"]).lower()
                if not words or any(w in low for w in words):
                    return f"his message at {self.clock.hm(m['ts'])}: {str(m['text'])[:60]}"
        if r["by"] in ("app", "any") and words:
            for d in self._digests_since(r["ts"]):
                if d["ts"] > until:
                    break
                if any(w in str(d["text"]).lower() for w in words):
                    return sight.w(self.config, "expect_by_app", hm=self.clock.hm(d['ts']))
        return ""

    def _around_evidence(self, r):
        for m in self._his_messages_since(r["start_ts"] - 600):
            if m["ts"] <= r["due_ts"] + 600:
                return f"he spoke at {self.clock.hm(m['ts'])}"
        try:
            if self.receipts and self.receipts.was_around_between(r["start_ts"], r["due_ts"]):
                return "he was at the machine"
        except Exception:
            pass
        return ""

    def tick(self):
        """Every loop pass: mirror new sources, settle what is due, notice
        her raising a missed one. Cheap; no model."""
        c = self.config.expect
        if not c.enabled:
            return
        rows = self.rows()
        changed = self._mirror_said(rows)
        now = self.clock.now_ts()
        for r in rows:
            if r["state"] != "open":
                # a missed one she brought up herself stops being raisable
                if r["state"] == "missed" and not r.get("raised") and r.get("words"):
                    for m in self._her_messages_since(r.get("settled_ts", now)):
                        if any(w in str(m["text"]).lower() for w in r["words"]):
                            r["raised"] = True
                            changed += 1
                            logger.log(f"[expect] she raised it: {r['what'][:60]}")
                            break
                continue
            if r["kind"] == "do":
                ev = self._evidence(r, r["due_ts"] + c.grace_minutes * 60)
                if ev:
                    self._settle(r, "kept", ev)
                    changed += 1
                elif now > r["due_ts"] + c.grace_minutes * 60:
                    self._settle(r, "missed", sight.w(self.config, "expect_missed"))
                    changed += 1
            elif r["kind"] == "around":
                ev = self._around_evidence(r)
                if ev and now >= r["start_ts"]:
                    self._settle(r, "kept", ev)
                    changed += 1
                elif now > r["due_ts"] + c.grace_minutes * 60:
                    self._settle(r, "missed", "he did not turn up in the window he named")
                    changed += 1
            elif r["kind"] == "risk":
                # foresight scores its own risk now; a row the old mirror
                # left open is closed, with no effect on her
                self._settle(r, "unclear", "scored by foresight itself now")
                changed += 1
        if changed:
            self._save(rows)
        try:
            self._check_habits(rows)
        except Exception as e:
            logger.log(f"[expect] habit check failed: {type(e).__name__}: {e}")

    def _settle(self, r, state, note):
        c = self.config.expect
        now = self.clock.now_ts()
        r["state"] = state
        r["settled_ts"] = now
        r["note"] = note[:160]
        him = self._him()
        moved = []
        try:
            if state == "kept":
                if r.get("belief") and self.model_of_him:
                    self.model_of_him.confirm(r["belief"], c.kept_confirm, f"he did what he said: {r['what'][:60]}")
                    moved.append(f"{r['belief']} confirmed")
                if "relief" in self.state.gauges:
                    self.state._warm("relief", c.kept_relief, 80)
            elif state == "missed":
                if r.get("belief") and self.model_of_him:
                    self.model_of_him.strain(r["belief"], c.missed_strain, f"he said he would and did not: {r['what'][:60]}")
                    moved.append(f"{r['belief']} strained")
                if self.sentiments:
                    self.sentiments.move(him, "resentment", c.missed_resentment, f"he said he would {r['what'][:40]}")
                rel = self.state.relationships.get(him)
                if isinstance(rel, dict):
                    rel["tension"] = max(0.0, min(100.0, float(rel.get("tension", 0)) + c.missed_tension))
                    moved.append(f"tension +{c.missed_tension}")
                due = self._his_local(r["due_ts"]).strftime("%a %H:%M")
                self.store.add_event(now, self.clock.date_str(), "expect",
                                     f"he said he would {r['what']} (by {due} his time) and has not", 3)
            self.state.save()
        except Exception as e:
            logger.log(f"[expect] effects failed: {type(e).__name__}: {e}")
        logger.log(f"[expect] {state}: {r['what'][:70]} -- {note[:80]}" + (f" ({', '.join(moved)})" if moved else ""))

    # ---------------- readers ----------------

    def _unmet_rows(self, rows=None):
        """Things he said he would do, did not, and she has not raised. This is
        the record, not the wording: whether her prompt line is something to DO
        is read from here rather than from the sentence, which is written in
        whichever language she is addressed in."""
        c = self.config.expect
        now = self.clock.now_ts()
        return [r for r in (rows if rows is not None else self.rows())
                if r["kind"] in ("do", "around") and r["state"] == "missed" and not r.get("raised")
                and now - r.get("settled_ts", now) < c.raise_for_hours * 3600]

    def has_unmet(self):
        return bool(self._unmet_rows())

    def situation_line(self, ja=False):
        """Her prompt: what she is expecting of him and what he owes her."""
        t = lang.pick(ja)
        c = self.config.expect
        now = self.clock.now_ts()
        bits = []
        # one read: a kv read is a fresh parse, and the unmet set is matched
        # by object id, so a second read never matched and the "did not"
        # line never rendered
        rows = self.rows()
        unmet = {id(r) for r in self._unmet_rows(rows)}
        for r in rows:
            if r["kind"] in ("do", "around") and r["state"] == "open" and r["due_ts"] - now < 36 * 3600:
                due = self._his_local(r["due_ts"])
                bits.append(t(f"he said he would {r['what']} (by about {due.strftime('%a %H:%M')} his time); you are expecting it",
                              f"彼は{r['what']}と言った（彼の時間で{due.strftime('%a %H:%M')}くらいまでに）。あなたはそれを待っている"))
            elif id(r) in unmet:
                due = self._his_local(r["due_ts"])
                bits.append(t(f"he said he would {r['what']} by {due.strftime('%a %H:%M')} his time and did not; you have not brought it up",
                              f"彼は彼の時間で{due.strftime('%a %H:%M')}までに{r['what']}と言って、しなかった。あなたはそれを持ち出していない"))
        habits = self.store.get("habits_him", [])
        if habits and getattr(self.config.situation_block, "habits_line", True):
            bits.append(t("his day, as you have it: ", "彼の一日の見当: ")
                        + "; ".join(t(f"{h['what']} ({h['hours'][0]:02d}-{h['hours'][1]:02d} his time)",
                                      f"{h['what']}（彼の時間で{h['hours'][0]:02d}-{h['hours'][1]:02d}）") for h in habits[:4]))
        checked = self.store.get("habits_checked", {})
        missed = [k.split(":", 1)[1] for k, v in checked.items() if v == "missed"]
        if missed:
            bits.append(t("today he was not: " + "; ".join(missed[:3]) + " -- unlike him",
                          "今日、彼がしなかったこと: " + "; ".join(missed[:3]) + " -- 彼らしくない"))
        if not bits:
            return ""
        return t("what you are expecting of him: ", "彼に対して待っていること: ") + " | ".join(bits[:5])

    def report(self):
        c = self.config.expect
        rows = self.rows()
        by = {}
        for r in rows:
            by.setdefault((r["kind"], r["state"]), 0)
            by[(r["kind"], r["state"])] += 1
        lines = [f"expectations of him: {len(rows)} on record; " + ", ".join(f"{k[0]} {k[1]} {v}" for k, v in sorted(by.items())) if rows else "expectations of him: none yet"]
        for r in rows[-12:]:
            due = self._his_local(r["due_ts"]).strftime("%m-%d %H:%M")
            lines.append(f"  [{r['kind']}] {r['state']:8s} {r['what'][:60]} due {due} his"
                         + (f"; rests on {r['belief']}" if r.get("belief") else "") + (f" -- {r['note']}" if r.get("note") else "")
                         + (" [raised]" if r.get("raised") else ""))
        habits = self.store.get("habits_him", [])
        lines.append("his habits: " + ("; ".join(f"{h['what']} {h['hours'][0]:02d}-{h['hours'][1]:02d} {h.get('days', 'any')} ({h['confidence']})" for h in habits) if habits else "none learned yet (at the compile, from a week of digests)"))
        checked = self.store.get("habits_checked", {})
        if checked:
            lines.append("today: " + ", ".join(f"{k.split(':', 1)[1][:30]}={v}" for k, v in checked.items()))
        sl = self.situation_line()
        if sl:
            lines.append("her prompt line: " + sl)
        return "\n".join(lines)
