# The VN channel (Phase 2)

Momoka can be talked to through a visual-novel stage instead of a phone chat.
The runtime is unchanged: it still composes her reply, times it, and asks the
channel to send it. What changes is the channel. `channels/vn_bot.py` draws
her turn as a koikano VN frame -- a background, her sprite, her face, an
emotion overlay, the message window and her voice -- and the player's typed
line is the inbound message.

Four passes were added on top of the first stage, all borrowed from Orb and
narrowed to Momoka's corpus:

- a **staging pass** (`sim/scene.py`) that decides where the scene is and how
  it is framed, before she writes a word of it;
- **28-label expressions** (`sim/emotion.py`) that read the finer feeling and
  carry an overlay piece;
- a **draft guard** (`sim/quality.py`) that catches the slop, a repeat and an
  over-long reply, after she writes it;
- a **token stream** so the page shows her reply as it is being written.

The channel is chosen in `config_momoka.json` under `vn.enabled`, ahead of
`talkapp.enabled`. Telegram is not a live channel in this fork: the stage
runs, and the Telegram object is only the console dry-run sink or the
fallback for a config with neither channel (`scail.py`). Her bundle
(`characters/momoka/bundle.json`) carries the same blocks, so
`tools/new_character.py compose momoka --diff` reports no difference and
`verify momoka` passes.

## Three scene roles

| Role | What it decides | When it runs |
| --- | --- | --- |
| Life director (`sim/director.py`) | Where she is, what she is doing, who is there, and what happened in her day | On a plan tick or an approved scene |
| Scene director (`sim/scene.py`) | Which background, light, camera, music, snow, sound and optional vocal cue fit that situation | Before she writes a reply |
| Stage manager (`sim/stage_manager.py`) | Discusses a scene with the player and proposes one for approval | Only when the player opens **舞台相談** |

The stage manager writes no scene until the player approves its proposal. The
life director then writes that scene into her day, and the scene director
stages her opening reply. The button is labelled **舞台相談** to distinguish the
conversation from the two automatic passes.

## Files

| path | role |
| --- | --- |
| `channels/vn_bot.py` | the channel (`VnInterface`) and its stdlib view server |
| `channels/vn_expression.py` | her feeling -> a verified koikano sprite tag, face id and overlay |
| `channels/vn_voice.py` | the generated line -> recorded koikano clip matcher |
| `tools/voice_index.py` | builds `data/vn/voice_index.json` from the read-only record |
| `sim/scene.py` | the staging pass: place, background, camera, transition, light |
| `sim/emotion.py` | the 28 GoEmotions labels -> one of her eight faces |
| `sim/quality.py` | the draft guard: slop, repeats and length |
| `prompts/scene_director.txt`, `prompts/emotion.txt` | the two judge roles' instructions |
| `prompts/quality_rewrite.txt` | the one voice role's instruction (shorten her own draft) |
| `view/index.html`, `view/app.js`, `view/style.css` | the player page, now with a background, an overlay and a stream |
| `config.py` | the `vn`, `scene_director`, `emotion` and `quality` blocks in DEFAULTS, the three roles, the `ROLE_STANCE` rows and the `REQUIRES` rows |
| `scail.py` | the channel selector and the wires (staging, feeling, guard, stream sink) |
| `llm.py` | `VOICE_ROLES` gains `quality_rewrite`; `on_delta` threaded through the stream |
| `config_momoka.json`, `characters/momoka/bundle.json` | the switches and the art paths |
| `tools/isolation.py` | the VN corpus, `vn.out_dir`, `vn.bg_dir` and `vn.emotion_dir` classified as shared machine files |

Nothing outside `F:\REPS2\SCAILV4` is written. The koikano corpus under
`clipboard capture (kirikiri)\extracted_games\koikano` is read in place.

## The channel surface

`VnInterface` implements `channels/base.py` and the wider surface the runtime
already calls on `App.tg`:

- `verify_connection` starts the view server (no outbound call);
- `get_new_messages` drains the lines the browser posted to `/say`;
- `send_message` publishes a turn and returns its hub id;
- `stream_delta` shows her reply while the model is still writing it;
- `send_typing`, `send_voice`, `send_audio`, `send_sticker`;
- `delete_message`, `edit_message`, `flush_queue`;
- `send_photo`, `send_document`, `file_link` return False or `""`;
- `speak_requests`, `get_ops_commands`, `post_ops_result`, `peer_send`,
  `peer_updates`, `post_swipes`, `post_swipes_state`, `state_push_due`,
  `hub_rows` are safe no-ops.

`active_chat_id` is `"vn"`, so the runtime treats a chat as bound.

## Her voice: recorded clips first, MiniMax otherwise

The TTS worker (`channels/tts_handler.py`) asks the channel for a recorded clip
before it renders or serves a cached line, through the optional
`clip_for(text)` method. The order is: a clip id named in the line; a recorded
koikano clip whose text matches the line; the MiniMax cache; a fresh MiniMax
render. The phone channel has no `clip_for` and the console fallback has no
voice path at all, so their path is unchanged.

`channels/vn_voice.py` does the matching against `data/vn/voice_index.json`,
which `tools/voice_index.py` builds from the read-only record (2509 of her
lines carry a clip id). Matching is conservative: an exact match of the
normalized text, and otherwise nothing. There is no approximate match, so a
miss falls through to synthesis rather than a guess at a clip. The full rule,
the clone step and the sample to upload are in `docs/voice.md`.

The channel serves a recorded clip from the corpus in place at
`/asset/clip/<MMK....ogg>` and a synthesised line from `data/vn/voice` at
`/audio/<name>`; the page plays either through the same audio element.

## The staging pass (`sim/scene.py`)

`SceneDirector` reads her scene (the director's own block: where she is, what
she is doing, who is there) and the moment's feeling, and returns the staging
the page draws and the line her draft is written under: `place`, `bg`,
`camera`, `transition` and `mood`.

Two rules:

- **The background is an id that is on disk.** `vn.bg_dir` is walked once at
  load; 28 places have verified day backgrounds in `PLACE_BACKGROUNDS`.
  `PLACE_LIGHTING` chooses the available day, sunset or night image from her
  clock. A missing lighting variant keeps the day image. A place with no
  mapping or a model naming `BG99z99` falls back to `default_bg`.
- **It rides in the FAST half.** The guidance is a `<stage>` block appended
  inside the `<situation>` she is given, never the cached system prompt
  (`docs/context.md` §1). Measured: `Persona._system()` is byte-identical
  (9127 bytes) with the staging pass on and off; the block is only in the
  situation.

The model pass is the `scene_director` role (a judge, no character sheet).
Off, or the model refused, and the deterministic pass reads the place out of
the scene's own words and takes the light off the mood band
(`reaction_last`), so the stage still changes. The last staging is kept in kv
`scene_guidance` and read by the channel through the `scene_provider` wire.

## Expressions: 28 labels, eight faces, overlays

`sim/emotion.py` labels a line with one of the 28 GoEmotions labels. The
default is the words: a cue table over Japanese (and a few romanised) phrases,
most specific first. `emotion.use_model` puts the same question to the
`emotion` role (a judge) and uses its label only if it is one of the 28;
anything else falls back to the words.

`GOEMOTION_EXPRESSION` maps all 28 labels onto the eight faces she has
(neutral, smile, laugh, surprise, sad, worried, excited, talk), so a feeling
with no face of its own (anger, pride, grief) is drawn as the nearest one
rather than invented. `EMOTION_OVERLAY` names the overlay piece a label
carries (heart, question, the stars, the sweat drop); `VnExpression` verifies
each overlay PNG on disk before emitting it.

`channels/vn_expression.py` also keeps the original path: a mood-band bucket
from `sim/reactions.py` (through `reaction_provider`) or her own words
(`infer`). The channel asks in that order -- the 28-label read, then the
bucket, then the words.

Eight expressions are verified, plus every overlay piece in
`png/scene/emotion` that its file confirms.
When several faces in one costume have the same expression, the label pass's
pose breaks the choice first, then the preferred face index. The selected
sprite's base and expression layer are composed offscreen and shown together;
the base's open eyes no longer flash between clicked lines.

## The draft guard (`sim/quality.py`)

`Quality` runs after her draft is settled and before it is logged. All five
passes are local unless the draft is over the cap and the rewrite role is on:

- **forbidden phrases** -- each phrase in `quality.forbidden` is rewritten or
  dropped;
- **capped tics** -- the marks of hers that the authored bible measures on her
  own lines (`quality.caps`: `おおー`, `おー`, `んっ`, `んーん`, `えへへ`, `百花`,
  and the wider doubled-group move) are capped per draft rather than banned:
  the first `max` occurrences stand and the rest are dropped, so the habit
  reads as hers instead of as a model's fill. `caps.source` names the evidence
  (`docs/koikano-bible-hyakka.md`, speech guide and mechanisms) so a cap can be
  audited and reverted;
- **repeated openers and duplicate bubbles** inside one draft;
- **a run shared with one of her own recent messages**
  (`store.recent_messages`), the same test the editor gate runs;
- **the length** -- over `quality.max_chars`, the `quality_rewrite` role (her
  voice) is asked to shorten it, and the draft is cut at a sentence end
  otherwise.

The caps are register-blind, so they are set loose enough to leave an H scene's
moans alone; a draft the cap would take everything from stands as she wrote it.

The guard never empties her: a draft that trips every pass is sent as she
wrote it. A note is returned for each finding and logged. It is
post-processing only -- her prompt is untouched.

## Streaming the turn

`llm.call` takes an `on_delta` sink; the stream loop hands it the text so far
(never a chunk), and a sink that raises is dropped rather than breaking the
call. `Persona._draft` passes `self.stream_sink`; the App sets it to the
channel's `stream_delta` when the channel has one.

`VnInterface.stream_delta` keeps the in-progress text off the turn counter and
off disk, so the live update does not replay the voice. The page reads it over
server-sent events (`GET /events`, chunked, one event per change, a comment
every 15s to keep it alive) and falls back to the 4-second poll, which shows
the finished turn only.

## The view and the server

The channel starts a `ThreadingHTTPServer` on `vn.host`:`vn.port` in a daemon
thread. It serves the page and the koikano assets in place, the latest turn at
`/state.json`, the live changes at `/events`, and takes the player's line at
`POST /say`:

- `/asset/sprite/<tag>.png`, `/asset/face/<id>.png` -- her, as before;
- `/asset/bg/<id>.png` -- the background the staging pass named;
- `/asset/emotion/<name>.png` -- the overlay the label carries;
- `/asset/clip/<MMK....ogg>` -- a recorded koikano line, from the corpus;
- `/audio/<name>` -- her synthesised voice.

The state is also written to `data/vn/state.json`, so the stage can be checked
with the model off. The page draws the background behind her sprite, the
overlay above it, and her text in the window.
Clicking a queued line changes its text, face and voice. The latest live frame
owns the background and music, so an older queued line cannot restore an older
track. A background chosen by hand draws at once, records its place in
`director_current`, and asks Momoka for one place-focused turn on the loop.

## Framing and the background at boot

The sprite canvas is drawn larger than the viewport and anchored to the top,
by `vn.sprite_zoom` (default `1.55`), which the channel sends in every frame as
`sprite.zoom` and the page writes to `--vn-zoom`. Her koikano art is cut at the
socks with no feet, so at `100vh` the cut landed on the viewport bottom behind
the message window and she read as footless; at the default zoom the cut falls
below the visible area and the frame is the head down to about the knee. `1.0`
shows the whole figure. The CSS carries the same default, so the first paint is
framed before the first poll returns.

The channel's `_scene_state` draws the staging the pass last decided. Before a
turn has run the pass has decided nothing, and the stage used to be the bare
CSS gradient; the channel now falls back to `scene_director.default_bg`
(Momoka's `BG02a01`), read from the merged config tree the same way
`_stored_voice_mode` reads `tts`, and served through `/asset/bg/` only when the
file is on disk. The stage has a place from boot, and the page stays
asset-agnostic: it never names a background of its own.

## Where the feeling mark sits, and how big it is

The mark is drawn the way the game draws it, not as a fixed screen corner. In
the game every `@emotion` tag names a point on the character -- the head
(`頭`), the forehead (`額`), the temple (`こめかみ`), the face (`顔`), the mouth
(`口`) -- and `CgSetupInfo.tjs` (`BUSTUP_EMOTION_POS`, keyed by costume: `MMK_X`
/ `MMK_Y` / `MMK_Z` for her) holds that point's offset, which
`ADVObject.tjs:emotion` scales by the sprite's own zoom. The offsets between
the game's own points, in units of her face box, are the temple `+0.47w
-0.17h`, the head `+0.17w -1.16h` and the forehead `+0.08w -0.50h` from the
face centre. The page keeps the same three points over the file families it
draws: a sweat drop at the temple, an exclamation or a question at the head,
a sparkle at the forehead, a heart or a balloon on the face (`MARK_ANCHOR`).

Two things make it land on her head and stay there:

- **Anchor.** The face box is the `geometry` the channel already carries on
  `sprite` (the diff patch that paints her face, in canvas pixels; a face with
  no patch of its own -- the worried one is drawn on the neutral base -- keeps
  the last box, which is right because the base and the pose are the same).
  The page reads the sprite's own `getBoundingClientRect` and places the mark
  from that box, so the breathing and the sway carry it for free, and it is
  recomputed every frame rather than on a timer. No part of the mark is a
  viewport corner.
- **Size.** The mark is the piece's native pixels times the sprite's screen
  scale -- the game draws a mark at its art size on the sprite's grid -- so a
  `59x102` sweat drop is about 29x51 at 1080p and a `46x46` star about 23x23,
  each in its own aspect rather than forced into one box. It scales with
  `--vn-zoom` the same way. A last-resort cap (`min(20vw, 34vh)`) and a hold
  inside the stage keep a stray aspect or the tall exclamation from leaving
  the viewport.

`#overlay` carries `z-index: 2`: the mark is on her head and her hair is
opaque on the canvas that follows it in the DOM, so an auto z-index would bury
it. The backlog (`3`) and the stage controls (`2`, later in the DOM) stay above.

## Idle motion on the stage

She was a still image; four pieces now move her while she rests. All of it is
the page's, the koikano art reused as it is, and none of it touches the turn
path: the sprite canvas is redrawn exactly as before, and the motion rides CSS
transforms on the elements around and over it.

- **Breathing.** A slow vertical bob of 6 px with a scale of 1.006 about the
  bottom of the canvas, which the framing puts below the viewport, looping
  every 5.2 s. This is the one motion that is on by default.
- **Sway.** A slow lateral drift of plus or minus 9 px, looping every 8 s.
  Off by default, switched on by `vn.idle_sway`.
- **Emotion overlay.** The mark the feeling carries does not sit frozen; each
  family of file name gets motion that suits it:

  | mark | file family | motion | cycle |
  | --- | --- | --- | --- |
  | heart | `heart*` | drifts up and fades | 3.6 s |
  | star | `star*` | twinkles (scale and tilt) | 2.4 s |
  | question | `question*` | bobs and tilts | 2.6 s |
  | sweat drop | `drop*` | settles (squash and fall) | 2.8 s |
  | attention | `attention*` | pulses | 2.2 s |
  | baloon | `baloon*` | floats and tilts | 4.2 s |
  | chat | `chat*` | bobs | 3.2 s |

  A name outside the table falls back to the gentle bob.

**Blink: not possible, and not faked.** Her koikano art has no eye-state pair.
The corpus carries eight whole-face expression diffs (neutral, smile, laugh,
surprise, sad, worried, excited, talk); every pair of frames sharing a base
differs across the whole ~280x240 face window, not in the eyes alone, and no
label carries a closed-eye or blink flag. A blink drawn by squeezing or
cropping the open-eye frame would be a fake, so none is drawn.

How it is switched:

- **Config.** `vn.idle_motion` (default `true`) and `vn.idle_sway` (default
  `false`) are declared in `config.py:DEFAULTS`, carried in Momoka's bundle and
  `config_momoka.json`, and read by the channel's `_idle_state`. The channel
  writes them into every frame as `idle: {motion, sway}`, so the page's own
  defaults come from her config.
- **View.** Two checkboxes at the top left, `#idle-motion` (動き) and
  `#idle-sway` (揺れ). A player's choice is kept in `localStorage` and wins over
  the config default on the next load. Turning 動き off stops the breathing,
  the overlay motion and the sway together.
- **Reduced motion.** `prefers-reduced-motion: reduce` is honoured only when
  nothing more deliberate applies. A stored player choice and the channel's
  `vn.idle_motion` default both count, so the stage breathes under reduced
  motion while her config says it should, which the media query lets through by
  the `force-motion` class. Reduced motion decides only when the page has
  neither a stored choice nor a default from the channel.

The sprite motion rides `#sprite` (breath) and its `#sprite-wrap` parent (sway),
so the two transforms never fight over one `transform` property.

## A turn, end to end

1. The player types a line; the page posts it to `/say`.
2. `VnInterface.queue_line` puts it in the inbound queue and tells the SSE
   readers.
3. The runtime's `poll_inbound` takes it from `get_new_messages` and stores it
   as a message from him.
4. `maybe_reply` and `delivery` compose her reply exactly as they do for a
   phone. Inside `Persona.generate`: the **staging pass** runs first and its
   `<stage>` block is appended to the situation (the fast half); the draft is
   written, streamed to the page token by token; the editor's gate and the
   **draft guard** run; what stands is sent.
5. Before sending the first bubble, `delivery` prepares each line's voice and
   chooses a MiniMax emotion from the same 28-label feeling used by the face.
   A scene director interjection is consumed once and added to audio only.
   `delivery` then calls `send_message` per bubble; the channel reads the feeling
   (28-label, else band, else words), publishes the frame -- background,
   sprite, face, overlay, text -- and the page draws it.
6. When the voice worker renders her line, `send_voice` stages the audio and
   the page plays it.

## Run it

```
momoka.cmd
```

or, directly:

```
python resident\run.py --config config_momoka.json --db data\momoka.db
```

Then open `http://127.0.0.1:8770/`.

A stub boot of the channel alone (no model, no key) is in
`channels/vn_bot.py` under `__main__`; it needs a `vn` block with the corpus
paths to find the sprite inventory, so the App path above is the reliable one.
A probe that builds the channel from `config_momoka.json`, starts the server
and exercises the staging pass, the feeling, the stream and the SSE is the
mechanical check used in this session.

## What still needs the key or the voice

- The reply itself needs the model key; without it the runtime logs the
  refused call and the stage stays on the last turn. The staging pass and the
  feeling both fall back to their deterministic pass, so the stage still
  moves.
- A recorded clip needs no key at all: when her generated line matches one of
  her koikano lines it plays from the corpus. A line she has never spoken needs
  the TTS key and the vendor config; without them the window shows her text
  with no audio and the channel and the page do not fail.
- A live reaction face needs Momoka's reaction database
  (`data/reactions/Momoka/reactions.db`). With none, the feeling comes from
  the 28-label read or the words.

## Scene cues and choices

The stage has 28 catalogued places and verified day, sunset and night variants
where the corpus supplies them. The scene pass can emit snow when the scene is
outside in explicit falling snow, a one-shot sound when a photo, flashback or
head-pat event occurs, and a new music bed on a concrete new emotional beat.
The channel checks every sound and snow file before it emits a URL. The page
draws the game's snow sprites above the background and plays each sound cue
once per cue id. The player's hand-picked background, outfit and music are
saved across a restart; an approved director scene clears a competing manual
background or music choice.

The voice decision this section used to list as open is made: recorded koikano
clips where her line matches one, MiniMax synthesis otherwise, with the
recorded clips as the clone reference. See `docs/voice.md`.

## Checks

```
python sim\scene.py                 # every mapped background on disk, fallback works
python sim\emotion.py               # 28 labels, every one on the set
python sim\quality.py               # the four passes over a sample draft
python channels\vn_expression.py config_momoka.json   # expressions and faces, 0 missing
python tools\voice_index.py --check # the clip index matches the record
python channels\vn_voice.py data\vn\voice_index.json "<voice dir>" "「……千奈」"   # one line -> a clip
python tools\new_character.py compose momoka --diff    # 0 key(s) differ
python tools\new_character.py verify momoka            # every bundle is hers alone
python tools\scene_cue_test.py                # one-shot scene events and music hold
python tools\vn_scene_cue_test.py             # cue paths and voice cue consumption
python tools\vn_stage_persistence_test.py     # manual choices survive restart
```

The cache proof: build her on a scratch save with the model refused, take
`Persona._system()`, attach a staging pass, take it again -- the two are
byte-identical and the `<stage>` block is only in the situation (measured:
9127 = 9127).
