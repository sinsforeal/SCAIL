# System One (typesafe.ai) against SCAIL: what it is, where it would fit, and the access request

An assessment that became a build, and then part of the live path. Adopted and
extended 2026-09-17: `typesafe.py` is the client. **All eighteen implemented
uses are enabled for Momoka as of 2026-09-18**: the five original uses and
the thirteen stage-role uses from
`docs/2026-09-17_jev_stage_roles_design.md`. Section 2.4b records the earlier
calibration; the activation audit is in
`docs/2026-09-18_source_game_and_typesafe_audit.md`. There is one
`.use('<name>')` call site per use, `typesafe` is not a key in `models`, and
Jev is in no role: every use is a classifier use and there is no Jev
model role. The one-provider rule (section 4) was his ruling and was taken as
a classifier beside the provider, not a fallback under it. Source: `https://docs.typesafe.ai/concepts/how-to-build-with-system-one`
and its sibling pages on confidence, confidence-gated routing, speculative
fan-out and composite scoring, read 2026-09-15.

**Names, settled 2026-09-17.** Three names for three things, and they are not
interchangeable. **System One** is the service -- the thing that answers.
**typesafe** is this project's code for it: `typesafe.py`, the `typesafe`
config section, the `[typesafe]` log tag, the `TypeSafe` class, and
`tools/typesafe_probe.py`. **Jev** is the MODEL behind the service
(`jev-latest`, which answers as `jev-1.13.0`). Prose says "System One" for the
service and "Jev" only when the model version is what is meant; the 2026-09-17
build notes used "Jev" loosely for the whole thing, which is the confusion this
settles. It is also not one of her stage roles: `typesafe` is not a key in
`models`, `jev-latest` is not a role model, and the stage's two model pickers
do not and must not offer it -- it is a classifier for code's half of the
split, never a voice or stage role.

**Measured 2026-09-17, with the key he placed at `secerts/typesafe.txt`.** The
probe is `tools/typesafe_probe.py` — read-only, and nothing in the runtime
imports it. Endpoint
`POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer <key>`;
Momoka now pins `model: "jev-1.13.0"` (the earlier `jev-latest` alias resolved
to that version). Latency 242–356 ms for a call of
1 to 30 questions: 30 questions took 315 ms against 316 ms for one, so the
parallel claim holds and questions are free in latency up to that batch. Three
identical calls returned the same first answer to the hundredth (0.97) and the
second within 0.01 (0.88, 0.89, 0.89), so repeat answers are stable but a
near-threshold noul can move in the second decimal — read a noul as a
probability, not a label, and put the threshold at a distance from it. All
three types answered correctly on the API's own example (`noul` 0.95, `choice`
billing 0.89 with confidence 0.84, `score` 1.04 with 0.94). A ten-question
fan-out shaped like SCAIL's used 807 input and 247 output tokens. **Price:
\$0.042 per Mtok input, output tokens free** (jev 1.13, from the models page);
all four probes together were ~3,588 input tokens, about \$0.00015. At this
document's own volume — say 1,000 calls a day at ~800 input tokens — that is
roughly \$0.034 a day, about \$1 a month. **Rate limits:** 250,000 tokens/second
and 1,200 requests/minute, far above that volume; the pages warn the limits
move while capacity lands. No 401, 422 or 429 was seen.

**What the SCAIL-shaped fan-out actually said.** On a state holding his newest
message, her draft, her day's record and the scene, the ten questions returned
`did_anything_happen` 0.82, `is_a_question` 0.89, `reaches_for_a_memory` 0.92,
`touches_a_promise` 0.40, `asks_her_to_do_something` 0.40, `draft_claims_a_spend`
0.02, `draft_language` japanese at confidence 1.00, `his_tone` 1.02 (ordinary,
confidence 0.96). The two that matter to the flag-not-cut rule both landed in
the uncertain band: `draft_leaks_an_app` 0.66 and `draft_step_out_of_line` clean
at confidence 0.68. The leak flag is a false positive in substance — she is
allowed to know the weather, and the draft named a weather *app* rather than the
weather — and it is exactly the behaviour section 2 argues for: a modest-
confidence flag in the log, not a cut. The language choice at confidence 1.00 is
a clean replacement for the current language check.

## 1. What System One is

A hosted classifier with a small, typed answer surface. One request carries a
`state` string (the thing being judged) and a batch of named questions, each
of one of three types:

| type | instructions plus | answer |
|---|---|---|
| `choice` | a `criteria` map of option name to one-line meaning | the chosen option, a probability per option, a `confidence` 0 to 1 |
| `score` | a scale with anchors (0 to 4 in the examples) | a level, a probability per level, a `confidence` |
| `noul` | a statement | yes or no; no confidence property |

Every question in a request is evaluated in parallel with no shared or hidden
context, so adding a question adds no latency. The vendor claims about 100ms
a call, calibrated probabilities, and the same answer on repeat. The vendor's
own design rule is code owns the workflow, the model gets narrow structured
decisions, and no agent loop; their seven steps are: deterministic work in
code, only relevant context per question, nested JSON for the state, one
atomic judgement per question, structured instructions over prose, many
independent questions in one call, and deterministic combination of the
answers afterwards.

Two patterns from the docs carry most of the value:

- **Confidence-gated routing.** The answer says what; the confidence says
  whether to act. A universal floor (0.6 in their example) routes the
  uncertain case elsewhere, and each action above it sets its own threshold
  by how much it costs to be wrong.
- **Composite scoring.** Score independent dimensions separately, normalise,
  and combine with weights code owns. The weights are visible and adjustable.

## 2. Where it fits SCAIL

The split his call of 2026-09-07 fixed (`docs/tool-calling.md` section 17)
is: code decides when she is asked and what she is allowed to do; the model
decides what she does. System One is a tool for code's half only. It can
sharpen when she is asked, what she is offered, and what gets flagged. It
never chooses what she does and never writes a word of hers.

Ranked by how directly the pattern maps and how little it disturbs the live
path:

**Built 2026-09-17, five original uses, all live on Momoka.** `typesafe.py` is the
client (key `secerts/typesafe.txt`, `jev-latest`, a universal `floor` of 0.6);
each use is one batched call, 240–370 ms and 500–1,300 input tokens, and every
answer only flags, routes or scores -- none writes a word of hers or decides
what she does.

| use | item | what it answers | her threshold |
|---|---|---|---|
| `reconcile` | 1 (detector half) | whether each (event, action) really happened, before the model role is called; a tick whose scene claims nothing never pays for the model | 0.5 |
| `inbound_signals` | 2 | the twelve-question speculative fan-out over his newest message; kept on the save and read by the state gate as an additive signal only | 0.5 |
| `sight_activity` | 4 (telemetry half) | what he is doing from the raw window trail (the classifier replaces the prose scrape) | 0.5 |
| `emotion` | other seams | the `choice` over the 28 GoEmotions labels, ahead of the `emotion` role | 0.35 (a 28-way choice spreads its probability, so the floor is not a two-way question's) |
| `state_appraisal` | 3 | her gauge deltas: 16 `score`/`choice` dimensions over the live tick context, combined by code and fed to `State.apply`; the `state` role is the fallback | 0.6 |

Item 1's leak and continuity checks, item 4's other half (the flash digest
writing prose from a classified moment) and item 4's note-reader decision are
not built. Item 5 has no seam on this fork (her cast is off) and item 6 does not
fit as written (below).

### 2.4b The stage-role uses built 2026-09-17

Thirteen uses for the stage, from `docs/2026-09-17_jev_stage_roles_design.md`
and its implementation guide. The table shows their current Momoka state.
Each is one config line from on. The floors were read off
SCAILV3's archive (532 runs, 78 roles; V3 has no Jev in code, so it is pure role
output), not guessed. The sample column is agreement on the answers Jev would
actually commit to, with everything under the floor falling back to the role.

| use | what it answers | floor | V3 sample at floor | state |
|---|---|---|---|---|
| `scene_director` | place, camera, transition, mood, track, vocal action and opening face as one batch | 0.3 place floor | -- (live) | live |
| `said_when` | did he say when he is reachable, and which kind | 0.5 | 1.00 | live |
| `lookup` | did he name a thing, and which kind | 0.5 | 1.00 | live |
| `expect_him` | did he commit to anything, and how firm | 0.5 | 1.00 | live |
| `wonder` | the kind of each question she turns over | 0.5 | 1.00 | live |
| `affection` | the warmth each of his messages leaves her at | 0.5 | 1.00 | live |
| `foresee` | `reply_p` and `reply_minutes` | 0.3 | 0.94 | live |
| `habits_him` | how solid each habit of his is | 0.5 | 0.94 | live |
| `ick` | how much her circle would make of it, how private it is | 0.3 | 0.93 | live |
| `rupture_settle` | mended, tried, worse or nothing | 0.5 | 0.87 | live |
| `intent` | the urge she is acting on | 0.5 | 0.75 | live |
| `wonder_answer` | what became of her unasked question | 0.5 | 1.00, but it defers most samples | live |
| `which_one` | the work the moment is about | 0.5 | 2 samples only | live |

On 2026-09-18 the live scene call gained meaningful camera, transition, mood,
interjection and face criteria, with separate confidence floors for music,
vocal tags and the opening face. The place and track catalogs appear only in
Choice criteria. A measured six-question call fell from about 4,360 to 2,716
input tokens before the face question was added. The scene probe and backlog
voice fix are in `docs/2026-09-18_typesafe_scene_and_backlog_notebook.md`.

Two shapes the design did not name, both now part of the pattern. **One factor
per question, composed in code:** where a judgement rests on several independent
things, each is asked and the answers are combined by code (`_wonder_combine`,
`_digest_combine`, and the rest), and the gate weighs only the factors that
decided the answer. **The floor is the mechanism:** raw agreement is usually
under the bar, but the errors sit low, so the role answers the unconfident half.
Where a later question needs something an earlier one found the call is chained:
`wonder` (the role writes the question, Jev labels it), `expect_him` and
`habits_him` (the role extracts, Jev sets the confidence). The same day's tests
also showed what does not move -- `digest_judge` (0.62), `recall`, `coherence`,
`settle_beliefs`, `spiral` and `approach` stay on their roles, for the reasons
in the build notebook. `rupture` is blocked on the prose ruling.

### 2.5 What the five uses bought

- **Cost and latency.** A batched classifier call is a fraction of the
  generative call it replaces: **$0.042 per Mtok input with output tokens
  free**, 240–370 ms, and **questions add no latency** (30 questions 315 ms
  against one at 316 ms). The gauge appraisal is one ~900–1,300-token call per
  significant tick, about **$0.002–0.01 a day**, where a generative `state`
  call stood and cost more. At the document's own ceiling of 1,000 calls a day
  the bill is about $1 a month.
- **A confidence to gate on.** Every answer carries a calibrated confidence, so
  a judgement is routed rather than trusted whole, and each use sets its own
  threshold by what being wrong costs: 0.5 where a miss is cheap, 0.6 for a
  gauge move, 0.35 for the 28-way feeling choice because a many-option choice
  spreads its probability. A threshold is put at a distance from the number it
  judges because repeat answers move in the second decimal.
- **The older behaviour is the floor, not a lost capability.** A call that
  fails, abstains or clears nothing falls through to the role or gate that ran
  before it. `reconcile`, `emotion` and `state_appraisal` each name their role
  as the fallback, and the role paths were not edited, so the fallback is the
  previous behaviour by construction.
- **Code owns the numbers.** The classifier says whether and which way; the
  weights, the gain and the floors are config (`state.appraisal`), visible and
  tunable without a code change. The feeling label is mapped to her eight faces
  by code and the gauge levels are mapped to points by code, so nothing it
  returns is applied raw.
- **One context, two renderings.** `State.appraisal_state()` builds the tick
  once; the `state` role reads that rendering and the classifier is handed the
  same fields, byte-identical for the role, so the two cannot drift.
- **Every answer is on the record and can be calibrated.** `inbound_signals`
  keeps the last 200 on the save, the gauge update logs a provenance line per
  delta (`relief +3 (warmth_from_him 4/0.91)`), and `state_log` keeps the row
  with its reasons. This is the calibration evidence the vendor's form asked us
  to report back.
- **The split holds.** Code still decides when she is asked and what she is
  allowed to do; the classifier answers narrow closed questions, never writes a
  word of hers and never chooses her action.

### 2.6 What is left, and why

- **Candidate seams a closed-set classification would take, none built.**
  `intent` -- one of `share/ask/complain/check_on/tease/continue/nothing` plus a
  line (`sim/intent.py:7-12`). `scene_director`'s place and background
  (`sim/scene.py:182`; camera and transition are written). The nightly
  `affection` review's per-message level, which is already a `score` shape
  (`sim/appraisal.py:172`; only its `why` is prose, so that half stays a role).
- **Item 1's other half.** `reconcile`'s detector is on the classifier; the
  leak and continuity checks on her draft are still model roles, which is where
  the false-positive leak on his uptime happened.
- **Ruled out by design, not by capability.** `pick` (section 3: the one place
  the model chooses what she does). `quality` (already mechanical). `coherence`
  (it can answer *whether* a seam is there; the sentence needs a writer).
  `expect_him`, `habits_him`, `commit`, `said_when`, `him_profile` (they extract
  a field, which is generation). `works` identify (a deterministic two-table
  lookup, so the classifier would guess where code knows). The roles that write
  her words.
- **Waiting on his ruling.** Whether `inbound_signals`'s `did_anything_happen`
  may skip a read the heuristics would have made (`scail.py:3420`), and whether
  `is_this_new` may skip a tick that fan-out would have woken. Both change when
  she feels things, so neither is the builder's to take.

1. **The checks that flag her replies.** The continuity editor, the leak
   checks (`tools/sight_words.py` is static; the runtime editor is a model
   role), and `reconcile.py` each ask a yes/no question of a draft: does it
   name an app on her phone, does it contradict the ledger, does it claim a
   send or a spend the record lacks. Today the role answers in prose or JSON
   with no measure of how sure it is, and the resident's editor once binned a
   true remark about his uptime as a leak. As `choice` questions (the yes/no
   `noul` type carries no confidence, so use a two-option choice) with a
   threshold, that remark would have been a low-confidence flag in the log
   rather than a cut. The standing rule holds: checks flag, never rewrite.
2. **The "did something happen" gate before a paid call.** The state role
   runs its deltas only when something happened; lore retrieval fires only
   when the moment reaches for a memory; commitments and expectations watch
   for a promise or a question. Each gate is a heuristic or a keyword today.
   One fan-out call per inbound message can carry a dozen speculative
   questions (is this a question, is he upset, does it touch a promise, does
   it reach for a memory, is it about a cast member, is he asking her to do
   something) and code reads the ones it needs. That is the vendor's
   speculative fan-out pattern exactly.
   **Built 2026-09-17 as `inbound_signals`:** `sim/inbound.py` asks the dozen
   in one `noul` fan-out per new message, keeps every answer on the save
   (`inbound_signals`, last 200) so the questions can be calibrated against
   what happened, and `scail.py:3420` reads them as an **additive** signal
   only -- a heuristic that fired is never overruled. The saving direction
   (letting the classifier skip a read the flags would have made) changes when
   she feels things and waits on his ruling; it is written into the comment at
   `scail.py:3420` rather than taken.
3. **Appraisal as composite scoring.** The composite-scoring pattern is the
   gauge model: independent dimensions scored 0 to 4, normalised, combined
   with weights code owns. **Built 2026-09-17 as `state_appraisal`.** His ruling
   that day -- "I don't mind if jev is controlling her emotional state -- as
   long as it is derived from context" -- settled the one-owner-per-gauge
   objection: the classifier takes the deltas, and "derived from context" is
   enforced by one context builder (`State.appraisal_state()`), by the
   classifier emitting only levels and options, and by code owning the points.
   The design and its capability split are
   `docs/2026-09-17_gauge_appraisal_composite_scoring_design.md`; the `state`
   role stays as the fallback. Replace with no shadow run was his call.
4. **Digest and snoop classification.** What he is doing from window titles
   (trading, anime, a game, work, reading) is a `choice` with probabilities.
   The flash digest would then write prose from a classified moment rather
   than from raw telemetry. Same for the note reader's decision that a file
   is a record of his at all.

   Seam checked 2026-09-17, and it is reachable. `resident/sight.py` reads his
   screen two ways and neither answers what he is DOING: `page_of` reads a
   title's shape only (site, and work/name/unknown from punctuation), and
   `noticed_line` recovers what he had open by regex-scraping the digest's own
   prose, which is why its comments are a list of prose shapes that fooled it.
   A `choice` over the raw window trail (the titles and process names the
   collector already writes) would answer the question the scrape is guessing
   at, and the scrape's whole class of capture bugs goes with it. This one
   changes what she knows about his machine, so it wants a deliberate turn, not
   a side effect of the client landing.
   **Built 2026-09-17, the telemetry half (`sight_activity`):** `resident/sight.py`
   `_trail()` gathers the live window plus the last half hour of closed
   sessions and classifies it into `working`/`reading`/`watching`/`anime`/
   `gaming`/`social`/`shopping`/`idle`/`other`; the answer is kept for one
   `poll_seconds`, stands on its last answer when the call fails, and renders
   one `fact` line in `glance_lines`. The other half -- the flash digest writing
   prose from a classified moment -- and the note reader's file decision are not
   built. The regex scrape in `noticed_line` is still there and is now a
   candidate for retirement once the activity line has been watched for a day.
5. **Cast mechanisms.** Which of the 189 codebook entries a beat calls for is
   a classification over a fixed set. The type file stays compiled and out
   of prompts, as `docs/cast-mechanisms.md` requires.
6. **Tests and the voice bench.** Checked 2026-09-17 and this one does not fit
   as written: `tools/expect_test.py` and `tools/compare_test.py` judge nothing
   at run time. They stub the model outright (`app.llm.call_json = ...` in the
   former), assert deterministically against it, and still name the third
   character's cast (`Rena-chan`, `Kaito`), so they are not runnable against
   Momoka as they stand. A stable repeat answer would have a place there only if
   one of those tests stopped stubbing and asked a real question of the message
   -- the item-2 pattern used inside a test rather than a new seam. It does not
   replace reading the source episodes by hand, which is his standing rule
   for any analysis.

**Other seams, found by reading the role list 2026-09-17 (90 roles).** Ranked by
"the answer is a closed set, and the path is either broken or is a whole model
call today":

- **`emotion`** is already this decision made through prose: `sim/emotion.py`
  takes the `emotion` role's answer and discards it unless the label is one of
  the 28 GoEmotions (`emotion.py:15-18`). A `choice` over those 28 removes the
  validation, carries a calibrated confidence, and costs ~350 ms against a model
  call. **Built 2026-09-17:** the 28 labels are the `choice` criteria (all
  `null`); a label off the set, an answer under her 0.35 floor, or a failed call
  leaves the `emotion` role to decide exactly as before, with the local cue pass
  as the floor under both. The floor is 0.35 rather than the doc's 0.6 because a
  28-way choice spreads its probability over 28 options, so its confidence is not
  comparable to a two-way question's; on the one genuinely flat line it answered
  `neutral` at 0.36, which the cue matcher would otherwise have read as
  `curiosity`.
- **The quality guard is already mechanical.** Checked 2026-09-17: `sim/quality.py`
  runs local passes (`_forbidden`, `_caps`, `_openers`, `_self_repeat`,
  `_recent_repeat`) and reaches for a model only in `_length`, where
  `quality_rewrite` is asked to say the same thing in fewer words. There is no
  model verdict to replace here; only a new capability (semantic repetition --
  "she is answering this the same way again") would be an addition.
- **`coherence` is a detection-only fit.** Its nightly `review` returns seams
  carrying `kind`, `severity` and a `what` that names the contradiction
  (`sim/coherence.py:175-199`), so the naming needs a writer. System One can
  answer *whether* a seam is there; the sentence describing it stays the role's.
- **The verdict roles**: `digest_judge`, `which_one`, `watch_pick`,
  `spiral_settle`, `rupture_settle`, `settle_beliefs`, `gloss`, `observer`,
  `devoice` -- each returns a label or a yes/no over a fixed vocabulary. All
  nine are wired with a prompt file and a call site, but only `watch_pick` has
  ever run (once); the rest have not fired because their subsystems are off for
  this bundle (no MAL mirror, no episode reads, no seed beliefs, no ruptures or
  spirals), not because code is missing. So there is no frequency evidence for
  choosing among them; they would be picked on value, and moving one buys
  nothing until its subsystem runs.
- **`works` identify** -- whether a title is a work she was in. Not a candidate
  on inspection: it is a deterministic yes/no/two-table lookup in the local
  mirror, so a classifier would guess where code already knows.
- **`pick`** looks like the strongest fit of all -- her action is a choice over
  a closed tool set (`reply_now`, `reply_later`, `leave_it`, `text_him`,
  `look_at_his_machine`), and the log of 2026-09-17 shows it returning nothing
  twice with its reasoning beside the answer, so the backup decides. But section
  3 rules it out on purpose: the pick is where the model decides what she does,
  and a classifier over it would swallow that decision. Named here so the
  collision is visible rather than quietly taken.
- **Not a fit**: `expect_him` (it extracts a quote and a due date, which is
  generation), `state` (item 3, and it owns the gauges), and the roles that
  write -- `persona`, `diary`, `recall`, `wonder`. `scene_director` is half a
  fit: place and background are a choice, camera and transition are written.

**The line to hold.** What the sprite should be is NOT a classifier's question.
Once the feeling has a label, the label -> face table (`sim/emotion.py`) and the
face -> base/diff/geometry resolution (`channels/vn_expression.py`) stay code:
her art has eight recorded faces and is cut at the socks, so an invented
expression is a missing file. Reading the feeling is the model's half; choosing
the sprite is code's.

## 3. Where it does not fit

- The ten voice roles, the diary, the persona, the cast's words: it does not
  generate text.
- The pick: the model chooses her actions through tool calls, and the impulse
  function is a pure function on the gauges by design. Neither wants a third
  decider.
- Her eyes: Gemini on Vertex, `sensors/vision.py`. Whether System One
  accepts images was not checked.
- Anything addressed to her. Every System One question is the machine
  talking to itself, so English is correct, on the state role's precedent
  (`docs/language.md`).

## 4. Constraints, and how they are kept now that it is adopted

- **The one-provider rule is his.** SCAIL runs one provider, OpenRouter, with
  no fallback between providers, by his call. System One is a second vendor
  with its own key. It is not an OpenAI-compatible endpoint and not a voice
  role, so it can be argued as a classifier beside the provider rather than
  a fallback under it. That is his ruling, not the builder's.
- **A failed call falls back to the deterministic gate that exists now**,
  logged by exception type only (`netwatch.redact`), never written to
  `missed_calls`, because a 100ms classifier is not a paid answer worth
  replaying. **Kept:** `typesafe.py` redacts `last_error` and prints the
  exception type alone, and no use writes `missed_calls`.
- **Key under `secerts/`**, beside the OpenRouter key, never in
  `config.json`.
- **Every switchable use gets a row in `Config.REQUIRES`** naming the
  property it needs (`None` for the mind and the machine). **Kept:** the five
  uses ride the existing `typesafe` row, and `state.appraisal` deliberately
  carries no `enabled` of its own, so there is one switch per use and no second
  flag to forget.
- **The log names which decided**: the classifier, or the gate it replaced,
  on the same line the pick already uses. **Kept:** each use prints a
  `[typesafe]` line, the gauge update prints `[state.appraisal] <gauge> +N
  (<dimension> <level>/<confidence>)` per delta, and a fallback prints the
  exception type.
- **Thresholds are config**, one key per use, in `config.py:DEFAULTS` and
  `config.json` both. **Kept:** `typesafe.uses.<name>.threshold` per use, and
  the gauge appraisal's weights, gain and per-dimension floors are the
  `state.appraisal` block, so a gauge that moves too little or too much is a
  number and a restart.

## 5. Access request

For the vendor's form. Contact details are his to fill in.

> **Project.** SCAIL is a private, single-user research build: a simulated
> person who lives on her own clock and talks to one user over a messenger
> we wrote. Four such characters run side by side on one machine, each her
> own process and save, sharing a mind library: a 25-gauge affective state,
> a schedule, a memory with a forgetting curve, a cast of people around her,
> and a psychology layer (attachment, withholding, rupture, commitments,
> expectations). Her words come from large language models over OpenRouter.
> Everything around her words is code: what she is allowed to do, when she
> is asked, what gets checked before a line is sent.
>
> **Why System One.** Our design rule since September 2026 is the one your
> docs state: code owns the workflow, the model gets narrow structured
> decisions. We have a dozen places where code needs a small calibrated
> judgement and currently uses either a keyword heuristic or a full
> generative call: did anything happen in this message that should move her
> state; does this draft contradict her day's record; does this draft leak a
> fact she cannot know; what is the user doing right now from window titles;
> which of 189 behaviour codes a scene calls for. We want to replace those
> with batched choice and score questions, gate on confidence, and keep the
> generative models for her voice only.
>
> **Volume.** Low. One fan-out call per inbound message and per 20-minute
> scheduler tick, across four characters: on the order of a few hundred to a
> low thousand calls a day. No end users, no redistribution, no training on
> your outputs beyond the deterministic combination your docs describe.
>
> **What we would report back.** Calibration against our own record: every
> call and answer is logged, and each flag it raises is checked against
> what actually happened in the save. We can share aggregate calibration
> numbers per question type.
