import logger
from sim import chattext
from sim import lang
from sim import wiring
from sim.director import scene_brief

# Typed initiation. The impulse (pure function) says she wants to text; one
# call then says what the urge is (share / ask / complain / check_on / tease
# / continue) or that it was not enough ("nothing": she opens the chat and
# puts the phone down), so a first message is not always "look what
# happened". The kind and the line go to the persona as what is on her
# mind; the kind is logged and counted so the mix over a week can be read.


class Intent:
    WIRES = ('attachment', 'foresight', 'persona', 'ruptures', 'social', 'wonder',)
    KINDS = ("share", "ask", "complain", "check_on", "tease", "continue",
             "confront", "make_up", "nothing")

    def __init__(self, config, llm, store, clock, state, receipts=None, reflection=None, phone=None, typesafe=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.receipts = receipts
        self.reflection = reflection
        self.phone = phone
        # The hosted classifier (`typesafe.py`, `docs/system-one.md`): when her
        # config turns the `intent` use on, one `choice` over the nine kinds
        # decides the urge. The role is still called for the words it writes
        # (`about`, `test`, `question`), and Jev's kind stands over the role's
        # when it answers above the floor.
        self.typesafe = typesafe
        wiring.declare(self)

    def _kind_typesafe(self, user):
        """Jev's kind for this urge, or "" when it cannot answer. `about`,
        `test` and `question` are prose and stay the role's; only the label
        moves."""
        ts = self.typesafe
        if ts is None or not ts.ready("intent"):
            return ""
        use = ts.use("intent") or {}
        floor = float(use.get("threshold", 0.5))
        answers = ts.ask("intent", {"what she carries and the chat": user},
                         {"kind": {"type": "choice",
                                   "instructions": "What is the urge she is acting on right now?",
                                   "criteria": {k: k for k in self.KINDS}}})
        if not answers:
            return ""
        kind, conf = ts.choice(answers, "kind")
        if kind in self.KINDS and conf >= floor:
            logger.log(f"[intent] typesafe: {kind} (conf {conf:.2f})")
            return kind
        return ""

    def _his_machine_line(self):
        """What his machine says about him THIS MINUTE, or "" when nothing is
        measuring it.

        The receipt above it answers a different question -- has he opened
        what she sent -- and `unseen` is true both of a man asleep and of a man
        three feet from the keyboard with his phone in his pocket. Without
        this the role had his clock as a bare reading and nothing else, and
        wrote her "are you still awake?" to send at his Saturday
        mid-morning."""
        if self.phone is None:
            return ""
        try:
            where, mins = self.phone.his_side_now()
        except Exception:
            return ""
        if where == "at it":
            return ("he is at his machine right now"
                    + (f", {mins} min in the same window" if mins >= 1 else " this minute"))
        if where == "away":
            return f"he has not touched his machine for {mins} min"
        return ""

    def _carrying(self):
        """The feeling strong enough to be deciding this, named. `confront` and
        `make_up` have been valid kinds since this was written and nothing ever
        pointed at them, so the model reached for them roughly never."""
        c = self.config.intent
        g = self.state.gauges
        att = self.attachment
        if att and att.intent_line():
            return att.intent_line()
        for gauge, threshold, line in (
            ("shame", c.shame_from, "shame -- something happened that she cannot stand having been seen. She is not "
                                    "going to raise it and she may not want to be looked at at all, but she is also a "
                                    "girl who covers by acting normal at people; either is in character"),
            ("anger", c.anger_from, "anger, and mostly not at him -- somebody was unfair to her. `complain` is the "
                                    "usual shape; `confront` only if the thing was his"),
            ("guilt", c.guilt_from, "guilt about how she left it with him -- `make_up` is what this is for"),
            ("sadness", c.sadness_from, "the flat kind of low, which does not want a conversation so much as company"),
            ("pride", c.pride_from, "something that went right, which she wants him to know without announcing it"),
        ):
            if g.get(gauge, 0) >= threshold:
                return line
        return ""

    def _account_line(self):
        so = self.social
        if not so:
            return ""
        try:
            bits = [x for x in (so.his_likes_line(), so.her_actions_line(3)) if x]
        except Exception:
            return ""
        return " | ".join(bits)[:700]

    def decide(self, scene, silent_hours, share_hint=""):
        """Returns (kind, line) or ("nothing", why)."""
        if not self.config.intent.enabled:
            return ("share" if share_hint else "continue", share_hint)
        st = self.receipts.status() if self.receipts else None
        his_side = self.receipts.brief(st) if self.receipts else ""
        msgs = self.store.recent_messages(8)
        chat = chattext.lines(msgs, self.clock, chars=160) or "(nothing recent)"
        thought = self.reflection.inner_hint(about=self.state._him_key() or "him") if self.reflection else ""
        today_counts = self.store.get("intent_counts", {}).get(self.clock.date_str(), {})
        counts_line = ", ".join(f"{k} x{v}" for k, v in sorted(today_counts.items(), key=lambda x: -x[1])) if today_counts else "nothing yet"
        machine = self._his_machine_line()
        user = (
            f"TIME: {self.clock.both_daypart()}\nWHERE SHE IS: {scene_brief(scene)}\nHOW SHE FEELS: {self.state.mood_tags()}\n"
            f"ON HER MIND (director): {share_hint or '(nothing in particular)'}\n"
            f"HIS SIDE: {his_side or 'unknown'}; {self.state.felt_gap_text(silent_hours) or f'he has been quiet {silent_hours:.1f} h'}\n"
            + (f"HIS MACHINE, THIS MINUTE: {machine}\n" if machine else "")
            + (f"WHAT SHE THOUGHT ABOUT HIM TODAY (private): {thought}\n" if thought else "")
            + (f"WHAT SHE IS CARRYING: {self._carrying()}\n" if self._carrying() else "")
            + (f"WHAT SHE EXPECTS OF HIM RIGHT NOW (her own prediction, which may be wrong): {self.foresight.intent_line()}\n"
               if self.foresight and self.foresight.intent_line() else "")
            + (f"AND WHAT IS BROKEN: {self.ruptures.intent_line()}\n"
               if self.ruptures and self.ruptures.intent_line() else "")
            + (f"ON THE X ACCOUNT (his, becoming hers; any of this can be an `ask` -- 'why did you like that', 'i unfollowed the chart guy btw' -- or nothing): {self._account_line()}\n"
               if self._account_line() else "")
            + (f"QUESTIONS SHE HAS BEEN WANTING TO ASK HIM (if the urge is to ask one, name it in `question` by id; the wording will be hers): {self.wonder.intent_line()}\n"
               if self.wonder and self.wonder.intent_line() else "")
            + f"HOW SHE HAS REACHED OUT TODAY ALREADY: {counts_line} (do not keep repeating the same move; a girl who complained twice already is more likely to go quiet or shift than complain a third time)\n"
            + f"\nTHE CHAT LATELY:\n{chat}\n"
        )
        # What she has in front of her this minute, above the sections this
        # prompt names one by one (the director's hint, HIS SIDE, WHAT SHE IS
        # CARRYING, HIS MACHINE THIS MINUTE), which stay because the
        # instruction refers to them by name.
        her = self.persona.judge_view() if self.persona else ""
        if her:
            user = her + "\n\n" + user
        system = self.config.role_system("intent")
        data, raw = self.llm.call_json("intent", [{"role": "system", "content": system}, {"role": "user", "content": user}])
        kind = str((data or {}).get("kind", "") if isinstance(data, dict) else "").strip().lower()
        if kind not in self.KINDS:
            kind = "share" if share_hint else "continue"
        # The classifier's kind stands over the role's when the use is on: the
        # same question, answered with code's threshold instead of the role's.
        jkind = self._kind_typesafe(user)
        if jkind:
            kind = jkind
        about = str((data or {}).get("about", "") if isinstance(data, dict) else "").strip()[:120]
        why = str((data or {}).get("why", "") if isinstance(data, dict) else "")[:100]
        # a question of hers, by id: the send marks it asked and his answer
        # is judged against it
        self.last_question = ""
        qid = str((data or {}).get("question", "") if isinstance(data, dict) else "").strip()
        wd = self.wonder
        if qid and wd and kind not in ("nothing",) and wd.find(qid):
            self.last_question = qid
            q = wd.find(qid)
            # this line is put in front of HER, in her situation block, so the
            # words around the question are in the language she is addressed in
            t = lang.say(self.config)
            if not about:
                about = q["text"][:150]
            elif q["text"][:40].lower() not in about.lower():
                about = (about + t(" -- the question underneath: ", " -- その下にある問い: ")
                         + q["text"][:120])[:200]
        # under protest the message is a test, and the test is named so the
        # persona sends it as one and the episode records what she was
        # checking him for
        test = str((data or {}).get("test", "") if isinstance(data, dict) else "").strip()[:160]
        att = self.attachment
        if test and att and att.strategy() == "protest" and kind != "nothing":
            att.note_test(kind, test)
            about = ((about + " -- " if about else "")
                     + lang.say(self.config)("what you are really checking: ", "本当に確かめようとしていること: ")
                     + test)
        elif test:
            test = ""
        # the receipt is a fact and the line must not contradict it. At 06:00
        # on 2026-08-28 the prompt said `HIS SIDE: unseen (412 min since her
        # last message)` and the intent still came back with "or did you just
        # leave me on read", which the persona then quoted into his chat. The
        # line is an instruction to her, not her words, so a false one is
        # dropped and the kind stands: she still reaches out, in her own words.
        if about and str(his_side or "").strip().startswith("unseen"):
            low = about.lower()
            if any(k in low for k in ("on read", "read it", "read my", "seen it", "you saw")):
                logger.log(f"[intent] dropped a subject that claimed he read it while the "
                           f"receipt says unseen: {about[:80]}")
                about = ""
        counts = self.store.get("intent_counts", {})
        today = self.clock.date_str()
        day = counts.get(today, {})
        day[kind] = day.get(kind, 0) + 1
        counts[today] = day
        self.store.set("intent_counts", {k: v for k, v in counts.items() if k >= self._week_ago()})
        logger.log(f"[intent] {kind}: {about or '-'} ({why})")
        return kind, about

    def _week_ago(self):
        import datetime
        return (self.clock.now().date() - datetime.timedelta(days=7)).isoformat()

    @staticmethod
    def reason_line(kind, about, share_hint, config=None):
        """Why she is the one starting this, in the second person, for HER.

        It goes into her situation block and the words are the builder's, not
        a role's, so they are in the language she is addressed in. Reading her
        own Japanese situation on 2026-09-05 this was the one English clause
        in it: `you want to ask him something: ` in front of a question she
        had thought in Japanese. `config` is optional only so that a caller
        holding no config gets the control's bytes rather than a crash."""
        if kind == "nothing":
            return ""
        t = lang.say(config)
        verbs = {"share": t("you want to tell him something", "彼に伝えたいことがある"),
                 "ask": t("you want to ask him something", "彼に訊きたいことがある"),
                 "complain": t("you want to complain", "文句を言いたい"),
                 "check_on": t("you want to check on him", "彼の様子を見にいきたい"),
                 "tease": t("you feel like teasing him", "彼をからかいたい気分"),
                 "continue": t("you want to pick the conversation back up", "さっきの話の続きをしたい")}
        s = verbs.get(kind, t("you feel like texting him", "彼に送りたい気分"))
        if about:
            s += t(" -- the subject: ", "——話題: ") + about
        elif share_hint:
            s += f": {share_hint}"
        return s
