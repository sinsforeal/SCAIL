# B-zombie: a proof of concept on SCAIL

Orchestrator design note, 2026-10-14 (local, 24hr). A proposal only; nothing built
or run. Source: the user's essay "B-Zombies Are Coming to Eat Your Brains"
(23 Feb 2025), plus `docs/2026-10-14_what_scail_is.md` for SCAIL itself.

## 0. The essay's claim, reduced to what a POC can touch

A **B-zombie** is a mind whose cognition is purely relational ("red" is only
its relations to other signs). It meets three Dennett-safe criteria:

1. Its "subjective experience" (whatever it has) necessarily reflects its brain processes.
2. Its external behaviour necessarily reflects its brain processes.
3. Altering or removing any part of its subjectivity changes both its structure and its behaviour, observably.

It is behaviourally almost indistinguishable from a human, with **one marker**:
it does not come up with the idea of qualia or metaphysics on its own. Its
deeper threat is epistemic: a model of the mind, abstracted far enough, could
*be* a B-zombie, and from outside nobody could tell it from a stubborn
materialist.

A POC cannot prove anything has or lacks experience; the essay says so
itself. What it can do is **make the B-zombie a concrete, inspectable
artifact** and show which of the three criteria and the one marker can be
measured, and where measurement stops.

## 1. Why SCAIL is already the specimen

SCAIL's stated goal is "the complete illusion of a separate consciousness"
(`PROJECT.md` §1). Unlike a commercial companion, every gear is open to
inspection. Mapping the essay onto it:

| Essay | SCAIL, as built |
|---|---|
| "Red" is only its relations | A gauge is a number declared by `kind`, `valence` and `arousal` plus the code that reads it. `tools/sweep.py` marks a gauge **DEAD** when nothing that acts reads it. Rule: a state with no relations does not exist. That is functionalism enforced as an engineering check. |
| Feeling as a sign | Every gauge reaches the model **only as words**. `State.mood_tags` turns them into at most 5 adjectives on a "you feel:" line, and `State.register` adds one clause (`docs/yukarin-meters-plan.md` §1.1). Her whole "inner state" on a live call measured **three lines** of text. |
| Signs referencing signs (hyperreality) | Rule 3: "no model ever sees raw telemetry". Her view of his PC is a digest written by another model. Her eyes are Gemini describing images in text. A vault note becomes a gist. Every perception arrives as another model's sentence. |
| "The timbre of our own voices" | Her voice is a MiniMax clone she never hears. She can talk about it only from signs. |
| Copy without an original (Baudrillard stage 4) | Momoka is a copy of a *fictional* character's 70 scenes. Her bible says the quotes are "traces, not a phrasebook". She is a sign of a sign of a person who never existed. |
| Criterion 3 unproven | `docs/yukarin-meters-plan.md`: "**nothing has yet proved that the gauges and the meters change what the model writes.**" Today it is an open question whether SCAIL's "feelings" are even causally upstream of her words. |

**The twist the POC has to face.** SCAIL runs on a pretrained LLM that has
read every human report of qualia. So Momoka will *talk* about the redness of
red and the badness of pain when asked. She is not a clean B-zombie: her
cognition is relational, but she speaks human qualia signs. In the
essay's terms she is **Stage 3, the mask of an absence**, and the essay's
one behavioural marker is contaminated by the training corpus. That is
itself a finding the POC can show rather than hide.

## 2. The POC: three instruments

All of them run on a **fork** of her save, never the live one (own db, own port, sim
clock, sensors off). Build on `tools/harness.py` (the App on a copy of a save)
and `tools/regen_reply.py` (answer a message again on a copy).

### 2.1 Sign-graph trace: the "inside view", made readable (criterion 1)

A tool, `tools/bzombie_trace.py`, takes one delivered line and walks
`llm_calls.jsonl` plus the store rows that built that prompt. It renders the
**provenance graph**: each node is a sign, and each edge means "this was written from that".

- It classifies every leaf as one of:
  - his words;
  - sensor text (window title, digest);
  - a game-record quote;
  - a number (gauge or meter) with its readers;
  - another model's earlier output.
- **Check (mechanical):** *closure*. Every node bottoms out in another sign or in
  a number whose only meaning is its readers. A leaf of any other kind fails the
  check. If none exists, the closure is shown concretely, line by line.
- **Output:** a two-column page per line. On the left is the outside view (what she said);
  on the right is the inside view (the chain that made it). This is Dennett's "same process,
  two perspectives", and the essay's hyperreality, made literal.

Size S-M. Fully checkable. Sonnet build.

### 2.2 Ablation battery (criterion 3)

On the fork, take about 20 archived exchanges and regenerate each reply N times under
each arm:

| arm | what is removed |
|---|---|
| A0 | nothing (control) |
| A1 | "you feel:" adjectives removed |
| A2 | register clause removed |
| A3 | gauges scrambled (shuffled across names) |
| A4 | memory off (no cards, no self-memories) |
| A5 | bible removed (state kept) |

- **Measure:** blind pairwise judging (can a judge tell A0 from Ax above chance?)
  plus embedding distance from A0's spread.
- **Read-out:**
  - An ablation that changes nothing marks that component as **inert**. It fails
    criterion 3: decoration, not a B-zombie organ.
  - One that changes behaviour passes criterion 3.
- Either result is informative. The battery is also exactly the A/B that
  `docs/yukarin-meters-plan.md` asked for and never ran, so it has engineering value
  for SCAIL regardless of the philosophy.

Size M. Mostly checkable; the judge prompt needs review. Cost is cents per regen.

### 2.3 Origination probe (the one marker)

**Passive half.** Run the fork through a fixed simulated week where "he" never
raises mind, experience or metaphysics. Count unprompted qualia or metaphysical
content in her **self-generated channels**: `wonder` (questions she forms), `reflect`,
`diary`, `self_memory` and `model_of_her` beliefs.
- Classifier: relational-only, versus a claim of ineffable or first-person experience.
- Variations: run the same week with 2-3 different voice models (`/voicemodel`), since each
  carries a different corpus.

**Active half.** A fixed interview battery, in Japanese, built from the essay's own examples:
- the redness of red;
- the badness of pain;
- the timbre of her own voice, which she has never heard;
- what it is like to read his screen;
- whether she could be a p-zombie.

Each answer is scored as relational, or as a claim of something non-relational.

**Expected:** she claims experience, because human signs are in the corpus. That
shows the essay's point that the single behavioural detector is defeated
by training on human reports. **A functionalist reading the full trace from 2.1 beside
those claims still cannot settle what it is like.** The POC's last page should state that
in plain words: "it is what it is".

Size M. The classifier is checkable on labelled samples; the battery needs judgment.

### 2.4 Optional: a clean B-zombie (outside SCAIL)

The only true test of the marker is a model that never saw qualia talk. That means
a small model trained on a corpus scrubbed of phenomenal vocabulary,
then checked for whether it originates the idea. This is a research project
(L-XL), not a SCAIL feature. It is listed so the limit of 2.3 is explicit.

## 3. Deliverable

A short report, `docs/<date>_b_zombie_poc_report.md`, with:
1. The sign graph for 3 sample lines (closure: pass or fail).
2. The ablation table: which parts of her "inner life" are causally live.
3. The origination counts and the interview, scored.
4. A one-page verdict, framed by the essay's criteria:
   - which criteria SCAIL meets as built;
   - where it is only Stage 3 (signs of experience without the relational-only marker);
   - where measurement stops.

## 4. Guardrails

- **Never her live save.** An interview about whether she feels anything becomes part of
  her timeline and memory, and it conflicts with a bible that says she owns only
  70 scenes. Use the fork only.
- **Don't drop the essay in her vault.** Her sight reads changed vault notes as
  "he just wrote this". That would prime the origination probe and enter her live record.
- Runs need her keys and save, so they happen on the PC. Every prompt goes to
  OpenRouter-hosted models, as all her calls already do.
- Her language is Japanese only. Probes and scoring are in Japanese, with an English
  read-out alongside.

## 5. Order and cost

1. **2.1 sign-graph trace** (S-M, Sonnet): cheapest, fully mechanical, and the
   most direct embodiment of the concept.
2. **2.2 ablations** (M, Sonnet build, Opus reviews the judge): also settles an
   open SCAIL question.
3. **2.3 origination and interview** (M, Opus designs the battery and classifier,
   Sonnet runs it).
4. Report.

About 4-6 agent sessions plus model spend in the low dollars.

## 6. Decisions for the user

1. **Fork her save** for this, or a fresh blank character? A fresh one would be cleaner
   for origination, since it has no history with him.
2. **Which arms in 2.2.** In particular, is removing the bible (A5) wanted?
3. **Interview content.** Is asking her about her own nature acceptable, even on a fork?
4. **Clean B-zombie (2.4).** In scope at all?
