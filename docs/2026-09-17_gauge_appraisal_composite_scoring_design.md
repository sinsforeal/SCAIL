# Gauge appraisal as composite scoring: design for System One on the `state` role

Design, 2026-09-17. Read-only scope: nothing here is built. This document
settles how the hosted classifier (`typesafe.py`, System One `jev-latest`)
would produce the gauge deltas that `sim/state.py`'s `state` role produces
today, by scoring independent dimensions over the live context and combining
them with weights code owns.

Source of the pattern: `docs/system-one.md` section 1 (composite scoring) and
section 2 item 3 (appraisal). Source of the permission: the ruling of
2026-09-17, "I don't mind if jev is controlling her emotional state -- as long
as it is derived from context", recorded in `ORCHESTRATOR_HANDOVER.md`.

The document is written to be read on its own. Where it names a file and a
line, that is where the thing lives today, not a claim about a build.

**Revision, 2026-09-17 (later).** His two rulings are applied here. (1)
"Replace without shadow run": the scorer takes the gauges over from the
`state` role. The shadow mode that was section 9.3 is deleted and the "only
after a shadow run" hedge is gone; calibration and rollback come from the live
path instead, and section 9.3 says how. (2) Decisions 2, 3 and 4 of section 12
are settled by what the classifier can actually do, not by preference. Section
6 records which of the role's non-gauge outputs move to the classifier, which
stay a model call because they are prose, and which become a code template.
Section 12 resolves every decision by capability and names the one that
survives as his. Section 14 is the build plan. The capability statement itself
is section A of the report that accompanies this revision; its findings are
folded into sections 6 and 12.

## 0. What it replaces, in one paragraph

`State.update_from_llm` (`sim/state.py:1877-1946`) builds one user message
from the tick's live context, sends it to the `state` role, and hands the
role's JSON to `State.apply` (`sim/state.py:1140-1245`). `apply` is where
every mechanical guard rail lives: the per-update cap, diminishing returns,
habituation, stress amplification, the refusal of computed gauges, and the
relationship daily budget. This design keeps `apply` exactly as it is and
changes only who produces the `deltas` dict it receives. A classifier scores
a fixed set of appraisal dimensions (0-4 or a named option), code maps those
levels to gauge units through a weight table in config, and the result goes
through `apply` unchanged. The classifier says *whether and which way*; code
owns *how much*.

## 1. The state handed to System One

### 1.1 One builder, two renderings

Today the role's context is assembled inline in `update_from_llm`
(`sim/state.py:1889-1914`) as a labelled string: `TIME`, `GAUGES`,
`RELATIONSHIPS`, `WITH HER NOW`, `ALREADY IN THE NUMBERS`, the talk block,
`SCENE`, `EVENTS`, `MESSAGE FROM HIM`, `HIS SIDE`, `LAST MESSAGES BETWEEN
THEM`, the digest, the body-noise line and the body-settled line.

The design extracts that assembly into one method, `State.appraisal_state()`,
returning an ordered dict of the same values as typed data (gauges as a dict
of numbers, `relationships` as a dict, `scene` and `events` as their own
objects). The role's user string becomes a rendering of the same dict in the
same order. This is the whole answer to "the same live context": there is one
source and two renderings, so the classifier and the role cannot drift.

A test asserts the two agree: the role prompt's field labels and
`appraisal_state()`'s keys are derived from one list, and a change to one
without the other fails.

### 1.2 What is in

Everything the role is handed, because a delta has to trace to something the
classifier was given. Mapped from the current string:

| field in `appraisal_state()` | built from (today) | line |
|---|---|---|
| `time` | `self.clock.both()` | 1890 |
| `gauges` | `self.gauge_line()`, as a dict | 1891 |
| `relationships` | `self.relationships_brief()` | 1892 |
| `present` | `self.present_brief(scene)`, when non-empty | 1893 |
| `already` | `self.already_line()` -- the last reasons lines | 1894-1895 |
| `talk` | the finished-exchange block and `_talk_outcome(talk)` | 1896, 1815-1838 |
| `scene` | `json.dumps(scene)` | 1897 |
| `events` | `json.dumps(events)` | 1898 |
| `his_message` | `user_msg_text` (or a "(none this tick)" marker) | 1905 |
| `his_side` | read receipts on her last message | 1906 |
| `last_messages` | `chattext.lines(recent, ...)` | 1879, 1907 |
| `digest` | `digest_text` | 1909-1911 |
| `body` | `self.body_noise_line()` | 1912 |
| `body_settled` | `self.body_settled_line()` | 1913 |

The four `with_him` / `sees_him` gates in the current string stay: a field
whose section is off is absent from the dict, the same way the line is absent
from the prompt today (`sim/existence.py`). A character with no chat gets no
`his_message`, `his_side` or `last_messages`.

### 1.3 What is out, and why

- The role's instructions. `prompts/state.txt`'s rules, the `gauge_tells`
  render (`sim/state.py:717-727`), and the `delta_schema` render
  (`sim/state.py:729-733`) are scaffolding for a writer. System One gets
  values, not instructions, because code, not the classifier, owns what a
  gauge means and how far it moves. The `tells` stay in config for the
  fallback role.
- The output schema (`his_mood`, `relationships`, `reasons`). Those are
  answers, not context.
- The last reasons lines are *in* (`already`), because the novelty and
  habituation judgement needs them; they are the only field whose absence
  would make a standing situation indistinguishable from a new one.

### 1.4 The question over the state

One request: one `state` object, a batch of named questions. Per the vendor's
rule and the reconcile/inbound precedent (`sim/reconcile.py:335-367`,
`sim/inbound.py:67-91`), each question's `instructions` names the fields it
reads (`` `scene.events[i]` ``, `` `his_message` ``, `` `already` ``), so a
question is never answered over context it was not pointed at. A test asserts
every dimension names at least one key that `appraisal_state()` returns.

## 2. The dimensions

Scores are `score` 0-4 with anchors, or `choice`. A dimension that is
genuinely two-option is a `choice`, not a `noul`, because a `noul` carries no
confidence (`typesafe.py:130-154`) and every dimension needs one to route.
The columns: id, type, the levels or options, the grounding, the proposed
confidence floor, and the output it feeds.

`A` = the level is converted to a factor by code (section 3.1); the sign and
the gauge are in the weight table (section 3.2).

### 2.1 The event

| id | type | levels / options | grounded in | floor | feeds |
|---|---|---|---|---|---|
| `how_good_or_bad` | score | 0 plainly bad for her, 1 bad, 2 neither/nothing, 3 good, 4 plainly good | `events`, `scene`, `his_message` | 0.60 | relief (+), sadness (-), anxiety (-) |
| `how_activating` | score | 0 leaves her as she was, 2 an ordinary beat, 4 jolting | `events`, `his_message` | 0.60 | a gain on the negative dimensions (code) |
| `is_this_new` | choice | `new` / `standing` / `answering_what_she_sent` / `nothing` | `already`, `events`, `his_message`, `his_side` | 0.50 | the `fresh` flag for habituation |
| `whose_doing` | choice | `him` / `her_own_people` / `herself` / `nobody` / `the_world` | `present`, `relationships`, `events`, `his_message` | 0.50 | routes a delta to him or to her own people |

`how_activating` moves no gauge on its own. Code uses it as a gain between
`0.6` and `1.2` on the negative-valence dimensions: an activating bad thing
lands harder on anxiety and anger, a deactivating bad thing lands more on
sadness. That interaction is appraisal theory and code owns it.

`is_this_new` is the standing-situation control. `standing` makes `fresh`
False, so `apply`'s habituation scales the repeated push down
(`sim/state.py:1187-1197`). `nothing` produces no deltas at all and skips the
`state_log` row the way a quiet tick does today.

### 2.2 The specific appraisals

| id | type | levels / options | grounded in | floor | feeds |
|---|---|---|---|---|---|
| `unfairness` | score | 0 nothing of the kind, 4 a rule applied to her and not to others | `events`, `present`, `his_message` | 0.60 | anger (+) |
| `wanted_and_blocked` | score | 0 nothing she wanted was at stake, 4 something she wanted was taken or did not happen | `events`, `his_message` | 0.60 | sadness (+) |
| `exposure` | score | 0 she was not seen, 4 caught out, laughed at, read properly | `scene`, `events`, `his_message` | 0.60 | shame (+) |
| `achievement` | score | 0 nothing of hers came off, 4 something of hers plainly did | `events`, `scene` | 0.60 | pride (+) |
| `uncertainty` | score | 0 nothing pending, 4 a question or a plan left hanging | `his_message`, `his_side`, `scene` | 0.60 | anxiety (+), curiosity (+), unsaid (+) |
| `holding_back` | choice | `holding_something` / `nothing` | `events`, `his_message`, `already` | 0.50 | unsaid (+) |
| `her_fault` | score | 0 not hers, 4 she did the thing she would regret | `events`, `last_messages`, `already` | 0.60 | guilt (+) |

### 2.3 Him and the contact

| id | type | levels / options | grounded in | floor | feeds |
|---|---|---|---|---|---|
| `warmth_from_him` | score | 0 absent or flat, 2 ordinary, 4 plainly warm and close | `his_message`, `his_side`, `last_messages` | 0.60 | relief (+), validation_craving (-), loneliness (-) |
| `attention_from_him` | choice | `answered_properly` / `answered_thinly` / `read_and_ignored` / `said_nothing` | `his_side`, `last_messages`, `his_message` | 0.50 | validation_craving (-/+), loneliness (+/-) |
| `who_else_has_him` | score | 0 nothing of the kind, 4 plainly spending himself on somebody else | `digest`, `scene`, `events` | 0.60 | jealousy (+), curiosity (+) |
| `his_valence` | score | 0 flat and grim, 2 ordinary, 4 plainly good | `his_message` | 0.60 | `his_mood.valence` |
| `his_arousal` | score | 0 dead on his feet, 2 ordinary, 4 wired | `his_message` | 0.60 | `his_mood.arousal` |

`warmth_from_him` and `attention_from_him` overlap; they are kept apart
because warmth is tone and attention is whether she was answered, and the
gauges they move are different (relief against craving). A build may collapse
them if calibration shows they never disagree.

`his_valence` and `his_arousal` do not go through the weight table. They feed
`note_his_mood` (`sim/state.py:623-644`) with `valence`/`arousal` scaled from
the 0-4 level to the -2..+2 range that function already expects, and
`catch_his_mood` (`sim/state.py:659-692`) runs unchanged. This is the one
place the classifier replaces the role's `his_mood` read directly.

### 2.4 Gauges with no dimension, on purpose

`energy` and `boredom` are movable in the spec but owned by sleep, the block
kind and the world terms (`sim/state.py:115-190`, `config.py:3886-3942`). No
dimension targets them; they stay code-owned. `physical_comfort`, `hunger`,
`fatigue` and `unwell` are absent for Momoka
(`characters/momoka/sheet.json:36-42`). `longing`, `belonging`, `affection`,
`stress`, `surprise`, `awkwardness` and `fondness` are `model_may_move:
False` or owned by a section, so `apply` refuses them anyway and the weight
table may not name them.

For Momoka the movable set is 14: `energy, anxiety, anger, sadness, shame,
pride, relief, loneliness, boredom, validation_craving, unsaid, curiosity,
jealousy, guilt`. Sixteen dimensions (including the two `his_mood` scores)
cover 12 of them; energy and boredom are deliberately left to code.

## 3. The code-owned combination

### 3.1 Normalisation

Each score 0-4 becomes a factor in a fixed range:

- bipolar (`how_good_or_bad`): `x = (score - 2) / 2`, so -1 to +1;
- unipolar (every other score): `x = score / 4`, so 0 to 1;
- a `choice` that fires contributes `x = 1.0`; a `choice` that does not, 0.

A dimension under its floor contributes nothing, whatever `x` would have
been. A missing or unparseable answer is treated the same way and logged.

### 3.2 The weight table

For each dimension, a map of gauge to signed points per unit of `x`. The
magnitudes are small because `apply` caps and shapes everything downstream
and `max_delta_per_update` is 15 (`config.py:4245`), and because the observed
record moves two or three gauges by a few points a tick
(`docs/state.md:93-103`).

| dimension | gauge: points (sign) |
|---|---|
| `how_good_or_bad` | relief +3, sadness -2, anxiety -2 |
| `unfairness` | anger +3 |
| `wanted_and_blocked` | sadness +2 |
| `exposure` | shame +2 |
| `achievement` | pride +2 |
| `uncertainty` | anxiety +2, curiosity +2, unsaid +1 |
| `holding_back` | unsaid +2 |
| `warmth_from_him` | relief +3, validation_craving -2, loneliness -2 |
| `attention_from_him` | validation_craving -2, loneliness -1 (sign flips on the negative options, in code) |
| `who_else_has_him` | jealousy +2, curiosity +2 |
| `her_fault` | guilt +2 |

`delta_gauge = round(sum over cleared dimensions of sign * points * x *
gain)`, capped at `state.appraisal.max_points_per_dimension` per dimension
and at `apply`'s `max_delta_per_update` per gauge once summed. The `gain` is
1.0 except on the negative dimensions that `how_activating` scales
(`sim/state.py`'s negative emotions), where it is
`min + (max - min) * arousal_x`.

### 3.3 Where the table lives

Two keys, and the split is deliberate:

- `config.py:DEFAULTS["typesafe"]["uses"]["state_appraisal"] =
  {"enabled": false, "threshold": 0.6}` -- the one switch, uniform with the
  four live uses (`config.py:723-728`). `0.6` is the universal fallback floor;
  a dimension may not go under it except where section 2 says so.
- `config.py:DEFAULTS["state"]["appraisal"]` -- code's table:
  `max_points_per_dimension` (4), the `gain_from_arousal` pair (0.6, 1.2),
  `weights` (the table above), and `thresholds` (per-dimension overrides of
  the use's floor, because a five-option choice spreads probability the way
  the 28-way `emotion` choice does and needs a lower floor --
  `docs/system-one.md:97`, `sim/emotion.py:179-194`).

`state.appraisal` carries no `enabled` of its own. The switch is the
`typesafe` use; an inert weight table behind an off switch is not a second
switch, and two enables would be a footgun.

Momoka's `characters/momoka/bundle.json` carries only the `uses` row
(`"state_appraisal": {"enabled": true, "threshold": 0.6}`) beside the four
that are there now (`bundle.json:140-157`), unless calibration wants her
weights different from the library defaults.

### 3.4 The dimension definitions in code

The question text, the anchors and the default per-dimension floors are code,
in a new module `sim/appraisal_gauge.py`, for the same reason the GoEmotions
list is code (`sim/emotion.py:43-49`) and the inbound questions are code
(`sim/inbound.py:21-50`): the answer surface is fixed and a config cannot be
allowed to invent a gauge or a level. Config owns the numbers (floors,
weights); code owns the questions. This is the vendor's "structured
instructions over prose".

### 3.5 How a dimension under its floor is treated

- One dimension under its floor: that dimension abstains, contributes no
  delta, and is logged by name and confidence. The rest of the call applies.
- No dimension clears at all: the call is treated as unusable and the role
  runs, because a tick that produces nothing is indistinguishable from a
  failure and the safe fallback already exists.
- `is_this_new` under its floor: `fresh` defaults to True, so a real change
  is not silently discounted. Habituation only fires on a positive `standing`.

## 4. How the mechanical rules survive

They survive because the classifier writes nothing itself. It produces a
`deltas` dict and the existing `State.apply` does the rest. Point by point:

| rule | where it lives today | what changes |
|---|---|---|
| diminishing returns near the ends | `apply`, `sim/state.py:1202-1206` | nothing |
| habituation on a standing situation | `apply`, `sim/state.py:1187-1197` | nothing; `fresh` now comes from `is_this_new` instead of `bool(user_msg_text) or bool(digest_text) or bool(talk)` (`sim/state.py:1880-1881`) |
| stress gain | `apply` -> `_stress_gain`, `sim/state.py:1200, 1045-1058` | nothing |
| per-gauge caps | `apply`'s `max(-cap, min(cap, d))` and `clamp`, `sim/state.py:1186, 1207` | nothing |
| one-way reporting | `wiring_report` reads `state_log`, `sim/state.py:774-782` | nothing; the scorer's states land in `state_log` the same way |
| relationship daily budgets | `apply`, `sim/state.py:1210-1245` | nothing; see section 6, the scorer does not write meters |
| the refusal of computed gauges | `apply`, `sim/state.py:1166-1180` | nothing; the weight table may not name a derived gauge, and `apply` still refuses one if it somehow got there |
| per-gauge `owner` sections | `State.live_gauges`, `sim/state.py:1283-1304` | nothing; a gauge whose owner is off is not in the passed `gauges` and cannot be scored toward |

The one behavioural difference is `fresh`. Today `fresh` is "he wrote, or a
novel digest, or an exchange". Under this design it is the classifier's
`is_this_new`, which is a judgement about the situation rather than about the
tick's inputs. That is the intended improvement (the doc's standing-situation
rule), and it is the one item with no shadow evidence, so it is read off the
live provenance and the habituation log line (`sim/state.py:1208-1209`) after
the switch rather than before it.

## 5. "Derived from context" as a testable acceptance criterion

The ruling has to be checkable, not a slogan. Five tests, each mechanical:

1. **One builder.** `State.appraisal_state()` is the only source of both the
   role's user string and the classifier's `state`. A test asserts the role
   renderer and the classifier are handed the same keys from one list.
2. **No score without a field.** Every dimension's `instructions` names at
   least one key of `appraisal_state()`. A test asserts the name appears.
3. **No free magnitude.** The classifier emits a level (0-4) or an option,
   never a gauge unit. `TypeSafe.ask` sends only `type`, `instructions`,
   `criteria` (`typesafe.py:97-105`); a test parses the outgoing body and
   asserts every question is `score` or `choice` and that code reads only
   `score`/`choice`/`confidence`. The weight table is the only place points
   appear, and it is config.
4. **Every weight is real.** At config load, every gauge named in
   `state.appraisal.weights` is in `State.movable()` (`sim/state.py:712-715`)
   and present in the character's spec; a failure is a named error, the way
   `Config._check_gauges` refuses a gauge missing `kind`/`valence`/`arousal`.
5. **Every delta shows its source.** Each applied delta logs the dimension
   that produced it, the level and the confidence:
   `[state.appraisal] relief +3 (warmth_from_him 4/0.91), validation_craving -2 (warmth_from_him 4/0.91)`.
   A scrape over a run's log asserts no non-zero delta lacks a dimension.

## 6. The parts of the state role that are not the gauges

| part | today | this design |
|---|---|---|
| `reasons` line (`sim/state.py:1933`, read by `already_line` 1801-1813 and `_moment` 1840-1875) | model prose, one line, stored in `state_log` | a code template: a phrase per cleared dimension, joined in a fixed order, capped at 300 chars like today. Still stored in `state_log`, so `already` and `_moment` are unchanged |
| relationship meters (`sim/state.py:1214-1245`, `relationships_brief` 1774-1778) | model deltas, `_match_person`, daily budget | for Momoka, nothing changes: she has no cast and her meters stay code-owned (`_relationship_gravity`, `derive`, `primitives`), and the one meter on him (`him.closeness`) is computed and refused at the write site. A character WITH a cast could have per-person moves scored by the classifier (a `score` per person, key and budget owned by code); that is a later piece for that character (section 12 decision 4) |
| `note_his_mood` / `catch_his_mood` (`sim/state.py:623-692`) | the role's `his_mood` `{valence, arousal, line}` | the two `score` questions in section 2.3 feed `valence`/`arousal`; `line` becomes a code template that quotes his shortest message (section 6), or a tiny role call only if the prose is wanted. `catch_his_mood` is unchanged |
| rupture check (`sim/state.py:1928-1932`) | `self.ruptures.check(data.get("deltas"), user_msg_text)` | unchanged: the scorer produces the same `deltas` and the same `user_msg_text` is passed |
| `_moment` memory write (`sim/state.py:1839-1875`) | deltas + `reasons`, top gauge, per-day cap | unchanged: it receives the scorer's deltas and the templated `reasons` |
| the finish of the call | `store.add_state(...)`, `save()`, `[state] ... | reasons` log | unchanged; the log line now also carries the dimension provenance |

Which of these the classifier keeps, which stays a model call, and which
becomes a code template -- decided by what the classifier can do, not by
preference. Its whole answer surface is a chosen option, a level and a
confidence over one `state` string it is handed; it writes no text and has no
memory beyond that string.

- **Classifier** (`score`/`choice`, no free text): the gauge `deltas`, and the
  `his_mood` valence and arousal. Each is an independent judgement over fields
  the state string carries, which is exactly what jev does.
- **Code template**: the `reasons` line, and `his_mood.line`. Jev cannot write
  either, so a template is the capability-honest answer. `reasons` is a phrase
  per cleared dimension joined in the fixed order of section 2, capped at 300
  characters as today; `his_mood.line` quotes the shortest clause of his
  message. Both keep the shape the readers expect, so `already_line`,
  `_moment`, `his_mood_line` and the fallback role are unchanged.
- **Code, already**: `_talk_outcome` (`sim/state.py:1815-1838`) is a template
  today, not model prose, so nothing about it changes; the talk tick's gauges
  go to the classifier like any other tick. The relationship meters stay
  exactly as they are for Momoka -- no role call -- because she has no cast and
  her one meter (`him.closeness`) is computed and refused at the write site. A
  character WITH a cast could have per-person meter moves scored by the
  classifier (a `score` per person, the key and the budget owned by code);
  that is a later piece for that character, not a reason to keep a call on
  Momoka's tick.
- **A role, only if the prose is genuinely wanted**: if he wants `reasons` and
  `his_mood.line` written rather than templated, they stay one small role call
  per significant tick. That is a preference for prose, and it should be said
  that way rather than as a capability jev lacks.

The rupture check is not part of the `state` role's output. `sim/rupture.py`
`check` reads the deltas and decides mechanically (lines 70-93), and its
`name` call is the separate `rupture` role, which writes `what`, `whose` and
`severity` (lines 95-133). Jev can answer `whose` (a `choice`) and `severity`
(a `score`) and whether a break happened at all, but not the `what` sentence,
so that role is untouched by this design.

The one loss to name plainly: when the prose is templated, `reasons` and
`his_mood.line` are flatter. They are read by the fallback role, by
`already_line`, by `his_mood_line`, and (the reasons line) by her own memory.
That is the non-gauge regression, and section 12 decision 2 states who
decides it.

## 7. The failure path

- `TypeSafe.ask` returns `None` on any failure and never raises
  (`typesafe.py:97-126`). The caller then runs `update_from_llm`, the role,
  exactly as now.
- Nothing is written to `missed_calls`: a 240-370 ms classifier is not a paid
  answer worth replaying (`docs/system-one.md:246-249`).
- Logging is by exception type only. This is a required change: the client
  today logs `f"{type(e).__name__}: {e}"` (`typesafe.py:108-119`), which puts
  the exception message in the log. The build must pass the error through
  `netwatch.redact` (`netwatch.py:16`) or log `type(e).__name__` alone, so no
  context, key or answer text reaches the log.
- A per-dimension abstain is not a failure and does not trigger the fallback;
  it is logged and its delta is omitted.
- A call in which no dimension clears is treated as a failure and falls back,
  so a bad day at the vendor degrades to the current behaviour rather than to
  a frozen state.

## 8. Cost and latency

- **Latency**: one batched call, 240-370 ms, and questions add no latency.
  The doc measured 30 questions at 315 ms against 316 ms for one
  (`docs/system-one.md:14-18`, `tools/typesafe_probe.py:162-176`). A 16-
  question batch is one call and does not lengthen a tick.
- **Input size**: the reconcile fan-out measured 1,090 input tokens for ten
  questions and the ten-question SCAIL-shaped fan-out 807 in / 247 out
  (`docs/system-one.md:22-29`, `ORCHESTRATOR_HANDOVER.md:571-579`). The
  appraisal state is larger than the reconcile state (the full tick context)
  and carries 16 short questions: assume **900-1,300 input tokens**.
- **Call volume**: one call per tick where the role runs now, plus one per
  finished exchange. The role runs only when the tick is significant
  (`scail.py:3434-3483`) and on a talk (`scail.py:3697-3710`). The save is the
  measurement: `state_log` holds one row per update. As of this reading it
  holds **15 states, all on 2026-09-17** (`data/momoka.db`), i.e. tens per day,
  not thousands. Assume **40 calls/day** for a busy day and **200/day** as the
  ceiling.
- **Daily cost at $0.042/Mtok input, output free** (`docs/system-one.md:24`):
  - 40 calls x 1,200 tokens = 48,000 tokens -> **$0.0020/day**, about
    **$0.06/month**;
  - 200 calls x 1,200 tokens = 240,000 tokens -> **$0.010/day**, about
    **$0.30/month**.
  A fallback call adds one role call, which costs far more than the
  classifier; the classifier is not the expensive part.
- **This replaces** a paid role call on every significant tick with a call
  about a third the price and a fifth the latency, so the direction of the
  cost change is down.

## 9. Verification and calibration plan

### 9.1 What exists to measure against

- `State.wiring_report` (`sim/state.py:739-787`) prints per-gauge min/max
  against baseline and flags `NEVER MOVED`, `ONE-WAY: never above rest`,
  `ONE-WAY: never below rest`, and `NEVER RECORDED`. `/gauges` and smoke print
  it.
- `state_log` (`store.add_state`, `sim/state.py:1943`; one row per model
  update) holds every recorded state and its reasons line. `wiring_report`
  reads it.
- The harnesses: `tools/typesafe_probe.py` (re-measure latency, price, the
  three types), `tools/stress_test.py`, `tools/gaps_test.py`,
  `tools/source_test.py`, `sim/sweep.py` (`/sweep`), `tools/smoke.py`.

### 9.2 The record to compare against (measurement, not a gate)

A shadow run is not built, so this is not a step in front of the build. It is
the record the first live scorer rows are read against, gathered from the rows
already in `state_log` plus whatever the role writes before the switch.

1. Record the current role's `wiring_report` min/max and notes per gauge --
   **the record today is one day (15 states), which is thin, so the first
   scorer rows read as a small sample and not as a regression.**
2. Record `state_log` rows per day (call volume) and the role's delta
   distribution per gauge: mean |delta|, sign mix, how often each gauge moved.
   The current 15-state sample already shows the shape: most emotion gauges
   never left baseline (`anger 8/8`, `shame 5/5`, `guilt 10/10`,
   `jealousy 15/15`, `pride 15/15`, `sadness 12/12`), while `relief` ran
   24-72 and `surprise` 6-40.

### 9.3 Calibration and rollback without a shadow run

His ruling is replace without a shadow run, so there is no pre-switch period
where the scorer is called and applies nothing. Calibration and rollback come
from the live path instead, which is possible because the switch is a config
key and every applied delta carries its source:

- **Rollback is one config key.** `uses.state_appraisal` starts `enabled:
  false` in `config.py:DEFAULTS`; only Momoka's bundle turns it on. Turning it
  off is the whole rollback -- no code change. The `state` role is never
  deleted and still runs whenever the scorer is off, returns None, or clears
  no dimension, so there is nothing to un-wire.
- **Calibration is read off the provenance, after the fact.** Every applied
  delta logs the dimension, the level and the confidence that produced it
  (section 5.5), and `state_log` keeps the `reasons` line per update. A run's
  log is therefore a labelled record of what scored what. The three numbers a
  shadow run would have produced are read from it instead: sign per gauge
  against the previous role rows, mean magnitude per gauge, and the
  per-dimension abstain rate. `wiring_report` gives the min/max and one-way
  view over the mixed record.
- **The floors and weights are the calibration knobs.** They are config
  (`state.appraisal.thresholds` and `.weights`), so a gauge that moves too
  little or too much is a number changed and a restart, not a build. The
  starting table is section 2's; the floors come down for a many-option
  `choice` the way `emotion`'s did (`sim/emotion.py:179-194`).
- **The fallback is the safety net, not the calibration.** A call that fails,
  or clears no dimension, runs the role for that tick, so a bad day at the
  vendor degrades to the previous behaviour rather than to a frozen state.

### 9.4 Success criteria, after the switch

1. No gauge that moved under the role stops moving.
2. No new `NEVER MOVED` or `ONE-WAY` note on a gauge that has room to move
   the other way (`one_way_warn_from` 20, `config.py:4252`).
3. Every non-zero delta in a run's log carries a dimension (section 5.5).
4. Fallback rate under an agreed ceiling, proposed 5% of calls.
5. `state_log` still holds one row per update; a quiet tick still writes none.
6. `his_mood` is still written when he writes and left null when he does not
   (`sim/state.py:641-644`).
7. `relief` and `surprise` keep their observed range, since they are the two
   gauges the record shows actually moving.

### 9.5 Gates that must stay green

- `python tools/new_character.py compose momoka --diff` -- 0 keys differ.
- `python tools/new_character.py verify momoka` -- the checks pass.
- `python tools/smoke.py` -- all clear, including the wiring table and grid.

Run them after any config or bundle change. Add the stage's own check: call
`wiring_report` on the live save and read the notes, not the summary.

## 10. Config and wiring conventions

| item | where | value |
|---|---|---|
| the use switch | `config.py:DEFAULTS["typesafe"]["uses"]["state_appraisal"]` | `{"enabled": false, "threshold": 0.6}` |
| her switch | `characters/momoka/bundle.json` under `typesafe.uses` | `{"enabled": true, "threshold": 0.6}` |
| the weight table | `config.py:DEFAULTS["state"]["appraisal"]` | `max_points_per_dimension`, `gain_from_arousal`, `weights`, `thresholds` |
| the questions and anchors | new `sim/appraisal_gauge.py` | code, like `inbound.QUESTIONS` and the GoEmotions list |
| the client | `typesafe.py`, plus a `score` reader beside `choice` and the log redaction | `jev-latest`, key `secerts/typesafe.txt` |
| wiring into the tick | `sim/state.py` `update_from_llm`; client injected as `State(..., typesafe=None)` and set after `scail.py:308` | see the wiring note below |

`Config.REQUIRES`: **no new row is needed.** The switch rides the existing
`typesafe` row (`config.py:7332`, `None` -- the machine and the mind), which
is how the four live uses already work. A `REQUIRES` row is only for a new
top-level section with its own `enabled` flag; this design adds none, so the
`Config` check at `config.py:7530-7546` stays satisfied. The brief asked for a
row; the honest answer is that the row already exists and covers this use.

`tools/isolation.py`: **no new MACHINE entry.** No new path appears --
weights and thresholds are numbers, and the questions are code. The key is
already claimed (`tools/isolation.py:60`, `typesafe.key_file`). If a rubric
file is later put under `prompts/`, it is a mechanism prompt and belongs with
`NEUTRAL`, not `MACHINE`.

The key stays `secerts/typesafe.txt`, beside the OpenRouter key, never in a
tracked config (`docs/system-one.md:250`).

**Wiring note, found while reading the boot order.** `scail.py` builds
`State` at `:236`, before `TypeSafe` at `:308`. A build cannot pass the client
into the constructor at `:236` as it stands. Either set
`self.state.typesafe = self.typesafe` after `:308` (the way `sight.wire` is
called after the runtime builds, `ORCHESTRATOR_HANDOVER.md:433-434`), or move
the `TypeSafe` construction above `:236`. The first is smaller and keeps the
existing order; the `State` constructor should default `typesafe=None` so
`tools/stress_test.py:56`, `tools/situation_test.py:64` and
`tools/character_test.py:113` keep working unchanged.

## 11. Relation to the four live uses and the nightly review

- `reconcile` (item 1): unrelated -- it checks whether a scene claims an
  action. No interaction.
- `inbound_signals` (item 2): a per-message fan-out (`sim/inbound.py`) whose
  `did_anything_happen` decides whether the state role runs at all
  (`scail.py:3435-3442`). This design's `is_this_new` overlaps it: both ask
  whether anything is there. They run at different times (per message against
  per tick), so keep both in Phase 1 and note the overlap. Folding
  `did_anything_happen` into the appraisal call is the later saving direction,
  and it changes when she feels things, so it needs his ruling the way the
  comment at `scail.py:3420` already says.
- `sight_activity` (item 4): unrelated -- what he is doing, read by
  `resident/sight.py`.
- `emotion` (other seams): a `choice` over the 28 GoEmotions labels for the
  VN face (`sim/emotion.py:170-213`). It labels a line for the sprite; the
  gauge scorer reads the tick for the gauges. They sit beside each other. The
  line to hold (`docs/system-one.md:219-224`) is unaffected: the scorer never
  picks a face.
- `sim/appraisal.py` (the nightly `affection` review): a separate judgement at
  a separate cadence. It scores each of his messages for the warmth it left
  (`sim/appraisal.py:130-204`) and feeds the computed `affection` gauge. It is
  **not** the gauge scorer and should not be replaced by it: one is a nightly
  per-message level with a `why` prose line, the other is a live per-tick
  gauge push. They overlap only on `warmth_from_him`.

  The nightly review is the smaller prize and a genuine follow-on: each of his
  messages is already a `score`, and its `why` is the prose candidate for a
  template. If the appraisal call kept its `warmth_from_him` answer per
  message (`appraisal_log`), the nightly review could be rebuilt from the
  record with no call at all. That is a second piece of work, commissioned
  separately; this design only says the relation.

## 12. The decisions, settled by capability

1. **Replace, without a shadow run.** Settled by his ruling. The scorer takes
   the gauges over from the `state` role. `apply` holds every guard rail and
   the scorer writes no text, so the only role outputs that change owner are
   the gauges and `his_mood`'s two numbers (section 6). The role stays as the
   fallback and is never deleted.
2. **The prose.** Settled by capability. The classifier cannot write text, so
   the `reasons` line and `his_mood.line` become code templates (section 6).
   If the prose is genuinely wanted, the same two lines stay one small role
   call per significant tick -- that is his preference to state, not a
   capability jev lacks. The build defaults to templates and leaves the role
   call on the fallback path, so asking for prose is a config choice, not a
   rewrite.
3. **The dimension set and the floors.** Jev can score all 16 dimensions
   (section 2): each is a `score` or a `choice` over fields
   `appraisal_state()` returns, which is exactly its answer surface. The set
   is approved as the starting table; the floors are calibration and move with
   the live numbers (section 9.3), not with a shadow run.
4. **Relationships on a tick with a person in it.** Settled by capability. The
   classifier CAN score a per-person meter move (a `score` per person, with
   the key, the magnitude and the daily budget owned by code), so for a
   character with a cast this could move. For Momoka the question is moot --
   no cast, and her one meter is computed -- so no role call is kept for her.
   A character with a cast gets it in its own design pass.
5. **The nightly `affection` review.** Capability says the per-message `level`
   already is a `score` and can move to the classifier; the `why` is prose and
   becomes a template or stays a role. Not part of this build; named in
   section 11 as the follow-on.
6. **The `is_this_new` gate -- the one surviving policy ruling.** Jev CAN
   answer `is_this_new` (a `choice`, section 2.1). The open question is not
   capability but policy: whether a tick the per-message `did_anything_happen`
   would have woken may be skipped by `is_this_new`, which changes when she
   feels things. It is the same ruling the comment at `scail.py:3420` already
   waits on, and it is his.

## 13. Scope: the files and lines that matter

Read for this design, and the places a build would touch:

- `docs/system-one.md` -- section 1 (the three question types, composite
  scoring), section 2 item 3 (appraisal) and the built note listing the four
  live uses, section 4 (the constraints).
- `docs/state.md` -- the gauges, the meters, the mechanical rules, the store,
  the invariants, the readers.
- `ORCHESTRATOR_HANDOVER.md` -- the ruling of 2026-09-17 09:11, and the four
  live-use entries this sits beside.
- `sim/state.py` -- `apply` (1140-1245, the guard rails and the rel budget),
  `movable`/`gauge_tells`/`delta_schema`/`system_prompt` (712-737),
  `wiring_report` (739-787), `note_his_mood`/`his_mood`/`catch_his_mood`
  (623-700), `_stress_gain` (1045-1058), `gauge_line` (1280-1281),
  `present_brief`/`relationships_brief`/`already_line` (1755-1813),
  `_talk_outcome` (1815-1838), `_moment` (1839-1875), `update_from_llm`
  (1877-1946), the context lines (1889-1914), `_him_key` (586).
- `prompts/state.txt` -- the role's rules, tells and output schema, kept for
  the fallback; the files its forks name (`with_him`, `sees_him`, `contagion`,
  `digest`).
- `config.py` -- `typesafe` (717-729), `state` (3869+), `gauges` (3964-4154),
  `mood_from` (4164-4172), `affection_from` (4188-4205), `habituation`
  (4239-4244), `max_delta_per_update` (4245), `one_way_warn_from` (4252),
  `REQUIRES` (7228-7347, the `typesafe` row at 7332).
- `characters/momoka/bundle.json` -- the `typesafe` block (134-158) and the
  `uses` map (140-157).
- `characters/momoka/sheet.json` -- the absent gauges (36-42).
- `typesafe.py` -- `use`/`ready`/`ask`/`yes`/`choice` (53-154), the new
  `score` reader beside `choice`, and the log lines that need redaction
  (108-119).
- `scail.py` -- `State` built (236), `TypeSafe` (308), `Reconcile` (312),
  `Emotion` (500), the state gate and `update_from_llm` call (3420-3483),
  `on_talk` (3697-3710).
- `sim/inbound.py` (the closest built fan-out), `sim/reconcile.py` (the
  fallback and logging shape), `sim/emotion.py` (a confidence floor per use,
  and why 0.35 for a many-way choice).
- `sim/appraisal.py` -- the nightly `affection` review, for the relation.
- `tools/typesafe_probe.py` -- the latency, price and type measurements.
- `tools/isolation.py` -- `MACHINE`, `typesafe.key_file` (46-127, 60).
- `tools/new_character.py` (`compose --diff`, `verify`) and `tools/smoke.py`
  -- the gates.
- `sim/appraisal_gauge.py` -- **new**, the dimension definitions (section 3.4)
  and the code-owned combination (section 3).
- `tools/appraisal_test.py` -- **new**, the section 5 acceptance tests.
- `netwatch.py` -- `redact` (16), for the `typesafe.py` log fix.
- `data/momoka.db` table `state_log` -- the only calibration record; 15 rows
  on 2026-09-17 at this reading.

Not found, and named in the brief: `docs/AGENT_RULES.md` does not exist in
this tree (its standing rules live in `CLAUDE.md`/`AGENTS.md`). The brief also
calls the role's path `run`/`apply`; `sim/state.py` has no `run`, and the path
is `update_from_llm` -> `apply`.

## 14. The build plan

One pass, in this order, each step behind the gate before the next. The scorer
is off in `DEFAULTS`; Momoka's bundle is the only place it is turned on, and
the turn-on is the last step, so the tree is never in a half-live state.

### 14.1 The client and the config (no behaviour change)

1. **`typesafe.py:106-119`** -- redact the failure detail. Both `self.last_error
   = f"{type(e).__name__}: {e}"` assignments currently put the exception
   message (which can quote the URL and the `state`) into the log and into
   `status()`. Build against `netwatch.redact` (`netwatch.py:16`) or log
   `type(e).__name__` alone, and redact `last_error` the same way. This is
   required by `docs/system-one.md` section 4 and is independent of the rest;
   do it first.
2. **`typesafe.py`** -- add `score(answers, qid)` beside `choice`
   (`typesafe.py:144-154`), returning `(level, confidence)`. `yes` reads a
   `noul` and `choice` reads a `choice`; nothing reads a `score` today, and
   the dimensions need one. This is the one addition to the client; section
   10's table is corrected below.
3. **`config.py:723-728`** -- add
   `"state_appraisal": {"enabled": False, "threshold": 0.6}` beside the four
   live uses. The universal `floor` stays 0.6.
4. **`config.py:DEFAULTS["state"]`** -- add the `appraisal` block:
   `max_points_per_dimension` (4), `gain_from_arousal` `{"min": 0.6, "max":
   1.2}`, `weights` (section 3.2's table), and `thresholds` (per-dimension
   floor overrides). No `enabled` here: the switch is the `typesafe` use, and
   two enables would be a footgun. **No new `Config.REQUIRES` row** -- the
   `typesafe` row at `config.py:7332` already covers it, the way the four live
   uses work.

### 14.2 The new module

5. **`sim/appraisal_gauge.py`** -- the 16 dimensions as code (id, type,
   instructions, anchors or `criteria`, default floor) and the combination
   code. Public surface:
   - `DIMENSIONS`, the fixed question set, like `sim/inbound.py:21-50` and the
     GoEmotions list (`sim/emotion.py:43-49`); config may not invent a gauge
     or a level.
   - `appraise(typesafe, state, config, clock)` -- one
     `typesafe.ask("state_appraisal", state, questions)`, read each answer at
     its floor, normalise (section 3.1), combine through
     `config.state.appraisal.weights` with the `gain_from_arousal`
     interaction, cap at `max_points_per_dimension`. Returns
     `(deltas, his_mood, fresh, provenance)` or `None` when the call fails or
     no dimension clears. `deltas` is an int dict for the existing
     `State.apply`; `his_mood` is `{valence, arousal, line}` already scaled to
     the -2..+2 `note_his_mood` expects; `fresh` comes from `is_this_new`
     (True under its floor); `provenance` is the per-gauge source list for
     section 5.5.
   - `reasons_line(provenance)` -- the template: a phrase per cleared
     dimension in section 2's order, capped at 300 characters.

### 14.3 The wiring in `sim/state.py` and `scail.py`

6. **`sim/state.py:21`** -- `def __init__(self, config, store, clock,
   typesafe=None)` and `self.typesafe = typesafe`. The default keeps
   `tools/stress_test.py:56`, `tools/situation_test.py:64` and
   `tools/character_test.py:113` working unchanged.
7. **`sim/state.py:1889-1914`** -- extract the inline context into
   `State.appraisal_state()` returning an ordered dict of the same values, and
   a `render_appraisal_state(d)` that produces the role's user string in the
   same order. One list of field names drives both, so the test at section 5.1
   can assert they agree.
8. **`sim/state.py:update_from_llm` (1877-1946)** -- when
   `self.typesafe` is set and `ready("state_appraisal")`, call
   `appraisal_gauge.appraise` first. On a non-None result: `self.apply(deltas,
   None, fresh=fresh)`, `self.note_his_mood(his_mood)`,
   `self.catch_his_mood()`, the unchanged `self.ruptures.check(deltas,
   user_msg_text)`, `self._moment(deltas, reasons_line(prov), ...)`,
   `store.add_state`, `save()`, and the provenance log line. On `None`, fall
   through to the existing role call exactly as it is today. The role path is
   not edited, so the fallback is the current behaviour by construction.
9. **`scail.py:236` and `:308`** -- `State` is built at `:236`, before
   `TypeSafe` at `:308`. Set `self.state.typesafe = self.typesafe` after
   `:308` (the way `sight.wire` is called after the runtime builds), rather
   than moving either construction. Nothing runs `update_from_llm` before the
   tick, so a later assignment is safe.
10. **Per-delta provenance** -- log
    `[state.appraisal] relief +3 (warmth_from_him 4/0.91), ...` for every
    applied gauge, from `provenance`. This is the calibration input (section
    9.3) and the section 5.5 test reads it.

### 14.4 The switch and the tests

11. **`characters/momoka/bundle.json:140-157`** -- add
    `"state_appraisal": {"enabled": true, "threshold": 0.6}`. Run
    `compose momoka`, so `config_momoka.json` carries it and `--diff` is 0.
    This is the only step that changes live behaviour, and it is last.
12. **`tools/appraisal_test.py`** -- the section 5 acceptance tests:
    - `appraisal_state()`'s keys and the role renderer's labels come from one
      list and match;
    - every dimension's `instructions` names at least one key
      `appraisal_state()` returns;
    - the outgoing request body carries only `score`/`choice` questions, and
      the code reads only score/choice/confidence;
    - every gauge named in `state.appraisal.weights` is in `State.movable()`
      and in the character's spec;
    - fixed answers normalise and combine to the expected `deltas` (a unit
      test of section 3.1 and 3.2);
    - a dimension under its floor abstains, `deltas` omits it, and a call
      where no dimension clears returns `None`;
    - every non-zero delta carries a dimension in the provenance, and
      `reasons_line` is non-empty and under 300 characters;
    - `fresh` is True when `is_this_new` is under its floor.
13. **Gates** -- `python tools/new_character.py compose momoka --diff` (0
    keys), `python tools/new_character.py verify momoka`, `python
    tools/smoke.py` (all clear). Then call `wiring_report` on the live save
    and read the notes, not the summary, after the first day of scorer rows.

### 14.5 Rollback

Flip `uses.state_appraisal.enabled` to false in the bundle, `compose`, and
restart. The `state` role resumes for every tick; the scorer's rows already in
`state_log` stay as history. No code reverts, and no `state.appraisal.shadow`
flag exists.
