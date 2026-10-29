# Making a character from material: the one guide

<!-- doc: reference -->

**This is the only document about making a character from material, and it
supersedes every other one.** Everything the project knows, in one place: what
the unit of description is, the two routes to a character, what can be measured
about one and what cannot, the machinery rules that were paid for in money or
in a night's work, the procedure from material in hand to a character running,
what changes for each kind of source, which tool runs which stage, the form of
every file the procedure has to produce, and what is still open.

**What it is for.** The goal is not a transcript wearing a name. It is a card
whose output matches **the person behind the voice** in situations the material
never contained -- which means finding the gaps in what the material can show
and closing them by inference that is named, converged, contradicted where the
record contradicts it, and scored on material it was not built from. §1.2 is
that premise and §1.4 is the shape the rest of the document takes from it.

**How to read it.** §1 to §5 are the reasoning: the premise, the unit, the two
routes, what a number can mean, and the operating rules. §6 to §11 are the work:
the procedure, the source kinds, what a given amount of material buys, the
tools, the file forms, and the seam to a running character. **An agent running a
fresh subject follows `docs/extraction-runbook.md`**, which is one page of steps
pointing back into here for the reasoning behind each.

It replaced nine documents in September 2026 and then absorbed their pointer
stubs. Section 13 maps every section of those nine to the section here that
carries it, and their full text is kept under
`data/retired/20260906_guide/originals/`.

**Two documents stay separate and are cited rather than absorbed, and here is
why in one sentence each.** `docs/scail-concept.md` is the origin -- the
six-step method the project began from, with its worked example -- and a
document whose whole value is saying where an idea came from stops being that
the moment it is edited to agree with what the idea became.
`docs/verification.md` is the specification of an instrument that runs
(`tools/voice_verify.py`), together with the seven ways its output will mislead
a reader, which makes it a tool spec rather than method.

Five specs also stay separate because they describe files and code as they are
today rather than method: `docs/codebook.md` (the codebook file, its generated
twins and its check, including the artefacts the type compile builds),
`docs/cast-mechanisms.md` (the authored mechanisms format and its renderer),
`docs/bundle.md` (what a character IS as files), `docs/shared-world.md` and
`docs/peer-talk.md` (two processes over one present). Turning somebody on a
roster into a character who runs is §11 here and `docs/promotion.md` for what
the generator writes from her row.

---

## 1. What this is, and what it is not

### 1.1 The idea

A character is a generative function and her behaviour is that function's
output. The job is to recover the rules that produced the behaviour, not the
behaviour itself. A rule is a conditional: **when this condition holds, this
class of behaviour, varying this much, unless this other condition holds.**
Rules are chosen for predictive power rather than for memorability, which is
what separates this from summarising a character: a summary selects what is
striking, and a rule has to be right about a situation nobody has seen yet.

Everything below is that one sentence made operational, and every departure
from it was forced by a number one of the runs produced.

### 1.2 The premise: a card that matches the person, not the recording

The goal is a card whose output matches the person **in situations the material
never contained**. That phrase does most of the work.

**The material is a performance.** A broadcast, a stream, a published
interview: every corpus this project is likely to get is a person doing
something in front of somebody, in a room whose shape decides much of what they
say. The shape is not theirs. It leaves cues everywhere -- in the counts, in
the turn lengths, in what is allowed to open a topic -- and a person's private
conduct leaves none, because nobody recorded it. **So the format is the loud
signal and the person is the quiet one, and a card written by counting what is
loudest is a card of the programme wearing the subject's name.** §3.2 has this
happening, with the receipt.

It follows that the gaps are the deliverable rather than a defect. The material
shows what she does when observed; the card has to say what she does when not.
**That crossing is inference, and inference is what the method is for rather
than what it apologises for.** The alternative to writing the gaps down is not
"no speculation": it is speculation improvised at generation time, differently
on every call, invisibly, by a model with no receipts.

**Inference is tiered and validated, not rationed.** Tiered: every inferred and
speculated row names the frame that produced it and the evidenced rows
underneath it (§2.5). Validated: a claim earns confidence by converging across
independent readings under named frames and by predicting held-out material it
was not fitted on, and it is dropped when an evidenced entry contradicts it,
however often it was reached (§3.2).

**Where the ceiling still is.** No procedure here can show that a claim about
somebody's interior is true. What it can show is that a claim was reached
independently more than once, that it predicts material it was not built from,
and that nothing in the record contradicts it. In the owner's words, given a
rich enough set of facts the inferences "will over time statistically converge
onto a select set of traits" -- which is what licenses saying the person behind
the veil has been mapped. That is a claim about convergence and prediction and
not about having seen inside anybody, and `docs/verification.md` still lists
every way a voice check will mislead the reader of one.

### 1.3 The frame the work is done under

Three decisions of the owner's shape everything.

**The vocabulary is engineered first and the record says which parts of it
have been seen filled.** The codebook is meant to be the whole map of
text-visible behaviour rather than the part a particular corpus happens to
reach, so it holds entries with no instance behind them as well as entries
with instances. A family with five entries and one instance states a bound
about the material; a family that was left out because nothing reached it
would state nothing at all, and nobody could see the hole.

**The next subject will bring less data.** In his words: on character
extractions he does not expect data as rich in future; whatever framework
uses the codebook has to be compared against the results of the non-codebook
method to show minimal loss; the point of coded mechanisms is that any
character in future can be extracted procedurally even from limited data; the
hand-annotated fictional subject is not a level of data quality to expect, and
a future run may have only subtitles; deriving data from picture or video
should be considered, with cost and time the constraint, because otherwise it
is a person doing it manually.

Three things follow and they are rules, not preferences. Every code is
defined in terms of what a subtitle file can show -- words, their order, the
cue index, the attribution label -- and no code may rest on a laugh, a pause,
a gesture or a face, because the next subject may have none of those. A
channel that does exist for a subject may add evidence to a code and may add
its own codes in a separate, marked section, and a card built with those
channels says so. And the procedure owes two figures: a **loss ledger** (the
share of what a reader with no codebook found that the codebook can express)
and a **data-hunger curve** (which parts of a card are measured, thin or
absent at three, six, twelve, twenty-four and all episodes). Section 4.7 is
both.

**The procedure is for any future character, not for one subject.** That is
why the codebook is one shared vocabulary rather than one per subject, why
the entry carries no character's name in any field, and why the same entry
has to be usable on a tape, on a chat log and on a sheet somebody wrote.

### 1.4 The shape of the method: invariants, then variants

**The extraction method for a new kind of source is not written from scratch
and it is not copied from the last run either.** It is the invariants below,
which hold whatever the material is, plus the one column of §7's table that
says what changes. That is deliberate: the next subject's material will not be
the last subject's, and a procedure written tightly around one corpus is a
procedure that has to be argued with rather than followed.

**The nine invariants. Every one of these holds for every source, and a run
that drops one has stopped following the method.**

1. **An occurrence is recorded with its attribution.** Every claim resolves to
   a place in the material -- a cue index, a line, a shot -- and to who
   produced the words there. A claim evidenced from somebody else's speech in
   her mouth is a citation error and is dropped (§5.7).
2. **The unit of description is a closed vocabulary, not a name a reader
   invented.** Extraction is classification against a frozen book. Free
   discovery is a stage whose product is the book, never the numbers (§2).
3. **Every rule carries the class of what it describes**: hers, the format's
   (or, in a scripted source, the author's needs), or a single moment. **A
   format-class rule may never govern private behaviour** (§3.2's worked
   example is what happens when it does).
4. **The person is what is invariant across contexts and the persona is what
   varies with the room.** So a rate is computed per context and only an entry
   whose rate holds across them may found a claim about her off duty, however
   frequent a situated one is (§4.6).
5. **The breaks are kept.** Where the material disagrees with the pattern, the
   material wins and the disagreement stays on the sheet -- in the
   contradictions of the type, in the drift of a rate, in the entry that will
   not reach the reliability gate. A card that is internally clean reads as a
   template.
6. **Inference is named, not rationed.** Every inferred and speculated row
   carries the frame that produced it and the evidenced rows it rests on, and
   there is no cap on how many there may be. **The count that must be zero is
   rows with no frame** (§2.5).
7. **Inference is validated three ways**: convergence across independent
   readings, prediction on material it was not fitted on, and being dropped
   when an evidenced entry contradicts it, however many readings reached it
   (§3.2's convergence pass).
8. **The type comes last and is derived, never asserted.** It is the one cheap
   check that the whole pattern is coherent, and it is a source of no rule and
   appears in nothing a call reads (§3.6).
9. **What she believes about herself is applied, not filed.** The convergence
   pass's claims about her self-beliefs are written into the store the running
   character reads and revises, with a confidence set by a stated rule
   (§10.3).

**And two rules about the boundary of the material itself**, which are what
keep the invariants runnable on a thin source: **no code may rest on a laugh, a
pause, a gesture or a face**, because the next subject may have none of those;
and **a channel that does exist may add evidence to a code and may add its own
codes in a marked section, and may never define one** (§1.3).

**The variants are per source kind**, and there are four written down: untagged
broadcast subtitles, speaker-tagged subtitles or scripts, a fictional canon with
scenes, and a mixed corpus. §7 has them stage by stage. **A fifth kind is
written by taking the invariants above and answering, for each stage of §6, what
this material makes free, what it makes impossible, and what it makes cheaper
than the last run** -- and the answer to "impossible" is a line in the bounds
block, never a substitution.

---

## 2. The unit: one entry of the codebook

The single change that made everything else possible: **extraction stops
being generation and becomes classification.** A reader is no longer asked
what an episode shows; it is asked, for each defined entry, whether that
behaviour occurs here and where.

The problem that forced it is on disk. Free extraction invents a name per
observation: 770 distinct names for 775 observations on the third subject,
766 of them appearing in exactly one episode; 1,790 names for 1,842
observations on the second. Two runs of the same extraction over the same
episode agree on about a quarter of the moments they cite (0.22 and 0.25 by
the overlap statistic, against 0.09 by chance) and on the *names* of what they
found they agree essentially never. The same input produced anywhere from 0 to
244 surviving mechanisms across 37 runs, a sixteen-fold range in the middle of
it, while the share of quotes that verify against the tape stayed at a median
0.982. **Fabrication is not the failure mode. Instability of the unit is.**

"The mechanisms have to agree" is three requirements and only the first is a
statistic: two readers of one episode should mark the same thing (reliability,
measurable); the same behaviour in two distant episodes must be one entry
rather than two names (design, fixed by a closed book); and the set must not
contain two entries that are one thing split or one entry that is two things
lumped (design, fixed by writing the exclusions).

### 2.1 The entry, field by field

The file is `data/codebook/v0.1.json` with a readable twin beside it, and
`docs/codebook.md` is its spec. One entry is one behaviour with one trigger.

| field | what it holds |
|---|---|
| identifier | family prefix plus a function phrase; stable, never reused, never renamed |
| family | one of the twenty, and the identifier's prefix must match it |
| layer | it happened at these cues (occurrence), or it did this for her in context (function) |
| definition | one sentence, in observable terms, text only |
| trigger | the condition under which it fires |
| suppressor | the condition under which the trigger is present and it does not fire |
| occasions | the fixed list of occasions on which it could fire, written for both a broadcast and a typed chat, so an absence is a datum rather than a silence |
| function | what it does for her, one sentence |
| variation | three surface forms that differ; if they do not differ it is a verbal tic and belongs to the marker battery instead |
| includes | the rule for what counts |
| excludes | one row per nearest neighbour: the neighbour's identifier, and the rule that separates them |
| anchors | real instances, by the inventories' own item identifiers |
| near misses | two instances that look like it and are not, with why |
| provenance | the observer-rated instrument the definition borrows from, declared off-label, or bespoke |
| what a rate would tune | the module in the mind library a rate would move, the dial by name, and whether it is a threshold or a gauge's baseline -- or "no home" |
| sources | which inventory candidates merged into it |
| status | anchored or theory-derived |
| single subject | true when every anchor comes from one person |
| version | the codebook version the entry was frozen in |

**Whether an instance is hers, the format's or a single moment is not a field
on the entry.** It is decided per subject at coding time, because an entry
carrying that decision would decide it for every character at once. It is a
field on the instance.

The three fields that buy agreement between two coders are the suppressor,
the exclusions and the near misses. A definition alone does not separate
"downgrades her own claim after making it" from "deflects somebody else's
compliment", and readers lump those two until told not to; the free readings
did exactly that.

### 2.2 Why the suppressor, the occasions and the variation

The original method was emphatic that a trigger without a suppressor gives
you a character who does the same thing constantly, and that the useful rule
is the one with an "unless". An intermediate version of this schema dropped
all three fields, and the correction restored them. Each earns its place for
its own reason.

**The suppressor decides agreement, and its status differs by route.** In
authored material it is what makes four different people's mechanisms one
entry, never the surface: four people carry one register inside an admitted
circle and another outside, triggered by who can hear; four are unreachable at
hours set by a fact they will not give; four have something that exists only
in a two-person room, with a third listener as the suppressor. On the test
case -- deciding for the group, against a worry that arrives as an instruction
-- the suppressors say two entries, because instant silent compliance
satisfies the second and leaves the first still firing. In extracted material
the field is nearly empty: two of 77 clusters and 15 of 775 observations state
one, because a suppressor is a non-occurrence and a free pass records
occurrences. **So for an extracted subject the suppressor is inference until
the coded pass records trigger-present-code-absent rows against the entry's
occasions, and that row is the only evidence a suppressor can ever have.**

**The occasions make absence a datum.** A classification instrument records
occurrence; without a fixed list of occasions on which an entry could have
fired, "not recorded" means either absent or overlooked and nothing
distinguishes them. With one, a miss becomes a measurement and recall becomes
computable at all.

**The variation range separates a mechanism from a verbal tic.** If the
surface always looks the same it is a phrase that recurs, and a card should be
told that; if the same function is reached different ways each time it is a
mechanism, and a card should be told "do something in this family" rather than
"say this line". Requiring the three anchors to differ in form catches a tic
at the point it would otherwise become an entry. The failure this guards
against is on record at three levels: a hand-written character card promoted
single moments into standing traits; a speech guide written to correct that
card illustrated a habit with a line that appears zero times in forty-seven
hours of tape, and six models reproduced the line verbatim in one afternoon;
and the guide's long demonstrations were real but smoothed, with connectives
inserted and the hesitation sounds taken out, 53 filler tokens in the tape's
wording against 5 in the file's.

### 2.3 The two statuses, and what rests on one subject

Version 0.1 holds **189 entries: 138 anchored and 51 theory-derived, with 81
resting on one subject's anchors.**

An **anchored** entry has instances from the project's own material. A
**theory-derived** entry is one the scope names and none of the 852 extracted
items, 207 authored items or 171 library mechanisms reaches. Both are held to
the same standard: a theory-derived entry with a vague definition, fewer than
three differing surface forms, or an exclusion naming no real neighbour fails
the check exactly as an anchored one does.

**A reliability run codes anchored entries only.** A theory-derived entry has
nothing to compute an agreement figure against, and coding one would
manufacture the evidence that is supposed to anchor it. It enters the coded
pass at the moment a coder finds an instance, which is the point at which the
version has to move.

**One subject only** is not a fault -- it is the honest state of much of the
material -- but it means agreement across subjects has not been shown for that
entry, and a card resting on one should say so.

A second tier exists for entries something else needs and neither an anchored
nor a theory-derived entry of the frozen file covers:
`data/codebook/v0.1_theory.json`, same schema, empty anchors, and a
provenance naming what asked for the entry. It holds one entry, for a default
mode that settles a choice by taking whatever is already in the room. The
check reads the two files as one book.

### 2.4 The twenty families, with what version 0.1 holds

A family is what the behaviour is. The counts are read from the frozen file.

| # | family | entries | anchored | theory | what it holds |
|---|---|---|---|---|---|
| F1 | self-presentation and face | 12 | 12 | 0 | how she manages how she is seen: hedges, deflected praise, credit routed away, the mask, the small face-saving lie |
| F2 | disclosure and concealment | 12 | 10 | 2 | what she tells, to whom, when: the trouble told only once it is closed, the late disclosure, the thing said then taken back |
| F3 | affect regulation | 10 | 8 | 2 | what she does with a feeling once she has it: comedy, naming it instead of showing it, sitting on it, the spiral, the discharge at a gauge's end |
| F4 | approach and initiative | 9 | 4 | 5 | reaching first: writing with no occasion, inviting, asking directly, the poke when he goes quiet |
| F5 | avoidance and withdrawal | 6 | 4 | 2 | the exit and the silence: one line then nothing, leaving without closing, present but not participating |
| F6 | attachment and reassurance | 9 | 6 | 3 | checking she is still held: silence read as a verdict, the reply-speed watch, the retrospective audit of her own message |
| F7 | conflict, rupture and repair | 10 | 6 | 4 | anger and what is done with it: the flat word walked back, the apology before anybody objects, the rupture that scars unmended |
| F8 | status, comparison and rank | 4 | 2 | 2 | where she stands: keeping score, measuring herself against a friend and reporting the gap, envy as flatness |
| F9 | belonging and conformity | 6 | 6 | 0 | not being the one outside: the room's verdict arriving as her own, going ill rather than miss what is said |
| F10 | care and obligation | 10 | 9 | 1 | doing for others: worry arriving as an instruction, the promise and its due date, the credit handed outward |
| F11 | self-concept and self-belief | 12 | 11 | 1 | what she says she is: the label she gives herself, the role refused, the rule she states about her own nature |
| F12 | decision and commitment | 12 | 7 | 5 | how a choice is made and held: deciding for everybody, handing it back the moment it is made, the plan changed on the day |
| F13 | attention and noticing | 12 | 9 | 3 | what she reports seeing: the price, the time, the slip caught and kept, the thing that was there and went unremarked |
| F14 | humour and play | 8 | 6 | 2 | the bit: the deadpan correction, self-failure comedy, the joke that delivers a real thing |
| F15 | the frame and the format | 10 | 9 | 1 | what the room requires: the opener, the corner's scaffold, the register a channel licenses. Every entry here is the format's by definition, so that a format behaviour is coded and then excluded from the person |
| F16 | memory and narrative | 14 | 12 | 2 | how what happened is told: the callback, the anecdote retold with one shape, the dated memory, the story stopped before its end |
| F17 | wanting and taste | 10 | 6 | 4 | appetite and preference: the want stated with its refusal attached, buying and not using, the taste drifting from his to hers |
| F18 | body and state | 9 | 6 | 3 | what the body does to the rest: the register that changes when tired, appetite reported as a surprise, being unwell given or withheld as a reason |
| F19 | the picture of another person | 8 | 4 | 4 | what she believes about somebody and what she does with it: the belief defended rather than revised, the stored evidence produced when it costs |
| F20 | requests and refusals | 6 | 1 | 5 | the exchange of obligations: asking, refusing while staying in the room, granting reluctantly, the smaller true counter-offer |
| | **total** | **189** | **138** | **51** | |

Two families exist because the inventories found material with nowhere to go.
Four observations of revising a belief about another person had been filed
under noticing, because nothing covered what she then believes; four refusals
that keep the conversation open had been filed under withdrawal, and they are
not withdrawal. Those are the picture of another person and requests and
refusals.

**No family is empty**, and the shape of the imbalance is itself a finding.
The extractions are thin in reaching first, withdrawing, attachment, repair,
rank, belonging, wanting and body, and the reason is the corpus rather than
the people: a solo broadcast has no second person in the room, and silence
leaves no trace on a tape, so attachment has zero clusters from the second
subject. Those families are stated as bounds on a card and never as findings
about her. The reverse asymmetry holds too: humour and the format carry 27 of
the second subject's 77 clusters and 757 of her 1,842 observations. The mind
library is lopsided the other way, with 23 rows of affect regulation and 19 of
attachment against two each of humour and wanting.

**What the ledger says the book can express.** The share of each source's real
mechanisms some entry covers, against the ninety-percent bar the plan set:
the scope's own 128 candidates, 100%; the extracted candidates, 121 of 123 at
98.4%; the authored candidates, 54 of 54; the authored mechanisms of the six
people around the first character, 100% of the 58 the inventory does not call
a one-occasion moment (63 rows, 61 mapped, 2 refused as moments -- a Sunday
behind a grandmother's counter and a Saturday morning that belongs to a little
sister); the first character's bible read as mechanisms, 30 of 30. The two
lost extracted candidates are one function counted in two families -- a word
doubled at a feeling's peak, which is a form with no function of its own and
belongs to the marker battery.

### 2.5 The dimensions every instance carries

A family is what the behaviour is. These are recorded on every instance and
are what the numbers are cut by:

- **the target**: herself, him, a friend, the group, a stranger, the audience;
- **the channel**: spoken on air, typed to one person, typed to a room, in
  person, written for herself;
- **the occasion**: offered and taken, offered and declined, not offered;
- **portability**: whether the rate held across the parts of the programme or
  depended on one -- computed, never authored (§4.6);
- **class**: hers, the format's, a single moment, per subject;
- **tier**: evidenced, inferred, speculated, authored.

The same entry with a different target is one entry and not two. The apology
for nothing owed, said to him and said to a friend, is one behaviour cut two
ways, and the cut is where a relationship shows.

**The three tiers, as a field and not a caveat.** An `evidenced` row needs
receipts, an episode count, and a rate with an interval. An `inferred` row
names the evidenced claims it rests on, by identifier. A `speculated` row
names the frame that generated it and the evidenced claims it must not
contradict. An `authored` row is somebody's decision and is never quotable as
a measurement. This buys two things immediately: a later reader can strip
every speculated row and regenerate it from a different frame without touching
the rest, and the running character can be told which is which, so a
speculated trait is held loosely and an evidenced one is not up for
negotiation.

**One older vocabulary describes the same thing and is still in use, so here is
the mapping.** `docs/pattern.md` §4 grades a claim on a numbered ladder of six
levels, and that ladder is cited by ten of the second character's own documents
and by two of her live prompt files, so it is not being replaced. Read across:
**level 0 is `evidenced`**; **level 1 is not a tier at all** but a declared hole
and belongs in the bounds block; **levels 2, 3 and 4 are all `inferred`** --
cautious adjacent inference, functional completion, and contrastive inference
from what everybody else in the room does and she never does -- because each
one names the level-0 records it was built from, which is what `inferred`
requires; **level 5 is `speculated`**, a conservative placeholder easily
overridden by later material; and **an authorial decision is `authored` at no
level**, because the ladder grades evidence and an authored row has none. The
ladder's own hardest rule is this guide's: **a level above 0 may not contradict
a level 0 record**, and "the genre average is not a level". The tier field is
the one this guide uses, because it carries the frame requirement the numbered
ladder does not, and because three names are easier to hold than six.

**There is no cap on how many rows may be inferred or speculated.** The card
carries **as many as the situations it has to answer require**. A character who
will be alone in a flat, will be asked what she wants, and will be left
unanswered for a day needs rows about all three, and a broadcast corpus has
none of them. What such a row owes is not scarcity, it is three fields: **the
frame that generated it, the evidenced rows it rests on by identifier, and its
validation** -- which readings converged on it, what held-out material it
predicted, and what would have contradicted it. A card that is mostly inference
and carries those three on every inferred row can be argued with; a card with
six speculated rows and no frame on any of them cannot. **Count the rows with
no frame, and that count must be zero.**

### 2.6 The version discipline

The version is on the file, on every entry, and in the filename. **A change of
version invalidates every code reference written under the previous one**,
because a prevalence computed across two versions is a number about two
different instruments. So a version is changed deliberately and rarely, and
changing it means a new pair of files, the loss ledger re-run because the
mapping from a candidate to an entry has moved, every code reference re-derived
from the new ledger rather than edited in place, and the check's own version
moved.

**The check refuses a mismatch**, and because it runs inside the build check
before a restart, a half-moved version stops the restart. That is deliberate:
half-moved is worse than either version, because it is the state in which a
coded pass silently mixes two instruments.

Within one version identifiers are frozen. A wrong identifier is corrected by
adding the right one and marking the wrong one lost in the ledger, never by
renaming, because a rename is invisible to everything already pointing at the
old name.

**Nothing may be added during a coding run.** Candidates go to a parking list
and the next version reads it.

### 2.7 What is deliberately out of scope

- **A feeling is not an entry.** A feeling is a gauge with a baseline and a
  reader; an entry is what she does while the gauge is where it is. The gauge
  machinery already refuses a feeling nobody acts on, and the check refuses an
  entry that is a feeling's name.
- **Traits, types and diagnoses.** Derived above the table from the
  distribution, never coded in it, and never reported as a finding.
- **Anything that needs a face, a voice or a body to define.** A channel may
  add evidence to an entry; an entry that cannot be seen in a subtitle file
  cannot be in a vocabulary shared between a tape, a chat log and a written
  sheet.
- **Interior explanation as definition.** "She deflects praise because she
  fears exposure" is two things: a behaviour (deflects praise) and an
  inference (because). The entry carries the first; a card may carry the
  second as a driver, tiered.

---

## 3. The two routes to a character, and the seam between them

Both routes end in the same object -- a mechanisms file of instances of the
shared codebook, rendered into the calls where she speaks or is planned -- and
both are measured the same way, a coded pass over her record against what her
file intends. They differ in where the instances come from, what they can
claim, what they cost and what they cannot know.

### 3.1 Written: from a private prior to behaviour

The author declares a prior, a compile step turns it into behaviour, and the
author specialises that into her world. **The type is never stated to the
model**: a model shown behaviour and asked to produce the type is the
experiment, and a model shown the type is a different and worse experiment.
The type is also the **last** step on this route as on the other: after the
compile and the specialisation it is re-derived from the behaviour that
actually resulted, and checked against the prior the author declared, because a
written character whose compiled behaviour no longer types as her prior has
drifted somewhere in the compile (§3.6).

**Three layers, held apart by a check rather than by good intentions.**

| layer | the file | who reads it |
|---|---|---|
| the prior | four letters, the function stack, the health setting, the author's one line of why, and the contradictions the record forces | the compiler and the measurement; never a prompt, never a role |
| the compiled instances | her mechanisms file: instances of codebook entries with her triggers, suppressors, frequency bands and drivers, plus her gauge baselines each naming the line the number came from | the renderer, into the calls where she speaks or is planned, as prose in her language |
| the markers | emitted by the same compile, per entry and per pole | the type test and the coded pass; never a prompt |

The rule is enforced: a check greps every prompt file, every fills file and
every sheet the renderer reads for the whole type vocabulary -- the sixteen
four-letter codes, the eight function names long and short, and the position
words -- and fails on a hit.

**What makes a type a mechanism is the conditional part**, not the four
adjectives, and every piece of it is a trigger and a suppressor on a gauge the
runtime already keeps. The default mode is the highest-frequency entries
firing on ordinary occasions. The support mode is the medium-frequency
entries that moderate it and fall silent first under load. **The stress mode
that runs on a gauge held high** starts when a gauge has sat at or above a
line for a span of hours and is what the rumination machinery gets its content
from. **The stress mode at a gauge's end** is the crude opposite appearing
after prolonged load and is what the discharge machinery gets its shape from.
Health is a dial rather than a label: the support mode's frequency down, the
two stress modes' up, the thresholds down, and the baselines of the gauges
that matter to that type moved.

**The compile table** is a table of authorial decisions, versioned with the
codebook and refusing to compile against any other version. Eight functions by
four positions, thirty-two cells, **104 code bindings over 66 distinct
entries**. Each cell names two to four entries with a frequency band, a
trigger template and a suppressor template written in behavioural words with
no function's name in them, the markers it contributes, and -- for the two
stress positions -- the gauge and the reading that starts the mode, set just
under the level the discharge rules fire that gauge at. Seventeen of the
thirty-two cells carry the wordings a compile needs, the ones the people
currently on file reach; the other fifteen carry entries, bands, mode and
markers and no wordings, and the tool refuses and names the cell rather than
rendering an empty line into somebody's prompt.

**The pipeline for a new written character.** The author writes the prior. The
compile tool writes the derived layer of her mechanisms file, the gauge
baselines with their basis lines, and the markers block, and refuses if the
table's version does not match the codebook's. The author specialises the
templates into her world -- "a plan is open and somebody hesitates" becomes
"the group has not fixed where to eat and one of them has gone quiet" -- keeping
the entry identifier, adds what no type predicts (a backstory, a secret, a
tic, a relative), and writes her sheet's prose **from** the instances, never
the other way round. Every instance carries a tier: derived for what the
compile wrote, authored for the specialisation and for anything added by hand,
so a later reader can strip the authored layer and recompile. Then the
generator builds her, the existence matrix proves she builds, the fills check
proves her prompt renders, and the vocabulary grep proves the type is nowhere
in what the model reads. After a span of record, the coded pass yields her
actual distribution and the comparison per axis and per position is the
finding.

**What exists on this route today.** The first character's circle is the
hand-made version done before the compile existed: 63 authored mechanisms over
six people, written in one evening, of which 61 now carry a codebook entry and
2 are refused as one-occasion moments; six private type files no prompt may
read; three backstories. Her own bible and speech guide were read as a
mechanisms file of 30 entries with the sentence of her sheet as each receipt.
The derived layer and both stress modes are now compiled under the
hand-written instances.

**The gauge baselines a compile proposes are a proposal.** Moving a running
character's baselines is the owner's call and the compile does not do it. This
matters more than it sounds: in about a third of the mind library's gates the
real dial is a gauge's baseline rather than the mechanism's threshold, because
every gate reads distance from rest, so fitting a prevalence there takes every
other reader of that gauge with it.

**Three families the library barely implements and should not be made to**:
humour (two rows, and the model's to decide), wanting an object (two rows;
every drive in the gauge table is a deficit about people), and the
deliberation in the middle of a decision (intentions and promises exist and
settle; weighing two options does not). Conformity and narrative are decided
in prose. A character with no body has the body family's gauges absent rather
than at zero, so a body entry is undefined for her rather than unobserved.

### 3.2 Extracted: from a corpus to an evidenced card

The structural change from the two runs on record: **extraction is two passes,
not one.** A free discovery pass whose product is a codebook, then a coded
pass against that frozen codebook whose product is the numbers. Everything
that was unstable about the earlier runs was the absence of the second pass.

#### What the subject has to come with

Transcribed speech, and nothing else is required. The pipeline never touches
audio. Its input is subtitle files: one file per session, cues with
timestamps, no speaker tags. The second subject's run had 99 sessions, 52,993
cues, 848,178 characters after cleaning, of which 532,880 (63%) were hers,
47.2 hours of tape over a stated window. The third had 57 episodes and 55.7
hours.

The filename carries the metadata and the pattern is hardcoded to one
programme's naming; **for a new subject that is the first thing to change**,
and it is two lines. A file with no session number and no date still gets a
corpus file but sorts nowhere, joins no per-year bucket, and cannot be cited.

The transcription is assumed to be a recogniser's and assumed to be wrong in
specific ways: stray spaces inside words are cleaned, because they break both
counting and quote matching; cues in a script foreign to the subject's
language are dropped as hallucinations over music; and **nothing corrects a
misheard word**.

#### Stage by stage

| stage | what it is | who does it | what it costs |
|---|---|---|---|
| corpus | subtitle files in, one cue file per episode out, plus the inventory | code | nothing |
| attribution | contiguous runs of cues labelled by who produced the words | one model call per episode | ~80k output tokens an episode, nearly all reasoning: the most expensive stage |
| fingerprint and bounds | surface marker counts over her spans, the others' spans and the borrowed prose; the three bounding measures | code | nothing |
| the reading control | six episodes read end to end, findings with cue receipts | a reader whose full transcript is kept | a day |
| free extraction | register, mechanisms, moments and stated facts per episode | one call per episode, three passes | ~$1.75 for 57 episodes |
| reduce by function | clustering, merging, one synthesis per cluster | many calls, code owns every number | ~$1 |
| consolidation | the draft becomes a frozen codebook | reading | **two to three days, and it decides everything after it** |
| pilot and gate | reliability per entry on three episodes | a panel of model families plus a hand anchor | measured at $2.12 on one family (§4.5) |
| the coded pass | one row per entry per chunk, present with spans or explicitly absent | model calls, eight at a time | budgeted under $3 for 57 episodes at five codings |
| holdout, specificity, counting, cross-subject | does a rate predict episodes it was not fitted on | code, plus one cheap cross-subject pass | ~$0.60 |
| judgement | every surviving entry read with its evidence and classed | reading | a day |
| records, moments, trigger table | the state the simulation reads | code plus a day of reading | nothing |
| profile and type | five factors with a confidence per dimension, a type derived as a handle | a few calls, a morning of reading | cents |
| the speculative readings | one independent reading per session under a stated frame, asked about the person behind the performance | one call per session | ~$1 to a few dollars, by model (§3.2's convergence pass, step one) |
| tiers and the gaps | every inferred and speculated row with its frame, the evidenced rows it rests on, its convergence count and its held-out result | reading | a day |
| the card | drivers, the trigger table, the baselines, the bounds | a writer, plus the shape check | cents |
| the speech guide, sorted | every rule marked measured, thin, inferred or authored, in its own file | reading | half a day |
| a day run, read against a control | the card driven through the real code and read | the day harness | ~$1 |

Compute for the whole thing was estimated at under fifteen dollars. Reading is
about two weeks. **The three days of consolidation are the ones that decide
whether any number after them means anything.** The pilot's measured spend
(§4.5) says the compute estimate is optimistic for the coded stages and the
reading estimate is not.

#### What each stage is actually for

**Attribution** assumes the tape is a mixture of voices and text and that only
one of them is the subject. The five labels used on the runs so far are: her
own words (the default when the labeller cannot tell); somebody else's prose
read aloud by her, which is the dangerous one because it is in her voice and
is not her language; copy, meaning advertisements, announcements, titles;
lyrics caught over music; and anybody who is not her. **A new subject needs
this set re-argued, not reused** -- the labels are a model of one programme's
structure -- but the useful distinction is always the same one: **words the
subject produced against words the subject only voiced.**

Code verifies the answer covers every cue exactly once in order, repairs a
near-miss mechanically and re-asks garbage. Everything downstream inherits
these labels, including the negative space, so an attribution error appears
later as a finding. The known bleed is a letter's closing line leaking one or
two cues into her span, worth about 0.013 of separation power downstream.

Two things neither earlier run did, both cheap and both now required. **Label
the not-her spans by speaker in at least five episodes**, because one label for
everyone who is not her makes "the room" a mixture, and if most of it is men
then part of every later separation figure is telling a woman from men and
needs no description of *her* at all. Nothing in either corpus bounds how
large that part is; it is the largest structural hole in the work. And **have
two independent readers attribute the same three episodes**: the measured
agreement, 95.6 to 98.4% on the third subject, is the reliability of the
foundation everything else stands on, and it is the one layer that can be
called solved.

**The fingerprint and the negative space** exist so three things are available
that no model can fudge: a mechanical baseline of the subject's surface, a
receipt for each countable claim in whatever prose already describes her, and
a check on the extractor. It is **the most person-specific part of the
pipeline** -- all 35 markers on the run were one woman's forms -- so for a new
subject the battery is rebuilt from scratch. What transfers is the shape of it
(first-person forms, sentence endings, hedges, connectives, self-cancellation,
address terms) and the discipline: count the family, not the spelling, because
vowel length in a filler is the recogniser's guess as much as the speaker's.
Read totals with dispersion beside them, never totals alone: 45 instances of
one word once landed in a single broadcast.

Running the same battery over the *other* voices is where a marker gets
returned to its owner. On the second subject, the idol register a
hand-written card ascribed to her belonged to the room at nine times her rate,
one formula belonged to the announcer, and against the other voices in the
same studio she is the casual one by a factor of two -- the polite frame is a
frame.

**The three bounding measures** are arithmetic over what is already on disk:
what share of her speech begins as a response rather than an initiation (87.9%
on the second subject, with 2.3% of her speaking spans opening cold); which
relationship types are present and which have no data at all (four and four);
how many distinct emotional pressures appear (six, one of them twice in 47.2
hours). These go on the card as **the statement of what it cannot support**,
as an explicit no-data block, because a model told nothing about her anger
writes anger from the genre average. This is the cheapest stage and the one
most likely to be skipped.

**The reading control** is the second route to the same material and it is
only a control if it is written **before** anyone has seen an extraction. Six
episodes end to end, each finding carrying a cue receipt. Every automated pass
is then measured against it: the free-extraction brief was accepted because it
recovered about 85% of the reading's findings on the two easiest sessions, and
judged later against five sessions the same sheet recovered 33 of 46, 72%.

**A correction that must not be inherited.** Several files call this reading
"by hand", "my own eyes" or "human control". It was none of those: **every
pass marked as a hand read on the runs so far was a long-context model session
reading the tape, not a person.** "No model call was made" is true of all of
them and means only that no tool made an API call. That does not make the work
worthless -- reading 99 sessions end to end is a genuinely different method
from chunked extraction plus clustering, and a different method catches
different things -- but it makes two claims false: a recall figure measured
against it is recall against another model's reading by another route rather
than against a human ceiling, and it is not independent of the extraction in
the way a person's reading would be. The same correction applies to the
pilot's anchor (§4.5).

**Free extraction** consumes her attributed cues verbatim and numbered, with
borrowed prose compressed to one context line and everything else dropped --
never the raw transcript. Output per episode: a register block, mechanisms
with trigger, suppressor, function, variation, evidence and confidence,
moments of six kinds, and facts she states about her own life. Code then
verifies every evidence quote against the cue it cites, whitespace-insensitive,
allowing a quote to span two adjacent cues with its index corrected. What fails
is dropped, a mechanism with no surviving evidence is dropped, and **the
offered-to-verified ratio is stored per episode, because that ratio is the
invention measure**. It has sat at 98 to 100% on every competent model.

Three rules on it. **Whole episode per call**: a mechanism is a repeat and only
a whole read sees one. **A floor and no ceiling in the brief** -- "if you have
found three, you have stopped early" and nothing about how many to expect;
a brief that names a range gets that range back, and on the third subject
every model stopped inside "ten to fourteen" and yielded a third of what the
same cheap model produced on the floor-only brief, while deleting the anchor
outright with no coverage rule in its place cost recall 13 to 7. And **run it
three times, not once**: about $1.75, and it produces the one number both
earlier runs skipped, run-to-run agreement on cited cues, which is what makes
every later comparison readable.

**The reduce** clusters by function in chunks of 300 observations, merges in
rounds of at most 120 records a call with the batches inside a round parallel
and the rounds sequential, then synthesises one entry per final cluster, with
code verifying at every step that nothing was dropped or invented. Chunk size
was measured: 200 gave 122 clusters with 79 singletons, 400 put three of five
calls into the output ceiling, 300 is the squeeze.

**Its output is a draft, not a result.** On the second subject it produced 77
clusters with every quote real and every quote attributed correctly, and about
10% of the placements wrong: one cluster held about fifteen members that
belong elsewhere, the boundary between two of the widest clusters was not
reproducible from their members, and the synthesis prose described the
commonest surface of a cluster rather than the cluster. A purity statistic
finds the lumped clusters without a reader: 0.33 and 0.40 on the two bad
clusters against 0.80 and 0.74 on two good ones. **Do not report the cluster
count as an achievement**: 77 was over-splitting and over-lumping at once, and
six survived into the character sheet.

**Consolidation into the codebook** is the expensive step and it is where the
whole method's quality is set. From the reduce's draft, write entries with the
full schema of §2.1, using a tool that prints one cluster with every cited cue
in its surrounding tape so a claim can be judged against what is actually
there. Then freeze.

**The coded pass** is the free extractor with the codebook in the brief and the
output changed to **one row per entry per chunk, present with spans or
explicitly absent**, plus trigger-present-code-absent rows against the entry's
occasions, a confidence per instance, and a free-text parking note. Forced
absence is the important half. In chunks cut at the episode's own segments
(§5.5). Products, all computed by code: per entry, episode count, rate,
interval, agreement; per episode, which entries fired with spans; per entry per
part of the programme, the rate in each separately.

**Judgement** reads every surviving entry with its evidence in context and
classes it hers, the format's, or a single moment. On the second subject that
came out 45, 16 and 16 of 77. The class is a field on the instance and on the
card, not a footnote.

**Facts into records.** Raw stated facts grouped by fact rather than by
subject, each with its receipts. On the second subject 929 raw stated facts
became 152 records and 475 of the 929 were not facts about her at all --
session-number announcements, release dates, corner scaffolding, fragments
that mean nothing once the surrounding cues are read. 111 of the 152 carry
more than one receipt and 74 are stated in more than one session, which is the
count that matters: two cues from one broadcast are one telling. On the third
subject the consolidation stands at 363 records with 924 receipts, off 775
mechanism observations with 2,027 verified receipts.

**These are claims she made on air, not facts about her life**, and they are
tiered as evidenced-as-claim. Expect about half to rest on a single episode; a
record stated in two or more is the one the corpus can call a property of the
person. The importance criterion is a judgement and is written down so it can
be argued: **a record is in if it changes what she would say next; it is out if
it only changes what an encyclopaedia would say about her.** Three grades: she
could raise it unprompted; usable when the subject comes up; true but inert. A
mundane fact is top grade when it is the occasion for a habit -- a dead light
fitting is mundane, and not changing it for six months while narrating it
weekly is the character.

**Moments** are the six kinds the free pass extracts. On the third subject:
sincerity 104, self-belief 74, delight 69, the drop 47, loneliness 27, anger 5,
so 326 over 57 episodes. The drops and the sincerity moments are the closest
the corpus comes to her with the performance off; they are few, which is
itself informative, and they are the highest-value material per instance in
the whole extraction. Keep them with their episode counts so nothing
downstream can promote a twice-in-fifty-hours instant into a trait.

**The trigger table is the state the simulation reads**, and it is not a type.
For every entry that survived the gate and is classed hers: trigger, response,
rate with interval, suppressor (from the trigger-present-code-absent rows,
which is the only evidence a suppressor can have), portability, drift as a
per-block value where the holdout demoted it, and the variation range. Gauge
baselines each naming the measurement they were set from. Decay and
habituation where the material supports a figure and marked unset where it
does not. **A type sits above this table as a tie-breaker for situations it
does not cover and is never consulted where the table has an entry.**

**The profile and the type.** Score a five-factor profile off the surviving
**portable** entries only, with receipts per dimension and a confidence per
dimension, because they will not be equally evidenced: apparent outgoingness
is confounded by a solo broadcast format, where being outgoing is the job, and
emotional stability is the best-evidenced thing in a corpus saturated with
self-monitoring. Derive a type from that profile as the generative handle,
carrying the per-axis confidence.

The four-letter scheme is used for one job and refused for the other. **As a
measurement it should not be used**: its dichotomies cut continuous traits at
a midpoint so a person near the cut flips letters between sittings, retest
agreement is poor for that reason, sixteen boxes is low resolution for a
character who has to behave differently in a hundred situations, and it has no
axis at all for the best-evidenced thing in these corpora. **As a generative
prior it is genuinely useful**, because a model has read an enormous amount
about how each type behaves, so four letters activate a coherent prior for a
thousand unobserved situations and nothing else available is as dense per
token. Three rules if it is used: derive it, never assert it; do not use it
alone, which is why the five-factor profile is the derived measure and the
type is read off it; and **keep the contradictions** -- where the tape
disagrees with the type, the tape wins and the disagreement stays on the
sheet, because a character who fits her type cleanly reads as a template and
the places a real person fails their own type are most of what makes them
legible as a person.

**The gaps, written on purpose: the convergence pass.** The corpus is a
performance and shows nothing of her unobserved life directly. Writing the gaps
is not the risky part; leaving them to be improvised at generation time is. The
pass has five steps: the first produces the material the rest works on, and the
last three are what make the first two worth anything. Each gap row still names
the **portable** entries it rests on (a situated entry may not found a gap
claim however frequent).

**One: produce the speculative readings, one per session.** This is a stage
with a cost and a product and it is easy to assume it already exists, because
on the third subject it did -- somebody had run it before the extraction
started. **On a fresh subject nobody has run it and it has to be commissioned,
because without it there is nothing to count.**

*The shape.* One call per session, each session read with no other session in
context and no findings from an earlier one carried in, so that agreement
between two sessions is agreement between two independent reads rather than one
read repeated. Output under a fixed set of headed categories with "None" where
the session has nothing for a category, and every category's answer written per
session rather than as a running profile. **That output shape is what makes the
section count of step three possible at all**: the file splits on its own
session headers, and a trait is counted by the number of sessions whose text
reaches it.

*What the call is asked.* The brief tells the reader it is building a record
for this one session and **not** a final profile, tells it to speculate about
the person rather than summarise the programme, and says in words that the
transcript is a recogniser's and carries errors it should account for and not
list. The question set that was actually used on the third subject is
`asumin/asumin_data/readme.txt`, with its answers in
`asumin/asumin_data/master_qa_output.txt`; stated as a brief, the eight
categories were:

| # | category | what it asks for |
|---|---|---|
| 1 | how she sees her own body and appearance | how she currently views her looks, her clothes and her age; physical action inferred from the audio; anything about her health, sleep or stamina |
| 2 | her voice and her language | the kind of laugh with a timestamp; filler words, stumbles, odd pronunciations; slips into her regional dialect |
| 3 | where she contradicts herself | places she calls herself weak set against actions that show stubbornness or risk; what she is afraid of about her career, her age and being left behind; how she handles being under strain |
| 4 | the people | every person named, with the **dynamic** rather than the name: what this person is to her and how she talks about them |
| 5 | taste | what she played or watched and the psychological reason she likes it; the objects she brings up and what her relation to the object shows |
| 6 | the stories | any anecdote from her past or her ordinary life told in this session |
| 7 | two or three lines that are her | direct quotations, with why each was chosen |
| 8 | the programme's own segments | what stood out in each named segment this session, written for a reader who already knows what the segment is |

**Categories two, three and five are where the person is** and categories one,
four, six and eight are mostly record. **Categories that ask for a laugh, a
pause, a gesture or a face are asked and then thrown away** if the reader had
only a transcript: on the third subject every one of the 57 sections carried a
laughter description and a body-language block, and all of them died at step
four under §1.3's rule that no claim may rest on something a subtitle file
cannot show. Ask for them anyway when the audio or the video exists and the
reader has it; delete the category when it does not, rather than paying for 57
sections of invention.

*What the readings are and are not.* **Useless as a source and useful as a
count.** They carry no cue index, no attribution label, and their quoted
strings are as likely to be the reader's own analytical labels as quotations
(§5.7 has the measurement: a third verbatim, two thirds not in the session at
all). So nothing goes from them into a card directly. What they are for is that
a trait 27 of them reach was reached from 27 different evenings.

*The held-out split, and it is a split of the corpus.* Fit on the sessions of
the first block and hold out the last, **and hold out the sessions rather than
the readings**: a reading of a held-out session read while forming a trait puts
the test set inside the training set, which is the drift error of §5.9. On the
third subject the split was sessions 1 to 40 against 41 to 57, the count
reported separately for each block, and the held-out block read only after the
traits were written. A summary file is not a corpus and cannot be split: if the
only material is one reduction of many sessions, there is no held-out block and
the step is skipped and said to be skipped.

**Two: name the frame on every row.** A frame is a stated way of looking, and
different frames reach different things. Three that have been used on this
project: the per-session speculative reading of step one; the coded pass
against the frozen codebook, which asks only whether a defined behaviour
occurred; and **the type prior as the second frame** -- what a person of the
shape the profile came out at does in a situation nobody recorded. The type
prior is used here and nowhere else: it may fill a gap the tape is silent
about, and it may never be the source of a rule in the trigger table, the
mechanisms, the bible or the speech guide (§3.6). A row it produced says so, so
that a later reader who rejects the type can strip exactly those rows.
**Name the frame on every row**, or it cannot be stripped and regenerated
later, which is the point of the tier field.

**Three: count the sessions that converge, and say how the net was drawn.**
Where the material is a set of independent readings -- 57 reads of 57 sessions,
one per session -- a trait asserted in many of them was reached from many
different evenings and a trait asserted in one was not. The count is mechanical
and its code is the record of how it was made: split the file on its own
session headers, and count, per candidate trait, the sessions containing at
least one of that trait's key strings, in the two blocks separately. **The net
belongs in the source rather than in the prose**, so a reader can disagree with
a specific string (`converge.py` in the third subject's report directory is the
worked instance). **The count is a ranking and not a proof**, for two reasons
that go wherever it is quoted: readings by one model share that model's blind
spots (§4.3), and a keyword net over prose over-counts -- a generic word like
tiredness or family appears in nearly every section as furniture and has to be
narrowed until it does not. **Read the matched sentences before keeping a
trait**, and report the count with the net beside it.

**Four: drop what an evidenced entry contradicts, whatever the count.** This
is the rule that makes the count safe to use at all. The worked example is on
the third subject: about fifteen of the 57 readings assert that her regional
accent surfaces when she is moved, several quoting it. The surface count says
six dialect tokens in three episodes of 901,064 characters, two thirds of them
inside one broadcast. **A converged claim died to an arithmetic one, and that
is the correct direction.** The same rule retired every claim in that file read
off a laugh, a pause or a gesture -- the reader had a transcript and no video
-- and it retired a psychological reading of the subject that turned out, on
checking the attribution, to be a fortune teller's speech about her sitting in
somebody else's span.

**Five: predict held-out material, and score it.** Take the traits as they
stand from the first N sessions and check whether sessions N+1 to the end
report behaviour consistent with them. A trait that predicts what the held-out
sessions report earns its confidence; one they contradict is dropped or
lowered; one they revise is revised.

**The rubric, so the three words mean the same thing twice.** A trait is scored
on the held-out block and nowhere else, and the verdict is one of three:

| verdict | what earns it | what happens to the row |
|---|---|---|
| **confirmed** | at least one held-out session reports an episode the trait predicts, named with its session and, where the phrasing is hers, its cue -- and no held-out session reports one it forbids | kept; its confidence is the higher of the two bands below |
| **revised** | held-out sessions report behaviour the trait half predicts, and the difference is statable as a narrower or differently conditioned rule | rewritten to the narrower rule, the old wording kept beside it in the report so the change can be argued, tier `inferred` at best |
| **contradicted** | a held-out session reports behaviour the trait forbids, or an evidenced entry's arithmetic says it did not happen at the rate claimed | dropped, whatever the count, and named in the list of what was dropped |

**Confidence follows the count and the verdict together, and the rule is
written down rather than felt.** The mapping used on the third subject: a trait
confirmed on the held-out block with a count in double figures across both
blocks sits at 78 to 88; confirmed with a single-figure count, or resting on
one held-out instance, at 70 to 78; a revised trait at 60, because the first
reading of it was wrong once already; and no trait goes above 88, because none
of them is a measurement. §10.3 is the same rule as the file format the running
character reads it through.

**A trait with no held-out result is not thereby confirmed.** Where the
material cannot be split (§3.2 step one), every row says `holdout: none` and
carries only its convergence count, and that is a weaker card said honestly
rather than the same card with a gap in it.

**The revisions are the most valuable output of the step**,
because a trait that survives unchanged tells you only that the reading was
stable. On the third subject nineteen of twenty traits were confirmed and one
was rewritten: "asked what she wants she produces no preference and takes what
is going" became "on what she does not care about she takes what is going, and
on what she does care about she asks and then does what she was going to do",
which the later episodes show repeatedly and the earlier ones do not.

Beyond the five steps the older check still applies and costs nothing: **check
each gap claim where the record touches it** -- how she eats alone against what
she reports eating, how she handles an unplanned day against an unplanned turn
on air. It cannot confirm a claim, only catch it contradicting the record.

**The card.** A handful of drivers rather than a behaviour list, each naming
the entries that express it and carrying a tier, because a driver predicts a
situation the material never contained and a list of surface behaviours
cannot. Then the trigger table, the baselines with their measurements, the
records, the moments with their counts, the profile with confidence per
dimension, the tier on every row, and the bounds statement as an explicit
no-data block. **Every sentence resolves to a cue, an identifier or a stated
frame; a sentence that resolves to none of those is deleted.** The bounds
statement ends with one line per gap saying what source, if any, could close
it -- which is the one thing the original method's completeness estimate had
that a bare bounds statement lacks.

**The speech guide goes in its own file, and every rule in it carries its
class.** The corpus is speech and the character types, so every rule in a
speech guide is a decision about how a spoken habit crosses into a text box,
and there is no held-out set of anything the subject would have typed. Sort
every rule as measured with counts, measured but thin, inferred, or authored,
and keep the sort in a separate file, or nobody downstream can tell which is
which: on the second subject the sort came out 14 measured, 7 thin, 6 inferred
and 10 authored, so roughly a third of the file was authorial decision wearing
the same typeface as the measured parts.

**And carry the format/person class of §2.5 into every rule, because a
format-class rule may never govern private writing.** The class is already a
field on every instance; a speech guide that drops it turns a fact about a room
into an instruction for a life. The failure is specific and it has happened: on
the third subject, "95.6% of her speech begins as a reply to a letter and 3.9%
opens cold" is a measurement of a fortnightly radio programme built on listener
mail, and it was written into her speech guide as a prohibition on raising a
subject in a private chat, with four length rules under it all derived from
"the letter sets the length". Nothing about the person licensed any of it.

The fix is structural rather than a rewording. **Format-class rules move into a
section of the speech guide headed as facts about the room, addressed to the
character, saying in her own language that the programme's shape is not hers**
-- so she still knows what her working life was, and none of it governs what
she types. **The rules they were feeding are rebuilt from what is hers.** On
the third subject, length is now set by whose subject is being discussed (short
and flat for his difficulty, the whole deliberation for her own: 6 instances
over 6 episodes), by whether she composed before sending (157 characters at
zero hedges when she did), and by what she has got that day. Every one of those
is measured over her own attributed speech, and none of them mentions a
letter.

**Porting the prompts is reading, not substitution.** The survey of the shared
prompt directory found 65 prompts, of which 41 name the previous character, 37
carry an output schema that must survive, and **20 presuppose a relationship
or the first character's life**. A file with names and no presuppositions is a
substitution; the 20 are rewrites, and they are rewrites for any second
character. What is character-bearing in a prompt is not the proper nouns, it
is the psychology written into the mechanism -- "being with one person calms
her, being watched by another does not" -- and substituting names into that
yields a different person with the first one's social world.

#### A worked example: the format filling the private chat

The third subject, found and fixed on 2026-09-08. Worth stating plainly,
because nothing about it was careless.

**The fault.** The strongest single line in her speech guide was
「テープのあなたの喋りの95.6%は、誰かの一通か誰かの声への返事として始まっている…
長さも、話題を出すことも、話を仕切ることも、番組の仕事。文字箱に持ってこない。」
-- a correct measurement of a fortnightly solo radio programme built on
listener letters, written as an instruction for a private chat with one man,
with four length rules under it all derived from "the letter sets the length".
Her bible said the same thing as a disposition:
「あなたが自分から何かを始めることはほとんどなくて、たいてい誰かの一通が先にある。」
Nothing in either file marked either as a fact about the room.

**Why it happened, and why it is general. A format has cues and a person does
not.** The programme's shape is countable -- reply-first rate, turn length, who
opens a topic, the polite floor -- and a card written from what the corpus can
count is a card of the programme. A private self leaves no countable trace in a
broadcast at all. So the honest-looking move, "write only what is measured", is
exactly the move that fills the private chat with the format.

**What it cost.** Read against a second resident character through one
17.6-hour silence they both lived at the same time, this character's gauges
moved further -- loneliness 33.8 to 53.7 against 35 to 46, warmth toward him
44.4 to 27.8 against 51.3 to 42.6 -- while her material forbade her to say so,
and her one self-started message in the whole silence turned the wait into her
own fault (`data/retired/20260908_1105_residents_silence/REPORT.md` §2).

**The fix, in the order it was done.** Sort every rule by class and tier and
keep the sort beside the file (`prompts_asumin/style_sort.md`: 25 sections, 17
hers and evidenced, one the format's entirely, one resting half on a receipt
that sits in a listener's span). Move the format-class rules into a section
headed as facts about the room. Rebuild the rules they were feeding from what
is hers. Extract the private self from the independent readings, count the
convergence, drop what an evidenced entry contradicts, score the held-out
block, and write the survivors into the bible as a section of its own, marked
line by line as reading or record. Then derive the type as the coherence check
on the whole (§3.6). The report is
`data/retired/20260908_1139_asumin_person_behind_voice/REPORT.md`.

### 3.3 When to use which

**Write** when the character is invented, when she is somebody on the roster
who may or may not be promoted, when the aim is to test whether a model can
carry a type from behaviour alone, or when there is no corpus and never will
be. The circle around the first character is the case: nobody will ever find a
tape of any of them.

**Extract** when a corpus exists and the aim is fidelity to a person on it,
which is the standard for the second and third characters: the question is
whether the output is her, judged against the tape with receipts, and no
amount of authoring answers it.

The asymmetry that matters most: **a written character is complete and
consistent because nothing constrains her, and an extracted one is incomplete
and inconsistent because the tape does.** The second is the more valuable
property for the illusion this project is after, and the written route can only
imitate it by writing the contradictions in on purpose.

| | written | extracted |
|---|---|---|
| tier of every instance | authored throughout; the derived layer is theory, the specialisation is invention | evidenced where a rate with an interval exists; inferred where two evidenced claims meet; speculated in the gaps, as many rows as the situations require, each carrying its frame, the rows under it and its validation |
| the suppressor | known, because the author wrote it, and it is the field that makes authored mechanisms agree | nearly absent from a free pass; inference until the coded pass records trigger-present-code-absent rows |
| frequency | a band the author chose, meaningful only relative to her other instances | a rate per episode and per part of the programme, with an interval, held out on later episodes |
| the type | the prior; the measurement tests whether the model reproduced it, never whether it is true. Re-derived from the compiled behaviour at the end as a check on the compile (§3.6) | derived from the surviving entries and the inferred traits, one confidence and its receipts per axis; **required as the last step of the extraction** (§3.6); a written prior would overwrite measured behaviour and is never compiled for her |
| contradictions | none, unless the author writes them in | the record's, kept on the sheet where it disagrees with the derived type |
| what she is with one person, in writing | whatever the author says; nothing checks it | absent from a broadcast corpus, stated as a bound; the largest hole in both extracted characters |
| a criterion | for a fictional character with a finite canon, the later canon; for an invented one, none | none for a living person; the later episodes hold out stability, not truth |
| model spend | cents: the compile is code, the sheet prose is an author's, a day run is about a dollar | budgeted under fifteen dollars on a cheap model; reading agent workers on the discovery pass is the expensive choice at about 110k tokens an episode |
| reading | half a day per character | about two weeks per subject, three days of it the consolidation |
| material | none beyond the author | subtitles at minimum; audio and footage as channels priced per episode; hand annotation never assumed |
| time to a running character | hours, once the compile exists | weeks |

### 3.4 Extraction from a fictional canon: the one case with a criterion

For a living person there is no criterion. **For a character from a finite
canon, the canon is the criterion**: a card built from the first half predicts
the second half, and the prediction can be scored on scenes the extraction
never saw, including the rare emotional ones a comedy's early episodes lack.
Hand annotations of such a character are the **anchor for that test rather
than an input to it**.

The extraction route on a fictional canon is also cheaper than on a broadcast
-- the speakers are labelled, the scenes are short, the register is dialogue --
and the written route is available for the same character as a control, so the
two can be compared on one subject: one codebook, one file compiled from a
type, one coded from the canon, both measured on held-out episodes. **That is
the cleanest test of the compile table there is and it costs a few dollars.**
It is also the cheapest honest test of "procedural with limited data", which
is why the second subject the codebook is run on should be a fictional one
with subtitles only.

The limits of a fictional source are the original method's and they are real.
Only what was performed can be extracted: a character in a comedy shows how
she handles romantic chaos and not how she handles grief, anger, betrayal or
solitude unless the show goes there. **The author's needs contaminate the
behaviour** -- some beats exist because a scene required them, not because the
character would organically do that -- and separating the two is judgement and
error-prone. And **consistency is an assumption the source may violate**: if a
mechanism extracted from early episodes is broken in a later one, deciding
between a genuine exception that reveals a suppressor and bad writing is a
judgement call.

#### The method, stage by stage, where it differs from a broadcast

Every invariant of §1.4 holds. What changes is the input, three stages, and one
check that exists only here.

**The input is speaker-tagged.** A script, a fan-transcribed screenplay or a
subtitle file for a dubbed release carries the speaker on the line, so
**attribution is a parse rather than a model call** -- the most expensive stage
of a broadcast run disappears, and with it the attribution error every later
figure inherits. What replaces it is a smaller job with its own failure: a
speaker label is a *name*, and the same person under two spellings is two
speakers. Normalise the label set by hand against the canon's own cast list
before anything reads it, and print the label counts, because a label with
three lines is usually a typo of a label with three hundred.

**Secondary text is a frame and never evidence.** An encyclopaedia article, a
wiki page or a fan compendium may be read before the coding to learn what
segments exist, who is related to whom and what order the canon runs in -- that
is a frame, and it saves a reader from mistaking a running joke for a one-off.
**No row's provenance may be a wiki.** The rule is already implemented for a
living subject and generalises unchanged: the second character's article was
fetched, cached and written to its own directory, and the tool that fetched it
is barred from writing to the record file (`yukarin/tools/wiki_ref.py`). A
claim whose only source would be secondary text does not go in; a claim that
has a scene behind it and a date the article corrects is recorded with the
disagreement noted and not resolved.

**A scene channel, coded into the same codebook.** A canon has what a radio
tape does not: a picture. What she does while somebody else talks, where she
puts herself in a room, what her face does against what she says -- the gap the
original method prized and a subtitle file cannot show. That channel is added
the way §1.3 allows and no other way: **its codes go in a separate, marked
section of the coded pass, its evidence may add to an entry defined on words
and may never define one, and a card built with it says so.** The project has
eyes for it already (`sensors/vision.py`, Gemini on Vertex, region `global`),
and the pricing and the verification discipline are §4.7's: a described action
is verified against the shot it cites exactly as a quote is verified against
its cue, by a second reader on a sample, and what fails is dropped. Where the
canon has an official script, prefer the script's own stage direction to a
model's reading of a frame: it is free and it is the author's.

**The volume is thin, and the rule for thin volume is not a different card.**
A season is a few hours of dialogue for one character where a radio corpus was
fifty-five. So most rows will be inferred rather than evidenced, every interval
will be wide, and the surface battery will have almost nothing testable
(§8 has the figures: about ten sessions to test a handful of markers, twenty
before there is any dispersion to read). **What does not change is the kind of
card.** The tier field carries the difference, the intervals carry the width,
the bounds statement carries what is absent, and a reader can see that this is
a thin card rather than a confident one. **What is refused is the compensation
move**: filling a thin canon out with the genre's average, or with what the
character is like in fan writing, or with a longer list of behaviours to make
the file look the same size as a rich one.

**And the check that exists only here: is the output the card's, or the model's
memory of a character it already knows?** For a living radio host a model has
read nothing; for a character from a broadcast anime it may have read a great
deal, and a card can score well while contributing nothing, because the model
was already able to write her. So the finding has to be a *difference*, and the
comparison is three-way on the same held-out scenes:

1. **the name only** -- the character named, no card, the situation given;
2. **the card with the name removed** -- every proper noun replaced, the
   mechanisms, triggers, suppressors and bounds intact;
3. **the card as written.**

If (1) matches the canon as well as (3) does, the card has established nothing
about the method on this subject, however good the output is. If (2) matches
and (1) does not, the card is carrying the character rather than the name, and
that is the result worth having. **Run it across model families**, because
"what the model already knows" varies by family more than by anything else the
harness changes: the second character's cross-provider control is the pattern
to copy -- one frozen instrument, the same inputs, the reference endpoint run
twice so that the agreement between its own two runs is the noise floor every
other comparison is read against (`yukarin/tools/control.py`), and no ranking
quoted from inside that floor (§4.4). This is also why §3.4's opening claim
matters: the canon is the only criterion in the whole method, and it is worth
nothing if the thing being scored is the model's prior.

### 3.5 The seam

**The codebook is what makes the two routes one system.** An instance is an
instance whether an author wrote it or a coded pass found it; the difference
is its tier and its receipt.

So a written character can be re-graded as her record grows: a coded pass over
her own turns yields her actual distribution, which is evidence about the model
under her prompt rather than about a person, but it is the same kind of number
an extracted character carries and the two can be compared entry for entry.
And an extracted character can be filled where the tape is silent by the
written route, tiered speculated, in as many rows as the situations she will
meet require, each row naming its frame and checked where the record touches
it. **Neither route is finished without the other: the written one has no
truth and the extracted one has no completeness.**

There is a third case, and it is the one that produces the most useful number.
**A live character with a record**: her sheet is prose and stays so, a
mechanisms file is written from her bible as instances of entries with the
sentence as the receipt and rendered into her prompt, and then the coded pass
runs over her own record in every room she talks in. The distribution she
actually shows is compared with the one her sheet intends, and **the gap
between the two is the finding** -- where the model is not doing what the sheet
says, and where the sheet says something the record never shows.

The closed circle has to be stated for authored characters: the prompt is
compiled from the prior and the record is written by the model under the
prompt, so the measurement is of obedience to the description. **A rate from
that measurement must never be fed back into the prompt.**

---

### 3.6 The type, as the required last step of both routes

**Every character ends with a four-letter type attached to her, derived from
the pattern as a whole, and no card is finished without one.** The owner's
rule, and it holds on the written route and the extracted route alike.

**What it claims and what it does not.** The label has no grounded validity and
nothing here pretends otherwise: its dichotomies cut continuous traits at a
midpoint so a person near the cut flips letters between sittings, retest
agreement is poor for that reason, and no published norm applies to this
material (§3.2, §4.1). What it represents is **the pattern as a whole**. In the
owner's words: if the person behind the pattern as a whole is being represented
correctly, we can type them. Which makes it the one cheap check on the whole
card at once.

**Why it is last, and why it is a check rather than a label.** Everything
before it is local -- an entry, a rate, a driver, a gap claim, each defensible
on its own. A type is the first statement that has to be true of all of them
together. **Deriving it forces the coherence question nothing else in the
procedure asks.** A card whose type will not settle -- where the axes only
resolve by ignoring half the entries -- is not a card missing a label. It is a
card whose pattern is not yet coherent, and the response is another pass over
the entries, not a pick between two letters.

**How.** Derive it from the surviving entries and the inferred traits, never
assert it, and never off the profile alone (§3.2 keeps the five-factor profile
as the derived measure and the type as the handle read off it). **Each axis
carries its letter, its confidence, and its receipts** -- cues, counts, or the
identifiers of the inferred rows -- so a reader can see which axis is thin.
**Every evidenced entry that fights the type goes to `contradictions` and is
never bent to fit**: a character who fits her type cleanly reads as a template,
and the places a real person fails their own type are most of what makes them
legible as a person. Where the near miss is close, name it and name the axis
that decides between them.

**What does not change.** The type is **never a source of a rule** -- nothing
in the trigger table, the mechanisms, the bible or the speech guide may be
derived from it -- and it is **never rendered into a prompt**.
`tools/cast_mechanisms_test.py` refuses the vocabulary anywhere a call reads,
and that check runs inside the build check before a restart.

**The format** is the one in `data/cast_types.json`, which is where the first
character's own type is kept: `type`, `why`, `axes` (a line, a confidence and
its receipts each), `contradictions`, `markers` (per axis, per pole, things a
counting tool can find in a single turn) and a note saying nothing reads it.
For a character rather than a cast member it goes on her own sheet under the
same field names: `characters/<key>/sheet.json`, key `type`. That file is
loaded at boot and read by the primitives seeder, the roster and some tools,
and is in no prompt -- the block headed HER CHARACTER SHEET in
`Config.role_system` is her bible, not the JSON.

**Worked, on the third subject.** ISFP, at I 82 / S 60 / F 85 / P 80, near miss
ISFJ with J/P the deciding axis (nine months of talking about a haircut, a
refusal to state any goal in advance, a free day given to nothing). Five
contradictions kept, including the one that matters most: an introvert whose
own room switches her off rather than restoring her,
「家にいるとき、もう何も頭が回転しないんですね」. The S axis is the thin one and its
confidence says so.

---

## 4. Measurement

### 4.1 The four layers, and the one rule

The single most useful rule in the framework: **a claim may not be stated at a
layer above the one its evidence reaches.**

| layer | what it asserts | status |
|---|---|---|
| the tape | these words were said | a recogniser's, with known non-uniform error |
| attribution | she said them, not a listener and not the staff | **solved**: 95.6 to 98.4% cue agreement between independent readers |
| occurrence | this behaviour occurred at these cues | the object of the whole framework |
| function | in context it did this for her | codeable with rules, weaker, needs its own reliability figure |
| construct | it indicates a disposition, a defence or a trait | **no criterion of truth; two of usefulness** -- prediction on held-out material, then the live output read against the standard (§3.2, §1.2) |

Most of the value is at occurrence, most of the risk is the slide from
function to construct, and **almost every sentence that sounds like psychology
is a construct sentence resting on occurrence evidence.** The original method
had the instinct when it refused to resolve whether a character fails to see a
dramatic framing or chooses to puncture it; making that refusal a rule rather
than a judgement call is the change.

**What changed at the construct layer, and why.** Saying only "no criterion
exists" was true and useless: it left every construct sentence equally
unsupported, so a card either avoided them -- and then had nothing to say about
a situation the material never contained, which is most of a life -- or
smuggled them in unmarked. There is still no criterion of truth. There are two
criteria of usefulness and both are checkable. **First, prediction on held-out
material**: a construct claim derived from part of the record either does or
does not predict what the rest of the record reports, and the held-out block is
scored before it is read for anything else (§3.2). **Second, the live output
against the standard**: once the character runs, her own words are the only
material in the whole procedure produced under the conditions the card is
actually for, and a construct claim her output contradicts is wrong about her
whatever the tape said. A construct row still may not be stated as a
measurement. It may now be stated as a claim carrying a frame, a count of the
independent readings that reached it, and a held-out result.

Where a family borrows its definitions from a published observer-rated system
-- the defence rating scales, the process model of emotion regulation, the
structural analysis of social behaviour, the relationship-narrative method,
conversation analysis of institutional talk -- the system is named in the
entry's provenance so a reader outside the project can see which half is
standardised. **Every one of them assumes speech that is not a performance to
an audience.** A solo late-night broadcast, scripted in part, with staff behind
glass, violates that assumption directly. Using them is off-label and must be
declared as such: they buy comparability of definition, not comparability of
norms, and **no published norm applies to this material and none may be cited
as if it did.** Bespoke families are marked bespoke and stay so.

### 4.2 Reliability per entry, and the gate

**The enabler.** Content analysis is normally rationed by human coder hours,
which is why most published work double-codes a tenth to a fifth of a corpus
and stops. At the measured cost per episode-read, five independent codings of
57 episodes were budgeted under three dollars. Reliability here is a compute
problem rather than a staffing problem, and that is a genuine advantage this
project has over the literature it borrows from. §4.5 is what it actually
cost.

**The statistic** is Krippendorff's alpha, because it handles many coders,
missing data and unitisation together, **reported per entry and never only as
a corpus average**, because an average hides the entries that are not working
and those are the ones that matter.

| alpha | what it means for that entry |
|---|---|
| below 0.4 | not operational; rewrite the exclusions and near misses |
| 0.4 to 0.67 | tentative; descriptive mention only, no inference on it |
| 0.67 and above | usable |
| 0.80 and above | conclusions may rest on it |

**An entry that cannot reach 0.67 after two rewrites is deleted, not kept with
a caveat.** That is the rule that makes the framework real rather than
decorative, and it is the one that will be hardest to obey, because the
entries that fail will include interesting ones.

**The gate**, before a corpus pass is justified: median **cross-family** alpha
at or above 0.67, and at least 60% of entries at or above it. Fail, rewrite
the failing entries' exclusions and near misses, repeat at most twice. If two
rewrites do not reach it, the answer for that corpus is no, and it will have
cost a few dollars and a few days of reading to establish, which is the point
of running it first.

**The unit must be fixed before agreement can be computed at all**, and
unitising reliability precedes coding reliability. The cue index is already a
fixed shared unit, so an instance is an entry identifier plus a contiguous cue
span, and coders are scored on the span overlap as well as on the label, with
the two reported separately.

### 4.3 What agreement between runs of one model is, and is not

**Model coders are not independent in the way human coders are.** They share
training data and therefore share systematic blind spots, so **agreement among
runs of one model overstates reliability by an unknown amount and is an upper
bound, never the honest figure.** Substituting a within-family number for a
cross-family one is the exact error to avoid, and the pilot is the
demonstration: the two model runs were closer to each other than either was to
a careful reading of the same episode under the same frozen book.

Two mitigations, both cheap. **A heterogeneous panel** -- the harness already
serves six model families, so cross-family agreement costs nothing extra. And
**an anchor read**, at least one episode coded end to end against the frozen
book with no model help, with every panel scored against it as well as against
itself. Note the correction of §3.2: an anchor produced this way by an agent
is another model's reading by another route, not a human ceiling, and should
be named as what it is.

**The blind spot a panel cannot see.** In the pilot, every reader including the
anchor coded a scripted role's lines as the subject's own moves, under seven
different person-level entries. An agreement figure is blind to this by
construction: all readers agreed and all were wrong in the same direction.
This is why the judgement pass, which reads with the tape open, is not
optional, and why the sampling and played-role rules of §4.5 are binding.

### 4.4 The noise floor, and what is on record about it

**No noise floor was ever measured on the second subject's run**, and it is
the one measurement that would make a host ranking interpretable. A tool was
written to produce it -- the reference endpoint run twice, the agreement
between those two runs being the floor every other comparison is read against
-- and the code below that docstring no longer implements it. It is four
calls.

What can be recovered from outputs that do exist: two runs of the same
extraction over one episode agree on about a quarter of the moments they cite,
two to three times chance, so the runs are reading the same text and are
nowhere near agreement; on the *names* of what they found they agree
essentially never, because those are free text a model invents.

**Model choice is not separable from the method's own variance.** The same
model on the same host with one inference setting changed agrees with itself
at 0.21 to 0.41 -- at or below the median agreement between two *different*
models. Whatever a host ranking is sorting on, the mid-field ordering is
inside the method's own noise and is not a result.

**And the description loses to counting.** On unseen sessions, telling the
subject from the other voices in the room:

| how the markers were chosen | separation |
|---|---|
| the commonest n-grams in the corpus, with no reference to who says them | **0.875** |
| markers picked by log-odds off the fit sessions, five lines of arithmetic | 0.873 |
| **the description read off the tape** | **0.808** |
| 29 forms of matched length and frequency drawn at random | 0.728 median |
| a hand-written character card, countable claims only | 0.653 |

The read description beats arbitrary forms decisively -- 1 of 200 random sets
reached it -- so the extraction found the woman rather than the episodes. It
loses to two procedures that involve no reading at all, by 0.068 with the
interval well clear of zero. It does carry something the counting does not:
adding it to the frequency baseline moves 0.875 to 0.898, and to the
fit-selected baseline 0.873 to 0.903, both intervals above zero. **A real
increment, and a small one, beside a separation that counting reaches on its
own.**

The honest reading: if the only goal were a discriminator, count n-grams. The
reading is worth its cost for what a count cannot produce -- triggers,
functions, suppressors, drivers, and a statement of what the material cannot
support -- and not for its ability to tell one voice from another. **Any card
claiming to describe a person has to be measured against that baseline or it
has established nothing.**

Two more things the earlier run did not establish, stated because a method
that buries its limits is worth nothing. **The extraction itself was never
held out**: the rates and prevalences were, fitting on the first 70 sessions
and testing on the last 29, but the sheet on disk was built from all 99, and
re-running the map over the fit sessions alone is the real test at about
seventy calls. And **a screen built from a corpus counts whether the subject's
markers appear**; a pattern absent from the corpus altogether cannot be
counted, because there is nothing to count it against.

### 4.5 The coded pilot: what it cost, why, and the rules it leaves

The section below is the orchestrator's own account, reproduced without
softening. Everything in it is read off the call ledger.

> ## The coded pilot of 2026-09-06: what it cost, why, and the rules it leaves
>
> The owner authorised the pilot at 09:20 expecting about thirty minutes:
> thirty-six chunk calls on DeepSeek v4 flash at eight concurrent, about
> thirty cents. It ran from 12:52 to 15:46 and cost $2.12 for four of nine
> codings. Every number below is read off `asumin/logs/calls.jsonl`.
>
> **Where the money went.** 65 coding calls: 27 finished (`stop`), 34 died
> (23 `error`, 11 `length`), 4 with no terminal row. The 27 that finished
> cost $0.56 together, median 573 seconds and two cents each. The 34 that
> died cost $1.57: median 1,800 seconds each, median 131,072 tokens out,
> median 425,570 characters of reasoning and up to 999,091, and not one
> character of answer. The two exits are one failure: the model reasoned for
> the whole generation and never began the answer, and whether the row says
> `error` (OpenRouter's request wall at about 1,800 seconds) or `length`
> (Together's ceiling of 131,072 output tokens) depends only on which came
> first. The client's recovery, handing the last 24,000 characters of
> reasoning back with an instruction to answer now, worked every time it was
> reached, at the price of a second full generation.
>
> **The five most expensive chunks** were all one chunk re-asked whole:
> ep010 run 1 chunk 2, six calls, $0.28, length then four errors then stop;
> ep010 run 2 chunk 1, five calls, $0.27, never finished; ep010 run 2 chunk
> 2, five calls, $0.20, never finished; ep010 run 1 chunk 3, six calls,
> $0.18; ep030 run 2 chunk 3, four calls, $0.14. The brief said a chunk whose
> answer fails twice is halved at the nearest segment boundary; the worker
> put the halving downstream of the client's own retry loop, so the client
> re-asked the whole chunk up to five times before the halving could see
> it.
>
> **Why it took seven hours.** The worker ran chunks one after another from
> 12:52; the guide's figure of eight concurrent, and the brief's, were not
> applied until the orchestrator read the ledger at 14:55, two hours in. The
> worker was then killed twice by the session limit (15:46 and earlier),
> and each death left its coding processes running as orphaned retry loops
> until the owner said nothing should be in flight at 16:00 and they were
> stopped by pid. The orchestrator's fault is the two hours of not reading
> the ledger; the worker's is the serial run and the retry placement.
>
> **What the four codings still established** (`asumin/pilot/BASELINE.md`,
> `REVIEW.md`): DeepSeek agrees with itself at a median alpha of 0.83 on the
> one episode coded twice, and with the Opus worker's hand reading at 0.03;
> the Opus review of 255 instances found the runs right 14 of 23 times where
> they disagree with that reading, and most of the gap to be a sampling rule
> the protocol never fixed (a code logged once at its clearest occurrence
> against once per chunk); sixteen codes clear the gate on both figures and
> carry the holdout's baseline rates; every reader, the hand one included,
> coded the kindergarten corner's scripted lines as her own moves, and the
> book has no rule for a played role.
>
> **The rules this leaves, all binding on any run that spends:**
>
> 1. A worker on paid calls reports its concurrency, its call count and its
>    spend after ten minutes, and the orchestrator reads the ledger at ten
>    and at thirty minutes, and messages on the first anomaly: serial calls,
>    a retry counter above two, `error` or `length` twice on one chunk.
> 2. A think-only death is handled inside the retry loop: the first is
>    handed back with the answer-now instruction, the second halves the
>    chunk at the nearest segment boundary, and a chunk is never asked whole
>    a third time. The client's own retry count for a coding call is two.
> 3. Eight concurrent is the default for a coded pass; a run that is serial
>    is wrong, not slow.
> 4. After a worker dies on the session limit, its child processes are
>    listed by exact command line before anything is resumed; a loop that
>    has outlived its worker is stale and is stopped by pid. A call in
>    flight under a live worker is never killed.
> 5. The coding protocol states the sampling rule (per chunk, for a coded
>    pass) and a played-role rule (a span the attribution marks as a role is
>    coded under the format and never under the person) before the next
>    coding call.
> 6. One family agreeing with itself is an upper bound and is reported as
>    such; the cross-family number is one coding of the anchor episode by a
>    second family, about twenty cents, and is bought before any corpus
>    pass.

**What the pilot's own numbers say about the instrument**, from the baseline
file it produced. Four codings exist where nine were designed, so one episode
has two readings and is the only one with any agreement figure at all. Within
one model, median alpha 0.830 with 73% of measurable entries at or above 0.67,
over 67 entries. Against the anchor reading, median 0.034 with 21% at or above
0.67, over 76 entries. Span overlap where both said present, mean 0.520.
Cross-family: **not measured**, so **the gate cannot be evaluated, and that is
structural rather than an oversight.**

The honest reading of the pair: **the codebook is internally consistent and
not yet demonstrably valid.** The raw numbers invite the wrong conclusion,
because the anchor recorded an entry once at its clearest occurrence and the
model runs recorded it in every chunk where it occurred, which produces a low
alpha on a four-unit matrix between two readers who are not actually
disagreeing. The same artefact explains the span overlap. And the figures rest
on four units per entry, where one disagreement moves an entry from 1.000 to
0.000, so any single entry's number is nearly noise and only the medians can
be read.

Six further findings from it, all of which change what the book must say:

- **Fabrication is not the failure mode, again**: 478 of 480 quotes offered
  exist character for character in the cue they cite and in a cue the
  attribution calls hers.
- **A rule for a played role is the single most consequential thing missing**,
  and the corpus already carries the label the rule would use.
- **A sampling rule belongs in the protocol, not in an entry**: record once at
  the clearest occurrence, or once per chunk. Say which.
- **An entry that can only be evidenced by its absence cannot be coded as
  written.** A prohibition ("say what she did, never why she is like that")
  has no positive instance to quote in a monologue, and the row shape cannot
  express "the occasion arose and she did nothing".
- **A position rule can do more work than the function it stands for.** One
  entry requires an exit to be offered before the ask; where the ask comes
  first and the refusal is made free one clause later, the function is
  identical and the entry cannot take it.
- **An entry requiring evidence of recurrence cannot be coded one episode at a
  time.** Either it is an episode-level entry with a different row shape or it
  is not an entry.

Two coverage results are worth as much as the agreement figures. **Seventy-two
parking notes were written and not one says the book had nowhere to put the
thing**: every parked observation was routed to a named neighbour with a
reason, which is the exclusions field doing the work it was written for. And
**no parking note reached a theory-derived entry**, so on that tape the
theory-derived half stays theory-derived. **Fifty-nine of the 138 anchored
entries were called absent by every reading in every chunk** -- mostly the
families a solo broadcast cannot reach, exactly as predicted -- and those are
bounds to state on the card, never findings about her.

### 4.6 Portability, the holdout, and what a rate is measured against

**Portability across the parts of a programme is the strongest new idea in the
method** and it attacks the format confound directly. Compute each entry's
rate separately in each context the programme offers -- the opening monologue,
answering a listener's letter, each named corner, the written essay, the close.
**An entry whose rate holds across all of them is portable and may found a
claim about her off air. One whose rate depends on the context is situated and
may not, however frequent it is.** A format's contamination shows up precisely
as a rate that changes with the format.

This needs a context label per span, which attribution does not produce: it
carries speaker labels and no context label. A letter's answer derives in code
as her span following a letter's span; corners and the essay need a labelling
pass, one call per episode, verified by code against the attribution's span
boundaries. **That labelling is also the segment list the coded pass chunks
by**, so it pays for itself twice.

The pilot's evidence, on three episodes: instances landed 256 in the opening
monologue and the free talk after a song, 148 in ordinary letter answers, 81
in one corner, 71 in another, 39 in the written essay, 4 in the close. Three of
the sixteen usable entries are **situated rather than portable**, and the split
falls exactly where the format does: answering truthfully from inside a played
role appears only in one corner, 6 of 6; rereading a childhood thing with
adult eyes only in the essay, 4 of 4; thinking a choice through aloud before
landing it mostly in one corner, 6 of 8. A rate for any of those is a rate for
that corner and not for her.

**The holdout.** Fit on the first block of episodes and test on the last. Every
entry's prevalence predicts a held-out count with a binomial interval. **An
entry that fails is not deleted; it is demoted to a period fact**, because the
usual cause is the programme changing its corners rather than the woman
changing. On the second subject, 21 of 33 testable mechanisms held and 12
moved, 8 down and 4 up, and **they moved as a set**: what fell away was the
correspondence material, what rose was the frame and the direct answer. That
is a programme changing its corners. The sheet already marked 16 of 77 as the
format rather than her; on that evidence at least 12 more of its prevalence
numbers describe a format era. **Prevalence is not a trait**, and the state is
dated, never timeless: anything that drifts gets a per-block value.

**What a holdout on the third subject will be measured against** is fixed now.
Sixteen entries reach 0.67 on both the within-model figure and the figure
against the anchor, and only those are offered, because an entry only its own
model agrees about is not a measurement. The unit is a distinct chunk of tape,
twelve across the three pilot episodes, so an episode read twice is not counted
twice; the interval is Wilson at 95%. **Read the width, not the point**: twelve
chunks put every interval at roughly plus or minus a quarter, six of the
sixteen sit at one or two chunks where the interval reaches from almost
nothing to a third, and the holdout will not be able to say anything at all
about those. The corpus pass is what makes the table worth having; the pilot
gives its shape, not its measurement.

**Two more tests the same code runs.** Specificity, against 200 random entry
sets of matched size and frequency. And the discrimination test against n-gram
counts with no reading at all (§4.4).

**The cross-subject control is the cheapest strong test there is and has never
been run.** One coded pass of one subject's codebook over the other subject's
corpus, about sixty cents. **An entry that fires at the same rate on another
woman on another programme in the same language is measuring the genre, the
format or the language, not her.**

### 4.7 The two figures a procedure owes

**The loss ledger, against the free pass.** The free-pass observations, and in
particular the mechanisms a careful reading judged true, are the record of
what a reader with **no** codebook found. Every one of those true mechanisms is
mapped to the entry that covers it, or written into the ledger with a reason:
no entry, entry too coarse (two functions lumped), entry too fine, or below the
reliability gate and deleted. The ledger has a number: **the share of
review-verified true mechanisms the codebook can express.** The recommendation
is that a codebook is not frozen as a full version below 90% on that number,
and that a lost mechanism with two or more occasions across the corpus is a
candidate entry for the next version rather than an accepted loss. The ledger
runs the other way too: entries that fire where the free pass found nothing are
either a gain (the free pass misses repeats, which it does) or a false entry,
and the judgement pass says which.

What is built today is the ledger against the **inventories**, not yet against
the free pass over the corpus (§2.4 has the numbers). The corpus-side ledger is
computed on the pilot's episodes first and on all of them after the corpus
pass.

**The data-hunger curve, so the procedure states what a given amount of tape
buys.** Run the coded pass on nested subsets -- three, six, twelve,
twenty-four and all episodes. For each subset: which entries reach the
reliability gate, which rates have an interval narrower than half their value,
and how the card's bounds statement changes. Compute only, because the codings
already exist after the corpus pass. **The product is one table that says, for
a future subject with a given number of hours of subtitles, which parts of the
card are measured, which are thin and which are absent.** That table is what
makes "procedural with limited data" a claim with a number rather than a hope.

**Where more data can come from, ranked by cost per hour of source.** Cost is
model spend and machine time; the alternative is the owner reading, which is
the one cost this project treats as real.

| channel | what it adds | cost per source hour | what it needs |
|---|---|---|---|
| subtitles only | words, order, cue index | nothing | a subtitle file |
| attribution by model | who is speaking, per cue | about 80k output tokens | the subtitles |
| speaker diarisation | who is speaking, from the audio, with no model reading | machine time only | the audio; replaces or checks attribution where several voices share a scene |
| prosody and laughter | pauses, pitch, pace, a laugh that ends a disclosure | machine time only | the audio; adds evidence to entries, never defines one |
| scene structure from video | shot boundaries, who is on screen, when the scene changes | machine time, one pass | the video; gives the scene list the coded pass chunks by |
| behaviour from frames | posture, gaze, expression, what she does while others talk | about a cent a shot; an episode of 300 shots is a few dollars | the video; the one channel that can replace hand annotation for a visual subject, and the one whose output must be verified like a quote |
| hand annotation | the richest standard there is | the owner's time | not to be expected |

The recommendation: **diarisation and prosody first**, because they cost no
spend and improve the foundation every entry stands on; **behaviour from
frames only where the words are thin and the picture is not**, priced per
episode before it runs, with the same verification discipline as a quote (the
described action must be at the cue it cites, checked by a second reader on a
sample); **hand annotation never assumed.** On the third character, low-
resolution footage of the broadcasts exists and the owner wants it used if it
is cheap enough; low resolution is enough for shot boundaries, who is in the
studio, and when she is reading against when she is talking, and probably not
for expression, so the cheap first use is the free one.

**The physical channel is the one signal the original method prized that the
current one does not ask for.** Two of its six recording bullets were the
character's physical state and the gap between what was said and what the body
or tone showed, and in its worked example that gap carries most of the interior
evidence. A radio corpus has no body, but it does have a voice, and nothing
reads prosody. This is not a fault in the method as run -- the text-only rule
of §1.3 is deliberate and right, because a procedure that needs the body cannot
run on a subtitle file -- but it should be named as an unused channel in the
bounds statement, and a laugh-and-pause pass over her attributed spans is a
cheap first read if the audio is kept.

---

## 5. Operating notes, all of them load-bearing

Everything in this section was learned by losing money or a night's work.
**Read it before running anything that spends.**

### 5.1 Two kinds of worker, and which stage gets which

**An agent worker** is a Claude agent with tools. It opens the cue file
itself, reads it in chunks, writes the attribution, writes the map, runs the
verifier on its own output, fixes its own quotes, and writes a note naming the
garbled stretches it skipped. It takes 10 to 15 minutes and about 110k tokens
an episode on Opus.

**A direct API call** is one chat completion through the extraction client.
Everything the model will ever see is in the message; it has no tools, cannot
look anything up, cannot run the verifier, and cannot correct itself. Code
does all the verification afterwards. It costs about a cent an episode on a
cheap model and runs eight at a time.

| | agent worker | direct API call |
|---|---|---|
| reads the file itself | yes | no: the whole input goes in the message |
| self-verifies and corrects quotes | yes | no: a verifier afterwards, and what fails is dropped |
| attribution and map in one job | yes | no: one job per call |
| cost per episode | ~110k tokens, Opus | ~$0.01, a cheap model |
| wall clock per episode | 10-15 min | ~13 min, but eight in parallel |
| dies on | the session's usage limit, losing the file in flight | the host's output cap or wall clock, recoverable (§5.3) |
| provenance | the transcript, which must be kept | the call ledger, written by the client |
| best at | recall on the free discovery pass; reading, consolidation, judgement | attribution, the coded pass, anything run many times |

**Rules for agent workers, each paid for.** Three or four at once, never more:
the usage limit killed workers three times in one day on the third subject's
run and each death lost the file it was writing. Give every worker its brief
as a frozen file on disk, its output paths under the subject's own tree, and
the instruction to write a report naming what it read, what it produced and
what its own check said. **Keep the transcripts**: one run's report said its
control reads were Opus and the transcripts showed all three were Sonnet, with
55 of 57 maps also Sonnet, and nothing else records which model read what. Run
agents on Opus; default-model agents died on the limit. **A worker that cannot
make a quote verify must look the cue up again, never delete the quote**: one
worker deleted its failing quotes and reported a clean verify.

**Rules for direct calls.** Never the running character's reply client (§5.2).
Her attributed cues only, numbered, with borrowed prose compressed to one
context line, never the raw transcript. One episode per call with no other
episode in context, so nothing is carried in from a neighbour. Every answer
verified by code before it is data. Every raw answer kept on disk.

**And the concurrency rules from the pilot.** Eight concurrent is the default
for a coded pass and **a run that is serial is wrong, not slow.** A worker on
paid calls reports its concurrency, its call count and its spend after ten
minutes; the orchestrator reads the ledger at ten and at thirty minutes and
messages on the first anomaly: serial calls, a retry counter above two, or two
failures on one chunk. After a worker dies on the session limit, its child
processes are listed by exact command line before anything is resumed; a loop
that has outlived its worker is stale and is stopped by process id. **A call in
flight under a live worker is never killed.**

### 5.2 The client, and why there are two

The reply client at the repository root belongs to the running character. Its
contract is that half a reply is never sent: on a cut it discards what arrived
and asks again from nothing, three times, then gives up and records a missed
call. That is right for a chat turn and wrong for a reading. It killed the
third subject's first extraction attempt at its 600-second request timeout
with 5,910 stream chunks of reasoning in hand and threw all of them away.

**The extraction client exists because of that class of failure. Use it for
every direct call in this guide.** It streams, keeps what arrived, and hands
interrupted reasoning back.

**Provider strings** select a host, and one of them means the cheap model
through the aggregator pinned to a single host with fallbacks off, so the
receipt names that host or the call fails. Keys live outside the documents:
the aggregator key in its own file, the first-party key in the config, the
vision service account under the secrets directory. **None of them goes into a
log, a document or a message.**

**Settings that were measured, not chosen.** Reasoning on at high effort: on
one host without it, 4.7k output tokens and 12 mechanisms; with it, 44k and
16. Temperature 0.2 for extraction, and every logged row carries it. The
official endpoint gets the API maximum sent explicitly because it applies a
low default when the field is absent; a pinned aggregator host gets its own
published maximum read once from the endpoints table, and then the number is
not trusted (§5.3). A rate-limit answer waits 30, 60 and 90 seconds and does
**not** spend a retry, because one host answered with a rate limit on half of
one stage's calls and another thirty times in a row.

**Where the money goes.** On a one-call read, 30,770 of 33,948 completion
tokens were reasoning: 91% of the spend bought thinking and the 19,717-token
prompt was nearly free. The prompt prefix is cached by the host, so **put the
stable text first (the brief, the codebook) and the episode last.**

**Also true of the model choice.** The host is a parameter and the model is
often not: every pipeline tool on the earlier run called with no model named
and the provider branch filled in one default slug, so changing the provider
changed which host served one model rather than which model ran. Reasoning
effort is set for the caller and is not chosen per call. Temperature is fixed
and there is no seed, so no configuration can be repeated exactly, which is
why that run has no reproducibility figure at all. **Do not believe a docstring
that says the model is chosen by an environment variable**; for a new subject
this is half a day of edits, not a redesign.

**What each stage asks of a model**, from the evidence: attribution needs a
whole session in context, strict JSON and an index constraint held over
hundreds of spans, and reasoning buys little there; the free map needs long
context and reasoning depth and shows **the widest spread in the pipeline**;
the reduce needs a large output cap and JSON that parses over 300-entry
chunks, where truncation rather than quality is the usual failure; auditing
and decomposition need cheapness at volume and nothing current struggles.
Writing the character is a different job from extracting her and is benched
separately.

### 5.3 How a long call dies, and how it is recovered

**Three deaths, measured:**

| what happens | how it reads | what fixes it |
|---|---|---|
| truncated at exactly the host's output ceiling | a length finish | continuation |
| runs past the aggregator's request wall at about 1,800 seconds | an error finish with usage present | nothing: a smaller ask |
| thinks for the whole generation and never begins the answer | an error finish or a timeout, zero characters of content, a long reasoning trace | hand the thinking back |

**The advertised maximum is not a promise; sending it changes nothing about
where the host stops.** No output-cap value prevents any of the three. The only
real lever is keeping the expected output well under the ceiling, which is what
a chunk size is for.

**Unstreamed, every one of these costs the whole call**: the body comes back
empty, and ten minutes and 131k tokens buy nothing. That happened eight times
in one night. So the client streams every request and assembles the answer from
the deltas, and what arrived before the cut is in hand.

**The recoveries.** On a length finish or a dead stream, the client hands the
model its own partial answer back as an assistant turn with an instruction to
carry on from exactly where it stopped -- no repetition, no fence, no
commentary -- up to four instalments. When the model thought and never spoke, it
hands back the last 24,000 characters of the reasoning with an instruction to
stop thinking and write the answer now from what it had already worked out.
The incident that produced it: 437,833 characters of reasoning and no content,
three times on one chunk. Only whole JSON objects are kept out of the joined
instalments, stitched before scanning because a continuation begins mid-string
and inverts quote parity if a piece is read alone; the fence and the
"Continuing:" line a model writes anyway are stripped; and a list cut
mid-object is salvaged object by object, because 90 whole clusters out of 110
beats none.

**Timeouts.** The short call defaults to 600 seconds and the long one to 1,200,
because a healthy reduce call has run 592 seconds and **the client must never
be what cuts an answer.** A read timeout does not trip while bytes are
arriving, so a runaway is bounded by the host's wall rather than the client's.
A too-short timeout is expensive twice: it discards a full reasoning trace and
then the retry loop buys another.

**The retry rule the pilot leaves, and it is binding.** A think-only death is
handled **inside** the retry loop: the first is handed back with the answer-now
instruction, the second **halves the chunk at the nearest segment boundary**,
and a chunk is never asked whole a third time. The client's own retry count for
a coding call is two. The pilot's single most expensive fault was a halving
placed downstream of the client's retry loop, so a chunk that kept thinking
reached a fifth whole re-ask before the halving could see it, and the five most
expensive chunks were all one chunk re-asked whole.

**Prove the recovery without spending a call.** A test fakes a host that cuts
mid-object and a host that streams reasoning only and then dies, and asserts
that the second request carried the right four turns, that the nudge went in,
that the severed object comes back whole, and that no fence, prose, nudge or
reasoning reaches the data. Run it whenever streaming, salvage, continuation or
the scrub changes. It found two real faults before the first paid call.

### 5.4 Probe a host before a stage trusts it

**A cap probe** forces one long generation and reads the finish: a length
finish at some number is a hard ceiling there; a stop finish means the ceiling
is above it; an error with no content means the host aborts rather than
truncates.

**A concurrency probe** fires several calls at once and checks the answers are
right and attached to the right request. One host was clean at 32 concurrent;
another refused at six because of a limit on a pool shared across the
aggregator's users that spending cannot raise, and was dropped.

The host ranking's mid-field order is inside the method's own variance and is
not a result (§4.4).

### 5.5 Chunking: one call per episode, or the episode in pieces

Neither earlier run chunked an episode. Attribution, the free map and the coded
reads were all one call per episode; the agent workers read the file in pieces
but wrote one map; only the reduce is chunked, and that chunks the list of
observations rather than episodes.

**What chunking buys.** It bounds what one call can spend and lose: the
reasoning runaway is not proportional to input (39k to 131k thinking tokens
over a 6k-token episode), but a smaller ask shortens the leash and a lost call
loses a quarter of an episode rather than all of it. And **it fixes
attention**: every reader front-loads a whole episode. Cited cues by quarter on
one episode were 15 / 19 / 6 / 6 for one model and 23 / 12 / 9 / 11 for
another, and the brief has to say in words that the second half is where the
personal material is. A chunk gets the whole of the reader's attention.

**What it costs.** A mechanism is a repeated conditional pattern and a chunk
reader cannot see the repeat: "many instances" is an episode-level fact, a
trigger often sits in one corner with its response in the next, and a register
block is counts over the whole episode and is meaningless per chunk. Chunk the
free discovery pass and every within-episode recurrence becomes two singleton
observations for the reduce to reunite, which is the reduce's weakest
operation.

**So, by pass:**

| pass | unit | why |
|---|---|---|
| attribution | whole episode | a span boundary is exactly what a chunk edge destroys |
| free discovery | whole episode, plus one chunked pass if money allows | the whole read sees recurrence; the chunked read sees the second half; the union is a cent |
| register counts | whole episode | counts are per episode by definition |
| the coded pass | **chunks, cut at the episode's own segments** | classification is local: an entry is present in this span or absent; forced absence per chunk, joined afterwards; and the segments are the per-context split that portability needs anyway |
| facts and moments | chunks | both are local by nature |
| the reduce | chunks of 300 observations | measured: 200 gave 122 clusters with 79 singletons, 400 put three of five calls into the output ceiling |

**Chunk by segment, never by token count.** The episode already has a structure
the attribution exposes -- the opening monologue, each letter and its answer,
each corner, the essay, the close. Cutting there keeps a trigger with its
response and gives the per-context rates for free; cutting every N cues puts
the edge inside an answer.

**Ask for the same schema per chunk and join in code.** A chunk's answer carries
the chunk's cue range, joining is a concatenation with the cue indices already
global, and the verifier does not know or care that the episode was read in
pieces. **Nothing may be merged by a model at this step.**

### 5.6 The brief

Frozen to disk before the run, identical for every episode, and kept. The parts
that earn their keep:

- One paragraph naming the subject and the programme, and nothing else about
  her from outside the text. Nothing from anywhere else may enter, and nothing
  from an earlier episode may be cited in a later one.
- What a listener's letter looks like and that it is not hers, even when the
  input is her cues only, because the boundary bleeds.
- **A floor and no ceiling**: "if you have found three, you have stopped
  early". A named range is returned as that range; deleting the anchor outright
  with no coverage rule in its place cost recall 13 to 7.
- Judge by function, not topic; split rather than lump; the corners are
  scaffolding and what she does inside a corner is the finding.
- **For a coded pass: the sampling rule and the played-role rule.** Whether an
  entry is recorded once at its clearest occurrence or once per chunk, said in
  the protocol rather than in an entry; and that a span the attribution marks
  as a played role is coded under the format and never under the person. The
  pilot's two most expensive omissions were these.
- The exact output schema, and "nothing outside it".
- Write UTF-8; a worker whose file tool refuses a path uses a shell heredoc
  with a quoted delimiter.
- Return counts and the verified share in under 25 lines.

### 5.7 JSON, raw answers, receipts

**An answer that does not parse is asked again**, two retries, and the raw text
is never handed on as data. **Every raw answer is written to disk before
parsing**, so a failure is read rather than guessed at, and so every map can be
rebuilt from the raw answers with a changed verifier at no cost. Every call
appends one row to the call ledger: provider, model, the host that served,
tokens in and out, seconds, finish, temperature, the pin, and the error if any.
**That file is the provenance for every number in a run**, and it is the file
the orchestrator reads at ten and thirty minutes.

**Verification rules, the same in every stage.** A quote must appear character
for character in the cue it cites, whitespace ignored; a neighbouring cue is
allowed and the index is corrected; what fails is dropped and a mechanism with
no surviving evidence is dropped. **The offered-to-verified ratio is stored per
episode and it is the invention measure.** The cue index is the index in the
first column, never a line number. A repair flag is for the orchestrator after
reading, never for a worker. **A cited cue is checked against the attribution**:
a mechanism evidenced from a listener's letter is a citation error and is
dropped. Garbled stretches -- runs of ten or so cues in another script or over
music -- are named in the episode's note so a later pass knows the hole was
seen.

The one body of material in this project that skipped quote verification has
33% of its quoted strings verbatim in the subject's words and 64% not in the
session at all: not fabrications, but its own analytical labels inside
quotation marks and paraphrases of real lines, which is ordinary usage and
mechanically indistinguishable from quotation. Everything taken from it had to
be re-verified.

### 5.8 Repository hygiene

- **Never open a live save.** The running characters' database files belong to
  them. A probe reads a copy, or the file read-only through a read-only URI,
  never the live path. Extraction never touches them.
- **Everything a subject produces lives under that subject's own tree** -- the
  corpus, the attribution, the maps, the raw answers, the reports. Documents
  live in the flat documents directory, one file per subject, indexed in its
  README. A dated note goes to the log, newest first, naming its reference
  section; the running state to the handover header; **nothing dated into a
  reference document.**
- **Superseded files go to a timestamped retired directory**, never deleted,
  and a patch script goes there too once it has run.
- **Patch scripts, not hand edits, for anything over a line**, written with a
  file tool rather than a shell heredoc, because heredocs mangle backslash
  sequences and choke on quotes and Japanese. **Every script is idempotent**:
  anchor on a whole unique line, assert the anchor occurs exactly once, assert
  the new text is not already present, refuse otherwise. **A script whose new
  text still contains its anchor doubles on every re-run**, and a
  non-idempotent script re-run after a partial failure has doubled its inserts
  four times in this project.
- **Windows.** Set the output encoding to UTF-8 before printing Japanese, or a
  console default turns quotes into replacement characters. Paths with
  backslashes go in raw strings or forward slashes.
- **A process started as a child of a tool's shell dies silently minutes
  later.** Long jobs run in the background with their output to a file, and
  **the wait is announced first**: what is running, roughly how long, what it
  costs.
- **Never kill by image name.** A filter over running processes once killed a
  another program. Find a process by its exact command
  line.
- **Run the build check before any restart of anything that runs**, and its
  documents check will name a document that refers to a file that does not
  exist, so a guide naming a tool still to be written says so in words.
- No version control. Retired copies and idempotent scripts are the version
  control.

### 5.9 Every failure already paid for

| failure | where | the rule it produced |
|---|---|---|
| the reply client discarded a cut answer and rebought the reasoning | third subject | §5.2: the extraction client, never the reply client |
| unstreamed calls returned no content eight times in a night | second subject, the reduce | §5.3: stream everything |
| the same model at a different reasoning setting agreed with itself no better than with another model | the host ranking | §4.4: the mid-field order is noise; measure the floor first |
| a brief naming a range got that range back from every model | third subject | §5.6: a floor, no ceiling |
| a worker deleted quotes that failed to verify | one worker, one episode | §5.1: look the cue up again, never delete |
| a report misnamed which model read what | third subject | §5.1: keep transcripts and read them back |
| the reduce placed about 10% of members in the wrong cluster with every quote real | second subject | §3.2: the reduce is a draft; the purity statistic; hand consolidation |
| 12 of 33 mechanisms drifted between blocks as a set | second subject holdout | §4.6: demote to a period fact, do not delete |
| 16 of 77 mechanisms were the programme, not her | second subject judgement | §3.2: class every instance |
| a letter's last line bled into her span | attribution | §3.2: spot-read boundaries; the cost is 0.013 of separation |
| a cue index off by one put a corpus's only flat anger at the wrong cue | third subject | §5.7: verify indices, correct against the cue |
| half of a host's calls came back rate-limited | one host | §5.2: waits, not attempts |
| a shared pool limit could not be bought past | one host | §5.4: probe concurrency before a stage |
| the read description lost to n-gram counting as a discriminator | second subject | §4.4: measure against counting or claim nothing |
| a cleaning step let a dedup collapse two cues and shifted every index after it | second subject, 27 sessions | §3.2: collapse duplicates on the raw text; refuse if a session's cue count does not equal what its attribution covers |
| a low output cap failed silently, stopping calls at a fraction of the endpoint's maximum | several hosts | §5.3: treat a length finish anywhere as a fault to read |
| a defensible reading became, one summary later, a line the subject never says | second subject | **summary-of-summaries**: the extraction was disciplined and the invention entered at the summarising step; every reduction of a reduction needs its receipts to survive the step |
| markers noticed while reading a session that later fell in the test block | second subject drift | drop every marker derived from a held-out session; two of five apparent drifts were selection on the test set arriving as a finding |
| a coded pass ran serially for two hours, and a halving sat downstream of the client's retry loop | the pilot | §5.1 and §5.3: eight concurrent, and halve inside the retry loop on the second think-only death |
| a worker killed by the session limit left orphaned retry loops spending money | the pilot | §5.1: list child processes by exact command line and stop stale loops by process id |

---

## 6. The procedure: from material in hand to a character who runs

This is the order of work for a **fresh subject**, from the moment there is
material on disk to the moment a character built from it is running under the
register. It is the same procedure for every source kind; §7 says which steps
change and which are skipped for each. The running state of the subjects
already extracted is not here -- it is in `HANDOVER.md`, because it is dated.

**How to read the table.** *Who* is one of three things and the distinction
decides the cost: **code** is a script over files on disk and costs nothing but
machine time; **a call** is a model asked one question with everything it needs
in the message; **reading** is a long-context session or a person going through
the material, and it is the expensive column. **The check** is what proves the
step was done rather than claimed -- run it before the next step, because every
later number inherits this one.

| # | step | in → out | who | cost | the check that proves it |
|---|---|---|---|---|---|
| 1 | **the intake note**: what the material is, how much of it there is, what channels exist, which variant of §7 this run is | the files as delivered → one page under the subject's own tree | reading | an hour | the note names a file count, an hour count and a per-file naming pattern; a stage later disagreeing with it is a fault in the note, not in the stage |
| 2 | **corpus**: subtitle or script files into cues with an inventory | `<subject>/srts/` → one cue file per session, plus the manifest | code | nothing | the session count, the numbers missing in range, and that no number is duplicated; the cue count is **identical before and after cleaning** (§5.9: a dedup on cleaned text shifted every index in 27 sessions) |
| 3 | **the index and the era blocks**: every session with its date, cue count and length; the gaps in the cadence and the eras they imply | the manifest → a readable index | code | nothing | the gaps in the index match the gaps in the file numbering, and each era block names the two dates that bound it |
| 4 | **attribution**: who produced each cue | cues → one span file per session, every cue covered exactly once in order | one call per session on untagged material; **a parse** on speaker-tagged material (§7) | ~80k output tokens a session, nearly all reasoning: the most expensive stage of an untagged run, and free on a tagged one | code asserts full ordered coverage and re-asks garbage; then **two independent readers attribute the same three sessions** and the cue agreement is reported (95.6 to 98.4% on the third subject); then a boundary spot-read of two sessions, because a letter's closing line bleeds |
| 4a | **label the not-her spans by speaker in at least five sessions** | the span files → the same files with the others separated | one call per session | five calls | the share of the not-her material that is one sex, one role or one voice; without it every later separation figure is partly telling a woman from men (§3.2) |
| 5 | **the reading views**: one plain file per session, cue index, clock time, her words plain and everything else marked | cues plus spans → one text file per session | code | nothing | a view opened at random shows the same cue index the span file names |
| 6 | **the surface battery**: counts of her own forms per session and per year, and **the same battery over everybody else in the same room** | the views plus a battery file → counts, hers and theirs | code | nothing | totals are read **with dispersion beside them**, never alone; a marker whose expected count is under about three is reported as not testable rather than as absent (§8, and `docs/verification.md` fallacy 1) |
| 7 | **the bounding measures and the negative space**: how much of her speech is reply rather than initiation; which relationship types have no data; how many distinct emotional pressures appear | everything so far → the bounds file | code | nothing | every family of §2.4 resolves to evidenced, thin or **absent**, with no fourth state and no "done"; the absent list is what the card's no-data block is written from |
| 8 | **the reading control**, written **before** any extraction brief is accepted | six sessions end to end → findings, each with a cue receipt | reading, transcript kept | a day | every finding carries a session and cue that resolve; and the pass is named for what it is -- **a long-context model reading is not a human ceiling** (§3.2) |
| 9 | **free discovery**, three runs: register, mechanisms, moments, stated facts | her attributed cues, numbered, one session per call → one map per session per run | one call per session per run | ~$1.75 for 57 sessions on a cheap model | code verifies every quote character for character against the cue cited, corrects a one-off index, drops what fails; **the verified-over-offered ratio is stored per session and it is the invention measure** (98 to 100% on every competent model); and the run-to-run agreement on cited cues is reported |
| 10 | **the recall figure**: the discovery brief scored against the control of step 8 | the maps plus the control → one percentage per session | reading | half a day | the brief is accepted or rewritten on this number and not on the count of mechanisms it produced (§5.6: a floor and no ceiling) |
| 11 | **reduce by function**: cluster in chunks of 300 observations, merge in rounds of at most 120 a call, one synthesis per final cluster | the maps → a draft cluster set | many calls, code owns every number | ~$1 | entry conservation (nothing dropped, nothing invented) asserted by code, then the **purity statistic per cluster** -- 0.33 and 0.40 on the two lumped clusters of the second subject's run against 0.80 and 0.74 on two good ones. **The output is a draft. Do not report the cluster count as a result** |
| 12 | **consolidation into a frozen codebook version** | the draft plus the shared book → entries with the full schema of §2.1, frozen | reading | **two to three days, and it decides everything after it** | the codebook check passes; every entry has a suppressor, occasions, three differing surface forms, an exclusion naming a real neighbour, and a version; nothing was added during a coding run (§2.6) |
| 13 | **context labels**: what part of the programme each span belongs to | the span files → one context row per span, derived where it can be and read where it cannot | one call per session, verified against the span boundaries | ~$0.60 | every span has exactly one context; **and this is also the segment list the coded pass chunks at**, so a chunk boundary never falls inside an answer (§5.5) |
| 14 | **the reliability pilot and the gate** | three sessions, the frozen book → alpha per entry, two units, plus span overlap | a panel of **at least two model families**, plus an anchor read | measured at $2.12 for four of nine codings on one family (§4.5) | median **cross-family** alpha at or above 0.67 with at least 60% of entries above it. Below it: rewrite the failing entries' exclusions and near misses, at most twice, then the answer for this corpus is no. **A within-family figure is an upper bound and may not be substituted** (§4.3) |
| 15 | **the coded pass over the corpus**: one row per entry per chunk, present with spans or explicitly absent, plus trigger-present-code-absent rows | the corpus, the frozen book, the segment list → codings | model calls, **eight concurrent**, five codings from two or more families | budget $3 and treat it as a floor | the ledger read at ten and at thirty minutes; a serial run is wrong, not slow; a think-only death handled inside the retry loop and the chunk halved on the second, never asked whole a third time (§5.3) |
| 16 | **holdout, specificity, the counting baseline, the cross-subject control** | the codings → a rate with an interval per entry, per context | code, plus one cheap cross-subject pass | ~$0.60 | an entry that fails the holdout is **demoted to a period fact, not deleted**; an entry that fires at the same rate on another subject in the same language is measuring the genre and is dropped; and **the card is measured against n-gram counting or it has established nothing** (§4.4) |
| 17 | **judgement**: every surviving entry read with its evidence in context and classed hers, the format's, or a single moment | the codings plus the tape → a class on every instance | reading | a day | the class is a field, not a footnote; a span the attribution marks as a played role is coded under the format and never under the person (§4.5) |
| 18 | **portability**: each entry's rate in each context separately | the codings plus the context rows → portable or situated per entry | code | nothing | **only a portable entry may found a claim about her off air**, however frequent a situated one is (§4.6) |
| 19 | **facts into records, and moments**: the stated facts grouped by fact with their receipts; the moments kept with their counts | the maps → records, and the moments file | code plus reading | a day | every receipt re-found in the cue it names and its attribution label checked; the importance grade written down so it can be argued (**in if it changes what she would say next**); a record stated in two or more sessions marked as such |
| 20 | **the trigger table and the baselines** | the surviving portable entries → trigger, response, rate with interval, suppressor, portability, drift, variation; each baseline naming its measurement | reading | half a day | every row resolves to a cue, an identifier or a stated frame; a suppressor with no trigger-present-code-absent row behind it is marked inference |
| 21 | **the five-factor profile** off the portable entries only, with a confidence and receipts per dimension | the trigger table → the profile | a few calls, a morning of reading | cents | the confidence on the confounded dimensions says so in words: apparent outgoingness is confounded by a solo format where being outgoing is the job |
| 22 | **the speculative readings**: one independent reading per session under a stated frame, asked about the person behind the performance | the sessions → one section per session under a fixed category set | one call per session | ~$1 to a few dollars by model | every session has a section; the file splits on its own headers; the category set is the brief and is kept beside the output (§3.2 step one) |
| 23 | **the convergence pass**: name the frame, count the sessions, drop what an evidenced entry contradicts, score the held-out block | the readings plus the codings → the inferred and speculated rows | reading, with the counting in code | a day | **the count of rows with no frame is zero**; the net is in the source rather than in the prose; every row carries confirmed, revised or contradicted, and a row with no held-out result says `holdout: none` (§3.2 steps two to five) |
| 24 | **the card**: a handful of drivers, the trigger table, the baselines, the records, the moments with counts, the profile, the tier on every row, and the bounds as an explicit no-data block | everything above → the card | a writer, plus the shape check | cents | **every sentence resolves to a cue, an identifier or a stated frame, and one that resolves to none of those is deleted**; the bounds block ends with one line per gap naming the source that could close it |
| 25 | **the speech guide, and its sort file beside it** | the card plus the surface battery → the guide, plus the sort | reading | half a day | every rule carries its class (hers / the format's / a single moment) and its tier; **no format-class rule governs private writing**; the counts in the sort match the counts in the guide (§10.1) |
| 26 | **the bible's off-tape section** | the convergence pass → one section, every line marked record or reading | reading | half a day | every line carries its mark and its receipt or its count; the section closes with what was dropped and why (§10.2) |
| 27 | **the seed self-beliefs file** | the convergence pass → one row per belief with confidence, investment, tier and receipt | reading, then code to apply | half a day | the confidence follows the stated rule from the count and the held-out verdict; the apply script merges, never lowers a confidence she holds, is idempotent, refuses to write behind a live process, and copies through the backup API first (§10.3) |
| 28 | **the type, derived last** | the surviving entries and the inferred rows → four letters, a confidence and receipts per axis, contradictions kept | reading | half a day | the axes settle without ignoring half the entries; **a type that will not settle means the pattern is not coherent yet and the entries need another pass** (§3.6); and the vocabulary appears in nothing a call reads |
| 29 | **compose her and verify her** | the card → a bundle, a config, a prompt directory, a save, a register row | code | nothing | §11, step by step, with the smoke check named against each |
| 30 | **a day run, read against a control** | the composed character → a day of her own record | the day harness | ~$1 | read against the frozen baseline of whatever method she is being compared with; **if the coded card is not ahead, that is the finding** and the reliability, portability, holdout and cross-subject numbers are still worth having |
| 31 | **live, and the audit on day two** | the running character → her own words | reading | half a day | the one material in the whole procedure produced under the conditions the card is for; a construct claim her own output contradicts is wrong about her whatever the tape said (§4.1) |
| 32 | **the two figures the procedure owes**: the loss ledger against the free pass, and the data-hunger curve on nested subsets | the codings → two tables | code | nothing | the ledger's number is the share of review-verified true mechanisms the book can express, and a version is not frozen below 90%; the curve says, for a given number of hours, which parts of a card are measured, thin or absent (§4.7) |

**Where the money and the reading actually go.** Compute for the whole of the
above was estimated under fifteen dollars and the pilot says treat that as a
floor for the coded stages. Reading is about two weeks, and **three days of it
is step 12**. Steps 8, 12, 17, 19, 23 and 25 are the ones that cannot be
automated and the ones that decide whether anything else means anything.

**What may be run out of order, and what may not.** Steps 1 to 7 have no
dependency on each other beyond the corpus and can run in a day. Step 8 must
precede step 10 and is worthless after it. Steps 12 and 14 gate everything
numeric: **no rate quoted before the gate is a measurement.** Step 22 can be
commissioned at any point after step 2 and is best commissioned early, because
it is one call per session and the wall clock is the only cost that matters.
Step 28 is last on purpose (§3.6).

---

## 7. Intake: the source kinds, and what changes per stage

§1.4 lists what holds for every source. This is the other half: what each kind
of material is, what it adds, what degrades without it, and which of §6's steps
change. **A reader with a fifth kind of source should be able to write its
column from §1.4 and this table.**

### 7.1 What each kind of material is, and what it buys

| kind | what it is | what it adds that nothing else does | what degrades without it |
|---|---|---|---|
| **untagged broadcast subtitles** | one file per session, cues with timestamps, no speaker labels; a recogniser's output with its own errors | volume, and a real rate: fifty-five hours of one person talking is enough for a prevalence with an interval and a per-context cut | nothing at all: this is the floor the whole method is written to run on |
| **speaker-tagged subtitles or scripts** | the same, with the speaker on the line | attribution for free, and with it the removal of the one error every later figure inherits; and the *other* speakers as a measurable comparison group rather than one mixed label | the most expensive stage of the run has to be bought as a model call, and 95.6 to 98.4% agreement is the ceiling rather than certainty |
| **scenes: a fictional canon with a picture** | speaker-tagged dialogue plus what is on screen | what she does while somebody else talks, where she puts herself in a room, and the gap between what she says and what her face does -- the physical channel the original method prized (§4.7) | the whole body family is undefined rather than unobserved, and the gap between word and body is unavailable, which in a scripted source is where much of the interior evidence sits |
| **secondary text**: an encyclopaedia article, a wiki, a compendium, an interview digest | prose about the subject written by somebody else | a frame: what segments exist, who is related to whom, what order things happened in, and a date to check a claim against | a reader spends a day working out the programme's structure from the inside, and mistakes a running joke for a one-off |
| **a summary of many sessions** (one reduction, not one file per session) | somebody's or some model's digest of the whole run | speed, and nothing else | **it cannot be split, so there is no held-out block and no convergence count**, and the invention that entered at the summarising step is invisible (§5.9: a defensible reading became, one summary later, a line the subject never says) |
| **audio beside the subtitles** | the recording the transcript came from | diarisation, which checks attribution for free; prosody, pauses and a laugh that ends a disclosure, as evidence added to entries defined on words | the two cheapest quality improvements available are not taken; a marker family that is really about delivery is scored as if it were about wording |
| **hand annotation** | somebody's own coded reading of the material | the richest standard there is, and the anchor a fictional canon's prediction test is scored against | nothing that the method assumes: **hand annotation is never assumed** (§1.3) |

**The one rule that decides all of it.** A channel that exists **may add
evidence to a code and may add its own codes in a separate, marked section; it
may never define a code**, because the next subject may not have it (§1.3). So
the codebook is the same book on every kind of source, and what changes is
which entries can be reached and how wide their intervals are.

### 7.2 The four variants, stage by stage

Read down the column for the run in hand. **"as written"** means §6's step is
unchanged; a named change is the whole of the difference.

| §6 step | A. untagged broadcast subtitles | B. speaker-tagged subtitles or scripts | C. a fictional canon with scenes | D. a mixed corpus |
|---|---|---|---|---|
| 1 intake note | as written | as written, plus the label set and its counts | as written, plus which seasons and which release the scripts came from | as written, plus **one row per source with its own kind**, because every later figure is reported per source before it is pooled |
| 2 corpus | as written; the filename pattern is the first thing to change and it is two lines | as written; keep the speaker column | as written, one file per episode; scene boundaries kept if the source marks them | as written per source, into **separate manifests under one tree**; never one merged cue stream, because a cue index has to resolve to a source |
| 3 index, eras | as written | as written | eras are seasons and arcs rather than dates | as written per source |
| 4 attribution | **the stage**: one call per session, five labels re-argued for this programme | **a parse.** Normalise the label set by hand against the cast list first, and print the label counts: a label with three lines is a typo of a label with three hundred | a parse, as B | a parse where the source is tagged, a call where it is not, and the label carried so a pooled figure can be cut by which route produced it |
| 4a the others by speaker | five calls, and it is the largest structural hole when skipped | free | free | free where tagged |
| 5 reading views | as written | as written, speaker shown | as written, plus the scene marker | as written |
| 6 surface battery | as written; the battery is rebuilt from scratch for every subject | as written, **and the comparison group is real people rather than one mixed label** | as written, and the other characters are the comparison group -- but they are one author's writing, so a difference between two characters is partly a difference between two of one person's registers | per source, and pooled only where the register is the same; a screen line and a chat line do not pool |
| 7 bounds | as written | as written | as written; expect the emotional-pressure count to be lower and the relationship-type count higher than a solo broadcast | as written, and the no-data block names which source could have covered each gap |
| 8 reading control | six sessions | six sessions | six episodes, chosen to include the rare emotional ones a comedy's early episodes lack | six, spread across the sources in proportion |
| 9 free discovery | as written, three runs | as written; **the input is her lines only and the others' compressed to a context line**, exactly as a letter is compressed | as written, plus the stage directions where the source has them | as written per source |
| 11 reduce | as written, chunks of 300 | as written | **often skipped**: under about fifteen sessions the whole map fits one chunk, the merge rounds do nothing, and clustering is a single unreviewable call (§8's degradation order) | as written on the pooled observation list, with the source on every observation |
| 12 consolidation | as written | as written | as written; a scene-channel section is added here, marked, or not at all | as written; an entry anchored in one source only is marked the way a single-subject entry is (§2.3) |
| 13 context labels | the programme's own segments | the same, or the script's scene headings | **scenes, free**: the source's own scene list is the segment list | per source |
| 14 pilot and gate | as written | as written | as written, and cheaper: dialogue is short and the register is plain, so a chunk is small | as written, **and the gate is computed per source as well as pooled**: an entry reliable on one source and not on another is a source-specific entry |
| 15 coded pass | as written | as written | as written, plus the scene channel's own marked section | as written |
| 16 holdout | fit on the first block, test on the last | as written | **the canon is the criterion**: build from the first half, predict the second, and score on scenes the extraction never saw. Hand annotations are the anchor for that test and never an input to it | hold out a whole source where there are three or more, which is the strongest holdout available anywhere in the method |
| 17 judgement | hers / the format's / a moment | as written | hers / **the author's needs** / a moment: a beat that exists because a scene required it is the fictional analogue of a format behaviour, and separating the two is judgement and error-prone | as written, and a class per source |
| 22 the readings | one call per session | as written | as written, per episode | as written, per session, per source |
| 23 convergence | as written | as written | as written, **and the type prior does less work** because the canon covers more situations than a broadcast does | as written; a trait converged in one source only says so |
| 28 the type | as written | as written | as written, and it has the one real check: does the second half of the canon type the same as the first | as written |
| the extra check | none | none | **is the output the card's or the model's memory of a character it already knows** (§3.4): the three-way comparison, run across model families | none |

**What no variant licenses.** Filling a thin source out with the genre's
average, with fan writing, or with a longer behaviour list to make the file look
the size of a rich one. A thin card is a thin card, said honestly through the
tier field, the interval widths and the bounds block (§3.4).

---

## 8. What a given amount of material buys, and what degrades first

The procedure has to be able to say what it can do with less, because the next
subject will bring less (§1.3). This is the order things fail in, measured.

**Surface counting goes first, and it goes by volume rather than by session
count.** A marker is testable only where its expected count clears about three.
Over 152,155 characters of the second subject's held-out speech, 22 of the 35
battery markers cleared that floor and 13 did not. At roughly 5,400 of her
characters a session that is about 29 sessions to test two thirds of a battery
and about ten to test the top handful. *Not testable* means **no information**,
not no problem.

**Dispersion goes next.** A count is read with the number of sessions it appears
in and never as a total, because one session can carry a marker on its own -- 45
instances of one word landed in a single broadcast. **Below about twenty
sessions there is no dispersion to read and every total is a hypothesis.**

**Then the reduce stops paying for itself.** 99 sessions yielded 1,842
observations, about 19 a session, and the reduce chunks at 300. Under about
fifteen sessions the whole map fits in one chunk, the merge rounds do nothing,
and clustering is a single call whose output nobody can check for lumping.
Under that threshold, consolidate by reading and skip step 11.

**Then the reliability gate becomes unreachable rather than failed.** The
pilot's own figures rest on four units per entry, where one disagreement moves
an entry from 1.000 to 0.000, so a single entry's alpha is nearly noise and only
the medians can be read. An entry needs on the order of a dozen chunks before
its own number means anything.

**And the coverage map fills with holes rather than with findings.** That is the
point of it, not a failure. Even at 99 sessions four relationship types had no
observations and one family came out unspecified. Less material does not make
the pattern wrong; it makes more of it honestly empty.

**What does not degrade at all is the fact record.** A biographical fact stated
once is a fact. 51% of the second subject's 152 records rest on a single session
and are not thereby weaker -- they are simply not confirmed by recurrence, which
is the only confirmation available without leaving the corpus.

**The product this section owes is a table, and it is computed rather than
argued**: run the coded pass on nested subsets of three, six, twelve,
twenty-four and all sessions, and report per subset which entries reach the
gate, which rates have an interval narrower than half their value, and how the
bounds block changes. The codings already exist after step 15, so the table
costs machine time only. **That table is what makes "procedural with limited
data" a claim with a number rather than a hope** (§4.7).

**Where more material can come from, ranked by cost per source hour**, is
§4.7's table. The recommendation stands: diarisation and prosody first, because
they cost no spend and improve the foundation every entry stands on; behaviour
from frames only where the words are thin and the picture is not, priced per
episode before it runs and verified like a quote; hand annotation never
assumed.

---

## 9. The mechanics: which tool runs which stage

Two toolsets exist, one per extracted subject, and they were written months
apart for different halves of the method. **Neither is a general pipeline and
this section says which is the base, what has to be lifted into it, and which
lines change for a new subject.** The rule the whole section obeys: a stage may
say *this script must be generalised before a fresh run*, and it may not be
left with no named tool.

### 9.1 Which toolset is the base, and why

**`yukarin/tools/` is the base.** It is the only one with a working tool at
every stage of the discovery half -- corpus, attribution, the map, the reduce,
the bounds, the judgement view, the records -- and it holds the instrument
itself, the extraction client (`yukarin/tools/llmx.py`), which the other toolset
imports across `sys.path` rather than reimplementing. It also holds every tool
that validates the method rather than running it: the cross-provider control,
the host probes, the held-out generation test, and the reference fetch.

**`asumin/tools/` holds the entire second pass and nothing in the base
replaces it.** The coded pass against a frozen codebook, the reliability
statistic, the context labels the coded pass chunks at, the retro-application of
a rule to codings already written, and the tool that recomputes every number a
baseline document quotes -- those exist only there. Its authoring half is data
rather than tooling: seven of its files are Python modules whose whole body is
one woman, which is a good arrangement (re-runnable and diffable) and not a
tool.

**So the first job of a fresh run is a merge, not a choice.** The coded half
must be lifted out of the third subject's tree into whichever tree the new run
uses, because it is the half that makes the numbers mean anything (§2). The
four files to lift are the coded pass, the alpha, the context labels and the
re-verification; they are already written to take their subject-specific parts
as arguments or as two constants, so the lift is a copy and a path change rather
than a rewrite.

### 9.2 The tools, by stage

`<Y>` is `yukarin/`, `<A>` is `asumin/`. **Model** says whether the tool
itself calls a provider.

| §6 step | tool | in → out | model | what is subject-specific |
|---|---|---|---|---|
| 2 corpus | `<Y>/tools/corpus.py` (ported as `<A>/tools/corpus.py`) | subtitle files → one cue file per session, plus the manifest | no | **two regexes**: the session-number pattern and the broadcast-date pattern. The ported copy already accepts two date conventions. Also the manifest's identity strings -- the subject's name and the programme's -- which are prose in `main()` |
| 3 index, eras | `<A>/tools/index.py` | the manifest → a readable index with the era blocks | no | the arithmetic (a gap of three times the median cadence starts a new era) is general; **the file's header prose is one tape's and is false for another** and must be cut |
| 4 attribution | `<Y>/tools/attribute.py` | cues → one span file per session | **yes**, one call each | the five labels are one programme's structure and must be re-argued (§3.2); the prompt file is the only place the subject appears. **The verifier is general** |
| 4 (tagged material) | **no tool exists.** A parse of the speaker column, plus a hand-normalised label set and its counts | the tagged file → the same span-file shape | no | **must be written before a fresh run on speaker-tagged material.** It is small: the output shape is already fixed by what everything downstream reads |
| 4 verification | `<A>/tools/verify_map.py` | a worker's or a call's answer → the same file with failures dropped and indices corrected | no | nothing. The five attribution labels are the only convention assumed. **The most reusable tool in either tree** |
| 5 reading views | `<A>/tools/read_ep.py --write-views` (from `<Y>/tools/read_ep.py`) | cues plus spans → one plain text file per session | no | nothing |
| 6 surface battery | `<A>/tools/fingerprint.py --against` (from `<Y>/tools/fingerprint.py`) | the views plus a battery file → counts, hers and the room's | no | **the battery is the subject and is rebuilt from scratch.** The ported copy improved on the original by moving the battery out of the code into `<A>/sheet/markers.json`, so a new subject writes a file rather than editing a script -- **use the ported arrangement.** What transfers is the shape (first-person forms, sentence endings, hedges, connectives, self-cancellation, address terms) and the rule to count the family and not the spelling |
| 7 bounds | `<Y>/tools/bounds.py` | everything so far → the bounds file | no | three paths, plus the table mapping families to card fields. The three bounding measures and the negative space are general. **There is no counterpart in the other tree, and skipping this stage is what leaves a card with no statement of what it cannot support** |
| 8 reading control | `<A>/tools/read_ep.py` is the instrument; the pass itself has no tool | the views → findings with receipts | no | the findings are the subject's entirely |
| 9 free discovery | `<Y>/tools/extract.py` (`YMAP=v2`) | her attributed cues → one map per session | **yes**, one call each | the prompt's opening paragraph names the person, the programme and the borrowed-prose label; **everything after it is general**, including the floor-and-no-ceiling instruction that earns its keep |
| 9 (agent-run variant) | no script: an agent worker with a frozen brief on disk. The third subject's run was done this way, brief at `<A>/prompts/worker_map_brief.md` | the views → the same map shape | the worker's own calls | the brief names the subject. **This route costs about 110k tokens a session against about a cent, and it is chosen for recall on the discovery pass and for nothing else** (§5.1) |
| 11 reduce | `<Y>/tools/reduce.py`, driven by `<Y>/tools/reduce_run.py`, with `<Y>/tools/reduce_merge.py` for the merge rounds | the maps → a draft cluster set | **yes**, many calls | **two lines**: the output filename is built from the subject's name, and the descriptive blurb names her. The clustering and every count are general -- the tool does not know who the subject is |
| 12 consolidation | `<Y>/tools/judge.py` is the reading instrument (one entry printed with every cited cue in its surrounding tape and who was speaking); the codebook itself is checked by `tools/codebook_check.py` | the draft → the frozen book | no | one path in the reading instrument. **The consolidation is reading and has no tool by design** |
| 13 context labels | `<A>/tools/context_labels.py` | the span files plus a hand-written table per session → one context row per span, each marked derived or read | no | the context vocabulary is a radio programme's; another radio subject needs no change and a non-radio corpus needs the vocabulary rewritten. **The hand-written half is the cost: one table per session** |
| 14, 15 coded pass | `<A>/tools/coded_pass.py` | the cues, the frozen book, the segment list → one coding file per session per coder | **yes**, eight concurrent, with a hard spend cap and a plan mode that calls nothing | **two constants**: the played-role segments of this programme, and the codebook search path. The coder label is the model's name, not the subject's. It imports the client from the other tree, which is what the merge of §9.1 fixes |
| 14 reliability | `<A>/tools/alpha.py` | the codings plus an anchor coding → alpha per entry at two units, plus span overlap | no | **nothing**: every subject-specific thing arrives as an argument. Fewer than two coders returns not-measured rather than a number |
| 14 the rule applied late | `<A>/tools/reverify_roles.py` | codings → the same codings with a rule applied, originals kept beside them, idempotent | no | the file list and the anchor path |
| 14 the document's numbers | `<A>/tools/pilot_numbers.py` | the codings, the anchor, the alpha file and the call ledger → every figure a baseline document quotes | no | one anchor path. **The pattern is the transferable part: nothing in a written baseline is typed by hand** |
| 15 resumption | `<A>/tools/state.py` | the manifest and the output directories → what is done, what is not, and the batch list still to hand out | no | nothing |
| 16 holdout, specificity, counting | `tools/voice_replicate.py` at the repository root produced the second subject's figures | the card plus the corpus → the held-out, specificity and counting-baseline numbers | no | it is written around one subject's sheet. **Must be generalised before a fresh run**, and it is the tool that produces the one number without which a card has established nothing (§4.4) |
| 16 cross-subject control | **no tool exists.** One coded pass of one subject's book over another subject's corpus, about sixty cents | two corpora plus one book → one rate table per subject | yes | **it is `coded_pass.py` pointed at the other corpus and has never been run.** The cheapest strong test in the method |
| 17 judgement | `<Y>/tools/judge.py` (verdicts written by hand, read back with `--report`) | the entries plus the tape → a class and a verdict per entry | no, deliberately -- the by-model version exists as `<Y>/tools/audit.py score` and has never been run | one path |
| 19 records | `<A>/tools/aggregate.py` → `<A>/tools/_author_*.py` (the reading, as data) → `<A>/tools/_author_build.py` → `<A>/tools/records_build.py`; the older single-tool version is `<Y>/tools/persona_build.py` | the maps → the pile → the authored grouping → the records, with every receipt re-found | no | the authored parts **are** the subject. The assembler, the receipt re-finder and the id derivation are general; `records_build.py` has one line, the record-id prefix that keeps one character's records from being confused with another's |
| 19 moments | `<A>/tools/memory_records.py` | the moments pile → records the retrieval can reach, with the drops and their reasons recorded | no | the drop table names specific receipts. The importance-from-kind rule is general |
| 19 retrieval phrases | `<A>/tools/triggers.py`, checked by `<A>/tools/trigger_check.py` | the records → one phrase list per record, then a sweep over the whole tape for a phrase that fires inside a longer word | no | the phrase lists are the subject's. **The checker is general and it is the one to keep**: the older tree has a repair script instead, hardcoded to fifteen specific phrases, which is the worse arrangement |
| 20, 21, 24 the card | no tool. `tools/character_test.py --sheet <file>` checks the shape | the trigger table → the card | no | the card is the subject entirely |
| 22 the readings | **no tool exists.** One call per session under a frozen brief; the third subject's brief and output are `<A>/asumin_data/readme.txt` and `master_qa_output.txt`. `<Y>/tools/qa_mine.py` reads such a file back and marks every quoted string as hers, as somewhere in the corpus, or as absent | the sessions → one section each | yes | the brief names the subject and the programme; the eight categories are general and are stated in §3.2. **A small driver has to be written for a fresh run**, and it is one call per session with no dependency on anything else |
| 23 convergence | **no tool exists as a general one.** The worked instance is `converge.py` in the third subject's report directory: it splits the readings on their own session headers and counts, per trait, the sessions containing at least one key string, in two blocks | the readings plus a net → a count per trait per block | no | **the net is the subject's and belongs in the source.** The splitting and counting are ten lines and should be lifted out |
| 25 the speech guide | no tool; the sort is a document beside the guide (§10.1) | the card plus the battery → the guide and its sort | no | entirely the subject's |
| 28 the type | `tools/compile_type.py` is the written route's compiler; on the extracted route the type is derived by reading. `tools/cast_mechanisms_test.py` is the check that the vocabulary reaches nothing a call reads | the entries → four letters with confidence and receipts per axis | no | nothing; the check is shared |
| 29 compose and verify | `tools/new_character.py compose <key>` then `verify <key>`; `tools/promote_cast.py` for somebody already on a roster | the bundle → her config, prompts, register row, launcher and save | no | nothing: these are the shared tools and they take the character as an argument (§11) |
| 30 a day run | `<A>/harness/day/run_day.py`, with `<A>/tools/check_package.py` to prove the package builds first | the composed character → a day of record | yes | the harness paths and a fixed date |
| any stage | `<Y>/tools/llmx.py`, the extraction client (§5.2); `<Y>/tools/cap_probe.py` and `conc_probe.py` for a host before a stage trusts it; `<Y>/tools/continue_test.py` to prove the recovery without spending a call | -- | the probes do | nothing. **Use this client and never the running character's reply client** |
| validation | `<Y>/tools/control.py` (cross-provider replication against a twice-run reference, which is the noise floor), `<Y>/tools/providers.py` (host ranking against a control extraction), `<Y>/tools/generate_test.py` (situations chosen because the bounds file says there are no observations there), `<Y>/tools/fp_text.py` (generated text against her measured surface and the room's) | -- | control, providers and generate do | the control tool is the most portable in either tree; the generate test is written around one subject's prompts and situations |
| reference text | `<Y>/tools/wiki_ref.py` | one article → a cached copy in its own directory | no, network only | three lines. **The arrangement is the point: the tool that fetches secondary text is barred from writing to the record file** (§3.4) |
| prompt port | `<A>/tools/prompt_survey.py`, and `tools/forge.py survey --sheet <file>` | the shared prompt directory → the count of prompts that name the previous character, carry a schema, or presuppose a relationship | no | nothing. **Both write nothing on purpose** (§11) |

### 9.3 Two things in the base tree that are wrong today

Named here because §5.8's rule is that a document naming a tool that does not
work says so in words.

- **`<Y>/tools/generate_test.py`'s docstring says it reaches no provider and
  the version that did is retired. It does**: the run branch imports the client
  and calls it, reading the persona role's own thinking, effort and temperature
  out of the live config. The docstring is older than the file.
- **`<Y>/tools/triggers.py` and `<Y>/tools/fix_trigger_substrings.py` point at
  files that no longer exist.** Both name a records file and a triggers file
  under the second subject's own tree; the live pair is under her bundle, where
  her config names them. The first fails on the read; **the second would create
  its output and report success, writing a triggers file nothing loads.** The
  third subject's arrangement -- a detector that reports and never rewrites --
  is the one to copy.

---

## 10. The three outputs that need a form

Three files come out of an extraction that are neither the card nor a prompt and
that nothing downstream can reconstruct if they are written freely. Each gets a
form here, with the third subject's as the worked instance.

### 10.1 The style sort: every rule in the speech guide, with its class

**Why it exists.** The speech guide is a prompt and cannot carry its own
apparatus; the sort is where the apparatus lives. Without it nobody downstream
can tell a habit of the person from a fact about the room, and the failure is
not hypothetical: the strongest single line in the third subject's speech guide
was a correct measurement of a fortnightly radio programme written as an
instruction for a private chat (§3.2's worked example).

**Where it goes.** `prompts_<subject>/style_sort.md`, beside the guide, and
**nothing reads it**. It is not a prompt and it says so in its own first
paragraph.

**The form.**

1. A header saying when it was written, that nothing reads it, and what it is
   for.
2. **The three classes defined in behavioural words**: *hers* is a habit of the
   person, measured over her own attributed speech, and it would still be true
   of her writing a note in a kitchen; *the format's* is a fact about the room
   she was speaking in and it stops being true the moment she is not in that
   room; *a single moment* is one evening, kept because it is vivid, and it may
   not be promoted into a standing habit.
3. **The four tiers**, as §2.5 defines them, restated so the file is readable
   on its own.
4. Why the file exists, with the receipt for the diagnosis.
5. **One table per file being sorted**, one row per section, with these
   columns and no others: the section's number and heading, **the class**,
   **the tier**, the receipt or basis (counts, cue identifiers, or the words
   "no writing of hers exists anywhere"), and **what happened to it** -- kept,
   kept and marked thin, split, moved, cut, or rewritten.
6. **A count line after each table**, so the shape of the file is one sentence.
7. A closing section: **what replaced the rules that were moved**, listing what
   is hers that the new rules are built from, each with its own evidence.

**The worked instance** is `prompts_asumin/style_sort.md`: 25 sections of the
speech guide and 12 claim groups of the bible, coming out 17 hers and evidenced,
2 hers but resting on one evening, 1 mixed, 1 with half a receipt in a
listener's span, **1 the format's entirely**, 1 a bounds statement, 1 hers
occasioned by the format, 1 authored.

**The rule the file exists to enforce.** A format-class rule may never govern
private writing. It moves into a section of the speech guide headed as facts
about the room, addressed to her, saying in her own language that the
programme's shape is not hers -- so she still knows what her working life was --
and the rules it was feeding are **rebuilt from what is hers**, not deleted and
not left empty.

### 10.2 The bible's off-tape section

**Why it exists.** The bible is what the tape says. The off-tape section is what
the convergence pass concluded about her when nobody was recording, and it is
the part of the card that answers the situations the material never contained
(§1.2). Kept in a section of its own so a later reader can strip it whole and
regenerate it from a different frame.

**Where it goes.** Inside the bible, as its own section, placed after the
section about who she is and before the section about him -- because it is about
her and it has to be read before anything relational.

**The form**, and it is written in her language like the rest of the bible:

1. **An opening that defines the two marks in her own language**, because she
   reads this file and the marks have to mean something to her. The third
   subject's: 記録 means the words came out of her mouth; 読み means fifty-seven
   separate readings of the tape landed in the same place, and it is not her own
   words. **A reading is held loosely.**
2. **One line per surviving claim**, each carrying its mark and, after it,
   either its cue identifier (for a record) or its convergence count (for a
   reading). No line without one.
3. **No diagnostic labels.** The behaviour under a label is kept and the label
   is not (§2.7).
4. **A closing list headed with what was dropped from this section**, naming
   each dropped class and what killed it: the claim killed by an arithmetic
   count, everything read off a laugh or a pause or a gesture, and everything
   somebody else said about her.
5. **A closing line that states the limit of the count**, in her language. The
   third subject's is 「何度も読まれたことは、正しいことではない。」 -- often read is not
   the same as true.

**The worked instance** is the section 「テープの外のこと」 in
`prompts_asumin/bible.md`: fifteen entries, each marked 記録 or 読み with its cue
or its count, and the dropped list closing it.

**The rule it enforces.** The bible's older instruction was "do not fill an
empty place with a guess", which produced a character who could say nothing
about most of a life. It is replaced by two sentences: **what is unknown is
unknown; and where the tape is silent and she has read her own manner, she knows
that what she has is a reading and not a record.** What is refused is not
inference -- it is a reading wearing a record's face.

### 10.3 The seed self-beliefs file, and the boot path that reads it

**Why it exists.** The convergence pass produces claims about what she believes
about herself, and the running character has a store for exactly that, revisable
by her own days. A belief left in a document is a belief nothing acts on; a
belief written into the store is one her gauges and her stances read.

**Where it goes.** `data/characters/<key>_seed_beliefs.json`, in the same shape
as the file her config names for her self-beliefs
(`characters/<key>/self_beliefs.json`).

**The form.** One row per belief, with: a **stable id** in words rather than a
number, because the id is the merge key and a renumber is invisible; the belief
in her own language; **confidence**; **investment**; **tier**; and **the
receipt** -- a cue identifier for an evidenced row, or the evidenced rows it
joins plus the frame for an inferred one.

**The rule that sets the confidence, written down rather than felt.** It is
§3.2's rubric applied:

| the row | confidence |
|---|---|
| evidenced by her own words and confirmed on the held-out block, count in double figures | 78 to 88 |
| evidenced, confirmed, but single-figure count or one held-out instance | 70 to 78 |
| **inferred** -- two evidenced claims joined, the joining named as an inference | 60 to 75, and the joining is named in the bible too |
| the held-out block's own revision of an earlier trait | 60, because the first reading of it was wrong once already |
| nothing above 88 | none of these is a measurement |

Investment follows what the belief costs her to hold rather than how sure she
is, and the two are separate fields for that reason.

**The boot path, and it is the reason the file is worth writing.** The store's
self-belief rows are seeded from the file the character's config names when a
save is created, and the seeding code adds the runtime fields a document does
not carry -- the state, the moment it was born, what it was before, why it
changed, and how strained it is. So a **fresh** save gets these rows only if
they are also written into the config's own file; a save that already exists
needs them merged in.

**The apply script's five rules, and every one was paid for.** It **merges** --
her existing rows carried through in order, untouched, the new ones appended
after them. It **never lowers a confidence she holds**: an id already in her save
is skipped whole, so whatever her days have done to that row wins. It is
**idempotent**, with a receipt row in the store, so a second run prints what the
first did and writes nothing. It **refuses to write behind a live process**,
reading the save's own lock through the singleton. And it **copies before
writing** -- the existing row to a file beside the script, and the whole save
through sqlite's backup API, never a file copy of an open database.

**The worked instance** is `data/characters/asumin_seed_beliefs.json`: thirteen
rows, eleven evidenced and two inferred, applied to her stopped save on
2026-09-08 after her ten existing rows were verified byte-identical, with a
planted collision proving the skip. **The one flag that is the owner's call** is
whether the rows are also appended to the file her config names, because that
changes what a future fresh save believes.

---

## 11. From a card to a character who runs

The card is not a character. This is the seam, in the order the files are
written, with the check that proves each. Nothing here is specific to an
extracted character: a written one takes the same path from step 3.

**Before anything: the five answers her sheet has to give.** `embodied`,
`in_world`, `sees_him`, `has_account`, and `with_him` -- and each one decided
from her own material with the reason written on the sheet beside it, because
`Config.REQUIRES` maps every switchable section to the property it needs and
the historical default for an undecided subsystem has been "runs for
everybody". Two more follow: `world_owner`, and `sees_him` lacking when
`with_him` answers `none`.

| # | what | the file | who writes it | the check |
|---|---|---|---|---|
| 1 | **her bundle**: one directory holding everything that is this person and nothing that is not | `characters/<key>/` -- `sheet.json`, `bundle.json`, and the files her config will name (her records, her beliefs, her memories, her triggers, her voice rules, her own circle, her timeline) | reading, from the card; `tools/promote_cast.py` writes it for somebody already on a roster | smoke: every registered character has a bundle and it agrees with her row |
| 2 | **her sheet's existence block and her type** | `characters/<key>/sheet.json`, keys `existence` and `type` | reading | `tools/existence_matrix.py` builds and renders every combination the sheet can declare; smoke builds **every kind of character the sheet can declare** on a scratch save |
| 3 | **her prompt directory** | `characters/<key>/prompts/` -- her bible and her speech guide at minimum | reading. **This is the step that is not substitution** | smoke: every role of every character renders with no unfilled token; and no role prompt of hers carries another character's life |
| 3a | **the prompts that presuppose a relationship, rewritten rather than substituted** | the shared prompt directory's own files, and any of them she overrides in her bundle | reading, and it is the largest single piece of work in this list | the survey counts them before the work starts: of 65 shared prompts, 41 name the previous character, 37 carry an output schema that must survive, and **20 presuppose a relationship or the previous character's life**. A file with names and no presuppositions is a substitution; those 20 are rewrites, and they are rewrites for any second character. **What is character-bearing in a prompt is the psychology written into the mechanism, not the proper nouns** -- "being with one person calms her, being watched by another does not" -- and substituting names into that yields a different person with the first one's social world |
| 4 | **her config** | her config file, composed from the library's defaults, the machine's settings, her manifest's overrides and her bundle's files | `tools/new_character.py compose <key>` | smoke: every character's config is what her bundle composes. **A key read by code and absent from the defaults is a crash**, and a secret is never written into a bundle |
| 5 | **her prompt directory as the config names it** | a copy of the bundle's | the same compose | smoke: the two rooms' system prompts do not diverge by more than the speech guide; `tools/fills_check.py` proves every token renders |
| 6 | **her save** | her database file, created only when the path does not exist and seeded by building her once with the model and the network refused | the same compose | smoke: her whole App constructs; her 166-odd declared wires are attached; nothing in her seeded save is another character's material |
| 7 | **her row in the register** | `characters.json` -- her key, name, hub id, config, save, program, launcher, task and **the exact command-line regex her process is found by**, written by hand because the restarter kills what it matches | the same compose; the manifest says `registered: false` until the owner decides | `restart.cmd --list` prints the table and touches nothing; the restarter refuses if a target's pattern matches more than one process |
| 8 | **her launcher** | her `.cmd`, **staged as `<launcher>.next`** because a running console reads a batch file by byte offset | the same compose; the restarter moves it into place between the stop and the start | the old launcher lands under the retired directory; **never edit a launcher under a running process** |
| 9 | **her scheduled task** | the task named in her register row | `restart.cmd <key>` creates it when it is missing | a bot started as a child of a tool's shell dies silently minutes later, so the task is the only way in |
| 10 | **the whole build check** | -- | `python tools/smoke.py` | it builds every registered character on a copy of her save and every kind of character the sheet can declare on a scratch one, calls every report, names dead config keys, and runs the static passes. **It must end all clear before any restart** |
| 11 | **verification of the bundle in isolation** | -- | `tools/new_character.py verify <key>` | builds her whole App on a scratch save with the model and the network refused, and fails on a surviving hole, a path that is neither hers nor the machine's nor the world's, another character's material in her prompts or her save, a roster that does not resolve her to herself, a missing world owner, or **an existence answer that disagrees with her sheet** |
| 12 | **her retrieval** | her records and her phrase lists | reading, checked by code | a paired test: messages that must reach a named record, and messages that must reach nothing, each printing the top match and its score whether it passed or not. And a sweep for a phrase that fires inside a longer word |
| 13 | **the day-two audit** | her own record | reading | §6 step 31. Her own words are the only material produced under the conditions the card is for |

**Three files that are shared and must not be edited for her.** The shared
prompts carry no person by construction and a check proves it; the shared code
never names a person and a check proves that; and how she sees him is the
program's table and never the library's, with a third check. A character whose
material needed a shared file changed is a character whose material belongs in
her bundle.

---

## 12. What is open

Decisions the owner has not made, or has made and that are recorded here so
nothing re-opens them. Anything with a date on it is in `HISTORY.md`; the
running backlog of a subject already extracted is in `HANDOVER.md`.

1. ~~**The speculation budget** for the written gaps.~~ **Settled: there is no
   budget.** A card carries as many inferred and speculated rows as the
   situations it has to answer require, and each owes its frame, the evidenced
   rows it rests on, and its validation (§2.5, §3.2). What is counted is rows
   with no frame, and that count must be zero.
2. **Who reads the anchor episode of a reliability pilot**, given that an
   agent's read is another model's reading by another route and not a human
   ceiling (§3.2, §4.3).
3. ~~**Whether the timeline seeds dated memories.**~~ **Settled: it does.** The
   dated once-events of an extracted character's timeline are written into her
   memory store at her next boot, keyed on the event's stable id and carrying
   its receipt, so her past is reachable by meaning and by a deliberate search
   and not only by a message naming it. The quoted moments beside the timeline
   stay in the retrieval.
4. **Which baseline card a comparison is against**, where two exist for one
   subject.
5. **Whether low-resolution footage is used, and for what.** He wants it if it
   is cheap enough. The free uses are the scene list and the diarisation check;
   behaviour from frames is priced per episode before it runs (§4.7).
6. **One entry in the codebook is his to overrule**: a refusal that lands flat
   with its hedges outside it, which names the shape of a refusal rather than a
   second trigger, and is therefore held as a surface form of the refusal that
   stays in the room rather than being given an entry of its own.
7. **Whether the seed self-beliefs are also written into the file a
   character's config names**, which decides what a future fresh save believes
   (§10.3).
8. **Whether the coded half of the pipeline is merged into the base toolset
   now or at the start of the next run** (§9.1). It is a copy and a path
   change; leaving it means the next run imports across two subjects' trees.

---

## 13. Appendix: where each part of the nine old documents went

The nine were cut to one-paragraph pointers on 2026-09-06 and the pointers
themselves were retired on 2026-09-08, so the filenames below name where each
document's full text is kept rather than a file in `docs/`. All nine are under
`data/retired/20260906_guide/originals/`, and the stubs that stood in their
place are under `data/retired/20260908_1250_guide_consolidation/stubs/`. The
documents that were not cut are listed last.

**The original concept read against the current method**
(`scail-concept-review.md`, retired). What the original claims and what survived
unchanged: §1.1 and, entry by entry, §2.1. Each change with the measurement
that forced it: §2 (the move from generation to classification), §4.2
(confidence became reliability), §5.7 (evidence count became a verified
receipt), §4.1 (function and construct separated into layers), §2.5 (the
honest boundary became a tier field), §4.6 (frequency became a rate in a
context), §3.2 (the completeness estimate became computed bounds; prediction
became the test of a description), §3.2 (a profile and a type as a prior),
§1.2 (the subject changed kind; register transfer), §5 (the machinery got its
own rules). What the codebook entry had dropped: §2.2 (the suppressor, the
occasions, the variation) and §4.7 (the physical channel, named as an unused
one). The composite pattern's home: the drivers of §3.2. The scene-level
context: §4.6. What the two say together about the evaluation: §1.2.

**Running the extraction pipeline on a new subject**
(`extraction-pipeline.md`, retired). What the subject must come with and what
degrades with less material: §3.2. Who does the work, and the correction that
a hand read was a model reading: §3.2 and §5.1. The eleven stages: §3.2. Model
choice and where the model is not a parameter: §5.2. Reusable code against what
must be redone, and the judgement work costed: §3.2 and §6. The traps: §5.9.
What the pipeline did not establish -- the missing noise floor, the extraction
never held out, the description losing to counting, prevalence not being a
trait, the negative class being a mixture, register transfer: §4.4, §4.6 and
§1.2. The one-screen order: §6.

**From a corpus to an evidenced character card**
(`corpus-to-card.md`, retired). Material, discovery, measurement, the state, the
card and its checks: §3.2, §4.2, §4.6. Every operating note of its Phase F:
§5, section by section -- the two kinds of worker (§5.1), the two clients
(§5.2), how a long call dies (§5.3), the probes (§5.4), chunking by segment
(§5.5), the brief (§5.6), JSON and receipts (§5.7), repository hygiene (§5.8),
and the failure table (§5.9, merged with the pilot's). What it establishes and
what it cannot: §1.2. The one-screen order: §3.2 and §6.

**A standardised mechanism codebook** (`mechanism-codebook.md`, retired). What the
problem is, and the three separate requirements: §2. The four layers: §4.1.
The framework -- the closed book, the entry, anchoring to published
instruments, unitisation, the coding protocol, reliability and the gate: §2.1,
§2.6, §4.1, §4.2. Validity, what is reachable: §4.4 and §4.6. What will work
and what cannot be made to: §4.3 and §1.2. The pilot that decides it: §4.5,
which now carries the pilot as run rather than as designed. The honest summary:
§1.2.

**A known state from a corpus** (`state-from-corpus.md`, retired). What makes a
state known, meaning that it predicts: §4.6. The three tiers as a field: §2.5.
The state as a trigger table rather than a type: §3.2. The four-letter scheme
as a prior and not a measurement: §3.2. The three bridges to the gaps -- where
the performance slips, what she says about her own life, and invariance across
contexts: §3.2 and §4.6. Speculating on purpose and then checking it: §3.2. Its
build order: §6.

**The codebook's scope** (`codebook-scope.md`, retired). What "entire" means and
what it does not: §2.7 and §1.3. The unit with the suppressor, occasions and
variation: §2.1 and §2.2. The twenty families: §2.4, now with the counts version
0.1 actually holds. The dimensions every instance carries: §2.5. Applying a
code to an extracted, an authored and a live character, and what a rate tunes:
§3.1, §3.2 and §3.5. Provenance declared once: §4.1. Size, and empty families:
§2.3 and §2.4. Out of scope: §2.7. What the three inventories found: §2.4.

**From the finished baseline to the codebook and the evaluation**
(`evaluation-plan.md`, retired). Building the codebook, the pilot and the gate, the
coded pass, the holdout and the cross-subject control, judgement: §4 and §6.
The evaluation itself -- records, the trigger table, the profile, tiers, the
gaps, the card, the comparison: §3.2 and §6. The order with costs and reading
time, and the owner's decisions: §6. The constraint that future subjects bring
less data, with the loss ledger, the data-hunger curve, the text-only rule, the
channels ranked by cost and the fictional subject as validation: §1.3, §4.7 and
§3.4.

**A type compiled into behaviour** (`type-compile.md`, retired). The three layers
and the vocabulary grep that holds them apart: §3.1. What the mechanics are in
this project's terms, including the two stress modes and health as a dial:
§3.1. The compile table: §3.1. The pipeline for a new agent: §3.1. What the
existing characters are under it: §3.1. Where it meets the codebook, and the
five-factor profile staying the derived measure: §3.1 and §3.2. The limits,
including the closed circle for authored agents: §3.5 and §1.2. What exists on
disk -- the table, the companion codebook and the compile tool -- stays in the
codebook file's own spec (`docs/codebook.md`) and in the authored mechanisms
spec (`docs/cast-mechanisms.md`), which describe the files as they are.

**Two ways to make a character** (`authored-vs-extracted.md`, retired). The two
routes: §3.1 and §3.2. What each can claim and what each costs: the table in
§3.3. When to use which: §3.3. Extraction from a fictional canon as the one
case with a criterion: §3.4. The codebook as the seam: §3.5.

**Not replaced.** `docs/scail-concept.md` is the origin and is kept exactly as
written; its idea is §1.1, its six steps and its limits are distributed through
§2 and §1.2, and its worked example is not reproduced anywhere, because the
point of the example is that it was the first thing the method was tried on.
`docs/verification.md` is the limits of any voice check -- the anchor as a
measurement rather than a judgement, the seven fallacies, and what no verifier
here can do -- and §1.2 quotes it rather than absorbing it.
