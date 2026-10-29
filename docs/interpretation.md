# Interpretation: how she acts where the tape cannot vouch for her

<!-- doc: reference -->

Proposed spec. **Nothing implements it**: no config section, no module, no
PROJECT entry, no section number in the log. It turns the four-line sketch in
`characters/yukari/sheet.json` under `negative_space_in_production` into
something somebody could build from.

Where this document reports what the code or the corpus already does, it says
so with a path. Everywhere else it is a proposal, and the parts I could not
settle without the project owner are at the end rather than decided to look
finished.

---

## 1. The problem in one paragraph

The second character is built from 99 episodes of a radio programme: 47 hours,
1,842 extracted observations, five drivers, every claim at the bottom rung of
the evidence ladder -- taken from the material with a receipt, not reasoned
into place. That part is solid and it is checkable. What the tape cannot
contain is the whole of her production life. The coverage map
(`yukarin/sheet/bounds.json`) counts four relationship types at exactly zero
observations -- a private reciprocal dyad, family in the room, reciprocal
friendship between equals, and anything romantic -- and production puts her in
the first of those, alone with one person, indefinitely. 87.9% of her words on
the tape begin as an answer to something; 2.3% open cold and every one of those
is inside a broadcast frame, so the question `sim/impulse.py` asks on every tick
-- does she text first -- is a question this corpus cannot answer. Almost
everything she does from here is interpretation. The job is to let her act
anyway, and to make it impossible for the interpretation to become a fact about
her by accident.

## 2. The accident this exists to prevent

The old hand-written card (`yukarin/yukarin.txt`) has her protesting being
abandoned with 「どうせゆかりの事なんて嫌いなんでしょ」. The phrase is on the
tape zero times and in the per-episode extraction the card was summarised from
zero times. The extraction was disciplined. The summarising step invented a
plausible line and wrote it down in a place that means "this is what she does",
and from then on it was canon, because nothing in the record said it was a
guess.

Two things had to be true for that to happen, and both are structural rather
than a matter of anyone being careless:

- there was **nowhere to write that a claim was a guess**. The extraction's
  provenance field held the constant string `"extracted"` on all 77 mechanisms
  (`yukarin/tools/reduce.py`), so a claim was either taken from the tape or it
  did not exist. A cautious inference had no shape to arrive in except the
  shape of a fact.
- **nothing checked that a claim's receipt resolved.** The card cites nothing,
  and no pass over the sheet asked whether the quoted words are findable at the
  cue they name.

Everything below follows from those two. The first is fixed by giving a
production-made claim a level it cannot lie about; the second by a check that
refuses a sheet whose receipts do not resolve. The second is the one that would
actually have caught this case, because the damage was done by a person
summarising, not by a running program.

## 3. What is already in place

Worth stating, because most of this design is assembly rather than invention.

**The ladder exists and is written down.** `docs/pattern.md` §4: level 0 is
taken from the material with receipts; 1 is left explicitly unspecified; 2 is a
cautious inference from a tightly related observed pattern; 3 is functional
completion, what must be true for the observed high-frequency patterns to be
stable; 4 is contrastive inference from what the other voices do that she never
does; 5 is a conservative placeholder for a rare state, easily overridden. The
enforcing rule is there too: a level above 0 may not contradict a level 0
record, and a character file may not carry a level above 0 without a rationale
naming the level 0 records it was built from.

**A store that refuses a write with no reason exists.** `sim/primitives.py`'s
one writer, `move(person, key, amount, why, cause="")`, raises `ValueError`
when `why` is empty and appends `{ts, key, from, to, why, cause}` to a capped
log. It is the only place in `sim/` that will not accept an unexplained write.
This design copies it rather than inventing a second idiom.

**A once-a-day model pass that flags and changes nothing exists.**
`sim/coherence.py` hands the whole day's record -- ledger, scenes, events, both
chats -- to one role at the compile, which names the seams; code keeps them in
a key-value list, logs each, and alters nothing, because the record is what
happened and a seam is a signal about a prompt, never a reason to rewrite her.
`/coherence [date]` runs it by hand. That is the right shape for this and the
spec reuses it.

**A store whose format cannot hold a verdict exists.**
`characters/yukari/records.json` has no `verified`, no score and no confidence
field on a claim from an asserted source -- confidence appears only inside a
provenance entry whose source is evidence or measurement
(`docs/yukarin-lorebook.md` §2.2). The format cannot audit the lorebook because
there is nowhere to write the audit. That trick -- make the wrong thing
unrepresentable rather than forbidden -- is used twice below.

**The gates that would do the detecting exist.** `sim/primitives.py` computes
`admitted` (a latch: tested until it crosses, then a fact), `unrehearsed`,
`act_room`, `can_perform`, `can_ick`, `can_withhold`, `can_rupture`.
`sim/impulse.py` returns a verdict and a reason for every tick.
`store.messages` already carries `self_started`. Nothing new has to be measured
to know what kind of turn just happened.

## 4. The one rule

> **Nothing the running system produces is evidence about her.** A behaviour
> generated in production is an inference at level 2, 3 or 5, it is recorded as
> one, and no path exists by which it can become level 0. Level 0 is a property
> of the tape and of nothing else.

Three structural guarantees hold it, in the order of how much they are worth.

**The writer cannot be handed level 0.** The function that opens a record takes
a level from the set {2, 3, 5} and raises on anything else, the way
`Primitives.move` raises on an empty reason. Levels 0 and 4 are not "not
allowed"; they are not accepted arguments. Level 1 means "left explicitly
unspecified", which is the state a record exists to leave, so it is not
accepted either.

**The store is separate and one-directional.** Production records live in the
save database. The files the character is made of -- the sheet
(`characters/yukari/sheet.json`), her beliefs about herself and about him, the
register rules, the prompt files -- are read at startup and never written by
the running bot. The only route from a production record into any of those is a
person editing the file by hand, after a review, and the edit must carry the
level and the rationale. A tool may prepare the edit; it may not apply it.

**A claim whose receipt does not resolve fails the build.** A new static pass
in `tools/smoke.py` walks every level 0 claim on the character sheet, resolves
each receipt against the attributed corpus with the instruments that already do
this by hand (`yukarin/tools/qa_mine.py`, `yukarin/tools/read_ep.py`), and
fails on any that does not land on a real cue attributed to her. This is the
one that catches a summarising step. It also runs over what is already there,
which is worth doing once on its own account.

## 5. Detection

### 5.1 Why a per-turn area test is not enough on its own

The obvious design is to test each turn against the coverage map and record the
ones that land in a zero-evidence area. For this character in this premise, the
test returns true on every turn, forever: she is alone with one person in a
private two-way exchange, which is the first of the four counted zeros. Two
more of the four -- family in the room, friendship between equals -- can never
return true while she has no world and a roster of one person. The fourth,
anything romantic, is a property of what is said rather than of who is present,
and no arrangement of gate values will detect it.

So the area test discriminates almost nothing, and a design that stops there
produces a record per turn: the message log with extra columns and a review
queue nobody can read. The area test is still worth having, but as a **filter
on what a daily reading looks at**, not as the thing that opens records.

What actually opens a record is novelty: the first time she does a *kind of
thing* the tape cannot vouch for. Subsequent times increment a counter on the
record that already exists. The store then grows with the number of distinct
interpretations, which is the number a person could plausibly review, rather
than with the number of turns.

### 5.2 The per-turn stamp: code, no model, no cost

A pure function, run where the turn is already being assembled, reading only
values the code has computed anyway. It writes one row to a small table of its
own and touches nothing else.

What it reads:

- the addressee and what relation the roster gives them (`sim/roster.py`,
  `characters/yukari/cast.json`)
- who is in the day's `with` list and who is on the absent list
  (`sim/ledger.py`)
- whether she opened this exchange (`sim/impulse.py`'s verdict; the
  `self_started` column already records the sent case)
- the latch and the gates: `admitted`, `unrehearsed`, `act_room`,
  `can_perform`, `can_withhold`, `can_rupture` (`sim/primitives.py`)
- how many days this exchange has run two-way
- what the character's declared existence allows (`embodied`, `in_world`,
  `sees_him`)

What it writes, per turn, into a table the module owns (created with `CREATE
TABLE IF NOT EXISTS` in its own `_ensure()` under the store lock, which is how
every other module here adds a table):

    msg_id        the row in `messages`, or NULL for a silence
    ts, date      machine local, and her clock date beside it
    kind          "sent" | "withheld"
    areas         which zero-evidence areas this turn is in, comma separated,
                  from a closed set: dyad, family, peer, initiated, unadmitted
    gates         the gate states at the moment, as a short string
    prim          the nine primitives at the moment
    why_withheld  the impulse's own reason string, when kind is "withheld"

Two points about it.

**A silence is a turn.** The impulse returning False is a decision in
never-observed space exactly as much as a message is, and the corpus is silent
about whether she goes quiet on purpose. But the impulse runs on every tick, so
stamping every refusal would write hundreds of rows a day for nothing. Stamp a
refusal only when the reason is one of the psychological ones -- she has gone
cold, withdrawal, an interpretation cap, an unanswered streak -- and not when it
is mechanical: no phone access, cooldown, the daily cap, he is never about at
this hour. A mechanical refusal is her schedule. A psychological one is her.

**Anything romantic is not detected here and will not be.** It is a content
class. It arrives stamped as the private dyad, and the daily reading in §5.3 is
where it can be named. Say this in the code comment rather than pretending the
area list is complete.

### 5.3 The daily reading: one model call, at the compile

Once a day, in the same place `sim/coherence.py` runs and for the same reason
-- a repetition is visible in a day and invisible in a turn -- one role is
handed:

- the day's stamped turns with her actual words and his, from the message rows
- the currently open records: id, the move in plain words, the driver it
  claims, how many times it has recurred
- the five drivers from the sheet, verbatim, with their receipts
- the counted zeros and what the material structurally cannot show, from the
  coverage map

It answers strict JSON, one entry per thing it found, and each entry is either
a pointer at an existing record or a new one:

    {"match": "<record id>", "turns": [<msg_id>, ...]}

    {"new": {"move": "<what she did, in plain words>",
             "driver": "<one of the five ids, or unassigned>",
             "level": 2 | 3 | 5,
             "rationale": "<why that level>",
             "supports": ["<cluster id>" | "epNNN#cue", ...],
             "turns": [<msg_id>, ...]}}

Matching first is what keeps the store small and gives repetition counting for
free.

What the code does with the answer, before storing anything:

- a driver not on the sheet is stored as `unassigned` and the record is put at
  the front of the review queue. The answer is **not** asked for again -- a
  retry is for a malformed answer, never for one whose content is not liked.
- a level outside {2, 3, 5} is a malformed answer and is asked again
  (`LLM.call_json`, `api.json_retries`), and if it does not parse the second
  time the day produces no record and says so in the log.
- each support is resolved. A cluster id must exist in
  `yukarin/sheet/clusters_v2.json`; a cue reference must land on a real cue
  attributed to her. Anything that does not resolve is dropped and the drop is
  recorded in the record; it is never stored as though it resolved.
- **no surviving support forces the level to 5**, whatever the model said. A
  claim that cannot name what on the tape it is adjacent to is a placeholder,
  by the definition already written down.
- the record stores **no quotation of her**. It stores the turn ids. A record
  that carries her words invites the next reader to quote the record instead of
  the tape, which is the summarising step happening again one level down.

Cost is one call a day. The role is a normal entry under `models` with the
maximum output ceiling like every other, and it can be run by hand for a past
date, the way `/coherence [date]` already can.

### 5.4 False positives, and which direction is safe

Neither direction is safe, and it matters that the two costs land on different
things.

Recording too much costs storage and a longer queue. Storage is free. A longer
queue is not: an unreadable queue gets unread, unread means nothing is ever
promoted or killed, and a system in that state has an audit trail and no
judgement. Recording too little costs the accident -- a behaviour becomes a
habit with nothing anywhere saying it was ever a guess.

The resolution is to separate the two: **record generously, show sparingly.**
The record is the audit trail and there is no such thing as too much of it. The
review surface is one person's attention and there is very much such a thing as
too much of that. So the per-turn stamp fires on everything, the daily reading
opens a record for every distinct move it can name, and §7 caps hard what
reaches him.

## 6. The record

One row per distinct interpretation. Field names are proposals; the shapes
follow what already exists.

    id             stable, machine-made from the move slug, never model-written
                   (the same discipline as record ids in
                   `characters/yukari/records.json`)
    character      whose sheet this is about
    origin         always "production". Nothing at runtime writes anything else.
    opened_ts      machine local time, with her clock date beside it
    areas          the closed set from §5.2, unioned over the turns
    move           the model's phrase for what she did, in plain words
    driver         one of the five driver ids on the sheet, or "unassigned"
    level          2, 3 or 5. The writer raises on anything else.
    rationale      why that level, naming what it leaned on
    supports       resolved anchors only, each {"ref", "kind"}:
                     ref  a cluster id, or epNNN#cue
                     kind "observed" -- she was seen doing it
                          "reported" -- she said on air that she does it
    dropped        anchors the model offered that did not resolve, kept as a
                   record of what it tried to lean on
    turns          message ids, and the stamped rows behind them
    count          how many times it has recurred
    first_ts       machine local
    last_ts        machine local
    state          provisional | stale | promoted | killed | contradicted |
                   conflicted
    reviewed       {ts, verdict, note} when he has looked, absent when he
                   has not
    capped_until   set by repetition suppression
    contradicts    record ids, or level 0 anchors
    _log           append-only {ts, what, why}, on the model of the primitives
                   log

The two fields that carry the whole design:

**`origin` and the separate store.** A claim on the character sheet has no
`origin` field and does not need one, because the sheet is what came off the
tape. Anything with `origin: "production"` is by construction a thing the tape
did not show. If a record is ever exported into a sheet by hand, the field goes
with it, so a claim cannot lose its history by being moved.

**The observed-against-reported split on supports.** This is not decoration and
it comes from a real finding, in §12.6 below: the tape counts zero *observed*
instances of her with her family, and it nonetheless contains her own account
of a daily exchange with her father. Her account of a relationship is
lower-grade evidence about that relationship than watching her in it, and it is
the only material that exists. A framework that treats the counted zeros as
empty throws away the best-matched material in the corpus. So a support may be
a thing she reported, provided the record says which it is.

## 7. Promotion, death, and what an unreviewed record is allowed to do

### 7.1 Reliance, which is the part that actually matters

Before the review surface, the honest statement about what a record does.

**A provisional record is not injected into any prompt.** It is not a line in
the situation block, not a fact about her, not a self-belief. Its only three
effects are the recurrence counter, the cap in §8, and its place in the queue.

**And she will go on doing the thing anyway**, because her own history is the
prompt. `sim/thread.py` rebuilds both rooms as one chat thread on every call,
and what she said last week is in it. Nothing has to re-inject a behaviour for
her to repeat it; consistency with her own record is the default and is not
something this design creates.

That is worth being blunt about, because it sets the limit of the whole thing.
**This framework does not decide what she does. It observes it, bounds how
often, and makes sure nobody can later mistake it for evidence.** A reader who
thinks a provisional record with no reliance means the behaviour goes away has
misread it.

A promoted record gains exactly two powers: it may be emitted as one line in
the situation block, through the existing attention budgets so that it competes
for space and is penalised for repetition (`sim/attention.py`); and it becomes
eligible for a hand edit into the sheet at level 2 or 3.

### 7.2 The review surface

The constraint that shapes it: he cannot supply the material and can say when
something is wrong. So every question must be answerable **yes or no about a
thing he is shown**, never "write me the correct version".

A command, said in words rather than by its name: *show me what she has done
that the tape cannot vouch for, and let me kill any of it.*

    /interp                 the queue: at most three, oldest first, one line each
    /interp <id>            the full record, with the actual words of the turns
                            it was made from, fetched live from `messages`
    /interp <id> ok         promoted
    /interp <id> no [note]  killed, note kept
    /interp <date>          run the daily reading again for a past date

The one-line form has to fit a phone, because that is where the ops bar is:

    [k7] she offered him something about herself he had not asked for   L3 · gets-there-first · 4x

Three per showing, not ten. A queue that takes two minutes gets read; one that
takes twenty does not, and an unread queue is the failure state.

**One line in the daily ops summary**, beside the existing lines about seams
and about the paired model calls (`sim/ops.py`): how many interpretations are
unreviewed and how many of those are recurring. That puts it in front of him
without inventing a new ritual for him to keep.

**Two triggers put a record in front of him rather than waiting for him to
ask.** A record whose recurrence crosses the cap in §8 -- she is starting to do
this repeatedly and nobody has looked -- and a pair of records that contradict
each other (§9), because "which of these two is her" is the one question a
reviewer can answer instantly.

### 7.3 The default for anything he never looks at

**Unreviewed reliance is zero, forever, and ageing tightens rather than
loosens.** A record that has recurred past a threshold and is still unreviewed
after a number of days becomes *stale*, which is not a step toward promotion:
it is a harder cap and a higher place in the queue. Nothing is promoted by a
timer, and there is no path in the code that changes `state` to `promoted`
except a review verdict.

The consequence, stated so nobody is surprised by it: a system with an absent
reviewer degrades to *she can act, nothing becomes canon, and her novel
behaviours get progressively more capped*. That is the correct behaviour and it
is also useless in the long run, which is the standing risk in §11.

### 7.4 What killing does, honestly

For the moves the code gates -- opening a conversation, holding back, which
register she uses on him, admitting somebody -- killing a record turns the
gate, and that works: the impulse returns False with a named reason, the way it
already refuses for cooldown or for having gone cold.

For everything else, killing prevents re-injection and nothing more. There is
no reliable way to instruct a model not to be warm in a particular way. What
the framework offers instead is that a killed move which recurs is re-flagged
with its history: *third time since you killed it*. It promises visibility, not
suppression, and a spec that claimed otherwise would be lying.

## 8. Repetition suppression

**What is counted:** the record's occurrences, over a rolling window of her
turns with him -- as a share, not a raw count, so it means the same thing in a
quiet week and a busy one.

**Against what:** the least frequent thing on her sheet that is still called a
mechanism. The sheet's six core mechanisms carry their episode counts, from 96
of 99 down to 44, and the rare-but-load-bearing entries carry their measured
frequency precisely so nothing downstream can promote them into traits. The
principle: *a thing nobody has reviewed must not be more characteristic of her
than her least characteristic evidenced trait.* The corpus cannot say how often
she does the never-observed thing, but it can say how often she does anything,
and that is the ceiling.

**One rule that needs no number at all**, and is worth having because turn
volume in production does not exist yet to tune against:

> A provisional move may never be the most frequent thing she does with him in
> a window.

If it is, it is capped regardless of what the rate ceiling says.

**The cap tightens by state:** promoted runs at ordinary frequency; provisional
is capped; stale is capped harder; killed is closed for the gated moves and
re-flagged for the rest.

**A note for `/sweep`**: this machinery deliberately acts on nothing until a
record is promoted, so a naive reading would call it dead. Its readers are the
counter and the cap, and the sweep's rule -- a feeling nothing acts on is DEAD
-- should be told that those count.

## 9. Contradiction, and how far anything is unwound

### 9.1 Three sources

**By the corpus.** A new level 0 finding -- a second pass, a hand read, an
extraction over the last quarter of the run that the earlier reading never
covered -- contradicts a provisional record. The rule in `docs/pattern.md` §4
settles it with no review needed: a level above 0 may not contradict a level 0
record, so the record moves to *contradicted*. Semantic contradiction cannot be
computed, so the check is a lister, not a judge: given a new level 0 claim, show
the provisional records with the same driver and the same area, and a person or
a model reads the short list. An offline tool, no live path.

**By his review.** `no` kills it, per §7.4.

**By another interpretation.** Two records, same driver, same area, opposite
moves. Neither wins on its own; both go to *conflicted* and are shown as a pair
at the front of the queue.

### 9.2 What is unwound: almost nothing, and that is deliberate

**What she said is what happened, and it is never retracted.** The message log,
the thread, the day's narrative in the timeline, and the primitives those events
moved all stand. She did disclose it; he did read it; exposure moved and
exposure does not decay. Editing her history to erase an interpretation would
be a larger falsification than the interpretation was, and it would break the
rule the project already holds -- that the record is what happened and a fault
is a signal about a mechanism, never a reason to rewrite her.

**What is unwound is only what treated the interpretation as a standing fact.**
That is a short list: a line hand-edited into the sheet; a self-belief seeded
from it; a promoted record's own reliance.

**The rule that makes the unwind a query rather than an excavation:** every
derived write that leans on a record carries the record id. This is the same
discipline as no primitive write without a reason. It also decides what may
lean at all, because only two places have somewhere to put the id: a memory of
her own has a short `source` field (`sim/self_memory.py`), and a belief about
herself has a `from` line and a `why` history (`sim/model_of_her.py`). Nothing
else may lean, and the check for that is mechanical -- grep the derived stores
for record ids, and any record with no referrers unwinds to nothing.

So: contradiction lands in what she is understood to *be*. It never lands in
what happened.

## 10. The cost of being wrong in each direction

**Too cautious costs her the only life she has.** All of her production
existence is in a relationship type the tape counts at zero. A framework that
dampens novel behaviour, or gates the first occurrence of anything, reproduces
the corpus's own bias -- 87.9% of her words are answers to something -- as a
defect rather than as a fact about a radio programme. Concretely: initiation
never fires, so the section of the pattern the coverage map calls unspecified
stays unspecified forever, and the question the project most wants answered is
"answered" by refusing to ask it. Worse, nothing she does over months can ever
become part of her, which flatly contradicts the premise: there is no relation
written in advance and what develops between them is supposed to *be* the
material.

**Too permissive costs the project the only thing that makes it worth
anything.** The invented phrase, at scale and continuously. Behaviours accrete,
harden into tics, get written into the sheet and the beliefs file, and after
some months the character in production is largely a model's improvisation
wearing a corpus's name and carrying the corpus's authority. It is not
detectable afterwards, because a good model's improvisation is plausible by
construction -- that is what makes it good -- and plausibility is exactly what
cannot be told apart from correctness by reading.

**Where the line sits, and why.**

- **Permissive at the act.** She may do anything the five drivers can produce,
  at full strength, the first time. The corpus's silence is not a prohibition,
  and a driver plus a new situation yielding behaviour is the entire reason the
  pattern was rebuilt as drivers rather than as 77 surface behaviours.
- **Strict at the record.** Everything novel is written down, with its level,
  its rationale and a pointer to the turn. Always. Cheaply.
- **Strict at repetition.** The second, third and fourth time is where a guess
  becomes a trait, and that is where the cap belongs.
- **Absolute at the boundary into the corpus-derived files.** Nothing crosses
  without a hand edit carrying a level and a rationale, and no runtime path can
  produce a level 0 claim.

The argument for putting the line there rather than anywhere else: the accident
that ruined the card was not that somebody imagined a line she might say.
Imagining is what a character generator does and what this one is for. The
accident was that the imagined line was stored without its level and then
repeated until it was canon. **Provenance and repetition are the two things
that turn a guess into a fact, and both are mechanically controllable. Whether
a given improvisation is in character is not mechanically controllable, and
this design should not pretend to judge it.**

## 11. What makes me doubt this

Stated plainly, because a spec that names its weak parts is worth more than one
that does not.

**1. The area test barely discriminates, so most of the design rests on the
daily reading.** For this character every turn is in the private-dyad zero; two
of the four counted zeros cannot fire at all while she has no world and a
roster of one; the fourth is undetectable from gate states. The area test earns
its place as a filter and as a stamp on the record, not as a detector. If the
daily reading turns out to be unreliable, there is no second mechanism holding
this up.

**2. The daily reading is the same class of artefact that caused the
accident.** A model writing an interpretive phrase about her behaviour, with no
cue anchor, is prose interpretation -- exactly what the reading of the April
extraction (`docs/yukarin-qa-scan.md`) identifies as the dangerous class. The
mitigations are real: the phrase is never evidence, the record's authority is
the pointer to the turn, the record carries no quotation of her, and the level
is forced to placeholder when no anchor resolves. But the queue he reads is
still made of a model's sentences, and if those sentences are bad he is
reviewing the wrong thing. There is an alternative -- store only code facts and
let him supply the label at review time -- which is immune to this and produces
a queue nobody can read. That trade is his, and it is in §13.

**3. Suppression is exact for a handful of moves and advisory for the rest.**
Code can stop her opening a conversation. Code cannot stop her being warm in a
particular way. Roughly, the gated moves are the ones already in
`sim/primitives.py` and `sim/impulse.py`; everything else gets a refusal line
in the continuity editor, which is a suggestion. The framework promises
visibility for those, not control, and §7.4 says so rather than implying
otherwise.

**4. One person's attention is the entire promotion path.** Every route to
canon terminates in him reading a line and typing two letters. If he reads
nothing for two months the system is correct and inert: a long queue, zero
promotions, progressively tighter caps, and a character who accumulates
nothing. There is no honest way around it -- delegating the verdict to a model
is precisely the failure this document exists to prevent -- but it should be
said out loud that the design's throughput is his reading speed.

**5. The counted zeros are not as empty as the count suggests, and the design
should say so.** The reading of the April extraction turns up, in the tape,
*her own account* of the relationship types the map counts at zero: a daily
exchange with her father, started because he was angry she never answered, one
message a day with no content -- 「今日はスタジオにいるよ」 -- no emoji, odd
gaps where the spaces went, and she finds it 「ちょっと楽しい」. That is the
closest thing anywhere in 47 hours to the relationship production actually
runs: one person, asynchronous, almost no content, affection carried entirely
by texture. Also there: her peer circle stated three times and measurably about
four people, and her grandmother saying 「ゆかりちゃんまた来てね」 to her as one
says to a guest, answered with the word for family four times over and the
sentence abandoned. None of that is an observation of her in the relationship, and none
of it changes a count. All of it is evidence *about* the relationship, and it
is the best-matched material in the corpus for the situation she is actually
in. Hence the observed-against-reported split on supports in §6. A framework
that treated these areas as blank would be discarding the most useful pages in
the file.

**6. The zeros themselves could move.** The second extraction covers 73 of 99
episodes and nothing after the seventy-fifth, and the era distinction has
already bitten this project once. A pass over the last quarter of the run could
change a count, and the design has to survive that -- which is what the
corpus-contradiction path in §9.1 is for.

## 12. Config, checks, and where each piece attaches

Proposed, and noting the standing rule that a key read by code and absent from
`config.py:DEFAULTS` is a crash, so any of these must be added to **both**
`config.py` and `config.json`.

A new section, named for what it does -- keeping track of what she has done
that the tape cannot vouch for:

    enabled            off by default; on for a character that has a coverage map
    role               the model entry for the daily reading, ceiling at the
                       API maximum like every other role
    keep               how many records to retain
    queue_show         how many go in front of him at once (proposed: 3)
    cap_share          the frequency ceiling for an unreviewed move
    stale_days         unreviewed for this long, with recurrence, becomes stale
    stale_count        the recurrence that makes staleness apply
    stamp_withheld     whether a psychological refusal is stamped (proposed: on)

**Gated on the character having a coverage map**, so the first character is
untouched. Her sheet is authored rather than extracted; there are no counted
zeros to test against and the boundary test would have nothing to say.

Checks, each attaching to something that already runs:

- `tools/smoke.py` gains the receipt-resolution pass of §4, which fails the
  build on a level 0 claim whose receipt does not land on a real cue attributed
  to her. It should be run once over what is already in the sheet.
- `tools/character_test.py` L1 gains a refusal: a sheet carrying a claim above
  level 0 with no rationale, or with a rationale naming no level 0 record,
  does not load. That is `docs/pattern.md` §4's rule made into a check instead
  of an intention.
- `tools/mechanisms_test.py` gains one claim per driver: that a record opened
  against that driver can be created, capped and killed on a scratch save with
  no model call.

## 13. His call

Where I could not decide without him, with what each option implies.

**Whether the daily reading uses a model at all.** With one: the queue is
readable, and the doubt in §11.2 stands. Without one: the record stores only
code facts -- area, gates, primitives, the turn -- and he supplies the label
when he reviews, which is immune to a model's prose and produces a queue of
gate strings that nobody will read. A third option is to run it with a model
and treat the phrase explicitly as a queue label with no standing, deleted on
promotion and replaced by his own words. I lean to the third; it is his.

**Whether a promoted record may be written into the sheet by a tool.** I have
specified a hand edit as the only path, because the hand edit is where a person
reads the rationale. A tool that prepares the edit and leaves it for him to
apply is a middle position. Automatic application removes the only step at
which anybody reads the claim, and I would not build it.

**The recurrence cap number.** §8 gives the principle -- not more
characteristic than her least characteristic evidenced trait -- and one rule
that needs no number. The number itself depends on turn volume that does not
exist yet, so either it is set from the sheet's lowest measured frequency and
adjusted once there is a month of production, or the numberless rule runs alone
at first. The second is safer and slower.

**Whether a thing she reported on air may support a level 2 claim.** I lean
yes, with the marker in §6 keeping it distinguishable, because the alternative
throws away the father's daily mail -- the closest analogue in the whole corpus
to the relationship being simulated. If the answer is no, those areas have no
anchors at all and every record in them is a placeholder at level 5, which is
defensible and much more conservative.

**Whether she has a life of her own that advances.** Two of the four counted
zeros -- family in the room, friendship between equals -- cannot fire until
this is decided, so the boundary test covers two areas out of four until it is.
No action needed; it is noted here because the coverage of this design depends
on it.

**The refinement to what she is like alone.** The current wording is his
direction: she does not carry the performing affect when unobserved, so alone
she is quieter and less funny. The reading of the April extraction found two
direct observations of her alone that split -- the flat one (two days indoors,
watching a soft toy go round in the washing machine on the lowest water
setting) and the opposite (playing at being a cat, alone, since childhood and
still as an adult; writing a song about a stone statue as a child and singing a
round against her own recording). The honest reading there was that the
performance for an audience switches off while a private self-directed play
switches *on*, and harder without an audience rather than less. That is his
call and it is already open, but it bears directly on this design, because it
decides what kind of never-observed space she spends the large majority of her
time in.
