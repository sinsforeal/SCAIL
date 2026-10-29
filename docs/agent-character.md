# A character who runs herself: what she needs, and how you know she has it

One of the people on a character's roster can be promoted into a character of
her own: her own process, her own config, her own save, her own voice, still
standing in the world she came from and still in its rooms, but writing every
word she says herself. `docs/promotion.md` is how she is made and
`docs/peer-talk.md` section 4b is the wire she speaks over. This document is
the third thing, and it is the one that was missing: what has to be TRUE of her
once she is running, each thing as a numbered invariant, with the check that
proves it and where that check lives.

It exists because the checks that ran before the fourth character's first day
all passed and none of them could have caught what went wrong. `tools/new_character.py`
in its verify mode, `tools/existence_matrix.py` and `tools/agent_seam_test.py`
are all structural: one process, a scratch save, the model stubbed, nothing
advancing. Every fault found afterwards was runtime behaviour on the seam over
a day beside the character who keeps the world. The two records are
`data/retired/20260907_203328_rena_audit/REPORT.md` (a read-only audit after
one day live) and `data/retired/20260907_210559_rena_fixes/REPORT.md` (the
repairs). Read them for the evidence; the invariants below are what they add up
to.

Two tools close the gap and are named throughout: `tools/agent_rehearsal.py`
lives one day of her clock with both processes up on copies of the live saves,
and `tools/agent_audit.py` reads a running character and says whether she is
working. Neither spends a penny.

---

## 1. What a running character is

Seven things, and she is not one until she has all seven.

| what | where | who writes it |
|---|---|---|
| a bundle: one directory that is one person | `characters/<key>/` | `tools/promote_cast.py`, then the author |
| a sheet, with the five existence answers | `characters/<key>/sheet.json` | promotion, from her roster row |
| a config composed from the bundle | `config_<key>.json` | `tools/new_character.py` in its compose mode |
| a save of her own | the `db` her manifest names | her first boot |
| a row in the operator's register | `characters.json` | compose, once her manifest says she is registered |
| a launcher and a scheduled task | `<key>.cmd`, `SCAIL_<key>` | compose stages the launcher; `restart.cmd` makes the task |
| the mark on her row in the world's roster | `agent: "<hub id>"` in the owner's cast file | the author, by hand |

The last one is what makes her an agent rather than a fifth process. Without
it the character who keeps the world goes on writing her words, and the two of
them are two people with the same name. With it, one line in the owner's
roster changes everything downstream: `sim/roster.py` reads it back through
`is_agent`, `agent_of` and `by_agent`, the room writer refuses to build a
prompt for her, and the day planner refuses to write her line.

**The five answers on her sheet decide what she is made of.** `embodied` (a
body that eats, sleeps and gets cold), `in_world` (people around her and
places to be in), `sees_him` (any window on his machine at all: `digest`,
`resident` or `none`), `has_account` (a public account of her own) and
`with_him` (whether she has a chat with him at all, `none` for a character who
exists for somebody else's circle). Two more follow rather than being
answered: whether she KEEPS the world she is in, and whether her sheet's
`sees_him` answer of `none` switches off everything that reads his machine.
`Config.REQUIRES` maps every switchable section to the property it needs, and
`sim/existence.py` answers the same questions where an OBJECT or a WORDING
depends on them rather than a section flag.

---

## 2. What the tools derive, and what is authored

The promotion tool writes what her roster row and her sheet already contain.
Nothing else is derivable, and the difference is not a matter of effort: a cast
row says who somebody is to the character whose world it is, and it does not
say where she lives.

**Derived, and correct without a hand on it:** her bundle manifest; her sheet
with the five existence answers and the reason beside each; the holes her
prompts fill; her gauge baselines with the behaviour sentence beside each; her
birth window; her bible and her speech guide seeded from her sheet and her
voice line; her roster identity; an empty save seeded from her roster. Then
compose writes her config, her prompt directory, her register row and her
launcher, and verify checks that none of it is somebody else's.

**Authored, and it stays authored:** her household as a file; her map, with an
address, a station, a walk and a ward; her flat and what is going round for
her; her own day beyond her week (fixtures, habits, curfew, twists); her bible
and speech guide finished from the seed into a voice; what she believes about
herself and about him; the numbers for her own people. Drafts of the first four
can be asked for and every invented value marked, but a draft is a draft.

**Mechanical and still by hand:** the `agent` mark on her row in the owner's
cast file, and the operator's own restart.

Two corrections to how this list has been told before. It has been called
seamless, and it is not: it is eleven steps of which four are real authoring,
and calling it seamless is what let a day of runtime faults be reported as
"every check passed". And "every check passed" was true of eight structural
checks that between them could not see a single one of the twelve invariants
below.

---

## 3. The runtime contract, as invariants

Each one is a sentence about what must be true while she is running, the check
that proves it, and where that check lives. Every one of them is a thing that
was false in production and nothing said so.

**1. A beat planned for her survives the planner.**
The character who keeps the world plans WHEN she reaches for somebody and about
what, and writes none of her words. A beat with no words in it is exactly what
the ask path is for, so the line that drops a wordless beat makes an exception
for a marked speaker (`tomoe/cast.py`, `plan_day`).
*Proved by:* `tools/agent_rehearsal.py`, which drives the real planner with a
canned day script and asserts hers is in what comes back; and a case in
`tools/agent_seam_test.py` that asserts a wordless beat for somebody the
process DOES write for is still dropped.

**2. The ask reaches her mailbox at the beat's own hour, not at the day
boundary.**
`CastEngine.deliver` puts the moment in her mailbox when the beat comes due, and the
beat is marked with when it was asked (`agent_asked_ts`) so a restart does not
ask twice.
*Proved by:* the rehearsal, which compares the hour the ask went out against
the hour the beat was planned for.

**3. A moment she is offered and does not take is a decision, not a failure.**
An empty answer to a beat marks it done and says she opened with nothing; a
beat nobody answers inside `exchange.agent_beat_deadline_seconds` is dropped
AND marked done, so it stops coming due for the rest of the day.
*Proved by:* `tools/agent_seam_test.py`.

**4. A silence she chooses settles the wait at once.**
The messenger refuses an empty body, so a silence travels as a token in the
text and as a flag on the envelope (`sim/rooms.py`, `SILENT`), and the room
reads the flag. A deliberate silence and a dead process were indistinguishable
to the room, and she paid for an answer while the room sat out its full
deadline.
*Proved by:* the rehearsal, which answers her second ask empty on purpose and
asserts the owner's wait is settled with no deadline line and neither record
gained an empty turn; and four cases in `tools/agent_seam_test.py`.

**5. A relayed turn is filed under whoever said it.**
Which side of a room a process is on is decided by whether it OWNS the room,
and it owns a room when it has a membership for it (`sim/peers.py`,
`_room_message`). The test used to be a roster lookup on the sender, and the
row of the character who KEEPS a world carries her own hub id in the file
everybody in that world reads, so in a reader's process every relay from the
only process that ever wrote to her was filed as the owner speaking for
herself: into the owner-side queue that nothing on her side drains, with the
real speaker thrown away.
*Proved by:* the rehearsal, which asserts the other speakers' turns arrive
under their own names and the owner-side queue is empty at the end of the day;
and `tools/agent_audit.py`, which compares her record of a room against the
world file's own rows for the same turns.

**6. Nothing that reads his machine is BUILT for a character who has no sight
of it.**
What she has not got is absent, not switched off. The app that reads his
machine is not constructed at all when her sheet answers `sees_him: none`
(`sim/existence.py`), the way the calendar loads no data for a character with
no world. Before that, only the role it fed was off: her phone-app open fired
fifty-one times, wrote a row to her save each time, and logged a line about how
long he had been quiet.
*Proved by:* the rehearsal, whose table of what each section owns in a save is
compared before and after a whole day; and the audit, which asks the same of a
running save and distinguishes a row written since her last boot from residue
nothing has retired.

**7. Nothing about him is written into the save of a character who has no chat
with him.**
Five helpers that are on for everybody were writing rows about a man she had
never spoken to: how much of her day was him at the compile, how much she cares
about him once a day, what being on her phone with him cost her with her own
people, how much she is missing him, and what he is to her. The guard is the
question her sheet already answers (`sim/existence.py`, `has_chat`).

The fifth was the last and the quietest. The layer that holds what a person is
to her opens a row for anybody it is asked about and saves it, so the first
reader at boot that asked what he is to her created an all-zero row about him
and the save then held it for good. It is refused at the source now
(`sim/sentiment.py`): a row about him is not opened by a read, not seeded and
not written for a character with no chat with him, and a reader is handed a
fresh all-zero dictionary that is never saved, so nothing downstream had to
learn about the absence. The keys refused are his name on her sheet and the two
conventions, because her relationship table has no row for him at all and every
call site falls back to the literal one.

*Proved by:* the rehearsal, which watches the eleven keys the boot repair pass
retires (`sim/repairs.py`) and fails if any is written back during the day; and
the audit, which reports what is left in a live save, the sentiments included.

**8. A gauge whose owner section does not run is not built, and nothing writes
one she has not got.**
A gauge is taken out of the spec when the section that owns it is off, so the
state is built without it, the mood computation does not average in a constant,
and the store stops holding it. And code that writes a gauge directly checks
that she has it first: warmth toward him went on being written onto a character
whose config no longer built it, which put it back into the store after the
spec had taken it out.
*Proved by:* the rehearsal, which compares her store after a whole day against
what her config builds; and the audit, on the live store.

**9. What she carries is headed for the kind of character she is.**
The headings over what she is holding, what she is into and what she has told
people fork on whether she has a chat with him at all, in her own language.
Three of them read "what you told HIM" over four lines about what she had told
two of her own friends.
*Proved by:* the rehearsal, which renders the block twice with the one answer
the fork reads turned each way and asserts the headings differ. Structurally,
not by looking for a word: a word is what the fork exists to remove.

**10. A diary fires on her own day.**
`sim/diary.py` gates on her hours, her phone being free, and something she is
sitting on. A promoted character went two evenings inside her configured window
without the key existing.
*Proved by:* the rehearsal, which lives the evening and, when nothing is
written, names the gate she is standing at in the words `Diary.may_write`
itself uses.

**11. Only her rows, under her id, about her.**
A world has one writer for everything its owner owns and a partition for
everybody else in it (`world/shared.py`, `_may_write`): three tables, rows
about herself only, under her own id and a source naming her own planner.
*Proved by:* `tools/world_reader_test.py` and `tools/world_test.py` on a
scratch world, and the rehearsal on a copy of the real one, which reads every
table that carries a person and resolves who each row is about through the
roster.

**12. She invents nothing for the owner's people.**
A director event is an invention, and a character who only READS a world
invents for her own circle and nobody else; what somebody is going through, and
whether she saw them today, is decided by whoever keeps that person.
*Proved by:* the rehearsal, which reads her cached relationships and her record
of each person's day and fails on a situation, a last-seen or a day written for
somebody who is not hers.

**13. Her prompts name no other registered character.**
*Proved by:* `tools/character_leaks.py` on her newest run, `tools/prompt_leaks.py`
on every role prompt of hers, and the rehearsal, which renders her system
prompt and what she carries and reads them for every other registered
character's names and places.

**14. Who was in the room is the room's own membership rule.**
The group chat is the friend group and somebody's household is out of it
whoever it is (`sim/roster.py`, `witnessed`), and who witnessed a turn comes
from `sim/rooms.py`, `members_for` rather than a second walk over the roster
that can disagree with it. A promoted character's mother and brother were in
the witnessed set of every turn in a school group chat while the membership
correctly kept them out.
*No automatic check covers this yet.* It is enforced at the two sources and
read by eye in the world file's own rows.

**15. Nobody plays the same move twice, and everybody has something of her own
to bring.**
Three things that landed together. A room keeps a ledger of the moves it has
already made, rendered into the next call (`sim/rooms.py`, `moves_block`), so a
speaker can see she has already played "fine, I will ask, but I am still the
one who decides". A turn that repeats what its own speaker already said in the
same conversation is dropped (`tomoe/exchange.py`). And each person gets a
pocket of three or four concrete things she could bring up today, assembled
from her own material and marked once used (`sim/pocket.py`), with a character
who runs herself filling her own from her own circle and never from somebody
else's roster.
*Proved by:* `docs/room-quality.md`, which is the spec for all of it and names
the eight measures and the tool that reads them off a save. These are about
believability rather than mechanism, and no check settles them on its own.

**16. What is going round is made relevant to her by a place she has.**
A national story is made hers by a line a model writes, and the model that
writes it was shown her taste sheet and the calendar and not her map. Hers gave
her a commute along a line her own map does not put her near, to a class on the
other side of the city. The judge is `world/rails.py`: it reads the lines she
rides and the stations she uses out of her own map and her own train watch, and
refuses a sentence that names a railway nothing in her life touches, or one
that runs near her and says she is on it.
*Proved by:* the fetcher and the reader, which both put the line through the
judge before it can be shown; and the rehearsal, which puts every line already
on her disk through the same judge and fails on what it refuses. The step
itself runs in a tool on its own clock rather than in the loop, so a rehearsal
of one day never exercises the writing of a new one.

---

## 4. The procedure

**Promote.** `tools/promote_cast.py` writes the bundle from her roster row, her
sheet and her mechanisms file. It refuses to edit the owner's roster for her.

**Author the holes.** The four files in section 2, her bible and her speech
guide, what she believes, and the numbers for her own people. Her boot refuses
to start with a person's file missing from a subsystem that is on, so the list
is not optional; the tool prints it.

**Mark her row.** `agent: "<hub id>"` in the owner's cast file, by hand. Until
this is there she is a second process and not an agent.

**Compose.** `tools/new_character.py` in its compose mode writes her config,
her prompt directory, her register row and her launcher, and copies the
machine's secrets in.

**Verify, structurally and then over a day.** `python tools/new_character.py
verify <key>` makes nine checks: eight structural (no hole in a role prompt,
no other character's name in her prompts or her seeded save, no file of hers
byte-identical to somebody else's, her own key resolves to her, no name means
two people, the owner of the world she reads is on her roster, every meter is
on somebody she has, her config agrees with her sheet, every one of her own
people's meters is a number somebody chose) and then the ninth, which runs the
rehearsal. Or run it alone:

    python tools/agent_rehearsal.py <key>
    python tools/agent_rehearsal.py <key> --root <dir>    # a bundle nobody has registered
    python tools/agent_rehearsal.py <key> --verbose       # with both processes' narrative

It copies the owner's save, her save and the world file to a temporary
directory, builds BOTH characters against the copies with the model, the
network and the browser refused and the hub living in the process, and advances
one clock that both of them read through a day. It takes about twenty seconds
and spends nothing. `tools/smoke.py` runs it for every registered character who
reads a world she does not keep.

**Start her.** `restart.cmd <key>`, which runs smoke first and refuses to start
anything if it fails, and creates her scheduled task when it is missing. A bot
started as a child of a tool's shell dies silently minutes later; the scheduled
task is the only way in.

**Read the log on day one.** Six things say the wire is alive, and all six are
lines you can look for:

  * her boot printing what her sheet switches off, and the tool list the pick
    is offered, which is the receipt for her sheet reaching the moment she
    decides anything;
  * `registered '<hub id>'`, and whether she is hidden;
  * in the OWNER's log, `asked '<hub id>' with N turn(s) she had not seen`;
  * in HERS, a `peer_reply` call with a cost, seconds later;
  * back in the owner's, her turn going into the record;
  * and the absence of any line saying she did not write within the deadline.

**Audit her on day two.**

    python tools/agent_audit.py <key>
    python tools/agent_audit.py <key> --verbose

Fourteen questions of a running character, in about two seconds, reading
nothing but read-only handles: her process against her own row's pattern, her
registration and whether his phone lists her, every ask matched to what her
process did with it, the beats the owner planned per person per day, the age of
her owner-side queue, her record of a room against the world file, anything a
switched-off section has written, her gauges against her config, what is left
about him, a person carrying the same thing three days running, a log line
repeating faster than anything real, tracebacks and error lines, and what she
has spent by role since her newest boot. `ok`, `WARN`, `FAIL`, and exit 1 on
any failure.

---

## 5. What none of this proves

The rehearsal answers every model call from a canned reply. So the words in the
room are the recorder's, and nothing it says bears on voice, believability,
pacing, or whether the character is anybody. It asserts the SHAPE of an answer
and never its content. It does not touch the network, the real hub process, the
scheduled tasks or a restart. It lives one day, so a carry streak, an opener
repeated on Thursday that was used on Tuesday, or a room that goes stale over a
week are outside it. And it rehearses the seam: the owner's own day is only
driven as far as the seam reaches into it.

The audit is mechanical throughout. Every question it asks has a right answer
that can be counted, and none of them is whether she is worth talking to.

That question is answered by reading her. Take a day of the room she is in, in
full, both before and after some change, and read both: what she reacts to,
whether she catches an error nobody else caught, whether she plays the same
beat twice, whether somebody who is absent from the conversation reads as
absent. `docs/peer-talk.md` section 4b has the shape of that read and the first
one done. It costs an hour and there is no tool for it.
