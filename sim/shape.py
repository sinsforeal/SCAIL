import random
import re

# How much she says, decided by code before the persona model runs. The
# model's natural failure mode is completeness: over four days her replies
# ran 3 bubbles at the mode (22 of 55 bursts), median bubble 89 characters,
# 6% under 30 -- essays, whatever the state was, because nothing bounded
# them. style.md already described the right register and was ignored,
# which is the proof instruction alone cannot hold this. So the shape of a
# message -- bubbles and characters -- is a draw conditioned on her state
# and the occasion, the instruction goes into the situation, and the
# persona enforces it after the draft (one redraft, then whole bubbles are
# dropped). Hurt is weight: upset collapses the draw to curt/short,
# because a person who is properly hurt sends less, never more.

LINES = {
    "curt": ("Send ONE line only, a few words -- the way you tap out a quick "
             "text one-handed. Do NOT write a second line and do NOT explain why."),
    "short": "Send ONE short line. One thought, then stop. Do NOT add a second line.",
    "plain": "Send at most TWO bubbles, a line or two each. Say the thing, not everything.",
    "full": "Send two or three bubbles. Answer what actually matters and let the rest go.",
    "spill": ("Let it run tonight: up to six bubbles, jagged, corrections and all. "
              "Stop when you run out, not when it is finished."),
}

# The same instruction for a character who is addressed in Japanese
# (`sim/lang.py`). This is the last thing she reads before she writes, so it
# is the least useful line in the prompt to leave in the other language.
LINES_JA = {
    "curt": "一行だけ送る。数語で。片手で打つ短いメッセージのように。二行目は書かない。理由も説明しない。",
    "short": "短い一行だけ送る。ひとつのことを言って、そこで止める。二行目は足さない。",
    "plain": "吹き出しは多くて二つ、それぞれ一、二行。言うことだけ言って、全部は言わない。",
    "full": "吹き出しを二つか三つ送る。本当に大事なところに答えて、残りは流す。",
    "spill": "今夜は出るに任せる。吹き出しは六つまで、ぐちゃぐちゃでも、言い直しごと出す。"
             "言い尽くしたからではなく、出尽くしたところで止める。",
}


# What HE just put in front of her, and what that obliges her first bubble to
# do. Read from his own words, in code, because it is a "when" -- and because
# the failure it fixes was hers on 2026-08-27: he said Japan having a Pixar
# exhibit was interesting and she answered "i'm just the body in the yukata",
# three clauses about her own standing and not one touching what he raised.
#
# A person answers the thing in front of them first and gets to themselves
# after. The bible already says she does; nothing told her which of his
# sentences was the thing.

READS_HER = ("you sound", "you seem", "you always", "you never", "you act like",
             "you're just", "youre just", "you're being", "youre being",
             "why do you", "why are you", "you get like", "you do this",
             # a read that lands (tk-mfx): her card gets loud and defensive when he is right
             "you're not the one", "youre not the one", "i bet you", "you probably",
             "you must be", "you just want", "you secretly", "you're scared", "youre scared",
             "you're afraid", "youre afraid", "you're jealous", "youre jealous")
ASKS = ("what", "why", "how", "when", "where", "who", "which", "do you", "did you",
        "are you", "is it", "can you", "would you", "have you", "you ever")


# What HE asks of her, apart from the three kinds above (tk-mfx). On cl2_s_tomoe
# all 17 of his messages came out "opinion" (any message of 40+ characters that
# is not a question), so every one of them got "agree with it, argue with it, or
# ask": a menu with agree first, and no way to tell "weird one, definitely" or
# "just reply to the newest dog video" (he asks her to go along) from a remark.
# `wants_kind` names the ask; `Shape.pushback` decides, from her state and her
# card's temper, whether her plan says she would resist it.
_DO_RE = re.compile(
    r"\b(just (?:say|reply|send|tell|go|pick|try|do|text|ask|put|show|call|watch|use|be|answer|write|come)|you should|you need to|you have to|you must|why don'?t you|how about you|"
    r"come on|go ahead|go and|promise me|do me a favou?r|do it|try (?:to |it|that)|"
    r"don'?t (?:forget|be|let|pick|say|tell|send)|dont (?:forget|be|let|pick|say|tell|send)|"
    r"please (?:\w+)|send (?:me|a|the)|tell me|show me|say (?:it|something|sorry))\b", re.I)
_AGREE_RE = re.compile(
    r"\b(right\?|don'?t you (?:think|agree)|you agree|isn'?t it|admit it|admit that|am i right|"
    r"agree\?|you know i'?m right|definitely|obviously|for sure|trust me|believe me)\b", re.I)


def wants_kind(his_txt):
    """"do" when he asks her to go along with something, "agree" when he asks
    her to agree, else "". Code reads his words; it never writes hers."""
    t = " ".join(str(his_txt or "").split())
    if not t:
        return ""
    if _DO_RE.search(t):
        return "do"
    if _AGREE_RE.search(t):
        return "agree"
    return ""


def _first_sentence(text, cap=110, floor=25):
    """Enough of what he said to be worth quoting back at her. A sentence
    shorter than `floor` is an opener, not the point ("to be completely
    fair."), so it keeps reading."""
    t = " ".join(str(text or "").split())
    best = 0
    for i, ch in enumerate(t):
        if ch in ".?!" and i + 1 < len(t) and t[i + 1] == " ":
            if i + 1 >= floor:
                best = i + 1
                break
    return (t[:best] if best else t[:cap]).strip()


def engage_kind(his_txt):
    """WHICH of the three things his message is, as a code word.

    Separate from the wording because the caller has to know which case fired
    and cannot find out by looking for a phrase inside the sentence: the
    sentence is written in whichever language the character is addressed in."""
    t = " ".join(str(his_txt or "").split())
    low = t.lower()
    if not t:
        return ""
    # 1. he has just told her what she is. The bible is explicit that this is
    # the one thing she does not take lying down, and on 2026-08-27 she
    # answered "why do you sound like a slave to them lmao?" with "like i
    # can't decide things for myself or something" -- agreeing, in his words.
    if any(k in low for k in READS_HER):
        return "reads_her"
    # 2. he asked something. It gets answered first, and how she feels about
    # having been asked comes after, if at all.
    if "?" in t or low.startswith(ASKS):
        return "asks"
    # 3. he put an opinion about the world in front of her and left it there.
    if len(t) >= 40:
        return "opinion"
    return ""


def engage_line(his_txt, ja=False):
    """The line that says what his message obliges, or "" when it obliges
    nothing. Three cases, in the order they beat each other."""
    def tr(en, jp):
        return jp if ja else en
    t = " ".join(str(his_txt or "").split())
    kind = engage_kind(t)
    if kind == "reads_her":
        return tr("he has just told you what you are. you do not take that lying down and you "
                  "do not agree with it to be nice -- get loud, get rude, tell him he cannot "
                  "read minds, make him back off. never hand him your own summary of yourself.",
                  "彼はいま、あなたがどういう人間かを決めつけた。それを黙って受けないし、"
                  "角が立たないように同意もしない。声を荒げていい、乱暴でいい、人の心が読めるわけがないと言って、"
                  "引き下がらせる。自分についての要約を自分から差し出さない。")
    if kind == "asks":
        # "the first thing you say" rather than "your first bubble": a
        # character told nothing about bubbles (`shape.tell_length` false) has
        # no first bubble to point at, and the instruction means the same for
        # one who does.
        return tr(f"he asked you something: \"{_first_sentence(t)}\". the FIRST thing you say answers "
                  "the question he actually asked. what it makes you feel comes after that, if "
                  "at all -- and if you are not answering it, say that, do not answer a "
                  "different question instead.",
                  f"彼はあなたに何か訊いた: 「{_first_sentence(t)}」。最初に言うことは、"
                  "彼が実際に訊いたことへの答えにする。それについてどう感じたかは、そのあと。"
                  "答えないなら答えないと言う。別の質問に答えてごまかさない。")
    if kind == "opinion":
        return tr(f"he has said what he thinks about something and left it with you: "
                  f"\"{_first_sentence(t)}\". take THAT up first -- agree with it, argue with "
                  "it, or ask him something back about it. your own day and your own standing "
                  "are not the answer to it.",
                  f"彼は何かについて自分の考えを言って、そのままあなたに預けた: "
                  f"「{_first_sentence(t)}」。まずそれを受ける。同意するか、反論するか、それについて訊き返す。"
                  "自分の一日の話も、自分の立ち位置の話も、それへの答えにはならない。")
    return ""


class Shape:
    def __init__(self, config, state, clock):
        self.config = config
        self.state = state
        self.clock = clock

    @property
    def ja(self):
        """The length line and the engage line are the last things she reads
        before she writes, so they are written in her own language. Read per
        call so a harness can flip the arm inside one process."""
        from sim.lang import reads_ja
        return reads_ja(self.config)

    def _mk(self, kind, line, engage):
        mb, mc = self.config.shape.kinds[kind]
        return {"kind": kind, "max_bubbles": int(mb), "max_chars": int(mc),
                "line": line, "engage": engage}

    def upset(self):
        """How hurt she is AT HIM, which is what makes a person send less to
        him. Tension is with him by definition; anger and sadness only count
        when their source is him (State.sources) -- a temper about school
        does not shorten her texts to him -- and sadness at half weight,
        because sad quiets differently from angry."""
        c = self.config.shape
        g = self.state.gauges
        him = self.state.relationships.get(self.state._him_key() or "him", {})
        vals = [int(him.get("tension", 0))]
        try:
            src = self.state.sources()
            hk = self.state._him_key() or "him"
        except Exception:
            src, hk = {}, "him"
        if src.get("anger", ("", ""))[0] == hk:
            vals.append(int(g.get("anger", 0)))
        if src.get("sadness", ("", ""))[0] == hk:
            vals.append(int(g.get("sadness", 0) * c.upset_sadness_weight))
        return max(vals)

    def _fade(self):
        """0 right after the last thing that happened between them (the
        rupture or its latest attempt), 1 after upset_fade_hours."""
        c = self.config.shape
        rup = getattr(self.state, "ruptures", None)
        try:
            r = rup.open_one() if rup else None
        except Exception:
            r = None
        if not r:
            return 1.0
        last = float(r.get("ts", 0))
        for a in r.get("attempts", []) or []:
            last = max(last, float(a.get("ts", 0)))
        hours = max(0.0, (self.clock.now_ts() - last) / 3600.0)
        return min(1.0, hours / max(1.0, float(c.upset_fade_hours)))

    def pushback(self, his_txt):
        """tk-mfx: the plan line that says she would resist what he asks, or "".

        Needs `shape.pushback.enabled`. Code reads the ask (`wants_kind`) and her
        state (edge, strain, low mood) against the card's base temper
        (`shape.pushback.base`); the line names the ask and leaves the words to
        the model. At most once per `min_gap_minutes`. `self.last_pushback`
        carries the score and terms for the trace."""
        pc = getattr(self.config.shape, "pushback", None)
        self.last_pushback = {}
        if not pc or not bool(getattr(pc, "enabled", False)):
            return ""
        kind = wants_kind(his_txt)
        if not kind:
            return ""
        g = self.state.gauges

        def gv(k):
            try:
                return float(g.get(k, 0)) / 100.0
            except Exception:
                return 0.0
        edge = max(gv("anger"), gv("awkwardness"), gv("shame"))
        strain = max(gv("stress"), gv("anxiety"))
        low = 1.0 - gv("mood") if "mood" in g else 0.0
        score = (float(getattr(pc, "base", 0.3)) + 0.4 * edge + 0.2 * strain + 0.2 * low
                 + (0.1 if kind == "do" and float(g.get("energy", 50)) < 35 else 0.0))
        rec = {"kind": kind, "score": round(score, 3), "edge": round(edge, 2),
               "strain": round(strain, 2), "low_mood": round(low, 2), "fired": False}
        self.last_pushback = rec
        if score < float(getattr(pc, "threshold", 0.5)):
            return ""
        now = self.clock.now_ts()
        last = float(self.state.store.get("pushback_last", 0) or 0) if hasattr(self.state, "store") else 0.0
        if last and (now - last) < float(getattr(pc, "min_gap_minutes", 20)) * 60:
            rec["held"] = "min gap"
            return ""
        rec["fired"] = True
        try:
            self.state.store.set("pushback_last", now)
        except Exception:
            pass
        how = str(getattr(pc, "how", "") or "").strip()
        q = _first_sentence(his_txt)
        if self.ja:
            return (f"彼はあなたに求めている: 「{q}」。" + ("同意するにせよ従うにせよ、" if kind == "agree" else "")
                    + "簡単に乗らない。まず押し返す。" + (how + " " if how else "")
                    + "折れるなら、押し返したあとで、自分のやり方で。")
        return (f"he is asking you to {'agree' if kind == 'agree' else 'go along'}: \"{q}\". you do not just "
                "go along to be easy. push back on it first, in your own way; if you give in, it is after that "
                + ("and on your terms. " if not how else "and on your terms. ") + how).strip()

    def _engage_only(self, unread):
        """What his message obliges, and nothing about length. For a character
        who is told to reply how she wants (`shape.tell_length` false): the
        draw would only be the first character's English measured on somebody
        it was never fitted to."""
        his_txt = "\n".join(m.get("text", "") for m in (unread or []))
        eng = engage_line(his_txt, self.ja) if unread else ""
        pb = self.pushback(his_txt) if unread else ""
        if pb:
            eng = pb if engage_kind(his_txt) in ("opinion", "") else (eng + " " + pb)
        return {"kind": "", "max_bubbles": 0, "max_chars": 0, "line": "", "engage": eng}

    def draw(self, unread, intent_kind="", scene=None):
        c = self.config.shape
        if not c.enabled:
            return None
        if not getattr(c, "tell_length", True):
            return self._engage_only(unread)
        g = self.state.gauges
        him = self.state.relationships.get(self.state._him_key() or "him", {})
        upset = self.upset()
        rng = random.Random(int(self.clock.now_ts()))
        scene = scene or {}
        access = scene.get("phone_access") or "free"
        alone = (scene.get("with") or scene.get("with_who") or "alone") == "alone"
        hour = self.clock.now().hour
        night = hour >= c.night_from or hour < 3

        # the occasion decides before the state does
        if intent_kind == "share":
            return self._mk("short",
                            "送るのはそのものだけ。リンクか画像と、多くても一行添えるだけ。"
                            "気持ちは付けない。前置きもしない。"
                            if self.ja else
                            "you are sending him the thing itself. "
                            "the link or the picture and at most one line with it. "
                            "no feelings attached, no lead-up.", None)
        if intent_kind == "afterthought":
            k = "short" if rng.random() < 0.7 else "plain"
            return self._mk(k, (LINES_JA if self.ja else LINES)[k], None)

        his_txt = "\n".join(m.get("text", "") for m in (unread or []))
        # gone cold on purpose is the fewest words she can manage, whatever
        # her mood says; protest is allowed the room to push
        bias = ""
        att = getattr(self.state, "attachment", None)
        if att:
            bias = att.shape_bias()
        # her body's say: walking is curt, a packed train is short, wiped is
        # short. A stance under threat still comes first.
        sit = getattr(self.state, "situation", None)
        if not bias and sit:
            try:
                bias = sit.shape_bias()
            except Exception:
                bias = ""
        if bias == "curt":
            w = {"curt": 65, "short": 35}
        elif bias == "short":
            w = {"curt": 30, "short": 55, "plain": 15}
        elif upset >= c.upset_short_from:
            # the collapse is at its tightest right after the break and eases
            # over upset_fade_hours toward the ordinary draw -- two days of
            # 70% curt on a held gauge made every reply "Cats are fine."
            tight = {"curt": 70, "short": 30, "plain": 0} if upset >= c.upset_curt_from else {"curt": 25, "short": 45, "plain": 30}
            eased = {"curt": 20, "short": 40, "plain": 30, "full": 10}
            t = self._fade()
            w = {k: int(round(tight.get(k, 0) * (1 - t) + eased.get(k, 0) * t)) for k in set(tight) | set(eased)}
        else:
            w = dict(c.weights)
            if int(g.get("energy", 50)) < c.tired_energy:
                w["curt"] += 10
                w["short"] += 15
                w["full"] = max(0, w["full"] - 10)
                w["spill"] = 0
            if "?" in his_txt or len(his_txt) >= c.long_msg_chars:
                w["full"] += c.question_full_bonus
            # a spill has to be earned: pressure, alone, a free phone, late
            pressure = max(int(g.get("unsaid", 0)), int(g.get("loneliness", 0)))
            if not (access == "free" and alone and night
                    and pressure >= c.spill_pressure_from):
                w["spill"] = 0
            else:
                w["spill"] = w.get("spill", 4) * 3
        if access == "glance":
            # she is sneaking a look; nothing long leaves from under a desk
            w.pop("spill", None)
            w.pop("full", None)
        total = sum(v for v in w.values() if v > 0)
        if total <= 0:
            w, total = {"short": 1}, 1
        r = rng.random() * total
        kind = "short"
        for k, v in w.items():
            if v <= 0:
                continue
            r -= v
            if r <= 0:
                kind = k
                break

        # completeness is a variable, not a guarantee: sometimes she answers
        # only the thing that got her, and a question can be left sitting
        engage = None
        if unread and (len(unread) > 1 or len(his_txt) > 80):
            p = c.engage_upset_p if upset >= c.upset_short_from else c.engage_partial_p
            if rng.random() < p:
                engage = ("彼が送ってきたもの全部に答えなくていい。本当に引っかかった一つに反応して、"
                          "残りは置いたままでいい。質問でも。"
                          if self.ja else
                          "you do not have to answer everything he sent. react "
                          "to the one thing that actually got you, and it is "
                          "fine to leave the rest sitting, even a question.")
        # ...but whatever she answers, she answers HIM. A read of her beats the
        # partial licence outright (there is no version of that moment where she
        # lets it stand); a question or a claim rides with it, because "you need
        # not answer all of it" and "the bit you answer is his, not yours" are
        # not in conflict.
        obliged = engage_line(his_txt, self.ja) if unread else ""
        if obliged:
            # a read of her beats the partial licence outright, and WHICH case
            # fired is read from the record of his words rather than from the
            # sentence, which is written in whichever language she reads
            engage = obliged if engage_kind(his_txt) == "reads_her" else (
                (engage + " " + obliged) if engage else obliged)
        pb = self.pushback(his_txt) if unread else ""
        if pb:
            engage = pb if engage_kind(his_txt) in ("opinion", "") else ((engage + " " if engage else "") + pb)
        return self._mk(kind, (LINES_JA if self.ja else LINES)[kind], engage)
