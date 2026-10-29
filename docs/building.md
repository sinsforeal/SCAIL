# BUILDING

<!-- doc: reference -->

How to add a mechanism to this simulation so that it works, can be seen to
work, and does not weld itself to one character. `PROJECT.md` says what exists;
this says what a new thing has to satisfy before it counts as built.

Every rule below was written after something broke. The failure is named in
each one, because a rule without its failure gets argued away.

---

## 1. Code decides *when*, a model decides *what*

Gates, caps, schedules, thresholds and arithmetic are code. Judgement is a
model call. A mechanism that asks a model "should this happen now" has no
gate; a mechanism that decides in code what a person feels has no judgement.

Model calls are not the scarce resource. Fidelity is.

## 2. Nothing may be declared that is not read

`social_standing` was a number on the cast sheet that nothing ever read. It was
deleted, and then the same fault was rebuilt six times in one week: six gauges
that wrote a mood tag and changed nothing, `influence` reaching only the beat
writer, `want`/`dread` that nothing consumed.

Before merging, name the reader. If the only reader is a report, it is not
built. `tools/smoke.py` prints the wiring table for exactly this: a gauge whose
writer or reader column is empty is an accusation.

## 3. A value must be able to move both ways

`affection` ran 45 to 100 across 72 states and never once went below its
baseline, because every mechanical write was `_warm` and decay only returns a
gauge to rest. `mood` ran 50 to 84 against a baseline of 55, so she could not
have a bad day and `mood < 30` was dead code. The health loop applied targets
downward only, which made a "floor" that could only lower the thing it floored.

So: for anything that can rise, name the thing that lowers it, and check the
observed range rather than the intent. `State._nudge` exists because `_warm`
and `_settle` between them could not push a gauge below rest, and contagion's
entire downward half did nothing, silently, for a day.

## 4. Measure pressure against rest, not against zero

A gauge sits at its baseline. Anything computed as "how far above zero" is
almost always at its baseline, so the term is constant and the mechanism never
fires. The snoop shipped with this bug; the spiral shipped with it again three
months later, in a new module, by a different route.

## 5. Time must not be the only healer

A rupture that decays is not a rupture. A charged item that only fades is not a
secret. If a thing is supposed to cost something, something must have to be
*done* to clear it, and the doing must be able to fail.

`rupture.holds_gauges` is skipped by `State.decay` while one is open, and that
is the whole of "time does not repair".

## 6. Character-specific behaviour is derived, never coded

This system is meant to run a different girl. So: no function may branch on who
she is, no threshold may encode a trait, and nothing girl-specific belongs in
`config.py`.

Where a trait is needed, derive it from her data. `goals.give_up_at` does not
know whether she is stubborn; it scales with what the belief in question has
riding on it, from `characters/tomoe/self_beliefs.json`. A want holding up 88 points of
self survives five failures and one holding nothing survives two, and a
different girl's file gives a different answer with no code change.

The test: could this mechanism produce the opposite behaviour for a character
whose sheet says the opposite? If not, it is a trait in code.

## 7. The character lives in one sheet, and the prompts are generated from it

`data/characters/<id>.json` is the single sheet: name, age, origin, dialect and
when it slips, the people, the place, the register, gauge baselines, and what
this person is wound up and settled by.

The mechanism in `sim/` branches on nobody -- the only coupling is that 42 of
46 prompts name her -- and that coupling is thin: two to eleven proper nouns in
files of two to ten thousand bytes.

`tools/forge.py` re-points those spans from one sheet to another and then
proves it broke nothing:

    python tools/forge.py check                      # live prompts vs their sheet
    python tools/forge.py generate --sheet data/characters/x.json --out prompts_x
    python tools/forge.py review  --sheet data/characters/x.json --dir prompts_x
    python tools/forge.py apply   --dir prompts_x    # only when review passes

**The rubric.** Each item is a fact about the file, not an opinion, and any one
of them refuses the result:

| check | why |
|---|---|
| `schema` | every `Output ONLY this JSON` block byte-identical. A prompt that loses its schema is not a worse prompt, it is a subsystem returning nothing |
| `tokens` | every `{{PLACEHOLDER}}` survives, same count. `{{TELLS}}` and `{{DELTAS}}` are generated from the gauge spec and cannot drift |
| `mechanism` | every quoted JSON key in the original still present |
| `residue` | no proper noun from the old sheet remains |
| `invention` | no name that is not on the new sheet |
| `register` | the shared voice block, if present, unchanged |
| `size` | within 30% |

A model may only *warn* about whether it reads as her. The rubric is what can
refuse.

## 8. Her voice is described, never exampled

A list of banned phrases teaches a model to avoid those phrases and invent
others. Describe the register instead: hers is casual JK Japanese rendered into
English, and the mapping is written out in `prompts/style.md` -- short clauses
chained with から/し/けど, trailing off on けど, hedging with かな and なんか,
one flat intensity word doing the work.

Three shapes are barred as rules, not examples: an image she made up, a feeling
given a place or a size, and naming a situation as a thing.

## 9. Do not let her own text teach her

The diary pasted its last two entries into the prompt that wrote the next one,
and all four on file carried the fault being corrected -- so every entry
studied two bad ones and no wording could have recovered it. It reached her
messages: she said the same invented image to him twice.

Where her own text is shown back, show less of it (a gist, not the prose) and
label it as the record of what happened rather than a model for how to write.
`tools/devoice.py` rewrites what is already spoiled, her side only, addressed
by `rowid`, refusing any rewrite that drops below half the original length --
because that is a summary, and it would quietly delete something that happened
to her.

## 10. Two stores, split by whose they are

Objective facts about the world go in their own file and are shared: his anime
(`data/mal_history.db`), the tags on an image (`data/x_images.db`). What she
made of them lives in `data/world.db`, because that is memory: it fades, it is
recalled on a cue, and two people looking at the same picture do not come away
carrying the same thing.

Tag in a vocabulary something else already uses, so the two can be compared.

## 11. Prove it by running it

Verify with the store's own reader before quoting a number. A per-tick
probability means nothing without the tick count; get that from `scenes`. Do
not trust `PROJECT.md` or `HANDOVER.md` as a description of what the code does
-- several entries have described behaviour the code did not have.

`python tools/smoke.py` before every restart. It builds the whole App against a
copy of the save, calls every report, prints the wiring table and the affect
grid, names dead config keys, and runs a static pass for two faults that hide
from everything else:

- a name used in a function and never bound there (`spiral_txt` was in the
  director's prompt without its assignment; every tick raised NameError and
  nothing showed it, because a sleeping girl gets no director ticks)
- a line ending in `+` followed by a line starting with `+`, which is a unary
  plus on a string (an inserted line in a concatenation chain)

Neither is caught by import, by `ast.parse`, or by constructing the App.

## 12. Patching rules that have cost a day each

- **Anchor on a whole line with its indentation.** `"diary": {` also matches
  the model-role line inside `models`.
- **`grep -c` after any patch script.** A script that writes per edit but is
  not idempotent, re-run after a partial failure, silently triples its inserts.
- **Never a bash heredoc for anything with escapes.** It mangles them. Write a
  python file and `ast.parse` before writing.
- **Changing a default's value or removing a key must be done in BOTH**
  `config.py` and `config.json`. A stale `config.json` value silently overrides
  the new default.
- **Fix the code before cleaning the data.** Cleaning first lets the running
  process rewrite exactly what was cleaned.
- **Stub the whole logger** in a throwaway script, not just `logger.log`, or it
  creates a real run directory with an ACTIVE pid file.

## 14. A record of an action must never exist without the action

Four times, in four modules, the same shape: the fiction said she did something
and the machinery had not done it. The X post was recorded before
`curation.decide` returned, so she had a memory of a post nobody ever saw.
`approach.note()` charged before the bubbles existed. `hazards_seen` was marked
before delivery, leaving 2 seen and 0 delivered. And the director wrote *"She
finally sends him the message she's been drafting since the bath"* with no
`messages` row and no `tg_id` behind it.

Two halves, and both are needed.

**Ordering.** Nothing is written down until the thing that decides whether it
happens has returned. Not the count, not the gauge release, not the event. If a
call can refuse, it is the authority, and every record waits for it.

**Assertion.** Prose can claim anything, so free text needs a check rather than
an ordering. Every action she can take gets a typed channel that code honours, a
deterministic reader for whether it really happened, and a pass that corrects
prose claiming otherwise -- `sim/reconcile.py`. Where a correction is itself
generated, it is checked by the same detector once and **dropped** if it still
lies: losing a sentence is always better than keeping a false one.

The tell that this is happening again: a doc entry that says "that is the X
post's fault again". Writing the recurrence down is not acting on it. The
second instance is the one that should produce the mechanism.

## 13. Times are the machine's clock

Every stamp in `PROJECT.md`, `HANDOVER.md`, a log reference or a chat reply is
the clock on his machine, read from `date`, never hers and never estimated. Her
clock appears only where it is the subject, labelled, usually with his beside
it. `HANDOVER.md` once carried entries stamped hours ahead of when the work
happened, which made the file read backwards.
