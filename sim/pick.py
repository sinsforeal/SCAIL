"""What she does with the phone, asked as a call that picks a tool -- and acted on.

Every decision to reach for him used to be a pure function (`sim/impulse.py`):
a score over her gauges, the silence and his hours, against a threshold, with a
roll on the edge. It can only answer one question -- does she write to him now
-- so a moment that is wrong for him is a moment where nothing happens, and a
promise to somebody who is not him has no term in it at all.

This asks the other question, and what comes back is what happens. At a moment
code already knows -- her plan gives her a free phone and something could be
done -- she is handed what a person with a phone has in front of her (where she
is, what has just happened, both clocks, the last of what the two of them said,
what is unanswered in her own rooms, what she is carrying) and the tools she has
a path to. The answer is what she DOES.

**Code keeps every hard gate and decides every moment; she decides what.** The
gates are listed in one place, `PhonePick.due`: her phone access off her own
schedule, so there is no call at all when the phone is not in her hand; the
frequency cap (`pick.min_gap_minutes`) and the day's cap (`pick.max_per_day`),
which are the money; a live run, never a sim and never a replay; and what kind
of thing she is, which decides the tools before the moment is built. A choice
the world cannot honour -- a friend who is not hers to write to, a group chat
that closed for the night -- is refused with the reason on the record and is
NEVER rewritten into a different action.

**The impulse function is the backup.** It still runs at the same tick and its
answer is still recorded beside hers, because two mechanisms answering the same
question is the only way to read either. What it no longer does is decide, so
long as the pick answered: the loop acts on her choice, and falls back to the
score and the roll when the pick is off for this character, was not due, came
back malformed after `api.json_retries`, or was never answered at all. Every
log line says which of the two decided.

**The prompt is the persona's own daily half plus the tools.** The system
message is `persona.system_for("him")` byte for byte -- the same string the
reply path builds, so the provider's cached prefix is shared with it -- the
tool definitions are constant bytes for a character and a kind of moment, and
the moment itself is the last user message and the only part that moves, with
`persona.carried_for()` in it so what she carries here is what she carries
everywhere. Measured over the replay that earned this (`docs/tool-calling.md`
§14): about 11k prompt tokens a call, 61% of them a cache hit, a tenth of a
cent a pick. Nothing goes into her thread: a pick is not something anybody
said (§10).

**The wire.** Native tool calling where the host that serves her takes tools,
and the same question as JSON in her text where it does not -- decided from the
receipt of the last pick, which names the host that actually served it, and
never from a guess about the pin (`api.hosts_without_tools`,
`docs/tool-calling.md` §7). The JSON path goes through `LLM.call_json`, so an
answer that does not parse is asked again `api.json_retries` times and the raw
text is never stored as the decision.

Three faults the replay found, all handled here: a tool name that was not
offered (`dislike`, once), arguments that do not parse, and words coming back in
the wrong language for a character who writes English to him. The first two are
recorded as invalid, are never a pick, and leave the backup to decide; the third
is why every argument that takes words asks for what she is reaching for and
never for a message -- her words are still written by the call that writes her
words.
"""
import json
import time

import logger
from sim import lang, roster, sight, talks, wiring


class PhonePick:
    WIRES = ('state', 'persona', 'impulse', 'receipts', 'phone', 'ledger',
             'director', 'wonder', 'outlook', 'said_today', 'sight')

    # The moments she is asked at. `block` is the start of a stretch her plan
    # gives her a free phone; `scene` is a change of what she is doing inside
    # one; `beat` is something landing from her own people; `inbound` is him
    # writing, where the question is not what to do with the phone but what to
    # do about his message.
    TRIGGERS = ("block", "scene", "beat", "inbound")

    # Every row of the save this writes. `picks` is the record; `pick_block`
    # and `pick_scene` are what has already had its look, so a restart does not
    # ask twice for the same moment; `pick_counts` is the day's cap and
    # `pick_last_ts` the frequency cap; `pick_host` is who served the last one,
    # which is how the transport is chosen; `pick_standing` is her own last
    # answer, which stands until the next moment.
    def __init__(self, config, llm, store, clock, live=True):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.live = bool(live)
        self._tools = {}
        self.last_refusal = ""
        wiring.declare(self)

    def _t(self):
        """The one wording she is addressed in (`sim/lang.py`). Read per call
        so `/lang` moves it without a restart."""
        return lang.say(self.config)

    def live_mode(self):
        """Is what she picks acted on. False is shadow: the call is made, the
        row is written, and the loop proceeds as it did before it existed."""
        c = self.config.pick
        return bool(c.enabled and not c.shadow and self.live)

    # ---------------- what is offered ----------------

    def _has_chat(self):
        ex = self.config.character.existence
        return str(getattr(ex, "with_him", "chat") or "chat").lower() != "none"

    def offered(self, trigger="block"):
        """The tool names this character has a path to at this kind of moment.

        Fixed for a character and a kind of moment, and read from what she IS
        rather than from what this minute holds: a menu that changes with the
        minute costs the cache the tool definitions on every call, and offering
        a group chat to a character with nobody in her world is offering her a
        door into somebody else's house.

        When he has just written, the question is a different one and so are
        the tools. There is no `nothing` on that moment: leaving his message
        where it is has its own name and its own consequence, which is what
        `leave_it` says."""
        ex = self.config.character.existence
        if trigger == "inbound":
            return ["reply_now", "reply_later", "leave_it"] if self._has_chat() else []
        names = ["nothing"]
        if self._has_chat():
            names.append("text_him")
        if getattr(ex, "in_world", True):
            names.append("message_friend")
            # The group chat belongs to whoever keeps the world. A character
            # who only READS one has a circle of her own and one-to-one rooms
            # in it, and no group room of her own to open
            # (`docs/shared-world.md` section 9) -- so offering her a group
            # chat is offering her a door into somebody else's house, and a
            # tool that can only ever be refused is a line she pays for on
            # every call.
            if not getattr(self.config, "world_reader", False):
                names.insert(-1, "open_group_chat")
        if str(getattr(ex, "sees_him", "digest") or "digest").lower() not in ("none", "resident"):
            names.append("look_at_his_machine")
        if getattr(ex, "has_account", True):
            names.append("open_feed")
        return names

    def _rows(self, trigger):
        """(name, what it is, what it costs her, arguments, required) for every
        tool of this kind of moment, in the source order.

        Every description is addressed to HER, so both wordings live here side
        by side behind the language arm, and the one that names how she comes
        to know what he does is the program's (`sim/sight.py`), never this
        module's. Each one says what the tool COSTS her, because a menu of six
        good ideas with no price on any of them is a menu, and a person picks
        the interesting item off a menu every time (`docs/tool-calling.md`
        §14.5)."""
        t = self._t()
        if trigger == "inbound":
            return [
                ("reply_now", t("Answer him now. Whatever you have to say, you say it in the next few "
                                "minutes.",
                                "いま返す。言うことがあるなら、これから数分のうちに言う。"),
                 t("You are in it once you answer, and he will be waiting for the next one.",
                   "返した時点で、あなたはその会話の中にいる。彼は次を待つことになる。"),
                 {}, []),
                ("reply_later", t("Answer, but not yet. Say when.",
                                  "返すけれど、いまではない。いつかを言う。"),
                 t("He sees the message sitting there unanswered until then, and so do you.",
                   "そのときまで、返していないメッセージがそこにある。彼にも、あなたにも見えている。"),
                 {"when": t("when you would answer: a clock time on your own clock, like 21:30, or a "
                            "few words like 'after dinner'",
                            "いつ返すか。21:30 のように自分の時計の時刻でも、「夕飯のあと」のような言葉でもいい")},
                 ["when"]),
                # She does not open it. His end shows delivered and not read,
                # which is a different act from opening it and saying nothing:
                # that one is hers to decide elsewhere (`sim/withholding.py`)
                # and is not on this menu.
                ("leave_it", t("Leave it sitting there for now. You do not open it.",
                               "いまはそのままにしておく。開かない。"),
                 t("It stays unopened and unanswered, and how long that goes on is a thing he can "
                   "see.",
                   "開いていない、返してもいないまま残る。それがどれだけ続くかは、彼にも見えている。"),
                 {}, []),
            ]
        return [
            ("nothing", t("Put the phone down. Nothing here needs you right now. Say roughly how "
                          "long you leave it before you would look again.",
                          "携帯を置く。いまここに、あなたを必要としているものはない。次に手に取るまで"
                          "どれくらい置いておくかを、だいたいで言う。"),
             t("Everything that is waiting is still waiting when you pick it up again.",
               "待っているものは、次に手に取ったときもまだ待っている。"),
             {"until": t("when you would next pick it up: a clock time, or a few words like "
                         "'after dinner'",
                         "次に手に取るのはいつか。時刻でも、「夕飯のあと」のような言葉でもいい")}, []),
            ("text_him", t("Write to him first, without waiting for him to write to you. Say what "
                           "you are reaching for, not the message itself.",
                           "彼から来るのを待たずに、自分から書く。書くメッセージそのものではなく、"
                           "何を求めて書くのかを言う。"),
             t("You started it, so it is his to answer -- and if he leaves it sitting there, you "
               "will be the one who has to live with having gone first.",
               "始めたのはあなたなので、返すかどうかは彼次第になる。そのまま置かれたら、先に行ったのは"
               "自分だったという事実と一緒に過ごすことになる。"),
             {"intent": t("what you want out of writing to him now, in your own words, one line",
                          "いま彼に書くことで何を求めているのか。自分の言葉で一行")}, ["intent"]),
            ("open_group_chat", t("Open the group chat with your friends and join whatever is going "
                                  "on in it.",
                                  "友だちとのグループを開いて、いま流れている話に入る。"),
             t("Once you have said something you are in it, and it will want you for a while.",
               "一度何か言えば、あなたはその中にいる。しばらくのあいだ引っ張られる。"),
             {}, []),
            ("message_friend", t("Write to one of your own people on your own, away from the group.",
                                 "グループとは別に、自分の人のひとりに個別で書く。")
             + self._own_only_line(),
             t("She will answer, and then the conversation is yours to keep up.",
               "相手は返してくる。そこから先の会話は、あなたが続ける番になる。"),
             {"name": t("which of them", "そのうちの誰に") + self._own_names_hint(),
              "intent": t("what you want to say to her, one line",
                          "その人に何を言いたいのか。一行")}, ["name", "intent"]),
            ("look_at_his_machine", t(*sight.w2(self.config, "pick_look_tool")),
             t(*sight.w2(self.config, "pick_look_cost")), {}, []),
            ("open_feed", t("Open your own account and scroll it for a bit.",
                            "自分のアカウントを開いて、少しスクロールする。"),
             t("Time goes while you are in there, and you may come out of it wanting to show him "
               "something.",
               "その中にいるあいだ時間は流れる。出てきたときに、彼に見せたいものを抱えていることもある。"),
             {}, []),
        ]

    def _own_people(self):
        """The people this character may open a room with, as the record names
        them. Empty for the character who keeps her world -- everybody in it is
        hers, and a list of the whole cast in every tool definition would cost
        her the cached prefix for nothing."""
        if not getattr(self.config, "world_reader", False):
            return []
        try:
            return [roster.record_name(self.config, k) for k in roster.own_keys(self.config)]
        except Exception:
            return []

    def _own_names_hint(self):
        """The names the option actually accepts, for a character who reads a
        world she does not keep.

        She was offered the owner's whole cast as people she could write to and
        refused every time she picked one -- the partition rule working exactly
        as written, on a girl who sits next to them at school. Being offered a
        thing you are never allowed to do is how a chooser learns nothing, so
        the option names her own circle and nobody else."""
        names = self._own_people()
        if not names:
            return ""
        t = self._t()
        return t(" -- one of: " + ", ".join(names), "。次のうちのひとり: " + "、".join(names))

    def _own_only_line(self):
        """...and the one sentence saying where the others are talked to."""
        if not getattr(self.config, "world_reader", False):
            return ""
        t = self._t()
        return t(" Only your own people: the rest of them you talk to in the group chat, when you are "
                 "in it.",
                 "書けるのは自分の人だけ。ほかの子たちと話すのはグループの中で、呼ばれたときになる。")

    def _nothing_at(self, rows):
        """Where the do-nothing option sits in the list today.

        It is never first and it is not last every time. A tool that is always
        the last line reads as the fallback the others are alternatives to, and
        the replay's failure mode was a model that never picks the empty option
        (`docs/tool-calling.md` §14.5). It moves once a DAY rather than once a
        call, because the definitions are a cached prefix and a byte that moves
        every call costs the whole of it."""
        n = len(rows)
        if n < 3:
            return 1 if n > 1 else 0
        return 1 + (self.clock.now().toordinal() % (n - 1))

    def tools(self, trigger="block"):
        """The tool definitions for this kind of moment, built once a day per
        kind: constant bytes behind the system half, which is what makes a
        pick a tenth of a cent."""
        key = (trigger, self.clock.now().toordinal(), lang.reads_ja(self.config))
        if key in self._tools:
            return self._tools[key]
        have = set(self.offered(trigger))
        rows = [r for r in self._rows(trigger) if r[0] in have]
        empty = [i for i, r in enumerate(rows) if r[0] == "nothing"]
        if empty:
            row = rows.pop(empty[0])
            rows.insert(min(self._nothing_at(rows) if rows else 0, len(rows)), row)
        t = self._t()
        out = []
        for name, desc, cost, props, req in rows:
            body = desc + " " + t("What it costs you: ", "これを選ぶと: ") + cost
            out.append({"type": "function", "function": {
                "name": name, "description": body,
                "parameters": {"type": "object",
                               "properties": {k: {"type": "string", "description": v}
                                              for k, v in props.items()},
                               "required": list(req)}}})
        self._tools[key] = out
        return out

    # ---------------- the moment ----------------

    def moment(self, trigger="block", now=None, scene=None, digest=None, unread=None):
        """The facts a person with a phone has in front of her, as the last
        user message of the call. No side effects and nothing drawn: the
        stances are entered by the reply path and a pick must not move one."""
        ts = float(now if now is not None else self.clock.now_ts())
        t = self._t()
        if scene is None:
            scene = (getattr(self.director, "current", None) or {}) if self.director else {}
        if digest is None:
            digest = (self.phone.latest_digest() if self.phone else "") or ""
        where, with_who = self._where(scene)
        lines = [self._opening(trigger, unread),
                 t("TIME: ", "時間: ") + self.clock.both_daypart(ts),
                 t("WHERE YOU ARE: ", "いる場所: ") + where,
                 t("WHO IS WITH YOU: ", "一緒にいる人: ") + with_who,
                 t("HOW YOU FEEL: ", "いまの感じ: ") + (self.state.gauge_line() if self.state else "")]
        have = set(self.offered(trigger))
        if self._has_chat():
            lines += ["", t("HIM:", "彼のこと:")]
            # Only what she has a way to act on. A character whose sheet says
            # she cannot see what he does is not handed an account of his
            # afternoon: a section that can only ever say "nothing" is a line
            # she reads and pays for on every call.
            lines += ["- " + x for x in self._him_lines(
                ts, digest if "look_at_his_machine" in have else "")]
            said = self._said_lines(unread)
            if said:
                lines += ["", t("THE LAST OF WHAT THE TWO OF YOU SAID:",
                                "ふたりのあいだで最後にあったやりとり:")]
                lines += said
        if "open_group_chat" in have or "message_friend" in have:
            rooms = self._room_lines()
            lines += ["", t("YOUR OWN PEOPLE:", "自分の人たち:")]
            lines += (["- " + x for x in rooms] if rooms
                      else [t("(nothing new from them)", "（その人たちから新しいものは来ていない）")])
        carrying = self._carrying()
        if carrying:
            lines += ["", carrying]
        lines += ["", self._closing(trigger)]
        return "\n".join(lines)

    def _opening(self, trigger, unread=None):
        """The first line, and it says truthfully what this moment is. A
        moment described as a quiet one with nobody waiting, when he has just
        written, is a moment she is answering a question nobody asked."""
        t = self._t()
        if trigger == "inbound":
            n = len(unread or [])
            return t(f"HE HAS JUST WRITTEN TO YOU ({n} message(s)), AND YOU HAVE NOT ANSWERED YET.",
                     f"彼からいま書いてきた（{n}件）。まだ返していない。")
        if trigger == "beat":
            return t("SOMETHING HAS JUST COME IN FROM YOUR OWN PEOPLE AND THE PHONE IS IN YOUR HAND.",
                     "自分の人たちから何か来たところで、携帯は手の中にある。")
        if trigger == "scene":
            return t("WHAT YOU ARE DOING HAS JUST CHANGED, AND THE PHONE IS IN YOUR HAND.",
                     "していることが変わったところで、携帯は手の中にある。")
        return t("YOUR PHONE IS IN YOUR HAND AND NOBODY IS WAITING ON YOU.",
                 "携帯が手の中にあって、誰もあなたを待っていない。")

    def _closing(self, trigger):
        t = self._t()
        if trigger == "inbound":
            return t("Now decide what you do about his message. Answering it, answering it later and "
                     "leaving it are all real answers; pick the one that is true of you right now.",
                     "では、彼のメッセージをどうするか決める。いま返す、あとで返す、そのままにしておく、"
                     "どれも本当の答えになる。いまの自分に本当のものを選ぶ。")
        return t("Now decide what you actually do with the phone, if anything. Doing nothing is a "
                 "real answer and not the leftover one; pick what is true of you right now.",
                 "では、この携帯で実際に何をするか決める。何もしないというのも、余りものではなく本当の"
                 "答えのひとつ。いまの自分に本当のものを選ぶ。")

    def _where(self, scene):
        """Where she is and with whom, from the day's one truth: the scene the
        director wrote if there is one, else the block her plan settled
        (`sim/ledger.py`)."""
        t = self._t()
        blk, people = (None, [])
        if self.ledger:
            try:
                blk, people = self.ledger.where()
            except Exception:
                blk, people = None, []
        loc = str(scene.get("location") or (blk or {}).get("location") or "")
        act = str(scene.get("activity") or (blk or {}).get("activity") or "")
        who = str(scene.get("with") or scene.get("with_who") or "").strip()
        if not who:
            who = ", ".join(people)
        return (f"{loc}: {act}".strip(": "),
                who or t("alone", "ひとり"))

    def _him_lines(self, ts, digest):
        """His side as the record has it: his last message, what her own last
        one has done since, how long he has been quiet, and what her sight of
        his machine last showed. The read-and-said-nothing sentence is
        `Receipts.line`, the one her reply already reads, so the pick and the
        reply cannot describe his silence two different ways."""
        t = self._t()
        ja = lang.reads_ja(self.config)
        out = []
        his = self.store.last_message("user")
        hers = self.store.last_message("assistant")
        if his:
            hours = max(0.0, (ts - float(his["ts"])) / 3600.0)
            when = self.clock.to_char(float(his["ts"])).strftime("%Y-%m-%d %H:%M")
            out.append(t(f"his last message, {when} your time ({hours:.1f}h ago): ",
                         f"彼の最後のメッセージ、あなたの時間で{when}（{hours:.1f}時間前）: ")
                       + '"' + " ".join(str(his["text"] or "").split())[:300] + '"')
            out.append(t(f"he has been quiet for {hours:.1f} hours",
                         f"彼は{hours:.1f}時間、何も言ってきていない"))
        else:
            out.append(t("he has never written to you", "彼から書いてきたことは一度もない"))
        if self.receipts:
            try:
                line = self.receipts.line(self.receipts.status(), ja=ja)
            except Exception:
                line = ""
            if line:
                out.append(line)
        if hers:
            when = self.clock.to_char(float(hers["ts"])).strftime("%Y-%m-%d %H:%M")
            out.append(t(f"your own last message, {when}: ", f"あなた自身の最後のメッセージ、{when}: ")
                       + '"' + " ".join(str(hers["text"] or "").split())[:200] + '"')
        if digest:
            out.append(" ".join(str(digest).split())[:1200])
            # He is at the machine and she is not what is in front of him. She
            # sees this herself (`resident/sight.py:attention_observation`), and
            # the moment she decides at has to carry it: the digest is what he
            # did, and this is that he is doing it now with her nowhere in it.
            # Only when she has a way to see his machine at all (`digest` is
            # handed in on that same condition).
            sg = getattr(self, "sight", None)
            if sg is not None and hasattr(sg, "attention_observation"):
                try:
                    obs = sg.attention_observation() or {}
                    why = str(obs.get("reason") or "").strip()
                    if why:
                        out.append(t("what his machine is showing right now: ",
                                     "いま彼のマシンに見えているもの: ") + why)
                except Exception:
                    pass
        return out

    def _said_lines(self, unread=None):
        """The last few turns between the two of them, stamped on her clock.

        The pick's system half is her daily one and carries no history at all,
        so without this she decides what to do about a conversation she cannot
        see. It is read out of the record rather than out of `sim/thread.py`:
        the thread is rebuilt byte-identical for the calls that write her
        words, and a second reader of it here would be a second thing that can
        move those bytes."""
        t = self._t()
        try:
            msgs = list(self.store.recent_messages(8) or [])
        except Exception:
            return []
        out = []
        for m in msgs[-6:]:
            who = t("you: ", "あなた: ") if m["role"] == "assistant" else t("him: ", "彼: ")
            hm = self.clock.to_char(float(m["ts"])).strftime("%H:%M")
            out.append(f"  [{hm}] {who}" + " ".join(str(m.get("text") or "").split())[:200])
        if unread:
            out.append(t("  (the last of those is what you have not answered)",
                         "  （そのうち最後のものが、まだ返していないもの）"))
        return out

    def _room_lines(self):
        """What has been said in her own rooms that she has not answered.

        Read through `sim/talks.py`, which is the record of her rooms without
        either engine behind it: a character with no cast and no peers simply
        has none, and nothing here imports a program."""
        t = self._t()
        out = []
        for rec in talks.all_rows(self.store)[-12:]:
            turns = list(rec.get("turns") or [])
            if not turns:
                continue
            theirs = [x for x in turns if not roster.is_self(self.config, x.get("who"))]
            if not theirs:
                continue
            after = []
            for x in reversed(turns):
                if roster.is_self(self.config, x.get("who")):
                    break
                after.append(x)
            if not after:
                continue
            last = " ".join(str(after[0].get("ja") or after[0].get("text") or "").split())[:120]
            who = str(rec.get("who") or rec.get("room") or "")
            kind = str(rec.get("kind") or "")
            out.append(t(f"{who} ({kind}), last at {rec.get('hm')}: {len(after)} message(s) since you "
                         f"last said anything -- ",
                         f"{who}（{kind}）、最後は{rec.get('hm')}: あなたが何か言ってから{len(after)}件 -- ")
                       + f'"{last}"')
        return out[-5:]

    def _carrying(self):
        """What she carries into this moment: the one block both her rooms
        already place after the thread (`persona.carried_for`), plus the two
        things that are about to be said and have not been -- something off
        her own feed she meant to show him, and what she woke up wanting.

        The same block, so a fact she is holding in her reply is a fact she is
        holding here. It is built after the system half and under the same
        peek, so nothing is drawn and no forgetting curve is charged."""
        t = self._t()
        ja = lang.reads_ja(self.config)
        out = []
        try:
            block = self.persona.carried_for() if self.persona else ""
        except Exception as e:
            logger.log(f"[pick] what she carries was not built: {type(e).__name__}: {e}")
            block = ""
        extra = []
        if self.wonder and self.config.wonder.enabled:
            try:
                for q in sorted(self.wonder.open(), key=lambda r: -float(r.get("ts") or 0))[:3]:
                    extra.append(t("a question about him you have not asked: ",
                                   "彼について訊けていないこと: ") + str(q.get("text") or "")[:160])
            except Exception:
                pass
        # what she has already been to each of them with today, across rooms,
        # and who is off the list because she went and had nothing to say
        # (`sim/said_today.py`). Without it the same want was offered at every
        # opportunity all evening and taken four times.
        if self.said_today:
            try:
                extra += self.said_today.lines_for_pick()
                extra += self.said_today.cool_lines()
            except Exception as e:
                logger.log(f"[pick] what she has already said today was not read: "
                           f"{type(e).__name__}: {e}")
        aside = self.store.get("pick_aside") or {}
        if isinstance(aside, dict) and str(aside.get("text") or "").strip():
            try:
                hours = (self.clock.now_ts() - float(aside.get("ts") or 0)) / 3600.0
            except (TypeError, ValueError):
                hours = 99.0
            if 0 <= hours <= 3:
                hm = self.clock.hm(float(aside.get("ts") or 0))
                extra.append(t(f"what you were thinking when you were last asked ({hm}): ",
                               f"前に訊かれたとき（{hm}）に考えていたこと: ")
                             + str(aside.get("text") or "")[:400])
        show = self.store.get("x_show_pending") or {}
        if isinstance(show, dict) and show.get("mention"):
            extra.append(t("something off your feed you wanted to show him: ",
                           "彼に見せようと思っていたもの: ") + str(show["mention"])[:160])
        if self.outlook:
            try:
                line = self.outlook.morning_line(ja=ja)
            except Exception:
                line = ""
            if line:
                extra.append(line)
        if block:
            out.append(block)
        if extra:
            out.append(t("WHAT YOU ARE CARRYING AND HAVE NOT SAID:", "抱えていて、まだ言っていないもの:"))
            out += ["- " + x for x in extra]
        return "\n".join(out)

    # ---------------- when it runs ----------------

    def block_key(self, schedule=None):
        """Which block of her plan she is in, as one string. This is what "the
        same block" means across a restart."""
        from sim import schedule as sched
        s = schedule or self.store.get_schedule(self.clock.date_str())
        blocks = (s or {}).get("blocks") or []
        if not blocks:
            return f"{self.clock.date_str()}|no-plan", None
        blk = sched.block_at(blocks, self.clock.now())
        return f"{self.clock.date_str()}|{blk.get('start')}", blk

    def scene_key(self, scene):
        """Which scene she is in, as one string: what she is doing and where,
        so a director tick that rewrote the same activity is not a new moment."""
        scene = scene or {}
        return "|".join(str(scene.get(k) or "")[:40] for k in ("hm", "location", "activity"))

    def due(self, trigger, access, schedule=None, scene=None):
        """(ok, why, trigger). Every gate code keeps, in one place.

        `access` is what her phone access reads right now -- the App's own
        answer, so a resident with no plan to be away from is judged by whether
        she is awake and a schoolgirl by her block. The trigger a caller asks
        with is what it knows; a loop pass asks with `block` and is told
        `scene` when the block has already had its look and what she is doing
        has moved since."""
        c = self.config.pick
        if not c.enabled:
            return False, "off", trigger
        if not self.live:
            return False, "not live (a sim or a replay)", trigger
        if not bool(getattr(c.moments, trigger, False)):
            return False, f"the {trigger} moment is switched off", trigger
        if not self.offered(trigger):
            return False, "she has no tool at this kind of moment", trigger
        if access != "free":
            return False, f"phone {access}", trigger
        today = self.clock.date_str()
        n = self.store.today_count("pick_counts", today)
        if n >= int(c.max_per_day):
            return False, f"the day's cap ({n}/{int(c.max_per_day)})", trigger
        now = self.clock.now_ts()
        gap = float(getattr(c, "min_gap_minutes", 0) or 0)
        since = (now - float(self.store.get("pick_last_ts") or 0)) / 60.0
        if gap > 0 and since < gap:
            return False, f"{since:.0f} min since her last look, {gap:.0f} needed", trigger
        if trigger in ("inbound", "beat"):
            return True, f"{trigger} moment", trigger
        key, _blk = self.block_key(schedule)
        if self.store.get("pick_block") != key:
            return True, key, "block"
        skey = self.scene_key(scene if scene is not None else
                              ((getattr(self.director, "current", None) or {}) if self.director else {}))
        if bool(getattr(c.moments, "scene", False)) and skey and self.store.get("pick_scene") != skey:
            return True, skey, "scene"
        return False, "already looked at this moment", trigger

    def standing(self):
        """Her own last answer, while it still stands.

        A moment has ONE decider. Between one pick and the next, what she
        decided is what holds -- so the impulse function does not quietly write
        to him twenty minutes after she put the phone down, which is the
        behaviour this replaces rather than the backup for it."""
        r = self.store.get("pick_standing") or {}
        if not isinstance(r, dict) or not r.get("name"):
            return None
        return r

    def holds(self):
        """Does her own last answer still stand at this tick, so code's own
        answer must not act over it.

        It stands while the only reason she was not asked again is that this is
        the same moment or too soon after the last one. When she was not asked
        because the day's cap is spent, because the phone is away or because the
        section is off, she is not being asked any more and the backup is what
        decides -- otherwise one `nothing` in the morning would silence her for
        the rest of the day."""
        if not self.live_mode() or not self.standing():
            return False
        why = self.last_refusal or ""
        if not (why.startswith("already looked") or "since her last look" in why):
            return False
        # And only while the moment she answered is still the current one. A
        # block is not a moment: the pick is asked at the top of a block and its
        # `nothing` used to stand for the whole hour, so the impulse's answer --
        # which is asked every pass and can change while the block runs -- never
        # got to act inside it. The pick's own minimum gap is how long a moment
        # lasts; past it her earlier pass stops vetoing the backup's answer.
        gap = float(getattr(self.config.pick, "min_gap_minutes", 0) or 0)
        since = (self.clock.now_ts() - float(self.store.get("pick_last_ts") or 0)) / 60.0
        return since < gap

    # ---------------- the call ----------------

    def ask(self, trigger, access="free", scene=None, digest=None, impulse=None,
            schedule=None, unread=None):
        """One call, one answer, written to the save the moment it exists.

        Returns the row, or None when this was not a moment to ask at, when the
        call was never answered, or when nothing that came back was a pick --
        which are the three cases the backup exists for. `impulse` is what the
        impulse function answered at this same tick, passed in rather than
        asked again: `Impulse.check` rolls a die, and a second call would be a
        second roll and a different answer from the one being recorded."""
        ok, why, trigger = self.due(trigger, access, schedule, scene)
        self.last_refusal = "" if ok else why
        if not ok:
            return None
        key = why
        # The scene is resolved ONCE and handed to both the moment and the
        # row: `_where` off an empty scene falls back to the plan's block, so
        # asking twice put "school, first period" in the moment and "home,
        # breakfast" in the row for the same minute.
        if scene is None:
            scene = (getattr(self.director, "current", None) or {}) if self.director else {}
        try:
            self.persona._peek = True
            system = self.persona.system_for("him")
            moment = self.moment(trigger, scene=scene, digest=digest, unread=unread)
        except Exception as e:
            logger.log(f"[pick] her prompt could not be built: {type(e).__name__}: {e}")
            return None
        finally:
            self.persona._peek = False
        # This moment has had its look, and the day's count is spent, BEFORE
        # the call goes out: a stop is a kill, and a marker written afterwards
        # would let a restart ask the same moment again on the next tick.
        if trigger == "block":
            self.store.set("pick_block", key)
        elif trigger == "scene":
            self.store.set("pick_scene", key)
        self.store.bump_today("pick_counts", self.clock.date_str())
        self.store.set("pick_last_ts", self.clock.now_ts())
        tools = self.tools(trigger)
        transport = self._transport()
        got = (self._ask_tools(system, moment, tools) if transport == "tools"
               else self._ask_json(system, moment, tools))
        if got is None:
            logger.log(f"[pick] no answer at the {trigger} moment; the call is missed and the "
                       f"backup decides")
            return None
        if got.get("served_by"):
            self.store.set("pick_host", str(got["served_by"]))
        if transport == "tools" and not (got.get("calls") or []) \
                and str(got.get("served_by") or "") in self._no_tools_hosts():
            # The pin fell through to a host that takes the request and drops
            # the tools (`docs/tool-calling.md` §7). That is the host and not
            # her, and the receipt is what says so.
            logger.log(f"[pick] {got.get('served_by')} answered without a tool call and does not take "
                       f"tools; asking the same moment as text")
            transport = "json"
            got = self._ask_json(system, moment, tools) or got
        picks = [self.validate(c, trigger) for c in got.get("calls") or []]
        # Her reasoning arrives beside the pick often enough to be worth
        # asking again for the choice and worth keeping the reasoning: on
        # 2026-09-08 five of twenty-two moments came back as prose with no
        # usable choice, and one of them was the best interior writing of
        # the day -- sixteen hours with no answer, the decision she made at
        # breakfast, the dry cleaning to fetch. It was logged as dropped
        # and dropped.
        aside = str(got.get("text") or "").strip()
        spent = float((got.get("usage") or {}).get("cost") or 0)
        asked_again = False
        if not [p for p in picks if not p["invalid"]]:
            asked_again = True
            t = self._t()
            line = (t("Answer with one tool call and nothing else.",
                      "ツールコールひとつだけで答える。それ以外は書かない。") if transport == "tools"
                    else t("Answer with one JSON object and nothing else.",
                           "JSONオブジェクトをひとつだけ、それ以外は書かずに答える。"))
            logger.log("[pick] asked again for a choice")
            more = (self._ask_tools(system, moment, tools, again=line) if transport == "tools"
                    else self._ask_json(system, moment, tools, again=line))
            if more:
                spent += float((more.get("usage") or {}).get("cost") or 0)
                txt = str(more.get("text") or "").strip()
                if txt:
                    aside = (aside + "\n" + txt).strip()
                p2 = [self.validate(c, trigger) for c in more.get("calls") or []]
                if [p for p in p2 if not p["invalid"]]:
                    picks = p2
                    got = more
                    if more.get("served_by"):
                        self.store.set("pick_host", str(more["served_by"]))
        if aside:
            # one row, overwritten, read by the next moment inside three
            # hours of her clock and by nothing else: it is what she was
            # thinking, not something she said, so it goes nowhere near her
            # diary or her private thoughts
            self.store.set("pick_aside", {"ts": self.clock.now_ts(), "text": aside[:1200]})
        u = got.get("usage") or {}
        # `ts` is machine local, like every stamp written anywhere; `world_ts`
        # is the same instant on the clock her messages are stamped on, which
        # is what `_outcome` compares the record against. The two are equal in
        # a live run and only a harness can pull them apart.
        row = {"ts": time.time(), "world_ts": self.clock.now_ts(),
               "character": str(getattr(self.config.character, "name", "") or ""),
               "date": self.clock.date_str(), "block": key, "trigger": trigger,
               "her": self.clock.now().strftime("%Y-%m-%d %H:%M"),
               "his": self.clock.user_now().strftime("%Y-%m-%d %H:%M"),
               "access": access, "where": self._where(scene)[0],
               "moment": moment, "picks": picks,
               "invalid": any(p["invalid"] for p in picks),
               "offered": self.offered(trigger), "impulse": impulse or {},
               "text": aside[:400],
               "mode": "live" if self.live_mode() else "shadow",
               "transport": transport,
               "min_gap_minutes": float(getattr(self.config.pick, "min_gap_minutes", 0) or 0),
               "acted": "", "acted_why": "", "fallback": "", "fallback_why": "",
               "asked_again": asked_again,
               "cost": round(spent, 6),
               "prompt_tokens": u.get("prompt_tokens"),
               "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
               "model": str(got.get("model") or ""),
               "served_by": got.get("served_by"), "finish": got.get("finish")}
        self._write(row)
        d = self.decision(row)
        logger.log(f"[pick] {row['mode']} at the {trigger} moment -- she picks: "
                   + (self.brief(picks) or "(no call at all)")
                   + f" | impulse: {self._impulse_brief(impulse)}"
                   + f" | {row['where']} | via {transport} | ${row['cost']:.5f}")
        if row["text"]:
            # The system prompt is her whole persona and nothing in the call
            # says what the answer is for, so the model sometimes writes her
            # reasons beside the pick. They are her reasons and not a
            # message: kept for the next moment, and out of every other role.
            logger.log(f"[pick] {len(row['text'])} characters of her reasoning came back beside "
                       f"the pick; kept for the next moment")
        if d is None:
            self.note_acted(row, "", "", fallback="code's own answer",
                            fallback_why="nothing that came back was a pick")
            logger.log("[pick] nothing that came back was a pick; the backup decides")
            return None
        self.store.set("pick_standing", {"ts": row["world_ts"], "name": d["name"],
                                         "trigger": trigger,
                                         "arguments": d.get("arguments") or {}})
        return row

    def _ask_tools(self, system, moment, tools, again=""):
        """Native tool calling: the answer is a call, and the client hands back
        what the model named without deciding what exists.

        `again` is the one line added when the first answer carried no
        choice at all -- the same moment, asked once more. That second ask
        FORCES a call (`tool_choice="required"`): the retry exists because the
        model wrote her reasons in prose instead of calling anything, and
        asking again in the same way asked for the same prose. Measured
        2026-09-17 on the pin (together/Together, deepseek-v4-flash): with
        `auto` the retry came back empty again; with `required` the call always
        arrives. There is always a tool to pick -- the do-nothing one is in the
        list -- so a forced call cannot trap her."""
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": moment}]
        if again:
            msgs.append({"role": "user", "content": again})
        return self.llm.call_tools("pick", msgs, tools,
                                   tool_choice=("required" if again else "auto"))

    def _ask_json(self, system, moment, tools, again=""):
        """The same question in her text, for a host that does not take tools.

        `LLM.call_json` is the whole of the difference: an answer that does not
        parse is asked again `api.json_retries` times with the bad answer in
        the conversation, and the raw text is never stored as the decision. The
        answer is shaped like the client's tool answer so `validate` and the
        record cannot tell the two apart."""
        t = self._t()
        names = ", ".join(x["function"]["name"] for x in tools)
        spec = []
        for x in tools:
            f = x["function"]
            args = (f["parameters"].get("properties") or {})
            spec.append(f"- {f['name']}: {f['description']}"
                        + (("\n  " + t("arguments: ", "引数: ")
                            + "; ".join(f"{k} -- {v['description']}" for k, v in args.items()))
                           if args else ""))
        ask = (moment + "\n\n" + t("Answer with one JSON object and nothing else: ",
                                   "JSONオブジェクトをひとつだけ、それ以外は書かずに答える: ")
               + '{"do": "<' + names + '>", "arguments": {...}}\n'
               + t("What each one is:", "それぞれの意味:") + "\n" + "\n".join(spec))
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": ask}]
        if again:
            msgs.append({"role": "user", "content": again})
        data, _raw = self.llm.call_json("pick", msgs)
        if data is None:
            return None
        u = dict(getattr(self.llm, "last_usage", None) or {})
        name = str(data.get("do") or data.get("tool") or data.get("name") or "")
        args = data.get("arguments")
        prov = getattr(self.llm, "last_provider", None) or ("", "")
        return {"calls": ([{"id": "", "name": name,
                            "arguments": args if isinstance(args, dict) else None,
                            "raw": json.dumps(data, ensure_ascii=False)[:300]}] if name else []),
                "text": "", "finish": "json", "usage": u,
                "served_by": prov[1] if len(prov) > 1 else "", "model": u.get("model") or ""}

    def _no_tools_hosts(self):
        """The hosts that take a request carrying tools and answer as if none
        were offered, as OpenRouter's own endpoint list has them
        (`docs/tool-calling.md` §7). Spelled as the RECEIPT spells them."""
        return {str(x).strip() for x in (getattr(self.config.api, "hosts_without_tools", []) or [])}

    def _transport(self):
        """Native tool calling, or the same question as text.

        Decided from the receipt of the last pick -- which host actually served
        it -- and never from a guess about the pin, because the pinned host may
        fail through to another for the same slug and only the receipt knows
        which one answered."""
        host = str(self.store.get("pick_host") or "")
        if host and host in self._no_tools_hosts():
            return "json"
        return "tools"

    def _write(self, row):
        rows = list(self.store.get("picks", []) or [])
        rows.append(row)
        self.store.set("picks", rows[-200:])

    def note_acted(self, row, acted, why="", fallback="", fallback_why=""):
        """What the seam did, written AFTER it did it.

        The decision row goes to the save the moment the answer exists, with no
        claim about what happened; this fills that in once the action is on the
        record. Nothing here may be written before the thing it says happened
        (`reconcile.py`)."""
        if not row:
            return
        rows = list(self.store.get("picks", []) or [])
        for r in reversed(rows):
            if float(r.get("ts") or 0) == float(row.get("ts") or 0):
                r["acted"], r["acted_why"] = str(acted), str(why)[:200]
                r["fallback"], r["fallback_why"] = str(fallback), str(fallback_why)[:200]
                row.update({"acted": r["acted"], "acted_why": r["acted_why"],
                            "fallback": r["fallback"], "fallback_why": r["fallback_why"]})
                break
        self.store.set("picks", rows[-200:])

    def decision(self, row):
        """The one call that is acted on: the first valid one.

        Several calls arrive in one answer even though `parallel_tool_calls` is
        never sent (`docs/tool-calling.md` §14.2). Acting on all of them would
        be two things happening in the same minute because the model listed
        two; the first valid one is the decision and the rest are on the record
        and said in the log."""
        picks = [p for p in (row or {}).get("picks") or [] if not p.get("invalid")]
        if not picks:
            return None
        if len(picks) > 1:
            logger.log("[pick] the answer carried " + str(len(picks)) + " picks ("
                       + ", ".join(p["name"] for p in picks) + "); the first is the one she does")
        return picks[0]

    def validate(self, call, trigger="block"):
        """One returned call against the whitelist of offered names and that
        tool's own arguments. A name nobody offered and arguments that do not
        parse are recorded as invalid and are never a pick: the library hands
        back what the model said, and deciding what exists is the program's."""
        name = str(call.get("name") or "")
        args = call.get("arguments")
        out = {"name": name, "arguments": {}, "invalid": False, "why": ""}
        spec = {t["function"]["name"]: t["function"]["parameters"] for t in self.tools(trigger)}
        if name not in spec:
            out["invalid"] = True
            out["why"] = "no such tool was offered"
            out["raw"] = str(call.get("raw") or "")[:300]
            return out
        if not isinstance(args, dict):
            out["invalid"] = True
            out["why"] = "the arguments did not parse as an object"
            out["raw"] = str(call.get("raw") or "")[:300]
            return out
        props = spec[name].get("properties") or {}
        missing = [k for k in (spec[name].get("required") or []) if not str(args.get(k) or "").strip()]
        if missing:
            out["invalid"] = True
            out["why"] = f"{', '.join(missing)} missing"
        extra = [k for k in args if k not in props]
        if extra:
            out["why"] = (out["why"] + "; " if out["why"] else "") + f"{', '.join(extra)} ignored"
        out["arguments"] = {k: str(v)[:300] for k, v in args.items() if k in props}
        return out

    # ---------------- reading it back ----------------

    @staticmethod
    def brief(picks):
        out = []
        for p in picks:
            args = json.dumps(p.get("arguments") or {}, ensure_ascii=False)
            out.append(f"{p['name']} {args}" + (f" [INVALID: {p['why']}]" if p["invalid"] else ""))
        return "; ".join(out)

    @staticmethod
    def _impulse_brief(imp):
        if not imp:
            return "not asked at this tick"
        s = f"{imp.get('fires')} ({imp.get('why')})"
        if imp.get("score") is not None:
            s += f", score {imp['score']:.0f}/{imp.get('threshold')}"
        return s

    def rows(self, date=None):
        rows = list(self.store.get("picks", []) or [])
        return [r for r in rows if not date or r.get("date") == date]

    def _outcome(self, row):
        """What the record shows happened after the pick, in the same block:
        she sent something, a room opened, or nothing. Read off the store, so
        it says only what is on the record."""
        try:
            key = str(row.get("block") or "")
            date = key.split("|")[0] if "|" in key else str(row.get("date") or "")
            start = key.split("|")[1] if "|" in key else ""
            blocks = (self.store.get_schedule(date) or {}).get("blocks") or []
            end = next((b.get("end") for b in blocks if str(b.get("start")) == start), "24:00")
        except Exception:
            return "unknown"
        out = []
        try:
            lo = float(row.get("world_ts") or row["ts"])
            msgs = [m for m in self.store.messages_for_date(date) or []
                    if m["role"] == "assistant" and float(m["ts"]) >= lo]
            if any(m["self_started"] for m in msgs):
                out.append("she wrote to him first")
            elif msgs:
                out.append("she answered him")
            for rec in talks.all_rows(self.store):
                if str(rec.get("date")) == date and start <= str(rec.get("hm") or "") < str(end):
                    out.append(f"a room opened with {rec.get('who')}")
                    break
        except Exception:
            return "unknown"
        return ", ".join(out) or "nothing"

    def report(self, arg=""):
        """`/pick [date]`: the day's moments -- how many she was offered, what
        she took, what was acted on, where the backup ran and why, and where
        she and the impulse function disagreed."""
        c = self.config.pick
        arg = str(arg or "").strip()
        date = arg if len(arg) == 10 and arg[:4].isdigit() else self.clock.date_str()
        n = int(arg) if arg.isdigit() else 10
        rows = self.rows(date)
        mode = ("off" if not c.enabled
                else "LIVE -- what she picks is done" if self.live_mode()
                else "shadow -- logged, nothing acted on")
        head = (f"pick {date}: {mode} | {len(rows)}/{int(c.max_per_day)} today, "
                f"no two looks inside {float(getattr(c, 'min_gap_minutes', 0) or 0):.0f} min "
                f"| {len(self.offered())} tool(s): {', '.join(self.offered())}")
        if not rows:
            return head + "\n(no pick on that day)"
        by_tool, by_trigger, acted, fallbacks, disagree, invalid = {}, {}, 0, {}, 0, 0
        for r in rows:
            by_trigger[r.get("trigger", "?")] = by_trigger.get(r.get("trigger", "?"), 0) + 1
            for p in r.get("picks") or []:
                k = p["name"] + (" [invalid]" if p.get("invalid") else "")
                by_tool[k] = by_tool.get(k, 0) + 1
            if r.get("invalid"):
                invalid += 1
            if r.get("acted"):
                acted += 1
            if r.get("fallback"):
                fallbacks[r["fallback"]] = fallbacks.get(r["fallback"], 0) + 1
            picked_him = any(p["name"] in ("text_him", "reply_now") and not p["invalid"]
                             for p in r.get("picks") or [])
            if bool((r.get("impulse") or {}).get("fires")) != picked_him:
                disagree += 1
        out = [head, ""]
        out.append("moments: " + ", ".join(f"{k} {v}" for k, v in sorted(by_trigger.items())))
        out.append("picked:  " + (", ".join(f"{k} {v}" for k, v in sorted(by_tool.items())) or "nothing at all"))
        out.append(f"acted on: {acted} of {len(rows)}"
                   + (f" | the backup ran: " + ", ".join(f"{k} {v}" for k, v in sorted(fallbacks.items()))
                      if fallbacks else "")
                   + f" | answers with something invalid in them: {invalid}")
        out.append(f"she and the impulse function differ about writing to him on {disagree} of {len(rows)}")
        for r in rows[-n:]:
            out.append("")
            out.append(f"{r.get('her')} her time ({r.get('his')} his) | {r.get('trigger')} | "
                       f"{r.get('where')}")
            out.append(f"  she picks: {self.brief(r.get('picks') or []) or '(no call at all)'}")
            out.append(f"  impulse:   {self._impulse_brief(r.get('impulse'))}")
            out.append(f"  done:      {r.get('acted') or '(nothing acted on)'}"
                       + (f" -- {r['acted_why']}" if r.get("acted_why") else ""))
            if r.get("fallback"):
                out.append(f"  backup:    {r['fallback']} -- {r.get('fallback_why', '')}")
            out.append(f"  after it, on the record: {self._outcome(r)}")
            out.append(f"  ${float(r.get('cost') or 0):.5f}, {r.get('prompt_tokens')} prompt tokens "
                       f"({r.get('cached_tokens')} cached), {r.get('transport')} via {r.get('served_by')}")
        spent = sum(float(r.get("cost") or 0) for r in rows)
        out.append("")
        out.append(f"{date}: ${spent:.4f}")
        return "\n".join(out)

    def ops(self):
        """The operator payload's own entry: today's counts and the last pick."""
        today = self.clock.date_str()
        rows = self.rows(today)
        last = (self.rows() or [None])[-1]
        by_tool = {}
        for r in rows:
            for p in r.get("picks") or []:
                if not p.get("invalid"):
                    by_tool[p["name"]] = by_tool.get(p["name"], 0) + 1
        return {"enabled": bool(self.config.pick.enabled),
                "mode": "live" if self.live_mode() else "shadow",
                "today": len(rows), "cap": int(self.config.pick.max_per_day),
                "min_gap_minutes": float(getattr(self.config.pick, "min_gap_minutes", 0) or 0),
                "offered": self.offered(), "picked_today": by_tool,
                "acted_today": len([r for r in rows if r.get("acted")]),
                "fallbacks_today": len([r for r in rows if r.get("fallback")]),
                "spent_today": round(sum(float(r.get("cost") or 0) for r in rows), 5),
                "last": None if not last else {
                    "her": last.get("her"), "trigger": last.get("trigger"),
                    "picked": self.brief(last.get("picks") or []),
                    "acted": last.get("acted"), "fallback": last.get("fallback"),
                    "impulse": self._impulse_brief(last.get("impulse")),
                    "where": last.get("where"), "invalid": bool(last.get("invalid"))}}

    def boot_line(self):
        c = self.config.pick
        if not c.enabled:
            return "[pick] off: the impulse function decides whether she writes to him first"
        when = ", ".join(k for k in self.TRIGGERS if bool(getattr(c.moments, k, False)))
        tools = ", ".join(self.offered())
        extra = self.offered("inbound")
        if extra:
            tools += "; when he has just written: " + ", ".join(extra)
        if self.live_mode():
            return (f"[pick] LIVE: she decides what she does with the phone at these moments ({when}); "
                    f"code does what she picks and the impulse function is the backup. Cap "
                    f"{int(c.max_per_day)} a day, no two looks inside "
                    f"{float(getattr(c, 'min_gap_minutes', 0) or 0):.0f} min. Tools: {tools}")
        return (f"[pick] shadow mode: the pick runs at these moments ({when}), logs what she would do "
                f"and changes nothing; cap {int(c.max_per_day)} a day, no two looks inside "
                f"{float(getattr(c, 'min_gap_minutes', 0) or 0):.0f} min. Tools: {tools}")
