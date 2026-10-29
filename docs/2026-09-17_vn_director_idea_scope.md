# 2026-09-17 — VN stage: the director-idea control (scope)

Read-only scope. Nothing built, nothing committed. This document names the
feature, every seam it touches with `file:line`, the options for what "starts
it" means with a recommendation, the data and persistence design, the view
change, the verification plan and the decisions that are the operator's.

## The feature, as understood

The operator wants a control on the VN stage where he types an idea for a scene
— his example is *"she is waiting for him at the school gate in the rain"* — and
the director takes the idea and **starts that scene**.

Two things happen in that sentence and they are separate:

1. **Stage it.** The idea becomes the place she is shown in: the background the
   `#bg` layer draws, and the scene her draft is written under.
2. **Start it.** A turn opens so she begins the scene herself, rather than the
   scene merely painting the stage until he types something.

The rest of this document settles where each happens and what the operator gets.

## 1. The input path to reuse

### The view's chat box and its send

- `view/index.html:31-34` — the `#say` form: `#input` (placeholder `話しかける…`)
  and `#send` (`送信`).
- `view/app.js:405-431` — the submit handler. It clears the input, disables both
  controls, `POST`s `{text}` to `/say` (`view/app.js:414-418`), then calls
  `loadLog()`.
- `view/app.js:299-342` — `loadLog()` reads `GET /log` for the backlog.

### The channel endpoints

- `channels/vn_bot.py:688-717` — `do_POST` accepts `/say`, `/control`, `/scene`,
  `/speak`; anything else is 404.
- `channels/vn_bot.py:713-717` — `/say` reads `text` and calls `queue_line`.
- `channels/vn_bot.py:724-737` — `queue_line` puts `{id, text}` on `self._inbox`,
  sets `self._user_text`, notifies SSE and logs `[him] <text>`.
- `channels/vn_bot.py:743-751` — `get_new_messages` drains the inbox for the
  runtime.

### The existing manual background pick (the nearest precedent)

- `view/index.html:22` — `#scene-pick` is a `<select>` fed by `GET /scenes`.
- `view/app.js:261-279` — `loadScenes()` fills the select from
  `data.backgrounds`.
- `view/app.js:461-479` — on change, posts `{bg}` to `/scene`.
- `channels/vn_bot.py:401-421` — `set_scene(bg)`: validates the png on disk,
  sets `self._bg_override` (draw now) **and** `self._scene_request` (stage next
  turn), bumps `_rev` so the page redraws, writes `data/vn/state.json`, notifies
  SSE.
- `channels/vn_bot.py:326-331` — `take_scene_request()` returns and clears the
  one-turn request.
- `scail.py:1412-1422` — the runtime's main loop, each pass, reads
  `quality_on()`, `voice_auto()` and `take_scene_request()`; a returned request
  is stored as `self.scene.request` (`scail.py:1417-1420`).
- `sim/scene.py:123-125` — `SceneDirector.request` is the one-turn slot.
- `sim/scene.py:210-229` — `run()` consumes `self.request` **first** and, when
  a valid bg is in it, emits that staging for the one turn with
  `why: "picked by hand on the stage"`.

### What the view does with the frame today

- `channels/vn_bot.py:179-211` — `_frame` builds the whole state: sprite, face,
  overlay, `idle`, `scene`, `voice`, `audio`, `user_text`.
- `channels/vn_bot.py:213-242` — `_scene_state` draws the `scene_provider`
  result; `self._bg_override` wins while set; otherwise `_standby_scene()`.
- `channels/vn_bot.py:468-485` — `_publish` (a new turn) **clears**
  `self._bg_override` at line 476, so a channel-side override lasts only until
  the next published turn.
- `view/app.js:344-380` — `render(state)`; `view/app.js:122-127` `renderScene`
  sets `#bg`'s `background-image` and skips if the URL is unchanged.
- `view/app.js:391-403` — SSE (`GET /events`), with the 4-second poll at
  `view/app.js:382-389` as the fallback.

**The reuse point.** The existing `/scene` + `take_scene_request` + `scene.request`
chain is the whole precedent for "a control on the page changes the staging."
The director-idea control is the same chain with a **place and a scene** in the
payload instead of a bare bg id, plus a start action.

## 2. Where the control lives and how it posts

- `view/index.html:17-23` — `#controls`, the stage's own row of controls. Its
  labels are Japanese: `動き`, `揺れ`, `音声`, `検品`, and the `背景…` select.
- `view/style.css:253-281` — `#controls` styling (top-left, `z-index: 2`,
  `font-size: 12px`, `accent-color: #6b4fbe`).

Recommended placement: one more control in `#controls` — a short text field and
a button, e.g. label `演出` ("direction") with placeholder in Japanese — or a
second small form beside `#say` (`view/style.css:211-243`) if the operator wants
a full-width box. The label follows the existing Japanese convention; the code
comment is English, as every comment in `view/app.js`/`view/style.css` is.

Post: a **new endpoint `POST /director`** beside `/scene` and `/control`, body
`{"text": "..."}` to set, `{"clear": true}` to clear. It reuses `do_POST`
(`channels/vn_bot.py:688-717`) and the `set_scene` shape (validate, bump `_rev`,
`_write_state`, `_notify`). A new `view/app.js` handler mirrors the `/scene`
handler at lines 461-479; a new `postControl`-style call or a direct `fetch`.
Styling follows `#controls` / `#say`.

The page should **not** keep the directive in `localStorage`. The toggles
(`view/app.js:35-47`, `481-495`) use `localStorage` because they are the
player's preference; a live directive is server-side state in the save and
belongs in `/state.json` (a new `directive` field in `_frame`), so it survives a
reload and a restart.

## 3. The director as the integration point

### `sim/scene.py:SceneDirector`

- `sim/scene.py:98-125` — construction. `enabled` (107), `use_model` (108),
  `bg_dir` (111-112), `default_bg` (113), `places` (114-117, from
  `PLACE_BACKGROUNDS` extended by `scene_director.places`), `bgs` scanned at
  118, `request = None` at 125.
- `sim/scene.py:39-57` — `PLACE_BACKGROUNDS`, the 17-place catalog with a
  description in each comment (`school_gate -> BG01a01` at line 56 is exactly
  the operator's example).
- `sim/scene.py:62-80` — `_PLACE_WORDS`, the deterministic place reader over
  the scene's own words (`school gate`, `main gate`, `校門`, `正門` at 76).
- `sim/scene.py:134-148` — `_scan_backgrounds` / `known()` returns
  `sorted(self.bgs)`.
- `sim/scene.py:152-158` — `_read_place`.
- `sim/scene.py:160-169` — `_fallback`.
- `sim/scene.py:173-206` — `_ask`: the `scene_director` role call. The user
  string is built at 179-181, and **line 181 hands the role
  `', '.join(self.known())` — every png id on disk, with no description.**
- `sim/scene.py:210-246` — `run(scene, mood)`: `request` first (216-229), then
  `_ask` or `_fallback` (231-237), then `self.last` and the kv write
  `scene_guidance` (238-245).
- `sim/scene.py:275-284` — `current()`, what the channel draws.
- `sim/scene.py:286-296` — `guidance_block`, the `<stage>` block. It carries
  place, bg, camera, transition, mood and says **"You are not told this and you
  never describe it; your words simply fit where you are."** So `<stage>` is
  framing only, never the scene.
- `sim/scene.py:298-299` — `run_standby()` returns `self.last`.

### `sim/director.py`

- `sim/director.py:676-687` — `scene_brief(scene)`: renders
  `location: activity`, `with`, `sensory`, `around`.
- `sim/director.py:79-92` — `_resume_scene`: prefers kv `director_current` when
  it is the same ts as the newest row.
- `sim/director.py:94-99` — `_keep_scene`: writes the scene whole to kv
  `director_current`.
- `sim/director.py:115-126` — `from_plan()`: `director.scene_source == "plan"`
  reads the schedule block with no model call.
- `sim/director.py:144-181` — `_plan_scene(blk)`: the scene cut from the plan
  (location, activity, with, phone_access, setting, events, ...).
- `sim/director.py:377-387` — `tick()`'s plan branch: `_settle_scene(_plan_scene(
  blk, extra_events), blk, unread_count)`.
- `sim/director.py:575-673` — `_settle_scene`, the one writer of a scene.
- `sim/director.py:70-77` — `catch_up`, the existing kv-backed standing flag
  (`director_catch_up`), the pattern a persistent directive should copy: a kv
  flag the tick consults, surviving a restart.

**For Momoka** `director.scene_source` is `"plan"`
(`characters/momoka/bundle.json:98-100`), so `director.current` is the resident
fallback day block, and the staging pass is what varies the background.

### The prompt, the config and the bundle

- `prompts/scene_director.txt:1-40` — the role: it is given *the scene*, *the
  feeling* and *the exact ids that exist* (lines 5-9), and returns
  place/bg/camera/transition/mood/why (11-18). Line 13: `bg` is "one id copied
  EXACTLY from the backgrounds list".
- `config.py:6108-6152` — `vn` DEFAULTS.
- `config.py:6153-6167` — `scene_director` DEFAULTS (`enabled` false,
  `use_model` false, `default_bg BG02a01`, `places {}`).
- `config.py:7424` — the `REQUIRES` row for `scene_director` is `None`.
- `characters/momoka/bundle.json:202-207` — her `scene_director` section:
  `enabled true`, `use_model true`, `default_bg BG02a01`, `places {}`.
- `characters/momoka/bundle.json:185-201` — her `vn` section.

### The exact call site where `run` happens

- `persona/persona.py:1621-1632` — inside `generate`: `self.scene_director.run(
  scene)` (1627) and `guidance_block(staged)` (1628), appended **inside**
  `</situation>` at 1630, i.e. the fast half, never the cached system prompt.
- `scail.py:502-508` — `SceneDirector` is built and `scene_provider=self.scene.current`
  wires the channel.
- `scail.py:532` — `wire(self.persona, scene_director=self.scene, quality=...)`.

**Where the operator's idea enters.** Not in the `<stage>` block and not in the
system half. It enters as the **scene**: `director.current`'s
`location`/`activity`/`with`/`sensory`, which `scene_brief` renders into her
situation at `persona/persona.py:1057-1059` under the label *"right now, around
you (background: it colours how you type, it is not something to report to
him)"*. The place then drives the background through `PLACE_BACKGROUNDS`.

## 4. The scene that reaches her draft (item 5)

- `persona/persona.py:804-825` — `_situation` builds `<situation>`.
- `persona/persona.py:1028-1115` — `_day`, and specifically **1057-1059**, where
  `scene_brief(scene)` is appended, pinned and labelled as background, with the
  comment at 1046-1056 saying the scene is "manner, not material" and must not be
  narrated back.
- `persona/persona.py:1621-1632` — the staging block goes in after, still inside
  the situation.
- `sim/director.py:676-687` — `scene_brief` is what turns the scene dict into
  that one line.

So the operator's idea becomes **a scene she is in**: `director.current` set to
`{location: "the school gate", activity: "waiting for him", with: "him",
sensory: "raining"}` reaches her as
`the school gate: waiting for him, with him. raining`. It is never a note she
reads. The `<stage>` block stays what it is — framing the page draws — and its
"you are not told this" rule is untouched.

For "starts it", the opening cue is the existing "why you are writing first"
line: `sim/intent.py:182-205` `reason_line`, fed by the hint that
`scail.py:4198-4199` forces into `write_him_first`. That line is phrased as her
own urge ("you want to tell him something -- the subject: ..."), so the
operator's words must be turned into an in-world urge, not restated as an
instruction (see Open decisions).

## 5. The catalog problem: pin a **place**, not a bg id

Today the role is handed `sorted(self.bgs)` (`sim/scene.py:181`) — every png id
on disk, ~111 of them, with no description — and asked to name one. The 17
places with their descriptions live in `PLACE_BACKGROUNDS` (`sim/scene.py:39-57`)
and the model never sees them. The prior Orb read
(`F:\REPS2\Orb\backend\pipeline\passes\director\`) concluded the right shape is:
**the model picks a place from an enumerated catalog and code owns the mapping.**

This feature should do the same:

- **Pin a place** from an enumerated catalog, not a bg id. The operator's idea
  is a place ("the school gate", "in the rain"), and code already owns a verified
  place→bg table.
- Give the role the **places with their descriptions**, not the 111 raw ids.
  The descriptions exist only as code comments today (`sim/scene.py:39-57`); they
  must become data the prompt can carry (a `place: description` list in the
  `_ask` user string, `sim/scene.py:181`). The role then returns `place`, and
  code maps `place -> bg` through `PLACE_BACKGROUNDS` (plus a bundle extension
  via `scene_director.places`).
- Free text from the operator maps onto the same catalog. The deterministic
  reader already exists: `_read_place` + `_PLACE_WORDS` (`sim/scene.py:62-80`,
  `152-158`). Use it first on the operator's text; if it finds no place, fall to
  the model to choose a place from the enumerated list; if that also misses, the
  staging falls back to `default_bg` as it does now.
- Keep the bg-id path only as the last fallback. A place with no verified
  mapping still draws `default_bg` (`sim/scene.py:163`), which is the honest
  behaviour.

## 6. What "starts it" should mean: options

| option | what it touches | what the operator gets |
|---|---|---|
| (a) staging only | `scene_director.request` + `_bg_override` / a directive; `sim/scene.py:run`; the frame. No turn. | The stage changes; no words. He still types to open. |
| (b) staging + open a turn | (a), plus `director.current` set to the directed scene, plus a forced self-start: `scail.py:maybe_impulse(force_hint=...)` → `write_him_first` (4128-4239) → `intent.decide` (4200) → `persona.generate` (4209). | The stage changes **and** she opens the scene in her own words. |
| (c) persistent directive | A kv flag the tick consults every turn (the `catch_up` pattern, `sim/director.py:70-77`), kept until he clears it; `run`/`_ask` and `director.tick` honour it. | The scene and the staging hold across turns until cleared or changed. |
| (d) temporary directive, N turns | (c) with a turn counter in the kv blob; cleared when it reaches 0. | The scene holds for N turns, then reverts. |

**Recommendation: (b), with the directed scene held until he clears it — a
bounded (c).** The operator's words are "and it starts it for me": the thing he
actually asked for is (b), the start. But (b) alone is broken by construction:
the staging pass re-decides every turn (`sim/scene.py:210-246`) and the plan tick
replaces `director.current` (`sim/director.py:377-387`), so a scene that opened
in the school gate would snap back to the resident fallback on the next
director tick. Holding the directive until he clears it (c) is what makes the
opening land. Option (d) is a smaller variant of (c) if he wants the scene to
end on its own.

The single button therefore does two things in one press: it sets and holds the
directed scene, and it forces one opening turn.

## 7. Data and persistence design

### The directive blob

A new kv key in the save, e.g. `scene_directive` (the `scene_guidance` /
`director_current` / `catch_up` pattern, `sim/scene.py:243`,
`sim/director.py:97`, `70-77`):

```
{
  "text":    "she is waiting for him at the school gate in the rain",
  "place":   "school_gate",
  "bg":      "BG01a01",
  "scene":   {"location": "the school gate", "activity": "waiting for him",
              "with": "him", "sensory": "raining"},
  "camera":  "static", "transition": "cut", "mood": "cool",
  "created_ts": 1789...,
  "active":  true,
  "turns_left": null            # null = until cleared; an int = option (d)
}
```

- **Survives a restart** because kv is in `data/momoka.db` (`store.py:72-80`),
  the same way `director_current` restores the scene on boot
  (`sim/director.py:79-92`).
- **Cleared** by `POST /director {clear: true}` (sets `active` false or deletes
  the key) and, in option (d), when `turns_left` reaches 0.
- **Precedence**, highest first:
  1. the per-turn manual bg pick (`SceneDirector.request`, one turn,
     `sim/scene.py:216-229`),
  2. the live directive,
  3. the model pass `_ask` (`sim/scene.py:173-206`),
  4. the deterministic `_fallback` (`sim/scene.py:160-169`).

  The manual pick already runs first in `run`, so keeping it above the directive
  needs no change; the directive is slotted before `_ask`.
- **With the model pass:** the directive pins the place; code maps place→bg; the
  model is still free to pick camera/transition/mood from the directed scene, or
  the directive may carry those too.
- **With the deterministic fallback:** a directive with no place that
  `_read_place` can resolve falls through to the model, then `default_bg`. A
  directive with a resolvable place never needs the fallback.

### The scene her draft sees

`director.current` must reflect the directive for the duration. `sim/director.py`
`tick`'s plan branch (377-387) needs to consult the directive before
`_plan_scene`, the way it consults `catch_up` (70-77, 414-418). The write to the
record is the open question (see below): a stage-only directive should not add a
`scenes` row or events; a scene that is meant to be lived should go through
`_settle_scene` (575-673).

### Two sources of truth, and how to avoid them

The channel needs to draw the new place **now** (before the next turn), and the
runtime needs it for the draft. `set_scene` already sets both
(`channels/vn_bot.py:409-412`: `_bg_override` for the draw, `_scene_request` for
the pass). The new endpoint should do the same: set a channel-side
`_bg_override` for the immediate draw **and** leave the directive in the save for
the pass. Note `_publish` clears `_bg_override` on every turn
(`channels/vn_bot.py:476`), which is fine because by then the directive is the
source the `scene_provider` and `run()` read.

## 8. View change

- `view/index.html`: one text field plus one button inside `#controls`
  (`view/index.html:17-23`), label Japanese (`演出` or `シーン`), placeholder
  Japanese; a small clear control and a text indicator of the live directive.
- `view/app.js`: a handler beside the `/scene` handler at 461-479 that `POST`s
  `{text}` to `/director`; a reader in `render` (344-380) for the new
  `state.directive` field, so the page shows what is live after a reload. No
  `localStorage`.
- `view/style.css`: reuse the `#controls` rules (253-281) and the `#input`/
  `#send` rules (221-243); no new pattern.
- `channels/vn_bot.py`: a `set_director(payload)` method beside `set_scene`
  (401-421), a `take_director_request()` beside `take_scene_request`
  (326-331), a `/director` route in `do_POST` (688-717), and a `directive`
  field in `_frame` (179-211).
- `scail.py`: the main-loop sync at 1412-1422 gains a `take_director_request()`
  read; the request is handed to `SceneDirector` (a new slot beside
  `self.request`) and, when `start` is set, the loop calls
  `maybe_impulse(scene, digest, force_hint=...)` (4061) after setting
  `director.current`.

## 9. Verification plan

### Gates (the standing three)

- `python tools/new_character.py compose momoka --diff` — 0 keys differ.
- `python tools/new_character.py verify momoka` — every bundle is hers.
- `python tools/smoke.py` — all clear.

### Module self-tests

- `python sim/scene.py` — every mapped background on disk, fallback works.
  Extend its sample set (`sim/scene.py:337-340`) with the operator's line and
  assert `school_gate -> BG01a01`.

### The cache proof

- Build her on a scratch save with the model refused, take `Persona._system()`
  with a live directive and without — byte-identical, and the directive's scene
  only in the situation, exactly as the `<stage>` block is checked today
  (`docs/vn-channel.md:382-385`).

### Live, what a build would test

1. The view control posts `{text}` to `/director`; `GET /state.json` shows
   `scene.bg == "BG01A01"` (or the place's bg) and a `directive` block.
2. `GET /asset/bg/bg01a01.png` returns 200.
3. The frame redraws: `_rev` bumped and an SSE event delivered, so the page
   changes without a reload (`view/app.js:122-127`, 391-403).
4. Her opening turn appears: a new turn in `data/vn/state.json` with the
   directed scene; log lines `[director] ...` / `[impulse]` and the scene row.
5. The built prompt carries the scene: a probe that sets the directive, calls
   `persona.generate`, and greps the situation for `scene_brief` of the
   directed scene and for absence of any operator wording in `<stage>`.
6. A restart: `GET /state.json` still shows the directive (kv survives), then
   `POST /director {clear:true}` removes it and the stage reverts.
7. The plan tick does not overwrite the directed scene while the directive is
   active.

## 10. Open decisions that are the operator's

1. **Start or stage?** Does the button start a turn (b) or only change the stage
   (a)? Recommendation: (b).
2. **Lifetime.** Until cleared (c), a fixed N turns (d), or one exchange?
   Recommendation: until cleared, with a visible clear control.
3. **The record.** Does a directed scene get written into her day (`scenes`
   rows, events, her diary, the day's cards), or is it stage-only? Writing it
   makes the scene real and consistent but can contradict the plan/ledger;
   stage-only keeps the record clean but the scene vanishes from her memory.
   This is the biggest design question and it is his.
4. **Free text or place pick?** Free text with the model mapping it to the
   catalog, a place dropdown plus a note, or both? Recommendation: free text
   first, catalog as the fallback binder.
5. **Restart.** Should the directive survive a restart? Recommendation: yes
   (kv), with an explicit clear.
6. **The opening urge.** What the forced hint says in her situation. It must be
   her own in-world urge ("you are waiting for him and want to reach him"), never
   a restatement of the operator's instruction, or she will read the operator's
   words as a note.
7. **Contradiction.** May a directed scene put her somewhere the plan and the
   ledger say she is not (home, asleep, in class)? If yes, what happens to the
   plan for that period?

## 11. Risks

- **Record pollution.** If the directed scene is written through
  `_settle_scene` (`sim/director.py:575-673`), it reaches `events`, the day's
  cards, her diary and her memory. A test scene would then be part of her past.
  Decide decision 3 before building.
- **Plan overwrite.** `from_plan()` (`sim/director.py:115-126`) and the plan
  branch of `tick` (377-387) rebuild `director.current` each tick. The directive
  must be consulted there or the scene reverts within one tick.
- **The cleared override.** `_publish` clears `_bg_override`
  (`channels/vn_bot.py:476`); a channel-only override will not survive the first
  turn. The endpoint must set both the channel override and the save.
- **Catalog change.** Rewriting the `_ask` user string (`sim/scene.py:181`) from
  111 ids to an enumerated place list changes the role's input; the prompt
  (`prompts/scene_director.txt:13, 22-24`) must change with it, and the role's
  answer must be validated as a place before mapping.
- **The live bot holds old Python.** `channels/vn_bot.py` and `scail.py` changes
  need a restart; only `view/` reloads from disk (established in
  `docs/2026-09-16_vn_view_framing_bg_idle_notebook.md:33-38`).
- **Two writers.** The channel's immediate override and the runtime's scene can
  disagree for one turn; keep the endpoint setting both, as `set_scene` does.
- **No verified mapping.** A place the operator names that is not in
  `PLACE_BACKGROUNDS` and that `_PLACE_WORDS` cannot read falls to `default_bg`
  (`sim/scene.py:163`). That is honest but may read as "the idea did nothing";
  the model pass is the second chance, and the view should say when it fell back.
- **Isolation.** A new kv key is not a path, so `tools/isolation.py` needs no
  row. If a new config key ever names a file, the `typesafe` precedent shows the
  row must be added or `verify` fails.
