# The stances and the loops -- `sim/attachment.py`, `sim/withholding.py`, `sim/rupture.py`, `sim/spiral.py`, `sim/stress.py`, `sim/stances.py`

Spec of record. Summary: PROJECT.md §7.3-7.5, §10.4-10.5. Dated notes:
HISTORY.md §5.45, §5.49, §5.59, §5.64, §5.79.

The first five are the mechanisms that make a bad day into a bad week and a
mend into something; §8 is a different kind of thing under the same word -- a
ranked table that picks one instruction about what she does with what she has
just seen of him. Each is code deciding *when* and *whether*, with a
model writing *what* only where words are needed. They read each other:
stress multiplies the spiral and the delays; a rupture holds gauges and
feeds threat; threat picks a strategy that changes how she withholds;
withholding aims anger at him; a spiral pays anxiety; the compile settles
them against the record.

**Four of these are off for the second character** (her sheet's
`mechanisms_absent`, his call): the rupture, not answering on
purpose, the attachment stance and the spiral. None of them has fired once in
her whole life -- 127 run directories, no `[rupture]`, `[withhold]`, `[attach]`
or `[spiral]` line in any of them -- and each is written around a history she
has not had: four days, one person, no cast, and an empty ruptures table. The
stress layer and the stances table stay on. Every output of the four is derived
from a live row, so switching them off changes no number that was not already
its resting value; what changed with them is one reader, `/sweep`, which had
been computing the withholding pressure whatever the section said and now shows
no such column for a character who has not got the decision.

## 1. Rupture (`Ruptures`)

- **Noticing** (`check(deltas, his_message, her_message)`, mechanical): a
  jump in the gauges that carry a break (`anger_weight`, `guilt_weight`,
  `shame_weight`, `sadness_weight`) over `min_score`, in a tick that had
  something said in it. A rupture is not a bad mood.
- **Naming** (`name`, role `rupture`): what broke, whose it was, severity.
  Opening one: tension +`tension_per_severity`, guilt (soft cap), scaled
  up by old unmended things (`scar_scale_per`, cap); an event
  (`event_salience`); kv `ruptures` (`max_kept`).
- **While open**: `holds()` = `holds_gauges` (guilt, anger, sadness) --
  they dull at `hold_decay_factor` toward `baseline + hold_floor` and stop
  there (`State.decay`); they are aimed at him (`State.sources`);
  `prompt_text` / `intent_line` carry it; the attachment's threat reads
  it (`w_rupture`, `rupture_hers_factor`: a break she caused threatens
  less).
- **Settling** (`settle(trigger)` on his message, hers, or the day; role
  `rupture_settle`): mended -- closeness ends ABOVE where it was
  (`closeness_on_mend`), tension and guilt off, relief on, a self-memory
  (`memory_weight_mend`); a failed bid -- shame, sadness, tension, and
  resentment (`sentiment.failed_bid_resentment`): it has to hurt or a bid
  costs nothing; worse -- anger.
- **Time** (`age()`): after `scar_after_hours` an open row is a scar:
  closeness off for good (`closeness_on_scar`; cast meters have no
  gravity), resentment (`sentiment.scar_resentment`), an event, a
  self-memory; `scars_in_prompt` of them in her prompt.

## 2. Attachment (`Attachment`, no LLM)

- **Threat** (`threat(silent_hours)`, 0..1): his silence
  (`silence_from_hours` .. `silence_full_hours`, `silence_floor` at an
  hour he is never about, `w_silence`), left on read (`read_left_minutes`,
  `w_read_left`), tension over `tension_from` (`w_tension`), an open
  rupture (`w_rupture`), recent scars (`scar_days`, `w_scar`, cap), the
  unanswered streak (`w_streak`, cap) -- summed, then scaled by the
  attachment sentiment (`attachment_floor` at zero).
- **Episode**: opens when threat holds `engage_from` for `engage_minutes`
  (no flapping); releases under `release_below` or `release_fraction`
  down from the peak; `max_hours`, `max_switches`; kv `attachment`,
  `attachment_log` (`keep`); an event and a self-memory
  (`event_salience`, `memory_weight`).
- **Strategy**: protest (pursue, test, escalate) or deactivate (go cold,
  get busy, minimise). `scores()` from `base` plus signed pulls: each
  belief pulls by what it says (`belief_pulls`: `wont_stay_quiet` +,
  `not_come_looking` -, ...), weighted by evidence (`belief_floor`),
  discounted under strain (`strain_discount`); the last episodes
  (`history_episodes`, `history_weight`, `history_half_life_days`: a
  strategy that worked is reached for); the meters and gauges
  (`w_closeness`, `w_tension_select`, `w_attachment`, `w_resentment`,
  `w_anxiety`). A running strategy that has failed switches, and the two
  directions are not symmetric: pushing gives out on a condition
  (`protest_exhaust_hours` of QUIET, measured from the later of the push
  starting and his last message, so a push he has answered inside the
  window is not one that brought nothing back; `protest_streak_stop`
  unanswered in a row; or shame past `shame_switch`), while going cold
  breaks on a roll that gets likelier the longer it holds and the higher
  her longing or craving climbs (`rebound_min_hours`, `rebound_from`,
  `rebound_p_base` .. `rebound_p_cap`). Either swap costs -- sadness
  (`sadness_on_give_up`) for giving up the push, shame
  (`shame_on_break`) for breaking her own cold front -- and `max_switches`
  caps them.
- **What it does**: `register_line` (a stance comes before a mood),
  `impulse_bonus`, `extra_streak` (`protest_extra_streak`: protest pushes
  past where a calm girl stops), `withhold_pressure`
  (`withhold_deactivate`), `delay_multiplier`, `shape_bias` (curt / open),
  `observable_line` (what a person near her could SEE: the phone, the
  timing), `intent_line` / `situation_line` / `director_line`;
  `note_test(kind, test)` records what a protest checks him for.
- **His message** (`his_message`, `maybe_resolve`): a message is not a
  resolution by itself; the threat has to have actually gone. The stamp
  it leaves on the row is where the exhaustion above measures its quiet
  from. `_close`
  writes the outcome; `_settle_beliefs`: each strategy names in config
  which belief a resolved / failed episode strains or confirms.

## 3. Withholding (`Withholding`)

- **Pressure** (`pressure()`, 0..1): tension over `tension_from`
  (`weight_tension`), anger, shame, sadness, resentment, an open rupture,
  tit-for-tat (he took `tit_for_tat_minutes`; `weight_tit_for_tat`), gone
  cold (`cold_from`, `weight_cold`), where she stands (`standing_secure_
  from`: under it a sulk costs more than she has, `weight_standing_low`;
  over it she can afford one, `weight_standing_high`), the attachment's
  `withhold_pressure`.
- **Deciding** (`due(unread)`: opportunity and cost -- `threshold`,
  `min_gap_hours`, `max_per_day`; `decide`, role `withhold` with
  `messages_shown` and foresight's "what his silence means"): kind, minutes
  (`min_minutes..max_minutes`), why, `breaks_if`. kv `withholding`,
  `withholding_log` (`keep`).
- **Holding** (`tick`): it costs -- every `charge_every_minutes`: unsaid
  `unsaid_per_hour`, awkwardness, guilt (soft caps). `broken_by(text)`:
  `always_breaks` words or `breaks_if_words` of his `breaks_if`.
  `unnoticed_hours` / `irked()`: after `irk_after_hours` with him quiet,
  craving and tension climb (`irk_*`) -- the sulk nobody noticed is worse
  than not sulking. `resolve()`: `resolve_base` decaying
  `resolve_decay_per_hour` (faster unnoticed) is what her own impulse
  must clear to break her silence -- never a lock on her mouth. `cave()`:
  shame (`shame_on_cave`, soft cap).
- **Ending** (`_release`): the clock, his words, her caving, or a new
  decision superseding it. A `silence` consumes his message while it runs --
  `App.maybe_reply` marks it read and her queue does not have it any more --
  and when the clock runs out with him STILL quiet the message goes back into
  that queue, once (`silence_hands_back`, kv `withholding_handed_back`), so
  the pick and her reply plan decide about it again and she may leave it a
  second time. Not when he has written since (the newer message is already in
  front of her), not when she caved, and not when she has spoken to him after
  it. Her situation line says she is not going to answer it while she holds,
  and says it is still sitting there once it is back. The row and the log
  carry `handed_back`. `App.recover_lost_reply` still refuses to put one back
  at a restart, which is what that refusal was written for.
- A live withholding aims anger / sadness at him (`State.sources`) and
  is in her situation block (`situation_line`).

## 4. Spiral (`Spirals`)

- **When** (`due(scene)`): `pressure()` = how far past her own rest
  (`pressure_cap`; not anxiety above baseline, which is zero almost
  always), `seedability()` = how unsettled her standing with each person
  is (`tension_weight`, `standing_weight`, `standing_settled_at`,
  `envy_weight`, `seed_min`), `_stress()` (stress lowers what she has left
  to hold it off), `busy_factor` (fine while she is with them, starts on
  the train home), `min_energy`, `min_gap_minutes`, `max_per_day`.
- **Running** (`run`, role `spiral`): a chain of steps; each `extend`
  roll accelerates (`extend_base` + `extend_per_step`: the one gate in the
  project that accelerates, because that is the thing being modelled);
  `max_steps` = `steps_per_invested` x what the belief it heads for holds
  up, capped `max_steps_hard`; `_pay`: anxiety per step through `_warm`
  (`anxiety_per_step`, `arrived_anxiety`, soft cap), pitch per step. kv
  `spirals` (`max_kept`), `spiral_counts`, `spiral_last_ts`.
- **His answer** suspends (`suspend_for_him`, `reassurance_relief`); the
  same seed can go again; `fade_hours` kills most of them; only the
  compile settles one (`settle(date)`, role `spiral_settle`: the chain
  against what happened -- `borne_out_fit`, `disconfirm_strain`,
  `disconfirm_relief`, a self-memory).
- Readers: `prompt_text` (`in_prompt`), `director_line`, `mood_tag`,
  `impulse_bonus` (`impulse_weight`: an afternoon that went badly with
  them is when she picks up her phone to him).

## 5. Stress (`Stress`)

- **Susceptibility** derived from `characters/tomoe/self_beliefs.json` -- how much of
  her identity is load-bearing and how concentrated (`per_invested`,
  `per_concentration`, `per_anxiety_baseline`, min / max). Not a trait
  anyone wrote down.
- **Load** (`load(silent_hours)`, `load_weights`): unfinished goals, an
  open rupture, the unspeakable (ick), unsaid, the body, belonging below
  par, him (silence to `silence_full`), what is ahead, money
  (`broke_below`), a bad night (`bad_night`); `cost_full`, `charge_full`
  scale the terms.
- **Dynamics** (`step`): `rise_per_hour` up, `fall_per_hour` down, and
  only as far down as the load allows (`floor`, `scale`); `recovery()`
  is real rest (`recovery_base`, `_alone`, `_comfortable`, `_slept`), not
  the absence of load; `exhaustion_from` forces rest.
- **Relief** (`relieve(kind)`): slept_well, bath, diary, post, cried,
  gave_up, goal_got, rupture_mended, warm_exchange, held_by_the_group
  (`held_from`) -- toward the load floor, never through it; one guard for
  all (`relief_gap_default`, `relief_gap_minutes`; kv `stress_relief_ts`).
- **Compounding** (`multiplier(what)`, over `compounds_from`, cap
  `compound_cap`): spiral, body_noise, delay, sleep_cost, shame,
  withdraw -- the terms that feed each other, capped so she comes back up.

## 6. Invariants across the five

- Time does not repair (a held gauge dulls to a floor; an open rupture
  scars); only a mend, a settle, or the compile resolves.
- A message of his is never a resolution by itself (attachment,
  withholding's `breaks_if`, the spiral's suspend).
- Every gate is opportunity and cost; whether the thing deserves it is
  the model's business, in the one call that writes words.
- Nothing here is a lock on her mouth: `resolve()` raises the bar, the
  impulse can always clear it.
- The compile has the last word: spirals, goals, commitments, foresight
  settle against the record, not against how she feels.

## 7. Ops and tests

`/rupture [settle]`, `/attach`, `/withhold [now]`, `/spiral
[now|settle]`; the stress report has no command of its own and prints
under `/gauges`, after the affect grid. `tools/attachment_test.py`,
`tools/stress_test.py`, `tools/source_test.py` (the hold).

## 8. What she does with what she has seen (`Stances`, `sim/stances.py`)

Not a loop and not a mechanism that holds state about a wound: one named
stance out of a ranked table, chosen fresh on every call, that says what she
does with what she has just seen of him. It exists because of a measurement
(`docs/yukarin-meters-plan.md` §2): across 45 consecutive persona calls of one
day, the gauge-derived text was 380 characters of a 35,000-token prompt and 337
of those characters were byte-identical on all 45. The register clause did not
move once in sixteen hours. A band word inside 0.7% of a prompt cannot compete
with the 88% of it that is her voice and his message; an instruction naming one
concrete thing can.

Built for the resident character and off by default (`stances.enabled`): a
character whose relationship is described by cast meters rather than by
relational quantities has nothing for the table to read.

### 8.1 The rules

- **Ranked and first-match.** The first row whose condition holds wins. It is
  the only structure that cannot put two contradictory instructions in one
  prompt, and it is the shape `State.register` already uses.
- **Pinned.** The line goes into her section of the situation block with
  `pin=True`, so the attention gate cannot drop it for being in a section whose
  budget ran out before it was reached. The register clause is pinned with it.
- **It owns the slot.** The line under `ON YOUR MIND NOW`, second to last in
  the prompt, in her own words, was empty on every call of her life: of the five
  action sources in shared code she has none. The stance decides whether that
  line is used and what it names. While a stance holds, the nudge is not
  consulted and the gate's pick does not ride. A stance that says *do not raise
  it* holds the slot EMPTY, which is an instruction too. This is an ownership
  rule in code, not `nudge.enabled` being false, because a setting can be
  changed by somebody who does not know it was load-bearing.
- **Hysteretic.** A stance is entered only after its condition has held for
  `stances.min_minutes`, and the table falling back to "even with him" has to
  hold for `hold_minutes` before the stance she was in is dropped. The two
  urgent rows enter at once: a person who has just been frightened does not
  wait twelve minutes to be frightened. Every other threshold in `mood_tags`,
  `register`, `blends`, `delay_factor`, `impulse.score` and
  `withholding.pressure` is a bare comparison re-evaluated per call, so a
  quantity sitting on one flaps the line between two consecutive generations.
- **The line follows the material.** A stance that names something names the
  thing she actually saw, out of the record -- the charged item's own words, the
  record of hers his message reached -- never a generic line about "something".
- **The default is no line.** "Even with him" adds nothing. An instruction on
  every call is not an instruction.

### 8.2 The table

| rank | stance | condition | slot |
|---|---|---|---|
| 1 | frightened of him | `unrehearsed >= primitives.fright_hard_from` | held empty |
| 2 | put back outside | expelled within `expel_hours` and not readmitted | held empty |
| 3 | carrying something she read and cannot raise | an unspeakable charged item live over `ick.carry_floor`, and awkwardness at or over `carrying_awkwardness` | held empty |
| 4 | held in mind by name | his newest message, inside `settler_minutes`, names a record of hers he could have got nowhere else; once per distinct record | the record he named |
| 5 | sitting on something she could say | a speakable charged item live, unraised for over `sat_on_minutes` | the item, once per item where `name_it_once` is on |
| 6 | outside his notice | evidence he keeps her in mind under `unnoticed_below`, his machine busy, and `active_hours` with nothing toward her | held empty |
| 7 | needling him about a thing that stopped being a shock | a cooled item whose sort she has met `ick.teasable_after_seen`+ times, and `Ick.settled()` at or over `settled_from` | the item |
| 8 | even with him | nothing above holds | not claimed |

**Row 5's instruction is spent once per THING for a character who sees
everything** (`stances.name_it_once`, on for the resident and off for a
character reading a digest). The row holds while an item sits unraised, and it
used to re-fill the one imperative line on every reply until she raised it --
which for somebody inside his machine is most turns of most days, and is how
noticing what is on his screen became a slot rather than a remark. On the
second and later turns over the same item the row renders a second wording
that says she is carrying it and had her chance at it, and claims no slot. The
row itself is deliberately left holding: `settle_discretion` is the only thing
that can pay her for having let a thing go by, and it can see that only
because the stance held over the item, so what is spent once is the
instruction rather than the stance.

Rows 1 and 2 are what the top of the register chain used to say, so the chain
gives them up where a stance table exists and keeps them where one does not:
they say what she DOES, which is not what a register says. Rows 3, 5 and 7 take
over from the three prose headings in `Ick.prompt_text`, which were lists with
no instruction attached; the lists stay for the items she is not acting on.

### 8.3 What it feeds

- **The ledger's credit side.** A discretion stance holding over one item for
  `discretion_minutes`, with the item unraised when it finally cools, is the
  one thing that knows she CHOSE to leave it alone -- an item that simply went
  cold unmentioned might never have been noticed. `settle_discretion()` pays it
  through `Primitives.held_back` on the primitives' own clock.
- **Withholding.** Row 3 is the state `Withholding.pressure` needs and could
  not reach.
- **Reaching out first.** The two rows that enter without waiting -- having just
  been frightened of him, having just been put outside (`URGENT`) -- open the
  gate that decides whether she may start a message at all
  (`sim/initiative.py`): a person who has just been frightened does not wait
  out a backoff. `Initiative.urgent()` reads the settled row from kv `stance`
  rather than asking the table, so consulting it cannot enter a stance nothing
  is about to use, and the override is logged with what the gate had been
  holding her for (`[impulse] override: an urgent stance over '2 unanswered,
  next self-start not before 15:40'`). No other row does anything here.

### 8.4 Ops and instrument

`[stance]` in the log names the stance, the thresholds that fired and the
material it names, and it is written only when it changes. kv `stance` holds
the current row and its pending challenger; kv `stance_named` is the once-per-
record ledger for row 4; kv `discretion` is what she has held back and not yet
been paid for. `data/retired/20260903_235946_meters_build/probe.py` stages each
row's own condition and checks the table returns it: a stance no state can
reach is dead code.
