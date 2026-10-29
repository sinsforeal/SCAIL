"""The nudge: a second reader of everything she carries, who is not her.

The attention gate ranks lines by number and cannot judge timing or tone
-- it would slot the anime nag straight after he said something sad, or
let a flea-market plan outrank the four hours he was gone. This role says
one thing: which of the lines the machinery put in front of her she would
actually be caught by right now, and what would be off. Code places that
in the one slot she reads. It never writes her words, never adds a fact,
never sets her length.

**It carries her situation block and nothing else of hers** (his call).
Its system prompt is its own instruction file, through
`Config.role_system` with a `judge` row, so her sheet cannot reach it by
any path; its user message opens on the situation block as she is being
sent it this minute (`Persona.judge_situation`), and carries the
conversation, every line the gate let through this turn with its marks --
never one it suppressed as already said or as a repeat, and never an
action the weight floor or the foresight kept out of the slot -- and the
gate's own pick. It used to be handed her whole assembly, bible and
carrying block included, with "YOU ARE NOT HER" appended after it, which
is the arrangement a judge reads as its own identity.

Two modes. `live`: its `attend` replaces the gate's mechanical pick in the
slot when its confidence clears `min_confidence`. `shadow`: it runs, is
logged beside the gate's pick with an agreement estimate, and changes
nothing -- the way in, so the disagreement rate can be read before it is
trusted. `friends`: the same reader on her turns with her own people
(`exchange._her_turns`), where the prompt is smaller and had no arbiter
at all. kv `nudge_last`; `/nudge`.
"""
import re
from sim import wiring


import logger

_TOK = re.compile(r"[a-z][a-z'\-]{3,}|[぀-ヿ一-鿿]{2,}")


# double quotes, curly quotes, 「」, and a single-quoted span that stands on
# its own (space before, space or punctuation after) -- never the apostrophe
# in can't or he's, which the first version ate along with the words between
_QUOTED = re.compile(r"\"[^\"]{3,}\"|\u201c[^\u201d]{3,}\u201d|\u300c[^\u300d]{3,}\u300d"
                     r"|(?:(?<=\s)|^)[\'\u2018][^\'\u2019]{3,}[\'\u2019](?=[\s.,;:!?)]|$)")


def _notes(text, limit):
    """What the nudge wrote, with anything she could send taken out: a
    quoted span is a line offered to her, and on 2026-08-31 'needed
    something soft right now' went to him in her voice word for word."""
    t = _QUOTED.sub("", str(text or ""))
    t = re.sub(r"\s+", " ", t).replace(" ,", ",").replace(" .", ".").strip(" -,;")
    return t[:limit]


def _agree(a, b):
    ta, tb = set(_TOK.findall(str(a).lower())), set(_TOK.findall(str(b).lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(min(len(ta), len(tb)))


class Nudge:
    WIRES = ('state',)
    def __init__(self, config, llm, store, clock):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.last = {}
        self.state = None       # wired by the App: the gauge it reads
        wiring.declare(self)

    def level(self):
        try:
            return float((self.state.gauges or {}).get("unsaid", 0)) if self.state else 0.0
        except Exception:
            return 0.0

    def due(self, channel="him"):
        """Does it fire now? `unsaid` at or over `unsaid_min`, off the gap.
        With `fire_on_unsaid` off it fires on every call, as it first did."""
        c = self.config.nudge
        if not self.enabled(channel):
            return False, 0.0
        if not getattr(c, "fire_on_unsaid", True):
            return True, self.level()
        lv = self.level()
        if lv < float(c.unsaid_min):
            return False, lv
        last = float(self.store.get("nudge_fired_ts", 0) or 0)
        if self.clock.now_ts() - last < float(c.min_gap_minutes) * 60:
            return False, lv
        return True, lv

    def carried(self, n):
        """Things she carries warm `unsaid` while they wait -- the nag, a
        post to show him, a promise due. Called once per reply to him with
        the count of action lines in front of her."""
        c = self.config.nudge
        if n <= 0 or not self.state or not getattr(c, "fire_on_unsaid", True):
            return
        try:
            self.state._warm("unsaid", float(c.unsaid_per_carried) * n, float(c.unsaid_soft_cap))
        except Exception as e:
            logger.log(f"[nudge] carried warm failed: {type(e).__name__}: {e}")

    def released(self):
        """It came out: the gauge settles toward rest, never past it."""
        c = self.config.nudge
        self.store.set("nudge_fired_ts", self.clock.now_ts())
        if self.state and getattr(c, "fire_on_unsaid", True):
            try:
                self.state._settle("unsaid", float(c.unsaid_relief))
                self.state.save()
            except Exception as e:
                logger.log(f"[nudge] release failed: {type(e).__name__}: {e}")

    @staticmethod
    def _tag(value):
        """A source tag as the answer may have written it: the brackets, a
        trailing mark and any words after it taken off."""
        t = str(value or "").strip().strip("[]").lower()[:40]
        return t.split(" ")[0].split("\u00b7")[0].strip()

    def _offered(self, value, offered):
        """The line the answer named, exactly as she was offered it.

        Asked what she is caught by in its own words, this role composed a
        sentence about her and code put it in the one slot she reads, so a
        role with no character sheet was writing what was on her mind. It
        picks now, and a tag naming nothing leaves the gate's line."""
        tag = self._tag(value)
        if not tag:
            return ""
        line = str((offered or {}).get(tag, "") or "")
        if not line:
            logger.log(f"[nudge] it named [{tag}], which is not a line it was offered; nothing attended")
        return line[: int(self.config.nudge.max_chars)]

    def enabled(self, channel="him"):
        c = self.config.nudge
        if not c.enabled or c.mode == "off":
            return False
        if channel == "friend" and not c.friends:
            return False
        return True

    def run(self, situation, history, candidates_text, gate_pick, channel="him", who="", allowed=None, level=None,
            offered=None):
        """Returns the text for the slot, or '' to leave the gate's pick.
        `situation` is her situation block, headed, as she is being sent it
        this minute and with nothing else of hers in it
        (`Persona.judge_situation`); `history` the exact messages;
        `candidates_text` everything the machinery put in front of her this
        turn; `gate_pick` the mechanical slot text; `offered` those same
        candidates as {tag: the line}, which the answer's tag resolves against."""
        c = self.config.nudge
        if not self.enabled(channel):
            return ""
        # its own instruction and nothing else: the stance table has it as a
        # judge, and `role_system` refuses to append a sheet to one
        framing = self.config.role_system("nudge")
        lv = self.level() if level is None else float(level)
        pressure = ""
        if getattr(c, "fire_on_unsaid", True):
            pressure = (f"THE UNSAID IS AT {lv:.0f}/100 (rest is {int(self.state._baseline('unsaid')) if self.state else 25}). She has been going along -- "
                        "answering in the same shape, holding things -- and this is the message where it stops. "
                        + ("What she carries about HIM (the anime nag, a post to show him) is not for this room; here it is the push-back, or what belongs to this person.\n"
                           if channel == "friend" else "One thing comes out: a carried thing, or the pattern she has been letting slide, pushed back on.\n"))
        ask = ((situation + "\n\n" if str(situation or "").strip() else "")
               + pressure
               + "EVERYTHING THE MACHINERY PUT IN FRONT OF HER THIS TURN (* = it is in her block; the rest is a thing she carries and has not said):\n"
               + (candidates_text or "(nothing beyond the conversation)")
               + f"\n\nTHE GATE'S OWN PICK FOR THE ONE SLOT: {gate_pick or '(none)'}\n\n"
               + (f"THIS IS HER TURN WITH {who}, NOT WITH HIM. You are not writing that turn: the turns/gist schema "
                  f"under HOW THIS CALL WORKS is hers; yours is the attend/avoid one below.\n" if channel == "friend" else "")
               + "Now: what is she actually caught by, and what would be off? JSON only.")
        msgs = [{"role": "system", "content": framing}] + list(history or [])
        if msgs[-1]["role"] == "user":
            msgs[-1] = {"role": "user", "content": msgs[-1]["content"] + "\n\n" + ask}
        else:
            msgs.append({"role": "user", "content": ask})
        data, _raw = self.llm.call_json("nudge", msgs)
        if not isinstance(data, dict) or not (str(data.get("attend_source", "") or "").strip() or str(data.get("do", "") or "").strip()):
            why = "it answered as her (a turns list)" if isinstance(data, dict) and "turns" in data else "nothing came back"
            logger.log(f"[nudge] {why}; the gate's pick stands")
            return ""
        attend = self._offered(data.get("attend_source", ""), offered)
        do = _notes(data.get("do", ""), int(c.max_chars))
        heavy = bool(data.get("needs_all_of_her", False))
        if heavy and do:
            logger.log(f"[nudge] the message needs all of her; its decision to do a thing ({do[:60]}) is dropped")
            do = ""
        do_src = self._tag(data.get("do_source", "")) if do else ""
        # a thing to do is a carried action; a fact line is what she knows.
        # On 2026-08-31 it named `anime_list` (his shelf, in her head because
        # anime was the topic) and she restated the numbers she had sent two
        # minutes before
        if do and allowed is not None and do_src not in allowed:
            logger.log(f"[nudge] its decision names [{do_src or '?'}], which is not a thing she carries; dropped ({do[:60]})")
            do, do_src = "", ""
        avoid = [str(a)[:120] for a in (data.get("avoid") or []) if str(a).strip()][:3]
        try:
            conf = max(0.0, min(1.0, float(data.get("confidence", 0) or 0)))
        except (TypeError, ValueError):
            conf = 0.0
        why = str(data.get("why", ""))[:160]
        agree = _agree(attend, gate_pick) if gate_pick else 0.0
        rec = {"ts": self.clock.now_ts(), "channel": channel, "who": who, "attend": attend, "avoid": avoid,
               "do": do, "do_source": do_src, "heavy": heavy,
               "confidence": conf, "why": why, "gate": str(gate_pick or "")[:200], "agree": round(agree, 2), "mode": c.mode}
        self.last = rec
        self.store.set("nudge_last", rec)
        hist = self.store.get("nudge_log", []) or []
        self.store.set("nudge_log", (hist + [rec])[-60:])
        logger.log(f"[nudge] {c.mode} ({channel}{', ' + who if who else ''}) conf {conf:.2f} agree {agree:.2f}"
                   + (f" DO[{do_src or '?'}]: {do[:110]}" if do else (" do: none (needs all of her)" if heavy else " do: none"))
                   + f" | attend: {attend[:100]}"
                   + (f" | avoid: {'; '.join(avoid)[:80]}" if avoid else "") + (f" | {why}" if why else ""))
        if c.mode != "live" or conf < float(c.min_confidence):
            return ""
        # the line she reads states what happens; nothing in it is optional.
        # A model offered a choice takes the way out every time (twelve of
        # twelve on 2026-08-30), which is why the deciding is done here
        # notes from outside, about her: what, not how. The words are hers
        # and none of these
        if channel == "friend":
            head_do = "NOW, IN THIS TURN, THIS COMES OUT -- she has been holding it (a note from outside; the words are hers and none of these): "
            head_at = "WHAT SHE HAS BEEN HOLDING, and it shows in this turn (a note from outside, not words): "
        else:
            head_do = "NOW, IN THIS MESSAGE, THIS COMES OUT -- you have been holding it (a note about you from outside: what, not how; the words are yours and none of these): "
            head_at = "WHAT YOU HAVE BEEN HOLDING, and it shows in this message (a note about you from outside, not words to send): "
        if not (do or attend):
            return ""
        if do:
            text = head_do + do + ((" Beyond it: " + attend) if attend else "")
        else:
            text = head_at + attend
        if avoid:
            text += " (not now: " + "; ".join(avoid) + ")"
        self.released()
        return text

    def ab_report(self, n=8):
        """The ongoing test: each live reply beside the reply she would have
        sent with the gate's line in the slot instead."""
        rows = self.store.get("nudge_ab", []) or []
        if not rows:
            return "nudge-ab: no pairs yet (nudge.compare is " + ("on" if self.config.nudge.compare else "off") + ")"
        out = [f"nudge-ab: {len(rows)} pair(s) on record; the newest first"]
        for r in rows[-n:][::-1]:
            t = self.clock.to_char(r["ts"]).strftime("%a %H:%M")
            out.append(f"--- {t} her time | him: " + " / ".join(x[:90] for x in r.get("him", [])))
            out.append("    nudge: " + (f"DO[{r.get('do_source') or '?'}] {r.get('do', '')[:120]}" if r.get("do") else ("none (needs all of her)" if r.get("heavy") else "none")) + f" | attend: {r.get('attend', '')[:100]}")
            out.append("    gate:  " + (r.get("gate") or "(none)")[:120])
            out.append("    WITH:    " + " // ".join(b[:160] for b in r.get("with", [])))
            out.append("    WITHOUT: " + " // ".join(b[:160] for b in r.get("without", []))
                       + (f"   [copied {r['copied']} word(s) in a row from the nudge]" if int(r.get("copied", 0) or 0) >= 4 else ""))
        return "\n".join(out)

    def report(self):
        rows = self.store.get("nudge_log", []) or []
        c = self.config.nudge
        head = ""
        if getattr(c, "fire_on_unsaid", True):
            last = float(self.store.get("nudge_fired_ts", 0) or 0)
            head = (f"unsaid {self.level():.0f}/100, fires at {c.unsaid_min}, gap {c.min_gap_minutes} min"
                    + (f", last fired {self.clock.to_char(last).strftime('%a %H:%M')} her time" if last else ", never fired") + chr(10))
        if not rows:
            return head + f"nudge: {c.mode} | nothing yet this run"
        n = len(rows)
        agree = sum(1 for r in rows if r.get("agree", 0) >= 0.3)
        used = sum(1 for r in rows if r.get("mode") == "live" and float(r.get("confidence", 0)) >= float(c.min_confidence))
        did = sum(1 for r in rows if r.get("do"))
        out = [head + f"nudge: {c.mode} | {n} run(s) on record, agreed with the gate {agree} time(s), placed in the slot {used} time(s), decided a thing happens {did} time(s)"]
        for r in rows[-8:][::-1]:
            out.append(f"  {r.get('channel')}{' ' + r['who'] if r.get('who') else ''} conf {r.get('confidence', 0):.2f} agree {r.get('agree', 0):.2f}: "
                       + (f"DO[{r.get('do_source') or '?'}] {r.get('do', '')[:90]} | " if r.get("do") else "")
                       + f"{r.get('attend', '')[:90]}"
                       + (f" | avoid {'; '.join(r.get('avoid') or [])[:60]}" if r.get("avoid") else "")
                       + (f"\n      gate: {r['gate'][:100]}" if r.get("gate") else ""))
        return "\n".join(out)
