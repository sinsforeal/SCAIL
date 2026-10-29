"""What she expects him to do next, written down and then checked.

His brief (2026-08-26): she keeps facts, beliefs and the ick about him; a
higher-fidelity version keeps an explicit, updating predictive model used
for planning -- what is he likely to do next, what would land badly, what
his silences mean -- so reaction becomes limited foresight.

The pieces already existed as separate readers: the rhythm knows when he
is usually about and how long he takes, the state carries what he last
sounded like, the beliefs carry what she has decided he is, the charged
items carry what she cannot say. Nothing joined them into a prediction,
and nothing checked one. This does both.

**A prediction is made when she sends** (a reply or a self-started
message) and, while he is quiet, refreshed every few hours: one `foresee`
call with the rhythm, his last mood, her beliefs, the chat, what she just
sent, and her last few predictions WITH their outcomes -- so the model sees
where she was wrong. It returns the chance he answers, the window, the
tone she expects, what in what she sent may land badly, what his silence
would mean, and her plan if he does not. kv `foresight`, sixty kept.

**The outcome is written by the record**: his next message closes the
live prediction with the minutes it actually took and whether it was
inside the window; the compile closes anything older than
`stale_hours` as unanswered. `accuracy()` is her calibration over the
last twenty, and it goes back into the next call.

**Readers**: her situation block (what you expect; careful: ...), the
intent call (WHAT SHE EXPECTS OF HIM), the withholding call (what his
silence means to her), and the impulse (reaching into expected silence
costs `impulse_weight` x (1 - reply_p)). `/foresee`.
"""
import logger
from sim import wiring
from sim import lang
from sim import chattext


class Foresight:
    WIRES = ('persona',)
    P_ANCHORS = ("none", "low", "even", "likely", "certain")
    MIN_BANDS = ("under 5 min", "5 to 15 min", "15 to 30 min", "30 to 60 min",
                 "60 to 180 min", "over 180 min")
    MIN_MID = (2, 10, 22, 45, 120, 360)

    def __init__(self, config, llm, store, clock, state, rhythm=None, model_of_him=None, ick=None, receipts=None, typesafe=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.rhythm = rhythm
        self.model_of_him = model_of_him
        self.ick = ick
        self.receipts = receipts
        # The hosted classifier (`typesafe.py`, `docs/system-one.md`): when her
        # config turns the `foresee` use on, one batched call supplies the two
        # numbers (`reply_p`, `reply_minutes`) with code's threshold. The words
        # (`tone`, `risk`, `plan`) stay the role's, so the role is still called
        # and only the numbers are overridden.
        self.typesafe = typesafe
        wiring.declare(self)

    def _numbers_typesafe(self, user):
        """(reply_p 0-1, reply_minutes) from Jev, or None when it cannot answer
        above the use's floor. The band's representative minutes are code's."""
        ts = self.typesafe
        if ts is None or not ts.ready("foresee"):
            return None
        use = ts.use("foresee") or {}
        floor = float(use.get("threshold", 0.3))
        questions = {
            "reply_p": {"type": "score",
                        "instructions": "What is the chance he answers within the window?",
                        "criteria": list(self.P_ANCHORS)},
            "reply_minutes": {"type": "score",
                              "instructions": "How long a window would he answer in?",
                              "criteria": list(self.MIN_BANDS)},
        }
        answers = ts.ask("foresee", {"what she carries, the chat and his rhythm": user}, questions)
        if not answers:
            return None
        lvl, conf = ts.score(answers, "reply_p")
        if conf is None or conf < floor:
            return None
        try:
            p = max(0.0, min(1.0, float(lvl) / 4.0))
        except (TypeError, ValueError):
            return None
        mlvl, _ = ts.score(answers, "reply_minutes")
        try:
            idx = max(0, min(len(self.MIN_MID) - 1, int(round(float(mlvl)))))
            mins = self.MIN_MID[idx]
        except (TypeError, ValueError):
            mins = None
        logger.log(f"[foresee] typesafe: p={p:.2f} (conf {conf:.2f}), window {mins} min")
        return p, mins

    def rows(self):
        return self.store.get("foresight", [])

    def _save(self, rows):
        self.store.set("foresight", rows[-self.config.foresight.keep:])

    def live(self):
        """The newest prediction still waiting on him, if any."""
        for r in reversed(self.rows()):
            if r.get("outcome") is None:
                if self.clock.now_ts() - float(r["ts"]) <= self.config.foresight.stale_hours * 3600:
                    return r
                return None
        return None

    # ---------------- the call ----------------

    def predict(self, sent, kind="reply"):
        c = self.config.foresight
        if not c.enabled:
            return None
        now = self.clock.now_ts()
        # one live prediction at a time; a new send replaces the last
        rows = self.rows()
        for r in rows:
            if r.get("outcome") is None:
                r["outcome"] = {"kind": "superseded", "ts": now}
        rh = ""
        lat = None
        try:
            rh = self.rhythm.brief() if self.rhythm else ""
            lat = self.rhythm.usual_latency() if self.rhythm else None
            usual = self.rhythm.usual_now() if self.rhythm else 0.5
            pres = self.rhythm.presence() if self.rhythm else 0.0
        except Exception:
            usual, pres = 0.5, 0.0
        mood = self.state.his_mood_line() if hasattr(self.state, "his_mood_line") else ""
        beliefs = ""
        try:
            beliefs = self.model_of_him.prompt_text()[:1200] if self.model_of_him else ""
        except Exception:
            beliefs = ""
        charged = ""
        try:
            charged = self.ick.prompt_text()[:600] if self.ick else ""
        except Exception:
            charged = ""
        msgs = self.store.recent_messages(10)
        chat = chattext.lines(msgs, self.clock, chars=160) or "(nothing recent)"
        his_side = ""
        try:
            st = self.receipts.status() if self.receipts else None
            his_side = self.receipts.brief(st) if st else ""
        except Exception:
            his_side = ""
        prev = [r for r in rows if r.get("outcome")][-5:]
        prev_txt = "\n".join(
            f"- {self.clock.hm(r['ts'])} she {r.get('kind')}: expected answer p={r['pred'].get('reply_p')} within {r['pred'].get('reply_minutes')} min, tone '{r['pred'].get('tone', '')[:40]}' -> "
            + (f"he answered after {r['outcome'].get('minutes')} min" if r["outcome"].get("kind") == "answered" else
               "no answer" if r["outcome"].get("kind") == "unanswered" else "she sent again before he did")
            for r in prev) or "(none yet)"
        acc = self.accuracy()
        user = (
            f"TIME: {self.clock.both()}\n"
            f"HIS RHYTHM (learned): {rh or '(not learned yet)'}; how usual it is for him to be about right now: {usual:.2f}; presence at the phone now: {pres:.2f}"
            + (f"; he usually takes about {lat:.0f} min to answer at this hour" if lat else "") + "\n"
            f"HIS SIDE: {his_side or 'unknown'}\n"
            + (f"WHAT HE LAST SOUNDED LIKE: {mood}\n" if mood else "")
            + (f"WHAT SHE HAS DECIDED HE IS:\n{beliefs}\n" if beliefs else "")
            + (f"WHAT SHE IS HOLDING ABOUT HIM (charged, unsaid):\n{charged}\n" if charged else "")
            + f"THE CHAT LATELY:\n{chat}\n"
            + (f"WHAT SHE JUST SENT ({kind}):\n{sent}\n" if sent else "SHE HAS SENT NOTHING NEW; she is waiting on him.\n")
            + f"HER LAST PREDICTIONS AND WHAT HAPPENED (learn from these):\n{prev_txt}\n"
            + (f"HER CALIBRATION: {acc}\n" if acc else "")
        )
        # What she has in front of her this minute, the same situation and
        # carrying blocks the persona itself would be sent
        # (`Persona.judge_view`). A judge gets what she has; it does not get
        # her character sheet.
        her = self.persona.judge_view() if self.persona else ""
        if her:
            user = her + "\n\n" + user
        system = self.config.role_system("foresee")
        data, raw = self.llm.call_json("foresee", [{"role": "system", "content": system}, {"role": "user", "content": user}])
        if not isinstance(data, dict):
            logger.log("[foresee] nothing usable came back")
            return None
        try:
            p = max(0.0, min(1.0, float(data.get("reply_p", 0.5))))
        except (TypeError, ValueError):
            p = 0.5
        try:
            mins = int(data.get("reply_minutes")) if data.get("reply_minutes") not in (None, "", "null") else None
        except (TypeError, ValueError):
            mins = None
        # The two numbers stand over the role's when the classifier answers
        # above its floor; the words below stay the role's.
        got = self._numbers_typesafe(user)
        if got:
            p, mins = got
        # No field of this role is written in her voice. `silence_means` was, and
        # it landed in her situation block, so a judge was writing her own reading
        # of his silence for her to read back (his call, 2026-09-05). What his
        # quiet means to her is hers: the persona has her state and what she
        # carries, and says it in her own words or not at all.
        pred = {"reply_p": round(p, 2), "reply_minutes": mins, "tone": str(data.get("tone", ""))[:120],
                "risk": str(data.get("risk", "") or "")[:200],
                "plan": str(data.get("plan", ""))[:200]}
        rec = {"ts": now, "date": self.clock.date_str(), "hm": self.clock.hm(), "kind": kind, "sent": (sent or "")[:200], "pred": pred, "outcome": None}
        rows.append(rec)
        self._save(rows)
        logger.log(f"[foresee] ({kind}) answer p={pred['reply_p']}" + (f" within {mins} min" if mins else "") + f"; tone: {pred['tone'][:50]}"
                   + (f"; risk: {pred['risk'][:60]}" if pred["risk"] else "")
                   + (f"; then she would {pred['plan'][:60]}" if pred.get("plan") else ""))
        return rec

    # ---------------- the record answers ----------------

    def outcome(self, his_text):
        """His message closes the live prediction."""
        rows = self.rows()
        now = self.clock.now_ts()
        for r in reversed(rows):
            if r.get("outcome") is None:
                mins = round((now - float(r["ts"])) / 60)
                win = r["pred"].get("reply_minutes")
                inside = (win is not None and mins <= win * self.config.foresight.window_slack)
                r["outcome"] = {"kind": "answered", "ts": now, "minutes": mins, "inside": inside, "text": his_text[:120]}
                self._save(rows)
                # a reply she had all but written off, or one far outside the
                # window, is a small surprise; it reaches her register and
                # arousal, never the model's deltas
                try:
                    p = float(r["pred"].get("reply_p") or 0.5)
                    fc = self.config.foresight
                    if "surprise" in self.state.gauges and (p <= fc.surprise_reply_p_under or not inside):
                        self.state._warm("surprise", fc.surprise_bump * (2.0 if p <= fc.surprise_reply_p_under else 1.0), fc.surprise_soft_cap)
                except Exception:
                    pass
                logger.log(f"[foresee] he answered after {mins} min (expected p={r['pred'].get('reply_p')}" + (f", {win} min" if win else "") + f"): {'inside' if inside else 'outside'} the window")
                return r
            break
        return None

    def settle(self):
        """At the compile: anything still open past stale_hours is a silence."""
        rows = self.rows()
        now = self.clock.now_ts()
        n = 0
        for r in rows:
            if r.get("outcome") is None and now - float(r["ts"]) > self.config.foresight.stale_hours * 3600:
                r["outcome"] = {"kind": "unanswered", "ts": now}
                n += 1
        if n:
            self._save(rows)
        return n

    def score_risks(self):
        """What she was half braced for, checked against his next read.

        Every prediction names a risk -- what in what she sent may land
        badly -- and it is scored here: happened if his next mood read is
        cold inside `risk_hours`, passed if not, unclear if nothing came.
        Happened warms guilt and shame, passed warms relief. This was a
        mirror in the expectations (a row per prediction, settled there),
        and seventy-nine of eighty expectation rows on a save were that
        mirror; a prediction the mirror already settled takes its state
        from there, so nothing is scored twice."""
        c = self.config.foresight
        rows = self.rows()
        if not rows:
            return 0
        now = self.clock.now_ts()
        m = self.store.get("his_mood", {}) or {}
        mirrored = {r.get("pred_ts"): r.get("state") for r in (self.store.get("expectations", []) or [])
                    if r.get("kind") == "risk" and r.get("state") not in (None, "open")}
        changed = 0
        for r in rows:
            risk = (r.get("pred") or {}).get("risk", "")
            if not risk or r.get("risk_state"):
                continue
            if r["ts"] in mirrored:
                r["risk_state"], r["risk_note"] = mirrored[r["ts"]], "settled by the old mirror"
                changed += 1
                continue
            if float(m.get("ts", 0)) > float(r["ts"]):
                if float(m.get("valence", 0)) <= -1:
                    state, note = "happened", f"his next read was cold ({m.get('valence')})"
                else:
                    state, note = "passed", "his next message was not cold"
            elif now > float(r["ts"]) + c.risk_hours * 3600:
                state, note = "unclear", "nothing from him inside the window"
            else:
                continue
            r["risk_state"], r["risk_note"] = state, note[:160]
            changed += 1
            try:
                if state == "happened":
                    for g, amt in (("guilt", c.risk_guilt), ("shame", c.risk_shame)):
                        if g in self.state.gauges:
                            self.state._warm(g, amt, 80)
                elif state == "passed":
                    if "relief" in self.state.gauges:
                        self.state._warm("relief", c.risk_relief, 80)
                self.state.save()
            except Exception as e:
                logger.log(f"[foresee] risk effects failed: {type(e).__name__}: {e}")
            logger.log(f"[foresee] risk {state}: {risk[:70]} -- {note[:80]}")
        if changed:
            self._save(rows)
        return changed

    def accuracy(self, n=20):
        done = [r for r in self.rows() if r.get("outcome") and r["outcome"].get("kind") in ("answered", "unanswered")][-n:]
        if len(done) < 3:
            return ""
        ans = [r for r in done if r["outcome"]["kind"] == "answered"]
        mean_p = sum(r["pred"]["reply_p"] for r in done) / len(done)
        rate = len(ans) / len(done)
        inside = sum(1 for r in ans if r["outcome"].get("inside")) / max(1, len(ans))
        return (f"over her last {len(done)}: she expected an answer {mean_p:.0%} of the time and got one {rate:.0%}; "
                f"of the answers, {inside:.0%} came inside the window she expected")

    # ---------------- readers ----------------

    def situation_line(self, ja=False):
        t = lang.pick(ja)
        r = self.live()
        if not r:
            return ""
        p = r["pred"]
        age = (self.clock.now_ts() - float(r["ts"])) / 60
        bits = []
        if p.get("reply_minutes"):
            if age <= p["reply_minutes"]:
                bits.append(t(f"what you expect: {'he will probably' if p['reply_p'] >= 0.6 else 'he might' if p['reply_p'] >= 0.35 else 'he probably will not'} answer, "
                              f"{'within the hour' if p['reply_minutes'] <= 60 else 'in a few hours' if p['reply_minutes'] <= 240 else 'not for a while'}"
                              + (f", {p['tone']}" if p.get("tone") else ""),
                              f"あなたの見当: {'たぶん返ってくる' if p['reply_p'] >= 0.6 else '返ってくるかもしれない' if p['reply_p'] >= 0.35 else 'たぶん返ってこない'}、"
                              f"{'一時間以内に' if p['reply_minutes'] <= 60 else '数時間のうちに' if p['reply_minutes'] <= 240 else 'しばらく来ない'}"
                              + (f"、{p['tone']}" if p.get("tone") else "")))
            else:
                bits.append(t(f"he is past when you expected him ({int(age)} min)",
                              f"あなたが見ていた時間を彼は過ぎている（{int(age)}分）"))
        if p.get("risk"):
            bits.append(t(f"what you are half braced for: {p['risk']}", f"半分身構えていること: {p['risk']}"))
        return "; ".join(bits)

    def risk_text(self):
        """What the live prediction says may land badly, in her own terms.
        The attention gate reads it to keep the action it warns against out
        of the one imperative line (`Attention.veto_from_text`): on
        2026-09-04 the slot said raise the follow while this said raising it
        again is what she is braced for."""
        r = self.live()
        if not r:
            return ""
        return str((r.get("pred") or {}).get("risk", "") or "")

    def intent_line(self):
        r = self.live()
        if not r:
            return ""
        p = r["pred"]
        return (f"answer p={p['reply_p']}" + (f" within {p['reply_minutes']} min" if p.get("reply_minutes") else "")
                + (f"; her plan was: {p['plan']}" if p.get("plan") else ""))

    def impulse_bonus(self):
        r = self.live()
        if not r:
            return 0.0
        p = r["pred"]
        age = (self.clock.now_ts() - float(r["ts"])) / 60
        if p.get("reply_minutes") and age < p["reply_minutes"]:
            # still inside the window she gave him: reaching again costs
            return -self.config.foresight.impulse_weight * (1.0 - p["reply_p"])
        return 0.0

    def report(self):
        rows = self.rows()[-8:]
        out = [self.accuracy() or "no calibration yet (fewer than three settled predictions)"]
        live = self.live()
        out.append("live: " + (self.situation_line() or "none"))
        for r in rows:
            p, o = r["pred"], r.get("outcome") or {}
            out.append(f"  {r['date'][5:]} {r['hm']} {r['kind']}: p={p['reply_p']} {p.get('reply_minutes')}m '{p.get('tone', '')[:30]}'"
                       + (f" risk '{p['risk'][:40]}'" + (f" [{r['risk_state']}]" if r.get("risk_state") else "") if p.get("risk") else "")
                       + f" -> " + ({"answered": f"answered {o.get('minutes')}m ({'in' if o.get('inside') else 'out'})",
                                     "unanswered": "no answer", "superseded": "she sent again"}.get(o.get("kind"), "waiting")))
        return "\n".join(out)
