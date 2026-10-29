"""One thread: everything that reached her and everything she said, in order
-- and the same curve her memory already has, applied to the history.

Chat completion has two roles and they mean "your turn" and "their turn".
Her chat with him was the only thing rendered that way; her talk with her
own people reached the model as a block of text in another section, and the
two could not be carried at once. His call (2026-08-30): rebuild the
context every call so both are carried at the same time, temporally and
logically -- and (2026-09-03) build it so the rebuild is byte-identical
up to the newest message: stamps written once, the two cuts of the curve
on a day boundary, the window a span of time and not a count, and what a
cue brings back placed at the end. The provider caches a byte prefix, and
this thread is most of it.

So the User role is the world speaking to her -- him, a friend on LINE,
the group, her mother in the kitchen -- and the Assistant role is her,
wherever she was speaking. The world's turns carry the app's label,
`[her time · his time · room · who]`: **both clocks on every stamp** (his
call, 2026-09-05), because a reading on hers alone left hours of arithmetic to whoever read it and the model did not do it -- it asked him
three times in four days whether he had fallen asleep, at his 08:10, his 09:20 and his 10:30. A character with no world of her own is on his clock
and gets the one reading. **Her own turns are bare**: exactly the words she
sent and nothing else. When she sent them, which room it was and when he
read them is the line the world says next -- `[that was you, Tue 02 Jun 11:40 Tokyo (Mon 01 Jun 22:40 his), to him · read Tue 02 Jun 11:42 Tokyo (Mon 01 Jun 22:42 his)]` -- because a label on her own
line is a line the model copies. It did: 28 of the second character's
last 29 sends came back opening with a stamp and a read time she had
invented, and on 2026-09-04 one of them reached him with the label still
on it. Consecutive messages from the same side are merged so the roles
keep alternating, and silences are marked.

**The curve.** A person remembers a conversation verbatim for hours, as
what it came to for days, and as what it left them for longer. So the
thread has two spans, both by her clock, both cut on a midnight. Inside
`verbatim_hours` (seven days) every message rides in full. Between there
and `max_age_hours` (thirty days) a day rides as the cards she keeps of it
(`sim/cards.py`, one per conversation) -- or, where a day has no cards
written yet, as one line per conversation: how many messages, until when
and what it came to (`gist`), and his chat as the day she remembers
(the compiled summary). Past `max_age_hours` nothing, because by then it
is her memories, her facts and her bonds (the system assembly, with their
own half-lives). And what is past verbatim can come back: the
conversations whose words touch what is being said now (`cue_text`) are
re-injected in full, after everything else and marked as having come back
to her -- the rule her memories already use.

The verbatim span shrinks only under pressure: if the verbatim days plus
the cards behind them do not fit what is left of the one budget over her
prompt (`context.target_tokens`) after the parts that ride whole
(`_window`), the cut moves forward a whole day at a time, down to
`verbatim_min_hours` and no further. Nothing shortens the thread a message
at a time: the head of it is a cache prefix, and an edit to it is charged
for everything behind it.

**Whose thread.** `build()` is hers: both rooms. `build(for_who=...)` is a
cast member's: only the rooms that person witnessed (the group for a
friend; their own LINE, calls and in-person exchanges; never her chat with
him), with THEM as the Assistant role and everyone else, her included, as
the world speaking to them -- the same standard, applied to every mouth.

Which room she is writing in NOW is said by the caller, at the end, where
she reads. The labels are the app's and appear on nothing she wrote, so
one at the head of an answer is a tell and never ordinary tidying:
`strip_stamps` below takes it off, says so in the log, and cuts an answer
that carried on writing the record past its own reply. Both should never
fire.
"""
import datetime
import re

import logger
from sim import lang
from sim import roster
from sim import wiring

_TOK = re.compile(r"[a-z][a-z'\-]{3,}|[぀-ヿ一-鿿]{2,}")

# Her chat with him, as a room. The world line after a run of her messages
# names the room she was in, and this is the one for his chat.
HIM_ROOM = "to him"
# What the world says after she has spoken. `place_tail` looks for it at the
# head of the last user turn, so it is one constant and not a wording.
WORLD_HEAD = "[that was you,"

# The one line between what she carries and his newest message, and the two
# wordings it is written in (`sim/lang.py`: everything she is addressed in is
# in the arm she is on). `place_tail` puts it where it goes; `frame_line`
# below is how a caller asks for it. It lived as a literal argument inside
# `Persona._draft`, so anything assembling her prompt from outside her --
# a bench, a replay, a card harness -- had to restate the bytes and go stale
# the first time they were edited.
TAIL_FRAME = ("--- HIS NEWEST MESSAGE(S), the ones you are answering now. Nothing above this "
              "line in this turn is his: it is what you carry and where you are ---",
              "--- 彼からの最新のメッセージ。いま返すのはこれ。この線より上はあなたが持ち込んでいるものと、"
              "いまの状況で、彼の言葉ではない ---")

# And the line that goes there when there is nothing of his to answer at all:
# she is writing first. The trailing run of the record is whatever is newest in
# HER record, which is not always his -- her rooms run on her clock, so an
# afternoon message of his lands at her 02:00 while she sleeps and her friends
# talk in the group after she wakes. That whole run used to go under the frame
# with a second wording naming whose it was, and the last thing in the prompt
# beat the instruction above it: at 20:07 on 2026-09-05 five group-chat turns
# in Japanese stood under the frame in her chat with HIM, she answered them, in
# Japanese, and it went to him as a message she started herself. Only his own
# turns follow the frame in his room now (`place_tail`), and where there are
# none this line stands in their place, so the turn still ends on a statement
# about him rather than on the urge that made her write.
TAIL_FRAME_NONE = ("--- NOTHING NEW FROM HIM: there is no message of his to answer, so you are "
                   "writing to him first. Anything newer above this line was not said to you by "
                   "him and is not what you are answering here ---",
                   "--- 彼からの新しいメッセージはない。返すべき彼の言葉はないので、"
                   "あなたから先に書く。この線より上にある新しいものは彼の言葉でなく、"
                   "いまここで返す相手でもない ---")

# And the LAST thing in the final user message, in both rooms she writes in:
# where the next message goes, whether it answers something or she is writing
# first, why she is writing first, and the language that room is in. The end
# of a prompt is the strongest position in it, and until 2026-09-05 nothing
# was there: the instruction naming the room and its language, and the urge
# that made her write, both sat INSIDE the situation block with the whole tail
# under them, and what came last was five group-chat turns in Japanese.
#
# The caller says who the message goes to and what language that room is in,
# because a room is the program's and the language is the character's; this
# holds the wording only, in the arm she is addressed in (`sim/lang.py`).
CLOSING_ANSWER = ("--- NOW: the next message goes to {to}, and it answers what is under the line "
                  "above. it is written in {lang}. ---",
                  "--- いま: 次のメッセージは{to}へ。すぐ上の線の下にあるものへの返事で、{lang}で書く。 ---")
CLOSING_FIRST = ("--- NOW: the next message goes to {to}, first: nothing is waiting to be "
                 "answered{why}. it is written in {lang}. ---",
                 "--- いま: 次のメッセージは{to}へ。返すべきものは来ておらず、自分から先に書く{why}。"
                 "{lang}で書く。 ---")

# What the record puts in front of a message OF HIS, after the stamp: the
# room and who wrote it. `place_tail` reads it to tell whose the trailing run
# is, so it is one constant rather than two spellings that can drift apart.
HIM_TURN = "· chat with him · him]"

# Where a reason too long for the closing line is cut. It used to be cut at
# the character, which put a broken word at the strongest position in the
# prompt: on 2026-09-07 both residents ended their turn on "...the bit that
# came to you straight after sendi...". The cut now falls after the last
# sentence that ends inside the cap, in either language, and a first sentence
# already longer than the cap is cut at a space so at least a word survives
# whole.
_SENTENCE_END = re.compile(r"[.!?。！？]")


def cut_to_sentence(text, cap):
    """As much of `text` as fits in `cap`, ending where a sentence ends."""
    t = str(text or "").strip()
    cap = int(cap)
    if len(t) <= cap:
        return t
    ends = [m.end() for m in _SENTENCE_END.finditer(t) if m.end() <= cap]
    if ends:
        return t[: ends[-1]].strip()
    space = t.rfind(" ", 0, cap)
    return (t[: space] if space > cap // 2 else t[: cap]).rstrip() + "..."



def frame_line(config=None, his=True):
    """The line that says what follows it and that nothing above it in this
    turn was said to her by him.

    Where it goes is `place_tail`'s business and this is only the wording:
    the final user turn reads the world's line about her own last message,
    then anything her other rooms said since she spoke, then what she carries
    and the situation, then this, then his newest messages with their bytes
    untouched, then the closing line.

    `his` is whether there is anything of his to answer. The wording for a run
    of his is unchanged; `his=False` is the line for a turn with nothing of his
    under it, which is what she reads when she writes to him first."""
    return lang.say(config)(*(TAIL_FRAME if his else TAIL_FRAME_NONE))


def closing_line(config=None, to="", language="", why="", first=False, cap=140):
    """The last line of the final user message: where the next message goes,
    whether it answers something or she is writing first and why, and the
    language it is written in.

    `to` is who or which room it goes to, named by the caller -- shared code
    cannot see a room -- and empty means him. `language` is what she writes in
    THERE: her chat with him follows `character.writes_to_him`, and a room of
    her own people is the program's to declare. `why` is the reason she is
    writing first, which is the urge as it was already stated to her; the
    clause after `--` in it is what she is really checking and is not repeated
    here, and a long one is cut at `cap`.

    Wanted because the end of the prompt is where a model looks last and this
    turn ends on somebody's words. Everything that named the room, the
    direction and the language was above the whole tail until now."""
    t = lang.say(config)
    who = str(to or "").strip() or t("him", "彼")
    word = (t("ENGLISH", "英語") if str(language or "english").lower().startswith("en")
            else t("JAPANESE", "日本語"))
    if not first:
        return t(*CLOSING_ANSWER).format(to=who, lang=word)
    reason = str(why or "").split(" -- ")[0].strip().rstrip(".")
    if len(reason) > int(cap):
        reason = cut_to_sentence(reason, cap)
    return t(*CLOSING_FIRST).format(to=who, lang=word,
                                    why=(t(" ({r})", "（{r}）").format(r=reason) if reason else ""))

# Every label the record puts in front of a line, at the head of a line. The
# thread writes these; nothing she says does. Three forms are stamps (the
# weekday with the date, the weekday alone, the bare time), one is the world
# line, and two are the record's own annotations of what she sent with a
# message. A model that reads the thread as a script and carries on writing it
# opens its answer with one of them.
_STAMP = (r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:\s+\d{1,2}\s+[A-Z][a-z]{2})?\s+\d{1,2}:\d{2}"
          r"|\d{1,2}:\d{2}")
_LABEL = (r"\[(?:" + _STAMP
          + r"|that was you,"
          r"|photo you sent:"
          r"|the post you sent:"
          r")[^\]\n]*\]")
STAMP_HEAD = re.compile(r"(?m)^[ \t]*" + _LABEL + r"[ \t]*")
# Where one entry of the record ends and the next begins: a CLOCK label at the
# head of a line, which is what the record writes in front of every line of
# the world's. `tail_run` cuts the trailing run of the final turn on it, so a
# message that runs over several lines keeps its own continuation lines --
# three of the five group-chat turns of 2026-09-05 20:07 had them.
ENTRY_HEAD = re.compile(r"(?m)^\[(?:" + _STAMP + r")[^\]\n]*\]")
# The same, without the two annotations: a clock label only. A repair of the
# stored record uses this one. What she sent him is what he read, and an
# annotation the model copied into a real message is a message of hers to
# take a line out of -- a decision, not a repair.
TIME_STAMP_HEAD = re.compile(
    r"(?m)^[ \t]*" + _LABEL.replace(r"|photo you sent:", "").replace(r"|the post you sent:", "") + r"[ \t]*")


def strip_stamps(text, where="persona"):
    """An answer with the record's own label on it, cleaned and SAID.

    Two different faults, and the log must tell them apart. A label at the
    very head of the answer is the model opening its reply with the line the
    record would have written above it: taken off. A label starting a line
    further in is the model having finished its reply and gone on writing the
    NEXT record entry, usually stamped a few minutes into the future: the
    answer is cut there, because a fabricated future message delivered as her
    next bubble is a message she never sent.

    Neither should ever fire now that her own turns are bare. They are tells,
    and they are loud on purpose: the silent strip that ran until today hid
    the fault for a week, and when the stamp form gained the date and the
    pattern stopped matching, the label went to him."""
    s = str(text or "").strip()
    head = None
    while True:
        m = STAMP_HEAD.match(s)
        if not m:
            break
        head = head or s[:90].replace("\n", " | ")
        s = s[m.end():].lstrip()
    if head:
        logger.log(f"[{where}] the answer came back with the record's own label on it "
                   f"(the thread continued, not answered): {head}")
    m = STAMP_HEAD.search(s, 1)
    if m:
        logger.log(f"[{where}] the answer carried on writing the record past its own reply; cut at "
                   + repr(s[m.start():m.start() + 70].replace("\n", " | ")))
        s = s[:m.start()].rstrip()
    return s


def _tokens(text):
    t = str(text or "").lower()
    out = set()
    for w in _TOK.findall(t):
        if re.match(r"[a-z]", w):
            out.add(w)
        else:
            out |= {w[i:i + 2] for i in range(len(w) - 1)}
    return out


def tail_run(history):
    """The trailing run of the record -- everything the world has said since
    she last spoke -- split three ways: the world's own lines about what SHE
    sent, the entries the record labelled his, and everyone else's.

    One split with two readers. `place_tail` places the pieces; the language
    check on her draft asks the same question, so a reply flagged for being in
    the wrong language can say in the log what the block she was answering
    actually held. An entry starts at a clock label (`ENTRY_HEAD`) and runs to
    the next one, so a message of several lines keeps its continuation lines,
    and the entries stay in the order the record put them in.

    Returns (the world's lines, the run as it stands, his entries, everyone
    else's). All four are empty when nothing has been said since she spoke."""
    if not history or history[-1]["role"] != "user":
        return [], "", [], []
    lines = history[-1]["content"].split("\n")
    head = []
    while lines and lines[0].startswith(WORLD_HEAD):
        head.append(lines.pop(0))
    body = "\n".join(lines)
    his, others = [], []
    if body.strip():
        marks = [m.start() for m in ENTRY_HEAD.finditer(body)]
        bounds = marks if (marks and marks[0] == 0) else ([0] + marks)
        for i, s in enumerate(bounds):
            piece = body[s: bounds[i + 1] if i + 1 < len(bounds) else len(body)].strip("\n")
            if not piece.strip():
                continue
            (his if HIM_TURN in piece.split("\n", 1)[0] else others).append(piece)
    return head, body, his, others


def place_tail(history, tail, frame, frame_none=None, closing=""):
    """The final user turn, in the order she reads it: the world's word on
    what she herself last sent at the TOP, then what she carries and the
    situation, as a second system prompt in effect, then `frame` -- one line
    saying that what follows is the only thing the other person actually
    said -- then the newest message, its bytes untouched, and `closing` last
    of all: where the next message goes and in what language.

    `frame_none` is what makes this the room with HIM. Given it, only the
    entries of his go under the frame and anything else the world said since
    she spoke stays ABOVE what she carries, as the history it is; where there
    is nothing of his, `frame_none` stands in the frame's place and says so.
    A caller that passes no `frame_none` -- a room of her own people, a room
    with another character -- is answering the whole trailing run, and it goes
    under `frame` as it always has.

    Which is the fix for 2026-09-05 20:07: the whole run went under the frame
    with a wording that named whose it was, five group-chat turns in Japanese
    were the last thing in the prompt of her chat with HIM, and she answered
    them there, in Japanese. A frame is read as an instruction, and an
    instruction above the tail is weaker than the position at the end of it.

    The world line comes first because it is about her, not about him. It used
    to be the other way round -- his message, then the tail -- so the thing she
    was answering opened a turn that ran fifteen thousand tokens further and
    the model read it in the middle of the least-attended stretch, and nothing
    marked where his words ended and the machine's began. The cache is
    unchanged by any of it: everything after the previous turn is uncached.
    Returns the history; the messages before the last are the same objects,
    byte for byte."""
    if not tail:
        return history
    if history and history[-1]["role"] == "user":
        head, body, his, others = tail_run(history)
        last = dict(history[-1])
        parts = ["\n".join(head)] if head else []
        if frame_none is None:
            parts.append(tail)
            if body.strip():
                parts.append(frame + "\n" + body)
        else:
            if others:
                parts.append("\n".join(others))
            parts.append(tail)
            parts.append((frame + "\n" + "\n".join(his)) if his else frame_none)
        if closing:
            parts.append(closing)
        last["content"] = "\n\n".join(parts)
        return history[:-1] + [last]
    parts = [tail] + ([frame_none] if frame_none is not None else []) + ([closing] if closing else [])
    return history + [{"role": "user", "content": "\n\n".join(parts)}]


class Thread:
    WIRES = ("episodes",)

    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock
        # what the last build brought back on its cue (`_ref_of` each), for
        # whoever else is answering the same cue
        self.last_recalled = []
        wiring.declare(self)

    # ---------------- rendering helpers ----------------

    def _both(self, ts, fmt, both=True):
        """One moment on both clocks, and the one place a label's time is
        built: her reading, the place her clock is kept on, then his in
        brackets -- `Sat 06 Sep 08:24 Tokyo (Fri 05 Sep 19:24 his)`.

        The place word comes from the clock (`WorldClock.char_zone_word`), so
        no shared module names a city and a character in another zone needs no
        edit. His reading is in brackets rather than after a second `·`
        because `·` separates the FIELDS of a label and the world's line about
        her own run already uses one before the read stamp; the one word
        rather than "his time" is worth about 1,700 tokens a call over the
        four thousand stamps in her thread.

        One reading where there is one clock: a character with no world of her
        own is resident on his machine and on his clock, and a label that
        printed the same time twice would say nothing and cost bytes.
        `both=False` is a cast member's thread -- a friend has no idea what
        his clock says.

        Deterministic on the timestamp, which is what keeps a stamp written
        once: the label is computed from the stored machine-local instant on
        every build and never carried forward."""
        her = self.clock.to_char(ts).strftime(fmt)
        if not both or not self.clock.two_clocks:
            return her
        return (f"{her} {self.clock.char_zone_word()} "
                f"({self.clock.to_user(ts).strftime(fmt)} his)")

    def _stamp(self, ts, now_ts=None, both=True):
        """Absolute, and written once. A stamp that aged -- "03:20", then "Wed
        03:20", then "Wed 02 Sep 03:20, a day ago" -- rewrote every message
        behind it on every call, and the provider's cache is a byte prefix:
        321 of the 400 thread messages that changed between one persona call
        and the next on 2026-09-03 changed for this reason alone. The form
        follows the CONFIGURED span and not the one chosen today, so a window
        the budget shrank does not re-render every stamp: a weekday alone
        places a message inside a window of under a week, and past that the
        weekday repeats and the date has to ride. Both clocks get the same
        form, so a label reads as one moment seen twice."""
        return self._both(ts, "%a %d %b %H:%M" if float(self.config.thread.verbatim_hours) > 144
                          else "%a %H:%M", both)

    def _cut(self, now, hours):
        """A cut of the curve `hours` back, on a midnight of her clock: the
        midnight of today, then whole days back, so every cut moves once a
        day at midnight and never in between. A cut that slid with the clock
        collapsed one more message into the recap at the head of the thread
        every few minutes, and a cut rounded to the NEAREST midnight moved at
        noon -- either way the whole thread behind it was a cache miss. The
        hours are read as days with a half-day's grace, so 36h is today and
        yesterday (24h to 48h of record), 168h is seven days."""
        import math
        day_start = self.clock.to_char(now).replace(hour=0, minute=0, second=0, microsecond=0)
        days = max(1, int(math.ceil((float(hours) - 12) / 24.0)))
        import datetime
        return (day_start - datetime.timedelta(days=days)).timestamp()


    def _records(self):
        """Every conversation of hers on the record: her cast exchanges, her
        conversations with another running character (`sim/peers.py`), the
        peer conversation in flight, and the rooms somebody else owns that
        she was in.

        Separate lists rather than one, because the cast exchange rewrites
        `cast_chat` whole when it closes a conversation and a record it does
        not own would be dropped by it. One reader, so the window's arithmetic,
        what a cue brings back and the build itself all see the same rooms."""
        out = list(self.store.get("cast_chat", []) or [])
        out += list(self.store.get("peer_chat", []) or [])
        live = self.store.get("peer_live") or None
        if isinstance(live, dict) and live.get("turns"):
            out.append(dict(live))
        out += self._peer_rooms()
        return out

    def _peer_rooms(self):
        """The rooms she is in that somebody else owns, as conversations.

        Her copy of such a room is one running record per room (kv
        `peer_rooms`, `sim/peers.py`) holding the last `room_keep` turns she
        was sent, which spans as many days as those turns do. One record per
        room per DAY is handed back, because a conversation in the thread is a
        day's conversation everywhere else -- the cards are written per day,
        the curve is cut on a midnight, and a record whose oldest turn fell
        past the cut would have taken today's turns out of the thread with it.

        A character who is in no room somebody else keeps has no such key and
        this adds nothing to her thread, byte for byte."""
        rec = self.store.get("peer_rooms", {}) or {}
        if not isinstance(rec, dict):
            return []
        out = []
        for room in sorted(rec):
            row = rec.get(room) or {}
            if not isinstance(row, dict):
                continue
            by_day = {}
            for t in (row.get("turns") or []):
                if not str(t.get("ja") or t.get("text") or "").strip():
                    continue
                by_day.setdefault(str(t.get("date") or row.get("date") or ""), []).append(t)
            for day in sorted(by_day):
                turns = by_day[day]
                out.append({"date": day, "hm": str(turns[0].get("hm") or ""),
                            "kind": str(row.get("kind") or "group"),
                            # whose room it is: the process that keeps it, as
                            # her own record of it names her
                            "who": str(row.get("owner_name") or row.get("owner") or ""),
                            "turns": turns, "gist": "", "_peer_room": str(room)})
        return out

    def _chars_between(self, a, b):
        """Characters of record between two timestamps: his chat and her talks,
        with the label each line carries."""
        n = 0
        for m in self.store.messages_since(a) or []:
            ts = float(m["ts"])
            if ts >= b:
                break
            n += len(str(m.get("text") or "")) + 40
        for ex in self._records():
            turns = ex.get("turns") or []
            if not turns:
                continue
            start = float(ex.get("started_ts") or 0) or self._turn_ts(ex, turns[0], 0)
            if a <= start < b:
                n += sum(len(str(t.get("ja") or t.get("text") or "")) + 30 for t in turns)
        return n

    def _cards_chars(self, a, b, now=None):
        """Characters the cards of the days in [a, b) put in the thread: the
        exact lines only for the recent days the thread shows them for
        (`episodes.anchors_days`) and the shape alone behind that, which is
        what the render does. Counting every card at full size charged the
        window for anchors that never appear, which is most of them once the
        cards reach back a month."""
        if self.episodes is None:
            return 0
        try:
            anchors_from = self._cut(now or self.clock.now_ts(), float(self.config.episodes.anchors_days) * 24)
            return sum(len(self.episodes.render(card, "", full=float(card["start_ts"]) >= anchors_from))
                       for card in self.episodes.between(a, b))
        except Exception:
            return 0

    def _window(self, now):
        """(cutoff, verbatim_from) for this build: the two spans, chosen once
        a day and cut on a midnight of her clock.

        `verbatim_hours` (168, seven days) is how far back the record rides
        word for word. `max_age_hours` (720, thirty days) is how far back it
        rides at all: every day between the two is the cards she keeps of it,
        and nothing older is in the thread.

        The verbatim span shrinks only when it has to. What is left of the one
        budget over her prompt is `context.target_tokens` less the parts that
        ride whole -- the system half, what she carries and the situation
        block, as the last persona call measured them (kv `context_last`) --
        less a reserve for the day still being lived, sized as yesterday's
        record. If the verbatim days plus the cards behind them do not fit
        that, the cut moves forward one whole day at a time and that day
        becomes cards, down to `verbatim_min_hours` (36) and no further; a day
        moved out saves its record and costs its cards, and both sides are
        counted.

        Chosen once per day of her clock and kept in kv `thread_window`, so
        the head of the thread -- the cache prefix -- moves once a day and not
        with every message; chosen again at once when the target under it
        changed (a config edit and a restart). Until 2026-09-04 the window had
        a budget of its own (`history_budget_tokens` x `fill`) beside budgets
        for the carried block and the situation block; the sub-budgets did
        nothing the one target does not, and they are gone. Until later the
        same day `verbatim_hours` was a FLOOR the cut grew back from until the
        budget stopped it, so at a large target the whole record was verbatim
        and no card ever rode."""
        c = self.config.thread
        target = int(self.config.context.target_tokens)
        want = self._cut(now, c.verbatim_hours)
        least = self._cut(now, float(getattr(c, "verbatim_min_hours", 36)))
        want = min(want, least)                          # never under the least span
        cutoff = min(self._cut(now, c.max_age_hours), want)   # the cards span reaches the cut
        today = self.clock.date_str(now)
        kv = self.store.get("thread_window") or {}
        if kv.get("date") == today and kv.get("verbatim_from") and int(kv.get("target_tokens", -1)) == target:
            return cutoff, max(cutoff, float(kv["verbatim_from"]))
        ratio = float(self.store.get("context_ratio", 0) or self.config.context.chars_per_token)
        last = self.store.get("context_last") or {}
        fixed = int(last.get("system", 0) or 0) + int(last.get("carried", 0) or 0) + int(last.get("situation", 0) or 0)
        midnight = self.clock.to_char(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        reserve = int(self._chars_between(midnight - 86400, midnight) / ratio)
        budget = max(0, target - fixed - reserve)
        cut = want
        chars = self._chars_between(cut, now + 1)
        cards = self._cards_chars(cutoff, cut, now)
        while cut < least and (chars + cards) / ratio > budget:
            nxt = cut + 86400
            chars -= self._chars_between(cut, nxt)
            cards += self._cards_chars(cut, nxt, now)
            cut = nxt
        v_days = max(0, int(round((midnight - cut) / 86400.0)))
        c_days = max(0, int(round((cut - cutoff) / 86400.0)))
        self.store.set("thread_window", {"date": today, "verbatim_from": cut, "set_at": now,
                                         "tokens": int((chars + cards) / ratio), "budget_tokens": int(budget),
                                         "target_tokens": target, "fixed_tokens": fixed, "reserve_tokens": reserve,
                                         "cutoff": cutoff, "verbatim_days": v_days, "card_days": c_days})
        logger.log(f"[thread] verbatim from {self.clock.to_char(cut).strftime('%a %d %b')}"
                   f" ({v_days} whole day(s) and today, ~{int(chars / ratio)} tokens);"
                   f" {c_days} day(s) before it as cards"
                   + (f" (~{int(cards / ratio)} tokens)" if cards else " (none written yet)")
                   + f"; {int(budget)} left of the {target} target"
                   f" (the rest of the prompt {fixed}, a day's reserve {reserve})")
        return cutoff, cut

    def _room(self, kind, who):
        name = roster.record_name(self.config, who) or who
        return {"line": f"LINE with {name}", "group": "group chat", "in_person": f"in person, {name}",
                "call": f"call with {name}", "video": f"video call with {name}",
                # another running character, on the same messenger he uses
                # (sim/peers.py). The name is the record's, and for a peer it
                # is what HER config calls her: nothing of the other
                # character's own record reaches this.
                "peer": f"messages with {name}"}.get(kind, f"{kind} with {name}")

    def _turn_ts(self, ex, turn, start_ts):
        """A stored turn keeps only its `hm`; the clock is the turn's own date
        where it has one and the conversation's otherwise, and a turn past
        midnight belongs to the next day.

        A turn carries its own date only in a room somebody else owns, where
        one record runs across days (`_peer_rooms`); a turn of an exchange has
        never had the field and reads exactly as it did."""
        if turn.get("ts"):
            return float(turn["ts"])
        hm = str(turn.get("hm") or ex.get("hm") or "00:00")
        try:
            h, m = hm.split(":")
            d = datetime.datetime.strptime(str(turn.get("date") or ex.get("date")), "%Y-%m-%d").replace(hour=int(h), minute=int(m), tzinfo=self.clock.char_tz)
        except (ValueError, TypeError):
            return start_ts
        ts = d.timestamp()
        if start_ts and ts < start_ts - 6 * 3600:
            ts += 86400
        return ts

    def _photos_sent(self, since_ts):
        try:
            with self.store.lock:
                rs = self.store.conn.execute(
                    "SELECT used_ts, caption FROM scenery WHERE used_ts IS NOT NULL AND used_ts >= ?", (since_ts,)).fetchall()
            return [(float(r[0]), str(r[1] or "")[:120]) for r in rs]
        except Exception:
            return []

    def _voices_sent(self, since_ts):
        """What she said aloud, by the time it was sent: the voice note rides
        on the bubble it spoke with. Stored as an event at salience 1 (the
        day's feed takes 2 and up), so until this the only reader was the
        voice model's no-repeat list and she never saw her own spoken lines."""
        try:
            with self.store.lock:
                rs = self.store.conn.execute(
                    "SELECT ts, text FROM events WHERE kind='voice' AND ts >= ?", (since_ts,)).fetchall()
            return [(float(r[0]), str(r[1] or "")[:120]) for r in rs]
        except Exception:
            return []

    def _day_summaries(self):
        """The compiled summary of each day, for a day past the verbatim cut
        that has no cards. It must reach as far back as the cards span or a
        day beyond the last fortnight falls back to its first message."""
        try:
            n = int(float(self.config.thread.max_age_hours) / 24) + 2
        except (TypeError, ValueError):
            n = 14
        try:
            return {d["date"]: (d.get("summary") or "") for d in self.store.recent_days(max(14, n))}
        except Exception:
            return {}

    def _sees(self, for_who, ex):
        """Which rooms a cast member witnessed. The group is every friend's;
        a LINE thread, a call, the kitchen belong to its two ends; her chat
        with him is nobody's, and neither is a room another process asked her
        into -- that record is what SHE was sent of somebody else's room, and
        the people in it have their own."""
        if ex.get("_peer_room"):
            return False
        try:
            return roster.witnessed(self.config, for_who, ex)
        except Exception:
            return ex.get("kind", "") == "group"

    # ---------------- what a cue brings back ----------------

    def _choose_recalled(self, exchanges, cue, cutoff, verbatim_from, now, for_who=None):
        """Which exchanges past the verbatim cut this cue brings back in full,
        as indexes into `exchanges`.

        What comes back is the BEST match, chosen before anything is
        rendered. Taking the first `recall_max` that cleared the overlap
        walked the store in date order, so the two OLDEST conversations that
        shared any two words won and the one the cue was actually about
        never came back: cued with the whole text of a conversation from the
        1st, the thread returned two from the 29th.

        The choice is made from the cue and the window and from nothing else.
        Nothing that reads the record afterwards feeds back into it: the head
        of the thread is the provider's cache prefix, and a byte of it that
        moved with somebody else's retrieval would cost the whole prompt
        behind it."""
        c = self.config.thread
        if not cue or int(c.recall_max) <= 0:
            return set()
        scored = []
        for ix, ex in enumerate(exchanges):
            turns = ex.get("turns") or []
            if not turns or ex.get("_live"):
                continue
            if for_who and not self._sees(for_who, ex):
                continue
            st = float(ex.get("started_ts") or 0) or self._turn_ts(ex, turns[0], 0)
            if st < cutoff or st > now:
                continue
            if self._turn_ts(ex, turns[-1], st) >= verbatim_from:
                continue
            words = _tokens(ex.get("gist", "")) | set().union(*[_tokens(t.get("ja") or t.get("text") or "") for t in turns[:12]])
            n = len(words & cue)
            if n >= int(c.recall_min_overlap):
                scored.append((n, st, ix))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return {ix for _, _, ix in scored[: int(c.recall_max)]}

    def _ref_of(self, ex):
        """One exchange, named the way its other readers name it: the record
        search labels a talk `<date> <hm> with <who>` (`sim/talks.py`) and a
        card `<start> <room>` (`sim/cards.py`), so a reader holding this can
        tell whether a row of its own is the same conversation."""
        turns = ex.get("turns") or []
        start = float(ex.get("started_ts") or 0) or (self._turn_ts(ex, turns[0], 0) if turns else 0.0)
        end = self._turn_ts(ex, turns[-1], start) if turns else start
        date, hm, who = str(ex.get("date") or ""), str(ex.get("hm") or ""), str(ex.get("who") or "")
        return {"date": date, "hm": hm, "who": who, "talk_label": f"{date} {hm} with {who}",
                "room": self._room(ex.get("kind", ""), who), "start_ts": start, "end_ts": end,
                "stamp": self.clock.to_char(start).strftime("%Y-%m-%d %H:%M"),
                "end_stamp": self.clock.to_char(end).strftime("%Y-%m-%d %H:%M")}

    def brought_back(self, cue_text, now_ts=None, for_who=None):
        """The exchanges this cue puts back into the thread in full, one ref
        each, without building the thread.

        The situation block asks before it pins a line about the past, so a
        conversation she is about to be handed word for word is not handed to
        her a second time as a sentence about it (`sim/recall.py`
        `already_in_thread`, `docs/memory.md` §5). The question runs one way
        only: the thread never asks what the deliberate search found."""
        now = now_ts or self.clock.now_ts()
        cutoff, verbatim_from = self._window(now)
        cue = _tokens(cue_text) if cue_text else set()
        exchanges = self._records()
        chosen = self._choose_recalled(exchanges, cue, cutoff, verbatim_from, now, for_who)
        return [self._ref_of(exchanges[i]) for i in sorted(chosen)]

    # ---------------- the build ----------------

    def build(self, live_turns=None, live_who="", live_kind="", now_ts=None, cue_text="", for_who=None,
              live_room=""):
        """[{role, content}] for the chat completion. Hers (both rooms) or,
        with `for_who`, a cast member's witnessed rooms with them as the
        Assistant role. `live_turns` is the exchange in flight; `cue_text`
        is what is being said now, and an exchange past verbatim whose words
        touch it comes back in full. `live_room` names the room those turns
        came out of, when they are a room somebody else owns, so her stored
        copy of that room is not read a second time beside them."""
        c = self.config.thread
        d = self.config.delivery
        now = now_ts or self.clock.now_ts()
        cutoff, verbatim_from = self._window(now)
        cue = _tokens(cue_text) if cue_text else set()
        # Her thread carries his clock beside hers on every stamp; a cast
        # member's carries hers alone. A friend does not know what his clock
        # says and has no reason to be told, and their thread has no room of
        # his in it to place against it.
        both = not for_who
        # the days past verbatim that have cards: a card stands for the
        # conversation it was written from, which is why it is looked up by
        # the stretch of clock it covers rather than by its date alone. A day
        # whose cards were never written, and a conversation the card writer's
        # answer left out, still get their own line: "the day has a card" used
        # to stand for "this is carded", and anything the cards missed on a
        # carded day fell out of the thread entirely.
        card_dates = set()
        cards_by_date = {}
        if self.episodes is not None and not for_who:
            try:
                for card in self.episodes.between(cutoff, now + 1):
                    cards_by_date.setdefault(card["date"], []).append(card)
                card_dates = set(cards_by_date)
            except Exception as e:
                logger.log(f"[thread] cards not read: {type(e).__name__}")

        def carded(date_str, a, b, room="", n_lines=0):
            """Does a card of that day actually cover the stretch [a, b]? A
            card is written per conversation, so the room has to match. The
            odds-and-ends card gathers what was too small to be a conversation
            of its own (`episodes.min_lines`), so it answers for any room --
            but only for a stretch small enough to have gone into it. Letting
            it answer for anything inside its span is as blunt as the day it
            replaced: that span runs from the first stray line of the day to
            the last, so it stands in front of a whole LINE conversation whose
            own card is missing and the conversation leaves the thread with
            nothing in its place."""
            try:
                small = bool(n_lines) and n_lines < int(self.config.episodes.min_lines)
            except (TypeError, ValueError):
                small = False
            for card in cards_by_date.get(date_str, []):
                if float(card["start_ts"]) <= b and float(card["end_ts"]) >= a:
                    if not room or card["room"] == room or (small and card["room"] == "odds and ends"):
                        return True
            return False
        items = []   # (ts, role, text)
        back = []    # what the cue brought back: shown at the end, not at its time
        recalled = 0

        def me(who):
            return roster.same(self.config, who, for_who) if for_who else roster.is_self(self.config, who)

        # --- his chat: hers only
        if not for_who:
            photos = self._photos_sent(cutoff)
            voices = self._voices_sent(cutoff)
            shared = self.store.get("x_shared", {}) or {}
            days = self._day_summaries()
            by_day = {}
            for m in self.store.messages_since(cutoff) or []:
                ts = float(m["ts"])
                if ts < cutoff or ts > now:
                    continue
                if ts < verbatim_from:
                    by_day.setdefault(self.clock.date_str(ts), []).append(m)
                    continue
                text = str(m.get("text") or "")
                if m.get("role") == "user":
                    items.append((ts, "user", f"[{self._stamp(ts, now, both)} {HIM_TURN} {text}", None))
                else:
                    cap = next((cp for t, cp in photos if abs(t - ts) <= 180), "")
                    pre = f"[photo you sent: {cap}] " if cap else ""
                    # a link she sent is a bare URL to him; to her it is the post
                    ps = re.search(r"(?:x|twitter)\.com/\w+/status/(\d+)", text)
                    meta = shared.get(ps.group(1)) if ps else None
                    if isinstance(meta, dict) and (meta.get("author") or meta.get("text")):
                        pic = str(meta.get("images") or "")[:120]
                        pre += (f"[the post you sent: @{meta.get('author', '')}: "
                                f"{str(meta.get('text', ''))[:140]}"
                                + (f" -- the picture: {pic}" if pic else "") + "] ")
                    # bare: what she sent, with what she sent alongside it.
                    # When it was and who read it is the world's line after it.
                    items.append((ts, "assistant", f"{pre}{text}",
                                  {"room": HIM_ROOM,
                                   "read_ts": float(m["read_ts"]) if m.get("read_ts") else None}))
            # the spoken line goes with the one bubble nearest its sending
            # (the hub attaches it to the last of the burst), within three minutes
            if voices:
                hers = [i for i, it in enumerate(items)
                        if it[1] == "assistant" and (it[3] or {}).get("room") == HIM_ROOM]
                for t, v in voices:
                    near = min(hers, key=lambda i: abs(items[i][0] - t), default=None)
                    if near is not None and abs(items[near][0] - t) <= 180:
                        ts0, role0, text0, extra0 = items[near]
                        if not getattr(self.config.tts, "aside_from_persona", True):
                            continue      # nothing in her history invites an aside
                        items[near] = (ts0, role0, text0 + f" [voice note you sent with it: {v}]", extra0)
            # past verbatim: a day of his chat is the day as she remembers it
            for day, ms in by_day.items():
                first = min(float(m["ts"]) for m in ms)
                if carded(day, first, max(float(m["ts"]) for m in ms), "chat with him", len(ms)):
                    continue
                # a DAY of her record, not a moment: it is cut on her
                # midnight and is a different span of his, so it carries her
                # clock alone where every stamp of a moment carries both
                label = self.clock.to_char(first).strftime("%a %d %b")
                summ = days.get(day, "")
                head = next((str(m.get("text") or "")[:80] for m in ms if m.get("role") == "user"), "")
                items.append((first, "user", f"[{label} · chat with him · {len(ms)} messages that day] "
                              + (f"(the day, as you remember it) {summ[:420]}" if summ else f"(it began) {head}"), None))

        # --- her people: the record, then the exchange in flight
        live_started = None
        straddling = []   # conversations that run across the cut and ride in full
        exchanges = self._records()
        if live_turns is not None and live_kind == "peer":
            # the caller is the peer conversation itself and hands its own
            # turns in; the copy `_records` read would be the same one twice
            exchanges = [x for x in exchanges if not (x.get("kind") == "peer" and x.get("who") == live_who)]
        if live_turns is not None and live_room:
            # the same, for a room somebody else owns: the caller hands in the
            # whole of her copy of that room, every day of it, so none of the
            # per-day records `_peer_rooms` built from the same key may ride
            exchanges = [x for x in exchanges if x.get("_peer_room") != str(live_room)]
        live = self.store.get("exchange_live") or None
        if live_turns is not None:
            live = {"date": self.clock.date_str(), "hm": (live_turns[0].get("hm") if live_turns else self.clock.hm()),
                    "who": live_who, "kind": live_kind, "turns": live_turns, "started_ts": None}
        if live and live.get("turns"):
            live_started = float(live.get("started_ts") or 0) or None
            exchanges.append(dict(live, _live=True))
        recalled_ix = self._choose_recalled(exchanges, cue, cutoff, verbatim_from, now, for_who)
        # and on the record, so that whatever else answers this cue can see
        # what she is about to be handed word for word (`brought_back`)
        self.last_recalled = [self._ref_of(exchanges[ix]) for ix in sorted(recalled_ix)]

        for ix, ex in enumerate(exchanges):
            turns = ex.get("turns") or []
            if not turns:
                continue
            if for_who and not self._sees(for_who, ex):
                continue
            start_ts = float(ex.get("started_ts") or 0) or self._turn_ts(ex, turns[0], 0)
            if live_started and not ex.get("_live") and abs(start_ts - live_started) < 60 and ex.get("who") == live.get("who"):
                continue      # the stored copy of the exchange in flight
            if start_ts < cutoff or start_ts > now:
                continue
            room = self._room(ex.get("kind", ""), ex.get("who", ""))
            end_ts = self._turn_ts(ex, turns[-1], start_ts)
            full = end_ts >= verbatim_from or ex.get("_live")
            dest = items
            if full and not ex.get("_live") and start_ts < verbatim_from:
                # it began before the cut and ran past it: it rides whole, at
                # its own time, and its card must not ride beside it
                straddling.append((room, start_ts, end_ts))
            if not full and ix in recalled_ix:
                # in full, but after everything else: what comes back
                # depends on what is being said now, and a block that
                # moved with the cue in the middle of the thread was a
                # cache miss for everything behind it on every call. Its
                # card stays where it is for the same reason: dropping it
                # would make the head of the thread depend on the cue.
                full = True
                recalled += 1
                dest = back
                back.append((start_ts - 1, "user", f"[{self._stamp(start_ts, now, both)} · {room}] (this came back to you just now)", None))
            if not full:
                if carded(ex.get("date"), start_ts, end_ts, room, len(turns)):
                    continue
                gist = str(ex.get("gist") or "").strip() or str(turns[0].get("ja") or turns[0].get("text") or "")[:80]
                until = ex.get("ended_hm") or turns[-1].get("hm", "")
                items.append((start_ts, "user", f"[{self._stamp(start_ts, now, both)} · {room} · {len(turns)} messages" + (f", until {until}" if until else "") + f"] (what it came to) {gist[:220]}", None))
                continue
            for t in turns:
                ts = self._turn_ts(ex, t, start_ts)
                if ts > now:
                    continue
                who = str(t.get("who") or "")
                text = str(t.get("ja") or t.get("text") or "")
                if not text:
                    continue
                if me(who):
                    dest.append((ts, "assistant", text, {"room": room, "read_ts": None}))
                else:
                    dest.append((ts, "user", f"[{self._stamp(ts, now, both)} · {room} · {roster.record_name(self.config, who) or who}] {text}", None))

        # the days past verbatim, as the cards she keeps of them
        if card_dates:
            # on a midnight, like every other cut: a line that slid with the
            # clock re-rendered a card at any hour and moved the head again
            anchors_from = self._cut(now, float(self.config.episodes.anchors_days) * 24)
            for card in self.episodes.between(cutoff, verbatim_from):
                st = float(card["start_ts"])
                if any(card["room"] == r and st <= e and float(card["end_ts"]) >= s for r, s, e in straddling):
                    continue      # the conversation itself is in the thread, in full
                items.append((st, "user", self.episodes.render(card, self._both(st, "%a %d %b %H:%M", both),
                                                               full=st >= anchors_from), None))
        items.sort(key=lambda x: x[0])
        # what came back on the cue goes after the record and BEFORE what is
        # being answered now: the trailing run of the world's messages since
        # she last spoke (his unanswered messages, or the other person's turns
        # in an exchange in flight). Appended after everything, it stood
        # behind his newest message, and the final turn ends on that message
        # now (`place_tail`). A self-start has no such run and gets it last.
        k = len(items)
        if back:
            back.sort(key=lambda x: x[0])
            while k > 0 and items[k - 1][1] == "user":
                k -= 1
        # silences over the record's own clock, then merge so the roles
        # alternate. Her turns are bare and the world says what they were:
        # one line after each run of them, naming when she sent them, the
        # room, and in his chat when he read them. That line is a user turn,
        # so it is also what keeps the roles alternating when she spoke in
        # two rooms with nobody answering in between -- which used to be one
        # merged assistant turn holding two rooms at once.
        out, prev_ts = [], None
        run = {}        # her messages since the last world line

        def add(role, text):
            if out and out[-1]["role"] == role:
                out[-1]["content"] += "\n" + text
            else:
                out.append({"role": role, "content": text})

        def close_run():
            if not run:
                return
            line = f"{WORLD_HEAD} {self._stamp(run['ts'], now, both)}, {run['room']}"
            if run["n"] > 1:
                line += f", {run['n']} messages"
            # the read stamp is the last of the run's: he opens a burst once.
            # A receipt that lands later rewrites this one line, as it used to
            # rewrite the label on the message itself.
            if run.get("read_ts"):
                line += " · read " + self._stamp(run["read_ts"], now, both)
            add("user", line + "]")
            run.clear()

        def emit(ts, role, text, extra=None):
            if role != "assistant":
                close_run()
                add("user", text)
                return
            room = (extra or {}).get("room", "")
            if run and run["room"] != room:
                close_run()
            add("assistant", text)
            if run:
                run["n"] += 1
                run["read_ts"] = (extra or {}).get("read_ts")
            else:
                run.update({"ts": ts, "room": room, "n": 1, "read_ts": (extra or {}).get("read_ts")})

        for i, it in enumerate(items):
            ts = it[0]
            if back and i == k:
                for b in back:
                    emit(*b)
            if prev_ts is not None and ts >= prev_ts:
                gap_h = (ts - prev_ts) / 3600.0
                if gap_h >= float(d.gap_marker_hours):
                    from persona.persona import _gap_text
                    emit(ts, "user", f"[nothing said anywhere for {_gap_text(gap_h)}]")
            prev_ts = ts
            emit(*it)
        if back and k == len(items):
            for b in back:
                emit(*b)
        close_run()      # her last run, when nobody has answered it yet
        if recalled:
            logger.log(f"[thread] {recalled} exchange(s) past verbatim came back on the cue")
        return out

    def report(self, n=12, for_who=None):
        msgs = self.build(for_who=for_who)
        chars = sum(len(m["content"]) for m in msgs)
        who = f"for {roster.record_name(self.config, for_who)}" if for_who else "hers, both rooms"
        win = self.store.get("thread_window") or {}
        out = [f"thread ({who}): {len(msgs)} message(s) after merging, {chars} chars; verbatim to "
               f"{self.config.thread.verbatim_hours}h back"
               + (f" ({win.get('verbatim_days')} whole day(s) and today chosen)" if win.get("verbatim_days") is not None else "")
               + f", then the cards of each day, out at {self.config.thread.max_age_hours}h"
               + (f" ({win.get('card_days')} day(s) as cards)" if win.get("card_days") is not None else "")]
        for m in msgs[-n:]:
            out.append(f"  {m['role']:9} {m['content'][:150].replace(chr(10), ' | ')}")
        return "\n".join(out)
