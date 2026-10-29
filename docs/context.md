# Context: what a character is sent, in what order, and why

Spec of record for how her prompt is built: the two halves, the one
thread, the curve by clock, recall, the final turn, the one budget, the
cast members' threads, and the tells. What she remembers and how it comes
back is `docs/memory.md`, its other half: this says where a retrieval
lands, that says what is retrieved and why it fades. Summary and pointers: PROJECT.md §3
(models), §5 (the persona and the thread), §12.2 (memory) and §12.13
(cards). Dated notes: HISTORY.md, the one-thread, one-budget, seven-days-verbatim,
final-turn and bare-turns entries. `docs/context-architecture.md` is the design draft this grew
from and is kept as history; `docs/memory-tiers-plan.md` is the next step.

Read the function and build the prompt on a copy before reporting on any
of this: `tools/context_sim.py`, `sim/context.py` (`/context`), and the
check scripts under `data/retired/20260904_final_message/`,
`data/retired/20260904_bare_turns/` and
`data/retired/20260905_him_room_tail/` build the real thing with the model
stubbed -- the last of those rebuilds one real logged prompt from the run
that sent it and places it again both ways.

## 1. The shape, in the order the model reads it

One chat-completion request per reply:

1. **The system prompt** (`persona/sections.py SYSTEM`, `Persona.system_for`):
   the bible, the backstory, what she has decided about herself, what
   people are to her, what makes her do a thing (her mechanisms), what is
   already fixed in the days ahead (the agenda), and the style guide last.
   It changes about once a
   day. Both rooms build it from the same core, so her replies to him and
   her turns with her own people share the cache prefix; `tools/smoke.py`
   fails if the two diverge by more than `style.md`.

   **The agenda is the last section before the style guide**
   (`sim/agenda.py`, config `agenda`): the coming days as one list --
   the calendar's holidays and what is on in her wards, the promises she
   has made with the date they come due, what he said he would do with the
   deadline it is judged against, and who the day's plan has taken out of a
   day ahead (from her own plan, or from the world file when the world is
   somebody else's to write). Every date is absolute -- `Thu 10 Sep: ...`,
   never "in two days" -- because this rides in the cached half and a
   countdown would rewrite every line of it every midnight. It starts at
   TOMORROW: today is the day's one truth (`sim/ledger.py`), which is in
   the situation block on every call already, and repeating it here would
   put a settled line that lands at four in the afternoon into the cached
   prefix. A character with nothing dated -- no world, no promises, nothing
   he said -- renders no block at all rather than a heading over an empty
   list. It sits after the mechanisms and before the style guide for the
   same reason the mechanisms do: adding it moved no byte of the prompt in
   front of it. `/agenda [days]` prints the whole join, today included,
   with a mark against the lines her prompt carries, and the ops payload
   carries it as `agenda`.
2. **The thread** (`sim/thread.py`): the record, both rooms, in time order.
   The days past the verbatim span as their cards, oldest first; then the
   verbatim days; then, before the messages being answered now, anything
   recall brought back.
3. **The final user turn** (`sim/thread.py place_tail`), in this order:
   the world's line about her own newest message when hers is the newest
   thing; in the room with him, anything her OTHER rooms said since she
   last spoke, which is history and not what she is answering; the
   `<carrying>` block; the `<situation>` block ending on the one
   imperative slot line; one frame line saying that his newest messages
   follow and that nothing above it in this turn is his; his newest
   message(s), bytes untouched -- or, when there is nothing of his, one
   line saying so and she is writing first; and last of all one closing
   line naming who the next message goes to, whether it answers something
   or she is writing first and why, and the language that room is in.

The pieces are asked for, never restated. `Persona.system_for` is
the system half, `Persona.carried_for` the carrying block,
`Persona.frame_line` the line between what she carries and his newest
messages (`sim/thread.py:TAIL_FRAME`, `TAIL_FRAME_NONE`), and
`sim/thread.py:closing_line` the last line of all. The frame used to be a
literal argument inside the draft call with no accessor, so anything
assembling her request from outside her -- a bench, a replay, the
persona-card harness -- restated the bytes and would have gone stale the
first time they were edited.

**In the room with him, only his own messages are what she is
answering.** The trailing run of the record is whatever is newest in HER
record, which is often not his: her rooms run on her clock, so an
afternoon message of his lands at her 02:00 while she sleeps and her
friends talk in the group after she wakes. That whole run used to go under
the frame with a second wording saying whose it was, and the last thing in
the prompt beat the instruction above it: at 20:07 one evening five
group-chat turns in Japanese stood under the frame in her chat with him,
she answered them, in Japanese, with a sticker tag, and it went
to him as a message she started herself (HISTORY, the entry on the
friends' turns standing under the frame in his chat). Now `place_tail` splits that run entry by entry on the record's
own clock label (`ENTRY_HEAD`, so a message of several lines stays whole)
and in his room only the entries the record labelled his
(`sim/thread.py:HIM_TURN`, the same constant the record writes) go under
the frame; everything else stays above what she carries, in time order,
as the history it is. When there is nothing of his the frame is one line
instead (`TAIL_FRAME_NONE`, asked for as `Persona.frame_line(his=False)`):
*nothing new from him; you are writing to him first*. `tail_run` is the
one split, and the language check on her draft reads it too, so a reply
flagged for being in the wrong language says in the log what the block
held. A room of her own people and a room with another character pass one
wording and are unchanged: there the whole trailing run is what she is
answering, byte for byte as before.

**The last line is the closing line** (`sim/thread.py:closing_line`, both
rooms): who the next message goes to, whether it answers what is under
the frame or she is writing first and why -- the urge as her situation
block already states it (`sim/intent.py reason_line`) -- and the language
that room is in. The end of the prompt is where a model looks last, and
nothing was there until this change: the instruction naming the room and
its language sat inside the situation block with the whole tail under it,
which is the other half of why the group chat won. The caller says who the
message goes to and what language that room is in, because a room belongs
to a program and the language to the character; the wording is the arm's
(`sim/lang.py`), so the second character reads it in Japanese.

The reasons for that order are three constraints at once. The illusion
decides the content: who I am, what has happened, what I am carrying,
where I am, what he just said. The provider's cache decides where the
stable parts go: a byte that changes early costs everything behind it, so
the slow half is first and the fast half is after the last cached byte.
One model call per reply decides the size: nothing is retrieved on demand
by a second pass, so everything she might need rides, and the design
leans toward carrying more and cutting less.

## 2. Roles and labels

**Role is who is speaking, not who is real.** Everything she said, in any
room, is the Assistant role. Everything anyone else said -- him, a friend
the cast model wrote, her father -- is the User role, the world speaking
to her. Same-role lines merge into one message so the roles alternate.

**The world's lines carry a label; hers carry none.** A line from the
world opens `[her time · his time · room · who]`: `[Mon 01 Jun 21:37 Tokyo
(Mon 01 Jun 08:37 his) · chat with him · him]`, `[Mon 01 Jun 21:08 Tokyo
(Mon 01 Jun 08:08 his) · group chat · 香芝玲奈]`, `[Mon 01 Jun 21:58 Tokyo
(Mon 01 Jun 08:58 his) · in person, 古賀健二 · 古賀健二]`. The rooms are
named in one place (`Thread._room`: `chat with him`, `LINE with <name>`,
`group chat`, `in person, <name>`, `call with <name>`, `video call with
<name>`). The stamp is written once and never rewritten as the message
ages; its form is the weekday and time inside a window of under a week and
the weekday, date and time past that, keyed on the configured span so a
shrunk window does not re-render every stamp.

**Both clocks on every stamp of a moment** (his call; `Thread._both`, the
one place a label's time is built). Her reading first
with the place her clock is kept on, then his in brackets. A reading on
hers alone left hours of arithmetic to whoever read it, and the
model did not do it: it asked him three times in four days whether he had
fallen asleep, at his 08:10, his 09:20 and his 10:30. The place word comes
from the clock (`WorldClock.char_zone_word`, the last segment of
`world.character_timezone`), so no shared module names a city; his reading
sits in brackets rather than after a second `·` because `·` separates the
FIELDS of a label and the world's line about her own run already uses one
before the read stamp.

Two exceptions, both deliberate. **A character with no world of her own
gets one reading**: she is resident on his machine and on his clock
(`WorldClock.two_clocks`, decided once at boot and never from a
character's name), and a label printing the same time twice would say
nothing and cost bytes -- the second character's thread is byte-identical
to what it was. **A cast member's thread gets one reading too**
(`build(for_who=...)`): a friend has no idea what his clock says and has
no room of his in her seat of the record to place against it.

**A line that names a DAY keeps her clock alone.** The day of his chat
past the verbatim cut that has no cards opens `[Wed 19 Aug · chat with him
· 53 messages that day]`, and it stays one clock because a day is a span
cut on her midnight and is a different span of his; there is no single
instant of his to print beside it. A card's header names a MOMENT -- when
that conversation began -- so it carries both, and the `until HH:MM` at
the end of a span is the far end of the same span, read on the clock its
head named.

**Her own turns are bare**: exactly the words she sent, plus what she
sent with them (`[photo you sent: ...]`, `[the post you sent: ...]`,
`[voice note you sent with it: ...]`). What the record knows about her
turn -- when, which room, and for a message to him when he read it -- is
the first line of the user turn that follows her run:

    [that was you, Tue 02 Jun 11:40 Tokyo (Mon 01 Jun 22:40 his), to him · read Tue 02 Jun 11:42 Tokyo (Mon 01 Jun 22:42 his)]
    [that was you, Mon 01 Jun 21:20 Tokyo (Mon 01 Jun 08:20 his), group chat, 2 messages]
    [that was you, Mon 01 Jun 21:59 Tokyo (Mon 01 Jun 08:59 his), in person, 古賀健二, 2 messages]

A run is one room: consecutive messages of hers in the same room are one
bare turn with one world line carrying the count and the read stamp of
the last of them; a room change closes the run, and the world line
between two runs is what keeps the roles alternating when nobody answered
in between. When her message is the newest thing, the world line opens
the final user turn.

Why bare: a label on her own line was a label the model copied. The
second character's model wrote a stamp, with a read time it invented, on
28 of 29 replies, and sometimes a second message dated minutes into the
future -- the next record entry rather than an answer. With her turns
bare, her own past turns are exactly the shape the model should produce
and there is nothing to imitate. The first character's model never did
this; the change costs her nothing.

**Nobody types the label.** The system prompt and the situation say the
labels are the app's; the closing instruction says the chat above is the
record, not a script. `sim/thread.py strip_stamps` is the tell that
should never fire: it strips one stamp at the head of an answer and says
so, and cuts the answer where a second one starts a line, so a fabricated
next message can never go out as her next bubble. Smoke fails if any turn
of hers in a built thread carries a label or has no world line after it.

**A room somebody else keeps is a room.** A character who was asked into
another process's room holds her own copy of it (kv `peer_rooms`,
`docs/peer-talk.md` §4b.5), and `Thread._records` reads it like every other
conversation: one record per room per day, the world's lines labelled with the
room and the speaker, her own turns bare. It is read as days rather than as one
running record because every other span here is cut on a midnight, and each
turn keeps its own day and the real instant it arrived, so a stamp is written
once and does not move when the record rolls over. A character with no such
record -- anybody who is in no room she does not own -- has not one byte of her
thread changed by this: measured at 551 messages either way on the first
character. A cast member's thread never sees it (`_sees`), for the same reason
it never sees her chat with him.

**Spoken rooms are spoken.** An in-person exchange, a call or a video
call is the same thread with the room label saying so, no read receipts,
seconds between lines rather than minutes, no phone gate, and the
speaker's prompt gets a line of what is visible of her; the line that
names where she is now says "speaking", not "writing"
(`tomoe/exchange.py SPOKEN`).

**Language.** The labels and the world lines are English for both
characters and move together if they ever move -- including the two words
that say whose clock a reading is, which come from the clock rather than
from a literal in shared code. Everything addressed TO
her is in her language (`character.writes_to_him`); the frame line in the
final turn is hers, the cast's frame is Japanese.

**The situation block says the same thing in prose, in the same order.**
The clock line at the head of her situation reads *it is Sunday 08:24
(early morning) for you in Tokyo. for him it is Saturday 19:24 (evening
his time), many hours behind you* -- her reading first with the same place
word the labels carry, then his. The two are not allowed to name her clock
two different ways, which is why both ask `WorldClock.char_zone_word` for
it.

## 3. The curve by clock

Three clocks, cut on a midnight of hers (`Thread._cut`, `_window`):

| age of the record | rides as | config |
|---|---|---|
| inside `verbatim_hours` (168) | every message in full, both rooms | `thread.verbatim_hours` |
| from there to `max_age_hours` (720) | the day's cards, one per conversation (`sim/cards.py`); the exact lines kept for the last `episodes.anchors_days`; a day with no cards as the compile's recap line | `thread.max_age_hours`, `episodes.*` |
| older | nothing in the thread; her memories, her facts and recall | -- |

The verbatim span shrinks a whole day at a time toward
`verbatim_min_hours` (36) only when the verbatim days plus the cards do
not fit what is left of the one budget (§5); at the live target it never
has to. The window is chosen once a day of her clock and kept in kv
`thread_window`, so the head of the thread moves once a day, at midnight,
and again at once when the target under it changes. A conversation that
crosses the midnight the cut sits on rides whole and its card is
suppressed; a card stands only for the conversation it spans, so a
conversation the card writer missed still rides as its own "what it came
to" line. The cards have thirty days to fill on a save from before them
(`Cards.backfill`, eight days a boot; `/episodes backfill`).

What comes next is `docs/memory-tiers-plan.md`: week cards from day 31,
month cards from day 91, rehearsal on recall, flashbulb days kept whole.

## 4. What retrieval puts in the prompt

Everything she remembers is `docs/memory.md`: the five stores, the
forgetting curve, the moment as one cue, and the local embedding that
lets a paraphrase or a Japanese cue reach an English row. What matters
here is that SIX retrievals run on one reply and land in three different
parts of the prompt, most of them asking with the same cue
(`sim/recall.py moment_cue`: what he just wrote, her own last line, the
scene she is in).

**Into the thread**: an exchange past the verbatim cut whose words touch
the moment comes back in full, at most `thread.recall_max` of them,
ranked by overlap and not by age, marked `(this came back to you just
now)`. It lands after the record and BEFORE the messages being answered
now, the trailing run of the world's lines since she last spoke, never
behind his newest message. The silence markers are computed over the
record's own clock, so an old block coming back cannot put a "[nothing
said anywhere for N days]" line in front of his message, and its card
stays where it is, so the head of the thread does not depend on the cue.

**Into the carrying block**: the facts about him that are above the fade
line plus the faded ones the moment just cued
(`Memory.facts_for_prompt`), and her own memories the same way
(`SelfMemory.for_prompt`). This is the durable record, so it changes
slowly and sits with the rest of the block after the cached prefix.

**Into the situation block**: what she just remembered on cue, written by
a model (`Recall`); a thing she once looked up or watched, matched by
name with no window and pinned (`sim/known.py`); and what she happens to
know, matched by hand-written phrases (`sim/lore.py`, the second
character). This is this minute's retrieval, so it arrives next to the
one action line. The last of those three lands in her rooms with her own
people as well, through the same gate and under the same header
(`sim/lore_rooms.py`, `tomoe/exchange.py:_her_turns` and
`sim/peers.py:_room_reply`); the other two are her chat with him only. The remembered line is dropped when the thread is
bringing that very conversation back in full, so one cue is not answered
twice -- the exact words above and a compiled sentence about them below
(`docs/memory.md` §5). The situation asks the thread; the thread asks
nothing, because its head is the cached prefix.

Both prompt-side retrievals run on the loop thread and therefore read
stored vectors only; the encoding of a save's whole record is paid for by
a background pass after boot. So a fresh save reaches by words alone
until that pass has run.

## 5. The one budget

`context.target_tokens` (200000) is the only budget over her prompt.
Everything rides whole: the system half, the carrying block, every line
the situation block admits. The thread's verbatim span is the one thing
that gives, whole days at a midnight, and only when the fixed parts plus
the verbatim days plus the cards exceed the target. The window's budget
is derived from the last persona call's measurement (kv `context_last`:
system + carried + situation) and a reserve for the day being lived,
sized as yesterday's record. `sim/memory.py fit` measures and trims
nothing; `measure` writes the measurement and logs it; `/context` reads it
back.

The sub-budgets that used to sit under the target -- the history's own
token budget, the carried block's budget over floors, the situation
block's per-bucket and total caps, the per-section warn sizes -- did
nothing the target does not, and were cutting the situation block to
fifteen lines while the prompt had room for all of it. They are gone
(HISTORY, the one-budget entry). The attention gate (`sim/attention.py`) still
orders each section by weight, suppresses a claim a covering source
already makes, lets a one-per-source source say it once, and hands the
single heaviest action to the slot; it drops nothing for room.

Realistic sizes today: the first character 90k to 120k once the cards
fill (23k fixed, 3k to 5k situation, 30k to 50k verbatim, 25k to 35k
cards, and 10k for his clock beside hers on every stamp); the second 60k
to 80k, unchanged, because she has one clock and one reading. The target
is a ceiling nobody expects to reach; `[context] ... over target` should
never appear.

Measured on a copy of the live save at one instant with the clock's answer
as the only switch (the dated note is in HISTORY): her thread 107,094 characters
on one clock and 131,512 on two, +24,418 characters over 839 labelled
lines -- 29 characters a label, +9,655 tokens a call at the calibrated
2.529 characters per token. The second character's thread: 42,853
characters either way, byte for byte.

## 6. The cast members' threads

A cast member's turn (`tomoe/exchange.py`, `Thread.build(for_who=...)`)
is the same thread from their chair: only the rooms that person witnessed
(the group for a friend, their own LINE, calls and in-person exchanges,
never her chat with him), THEM as the Assistant role -- bare, with the
world line after their runs -- and everyone else, her included, as the
world. They share her window and her cut exactly; they get no cards by
design (a card spans every room, his included) and their past reaches
them as "what it came to" lines. Her own turns in her rooms build the
full thread, both rooms, so the record of her chat with him is in front
of her when she writes to a friend; the situation names the room she is
speaking or writing in now, and his chat is never the thing being
answered. Their final turn has the same order as hers: the room's
situation and the write instruction, the frame, the newest turn last. HER
turn in one of her own rooms ends on the closing line as her chat with him
does, naming that room and saying it is written in Japanese; a cast
member's own turn does not, because the line is about her.

## 7. Cache

The system half is the cached prefix and changes about once a day. The
thread is byte-identical up to the newest message between two builds when
the window does not move; a read receipt written later rewrites one world
line, once. Everything after the previous turn -- the world line, what her
other rooms said, the carrying block, the situation, the frame, his newest
message, the closing line -- is uncached by nature, so their order costs
nothing. Measured: 95% cached on
the second character's persona calls at 41k; a drop to under half on
consecutive calls inside one day means the head moved, which it must not.
A change to the stamp form, the world-line wording or the window is one
full cache miss per character and then stable. Putting his clock on every
stamp was exactly that, and it was his call knowing the price: one cold persona call for the first character and none for the
second, whose bytes did not move.

**The cache is measured, not assumed** (`LLM._track_cache`, kv
`cache_track`, `/provider`). Every receipt carries its cached prompt tokens
and the call's log line ends `cache=NN%`. Per role the store keeps the last
hit rate, how many calls came back warm and how many cold, the longest idle
gap a warm call survived, and the shortest and most recent gap that came back
cold; `[cache] <role>: COLD after N idle` says so as it happens when the
previous call had been warm. A cold call is counted whenever the hit rate is
under half and that role has a previous call to measure the gap from, whatever
the previous call did -- the count used to require the previous call to have
been warm, so a role that is cold every time recorded nothing and the table
read "never gone cold" while every call was missing. The gap runs from the
previous call of that role FINISHING to this one going out; a call sent inside
`api.cache_settle_seconds` of that finish is counted separately and never as
cold, because the entry the previous call wrote is not readable that soon (on
Z.AI at 44k tokens, about ten seconds). The pair of gaps is the provider's
lifetime as observed on this prompt; a cold call well inside the warm gap
means the prefix changed, which is the fault to look for. What each host was
measured to do, and why a 0% on this prompt was timing rather than a broken
prefix, is `docs/openrouter.md` §4.

## 8. Config

`context.max_tokens` (the model's window, never an output cap),
`context.target_tokens`, `context.chars_per_token` (the seed for the
calibrated ratio, kv `context_ratio`); `thread.verbatim_hours`,
`verbatim_min_hours`, `max_age_hours`, `recall_max`,
`recall_min_overlap`; `episodes.*` (the cards); `delivery.gap_marker_hours`
(the silence markers); `attention.*` (weights and the slot, no caps);
`agenda.enabled`, `agenda.days` (how far ahead the coming-days block
looks), `agenda.max_items` (how many lines it may carry, nearest first)
and `agenda.in_prompt` (whether she reads it at all; off leaves the join
in `/agenda` and the ops payload).

The LANGUAGE of what is built here is one switch, not a property of a file:
`character.instructions` (`sim/lang.py`) decides what language everything
addressed to her is written in -- the headings over the sections above, every
bucket of the situation block, the closing instruction -- and
`character.instruction_language` says which language that arm renders for a
given character. `language.material_roles` extends it to the roles that wrote
the sentences UNDER those headings, since the builder cannot reach those, and
kv `instructions_override` (`/lang ja|en|auto`) moves the arm live. The
mechanism, the coverage table and the roles deliberately left in English are
`docs/language.md`; what the switch measured on the second character is
`docs/yukarin.md` §21, "Which language she is addressed in".

## 9. Store and log

kv `thread_window` (the cut chosen today, with the target, the fixed
tokens and the reserve it was derived from), `context_last` (the last
persona call's measurement), `context_ratio`, `stamps_stripped_once` (the
one-off repair that took the record's own labels off stored messages,
`sim/repairs.py`; the old text under `data/retired/<ts>_stamps/`).

Log lines: `[thread] verbatim from <day> (N whole day(s) and today, ~T
tokens); M day(s) before it as cards (~C tokens); B left of the T target
(the rest of the prompt F, a day's reserve R)` once a day at her midnight
and once after a restart that changed the target; `[thread] N exchange(s)
past verbatim came back on the cue`; `[context] ~Nk tokens of 200k:
system | history | carrying | situation` on every persona call;
`[episodes] <date>: N card(s) ... D dropped as not said` at each compile;
`[repair] the record's own label taken off N message(s)` once and never
again. Ops: `/context`, `/episodes [fed [date] | relink [days] | backfill | <date>]`,
`/thread`.

## 10. Tells, and what each means

- `[persona] the answer came back with the record's own stamps on it`, or
  the cut line from `strip_stamps`: the model is writing the record
  rather than answering. It should never fire now; if it does, read the
  thread the model was sent, not the cleaner.
- Replies that quote or transcribe the record: the same fault by eye.
  The fix is fewer verbatim days, never a tighter target.
- `[carrying]` or a numeric reason in an `[attention]` `dropped:` list: a
  cap came back.
- `[context] ... over target`: the parts that ride whole outgrew the
  target, or the 36-hour floor alone is over it; nothing was trimmed.
- The cache rate falling inside a day: the head of the thread moved.
- The same `ON YOUR MIND` slot line on two consecutive persona calls after
  she has said it: an item that did not retire.

## 11. Tests

`tools/smoke.py` (the thread builds for every character and for a cast
member; roles alternate; no turn of hers carries a label; the two rooms'
system prompts diverge by no more than the style guide; the room with him
ends on his own messages under the frame or on the line saying there are
none, then the closing line, and the placer moves no message before the
last);
`tools/situation_test.py`; `tools/context_sim.py --budget <target>` (her
clock rewound over a copy, the window compact, the cards written, the
probes answered); `tools/docs_check.py`. The check scripts beside the
same day's patches build her friend turn and a cast member's turn on a
copy and print the final turn's last lines.
