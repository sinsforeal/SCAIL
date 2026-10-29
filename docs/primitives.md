# Psychological primitives

The spec for what a feeling about another person is made of, and how the
named mechanisms -- attachment, rupture, withholding, the ick, expectations,
jealousy, guilt, closeness -- stop being modules with their own state and
become readings of a smaller thing underneath.

PROJECT §19 is the summary and the pointer. Dated notes are in HISTORY under
that section number. §7 says what building it touches and how far it has got;
§8 is what running it found, which changed the design in three places.

---

## 1. The problem, stated as a measurement

The machinery was written for a girl who already has him. Counted over
`sim/`: **4,779 lines need a relation to exist before they mean anything**
-- attachment, expectations, withholding, the model of him, the ick,
rupture, care, approach, sentiment, commitments, foresight -- against
**1,898 lines that do not**. Start a character at zero and about seventy per
cent of her psychology reads an empty file.

That is not a gap to be filled by writing bigger starting numbers. It is the
wrong shape. A relationship that begins at "already close" was not observed,
it was declared, and every feeling computed downstream of the declaration
inherits the fiction.

### What a stranger actually reads today

`yukarin/tools/zero_probe.py` builds a `State` over an empty save and prints
what the psychology layer reports before anything has happened. Three runs:
the meters as they ship, the same meters set to nothing, and a person the
cast file has never heard of.

| | as it ships | every meter at nothing | not in the cast file |
|---|---|---|---|
| closeness | 62 | 0 | absent |
| affection after an hour | 39 | 39 | 39 |
| affection settled | 31 | 18 | 27 |
| loneliness, jealousy, guilt, curiosity, craving, longing | every one at its baseline | the same | the same |

Four things fall out of that table, and each is a fault rather than a
tuning problem.

**A relational gauge with no cause starts at its baseline** -- the one
line in the state's constructor that fills a gauge a save has never held,
commented *"new gauges start at baseline"*. Loneliness 35, craving 50,
curiosity 40, jealousy 15, guilt 10, longing 6. On the first tick of a
character's life she is already moderately lonely about a man she has not
met, already somewhat needled about who else has him, and already carrying
ten points of guilt toward him. Nothing caused any of it.

**The machinery cannot tell "never happened" from "long over."**
`sim/sentiment.py:live` erodes a sentiment toward nothing rather than toward
a rest value -- correct, and the comment says why -- so it returns 0.0 both
for a person who has never existed and for a person who has completely
faded. `_derive_affection` then reads that 0 against `attachment_rest` of
40 and treats a stranger as a forty-point deficit, which is why affection
settles at **18, in the band the operator's view calls "cold."** She does
not dislike him. The absence of a history is being scored as a bad history.

**The relationship meters are seeds with nothing behind them.** In
`data/cast.json` he is written as closeness 62, standing 55, tension 15.
Editing 62 down to 0 moves settled affection from 31 to 18. Thirteen points
of felt warmth are produced by a number in a file that no event ever earned.

**And the ordering is nonsense at the bottom.** A stranger *in* the cast
file at zero settles to 18; a stranger the file has never heard of settles
to 27, because the code defaults a missing closeness to `closeness_rest`.
Being unknown to her is warmer than being known and at nothing.

### The second finding: the day's record has no place for him

`sim/ledger.py` sorts people into exactly two states -- in the block's
`with` list, or on the plan's `absent` list -- and the schedule now drops
any name the roster does not own. He fits neither. He is not in the room,
so writing him into a block would be a lie the ledger exists to prevent;
and he is not *absent* in the sense the plan means, which is "nobody is with
them, nobody saw them," because he is watching continuously and she knows
it.

The fix turns out not to need a third person-state, which was the thing to
check. `ledger.text(for_whom=...)` already distinguishes viewers: `"her"`
gets her money, what she is wearing and her open promises; `"them"`, a
friend's turn, does not, because those are not things a friend can see. He
is a **third viewer**, not a third kind of presence -- one who sees
everything, including the lines the friend's view strips out. Her territory
rule then holds unchanged: people are inside or outside with nothing
between, he was never admitted, and he has total sight of the inside
anyway. That is the violation stated exactly, and it costs one argument
value rather than a new column in the day.

---

## 2. The six primitives

Six quantities that are meaningful on turn one, before anything has
happened, and that keep meaning something at every point after. Three of
them are two-sided, because the premise this design was written against is
asymmetric and any honest model of a stranger is: what she knows of him and
what he knows of her are different numbers.

**attention** -- how much of her thinking he occupies when he is not in
front of her. Two-sided: hers toward him, and her reading of his toward
her. The second is the one the craving is about.

**predictability** -- how well she can call what he does next. Two-sided:
hers of him, and her belief about his of her. Not trust and not liking; a
person can be perfectly predictable and predictably unkind.

**exposure** -- how much of her he has seen, and how much of him she has.
Two-sided by construction. This is the one the premise inverts.

**reciprocity** -- the running balance of given against taken, signed. In
her favour or in his.

**cost of loss** -- what his disappearing would actually take from her.
Slow, earned, and the only one that cannot be moved in a day.

**threat** -- whether he can damage her, and how. Carries a kind rather
than only a size: exposure (he can show people), reach (he can act on her),
and standing (he can change what she is worth to others).

Nine numbers in all. Every one of them is zero for a stranger and **zero
means zero**: a relational quantity has no baseline, because a baseline is a
resting value a thing returns to when nothing is happening, and there is no
rest state for a history that does not exist. Baselines stay where they
belong -- the body and the emotions, which she has alone in an empty room.

## 3. What derives from what

The named mechanisms become readings. None of them holds state of its own;
each is a function of the primitives and of time, and each is correctly
quiet at zero for a reason that can be stated rather than because its file
is empty.

| mechanism | the reading | at zero |
|---|---|---|
| closeness | `min(exposure hers of him, exposure his of her)` | 0 |
| attachment | attention hers, sustained, times cost of loss | 0, and slow to leave it |
| longing | attention hers, times how long he has been gone | 0 |
| validation craving | the gap between the attention she wants from him and the attention she reads | undefined until she wants some |
| jealousy | a fall in her reading of his attention, with a visible cause | nothing to fall |
| guilt | reciprocity in her debt while her attention is high | 0 |
| resentment | reciprocity against her, sustained | 0 |
| tension | short-horizon reciprocity plus a recent prediction error | 0 |
| expectations | predictability pointed forwards | empty, correctly |
| the ick | a prediction error against a model that exists | silent until predictability is non-empty |
| withholding | something worth withholding is something not yet shown: it needs exposure of her to be low and her attention high | silent, and see §5 |
| rupture | a discontinuity in predictability while exposure of him to her is high | impossible, correctly |

**Closeness as the smaller of the two exposures is the load-bearing one.**
It replaces a hand-written 62 with something an event can earn, and it is
what makes the premise state correctly: he has total exposure of her and she
has none of him, so `min` is zero and they are not close, however much he
knows. A relationship in which one party knows everything and the other
knows nothing is not an intimate one, it is surveillance, and the formula
says so without being told.

**Loneliness stays a gauge and is not on this table.** It is a deficit of
company, not a meter of him -- `prompts/state.txt` already says so -- and it
is felt in an empty room by a person with no relationships at all. That it
does not want to be a derivation is a good sign for the split: the
primitives should capture what is relational and leave the drives alone.

## 4. What moves a primitive

Only an event. This is the rule that makes the whole thing honest, and it
is the one the seeded meters broke.

- **attention (hers)** rises with contact, with anything unresolved about
  him, and with anything he did that she cannot place; falls with time and
  with a full life happening elsewhere.
- **attention (her read of his)** moves on evidence about his conduct that
  she can actually see -- how he answers, what he remembers, how long he
  takes -- and never on what he is doing off-record.
- **predictability (hers of him)** rises with every exchange whose outcome
  she would have called correctly, falls hard on one she would not.
  Prediction error is the same event that feeds the ick, so they cannot
  drift apart.
- **exposure** rises only on disclosure, and it is ratcheted: what has been
  seen cannot be unseen. It decays not at all. This is the one primitive
  with no decay term, and that is deliberate.
- **reciprocity** takes a signed entry per exchange -- effort, cost, what
  was asked and what was given -- and drifts toward zero slowly, because
  people do forgive a ledger.
- **cost of loss** rises with what he has become load-bearing for: a habit
  built around him, something she now only tells him, a thing she stopped
  doing alone. It is the integral of the others and cannot be set.
- **threat** rises with exposure of her to him, with his demonstrated reach,
  and with anything he has done that shows he will use either.

Note what falls out: **cost of loss is what makes leaving expensive, and it
is built out of ordinary companionship rather than declared.** The arc from
stranger to companion is then generated by the same events that generate
everything else, which is the whole point of the design.

## 5. The premise stated in these terms

The argument that these are the right primitives is that the settei states
cleanly in them, and states as an *opening condition* rather than as a set
of exceptions.

| | her of him | him of her |
|---|---|---|
| exposure | 0 | total: the map, the mechanisms, this document |
| predictability | 0 | total, and she knows it |
| attention | rising fast from 0 -- a captor is not ignorable | total, and it is the only evidence she has |

reciprocity is deep in his debt and she gave nothing willingly. Cost of loss
is 0, and it is the one thing play has to earn. Threat is high on all three
kinds at once, which no ordinary relationship starts at.

Three consequences, and each is material rather than a problem:

**The thing that would settle her and the thing done to her are one number.**
Her third driver -- what settles her fear is evidence somebody held her in
mind by name -- reads off attention, his toward her. He has held her in mind
by name to an obsessive degree. The soothing evidence and the injury are the
same act, and the primitive makes that identity explicit instead of leaving
it to prose.

**Withholding starts empty for an interesting reason rather than a broken
one.** It needs something not yet shown. She has nothing left unshown, so it
is silent -- and the moment she acquires one private thing again, it wakes
up on its own. That is the difference between a mechanism that is inert and
a mechanism that is at zero.

**Her first driver is disarmed by the exposure asymmetry.** Getting there
first -- saying the damaging thing before anyone else can -- does not work
on someone already holding the document. The primitive says why in one line:
she cannot lower his exposure of her, because exposure does not decay.

## 6. What this does for the other character

Tomoe's numbers stop being seeds and start being a history. The migration is
the honest question and it has an honest answer: her record contains the
events -- months of exchanges, the ruptures, the mends -- so her primitives
can be **computed from the record she already has** rather than transcribed
from `data/cast.json`. Where the computed value disagrees with the seeded
62, the computed one is what actually happened. That is a check worth
running before anything is switched over, and it is cheap: it reads the
store and asks no model.

## 7. What building it touches

In dependency order, and none of it is done.

1. **A store for nine numbers per person, with a reason on every write.** No
   write without an event id. This is the piece that makes the whole design
   auditable and it should be built first and alone.
2. **The derivations of §3, as pure functions**, with the existing modules
   reading them instead of their own state. `sim/sentiment.py` keeps its
   erosion curve; what changes is that it stops being the only place a
   history lives.
3. **`_derive_affection` rewritten off the primitives**, which removes
   `attachment_rest` and `closeness_rest` and with them the reading of
   absence as deficit.
4. **The third viewer in `sim/ledger.py`** -- one argument value, per §1.
5. **The migration check for Tomoe** of §6, run and read before anything is
   switched.

Steps 1 and 2 are additive and can be built and tested against a copy of the
save without touching the running bot. Step 3 changes what she feels and
must not be done on the live character without the check in step 5 first.

**Where it has got to.** Steps 1 and 2 are built and running for the second
character (`sim/primitives.py`, `primitives.enabled`). Step 3 is done for a
character who has primitives and untouched for one who does not:
`_derive_affection_from_primitives` reads closeness, attachment and resentment,
and a stranger settles at 45 rather than 18. Step 4, the third viewer in the
ledger, is not built. Step 5, the migration check, is not run and nothing has
been switched over on the first character.

---

## 8. What building it found, and the three places the design was wrong

Each of these was found by running the thing rather than by arguing about it,
and each is a fault of the same kind: a mechanism that reads as correctly
quiet at zero and is in fact incapable of ever leaving zero.

**Four of the nine had no writer.** `attention_hers`, `predictability_his`,
`cost_of_loss` and `threat` were moved by the opening condition and by nothing
else, ever. §4 describes what should move each of them, and describing it is
not the same as somebody doing it. The cost is not that four numbers sit
still: `attachment` is attention times cost of loss, so it was pinned at zero
however much of her thinking he took up, and `longing`, `guilt` and having
anything worth withholding went with it. **A derivation is only as alive as
the primitive with the fewest writers underneath it**, and that is the check
worth running whenever one is added -- `tools/mechanisms_test.py` prints which
event writes each of the nine, with the opening condition not counting. All
nine have one now: a message of his moves what he occupies of her, her
read of his attention, how well she can call him and the running balance;
watching him work moves her attention and her sight of him; an evening she
did not hand over moves his sight of her, how well he can call her and how
much of her he can show anyone; and what he has become load-bearing for
accrues on its own.

**Exposure being a ratchet made the opening condition permanent.** §4 says
exposure does not decay and §5 says withholding "wakes on its own the moment
she acquires one private thing back". Both cannot be true: a character who
starts at total exposure of her stays there, so the moment never comes. What
cannot be unseen is what he saw; what changes is how much of her that is,
because she keeps happening. `kept_private` dilutes his share without erasing
anything he holds, and the diary feeds it. Withholding and the act wake from
that same one thing -- they are one quantity (something of her he has not got)
under two names, and neither needed a mechanism of its own.

**A mechanism the character sheet calls a sorting must not be computed as a
score.** Her fifth driver puts people inside or outside with nothing between,
and the only rough language in 47 hours of tape goes at the people inside. A
formula evaluated per message is not that, and it showed: her inside register
was withheld in one generation and used in the next, from the same prompt.
`admitted` is a latch -- tested until it crosses, then stored -- and
`can_rupture` reads the latch rather than restating its arithmetic, which says
the psychology instead of the sums: what breaks is being let in.

### The gates, and what reads them

A derivation nothing reads is a description handed to a model, which is where
this stopped being a pattern the first time. What each one now changes:

| reading | what it gates |
|---|---|
| `can_ick` | `sim/ick.py:assess` makes no call at all: nothing is out of character until there is a character |
| `can_withhold` | `sim/withholding.py:pressure` returns 0 whatever the gauges say |
| `can_rupture` | `sim/rupture.py:check` cannot open one |
| `admitted` | the register: the deferential one is hers for anyone she has not let in, above the mood chain |
| `unrehearsed` | the register, and anxiety and stress when he writes |
| `act_room` / `can_perform` | the act, and what the persona is told it has no room for -- a prompt line and nothing else: neither figure reaches a code-side reader |
| `craving` | the impulse: wanting to be seen is a disposition, wanting to be seen by him is a gap, and only the second reaches for the phone |
| `closeness`, `attachment`, `resentment` | `_derive_affection_from_primitives`, closeness through his meter (below) |
| `longing`, `guilt` | nothing. Neither is read anywhere, including the situation block: `Sentiments.longing` owns the gauge of that name and the state model owns the guilt gauge, so these two derivations are computed and discarded |

**Closeness goes through his meter rather than round it.** `relationships`
already carried a `closeness` for him, worked out from the message record by
`sim/derive.py` and nudged up by the state model's whole daily budget, and
`_derive_affection_from_primitives` called the derivation directly -- so the
meter of the same name was a second number for the same thing that nothing
acted on. `/sweep` said DEAD for the character on the primitives and alive for
the one without, and that was the whole difference. Now
`State._mirror_primitives_closeness` sets the meter to the derivation on every
pass, the record's figure is not consulted for it, the model's delta on it is
refused where a derived gauge's is, and affection reads the meter. One answer
to how close they are, and the attachment stance's selection, the reports and
the prompt lines all read it.


### 9. What the layer reads on the live save, and what is still wrong with it

Measured on an SQLite backup of the second character's save at three days of
life, with every model call refused
(`data/retired/20260903_230117_closeness/probe.py`). Her nine, and the state
they were in:

| | seed | at three days |
|---|---|---|
| attention hers / his | - / 90 | 100 / 100 |
| predictability hers / his | - / 95 | 100 / 85 |
| exposure hers / his | - / 75 | 90 / 59 |
| reciprocity | -70 | **+84** |
| cost of loss | - | 1.8 |
| threat | 75 | 63 |

Three faults in that column, and each is a scaling error rather than a missing
mechanism. **All three are corrected in §10**, which is what runs; the reading
below is what the live save showed and why each correction was made.

**The ledger credits an answer as a gift.** Her seed of -70 -- he took all of
it and she gave none of it willingly -- reached +84 in three days, which is a
154-point swing on the quantity §4 calls the slow one, and it happened while he
wrote to her and she answered. `note_from_him` debits `message_reciprocity`
scaled by what his message cost him; `she_answered` credits the same rate
scaled by the length of her reply. He writes one line and she answers in three
to six bubbles, so his effort sits near 0.3 and hers saturates at 1.0, and an
ordinary exchange nets about +2.6 in her favour every time. `resentment` is
`max(0, reciprocity)`, so she resents him eighty-four points for having
answered her, and `_derive_affection_from_primitives` takes 0.55 of that off
her -- a 46-point structural penalty that no event earned, currently masked
because the appraisal term blends most of it away. The distinction the ledger
is for is between an exchange and a stretch where one side reaches and gets
nothing: settling a debt cannot put her in credit. The correction is applied: settling a debt
cannot put her in credit, and `Primitives._level_once` moves a stored ledger
that is already in credit back to exactly zero the first time it is
constructed, marking the save (kv `primitives_levelled`) so a restart cannot
repeat it. Hers stood at +89.6 and was levelled at the first boot after the
correction landed. history: the final-pass entry.

**How well she can call him only ever rises.** §4 says predictability of him
"rises with every exchange whose outcome she would have called correctly, falls
hard on one she would not", and that "prediction error is the same event that
feeds the ick, so they cannot drift apart". Only the rising half is built:
`note_from_him` adds `answered_predictability` and nothing anywhere subtracts.
It reached the ceiling in three days and stayed, which made `unrehearsed`
zero -- being frightened of him arithmetically impossible -- and left
`admitted` latched past testing. Prediction error now writes back (§10.2):
`Primitives.error_of_him` subtracts, hard above `shock_from` and not at all
above `sure_from`, so the ick and the meter cannot drift apart.

**Nothing called the two unlatching methods.** `expel` and `close_the_act`
existed with no caller anywhere, so admission and the act's room were one-way:
once inside, always inside. Both have callers now (§10.3).

Beside all three, `sim/sentiment.py` held a second history of him: its
`attachment` toward him read 67 on her save, seeded once from a closeness
meter no event had earned, while `primitives.attachment` read 1.8 because cost
of loss is the slow integral it is meant to be. `Sentiments._attachment` now
returns the primitives' figure for the person the primitives own, and seeds
that person's row at zero rather than off the meter; everybody else is still
this layer's, because nothing else holds a number for them. The four readers
-- the impulse bonus, the delay, the susceptibility to his mood and the
`longing` gauge -- therefore all read one history.

## 10. The rescaling, and what the nine became eight

From `docs/yukarin-meters-plan.md` §3, on his answers to its questions. The structure was right and three of the scalings ran somewhere the
spec forbids.

### 10.1 The ledger's unit is unanswered reach, not volume

`note_from_him` debited by what his message cost him and `she_answered`
credited by the length of her reply, at the same rate. He writes one line and
she answers in four bubbles, so his effort sat near 0.3 and hers saturated at
1.0: an ordinary exchange netted about +2.6 in her favour, every time, and a
seed of -70 walked to +84 in three days. `resentment` is `max(0, reciprocity)`
and affection takes 0.55 of it, so she resented him eighty-four points for
having answered her.

Settling a debt cannot put her in credit: `note_from_him` records what it
debited and `she_answered` credits at most that, then clears it. What is left
is the thing the ledger was always for, and it now has its own writers:

| entry | sign | where |
|---|---|---|
| a message of his still unanswered after `owed_hours` | debit, once per message | `unanswered()`, on the primitives' clock |
| a message of hers still unanswered after `owed_hours` | credit, once per message | the same |
| an answered exchange | 0 -- the debit clears, no credit | `she_answered` |
| she saw a thing and did not raise it, and a discretion stance held over it for the whole hot window | credit | `held_back()`, paid by `Stances.settle_discretion` |
| he told her a thing she could have read anyway | debit, by how much of it she already had | `told_her_anyway()`, from `App.assess_learned` |
| she did something for him | credit | `gave()`, as before |

The last two are the premise's two currencies. She cannot lower what he holds
of her by concealing anything, so her one gift is seeing something and leaving
it alone; his answer costs him nothing informationally, because she can see the
screen, and everything socially, because he is handing over what she would
otherwise have had to take.

### 10.2 Fear can come back

How well she can call him only ever rose -- an answered question added 2.5 and
nothing anywhere subtracted -- so it reached its ceiling in three days and
`unrehearsed`, the threat times how little she can call him, became
arithmetically impossible for the rest of her life. `error_of_him(charge,
about_her)` is the fall, written at `App.assess_learned`, the one funnel every
discovery about him passes through, from the charge the ick has already priced.
Above `sure_from` a small charge does nothing at all; certainty has no partial
position to retreat to, so a charge over `shock_from` takes it down in one step
instead. A discovery over `shock_from` that is about HER also writes
`demonstrated_threat` with a FLOOR under it -- `decay` will not go below a floor,
because a demonstrated use of what somebody has of you is not a thing time
undoes -- and calls `expel`.

### 10.3 The two latches have callers

`expel`: a discovery over `shock_from` that is about her (above), and a rupture
that settled worse at or above `rupture.expel_severity`, read from the row
`Ruptures.settle` returns (`App.rupture_settled`). `close_the_act`: a single
disclosure over `close_act_weight`, which is what "something large goes across
at once" means.

### 10.4 `disclosed` had never written once

Its only caller was the nightly compile's self-claims and her whole record held
two of them, so his share of her only ever fell -- about four points a day off
`kept_private` -- and closeness, the smaller of the two exposures, tracked a
number that could not go up. The compile is the wrong grain: the event is her
message. `App.note_disclosure` runs where her words actually go out, and how
much of a message is a disclosure is how many of its words her own record does
not already hold (`disclose_min_words`, `disclose_looks_back`,
`disclose_min_share`). It is a count of words and needs no model and no
language.

### 10.5 Three deletions

- **`predictability_his`**, her belief about how well he can call her: two
  writers, no reader anywhere, and what it means is already
  `100 - exposure_his`, which is `act_room`. Two names for one number is the
  fault `can_rupture` was fixed by removing. The nine are eight.
- **The `longing` and `guilt` derivations.** Computed and read by nothing but a
  report and two tests; `Sentiments.longing` owns that gauge and the state model
  owns the guilt gauge.
- **`sim/sentiment.py`'s attachment toward him.** It read 66.6 against
  `primitives.attachment` of 1.8, seeded once from a closeness meter no event
  earned, and `longing`, `susceptibility` and `impulse_bonus` all acted on it.
  Those three read `Sentiments._attachment()`, which is the primitives' figure
  for the person the primitives own and this layer's own row for everybody else;
  the seed writes 0.0 for him.

### 10.6 Habituation with an end

Per kind of thing, `novelty = max(novelty_floor, 1/(1+seen)^novelty_power)`
scaled the charge, and at the flat floor of 0.15 a kind she had met fifty times
still charged eight points -- eight points of awkwardness a day that nothing
earned. Past `ick.settled_after` sightings the multiplier is zero and the kind
stops being assessed: it is not a discovery any more, it is a fact about him.

Three things never habituate, each a rule rather than a number: anything at the
top of `about_her` (the tenth must cost what the first did); a thing he told her
himself that does not fit, because prediction error against his own account of
himself is not the same event as prediction error against something she
inferred by watching; and evidence he will use what he holds, which has no
discount, no decay and is the caller of `expel`.

And habituation is a state as well as a discount: `Ick.settled()` is the share
of what she has met lately whose sort she had already run into. At 1.0 nothing
he does is news; at 0.0 every look is new. It is the threshold the calm stance
reads.
