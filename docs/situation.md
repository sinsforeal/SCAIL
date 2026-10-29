# `embodied/situation.py` -- a situated body: the map, journeys, fatigue

Spec of record. Summary: PROJECT.md §8.3. Dated notes: HISTORY.md §5.84,
§5.85 (family and the car), §5.19 (body), §5.89 (rain).

## 1. Purpose

"I am tired and the room is hot and I still have to answer" as a
persistent constraint on every action rather than a tag. Where her body
is, continuously; what moving it costs; what the world does to her on the
way. No LLM anywhere in it: the director is TOLD where she is.

## 2. The place graph (`data/places.json`)

Nodes she can be at (id, name, keywords, kind) and edges with a `mode`
(walk / bike / train on a named `line` / car) and `minutes`. `resolve
(location, activity)` maps the free text the schedule or the director
writes to a node by keyword (`environment.transit_keywords` mark "in
transit"); text that matches nothing leaves her where she was. `route
(a, b)` is BFS by hops; a place the map cannot reach gets the unknown-trip
leg. `characters/tomoe/map.json` is the human-readable map (addresses, her line
and its stops) the prompts get; this file is the one the body walks.

`resolve` takes the LONGEST keyword it finds, which is a trap worth knowing:
`school` carried `library` among its keywords, so "the library at 9 with
Aya" -- a public library ten minutes from her flat, in the summer holidays --
resolved to the school in Nishi-Ikebukuro, 32 minutes away. The ward
library is its own node now and the school's keyword is `school library`, so
the specific phrase still wins for the specific place. A word that names
something real in her life and nothing in this file is the same class of bug
as "on the bus": she can talk about it and her body cannot go there.

The same trap by omission: the three girls' homes were real and correct in
`data/cast.json` -- Aya at Sakuradai, the next stop; Rena-chan at Ekoda, two
in; Hinako at Shiinamachi, one before Ikebukuro, which is the true order of
the Seibu Ikebukuro line -- and none of it was in this file. "At Aya's
place" and "at Hinako's" resolved to nothing at all, so a scene there left
her standing wherever she had been: no journey, no train, no sweat, no time
passing. Only "Rena's place" resolved, to a generic `friend_home` whose
keywords still named a yuzu and a miki who left the roster. They have nodes
of their own now (`aya_home`, `rena_home`, `hinako_home`), each with its
station and its own edges to Nerima and Ikebukuro on the line they all
actually live on; `friend_home` stays as the fallback for a classmate with
no name.

**The map is also what she KNOWS about getting anywhere**, and it goes into
her prompt as fact:

- `travel_line()` -- the modes the graph actually has (walk, train, bike,
  dad's car), and, while no edge has one, the sentence that there is no bus
  in her life. Derived from the edges, so adding a bus edge retires it.
- `trip_lines(texts, limit, min_minutes)` -- for the places her promises,
  her goals or the day's plan name, the real legs: the walk to Nerima, the
  named line, the change, the door-to-door minutes. Each text is split into
  CLAUSES before resolving, because `resolve` takes the longest keyword in
  what it is given and a three-promise line resolved "the Pixar event
  tomorrow" to a FamilyMart named in the next clause. One line per place,
  in the order named, skipping anything under `trip_min_minutes`.

This exists because she told him she would do her homework "on the bus".
There is no bus; the model had no fact about the vehicle and picked the one
that sounds right for a school trip. The rule it stands on: a model
invents exactly where the prompt is silent.

## 3. Journeys

When the block she is in wants her somewhere else (`_blocks`, `tick`), a
journey starts from where she actually is (`start(to, why, blk, nxt,
scene, vehicle)`): legs with minutes, mode and line, run on the clock.
Reality lands on the legs:

- the train feed (`tomoe/world/trains.py`, kv `train_status`) on a train leg of
  hers: delayed adds `delayed_minutes`, suspended stops her with an event
  and a `stopped_minutes` wait, a change costs `change_minutes`;
- the rush windows (`_rush`): the Seibu is packed, `packed_minutes`;
- the weather on a walk leg (`_weather`): rain she is in
  (`walk_rain`, exposure to `Body.note_wet`), heat she is walking in
  (`walk_heat_per_degree` over `heat_free_feels`);
- what she wears and carries (`_outfit`): a yukata and geta
  (`yukata_keywords`: `yukata_walk`, `yukata_sweat`), the uniform in
  summer (`uniform_sweat`), the school bag (`school_bag_load`), shopping
  (`shopping_keywords`, `shopping_load`);
- whether she is late (`_hurry`: the next block's start against the eta
  with `hurry_tolerance_minutes`): she runs -- `run_time_factor` faster,
  `run_fatigue_factor` costlier, `run_sweat_factor`, `run_bump_factor`
  likelier to bump into someone; `late_event_from` minutes late is an
  event;
- a vehicle: `car_keywords` or a forced `car` (a pickup, a family trip,
  `car_min_minutes`), `bike`.

`pickup(why)` starts the drive home by car from wherever she is; who
answers the phone is decided before it, in `_pickup_offer`, when the line
strands her on a train leg. That asks the family object
(`Family.can_pickup(ts, from_node, minutes_away)`) for the honest answer,
and with no family object nobody can come -- a character with a body and
no family has nobody to ring, and the journey records "no pickup". A
finished journey is written to kv `journeys` (`keep_journeys`) with what
happened on it.

## 4. Things that happen on the way

One roll per leg at departure (`_roll`), seeded by the journey so a
restart does not re-roll, against a small table per mode scaled by the
conditions: a seat on a packed train, a dropped hairpin found, a cat on a
wall, missing the express, a bump on the stairs, someone standing too
close, a cracked screen. Most legs: nothing. The result sits on the leg
until its minute comes (`_fire`). Texting while walking is allowed and
multiplies the bump chance for the minutes she is doing it
(`_texting_risk`, read off her own messages).

## 5. Fatigue

A code-owned body gauge (`fatigue`, rest 5, no decay of its own) that
accumulates by `mode()` -- walk `walk_per_hour`, packed train
`packed_per_hour`, train, out, sitting -- heat scaling the positive rates
(`heat_per_degree` over `heat_free_feels`) -- and recovers only when
resting: rest `rest_per_hour`, bath `bath_per_hour`, sleep
`sleep_per_hour`. Energy is what sleep gives; fatigue is what the day
takes. `tired_from` / `wiped_from` are the words.

## 6. Readers

| reader | what it gets |
|---|---|
| `State.delay_factor` via `delay_multiplier()` | x(1 + fatigue/100 x `fatigue_delay_weight`), x`walking_delay` while walking, x`packed_delay` on a packed train |
| `Impulse.score` | a weight against reaching out while moving / wiped |
| `Shape.draw` via `shape_bias()` | shorter while walking or wiped |
| `State.register` via `register_line()` | "wiped is wiped whatever she feels about him" -- the body before the mood |
| `State.mood_tags` | the tired / wiped tags |
| the director via `director_line()` | HER BODY NOW: where she is on the way, how long is left, the mode, fatigue; it may not put her at school before she has arrived |
| the persona via `persona_line()` / `constraints()` | the situation block |
| the persona via `travel_line()` / `trip_lines()` | how she gets anywhere, and the real route to a place her day names |
| `Body.note_wet` via `_arrive` | rain exposure for tomorrow's health draw |
| `/where` via `report()` | node, journey, fatigue, the last journeys |

## 7. Config

`situation.*` (62 keys: minutes per condition, fatigue rates, reader
weights, walk factors, outfit keywords and factors, hurry, vehicle, the
event tables), `environment.*` (transit keywords, heat / AC thresholds
shared with `embodied/body.py`), `needs.heat_from_feels`, `needs.rain_mm_from`.
Every number is in `CONFIG.md` with its comment.

## 8. Store and log

kv `situation` (node, journey, fatigue, mode, last tick), `journeys`,
reads `train_status`. Log `[where]`. Events of kind `journey` / `late` /
the on-the-way table.

## 9. Invariants and edge cases

- The director never places her; it is told. A scene that says "at
  school" while the journey has 12 minutes left is corrected by the
  situation line, not the other way round.
- Rolls are seeded by the journey: a restart mid-journey does not re-roll
  the cat or the bump.
- Fatigue has one owner (this file); `energy` is health's; the two are
  different curves and both are read.
- A journey to a place the map lacks is one unknown leg, never a crash;
  add the node to `data/places.json` when it recurs.
- Texting while walking is possible and not free; the persona is not told
  to stop, the bump table is.
- Family days and pickups come from `tomoe/family.py` (seeded per date);
  the car is in the monthly lot on weekdays, mom drives only in daylight
  and close, dad drunk is a no.
- The module is shared and the family and the train feed are declared
  wires (`WIRES`, `sim/wiring.py`): the program that builds them attaches
  them by name, and a character whose program builds neither reads them
  as `None` rather than as switched off.
- The place graph and the human-readable map are world files. A character
  with no world has both blanked (`Config.WORLD_KEYS`), so the
  constructor loads an empty graph -- the honest map of nowhere -- and
  `resolve` returns nothing, which leaves her where she was put.

## 10. Ops and tests

`/where`, `/family`; `tools/situation_test.py` (resolve, routes, a
delayed leg, rain, running late, the seeded roll), `tools/family_test.py`.
