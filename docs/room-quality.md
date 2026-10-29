# Whether a room is a conversation

A group chat that reads wrong reads wrong for reasons that can be counted. Two
rooms in the world's own record were read line by line in the audit behind
this work (HISTORY.md, the cast and the exchange): one loops
outright, and the other, written by two processes instead of one, plays the
same beat twice on each side inside four minutes. This is what was wrong with
them, what was built, and how each piece is proved without paying for a call.

Everything here is code, in the shared library (`sim/`) or in the world program
(`tomoe/`). Nothing is in a prompt file, so a bundle cannot copy over it, and
every knob is a default in `config.py` that a character composed by
`tools/new_character.py` gets without opting in.

## 1. What was wrong

**Loops.** The writers' only repeat test compared two WHOLE messages by the
SAME speaker at 86% similarity. Neither loop in the record is that shape. One
girl wrote the same sentence at 07:17 and at 07:21 wrapped in different second
bubbles, so the two messages were 57% alike and the sentence inside them was
identical. Another wrote back almost word for word what somebody else had said
two minutes earlier. Nothing recorded what a turn had been FOR, so one girl
played "fine, I will ask, but I am still the one who decides" at 07:19 and
again at 07:23 in different words. The room continued at
`exchange.group_continue_p` 0.87 a round whether or not the round had added
anything. The member who writes her own turns had no repeat test at all.

**Nothing to talk about.** Every one of six people's one carried thought was
about the character whose world it is, and four of them were the identical
sentence three days running. Of twelve things going round, six were known to
exactly one person, and a speaker is shown only what she has heard. Nobody had
a per-day handful of concrete things, although the prompt tells them a group
chat is mostly made of those.

**Pace.** The gap between turns read the availability of the person who OPENED
the conversation and only when the next turn was theirs, so a room whose
speakers were all in class ran at full speed if the opener happened to be free.
Fourteen messages landed in eighteen minutes while four girls were at
breakfast, on a platform and on a train.

## 2. The six measures

`tools/room_quality.py` reads a room read-only from wherever it lives -- the
owner's save (kv `cast_chat`, and the one in flight in `exchange_live`), a
participant's save (kv `peer_rooms`), or the world file's `rooms` table -- and
reports:

| measure | what it is |
|---|---|
| own repeats | a whole message that repeats a whole message of the same person's: the old test, kept as its own column so the new one can be seen to add something |
| sentence echoes | a message more than half of whose long sentences anybody in the room has already said |
| same move twice | two turns by one person whose one-line summaries mean the same thing |
| messages a minute | over the room's own span |
| bubble length | the mean per speaker, in characters |
| stale rounds, long bubbles | what the room's own record counted while it ran |
| arrangements | the share of turns naming a time, a place, or asking for one: a chat that is only ever a committee |
| pocket used | how many of the day's concrete things reached a call |

    python tools/room_quality.py --world data/worlds/tokyo/world.db --date <day>
    python tools/room_quality.py --save data/world.db --date <day> --room group -v
    python tools/room_quality.py --save data/rena.db --peer-rooms

A room that has no moves ledger (anything written before the ledger, and every
room read out of the world file, which copies turns and not the record) answers
`-` for the move column rather than zero.

## 3. What was built

**A moves ledger per room.** Every call that writes a turn already returns a
one-line summary and the record kept only the last one. The room now keeps the
list: who moved, when, and what the move was
(`tomoe/exchange.py _note_move`). Both writers render it -- the owner's, and
the process of a member who writes her own turns, which is handed the list on
the ask and sends its own summary back on the envelope (`sim/rooms.py`
`moves_block`, `ask(moves=...)`, `put`, and `gist` on the way back). The
rendered header says: a move that landed is done, a move nobody answered is
dropped or made shorter, nobody plays the same beat twice. The list holds each
move once, `exchange.moves_shown` of them are shown, and it costs no call.

**A sentence-level repeat filter across all speakers.** `sim/textutil.py`
splits a message on sentence enders, skips anything bracketed (a sticker, a
photo) and anything under `exchange.repeat_min_chars`, and calls a sentence a
repeat when it is a near-duplicate of one anybody in the room has said in the
last `exchange.repeat_window_turns` turns. A message more than half repeats is
dropped and logged `[dedup] dropped a bubble ... that echoed <who>`. Used by
the owner's cleaner (`_clean`) for every speaker including her, and by the
participant's writer (`sim/peers.py _room_reply`), which had nothing. A short
deliberate echo is never touched. Flagged and dropped, never rewritten and
never asked for again: a message that says what has already been said is a
signal about the prompt.

**A staleness gate on continuation.** A round is stale when the filter dropped
a bubble in it or when somebody's move was the move they made last time. Each
stale round multiplies the chance the room continues by `exchange.stale_drag`;
two in a row end it with "nobody had anything new". The count is on the record
and in the log.

**Pacing off the actual speakers.** `_availability` reads everybody who spoke
in the last three turns and whoever speaks next -- her own phone access from
the scene when the next turn is hers, the others' own days when it is theirs --
and takes the mean. The existing multipliers, the reasons somebody is away and
the mechanism that puts a person out for the night are untouched.

**The medium, flagged.** The friend-side assembly says what a group message is:
one short bubble, one thought, typed with a thumb; not a diary entry, not three
clauses of interior, not a summary of what everybody has just agreed.
`exchange.group_bubble_chars` is a LOG threshold and nothing else -- a longer
bubble is counted on the room's record and named in the log, never cut, never
asked for again, never rewritten.

**A daily pocket per person.** Three or four concrete things one person could
bring up, assembled at the compile for the day about to start by the call that
already writes each person's day (`tomoe/cast.py write_lives`, one extra key on
an answer it already makes): their own day just gone, whatever they said they
would bring up, one thing going round that they have actually heard, a piece of
the week assigned to them, the beat of their own storyline if one falls now,
and the fixture their week has them at. Each is put in front of one call and
then spent (`sim/pocket.py`, kv `cast_pockets`). A character who runs her own
process builds hers from her OWN material -- her scene, her own circle's chats,
her watchlist, her own record -- in the same shape, in shared code, so a
resident with a circle gets one too, and never from somebody else's roster.

**Gossip that spreads.** An item is born known to the people who would
plausibly have heard it: everybody at that school for a school, a person or a
couple; whoever lives or passes there for a shop, in either language, falling
back to the school when no week names the place; everybody for a thing everyone
has seen. Anyone in the room when an item is stated knows it from then on, which
is read where a turn lands rather than where one is cleaned, so a turn written
by somebody's own process counts too.

**A carry that has to move.** After `cast.carry_about_her_max_streak`
consecutive days of one person's carried thought being about the character, the
prompt says today's is about their own life, and a carry that is still about
her is dropped rather than rewritten. "About her" is her names from
`sim/roster.py`, never a literal, so a recast cannot leave one behind.

## 4. The knobs

| key | default | what it does |
|---|---|---|
| `exchange.repeat_min_chars` | 12 | how long a sentence must be to count as a repeat |
| `exchange.repeat_window_turns` | 20 | how far back in the room the filter looks |
| `exchange.moves_shown` | 8 | how many moves a writer is shown |
| `exchange.stale_drag` | 0.5 | what one stale round does to the chance the room continues |
| `exchange.group_bubble_chars` | 90 | the length a group bubble is counted and logged at |
| `cast.pocket_items` | 4 | how many concrete things a person gets for a day |
| `cast.carry_about_her_max_streak` | 1 | days a carried thought may be about the character before it must move |

All on by default. None is a new switchable section: the ledger, the filter and
the staleness gate live inside `exchange`, the pocket and the carry inside
`cast` (both already assigned to `in_world` in `Config.REQUIRES`), and the
spread of a rumour inside `gossip` (`world_owner`). The two that shared code
reads -- the filter's and the ledger's -- are read defensively, because a
resident has an `exchange` section that is switched off rather than absent.

## 5. What proves it

**In smoke, on every kind of character.** `tools/existence_matrix.py` builds all
forty kinds and now also asserts, on an in-world character, that a rendered cast
turn carries the pocket header and the moves header and that the ask envelope to
a member who writes her own turns carries the moves list; and on a resident,
that she gets a pocket of her own. Each of the four was made to fail on purpose
before it was trusted.

**Offline, on the two rooms that were read.** The scripts under the working
directory for this change replay the transcripts and the arithmetic without a
model call: the filter over both transcripts, the moves ledger and the
staleness gate on a scratch record, the pacing with reachability stubbed, and
the pocket and the seeding on a copy of the save. Nothing is proved by replaying
paid calls.

**Live.** `tools/room_quality.py` on the next room, and the operator's views:
`/lives` names a pocket item nobody ever brought up, and `/gossip` names an item
nobody has heard two days after it was born, the way `/sweep` names a feeling
nothing reads.
