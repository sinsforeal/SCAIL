# -*- coding: utf-8 -*-
"""What his newest message is, as one fan-out of typed questions.

`docs/system-one.md` item 2. The gates that decide whether she thinks about a
message at all -- does the state role read it, does it reach for a memory, does
it carry a promise or a question with weight -- are heuristics over flags
today. One call answers a dozen of them at once, because questions in one batch
cost no extra latency, and code reads the ones it needs.

Nothing here decides anything. It reports probabilities and code thresholds
them. A classifier that cannot answer returns None and every gate keeps the
reading it had; off, no call is made. Every answer is also kept on the save
(`inbound_signals`) so the questions can be calibrated against what actually
happened, which is what `docs/system-one.md` section 5 asks for.
"""

import logger

# The dozen the doc names, plus three that only this fork needs: she lives on
# his machine, so whether he is talking about it is a fact worth having.
QUESTIONS = (
    ("did_anything_happen",
     "Does `his_message` contain anything that should move her internal state -- "
     "an event, a change, news, a decision, or a question with weight?"),
    ("is_a_question",
     "Does `his_message` ask her something she is expected to answer?"),
    ("is_he_upset",
     "Does `his_message` carry anger, hurt or displeasure at her?"),
    ("is_affectionate",
     "Does `his_message` carry warmth or affection toward her?"),
    ("touches_a_promise",
     "Does `his_message` refer to something the two of them agreed or promised, "
     "or say that he will do something?"),
    ("reaches_for_a_memory",
     "Would answering `his_message` well need an earlier conversation or a fact "
     "she would have to remember?"),
    ("about_a_third_person",
     "Is `his_message` about somebody other than the two of them?"),
    ("asks_her_to_do_something",
     "Does `his_message` ask her to perform an action rather than to talk?"),
    ("is_time_sensitive",
     "Does `his_message` name a time, a deadline, or something happening today?"),
    ("is_greeting",
     "Is `his_message` a greeting or a nothing-message -- a hello, a check-in, "
     "a sticker?"),
    ("is_about_her",
     "Does `his_message` ask about her, her day, or how she is?"),
    ("is_about_his_machine",
     "Is `his_message` about his computer, a program, a file or a process?"),
)


class InboundSignals:
    """One fan-out per inbound message. Read-only: it answers, it never acts."""

    def __init__(self, config, typesafe=None, clock=None, store=None):
        self.config = config
        self.typesafe = typesafe
        self.clock = clock
        self.store = store
        self.last = None
        self.last_text = ""

    def ready(self):
        return self.typesafe is not None and self.typesafe.ready("inbound_signals")

    def read(self, text):
        """One call over his newest message. {question: probability}, or None.

        None means the use is off, the message is empty, or the classifier could
        not answer -- and then every gate keeps the reading it already had."""
        if not self.ready():
            return None
        msg = str(text or "").strip()[:2000]
        if not msg:
            return None
        questions = {qid: {"type": "noul", "instructions": ins} for qid, ins in QUESTIONS}
        answers = self.typesafe.ask("inbound_signals", {"his_message": msg}, questions)
        if not answers:
            return None
        out = {}
        for qid, _ins in QUESTIONS:
            v = self.typesafe.yes(answers, qid)
            if v is not None:
                out[qid] = round(float(v), 3)
        self.last = out
        self.last_text = msg
        self._keep(out, msg)
        top = sorted(out.items(), key=lambda kv: -kv[1])[:5]
        logger.log("[inbound] " + ", ".join("%s=%.2f" % kv for kv in top))
        return out

    def _keep(self, out, msg):
        """The answers, on the save, for calibration against what happened."""
        if self.store is None:
            return
        try:
            hist = list(self.store.get("inbound_signals", []) or [])
            hist.append({"ts": (self.clock.now_ts() if self.clock else 0.0),
                         "text": msg[:200], "sig": out})
            self.store.set("inbound_signals", hist[-200:])
        except Exception as e:
            logger.log(f"[inbound] not kept: {type(e).__name__}")

    def yes(self, qid, floor=0.5):
        """Whether the last fan-out said yes to one question, at a floor.

        A `noul` carries no confidence of its own -- its value IS the
        probability -- so the floor is applied to that, and the step is a
        deliberate one: a question whose wrong answer is a missed moment wants a
        low floor, one whose wrong answer is a false alarm wants a high one."""
        if not self.last:
            return False
        return float(self.last.get(qid, 0.0) or 0.0) >= float(floor)

    def floor(self, default=0.5):
        """This use's own threshold, which is where a `noul` is read."""
        use = self.typesafe.use("inbound_signals") if self.typesafe else None
        try:
            return float((use or {}).get("threshold", default))
        except (TypeError, ValueError):
            return float(default)
