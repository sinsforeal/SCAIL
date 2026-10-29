# 2026-09-17 — VN stage director-idea control: build scope

This document supersedes the build-relevant sections of
`docs/2026-09-17_vn_director_idea_scope.md` — its options for what "starts it"
means (section 6), the data design (7), the view (8), the verification plan (9)
and the open questions (10). The feature description and the read of the input
path in that document's sections 1 through 5 still stand and are not restated
here. Nothing is built; no code, config or prompt was changed. One document is
the only write.

Two rulings were made after that scope was written. The control **starts a
turn**: it stages the scene and forces one opening turn so she begins it. The
directed scene is **recorded** and becomes part of her memories — scenes,
events, the day's cards, her diary. The operator took the record-pollution risk
knowingly, so a test scene becomes her past.

The Orb clone (`F:\REPS2\Orb`, read `backend/pipeline/passes/director/director.py`,
`prompts.py`, `backend/prompting/scene_direction.py`) confirmed the useful shape:
the model picks a **place** from a small enumerated catalog and code owns the
place-to-background mapping, and a directive is **held across turns** rather than
recomputed each turn. Orb's Director is not an asset picker and cannot supply our
background; what it does better is enforce a closed set and carry values forward.
This build takes those two things.

Every seam below carries `file:line`. The Python files are `sim/scene.py`,
`sim/director.py`, `channels/vn_bot.py`, `scail.py` and `config.py`; the view is
`view/index.html`, `view/app.js`, `view/style.css`.

## 1. The data design

The directive is a blob in the save under the kv key `scene_directive`, the same
store `sim/scene.py:243` writes `scene_guidance` to and `sim/director.py:97`
writes `director_current` to. It survives a restart because kv lives in
`data/momoka.db`, the way `director_current` restores the scene on boot
(`sim/director.py:79-92`).

```
{
  "text":       "she is waiting for him at the school gate in the rain",
  "place":      "school_gate",
  "bg":         "BG01a01",
  "scene":      {"location": "the school gate",
                 "activity": "waiting for him in the rain",
                 "with": "him",
                 "sensory": "raining"},
  "camera":     "static",
  "transition": "cut",
  "mood":       "cool",
  "created_ts": 1789...,
  "active":     true,
  "turns_left": null
}
```

Fields and defaults:

- `text` — the operator's words, verbatim, trimmed and capped (256 characters);
  kept so the page can show what is live and so a later rebuild has the source.
- `place` — a key of `PLACE_BACKGROUNDS` (`sim/scene.py:39-57`), or empty when
  nothing binds; `bg` — the mapped background id, or `default_bg`.
- `scene` — the four fields `scene_brief` renders (`sim/director.py:676-687`) and
  `persona._day` pins into her situation (`persona/persona.py:1057-1059`).
- `camera`, `transition`, `mood` — from the constants `CAMERAS`, `TRANSITIONS`,
  `MOODS` (`sim/scene.py:84-89`), defaulting to `static`, `cut`, `neutral`.
- `created_ts` — `clock.now_ts()`; the one field that lets the runtime tell a
  directive it has already settled from a newly posted one.
- `active` — the flag that makes it live. Absent key or `active: false` means no
  directive; this is the default, so every existing save is unchanged.
- `turns_left: null` — held until cleared. An integer is the fixed-life variant
  (decision 2) and is not built in this pass.

What "held" means: `active: true` makes the blob read on every staging pass and
every director tick until it is cleared. It is not consumed after one turn. This
copies the standing-flag shape the catch-up uses — a kv flag the tick consults
every time, surviving a restart (`sim/director.py:70-77`).

Precedence, highest first:

1. The per-turn manual background pick (`SceneDirector.request`, one turn,
   `sim/scene.py:125,216-229`).
2. The live directive (place pinned; code maps place to background).
3. The model pass `_ask` (`sim/scene.py:173-206`).
4. The deterministic `_fallback` (`sim/scene.py:160-169`).

The manual pick needs no change: `run` consumes `self.request` first
(`sim/scene.py:216-229`). The directive is slotted between that branch and
`_ask`.

## 2. The endpoint and channel

- **Route.** Add `/director` to the accepted tuple in `do_POST`
  (`channels/vn_bot.py:688-717`, the tuple at `:690`). Two bodies: set
  `{"text": "...", "place": "..."}` (`place` optional), clear `{"clear": true}`.
  When the control's dark switch is off (§8) the route is a 404, the way an
  unknown route is now (`:691`).
- **`set_director(payload)`** beside `set_scene` (`channels/vn_bot.py:401-421`).
  Set: resolve the blob through the provider in §5, write it to kv
  `scene_directive`, set `self._bg_override` to `bg` for the immediate draw, set
  `self._director_request = {"start": True}`, bump `_rev` and rewrite
  `self._state["directive"]` and `["scene"]`, then `_write_state()` and
  `_notify()` — the same sequence `set_scene` uses (`:409-419`). Clear:
  `store.set("scene_directive", None)`, `self._bg_override = None`,
  `self._director_request = {"clear": True}`, bump `_rev`, rewrite, write,
  notify.
- **`take_director_request()`** beside `take_scene_request`
  (`channels/vn_bot.py:326-331`): return and clear the one-shot request under
  the lock.
- **`directive` field in `_frame`** (`channels/vn_bot.py:179-211`): add
  `"directive": self._directive_state()`, which reads kv through `self.store` and
  returns `{"text", "place", "bg"}` or None. Reading the save rather than an
  in-memory copy is what shows the live directive after a page reload.
- **Immediate draw.** `_scene_state` already lets `self._bg_override` win
  (`channels/vn_bot.py:213-242`, the override at `:227-229`). Note `_publish`
  clears it on the next turn (`channels/vn_bot.py:476`); that is fine, because by
  then the runtime has settled the directed scene and `scene_provider` —
  `SceneDirector.current` (`sim/scene.py:275-284`) — returns the held staging.
- **The provider.** Add `wire(self.tg, director_provider=self.scene.resolve_directive)`
  beside the existing scene wire (`scail.py:508`), so the channel asks the one
  resolver and never names a background itself. With no provider (the stub boot),
  the channel stores the raw text and leaves the draw alone.

## 3. The view

Exact edits.

**`view/index.html:17-23` (`#controls`).** Add one form after the `#scene-pick`
select at line 22:

```html
<form id="director-form" title="演出">
  <input id="director-text" type="text" autocomplete="off" placeholder="演出のアイデア…" />
  <button id="director-send" type="submit">演出</button>
  <button id="director-clear" type="button" hidden>解除</button>
  <span id="director-live"></span>
</form>
```

Labels Japanese, matching the labels already there (`動き`, `揺れ`, `音声`,
`検品`, `背景…`); comments English, as every comment in `view/` is.

**`view/app.js`.**

- Element constants beside the list at `:21`.
- A handler beside the `/scene` handler (`view/app.js:461-479`): on the form's
  submit, `POST {text}` to `/director` and clear the field; on the clear button,
  `POST {clear: true}`. A failure writes `setStatus(...)`, as the `/scene`
  handler does (`:471-477`).
- A read of `state.directive` in `render` (`view/app.js:344-380`): when present,
  set `#director-live` to `演出中: <place or bg>` and unhide `#director-clear`;
  when absent, clear both. `renderScene` (`view/app.js:122-127`) needs no change —
  the new background arrives as `state.scene.url` and is redrawn by the existing
  change test.
- No `localStorage`. The toggles keep a preference there (`view/app.js:35-47`,
  `481-495`); a live directive is server state and belongs in `/state.json`.

**`view/style.css`.** Add rules for `#director-form`, `#director-text`,
`#director-send`, `#director-clear` and `#director-live` beside `#controls`
(`view/style.css:253-281`), reusing the `#input`/`#send` shapes
(`view/style.css:221-243`). `#controls` is already `display:flex; gap:12px;
font-size:12px` (`:253-262`), so the form needs no new layout pattern. The live
indicator uses the muted violet already in that block (`:260-261`).

## 4. The runtime

**The read.** The control block is inside `poll_inbound` (`scail.py:1383`), at
`scail.py:1412-1422`. Beside the `take_scene_request()` read (`:1417-1420`) add:

```python
if hasattr(self.tg, "take_director_request"):
    d = self.tg.take_director_request()
    if d is not None:
        self._pending_director = d
```

**The apply.** Act on `self._pending_director` once after `poll_inbound` returns
in `run` (`scail.py:4869`), not inside `poll_inbound` — the forced turn must not
start in the middle of draining the inbox.

- Clear: set the staging back to its own reading (the provider's resolver returns
  None once kv is cleared) and let the next plan tick rebuild `director.current`
  (`sim/director.py:377-387`).
- Set: call a new `Director.direct_scene(blob, blk)` (§4 below), then force one
  opening turn with `self.maybe_impulse(self.director.current, self.latest_digest(),
  force_hint=urge)` (`scail.py:4061`), where `urge` is §6. `maybe_impulse` already
  returns early when delivery is busy or a line of his is unread (`scail.py:4064`),
  which is the right guard for a forced start.

**Where the directive reaches the staging pass.** `SceneDirector` reads the blob
itself through a new `directive()` method that reads kv `scene_directive` from
`self.store`, the way `current()` reads `scene_guidance` (`sim/scene.py:279-283`).
No attribute has to be kept in sync across a restart, and the runtime does not set
anything on the staging object. `run` consults the directive between the manual
pick and `_ask` (§5). The channel's `director_provider` wire (§2) calls the same
resolver, so place-to-background mapping lives in one place.

**How `director.current` is set.** On a set request, `Director.direct_scene`
builds the scene dict from `blob["scene"]` (`location`, `activity`, `with`,
`sensory`), copies `phone_access` from the schedule block, leaves events empty,
and sets `next_tick_minutes` to the ordinary beat. It passes that dict to the
existing `_settle_scene` (`sim/director.py:575-673`), which is the one writer of a
scene: it writes the `scenes` row (`store.add_scene`, `:654`), writes the events
(`:618`), and sets `self.current = data` and `_keep_scene(data)` (`:668-669`).
On a restart, `_resume_scene` (`sim/director.py:79-92`) restores that same scene
from kv `director_current`, so it survives.

**The required fix — the plan tick must not overwrite it.** The plan branch of
`Director.tick` (`sim/director.py:381-387`) rebuilds `director.current` from the
schedule block every tick, so a directed scene would snap back within one tick.
Add a guard at the head of that branch:

```python
if self.from_plan():
    if self.directive_live():
        self.last_tick_ts = self.clock.now_ts()
        self.store.set("director_last_tick_ts", self.last_tick_ts)
        logger.log("[director] directive holds; the plan tick does not rebuild the scene")
        return self.current
    ...
```

`Director.directive_live()` reads kv `scene_directive` and returns it when
`active`, else None. While it is live the tick stops rebuilding; when it is
cleared the plan resumes at the next tick. For Momoka `director.scene_source` is
`"plan"` (`characters/momoka/bundle.json:98-100`), so this branch is the one that
matters; a character later set to `"model"` needs the same guard before the model
branch, so the guard belongs at the head of `tick` rather than inside the plan
half alone.

## 5. The catalog change

Today `sim/scene.py:181` hands the role `', '.join(self.known())` — every png id
on disk, about 111 of them, with no description — and asks it to name a raw `bg`.
The change:

- **Promote the descriptions to data.** The 17 descriptions exist only as
  comments (`sim/scene.py:39-57`). Add a `PLACE_DESCRIPTIONS` dict keyed by the
  same place names, one line each from those comments. `PLACE_BACKGROUNDS` stays
  `place -> bg`, because code maps it at `sim/scene.py:163`.
- **One catalog builder.** Add `SceneDirector.place_catalog()` returning one line
  per place, `place (bg): description`, from `self.places` (which already merges
  the bundle extension at `sim/scene.py:114-117`) and `PLACE_DESCRIPTIONS`; an
  extension entry with no description renders `place (bg)`.
- **`_ask`** (`sim/scene.py:173-206`): the user string at `:179-181` becomes the
  scene, the feeling, and `places you may name (choose one): <catalog>`. Parse
  `place` from the role, validate it against `self.places`, and set
  `bg = self.places.get(place, "")`. A raw `bg` id the role still returns is
  accepted only if it is on disk (`_bg_lower`, `:144`), as a compatibility
  fallback; anything else falls to `default_bg`.
- **The background-id path stays last.** A place with no verified mapping still
  draws `default_bg` (`sim/scene.py:163`), as it does now.
- **`prompts/scene_director.txt`.** Line 13 (`bg` is "one id copied EXACTLY from
  the backgrounds list") becomes the `place` field — one word copied from the
  list. Lines 22-24 (the bg-id rule) become the place rule: name one place from
  the list, and if nothing fits, the closest one. Line 40's JSON output drops
  `bg` and keeps `place`. The `"the player"` literal in this prompt is a
  registered known literal (`tools/known_literals.json:24-29`) and is not touched.
- **The operator's free text binds to the catalog in two steps.** Add
  `SceneDirector.resolve_directive(text, place=None)`:
  1. `place` given and in the catalog — use it;
  2. else `_read_place`/`_PLACE_WORDS` (`sim/scene.py:62-80,152-158`) over a
     synthetic scene built from `text`;
  3. else, if `use_model`, ask the `scene_director` role with the text as the
     brief (the existing `_ask` with that synthetic scene);
  4. else no place: keep the text in the scene's `activity`, pin no place, and
     draw `default_bg`.

  The resolved blob is what `set_director` stores and what `run` reads. The
  deterministic reader runs first and the model second, so the operator's own
  words and a known place name resolve with no call.

## 6. The opening urge

The forced hint travels `maybe_impulse(..., force_hint=...)` (`scail.py:4061`,
the override at `:4198-4199`), `intent.decide` (`:4200`) and
`Intent.reason_line` (`sim/intent.py:182-205`), which renders `you want to tell
him something -- the subject: <about>`. The fault to avoid: if `force_hint` is
the operator's sentence, `reason_line` prints it as the subject and she reads an
instruction as her own reason.

The fix: build the hint from the directed **scene**, in the second person, never
from `blob["text"]`. A new `Director.opening_urge(blob)` returns, in the language
she is addressed in (`lang.say`, `sim/intent.py:193`), a line of the shape
`you are <place> and <sensory/activity>, and you want him to be part of it` — the
place and the weather come from `blob["scene"]`, the want is code's. The
operator's words exist only as the scene she is in (`director.current`), which
already reaches her through `scene_brief` in `persona._day`
(`persona/persona.py:1057-1059`) and is labelled background, not material. The
urge never restates those words, and the `<stage>` block's "you are not told
this" rule (`sim/scene.py:295`) is untouched.

## 7. The remaining decisions

Recommended default for each, implementable now. Each is the operator's to veto.

**(2) Directive life.** Until cleared (option c of the earlier scope):
`turns_left: null`, with the visible clear control in §3. *Veto* if the scene
should end on its own (option d would count turns in `turns_left` and clear at
zero).

**(4) Free text or place pick.** Free text in one field; the catalog binds it
deterministically first and through the model second (§5). No dropdown in this
build. *Veto* for a place dropdown or a dropdown-plus-note.

**(5) Restart.** Survives. The blob is kv, the scene is `director_current`, and
the plan-tick guard reads kv, so a restart holds it; clear is the only way out.
*Veto* for clearing on boot.

**(6) The urge wording.** Second person from the scene fields, never the
operator's text (§6). *Veto* to hand the operator's own sentence through.

**(7) May a directed scene contradict the plan and the ledger?** Yes, but because
the scene is now recorded the contradiction is **resolved** at the one writer,
not ignored. `Director.direct_scene` (§4) is where the directive is checked
against the block and the ledger before `_settle_scene` writes it:

- When the schedule block's `location`/`activity` differ from the directed place,
  write a `schedule_change` event through `_settle_scene`
  (`sim/director.py:638-639`) so the deviation is on the record and the day's
  cards, agenda and outlook read it. The plan file itself is not rewritten and
  the next block resumes.
- When the directive would put her somewhere the machine says she cannot be —
  `director.asleep_block(self.schedule)` (`sim/director.py:247-255`) or
  `phone_access(request) == "none"` (`sim/director.py:235-245`), because the
  ledger has her asleep or without a phone — refuse the start and show the reason
  in the view, rather than recording a scene the ledger contradicts. The stage may
  still change (the earlier scope's option (a)); the opening turn and the record
  do not.

*Veto* on either half; the resolution point is the new `direct_scene` method.

## 8. Build order and the never-half-live rule

The tree is never half-live: every edit is additive behind a switch that is off,
and the switch is turned on last. Python changes (`sim/`, `channels/`,
`scail.py`, `config.py`) need a **bot restart**; view changes (`view/`) need only
a **page reload** (`docs/2026-09-16_vn_view_framing_bg_idle_notebook.md:33-38`).

1. **`sim/scene.py`** — `PLACE_DESCRIPTIONS`, `place_catalog()`,
   `resolve_directive()`, the `directive()` reader, the directive slot in `run`,
   and `_ask` reading a place; the `__main__` self-test extended (`:311-341`).
   With no directive in kv, behaviour is unchanged.
2. **`prompts/scene_director.txt`** — the place-based role. This changes the
   role's input for every staging pass (Momoka has `use_model: true`,
   `characters/momoka/bundle.json:204`), so it lands with step 1 in the same
   restart and is gated by `sim/scene.py` and `smoke.py`.
3. **`sim/director.py`** — `directive_live()`, `direct_scene()` through
   `_settle_scene`, `opening_urge()`, and the plan-tick guard (`:381-387`).
   Additive; a save with no directive behaves as before.
4. **`channels/vn_bot.py`** — `set_director`, `take_director_request`,
   `_directive_state`, the `directive` field in `_frame` (`:179-211`),
   `/director` in `do_POST` (`:690`), and the dark switch `_director_control_on()`.
   **Restart.**
5. **`scail.py`** — the read in `poll_inbound` (`:1412-1422`), the apply and the
   forced turn after `poll_inbound` in `run` (`:4869`), and the
   `director_provider` wire (`:508`). **Restart.**
6. **`view/index.html`, `view/app.js`, `view/style.css`** — §3. **Page reload.**
   The control is hidden while the endpoint 404s, so the view may land first.
7. **The switch** — a new `scene_director.director_control` boolean in `DEFAULTS`
   (`config.py:6153-6167`, default `false`) turned on in Momoka's bundle
   (`characters/momoka/bundle.json:202-207`), then
   `python tools/new_character.py compose momoka`. Composed last, so every earlier
   step is live-but-dark; the same key turns the whole feature off again.
   **Restart.**

## 9. Acceptance and verification

**`sim/scene.py` self-test** (`:311-341`):

- add the operator's line to the sample set (`:337-340`):
  `{"location": "the school gate", "activity": "waiting for him in the rain"}`
  and assert the resolved place is `school_gate` and
  `places["school_gate"] == "BG01a01"`;
- assert the catalog string carries every place in
  `PLACE_BACKGROUNDS`/`PLACE_DESCRIPTIONS` with its description, and names no raw
  png id;
- assert `resolve_directive("she is waiting for him at the school gate in the
  rain")` returns place `school_gate` and background `BG01a01` with the model
  refused.

**The cache proof.** Build her on a scratch save with the model refused, take
`Persona._system()` with a live directive and without — byte-identical, and the
directive's scene only in the situation
(`docs/vn-channel.md:382-385`, `persona/persona.py:1621-1632`).

**The three gates.**

- `python tools/new_character.py compose momoka --diff` — 0 keys differ;
- `python tools/new_character.py verify momoka`;
- `python tools/smoke.py`.

**Live checks.**

1. `POST /director {"text": "she is waiting for him at the school gate in the
   rain"}` returns 200.
2. `GET /state.json` shows a `directive` block and `scene.bg == "BG01A01"`;
   `GET /asset/bg/bg01a01.png` returns 200.
3. The frame redraws over SSE with no reload: `_rev` bumped and an event
   delivered (`channels/vn_bot.py:459-466`, `view/app.js:122-127,391-403`).
4. Her opening turn is sent: a new row in `data/vn/state.json`, log lines
   `[director ...]` and `[impulse] forced`, and a `scenes` row plus an event in
   `data/momoka.db`.
5. The plan tick does not overwrite: after one tick interval the scene is still
   the directed one, with `[director] directive holds; the plan tick does not
   rebuild the scene` in the log.
6. A restart keeps it: `GET /state.json` still shows the directive and the
   directed scene (kv `scene_directive` and `director_current`).
7. Clear reverts: `POST /director {"clear": true}` removes the directive, the next
   plan tick rebuilds the scene, the stage returns to the plan's background, the
   `directive` field is absent and the clear control hides.
8. The forced-hint check: grep her built situation for `reason_line` and confirm
   it carries no substring of the operator's `text`.

Also run the self-tests a touched `sim/` module owns — `python sim/scene.py`,
`python sim/emotion.py`, `python sim/quality.py` — because the three gates do not
run them (`ORCHESTRATOR_HANDOVER.md:399-402`).

## 10. A known live blocker, to note and not fix in this build

The VN stage's typed input never reaches the store, so an ordinary typed line
still vanishes even though `/director` can force a turn. `channels/vn_bot.py:113`
starts `self._inbound_next = 1` in every process; `queue_line` (`:724-737`) puts
that id on the inbox as the message's `tg_id`; and `store.add_message`
(`store.py:201-215`) silently discards a message whose `tg_id` already exists
(`:203-210`, the Telegram redelivery dedupe). The save already holds rows with
`tg_id` 1, 2 and 3 (`data/momoka.db` ids 1-3, `ORCHESTRATOR_HANDOVER.md:15-17`),
so the first lines of every run collide and disappear; `unread_user_messages()`
(`store.py:266-269`) stays empty and `maybe_reply` (`scail.py:4419-4426`) returns
before it plans anything.

This is a separate fix with its own verification: namespace the channel's inbound
ids (seed `_inbound_next` from the store, or give VN ids a namespace the Telegram
dedupe does not own) and prove that two typed lines, in one run and across a
restart, become two rows; `unread_user_messages()` returns them; and she answers.
Not part of this build.
