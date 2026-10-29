# The pattern spec: how a character is described, measured and filled

Proposed spec of record for character patterns, for any character in this
project -- Tomoe, Yukarin, a cast member, anyone extracted or authored later.
**Not yet approved and nothing implements it**: no PROJECT entry, no HISTORY
section number, and the pipeline still writes the old shape. It is the design
asked for, put where a spec goes so it can be read against the code.

**The Method is `docs/yukarin-pattern.md`**: the schema sections, the collection
order under scarcity, the signal ranking and the gap-filling ladder, stated
portably for any material. It was **written by a different AI** when SCAIL was
described to it, and adopted as a starting point -- a design proposal, not a
standard handed down. It is not edited from here, and where it and this
document disagree the disagreement is worth resolving rather than assuming
either side; where the data argues against either, the data wins.

This document is the *binding*: what each section feeds in SCAIL, what a
record has to carry, what the bar is, and how coverage is measured rather than
asserted.

## 1. Why a binding is needed

The extraction pipeline (`docs/yukarin.md`) implements the Method's section
labels and nothing else about it. Measured against `docs/yukarin-pattern.md` as it
stands:

- **Section I does not exist in the pipeline.** The map asks for A-H only.
  The sheet's whole `uncertainty` block is one sentence: *"moment kind 'anger'
  seen only 2x in 99 episodes."* The Method's section I wants states never
  observed, relationship types with zero data, situations that would
  stress-test the model, and an explicit list of inferences against
  extractions. None of it is produced.
- **The record cannot express a gap-fill.** The Method's field set ends with
  `Inferred? (yes/no + rationale)`. The sheet's equivalent is `provenance`,
  whose value is the constant string `"extracted"` on all 77 mechanisms. There
  is no field in which a cautious inference could be written, so the ladder in
  the Method's §4 is unusable: everything is either extracted or absent.
- **Coverage cannot be measured.** Every one of the 1,842 observations carries
  its `section`, and the reduce drops the field -- it is in neither
  `yukarin/sheet/clusters_v2.json` nor the sheet. The one instrument that could say whether
  the pattern is full was collected and thrown away.
- **Step 0 is half done.** `yukarin/corpus/manifest.json` counts episodes, cues, hours
  and years. The Method's Step 0 also asks how much of the material is
  reactive against initiated, how many distinct emotional pressures appear,
  and how many relationship types are present -- the three measures that
  bound what can honestly be claimed.

## 2. The sections, and what each one feeds

A section is not a filing label. It exists because something downstream reads
it, and a section with no data must make that consumer refuse rather than
invent.

| | section | what reads it |
|---|---|---|
| A | resting state & baseline presence | `sim/schedule.py` and the director's tick (what she does when nothing is required), the gauge **baselines** in `data/characters/<id>.json`, the no-event path of `sim/impulse.py` |
| B | affect & drive | `sim/state.py` -- the gauges, their decay and habituation; `discharge`, `stress` |
| C | relational stance | `attachment`, `rupture`, `withholding`, `care`, `expectations`, the model of him, `sentiments`, the cast exchanges |
| D | initiation & agency | `sim/impulse.py` (**does she text first** -- a pure function), `approach`, `goals`, `commitments` |
| E | expression mechanics | `persona/` -- bubbles, shape budget, the continuity editor; `prompts/style.md`; the register block |
| F | belief & predictive model | `characters/tomoe/self_beliefs.json`, `appraisal`, `ick`, social comparison |
| G | memory & continuity | the timeline compile, `sim/memory.py`'s forgetting curve, facts about him |
| H | group & social ecology | `tomoe/cast.py`, the social graph, `sim/ledger.py` (who is present, who is absent) |
| I | uncertainty & boundary conditions | **the prompt builder**, as an explicit no-data instruction -- §5 |
| J | body and self-image | `embodied/body.py` and `embodied/health.py`, the fatigue / hunger / physical_comfort / unwell gauges, and the situation line that says what she is doing with herself |
| K | taste, and what rewards her | `goals`, `care`, `discharge`, the attention budgets, and everything that decides what she does with an hour nobody has claimed |

**J and K are additions to the Method, and they were found by reading somebody
else's schema.** `docs/yukarin-pattern.md` has nine sections and neither of these;
the brief in `yukarin/sys_prompt - yukari.txt` asks for both, and the answers
turned out to be the two blocks the character sheet most obviously lacked. A
simulation with a fatigue gauge and no statement of how tiredness shows in
this particular person will invent one. A simulation that has to decide what
she does with a free hour needs to know what she actually enjoys, and
"performing" is not the answer -- for this character it is close to the
opposite of the answer.

## 3. The record

Every mechanism, in the sheet or in a character file, carries:

    name          kebab-case and functional
    section       A-I
    trigger       under what condition
    suppressor    what ends it; "" if never observed (not guessed)
    function      what it accomplishes for her, what cost it avoids
    variation     the surface forms it actually took
    frequency     episodes, observations, and per-era share -- code's, never a model's
    evidence      verbatim quotes at their cue, and the count
    confidence    1-3
    sources       the episodes or scenes
    inferred      0-5 on the ladder in §4, and a rationale whenever it is not 0
    load_bearing  true, or `format` when it exists because the material needed
                  a transition or a joke rather than because she is like that

`inferred` and `load_bearing` are the two new required fields. `provenance:
"extracted"` is replaced by `inferred: 0`, which means the same thing and
leaves room for the rest of the ladder.

`load_bearing` is the Method's Step 4. It has already been applied once by
hand: `yukarin/sheet/judgement.json` sorts all 77 mechanisms into `her`,
`format` (16 -- the frame formulas, the mail ritual, the sponsor read, the
prize logistics) and `moment` (16 -- the one-to-three-episode entries the
sheet itself labels as one-offs). That verdict becomes this field.

## 4. The gap-filling ladder

Straight from the Method's §4, as a stored integer so that nothing downstream
can lose track of which level a claim came from:

| level | what it is |
|---|---|
| 0 | extracted from the material, with receipts |
| 1 | **left explicitly unspecified** -- the default, and the reason section I is executable |
| 2 | cautious adjacent inference from a tightly related observed pattern; confidence low |
| 3 | functional completion -- what must be true for the observed high-frequency patterns to be stable; confidence medium |
| 4 | contrastive inference from the ensemble -- what others do in the same situation that she never does |
| 5 | provisional rare-state placeholder, conservative, muted rather than theatrical, easily overridden by later data |
| -- | **genre average is not a level.** Importing "typical quiet girl" or the fandom's compression of her is the failure mode this whole scheme exists to prevent |

The rule that makes it enforceable: **a level above 0 may not contradict a
level 0 record, and a character file may not carry a level above 0 without a
rationale naming the level-0 records it was built from.** A check can hold
that; opinion cannot.

The reason the level has to be stored is better shown by a case that is not a
genre average at all. `self-image-defense`'s function in the sheet describes
her preferred self-image as "elegant, cute, truthful, capable, **eternally
17**". 「永遠の17歳」 occurs zero times in these 99 episodes. It is nonetheless
**true of her** -- the age joke is continuous and hardens as she gets older,
and she never stops playing the idol persona -- so this is not an invention to
be deleted. It is a **forward projection past the window**, correct in
substance, written into a field that means "extracted from this material".

The era's actual surface is ep053: seventeen plus a number of months, the
audience told 「計算しといて」, the answer 「120ヶ月くらい?」 given and then denied.
The brand form belongs to the later years the corpus does not cover.

With no `inferred` field there was nowhere to say that, so a level-2 claim
went in at level 0 and the sheet now asserts a phrase its own evidence does
not contain. This is the ordinary case, not the pathological one: most of what
a parasocial corpus cannot show still has to be filled in from somewhere, and
the only thing that keeps it honest is that the level and the source are on
the record.

## 5. Section I is generated, and it is executable

The Method calls uncertainty a first-class section. In this project it is also
a runtime instruction, because "leave explicitly unspecified" only works if
something at the other end is told.

Section I is **computed, not written** -- from what the extraction did *not*
find, which is knowable:

- **states never observed**: the moment kinds and fingerprint counters at or
  near zero
- **relationship types with zero data**: from the section-C breakdown
- **initiation forms that never occur**: from section D against the reactive
  share
- **negative space** (the Method's Step 2): emotions that never appear, topics
  never raised, ways of claiming status or care that are absent, and --
  contrastively -- what the other voices in the material do that she never
  does. The `other`-labelled spans make that last one computable rather than
  recalled.

The prompt builder then emits the result as a bounded no-data block, in the
same place a persona section goes, saying what there is no evidence for. A
model told nothing about her anger will write anger from the genre average;
a model told *there are two anger moments in 47 hours and no expression path
for it* will not.

## 6. Step 0 bounds the claim

`yukarin/corpus/manifest.json` is extended with the Method's three missing measures.
For the Yukarin corpus they are already computed and they are the whole
argument about what this material can and cannot support:

- **reactive against initiated**: **87.9% of her words begin as a response**
  to a letter, a read insert or another voice. Only 2.3% of her 3,983 speaking
  spans open cold.
- **relationship types present**: broadcast one-to-many (190 observations),
  workplace (131), guest (3), absent/fictional/object (44). **Private
  reciprocal dyad: 0. Family present: 0. Peer friendship: 0. Romantic: 0.**
- **distinct emotional pressures**: six kinds, one of which (anger) appears
  twice in 47.2 hours.

The inventory states the maximum completeness any extraction can honestly
claim, and this one says: a strongly evidenced *responsive* character, and
almost no evidence for an *initiating* one or for any private relationship.

## 7. The bar

A pattern is **usable** when, per section, either the evidence bar is met or
section I names the gap and the level it was filled at. There is no threshold
that makes a section "done" -- the honest states are *evidenced*, *inferred at
level N*, and *unspecified*, and every section must be in one of them.

Two quantities are worth holding to, both from the Method's §5:

- **6-12 solid high-confidence mechanisms** is the expected yield under
  limited material. 77 was never the right number;
  `characters/yukari/sheet.json` carries six core and three rare, which is the
  band.
- Rare-state and initiating mechanisms are expected to be **few and
  low-confidence**. A pattern claiming many of either, from material like
  this, is overfitted.

## 8. Where a pattern lives

The Method's object and this project's runtime object are the same file:
`data/characters/<id>.json`, which `tools/forge.py` generates 78 prompts from
and `tools/character_test.py` runs against the machinery. A pattern is not a
document beside the character sheet; it is the character sheet, with the
fields of §3 on its mechanisms and the computed section I attached.

`docs/yukarin.md` is how one character's pattern was extracted;
`docs/yukarin-spine.md` is how that extraction became a sheet; this is the
shape both of them have to satisfy.
