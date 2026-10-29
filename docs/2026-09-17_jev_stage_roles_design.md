# Design: moving the director and the judge-shaped stage roles onto Jev (System One)

2026-09-17. Design only: nothing in code, config or prompt is changed by this
document. It was built the same day -- thirteen of the twenty-one roles are in
for Momoka (`scene_director` live, twelve left off), six were tested and stay on
their role, and `rupture` is blocked on a ruling. The build record is
`docs/2026-09-17_jev_stage_roles_implementation.md` (status, the four findings,
per-role notes) and `docs/2026-09-17_jev_stage_roles_build_notebook.md` (the
numbers). Companions: `docs/system-one.md` (what the service is and what one
call returns; its section 2.4b is the use table) and
`docs/2026-09-17_gauge_appraisal_capability_revision_report.md` (the capability
method this repeats).

## 1. Decisions (his rulings, 2026-09-17)

- **Withhold is off for Momoka.** A visual novel has no "she chooses not to
  reply": the player advances and she answers. `withholding` and the `withhold`
  role come off her build.
- **No `quality_rewrite` and no `editor`.** The draft guard and the continuity
  editor are not part of her build. `quality.enabled` and
  `delivery.editor_enabled` go false.
- **The director moves.** The `scene_director` staging is a closed set of
  choices and moves to Jev.
- **The judge-shaped roles and the splits move**, listed in section 3.
- **No shadow mode.** Each move is checked with light tests against output the
  system has already produced, before it is trusted (section 6).

The two "director" names are not the same role and the distinction matters:
`scene_director` (`sim/scene.py`, the staging: place, background, camera,
transition, mood, track) is the closed-set judge and **moves**; `director`
(`prompts/director.txt`, the world's `sensory`/`activity`/`events` prose) is
generation and **stays a role**.

## 2. What Jev is, in the terms the design uses

One request to System One carries a `state` (everything the judgments may see)
and a batch of named questions. A question is one of three types:

| type | carries | returns |
|---|---|---|
| `choice` | `instructions` + a `criteria` map option -> one-line meaning | the chosen option, a probability per option, a `confidence` 0-1 |
| `score` | `instructions` + a scale with anchors | a level (a float, e.g. 1.04), a probability per level, a `confidence` |
| `noul` | `instructions` (optional yes/no criteria) | yes/no as a probability; **no confidence** |

Questions are answered independently and in parallel, so a batch adds no
latency (30 questions 315 ms against 316 ms for one). Jev does not write prose,
does not extract text, carries no state between calls, and can only use what is
in the `state` string. **Code owns the policy**: Jev supplies the judgment and
its confidence, code supplies the threshold and the action. The client is
`typesafe.py` (`use`, `ready`, `ask`, `yes`, `choice`, `score`); a failed call
returns `None` and the caller keeps the gate it already had.

## 3. The roles in scope

Each row says what the role returns today, which part moves, the `state` the
questions see, the questions, and what code does with the answers. Everything
not named as moving stays a role.

### 3.1 Direct moves (the output is already a closed set)

| role | moves to Jev | state | questions | code's policy | fallback |
|---|---|---|---|---|---|
| `scene_director` | `place`, `camera`, `transition`, `mood`, `bgm` | the scene brief, the mood, the place catalog, the track catalog (`sim/scene.py:390-395`) | `place` choice over the catalog + `none`; `camera` choice; `transition` choice; `mood` choice; `bgm` choice over the ids + `none` | `place` -> background through `places`; `mood` -> track through `bgm_for`; a place not in the catalog is dropped | the deterministic staging, `SceneDirector._fallback` (`sim/scene.py:370`) |
| `which_one` | `chosen` | the candidate table (`prompts/which_one.txt`) | one `choice` over the candidate ids + `unsure` + `none` | null/unsure keeps the existing branch | the existing role call |
| `wonder_answer` | `verdict` | the question, his answer, the evidence | one `choice` over `confirmed/disconfirmed/dodged/unclear/not_answered` | as today | the existing role call |
| `rupture` | `broke` (noul), `whose`, `severity` | the exchange and her gauges | `broke` noul; `whose` choice (`his/hers/both`); `severity` score 1-5 | `check` keeps its mechanical read of the deltas; `severity`/`whose` feed it | the existing role call; the `what` sentence stays the role |
| `rupture_settle` | `outcome` | the rupture and the exchange | one `choice` over `mended/tried/worse/nothing` | as today | the existing role call |
| `digest_judge` | `best` | the candidate digests | one `choice` over the candidate numbers + `-1` | `-1` means none, as today | the existing role call |
| `said_when` | `kind` | his message and the schedule windows | one `choice` over `open_now/scheduled/unavailable` | as today | the existing role call; the `quote` stays code or a role |
| `intent` | `kind` | his message and the thread | one `choice` over the nine labels | as today | the existing role call; `about`/`test`/`question` stay a role |
| `lookup` | `kind` | his message and the thread | one `choice` over the twelve kinds | as today | the existing role call; `term`/`name` stay a role |
| `foresee` | `reply_p`, `reply_minutes` | his message, the thread, his rhythm | `reply_p` score 0-4 (code scales to 0-1); `reply_minutes` score over bands | as today | the existing role call; `tone`/`plan` stay a role |
| `expect_him` | `found` (noul), each `confidence` | the record | `found` noul; one `score` per expectation | as today | the existing role call; the `what`/`quote` extraction stays a role |
| `habits_him` | each `confidence` | the record | one `score` per habit | as today | the existing role call; the `what`/`words` stay a role |
| `approach` | `risk` | the event and her state | one `score` 0-3 | as today | the existing role call; `subject`/`angle` stay a role |
| `coherence` | whether a seam of each `kind` exists, `severity` | the seam and the record | one two-option `choice` per kind; one `score` per kind | any red flag over its threshold opens the existing path | the existing role call; the `what`/`where`/`record` sentences stay a role |
| `affection` | `level` | the per-message record | one `score` 5-95 (or 0-4, code scales) | the band clamp is already code (`sim/appraisal.py:193`) | the existing role call; the `why` stays a template or a role |

### 3.2 Splits (the judgment moves, the prose stays a role)

| role | moves to Jev | stays a role |
|---|---|---|
| `recall` | `clarity` choice over `clear/hazy/faint/none` | the `memory` sentence |
| `settle_beliefs` | `borne_out`, `worn` scores | the note put in front of her |
| `ick` | `strain`, `weight`, `circle`, `intimate` scores | the note |
| `spiral` | `terminus` choice over the belief ids; `arrived` noul | the `step` sentence |
| `wonder` | `kind`, `belief` choices | the question text |
| `reconcile` | already moved (`sim/reconcile.py:341`) | the `fixed` text |

`reconcile` is listed only to mark it as done; the other five are new splits.

## 4. The off-switches

- `withholding.enabled: false` (DEFAULTS `True`, `config.py:2745`). Also drop
  `withhold` from `language.material_roles` (`config.py:659`).
- `quality.enabled: false` and `quality.use_model: false` (her config has both
  true).
- `delivery.editor_enabled: false` (her config has it true).
- Once Jev serves `scene_director`, `scene_director.use_model: false` so the
  role call cannot come back.

None of these removes code; they are config, and each is the rollback.

## 5. Never moved to Jev

Every create-shaped role: `persona`, `director`, `diary`, `weekly`, `reflect`,
`reflect_cast`, `morning`, `anticipation`, `revise`, `revise_self`,
`quality_rewrite` (off), `devoice`, `gloss`, `observer`, `voice`, `peer_reply`,
`episode_account`, `episode_cards`, `transcript_digest`, `watching_digest`,
`character_digest`, `timeline`, `phone`, `downloads`, `note_read`, `vault`,
`eroge_digest`, `taste`, `x_account`, `vision_photo`, `vision_x`, `import_day`,
`sleep`, `lookup_gist`, `search_gist`, `him_profile`, `schedule`. A classifier
would either fail or flatten her.

Two more are excluded on capability, not shape: `commit`/`commit_him` (the
`what` is extraction) and `works` identify (`her_part_verdict` is a
deterministic two-table lookup; Jev would guess where code already knows).

## 6. How each move is checked (light tests against existing output)

No shadow mode. For each role, take the calls the system has already logged,
rebuild the `state` and the questions from the same inputs, ask Jev, and compare
its answer to the answer the role gave. The evidence is the record itself:
`logs/<run>/llm_calls.jsonl` holds each role's prompt and answer, and the save
holds the derived rows (`scenes`, `state_log`, `messages`, `days`).

A move passes when, over the sampled calls:

1. **Agreement.** The Jev answer equals the role's answer at or above the
   role's bar, and the disagreements are inspected by hand, not just counted.
2. **Confidence separates the errors.** The wrong answers sit below the proposed
   threshold and the right ones above it; if they do not, the threshold or the
   question wording is wrong, not the service.
3. **Latency and cost.** One batch, measured, against the role's own call.
4. **The fallback is safe.** With the use switched off, or with a forced
   failure, the role path is byte-identical to today.

Bars are per role and set before the test: `scene_director` place agreement is
the highest bar (a wrong background is visible), `coherence` and `rupture` are
checked for false negatives first (a missed break costs more than a spurious
flag), and the `score` moves are checked for rank agreement rather than exact
level. The test tool is `tools/jev_stage_test.py` (read-only; calls Jev; never
imported by the runtime), built like `tools/typesafe_probe.py`.

## 7. Risks and caveats

- **A `noul` carries no confidence.** Anywhere a threshold must travel with the
  answer, use a two-option `choice`, not a `noul`.
- **No free-text extraction.** A quote, a name, a date is generation; it stays
  code or a role. The moves above move only the label or the number.
- **No state between calls.** Everything a question needs goes in the `state`;
  independent questions go in one batch; chain only when a later question needs
  something an earlier one found.
- **No free-text names to roster people.** `_match_person` stays code; Jev
  answers about a key it is handed.
- **Unbounded integers are code's.** Jev returns a level; code scales and
  clamps.
- **Not a provider fallback.** Jev sits beside the provider. A failure returns
  `None` and the existing gate decides, exactly as today.

## 8. Deferred (proposed, not in this scope)

The gates that skip a whole role call were proposed with this review and are not
part of it: a "does his message name something she does not know" gate before
`lookup`/`recall`, a "did he commit to anything" gate before
`commit`/`commit_him`, and a "is there a real gap" gate before `wonder`. The
draft-inspector gate is moot here because `editor` and `quality_rewrite` are
off. Each is one batched Jev call in front of a role that would otherwise run;
they are worth their own design once the moves above are live.
