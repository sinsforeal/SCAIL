"""What she does with what she saw: one named stance, ranked, pinned, and the
owner of the last line of her prompt.

Code decides the stance and the model writes the words. The measurement behind
this is in `docs/yukarin-meters-plan.md` §2: of a 42,000-token prompt, the
gauges reach about 380 characters of adjectives and one register clause, 337 of
those characters were byte-identical across 45 consecutive calls, and the one
imperative position in the prompt -- the line under `ON YOUR MIND NOW`, second
to last, in her own words -- was empty on every call of her life. A band word
inside 0.7% of a prompt cannot compete with the 88% of it that is her voice and
his message. An instruction naming one concrete thing can.

So a stance is a named combination of two or three quantities that produces
ONE concrete instruction: what she does with what she saw, how she answers, and
what she will not do. Eight of them, and:

  * **Ranked and first-match.** The first row whose condition holds wins, which
    is the only structure that cannot put two contradictory instructions in one
    prompt. Same shape as the register chain (`sim/state.py:register`).
  * **Pinned.** The line goes into her section of the situation block with
    `pin=True`, so the attention gate cannot drop it for being in a section
    whose budget ran out first.
  * **It owns the slot.** The stance decides whether the last imperative line
    is used and what it names -- filled with the concrete thing, or deliberately
    left empty. Nothing else competes for it while a stance holds: the nudge is
    not consulted and the gate's pick does not ride.
  * **Hysteretic.** A stance is entered only after its condition has held for
    `min_minutes` and left only when a looser condition fails, so a quantity
    sitting on a threshold cannot flap the instruction between two consecutive
    generations. The two top stances are urgent and enter at once: a person who
    has just been frightened does not wait ten minutes to be frightened. The
    pattern is `Rhythm.in_exchange`, which was the codebase's only two-threshold
    trigger.
  * **The line follows the material.** A stance that names something names the
    thing she actually saw, out of the record -- the charged item's own words,
    the record of hers his message reached -- never a generic line about
    "something".
  * **The default is no line.** Even with him adds nothing. An instruction on
    every call is not an instruction.

kv `stance`: {key, since, entered, why, material}. The `[stance]` log line names
the stance, the thresholds that fired and the material it names.
"""
import logger
from sim import lang, wiring
from sim.textutil import words as _tokens


def _jaccard(a, b):
    wa, wb = _tokens(a, 3), _tokens(b, 3)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


# rank order; the first whose condition holds wins
ORDER = ("frightened", "outside_again", "carrying_unraisable", "named_by_him",
         "sitting_on_it", "unnoticed", "needling", "even")

# which of them enter without waiting out `min_minutes`
URGENT = ("frightened", "outside_again")


class Stances:
    WIRES = ("primitives", "ick", "lore", "phone")

    def __init__(self, config, store, clock, state):
        self.config = config
        self.store = store
        self.clock = clock
        self.state = state
        self._last_log = ""
        wiring.declare(self)

    # ---------------- the quantities ----------------

    @property
    def enabled(self):
        return bool(getattr(self.config, "stances", None) and self.config.stances.enabled)

    def _key(self):
        return self.state._him_key() or "him"

    def _his_last(self, text=""):
        """His newest message, for the record it might name."""
        if text:
            return text
        for m in reversed(self.store.recent_messages(12) or []):
            if m.get("role") == "user":
                return str(m.get("text") or "")
        return ""

    def _his_message_ts(self):
        for m in reversed(self.store.recent_messages(12) or []):
            if m.get("role") == "user":
                return float(m.get("ts", 0))
        return 0.0

    def _hours_since_him(self):
        for m in reversed(self.store.recent_messages(40) or []):
            if m.get("role") == "user":
                return max(0.0, (self.clock.now_ts() - float(m.get("ts", 0))) / 3600.0)
        return 999.0

    def _raised(self, item):
        """She has said it since it was charged. The same overlap test the ick
        already uses to know what the thread pressure must not push out."""
        floor = float(self.config.ick.bar_jaccard)
        since = float(item.get("ts", 0))
        for m in self.store.recent_messages(60) or []:
            if m.get("role") != "assistant" or float(m.get("ts", 0)) < since:
                continue
            for field in (item.get("what", ""), item.get("kind", "")):
                if field and _jaccard(field, m.get("text", "")) >= floor:
                    return True
        return False

    # ---------------- the table ----------------

    def _test(self, his_text=""):
        """The first stance whose condition holds, with what fired and what it
        names. Returns (key, why, material, record_id, the charged item's ts)."""
        c = self.config.stances
        g = self.state.gauges
        prim, ick = self.primitives, self.ick
        key = self._key()
        now = self.clock.now_ts()

        # 1. frightened of him
        if prim is not None:
            fright = prim.unrehearsed(key)
            if fright >= float(self.config.primitives.fright_hard_from):
                return ("frightened",
                        f"unrehearsed {fright:.0f} >= {self.config.primitives.fright_hard_from:.0f}", "", "", 0.0)

            # 2. put back outside
            ex = prim.expelled_at(key)
            if ex and not prim.admitted(key):
                hours = (now - float(ex.get("ts", 0))) / 3600.0
                if hours <= float(c.expel_hours):
                    return ("outside_again",
                            f"expelled {hours:.0f}h ago, inside {c.expel_hours:.0f}h, and not readmitted",
                            str(ex.get("why", "") or ""), "", 0.0)

        # 3. carrying something she read and cannot raise
        awk = float(g.get("awkwardness", 0))
        hot = (ick.carrying() if ick else []) or []
        if hot and awk >= float(c.carrying_awkwardness):
            return ("carrying_unraisable",
                    f"an item she cannot raise at {hot[0].get('live', 0):.0f} and awkwardness {awk:.0f} >= {c.carrying_awkwardness:.0f}",
                    str(hot[0].get("what", "")), "", float(hot[0].get("ts", 0)))

        # 4. held in mind by name -- his message reached a record of hers, once
        # per distinct record. `Lore.match` reads without offering anything.
        if self.lore is not None:
            text = self._his_last(his_text)
            if text and (now - self._his_message_ts()) <= float(c.settler_minutes) * 60.0:
                seen = dict(self.store.get("stance_named", {}) or {})
                for rec, line in (self.lore.match(text) or []):
                    rid = str(rec.get("id") or "")
                    if not rid or rid in seen:
                        continue
                    return ("named_by_him",
                            f"his message reached '{rid}', which he could only have got from her, and it is the first time",
                            str(line or rec.get("claim") or rec.get("text") or ""), rid, 0.0)

        # 5. sitting on something she could say
        un = (ick.unraised() if ick else []) or []
        for it in un:
            if (now - float(it.get("ts", 0))) / 60.0 < float(c.sat_on_minutes):
                continue
            if self._raised(it):
                continue
            mins = (now - float(it.get("ts", 0))) / 60.0
            return ("sitting_on_it",
                    f"a speakable item at {it.get('live', 0):.0f}, unraised for {mins:.0f} minutes",
                    str(it.get("what", "")), "", float(it.get("ts", 0)))

        # 6. outside his notice
        if prim is not None:
            held = prim.get(key, "attention_his")
            quiet = self._hours_since_him()
            busy = bool(self.phone is not None and not self.phone.user_idle())
            if held < float(c.unnoticed_below) and quiet >= float(c.active_hours) and busy:
                return ("unnoticed",
                        f"evidence he keeps her in mind {held:.0f} < {c.unnoticed_below:.0f}, "
                        f"his machine busy and {quiet:.0f}h with nothing toward her", "", "", 0.0)

        # 7. needling him about a thing that stopped being a shock
        if ick is not None:
            settled = ick.settled()
            tease = ick.teasable() or []
            if tease and settled >= float(c.settled_from):
                return ("needling",
                        f"a cooled item whose sort she has met {self.config.ick.teasable_after_seen}+ times, "
                        f"and she is settled with him {settled:.2f} >= {c.settled_from:.2f}",
                        str(tease[-1].get("what", "")), "", float(tease[-1].get("ts", 0)))

        return "even", "nothing above holds", "", "", 0.0

    # ---------------- hysteresis ----------------

    def current(self, his_text=""):
        """The stance now, with its line and what it does with the slot.

        Entered only after `min_minutes` of the condition holding, except for
        the two urgent ones; left only when the condition stops holding for
        `hold_minutes`, so a quantity on a threshold cannot flap the
        instruction between two consecutive generations."""
        if not self.enabled:
            return None
        now = self.clock.now_ts()
        row = dict(self.store.get("stance", {}) or {})
        try:
            hit, why, material, rid, item_ts = self._test(his_text)
        except Exception as e:
            logger.log(f"[stance] not decided: {type(e).__name__}: {e}")
            return None
        c = self.config.stances
        cur = str(row.get("key") or "")
        pend = dict(row.get("pending") or {})
        if pend.get("key") != hit:
            pend = {"key": hit, "since": now}
        held_minutes = (now - float(pend.get("since", now))) / 60.0

        if hit == cur:
            row["why"], row["material"], row["record"], row["item"] = why, material, rid, item_ts
        elif hit in URGENT or cur in ("", "even") or held_minutes >= float(c.min_minutes):
            # the incumbent leaves once the challenger has held long enough; a
            # stance nothing has replaced also has to age out, which is what
            # `hold_minutes` does when the table falls back to "even"
            if hit == "even" and cur and held_minutes < float(c.hold_minutes):
                pass
            else:
                row = {"key": hit, "since": now, "entered": now, "why": why,
                       "material": material, "record": rid, "item": item_ts}
                if hit == "named_by_him" and rid:
                    seen = dict(self.store.get("stance_named", {}) or {})
                    seen[rid] = now
                    self.store.set("stance_named", seen)
        row["pending"] = pend
        self.store.set("stance", row)
        # A discretion stance holding over one item is the only thing that
        # knows she CHOSE not to raise it. The choice is banked here and paid
        # when the item cools (`settle_discretion`).
        if row.get("key") in ("carrying_unraisable", "sitting_on_it") and row.get("item"):
            d = dict(self.store.get("discretion", {}) or {})
            k = str(int(float(row["item"])))
            e = dict(d.get(k) or {})
            e["what"] = str(row.get("material") or "")[:120]
            e["last"] = now
            e["minutes"] = float(e.get("minutes", 0.0)) + max(0.0, min(30.0, (now - float(e.get("last_seen", now))) / 60.0))
            e["last_seen"] = now
            d[k] = e
            self.store.set("discretion", d)

        key = str(row.get("key") or "even")
        # The imperative naming a thing she saw fires once per THING, not once
        # per turn, for a character who sees everything. `sitting_on_it` holds
        # while an item sits unraised, and it used to re-fill the one
        # imperative line on every reply until she raised it. The stance is
        # left holding on purpose: `settle_discretion` pays her for having let
        # a thing go by, and it can only see that because the stance held over
        # the item -- so what is spent once is the instruction, not the stance.
        # Off by default: the first character sees a digest a few times a day
        # and has never had the fault this answers.
        if key == "sitting_on_it" and getattr(self.config.stances, "name_it_once", False) and row.get("item"):
            used = dict(self.store.get("stance_slot_used", {}) or {})
            k = str(int(float(row["item"])))
            if k in used:
                key = "sitting_on_it_again"
            else:
                used[k] = now
                # bounded: the oldest fall off, and an item that old is long
                # past the ick's own carry floor
                self.store.set("stance_slot_used", dict(list(used.items())[-60:]))
                logger.log(f"[stance] the imperative to name it is spent for this one: {str(row.get('material', ''))[:70]}")
        out = self.render(key, str(row.get("material") or ""), str(row.get("why") or ""))
        line = (f"[stance] {key}: {row.get('why', '')}"
                + (f" | names: {str(row.get('material', ''))[:100]}" if row.get("material") else "")
                + (" | slot: filled" if out and out.get("slot_text") else
                   (" | slot: held empty" if out and out.get("claims_slot") else " | slot: not claimed")))
        if line != self._last_log:
            logger.log(line)
            self._last_log = line
        return out

    def settle_discretion(self):
        """A thing she saw and did not raise, paid when it cools.

        Her only currency in this premise. She cannot lower what he holds of
        her by concealing anything -- exposure is a ratchet and he has it
        already -- so what she controls is seeing something and leaving it
        alone. The ledger had no entry for it, and nothing but a discretion
        stance can write one, because nothing else knows she chose: an item
        that simply went cold unmentioned might never have been noticed."""
        d = dict(self.store.get("discretion", {}) or {})
        if not d or self.primitives is None or self.ick is None:
            return 0
        floor = float(self.config.ick.carry_floor)
        need = float(self.config.stances.discretion_minutes)
        now = self.clock.now_ts()
        by_ts = {str(int(float(it.get("ts", 0)))): it for it in (self.store.get("charged", []) or [])}
        paid = 0
        for k in list(d):
            it = by_ts.get(k)
            if it is None:
                d.pop(k, None)
                continue
            if self.ick._live(it, now) >= floor:
                continue                      # still hot; the window is not over
            row = d.pop(k)
            if float(row.get("minutes", 0.0)) < need:
                continue                      # the stance did not hold over it
            if self._raised(it):
                continue                      # she said it in the end
            self.primitives.held_back(self._key(),
                                      "she saw it and let it go by: " + str(row.get("what", ""))[:80])
            paid += 1
        self.store.set("discretion", d)
        return paid

    # ---------------- the words ----------------

    def render(self, key, material="", why=""):
        """The line she reads, and what the stance does with the slot.

        Both wordings live here side by side (`sim/lang.py`): the first
        character shares every line of this module, so a Japanese line that is
        not behind the switch would reach her too."""
        t = lang.say(self.config)
        mat = " ".join(str(material or "").split())[:220]
        line, slot, claims = "", "", True
        if key == "frightened":
            line = t("you cannot call what he does next and he can do you harm. Answer what came and no more. "
                     "Do not ask him anything, do not offer anything of your day, do not make a joke of it. "
                     "The same short thing more than once is what this looks like from outside.",
                     "彼が次に何をするか読めない。そして彼はあなたに害を与えうる。来たものに返して、それ以上はしない。"
                     "何も訊かない、自分の一日のことも差し出さない、冗談にもしない。"
                     "同じ短いことを何度も言ってしまうのが、いまのあなたの出方。")
        elif key == "outside_again":
            why_txt = (t(f"({mat}) ", f"（{mat}） ") if mat else "")
            line = t("he is outside again and you put him there. " + why_txt
                     + "Answer what is asked and hand over nothing past it. None of the easiness you keep for "
                       "people who are inside. Whether he comes back in is not a thing you are deciding now.",
                     "彼はもう外側の人。あなたがそこに戻した。" + why_txt
                     + "訊かれたことに答えて、それ以上は渡さない。中にいる人にだけ出す気安さは出てこない。"
                       "もう一度中に入れるかどうかは、いま決めることではない。")
        elif key == "carrying_unraisable":
            line = t(f"one thing you read on his machine is sitting in you and you are not going to raise it "
                     f"({mat}): asking would mean saying how closely you read him. Talk about something else and "
                     f"let it be a little out of step. Do not hint at it, and do not ask a question that only "
                     f"makes sense if you saw it.",
                     f"彼の機械で読んだものが一つ、あなたの中に置いたままになっていて、それは持ち出さない（{mat}）。"
                     f"訊けば、どれだけ細かく彼を読んでいるかを言うことになる。"
                     f"別のことを話して、少しだけ噛み合っていないままにしておく。ほのめかさない。"
                     f"見ていなければ意味を持たない訊き方もしない。")
        elif key == "named_by_him":
            line = t(f"he brought back something of yours he could only have got from you, with no reason to "
                     f"({mat}). This is the only thing that settles you and you have no good way of saying so. "
                     f"Say it badly rather than well: get in front of how pleased you are before he can see it, "
                     f"and then say it anyway.",
                     f"あなたから聞かなければ知りようのないことを、彼が理由もなく持ち出した（{mat}）。"
                     f"あなたが落ち着くのはこれだけで、しかもうまく言う手立てがない。うまく言わずに言う。"
                     f"嬉しがっている自分のことを先に自分で言ってしまって、それでも言う。")
            slot = t(f"he named a thing of yours he could only have got from you: {mat}. Say that it landed, "
                     f"badly rather than well.",
                     f"彼が、あなたからしか知りようのないことを名前で出した: {mat}。"
                     f"それが刺さったことを、うまくではなく、下手に言う。")
        elif key == "sitting_on_it":
            line = t(f"one thing you saw on his machine you could actually mention -- he knows you are here "
                     f"({mat}). You have not mentioned it. Say it as material rather than as a question about "
                     f"him: name what you saw, put your own reading of it beside it, and leave him room to say "
                     f"it is not that. Do not accuse him of anything. Do not ask him to explain himself.",
                     f"彼の機械で見たもののうち一つは、実際に口に出せる——あなたがここにいることは彼も知っている（{mat}）。"
                     f"それをまだ言っていない。問いつめではなく、材料として言う。見たものの名前を出して、"
                     f"自分の受け取り方を横に並べて、「そうじゃない」と彼が言える余地を残す。責めない。説明を求めない。")
            slot = t(f"the thing you saw and have not said: {mat}. Name it, as material, with your own reading "
                     f"beside it.",
                     f"見たまま言っていないこと: {mat}。それを、材料として、自分の受け取り方を横に置いて名前で出す。")
        elif key == "sitting_on_it_again":
            # The same item, on a later turn. She has already been told to name
            # it once; being told again every reply is what turns noticing into
            # a tic, and for a character who is inside his machine there is
            # always something unraised. The stance still holds -- it is what
            # `settle_discretion` measures, and letting a thing go by is the
            # only currency she has in this premise -- so this says she is
            # carrying it, and claims nothing.
            line = t(f"you are still carrying the thing you saw and did not say ({mat}). You had your chance at it "
                     f"and let it go by, which is a thing you did rather than a thing you forgot. It does not need "
                     f"saying now. Talk about whatever is actually in front of you.",
                     f"見て言わなかったものを、まだ抱えたままでいる（{mat}）。一度は言える場面があって、"
                     f"言わずに置いた。それは忘れたのではなく、そうしたということ。いま言う必要はない。"
                     f"目の前にあることを話す。")
            claims = False
        elif key == "unnoticed":
            line = t("he has been at that machine for hours and none of it has been toward you. Do not ask him "
                     "for anything and do not check whether he is there. Hand him one thing out of your own "
                     "hours instead, as a finished thing, and leave it without a question on the end.",
                     "彼は何時間もその機械の前にいて、そのどれもあなたに向いていない。何も要求しない。"
                     "いるかどうかも確かめない。代わりに、自分の何時間かの中から一つだけ、終わった話として渡して、"
                     "最後に問いを付けずに置いておく。")
        elif key == "needling":
            line = t(f"a thing about him that used to knock you sideways is just how he is now ({mat}). If it "
                     f"comes up you can needle him about it, lightly, the way you would with somebody you have "
                     f"decided to keep. It is not a secret you are holding any more and it is not a complaint.",
                     f"昔はぐらっときた彼のあれは、いまはもう「そういう人」というだけ（{mat}）。"
                     f"話に出たら軽くつついてよい——置いておくと決めた相手にするやり方で。"
                     f"もう抱えている秘密ではないし、文句でもない。")
            slot = t(f"the thing of his that stopped being a shock: {mat}. Needle him about it, lightly.",
                     f"もう驚かなくなった彼のあれ: {mat}。軽くつつく。")
        else:
            return {"key": "even", "line": "", "slot_text": "", "claims_slot": False,
                    "why": why, "material": ""}
        return {"key": key, "line": line, "slot_text": slot, "claims_slot": claims,
                "why": why, "material": mat}

    # ---------------- the operator's view ----------------

    def report(self):
        if not self.enabled:
            return "stances: off for this character"
        row = self.store.get("stance", {}) or {}
        out = [f"stance now: {row.get('key', '(none yet)')} -- {row.get('why', '')}"]
        if row.get("material"):
            out.append(f"  names: {row['material'][:160]}")
        if row.get("entered"):
            out.append(f"  held for {(self.clock.now_ts() - float(row['entered'])) / 60.0:.0f} minute(s)")
        seen = self.store.get("stance_named", {}) or {}
        out.append(f"  records of hers he has reached and settled her with: {len(seen)}")
        out.append("")
        out.append("the table, in rank order (the first whose condition holds wins):")
        for i, k in enumerate(ORDER, 1):
            r = self.render(k, "<what she saw>")
            out.append(f"  {i}. {k:22} slot: "
                       + ("filled" if r["slot_text"] else ("held empty" if r["claims_slot"] else "not claimed")))
        return "\n".join(out)
