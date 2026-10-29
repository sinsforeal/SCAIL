
---

## 7. Her state (`sim/state.py` and the feeling layer)

### 7.1 `state.py` `State`: the gauges, the meters, the rules

Holds the gauges (26 for the first character, 21 for the second, whose
sheet removes the four a body in a real world feels and has no circle of her
own, 24 for the fourth, who has a body, a circle and no chat with him;
`state.gauges`:
baseline, decay, `kind` /
`valence` / `arousal`, `tells`, `tags`, and optionally `owner`, the config
section that writes it -- a character for whom `Config.REQUIRES` has switched
that section off is not BUILT with the gauge: `Config._existence_implies`
takes it out of the spec, the way a sheet's `gauges_absent` takes out the ones
she has not got, and says so on the boot line, so the state, the store, the
mood computation, the status line, the prompt the state role is handed, the
tags and `/sweep` are all without it rather than each guarding itself
(`State.owner_off` and `State.live_gauges` stay as the reader's answer for a
section switched off by hand; warmth toward him and missing him both name the
section that holds what she feels toward him, and warmth toward her own
people names the section that keeps what she holds with them, so a character
with no circle has not got it; taking warmth toward him out used to empty the
good/neutral cell of the emotion grid, which the boot said, and warmth toward
her own people now fills it for anybody who has people)) and the per-person meters
(`relationships`); moves them deterministically every loop (`decay`:
drift, the world terms, loneliness under his silence weighted by the
rhythm and the company, his meters' gravity, derived mood and affection,
contagion, the body-settled correction; a gauge an open rupture holds
dulls to a floor instead of freezing) and by model deltas only when
something happened (`update_from_llm` -> `apply`: diminishing returns, a
daily budget on his meters, habituation, stress gain, derived gauges
refused). For a character on the primitives his `closeness` meter is
derived too: `_mirror_primitives_closeness` sets it to the smaller of the
two exposures every pass, the gravity leaves it alone, `apply` refuses the
model's delta on it, and affection reads it there rather than calling the
derivation -- one answer to how close they are instead of two, and a value
`/sweep` can move. Every reader that turns a feeling into behaviour lives here:
`register` (how she answers HIM), `delay_factor` / `compose_factor`,
`mood_state`, `mood_tags` + `blends`, `body_noise`, `felt_hours`,
`affect`, `present_brief`, and `sources()` / `directed_line(who)` -- who
a feeling is aimed at (a rupture or a withholding -> him; a person's
resentment or envy -> them), so a friend exchange gets "NOT AT
RENA-CHAN" and never his register. Invariants: the eight gauge rules in
§16; one owner per gauge; a threshold nobody can reach is dead code.
**Emotional contagion needs a chat with him to be a route at all**: `Config.REQUIRES` assigns it to `with_him`, the paragraph asking what he sounds like and the `his_mood` key of the answer schema are behind a `[[?contagion]]` fork in `prompts/state.txt`, and the three lines of the user message about his message, his read receipts and their chat -- and the one about what she saw of his machine -- are built only for a character who has one. A null line is nothing rather than the four-letter word "None", which is what turning it into a string made of it and what the guard let through into a save. `sim/repairs.py retire_his_mood_once` takes the row out once for a character whose sheet answers `with_him: none`. **And the state role is told how the room went**, not only what was said in it (`_talk_outcome`): how many messages were hers and how many theirs, why it ended, and what code has already charged for it -- a room she never answered in reached this role as the other person's one friendly line and read as a settled plan.

kv `gauges`, `relationships`, `his_mood`, `standing_deltas`, ...; table
`state_log`. `/state`, `/gauges`, `/set`, `/sweep`. **spec:
`docs/state.md`.** history: archive §5.3, §5.45-5.53, §16.1.

### 7.2 `discharge.py` `Discharge`: a gauge at its end is an event

A gauge at its ceiling or floor discharges into a discrete behaviour and
resets to a level (not to rest: the cause has not gone). `state.discharge.rules`,
one per gauge: level, reset, cooldown, behaviour -- `say` (a forced
self-started message with the discharge as the whole hint), `look` (a
forced look at the app), `spiral` (a chain starts), `act` (something in
the room: she cried, gave up on the day, went small -- an event of
salience 3 the next scene must reflect, side effects on other gauges, a
stress relief). Code decides all of it; `App.maybe_discharge` carries it
out; a `say` without the phone falls back to the `act`. Caps
`cooldown_hours`, `max_per_day`. kv `discharges`, `discharge_counts`,
`discharge_last`. `/discharge`. history: archive §5.94.

**7.2b `stances.py` `Stances`: what she does with what she has seen.**

One named stance out of a ranked, first-match table of eight, chosen on
every call from the relational quantities, the ick and her own record. The
line is pinned into her section of the situation block and the stance owns
the slot -- the imperative line under `ON YOUR MIND NOW`, which was empty on
every call of the resident character's life -- filling it with the concrete
thing she saw or holding it empty on purpose. Hysteretic: entered after
`min_minutes` of the condition holding, except the two urgent rows, so a
quantity on a threshold cannot flap the instruction between two
generations. Where the table exists, `State.register` gives up its fright
and territory branches to it and its awkwardness branch drops below the
nine it was masking. Off unless `stances.enabled`; the first character has
no relational quantities for it to read. `[stance]` in the log names the
row, the thresholds that fired and the material; kv `stance`,
`stance_named`, `discretion`. **spec: `docs/stances.md` §8.**
history: 2026-09-04 00:55.

### 7.3-7.5 `stress.py`, `spiral.py`, `rupture.py`: the three stances that sit inside her state

One mechanism each, all three specified in full in `docs/stances.md`.

**7.3 `stress.py` `Stress`: an integrator, not a feeling.**

An integrator, not a feeling: `load` is the weighted sum of what she is
carrying (goals, a rupture, the ick, unsaid, the body, belonging, him,
what is ahead, money, a bad night), susceptibility is derived from how
load-bearing her self-beliefs are, `step` rises fast and falls slowly and
only as far as the load allows, `relieve(kind)` is a discrete release
toward the floor, `multiplier(what)` is the capped compounding the
spiral, the delays and the body noise read. kv `stress_relief_ts`.
`/stress`. **spec: `docs/stances.md` §5.** history: archive §5.59.

**7.4 `spiral.py` `Spirals`: going over something.**

Going over something: code decides when (pressure past her own rest,
who could seed it from her unsettled standing with them, stress, an idle
minute), the `spiral` role writes the chain, each step accelerates and
pays anxiety; his answer suspends, only the compile settles
(`spiral_settle`). `impulse_bonus`: an afternoon that went badly with
them is when she picks up her phone to him. kv `spirals`. `/spiral`.
**spec: `docs/stances.md` §4.** history: archive §5.45.

**7.5 `rupture.py` `Ruptures`: something broke, and whether it mends.**

Noticing a break is mechanical (a jump in the gauges that carry one, in
a tick with words in it); naming it is one call; settling on his message,
hers or the day mends (closeness ends ABOVE where it was), fails (a bid
nobody took has to hurt) or worsens; after `scar_after_hours` an open row
is a scar that takes closeness off for good. While open, the held gauges
dull to a floor and are aimed at him. kv `ruptures`. `/rupture`. **spec:
`docs/stances.md` §1.** history: archive §5.49.

### 7.6 `sentiment.py` `Sentiments`: what people are to her, slowly

Five kinds per person -- `attachment`, `resentment`, `respect`, `contempt`,
`envy` -- accumulated in small amounts (`move`; a sentiment is a hundred
evenings, not one) and eroding with absence toward nothing
(`live`; `sentiment.half_life_days` per kind, `ceiling`). Seeded once from
the meters (`_seed`). **A character whose sheet says she has no chat with
him gets no row about him at all**: `_no_him` refuses it in the read, the
seed, the hand-set and the move, and a reader is handed a fresh all-zero
dictionary that is never saved, so no call site has to handle the absence.
The keys refused are his name on her sheet and the two conventions, because
her relationship table has no row for him and every call site falls back to
the literal one. Readers: `longing(silent_hours)` (attachment to him
times his absence -- the thing loneliness is not), `susceptibility` (whose
mood she catches), `impulse_bonus` (attachment makes her reach; resentment
makes her not), `delay_bonus`, `belonging` (her standing with the circle
times how recently she was among them, the counterweight to him;
`peers`, `last_circle_contact`), `phone_debt` (what being on her phone
with him costs her with them), the spiral's seedability, `State.sources`.
`note_phone_use` keeps a ring of when she physically looked at her phone.
kv `sentiments`, `phone_use`. `/sentiments`, `/set sentiment.<kind>`.
history: archive §5.51, §5.52, §5.90; 2026-09-08 00:20.

### 7.7 `appraisal.py` `Appraisal`: what his messages left her feeling

Once a night as she goes under, only if the day had a conversation in it
(`affection.min_messages` counts the exchange): every message of his since
the last read is scored (role `affection`; hers are context, never
scored). `level()` fades by age and is one input of the affection target.
kv `appraisal_levels`, `appraisal_last_ts`, `appraisal_night`.
The history already on file when the review arrived was scored once, by a tool since retired. history: archive §5.54.

### 7.8 `self_memory.py` `SelfMemory`: what she is still carrying

Her own memories are one of the five stores in `docs/memory.md`, the spec
of the whole memory system; this entry is her side of it.

**Written by the moment, consolidated by the night.** A tick of the state
model whose biggest move is `moment_min_delta` (or whose moves sum to
`moment_min_total`) keeps the model's own `reasons` line as a memory then
and there (`State._moment`; source `message` / `exchange` / `scene`,
feeling = the gauge that moved most, valence from the gauge's own spec, at
most `moment_max_per_day`); an npc moment at `moment_npc_salience` does the
same (source `npc`); the compile authors at most `compile_max_per_day` of
its own and mostly reinforces what the day wrote. Before this every memory
outside promises and ruptures was the nightly narrator's.

Her own memories (table `self_memories`: date, text, weight, feeling,
valence), written by the compile, the spiral, the rupture, the goals,
commitments, scenery. A near-duplicate reinforces instead of sitting
beside (`self_memory.duplicate_jaccard`); `score` fades with a half-life
by weight; `congruence` surfaces the ones that match her mood (feeling
low surfaces the low ones -- the second self-feeding loop, with the
spiral); `for_prompt(cue_text)` is what is above the fade line plus what a
word of his just brought back. `/self`. history: archive §5.42, §5.50.

**A memory written in from a character's own record does not fade at all.**
`STANDING_SOURCES` is the source values that mean "what she is made of rather
than a day she lived through" (`seed`, written by `sim/seed_memories.py` and,
before that module existed, by the one-off script
`yukarin/week/patch_live.py`), and `score` returns the row's weight for those,
for ever -- at the one function every reader of a score goes through, so no
call site carries a guard. The two kinds are chosen for the prompt separately
and get their own slots, so hundreds of biography lines cannot crowd out the
lived days and the lived days cannot bury the biography. The lived ones keep
the fade line and `max_in_prompt`. The standing ones cannot use it, since none
of them fades, and neither recency nor cue overlap can rank them (measured:
§19), so they are chosen by weight and by turn -- weight 5 in every prompt,
the remaining `standing_in_prompt` slots walking the rest in weight order, one
step a character day (kv `selfmem_turn`, stepped once a day and not once a call
because `persona.system_for` builds the prompt twice and smoke requires the two
to match). The first character has no memories of this kind:
hers were seeded once under `backstory` by a tool since retired, whose own
note is an argument for letting them fade. `/remember` prints the two kinds apart.

**How a character read out of a real archive gets those rows** (`sim/
seed_memories.py`, `docs/memory.md` §7a). Her config names the dated
once-events of her past (`character.timeline_file`) and the quoted moments
beside them (`character.memories_file`); the program that runs her calls the
seeder once at boot, and for a character who names no such file nothing runs
and nothing is logged. It writes the timeline only -- a quoted moment is her
record, found when a message names it (`sim/lore.py`) -- and it reads the
moments file to record on each row which of its rows is the same moment of
tape, matched on the episode and cue index within the extraction's own
three-cue drift class. No model is asked anything: the Japanese is the
timeline's and the English reading beside it is its gloss, which is the two
search keys the store wants. `date` holds the day the archive gives, or the
span it bounds the thing by when it gives no day, and a reader shows a month
and a day only for a plain calendar day. `ts` and `last_seen` hold the felt
age, which is an ordering device: the last event of the archive is fixed at
the day before the save's first day, so her remembered life ends where her
lived record begins and the rest runs back at its true distance, keeping the
real intervals of a real life. Every row keeps a `receipt` -- the event's
stable id, the basis its date rests on, every episode and cue index the claim
was found at -- which no prompt reads and which is what makes the row
auditable back to the archive and the write idempotent. Insert-only, keyed on
that id, with a kv marker (`selfmem_seed`) carrying the seed version; a replay
window cannot delete one of these rows, because its stamp is a felt age and
not the hour the bot wrote it (`Store.retire_window`).

**What lands in `text` is in the language the character writes.** Fifteen
calls in ten modules write memories and most build their sentence in English; `add()` is the
one door they all go through, and it was already asking the model for the same
line in the other language to use as a second search key. When the line arrives
in the language she does not write, the two change places -- the rendering is
what she reads, the original becomes the hidden key -- so nothing extra is
asked and retrieval still works from either language. `hers()` reads
`character.writes_to_him`; for the character who writes English nothing moves.
`feeling` is rendered the same way and dropped rather than left in the wrong
language. `repair()`, called from the compile, puts right what is already in
the table (swapping where the rendering is stored, asking otherwise, 20 a
pass), and `for_prompt` and `search` skip a row she cannot read until it has.
The second character's 252 seeded memories come from the hand read of the tape
(§19).

### 7.9-7.10 `derive.py`, `sweep.py`: the two instruments that ask what a number is worth

Neither is in the loop: one works a meter out of the record rather than
believing what is stored, the other asks what would behave differently if a
value moved.

**7.9 `derive.py`: his meters from the record.**

`derive_him(config, store, now_ts)` works closeness / standing / tension
out of the message record alone (half-life weights, quiet days), and
`apply_if_new` writes them once unless they were derived already or set by
hand (kv `relationship_derived`). Its closeness is not consulted for a
character on the primitives, where how much of each other they have seen
owns that meter; standing and tension still drift toward it. `/derive`.
history: archive §5.38.

**7.10 `sweep.py`: does a value do anything.**

Sweeps a gauge (or his meters) across its range and asks the code-side
readers what they would do -- read delay, compose time, register, impulse
score, withholding pressure, shape, posting mode, the wonder gate's
curiosity verdict -- restoring the gauges after every probe; a value that
moves none of THOSE is DEAD. The felt affect and the tag count are in the
table and not judged: they are arithmetic over the gauge spec, every gauge
with a valence moves them, and while they counted the DEAD line could
never print. `/sweep [gauge|him|all]`, `tools/sweep.py`. history: archive §5.83.
