# The stage manager (the director button): scope

Supersedes `docs/2026-09-17_vn_director_idea_build_scope.md`, which was written
against a stale reading of Orb and assumed a place catalog that already exists.
This document records the agreed design and the order to build it.

## What it is

An out-of-character console the player opens from the stage. He talks to it in
English: what is the current scene, what could happen next, start this. It knows
the whole machine -- catalogs, the current scene, the scene list, the main
thread, her record and her state -- and it acts only through tools. Every write
is proposed first and executed only after the player approves it.

A scene the console starts is a **scene thread**: its own transcript, its own
stage save, its own backlog. Backlogs are not shared between scenes and a scene
can be returned to. The default scene is the main thread.

## Decisions taken

- **Scene life: until cleared.** A directed scene holds until the player clears
  it; the plan does not reclaim it.
- **Confirm before writing.** The console resolves a proposal (place ->
  background, mood -> track, CG -> image) and shows it for approval. Nothing is
  written until he approves.
- **Rewritable.** The player can rephrase a request to the console and resend
  it, and can edit a proposal before approving.
- **Each scene is its own thread**, with its own backlog and its own save.
  Backlog is not shared between scenes. Scenes can be returned to.
- **The console knows everything**: catalogs, current scene, scene list, main
  thread, record, her state. Its conversation is never in her prompt and never
  in her record.
- **H scenes are deferred.** A single CG plus the original seiyuu audio already
  on disk, played in preference to TTS. Build this after the rest stands.

## The record model: one writer, transcript per scene, memory shared

There is still one writer. A scene the console starts is written through
`Director._settle_scene` (`sim/director.py:575`), the same call the plan uses, so
it writes a `scenes` row, its `events`, and `director_current` exactly like a
planned scene. That is what makes it real.

- **In the moment:** her situation already reads `scene_brief(director.current)`
  (`persona/persona.py:1057`), labelled background: she is in the scene and is
  not told where it came from. The `urge` for the opening turn is built from the
  scene's fields in the second person, never from the player's English.
- **Later:** the scene row and the forced turn's messages are the ordinary
  record. The day's compile and the cards turn them into memory with no special
  path.

Two layers, deliberately separate:

- The **transcript** is scene-local. Messages carry a `scene_id`; the backlog
  reads only the active scene's messages. A scene's transcript can be returned
  to without touching another's.
- The **record** (scenes, events, threads, days) is shared. A scene's events
  reach her memory even though its transcript is isolated, which is what the
  player asked for: correct in the moment, hers afterwards.

## The console and its tools

A config role `stage_manager` (its own prompt, its own model), off by default.
A second window over the stage (`view/`), chat log persisted in kv
`stage_console`, surviving a restart, never in her thread.

Tools, each mapping to an existing seam:

- `read_scene` -- current `director.current`, staging, recent messages, scene
  list, reachability. The console's answers come from this, not from guesswork.
- `propose_scene(text, place, cg, mood, bgm)` -- resolve only, no write. Returns
  the place->background mapping, the mood->track, the CG->image, and a one-line
  "what will happen" for approval.
- `apply_scene(...)` -- on approval: create or resume the scene thread,
  `_settle_scene` for the words, set the staging, optionally one forced turn.
- `set_staging(place, camera, transition, mood, bgm, cg)` -- stage only, no turn,
  no record (the `/scene` + `/track` behaviour, held until cleared).
- `clear` -- hand the stage back to the main thread; the scene stays in the list.

## Catalogs

Already built and described: `place_catalog()` (`sim/scene.py:378`),
`bgm_catalog()` (`sim/scene.py:326`), cameras, transitions, moods.

Event scenes: the corpus holds 1565 CG files
(`.../png/scene/cg`, `EA01B`, `EA01BL`, ...) with no descriptions. Do not hand
the console 1565 opaque ids. Curate a small `EVENT_NOTES` table, one line per
scene, the same rule as `PLACE_NOTES` and `BGM_TITLES`: the console picks a
named option and code owns the file. This is the hook the deferred H-scene work
uses, so it is written now even though the CGs are not wired yet.

## The forced turn

Do not use `maybe_impulse`: it returns at once for a `player_driven` character
(`scail.py:4109`) and Momoka is one. Add `App.force_scene_turn(scene, urge)`
modelled on `maybe_arrival` (`scail.py:4177`): `persona.generate(...,
impulse_reason=urge, intent_kind="scene")` then
`delivery.send_bubbles(..., self_started=True)`. Skip while `delivery.busy()` or
one of his messages is unread.

## Coherence guards

- **Plan tick:** `Director.tick` (`sim/director.py:381`) rebuilds the scene every
  tick when `from_plan()`. Guard it while a directive is live, or the plan
  overwrites the directed scene within twenty minutes.
- **Two keys:** the stage draws `SceneDirector.current` (kv `scene_guidance`); the
  words come from `Director.current` (kv `director_current`). An apply sets both.
  `_bg_override` covers only the draw until the provider returns the held staging.
- **Ledger contradiction:** an H scene at 3pm when the plan has her in class.
  Warn and let the player override, and write a `schedule_change` event through
  `_settle_scene` so the day reconciles. Refusing makes the button feel dead;
  contradicting silently poisons the record.

## Step 1 in detail: where a scene transcript lives

The message table has about sixty readers -- `recent_messages`, `last_message`
and friends across `scail.py`, `persona/`, `sim/` and the channels. Partitioning
that table by scene therefore has a large blast radius, and the model chosen
here decides the whole build. Two candidates:

- **A store-level active scene.** Add a nullable `scene_id` to `messages`
  (default `main`), keep the active scene in kv, and make `recent_messages`,
  `last_message` and `message_span` filter to the active scene by default. The
  sixty callers then see the scene she is in with no change, and the
  record-level readers that need the whole history (`all_messages`,
  `messages_for_date`, the embedding scan) opt out explicitly. One table, one
  source of truth; the cost is auditing the readers that must stay global
  (`sim/derive.py`, `embed.py`, the compile).
- **A separate transcript table.** Directed-scene messages live in a new
  `scene_messages` table (or per-scene files under `data/vn/scenes/<id>/`) and
  the main `messages` table is untouched. The sixty callers are safe, but the
  thread builder (`sim/thread.py`) and the persona's context now read two
  sources, and "what did she just say" has two answers. This matches the
  player's word "file" but costs a second source of truth.

Recommendation: **A**. The player's requirement is that she is not confused in
the scene, which means the scene's own messages must be in her context while it
is active; a store-level active scene gives that for free. The transcript is
still isolated per scene, and the record (scenes, events) stays shared. The
per-scene save and backlog are then keyed by the same `scene_id`.

Before writing any of it, the readers that must see the whole record are listed
and given an explicit opt-out, so no analysis silently loses the other scenes.

## Steps

Each step is off by default and verifiable on its own.

1. **The scene thread foundation.** A `scene_id` on messages; per-scene
   transcript, stage save, and backlog; the scene list; jump between scenes;
   clear returns to main. This is build-backlog item 13, extended. The console's
   scene actions depend on it, so it comes first.
2. **The console role and window.** `stage_manager` config, prompt and module;
   the second window; chat persisted in kv; `read_scene` and `propose_scene`
   only. No writes yet. Gate: the console answers "what is the current scene"
   and proposes a staging that matches the catalogs, and nothing in the save
   changes.
3. **The write path.** `apply_scene`, `set_staging`, `clear`; the plan-tick
   guard; `force_scene_turn`; the scene row and the `schedule_change` event.
   Gate: a proposed scene becomes a `scenes` row, the stage shows it, the plan
   does not overwrite it, and clear hands back to main.
4. **The event-scene catalog.** `EVENT_NOTES` and the CG layer, wired to the
   console but not yet to audio.
5. **H scenes (deferred).** The CG catalog in use and the original seiyuu audio
   preferred over TTS.

## Open decisions

1. When a directed scene's events reach the shared record: at `apply_scene`, or
   at `clear` (the scene is a draft until then)? The player's wording ("later,
   after the fact, it becomes part of her memories") suggests at `clear`, but
   that means a scene can be discarded with no trace. Recommendation: events
   land at `clear`, and `clear` is itself confirmed.
2. Does the main thread's backlog show that a directed scene happened (a marker
   with a jump), or nothing at all?
3. Does the console see her private interior (gauges, spirals) or only the scene
   and the thread? He said "everything"; the risk is an OOC suggestion that
   reads her private interior back to her. Recommendation: it sees everything,
   and the rule that its words never enter her prompt is what contains it.
