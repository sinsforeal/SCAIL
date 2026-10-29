# `sim/state.py` -- the gauges, the meters, and the rules they live by

Spec of record. Summary and pointers: PROJECT.md §7.1. Dated notes:
HISTORY.md §5.3, §5.45-5.53, §5.57, §5.89, §16.1.

## 1. Purpose

One object holds what she feels (25 gauges, 0-100; 21 for a character
whose sheet names gauges she does not have -- the second character's
`gauges_absent` drops hunger, fatigue, physical comfort and being unwell)
and what people are to
her (per-person meters), moves them by rules code owns and by deltas a
model writes only when something happened, and answers every reader that
turns a feeling into behaviour: how fast she reads, how long she takes to
type, what register she answers him in, what shape a message takes, what
face she shows, what her prompt says she feels.

## 2. The gauges

`state.gauges` in config, one entry each: `baseline` (rest),
`decay_per_hour`, `kind`, `valence` (-1/0/+1), `arousal` (-1/0/+1),
`tells` (what the state model is told the gauge means), `tags` (level ->
the words her prompt uses). Kinds:

| kind | gauges | what it is |
|---|---|---|
| emotion | anxiety, anger, sadness, shame, pride, relief, jealousy, guilt, awkwardness, surprise, longing, fondness | has an object, fades in hours, feeds mood |
| drive | loneliness, boredom, validation_craving, unsaid, curiosity, belonging | appetitive: wants something; weakly feeds mood |
| body | energy, physical_comfort, unwell, hunger, fatigue, stress | owned by health / body / situation / stress |
| derived | mood, affection | computed from the others; refused at the write site |

`Config._check_gauges` refuses to start on a gauge missing `kind` /
`valence` / `arousal`. `affect_report()` prints the valence x arousal grid
and names an empty cell: an empty cell is a feeling she cannot have (the
bad/deactivating corner was empty once, which is why nothing could put her
mood down).

## 3. The meters

`relationships` (kv): per person `closeness`, `standing`, `tension`, plus
the sheet fields merged from `data/cast.json` (role, stance, rhythm,
influence, ja, reading, calls). His entry (`_him_key()`) also carries the
sentiments (`sim/sentiment.py`) and is the one `sim/derive.py` can work out
from the record. Cast meters have no gravity: what a scar takes off stays
off. His drift toward what the record supports (`_relationship_gravity`).

For a character on the primitives, `closeness` on his row is not a meter of
its own: `_mirror_primitives_closeness` sets it to the smaller of the two
exposures (`docs/primitives.md` §3) on every pass, the gravity skips it, and
`apply` refuses the model's delta on it the way it refuses a derived gauge.
Before that it was a second number for the same thing -- worked out from the
message record, nudged up by the model's whole daily budget, and read by
nothing, because affection called the derivation directly and went round the
meter. Everything else that reads the meter (the attachment stance's selection,
the reports, the prompt lines) now gets the figure the events support.

## 4. Movement

### 4.1 Deterministic, every loop: `decay(silent_hours, world)`

Per elapsed hour since `last_decay_ts`:

- drift toward baseline by `decay_per_hour` (derived gauges skipped);
- a gauge an open rupture holds (`rupture.holds_gauges`) drifts at
  `rupture.hold_decay_factor` x its rate toward `baseline +
  rupture.hold_floor` and stops there -- dulls, never freezes, never files
  away (anger sat at 81 through a night's sleep before this rule);
- the world terms (`state.world`): weather on comfort, sleep on energy,
  the block kind on boredom, exams ahead on anxiety, being read and
  ignored on craving and anxiety (`impulse.read_ignored_minutes`);
- loneliness climbs `loneliness_per_silent_hour` after 2 silent hours,
  weighted by how much of him she expects at this hour (the `usual_w`
  world term, from the rhythm) and by who is with her (`note_company`,
  `state.company`), and the people in the room settle it toward rest;
- `_relationship_gravity`, `_derive_affection`, `_derive_mood` (lagged:
  `state.mood_from`), `catch_his_mood` (contagion: `contagion`,
  scaled by `Sentiments.susceptibility`, stronger downward),
  `_body_settle_check` (`state.body_noise`: when body noise drops from
  past `report_from` to under `clear_below`, part of the anger / anxiety
  / sadness that was really hunger or exhaustion settles, `relief`, once,
  cooldown; `body_settled_line` tells the next state call).

### 4.2 Model deltas, only when something happened: `update_from_llm` -> `apply`

The `state` role (`prompts/state.txt`) sees the scene, the events, his
message, the digest, his side, a finished exchange (`on_talk`), the
`gauge_tells` and `delta_schema` rendered from the spec (so they cannot
drift from the gauge list), `already_line` (the last reasons, so the same
thing is not charged twice), her mood tags and body noise line. It
returns deltas per movable gauge (`movable()`), relationship deltas, and
reasons. `apply` enforces:

- `max_delta_per_update`; `diminishing_returns` near the ends;
- a derived gauge is refused with a log line (`refused_line` shows what
  the model kept trying to write this run);
- `relationship_daily_budget` on his meters (kv `rel_delta_spent`);
- habituation (`state.habituation`, kv `standing_deltas`): the same
  delta for the same standing reason again is worth less, logged as
  `[state] habituated`;
- stress gain (`_stress_gain`): stress amplifies what lands badly, only
  upward, only the bad direction;
- `one_way_warn_from`: a gauge the model only ever moves one way is
  reported by `wiring_report`.

Mechanical moves used everywhere else: `_settle(gauge, amount)` (toward
rest, never past it), `_warm(gauge, amount, soft_cap)` (up, losing value
near the cap), `_nudge(gauge, amount, soft_cap, soft_floor)` (signed, both
ends), `his_attention()` (he answered: craving fed a little before the
model reads the tone), `talk_relief(who, rounds)` (a conversation is
company after the fact), `things_happened(events, social_salience)`
(salient events leave things unsaid: `unsaid_per_salience`,
`unsaid_social`), `_him_tension(amount)` (withdrawal can build from
neglect outside the daily budget).

## 5. Readers (code-owned; the reason a feeling exists)

| reader | from | feeds |
|---|---|---|
| `register()` | tension, mood, craving, energy; the attachment stance first; the body (`situation.register_line`) | the persona's register line, the reactions (`mood_delivery.*`) |
| `register()`, where a stance table exists | the same, minus fright and the territory, which the stance owns (`sim/stances.py` rows 1 and 2); the awkwardness branch sits below the nine it used to mask | the same |
| `delay_factor()` / `compose_factor()` | tense, low, tired slower; craving faster; fatigue (`situation.delay_multiplier`); attachment | read delay (`Rhythm.noticing_seconds`), typing seconds (`Delivery`) |
| `mood_state()` | mood valence vs baseline over `mood_from.max_swing`, instantaneous arousal | raw / low / flat / off / even / alright / keyed up / bright / buzzing: the persona, the reactions' bands |
| `mood_tags()` + `blends()` | the `tags` per gauge (the most extreme fitting tag: highs from the top down, lows from the bottom up); `state.blends` pairs (both up at once, named) | every prompt's "you feel" |
| `affect(axis)` | signed deviation from rest weighted by kind | the sweep, the affect grid |
| `body_noise()` / `body_noise_line()` | hunger, fatigue, energy, comfort, unwell | misattribution both ways: the state prompt and the persona |
| `felt_hours(hours)` / `felt_gap_text` | the gauges that make waiting hurt; `Rhythm.silence_factor` | how long his silence feels, never a decimal |
| `present_brief(scene)` / `relationships_brief()` | who is with her and what they are to her | the state and director prompts |
| `his_mood()` / `his_mood_line()` | `note_his_mood` from the appraisal / the message read, faded | what she has noticed vs what she has caught |
| `sources()` / `directed_line(who)` | an open rupture and a live withholding -> him; a person's resentment / envy -> them (`state.sources`) | the friend exchanges ("NOT AT RENA-CHAN..."), the persona (`_directed`) |
| `gauge_line()`, `wiring_report()`, `affect_report()` | the spec and `state_log` | `/state`, `/gauges`, smoke |

`/sweep` (`sim/sweep.py`) sets each gauge to 0 / rest / 100 and asks ten
probes what they would do: her read delay, her composing time, her
register line, the impulse score, the withholding pressure, the shape she
would draw, the posting mode, the wonder gate's own last gate
(`Wonder.pull`, curiosity over its rest, because the day's cap and the
cooldown in front of it hide that reader on most probes), her felt
valence and her mood-tag count. DEAD is judged on the first eight only.
The last two are arithmetic over the gauge spec -- the felt affect is a
weighted sum of every gauge's declared valence, the tag count follows any
gauge past its threshold -- so every gauge moved them by construction and
the DEAD line could never print. They stay in the table as information.

## 6. Store

kv `gauges`, `gauges_ts`, `relationships`, `his_mood`, `rel_delta_spent`,
`rel_gravity_ts`, `standing_deltas`, `body_noise_prev`, `body_settled_note`.
Table `state_log` (ts, date, gauges json, reasons) -- one row per model
update, i.e. when something happened; a night asleep may add none. Log
`[state]`, `[contagion]`, `[stress]`, `[rupture]`.

## 7. Invariants and edge cases

1. `mood` and `affection` are computed, never written. `/set` refuses a
   derived gauge; affection may be set by hand and drifts back to its
   target at inertia speed. His `closeness` is computed too for a character
   on the primitives, and the model's delta on it is refused at the same
   write site (`refused_line` shows it as `him.closeness`).
2. One owner per gauge: health -> `unwell`; situation -> `fatigue`;
   stress -> `stress`; sentiments -> `longing`, `belonging`; what she holds
   with her own people (`cast_bond`, `tomoe/cast_psych.py`) -> `fondness`;
   nothing else writes them.
   A gauge may NAME its owning section (`owner`), and then a character for
   whom that section is switched off does not have the gauge at all: it is
   dropped from her spec at load, the store stops holding it, the mood
   computation stops averaging in a constant, and `/sweep` does not have to
   call it dead. `affection` and `longing` name the warmth-toward-him
   section; `fondness` names the cast-bond one.
3. A threshold nobody can reach is dead code: before branching on a level,
   `SELECT` it from `state_log`. `mood < 30` never executed in 112 states.
4. Measure deviation from rest, signed. A term measured only above its
   baseline is zero almost always because a gauge sits at its baseline.
   `State.over_rest(gauge)` is that number in gauge units (the stress,
   attachment, withholding, approach, ick and snoop readers take it from
   there); `State._room(gauge, spec)` is the rest, the reading and the room
   on the side it sits, for the three readers that want it as a fraction of
   what was possible in that direction.
5. A release settles at the baseline, never through it. A mechanical bump
   loses value near its cap. Nothing flat-adds to a 0-100 gauge.
6. Every gauge needs a reader. Adding one: config entry with the four
   fields and `tells`; a reader in this file or a module; `/sweep` proves
   it; `prompts/state.txt` needs no edit (the tells and schema render).
7. A held gauge dulls and stops at `baseline + hold_floor`; below the
   floor it is left alone (a gauge that was low is not pushed up).
8. `loneliness` has more than one owner on purpose (his silence, the
   company, the talk relief) -- all in this file.
9. The first decay after a boot uses the saved `last_decay_ts`, so a
   restart neither skips nor doubles an hour.

## 8. Ops and tests

`/state`, `/gauges` (the affect grid, then the stress and appraisal
reports), `/set <what> <0-100>`, `/sweep [gauge|him|all]`;
`tools/smoke.py` prints the wiring table and the grid;
`tools/gaps_test.py` (blends, body-settled, surprise, wet), `tools/
source_test.py` (the hold, the sources), `tools/stress_test.py`,
`tools/discharge_test.py`.

## 9b. Warmth toward her own people (`fondness`)

The good/neutral cell of the grid held one feeling, warmth toward him, and
nothing else. When the fourth character's warmth toward him was taken out
(her sheet gives her no chat with him, so the section that would move it does
not run), the cell went empty and her boot said so -- a girl with
friends who could not feel fondness for them. `fondness` fills it, for every
character who has a circle and for no one else.

**What it is, and what it is not.** `belonging` is her STANDING in the group:
how held she is, whether they could leave her out, weighted by how recently
they had her. It is a drive and it wants something. `fondness` is warmth toward
particular people: the pleasant residue of having been with one of them. She
can be fond of two friends while feeling on the outside of the group, and the
grid needs both. Family counts here and does not count in `belonging`, which is
about the people who could exclude you.

**Owner.** The section that already keeps what she holds with them
(`cast_bond`, `tomoe/cast_psych.py`), which is `in_world` in `Config.REQUIRES`.
A character with no circle has the section off, and the load then drops the
gauge out of her spec entirely: she does not have the feeling, rather than
resting at a constant nothing can move. Four things raise it -- a thing between
them got sorted, they did what they said they would, she told one of them
something real, an ordinary exchange that broke nothing -- and three take it
off: a new break, a repair of hers they did not take, and a promise they missed.
All seven are moments that module already reads, and all of them go through
`_warm` / `_nudge`, so nothing moves a gauge a character has not got.

**Readers.** Its own tags reach `mood_tags()` and so her situation block, her
turns with her own people and the moment the pick is asked at; being an emotion
with a positive valence, it feeds the computed mood like any other; and it is
the term that stops her leaving one of her own on read
(`cast_psych.leave_it`, `cast_bond.leave_weight_fondness`), which is the
behaviour reader `/sweep` needs to not call it dead.

## 10. What the feeling line is allowed to carry

`situation_block.feel_tags_max` caps the "you feel:" line. 0 is no cap, which
is the first character's setting. It matters more than a cap usually does,
because the named feelings are inserted at the FRONT of the list and everything
after them is what the cut discards: her mood state, the four gauge levels, and
the tail lines (a lot left unsaid today, curious what he is up to, the jealous
edge, squirming). At a cap of 5 the second character's whole feeling line was
five named feelings and nothing else, with unsaid at 98.6 never reaching her
prompt or any of the fourteen mechanism prompts that read `mood_tags()`. Hers
is 12: her standing set is energy, mood, up to two blends and four levels, so
12 admits that plus about five named feelings and the tails, and it is still a
cap -- at the fullest state that has been measured she offers eighteen.

**A gauge with no writer for this character does not get a tag.** `belonging`
is the case that made the rule: `Sentiments.belonging` returned
`belonging_floor x 100` for a character with no peers, which cleared its own tag
threshold of 22, so "on the outside of them lately" was permanently on and held
a fifth of a five-item line for good -- while its two behavioural readers, the
impulse and the stress load, were being handed a constant. It returns None now,
the writer skips it, and her config rests the gauge at 0 with no tags. A floor
is not a feeling.
