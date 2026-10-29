"""Questions she is curious about, and what his answers do to her picture.

His ask (2026-08-26): "she forms theories about me already, should be able
to test and confirm. comparison to herself as well." The beliefs
(`model_of_him.py`) were, by their own prompt text, "never tested" -- they
strained or confirmed only off what the app and the snoop turned up. She
never once asked him a thing to find out. And nothing held "is he like me
on this" as a question at all.

A question is an object: what she wants to know, in her own words to
herself; what kind (test_him: it would test one of her beliefs about him;
compare_self: whether he is like her on something she believes about
herself; understand: a thing she has seen and cannot place -- a habit, a
window title, a like); which belief it bears on and what a yes or a no
would do to it; a charge; and whether she would ask it straight.

Code decides when one forms (`due`: curiosity over its rest, or something
just seen -- a look, a snoop, a discovery -- a cooldown, a daily cap, a
cap on open questions). The `wonder` call decides what. The intent is
handed the open questions by id and may pick one when the urge is `ask`;
the persona puts it in her words; the send marks it asked. His next
message inside `answer_hours` is judged by `wonder_answer` (confirmed /
disconfirmed / dodged / unclear, and what she learned). Effects are code:
a test_him question confirms or strains the belief it bore on; a
compare_self question moves attachment (he is like her: closer; he is
not: a little distance) and can confirm or strain the self-belief it
bore on; dodged warms curiosity and leaves the question standing to be
asked again later; what she learned becomes a fact about him.

Readers: her situation block (the two she is turning over, unasked), the
intent (candidates), `/wonder [now]`.
"""
import logger
from sim import chattext
from sim import sight
from sim import bz
from sim.director import scene_brief


class Wonder:
    def __init__(self, config, llm, store, clock, state, model_of_him=None, model_of_her=None, memory=None, sentiments=None, typesafe=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.model_of_him = model_of_him
        self.model_of_her = model_of_her
        self.memory = memory
        self.sentiments = sentiments
        # The hosted classifier (`typesafe.py`, `docs/system-one.md`): when her
        # config turns the `wonder_answer` use on, one `choice` answers what
        # became of her unasked question. The role still writes `learned` and
        # `fact`; they are kept when its verdict agrees with the classifier.
        self.typesafe = typesafe

    # ---------------- store ----------------

    def rows(self):
        return self.store.get("questions", [])

    def _save(self, rows):
        self.store.set("questions", rows[-self.config.wonder.keep:])

    def _count(self):
        return int((self.store.get("wonder_counts", {}) or {}).get(self.clock.date_str(), 0))

    def _him(self):
        return self.state._him_key() or "him"

    def open(self):
        return [q for q in self.rows() if q["state"] == "open"]

    def seed(self, why):
        """Something just reached her (a look, a snoop, a discovery): the next
        pass may form a question about it without waiting on curiosity."""
        self.store.set("wonder_seed", {"ts": self.clock.now_ts(), "why": str(why)[:80]})

    # ---------------- when ----------------

    def due(self, scene=None):
        c = self.config.wonder
        if not c.enabled:
            return False, "off"
        if self._count() >= c.max_per_day:
            return False, "daily cap"
        if len(self.open()) >= c.max_open:
            return False, "enough open questions"
        now = self.clock.now_ts()
        if now - float(self.store.get("wonder_last_ts", 0) or 0) < c.cooldown_hours * 3600:
            return False, "cooldown"
        seed = self.store.get("wonder_seed", {}) or {}
        if seed and now - float(seed.get("ts", 0)) < 3 * 3600:
            return True, f"something just reached her: {seed.get('why', '')}"
        return self.pull()

    def pull(self):
        """What curiosity alone says: the last gate of `due`, and the
        sweep's reader for the gauge (`sim/sweep.py`)."""
        c = self.config.wonder
        base = float(self.config.state.gauges["curiosity"]["baseline"])
        cur = float(self.state.gauges.get("curiosity", base))
        if cur - base >= c.curiosity_over:
            return True, f"curiosity {cur:.0f} over its rest"
        return False, "nothing pulling"

    def maybe(self, scene=None, force=False):
        ok, why = self.due(scene)
        if not ok and not force:
            return []
        return self.run(scene, why if ok else "forced")

    # ---------------- what ----------------

    def run(self, scene=None, why=""):
        c = self.config.wonder
        now = self.clock.now_ts()
        today = self.clock.date_str()
        beliefs = self.model_of_him.brief() if self.model_of_him else "(none)"
        selfb = self.model_of_her.brief() if self.model_of_her else "(none)"
        digests = self.store.digests_for_date(today)[-3:]
        dig = "\n".join(f"[{self.clock.hm(d['ts'])}] {d['text'][:500]}" for d in digests) or sight.w(self.config, "digest_none_today")
        facts = self.store.user_facts()[-15:]
        habits = self.store.get("habits_him", [])
        hab = "; ".join(f"{h['what']} ({h['hours'][0]:02d}-{h['hours'][1]:02d} his time)" for h in habits) or "(none learned yet)"
        msgs = self.store.recent_messages(10)
        chat = chattext.lines(msgs, self.clock, chars=160) or "(nothing recent)"
        prev = self.rows()[-8:]
        prev_txt = "\n".join(f"- [{q['state']}] {q['text'][:120]}" for q in prev) or "(none)"
        user = (
            f"TIME: {self.clock.both()}\nWHERE SHE IS: {scene_brief(scene) if scene else '(unknown)'}\nHOW SHE FEELS: {self.state.mood_tags()}\n"
            f"WHY NOW: {why}\n\n"
            f"WHAT SHE HAS DECIDED ABOUT HIM (never tested; a question can test one, by id):\n{beliefs}\n\n"
            f"WHAT SHE BELIEVES ABOUT HERSELF (a question can ask whether he is like her on one, by id):\n{selfb}\n\n"
            f"{sight.w(self.config, 'digest_today_label')}\n{dig}\n\nHIS HABITS AS SHE KNOWS THEM: {hab}\n\n"
            f"WHAT SHE KNOWS ABOUT HIM (recent):\n" + "\n".join(f"- {f}" for f in facts) + "\n\n"
            f"THE CHAT LATELY:\n{chat}\n\n"
            f"QUESTIONS SHE ALREADY HAS (do not repeat; an answered one is settled):\n{prev_txt}\n"
        )
        system = self.config.role_system("wonder")
        data, raw = self.llm.call_json("wonder", [{"role": "system", "content": system}, {"role": "user", "content": user}])
        self.store.set("wonder_last_ts", now)
        self.store.set("wonder_seed", {})
        self.store.bump_today("wonder_counts", today)
        if not isinstance(data, dict):
            logger.log("[wonder] nothing came")
            return []
        rows = self.rows()
        added = []
        for q in (data.get("questions") or [])[: c.max_per_call]:
            try:
                text = str(q.get("text", "")).strip()[:220]
                if not text:
                    continue
                kind = str(q.get("kind", "understand") or "understand").strip().lower()
                if kind not in ("test_him", "compare_self", "understand"):
                    kind = "understand"
                row = {"id": f"q{int(now) % 100000}{len(rows) + len(added)}", "ts": now, "date": today, "text": text, "kind": kind,
                       "belief": str(q.get("belief", "") or "")[:40], "self_belief": str(q.get("self_belief", "") or "")[:40],
                       "if_yes": str(q.get("if_yes", "") or "")[:120], "if_no": str(q.get("if_no", "") or "")[:120],
                       "charge": max(0, min(100, int(float(q.get("charge", 50) or 50)))), "straight": bool(q.get("straight", True)),
                       "source": why[:80], "state": "open", "asked_ts": None, "asked_line": "", "answer": None}
                row.update({"reality": "inferred"} if bz.reality_on(self.config) else {}); rows.append(row)
                added.append(row)
            except Exception as e:
                logger.log(f"[wonder] question dropped: {type(e).__name__}: {e}")
        # The classifier labels the questions the role just wrote. This is a
        # chained judgement: the text stays the role's, only the `kind` moves,
        # and a question it cannot place keeps the role's own label.
        jkinds = self._classify_typesafe(user, added)
        if jkinds:
            for q, k in zip(added, jkinds):
                if k:
                    q["kind"] = k
        if added:
            self._save(rows)
            logger.log(f"[wonder] {len(added)} question(s) ({why}): " + " | ".join(f"[{q['id']}] {q['text'][:70]} ({q['kind']}" + (f", tests {q['belief']}" if q['belief'] else "") + ")" for q in added))
        else:
            logger.log(f"[wonder] nothing she wants to know right now ({why})")
        return added

    def _classify_typesafe(self, user, questions):
        """Jev's kind for each question the role just wrote, or None.

        The role writes the question text; only the label moves, so this is a
        chained call made after the role returns. A question Jev cannot place
        above the floor keeps the role's own kind."""
        ts = self.typesafe
        if ts is None or not questions or not ts.ready("wonder"):
            return None
        use = ts.use("wonder") or {}
        floor = float(use.get("threshold", 0.5))
        qs = {}
        for i, q in enumerate(questions):
            qs["kind_%d" % i] = {
                "type": "choice",
                "instructions": "Her question, as she thinks it: %s\n\nGiven the beliefs she has "
                                "decided about him, and what she believes about herself, in the "
                                "state: which kind is this question? `test_him` if an honest answer "
                                "would confirm or break one of her beliefs about HIM; `compare_self` "
                                "if it is really 'is he like me on this' against one of her beliefs "
                                "about HERSELF; `understand` if it is about a thing she has seen and "
                                "cannot place (a habit, a window, a like, a note)." % str(q.get("text", ""))[:280],
                "criteria": {"test_him": "it would test a belief about him",
                             "compare_self": "it is about whether he is like her",
                             "understand": "it is about a thing she cannot place"}}
        answers = ts.ask("wonder", {"what she has decided and what she has seen": user}, qs)
        if not answers:
            return None
        out = []
        for i, q in enumerate(questions):
            v, conf = ts.choice(answers, "kind_%d" % i)
            if v in ("test_him", "compare_self", "understand") and conf is not None and conf >= floor:
                out.append(v)
            else:
                out.append(None)
        logger.log("[wonder] typesafe: " + ", ".join(
            (k or "-") for k in out))
        return out

    # ---------------- asking ----------------

    def candidates(self, n=None):
        c = self.config.wonder
        now = self.clock.now_ts()
        out = []
        for q in self.rows():
            if q["state"] == "open" or (q["state"] == "asked" and q.get("answer") and q["answer"].get("verdict") == "dodged"
                                       and now - float(q.get("asked_ts") or 0) > c.reask_hours * 3600):
                out.append(q)
        out.sort(key=lambda q: -q["charge"])
        return out[: (n or c.candidates)]

    def intent_line(self):
        cands = self.candidates()
        if not cands:
            return ""
        return " / ".join(f"[{q['id']}] {q['text'][:110]}" + (" (she would only circle this one)" if not q.get("straight", True) else "") for q in cands)

    def find(self, qid):
        for q in self.rows():
            if q["id"] == qid:
                return q
        return None

    def note_asked(self, qid, line=""):
        rows = self.rows()
        for q in rows:
            if q["id"] == qid and q["state"] in ("open", "asked"):
                q["state"] = "asked"
                q["asked_ts"] = self.clock.now_ts()
                q["asked_line"] = str(line)[:200]
                q["answer"] = None
                self._save(rows)
                logger.log(f"[wonder] asked: {q['text'][:80]}")
                return q
        return None

    # ---------------- she put it to him herself ----------------

    @staticmethod
    def _run(a, b):
        """Longest run of consecutive content words the two texts share."""
        import re as _re
        wa = [w for w in _re.findall(r"[a-z']+", str(a).lower()) if len(w) >= 3]
        wb = [w for w in _re.findall(r"[a-z']+", str(b).lower()) if len(w) >= 3]
        best = 0
        for i in range(len(wa)):
            for j in range(len(wb)):
                k = 0
                while i + k < len(wa) and j + k < len(wb) and wa[i + k] == wb[j + k]:
                    k += 1
                best = max(best, k)
        return best

    def voiced(self, bubbles):
        """A reply of hers that says an open question in its own words marks
        it asked -- the self-start path did this through the intent; the
        reply path never did, so `does he ever wonder about me...` was
        asked at 03:23 on 2026-08-31 and stayed open, riding every reply."""
        c = self.config.wonder
        text = " ".join(bubbles or [])
        if not text.strip():
            return []
        out = []
        for q in self.rows():
            if q["state"] != "open":
                continue
            if self._run(q["text"], text) >= int(getattr(c, "voiced_min_words", 5) or 5):
                self.note_asked(q["id"], text[:200])
                logger.log(f"[wonder] she put it to him herself: {q['text'][:70]}")
                out.append(q["id"])
        return out

    def review(self, date_str):
        """At the compile: an open question he has answered on his own is
        settled from the day's chat, the way an asked one is settled from
        his next message; nothing judged open questions before this, and
        five sat open from 08-26 with two of them answered in the record.
        Past `open_max_age_days` a question fades: she stopped turning it
        over."""
        c = self.config.wonder
        if not c.enabled:
            return 0
        now = self.clock.now_ts()
        rows = self.rows()
        msgs = self.store.messages_for_date(date_str) or []
        his = [m for m in msgs if m.get("role") == "user"]
        if not his:
            return 0
        chat = chattext.lines(msgs[-40:], self.clock, chars=220)
        n, done = 0, 0
        for q in rows:
            if q["state"] != "open":
                continue
            age_h = (now - float(q.get("ts") or q.get("born_ts") or now)) / 3600
            if age_h > float(getattr(c, "open_max_age_days", 7) or 7) * 24:
                q["state"] = "faded"
                logger.log(f"[wonder] faded, never asked: {q['text'][:70]}")
                done += 1
                continue
            if age_h < float(getattr(c, "review_after_hours", 24) or 24):
                continue
            if n >= int(getattr(c, "review_max_per_compile", 6) or 6):
                break
            n += 1
            user = (f"THE QUESTION SHE HAD (to herself): {q['text']}\nKIND: {q.get('kind', '')}"
                    + (f"\nIT BEARS ON HER BELIEF ABOUT HIM: {q['belief']}" if q.get("belief") else "")
                    + (f"\nIT BEARS ON WHAT SHE BELIEVES OF HERSELF: {q['self_belief']}" if q.get("self_belief") else "")
                    + f"\nIF YES: {q.get('if_yes', '')}\nIF NO: {q.get('if_no', '')}\n"
                    f"HOW SHE PUT IT TO HIM: (she never asked it; the day's chat is what he said on his own)\n\n"
                    f"THE CHAT THAT DAY:\n{chat}\n\nHIS LATEST MESSAGE:\n{str(his[-1]['text'])[:1200]}\n")
            verdict, learned, fact = self._verdict(user)
            if verdict not in ("confirmed", "disconfirmed", "unclear"):
                continue           # dodged / not answered / anything else: it stays open
            q["answer"] = {"ts": now, "verdict": verdict, "learned": learned, "his": str(his[-1]["text"])[:160], "unasked": True}
            q["state"] = "answered"
            moved = self._apply(q, verdict, fact)
            done += 1
            logger.log(f"[wonder] {verdict}, on his own: {q['text'][:70]}" + (f" -- {learned[:80]}" if learned else "") + (f" ({moved})" if moved else ""))
        if done:
            self._save(rows)
        return done

    # ---------------- his answer ----------------

    def on_his_message(self, text):
        c = self.config.wonder
        now = self.clock.now_ts()
        rows = self.rows()
        asked = [q for q in rows if q["state"] == "asked" and q.get("asked_ts") and now - float(q["asked_ts"]) <= c.answer_hours * 3600
                 and not q.get("answer")]
        if not asked:
            return None
        q = max(asked, key=lambda r: r["asked_ts"])
        since = [m for m in self.store.recent_messages(12) if float(m["ts"]) >= float(q["asked_ts"]) - 60]
        chat = chattext.lines(since, self.clock, chars=220) or "(nothing)"
        user = (f"THE QUESTION SHE HAD (to herself): {q['text']}\nKIND: {q['kind']}"
                + (f"\nIT BEARS ON HER BELIEF ABOUT HIM: {q['belief']}" if q.get("belief") else "")
                + (f"\nIT BEARS ON WHAT SHE BELIEVES OF HERSELF: {q['self_belief']}" if q.get("self_belief") else "")
                + f"\nIF YES: {q.get('if_yes', '')}\nIF NO: {q.get('if_no', '')}\n"
                f"HOW SHE PUT IT TO HIM: {q.get('asked_line', '')}\n\nTHE CHAT SINCE SHE ASKED (his latest message last):\n{chat}\n\nHIS LATEST MESSAGE:\n{text[:1200]}\n")
        verdict, learned, fact = self._verdict(user)
        if verdict is None:
            return None
        if verdict not in ("confirmed", "disconfirmed", "dodged", "unclear", "not_answered"):
            verdict = "unclear"
        if verdict == "not_answered":
            # his message was about something else; the question stays asked
            # and the next message inside the window gets judged instead
            return None
        q["answer"] = {"ts": now, "verdict": verdict, "learned": learned, "his": text[:160]}
        q["state"] = "answered" if verdict in ("confirmed", "disconfirmed", "unclear") else "asked"
        moved = self._apply(q, verdict, fact)
        self._save(rows)
        logger.log(f"[wonder] {verdict}: {q['text'][:70]}" + (f" -- {learned[:80]}" if learned else "") + (f" ({moved})" if moved else ""))
        return q

    def _verdict(self, user):
        """(verdict, learned, fact) for one judgement of her unasked question.

        Jev chooses the verdict when it clears the floor. The role still
        supplies a learned sentence and fact when its verdict agrees, so
        enabling the classifier does not discard what she learned. `verdict`
        is None only when neither answered."""
        ts = self.typesafe
        picked = None
        if ts is not None and ts.ready("wonder_answer"):
            use = ts.use("wonder_answer") or {}
            floor = float(use.get("threshold", 0.5))
            options = ("confirmed", "disconfirmed", "dodged", "unclear", "not_answered")
            answers = ts.ask("wonder_answer", {"her question and his message": user},
                             {"verdict": {"type": "choice",
                                          "instructions": "Given her unasked question and what he said, what became of it?",
                                          "criteria": {o: o for o in options}}})
            if answers:
                v, conf = ts.choice(answers, "verdict")
                if v in options and conf >= floor:
                    logger.log(f"[wonder] typesafe: {v} (conf {conf:.2f})")
                    picked = v
        try:
            data, _raw = self.llm.call_json("wonder_answer", [
                {"role": "system", "content": self.config.prompt_text("wonder_answer")},
                {"role": "user", "content": user}])
        except Exception:
            return picked, "", ""
        if not isinstance(data, dict):
            return picked, "", ""
        role_verdict = str(data.get("verdict", "") or "").strip().lower()
        if picked and role_verdict != picked:
            return picked, "", ""
        return (picked or role_verdict,
                str(data.get("learned", "") or "").strip()[:200],
                str(data.get("fact", "") or "").strip()[:160])

    def _apply(self, q, verdict, fact):
        c = self.config.wonder
        him = self._him()
        w = q["charge"] / 100.0
        moved = []
        try:
            if q["kind"] == "test_him" and q.get("belief") and self.model_of_him:
                if verdict == "confirmed":
                    self.model_of_him.confirm(q["belief"], c.confirm_gain * (0.5 + w), f"she asked and he answered: {q['text'][:60]}")
                    moved.append(f"{q['belief']} confirmed")
                elif verdict == "disconfirmed":
                    self.model_of_him.strain(q["belief"], c.strain_gain * (0.5 + w), f"she asked and the answer did not fit: {q['text'][:60]}")
                    moved.append(f"{q['belief']} strained")
            elif q["kind"] == "compare_self":
                if verdict == "confirmed" and self.sentiments:
                    self.sentiments.move(him, "attachment", c.similar_attachment * (0.5 + w), "he is like her on this")
                    moved.append("attachment up: he is like her")
                    if q.get("self_belief") and self.model_of_her:
                        self.model_of_her.confirm(q["self_belief"], c.self_confirm_gain, f"he is the same: {q['text'][:60]}")
                elif verdict == "disconfirmed" and self.sentiments:
                    self.sentiments.move(him, "attachment", c.unlike_attachment * (0.5 + w), "he is not like her on this")
                    moved.append("a little distance: he is not like her")
            if verdict == "dodged":
                if "curiosity" in self.state.gauges:
                    self.state._warm("curiosity", c.dodged_curiosity, 85)
                q["charge"] = min(100, q["charge"] + c.dodged_charge)
                moved.append("dodged: curiosity up, still standing")
            if fact and self.memory and verdict in ("confirmed", "disconfirmed", "unclear"):
                if self.memory.add_fact(fact, 2) == "new":
                    moved.append("a new fact")
            self.state.save()
        except Exception as e:
            logger.log(f"[wonder] effects failed: {type(e).__name__}: {e}")
        return ", ".join(moved)

    # ---------------- readers ----------------

    def situation_line(self, ja=False):
        c = self.config.wonder
        opn = [q for q in self.rows() if q["state"] == "open"]
        opn.sort(key=lambda q: -q["charge"])
        if not opn:
            return ""
        head = ("彼について、自分の中で引っかかっていること（訊いてはいない）: " if ja else
                "things you have been wondering about him (to yourself, unasked): ")
        _lab = bz.reality_on(self.config)
        return head + " / ".join((bz.label_phrase(q["reality"], ja) + " " if _lab and q.get("reality") else "") + q["text"][:110] for q in opn[: c.in_prompt])

    def report(self):
        rows = self.rows()
        ok, why = self.due()
        lines = [f"questions about him: {len(rows)} on record, {len(self.open())} open, {self._count()}/{self.config.wonder.max_per_day} formed today; "
                 f"{'one is due' if ok else 'not now'} ({why})"]
        for q in rows[-12:]:
            a = q.get("answer") or {}
            lines.append(f"  [{q['id']}] {q['state']:8s} {q['kind']:12s} {q['text'][:80]}"
                         + (f" (tests {q['belief']})" if q.get("belief") else "") + (f" (vs {q['self_belief']})" if q.get("self_belief") else "")
                         + (f" -> {a.get('verdict')}: {a.get('learned', '')[:60]}" if a else ""))
        if not rows:
            lines.append("  (none yet; /wonder now forms some)")
        return "\n".join(lines)
