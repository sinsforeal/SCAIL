# PROJECT.md: the reference

What SCAIL v3 is and how each part works, as it is now. No dates except
"since". Every module entry has the same shape: what it does; what code
decides and what a model decides; the config it reads; what it reads and
writes in the store; the invariants and the edge cases that have bitten;
and a `history:` pointer into `HISTORY.md`, where every dated note,
amendment and measurement lives. A pointer that reads "history: archive"
goes to `HISTORY-archive.md` beside it, which holds the two documents the
log used to open with: the whole of the previous PROJECT.md, its own §1-§17
numbering unchanged and its modules under §5, and the dated entries that
used to sit under the HANDOVER header. `HANDOVER.md` is the running state
only. `CLAUDE.md` is the rules that must
be seen on every call. A module too large for an entry has a **spec** of
its own under `docs/` (`state`, `cast-exchange`, `situation`, `talkapp`,
`x-account`, `scenery`, `reactions`, `stances`); the entry here is the
summary and the pointer, and the spec is the whole mechanism, config,
store, invariants and edge cases, kept current like this file.

Read the function and query the live store before reporting on a
subsystem; the docs have described behaviour the code did not have.

---

## 1. Purpose and principle

The goal is the complete illusion of a separate consciousness: a girl (Koga
Tomoe, 15, first year at a public high school in Ikebukuro, living in
Nerima) whose day advances whether or not he is around, who can only read
or send messages when her life gives her a phone in her hand, who learns
about him the way a person would (by looking, later, at what he left
visible), and who is moved to speak by her own state rather than by a
timer keyed to his activity.

Four rules, and everything follows from them:

1. **Her state exists independently of him.** Time, weather, calendar,
   schedule, gauges, relationships all move on her clock (Asia/Tokyo). His
   silence is a fact her state reacts to, not the thing that drives the
   loop.
2. **Availability is the strongest illusion lever.** When she cannot answer
   she does not. Reply latency, message length and whether she initiates
   all derive from where she physically is.
3. **She learns about him through a phone, not through omniscience.** His
   PC telemetry, his anime list, his notes are visible to her only when she
   looks, and only as a digest from her side of the glass. No model ever
   sees raw telemetry as "what she knows".
4. **Messages originate from state.** An impulse function reads her gauges,
   her scene and the silence and decides she wants to text; only then does
   the persona speak.

The persona is a static bible plus a texting style guide (`prompts/bible.md`,
`prompts/style.md`, his). Growth lives in state, memory and relationships,
never in machine-edited prompt text. The running bot never edits its own
persona.

**There are four characters now, and the machinery belongs to none of them**
(§20 is the register and the kinds). Everything above is the goal for the
first (§1-§18); the second (§19) is a different kind of thing -- resident on his machine and watching it, with a
body and a flat of her own and no world for them to be in -- and she runs as
her own process against her own save beside the first. What that cost is the subject of §19, and the short version is that
a mechanism written around one character will quietly serve her life to
anybody: the second character's first boot gave her a school day in a ward she
does not live in, friends her roster had never heard of, a menstrual cycle and
an X account. **So a character now declares what KIND of thing she is -- four
properties on her sheet -- and `Config.REQUIRES` assigns every switchable
subsystem to one of them or to none, and refuses to start if a subsystem is
unassigned.** The prompts hold no person either: a character-shaped span in a
mechanism prompt is a `[[TOKEN]]` filled from her own file, checked byte for
byte by `tools/neutral_gate.py`. Two characters sharing a file is a fault
unless the file belongs to the machine (`tools/isolation.py`), and one
character's material appearing in the other's output is a fault
(`tools/character_leaks.py`, which reads a run's `session.log` or, with
`--out` / `--text`, any other output about her: a harness's assembled prompt,
a regenerated reply, a persona card); both run in smoke.

**Which language a character is addressed in is one switch, not a decision per
line** (`sim/lang.py`; the detail and the measurement are §19 and
`docs/yukarin.md`). `character.instructions` picks the arm --
`as_they_run_today` (the control and the default), `in_english`,
`in_her_language` -- and covers everything the prompt BUILDER writes at her:
the headings, the situation block, the closing instruction. What the third arm
actually renders is declared per character by
`character.instruction_language`, so it cannot be inferred from the language
she answers him in: the first character is bilingual, writes English to him,
and every measurement ever taken on her was taken with English instructions,
so `/lang ja` refuses her with that reason. The other half is the material
another role wrote and she then reads -- her facts about him, her beliefs, her
reflections, her promises -- and the `language` section reaches that: each of
the 29 roles in `language.material_roles` is told, in one English line
addressed to it as a mechanism, which language to write her material in, with
field names, keys, fixed choices and quotations from the record excepted.
Four roles are off that list on purpose because code reads their words as data
(`phone`, `director`, `schedule`, `state`), and the continuity editor forks
inside its own prompt instead (`[[?her_language]]`: its note to her in her
language, its verdict in English for the log). Nothing already in the record
is translated; a fact written in English stays as written and ages out through
the forgetting curve. `/lang [ja|en|auto]` throws it live, saved to that
character's own save (kv `instructions_override`) so it survives a restart
with no config edit, and the boot line and `/provider` both print which arm is
rendering and where the choice came from.

**And the code is two programs over one mind library** (his call, HISTORY
§19). `sim/` holds the mind and the relationship, `persona/` her voice,
`embodied/` a body (health, the body in its setting, money, where she is on a
map), `world/` the clock, the weather and the calendar, `machine/` his
machine's one collector, and `scail.py` the runtime that runs either of them.
`tomoe/` is the first character's: her world (`tomoe/world/`: trains, hazards,
zeitgeist), her cast and exchanges, her account, her phone-app sight, her
schoolgirl's day (`tomoe/schedule.py`), her household and map as prompt text
(`tomoe/briefs.py`), her prompts (`tomoe/prompts/`) and `tomoe/words.py`, how
she sees him. `resident/` is the second's: `resident/sight.py`,
`resident/schedule.py` (a flat and a week of her own) and `resident/words.py`.
**The runtime builds the mind, the body and his machine, then asks the program
her config names (`character.program`) to build the rest** (`tomoe/app.py`,
`resident/app.py`): every world-and-account object is a slot on the App
(`scail.PROGRAM_SLOTS`) that starts as `None`, the program fills the ones she
has, and the loop calls the program's hooks -- her day's plan, the beats and
exchanges, the feeds, the compile's stages, shutdown -- through
`App._program_call`, which does nothing for a hook the program does not
define. A character with no world therefore never has a cast, an exchange, an
account or a snoop in her process; they are not switched off, they are absent.
**What a module is handed after construction is a declared wire**
(`sim/wiring.py`): the objects are built in an order no constructor
signature can express, so a receiver lists its collaborators in `WIRES`,
`wiring.declare(self)` at the end of its constructor makes each one an
attribute that starts `None`, the runtime and the program builders attach
with `wire(target, name=obj)`, which refuses a name the target has not
declared, and the receiver reads the wire as a plain attribute. A wire still
`None` after the build while the App holds the thing to attach is reported
at boot (`App.unwired`, `[wiring] built and not attached`) and fails smoke;
a wire that is `None` because the program built no such thing is ordinary.
The persona declares 41, the exchange 19, the director 18, the state 12.
The coming days are one of them: `Agenda` (`sim/agenda.py`) is built beside
the other mind objects in `scail.py`, declares the four stores it joins --
the calendar, her promises, what he said he would do, and the day's one
truth -- and is attached to the persona as `agenda`, so a character whose
program built none of a world still gets the join over what she does have.
It prints one line at boot: `[agenda] N dated thing(s) over 7 day(s): ...`.
**One owner for each thing the modules used to write for themselves:** his
chat as prompt lines (`sim/chattext.py`, every caller keeping its labels,
cut and fallback); a per-day counter in kv (`Store.bump_today`,
`Store.today_count`); "HH:MM" to minutes and back (`hm_to_minutes` in `world/clock.py`
with a default for a string that is not a clock, `minutes_to_hm` wrapping
past midnight only when asked, since a schedule's day may end at "24:00");
an interior role's system prompt, the role's file then her sheet
(`Config.role_system`, the prompt files cached by mtime); a gauge's distance
from its rest (`State.over_rest`, `State._room`); which relationship row is
him (`State.him_key_in`); the bilingual closure (`sim.lang.pick`); and the
App on a copy of a save for a harness (`tools/harness.py`).
The library never imports a program: `sim/sight.py` looks a phrase up in the
table the program registered (importing `<program>.words` by the config's
name if none has), and two passes in smoke keep it so -- `tools/sight_words.py`
fails on a shared string or prompt that says how she sees him, and
`tools/character_names.py` fails on any character's or cast member's name --
and on any place of hers: her home area, her station and the stops on her
line, her ward, her school and its area, the places she keeps going back to --
appearing in what the characters share. That is the library, the hub, the
sensors, the channels, the car, the tools, both program packages (each exempt
for its own characters' names) and every prompt directory, in six kinds of
file rather than in Python alone, with a match inside a longer word reported
separately and a comment or a docstring reported and never failed.
`tools/known_literals.json` is what was already there the day it was widened,
each entry with its reason; a finding that is not in it fails the run.
`tools/prompt_leaks.py` is the same rule on the text that is actually sent:
every role prompt a character's config points at, rendered through her fills
and read for another character's life. Both are in smoke. The config defaults
name nobody at all: every person-shaped default is empty
(`tools/defaults_person_test.py`), a character's name, her sheet, her seeds and
her chat titles are her config's, and the shared modules take them from
`config.character` and the roster. The account's keys under `sensors` are blanked for a character
with no account (`Config.ACCOUNT_KEYS`), the way `Config.WORLD_KEYS` blanks a
world. **A blanked path is therefore a state the project produces on purpose,
and every module that reads a configured path treats an empty one as nothing
here** -- in the constructor, the way `world/calendar.py` loads no calendar at
all, so anything added to the class later inherits the silence. A path that
names a file which is not there is still an error: that is a wrong path
rather than an absent one. `tools/blank_paths.py` (in smoke) builds every
character with every person-shaped path blank at once and fails if one does
not build; the classification of which paths are a person's is
`tools/isolation.py`'s own.

**Working rule:** model calls are not the scarce resource; fidelity is. Code
decides *when* (gates, caps, schedules); a model decides *what*.

---

## 2. Vocabulary

- **her time / his time** -- `world.character_timezone` and the machine's
  local zone. The first character is `Asia/Tokyo`, many hours ahead of him. A
  character with no world of her own has no timezone of her own either and
  gets his (`WorldClock`), because there is no elsewhere for her to be.
  Schedule decisions use her time; every timestamp written to the store or a
  doc is machine local time.
- **tick** -- one director pass every `director.tick_minutes`; produces a
  scene. The night is one scene.
- **scene** -- the physical present: location, activity, who is with her,
  `phone_access`, a sensory line, an inner line, events, `share_worthy`.
- **phone_access** -- `free` (alone with the phone), `glance` (can peek),
  `none` (asleep, bath, exam). Governs reading, replying, initiating, looking
  at the app.
- **gauges** -- values 0-100, each declaring `kind` (emotion / drive / body /
  derived), `valence` and `arousal` (§3.1); 25 for a character with a body in
  a world and 21 for one whose sheet removes `hunger`, `fatigue`, `physical_comfort`
  and `unwell` -- what a body reports about being in a world. She keeps
  `energy`, because being tired is something she says. `mood` and `affection`
  are derived and refused at the write site.
- **meters** -- per-person `closeness`, `standing`, `tension` in
  `relationships`; his also carry the sentiments (§3.6).
- **digest** -- the account of what his PC / MAL / vault were doing since she
  last looked, written from her side.
- **impulse** -- the decision that she texts first.
- **exchange** -- a conversation of hers with a person around her (LINE, the
  group, in person), in Japanese. There is no gloss: `ja` is the whole of it.
- **beat** -- a moment planned for the day when somebody reaches into it (a
  LINE, a group burst, a call, something said in person).
- **compile** -- the nightly record of one date: narrative, summary, facts
  about him with a forgetting curve, her own memories, facts about people.
- **bubble** -- one message in the app. A reply is usually one to three.
- **register** -- how she is answering *him* right now, mechanically
  (§3.1); never handed to a talk with anyone else.
- **source** -- who a feeling is aimed at (§3.1 `State.sources`).
- **her two languages** -- of the FIRST character. `character.writes_to_him`
  is the setting, and the second character has one language: she writes
  Japanese to him and everywhere else, and the write line, the voice rules
  and the language flag all read that same key. For the first character:
  she writes ENGLISH to him and only to him: her
  second language, self-taught off subs, forums and him, fluent in text and
  slower out loud (`prompts/bible.md`, `prompts/style.md`). **Everything else
  in her life is Japanese and is GENERATED in Japanese** -- the cast beats,
  her turns and theirs, her diary, her private thoughts, her beliefs, the
  gist of an exchange. There is no English gloss: a turn is `{who, ja, hm}`.
  Her own Japanese has its own guide, `prompts/style_ja.md` (the standard
  Tokyo she is performing, when Hakata slips, how she is different with each
  of them, her first person), and each other person has a sheet of their own
  under `prompts/cast/`, in Japanese.
  The narration and record layer stays English, because it is the machine
  describing her rather than anyone speaking: the director's scene, the
  events, the compiled day, `self_memories`, `user_facts` -- which is also
  the index `Recall` searches with HIS English words, and what
  `worldshare`'s English `HIM` regex measures.
  The rule that draws the line: **first person is Japanese, third person is
  English.** Where a prompt asks for Japanese, the part that says HOW to say
  it is written in Japanese too, naming the actual forms -- asked in English,
  a model plans in English and renders at the last step, which is how
  「お前は…」 came back for a fifteen-year-old girl's own belief.

---

## 3. Runtime

`scail.py:App.run` is one loop per `telegram.poll_seconds` of character
time. In order: day boundary (`ensure_day`: schedule, cast day, arcs,
family, goals, morning outlook), her picture of him, inbound
(`poll_inbound`; commands never enter her chat), replies (`maybe_reply`,
which ends in `foresee_after`, then `maybe_afterthought`), where her body
is on the clock, then one of three branches -- asleep (one scene for the
night, the gauges still drifting), the link down, or a tick due. The tick
itself is the phone look, the director's scene and the reconcile
(`tick`); the loop then reads the psychology, the impulse, the discharge,
her face, the diary, the morning, the anticipation and the reflection.
After the branch: the withholding, the foresight refresh and its risk
scoring, the expectations, the wonder, a promise she just made him, the
attachment, the shelf nag, the nightly compile (`maybe_compile` at
`timeline.compile_at`). Every stage runs under one guard (`_guarded`),
which logs the failure by exception type under the stage's tag and lets
the loop go on. What belongs to a program rides on a hook at a fixed
point in that order: her beats and exchanges (`loop_pass`,
`after_situation`), her snoop, a photograph and the account
(`after_tick`), the hazards, the trains and the feeds (`late_pass`).
`shutdown` zips the run's log directory.

**An ordinary tick stands aside while a message of his is waiting for its
reply tick.** The reply senses the scene with his words in front of it and
reads the gauges off them (`force=True` with his text), so an ordinary tick
landing in between re-sensed the same scene, recorded his message as an event
of her day and paid for a gauge read that the reply tick then repeated on the
same inputs 41 seconds later -- three answers bought and thrown away, measured
on the second character. `App.tick` now returns the director's current scene
unchanged when the tick is not forced, one of his messages is unread and a
reply is already planned, with `[director] his message is waiting for its
reply tick; not resensing now`. The look at his machine above that branch
still happens, and the reply tick reads it.

**What a restart keeps.** Both bots are stopped and started many times a
day, and a stop is `Stop-Process -Force`: no `finally` and no `atexit`
runs, so `shutdown` fires only on a keyboard interrupt and anything
written on the way out was never written. Her state therefore lives in the
save at the moment it changes, not at the end -- `Store.set` commits
before it returns and the saves are `synchronous=FULL`, so what reached
the store is on disk. What a new process picks up: the scene she is in and
when the next one is due (kv `director_current`, `director_last_tick_ts`,
`director_next_tick_minutes`), the hole the catch-up asked for
(`director_catch_up`) and the phone look that goes with it
(`phone_force_next`), an exchange in flight with its next beat as an
absolute time (`exchange_live`), a running spiral or an open rupture, every
cooldown and every per-day count, the verbatim window at the head of her
thread, and the voice lines rendered but not yet sent (a file per
character under `data/tts_jobs/`). A message of his read and never
answered goes back in his queue once, while it is recent
(`App.recover_lost_reply`, `delivery.recover_lost_reply_hours`).

**And the work that was running when it died.** Every paid or stateful
background job -- a lookup, a recall, the day's compile, the photograph
harvest, a photograph picked and not yet sent, her look at her own timeline
-- writes a row to kv `in_flight` when it starts and removes it when it
returns, well or badly (`sim/inflight.py`, `with inflight.job(...)`). A
killed process never removes its row, and that leftover row is the flag. The
boot read runs once, off the loop thread and before this process has started
a job of its own, logs `[boot] N job(s) were in flight when the process
died: ...` and hands each row to `POLICY`, which is the whole of the
(Beside it, `sim/repairs.py` is the home of one-off repairs of a live save,
each run once at boot for every character and keyed on a kv flag -- the
record's own labels taken off stored messages, the per-save recap rows
copied into the machine's store -- with the old text kept under
`data/retired/<ts>_*/`; a repair there is a fault the record already
carries, never a migration of shape.)
behaviour and the only place a new kind of job is registered: a compile is
rerun if its date still has no `days` row and left alone if it has one; a
lookup, a recall or an X look is dropped and written to `missed_calls`, the
same record an unanswered model call goes to, so `App.catch_up` sees it; a
picked photograph goes back in the pool. `/inflight` shows what is running
now. What still has no flag: a browser session's part-finished page, and the
hazards queue, which holds a quake pushed but not yet delivered in memory
alone. **One bot per save file**
(`singleton.py`): the lock names the holder's pid AND the command line it
was started with, and liveness is both, because a handle opens for a
process that has exited and pids are recycled. **The save the lock is keyed
to comes from the config the process was started with** (`_db_from_config`
reads `logging.db_path` out of that file) and only from `--db` when one was
given; reading it from the command line alone meant a launcher that omitted
`--db` locked the FIRST character's save while opening its own, which is two
bots on one lock and neither of them noticing.
`tools/restart_safe_test.py` builds the App twice on one copy of a save
and asserts each of these came back.

**Processes.** Two: the character, and the machine's. Momoka is the one bot
(`SCAIL_momoka` task, `momoka.cmd`, `resident/run.py` with her own config and
save), and the MyAnimeList mirror daemon is the machine's rather than
anybody's -- it keeps HIS anime history current and there is one of it
(`SCAIL_mal`, `mal_daemon.cmd`, detached under `pythonw` so it has no console
of its own, writing `logs/mal_daemon.log` itself). Both are `restart.cmd`'s to
stop and start, in the order daemon, character (§14). The TALKAPP hub is not
run in this fork. One bot per save file (`singleton.py`), which is what lets
more than one sit beside each other. Logs: one directory per run under
`logs/`, `session.log` the narrative, `llm_calls.jsonl` every prompt and
answer. **The dated backup is
named after the save it copies**; it was `world-<date>.db` whatever the
source, so the second character's save landed on the first one's backup within
a minute of her first boot and the prune would have eaten his history a day at
a time.

**Models.** `llm.py`: the OpenAI-compatible client, one entry per role
under `models` in config (`deepseek-v4-flash` by default; the judge-role A/B
that once shadowed pro with flash was read, `docs/ab-judge-roles.md`, and
its machinery is gone). `LLM.call` and
`LLM.call_json`; a JSON answer that does not parse is repaired
(`parse_json_block`: trailing commas, split string values) and then asked
again (`api.json_retries`); a caller handles `None` and never stores a raw
answer as data. **Every answer is streamed** (`LLM._stream`, `api.stream`):
the body is read chunk by chunk, so a stream that ends with no finish
reason was cut off and goes round the retry, a `length` finish with words
in it is logged `TRUNCATED` and asked again once (`api.empty_retries`)
and then given up on rather than sent as half a reply, an `error` object
a host sends inside the stream raises with its message, and no bytes for
`api.stream_stall_seconds` fails the call there instead of at the
ten-minute request timeout, which still bounds the whole answer. **An answer
that has begun repeating itself word for word is ended where the repetition
starts**: past `api.repeat_guard_chars` the last 400 characters are counted
against everything written before them, and a tail already written
`api.repeat_guard_copies` times raises `RunawayAnswer`, which is logged
`RUNAWAY`, asked once more and then given up on into the missed-calls
ledger. `LLM.call_json` does not re-ask after one at all, and never hands
an answer longer than `api.json_retry_max_chars` back to the model to
repair, because sending it costs its whole length as prompt. The
receipt carries the finish reason and the seconds to the first token;
`/provider` counts truncated, cut-off and runaway answers beside empties.
**A stream that is abandoned writes a row of its own** (`LLM._note_abandoned`,
finish `abandoned`): a stream that times out, stalls, is cut off, sends an
error object or loops has been generated for as long as it ran and is billed
for, and until this it left nothing at all in `llm_calls.jsonl` -- a cast-beat
call once ran to its ten-minute ceiling, was retried inside the same call and
answered, and only the retry was on the record. The row carries the
reason, the seconds, the chunk count, and the receipt's tokens where the last
chunk carried them, else the prompt measured off the bytes that went out at
four characters to the token and marked `estimated`, which `tools/llmstats.py`
prices at the published rates like any row with no cost on it. A call that
never got a chunk cost nothing and writes nothing. The retry writes its own
row as before, so the ledger counts both. Every
role's `max_tokens` is the API maximum; a low cap
fails silently. Thinking is ON by default upstream at effort `high`, so a
non-thinking role sends `thinking: disabled` explicitly, and a thinking
role's `effort` (`low` / `high` / `max`, the only documented values) is
sent both inside the `thinking` object and at the top level; a 402 is
named in the log as a spent balance, the one error no retry fixes.
The prompt cache is tracked per role (`LLM._track_cache`, kv `cache_track`:
the last hit rate, how many calls came back warm and how many cold, the
longest idle gap a warm call survived, and the shortest and most recent gap
that came back cold; `cache=NN%` on every call line, `[cache] ... COLD after
N` when the previous call had been warm, the table in `/provider`;
`docs/context.md` §7). **A cold call is counted whenever the hit rate is under
half and that role has a previous call to measure the gap from**, whatever the
previous call did; requiring the previous call to have been WARM meant a role
that is cold every time recorded nothing and the table read "never gone cold"
while every call was missing, which is what both live saves held until this
was fixed. The gap is measured from the previous call of that role FINISHING
to this one going out, and a call sent inside `api.cache_settle_seconds` (15)
of that finish -- or while the previous call of the same role is still running
-- is counted on its own line and never as cold, because the entry the
previous call wrote is not readable that soon (measured on Z.AI at 44k tokens:
about ten seconds). **The first call of a burst goes out alone and the rest of
the burst waits for its entry once** (`LLM._hold_for_burst`,
`api.cache_burst_hold`): a call that would go out inside the settle window of a
COLD call of the same role on the same system prefix waits out the remainder,
and every call behind it then reads that prefix without waiting, so fifteen
calls cost one wait rather than fifteen. The cap holds even where the host does
not cache at all -- one wait per burst, a burst ending at the first
settle-length gap -- and a warm previous call, a different system prefix or a
prompt under about 2,000 tokens hold nothing. The line is `[cache] <role>: held
Ns so the burst reads the first call's prefix`; `/provider` counts the holds and
their seconds. What this fixes: the day rollover fires about fifteen cast-beat
calls back to back and every one of them logged `0% cached, sent 0s after the
previous call of this role finished`. **`docs/openrouter.md` is the spec of the provider seam**:
the request `llm.py` builds, the pin and the fall-through, what is read off
the receipt, the cache and the effort levels as measured, and the open
decisions with their numbers. `tools/llmstats.py` (`/stats [days]`) prices every call on disk: the cost the
host reported for the call where the log has it, else OpenRouter's published
per-token rates for the slug that answered. Her eyes
are Gemini on Vertex (`sensors/vision.py`, `gemini-3.8-flash`, region
`global`, which is the only region it is on for this project). `vision.model`
is the BARE id: the caller builds
`.../publishers/google/models/<model>:generateContent`, so the publisher is
already in the path and the `google/` prefix an OpenRouter slug carries would
404.

**Which model writes in her words.** `LLM.VOICE_ROLES` names the nine roles
that write as her -- persona, revise_self, spiral, approach, morning,
anticipation, reflect, diary, wonder -- as against the machinery that thinks
about her. `/voicemodel <name>` (kv `voice_model_override`, per character,
for the run) moves exactly those and leaves her director, her state read and
her judges where her config put them; it is the narrower switch, so it wins
over `/model`'s all-roles pin for those roles. `api.voice_models` is the menu
the control in the chat header offers (kimi-k3, deepseek-v4-flash-0731,
deepseek-v4-pro-0813, sakana-namazu, gemini-3.8-flash, glm-5.3-flash,
glm-5.3); a name the active provider has no slug for is not offered, because
it would go out as a literal and be rejected. **Neither pin is written to the
config file** -- both are live switches, and `tools/set_model.py` is what
keeps a choice. `LLM.effective_model(role)` is the one reader of that
precedence, and the chat header, the frozen reply prompt and the swipe all
draw from it. Every pin in `api.providers.<p>.order` is the host name
OpenRouter's own receipt reports (`Google AI Studio`, `Z.AI`, `StreamLake`),
never the endpoint tag: pinned under the tag, every call logs a fall-through
that never happened.

**Providers.** Who answers is `api.provider` and `api.providers`: the
official DeepSeek endpoint (`kind: deepseek`, `api.api_key`, the API-maximum
`max_tokens` sent) or a host on OpenRouter (`kind: openrouter`, key
`api.openrouter_key_file`, no `max_tokens` sent -- hosts cap output
differently and refuse a number above theirs -- the role's `thinking` flag
mapped to OpenRouter's `reasoning`, on at the role's `effort` or off), each
with the slug every bot model name maps to there and, per slug, the host
order, the pinned host first and OpenRouter's other hosts for the same slug
after it (`api.host_fallback`; off, the pinned host or a missed call). The
default is DeepSeek v4 flash 0731 at Together. **One provider answers and
no other provider is fallen to** (his
call): a fallback maps a model name to another host's slug and so can change
the model and not just the host, and with one host in a chain the cooldown
demoted the only host there was and answered nothing for thirty minutes. A
call that fails after `api.max_retries` returns nothing, is logged, and goes
into kv `missed_calls`, which `App.catch_up` reads when the host is back.
`/provider <name>` pins a defined provider (kv `provider_override`),
`/provider auto` unpins, `/provider` shows who answers; `/speed` runs one tiny
call on each defined provider. **`LLM.call_tools(role, messages, tools,
tool_choice)`** is the one entry point that offers a model tools and hands
back what it picked: the same provider, pin, reasoning effort, receipts and
`missed_calls` behaviour as `call`, plus `provider.require_parameters` so a
fall-through cannot land on a host for the same slug that drops the tools, and
never `parallel_tool_calls`. It streams and reassembles `delta.tool_calls` by
index, parses each `arguments` object, and treats `finish_reason:
"tool_calls"` with no content as a normal answer rather than an empty one.
There is no loop and no dispatch: what a tool does, what it is capped at and
whether this moment is one to look on are the program's. **One live caller**
(`docs/tool-calling.md` §16): which post out of her scroll she sends him
(`tomoe/share_pick.py`, the `share_pick` role and section), one call at the
moment her reply is about to carry the offer, two tools, no free-text
argument, and the answer acted on. Everything else about tools in that
document is a bench or a replay. Every `llm_calls.jsonl` row carries
`provider`, `served_by` (the host OpenRouter names) and the slug. The
persona role runs at temperature 1.0 (1.3 was worse for every provider on
the persona test, HISTORY 2026-08-31).

**Config.** `config.json` is generated from `config.py:DEFAULTS` and
backfilled; the merge keeps `config.json`'s values, so a default change or
a key removal is done in both files. A key read by code but absent from
DEFAULTS is a crash. `Config._check_gauges` refuses to start on a gauge
without `kind` / `valence` / `arousal`. `tools/smoke.py` builds the App on
a copy of the save, calls every report, prints the gauge wiring table and
the affect grid, names dead config keys, runs the static passes; run it
before every restart.

**Commands** (`App.run_command`, from Telegram or the app's ops bar, never
into her chat) are one table, `App.COMMANDS`: the command, the method that
answers it (`_cmd_<name>`), the program slots its body touches, and whether
it needs an argument. A command whose slot this character has not got is
answered "not part of this character (she has no cast)" rather than run into
a None, and `/help` lists only what she has; a command that needs an
argument and gets none answers with its own help row. `tools/smoke.py` fails
on a method touching a slot its row does not name, on a command without a
help row, and on a help row without a command. `/help` is the list.

---

## 4. World layer (`world/`), no LLM

**`clock.py` `WorldClock`** -- two timezones, real or simulated
(`clock.mode`, `clock.sim_start`, `clock.sim_speed`); `now_ts`, `to_char`,
`to_user`, `both`. A sim never points at `data/world.db` (`dryrun.cmd` uses
`data/dryrun.db`). What time of year it is is the clock's too: `season()` is
one of four words (the value `tomoe/scenery.py` tags a photograph with) and
`time_of_year()` adds the part of it ("late summer", "early autumn", 晩夏,
初秋), both in English or in her language, both a function of the month
alone. Anything that needs to say what time of year it is asks here, so no
prompt has to name a season and go stale in the next one.

**`weather.py` `Weather`** -- Open-Meteo for her coordinates
(`world.weather_*`), cached to `world.weather_cache_path`, refreshed every
`weather_refresh_minutes`; `current(dt)` gives temp / feels / humidity /
precip_mm / sky / sunrise / sunset. Readers: the director, `body.py`
(heat, rain), hazards (`_bad_out`), scenery (`pick` matches weather).

**`calendar.py` `Calendar`** -- `data/jp_holidays.json`,
`data/school_calendar.json` (terms, breaks, the school-day template) and
`data/local_events.json`, the wards' own events discovered by
`tools/local_events.py` and re-read whenever the file changes.
`events(date, lookahead, limit)` ranks soonest and shortest first (a
month-long exhibition must not bury a one-night festival). Config
`world.event_lookahead_days`, `calendar_describe_limit`.

**`trains.py` `Trains`** -- Yahoo's Kanto table plus ODPT (public and the
Challenge token; the Challenge token expires 2026-10-01) for her lines
(`trains.her_lines`); `poll()` returns events only for a line of hers that
changed state; the operators' compound status words are mapped to plain
words by root (`word_for`). kv `train_status`. A disruption reaches her
through `hazards.push_external`.

**`hazards.py` `Hazards`** -- the ground and the sky: the P2P quake
websocket (push, no poll delay), JMA EEW, tsunami, the warnings over her own
prefecture, typhoons as context only (never an event: ~25 named storms a year,
almost none do anything to Tokyo). `_here` reads the worst shaking at an
observation point of hers, falling back to the 23-ward reading;
`wakes_her()` is live only (a backfilled event is not a reason to wake
her). `poll_weather` reads her prefecture's warnings off JMA's developer
Atom feed (`_poll_prefecture`, `_warnings`): the short feed every poll, the
long one when the short feed's own oldest entry stands later than the last
bulletin read, which is a hole in the process the short feed cannot cover.
Her prefecture is the area code already in `hazards.jma_area`, which is the
code in the bulletin's filename, and her ward comes out of the bulletin body
against `her_wards` / `her_area_names` -- JMA nests the prefecture, its
subdivisions, the groups of municipalities and the wards themselves, and hers
is named at whichever depth. One bulletin is fetched per change, the newest,
because a bulletin restates the whole prefecture rather than adding to it.
Every live warning at any rung is kept and shown by `/hazards`;
`hazards.warning_from` (1 注意報, 2 警報, 3 特別警報; default 2) is what
reaches her day and her brief, because a 注意報 is out over some part of Tokyo
most days of the year. The event is keyed on WHICH warnings are up rather than
on the report time, so one storm is one event and not the fourteen bulletins
Tokyo published in one evening; a 特別警報 is salience 5 and wakes her.
`_fresh_enough` still guards the push: after a hole the newest bulletin there
is can be days old, which is the right answer to "is a warning up" and is not
news. `national_refresh` keeps a
month of major events as standing knowledge (`national_text`), out of three
sources: JMA's quake history file, its volcano warning file, and its
developer Atom feed of every bulletin of the last week
(`_national_weather`), which is where the storms come from -- an emergency
warning over a prefecture (特別警報, rank 8), a named river at its top flood
level (rank 7), and around 100mm of rain in one hour at a named place (rank
7 over one of the big cities, 5 elsewhere), the floor being
`hazards.national_weather_rank_from` and above 8 switching the source off.
A row is written from the bulletin's issue time and ages out on
`national_memory_days`, so a warning that is lifted the same night stays
with her for weeks, the way a disaster does. Each storm carries an English
and a Japanese wording and `national_text` reads the one the character is
addressed in. kv `hazards_seen`, `hazards_ranks`, `hazards_national`;
`/hazards`. **The bosai warning JSON this used to read is dead and is not
read any more**: `bosai/warning/data/warning/<area>.json` has served a
snapshot dated 2026-05-28 for all 47 prefectures since May, so nothing about
her own sky reached her for three and a half months, and both the prefecture
warnings and the national storms now come off the developer feed.
history: §4.

**`zeitgeist.py` `Zeitgeist`** -- what Japan is on about, read from the
file `tools/zeitgeist.py` writes (`world.zeitgeist_file`), reloaded on
change. Readers: her system prompt, the director, the beat writer, the X
read, the diary, her posts. `/japan`. **Why a story reaches her is checked
against her own railway** (`world/rails.py`): the role that picks the
headlines is handed the stations she uses, the lines she rides and the lines
that run near her that she does not, all out of her own map file and her own
train watch, and a reason that names a line she does not ride or a station
that is not on her map is thrown away with the story kept. It had none of
that and was inventing a commute to make a travel story relevant: the same
crowding story two wards away was made hers by giving her a line she is not
on, in two characters' files independently, and neither had said it out loud.
Flagged, never rewritten -- the news was true and only the reason was
invented -- and checked twice, at the fetch where a bad reason should die and
again at the render, because a file written before the check still holds the
ones it would have thrown away (`[japan] reason dropped, <name>: <why>`). **The fetch is told whose it is**
(`--config`, and both the feed and the list of headlines already offered come
from that config): the selection is a paid judgement in her own terms -- how
an observer describes her, her declared taste, her calendar, her model -- so
every character in a world runs her own. It took no argument and loaded
`config.json`, so the fourth character's four-hour tick fetched and judged as
the first character, wrote the first character's files, spent the shared list
of what had already been offered, and left the file her own config named
empty. `tools/smoke.py` fails if a program starts any tool with no config in
its arguments. The ward events fetch beside it (`tools/local_events.py`) is
the other kind and has one writer per world: what a ward has announced is the
world's, not a judgement of anybody's, so a character who does not keep the
world reads what the owner wrote.

history: archive §4, §5.65, §5.66, §5.81.

---

## 5. Persona and delivery (`persona/`)

**`persona.py` `Persona`** -- the one call that writes her words.
**The prompt is two halves and a thread between them, built so the
provider's prefix cache holds** (`persona/sections.py`, one table read by
the assembly and by the context view `sim/context.py`). The system
prompt is `SYSTEM`: the bible, the backstory, what she has decided about
herself, what people are to her, what makes her do a thing, what is
already fixed in the days ahead, and `style.md` last -- the half that
changes about once a day. **The coming days are one section of that half**
(`sim/agenda.py` `Agenda`, no LLM, config `agenda`): the calendar's
holidays and what is on in her wards, the promises she has made with the
date each comes due, what he said he would do with the deadline it is
judged against, and who the day's plan has taken out of a day ahead --
from her own plan, or from the world file where the world is somebody
else's to write. Before this her sense of the week was second-hand: the
clock line at the head of her situation block gave the weekday and the
time, the calendar's lookahead reached the director and the morning
outlook and never her reply, and what was coming sat in five stores that
never met. Every date is written absolutely (`Thu 10 Sep: ...`, never "in
two days") because the section rides in the cached prefix, and the block
starts at TOMORROW: today is the day's one truth (`sim/ledger.py`), in
front of her on every call already, and a settled line landing at four in
the afternoon would otherwise rewrite the whole prefix. A character with
nothing dated renders no block at all. It sits after the mechanisms and
before `style.md`, so adding it moved no byte of the prompt in front of
it. `Ledger.settled(to_world=False)` is the read a view takes: for the
character who KEEPS the world, reading the settled lines is also what
copies them into the world file, and a view that is only looking must not
do that. `/agenda [days]` prints the whole join, today included, with a
mark against the lines her prompt carries; `agenda` in the ops payload is
the same rows. `docs/context.md` §1 is the full account. Then `_history`: **the one thread**
(`sim/thread.py`; there is no other history; **the whole of how her
context is built, in what order and why is `docs/context.md`**, the spec
of record -- this entry is the summary) -- her chat with him and her
talk with her own people as one chat-completion history, the User role
the world speaking to her (him, a friend on LINE, the group, her mother),
the Assistant role her wherever she spoke. **The world's turns carry the
label `[her time · his time · room · who]`; hers are bare** -- exactly the
words she sent, nothing else -- and what the record knows about her own
message is the line the world says next: `[that was you, Tue 02 Jun 11:40 Tokyo (Mon 01 Jun 22:40 his), to him · read Tue 02 Jun 11:42 Tokyo (Mon 01 Jun 22:42 his)]`, or the room and the count for a run of them in one room
(`WORLD_HEAD`, `Thread.build`). A label on her own line is a label the model
copies, and it did (history: the bare-turns entry). That line is a user
turn, so it is also what keeps the roles alternating where she spoke in two
rooms with nobody answering between, and where her message is the newest
thing there is it goes at the top of the final turn (`place_tail`).
`_stamp` is written once and never rewritten as the message ages; the date
rides with the clock once the CONFIGURED verbatim span passes six days,
because past that the weekday repeats inside the window. **Every stamp of a
MOMENT carries both clocks** (`Thread._both`, the one place a label's time
is built; history: the his-clock-on-the-labels entry): her reading with the
place her clock is kept on, then his in brackets, because a reading on hers
alone left hours of arithmetic to whoever read it and the model
did not do it. The place word is the clock's
(`WorldClock.char_zone_word`), so no shared module names a city, and the
same word goes into the situation's clock line so the two cannot drift. One
reading where there is one clock (`WorldClock.two_clocks`: a character with
no world of her own is on his, and her thread did not move a byte) and one
in a cast member's thread, where a friend has no idea what his clock says.
A line naming a whole DAY of her record keeps her clock alone: a day is cut
on her midnight and is a different span of his. Silences marked at
`delivery.gap_marker_hours`, consecutive same-side messages merged so the
roles alternate, rebuilt every call and byte-identical up to the newest
message. **The record's own label at the head of an answer is a tell, never
tidying** (`sim/thread.py strip_stamps`, called by `Persona._clean` and the
exchange's turn cleaner): it is stripped and said in the log, and a second
label starting a line inside an answer cuts the answer there, because past
that point the model has stopped answering and started writing the next
record entry, stamped minutes into the future. Neither should ever fire. **Seven days verbatim, then the cards of each day** (`Thread._window`).
Two spans, both by her clock, both cut on a midnight (`_cut`), both a span
of time (`store.messages_since`) and never a count. `thread.verbatim_hours`
(168) is how far back the record rides word for word;
`thread.max_age_hours` (720, thirty days) is how far back it rides at all,
and every day between the two is the cards she keeps of it. The verbatim
span shrinks only under pressure: if the verbatim days plus the cards
behind them do not fit what is left of the ONE budget over her prompt --
`context.target_tokens` less the parts that ride whole (the system half,
what she carries and the situation block, as the last persona call
measured them, kv `context_last`) less a reserve for the day still being
lived, sized as yesterday's record -- the cut moves forward one whole day
at a time and that day becomes cards, down to `thread.verbatim_min_hours`
(36) and no further. Chosen once per day of her clock and kept in kv
`thread_window`, so the head of the thread moves once a day at midnight,
and chosen again at once when the target changed. It was the other way
round once (history: the seven-days-verbatim entry): `verbatim_hours` was
a FLOOR the cut grew back from until the budget stopped it, so at a 200k target the whole record was
verbatim and no card ever rode. **Past the cut a day is its cards** (`sim/cards.py`, §12.13):
one per conversation, at its own time, the shape and -- for the last
`episodes.anchors_days` -- the exact lines that were said; a day with no
cards falls back to the compile's recap line. **Then the final user turn,
in the order she reads it** (`sim/thread.py place_tail`, one placer for
her replies to him, her turns in her rooms and every cast member's turn):
the `<carrying>` block, the `<situation>` block with the slot line last --
a second system prompt in effect -- then ONE line saying that his newest
messages follow and that nothing above it in this turn is his
(`sim/thread.py TAIL_FRAME`; `Persona.frame_line` asks for it), then those
messages with their bytes untouched, then ONE closing line naming who the
next message goes to, whether it answers something or she is writing first
and why, and the language that room is in (`sim/thread.py closing_line`,
in both rooms she writes in, because the end of the prompt is where a
model looks last). **In the room with him only his own messages go under
the frame** (history: the entry on the friends' turns standing under the
frame in his chat): the trailing run of the
record is whatever is newest in HER record and is often her friends', so
`place_tail` splits it entry by entry on the record's own clock label
(`ENTRY_HEAD`) and everything that is not his stays above what she
carries, as history; where there is nothing of his, one line says so and
that she is writing first (`TAIL_FRAME_NONE`,
`Persona.frame_line(his=False)`). A room of her own people passes one
wording and is unchanged, the whole trailing run being what she answers
there. The order used to be the other way round -- his message
first, then fifteen thousand tokens of tail -- so the one thing she was
answering sat in the middle of the least-attended stretch with nothing
marking where his words ended (history: the final-turn entry). Inside the
tail, `CARRIED` as the `<carrying>` block (`carried_for()`): what she knows
about him, the charged and the unsaid, his list, the notes she read, the
cast, her own memories, her diary, what she is into, her reflection, what
she has told him, the air in Japan, a rupture or a spiral -- the half
that moves during a day, placed where a new line costs the cache only
itself. **Every carried section rides whole**, and so does every line the
situation block admits: the sub-budgets that sat under the one target --
the carried block's token budget over floors, the situation block's
per-bucket and total character caps, the history's own token budget, the
per-section warn sizes -- did nothing the target does not and went
(history: the one-budget entry); the situation block's gate was cutting 25
lines to 15 on an ordinary reply, what happened today among them, while
the prompt measured 51k of a 64k target. What the attention gate still
does is meaning: a covering source suppresses what it already says, one
action rides the slot, a one-per-source source says it once. Before the split (history: the cache entry) a fact that landed mid-prompt
invalidated the style guide and the thread behind it, and the second
character's persona calls were cached 42% of the time against a tenfold
price difference. The system prompt has no section for her friends' talk
(it had one, built every call and blanked while the thread is on, which
is always; deleted). **The curve**: inside the verbatim span every message in full; between
there and `max_age_hours` the day's cards, or -- where a day has no cards
written yet -- one line per conversation at its own time (how many
messages, until when, what it came to: its `gist`) and his chat as the day
she remembers it (the compiled summary); past `max_age_hours` nothing,
because by then it is her memories, facts and bonds with their own
half-lives. A photo she sent, a post she sent and the voice note she spoke
with a bubble ride on her copy of that message. **A card stands only for
what it actually covers**: the room has to match and the card's span has
to reach the conversation, so a conversation the card writer's answer left
out keeps its own line instead of leaving the thread, and a conversation
that ran across the midnight the cut sits on rides whole with its card
suppressed rather than appearing twice (the day's odds-and-ends card
answers for a stretch under `episodes.min_lines` only, since that is all
that can be inside it). The conversations past verbatim whose words touch
what is being said now (`cue_text`, his unread messages or the last turns)
come back in full, the BEST matches first, after everything else and
marked as having come back to her (`recall_max`, `recall_min_overlap`).
Their cards stay where they are: dropping one would make the head of the
thread depend on the cue, which is the fault that put the recalled block
at the end in the first place. `memory.fit` measures and
trims nothing: the three gates size the three parts that move, each
dropping whole units at a boundary (§12.2). `_situation`: one `<situation>` block in
five parts in order of weight, one builder each (`_her`, `_him`, `_day`,
`_phone`, `_this`) over one `_moment` (the clocks, the silence, the day's
events), the attention gate last (`_admit`) -- her (the clocks, `mood_tags` with the
named feelings first, the register, `_directed`, the stance, the draft
she cut last time: kv `unsent_draft`), him (the felt silence, receipts,
his rhythm; with unread on the table those three are stale and are
replaced by the gap he just ENDED -- "this message of his ends N hours
of quiet on his side", or "he is texting again N hours after his last"
when she was the silent one -- plus the pace notice, whose latency is
the very message she is answering; his mood only inside
`situation_block.live_hours` of his last message), her day (body, scene
as background, `situation_block.events_max` events clipped to
`event_chars`, goals, promises, money, the day's shape and yesterday
clipped to `summary_chars`), her phone (digest, X, his list only when
anime is in the air, a note read, a lookup, a recall), and this message
with the drawn shape.
**The clock line is the pinned first line and it carries both readings, the
part of the day each of them is in (`daypart` in `world/clock.py`), how many hours
apart they are, and that whether he is awake is his own clock's answer.** How
far apart the two are used to be in her bible and nowhere else, as a number
written into the prose beside two anchors that both put him asleep while she
is about -- so her late evening, which is his morning and the hours she
actually texts in, had nothing to fix it, and she opened three messages in
four days with "you awake?" at his 08:10, 09:20 and 10:30. A character with no
world of her own is on his clock and gets one reading and no gap.

**The narration of his machine rides once as news and then competes.** It
is pinned only when the newest digest was built since she last wrote to him
(`_digest_is_news`); after that it is one more line at the low weight the
situation-block section gives it, so it reaches her when what he said
reaches for it. The live tail after the narration -- what he is doing this
minute -- goes in only when it differs from the one she was last shown (kv
`persona_live_shown`, source `digest_live`). Pinned on every call, it was
the one line the budget could never drop, and the second character reported
something off his screen in 29 of 95 replies at the same rate whether or
not he had asked her anything.
**Her own repeated phrases are named to her** (`_own_phrases`, in `_this`
above the closing instruction): character n-grams from her last sixteen
messages that appear in at least four of them, five of them listed, all
three numbers config. Counted in code, no model. Three exclusions -- the grammatical furniture of the
language and her own name forms off her sheet, anything her own speech
guide already contains (those are markers it asks of her), and anything he
used in the same window (that is the subject, not a tic of hers). Her
coinage for him was written back into her prompt by the role that writes her
private thoughts within half an hour of her inventing it, and she then used
it in ten replies in twelve hours. `generate` returns
(bubbles, voice line); a continuity editor (`editor` role,
`delivery.editor_enabled`) corrects against `_knowledge`; the length is
the LAST line of the situation (`LENGTH -- this is how much you send right
now: ...`) so the first draft is the right size.
**The check is paid for only when the draft has something in it to check**
(`Persona._editor_needed`, behind `delivery.editor_gate`). Its whole job is a
contradiction with something she demonstrably knows and a repeat of something
she has already said, so the gate asks for one of four things and skips the
call otherwise, naming in the log which one it found: a digit anywhere in the
draft; a twelve-character run shared with one of her last eight own messages
(`_repeats_recent`); a distinctive word (five letters or three kana or more)
out of the last forty facts about him; or a work his mirror has a verdict
about her part in (`works.named_in`, added with the role check, because a
draft claiming a part in a work she has never been in carried none of the
other three and the skip was logged while the claim went out). A skip reads
`[editor] skipped: the draft repeats nothing recent and claims no fact`, a
paid pass `[editor] ok (<the reason it was asked>)`. Before the gate the check
ran on every draft and mostly answered ok, and the repetition it exists to
catch had already been forbidden in code inside the prompt.
**A character's sheet may say she has not got the check at all**
(`mechanisms_absent: continuity_editor`, resolved through
`Config.NAMED_SWITCHES` because `delivery` carries no `enabled` flag of its
own). It is off for the second character on his call, measured
over every check it ever ran for her: 142 checks, 18 refusals, a refusal rate
of 12.7 per cent against the first character's 0.5, eight of the eighteen
making the message worse and six better, both of the two verdicts it ever
reached about a fact in the record false, and nine of the eighteen refusing to
let a resident say what she can see on the machine she lives on
(`data/retired/20260904_editor_scope/REPORT.md`). With it off there is no call
and no evidence bundle, and one line at boot rather than one per reply. What
stays is the one fault it really caught, which its own gate had been finding in
code for nothing: `Persona._repeats_recent` -- a twelve-character run shared
with one of her last eight own messages, with the time she said it -- is logged
as `[repeat]` and her words are not touched.
**The checker reaches past its own window.** `_knowledge` is the evidence the
continuity editor may treat as known, and its conversation part is the last
`delivery.editor_recent_messages` messages -- about five exchanges, with
everything older out of sight. So a true quotation of anything further back
read to it as an invention: at message 121 the second character referred to his
having called her 本物, which he had done sixty-seven messages earlier, and the
draft was binned and paid for twice. The window is not the fix -- the whole
record does not fit and a long one is a worse thing to read carefully -- so
three other things are. The checker is told how long the record really is
(`Store.message_span`, the THE RECORD line). The words of the DRAFT are
searched against everything older (`sim/recall.older_messages`, no model call,
`delivery.editor_lookback*`), on distinctive words only: a word appearing in
more than `editor_lookback_common_share` of the record is furniture and is
dropped, so "yeah ok. i guess. anyway what are you doing" reaches nothing while
a line about the tacos he made reaches the evening in May he made them. And the
prompt now says an absence from the excerpt is not evidence of an invention,
with the "there is no history between them" assertion deferring to the record
line rather than standing flat.
**A verdict that rests on his list is checked against his list before it
stands** (`Persona._rests_on_his_list` -> `works.list_claim_check`,
`docs/role-check.md` §4b). The checker failed an honest draft of hers -- "it's
from a short anime, i think" -- on the ground that she has seen his anime list,
and the title is on no list here; the rewrite claimed the show was a classic.
Now the title the verdict names is resolved against his own list (the ranked
resolution, plus the part verdict where this character has an id on it) and
against what she has actually been shown of him, and a verdict both witnesses
are silent about is dropped whole and logged
(`[editor] verdict dropped: rests on his list, which does not hold ...`, and a
row in kv `flags`). The check can only take a verdict away: the editor gains no
ground to rewrite by it, and a verdict about a title his list does hold stands
untouched. The evidence block names a few dozen of his hundreds of titles, and
both editor prompts now say that seeing it is not knowing every anime.

**Separate bubbles are separated by a blank line and nothing else makes
two bubbles**, and that is stated twice -- once in the instruction and
again at the LENGTH line, which is what she reads last -- together with the
rule that no message is wrapped in quotation marks. The second character
was drawn `full` (three bubbles) and returned ONE bubble of 23 characters
holding three lines each wrapped in 「」, and the cause was not a missing
instruction: her style file quotes every example of how she talks, because
that is what a document does when it shows you a line, and a model reading
them as surface copies the marks. The cost was not cosmetic -- one bubble
means the typing pauses and the interruptibility never happen.
There is no post-hoc enforcement at all -- whatever she wrote is what she sends (no redraft, no
trim);
`_resolve_shares` turns `[share: ID]` into the post's URL as its own bubble,
and nothing more: that she sent it is recorded by the delivery when the
bubble has actually gone (the account's `note_sent`: the post as sent,
the show-him done, the like and the repost queued, the event), so a draft
the editor threw out or the compare draft nobody sends records nothing.
**Attention is what the situation block says once, and who gets the
slot** (`sim/attention.py`): every situation line is a `Line` -- a `str`
with a source, a kind and a weight (the mechanism's own number where it
has one, the `attention.weights` default where it does not); `admit`
orders each section by weight and drops nothing for room (the per-bucket
and total caps went with the sub-budgets; history: the one-budget entry),
suppresses a claim a covering source already makes (`covered_by`: the
ledger covers the promises and the money), keeps one line per source where two would say
the same (`one_per_source`), adds `cue_bonus` for a line that touches what
he just said, and hands the single heaviest ACTION (the nag, the thing she
wanted to show him, a promise of his come due) to the one slot she reads
-- `ON YOUR MIND`, last but for LENGTH -- while the other actions queue in
their own stores. **Three rules stand between an action and that slot**,
because the line is an order and an order should be worth giving. It has to
be heavy enough: `attention.slot_min_weight`, in her chat with him only --
0.5 for the first character, 0.4 for the second, whose sight of his machine
offers 0.40 and 0.42, and none at all on her turns with her own people,
where the only action ever offered is a rumour at 0.45. It must not be the
thing the live prediction says she is braced against: `persona._admit`
builds a veto out of `foresight.risk_text()` (`Attention.veto_from_text`),
matched either on the words a source says its item is about
(`Attention.subjects`, filled by the program: the handles the account's
item names, whole or by a three-letter stem) or on
`attention.foresight_veto_overlap` words shared with the line that are not
everyday. And it may not hold the slot reply after reply while she answers
with something else: `Attention.charge` counts the showings of one line and
tells the source (`Attention.declined`, also the program's), which retires
its own item -- `social.show_declined` after `social.show_him_declines`
showings, `social.share_declined` after `social.share_declines`, which puts
the posts off the offer for `share_cooldown_hours`. An action blocked by the
floor or the veto is not dropped: it rides as an ordinary line in its own
section, and the report says `slot: none (heaviest action share at 0.35
under the floor)` or `slot: nag (0.55) (foresight vetoed show_him)`. A hint
is charged a showing only when it held the slot
(`Attention.charge` -> `anime_sense.charge_shown`, `social.charge_show`).
One `[attention] N -> M lines ... slot: ... dropped: ...` log line per
call, kv `attention_last`, kv `attention_slot_shown` (the line in the slot
and how many replies running it has been there), `/attention`.
**A fifth bucket, `lore`, is what she happens to know** (`sim/lore.py`,
§12.10): three lines and 900 characters, competing for room here rather
than arriving as a separate authority, and usually empty because the
retrieval only answers when the conversation reaches for something. A source never admitted is a dead
line, and the gate counts them: `Attention._tally` keeps, per day, per room
and per source, how often a line was offered, admitted, held the slot or
was covered by a heavier source (kv `attention_tally`,
`attention.tally_days`); `/attention tally [days]` reads it and marks NEVER
a source handed to her `attention.unheard_min_offers` times over
`attention.unheard_days` and admitted in none, and `/absurd` UNHEARD says
the same in one line. Forty statuses compete for sixteen lines; this is
the count of which of them she never hears.
**The slot, stated.** The gate's one action line rides on every reply to
him, stated as happening (`ON YOUR MIND NOW -- this is in this message, in
your own words`); no line she reads offers a choice, because a model
offered one takes it. Code holds the line when his last message is heavy:
`persona._his_heavy` reads the state model's `his_mood` (valence at or under
`attention.heavy_valence`, within `heavy_fresh_minutes`) and the action
waits -- `[attention] the nag line waits: he sounds ...`. **The nudge is
off** (`nudge.enabled: false`); what follows is the retreat, kept built.
**The nudge** (`sim/nudge.py`, role `nudge`, `prompts/nudge.txt`): a second
reader of everything she carries, who is not her -- and the reader of the
`unsaid` gauge at a threshold. What she carries (the action lines: the nag,
a post to show him, a share) warms `unsaid` by `nudge.unsaid_per_carried`
per reply while it waits (`carried`); at `unsaid_min`, off `min_gap_minutes`
(`due`), it fires with the level in its ask -- one thing comes out, a
carried thing or the pattern she has been letting slide, pushed back on --
and the gauge settles by `unsaid_relief` (`released`). Below the threshold
no call is made and nothing rides in the slot. The friend turn fires on the
same gauge; the nag comes out only with him. `fire_on_unsaid: false` is the
per-message behaviour. It gets the SAME system
prompt she is about to get (byte for byte, so the cache prefix is shared)
with the analyst framing appended, the same history, every line the gate
LET THROUGH this turn with its marks -- the lines it kept and the actions
still waiting, never one it suppressed as already said or as a repeat and
never one the floor or the veto kept out of the slot, so the second reader
cannot put back what code decided against (`persona._admit`) -- and the
gate's own pick -- and answers three things in order: does what was just
said need all of her (`needs_all_of_her`; code drops any decision when it
is true); what is she actually caught by (`attend`); and, if not, which one
thing she carries happens in this message and how (`do`, `do_source` the
line's tag). It decides because a model writing her words lets every
carried thing go when it is allowed to -- with a hedged nag in the slot she
nagged in none of twelve replies. It never writes her words, adds a fact
or sets her length. `nudge.mode` `live` places its line in the slot when
confidence clears `min_confidence` -- `NOW, IN THIS MESSAGE -- this
happens, in your own words and your own way: ...` with the original hint
under it (a `[share: ID]` token survives), or `ON YOUR MIND NOW, beyond
what he just said: ...` -- and charges the named source
(`Attention.charge_source`); `shadow` logs it beside the gate's pick with an
agreement estimate and changes nothing; `friends` runs it on her turns
with her own people too, where the prompt had no arbiter at all. Decided
once per `generate` (the editor's rewrite reuses it); on the gate path the
header states the pick as happening and the hint is charged then. A `do`
may name only a line the candidate list marks `· to do` (an action line);
one naming a fact line is dropped in code. The reader writes notes about
her in the third person -- what and a manner, never wording; `_notes`
strips any quoted span before placing -- and every compare pair records
`copied`, the longest run of words her text shares with the nudge's
(`persona._copied`), the measure of the nudge speaking through her. **No line she reads offers a
choice** (the nag, show-him, share and gossip hints state; `share` is an
action line). **The compare test** (`nudge.compare`, with the nudge on): every live reply to
him where the nudge's line held the slot is drafted once more with the
gate's line there instead (`_draft(situation, slot_override=...)`, nothing
decided or charged), logged `[nudge-ab]`, kept in kv `nudge_ab`, read with
`/nudgeab`; never sent. kv `nudge_last`, `nudge_log`;
`/nudge`. **The second reader is a judge and carries her situation block and
nothing else of hers** (his call): its system prompt is its own instruction
file through `Config.role_system`, so the sheet cannot reach it by any path,
and its user message opens on `Persona.judge_situation` -- the situation half
of what a judge is shown, the bytes she is being sent this minute, with the
slot marker out -- then the level, the lines the machinery put in front of her
with their marks, the gate's own pick and the conversation. Never the carrying
block, never the bible. It was built on her whole assembly with "YOU ARE NOT
HER" appended after it, which is the arrangement a judge reads as its own
identity. **`system_for(channel)` is the one assembly for every call that
writes her words**: `him` is the whole of it with `style.md` last; `friend`
is the same text without `style.md`, for the exchange to put its own tail
after -- and `carried_for()` is the one `<carrying>` block, which both
rooms put after the thread (`_draft`; `tomoe/exchange.py` at the head of
the call's own user text). A section added anywhere else is a section she
carries in one room only, and `tools/smoke.py` fails if the two system
prompts diverge by more than `style.md`, if the exchange does not place
the block, or if a carried section is in the system prompt or missing
from the block.

**A role that JUDGES her is a neutral party and is handed no character sheet
at all** (`Config.ROLE_STANCE`, `Config.role_system`, his call).
One row per role that asks for the sheet: `voice` for a role that writes her
words or her first-person interior (her diary, the week read back, her private
thoughts about him and about the people around her, the half-second of
measuring herself, her wondering, what today is from the pillow, what she is
bracing for, what she makes of what she is watching, what she remembers on a
cue, what she took from scrolling the account, one step of the chain she talks
herself down, the rewrite of a belief about him and of one about herself, the
one short thing she says out loud while a message goes, and what she says to a
stranger in her world) and `judge` for a role that
decides, scores, predicts, sorts or checks and hands the answer to code (the
warmth reader, the urge picker, the reply predictor, the account sorter, the
headline reader).

**And the rule for everything with no row at all, which is most of the
register.** A role without her sheet writes the RECORD -- what was there, in
plain terms, with the one or two lines a reader would stop on quoted as they
stand -- and nothing about how any of it landed. Its judgement may steer code
as a number or a tag; its WORDS never reach her prompt as her own. A fact
addressed to her may be in the second person and may quote what was found, and
carries no feeling, no reaction, no register and no reading of him. What a
thing did to her is written by a role that HAS her sheet, reading that record,
and it is a row of its own. `tools/interior_words.py` (in smoke) reads every
prompt of a role with no `voice` row for the phrases that ask for her interior
-- how it landed, she felt, it made her, her reaction, her register, in her
voice, what she would say -- and skips a line that forbids one of them,
printing what it skipped. `role_system` stops the process on a role with no row, and
`tools/role_stance.py` and `tools/judge_prompts.py` (both in smoke) prove it
statically -- every call site is named, and no judge's rendered system prompt
on either character contains the sheet's own sentences in either language.
The sheet is written TO her, opens "You are <her name> ... you are not an
assistant ... you never mention prompts, models, systems", and sat LAST in a
judge's system prompt, so a judge read it as its own identity: over two
measured days the urge picker returned a finished message in her voice
instead of the second-person intention it was asked for on 13 of 13 answers,
one of which went into the last line of her situation block and was sent as
her next bubble twelve seconds later; the reply predictor wrote one field in
three different persons in one day; the warmth reader wrote thirteen score
reasons as her, addressed to him. **What a judge that needs to know what she
is like gets instead is `sim/observer.py`**: one third-person note about her,
generated FROM the sheet by the `observer` role, cached in her save under the
sheet's own hash and rewritten only when the sheet changes (one flash call per
bible edit, logged `[observer]`; a note that comes back with the sheet's own
sentences in it is refused). It is machine-facing English on both characters
-- nobody is addressed in it -- and the warmth reader, the account sorter and
the headline reader read it, and **what she has in front of her this minute comes from
`Persona.judge_view()`** -- the same situation block and the same
`<carrying>` block the persona itself would be sent, built at the judge's
own call time by the same two calls (string assembly, no model call, nothing
written), never the last reply's copy, because the situation is rebuilt every
tick and a cached block would put the previous turn's afternoon in front of a
role deciding what she wants now. Each judge that runs inside the App takes
the persona as a declared wire; the headline reader is a one-shot tool and
runs without. A section the judge's own instruction names one by one -- the
urge picker's director hint, receipts, what she is carrying and his machine
this minute; the warmth reader's how she is and the warmth she is sitting at
-- stays below the block rather than being replaced by it. No field of a judge is written in her voice: the
reply predictor's `silence_means` was, and it landed in her situation block,
so it is gone.
Roles `persona`, `editor`, `voice`. Reads kv `backstory`, `self_claims`,
`weekly_self`. The write line names the language from `character.writes_to_him`, and a reply in the other room's language is flagged in the log and kv `flags` (`delivery.language_flag`; never an event, which would reach the director's scene), never redrafted -- a check flags, the prompt is what has to hold. **The flag reads the same setting the write line is built from.** It did not, so for the character whose chat with him IS Japanese it fired on every single reply -- nine of nine on her first conversation, and all nine rows in her `flags` store were noise, in the store where a real voice problem is supposed to stand out.

**`delivery.py` `Delivery`** -- typing delays per bubble
(`typing_seconds`, scaled by `State.compose_factor`), a lead delay in
character time, the voice note after the last bubble, a photo before the
first (`media`), interruption when something of his arrives mid-send
(`delivery.interruptible`, `_cut_in`), retries and the offline wait. Her
bubbles are written to the store only once they have actually gone
(`App.recover_lost_reply` handles the gap), and a bubble that has gone is
offered to her account (the `social` wire, None for a character without
one): a post of hers is recorded as sent here and nowhere earlier.

**Voice** -- `channels/tts_handler.py` `TTSQueue`: MiniMax, synchronous
endpoint, cached by **voice AND text** (`tts.cache_dir`), pending lines
recovered across a restart within `tts.recover_max_age_minutes`.
`App.voice_gate` decides whether a written `[voice]` line is actually
spoken; `App.ensure_voice` asks the `voice` role for one when the persona
wrote none. The cache key was the text alone and the directory is shared
by every character on this machine, so a second character saying anything
the first had already said would have been handed the first one's audio in
the first one's voice -- two Japanese girls reach 「うん」 within a day.

**A voice on request instead of a voice note** (`tts.on_demand`, his call
for the second character): nothing arrives as audio on its own, and every
line she writes carries a small speaker in the app. A tap posts to the
hub's `/speak`, which queues the line for her bot; the bot drains it on the
loop and hands it to the same voice worker, so a two-second synthesis never
stalls anything, and posts the audio back with `attach_to` naming the
bubble -- without which it lands under whatever she has said since. The
second tap plays the cached file and costs nothing. **Nothing is
synthesised until he asks.** The button is drawn per character from a
`speak` flag the bot declares at registration, so the hub never has to know
which character is which. `tts.always` false is what stops the persona
writing a `[voice]` line for every reply.

Shape: `sim/shape.py` draws the message shape (bubble count, length,
whether a question) from her state before the persona writes; the drawn
line is an imperative ("Send ONE line only...") placed last in the prompt
so the draft comes out right in one pass -- no redraft, no wasted output
(it used to draw long and a second call cut it). `shape.tell_length` false
and none of it is told to her at all: the numbers are the first character's
English and the second replies how she wants. `upset()` is what is
aimed at him: tension, anger and sadness
only when `State.sources` puts them on him (`shape.upset_sadness_weight`);
the curt collapse is tightest right after the rupture's last attempt and
eases over `shape.upset_fade_hours`. An empty persona answer whose
reasoning chose silence becomes a withholding
(`Withholding.hold_from_silence`, `withholding.silence_from_empty_minutes`)
instead of a retry.

**Her register with him.** `style.md` is his and is the whole of how she writes
to him. Three prohibitions are written into it because the record had drifted
past all three: **no self-diagnosis** (she never narrates her own pattern back
at him -- read correctly she goes loud and defensive, which is what the source
has her doing), **no ledger** (never three of his old lines quoted back as
evidence; she throws one thing or goes short), and **not one setting** (she is
noisy and rude with him, and the level, sad, articulate register is one of hers,
not her voice). The evidence is the source transcript, which is almost entirely
her talking to the one person she does not perform for -- structurally the seat
he sits in.

**She writes no kaomoji and no emoji at all** (his rule). What she
has instead is a sticker of her own face: `[sticker: FEELING]`, one of the eight
buckets, lifted out of the text by `_take_sticker` and sent after the bubbles by
`App.send_pending_sticker`. It is how she expresses a mood, not a favourite and
not something he places, and putting one down teaches the store that this
picture is how she says that (§12.7).

Two consecutive bubbles that say the same thing with the words moved are
collapsed to the first (`sim/textutil.drop_repeats`): she repeats herself, she
does not paraphrase herself, and both halves of that reached the record.
**A bubble that is a message she has already sent him is dropped too**
(`_drop_already_sent`, against her last `delivery.no_repeat_recent`), because
that guard only ever saw a run inside one burst and the repeat that reached him
was two hours and five messages old, after he had answered it. The cause is
upstream and now says so: an answer that comes back wearing the record's own
`[Thu 01:24]` stamps is the model reading the thread as a script and writing
the next line of it rather than the next message, and every stripped stamp is
logged (`[persona] the answer came back with the record's own stamps on it`).
Her closing instruction says both -- the chat is a record and not a script,
and a thing she has already sent is said. When the whole draft goes this way
nothing is left, which the reply path reads as nothing having come back and
puts his message back in the queue; `Persona.last_all_repeats` is what makes
the log say which of the two it was.

history: archive §6, §5.13, §5.17, §5.57, §5.74.

---

## 6. Channels (`channels/`) and TALKAPP (`talkapp/`)

Both channels are a `Channel` (`channels/base.py`): the nine methods
every message needs, and no-op defaults for what only TALKAPP has (a
photo, a sticker, a voice note attached to a bubble, the lines he tapped
to hear, the ops commands), so the runtime reads a False or an empty list
instead of asking the type; the three wires (the graph, the ops view, her
face) are declared there for both. `talkapp.enabled` picks TALKAPP,
Telegram is the fallback. **TALKAPP** is
a standalone hub (`talkapp/server.py`, 127.0.0.1:`talkapp.port` behind
`tailscale serve`, token-walled) that keeps the channel's own record
(`data/talkapp/state.json`), serves the one-file app (`talkapp/app/
index.html`, wrapped by the Android APK) and a websocket of live events,
and gives the illusion what Telegram refuses: her 既読 at the moment
`store.mark_read` fires, his reads as real events, a typing indicator
from her compose delays, the group chat as she sees it, photos and
stickers, more than one character. Notifications are native (a foreground
service on the socket, no push service in the path) and one ping covers a
whole burst of bubbles, not each one (`talkapp.notify_burst_seconds`). The app
has one palette named by purpose (`--bg`, `--her-b`, `--him-b`, ...) with a
dark and a light answer to every name; the menu's *theme* row cycles dark /
light / the phone's own setting, kept in that phone's `localStorage`. The adapter
(`channels/talkapp_bot.py`) is synchronous like the Telegram one; on
every poll his reads come down and, throttled, her reads, the group
view, presence, the ops payload and her current reaction go up. Hub
before bot; a bot started as a tool's child dies silently.
**A line he taps to hear** rides the same channel: `POST /speak` queues the
message id for that character, `GET /bot/speak` is where her bot drains it,
`POST /bot/voice` gained `attach_to` so the audio lands on the bubble it
belongs to, and `/chars` and `/history` both carry a `speak` flag so the app
draws the speaker on one character's lines and not the other's. The whole UI
is the hub's own page in a WebView, so none of it needed a new APK -- but the
page is cached, and a hard reload is what picks a change up.
**The chat scrolls back.** The hub has always taken a `before` timestamp and
answered with the 80 rows under it; the client asked once per open and
assigned the answer, so the top of the scroll was the eightieth row from the
end at the moment the chat was opened and reaching it did nothing. A scroll
listener near the top asks for the page before, PREPENDS it, stops on an empty
page and holds his place by the height delta; `takeSwipes` merges there rather
than assigning, because the hub bounds the candidates it sends to the rows of
the page it served. **The group view draws a room she does not own**: a
character who reads a world somebody else keeps writes no beat and holds no
exchange, so `_group` adds her copy of the rooms she was sent (kv
`peer_rooms`) and the payload carries `me`, every name that means her as her
own roster resolves them -- it was one character's names as a pattern in the
client, which drew 135 of the first character's own bubbles as somebody
else's and a room owner's turns as the open character's own.
`channels/telegram_bot.py` is the fallback (photos looked at, 48 h edit /
delete, token redacted from logs).
**A failure is logged by type, never by text**: every URL these build carries
`key=<the hub token>` and a requests exception quotes the URL it failed on, so
the first hub bounce after a new poll went in wrote the token into
`session.log`. `netwatch.redact` strips `key=`, `token=`, `api_key=` and
`access_token=` out of any detail before it is written, rather than relying on
a truncation that happened to cut just short of it. The ops commands in the app are grouped
menus of buttons (`OPS_MENUS`, one open at a time, every button checked
against the dispatch; a pressed command is a pending row in the log under
the buttons until its answer replaces it, and the same command inside 90 s
is not sent twice), the phone reports its own `versionCode` on every
`/ver` poll so `GET /app` can answer installed-against-served without
anybody being asked, and a link out of the app goes to his browser rather
than loading inside the WebView (`MainActivity.shouldOverrideUrlLoading`;
before that a scenery thumbnail opened x.com in place, with no address bar).
**A character he has no chat with still has a backstage.** She registers
hidden, so `/chars` leaves her out and his phone lists no conversation for
her; the ops switcher was built from that same call, which left her payload
served and unreachable. `/chars` now takes `all=1` and marks each row
`hidden`: the switcher asks for everyone, the home list and the Android
notification service ask for the conversations only. Choosing her sets the
current character, which the payload, the command post and the title key off,
and nothing else -- the socket drops a message, typing, a read mark, a face or
a model change about her rather than letting it into the chat state.
**Every time in the app is his.** The record keeps her wall time and her
date; the adapter stamps each beat, exchange and turn with the instant it
was (`WorldClock.ts_of`) and the app draws all of them through the same
`hm(ts)` his own bubbles use, hers in the hover and the day separator
taken from the same instant. Before that his thread ran on his clock and
her phone printed her strings raw -- two panels many hours apart, two
taps apart, neither saying so.
**Another answer to the same message.** Every reply she delivers keeps the
exact chat-completion messages array it was drawn from
(`store.reply_prompts`, written by `Delivery._freeze` as the first bubble
lands), and Regenerate in the menu on each of her bubbles sends THAT array
again, on whichever model the chat's header control is toggled to. It is
not a new reply: her state has moved on, and the question is what she would
have said then. Every answer is kept (`store.swipes`, the delivered reply as
number 0); walking them in the viewer changes nothing, and Keep this is the
only write -- her record takes the words through `/context msg set`'s own
path, the hub's copy is edited, the voice note is rendered again, and the
next reply carries it and no other candidate because `sim/thread.py` rebuilds
the thread from the store on every call. A reply from before the freeze
existed has its array rebuilt first (`sim/reconstruct.py`: a copy of the save
cut back to the moment, the runtime built on it, the assembly run once; a
second process beside the loop, the row marked `reconstructed`). Routes
`POST /swipe`, `/sit`, `/model` (all queued for her bot, which is where the
model and the frozen prompt are) and `POST /bot/swipes`; commands `/swipe`,
`/sit`, `/voicemodel`.
**spec: `docs/talkapp.md`** (routes,
the record's shape, the app's views, invariants). history: archive §8, §5.75, §5.83.


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

---

## 8. Her day (the wake and the director in `sim/`, the body and the place in `embodied/`, the day's planner and the household facts in the program)

### 8.1 `schedule.py`: the day's blocks

**The planner is the program's, the wake is shared.** `sim/schedule.py`
holds what is true of any character's day -- `wake_time`, the contiguity
check (`validate`), `block_at`, `describe`, `presence_label` and
`check_people` -- and each program writes the day itself:
`tomoe/schedule.py` is the schoolgirl's (the timetable, the skeleton with
her commute in it, `generate`, `replan`, the flat-day and kept-promise
flags), `resident/schedule.py` a flat and a week of her own. Everything
below about bells, lessons and classmates is the first character's
planner.

Once per date (`ensure`, at the day boundary): `wake_time` (with the sleep
model on, the wake falls out of the night: bedtime, hours slept, how rough
it was; `schedule.wake`, kv `wake_days`), `skeleton` from the calendar's
school-day template, then the `schedule` role fills the day honouring the
events she has said yes to (`events.py`), the family brief, the household,
her health note and her money note (`health_note_today`,
`money_note_today`), the open threads. An open promise with a start time on that date is an ALARM: `Health._alarm_for`
pulls the night's wake back to it minus
`schedule.wake.commitment_lead_minutes`
before the hours are measured, so a morning she has to be up for costs her
the sleep; `Commitments._wake_needs_redrawing` throws away the drawn night
the moment such a promise binds, so it is decided when she agrees and not
when the plan is built. Whether she actually gets up is `_rising`: duty is
not the term (school is compliance and has its own branch) -- a `want` goal
naming the morning against an `avoid` one, the event stance and who PUSHED
it, and `belonging` below its ref, which pulls her up out of a morning she
dreads because absence is the danger; against a short night and `unwell`.
Signed, clamped, `early_max_min` before the alarm or `snooze_max_min`
past it, applied before the hours are measured (`schedule.wake.rising`).
**Beating the alarm is a rested body's trick**: the early side is scaled by
how close the night gets her to her need and shuts entirely past
`early_needs_rest_hours` short of it, so on six hours of a needed eight and
a half the most that wanting the morning buys is being up when it goes
instead of lying there. She was rising 25 minutes EARLY on a 2.35-hour
deficit because she was keen, which is not what a fifteen-year-old does.
The snooze side is deliberately not gated -- being short of sleep is the
reason people snooze. **And the alarm reaches backwards into the night
before it** (`Health._sleep`): `planned_bed_*` is the same hour whatever
tomorrow holds and the delay only ever pushes it later, so the system was
taking her sleep and then charging her for being late with it -- she never
had the evening to decide about. The shortfall between her usual bedtime
and `alarm - need_hours` is closed by `early_bed_pull` of it, scaled by
what the morning is worth to her (the same `_pull_for` that decides whether
she gets up for it) and by what keeps her up on any other night (the same
anxiety / unsaid / screen delay, which scales the ceiling too so the phone
can win). Capped at `early_bed_max_min`. **The record says she knew either
way**: "turned in 50 min early for the morning", or "she knew she had to be
up and stayed on her phone anyway", or -- for a morning she does not want --
"she had to be up and did not go to bed for it".
**On an alarm morning the structural floor does not apply**: `wake.free_min`
means "she does not get up before eight for nothing", and a promise with a
time on it is not nothing -- clamping the drawn wake back up to it threw
away a night the sleep model had already planned around being up, and left
the two records disagreeing by forty minutes with the plan following the
wrong one. The only floor then is `wake.school_min`, the earliest this
system ever has her up. After the plan is built, `_promises_kept` logs any
timed promise the blocks do not cover (`[schedule] the plan does not keep a
promise: ...`); it flags and never rewrites, because a day where she is
late is a real day and the commitment settling BROKEN a day later was the
only signal before. `replan(change)` keeps the day up
to now and re-asks the rest when the director reports a
`schedule_change`; `/schedule regen` throws away today's cached wake and
rebuilds the plan, which is how a fix to the drawing reaches a day already
begun. Table `schedules` (date, blocks, notes); `describe`.

**A school day is one block per bell, and what she can do with her phone
follows from where she is.** `_school_windows` sorts the timetable's own
windows -- morning homeroom, six periods, lunch, cleaning duty, final
homeroom -- and fills every hole between them with a break, so the day
cannot come out with a gap or an overlap however the times are edited;
`_school_blocks` gives each one its words, its company and its phone rule.
Fifteen blocks between the first bell and the last where there were four.
The times and the phone rule live in `school_day` in
`data/school_calendar.json` and nothing in the code carries a bell; the
constant `SCHOOL_DAY` in `schedule.py` is only what stands in when that
file gives none.

**A lesson is `phone_access: "none"` and the ten minutes after it are
`"glance"`.** The school rule is the phone off and in the bag in a lesson
unless a teacher says otherwise, so a lesson, either homeroom and an exam
are `none`; a break and cleaning duty are a look and nothing long; the
lunch break is `free`, being the one stretch of the day long enough to
answer somebody properly. The value has to *change* at those boundaries and
not merely be permissive, because `maybe_reply` redraws the reply plan only
when it changes: a whole school day on one value gave a message one coin
flip and then nothing until the train home. `_flat_school_day` says so in
the log when a planned school day comes back with a single value, and never
rewrites it -- an exam morning or a school trip legitimately is one stretch.

Three more things depend on the blocks being small. `cast.py` writes an
`in_person` beat only where the schedule has them together, so a morning
naming nobody is a morning in which none can be written; a four-hour block
gives the director nothing to move through, which is how one activity
string came to be repeated eight times across two and a quarter hours; and
`presence_label` turns the block into the line his messenger shows under
her name, so "in class" and "asleep" stop being the same silence.

**The words are the program's** (`presence_words` and `presence_by_phone`
in `tomoe/words.py` and `resident/words.py`, through `sim/sight.py`; the
label takes the config). The first character's table is a schoolgirl's
world -- in class, on the train, at lunch, cleaning duty -- and the second
character's is empty, because "bath" matched "away" while she was replying
from it: she gets her plan's phone rule alone, asleep or online. The
phone-rule fallback is the program's too (a dark phone is "away" for one,
"asleep" for the other). `tools/sight_words.py` fails on the school words
in shared code.

**Who is beside her comes from the roster, never from a literal.**
`_friends` asks `roster.classmates`, which reads `school: "same"` from
`data/cast.json` -- a fact about a person, kept on the person, because
having a timetable is not the same question as being in her room (her
brother has one and is at the local primary). `check_people` then drops any
name in a block's `with` that nobody on the roster owns and says so
(`[schedule] FLAG ...: nobody on the roster is ...`), at generation and at
replan. A name there is a claim that somebody is in the room, and every
mechanism downstream keys on the roster: a stale one is not a cosmetic error
but an empty chair the record cannot see, occupied by a person the director
keeps describing. `NOT_PEOPLE` -- the words a `with` may hold that are not a
person -- is defined here and imported by `ledger.py`, so the gate that
keeps a stranger out and the audit that reports one read the same list.
Log `[schedule]`, `[wake]`. `/schedule [regen]`, `/replan`. history: archive §5.1, §5.15.

### 8.2 `director.py` `Director`: the scene

Every `director.tick_minutes` while awake (`needs.red_tick_minutes` when a
need is red), one scene from the `director` role: location, activity, who
is with her, `phone_access`, a sensory line, events,
`share_worthy`, `ate`, `spent`, a `schedule_change`. **It writes nothing of
what is on her mind and nothing of what she would say**: both fields were read
back to her, and one of them she typed. `share_worthy` stays as a pull, and
the scene's `share_hint` key is still set by what her sight puts in front of
her (a note she has just opened, the week's shelf, the account) rather than by
a paraphrase of her. The night is ONE
scene (`sleep_scene`, role `sleep`, written when she goes under;
`sleeping()` is rebuilt from the scenes table on boot, not a flag in the
dict). The night's message carries the date and `THE TIME OF YEAR` from
the clock (`WorldClock.time_of_year`, in her instruction language) and the
prompt names no season of its own: what the room is like -- what is
running, what comes in the window, how early it gets light -- is asked for
from the date it is given. The prompt carries her body now (situation, health, hunger, money),
the family line (`_family_txt` never lets the tick down), the friends'
line, what Japan is on about, the open threads, the spiral's line, what
just happened (`extra_events`: discharges, cast beats, hazards, journeys).
`due(schedule)`, `phone_access(schedule)`, `asleep_block`. Table `scenes`
(ts, date, hm, scene, raw); kv `director_last_tick_ts`,
`director_next_tick_minutes`, `open_threads`, `sleep_scene_ts`. `/scene`.
Invariant: the director is TOLD where she is on the way (situation) and
may not put her at school before she has arrived. For a character with
`household.enabled` (`sim/household.py`) the director is also shown her
household -- her things with a state and the moves allowed -- and returns
`household_changes`, checked by code against the seed and the day's budget
and written as events; her own director prompt then carries no voice fields. history: archive §5.2, §5.15.

**An event that differs from the last one only in its figures is not written**
(`_same_but_the_figures`, kv `last_life_event`). A tick is asked for a scene
whether or not anything has happened, and a machine he has walked away from
produces the same true sentence every time: "He's been away from the machine
for 116 / 177 / 237 / 371 / 485 minutes, nothing touched since 04:19" was 32 of
the 35 events written about him in one day. Nothing downstream can tell those
from 32 things happening, so her day so far, her diary and the compile all read
them as a day of events, and she reported one observation to him in four
messages across 25 hours. Digits, clock times and the words that only ever
carry a figure are stripped from both sentences and what is left is compared;
only the immediately previous event is compared, because a thing that genuinely
happens twice with a gap between is two events. The line is `[director] event
dropped, the last one said this with different numbers`. The household's moves
are not compared: those are states of things in her flat and two of them are
never the same sentence with a number changed.


**The hole and the catch-up.** kv `director_last_model_ts` is the last
scene the model actually wrote; a tick whose answer did not parse writes a
placeholder cut from the schedule block and leaves that key alone. When
the two drift apart by more than 2.5 ticks, or `App.catch_up` has set
`director.catch_up`, the next prompt carries `THE RECORD HAS A HOLE: from
HH:MM to HH:MM nobody wrote her` with the schedule blocks that passed, and
asks for the whole stretch as one scene, events in order, ending where
she is now -- the night scene's idea applied to an outage. The trigger:
`LLM.call` writes every call that no provider answered to kv
`missed_calls` (`/missed`); once a provider is back (`llm.last_ok_ts`) the
loop runs `App.catch_up` before the tick: `director.catch_up` set, the
next phone look forced (`phone.force_next`, so his telemetry for the
stretch is digested and the X action queue runs), the rows moved to
`missed_calls_done`. `/catchup` does the same by hand and forces the tick.
The state model then reads the catch-up scene's events as it reads any
scene's, so what she went through in the hole moves her.
### 8.3 `situation.py` `Situation`: a situated body, no LLM

**The replay.** The one-scene catch-up writes hours as a scene stamped
now, and every reader then runs at now with its own clock (the state read
three hours as one quiet tick; the anticipation dreaded "tomorrow's"
ceremony at 11:44). `python tomoe\run.py --replay "<from>" "<to>"
[--speed N]` (her program's entry point, or `resident\run.py` for the
second character; machine-local times, the bot stopped) re-lives the
stretch instead: the
save is copied to `data/retired/<ts>_replay/`, what the bot wrote inside
the window is retired (`Store.retire_window`: scenes, events but the
world's kinds, state_log, self_memories), the gauges go back to the
snapshot at FROM (`Store.gauges_at`), the director is pointed at FROM,
today's anticipation keys are dropped and the missed rows marked
`replayed`; then the loop runs the window on a sim clock at `--speed`
with the delivery withholding every bubble (`Delivery.withhold`), the
reply, the impulse, phone looks, X actions, hazards and sensors off, and
stops at TO (`_replay_finish`, kv `replays`) without compiling. Every
scene, event, gauge move and memory lands at its real time from the
mechanism that owns it. Nothing reaches him from inside the hole: a line
written at 09:30 cannot be sent at 11:50 as if it were 09:30, so what is
unread waits for the live loop with the gap honest in the thread. A
window holding a message of hers is refused. The replay is only as good
as the schedule: a calendar event the planner folded into "classes" does
not happen in a replay either (the planner rule in `prompts/schedule.txt`).
**The estimate comes first** (his rule): before anything is touched the
command prints the window's ticks (`director.tick_minutes`), ~3 model
calls a tick, the cost at `replay.usd_per_tick` and the wall minutes at
`replay.speed`; past `replay.cost_warn_usd` it refuses without `--yes`.
**The temporal gap** is the honest alternative: `--replay FROM TO --gap`,
or `/gap` from ops for the hole the record knows (the last model scene to
now, widened by the missed calls), writes one event of kind `gap` at the
hole's end -- `[08:40-11:59] the record has nothing for this stretch:
nobody wrote her; she lived it unrecorded` -- points
`director_last_model_ts` past it so `_hole` never asks for it, marks the
missed rows `skipped`, and keeps kv `gaps`. The compile and the coherence
read see a blank, never a stretch invented at the wrong hour. The span
carries its date at each end when the two ends fall on different days of
hers, and its length in the unit that fits it -- minutes, hours or days --
so a stop of three days does not read as one evening. A caller may pass a
second sentence naming the cause, which goes into the event after the
first.

**Coming back from a deliberate stop** (`sim/downtime.py`, config
`downtime`). A stop is `Stop-Process -Force`, so the process being stopped
writes nothing on its way out and the next one would otherwise see an
empty stretch as work outstanding. The stop tool writes kv `stopped` on
each character's save once her process is confirmed down -- when, why, and
whether it was a deliberate stop or the account running out of money --
and `downtime.on_boot` is the read at the other end, one of the `[boot]`
lines and never in a replay: it clears the marker, works out the stretch
from the marker to now, closes the open row in kv `stops` (the last 50,
with how long she was away and whether it was written as a gap), and past
`downtime.gap_after_minutes` calls `App.temporal_gap` with the reason as
the event's second sentence. Under that many minutes she simply comes
back, and the log says so. No marker is the ordinary case -- a crash, a
kill by hand, a machine that lost power -- and says nothing. A marker
stamped in the future or before anything in the save is clamped, and the
boot line says it was not trusted.

**The account running out of money** is the same record reached from the
provider. `downtime.no_credit` is called from both out-of-balance branches
of the client: a status code of 402, or one of a short list of phrases
that say in words that money is what is missing (a bare `402` in the text
is not enough -- it turns up in a token count). It writes this character's
own marker at once, then launches `downtime.shutdown_command` detached to
stop the whole machine, so every other character's save gets the same
reason by the ordinary route. Once per process. It refuses unless
`downtime.enabled` and `downtime.shutdown_on_no_credit` are on, the clock
is live and the machine is Windows, and it refuses outright with
`SCAIL_NO_SHUTDOWN` in the environment: a sim, a replay, a dry run and
smoke can never stop his machine. The client's own log line and its
`return None` are unchanged; the stop happens as well, never instead.

No LLM. A place graph (`data/places.json`; every node carries a `kind` for
the scenery picker, and the three girls have their own homes on her line --
`aya_home` Sakuradai, `rena_home` Ekoda, `hinako_home` Shiinamachi -- which
were right in `cast.json` and absent here, so "at Aya's" resolved to nothing
and left her body where it was), journeys that run on the
clock from where she actually is (the train feed on a train leg, the
weather on a walk leg, the rush, what she wears and carries, running when
late), one seeded roll per leg for the things that happen on the way, and
a `fatigue` gauge that accumulates by what she is doing and recovers only
at rest. Readers: her read delay and composing, the impulse, the shape,
the register ("wiped is wiped"), the director (TOLD where she is; it may
not put her at school before she arrives), her situation block -- which
also carries the FACTS about getting anywhere, so a vehicle is never
invented: `travel_line` (the modes the map actually has for her, and that
there is no bus in it) and `trip_lines` (the real legs, lines and minutes
to a place her promises or her plan name, clause by clause so a
three-promise line does not resolve to the wrong one;
`situation_block.trip_lines`, `trip_min_minutes`). Pickups
through `Family.can_pickup`. kv `situation`, `journeys`. `/where`. **spec:
`docs/situation.md`.** history: archive §5.84.

`minutes_to(node)` is what the journey honestly costs from where she is --
the figure `Commitments.running_late` needs to know whether she will make a
promise (§9.7); what she BELIEVES about it is that module's business.

### 8.4 `body.py` `Body` and `health.py` `Health`: the body

`Body`: the setting of a scene (indoor / outdoor, room feels-like with
the AC once it is hot enough, `environment.ac_from_feels`,
`heat_from_feels`), exposure hours outdoors in heat or rain per date
(`note_exposure`, `note_wet` with `health.wet_exposure_factor` for
soaked), meals (`meal_kind` from the director's `ate` or the words of the
block; `note_meal` moves hunger at once; kv `last_meal_ts`), `red(gauges)`
(hungry / exhausted), the needs line for the director.

`Health`: per-day draws (`health_days`: a cold from yesterday's exposure,
the cycle, a bad night; `health.seed`), the sleep model (`_sleep`: score
from bedtime, wake, hours against need, factors; the energy target),

**What keeps her up is the chat, not the phone** (`_chat_alive`). Her own rule,
in her own words: 「みんな起きてるのに私だけ寝るなんて無理!」 -- she is not held by a
screen in the abstract, she is held by the group still being ALIVE, because
being the one who drops out first is unthinkable. Other people's group turns
between `chat_alive_after_hm` and `chat_alive_until_min` feed `delay`; her own
are excluded, because what holds her is that THEY are still talking. One term
buys both behaviours, since the early-bed block derives `resist` from `delay`:
a live chat pushes her bedtime later AND makes her refuse to turn in early for
a morning she promised, which is exactly the trade the source describes. An
exchange keeps the date it STARTED on, so one opening at 23:20 and running to
00:40 carries its later turns under yesterday -- both sides of midnight count,
and an exchange dated today at 23:30 belongs to the NEXT night and does not.
What the planner puts in that stretch is §9.1.

`effects()` -> the per-hour targets the world terms pull toward (composes
two conditions on one gauge by taking the worse), `tags()` for her mood
tags, `schedule_note` for the 05:00 plan (a sick day changes it). Owner
of `unwell`; never touches mood. `/health`. history: archive §5.18, §5.19, §5.89.

### 8.5-8.7 `family.py`, `money.py`, `events.py`: the household facts her day is planned against

Three constraints the schedule, the director and the cast prompts all read:
who is in the house, what she can afford, what she has already agreed to.

**8.5 `family.py` `Family`: where her parents are, and the car.**

Drawn from `characters/tomoe/household.json` with seeded per-day variation, no LLM:
dad's commute and overtime, the Wednesday no-overtime day, the Friday
nomikai, the Saturday golf day, the Hakata trip; mom's Life shifts and
the Sunday call to Kashii; the car in the monthly lot. `where(who, ts)`,
`car_at_home`, `can_pickup(ts, from_node)` (the honest answer: no car,
nobody home, dad drunk, past his cut-off, a coin he can lose), `trip(date)`
(a family day out about one Sunday in five), `brief(date)` for the
schedule writer, the beat writer and the director. The house as an economy
and the one thing she has not been told are prompt text the PROGRAM writes
(`tomoe/briefs.py`: `household_brief`, `household_secret`, and
`geography_brief` for the real addresses and her line's stops); the
director asks its program for them by name (`Director._brief`), so a
character with no world is handed nothing rather than somebody else's
household. Both are world-facing only: the persona may not tell her. kv
`family_days`. `/family`. history: archive §5.72, §5.85.

**Whoever this household has, and no member written into the code.** The
module asked the file for `dad` and `mom` by those keys and printed a label to
match; the brief looked up `dad`, `mom` and one brother by name. So a girl
whose file names her mother, her brother, her sister, her grandmother and the
ABSENCE of a father was handed `dad: ,  --` as the first line of her
household, no brother and no sister, in every call that builds her world.
`household_brief` walks whatever members the file has, in the file's order,
labelled by the relation each member states (`relation`), takes the work
block, the grandmother block or the plain note as the member's shape has it,
and prints a member with no name as the file's own words about the absence.
`Family.has(who)` is a member with a name, and a drawn day is fingerprinted
with what the module read out of the household, so a day drawn under a
different household is re-drawn: the draw is seeded by the date, so an
unchanged household hands back exactly the same day, and a save copied from
another character no longer carries her family into a day. Without that, the
promoted character's planner was told "dad is home all day (his day off)" and
"the car is at home in the monthly lot" out of a cached row, hours after her
own household file was written.

**And the day's spine names her places, not the first character's**
(`tomoe/schedule.py:skeleton`, `_day_words`). The walk to the station, the
after-school block, the Saturday and who is at breakfast and at dinner were
string literals, so every embodied character in this program walked to Nerima
station on the Seibu Ikebukuro line and ate with mom and Kaito. They are a
`day_words` block in her own map file now, with a default that names nobody's
station and nobody's family, so a character with no map gets a day with the
right shape and no places in it. The map's own `areas` list says which parts
of the city it prints and what to call each of them; two ward names used to be
in the reader.

**8.6 `money.py` `Money`: her allowance.**

Balance, the allowance day (`ensure_allowance` hands it over on the day or
the first day she is around after), the director's `spent` clamped to
the balance, reservations for commitments (`reserve` / `release`), a
money log (`money.log_keep`). "Just bought a cola" that the log never saw
is an embellishment: `spent_today` is the record the cast prompts get.

**One purchase, once.** The director runs every `tick_minutes` and is not
shown what the last scene bought, so it re-narrates it, and the same
purchase goes into the log twice in twenty minutes with her balance paying
twice. An identical `on` and `yen` inside
`money.duplicate_minutes` (45) is refused, and `Money.line` now tells the
director what she has already bought today -- which also makes the third
grape ice of the week visible as the tic it is. kv `money`. `/money`.
history: archive §5.22.

**8.7 `events.py` `Events`: what she has said yes to.**

Before the schedule is built, one call (`events` role) decides her stance
on the upcoming calendar events (going / dragged / skipping), kept in kv
`event_stances`; the schedule must honour a yes, the director may deviate
the way she would; the stress load reads what she is committed to. A stance
that is really one of her own promises takes its day from the promise and
not from the sentence (`_when_from_the_promise`, matched against the open
commitments): the model reads the prose, and prose that says "tomorrow"
still says it tomorrow.
`/events`. history: archive §5.69, §5.70.

### 8.8 `records.py` `Records`: threads, cast sheets, places, arcs

Threads (table `threads`): the director's open / resolved lists reconciled
by head (`_head`, `_sim`; the tail is rewritten every tick), deduped,
dormant after `threads.dormant_after_days`; `pressing_thread` is the
thing she has been not-saying to him once it has sat long enough.
`cast_sheet` renders a person for a prompt (with `influence`, the clear
pressure they put on her). Places (kv `places`, `places.in_prompt`) and
arcs (kv `arcs`, `showrunner.max_arcs`). The household, the map and the
geography left here for the program's own brief module (§8.5). `/threads`,
`/places`, `/arcs`. history: archive §5.10, §5.39, §5.55.

### 8.9 `rhythm.py` `Rhythm`: when he is around, learned and told

From the record alone: `profile()` per hour of his day (how much of him is
in it, his median latency, faded by age), `learned_now(ts)`; from what he
has said (`hear`, role `said_when`, kv `rhythm_said`): `expectation(ts)`
-1..+1, faded. `usual_now` combines them. `presence()` (is he at the
phone right now, from his last latency and freshness) replaces the old
`tempo`; `in_exchange()` with hysteresis (kv `in_exchange`);
`noticing_seconds(access)`, `reply_seconds()`, `delay_cap()` (being tense
does not slow her when he is right there); `silence_factor(ts)` (an hour
of silence at 03:00 his time is not an hour of being left; read by
`State.felt_hours` and the loneliness climb); `notices()` for her prompt.
`/rhythm`. history: archive §5.63.

### 8.10 `impulse.py`, `intent.py`, `shape.py`: does she text, what
kind, what shape

`Impulse.score(state, scene, silent_hours)` is a pure function of her
gauges, the scene, the silence, his tension, the unanswered streak
(counted in messages, not bubbles), the spiral bonus, the sentiment bonus
and **his own hours** (`Rhythm.learned_now`, learned from the record: 0.29
at 06:00, 1.00 at 10:00, 0.01 at 04:30). `impulse.presence_floor` is the
hour he is simply never there and she does not text into it;
`presence_weight` makes a quiet hour a weaker pull than a busy one rather
than the same one. `check` gates it (`impulse.*`: caps, `burst_gap_minutes`, the phone
must be free); `App.maybe_impulse(scene, digest, force_hint, media)`
runs it (a discharge or a photo forces it with the hint as the whole
reason). kv `impulse_last_ts`.

`initiative.py` `Initiative` is the gate BEFORE the score: whether she may
reach out first at all, which is a different question from whether she wants
to. `Impulse.check` asks it, and so does the afterthought, so there is one
owner and no guard per caller. Three rules. **His coming back** is a reason
she might write and never a certainty: the program that can see whether he is
at his machine calls `observe_away(seconds, state)` every pass
(`resident/app.py`), and the transition from away to here rolls once --
`return_p_base` + `return_p_per_hour` per hour gone (to `return_p_hours_cap`)
+ `return_p_unsaid` x how far `unsaid` is over its rest, capped
`return_p_max`. Taken, she writes somewhere in `return_delay_minutes`; not
taken, nothing self-started for `return_hold_minutes`. Both are logged with
the odds (`[impulse] his return: p=0.54 (gone 6h, unsaid 58) -> in 13 min`).
A character nothing tells has no return rule at all. **Being ignored** raises
the bar with each unanswered message: `backoff_minutes` by streak, x
`backoff_read_factor` when he has OPENED it and said nothing and x
`backoff_unseen_factor` when he has not (`Receipts`, through
`Impulse.read_state`), with `max_unanswered_per_day` under it as a backstop.
**His small hours** (`quiet_start_his`-`quiet_end_his`, in his clock) are
quiet. Through it anyway: a gauge at its end, and the two stances that enter
without waiting (`sim/stances.py` `URGENT`), both logged as
`[impulse] override: ...` with what the gate had been holding her for.
Everything is in the save (`initiative_away_since`, `initiative_return`,
`initiative_hold_until`, `initiative_unanswered_counts`); the backoff itself
is read off the record of what she actually sent. `/impulse` prints the gate
under the score; `tools/initiative_test.py` proves it on a copy.

`Intent.decide(scene, silent_hours, share_hint)` (role `intent`) names
the kind of opener -- share / check-in / confront / make_up / question
(`wonder`) / the X account's own doing (`_account_line`) -- with the
feeling that is deciding it (`_carrying`) and per-kind daily caps (kv
`intent_counts`). `Intent.last_question` carries an asked question to the
send. **It returns the SUBJECT of the urge in two to five words, never a
sentence and never anything she could send**, and `reason_line` renders it to
her as a subject: it is a judge, and after its sheet was taken away it was
still writing finished first-person messages that reached his chat.

**The role is told what part of the day it is on each clock and whether he is
at his machine this minute.** `WorldClock.both_daypart()` puts the words on
both readings and names the gap between them, and `Intent._his_machine_line`
asks the phone for the monitor's own reading (`Phone.his_side_now`: at it and
how long in the window, away and how long since, or nothing when no monitor is
running). The receipt above it answers a different question -- has he opened
what she sent -- and `unseen` is true both of a man asleep and of a man three
feet from his keyboard, so with two bare clock readings and nothing else the
role wrote her "are you still awake?" to send at his Saturday mid-morning.
`prompts/intent.txt` names the two lines and rules the question out; a
`check_on` is asking after him, not asking whether he is up.

`Shape.draw(unread, intent_kind, scene)` draws the message shape (bubble
count, length, a question or not, `shape.kinds`) from her state, the
situation's `shape_bias` and the register, before the persona writes; the
persona fills it, and the drawn line is the LAST instruction in her prompt
so the draft is the right size in one pass (no redraft, no post-hoc trim).

**`shape.tell_length` false and she is told none of it** -- no length, no
bubbles, and the reason clause on the feelings rule ("what you feel shows in
how short you are... what you ask") drops with them, because it is a length
instruction wearing a style rule's clothes. The classes and the weights were
measured on the first character's English, and on the second, who they were
never fitted to, "curt" and "short" both saying ONE line came to four messages
in ten: 39 of 39 a single bubble, median 28 characters, 36% ending on a
question back at him. Off for her, on for the first character, and what she
writes is what goes.

It still says **what his message obliges her to take up first**
(`shape.engage_line`, read from his own words because it is a "when"). Three
cases, in the order they beat each other: he has told her what she is ("why do
you sound like a slave to them lmao?") and she does not take that lying down or
agree with it to be nice; he asked something, and her FIRST bubble answers the
question he actually asked; he put an opinion about the world in front of her
and left it there, and she takes THAT up rather than her own day. The first
beats the partial licence outright, the other two ride with it. It exists
because she once answered his remark that a Pixar exhibit sounded interesting
with three clauses about her own standing, none of them touching what he
raised. history: archive §5.4, §5.32, §5.74.

### 8.10a `pick.py` `PhonePick`: what she does with the phone, decided by her

The impulse above can only answer one question -- does she write to him now --
so a moment that is wrong for him is a moment where nothing happens, and a
promise to somebody who is not him has no term in it at all. This asks the
other question at every moment code can offer her one, and **what comes back
is what happens**. The impulse function, the reply delay and the group-chat
roll still run, as the backup for a moment she was not asked at or did not
answer. The replay that earned it is `docs/tool-calling.md` §14 (forty-six
real moments, $0.041: defensible at the phone, a like-everything machine after
a scroll, so the scroll pick is still not wired), §15 is the shadow run in
between, and the live wiring is **§17**. `pick.shadow` true is that shadow
mode, unchanged and still available.

**When.** Four moments, `pick.moments`: the start of a stretch her plan gives
her a free phone (`block`), a change of what she is doing inside one (`scene`),
something landing from her own people (`beat`), and him writing (`inbound`).
The first two are asked from `App.maybe_impulse` right after `Impulse.check`
and its log line -- after, because the impulse's answer is part of what the
pick is recorded against and `check` rolls a die; `beat` from the program's
`loop_pass` after the beats are delivered; `inbound` from `App.maybe_reply`
before the delay plan is made. A discharge reaches none of them.

**A character who reads a world she does not keep is offered only her own circle** by name in the `message_friend` argument, with one line saying the rest of them are talked to in the group chat: she picked one of the owner's people and was refused by the partition rule, which is a fact about the file layout and not about the girl, and a chooser offered a thing it is never allowed to do learns nothing. **What she has already been to each of them with today** rides in the same block, and so does the sentence naming anybody off the list because she went to her and had nothing to say (`sim/said_today.py`, §9.8c).

**The gates are code's and are all in `PhonePick.due`**: `pick.enabled`, a live
run (never a sim, never a replay), `App.phone_access() == "free"` so there is
no call at all when the phone is not in her hand, the day's cap (kv
`pick_counts`, `pick.max_per_day`), no two looks inside `pick.min_gap_minutes`
(kv `pick_last_ts`, and the figure is on every row), and one look per block and
per scene (kv `pick_block`, kv `pick_scene`) so a restart does not ask the same
moment twice.

**What she is offered follows from what kind of thing she is**
(`PhonePick.offered`), not from a second switch: `nothing(until)` for
everybody, `text_him(intent)` with a chat with him, `message_friend(name,
intent)` in a world, `open_group_chat` in a world she OWNS (the group room
belongs to whoever keeps the world), `look_at_his_machine` unless her sheet
says `sees_him: none`, `open_feed` with an account; and on his message the
tools are `reply_now`, `reply_later(when)` and `leave_it` instead, because the
question is a different one. Six and three for the first character, three and
three for each resident, two and none for the reader of the shared world. Every
description says what the tool COSTS her, and `nothing` is never first and
moves position once a day rather than once a call, which is the cached prefix.
The sections of the moment go with the tools. The descriptions are addressed to
her and are behind the language switch (`sim/lang.py`); the two that name how
she comes to know what he does are `pick_look_tool` and `pick_look_cost` in
each program's words table.

**The prompt is her own daily half plus the tools.** The system message is
`persona.system_for("him")` byte for byte, built under `_peek` so nothing is
drawn, which puts the pick behind the prefix the provider has already cached
for her reply. The moment is everything that moves: what kind of moment it is,
both clocks, where she is and with whom, her gauge line, his side off the
record, the last six turns between them, what is unanswered in her rooms, and
`persona.carried_for()` -- the same `<carrying>` block both her rooms place
after the thread, so what she holds while deciding is what she holds while
speaking. The `pick` entry under `models` is flash at the persona role's
thinking and effort for EVERY character, including the two on a voice model,
because this call decides something and writes none of her words;
`"prompt": ""` says it has no file of its own by design. `Config.ROLE_STANCE`
has it as `voice`.

**The seams.** The runtime carries out what is the mind's and the
relationship's -- `App.write_him_first` (the path the impulse's yes runs down,
with her `intent` as the hint), `App.look_at_phone`, `App._plan_from_pick`
(the reply plan the delivery path already runs on) -- and hands the rest to the
program's `pick_act` hook, which is `Exchange.self_open(chosen=True)`,
`Exchange.open_with` and `Social.start_look` for the character with a world and
an account, and does not exist for a resident. Every hard gate on those stays:
the exchange's own reasons a room cannot open, the account's hours and caps,
the cost cap on a look. What is skipped is code's guess at whether she WANTS
it -- the group chat's score and roll, and the boredom probability behind a
scroll. **A choice her world cannot honour is recorded with the reason and is
never rewritten into a different action.**

**The wire.** Native tool calling where the host takes tools, and the same
question as JSON in her text where it does not -- decided from the receipt of
the last pick (kv `pick_host`, `api.hosts_without_tools`), never from a guess
about the pin. The text path goes through `LLM.call_json`, so a malformed
answer is asked again `api.json_retries` times and is never stored raw.

**The record.** One row in kv `picks` (last 200) written the moment the answer
exists -- the character, both clocks, the trigger, phone access, where she was,
the moment verbatim, every call with its validated arguments, the impulse's
answer with its score, the mode, the transport, the gap in force, the cost, the
tokens, the model and the host. `acted`, `acted_why`, `fallback` and
`fallback_why` are filled in AFTER the seam has run, so nothing claims a
message, a room or a look before the thing itself. The block marker and the
day's count are written before the call goes out, because a stop is a kill.
`PhonePick.validate` is the whitelist: a tool nobody offered, arguments that
did not parse and a missing required argument are recorded as invalid with the
reason, are never a pick, and leave the backup to decide; an argument the
schema has not got is dropped. **An answer with no usable choice in it is asked once more** -- the same messages and one line saying to answer with one tool call and nothing else -- and both calls are counted in the moment's spend; if the second is not a pick either, the backup decides as before. **Her reasoning arriving beside the pick is kept**, as kv `pick_aside` (`{ts, text}`, one row, overwritten), and read by the NEXT moment inside three hours of her clock as one line of what she was thinking when she was last asked. Nothing else reads it: it is what she was thinking and not something she said, so it goes nowhere near the diary or the private-thought role. It used to be logged as dropped and dropped, and in one nine-hour window five of twenty-two moments came back that way, one of them better interior writing than several roles that cost more. Nothing enters her thread. `PhonePick.holds` is the one
place the backup is refused: while the only reason she has not been asked again
is that this is the same moment or too soon after the last one, her own answer
stands. `/pick [date]` prints a day -- moments by kind, what she picked, how
many were acted on, where the backup ran, how often she and the impulse differ
about writing to him, and the spend; the ops payload carries the same counts;
every boot logs live or shadow with the moments, the caps and the tools. About
$0.0015 a pick for the first character and $0.0002 for the reader, four cents
a day at the cap. Proved by `tools/pick_live_test.py`, in smoke. **All four
characters run it live** (`pick.enabled`), with the same caps: the two
residents were on the impulse function alone, which for the third character
answered no permanently -- her tension sits above `impulse.withdraw_silent_from`
and that gate is shut and stays shut.

### 8.11 `diet.py` `MediaDiet`: what she is into

0-3 one-liners a day from the compile (`things_recent`), the accounts her
taste keeps liking (`liked_accounts`, from kv `x_taste`), a brief for her
system prompt and one line for the director. kv `media_diet`. history: archive §5.21.

### 8.12 `world/shared.py` `SharedWorld`: the world as a file two processes read

Everything a character knows about the world around her is in her own save, so
a second process running one of the people beside her as a character of her own
would plan a day the first process never had. The world therefore gets a file
of its own: one sqlite file per world under
`<world.shared_dir>/<world_shared.id>/world.db`, with **one writer** -- the
character whose config says `world_shared.owner` -- and any number of readers,
who open it through a `mode=ro` URI and never take a copy.

Eight tables, each row stamped in machine local time and carrying the writing
character's id: who the people are and what they are called (`roster`, never a
sheet), where each of them is between two times and how reachable
(`whereabouts`), what the day fixed (`settled`), every turn of the group chat
and of every two-person exchange (`rooms`), what each of them privately holds
about another (`graph`), the people around the people (`orbit`), what is going
round (`gossip`) and what the record says happened (`events`).

**One writer for everything the owner owns, and a partition for everybody
else** (docs/shared-world.md §2). A character who only lives in the
world writes the rows that are about HERSELF -- the windows her own day planner
puts her in (`CastEngine.own_day_to_world`, as her day is settled and again
when it changes), the membership row that says she is in a room, and the lines
her own plan settled -- each under her own id and a source naming her own
planner, and nothing else: a row about another person or in any of the owner's
six tables is refused with the fault logged (`_may_write`). Conflicts are
impossible by key, because the person and the source are already in the natural
key. She does not stamp who keeps the world; she records herself under `meta`'s
`writers`. And the owner's planner PREFERS a person's own rows for the windows
they cover -- where everybody is today, how reachable somebody's phone is, who
is free after school, and the absences in the day's one truth -- with its own
draw of her week as the fallback for a window she wrote nothing for
(`_prefer_own`, `CastEngine.their_own_where`). `world_shared.reader_writes_own_rows`
switches her writes off; the reading side has no switch.

It is a copy and not the truth: every fact still has one owner in the owner's
own save, nothing in the owner's process reads the file to decide anything, and
each write sits beside the write that already records the thing -- the plan
(`CastEngine.day_to_world`), the day's one truth as it accepts a line
(`Ledger._settled_to_world`), the exchange inside the stamping of a turn
(`Exchange._turn_to_world`) and the compile (`compile_to_world()`). Every write
is one row the moment the thing exists and is guarded inside the store, so a
world write can never take a tick down. Each table has a natural key, so a
re-planned day or a settled line read on every prompt build leaves one row.

`world_shared` is `in_world` in `Config.REQUIRES` and `world.shared_dir` is
`in_world` in `Config.WORLD_KEYS`, so a character with no world has no path to
anybody else's world rather than merely never being shown it. The store is a
declared wire, built by the program. `python world/shared.py --id <world id>`
prints the counts and the last row of each table; `tools/world_test.py` drives
a plan, a settled line and a turn through the live paths on a copy of the save
and reads them back from a second `Config`, then drives the partition: a
character who does not keep the world writes her own day, is refused a row
about anybody else and a row in any other table, and the owner's read prefers
hers for a window -- with the owner's own rows proved unchanged against a copy
of the live world file. What a promoted cast member still needs from the world
is §7 of `docs/shared-world.md`.

**A character who is in a world she does not own reads it and runs none of the
machinery that writes it** (`docs/shared-world.md` §8, from the third
character's first forty-five minutes, which built a second world on the same
roster inside her own save). `Config.REQUIRES` carries a fifth property,
`world_owner`, and the eight sections that write the world -- the people's own
weeks and the pressures behind them, the pool of what is going round, the
day's record of what happened, the people around the people, the strangers,
measuring herself against the room, and who privately holds what about whom --
are assigned to it, so they are off for a reader and, as before, for a
character with no world at all. Three more
are gated in the program because their sections stay on for her: the cast
planner's day, a beat of that plan coming due (`CastEngine.due`, the other end
of the same rule -- a plan already in the save keeps arriving on her clock),
and the exchange's own starting of rooms. And one is gated the other way
round: what her ward has announced is the world's rather than anybody's
judgement of it, so the ward events fetch has one writer and a reader reads
the file the owner wrote, while the national news feed is per character because
its whole selection is hers. What stays on reads
the world file: the settled lines and the absences in the day's one truth,
everybody's whereabouts and reachability behind the cast engine, and the pool
and the orbit in the half of her prompt that moves during a day. The social
graph is the one of the eight whose object is still built for a reader,
because every reader of the edges takes them through it: it reads the file's
rows rather than her save, seeds nothing and runs no update, and it is keyed
on what the record calls the running character (`sim/roster.handle`, resolved
from the cast row that carries her hub id) rather than on a name written into
the module.
`world_shared.read_rows` bounds what a reader puts in front of a model.
A save written before the rule went on is emptied of its second world once, at
the reader's next boot: eight keys and the record rows of the day's beats moved
verbatim to `data/retired/<stamp>_second_world/<save>.json` and deleted, kv
`second_world_retired` marking it done (`tomoe/app.py
retire_second_world_once`, `tools/second_world_retire.py` for a stopped save).
`tools/world_reader_test.py` is in smoke; `tools/existence_matrix.py` builds
the two world kinds as separate rows.

---

## 9. The people around her (the first character's own: `tomoe/`, cast, exchanges, the graph; the roster, the promises and the voice check are shared)

The friends are the canon three -- Rena-chan (香芝玲奈 Kashiba Rena, the
center), Hinako (米山日南子 Yoneyama Hinako, glasses and a braid, the one
who notices), Aya (前田亜矢 Maeda Aya, short black hair, the quiet one) --
and the family (mom Yumi, dad Kenji, Kaito, 11). Sheets, kanji, readings,
`aliases`, a `week` for every one of them (the parents' shifts and hours
included, so the plans layer can place them) and what each calls the others
live in `data/cast.json`; a rename
touches that file too, or `merge_sheets` re-seeds the old name as a fresh
sheet. Avatars in the app are files in `data/talkapp/avatars/`, named by roster
handle (`Rena-chan.jpg`, `Yumi.jpg`); the hub resolves whatever name the record
asks with through the roster (`GET /avatar/香芝玲奈` serves `Rena-chan.jpg`), so
the Japanese record names get their pictures and a file dropped in under a
Japanese name works too. **古賀健二 has no file** and draws the letter circle.

**Three names each, and they are not interchangeable** (`sim/roster.py`): the
**roster key** (`Rena-chan`, `mom`) that the sheets and prompt files are named
after, the **role_id** (`ringleader`, `mother`) that the machinery thinks in
and the only one that survives a recast, and the **record name** (香芝玲奈) that
the stored record uses, because the record is Japanese and a romaji speaker
label is the same English leak the glosses were. `role_of` / `key_of` /
`record_name` / `same` / `is_self` resolve any form -- key, role_id, Japanese
name, reading, a nickname harvested from everyone's `calls`, an explicit
`aliases` entry -- by **exact match against a built table, never a substring**;
re-read when the file changes, through `atomic.read_json`, which tries a
failed read twice more before it falls back to the table it already has: the
file is replaced by a rename and the window a read can fail in is over in
microseconds. A file that stays unreadable is said ONCE and then once a
minute with the count, and the recovery line names how long it lasted. A
patch script rewriting the roster in place once produced 233 identical parse
failures on one character and 131 on another in 31 seconds. Before it, six modules matched names by
lowercasing and testing `in`, so `Rena` and `Rena-chan` were two girls in one
conversation and every rule keyed to a label skipped the other one. Each
role_id resolves to itself, so a store keyed by roster name and one keyed by
role read the same. The stored speech record was relabelled once to match,
by a migration tool since retired.

**Whether a person is family is a fact on the row** (`roster.is_family`, and
`is_own` beside it for whose). Two questions read it -- who is in the group
chat (`sim/rooms.py:members_for`) and who could have been in the room where
something was said (`roster.witnessed`) -- and both used a global set of five
role ids. Two households in one world cannot both be `mother` and `sibling`,
so a reader's own mother sits under a role id of her own and that set said she
was not family. A row may carry `family: true|false`; without it the five ids
are the answer, so the character who keeps her world is unchanged.

**Who may hold a relationship meter is also the roster's answer**
(`roster.meter_rows`, read by `sim/state.py:_seed_people` and by the repair in
`tools/promoted_save_retire.py`, so a save seeded today and a save repaired
today hold the same rows). It was the cast file's `people` dict, read raw and
taken whole, which for a character promoted out of somebody else's cast meant
a meter on herself at closeness 45, meters on the world owner's mother, father
and brother, none on her own mother and brother -- they are in a second file --
and none at all on the girl whose world she reads, who is that file's keeper
rather than one of its people. A person the roster has and the cast files give
no numbers for is seeded from her own sheet's opening values
(`people.<key>.opens_at`), and seeded flat with a line in the log when the
sheet has none: choosing a closeness for somebody is authoring, not seeding.

### 9.1 `cast.py` `CastEngine`: the people as sources

Per date: seeded draws (mood, attention, friction), plans from each
sheet's week with a twist, the day's beats from one `cast_day` call (a
LINE, a group burst with nicknames in the words -- and sometimes a short
speaker prefix, which `cast.is_japanese` tolerates -- a
sticker, a call, something said in person, being left on read), their
lives written at the compile (`cast_life`). `due()` -> `deliver()` makes
beats events the director must reflect. `merge_sheets` carries
`data/cast.json` into `relationships`.

**Each of them gets a handful of concrete things for the day about to start**
(kv `cast_pockets`, `sim/pocket.py`, `cast.pocket_items`), written by the same
compile call that writes their day, from one extra key on an answer it already
makes plus what the stores already hold: their own day just gone, one thing
going round they have actually heard, a piece of the week assigned to them, the
beat of their own storyline, the fixture their week has them at. Each is put in
front of one call and then spent, and `/lives` names one nobody ever brought
up. Its absence is most of why a group chat told it is mostly made of concrete
things settled the plan again instead. **And the carry has to move**: after
`carry_about_her_max_streak` days of one person's carried thought being about
her, the prompt says today's is about their own life and one that is still
about her is dropped rather than rewritten -- all six of them were about her in
the record that prompted this and four were the identical sentence three days
running. **spec:
`docs/room-quality.md`.**

**Which room a person reaches her in is `rhythm.channel`, and it is prose.**
No room table, no per-person flag, no tie strength: each person's channel
line goes to the planner beside her share of the beats and the planner picks
every beat's `kind`, so a one-to-one with somebody exists on the days it
writes them a `line` beat. The confidante's line says LINE and she has one
most days; the rival's says group chat mostly and she can go a week without
one, in the group and the corridor instead. That is the sheet working. **But
`rhythm` is seeded once and never refreshed** -- `merge_sheets` keeps
`role_id` / `influence` / `ja` / `reading` / `calls` / `week` / `aliases`
current and copies the rest only when the key is missing -- so changing a
channel on a live character means the file and the `relationships` row
together.

**The chat's own silence is a number now, and one thing acts on it.**
The beats are placed once, when the plan is written, and an exchange
continues on a flat per-round probability, so a room dead for five hours was
in the same state as one that spoke a minute ago; the only thing pushing
against a silence was a sentence in the planner's prompt asking for none, and
the record's longest daytime gaps ran past five hours against a median of
three minutes. `group_silent_minutes()` is how long the group has held
nothing, read off the record and the live exchange. `_quiet_pull`, at the top
of `due()`, moves the earliest undelivered group beat of the day forward to
now once that passes `cast.quiet_after_minutes`, at most
`quiet_pull_max_per_day` times, never over a live conversation and never into
the dead part of the night -- the same argument `_fill_late` moves a beat on:
the intent is real and only the timing is impossible. kv `cast_quiet_pulls`.

**The late stretch is drawn, asked for, and repaired.** `_late_window` draws
tonight's last light per night (seeded, off the hour and the half hour, 21:20
to 02:20) and the planner is told it. A draw before `late_from_hm` is a night
the chat simply dies early and **nothing late is required** -- a mandatory late
block every night is as artificial as the 21:00 ceiling it replaced -- but
never before `night_floor_hm` (22:20). A negative draw says "no late stretch";
it does not say the group is over at half nine, which is what a -100 draw
plus tomorrow's pull comes to without the floor. And it is not a blind
draw: `_group_morning` reads the earliest thing anybody in the
group has to be at tomorrow (their `week` fixtures for that weekday, the school
start on a school day, her own promises) and pulls the end in by
`late_morning_pull` of every minute earlier than `late_morning_ref_hm`, so they
turn in together before a school day and let it run before a Sunday. The week
is read from `cast.json` and not from `relationships`, which never carries it; `_fill_late` inserts low-salience
`group` beats if the plan came back without them, and tops up the share of the
day that is about NOTHING (`idle_share`; beats carry `"idle": true`) if it came
back short. Both repairs log loudly, because if they fire every day the planner
is what needs fixing rather than the repair. This exists because the sleep model
reads that stretch (§8.4) and had nothing to read: every group turn in the
record sat at 12:00, 20:00 or 21:00, nothing after 21:37 in eight days, and
every beat was a time, a place or an obligation. Her schedule was never the
constraint -- she has `phone=free` to 01:30 -- the planner simply never used the
window. A prompt asking a model for purposeless messages loses to an input full
of plans, so code decides WHEN one is needed and the person still writes her own
words from it.

**Her promises are facts the plan carries, and the plan gives a promise
its hour.** The planner is handed what she has promised BY ID with the date
written out (`Commitments.planner_lines`: the day being planned and the day
after, `time not fixed` when none was said); a beat about one keeps its
date and time, a promise the day cannot keep becomes a beat about it
falling through and is never moved, and a promise with no time takes one
from the plan -- the beat names `promise` and `at`, and
`Commitments.pin_time` makes that the promise's hour for the schedule, the
director, every speaker and the settle. **Every relative day is dated**
(`_absolute_days`): `tomorrow (<date>)`, `明日の夜(<date>)` in
`settled` and in `about`, because those lines are read again when the next
day is planned and the bare word then means a different day; the planner
and each beat's writer are told which day they are writing and what 明日
means inside it. **What yesterday settled is carried "unless a beat today
changes it", so the planner is also given what has stopped being owed**
(`Commitments.closed_brief`, §9.7): nothing else could ever tell it a
promise was finished, so a line saying one was still due outlived the
promise itself and every friend's turn was written against a debt that no
longer existed. **A plan to go to something public names the calendar entry
it means** (`dates_ahead`, `event_of`, `_settled_from`; docs/cast-exchange.md):
the planner is shown what is on with the day or the span of each, every beat
and settled line about a public event carries the entry's date and title in
an `event` field, and code refuses the beat or the line when the calendar has
nothing of that name on that date. What is kept rides in the line as
`[calendar: <date> <title>]`, so the next day's planner, both sides of every
exchange and the ledger all see the same binding, and the carry expires on
the entry's day. It is the entry and not the word "festival" that decides,
because a festival she had already been to came back six days running and the
last time it came back with the word taken out, as "meet dad at the station
tomorrow". kv `cast_days`, `cast_plans`,
`cast_beats`, `cast_life`. `/cast`, `/beats`, `/lives`. **A picture between friends is its description and nothing else** (his call):
the bracket is the whole of it, no file is attached and none is needed, and the
pool of real photographs is kept for what she sends HIM, which he opens.
**The group carries on without her** whenever her turn
comes due and she is not in it -- her phone away counts, not only her
declining -- and a beat of another kind waits rather than ending a live
group chat. **What today has already been over** (`Exchange.covered_today`)
reaches every friend's turn and the beat writer. **spec:
`docs/cast-exchange.md` §2-3.** history: archive §5.16, §5.86; §9.1.

### 9.2 `exchange.py` `Exchange`: her side of her social life

**Each of them is an agent with a sheet of their own.**
`prompts/cast/<key>.md` is that person's document, written the way her bible is
and IN JAPANESE because everything they say is: who they are, what they want,
what they do not know, and 話し方 -- how they sound, naming the forms and the
first person. It is the system prompt for their call (`cast.person_sheet`, read
fresh; an honorific comes off the key rather than costing somebody their sheet
in silence), and the role prompt under it is only the contract. One role prompt
with a `role` field pasted in had given six people one voice.

**Under the sheet, a set of mechanisms** (`tomoe/cast_mechanisms.py`,
`data/cast_mechanisms/<key>.json`): per person, what makes them do a thing,
what stops them, what doing it gets them, in the same shape the extracted
character uses and marked `authored` so it can never be quoted as a
measurement. A sheet gives a model an adjective to perform; a mechanism gives
it something to run, and a suppressor in front of the person is a real answer
too. The sheet stays the system prompt and the block goes in the user message
of the three calls where somebody speaks or is planned for -- their own turn,
their own beat, and the day plan, which gets everybody's mechanisms and
nobody's secrets, because one call writing for six people holding a secret is
six people holding it. Each mechanism names the roles that may see it, a
mechanism no call renders is DEAD the way a gauge nothing acts on is
(`tools/cast_mechanisms_test.py`, in smoke), and over
`cast.mechanisms_max_chars` the rarest is dropped first. The personality type
each person was written FROM is in a file of his (`cast.types_file`) that
nothing assembling a call may open; `tools/cast_type_test.py` counts its
markers in the record and is the only reader. **spec:
`docs/cast-mechanisms.md`.**

A beat that wants an answer becomes a paced exchange: the opener verbatim
from the planner, one side's turns per loop pass on the clock, his
message pushing her turn back. Her turns (`cast_reply`) carry her state
with `directed_line(who)` -- never his register -- her meters with them,
her record of the day (events, what she said to people today, money),
what she owes them, the nicknames, and `prompts/style_ja.md`, which is the
other half of her voice (`style.md` is how she writes to HIM and has no
business in a call to Aya); their turns (`cast_turn`) one call per speaker
with their own sheet, day, life and graph edges, nothing of her interior; a
group is multi-agent.

A turn is `{who, ja, hm}`: `ja` is what was said, there is no English gloss
any more, and a turn without Japanese is dropped (`cast.is_japanese`, which
ignores the Latin speaker prefix a group burst carries by design). An exchange's
`gist` is Japanese, written by the model as part of the same answer; a beat
saved unanswered keeps the planner's English line as its gist instead, which
is what `search_rows` gives recall to match his English cue words against. Two
consecutive turns saying the same thing with the words moved are collapsed
to the first (`sim/textutil.drop_repeats`, the same test the bubbles get): a
person repeats herself, she does not paraphrase herself.

**The summary is written only from turns that survived the filter.** `gist` and `about_him` are assigned after the check that a bubble came back, not before it, on both sides of the room; when nothing survived, the record keeps the summary it already had and that round is counted as a round that added nothing before the room closes. Written the other way round, two rooms in one evening stored a sentence saying what she said in them -- one of them a promise to her brother she never made -- and the round that produced literally nothing was the one round never counted as having produced nothing.

**A room that loops is caught four ways, and none of them rewrites a line.**
The whole-message test above compares one speaker with herself, and neither
loop in the record is that shape, so: a sentence-level filter over the room's
last `repeat_window_turns` turns from anybody drops a bubble more than half of
whose long sentences have already been said (`sim/textutil.echoed_by`, used by
the owner's cleaner and by a participant's writer, which had nothing); a moves
ledger keeps the one-line summary every writing call already returns, renders
it to both writers and carries it on the ask to a member who writes her own
turns (`sim/rooms.moves_block`); a round in which a bubble was dropped or a
move was played twice is stale, and each stale round multiplies
`group_continue_p` by `stale_drag` while two in a row end the room; and the
pace reads the reachability of everybody who just spoke and of whoever speaks
next, hers off the scene's phone access, rather than the opener alone.
**A stamp is outside all of it** (`is_stamp`): a bubble that is only 「[スタンプ: …]」 is never compared with anything and never counts as a dropped bubble, because two girls sending うん as a stamp twice in an evening is agreement rather than a loop -- all three deletions on one character that day were the same stamp, and one of them cost the room a round. A run of the identical bubble inside one answer is still collapsed. `group_bubble_chars` counts a bubble too long for the medium in the record and
in the log and cuts nothing. **spec: `docs/room-quality.md`**, and
`tools/room_quality.py` measures a room off any save.

**The dialect is flagged, never redrafted.** `_slip_ok` says why a Hakata slip
is the TRUE reading now -- alone with the confidante (`slip_with_roles`, by role
so it survives a recast, and never in a group, because the point of a mask is
the audience), real anger, genuinely short of sleep, or cornered by that person
-- and that, with the family case, reaches `voicecheck` as `context`, where a
rule's `skip_when` turns it off. A second mechanism here used to hold its own
copy of the patterns and spend a call rewriting a slip; it is gone (§9.10).

**A group chat is a venue, not an errand.** The one-to-one numbers are the
originals; the group has its own. `group_continue_p` (0.87) and
`group_max_rounds` (12) set the length -- E[rounds] = (1-p^R)/(1-p), so 2.18
became 6.25 -- `group_max_live_minutes` (180) lets one run for an evening,
`group_jump_in_p` (0.7) puts more than one other voice in a round, and
`max_per_day` covers every kind of exchange EXCEPT in-person, so the group
used to compete with LINE and the kitchen for the same slots -- and an
evening of five library exchanges with the confidante spent the day by
16:31 and left her mother in the kitchen as a one-line stub. The budget is
the phone's, not the room's: `wants` lets an `in_person` beat through
whatever the count says, and neither increment charges it. The cheapest lever was the prompt:
turns per call had NO code bound, so "one or two turns" was the whole of it,
and `cast_turn` / `cast_reply` now ask for one to four and say what a turn is
-- one MESSAGE, not one thought. A day went from about 48 group messages to
**134 at five group exchanges, 158 at six, 183 at seven, 204 at eight**, at
0.43 calls a message. (An earlier analytic model said 231; it did not know
about absences, and `tools/chat_project.py` drives the real code now.)

**She is not the chat** (`exchange.group_without_her`, 3). Her silence used
to close a group: `_her_turns` came back empty and the exchange finished, so
three girls stopped talking to each other the moment she did not answer. Most of a
day's group conversations came out **one message long** for that reason, and
each of those stubs also charged her `reply_miss_standing`. Now they carry on without her for up
to three passes and she can walk back into what they said; only then does it
end, as "she never came back to it". The idle beats (`idle_share`, the ones
about nothing) are what this rescues: they were the stubs.

**And the room does not need her to have been in it at all**
(`Exchange.alone_beat`, `exchange.alone_beats_per_day`). The passes above
only ever ran inside a conversation she had stepped out of, so a group beat
the day's phone budget or the late reserve refused her never reached them: it
was filed as one unanswered line by `CastEngine.save_beat` and that was the
end of the room, with the other two girls in the chat the whole time. **17 of
the 47 group conversations in a week were exactly that row.** Such a beat now
opens a conversation with her out of it from the first turn -- the side starts
as theirs, `skipped` starts at one, and the same `group_without_her` passes
bound it, with a `group_continue_p` roll in the hand-off so it thins out
instead of running its six. Her phone budget is not charged, because the
budget is what she can ANSWER; nor is her standing, because a room she was
never offered is the machine's cap and not her silence. She reads it in the
thread when her phone comes back. kv `exchange_alone_counts`.

**She can start one** (`Exchange.self_open`, `exchange.self_open_per_day` 1).
Every beat is somebody reaching HER -- the planner is refused any beat
written as her, and that rule stays -- so she opened **none** of the 47 group
conversations in a week and three girls opened all of them. This is the other
door, and it is shaped like her urge to text him (`sim/impulse.py`): flat
refusals first, each sayable in the log (a live conversation, no phone, the
day's cap, fewer than `group_without_her_min` friends awake, past the night's
last light, the room quiet for less than `self_open_quiet_minutes`, a
friend's own beat due inside `self_open_clear_minutes`), then a score on her
own gauges (`self_open_weights`: loneliness, boredom, craving, and belonging
by how far UNDER par it is) against `self_open_threshold`, then the impulse's
own soft edge. Her words come from `_her_turns` with an empty turns list and
one extra line in the ask saying the room is empty and she is picking it up
-- the same assembly, `persona.system_for("friend")` and the one thread and
the carried block after it, because a second assembly is how her friend turns
went eleven days without her interior. kv `exchange_self_open_counts`.

**One name per person, and every person is told their own first person.**
`voice_line` renders `cast.json`'s `voice`, and no sheet's `voice` named a
first person -- the 一人称 lived only in `prompts/cast/<key>.md`, twenty-five
lines into Japanese prose in the system prompt, while the line next to the
transcript said how she sounds and left the pronoun out. `first_person` is a
field on each person now and it goes in first. The other half was the name:
the OPENER of an exchange reaches `_one_speaker` as the record name and a
jumper-in used to reach it as the roster handle, so Aya's own prompt said
`SPEAKER: Aya` and `what Aya holds about Rena-chan` above a sheet saying
前田亜矢 and a transcript in which every line is 前田亜矢. The pool resolves,
the SPEAKER line resolves at the point of use, `SocialGraph.brief_for` renders
both ends of an edge through the roster, and `roster.one_name` replaces every
capitalised handle in the assembled prompt -- `mom`, `dad` and `him` are
English words before they are keys.

**Nobody repeats their own message** (`no_repeat_own_turns`, 6), and
neither does she -- by contract first (`cast_reply.txt`: her own earlier
messages are said; a standing point is advanced, answered or dropped; an
answered worry gets a reaction to the answer, and a dodge uses something
new), with the near-duplicate refusal on her own lines as the guard. The
guard exists because a guard can only catch the verbatim copy; the
reworded restatement is the prompt's to prevent. A speaker is
shown their own last turns in this conversation and told that a point still
standing is dropped, sharpened or replaced -- never restated -- and a turn
that comes back a near-duplicate of one of them is dropped in code
(`near_duplicate` against that speaker's own lines, where `drop_repeats` sees
only a consecutive run).

**A group chat is mostly not arrangements.** The same fifty-one messages were
100% logistics -- 明日 21, 10時 16, 日曜 11, フリマ 9, 手帳 8, and not one joke,
photo, complaint about the heat or piece of gossip. The group prompt now says
what a group chat is made of and that a settled plan is not settled again.
The negotiation underneath it was sound: Hinako pushed, Rena deflected for
her, Aya bridged, and 「流れたら、もう誘わないから」 got a commitment out of her.
The bones were right and the texture was not.

**Nobody is chained to the phone** (`_gap` / `_away`). Every gap used to be
`prev_len/6 + U(20,150) + n/3`, bounded about 29-198 seconds by construction,
so a three-hour chat was a two-minute metronome: mean 1.9 min, median 1.9, max
3.2 over thousands of samples. `away_p` of the time a gap is an absence
instead, and the absence has a REASON that carries its own length (`AWAY`: the
loo, a video then another one, dinner, the bath, homework, somebody in the
room, went outside, fell asleep with it on their chest), weighted so the
late-night ones are the sleepy kind. Median stays 2.2 min -- most answers are
still quick -- and p90 goes to 20-27 with a tail to about 70.

An absence is not free, and one of them ends a night rather than pausing it.
Every absence multiplies the chance the conversation keeps going by
`away_drag`, so a chat that has already stopped for somebody's dinner and
somebody's bath thins out instead of running its twelve rounds regardless (34
messages a late night -> 26, 127 minutes -> 99). And **falling asleep means
sleep**: the person is written to kv `cast_asleep` until `sleep_wake_hm` the
next morning, out of the speaker pool (`_awake_friends`), unable to open a beat
(`wants`), and when everybody who was in it has gone the exchange ends with
"they had all gone to sleep". Nobody's tiredness is modelled -- this is drawn,
not simulated, and it is the one way a person's night ends.

**A beat nobody answered is still something that was said**
(`CastEngine.save_beat`). A beat is a model call in that person's own voice and
its words lived in kv `cast_beats` -- overwritten by the next day's plan, one
day of grace in `cast_beats_prev` -- while the only durable trace was the
planner's ENGLISH line in `events`. Everything that reads her social life reads
`cast_chat`, where a beat appeared only if it happened to become an exchange.
One that `wants()` refuses (the budget spent, the group chat already running,
the sender asleep) is now written there as a one-turn row marked `unanswered`
-- unless it is a low-salience idle beat and the coin lands (`exchange.stub_stamp_p`):
then she stamps back from her own set, code only, never with the phone away,
and the row carries her half-attention instead of a one-voice stub.

**Somebody she is sitting WITH says something** (`CastEngine.presence_beat`,
called every pass from the loop). The planner writes a day in advance and
cannot know she would still be at that table two hours later: she can sit
across from Aya all morning while the day holds one four-minute conversation
with her and a LINE exchange with somebody else runs at the same table. The scene knows who she is with (`with_who`) and the cast layer
never read it. Code decides when -- somebody in the room has not spoken to her
for `cast.presence_gap_minutes` (25), under `presence_max_per_day` (5) -- and
that person writes her own words through the ordinary beat path. Never for
him, never for a name the roster does not own, never for somebody dormant.

**A table is not one person.** This read `with_who` as a single name and
returned nothing the moment it held a comma, so the only scenes that could
ever produce a presence beat were the ones where she was alone with somebody
-- which at school is never, because she is at lunch with the group. Her
whole first school day of term passed with friends named in the block and not
one word between them, and every non-family in-person conversation on record
came from a break day where the plan happened to seat her with exactly one
person. Now everybody in the room is a candidate: the one she is already in a
live exchange with is dropped (a presence beat never opens a second
conversation on top of the first), anyone inside the gap is dropped, and code
picks the most overdue, so the quiet one at the table gets her turn before
the girl she has been talking to all lunch.

**One girl, one name, in every seat.** Read from Rena's chair
(`tools/context_audit.py`) the prompt called her four things at once: 古賀朋絵 in
the transcript, とも on the sheet, `Tomoe` in the stored stance lines and the
promise list, and `Rena-chan` in the roster of who else is reading -- which also
listed Rena herself, because the exclusion compared a roster handle with a
Japanese record name. The friends' user block is normalised at render, the
group roster uses record names and excludes the speaker through the roster, the
sheet header and the promise brief use her record name, and the beat prompt is
normalised the same way.

**Her friends see her by the name the record uses.** The labels around a
speaker's call said "Tomoe" while the transcript said 古賀朋絵 and the sheet said
they call her とも: three names for one girl, in the prompt, which is the fault
the roster exists to stop. `EARLIER EXCHANGES WITH 古賀朋絵`, `attention for
古賀朋絵`, `WHAT 古賀朋絵 HAS PROMISED THIS SPEAKER`, and `calls_line` resolves the
`calls` map's roster keys to record names (`calls 古賀朋絵 とも, 米山日南子 ひな`).
`tomoe/prompts/cast_turn.txt` and `cast_day.txt` name her the same way.

**A beat that lands while the group chat is running joins it** (`absorb`).
A group beat used to go through `start`, which ends whatever she is in -- so
Rena dropping a photo into the chat at 23:50 was the thing that killed the
chat it was meant to be part of. It is appended as her turn instead, the side
flips back to Tomoe, and the conversation gets a round and one absence back,
because somebody new arriving is exactly what keeps a chat alive.
A one-to-one beat from the very person she is talking to, on the same
channel, joins the live exchange the same way -- their next line in this
conversation, never a second one -- and `presence_beat` does not fire for
the person she is with in a live exchange (two in-person exchanges with
Aya at 09:37 came from that).

**Beats landing together wait their turn** (`hold_back`, `cast.hold`). The
loop takes due beats one at a time; a beat that lands while an exchange is
live and she has not yet had her turn in it (side hers, no rounds) is put
back undelivered and comes whole on a later pass, up to
`exchange.hold_minutes` past its own time. Two events due in one pass used
to open and drop each other within the second, and the dropped one cost
her standing for a message she was never given a turn to answer; an
exchange closed before her turn was due is never charged (`_finish`).

**A chat that is past the night's last light is over** (`_past_last_light`).
`_late_window` draws when the group turns in and `_group_morning` pulls it in
by what everybody has on tomorrow, but nothing enforced it once a conversation
had STARTED: a beat at 23:50 on a night meant to end at 00:07 ran to 02:38 on
the three-hour live cap, which undid the whole point of them turning in
together before a school morning. The check reads the small hours as belonging
to the evening they came out of and runs from the last light **until the group
wakes** (`CastEngine._after_last_light`, the one owner of the rule, asked by the
planner and by delivery alike): a fixed six hours reached 08:13 after a 02:13
night and refused a 07:30 morning chat, which is nobody's overrun. Nights now
run about half an hour past their own end -- people finish the thread, they do
not stop dead on a clock -- against two hours before.

**And the plan does not schedule into it.** A beat placed past
tonight's end would open and shut in the same tick and cost her standing for
a message nothing would have let her answer, so `_fill_late`
moves such a beat back into the evening -- the intent is real, somebody wanted
to reach her tonight -- and a close that was nobody's choice (the curfew, the
others asleep, the opener dropping it before her first turn) is not charged to
her at all.

**Her prompt does not carry every line of it, and it is the thread that
cuts it.** At a couple of hundred group messages a day, two days of
exchanges whole is ~23k characters, and most of it is about nothing by
design. The exchange had a section of its own in her system prompt that
kept the newest group conversations verbatim and rendered the older ones
as the gist they already carry; that section and the function behind it
are gone, because her friends' talk reaches her through the thread
(`sim/thread.py`) and the thread applies the same cut on its own curve --
verbatim inside the verbatim span, then the conversation's card, or one
line at its own time saying how many messages, until when and what it came
to where no card covers it. A cast member's own thread carries no cards at
all: a card is written per conversation across every room, her chat with
him among them, so their past conversations reach them as those lines.

**She is not always available, and owing him an answer is not the same as
being with him.** `_busy_with_him` was true from the moment his message landed
until she replied, so a message that arrived while she was ASLEEP froze every
exchange: 456 minutes, Kaito's beat dying in her doorway and Aya's dying while
she sat across a library table from her. It now means she is actually sending,
or his message is newer than `busy_window_minutes`; deferrals are capped at
`busy_max_pushbacks`; and an `in_person` exchange is never deferred at all,
because a phone does not stop you talking to the person in the room.

**What she carries from the other room** (`tomoe/carried.py`). Her chat with him
and her chat with her friends are two rooms, and each was represented in the
other by a keyhole of raw messages: the cast calls got `recent_messages(4)` cut
to 80 characters, laid out exactly like the conversation she was actually in.
Wrong twice -- too little, and the wrong KIND of thing, because a transcript in
a prompt reads as a conversation to answer and the one thing she must never be
confused about is which conversation she is in.

`Carried.him(cue)` gives a cast call a corpus instead: where it stands with him
(who wrote last, how long ago, whether she owes him an answer), what she knows
about him with the fade already applied (`Memory.facts_for_prompt`, cued by
what is being said around her), what is still open between them, whether
something is unsaid, and only then the last `him_messages_shown` (10) messages
at `him_message_chars` (160) -- labelled a record and not a conversation
waiting on her. `Carried.circle()` was the mirror in her own prompt while she
talks to him: whether the group chat is live right now and who is waiting on
whom, what it has been about (gists), where she stands with each of them and
how many conversations she has been out of, and who is asleep on the chat. No
model call: all of it is assembled from what the record already holds. Nothing
calls it now: the system-prompt section it fed was built and blanked on every
call while the thread is on, and was deleted; putting the circle back into her
prompt through the attention gate is a prompt addition and his call.

THEIR side still sees none of his chat: a friend's turn has that person's
sheet, their day and edges, the chat as it stands and their earlier exchanges
with Tomoe, and nothing of her private mind or her DMs.

**A slow answer costs her, and missing the chat compounds** (`_reply_cost`, at
`_finish`). Past `reply_slow_minutes` a group or LINE exchange takes `standing`
off whoever opened it; never answering costs more. kv `behind` rises on a group
conversation she stayed out of, falls when she took part, caps, and **scales the
cost of the next one** -- the compounding, and why she over-attends. Read back
in her own turn prompt (`_behind_line`), so it is not a number nothing acts on.
Both are her own rules from the bible and neither had a mechanism: she could
ignore the group for a week at no cost.

The
record (kv `cast_chat`) reaches her state like his message does, the compile,
recall, the app. `/chat`. **spec: `docs/cast-exchange.md` §4.** history: archive §5.29, §5.73; Part C 2026-08-27.

### 9.10 `voicecheck.py`: is this line in the voice it should be in

`characters/tomoe/voice_rules.json`, keyed by speaker (`Tomoe`, `Kenji`), by role
(`role:diary`) or `_all`; a rule is `find` / `why` / an optional `unless` that
makes it fine (a quotation, an honorific), and a role set may `inherit` a
speaker's rules rather than restate them. `voicecheck.note` runs on every turn,
every beat, and -- through `LLM.call`, the one place every role's output passes
-- every role, including ones that do not exist yet. It writes `[voice]` to the
log and a row to kv `voice_flags`, and **changes nothing**: a line in the wrong
voice is a signal about the prompt, and correcting it quietly hides the signal
(the first Chinese-character blocklist would have mangled 写真 nine times).
Adding a person or a role is an entry in the json and no code.

A rule may also declare **`skip_when`**, naming what the caller knows that a
regex cannot see -- `family` for the kitchen, `slip` when her state says the
mask is legitimately down -- and the caller passes `context` (§9.2). That is how
a conditional rule (her Hakata is hers at home and a slip in front of Rena)
lives in the rule file instead of a second copy of the patterns. A rule SET may
in turn declare a **`context`** that is always true of it: the twelve role sets
that are her private mind (anticipation, reflect, spiral, diary, wonder and the
rest) declare `inner`, and the dialect rule skips it, because a mask is for
other people and there is nobody in her own head. The caller could not say so --
`LLM.call` has a role name and knows nothing about her. The speaker is
resolved through the roster before the rule sets are chosen, or a whole person's
rules silently never run: relabelling the record in Japanese took every flag to
zero until that was added.

An answer that had to parse as JSON reaches the check as **`machinery`**, passed
by `LLM.call_json` through `LLM.call`. Its keys and the fields the code reads
back are English by construction, so a rule about how a person writes cannot say
anything about it -- while a rule that is true of any answer at all, Hangul or a
simplified Chinese character, still runs. The three roles that answer in prose
and are still the machine talking (the app's account of him, a note of his
summarised, the week written into the record) say the same of themselves with a
`context` in the rule file. Before this the second character's "she writes
Japanese only" rule fired on all 33 calls of a morning -- every scene the
director wrote, every state delta -- and buried the one real flag, which was her
own reply.

`tools/voicelint.py` runs the real checker over the real record, read-only, so a
regex is measured before it is trusted -- it caught `たい` flagging 「聞きたい」 and a
bare `ばい` that would have eaten 「やばい」. `/voicecheck` is the report (it
was a second `/voice` branch that the voice queue's own answer had always
reached first, so it never once ran).
history: Part C 2026-08-27.

### 9.2b `npc.py` `People`: everybody who is not the cast

The cast is seven people with sheets, a graph and a place in her prompts.
Everybody else in Tokyo did not exist: she rode a packed train with
`with: "strangers"` in the schedule and nobody on it, stood in a konbini with
nobody behind the till, and spent a school day in a building holding one class
of girls none of whom were ever in the room.

**Who is plausibly there comes from the place.** `data/places.json` already
gives every node a `kind` -- konbini, station, school, library, park, shrine,
museum, shotengai, city -- and `_WHO_IS_THERE` maps each kind to the roles that
populate it, weighted: a konbini is mostly the person on the till, a platform
has a school kid from another school and somebody standing too close, a shrine
has an old woman. `home` is empty because her family IS the cast; a friend's
flat is `kind: home` and is not her home, so it gets their mother.

**Three things a person can be**, which is how it works in life: a face she
will never see again; a face she knows by sight and has no name for -- code
reuses a face already seen AT THAT PLACE with `known_face_p`, weighted by how
often she has met them, which is what gives the konbini a regular clerk instead
of a new stranger every visit; and a face with a name, only where you would
learn one (school, or `name_after` meetings). A new draw that comes back as
somebody already on the record IS that person: one row per face, matched on
either name form, or the same clerk accumulates a row a night.

**Most of them are simply there.** An encounter is rare and that is right;
what was wrong is that between encounters nobody existed. `around(scene)`
is the ambient population of wherever she is -- one or two roles from the
place's table, the face she has seen most there first -- computed in code,
deterministic within the hour, never a model call and never an event. The
director is told (`PEOPLE SIMPLY THERE`), the scene carries it (`around`)
and her own prompt reads it as background ("people about, nobody in
particular"). You do not remember the person on the till, and a stranger
who keeps turning up does not change her life: `promote_after` is 0 (never)
and `/npc` names no candidates. The value of the other people is that they
are there, not that they matter.

**Code decides when and who, the model decides what.** The gate is the place's
own `place_p`, an alone multiplier (three girls together are a wall), a gap, a
daily cap and a roll on a cadence rather than on every pass of the loop. The
slot -- known face or new, and which role -- is picked in code and handed over.
Most encounters have no words in them at all, which the prompt says plainly,
and money is not the encounter's to spend: her purse is a record kept elsewhere.

**They stay out of the cast machinery.** An NPC never enters `relationships`,
`sentiments`, the graph, `cast_chat` or the group -- no standing, no closeness,
no beat -- because the empty-person fault was a name reaching a lookup with
no row for it. One door out: an `events` row, which is what
everything else in her day comes through. The director reads the day's events,
so the scene answers a stranger; the diary reads them all; her own voice to him
reads only `salience >= 2`, so the person on the till never reaches her chat
with him and something that stayed with her does. A face she keeps meeting is a
cast candidate named by `/npc`, and nothing here writes `data/cast.json`:
promotion is his. kv `npcs`, `npc_moments`, `npc_counts`. `/npc`.

**One person in every room.** `_her_turns` builds its system prompt from
`persona.system_for("friend")` -- the same assembly as her replies to him,
byte for byte, without `style.md` -- FIRST (so the cache prefix is shared),
then its own tail: `cast_reply.txt`, `style_ja.md`, her stickers. From
08-19 to 08-30 it built from the bible alone, and half of everything she
said in a day carried none of what she had decided about herself,
remembered, wrote last night or was into; `tools/smoke.py` now fails if
the two assemblies diverge by more than `style.md`. With the nudge on
(`nudge.friends`; it is off) it fires on her turn at the `unsaid` threshold
with the bond line as the gate's pick.
**Her friend turn sits on the same thread**: the
messages are the persona core, then `thread.build(live_turns=...)` --
both rooms, one clock, the exchange in flight as its tail -- then the
call's own block, which says which room she is writing in NOW and that
the other rooms are answered there. `THE CHAT SO FAR`, `EARLIER
EXCHANGES` and the carried him-block are what the thread replaced: there
is no flag any more, and the presence of the thread object is what
decides, so those blocks are only what a call built without one falls
back to. **Her turn goes through the gate.** The block she reads with her own
people is built the way `persona._situation` is: a fixed header (time,
where, how she is, who and her meters), then tagged lines through
`attention.admit` -- `them` (bond, behind, known, thought, a promise on
the record, anything she has promised to SEND them and can put in this
message as 「[写真: …]」, each rumour an action candidate), `day` (yesterday, today,
what she said today, money, threads, the settled ledger), and `him` as
facts only (`_him_lines`: his last message and when, the gap, how he
sounded, expectations, the digest -- never her private questions about him
or the thing she is not-saying to him; those ride only in his room) so he
can come up in her rooms
-- one action stated in the slot, last before the ask; a rumour held there
is charged a showing (`Gossip.charge_shown`, `gossip.shows_max`) and steps
aside for the day when unsaid; him is the `himf` section (3 lines); the nag / show-him / share never
candidates there. `[attention] (who) ...`, kv `attention_last_friend`.
**And every other mouth.** A cast member's turn (`_one_speaker`) sits on
their own thread -- `thread.build(for_who=...)`: only the rooms that
person witnessed (the group for a friend; their own LINE, calls and
kitchen; never her chat with him), with THEM as the Assistant role and her
and everyone else as the world speaking to them, the same curve applied,
the exchange in flight as its tail, and the call's block saying which room
they are writing in NOW. In the fallback block form, `THE CHAT SO FAR`
carries each turn's own stamp and a `[N minutes with nothing said]`
marker at `exchange.chat_gap_marker_minutes`. The latest compiled day is
labelled by its age, not always "yesterday".

### 9.2c-9.2e `gossip.py`, `stickers.py`, `orbit.py`: the fixed sets around the cast channel

Three owned sets the exchange reads, and none of them is the cast: what is
going round, which stamps a person has, whose little sister that is.

**9.2c `gossip.py` `Gossip`: something to talk about that is not the four of them.**

Measured over 175 group turns, 77% carried a time, a plan or an obligation
and 13% carried anything else -- the chat was a committee because the
committee's business was the only thing in the world. `cast_arcs`,
`cast_life` and `social_graph` are all about the group or about her; this
is the rest of it. Every `gossip.every_hours` the `gossip` role writes up
to `new_per_run` things going round -- a teacher, a second-year, a shop
closing, a video -- from the faces she has actually met (`tomoe/npc.py`),
`tomoe/world/zeitgeist.py`, the calendar and what she noticed about Japan on her
own timeline (kv `x_japan`, `_timeline_seen`). Each carries a `heat` that falls
`cool_per_day` and rises `warm_on_use`, a `knows` list so a person who has
not heard a thing cannot repeat it, and `kind` (person / school / couple /
shop / seen / nothing). **A rumour about anybody the roster owns is
refused**: that is the cast, and the cast has arcs. The planner sees the
warm ones (such a beat is `idle`), a speaker sees only what that speaker
knows, her own reply sees the warm ones. **`knows` is seeded when the item is
born and grows when it is said**: a school thing, a person or a couple is known
to everybody at that school on the roster, a shop or a place to whoever lives
or passes there per `cast_plans` in either language (falling back to the school
when no week names it), a thing everybody has seen to everybody; and anybody in
the room when it is stated has heard it from then on, read where a turn lands
rather than where one is cleaned, so a turn written by somebody's own process
counts too. Before that, six of twelve were known to one person and the
speaker filter hid them: one girl could bring up 6 of the 12 on file and now
brings up 11. `/gossip` names an item nobody has heard two days after it was
born. kv `gossip`.
history: §9.1.

**9.2d `stickers.py`: a fixed set of stamps.**

The record narrated stamps -- 「（悲しそうなキツネのスタンプ）」 -- and invented
each one fresh, so nobody's stamps were ever twice the same. There are no
images and none are wanted: a stamp read as text is what he sees. What was
missing is that it be the SAME stamp. `SETS` holds five, one per role
(overridable per person with `stamps` in `data/cast.json`); `line_for` puts
only that person's own on their prompt; a stamp is written
「[スタンプ: 名前]」, the same shape as the photo marker, so every reader
carries it; `snap()` pulls a name they do not own to the nearest one they
do, or drops it, logged. The app draws it as a stamp. history: §9.1.

**9.2e `orbit.py` `Orbit`: the people who belong to somebody in the cast.**

Rena's little sister was one sentence in `cast_facts` and a different
person every time she came up. One row per person outside the cast who
belongs to somebody in it: owner (a roster key), relation, a name only if
the record ever gave one, `ja`, the facts the record has put on them,
`status` (the fever) with its date, and two standings -- how Tomoe stands
with them and how the owner does, a sentence and a slow number each.
Written once a day at the compile by the `orbit` role from the day's
exchanges and `new_cast_facts`; code matches by owner+relation or by name,
drops a row that IS cast (a name the roster owns, or a self-owned family
relation -- her family is the cast), clamps nudges to +-2 and caps. Read
by the exchange (`line_for(who)`: a speaker knows the people in their own
life), the planner and her own prompt (`brief`), and the gossip pool
(`owns`: an orbit person is off limits like the cast). kv `orbit`;
`/orbit`. history: §9.2e.

### 9.3-9.4 `social_graph.py`, `cast_arcs.py`: the cast's own ground truth

What the people hold and where their own lives are going, both written away
from her.

**9.3 `social_graph.py` `SocialGraph`: what they actually think.**

Ground truth per holder (`view`, `regard`, `irritation`; friends to
Tomoe and to each other, family only to Tomoe), rewritten at the compile
from what each person witnessed; readers: each speaker's own edges, the
lines her guesses settle against, `witnessed_heat` (a stumble costs more
in front of an irritated group), the showrunner's drift, the app's
backstage. A view is the holder's own thought in Japanese; one that comes back in
English is flagged (`[graph] FLAG`) and kept. Known gap: friend-to-friend
edges have no writer. kv `social_graph`. `/graph`. **spec: `docs/cast-exchange.md` §5.** history: archive §5.76.

**9.4 `cast_arcs.py` `CastArcs` and `Showrunner`.**

Arcs: each person's own life by role, written weekly (`run`, role
`cast_arc`; `_focus` picks who carries one: attention x volatility +
tension) and evolved (`evolve`, role `cast_evolve`); `day_nudge` raises a
person's attention on a day their arc moves; `context_for_beats` for the
planner. kv `cast_arcs`. The showrunner (role `showrunner`, weekly) sets
her arcs from the calendar, the receipts, the cast and the graph's drift,
leaning toward her own people when the week was mostly him
(`cast.him_share_warn`); kv `arcs` via `records`. Both live in
`tomoe/cast_arcs.py` and share the one weekly gate (`weekly_due`: on the
section's weekday, once a day at most, not inside `min_days_between` of
the last run, and straight away when there is nothing yet). `/castarcs`,
`/arcs`.
history: archive §5.11, §5.35.

### 9.5 `reflect.py` `Reflection`: her private mind

A private thought, in a quiet moment, about him (`run`, role `reflect`:
from the digest, the app, his notes, the receipts) or about a person in
her own life (`run_cast`, role `reflect_cast`: from the exchange record
only; `cast_subject` picks by pressure, not rota). **`after_reading(scene,
why, record)` is the third way in**: something of his she has just read, with
the record handed to the call under a heading of its own, the day's cap and
the alone rule holding and the minimum gap not, because it is an event rather
than the standing pressure the gap spaces out. kv `reflections`
(`reflect.keep`), counts and gaps per kind. Readers: her system prompt
(`prompt_text`), the intent (`inner_hint`;
a thought about Rena is not what she carries toward him), the person's
own reply call (`about(who)`), the comparison's thought goes out through
this channel. `/reflect`. history: archive §5.27.

### 9.6 `compare.py` `Comparison`: measuring herself against them

Code decides when (a peer in the scene or just talked with; pressure
from craving, shame, anxiety above their rest and belonging below par;
`compare.max_per_day`, cooldown); one call (`compare` role) decides what
from the record only, and `fires: false` is the common answer. Upward:
`envy` toward that person, shame, craving, a little anxiety, a strain on
the self-belief it lands on (`ModelOfHer.strain`); downward: a little
pride; level: only the thought, through the reflections channel, never
said aloud. kv `comparisons`, `compare_counts`, `compare_last_ts`.
`/compare [now]`. history: archive §5.90.

**Nobody writes anybody else's words.** `plan_day` is two stages. The
`cast_day` role plans the SHAPE of the day and nothing else -- time, who,
channel, salience, and `about`, one plain English sentence saying what that
person is reaching her about. Then `_speak_beat` calls each of them
separately (`cast_beat`), with **her own sheet as the system prompt** and the
contract underneath it, exactly as `Exchange._one_speaker` already does for
her turns: her day's draw, where she is, what she privately holds, and what
has already been said. One writer ventriloquising six people had put 俺 in a
fifteen-year-old girl's mouth, and no rule downstream can put back a voice
that was never there. It also told the writer "Hakata-ben ONLY from Tomoe",
which is wrong for a family whose sheets all say 家では博多が出る. A `group`
beat is one person's opening; the others answer in their own calls.

**The day's budget is the cast's own reach.** `plan_day` took the MEAN of
their attention, so the whole social world got about eight moments a day
whoever was in it -- six people, the group chat, LINE and the kitchen
between them -- and every day in the record had a three-to-four hour silence
sitting inside her waking hours while a ringleader whose sheet says she pulls
the group around all day got two beats. It is the SUM now
(`beats_base + beats_per_attention * sum(attention)/100`, capped at
`beats_max`), and each person is handed her own share of the total with the
channel her sheet says she lives on, rather than the model dividing it by
taste. Measured on the same day: 7 beats -> 16, group chat 2 -> 6, the
longest waking silence 4h30 -> 2h13. A beat written as HER is dropped
(`_HERS`): a beat is somebody reaching her, and her own turns come from the
exchange.

### 9.7 `commitments.py` `Commitments`: a promise with something on it

After an exchange (`from_exchange`, role `commit`) or after she has said
something to him (`from_chat`, role `commit_him`): one call names what she
committed to; code decides whether it binds (a cast counterparty and a
real date; for him one of `HIM_KINDS` and a date; `_week_line` gives the
model the dates so 明日 resolves). **A time said later is the promise's time** (`amended` in the `commit`
answer: an hour or a date named by either side for an open promise, not
refused, updates it -- `[commit] amended with ...`), **the last word in an
exchange counts** on a cancel, and `_promises_kept` names an untimed promise
the plan has no block for as well as a timed one it does not cover. The lines
this writes into the event ledger name `character.name` ("… told him she
would", "… promised"): the module is shared, and six of those lines wrote
the FIRST character's given name into every character's ledger until
`tools/character_names.py` was taught to read f-strings again (the tokeniser
stopped handing them over as plain strings in 3.12, so the guard had been
reporting shared code as clean).
**The prose never keeps a relative day**:
`_drop_relative_day` takes today / tonight / tomorrow / 明日 / 今日 and the
rest out of `what`, because the `date` beside it is the record of the day
and a sentence that says "tomorrow" still says it tomorrow -- one promise
was dated the 28th and read by the events model as the 29th, so it sat on
two days and the day it was dated had no block for it. Money can be
reserved. **The verb decides which record settles it, and the four are
`attend` / `buy` / `bring` / `send`**: a promise to send a person in her
world something goes out through the chat itself, so `_check_send` looks
for a message of HERS carrying a picture or a video, in a room that person
was in (`roster.witnessed`, the one rule `sim/thread.py` also reads), any
day from the promise to the day it is due. Her saying she sent it does not
count. Only `attend` and `bring` need her standing there, so only those two
go moot when the other person could not come -- somebody shut in at home is
exactly who a picture gets sent to. `send` means one thing to him and
another to a friend, so the branch is on who it was made to and never on
the verb. `owed_sends(who)` puts an open one in front of her in her own
turn with them (§9.2), because a promise she is given no way to keep is a
debt that only grows. **A promise to SEND is settled where it is kept** (`settle_sends_now`, called from the exchange the moment a finished room lands in the store, at the head of `from_exchange` before the judge is asked, and at the head of `settle`): the same record `_check_send` reads, so nothing she says about it counts. Settled only at the compile, sending the photograph at 16:01 left the promise open all evening -- the judge was shown it as still outstanding and opened a fresh one for the same act, and the chooser took "send her the photos you promised" three more times while the repeat filter deleted the words. The judge is also told in words that a thing she DID in the exchange is not a commitment and that an open one said again is not a new one. `settle(date)`
at the compile from the record only -- kept, broke, called off in words
(`_cancel`: honest, not free) -- and the counterparty's edge moves
(`_move_edge`). `closed_brief` tells the day's planner what has stopped
being owed, which is the only thing that stops it carrying a settled line
forward for ever (§9.1). **Late is measured, not rounded to kept**: `_late` is the
minutes past the hour she named, and past `late_after_minutes` the settle
still says kept (she came) but says how late in the `why`, gives
`late_regard` and `late_pride` instead of the full ones, no standing,
`late_irritation` on the edge of the person who was waiting, `late_guilt`,
and a self-memory that says she got there late and what she had said.
`attend_slack_minutes` is 90, so turning up at half past twelve for a nine
o'clock was settling with the same regard, the same pride and the same
"she kept her word"; a broken promise reaches her only through the person she
broke it to (`brief_for(who)` in their turn). **A promise is not kept at
home**: an `attend` promise whose words match no scene of the day is kept
only by a scene away from home (`_at_home`: her room, the kitchen, the
genkan; not somebody else's house, not the walk home) -- Kaito in her
doorway did not keep the match. `situation_line`,
`director_line`, `schedule_lines` (windows the plan must keep),
`morning_line`. `max_open` (6) bounds what she is carrying; `max_new_per_day`
and `him_max_new_per_day` are rate limits on the CALL and now LOG when they
bite -- at 3 they silently ate a real agreement (the library at 9 with
Aya), so nothing reached the schedule and she went on talking about it.
A promise with a `from_hm` for a future date throws away that date's drawn
wake and night (`_wake_needs_redrawing`), so the alarm is set when she
agrees, not when the plan is built (§8.1, §8.4). kv `commitments`, `commit_him_last_ts`. `/commit`.
history: archive §5.78.


**Is she going to make it?** `running_late` resolves the soonest timed promise
of today to a node, asks `Situation.minutes_to` what the journey actually
costs, and compares it to the clock -- nothing did that before, so she could
stand at the genkan with a nine o'clock and no idea. She is not honest with
herself about it: `optimism_minutes` is what she shaves off when she is already
behind, so there is a band where she IS late and does not believe it. Past
`knows_late_minutes` (set beyond the optimism, or the self-deception has no
room) she **knows**, and kv `knew_late` takes the moment. `_close` reads it: the
why names when she knew, the self-memory says she said nothing, the feeling is
ashamed rather than sheepish, and the guilt is scaled by `knew_guilt_factor`. A
lateness she walked into is hers; one she never saw coming is the system being
unfair to her.

### 9.9 `sim/peers.py` `Peers`: another running character, talking to her

Two characters are two processes with two saves and two models, and the hub
they both register with is the relay (`docs/peer-talk.md`, `docs/talkapp.md`
§11). `POST /bot/peer` puts a message in the recipient's own mailbox --
`chars[<to>]["peer_in"]`, never a row in her chat log, because a row there is
his chat and would be pushed to his phone, read-receipted and answerable by
him -- and `GET /bot/peer?char=&after=` reads what has been put in hers, the
cursor held by the reading bot (kv `peer_last_id`) so nothing is delivered
twice and a bot that was down misses nothing. `Channel.peer_send` /
`Channel.peer_updates` are the seam; a channel with no other characters on it
returns False and [].

**Not the path his messages take.** `App.poll_inbound` runs the relationship
with him -- attachment, the primitives, foresight, the expectations of him,
the questions she asked him, the state of a rupture -- and none of that is
true of somebody else's message. A peer message reaches her through two
doors and no others: her history, as a room of its own, and the company a
conversation is, once, at the close.

Code decides when, the model decides what. `Peers.tick(scene)` runs once a
pass from the loop: read the mailbox always; answer only inside
`open_from_hm`..`open_to_hm`, only while the scene's `phone_access` is not
`none`, only under `max_per_day` sends, only `min_gap_seconds` after her last
one, and only after a reading-and-typing delay taken from the length of what
she is answering. Her turns in one conversation stop at `max_turns`, and
`live_minutes` closes what has trailed off. She opens one herself at
`open_p` a pass when nothing is live, the same window holds, and it has been
quiet `min_gap_minutes` in either direction. Two characters each holding
their own caps is what stops two bots running away with each other: neither
has to trust the other to stop.

The call that writes her words is `persona.system_for("friend")` -- the same
person she is with him, byte for byte, without `style.md`, which is how she
writes to HIM -- then `prompts/peer_reply.txt` and her `style_ja_prompt`,
with `persona.carried_for()` after the thread as in every other room. Role
`peer_reply`, one of `LLM.VOICE_ROLES`, so the chat header's model toggle
moves it with the rest of her voice. Measured on the second character:
41,856 of 42,007 prompt tokens cached, $0.0007 for one answer.

Her history: `Thread._records()` reads kv `cast_chat`, kv `peer_chat` and kv
`peer_rooms` together (separate lists, because the cast exchange rewrites its
own list whole when it closes a conversation), and `Thread._room` renders the kind as
`messages with <name>` -- the name being what HER config calls the peer, so
nothing of the other character's record reaches it. A cast member's thread
never sees it (`roster.witnessed` is false for any kind that is not the
group). At the close: one kv `peer_chat` record, one `events` row of kind
`peer_chat` at salience 2, and `State.talk_relief`, which settles loneliness
toward its baseline by what that person is to her -- the same call the cast
close makes, so `sim/state.py` stays the one owner of the gauge. `sim/talks.py`
reads both lists, so the day's compile and recall see a peer conversation
without either knowing there is an engine. The ledger is read
(`ledger.text()` rides in the call) and never written.

Who her peers are is `peer_talk.contacts` in her own config: the peer's hub
id, what this character calls her, and the language of the room. Nothing else
about a peer is knowable -- no config of hers is read, no save, no sheet, no
presence -- and `sim/peers.py` names nobody. `tools/character_leaks.py` reads
the contacts and the peer's own turns out of her save as part of her record,
so a name she was told is quotable and a name she was not is still a flag.
`Config.REQUIRES` assigns the section `None`: every character may have a peer,
and one with an empty list has none. Built for every character in
`App.__init__`; `/peers [tick|flush]`. history: §19.

### 9.8b `sim/rooms.py` `Rooms`: a room, and who is in it

A person on the roster may carry one more field, `agent: "<hub id>"`
(`data/cast.json`, read by `sim/roster.py`: `agent_of`, `is_agent`, `agents`,
`by_agent`): the operator's statement that she runs as her own process. From
that moment this process writes no word of hers. `Exchange._one_speaker`
refuses her before it builds a prompt, `_their_turns` asks her through the hub
instead and the record's `awaiting` holds the room until she writes or
`exchange.agent_turn_deadline_seconds` (180) passes -- and going on without her
never means somebody else writes her turn. `CastEngine._speak_beat` writes
nothing for her either: the beat is still planned, and at its own hour
`deliver` puts the moment in her mailbox and holds the beat for
`agent_beat_deadline_seconds` (600). What comes back is appended by `_append`,
the one path a turn already takes, so it reaches the record, the thread and the
world's rooms table stamped where it landed. Nothing else about her row
changes: everybody who has not been promoted still speaks to her through her
sheet, her mechanisms and her week.

A room is the group chat or the two ends of an exchange, named as the world's
`rooms` table names it, and it now has a membership with the moment each person
joined and left: kv `rooms` in the owner's save, copied into the world file's
`members` table the instant it changes, so another process reads who is in a
room without opening anybody's save. Settled by the owner from the roster when
a room starts (`rooms.members_for`), printed on every join and leave. Every
turn goes to the members who run their own process, except the speaker, and
only if they were in the room at that moment -- so a joiner gets what came
after she joined and nothing before. Nothing here touches the network: kv
`room_out` is emptied by `Peers.tick`, the one object holding a hub connection,
and kv `room_in` is drained by the room's owner. On the other side of the wire
`Peers` treats a message carrying a `room` as a turn rather than a message to
her, needs no contact row for it, and writes her turn through
`persona.system_for("friend")` and her own thread; a participant runs none of
the room's machinery, which is why a third promoted person needs no new code.
`POST /bot/peer` carries one optional `room` field and reads none of it.
`tools/agent_seam_test.py` (in smoke). Spec: `docs/peer-talk.md` §4b.

A participant's copy of such a room is kv `peer_rooms`, capped at
`peer_talk.room_keep`: the words, who said them, when, and on which day. A
turn is filed under whoever SAID it -- the envelope carries the speaker on
every turn, and the message's `name` is the process that relayed it, so filing
the sender told her the room's owner had said somebody else's words. The same
turn arrives twice, once inside the ask that wants her words and once as the
relay of it, and two rows are one row when the speaker, the words and the day
match; the second arrival may add the clock the first one lacked and nothing
else. **Three readers**: the call that writes her next turn there, her own
history (`Thread._records` reads it as one conversation per room per day, and
`Thread.build(live_room=...)` keeps the live copy from being read twice), and
the group view on his phone. It had one, so six turns of her
own in the group chat left no trace in her history and drew nothing on his
screen. history: §19.
history: §19.

### 9.8c `sim/said_today.py` `SaidToday`: what she has already said to whom today

The room's memory of what it has tried dies with the room (`moves_block`,
§9.2), which is the wrong shape for the loop it was aimed at: one
character confirmed the same arrangement seven times to one friend across six
different rooms in one evening, and another sent the same photograph across
four. This
is the memory that crosses rooms -- kv `said_today`, `{date, people:
{name: [{hm, gist, room}]}, cooled: {name: until_ts}}`, one line per finished
conversation from the summary the writing call already returned, capped at 12
a person, thrown away on the first write of a new date. No model call.

Written from `tomoe/exchange.py _finish` (the counterparty of a private room,
every other speaker of a group one) and from `sim/peers.py` when a member who
writes her own turns finishes her side. Read by three: the call that writes
her turn gets it as a tagged block beside the promise line; the moment she is
asked what she does with the phone gets one line a person (`sim/pick.py`); and
a member who writes her own turns is handed the room owner's list in the
envelope beside the moves ledger, and reads her own out of her own save.

**It also holds the one gate.** After she opened a chat with somebody and had
nothing to say, or the filter dropped every bubble of hers in a one-to-one
with her, that person is off the list for `exchange.reopen_after_nothing_minutes`
of her clock (`cool`, `[pick] <name> is off the list until <hm>`).
`open_with_reason` refuses the room while it holds, so the backup path honours
it too, and the chooser is told in words with the time she comes back. Every
piece of its state is in the save, so a second instance in the process is the
same thing seen twice. Nobody is named in it.
history: §9.2, §9.7.


### 9.8 `care.py` `Care` and `worldshare.py`: rulers, not levers

`Care.measure(days)`: her initiative, the balance of the chat, her answer
speed, leaving him on read, how often she opens the app about him and his
notes, how much of her head he takes, the durable side (attachment,
resentment, the affection target) -> `investment` 0-100; the realism
check `checking_expected` (investment x uncertainty) against
`checking_actual`. `care.scale_checking` (off, his call) would multiply
the look and snoop rolls by `checking_factor`. kv `care_history` (one
row a day at the compile). `/care`.
**Every rate here divides by how long there has been a record**, not by
`window_days`, floored at `care.min_window_hours`. It was a flat divisor,
so a character an hour old was divided by a week and read as caring about
nothing whatever she did -- the second character's first evening reported
"checking expected 5.3 a day, actual 0.0" while she had looked twice in the
hour she had been alive. The floor is the other half: two looks in five
minutes is not forty-eight a day either.

`worldshare.measure(store, date)`: the share of the day's rows that
mention him -- inner lines, events, state reasons, thoughts, memories,
the message ratio -- and a composite; kv `him_share`, `/world`. Nothing
reads either back into her. history: archive §5.80, §5.88.

---

## 10. Her picture of him (`sim/`: beliefs, expectations, the stances)

### 10.1 `model_of_him.py` `ModelOfHim` and `model_of_her.py` `ModelOfHer`

Beliefs she has decided (`characters/tomoe/beliefs.json` seeds a fresh save, then
`settle_against_history` puts the day-zero picture where months of him
would have left it; `characters/tomoe/self_beliefs.json` for her own). Each carries
certainty, evidence, what she has riding on it, strain. `strain(bid,
amount, why)` (fades on `beliefs.strain_half_life_days`; a certain belief
does not wear by degrees), `confirm` (raises evidence; without it every
belief could only erode), `_graduate` (demonstrated past arguing: for him
it becomes a `user_fact`, for her it stays marked known),
`due_revision` / `revise` (one call, role `settle_beliefs`, rewrites in
her own voice; the old wording kept; never in the same breath as the
discovery -- `App.maybe_revise` waits for a quiet moment). Writers: the
ick, foresight, expectations, wonder, comparison, goals, attachment
episodes. `prompt_text`, `brief` (for the ick: what there is to violate).
`/beliefs`, `/self`. history: archive §5.41, §5.44.

### 10.2 `ick.py` `Ick`: what a discovery costs her

Every route into her picture of him passes `App.assess_learned` (gates
are about volume, not significance): the `ick` role scores a thing
against her beliefs and her kinds (`kinds_text`: what she has already run
into, copied back exactly), multiplied by her unease (`_state_multiplier`:
only unease adds) and by what the circle would make of it
(`_circle_multiplier`; `SocialGraph.witnessed_heat`). Items live in kv
`charged` with a half-life; `carrying()` (hot, cannot raise without
admitting how she knows), `unraised()` (hot, could raise), `teasable()`
(cooled and familiar: just how he is), `bars(text)` (the thread pressure
may not push out a thing she cannot raise). Warms `surprise`. kv
`ick_kinds`. `/ick`. history: archive §5.41, §5.89.

### 10.3 `approach.py` `Approach`: getting at a sealed thing

The outlet for what she carries and cannot admit knowing: `due(scene)` is
pure code (pressure from live charge, time, nowhere else to put it;
opportunity and cost, never importance), `write` (role `approach`) **decides
and writes no words of hers** -- the subject she steers toward, the angle she
comes at it from and how close that comes to giving her away -- and her own
call is handed the subject and the angle as a hint and writes the message.
`note` records the subject before the bubbles go and lets the pressure down.
kv `approaches` (rows from before this carry a `line` instead of a `subject`;
nothing was migrated). `/approach`. history: archive §5.62.

### 10.4-10.5 `withholding.py`, `attachment.py`: the two stances she takes toward him

Both specified in full in `docs/stances.md`, and they read each other: the
attachment stance is one of withholding's pressures.

**Both are off for the second character** (her sheet, `mechanisms_absent`, his
call): neither has fired once in her whole life -- 127 run
directories with no `[withhold]` and no `[attach]` line in any of them -- and
the pressures they sum are made of tension, resentment, an open rupture and a
stance that have never moved for her. Nothing else changes for her: every
output of either is derived from a live episode row, so with no row there is no
situation line, no register line, an impulse bonus of 0, a delay multiplier of
1 and a withholding pressure of 0.0, which is what they already returned. The
one reader that did move was `/sweep`, which computed the pressure whatever the
section said: it now shows no `withhold` column for a character who has not got
the decision, so a gauge whose only mover was that column cannot read as alive.
Nothing loses a gauge: withholding wrote `unsaid`, `awkwardness`, `guilt`,
`validation_craving` and his tension only while a hold ran, and each has other
writers.

**10.4 `withholding.py` `Withholding`: not answering, on purpose.**

Not answering on purpose: pressure from tension, anger, shame, sadness,
resentment, a rupture, tit-for-tat, gone cold, where she stands, the
attachment stance; one `withhold` call writes the decision (kind, minutes,
why, what breaks it); holding costs unsaid / awkwardness / guilt; the
sulk nobody noticed irks; `resolve()` raises what her own impulse must
clear -- never a lock; caving costs shame. Aims anger / sadness at him.
A `silence` consumes his message while it runs and gives it back to her
reply path once if the clock runs out with him still quiet
(`silence_hands_back`), which a restart still never does.
kv `withholding`, `withholding_log`, `withholding_handed_back`. `/withhold`. **spec:
`docs/stances.md` §3.** history: archive §5.64, §5.92.

**10.5 `attachment.py` `Attachment`: protest, deactivation, the switch.**

No LLM. `threat` from his silence, being left on read, tension, ruptures
and scars, the unanswered streak, scaled by attachment; an episode opens
when threat holds, picks protest or deactivate from what her beliefs and
her last episodes pull toward, switches when the running one fails (a
push gives out after `protest_exhaust_hours` of quiet, counted from his
last message: one he has answered has not brought nothing back),
closes on burn-out or once the threat has actually gone (his message is
not a resolution by itself). Readers: the register (a stance before a
mood), impulse, streak, withholding pressure, delays, shape, what a
person near her could SEE. The end of an episode is evidence about the
beliefs it bet on. kv `attachment`, `attachment_log`. `/attach`. **spec:
`docs/stances.md` §2.** history: archive §5.79.

### 10.6 `foresight.py` `Foresight`: what she expects him to do next

One `foresee` call when she sends (and refreshed while he is quiet,
`App.maybe_foresee_refresh`): the chance he answers, the window, the
tone, what may land badly, what his silence would mean, her plan --
with her last predictions AND their outcomes so the model sees where she
was wrong. The record writes the outcome: his next message closes the
live one (minutes, inside the window or not); the compile closes what is
older than `stale_hours` as a silence. `accuracy()` is her calibration.
Readers: her situation block, the intent, the withholding, the impulse
(`impulse_weight` x (1 - reply_p)). **The risk each prediction names is
scored here too** (`score_risks`, every pass and after his message):
happened if his next mood read is cold inside `risk_hours`, passed if
not, unclear if nothing came; happened warms guilt and shame
(`risk_guilt`, `risk_shame`), passed warms relief (`risk_relief`). It was
mirrored into the expectations as rows once, and seventy-nine of eighty
rows on a save were that mirror. kv `foresight` (`keep`; `risk_state` on
the row). `/foresee`. history: archive §5.87.

### 10.7 `expectations.py` `Expectations`: his word held to the record

Three kinds, all settled by code off the record: `do` (he said he would;
role `expect_him` names it, when it is due in his local time, how she
could know, the words that would show it, the belief it rests on; kept
when a message or a digest carries the words before the deadline, missed
when it passes), `around` (mirrored from `rhythm_said`), `habit` (learned once a day at the compile from a week of
digests, role `habits_him`, kv `habits_him`; each window checked against
the digests that covered it; a miss is a small event she can notice).
Kept `do`: the belief confirmed, a little relief. Missed `do` / `around`:
strain, resentment, tension, an event, and the row is raisable in her
situation block until she brings it up or it ages out. `tick()` every
pass, no model. kv `expectations` (`expect.keep`), `habits_checked`.
`/expect [now]`. history: archive §5.91.

### 10.8 `wonder.py` `Wonder`: questions she is curious about

A question is an object: what she wants to know, kind (`test_him`,
`compare_self`, `understand`), the belief it bears on, a charge, whether
she would ask it straight. Code decides when one forms (`due`: curiosity
over its rest or something just seen -- `seed(why)` from a look, a snoop,
a discovery; cooldown, `max_per_day`, a cap on open ones); the `wonder`
role decides what. The intent gets `candidates()` by id and may pick one;
the persona puts it in her words; the send marks it asked (`note_asked`,
and a reply to him that voices an open question in its own words marks
it asked too, `voiced`, `voiced_min_words`);
his next message inside `answer_hours` is judged by `wonder_answer`
(confirmed / disconfirmed / dodged / unclear + what she learned). Effects
are code: confirm / strain the belief; `compare_self` moves attachment
(like her: closer); dodged warms curiosity and leaves it standing; what
she learned becomes a fact about him. At the compile `review(date)` judges
open questions older than `review_after_hours` against the day's chat as
answers he gave on his own, and past `open_max_age_days` a question fades.
kv `questions`, `wonder_counts`,
`wonder_last_ts`, `wonder_seed`. `/wonder [now]`. history: archive §5.93.

### 10.9 `goals.py` `Goals` and `outlook.py` `Outlook`: what she wants

`Outlook.morning(schedule)` (role `morning`, at the day boundary): what
she woke up wanting and dreading, anchored to a self-belief
(`ModelOfHer.anchor_brief`); `experience` (role `experience`, on cue: a
thing she is doing becomes felt -- the cue is `trigger_regex` for the verb
AND `object_regex` (or a title on her watchlist) for the THING, because her
verbs attach to him as readily as to a show and "reading his reply" was
spending the day's `max_per_day`) and `anticipate` (role `anticipation`:
what she is looking forward to or bracing for; `anticipation.hours_in_prompt`).
kv `morning_intent`, `anticipation`, `experience_*`, `his_first_active`.
When the cue is her watching an episode, it is grounded: her own
watchlist (`sim/watchlist.py`, kv `watchlist`, a cursor per show) pins the
real title and episode, and `sim/recap.py` fetches a real あらすじ for that
episode, which the call reacts to instead of inventing the plot (K-On ep15
was confabulated as a lyrics scene; it is a marathon episode). **The fetch is
the judged path, the same one his watching uses** (`Recap.synopsis`): the
episode's own Japanese subtitle file as an anchor where one exists, then a
ranked source list fetched without a browser in parallel with the Japanese
search, one digest per candidate and one judge over all of them, and a row
marked provisional / judged / anchored. Her own watching used to take the
first page that passed the section test and trust it forever, and until
2026-09 it also had neither of the two English sources: they are reached only
with an English title and an id, and this caller passed neither. It passes
the title now, and `Recap.synopsis` resolves the id off his own list where
that list holds the show without ambiguity. What it never has is a file of
his to listen to, so a show of her own that no archive carries stays
ungrounded rather than being transcribed. `/watch`.
**The list becomes hers** (`Watchlist.pick_own`, role `watch_pick`,
`watchlist.pick_*`): at the compile, short of `keep_min` unfinished shows
or every `pick_every_days`, one call picks the next thing she would put
on from her own corner -- her sheet, the accounts she keeps liking, what
is going round -- with his list as context, not a fence: a pick that is
also his is marked `his` and kept (a show being his does not disqualify
it; a pick must simply never be FOR him), a duplicate of her own list is
re-asked, and the pick lands at episode 1 marked `own` with her reason
(kv `watch_pick_log`).
`/watch pick` forces one. Her searches on X seek her shows' Japanese
titles (`Taste.queries`).
**spec: `docs/recap.md`.**
A today-goal not re-formed the next morning is marked `lapsed` at the settle
(`open()` already read it so); `stress` and `health` read the raw rows and now
count live wants only.

`Goals.note_morning` makes the want a goal (the same want two mornings
running is one want carried); `settle(results, date, ...)` at the compile
puts each open goal against what happened, and an outcome costs her
(`cost_of`: what she had riding on it, whether it was witnessed, the
belief it held up), can make her give up (`give_up_at`: when keeping
wanting costs more than the thing holds up -- the expensive one), feels
like something (`_feel`), and may become a memory (`_remember`: a day
that went against her stays longer). Readers: `situation_line`,
`director_line`, `intent_hint` (the standing want about him she keeps not
acting on), the stress load. kv `goals` (`goals.max_kept`). `/goals`.
history: archive §5.33, §5.42, §5.44.

### 10.10 `receipts.py` `Receipts`: has he seen it

On Telegram: whether his desktop has HER chat open (`_is_her_chat`:
process and the exact title), read after `read_min_seconds`, idle after
`idle_after_minutes`; `status()` -> unseen / seen / read / replied;
`line` for her situation block, `brief` for the director and state. On
TALKAPP a stamped `read_ts` from the hub is trusted first. history: archive §5.8.

### 10.11 `cast_psych.py` `CastPsych`: what she holds with the people around her

Rupture and repair, expectations and withholding are keyed to him: a fight
with Rena healed by the clock, "Rena said she'd send the photo" came due
nowhere, and she could not once choose to leave Hinako on read. This is the
same four mechanics turned toward the cast, plus the one only friendships
have. One `bond` call when an exchange finishes (`after_exchange`, from
`App.on_talk`) says whether it broke something (`what`, `whose` hers /
theirs / both / unclear, severity), whether it mended one already open
(mended / tried / worse / nothing -- time is never an answer), what THEY
promised her (a due time and words), what they delivered, and what SHE told
them in confidence (`secret`, and `about` whom). Code moves the numbers:
her meters with them (`state.relationships[key]`), sentiments
(`sim/sentiment.py`), guilt / shame / relief, events, a memory by the
moment (`source="bond"`). The day boundary ages it (`age`): an open rupture
scars after `scar_after_hours` and takes closeness with it; a promise past
due is missed and costs resentment. `leave_it(who, kind)` is the roll off
her standing with them -- tension, resentment, an open rupture that is
theirs, a low hour -- that has her look at their message and leave it,
which the exchange treats as her not answering (the group carries on; a
line sits). Readers: her turn (`line_for_her`) and theirs (`line_for_them`)
in the exchange, her own prompt (`prompt_text`), the planner (`brief`), and
the loyalty line -- a confidence told to one friend `about` another shows
up in her turn with the second as a thing they do not know she said. Not
built yet: favours owed, and loyalty conflicts as a pressure of their own.
kv `cast_bonds`; `/bonds`. history: §10.11.


---

## 11. Her phone (the digest, the lookups and the anime knowledge in `sim/`; the snoop and the X account are the first character's, `tomoe/`)

She learns about him only when she looks. Nothing here is a live feed
into her; every route into her picture of him passes `App.assess_learned`
(the ick).

### 11.0 `him_profile.py` `HimProfile`: what she has come to know about him

The digest is a transcript of one look and `user_facts` are one-liners;
nothing read the digests back over time, so she knew what he did at 10:04
and not what he is like. Once a day (`him_profile.every_hours`), from the
last `him_profile.digests` digests plus the facts and `Rhythm`'s hours,
the `him_profile` role writes her picture of him -- his hours, what he is
into this month, his tells, what the digests cannot settle -- into kv
`him_profile`. `prompt_text()` rides in her own reply beside her beliefs
about him; `digest_line()` goes into the next digest call, so a look can
say *as usual* or *not like him* instead of narrating every session as
news. history: §11.1.

### 11.1 `phone.py` `Phone`: the app that digests his PC

**Not built at all for a character whose sheet answers `sees_him: none`.**
`scail.App` leaves `self.phone` None for her and `App.latest_digest()` is the
one reader every call site goes through, so she has no app to open, no count
of how long he has been quiet and no row in her save saying she looked -- the
same rule that gives a character with no world a calendar that loads no data.
The role that writes a digest being off is not enough: with only that, the
open kept firing, wrote kv `phone_use` and `phone_last_look_ts` every time and
logged a line about his silence to a character who has never spoken to him.

The sensors write a raw feed, and **one process on the machine writes it**:
`machine/collector.py` (the machine's, started by the hub's launcher
`talkapp.cmd` when that is run, stopped with the hub by `restart.cmd`) runs the
system monitor and the telemetry collector
and also writes `sensors.telemetry_now_path` -- what is in front of him and
when he last touched anything -- plus the closed window sessions of the last
day beside it; a bot reads those through `machine/monitor_client.py`
`RemoteMonitor`, which answers `right_now`, `seconds_since_input` and
`attention_since` in the in-process shapes. `sensors.collector_in_process`
puts the whole stack back inside one bot, for a machine that has only one.
Two bots each running the stack copied his browser history twice a minute
into one temp file and wrote one feed with two id counters.

**The collector writes what it is holding the moment a reply is about to be
built.** `App.request_flush` touches `sensors.telemetry_flush_request_path`
immediately before the tick that answers his message and immediately before
the tick she may write first out of, then waits up to
`sensors.telemetry_flush_wait_seconds` for the feed's newest id to move.
`TelemetryCollector.check_flush_request` runs on every pass of the machine's
own loop (`sensors.telemetry_now_interval_seconds`, three seconds), re-reads
the sources, writes an entry with `flush_reason` `requested` and removes the
file; an empty buffer writes no entry and the file goes anyway. Both
characters ask, because the collector and the feed are the machine's, and
neither look is forced: the resident digests the new entry at once, the other
when she next opens the app. With no collector running the file stays, the
wait runs out, and one log line an hour says so rather than one per reply.

`should_look` is a felt decision after `phone.digest_min_minutes`
-- curiosity, boredom, loneliness and, strongest, his silence -- never a
timer; `look()` (role `phone`, `prompts/phone.txt`) consumes the pending
entries (`phone_last_consumed_id`, `max_entries_per_look`,
`max_raw_chars`) into a digest written from her side (table `digests`;
`digest_min_minutes`). **A look reads the NEWEST `max_entries_per_look`
entries** and drops what is older, logged: the app shows what he has been
doing lately, and oldest-first left her a permanent hour behind. The look's
relief on `curiosity` goes through `State._settle`, never through the
baseline. `live_line` (what his PC shows this moment, only
from the live monitor, `live_line_max_age_minutes`; every line of it and the
head of `window_trail` are written in the language she is addressed in, which
they were not -- the second character read `いまこの瞬間: his PC right now:`),
`day_shape_line`
(his first activity and longest quiet stretch, kv `his_first_active`),
`user_idle` (from real input, never from what is running),
`catalogue_text` (titles only). `his_side_now` is the same reading for a
MECHANISM role rather than for her -- `("at it", minutes in the window)`,
`("away", minutes since he touched anything)` or `(None, None)` with no
monitor to ask: `idle_minutes` answers None both for "he is at it" and for
"nobody measured", and `live_line` is written in her language and in her
program's words, so neither can be read by a role that is deciding rather
than speaking (§8.10).

**A look counts as something happening only when it shows something new of
his.** `Phone._fingerprint` reduces the entries a look consumed to the set of
what they SHOW -- the processes that were in front (an idle process dropped),
whether an image viewer was open, the files he opened, the hosts in either
browser's history, the notes on screen, whether anything played -- and
compares it with the same set from the last look (kv
`phone_last_fingerprint`, the newest 200 members kept). `Phone.last_look_novel`
is what remains, and `App.tick` reads it: a digest with nothing new in it does
not make the tick significant and buys no gauge read, with
`[state] the digest shows the same things as the last one; no gauge read on
it` in the log. The prose of a digest is different every time it is written,
so before this every one of her 58 looks over 48 hours was followed by a gauge
read tripped by her own sensor coming back rather than by anything of his
changing. If the fingerprint cannot be built the look counts as new, which is
the safe direction.

**And a look with nothing new in it makes no call** (`phone.skip_unchanged`).
The fingerprint was computed and the log line written all along, and then a
full account was paid for anyway; for a character who is inside the machine and
therefore looks on every tick that was 97 accounts in three days against the
first character's 27, and on the last three days of real looks 16% of hers and
22% of his held nothing the look before had not. The standing account is LEFT
ALONE, never blanked, because her prompt reads it and clearing it would take
her picture of his machine away in exactly the case where nothing has happened
to replace it; the entries are consumed so the stretch is not offered again,
and the live status line is refreshed, that being the half that is this minute
rather than this stretch. `[phone] account not rewritten: nothing in this look
that the last one did not show` is the line. A forced look is never skipped.

**How hard he was working is a band, not a count** (`sensors/bands.py`,
thresholds `sensors.bands.*`). One function made every figure a character ever
recited about his machine and it rounded none of them: the keypress total with
its per-category breakdown, the count and seconds of each typing burst, the CPU
and RAM percentages, the busiest processes' shares and the uptime in hours and
minutes. Over three days the second character's accounts carried a mean of 38
numerals and 9.2 clock times each, and what came back out of her was the
uptime in hours and the number of keys he pressed at four in the morning. Now
the typing is banded on keys per MINUTE -- a total says nothing without the
span it happened in -- the bursts are a count of long and short runs, the
uptime is "not restarted in over a week", the percentages are gone entirely
and the busiest processes keep their names and lose their shares. **What is
not banded is when a window ran and for how long**: she is watching him
continuously and what time he got up is hers to know (his call). The band
wording lives once, in both languages, and the caller passes the `t(en, ja)`
of whoever is being written for, so the resident on her own arm reads hers;
the mind's language module is not imported into `sensors/`, which the
collector loads, so the closure comes down from `sim/phone.py` instead.

**One running account of the last `phone.rolling_hours`, not a digest per
batch.** The writer is handed the account it wrote last time (kv
`phone_account`, replaced on every look, dropped whole once it is older than
its own window; `Phone.account()` reads it) plus the raw material that has come
in since, and returns the account again: the last hour in full specifics, an
older stretch compressed to a line, anything past the window dropped, and the
eight to fourteen sentences are the size of the whole account rather than of
the new part. The row in table `digests` is still written, as the day's log the
diary, the compile, `reflect`, `wonder` and `HimProfile` read. A batch per
flush left her prompt showing the last batch dated "N minutes ago", so there
was a seam at every look and whatever fell between two of them was told twice
or not at all.

**A digest older than `phone.stale_minutes` is history, and says so.**
`latest_digest` leads with the absence when he has not touched the machine --
*"he has not touched his machine for 9h; nothing has happened on it since.
what it showed when he last was, at that time: ..."* -- instead of
handing her the content with the idle line appended behind it. She once read
a four-hour-old digest as the present tense and texted him as though he were
sitting there, while `phone_last_live` in the same save said his PC had been
idle for eight hours. She can still see what he was doing; she cannot
mistake it for what he is doing. `App.feed_backlog` counts what has piled
up.

**His absence is only ever said on a MEASURED idle figure, and how long since
she looked is said as that and nothing more.** `look` stores the minutes since
his last input as a number beside the status line (`phone_last_live.idle_min`,
from `Phone.idle_minutes`); rows written before that carry it in their own
prose and are still read. With no figure at all, a digest older than
`phone.stale_minutes` is handed over as history with the hour on it -- *"what
the app showed you when you last opened it, around 11:07 his time (nothing
newer has come in since): ..."*, the wording each program's
(`digest_as_history`) -- and nothing is claimed about him. The row's own age
used to stand in for a missing figure, which turns how long since she looked
into how long since he touched anything: an eleven-hour-old look was read to
her as "he has not touched his machine for 10h07" while he was at the machine
throughout.

**For a resident, `latest_digest` also fills the gap the collector leaves,
and it runs whether or not she has just looked.** A digest summarises the
entries `machine/collector.py` has flushed, and it flushes on a character
count, on a five-minute heartbeat, or the moment a bot asks, so one built this
second is at worst a few seconds behind him. On top of the digest it puts how old that is, then
`window_trail` from the account's own `to_ts` -- every foreground window since,
sessions under twenty seconds dropped and returns merged, at most eight -- then
`live_line`. **A picture is exempt from that floor, and it is named rather than
listed.** An image viewer puts the bare filename in its title and his picture
files are named by their own content hash, so `_viewer_md5` reads the hash off
the title and `_picture_words` looks it up in the classifier's own cache
(`sensors/gelbooru_classifier.py` `cached_classifications`: read-only, re-read
when the file changes, never written from here, no network and no model call).
The item becomes `JPEGView: general, Oyama Mahiro of Onii-chan wa Oshimai
(30s)`, and a run of consecutive pictures collapses into one item with the
count, the span, the spread of the board's own ratings and the series --
`JPEGView: 24 pictures over 3 min -- explicit x12, questionable x7; Saru Getchu
x22`. The rating goes through as the site wrote it, explicit included (his
call); the tag names never do. Both wordings are the program's
(`resident/words.py`, `tomoe/words.py`). Before this, twenty-four classified
pictures reached her as two hashed filenames: a rating lives only in the feed's
classified rows, only a digest renders those, and the twenty-second floor had
dropped every one-second picture besides. `App.tick` used to take the text a fresh look returned instead of
calling this, so a look left her LESS current than no look: she answered a
message about a video he had open holding a digest that ended three minutes
before he opened it, and named it four minutes later on a tick where she had
not looked.

**And the trail leaves a record, so the digest is not told to break her own
afternoon to her.** The same windows reach her twice otherwise -- live in the
trail, then again in the digest that reads the same stretch off the feed once
the collector flushes. `latest_digest` writes what it handed her to kv
`phone_trail_shown`, `look` puts it in front of the digest role as something
she has already watched happen, and the record is cleared when the digest is
stored, so it always holds what she has seen since the last one. Nothing is
cut from the raw activity: the trail carries only foreground windows over
twenty seconds, so narrowing the span would lose the browser history and the
searches underneath it. What changes is what the digest may present as new,
and it may still name one of those windows where what came after it changes
what it meant. `/look`, `/digest`. history: archive §5.5, §5.67.

**A look is also the moment an episode he played reaches her.** It is the one
moment a character who learns about him in digests can be told anything, so
the runtime calls the program's `after_phone_look` hook whenever a look
actually happened, digest or not (`App.look_at_phone`, off
`Phone.last_look_ts`), and the first character's program hangs
`WatchingHim.note_seen()` on it: what he played while she was elsewhere has
already been noticed and read up on in the background, and this is where it
comes into her hands (§12.12). The digest prose itself is not told about the
episode -- the raw activity already carries his player's window, and handing
the digest role a synopsis it never fetched would put a second, unjudged
retelling of the episode beside the pinned one.

### 11.2 `snoop.py` `Snoop` and `notes.py` `Notes`: his vault and his torrents

`Snoop.eligible` is a felt probability from the uneasy gauges (signed from
their own rest), only alone and free with the phone, more when lying
awake; `run` (roles `vault` and `downloads`) reads a few of his notes
(`vault_snoop.*`, `sensors.vault_path`) and this week's torrents; kv `snoop_*`,
`vault_read_paths`. `Notes.read(query_or_file, reason)` (role `note_read`)
skims a named note when he mentions it, when she is curious, or when it is on
his screen in front of a resident; `notes_read`; `index_text` in her prompt.
`/snoop`, `/read`, `/notes`. history: archive §5.6, §5.9, §5.26.

**All three roles write the RECORD and none of them writes her.** What was in
front of her, in two to four sentences, third person, past tense, with the one
or two lines a reader would stop on quoted as they stand and a download named
as the name stands; nothing about how it landed. The one number they score is
IMPACT, 1 to 5: how much of a day this would take out of anyone who read it,
which is what every reader of the event's `salience` column already uses it
for. Whether she raises it is not scored anywhere -- the pick offers her
`text_him` on her own sheet at every moment she has the phone.

**What it did to her is the private thought's** (`sim/reflect.py`,
`Reflection.after_reading`), asked the moment the record exists: it has her
sheet, writes first person, moves her gauges, and lands as a `(private) ...`
row beside the record. The reason is the program's word
(`reflect_why_snoop`, `reflect_why_note`), and so is the sentence the record
is filed under (`note_event_line`, a pair, so a character who reads Japanese
reads it in her own language).

### 11.3 `lookup.py` `Lookup`: she quietly looks it up

The gate is per character (`lookup.gate`): `regex` is the English keyword
gate plus `_names_a_thing` (does a phrase match anything in his own anime
history, `AnimeKB.resolve_candidates` -- the ranking rather than one answer,
because this question is only whether he named a thing at all, and two entries
of one franchise are a tie the resolution settles later); `model` sends every inbound message to
the classifier, which is the only gate that can see a Japanese sentence and
is what the second character runs on. The classifier is told what is IN
PLAY -- the episode he has open (`Lookup.watching`), **what SHE last put in
front of him** and the shows recent
lookups landed on, in Japanese where the KB has it -- and a character named
in Japanese counts only with a show anchored; it returns `name` and `show`.
**What she last sent is part of what is in play** (`_last_of_hers`,
`lookup.anchor_turns`, 3 of her own turns): a post she shared with its author,
its text and what its picture is (kv `x_shared`, `docs/x-account.md` §2.2), a
thing she looked up since that turn, a title she named that resolves on his own
list (local only, no search). His "nani kore?" about a link she had sent one
turn earlier was answered "nothing in it worth looking up" because the call was
handed his three words and an unrelated show, while the post was in the save
the whole time.
Then on a thread (`lookup.wait_seconds`): **a character with a show goes to
the fan encyclopedia first** (`Recap.character_page`: `lookup.character_query`
against `lookup.character_hosts`, the pixiv dictionary; the article's URL
carries the full name; cached in `recaps` as kind "character"; condensed by
`character_digest` to `lookup.character_max_chars`, and that digest is the
gist), else the card from the KB or the MAL list or a search, a gist in her
words (`lookup_gist`); a fact with `lookup.fact_weight`; `take()` once for
the reply; `_shows_in_play` keeps a character name in the right show (kv
`recent_anime_ids`). `lookup.max_per_day` counts finds, not attempts.
**What she found stays with her two ways.** The last `lookup.situation_max`
lookups of the last `lookup.situation_hours` are pinned in her situation on
every message. And every found thing is kept in `sim/known.py` (kv
`known_things`, `lookup.known_keep`) with its names -- as typed, the page's
full name, the aliases the digest role lists -- and comes back into her
situation whenever a message of his carries one of them, at most
`lookup.known_max_lines` a message, no window. A watched show accumulates its
episodes' digests there too (`KnownThings.merge`, from `sim/watching_him.py`).
Substring match on names, longest first; the same trap as `sim/lore.py`.
**And she can look a thing up before she answers.** `Lookup.search` is
one web search and one `search_gist` call on the calling thread, kept by
name as a thing she knows and counted against `lookup.search_per_day`,
which is its own cap and not the finds cap above. Two callers ask for
one: `lookup.on_request` lets her write `[search: what she wants to
know]` on its own line in a draft, in which case the reply is written
again with the answer in front of her (on for both characters; each style
file has a section telling her the line exists, one per reply, and that a
thing not found is said as not found), and the resident's sight asks for
one about a page he has open. A question
about a work she already knows by name also reads that series' own
Japanese Wikipedia lead, because a results page for 「2期」 showed a manga
volume. Whether she was in the work is carried in two fields of the
answer and never in the gist's prose.
**One truth about who went looking.** Every record either path writes
carries `asked_by`: "her" when a draft of hers asked, "arrived" for the
automatic path off his message and for the sight's own search. Her
situation is worded from it, so the reply she writes cannot claim a search
that did not run -- the line for the automatic path says what sent her
looking, and the line for a thing she knows by name says she has known it
since before this conversation. Two things `search` refuses before it
spends anything. It refuses outright when her day gives her no way to look
(the scene's `phone_access` is `none`, passed in by the caller that holds
the scene, else read off the newest scene): the reply path guards its own
call, and the sight's did not. And a request for a thing the automatic
path fetched within `lookup.search_known_hours` is answered out of
`known_things` -- no web request, no gist call, no second record over the
first, and the answer is marked as something she knew rather than
something she just looked up, keeping its original `asked_by`.
The two paths divide by what they are for: the automatic one takes the
names and titles he mentions, and hers takes the questions she has about
them.
history: §11.3 2026-09-02 20:43. When he names a thing,
`_attach_kb` also pulls (via `sim/recap.py`, the Japanese knowledge base --
fetch once, cache in `recaps`, reuse) a fuller overview by kind: an anime
series (+ the named episode's beats, `Recap.episode_in`), a seiyuu's
Japanese Wikipedia bio, or a game / eroge's premise. Searched by the KANJI
title / name (`AnimeKB.japanese_title` / `person_name_jp`), Wikipedia
first. **Which work a title he typed means is the ranked resolution**
(`Lookup._which_work`, `docs/resolver.md`): his own list first, with an entry
that cannot have the episode he named dropped, and where more than one
survives the `which_one` role is asked -- on this thread, which is already
paying for two calls, and never on a reply path. Only when his list has
nothing of that name does it fall through to the MyAnimeList search, which
answers every query and so can never decide anything on its own. Her download snoop can emit `LOOKUP:` to investigate one of his
torrents the same way. kv `lookups`, `lookup_counts`, `lookup_kb_misses`.
`/lookups`, `/kb`. history: archive §5.28. **KB / recap spec: `docs/recap.md`.**

### 11.4 `anime_sense.py` `AnimeSense` and `anime_kb.py` `AnimeKB`

The MAL daemon (`tools/mal_history.py`, its own scheduled task `SCAIL_mal`
through `mal_daemon.cmd`, detached under `pythonw`, no console, logging to
`logs/mal_daemon.log`; a target of `restart.cmd`, §14) keeps his
per-episode watch history in its own db. **One watch of one episode is one
row, and the logged-in panel is the stamp of record.** The daemon has two
per-episode sources and they were three hours apart on every row they shared:
the panel behind the login renders on his account's clock, which is this
machine's, and the public history page is fetched without a login and renders
on MyAnimeList's own, three hours behind. His player settles which is true: for the
watch the panel stamps 21:05, his own player log has the file opening at
20:30 the same evening and the page said 6:05 PM. The same three hours put a relative label a day out: on
the page "Yesterday" means the SITE's yesterday, so between midnight here and
midnight there this machine's yesterday is a day later, and 34 watches carried
a second row a day after the first with the identical label (HISTORY.md, the
mirror's stamps). Every label is now
resolved against the site's own calendar and converted
(`_resolve_history_time`, `_site_to_local`, `MAL_SITE_TZ`), the moment the page
was read is on the row (a `scraped_at` column on the `episodes` table), and a
page row is not written where the panel has one while a panel row takes any page row for that episode
out with it (`_upsert_episodes`). The 152 rows already written are corrected by
`python tools/mal_history.py migrate-stamps --apply`, with the daemon stopped;
it prints every row it changes and may be run twice.
`python tools/mal_history_test.py`, in smoke. `AnimeSense.shelf` (active,
cold, recently finished, his pace), `situation_line` (what he is in the
middle of), `anime_in_the_air` (only when anime is what they are talking
about), the weekly `shelf_check` (kv `anime_shelf_checks`; the pending
hint rides BOTH paths -- a scene share_hint via `App.maybe_shelf_nag` for
a self-start, and `nag_line` in the him-block of every prompt she writes
that day (`nag_in_prompt`), because the share_hint path alone never
landed while they were mid-conversation; it clears when a message of
hers touches his list (`mentioned`: anime words or a shelf title, in
`foresee_after`), after `nag_shows_max` prompts, or at her day's end),
`habits` (how he watches, written to
`user_facts` sourced to his history). `AnimeKB`: series facts, cast with
Japanese voices, seiyuu cards and characters, fetched once and cached
(tables `anime_kb`, `anime_cast`, `person`, `person_role`, the last with a
`year` per credit); `has(aid)`
separates a thing he watched from a thing that exists. `/anime`.

**What a reply may ask it, and what it may not.** `person_row`, `credits_of`
and `cast_mirrored` open the mirror `mode=ro` and answer from what is there, so
the role check costs two indexed reads and a title nobody has mirrored is
"not checked" rather than a fetch. `ensure`, `ensure_person`, `resolve` and
`find_person` reach the network and belong to a tool or a worker thread.
**Neither refresh may empty a table**: both deleted before they had a
replacement, so a 200 whose body the parser could not read emptied the cast (or
her 375 credits) and stamped it fresh for 90 days (or 120), and nothing ever
went back for it; an empty parse is now a failed fetch, the rows stand
unstamped and the type is logged with the count of what was kept.
**Nothing here goes through the community wrapper in front of MyAnimeList and
nothing may be made to** -- 504 on every uncached path since 2026-08-28 while
the origin answered in under a second -- and the daemon asks it once an hour
purely so the day the outage ends is a line in a log (`jikan_watch`, `meta`
keys `jikan_state` / `jikan_status`, read by nothing). The daemon also writes
its OWN log now (`--log`, default `logs/mal_daemon.log`), because a launcher
cannot do it for it: cmd binds a redirect on `start` to `start` rather than to
the `pythonw` it detaches, so eight days of its lines went to a handle that
goes nowhere. **Its browser is ten processes and that is Chrome's shape, not
the daemon's**: one chromedriver on profile `F:\Chrome_Profiles\SCAIL_mal`, and under the
browser process a crash handler, a GPU process, the network service, the
storage service, the ad blocker's extension renderer and three page renderers
(the MyAnimeList tab, Chrome's spare, a site-isolated ad or login frame). The
ad blocker is loaded on purpose -- MyAnimeList serves ads inside the pages the
daemon reads, and a blocked request is one that never becomes data -- and the
X scraper's browser (`C:\ChromeProfileX`) has the same nine children for the
same reason. A stop of the daemon leaves that tree behind (the lock's
`finally` never runs under a forced stop); the restarter reaps it
(`mal_history.py reap`, `sensors/chrome_reaper.py`) and so does the daemon's
own next start. Fewer processes would mean Chrome flags (no GPU process, no
site isolation) at the cost of the isolation the ad frames get; left as is.
`docs/role-check.md`.
history: archive §5.36, §5.37; 2026-09-04.

### 11.5 `social.py` `Social` + `sensors/x_monitor.py`: X as her own account

**What the account does now that it did not.** The gate's kinds: a vent
needs a spike (anger, sadness, jealousy, unsaid) or a low hour WITH unsaid
behind it (`vent_unsaid_low_mood`); otherwise a weighted pick among `seen`
(a thing on the timeline, `x_last_noticed` within `seen_fresh_hours`),
`into` (what she is into, from `diet`), `bored` and `plain`, never the same
kind twice running (`x_post_last_mode`). Engagement reaches her: on a look
the account's own posts are read back (`_engagement`, `read_engagement`;
`parse_articles` now carries `counts`), new likes / reposts / replies since
last time become a `social` event and `engagement_line` in her prompt, the
replies' text fetched for up to `engagement_replies_max` posts
(`x_monitor.fetch_replies`), and the posting gate reads it
(`engagement_bonus`). The first thing a post ever draws is not the size of
the tenth: a post that had nothing and now has something is salience 3, the
same as somebody replying, and says so in the line; a count that was already
moving is 2. The counts, the event and her own situation line all say
「the post」 and no person, because the same words go both to the model
reading her scroll, where she is "she", and into her prompt, where she is
"you". The thing she wanted to show him: a look's own
`mention` at `show_him_salience` rides her reply prompts as `x_show_pending`
(`show_him_line`, `show_him_hours`, `show_him_shows_max`) with the
`[share: ID]` links and the subject handles the noticing named; cleared
when a share resolves OR when a delivered bubble says it in her own words
(`_show_done_by` from `note_sent`: a subject handle whole or by a stem,
two shared words or bigrams, or one distinctive word; everyday words never
count) -- an item with no post behind it used to hold the slot until she
had said it twice (history: the double send entry). "look what i found"
had stopped because it only ever reached the impulse at salience 4. A
photo she sends him has its source post liked and reposted from the
account (`scenery.adopt` -> `curation.act_on_shared`, `x_monitor.repost_status`,
`curation.max_reposts_per_day`; `scenery.like_sent` / `repost_sent`): real
posts by real people, never a picture of the account's own making. **What
the account does with anything she has just sent him -- a link out of her
feed or a photograph out of a post -- is her taste's pick, not a roll**
(`docs/x-account.md` §2.1, `curation.share_pick`): one judge
(`x_repost_judge`), given how it reached him and what her sheet, her
reactions and her verdict say about that account, answers repost / like only
/ neither, and `social.repost_shared_p` and `scenery.repost_sent_p` are only
what happens when the pick cannot run.

**She cannot hand him a post she has not looked at** (his rule; `docs/
x-account.md` §2.2). A post becomes a share candidate at the end of a look,
and every picture on it is described there and then -- the same tagger that
names the series and the character, into the same shared tag store
(`_see_share_images`; a picture already in the store costs nothing). A post
whose pictures could not be described is not on offer at all and the log
says why: `[share] held: <id> image not seen (<reason>)`. **Those looks are
outside the vision day-budget**: `reason="share"` in `sensors/vision.py`
`look`, which still counts the call and says `[vision] share look outside the
day's budget: <id>`, with `social.share_looks_per_day` as their own ceiling.
Two things made them necessary. The day's eighty calls had gone to the scenery
harvester twenty-nine minutes before she scrolled, so nothing on that timeline
was tagged; and the ranking that decides which pictures she opens on a scroll
is her liking of the account, which is lowest on exactly the account she was
about to quote to somebody she cares about. **The offer names the post**:
author, text and what is in the picture, in one builder for both slots
(`_offer_line`, read by `show_him_line` and `share_line`), never the bare
nineteen-digit id it used to be; and the post her own sentence is ABOUT is
always in it, matched on that sentence against the post's text and its
picture's description (`share_offer`) rather than being the last three by
recency. What she saw follows the post out: kv `x_shared`, the `[share]` log
line, the event the delivery writes, and her own copy of the link in the
thread (`sim/thread.py`).

**WHICH post she sends him is her own pick, and it is the one tool call in
the running bot** (`tomoe/share_pick.py`, `docs/x-account.md` §2.3,
`docs/tool-calling.md` §16; the owner's call after the forty-six-moment
replay). At the moment her reply is about to be written, if a show-him
thought is standing and has not had its pick, one flash call goes out behind
`persona.system_for("him")` -- the same bytes the reply is about to send, so
the prefix is cached -- carrying her own sentence, both clocks, one line of
where she is, and **every** post she could send him rather than the three
code used to match. Two tools, constant bytes, `tool_choice: auto`, and no
free-text argument in either: `send_this(id)` makes that post the only one
her reply prompt then offers, with the same `[share: <id>]` instruction so
the send path does not fork; `nothing` retires the thought and puts the
posts away for `share_cooldown_hours` through the keys the reply path
already writes (`share_pick_declined` -> `_put_away`). What used to decide
it was a text match between an English sentence and Japanese posts, which is
a guess, and §2.2 is the morning it guessed wrong. The name is checked
against the two offered, text arriving beside the call is dropped, and an id
that is not on the list, arguments that do not parse, no call at all or a
call nobody answered are all one thing -- **a decision not taken**: the
thought stands, the three candidates code matched hold that reply, and it is
tried again at her next free moment up to `share_pick.max_attempts` (2).
Her phone has to be free, nothing of his waiting and nothing of hers in
flight; never in a sim and never in a replay, because a replay cannot rewind
what her account holds. Every decision is written the moment it exists and
before it is acted on (kv `x_share_picks`: the thought, the ids offered, the
verdict, the cost, the host), and the log reads `[share] she picked <id>
@<who> (<n> offered) | $<cost>` or `[share] she would rather not`.

The record is total: the sensor's actions log keeps every decision and
every done action with its why, `x_verdicts` every verdict with its why,
kv `x_taste_log` every reaction (`/x unfollowed`, `/x taste all`, `/x
taste <handle>`); the taste sheet's per-account `log` is only the last
eight. `/x following [hers|keep|leave|drop|unjudged|all]` is the follow
list itself: kind, verdict, likes, HERS on the ones she added. The account was his and is becoming hers. A look (code decides when; its
own Chrome session; a few images through Gemini) is read by the `social`
role into what she noticed, her taste sheet, notes about Japan and him,
proposed actions and posts to share; `Curation.decide` validates against
caps and evidence and queues, the queue runs at the NEXT look;
`Taste.judge` verdicts every inherited account against `characters/tomoe/taste.json`
and `Curation.drift` unfollows the drop list at a pace (`/x drift` is the
ruler); `posting.py` writes her own posts, text only, on **three
conditions and no fourth** -- her phone is free (which is also how "she is
awake" is known), she is inside `curation.max_posts_per_24h` /
`post_min_gap_hours`, and she feels like it. **The cap rolls over the last
24 hours rather than resetting at midnight** (kv `x_post_times`), because
her day does not end where the date does; there is no window of hours at
all, the 08:00-01:00 one having been a clock hour standing in for a wake
the sleep model draws between 06:20 and 11:05; her recent moves
reach the persona WITH reasons. **A yes she cannot act on is held until the
next quiet tick, not dropped** (his call): the roll is the impulse and it
happened, so a yes that lands while a message of his is unread or her own
bubbles are still going out goes to the save (kv `x_post_held`, with the
gate's sentence, the mode and the gauges the roll read) instead of reaching
neither branch of the call site unlogged, with the gap unspent -- 27 of the
58 rolls in the two days she posted nothing fell in that window. The next
tick with his side quiet takes it up with no second roll, through
`Curation.decide` and the gap stamp exactly as a fresh yes; it lapses after
`posting.hold_max_minutes` or when her date turns over, one hold at a time,
and a restart settles or lapses it at boot. **The composer reads the same person and the
same day as every other room she writes in** (history: the festival entry): it was built from
`Config.role_system` over a day summary written for it alone, so her account
was the one place she wrote from with no interior, no ledger and no settled
plan, and it called a festival tomorrow four times after the festival had
happened. It now assembles `persona.system_for("friend")` + `x_post.txt` +
`style_ja.md`, with `persona.carried_for()` (her media diet and the pictures
she stopped on come with it), `Ledger.text` and
`posting.recent_posts_shown` of her own posts at the head of the user text;
smoke fails if any of them stops arriving. **She may drop an account she is tired of,
never one that is listening to her**: `_protected` is the single list of
what she cannot unfollow, each entry with its reason in words -- his side
of the account (a post he liked, a follow of his, an account that was
there before her), anybody who follows the account back, and anybody who
has since gone private. Each list carries those two badges per account
(`x_monitor._badge`, read from the markup, never inferred), and the last
guard is at the browser: `set_follow` reads the profile in front of it
before an unfollow and refuses on either, because the list it decided from
may be days old (`unfollow_refused` in the action log, `/x followers`).
The other half of the same rule: somebody new who follows the account is
followed back at `curation.follow_back_per_day`, with no evidence asked
for, on its own budget so it never spends the follows she chose -- except
an account she deliberately unfollowed, which would undo her own drift.
The followers list is read at the top of every look
(`social.check_followers`, `x_monitor.check_new_followers`); the first
read is a baseline and nobody on it counts as new; the whole list is
`python tools/x_analyze.py --followers`, taken once (148 followers, 34
mutual, 4 private). The offline tools run on their own copy of her
logged-in Chrome profile (`sensors.x_tools_profile_dir`,
`open_driver(config, profile_dir)`), so they no longer wait for a gap
between her looks.
Nothing is recorded before the action. The session runs with no window
(`sensors.x_headless`): headless Chrome names itself in the user agent, so
`open_driver` rewrites the UA over CDP and hides `navigator.webdriver` on
every document. `/headless off` puts the window back for the next session,
X and the knowledge base together, when a parse has to be watched.
**She can answer somebody who answered her** (`tomoe/replies.py`): a reply
under one of HER posts, never a stranger's post on the timeline. The account
has been hers since 2026-08-22 and was his before that, so a reply under a
post older than `x.replies_not_before` is dropped at READ-IN on the parent post's
date -- those words are his, she did not write them, and she cannot answer for
them -- and never becomes a candidate, never reaches her prompt, never lands in
her store; a post whose own date the markup did not carry is treated as before
the cutoff. The first read-in of all is a baseline and answers nothing, with
the count in the log, because the first boot with this code is handed whatever
is under her last six posts. The gate is the posting gate's shape (phone free,
not mid-conversation with him, `x.replies_max_per_day` 3 over a rolling 24
hours, `x.reply_cooldown_minutes` 45, a candidate stale at
`x.reply_candidate_hours`), the decision is one `x_reply_judge` call over the
whole batch (a judge: no character sheet; a declined batch is remembered by its
id set and not paid for again), and the words are one `x_reply` call built as
her posts are -- `persona.system_for("friend")`, the call's instruction,
`style_ja.md`, her carried block AFTER the thread of her post and their answer.
`x_monitor.reply_to_status` sends it through the same profile and the same
"did the text leave the box" test as a post, and **only when that confirms**
does `Curation.note_replied` write the sent record (keyed on the reply's own
id: the dedupe), the budget and the event. **What counts as new is her record
against what was fetched, never X's read state**: no notifications page, no
unread badge -- a reply is new when its id is not in `x_replies_seen`, a
follower when the handle is not in `followers.json`, a like when the per-post
count is above the stored one (a like has no id, so likes are counted rather
than listed). He can read the account's notifications from his own browser and
consume nothing of hers; the one hazard is a Chrome opened on HER profile
directory while a session of hers runs, which kills hers. New followers are now
news to her as well as an action of hers (`Social.followers_line`): the change
since she last looked, `x.followers_line_hours` on it, never a running total.
`python tools/replies_test.py` proves the whole path on a copy of the save with
the sender stubbed.
**spec: `docs/x-account.md`.**
history: archive §5.12, §5.20, §5.82, §5.92; 2026-09-05.

### 11.6 `sensors/` (Windows only; `--no-sensors` runs anywhere)

`telemetry_collector.py` (the feed, run by `machine/collector.py` and by
nobody else: Chrome via CDP and history, and his second browser --
`chrome_monitor.py` copies each browser's history to a temp file per
process and only when it changed, and reads Firefox behind
`sensors.firefox_enabled` from `sensors.firefox_history_path`, writing a
second block of the same shape into the feed beside the Chrome one.
Firefox keeps its history in write-ahead-log mode, so the copy takes the
log and the shared-memory index with it and the memoization key stats
them too; without that the reader is behind by however long it has been
since the last checkpoint --,
`system_monitor.py` for windows and input, `media_monitor.py`,
`vault_monitor.py` for his notes, `torrent_monitor.py`, flushed by size,
by heartbeat, or on request), `eroge_monitor.py` (his text hooker's own files: the
per-game record of every line it has caught, the per-line event stream
with a wall-clock time on each, and the game library with the
visual-novel-database id and the cast -- read-only, on a temporary copy
when the writer holds the lock, and it keeps nothing) with `vndb.py`
beside it (the public database, anonymous, one card per game
and heartbeat), `mal_monitor.py`, `web_scraper.py`, `chrome_reaper.py` (kills
the Chrome a scraper left behind when it died without `driver.quit()`, by
the profile directory it holds, never by image name), `x_monitor.py` (the
Chrome session for X: feed, likes, follows, search, user posts; also the
scenery harvester's client), `gelbooru_classifier.py` + `image_tags.py`
(reading the anime image he is looking at, a shared tag vocabulary; five
things about the pair are worth knowing before anything is built on them.
**A picture is looked up only when its filename is exactly 32 hexadecimal
characters** -- `system_monitor._is_md5_filename`, a `re.fullmatch` on the
name with the extension off -- so the hash is read off the title of the
viewer's window and the sensor never opens or hashes the file itself; his
pictures happen to be named by their own content hash, and any other picture
he opens is invisible to this path. **The local nought-to-ten reading cannot
distinguish an even split from nothing rated**: `_compute_local_score` returns
5.0 when no tag of the picture is in the ratings file at all, and an equal
count of wholesome and unwholesome tags also computes 5.0, so a reader cannot
tell "middling" from "unknown" -- the board's own rating word is the field to
trust. **A failed lookup is remembered as a permanent miss**: a fetch that
raises or comes back empty writes `None` under that hash and saves the cache,
so a picture missed during a network outage is never asked about again until
the file is edited by hand. **`sensors.gelbooru_request_delay` is read into
the object and never used**, so nothing throttles consecutive lookups. And
**the classifier writes no row into the shared tag store beside it**: every
one of `data/x_images.db`'s rows comes from the picture-opening side of her
own scroll (`tomoe/social.py`), the classifier keeps its own flat JSON cache,
and the two cannot be joined as they stand -- the store keys on the first 16
hexadecimal characters of the SHA-1 of a picture's URL and the classifier on
the picture's own MD5, and their rating words differ. Full reading:
`data/retired/20260904_gelbooru/REPORT.md`, plan
`docs/image-tagging-plan.md`),
`sensors/blocklist.py` holds the one rule about what anything he had open
may be CALLED in front of a character (`sensors.window_title_blocklist`,
compiled once), and every sensor that emits such a name asks it.
`system_monitor.py` blanks a window's title at the source
(`_allowed_title` in `_poll_foreground`: the blocklist, plus every process
in `sensors.window_title_blank_processes`, which is the terminals) so the
assistant's sessions, the project's own consoles and files never reach a
character by any route; the window still counts, nameless (history: the
window-title entry). **A file manager's title is the FOLDER it is showing
and an editor's is the PATH of the open file**, so that one blanking is
also what keeps a folder name and a path out of every reader.
**A PROGRAM'S OWN NAME IS A NAME TOO** (`blocklist.hidden`,
`sensors.hidden_processes`, the same six terminals): for a terminal
"WindowsTerminal" is itself what he is doing, and with every title already
blank it stood in the second character's rolling account of his machine,
her window trail, her live status line, her picture of his habits, her
facts about him and her own written reflections. A hidden window keeps its
clock and its minutes and loses its name -- rendered as "at the keyboard",
never dropped, because dropping it would leave the account saying the
machine was quiet through the hours he typed four thousand keys into it,
and consecutive hidden windows merge into one item. Four renderers ask:
the raw activity the digest role is handed
(`system_monitor.format_system_activity`, which also drops a hidden
process from the list of the busiest), her live status line and her window
trail (`sim/phone.py`), and the busiest-process line. **And the stored feed
is read through the blocklist as well as written through it**: the monitor
blanks a title when the window closes, so a title recorded before a pattern
was added is still on disk and used to be re-rendered whole
(`_shown_title`, and `Phone._sessions_from_feed`). The same
list reaches his browsing history, where `chrome_monitor.py` drops a visit
whose PAGE TITLE matches -- a Google search whose query was a path put the
project's name in a digest from a google.com address that no address
filter names. The address side is `sensors.chrome_junk_filters`, which
both browsers' readers apply to the URL of every visit
(`sensors.firefox_junk_filters` is added on top for Firefox): sign-in
pages, whose query strings carry live tokens; the machine's own addresses,
which is where her messenger and his other chatbot software sit; and the
sites this project is built and served through, because the assistant's
chat titles name the characters and the work on them. `vision.py` (Gemini on
Vertex, region `global`: `look([images],
instruction)`; her eyes for X images, photos he sends, scenery; the day's
call count against `vision.max_calls_per_day` is kept in the save, kv
`vision_calls` `{date: n}`, so a restart does not reset it, and every call
is counted, the machine's date standing in when a caller gives none. **One
caller is never refused by that ceiling**: a picture on a post she is about
to send another person, `look(reason="share")`, which is counted like every
other call, logs that it went past the day's number, and is capped by the
share pipeline's own `social.share_looks_per_day` -- she cannot hand him a
thing she has not seen, and the harvester had spent the day's allowance by
the time she scrolled). Config
for these is flat keys in `sensors` / `sensor_view` / `vision`. Every
browser this bot drives is headless -- X (`sensors.x_headless`), the
knowledge base (`recap.headless`), the MAL daemon (`cmd_daemon`, always);
the only windowed Chromes are the ones a person logs in through
(`x_login.cmd`, `mal_history.py login`). `/headless on|off` is the toggle.

**One store of what was fetched about the world** (spec: `docs/retrievals.md`; `machine/retrievals.py`,
`sensors.retrievals_db`, default `data/retrievals.db`) sits beside the image
tag store one file over and makes the same claim: a page about an episode of a
television programme, that page condensed by a role that names nobody, the
verdict between two candidate pages, the web search behind an arriving lookup
and a game's database card are the same whoever is looking, so they are fetched
once for the machine and both characters read them. A row is `(pool, key,
model)` -- the key names the THING and never the character, the model is who
wrote the text, so a re-digest by another model is a new row rather than a
silent overwrite. A fetch is CLAIMED before it starts (table `inflight`),
because both bots poll his media player and would otherwise fetch, digest and
judge the same episode inside the same minute: whoever gets there first
fetches, the other waits for the row and reads it, a claim older than
`sensors.retrievals_inflight_stale_seconds` is taken over because a bot is
stopped with `Stop-Process -Force`, and a fetch that found nothing marks the
claim failed so everybody waiting stops waiting NOW and goes and looks, rather
than waiting the timeout out for a row that is not coming. **The claim covers
the QUESTION, not one fetch of one address** (`Recap.synopsis`,
`Retrievals.claim` / `wait_for` / `finish` / `fail`): the candidate set comes
from a live web search per process, so three processes searching for one
episode get three different sets, and the search is what has to happen once.
The claim is taken before the search and held through the pages, the digests
and the judge; the answer and the release are one transaction, so a waiter
cannot see the claim gone with the row not yet there. Three characters once
resolved one episode inside twenty-three seconds, each ran her own search, and
the one that finished nine seconds too early to read the others' page was left
holding a record of that episode with nothing in it (HISTORY.md, one
reading-up per episode). Written the moment the answer
exists, never held. What each character MADE of a retrieval is in her own save.
**An episode whose record holds no synopsis and no raw page is read again**
(`WatchingHim.owed`, §12.12): as soon as the shared store holds a page for it,
which costs a lookup and no search, and otherwise after
`sensors.retrievals_retry_after_minutes` (30), at most
`sensors.retrievals_max_retries` (2) more times, with the count of readings-up
begun written on the record before each one so a search that keeps failing is
not run every poll for ever. `python tools/retrievals_test.py`, and `--store`
in smoke: three threads on one key run one search and all three hold the
result, a claimant that found nothing releases and the next one searches
without waiting out the timeout, and a stale claim is taken over.
history: archive §7, §5.60, §5.67.

---

## 12. Memory, the compile, and her outward things

### 12.1 `timeline.py`: the nightly compile

`compile_day` at `timeline.compile_at` (`App.maybe_compile`; `/compile
[date]` redoes a day) -- but **not while she is still in a conversation**.
The compile flushes a live exchange so the day's record holds it, and 23:55
was chosen when the group chat died at nine; with the chat now running to
02:20 the fixed hour was cutting off the late night the cast layer had just
been given permission to have. It holds while an exchange is live and until
the night's last light, the day boundary leaves a night that ran over
midnight alone, and the small hours close it instead (`compile_hold_for_chat`,
`compile_quiet_by_hm`). One `timeline` call over the day's scenes, events,
messages, digests, exchanges (`Exchange.compile_rows`) and diary ->
narrative, summary, facts about him (`user_facts`, with a weight), what
she herself will carry (`self_memories`, `self_memory.max_per_day`; and she
did not arrive at fifteen with nothing -- a seeding tool, since retired, wrote the
floor, 14 memories from `prompts/bible.md`, her canon dialogue and the sheets,
because the table began with the save and her whole life before it was one
short paragraph with HIM as the subject of every clause. **Both `ts`
and `last_seen` are the event**, unlike the cast facts, which were seeded at
`last_seen = now` on purpose: a fact about her mother's job is re-encountered
every time her mother goes to work, and a remembered afternoon is not. It fades
unless something brings it back, which is what `for_prompt(cue)` is for. So the
train up to Tokyo scores 4.58 and the friend who drifted 0.59, just above the
floor, nearly gone and recoverable on a cue.

**Both languages, and one tokeniser for them.** Six modules carried the same
regex -- Latin words plus a maximal run of kana and kanji -- which is right for
English and wrong for Japanese: a language without spaces makes such a run a
whole CLAUSE, so 「彼は生きていた。ただ朝で、浴衣の話しか返してこなかっただけ。」
tokenised to three tokens, one per clause, and 「浴衣のこと」 shared none of them
despite both being about the yukata. A Japanese memory was unrecallable in ANY
language, and the duplicate test on the same tokens could not see two Japanese
lines saying the same thing either. `sim/textutil.words` is the one tokeniser
now, used by `goals`, `ick`, `memory`, `recall` and `self_memory`: Latin words
at each caller's own threshold, CJK as character bigrams, which is the standard
answer for a language without spaces and without a morphological analyser.

**And the store is dual-keyed**: `alt` holds the same memory in the other
language, written by the `gloss` role, and every match -- the cue in
`for_prompt`, `search`, the duplicate test -- runs against both (`_keys`). So
an English cue reaches a memory she wrote in Japanese and the other way round.
The gloss checks itself: it must come back in the OTHER language and it must
not be Chinese, because one of the first sixty-nine returned
「彩的备用自动铅笔」 -- simplified, with Aya renamed -- which is the fault
`voicecheck`'s `simplified-chinese` rule has existed for since a simplified 绫
turned up in her own mouth. Two attempts, then the memory stays one-language
rather than carrying a wrong key. A one-time backfill, since retired, gave all 69 rows
already on file their second key, because a store
where only the new rows are dual-keyed would quietly favour whatever was
written most recently),
`self_claims` (what she told him about herself), `new_cast_facts` (the
`cast_facts` table), things she did for herself (`diet`), goals settled,
the spiral settled, foresight settled, commitments settled, the graph
updated, the cast lives written, habits learned, care and worldshare
recorded, the sentiments' daily moves. A failed parse marks the row and
is retried; a raw answer is never stored as a day. A narrative under
`timeline.narrative_min_chars` on a day with at least
`narrative_min_scenes` in it is asked again once with the span of the
record in front of it (`narrative_retries`): the prose can come back as
one short paragraph while every other field is full, and a thin day is
silent otherwise. **What is stored after a retry is a MERGE**
(`merge_retry`), because the retry names the narrative and the role answers
with the whole JSON as a fresh telling: the retried field comes from the
second answer, every other field from whichever answer has one, the first
preferred where both do, and the log names which fields came from where.
Taking the second answer whole cost the second character every fact about
him for a whole day (HISTORY.md has the date and the receipt). The retry message also repeats the line naming which
language its prose goes out in (`sim/lang.material_line`, and nothing for a
character with only one language): the system half carries it, but the
retry's own English paragraph is the last thing the model reads, and the
answer that lost the facts came back with an English summary on a character
who writes Japanese everywhere. `tools/timeline_test.py` holds both, with no
model call. `compile_week` on
Sunday (role `weekly`, kv `weekly_self`). Table `days`. Log `[timeline]`,
`[memory]`, `[self]`. `/day`, `/week`.

**The compile is shown what is already in all three stores.** The facts about
him and what she knows about the people around her have been handed to it for
a while; her own memories were the one store it wrote into blind, so a running
theme got a fresh row a night instead of reinforcing the row it repeats. It is
now handed the last fourteen things she is carrying as well
(`SelfMemory.recent_report`: the lived ones, in the language she reads, with
their weights and mention counts), under a heading saying they exist and that
a day which is one more day of the same thing says nothing new about it. The
date being compiled is excluded from that list, because the compile drops its
own memories of that date a moment later and would otherwise be told not to
write the rows it is about to lose. A memory that does repeat one she has
reinforces it (`SelfMemory.add` returns `reinforced`: `last_seen` bumped,
`mentions` raised, the higher weight kept) and the compile says so in the log;
it used to count the new ones only, so a reinforcement read as a memory thrown
away.

**The day's cards are written here too**, straight after the `days` row and
before anything else is settled: `episodes.write(date)` cuts the day into
conversations and pays one more call for their shapes and their exact lines
(§12.13), so the day the compile just told is reachable by the thread and by
the retrieval from the moment it exists. **A day compiled again replaces
itself rather than accumulating**: the `days` row and the cards are
rewritten, the memories this call wrote for that date are dropped and written
again (`SelfMemory.forget_day(date, "day")`; the settlers write their own
memories of the same date and are each guarded separately), what she told him
about herself keeps one set of rows per date, the things she did for herself
drop the date's rows first, a place counts one visit per date, an arc keeps
one note per date, the coherence seams drop the date's own flags, and the
social graph refuses a date it has already applied. Each of those pools
deduplicates on WORDING, so without the per-date replacement a second telling
wrote the same evening again in other words and got past the duplicate test:
a day compiled twice added two more memories and ten more claims of the same
day. What is still on wording alone is `cast_facts`, which gains a few rows on
a recompile.

**What she told him reaches the meters.** The new claims of a day go to
`primitives.disclosed`, the one event that closes the gap a diary opens; a
claim already on the record, or already counted for that same date, counts for
nothing, so a day on which she said nothing new about herself moves nothing.
Seen firing on the second character: three claims of one day took
`exposure_his` 58.6 to 59.7, with `predictability_his` and `threat` moving
beside it, every step logged with `cause: told`. The first character has no
primitives layer at all (`primitives.enabled` false), so for her this block
does nothing by design.

**The compile is one job under the in-flight flag** (§3): it writes a row to
kv `in_flight` when it starts and clears it when it returns, and a process
killed mid-compile leaves that row for the next one, which reruns the day
only if it still has no `days` row.
history: archive §5.7, §5.31.

### 12.2 `memory.py` `Memory`: how she forgets, and the context budget

**The whole of what she remembers and how it comes back is
`docs/memory.md`**, the spec of record: the five stores, the curve, the
moment as one cue, the embedding, and which retrieval lands where in her
prompt. This entry and §7.8, §12.3, §12.11 and §12.13 are its pieces.

Facts about him (table `user_facts`: weight, half-life by weight, score
fades; a near-duplicate reinforces, `memory.duplicate_jaccard`;
`facts_for_prompt(cue_text)` is what is above `fact_min_score` plus what
the moment just cued -- by a word of it or by meaning (§12.13: the same
vectors the record search uses, so a Japanese line reaches an English
fact), ranked by that and capped at `max_recalled`, and cueing bumps
`last_seen`. The cue decides WHICH facts come back and nothing else: a
recalled fact is still worth its half-life score, and an empty cue
retrieves nothing. The pool is `search_items`, one row list shared with
the record search, so the words and the cosine cannot disagree about
which row is which; a fact written by the compile is embedded by
`add_fact` as it is written, because the persona reads stored vectors
only). Facts about
people (`cast_facts`: `add_cast_fact`, `cast_facts_for(who, cue_text)`,
`who_key`, which resolves **through the roster** -- it used to fold
honorifics and lowercase and its own docstring said `mom` and `Yumi` were not
resolved, which was survivable while the record was English and became a
silent hole the moment the speakers were relabelled: every caller passes the
record name, so `cast_facts_for(古賀由美)` searched for 古賀由美 while the row
sat under `mom`, and on every cast turn since she could not reach one thing
she knew about her own mother, father or brother. A name the roster does not
know keeps the old normalisation, which is what it is for).

**And she did not arrive at fifteen knowing nothing.** The compile is asked
for `new_cast_facts` and was told "most days have none"; it obliged nine days
running, leaving 118 facts about him against three about her whole family and
none at all about the three girls she is in the group chat with every day. Two
halves to the repair: the compile is now handed `WHAT SHE ALREADY KNOWS ABOUT
THE PEOPLE AROUND HER` (`Memory.cast_facts_report`) the way it has always been
handed the facts about him, and told that a day teaching her nothing about
anybody is the exception; and a seeding tool, since retired, wrote the floor --
38 facts bounded by **what she could actually have observed**. Her family she
has had all her life, so those go deep but only as deep as a fifteen-year-old
looks: she knows her mother gave up the Kashii clinic for the transfer, not
the figure kept under the insurance wall, and she does not know her father is
no longer a section chief, because the sheet says he has not said so. Her
friends she met in **April**, when the transfer put her in a Tokyo high school
knowing nobody -- five months, so what she has of them is which station, which
club, who has a sister, and what happened in the first week, unevenly: seven
for Aya (closeness 74), six for Rena (42), five for Hinako (34). `ts` is when
she plausibly learned it and `last_seen` is now, which is the honest shape --
a thing you still know is a thing you keep meeting -- so the fade leaves the
structural facts standing for years and lets the small ones go. `cast_lines` renders the people
around her for her prompt (recent plain, older dated, stale gone). The
context budget (the spec of the whole context system is
`docs/context.md`): ONE, `context.target_tokens`. Everything rides whole
except the thread, whose verbatim span is seven days and shrinks a day at
a time toward `thread.verbatim_min_hours` only when the verbatim days plus
the cards behind them do not fit what is left of the target after the rest
of the prompt (§5, `sim/thread.py _window`, reading kv `context_last`), so
`fit(sections, history, situation)` measures and trims nothing. It used to pop the oldest turn one at a time
and then shorten the diary, the notes index and the facts to a fixed count,
which rewrote the head of the thread on every call: the one edit the
provider's cache charges for everything behind; then three sub-budgets and
three gates sized the three moving parts, and those went too (history: the
one-budget entry). A total still over the target is the parts that ride
whole outgrowing it or the window's floor alone being over it, and the log
says so rather than hiding it. `measure` logs the four parts -- the system
half, the history, what she carries, the situation -- against the target;
`ratio` is calibrated from the model's own token count (kv `context_ratio`,
`context_last`). `context.max_tokens` is the window, not an output cap.
`/memory`, `/remember`, `/context`. history: archive §5.24, §5.25, §5.89.

### 12.3 `recall.py` `Recall` and `diary.py` `Diary`

The search and the cue in full are `docs/memory.md` §3 and §6.

Recall searches her cards, the compiled days, the machinery's own record of
her day (`events`), what she knows about him and
her own memories, by words and by meaning (§12.13). The cue is the moment,
from one owner (`recall.moment_cue`): his message, her own last line, and
the scene she is in. The same function cues the persona's own recall of a
faded fact, so the two ask the same question.

**The events are a source because some things are in no other store.** The
only row in the first character's save that held the title of an anime she had
an opinion about was an event, and when he asked about it sixteen days later
the search read past it. They are filtered by `recall.events_min_salience` (2),
bounded by `events_scan` (which also bounds their vector pool), and faded from
`events_weight` on her own life's half-lives rather than on the shorter scale a
fact about somebody else fades on (`Recall.events_wanted` owns both numbers;
either at 0 takes the pool out).

**A cue in one script reaches a record written in the other**
(`recall.cross_script`): the titles the cue names are looked up in the two
local stores that hold both spellings of a work -- a thing she knows by name,
and his own list -- and, where neither holds the pair, the romaji is
transliterated to kana (`recall.kana_forms`, strict, both scripts). "yani neko"
reaches ヤニねこ on ヤニ and ねこ. A description crosses to nothing and is said to:
no store here maps "the smoking cat anime" to a Japanese title.

**A memory the store cannot ground is not written.** The role is handed every
excerpt with a number and must cite the one its memory comes from; code checks
the citation against the excerpts it was actually shown, and a memory that says
one of them SAID something about a distinctive word of his message that appears
in no excerpt is dropped and logged (`[recall] not grounded: ...`,
`recall.require_grounding`, `subject_common_share`). The fault: the role wrote
that he had promised weeks earlier to watch an anime with her, on a
cue whose subject is nowhere in her record, and it was stored at clarity hazy
where a later cue could pull it. Each kept row carries `cited`. Measured over
the fifty-two recalls in her save, eight would not have been written and six of
those eight say again as memory what he had typed that minute
(`docs/memory.md` §6).

**Where the search starts is the thread's own verbatim cut** (kv
`thread_window`, `Recall._verbatim_from`), not a boundary of its own: the
search is for what is not already in front of her word for word, and the
thread's span shrinks toward `thread.verbatim_min_hours` under the budget. It
covers the messages, the compiled days, her talks and her cards, and the
meaning pass over the same pools, so a day inside the span cannot come back as
its narrative or as one of its cards while every message of it is on the
screen; an empty window falls back to `thread.verbatim_hours` and a stale one
is clamped to it. The delivery section's own history-age setting, a second 168 hours
that agreed with the thread's by coincidence and covered the messages only,
had this module as its one reader and is gone.

`Recall.start(text)` on his message: a search over the days, her own
memories and her talks (`Exchange.search_rows`), then the `recall` role
writes what she remembered on cue (`recall.max_excerpts`, `wait_seconds`;
kv `recalls`); `take()` once for the reply. `Diary.may_write(scene)` in a
quiet moment (role `diary`; **one entry an EVENING, not one a calendar
day** -- the window wraps midnight (20:30-01:30) and everything inside it
belongs to the date it opened on (`Diary.date_for_now`), so an entry
written at 00:27 is about the evening before and is handed that evening's
events plus whatever has happened since midnight; the `unsaid` outlet; kv
`diary`). **What opens the gate depends on what she has got.** For a
character with a chat with him it is pressure: `unsaid` past `min_unsaid`, or
shame or the flat kind of sadness past `min_carried`. Three of the four
things that fill `unsaid` are the relationship -- holding something back from
him, a thing about him she cannot raise, being left on read -- so a character
who has no chat with him cannot reach it: the fourth character's ran between
15 and 24 against a gate of 50 across her whole record, with the window open
both evenings and eight to sixteen things happening in each, and she had never
written one. For her the gate is her own day instead: how many things at or
above `state.salient_from` her record holds for the evening she would be
writing about, against `diary.min_day_events`, with `diary.day_weight` per
thing past it in the odds. The refusal is logged once an evening now, which is
what was missing when nobody could say why she never wrote. **And the prompt
forks on the same answer**: the two sections about him -- what they said today
and what she last saw of his machine -- are built only for a character who has
a chat and a window on him, and the role file's own sentences about him sit
behind `[[?with_him]]`, so a character who exists for somebody else's circle
does not get a man in the one place that is supposed to be hers. Her hand is Japanese (`ja`) and this is the one place a gloss
survives (`text`): the turns lost theirs, but the diary's English is what
the compile and the weekly read, never the thing itself; `prompt_text` for her system prompt.
`/recalls`, `/diary [write]`. history: archive §5.14, §5.30.

### 12.4 `context.py` `ContextView`: reading her prompt back

`snapshot(fit)`, `overview`, `show(name)`, `find(needle)` (why does she
keep saying that: usually one line in one section), `dump`, and the
corrections: `delete` / `replace` / `add` on the stored parts, `message_set`
/ `message_del` on her history (`store.update_message`). Read-only
sections are named. `/context [full|find <t>|msg|<section>|add|set|del]`. Editable sections are the stored kv lists (`claims`, `diet`, `reflect`, `diary`, `weekly`, `notes`) plus `facts`, `backstory` and `cast`.
history: archive §5.40.

### 12.5 `reconcile.py` `Reconcile`: prose against the machine

For every action she can take (a message, a spend, a note read, a post)
an `Action` holds the typed field that legitimately carries it, a reader
that answers whether it really happened in the window, and the policy
when prose claims it and neither is true; `check(app, scene, since_ts)`
runs on every tick that produced prose (role `reconcile`), corrects the
fiction down to what the machine did or hands the action to the channel
that can perform it, and logs every violation (kv `reconcile_log`). The
rule underneath: a record of an action never exists without the action.
Beside it and flag-only, `claims_own_photo` / `flag_own_photo`: a
deterministic test in both languages for a picture of her own making
FOR HIM, or for him having seen one, wired into the director's scene
events and inner line, `outlook.anticipation`, `outlook.morning`,
`reflect.run` and every bubble in `persona.generate`. It logs
`[reconcile] FLAG: a photo of her own making, for him (<where>)` and
keeps a row in kv `flags`; it never rewrites. She has nothing of her own
to give him -- scenery and `[share: ID]` are the machine's, pictures to
her own people are real -- and the fact itself lives in `prompts/bible.md`
under "Him", which every interior role appends.
history: archive §5.71; 2026-08-31 23:45.

### 12.6 `scenery.py` `Scenery`: borrowed eyes

**Collecting new photographs is off** (his call: "stop collection of
scenery data. only keep the x scroll"). `scenery.harvest` is
false, so `Scenery.due` never comes due and no session opens a browser,
runs a discovery search, judges an account or pays Gemini to describe an
image; the only look session left on X is her own scroll
(`tomoe/social.py`). Sending is untouched -- 641 usable photographs are
already on file against a cap of one a day -- so `offer` / `pick` /
`adopt` and the lore run exactly as before, and `/scenery harvest` is the
manual door that still opens a session. What is written below about
searching, judging and describing is what a session does when he starts
one, not what happens on a clock.

Machinery, not her: a harvester on its own clock and session discovers
real photographs of ordinary places around Tokyo (`scenery_judge`:
`follow` is somebody's own snapshots, `place` is a ward or park or shop
feed whose pictures are still real pictures of real places, and both go
on the watchlist -- the bar is the photographs, not the person, because he
cannot tell a Saitama platform from a Nerima one and what has to be right
is the light, the weather and the hour). **The searches are aimed**: the
kinds her own scenes and the next `route_days` of plan put her in, minus
what is on file for that kind at that hour, ranked by `missing` and
rotated across the top `gap_spread` (`demand` / `coverage` / `gaps` /
`next_query`, `kind_queries`, `/scenery gaps`) -- and **a named event she
is going to comes before all of it**, the one perishable thing in the
feature, because people post a festival while
it is on and not afterwards: an `event_stances` row of going or dragged is
joined to `data/local_events.json` by name, or through the place graph when
the stance is written as the promise ("wear the yukata to the Pixar
event"), and two things on at one venue are refused rather than guessed
between -- unless HER OWN RECORD names one of them (`_named_by_her`: her
commitments, her event stances and her recent gists against the feed's own
English note, which is the bridge between 「ピクサーの世界展」 and "the Pixar
event"). Koto had the Pixar exhibition and a Doraemon one running at once and
the refusal was throwing away the promise she had made by name. Those images are tagged with the event and go out at it and
nowhere else, and there the place-kind gate does not apply. It describes the images
with Gemini into fixed JSON (place kind, hour, season,
weather, names, `region`, `portrait`, `venue`, plausibility), keeps them
in the `scenery` table with attribution, and when her scene fits one --
place, season, hour, weather, `send_kinds` (a `food` row only inside a
meal window, `food_hours`), no name that contradicts the lore -- the image
goes out as a photo she just took before her bubbles, its caption is
recorded on her own bubble (`[photo you sent: ...]`, so a later reply does
not misremember it), and its details are adopted as lore. Never a selfie
or a portrait; never her feed, seen list or follows; never reposted.
**Where she is comes from the place graph, not from the words**: the node
`embodied/situation.py` walked her to carries a `kind` in `data/places.json`
and is the authority, the leg of a live journey is `train` or `street`,
and `place_map` (both languages, longest keyword first, ASCII on word
boundaries) is the fallback -- "homework with Aya" used to resolve to
`home`. A photo that contradicts what she has said to him in the last
`said_minutes` does not go. An image whose own signs place it outdoors outside
`regions_ok` is never usable (Kyoto and a German platform were both on
file); an interior anywhere in Japan is (`region_ok`,
`scenery.indoor_any_japan`), because a cafe table gives nothing away, and the signs that name a place are held to `local_names` whichever
field the vision filed them in (`local_names` drawn wide: her line and
the wards around her). The review is `/scenery gaps` and the ops view's
`scenery` section: kept and refused as thumbnails, newest first, each with
its reason. `/scenery [now|lore|harvest|gaps|rejudge]`.
**spec: `docs/scenery.md`.**
history: archive §5.95.

### 12.7 `reactions.py` `Reactions`: her face in the app

Frames of her from the anime (`tools/reactions.py`: detect, identify by
CCIP against ~20 crops, frame, dedupe, tag, bucket by expression against
her own baseline face, a second pass for a sharper same-moment frame,
his review of `merged/<bucket>/` as the labels) read by `sim/reactions.py`:
one face each time her mood valence crosses a band, the face that is up
changes, or surprise crosses; shown as the header avatar; `backfill` places
past crossings.

**And only while he is there** (`reactions.active_minutes`): her mood wanders
all day and her face was following it into an empty room. Nothing is recorded
while he is away, so the first tick after he comes back moves it once, to now.
A sticker that does reach his chat says whose it is -- `auto` rides to the hub
row and the app draws an automatic one dimmed and captioned *her face changed*.

**It reaches his chat as a marked sticker** (`reactions.sticker`). Without
`active_minutes` that is a night of wordless pictures while he sleeps -- her
mood wandering through its bands, narrated at him -- and the window and the
mark are the answer, not a reason to stop sending: he wants to see her face
change while he is there.

**And one she puts down herself** (`chosen`). She has no kaomoji at all any
more (§5): what she has instead is a sticker, her own face, written as
`[sticker: FEELING]` on its own line or on the end of a bubble, naming one of
the eight buckets and never a file -- she could not know an id, and which
picture carries a feeling for her is the store's business. `Persona._take_sticker`
lifts it out of the text (it is not a bubble) and `App.send_pending_sticker`
sends it after the words, the way a LINE sticker lands at the end of a burst.

Putting one down adds **+1 to that image's weight for that feeling** (kv
`sticker_weight`), and `pick(..., learned=True)` draws against those weights,
so the picture she reaches for when she is tired slowly becomes HER tired face
rather than a random frame of one. It is not a favourite and it is not
something he places (his rule): it is how she says a mood. The
automatic band reaction stays unweighted -- 40 uses of `tired` narrow her to 17
of 48 images with clear repeats, while the automatic draw stays at 22 distinct
in 30.

Character-agnostic; the recipe
is the tool's docstring. `/reaction`. **spec: `docs/reactions.md`.**
history: archive §5.96, §5.97; Part C 2026-08-27.

### 12.8 `ops.py` `Ops`: the operator's view

One read-only JSON payload for the app's ops view (gauges, his meters,
her looks at the app, the snoops, X -- with the actions themselves, her
reason for each and whether it was done, what the drift unfollowed and
drops next -- scenery, her shows with what she thought when she watched, each thought
marked when a fetched recap grounded it, and what she would put on next
(`watch`), what she is carrying -- open promises, the questions she is
turning over, what she woke wanting, her goals (`mind`) -- what the
readers say: the day's seams, the sources she is handed and never hears,
the flags (`checks`; it still renders a pro/flash pair count from a store
nothing writes any more, the judge-role A/B having been read and removed),
model calls by role, the world), posted with the state sync; commands from that view come back
through `App.run_command` and their output goes to the hub's ops log,
never her chat. `/ops`. history: archive §5.83.

### 12.9 The chat itself

His message: `poll_inbound` -> `store.add_message` -> `maybe_reply`
(marks read before generating; recall and lookup start on threads; the
withholding may decide not to answer; the wonder judges an answer; the
rupture may settle; expectations hear a promise; rhythm hears when he is
around) -> `Persona.generate` -> `Delivery` -> `foresee_after`,
**One truth about the day** (`sim/ledger.py` `Ledger`, no LLM): the block
she is in and who is actually with her (the schedule as corrected by the
plan's `absent`), who is not around and why, what the plan `settled`, what
she is wearing (`/ledger wear ...` pins it, kv `ledger_wearing`), her money
her open promises, and **what the money record says she bought** --
`Money.bought_line`, `bought nothing today (... a purchase the plan or a
scene mentions never happened)` -- for every reader, because a block's
activity is the plan's wording and a friend's turn once read a planned
paperback as bought. `text(for_whom=...)` goes to the director, both
sides of every exchange (a friend's side sees no balance and no promises)
and her own reply; `day_text` to the compile, where it outranks a scene;
`is_absent` settles a promise `moot`; `audit()` is `/absurd LEDGER`.
**A plan for a public event is checked against the calendar** and refused
where it is read, so the director, both exchange sides, her reply, the
compile and her own account cannot hold different versions of whether a
thing is happening. A line bound to a calendar entry
(`[calendar: <date> <title>]`, written by the cast planner) is judged on the
entry alone: `event_ok` asks `Calendar.entry`, `outing_unbacked` refuses the
line when the calendar has nothing of that name on that date, and
`promise_unbacked` does the same for a promise row carrying an `event`, which
settles `moot` rather than broken. `world.outing_words` stays as the second
net for free text nobody bound to anything, and is blanked for a character
with no world. `spoken()` writes the binding out as prose for a prompt asked
for words. This is where a festival she had already been to stopped being
tomorrow: it was carried forward for six days, latterly as "meet dad at the
station tomorrow", and sixteen promises came due against it and were all
recorded missed.
`Commitments.from_chat`, `maybe_afterthought` (`afterthought.*`: the bit
she thinks of straight after; a read counts as "read and said nothing"
only after `read_silence_minutes`, and `Delivery` re-checks for his reply
after typing each bubble, not only before). Her own opener: the director tick ->
`maybe_impulse` -> `Intent.decide` -> the persona, or a discharge / a
photo forcing it. Voice: every reply speaks (`ensure_voice`,
`voice_gate`). `App.recover_lost_reply` re-queues a message whose reply
was generated but never sent. history: archive §3, §5.43, §5.57.

### 12.10 `coherence.py` `Coherence`: the day read as one story

`tools/absurd.py` measures the parts; nothing read the record as one story,
and the seams that break the illusion sit between the parts -- she tells him
she cannot go to her brother's match, tells her brother she is coming and in
the same exchange apologises for having slept through it; thanks a friend for
a notebook no exchange mentions; puts the same three titles to him twice,
minutes apart. Each is structurally valid and visible to anybody who reads
the day, and the only reader was him.

Once a day at the compile (`review`, role `coherence`, `prompts/coherence.txt`),
the day's record -- the ledger, the scenes, the events, his chat, every
exchange with her own people, and THE COMPILED DAY (narrative, summary,
the facts about him it wrote, the memories it kept; the review runs after
`compile_day`) -- is read as one story and the seams named:
a CONTRADICTION (two incompatible things she said, or a thing the ledger or
a scene refutes), an INVENTED thing (an object, event or person with no
source anywhere in the record), a REPEAT (the same thing said again as new),
a COMPILE seam (a claim in the compiled day the record does not support --
the one that outlives the day); the resident's own prompt adds two more,
a KNEW seam (a thing she says about him that nothing in the record showed
her, which for a character whose only source is his machine is the one that
matters) and a SHARED seam (her own past talked about as though he had been
there),
each with a severity (3: he would notice in his chat; 2: anyone reading the
day; 1: a careful reader) and the line of the record it clashes with. Code
keeps them (kv `coherence_flags`, `coherence.keep`, at most
`coherence.max_seams` a reading, one row per distinct kind and sentence),
logs each as `[coherence] FLAG`, and
changes nothing: the record is what happened, and a seam is a signal about
a prompt or a mechanism, never a reason to rewrite her. A lie she tells on
purpose, a plan that fell through with its reason on the record, a thing
said in one room and not the other are not seams. `/coherence [date|now]`
reads a day by hand, `/coherence [days]` shows the last readings, and
`/absurd` SEAMS reads the last `coherence.absurd_days` back: ODD on a seam
at severity 2, ABSURD on five.

**The number of seams the code keeps is told to the model.** The prompt asks
for a list with no end to it and `review` throws away everything past
`coherence.max_seams`, so the reader was being invited to enumerate an
answer nobody would read; on a day whose findings were near-copies of each
other it enumerated 31 of them, and twice it stopped enumerating and simply
wrote the same seam again until the host's output ceiling. `review` now
appends the cap and "never the same seam twice" to the system prompt, which
is the same bytes every night and stays cacheable. history: §12.10.


### 12.11 `lore.py` `Lore`: what she happens to know

One of the stores in `docs/memory.md`, and the one retrieved by
hand-written phrases rather than by score.

The persona dataset (§19) is 1,664 claims over 346 records and nothing read
it, so a character could be told the name of her own radio programme and
answer as though she had been handed recordings of her voice. This retrieves a
few lines of it into the `lore` bucket of the situation block.

**The split is the design, and it comes from `docs/yukarin-lorebook.md` §3.2.**
What is true of her every minute is NOT retrieved: her register, her sentence
endings, her mechanisms, the people in the booth. That belongs in the bible,
where it is always true, and `lore.standing_kinds` keeps those kinds out. This
is for the occasional -- the shoes somebody took by mistake, the ten-year-old
tin of crab, the flat she used to check the listing for -- which is worth
having on the turn it comes up and is noise on every other.

So the module is made of two refusals. It retrieves **nothing at all** unless
the conversation reaches for something (`lore.min_score`), because a bucket
that always fires is a character who always has a fact to tell you; and a
record it has offered is not offered again off her own words, because the
failure mode of every lorebook is an anecdote calcifying into a catchphrase
inside a week. Read across thirteen probe turns it fires on seven and is silent
on every conversational filler. The lines ride under a header that says plainly
they are memory and not a brief -- *not a list to get through and not a subject
to raise; if it does not come out of you naturally, leave it alone*.

**Who said the naming word decides whether an already-told record comes back.**
The cue is the last `lore.cue_exchanges` exchanges rather than his newest
message, because a subject arrives over several turns, and her own words count
as a naming: she is often the one who raised the thing. But she is also the one
who just told it, and her telling stays in that window for the next few turns,
so an anecdote she has given him names its own record again on the following
call and the one after. The two sides are therefore kept apart. A record HE
names is reachable however often he names it -- `lore.suppress_days` is 0 and
that is his decision, because a person asked twice about her own job answers
twice. A record only HER OWN words name is held for `lore.own_words_days` once
she has been offered it.

**A record is found by name, not by resemblance.** Every record carries a short
list of phrases somebody would actually type when they mean it
(`characters/yukari/triggers.json`), and those phrases decide the match and
nothing else does. Comparing his message against a record's own text was tried
at length and cannot be made to work: conversational speech is mostly grammar,
and weighting by rarity makes it worse rather than better here, because every
record is about the same person, so her subject words score low and the
character runs that span a question's grammar score high. Four faults were
found only by dumping what would be injected and reading it, and each is a rule
now:

- **Only a gated claim is rendered.** A record's `statement` is its first
  bullet and may be one the era gate held; rendering it printed sequels running
  to 2017-18 at a character pinned to 2003.
- **Which text is the fact depends on the source.** A tape record keeps the
  reading in `statement` and its claims are the verbatim cues that evidence it,
  cut mid-phrase; a lorebook record is the reverse. Backwards, and she was
  reminded of a truncated fragment of her own speech.
- **A tape record matches on its Japanese cues and renders its statement**,
  because 225 of 346 statements were English and matching is on shared
  characters, so half the dataset was unreachable from a message in Japanese.
  (Those statements have since been rewritten in Japanese; the rule stands.)
- **Duplicates are dropped by text**, because 53 lorebook bullets are copied
  onto the tape record they were judged the same fact as.

Two things were tried and are wrong, recorded so they are not re-added.
**Cutting high-frequency grams** deleted 黒うさぎ, 矢野 and 弟 -- every record here
is about one person, so her core nouns are the most frequent and the most
informative at once. **Requiring the heaviest matched gram to be a large share
of the match** does the opposite of what it looks like: a record that really
answers a question shares a dozen grams and spreads the weight, while a record
sharing one weak fragment scores 1.0 by definition; it killed every good match
and kept the junk. The remaining weakness -- a short question with one content
word -- is a known limit rather than something to paper over.

**A blank path is a character with no record; a wrong path stops the boot.**
`lore.enabled` with no `lore.file` at all builds, writes one line --
`[lore] no record for her; nothing to be reminded of` -- and every retrieval
returns nothing, because a config that names none of a person's files is a
state the project produces on purpose (`Config.WORLD_KEYS`, and a character
sheet answering "no"). A `lore.file` that NAMES a file which is not on disk,
or one that loads no claim any phrase can reach, is a wrong path rather than
an absent one and `Lore.__init__` refuses to start: her own past is what she
is made of and running without it is running as somebody else. Both halves are
checked by `tools/blank_paths.py`, in smoke. A sheet carrying a `lore` block
switches the retrieval on whether or not the block names a file, so a lost
path is answered by that boot line instead of by silence -- silence is the
shape the fault had when a regenerated config dropped the paths.

**The era gate is OFF, and that is his call** -- "just turn the era gate off,
it's pointless". Nothing is withheld and every record is reachable. What
follows is the mechanism, which is kept, works, and idles while the flag is
false; it is one line if the withholding is ever wanted back, and turning it on
can only take material AWAY from her, never add any.

178 lorebook claims are marked as coming from after the corpus ends
(`gate.hold`, judged one at a time in `yukarin/audit/lore_gate.py`) and
`lore.era_gate` decides whether that costs them. **The mark judges on when the
thing described BEGAN**, which it did not always: it had been put on the text
naming a later year, so the record of her own radio programme says 「2003年4月5日〜2016年3月
20日」 in one sentence and was shut whole, and so were her debut single, Kanon,
Galaxy Angel, Tenten, D.C., 舞-HiME, Nanoha's first series and the agency she is
at. Thirteen claims carry `gate.until_then`, the part of the claim that had
already happened -- the claim stays held and that part is what she may
volunteer. The other 165 would be genuinely her future and would stay shut
until he watches the work (§12.12). Measured both ways: off, 255 records
reachable by name and 751 claim texts; on, 223 records and 586 texts, so the
gate costs 32 records and 165 lines and cuts 13 back. None of that is in force
while the flag is false. `yukarin/audit/lore_gate_apply.py` writes a
re-judgement onto the records without a full rebuild. history: §19.

### 12.12 `watching_him.py` `WatchingHim`: what he is watching, and her own part in it

**An episode she was told about and never told what is in gets read again**
(`owed`, called on the watching tick when the poll found nothing new). The
episode is marked seen before the fetch runs, and the one repair path there
was needed a stored raw page to make a digest from, which a search that found
nothing does not leave -- so a reading-up that lost the race to another
character's search left a record saying he watched it and nothing else, for
good. A record with no digest, no raw page and no mark saying it was recorded
without one on purpose is owed a retry: at once when the machine's shared store
has a page for it (`sensors.retrievals_retry_after_minutes` /
`retrievals_max_retries`, §11.6), and it does not move the thing in the room --
the moment it reached her, whether it was a stub and how many readings-up it has
had ride across with it, and `watching_last` is only rewritten when it is that
same episode.

Her anime knowledge had every piece except the one that joined them. His list
is mirrored locally by the daemon (700 shows, 3,161 episodes, cast with
Japanese voice actors for 479 of them), a real Japanese あらすじ can be fetched
for any (show, episode) and cached (§5 `recap.py`), and she has a record of her
own career (§12.11). Nothing connected the three: he could play an episode and
she learned only that a count on a website went up, because the synopsis
fetcher was reachable **only** from him naming the show in chat.

It notices an episode two ways and takes whichever comes first. The player's
own history is the moment he starts and needs a filename parsed and resolved
against his list -- 91% of his library resolves, and the rest is dropped
silently, which is right, because the same folder holds her radio recordings,
music videos and a file called `input.webm`. The list is minutes later but
carries the show's id rather than a guess. **The cursor starts at now**: with
an empty cursor the list query matches all 3,161 rows and the oldest wins the
sort, so her first act would have been to read up on something he watched
years ago as though he had just put it on.

**Which work it is, is decided from facts the machine holds** (spec
`docs/resolver.md`). The whole path is read, not the basename: a folder of
`OVA` / `OAD` / `ONA` / `SP` / `Specials` / `Season 0` marks the file as a
special and `Season N` gives the season, season zero being the specials season
in the convention his library uses, and `parse_file` declines both so the
`parse_special` -> `resolve_special` route that exists for exactly that case
gets its turn. `AnimeKB.resolve_candidates` then RANKS every entry his list
holds under that name -- the title as written first, so `K-On!!` is not
`K-On!`; then the title with its punctuation out; then a distinctive phrase
inside a longer title, closest length first -- drops any candidate whose
episode count is below the episode asked for, and answers NOTHING when the top
two tie. A play resolved from the filename alone waits
`watching.confirm_minutes` for his list to name the id, and when the id
arrives and differs the id wins with the log naming both. Before this,
`Example Show - S00E01 - OVA.mkv` answered "episode 1 of Example Show", which
resolved to the 26-episode television run he had finished three days earlier;
eighteen of his 702 titles resolved to a sibling; and three of the 26 plays in
one week asked for an episode the chosen work does not have. One `[resolver]`
line per decision names the candidates, the choice, what was dropped and
whether code or a model chose.

Then it asks whether she is in it, which for the second character is not a
rare case -- **72 of the shows on his list have her in the cast, and one of the
thirteen he is part-way through has her in the lead**. `watching.her_seiyuu_name`
is what decides whether that question can be asked at all; blank, as it is for
a character who has never been in anything, and the whole self-recognition
half of the module is inert.

**And when she is in it, the part of her own record that was held back opens.**
Her record is pinned to early 2003 and 178 claims about her later career are
withheld (§19, the era gate), because a character who volunteers what she will
do in 2011 is not a character. Him watching it is what releases it, and only
the part he touched: Higurashi opens Furude Rika and nothing else, Nanoha opens
Nanoha and the note about what it did to her career, and the concerts, the
singles and the roles in shows he has never opened stay shut. Her future
arrives through him, one work at a time, rather than on a date. 19 records
carrying 68 of the 178 claims are reachable this way from his list as it
stands; the other 34 records are songs, concerts and roles in shows he does not
have.

**The match is deliberately strict**, because the two failure directions are
not equal. A record that fails to open is a thing she does not bring up; a
record that opens wrongly is her claiming a part she never played. Every word
of the record's title must appear in the show and character, or the record must
share a word of five characters or more with the show's own title -- the second
is what lets a note *about* a role come with the role, and the length floor is
what stops it firing on a surname two shows share. On a looser rule, him
watching Kashimashi opened her record for a different Kurusu from a different
show four years later. `Rino Randou` is a known miss in the other direction,
romanised two ways.

**It reads up on the newest unseen episode first, and no longer loses the
rest.** Taking the oldest meant that on an evening of six episodes she read up
on the one he watched three hours ago while he was finishing the sixth, and
then had nothing to say about the one he had actually just seen. But the poll
also moved both cursors past everything else it had found, so a session his
list logs as several rows at one timestamp -- six episodes of one work at one
minute, four at another, three at a third -- lost every row but the newest,
and those plays were never mentioned to her at all. What the poll cannot take
up now goes to kv `watching_queue` and is read up one per poll, so the
summaries still arrive one at a time rather than six at once. Two numbers
bound it: `watching.max_fetches_per_day` is how many episodes are read up in a
day, and past it the rest of the batch is recorded as watched with **no**
synopsis (kv `watching_recent`, `stub`), so the range she is told about still
covers them and no model call is spent; `watching.queue_max` bounds the queue.

**The record of a play keeps the file he played.** The path was used during
the fetch and thrown away with it, so a repair pass -- an episode read up again
because its account came out thin -- reached the transcriber with nothing and
logged *there is no file of his to listen to* about a file still on the disk,
and nothing he had already watched could ever become transcript-anchored. The
row carries the path and the unpaused seconds now, from the moment the open is
noticed through the hold to the record (kv `watching_recent`, `watching_held`),
`WatchingHim.owed` hands both back when the file is still there, and one boot
step recovers them for the rows written before by matching the row's own stamp
against the player's history, exactly and then inside a minute, with the
filename's episode number as the check (kv `watching_path_backfill`).

**Where an episode's own dialogue came from, readably.** It was in SQL only --
one row per (show, episode) in each save's `transcripts` table -- and the
reasons were scattered across a thousand session logs, so the answer to "where
did that transcript come from" had nowhere to be read. `reports/transcripts.md`
is the machine's, append-only, one line per attempt that resolved: when, the
show and episode, where the file came from (beside his video, the clone of the
archive on this machine, the archive over the network, or the transcriber
here), the lines, how far into the episode the last line runs, the GPU minutes
a transcription cost, the file itself, and which process recorded it first.
Each save catches up its own rows into it once at construction, because the
file did not exist while every transcript so far was made, and a line is
written once per show, episode and file, so three writers make one record. The
episode index carries an `anchor` column beside the completeness word --
`subtitle (broadcast)`, `subtitle (fan)`, `subtitle (whisper)` or `web only`,
with the file named on the episode's own page -- because how complete an
account came out and whether the episode's own dialogue is behind it are
different questions and only the first was answered.
Where the cap bites, what is kept is the lowest-numbered episode of each work,
because a run is followed from where he started. Only his list is queued: a
run in the player arrives one open per poll -- he is inside each episode for
twenty minutes and the poll runs every four -- so each is noticed on its own.
The two routes are sorted by a real time now (`_when_ts`), not by their stamps
as text, which put every list row ahead of every player row because "1788..."
sorts under "2026..."; a list row for the same watch still wins, and should.

**What she is shown is one line per WORK, over everything since her last
look** (`grouped_lines`). Her line used to be the newest episode and nothing
else, so a day of three works came out as the last of them: the line for an
OVA he played in the afternoon was replaced by the line for the work he put on
that evening, two minutes and eleven seconds later in the same run of the bot,
and she had never said anything about the first. The newest work keeps the whole shape it
always had, including its digest whole -- it is the one he has just come out
of -- and where he did not stop at one, its opener names the range (*episodes
8 to 13*) and the episodes before it become one clause each after it, in
order, an arc rather than six synopses. Every other work is one line: what it
was, the episode or the range, when he played it **on her clock in words**
(*yesterday, in the afternoon*; `played_words` over `world/clock.py`'s part of
the day, never a count of hours, because the block is rebuilt on every reply
and a number that ticks would cost the cache its bytes), and one clause of
what happened. `watching.recent_works` caps the works and
`watching.recent_max_chars` caps what the grouping adds to the line she
already had, oldest first, with a line saying how many were left out. **One
work with one episode renders exactly the line it always did.** One play filed
under two ids -- the filename's, then his list's correction, both in the
record -- is one row, not two works (`_one_play_once`): two entries of his list
share the Japanese title エグザンプル.

**Two windows, and they are different rules.** `watching.fresh_hours` is how
long an episode stays the thing in the room, counted from when it reached her,
and it is what the grouped block covers: one look marks every unseen episode
with the same moment (`note_seen` marks all of them, not only the newest), so
what arrived together stays together and leaves together, and that is what
makes "everything since her last look" a set. `watching.discover_hours` is the
age past which an unseen play is never marked at all -- what she goes and
fetches is what he has been doing lately, not a transcript of the week.

**And a third thing, which is not a window.** Between the block ageing out
and the end-of-day compile turning the watch into a lasting fact about him
there were hours where she had been told and had nothing left to say it
with, and she agreed with him that he hardly watches anything twelve hours
after being shown him playing an episode. `provisional_facts` returns
`(what he watched, one line about it)` for every episode she has been shown
whose day has no compiled record yet -- today and yesterday on her clock
only, capped at `recent_works` -- and `Persona._system` puts the ones no
fact she already holds names into the section of facts about him. Nothing
is written to her record: the moment that day is compiled the lines stop
being produced and what stays is whatever the compile kept.

Each line also carries **where he is in the series** -- his own list, with the
episode in front of him preferred to the number he has got round to ticking,
because he plays ahead of what he marks. "Episode 5" alone cannot tell the
difference between trying a series out, being deep in it, and finishing it,
and those are three different conversations.

**Where he is inside the episode comes from inside the player.** The obvious
answer -- how long since the file opened -- is wrong the moment he pauses, and
pausing is the state most worth knowing about. So mpv is asked:
`tools/mpv/scail_logger.lua` (installed at `%APPDATA%/mpv/scripts/`, and
already the script that writes the history line and the play line) also writes
its own `time-pos`, `duration` and `pause` to a small state file every ten
seconds and immediately whenever he pauses, with the unpaused seconds so far
and the epoch the file opened at beside them, and clears it when the file ends
or the player quits. A paused file simply stops moving and says so. Anything not refreshed
inside `watching.now_stale_seconds` is nobody watching, which is what covers
the player being killed rather than closed, since that writes no ending. She
gets *he is watching it right now, 8 minutes in, 34% through, about 15 minutes
left -- he is in the middle of it, he is not sitting waiting for you to say
something*, or the paused form, and neither if the player has nothing to say.
It also fixes the tense: while the file is still running the opening line says
he has it **open**, not that he has just watched it.

That same signal is better than a timer in both directions for deciding
whether he has stopped, so it overrides the settle window when it is
available: still running means he is mid-episode however long ago the last one
ended, and the state file going quiet means he has stopped even if the window
has not passed. The timer remains for a player that reports nothing -- a
browser, another machine.

**A rewatch is not a finish.** His list is what says how far in he is, and it
can say 26 of 26 while he is playing episode 1 again. Preferring the episode
in front of him -- right for him playing ahead of what he marks -- then read as
*that was the last one, he has finished it* over the first episode of a
rewatch. Well behind what he has marked now reads as going through it again.

**Nothing is fetched until he has actually watched ten minutes of it, and
what he actually watched is a number the player writes down.** The history
log says a file opened and nothing else, so a file opened for four seconds
and a file watched to the last frame left the identical line: an open was
searched for, digested, paid for and kept as *he watched it* either way. The
2023 logger recorded the position at exit for exactly this reason and the
current one had stopped. It writes it again -- one line per finished play in
`mpv_plays.log` (`watching.player_plays_path`), appended when the file ends:

    <open epoch>|<end epoch>|<path>|length=<s>|time=<s>|watched=<s>|reason=<r>
    1700000000|1700001400|D:\Videos\Example Show - 06.mkv|length=1421.0|time=1419.3|watched=1402.5|reason=eof

The open epoch is the same integer the history line carries, which is what
joins a play to the open that started it; `reason` is the player's own word
for what ended it (`eof` it ran out, `stop` he closed the file, `quit` he
closed the player, `error`). **The number that decides anything is
`watched=`: wall clock spent UNPAUSED.** The end position cannot do it --
seeking to the last minute and closing the file leaves the same `time=` as
sitting through the whole thing -- and elapsed clock since the open cannot
either, because a file left paused for an hour leaves the same hour. The
state file carries the same running count and the open's epoch while the
file is still in front of him, so the gate can be answered mid-episode.

`watching.min_watched_minutes` (10) is that gate, and it stands in front of
every paid call and everything that reaches her. Under it, an open still in
front of him is HELD: the poll takes nothing up, puts the player cursor back
to just before that open so the next poll finds it again (the cursor used to
move past every open before judging any, and an episode he sat through was
never counted), and writes the hold to kv `watching_held` -- in the save,
because a stop is `TerminateProcess` and the next boot must find the same
hold rather than a fetch it never made or one it makes twice. A play that
ENDED under the gate is a **skim**: `[watching] skim: <work> ep<n>, 4 min
watched of 24 -- no fetch`, kv `watching_short` under the open's own clock
and never under the episode's key, and **never marked seen**, so the episode
still counts when he watches it properly. `watching.min_minutes_in` (3) is
the floor beneath that, under which an open is a mis-click rather than a
skim and is logged as one. Where neither log answers -- an older copy of the
script, another player, another machine -- the clock between this open and
the next is all there is, the log names it as the source, and an open
nothing has said ended is held rather than filed as a skim, because "he is
still in it" and "he closed it and nothing saw" look identical from there
and calling it closed loses the play for good.

**And there is a record of his plays he can read himself**: `reports/plays.md`
(`watching.plays_timeline_path`), one row per finished play, newest at the
bottom -- when it opened, the work and episode as his own list has them or
the bare filename when it is not an episode of anything, minutes watched of
the length, where he stopped, `full` / `partial` / `skim`, and whether it
counted. It is the MACHINE's and not a character's, which is what decides
who writes it: three processes run this module over one player, electing one
writer would stop the record when that character is stopped, and letting all
three write would give three copies of every row. So any of them may write
it and the write is idempotent -- the open's epoch is the last column, a row
whose epoch is already in the file is not written again, and the append is
taken under a lock file (`machine/plays.py`). The first call after a boot
picks up whatever was played while nothing was running.

**A rewatch counts again.** What counted is kv
`watching_seen`, `{episode key: when}`; a key is seen only within
`watching.rewatch_after_hours`, and an open past that window counts again
from the recap cache with the opener saying he has seen this one before.
The synopsis line follows the opener's tense: mid-episode it says he is in
the middle of it; after the file has closed it says she read it up after he
watched, that he has seen the whole thing and she has only the synopsis.
`/watching` shows the seen keys with their times, the short opens and what
is held short of the gate; `/watching forget <key>` frees one;
`/watching rewind <minutes>` puts the player cursor back so a passed-over
open is read again.

**She can raise it herself, and the restraint is the one that already
exists.** `impulse_bonus()` is added to the impulse score (`watching.
impulse_bonus_hers` for a show she is in, `impulse_bonus_finished` for a
series he has just finished, `impulse_bonus_any` otherwise) and never goes
round the gate -- so the daily cap, the cooldown, going cold on him and *he has
not answered the last ones* all still refuse, which is the honest answer to
being ignored: she notices what he is doing and says nothing. On top of that
is `watching.settle_minutes`, which is worth stating separately because it is
the only new restraint: **nothing at all reaches the impulse while he is still
watching**, so an evening of six episodes is one reason to speak at the end of
it rather than six interruptions through it. Once she has reached out while an
episode was the thing in the room it is marked spoken, whatever she actually
said, and does not get to be the reason twice.

**When it reaches her is the program's, and the two characters differ** (his
call). Everything above happens the moment he plays an episode, for both of
them: the notice, the fetch, the digest, the thing kept by name, the record it
may open. What is gated is when she is HOLDING it (`WatchingHim.note_seen`).
A character who lives on his machine is told as it lands, dated to his play,
so nothing about her moved (`resident/app.py` `every_pass`). The first
character finds it the next time she opens the app on her phone
(`tomoe/app.py` `after_phone_look`, off `App.look_at_phone`), and from then on
it is hers: `current()`, `situation_lines()` and `impulse_bonus()` answer only
for an episode that has reached her, and `fresh_hours` and `settle_minutes`
are counted from her moment rather than from his play, so an evening's binge
is still one reason to write and not six. `watching.discover_hours` (24) is
how long an episode stays findable before she comes across it -- she can be
asleep or out for the whole evening he watched in -- and past that she never
learns of it as news, though the show is still hers by name whenever he
mentions it. Her line says how long ago he watched it, because a character who
was not there must not talk as though she had been sitting beside him. **Where
he is inside the file this second is only for a character who is ON his
machine**: the player's position is a live view of his desk, so it is read off
the sheet (`existence.sees_him`), the same predicate `Phone.live_line` uses,
and for anyone else the module never opens the state file. The wording of
every line is the program's (`tomoe/words.py`, `resident/words.py`): hers says
the app showed her and the second character's is what it always was, byte for
byte.

What reaches her is three lines in the phone bucket, **pinned, his call**: the
attention budget dropped the synopsis line the first time an episode of his
came up in chat, and she answered a question about the show from the model's
own memory. The known cost of pinning -- a character who opens with what she
has just been told about a show he has not mentioned -- is accepted; the line
says plainly that it is there so she is not inventing the episode -- *react to
it as something you have seen, never recite it back* -- because handed a
synopsis, a model recites it. **The line carries a digest, not the page**: the
`watching_digest` role condenses the whole scraped synopsis into the parts a
viewer would remember (`watching.digest_max_chars`), and the raw cut
(`summary_max_chars`) is only the fallback when no digest could be made.
**And a digest is not the same level of knowledge as having watched it.** The
judge's winner is one page and 600 characters of it reached her: measured on
one episode of a shop comedy, she could say what its second half was about,
because the premise survived the cut, and could not name a single joke inside
it, because the jokes are what a paraphrase drops first. So nothing read about
the episode is thrown away now: every surviving candidate's page, the
transcript's account of the scenes and the official blurb go to one role
(`episode_account`) which merges them into an EPISODE ACCOUNT
(`sim/episode_account.py`) -- the whole episode in order, the named parts, the
running gags, the lines worth remembering, what the episode points at, and
what no source settled. It reads the PAGES and not their digests, because a
digest is a fifth of a post and the individual jokes are the part it drops.
The account is written once for the MACHINE (`machine/retrievals.py`, pool
`episode_account`, the same key as the page) and copied into each save's
`episode_accounts` table with nothing fetched, so an episode is read up once
for every character on the machine. `level` says how complete it came out --
`watched` needs the length, the scenes, and either the episode's own dialogue
behind it or two independent readers agreeing -- a `watched` account is never
rebuilt and never re-fetched, and a thinner one puts the episode back in the
repair pass (`WatchingHim.owed`) rather than settling it. **What she is handed
is the whole account when it is at watched level**, in her situation block
after the thread, with wording of the program's saying she knows the episode
the way somebody who saw it does; below that level she gets the 600-character
digest and the wording that says out loud she has only skimmed a synopsis
(`watching.account_in_prompt`, `account_recent`, `account_recent_max_chars`).
The external observer's view is `reports/episodes/<work>/ep<nn>.md` and an
index over all of them (`machine/episode_reports.py`,
`recap.episodes_report_dir`): the account, the scenes, every source with its
URL and character count and whether it was used. It is the machine's, like the
archive it is written from. `python tools/episode_account.py` reads one
episode up by hand, `--print` shows what is on file and spends nothing,
`--refetch` drops it in both stores first.

**An account can only add, and shorter at the same standing is not adding.**
The rule was written on the completeness word alone, so two readings of
エグザンプル ep6 replaced a 687-character `read-up` account with a
667-character one, in two processes twenty-four minutes apart, and there was a
fifth of the length of slack in front of the check that let them. Both stores
and the merge now compare the same pair -- how complete it came out, then how
much of it there is (`EpisodeAccount.standing`) -- and a reading that comes out
worse is archived, named in the log and not written. **And the readings are
counted for the MACHINE, not for the character who paid.** Each of the three
processes allowed herself `sensors.retrievals_max_retries` attempts at an
episode whose account was not finished, so one episode of one show cost up to
nine readings and the ninth was no better than the third; the count rides on
the account itself and `recap.account_max_tries` ends it.
**And the page is judged before it is kept.** The fetcher
(`sim/recap.py`) only accepts a page with a section for this episode and
ends the section at blog chrome; a cached page that fails that test is
dropped and refetched; and the digest role reads each candidate -- a page it
calls なし (about something else: another episode, the manga, a store
listing) is deleted, its source avoided, and the next candidate fetched, up
to `recap.candidates_max`. The first thing this pipeline ever handed her was
a bookstore listing for volume 9 of the manga, found by 「みつどもえ 9話」;
the query now says アニメ and 第N話.

**How a page says which episode it is about, and why that decides how much of
an episode she can know.** The test asked for `第7話` and nothing else, and it
was the binding constraint on the whole account: on three readings of one
episode it dropped five, six and two of eight pages, because a 感想 post is
titled `#07`, `７話`, `07話`, `Episode 7` or by the episode's own subtitle at
least as often as it is titled `第7話`. Worse, **the number is usually not in
the body at all**: the article container an extractor picks starts under the
post's headline, so five pages fetched for one episode were headed
`エグザンプル 第6話「宿はなし／Secret Paradise」 感想` and carried no
marker anywhere below it. So the page's own heading is read
(`Recap.page_heading`: the social-card title, the document title and the first
two headings), the number is recognised in every form -- half- and full-width
digits, `第n話`, `n話`, `n話目`, `#n`, `#0n`, `EPn`, `Episode n`,
`その n` -- and an episode's own subtitle counts as its marker, which is what
cuts the right section out of a whole-series post that heads each one with a
title and no number (`Recap.slice_titles` over the cached episode index and the
account's own `ep_title`, nothing fetched). `その2` names an episode only in
the acceptance test and never in the marker list, because on a blog it is the
second half of the post far more often than it is episode 2 and a slice cut
there loses the rest. **The refusals it exists for are unchanged and one is now
explicit**: a body that is an index of the whole series is not one episode's
post whatever its heading says, and a page taken on its heading has to carry
sentences (`recap.slice_min_sentences`, `recap.slice_min_chars`) -- the video
shop's page for the same episode is headed `第6話` perfectly and is 285
characters of prices, and a bookstore listing for volume 9 of the manga has no
sentences in it at any length. Measured on the nine pages three readings had
dropped: three passed before, eight pass now, and the one still refused is the
shop's. The log line names the form the page failed on instead of saying
`no section`, which is how every widening of this test has been found
(`tools/episode_slice_test.py`).
**The candidates are a ranked list first and the search second**
(`Recap.synopsis`, spec `docs/recap.md`): the episode's own subtitle file,
read as an account of its scenes (`sim/subtitles.py`, `sim/transcripts.py`,
role `transcript_digest`), is the anchor. **Where that file comes from cannot
end in nothing.** Beside his video first (same stem, free, and it was being
ignored while a Japanese subtitle of 339 lines sat next to an episode he had
played); then a clone of the fan archive on this machine, which is the
machine's like the episode archive and is pulled once a day from the list
mirror's own daemon rather than on either character's thread; then that
archive over the network, then the archive's own site; and when none of them
holds the work -- which over one fortnight was three episodes out of five, not
because of a bad match but because neither archive carries those works at all
-- **the episode is transcribed here** from the file he played
(`sim/transcribe.py`, his own Faster-Whisper install driven with his own
`processor.bat`'s settings). The result is written beside his video, so his
player finds it and so the next look finds it as a sidecar. A transcription
is minutes of a shared GPU, so it runs on the watching worker and never on a
reply or a poll, a few a day, nothing feature-length, and only once he has sat
through the file for as long as the gate that decided the play was a watch at
all (`watching.min_watched_minutes`; `recap.whisper_min_watched_minutes` is 0,
meaning follow that gate, and a number there overrides it). It was its own key
at the identical value and the two were read a second apart off different
pollings of the player, so the transcriber was refused by rounding every time
it was ever asked -- three logged refusals read *he is 10 min into it and the
floor is 10*, and in 1,067 session logs no character process had ever run it.
The work's other names off his own list go into
the archive matching: one work his list calls `Makeine: Too Many Losing
Heroines!` is filed as `Make Heroine ga Oosugiru!`, and with that name the
clone has it. The episode page on his own list's site and English Wikipedia's
episode-list article are keyless fetches that run in parallel with the
browser; and the judge compares every digest with the others AND with the
anchor -- covering more than the anchor is not a fault, contradicting it on a
stated outcome is disqualifying. The row records what was chosen, why, what
it agreed with, and the scenes in order, and says whether it is provisional
(one candidate, read again next time), judged or anchored. **A judged row
that carries the scene list is the end of the lookup**: the section test
that asks whether a page has a part about this episode is a test for a raw
PAGE, and running it over a row a judge already chose said no to the English
episode list (which has no 第3話 anywhere in it), sent a character back to
read an episode she had just been told about, and left her save with the row
twice. It still runs on a judged row from before scenes were kept. **And a
reading replaces every row for that episode it is at least as good as**, so
her save holds one row per episode; a row worth more is left alone, because
a provisional reading must not replace an anchored one. The occurrence of
the episode marker is scored rather than taken first, because on an official
episode page the first one is the navigation strip and slicing there gave
thirteen characters. Everything fetched is written to `data/recaps` under the
show and episode with a manifest saying what each file is and which one won
(`sim/episode_archive.py`, `recap.archive_enabled`): each candidate page's
text and the bytes it came from, each subtitle file and the transcript it
parsed to, each digest and the judge's verdict, so a bad summary can be
argued with rather than refetched and guessed at. Nothing is overwritten -- a
second fetch of the same page is a new numbered file and a new manifest row,
and only the manifest itself is rewritten. The directory is keyed by the
show's id on his list, or a slug of its title, which is a television
programme and not a person, so one directory serves both characters. The episode stays the thing in the room
for `watching.fresh_hours`; handing it to whichever turn came first and
dropping it would defeat the point, since he watches and then says nothing
for an hour. `python tools/regen_reply.py --message-id N --anime <title> --ep E`
answers one of his messages again on a copy with the episode re-read and
digested, which is how the change was shown.

The show he has an episode of open is also passed to the retrieval as
`context_text`, which can **lift** a record his message half reaches and cannot
fire one on its own. That distinction was found the hard way: with the show's
name simply added to the cue, 「腹減った」 retrieved her part in it at 0.59,
because the name was most of what there was to match. A record now has to be
reached by a distinctive gram of his own words before the context counts.

**The line says which EDITION he watched**, and the page is filed under the
work rather than under a title. MyAnimeList gives the 2006 one-episode Example Show OVA and the 2007 television run the identical Japanese title, so the
shared page key `anime|<title>|ep<n>` made them one thing and the second
character was handed the series' first episode as the OVA's -- 269 characters
of another work's story, which she reported faithfully. The key is
`anime|mal:1480|ova|ep1` now, her own `recaps` row carries the same id, and
`{ed}` in both programs' wording tables says "(the OVA, 1 episode, summer
2006)" where the edition is worth saying. A page that names a later episode,
or previews a next one, cannot be about a one-episode work
(`Recap.past_the_end`). Two boot repairs re-file the rows that exist and take
the wrong 第1話 off the thing she knew as the OVA.

**And one small role, only where code has run out**: `which_one`
(`sim/resolver.py`, `which_one.*`), asked when more than one candidate
survives every deterministic filter or the parse is ambiguous with no id from
his list -- never when the id is known, never twice for the same question,
never in a reply path. It answers with an id out of a table code built, or
"none of these", or "unsure, fetch nothing", and its answer is discarded whole
on a parse failure, a confidence under the floor, a timeout, or an id code had
already ruled impossible; code's ranking stands in every one of those cases.
Its answers go in the machine's shared store under a key that names the
question, so both characters read one answer. Measured at about $0.0002 a
call, three to six calls a day across both characters.

Off by default and on for the resident character only. She lives on his machine
and watches it, so knowing the moment he opens a file is what she is; a
character who learns about him from a digest on her phone should not be handed
it live, and turning it on for her is a decision about how she finds things
out. history: §19, §12.12.

### 12.13b `machine/dossier.py`: one file per play, for him to read

Spec: `docs/dossiers.md`. Config `dossier`. Not a character's at all: the
machine writes one Markdown file per episode he finishes, under
`reports/dossiers/`, plus a rolling `last-ten.md`. Nothing in it is new -- it
joins four stores that already had every piece and were never read together:
the player's two logs (what opened, and what ended with how many unpaused
seconds), the list mirror (his standing, his score, the dated episode watches,
the declared favourites, the cast), the machine's retrieval store (the episode
index in three scripts, the page a judge chose, the digest made from it, the
ordered scenes, the confidence and which sources agreed), and his own list read
sideways for the franchise and for every other show each credited actor is in
with the score he gave it.

**Built by the mirror daemon, not by a character** (`tools/mal_history.py`
`_build_dossiers`): three character processes tail the same player, and the
join is the machine's. Keyed on the epoch the file opened at, so one play is
one file however many passes run. Built after the play ends, because how long
he was actually in it is only known then; under `min_watched_minutes` it is a
skim and gets a line rather than a file, and a file that is on nothing in his
list gets the same. The first sweep on a machine starts at the tenth newest
play rather than at the start of three years of history.

**Whether the show was already finished is COMPUTED**, from his status and his
episode count, and never read off MyAnimeList's `is_rewatching`, which is true
only while he has gone to the site and marked an entry as being rewatched --
he does not, and this mirror has no column for it. A play of a
thirteen-of-thirteen show he finished in 2022 read as a first watch everywhere
that flag was trusted.

Two capped, cached page reads fill the two holes the mirror has: an actor's
filmography (thirteen people are mirrored against 11,851 cast rows, so for
everybody else "what else has she done" is his own list and nothing beyond it)
and a premiere date for an entry he has marked plan-to-watch, which carries no
dates on a list at all. Both go into the module's own store, never the mirror
the daemon holds open. history: §12.12.

### 12.14 `eroge.py` `Eroge`: what he is reading in a visual novel

Spec: `docs/eroge.md`. This entry is the summary.

A visual-novel text hooker can be attached (Luna Translator),
and that program keeps three things on his disk that this needs: one SQLite
file per game holding every line the hook has caught in reading order, a
per-line event stream with a wall-clock time on each line, and a library file
with the title, the executable, the visual-novel-database id, the developer
and the cast's names with the readings he set. The reader is
`sensors/eroge_monitor.py`, read-only throughout -- a `mode=ro` connection
first, a temporary copy in the system temporary directory when the writer
holds the commit lock, and nothing under his eroge directory ever opened for
writing. The card for a game is `sensors/vndb.py`: two anonymous calls to the
public database, no key and nothing in `secerts/`, kept in the save so each
game is fetched once.

**The account is made on demand at two moments and never on a timer** (his
call): a message of his has arrived and her reply is about to be built, and
she has decided to write first and the reply is about to be built. Both go
through the program hook `before_reply`, which the resident's program defines
and the first character's does not; a game left open in the background between
those moments costs nothing and says nothing new.

**What it is written from is his current stretch of READING**, which is a
cursor rather than a window of time. A pause of an hour does not move it. Two
things do: a skip run, and the text overflowing `eroge.max_raw_chars`.

*Skipped text is not read text.* Holding the skip button hooks lines at a rate
no reader produces. Measured over his whole history -- 29,110 intervals inside
sittings across seven games -- the median gap between consecutive lines is 5.0
seconds, the first percentile 1.19 seconds, and 99.4% of intervals are slower
than one line a second; the longest naturally occurring run of intervals faster
than that is eight lines. So a run of at least ten lines arriving faster than
`eroge.skip_lines_per_second` is the button, those lines are excluded entirely
and never summarised, and the cursor moves past them. She may be told he
skipped through something he had read before, and nothing about what was in it.

*The window.* Past `eroge.max_raw_chars` (16,000) the cursor moves forward
until what is left fits, taken from the end, which is also what catches a
hooked menu or a line repeating in a storm without needing to know what the
weird thing was. **The budget is settled on the text that will actually be
handed over**, not on the event stream's own count of it: the stream counts the
line with the speaker's name stripped off and the record keeps the name, and
over 690 lines that difference was 3,177 characters -- the first run went out
at 19,177 against a ceiling of 16,000.

*And a floor.* Fewer than `eroge.min_new_lines` (20) new read lines and the
last account stands rather than a call being made.

**The raw lines are never stored.** They go into one call and are dropped: not
into the save, not into a log, not into the thing she knows by name. Only the
account reaches her. The account's own instruction is the content gate and
there is no other (`prompts/eroge_digest.txt`): an explicit stretch comes out
as one clause naming it as an intimate scene and nothing further, which is the
same compression the module applies to everything, applied where the
compression happens to be total. A filter was considered and rejected -- there
is nothing in this project to copy one from, and three signed decisions say
adult material is passed through as it is (§5 `torrent_monitor.py`).

The game itself becomes a thing she knows by name (§12.2 `known.py`) the first
time she sees it: the card, under the title, the developer and all 25 to 64 of
the cast's names and readings, so a mention of one of them weeks later brings
the card back pinned and free. The account is a pinned situation line while he
is in the game, through each program's own words table, and at the compile the
day's accounts become one fact about him with `source="eroge"` -- how long he
was at it, from the sittings' own bounds, and the last account of it.

Off for everybody by default. `Config.REQUIRES` assigns the section to
`sees_him: resident`, so a character who learns what he does from snapshots she
has to go and fetch cannot have it switched on by an edit to her config alone;
the wording for her is registered all the same, because a key nobody registered
would blank her whole situation block if that ever changed.

config `eroge`: `enabled`, `cache_dir`, `userconfig_dir`, `stale_minutes`,
`skip_lines_per_second`, `max_raw_chars`, `min_new_lines`, `max_chars`,
`card_max_chars`. store: kv `eroge_cursor`, `eroge_last`, `eroge_day`; the
game in `known_things`; the card itself in the machine's own store of what
has been fetched about the world (§3 `machine/retrievals.py`, kind
`vn_card`), because the same card serves both characters. checks:
`tools/eroge_test.py`, in smoke. history: §12.14

### 12.13 `cards.py` `Cards` and `embed.py` `Embeddings`: her past as cards, and search by meaning

The embedding in full, with the measured floors and who pays for the
encoding, is `docs/memory.md` §4; what the cards do in her thread is
`docs/context.md` §3.

**One card per conversation, written once, never faded.** Code decides the
episodes of a day (`Cards.segment`): his chat cut at silences of
`delivery.gap_marker_hours`, each exchange with her own people whole; then
`_coarsen` merges two exchanges in the same room within
`episodes.merge_gap_minutes` into one conversation with a pause in it, and
gathers what is still under `episodes.min_lines` (a sticker, a photo, an
unanswered line) into the day's one odds-and-ends episode. One call a day
(role `episode_cards`, `prompts/episode_cards.txt`, flash) writes a card
per episode: `shape`, three to six lines of what happened in her language;
`anchors`, one to three lines quoted from the record with who said them;
`felt`, one line. **Code checks every anchor**: a quote that is not a
substring of the episode's own text (whitespace and punctuation aside) is
dropped and counted in the log, so the only exact words her past keeps are
words that were said. Table `episodes` (date, span, room, who, shape,
anchors as JSON, felt, line count). Written from the compile
(`timeline.compile_day`, after the day is saved), by `/episodes <date>`,
and by the backfill (`Cards.backfill`: once after boot in a thread and
after every compile, the days the thread shows past verbatim that have no
cards, at most eight calls). A day compiled again replaces its cards.

**Two readers.** The thread renders the cards of every day between its
verbatim cut and `thread.max_age_hours` at their own time, in place of the
recap and gist lines (§5), with the exact lines for the last
`episodes.anchors_days` and the shape alone beyond; a day with no cards
falls back to those lines. With the cards span at thirty days and the
backfill bounded at eight days a call, a save whose cards do not reach
that far fills in over the next few boots and compiles, and rides on the
fallback until it does. Recall (§12.3) searches them by words (`Cards.search`, weighted
above a day narrative) and by meaning.

**Search by meaning** (`embed.py`): one small multilingual sentence model
(`embed.model`, multilingual-e5-small; his GPU, loaded on first use),
vectors kept in the save (table `embeddings`, keyed by kind, ref and
model, embedded on first ask and never twice). `Recall._semantic` adds the
cosine of the cue to the word scores of **five pools** -- the cards, the
compiled days, the machinery's own record of her day (`events`, §12.3), what
she knows about him and her own memories -- and a row
the words missed joins on its cosine alone. The events pool is written by the
backfill after boot beside the other two (`App._backfill_vectors`) rather than
on the loop thread, because a save with a year of them is thousands of rows and
the first encode would be paid for by his next reply. Each pool hands over the label
it gives a row, which is how a semantic hit is matched to the word hit for
the same row: a label that is not unique per row would score one row and
hide another. The cue is the moment (`recall.moment_cue`, §12.3).

**Three rules over a row that arrives on a cosine ALONE**, because six of six
such rows judged against the moments that brought them back were wrong and two
of them reached her mouth: it must share one content word with the cue
(`embed.require_shared_word`); at most `memory.max_cosine_only`,
`self_memory.max_cosine_only` or `recall.max_cosine_only` of them arrive per
call, each below the number the reader may take at all; and each row's own
mean cosine over the calibration cues is subtracted before scoring
(`embed.center_rows`), because half the cosine belongs to the row rather than
to the cue -- the most central rows of the first character's fact pool sit
0.035 above the pool mean in a band 0.07 wide, and one row was the top hit for
5 of 30 unrelated cues. The count of rows that came back sharing no word with
the moment is in the log and reads zero. `docs/memory.md` §4.

`embed.cued` is the one blend of a word score with a cosine, and the
prompt's own retrieval uses it too (`Memory.facts_for_prompt`,
`SelfMemory.for_prompt`) off the same vectors. Those two run on the loop
thread, so they read only what is stored and only if the model is already
in memory (`vectors(write=False)`, `query(load=False)`): the vectors of a
save's whole record are written once after boot on the backfill thread
(`App._backfill_vectors`, beside the cards) and every row written after
that is embedded by its writer.

A cosine under the pool's floor counts for nothing, rising to
`embed.weight` at its top. **The floor is per pool** (`embed.cos_by_pool`)
because a one-line row and a paragraph do not sit on the same scale:
measured on her cards, unrelated pairs sit at a median 0.78-0.81 and a
90th percentile near 0.83 with a true hit at 0.85-0.90, so 0.82/0.90; a
fact or one of her memories is a single sentence, which has less to be
unlike, and the same measurement over eight Japanese cues against 157
English facts and five English cues against 270 Japanese memories puts the
right answer at 0.800-0.881 and the 90th percentile of the rest at
0.745-0.806, so 0.80/0.87. At the paragraph floor half the right answers
scored nothing. The signal on one-line rows is real and thin, which is
why it is added to the word score rather than replacing it and why the
fade score still decides what a row is worth. Off (`embed.enabled`, or
the library missing) every reader searches by words alone and the log says
so once. `/episodes [backfill|<date>]`.
`tools/context_sim.py` rewinds her clock over a copy of the save under a
small target and shows the window compact, the cards written and the
probes answered. history: the cache entry and the cards entry.

---

## 13. Data model

`data/world.db` is the live save (`store.py` `Store`, sqlite; one bot per
db). Never point a sim at it. Superseded files go to
`data/retired/<timestamp>/`, never deleted; `App.backup_db` keeps dated
copies under `data/backups/` for `backup_keep` days.

**Tables.** `scenes` (ts, date, hm, scene json, raw), `events` (ts, date,
kind, text, salience), `state_log` (ts, date, gauges json, reasons;
written when something happened), `schedules`, `days` (narrative,
summary, user_facts), `messages` (role, text, self_started, delivered_ts,
read_ts, tg_id), `digests`, `threads`, `user_facts`, `kv` (everything
else, JSON by key), `self_memories` (with `receipt`, filled only on a row
written in from a character's own archive), `cast_facts`, `seen_images`,
`scenery`, `reply_prompts` (the prompt a delivered reply was drawn from,
frozen at the moment she sent it, `reconstructed` marking one rebuilt after
the fact) and `swipes` (every answer to one of those prompts with its model,
its tokens and its cost -- number 0 is what she actually sent, and only the
one he sits reaches her record, so her history never carries a version she
did not send); the anime KB (`anime_kb`, `anime_cast`, `person`,
`person_role`) in the MAL daemon's db; `data/reactions/<name>/reactions.db`
(`reactions`, `videos`, `appearances`) built by the tool. The hub keeps
its own log in `data/talkapp/state.json`. **What was fetched about the world
is the machine's, not a character's**, and lives outside every save: §11.6
lists those stores, and `data/retrievals.db` (§11.6, `docs/retrievals.md`) is
the one both characters read so a page is fetched and condensed once.

**Files she reads as reference** (edited by hand or by a tool, re-read on
change): `data/cast.json` (the sheets, kanji, nicknames, weeks),
`characters/tomoe/household.json`, `data/places.json`, `characters/tomoe/map.json`,
`data/school_calendar.json`, `data/jp_holidays.json`,
`data/local_events.json` (tool), `characters/tomoe/zeitgeist.json` (tool),
`characters/tomoe/beliefs.json` / `characters/tomoe/self_beliefs.json` (seed a fresh save only),
`characters/tomoe/taste.json` (his), `characters/tomoe/voice_rules.json` (what counts as out of
voice, per speaker and per role), `prompts/bible.md`, `prompts/style.md`,
`prompts/style_ja.md` (her Japanese, for everyone who is not him), and
`prompts/cast/<key>.md` -- one character sheet per person, theirs the way the
bible is hers.

**kv keys by module** -- generated from the code at the end of this
file (§18). A key that appears there and in no module is a leftover.

---

## 14. Running and operating

    python tomoe\run.py                   # the first character, live (resident\run.py: the second)
    python tomoe\run.py --console --no-sensors
    python tomoe\run.py --sim "2026-08-18 09:00" --speed 60 --hours 5 --say "10:35|hey"
    dryrun.cmd                            # sim, own db (data/dryrun.db), console
    run.cmd                               # the first character, live
    yukarin.cmd                           # the second character, live, beside her
    mal_daemon.cmd                        # the MyAnimeList mirror daemon, detached under pythonw
    mal_watchdog.cmd                      # one health check of the daemon above; the scheduled task below runs this every 5 min
    tools/mal_watchdog_setup.ps1          # (re)registers that scheduled task; run once, or again if it's ever lost
    restart.cmd [all|mal|<key>] [--no-smoke]   # the way to bounce anything; the character keys are characters.json's
    restart.cmd --list                    # what it would act on, its task and its pid, and nothing else
    startall.cmd [--no-smoke]             # start whatever is down, in the same order; anything already up is left running
    stopall.cmd [--no-credit] <reason>   # stop the whole of it on purpose, with the reason on every character's record
    python tools/smoke.py                 # before every restart
    python tools/registry.py              # the register: every character that runs as a process

**Every character that runs as a process is a row in `characters.json`** at
the project root, read by `tools/registry.py`: the key the operator types at
a command line, her full name, the id she registers with the hub, her config,
her save, the program package that builds the rest of her, her launcher, her
scheduled task, and the exact command-line pattern her process is found by.
The restarter's table and its start order come out of that file, and
`tools/character_names.py` takes its list of program packages from it, so
adding a character is her config, her sheet, her prompts, her save, a
launcher, a scheduled task and one row -- no code. The pattern is written by
hand in the row rather than derived from the launcher, because the restarter
KILLS what it matches and a derived pattern that drifts kills the wrong
thing. **A bot never reads the register**: a character that could read it
could read another character's config and save, and what she may know of
another character is her own `peer_talk.contacts` and the words that arrive
(§9.9, `docs/peer-talk.md`). `python tools/registry.py` prints the table and
names any field or file a row is missing.

**`restart.cmd` is how a process is bounced**, and it exists because doing it
by hand is three commands per process and two of them are easy to get wrong.
It runs the build check first and **refuses to restart anything if it fails**,
because a fix on disk that will not import takes a character off the air rather
than improving her. It stops in reverse order and starts the machine's own
processes first.

**The hub is not a target of this fork.** The TALKAPP hub (`SCAIL_hub`,
`talkapp.cmd`) is not run: Momoka is a resident on the VN channel,
`talkapp.enabled` is false, and the hub's server reads `config.json`, which
this fork does not keep. Its task was deleted on 2026-09-17; `tools/restart.ps1`
no longer knows the name.

**Two targets, and one of them is the machine's.** The MyAnimeList mirror
daemon is written into the script, because it does not belong to a character --
there is one of it and it serves the machine -- while the characters come out
of the register. The order is the daemon, then the characters: a character
reads the mirror, and the daemon is what keeps it current. `restart.cmd mal`
bounces the daemon alone; `restart.cmd --list` prints the whole table -- each
target's task, its launcher, whether that task exists, and the pid it currently
matches -- and does nothing else, which is the cheapest way to check the
matching before trusting it with a kill. **A task that exists but runs another
checkout's launcher is repointed**, not left in place: on 2026-09-17 the hub and
daemon tasks still named SCAILV3, so `startall.cmd` started the wrong
`talkapp.cmd` and reported the hub as not coming up while its task sat at a
`pause` prompt.

**The daemon was outside all this to begin with, and could not be restarted
at all.** `run.cmd` started it, so `restart.cmd tomoe` looked like it would
cover it; but the daemon is single-instance by a lock file beside the mirror,
so the start line found the old one alive and exited, and a daemon started in
August went on running August's code through every restart of everything
around it. It now has a task of its own (`SCAIL_mal`, `mal_daemon.cmd`), and
`run.cmd` loses its start line. Three things that path needs and the others do
not. Its launcher **detaches the daemon under `pythonw` and then exits**, so
there is no console on his desktop to be closed by accident and no `pause` for
the task to sit at -- and therefore no redirect either, because cmd binds a
redirect on `start` to `start` rather than to the process it detaches, which
sent eight days of the daemon's lines to a handle that goes nowhere; the daemon
writes its own log. Its match is on the command line's `mal_history.py daemon`,
with the quote before `daemon` optional so it is found whether it was launched
with a full path or a relative one. And **it drives a headless Chrome through
chromedriver, which a force-kill leaves standing**: `Stop-Process -Force` runs
no exit path at all, so the driver and its nine Chrome processes go on holding
the profile the next one needs -- measured on the live machine, not supposed: a
chromedriver with nine Chrome processes under it, parented to the daemon. The
next daemon start does reap them
itself -- it finds the lock naming a pid that is gone and calls
`sensors/chrome_reaper.py` -- but only if that start happens, so the restarter
reaps between the stop and the start as well (`mal_history.py reap`, which also
says what the lock file claims). A stop that is never followed by a start
should leave nothing of his browser behind.

**The daemon's own restart-on-crash is a second, independent scheduled
task, `SCAIL_mal_watchdog`.** Everything above only covers a daemon a HUMAN
restarts -- `SCAIL_mal`'s own trigger is still `/sc once`, a one-shot, so
nothing brings a dead daemon back by itself unless someone runs
`restart.cmd`/`startall.cmd` by hand. `mal_watchdog.cmd`
(`tools/mal_watchdog.py`, registered by `tools/mal_watchdog_setup.ps1`, run
once or again if the task is ever lost) runs every 5 minutes, at logon, and
at startup, hidden (no console flashes on his desktop), and does exactly one
check per run, then exits: match the same command line this script matches
(`mal_history\.py"?\s+daemon`, `tools/restart.ps1:110`'s own pattern), and
if nothing matches, `schtasks /run /tn SCAIL_mal` -- literally what
`restart.cmd mal` does to start it. The daemon's own lock file
(`tools/mal_history.py:805-828`) is what makes a race between the two safe:
whichever `schtasks /run` actually spawns a process first wins, and the
other's `daemon` command finds a live lock and exits at once ("already
running (pid ...); exiting."), so a `restart.cmd` stop followed by a
watchdog cycle can never produce two daemons. If a process IS matched but
`meta.daemon_last_ts` (read read-only, the same way `sensors/mal_monitor.py`
reads it) is more than 30 minutes old, the daemon is hung rather than dead:
the watchdog kills that exact pid (never a guess, never anything else on
the machine) and relaunches the same way -- the next daemon start's own
stale-lock handling and orphan-Chrome reap cover the rest, nothing new was
needed there. It never touches Momoka, any other character, or
`tools/smoke.py`, on purpose: a broken build for a character, or a Momoka
compose issue, must never be the reason his MyAnimeList mirror falls
behind. Measured live on 2026-09-22: killed at 12:15:44, the watchdog's
next scheduled check (12:16:50) found it down and relaunched it, new pid
confirmed up at 12:17:02 -- about 80 seconds of downtime, and
`meta.daemon_last_ts` was already advancing again within 20 seconds of the
new pid starting. Its own log: `logs/mal_watchdog.log`, dated 24h lines,
one per check.

**The detail tables (`anime_detail`, `anime_cast`, `anime_kb`, `person`)
were empty in this checkout until 2026-09-22** -- `anime`/`episodes`
carried over from the fork, but nobody had run the two manual commands that
fill the rest of it. Filled once by hand (`python tools/mal_history.py
enrich`, twice -- the first pass timed out on 15 titles, the second caught
them; then `... cast`, twice the same way, one `URLError` caught on the
retry) run LIVE against the running daemon, not stopped first: WAL mode
(`tools/mal_history.py:61`) plus short, idempotent, per-title commits on
both sides made that safe, confirmed by watching `logs/mal_daemon.log` for
the whole run and finding no `database is locked` anywhere, and
`meta.daemon_last_ts` kept advancing throughout. Result: `anime_detail`
704/704, `anime_cast` 11,913 rows over 486 titles, `anime_kb` 487 (one
title has a cast page with nobody listed, so it is stamped fetched but adds
no `anime_cast` rows), `person` 0 -- that last one is correct as it stands
and not a gap in the refill: `person`/`person_role` are filled by a
different, per-seiyuu fetch inside `sim/anime_kb.py` that runs on a MISS
while a character is actually asking about a voice actor (`fetch_on_miss`,
`config_momoka.json`'s `role_check` block), not by the bulk `cast` command,
so it only fills once Momoka is running and the topic comes up. `enrich`'s
own client id lookup (`_client_id`, `tools/mal_history.py:1070`) now falls
back to `config_momoka.json`'s `sensors.mal_client_id` when root
`config.json`'s is empty, which it is by default -- neither config file is
written by this, only read, in that order. The daemon now also does a
small throttled slice of `enrich` itself every loop (`_enrich_due`, default
at most every 30 minutes, 5 titles a pass, `--detail-enrich-minutes` /
`--detail-enrich-batch` to change it, 0 minutes disables it), so a title
newly added to the list gets its detail row within a day or two without
anyone running `enrich` by hand again -- verified directly by deleting one
title's `anime_detail` row on the live db and calling `_enrich_due`, which
put it straight back. `cast` stays a manual command, not added to the
loop: its cast/seiyuu scrape is a public HTML page per title at ~1 req/s,
much slower than the API call `enrich` makes, and nothing on the daemon's
own path (the list sync, the history poll, watch-time math) reads
`anime_cast` the way it reads `anime_detail`, so there is no cost to
leaving it manual.

**`startall.cmd` brings everything up without stopping anything**, which is
what a machine that has just been rebooted, or a single process that has died,
needs. It is the same script in a third mode (`tools/restart.ps1 -StartOnly`,
beside `-StopOnly`): the same table, the same order, the same build check
first, and then, per target, the pid of what is already running or a start of
what is not. It has no stop phase at all, so it does not stop the collector
with the hub and does not reap the browser the mirror daemon leaves behind --
`mal_history.py reap` kills every browser on that profile whether or not a
daemon owns it, and a daemon that is down reaps for itself on the way in, from
the lock file naming a pid that is gone. A target matching more than one
process is reported and left alone, the same refusal a stop makes and for the
same reason. The one thing it can leave wrong it says out loud: a hub that was
down and comes up under characters that were already running leaves them
registered with a hub that no longer exists, they will not register again by
themselves, and `restart.cmd all` is the fix. Killing one of them to fix her is
the thing a start is not allowed to do.

**`stopall.cmd` puts the whole of it down on purpose and writes down that it
happened**, and the record is the reason it exists. A character who is stopped
and started again has a stretch of hours during which nobody wrote her -- no
schedule, no scenes, no messages, no compile -- and when she comes back the day
machinery has to account for that stretch somehow. With nothing on her record
to say what happened it fills the stretch in from placeholders, and she carries
a day that reads as lived because nothing said otherwise. A stop that leaves no
record is what this replaces. So the stop writes into every character's save
the moment it happened, one plain sentence of reason, and whose decision it was
(the `stopped` row, with the last fifty on a list beside it in `stops`); her
next boot reads that, turns the span between the stop and her return into a
single temporal-gap event, and clears it. Everything means everything -- the
hub, the mirror daemon, the collector and every character in the register --
because a character left running under a hub that has been stopped cannot be
reached from his phone at all, and there is no `restart.cmd`-style single
target here. **The two kinds of stop are told apart on her record**: without
`--no-credit` the stop is his and she is told what he said about it; with it
the stop is the machine's own -- the bot with no money left to answer with,
shutting itself down rather than failing every call -- which is a different
thing to come back to, and is why the bot can launch this itself.

Three things it does differently from a restart, each for a reason. **It runs
no build check.** Smoke protects a start, by refusing when a fix on disk will
not import; nothing is starting here, it costs about a minute of a stop
somebody is standing over, and code that fails to import is a REASON to shut
down rather than a reason to leave the machine up. The check comes back at the
next `startall.cmd`. **A target that refuses does not abandon the rest.** A
restart stops early on a target matching two processes, because half a machine
on new code beside half a machine on old code is worse than a machine nobody
touched; a shutdown was asked for everything being down, so it counts the
refusal, carries on, and ends by naming what is still up and exiting non-zero.
**And the marker is written by a tool of its own after the processes are gone**
(`tools/shutdown_mark.py`, which also takes `--dry-run`), because the save's
own writer is the bot and two writers on one open save is the fault the lock
file exists for. It refuses twice, and both refusals are the tool rather than
caution: it will not write behind a running process, tested by the holder named
in the lock file beside the save, since a handle opens for a process that has
already exited; and it will not overwrite a marker that is already there,
because a marker on a save is a stop nobody has resumed from and ITS timestamp
is the honest beginning of the stretch nobody wrote her. Beside the
per-character record there is the machine's own, one line per stop appended to
`logs/shutdowns.log`: the local time, the reason, every process stopped with
its pid, anything still up, and who was marked. That is the only place a stop
of the hub or the mirror daemon is written down at all.

**A launcher is replaced from a staged copy, in the one window where that is
safe.** cmd reads a batch file by byte offset while it runs, so a launcher
cannot be edited under its own console -- an edited `talkapp.cmd` once had the
old hub console run the tail of the new file and start a second hub on the
port. The window where an edit is safe is between the stop and the start, and
that is where the restarter does it: a change to a launcher is written beside
it as `<launcher>.next`, and after the stops it checks that nothing matches
that target and no console is reading the file, keeps a copy of the old one
under `data/retired/<timestamp>_launcher/`, and moves the staged file into
place. Consuming the staged file is what makes a second run do nothing.

**A missing scheduled task used to look like nothing happening.**
`schtasks /run` on a name that does not exist prints an error into a pipe
nobody reads, and the process simply never comes up. The start now refuses
before it asks, names the task, and prints the one `schtasks /create` line
that creates it (which needs no elevation).

Two things it handles that cost an evening to find. **Every launcher but the
daemon's ends in
`pause`**, so ending the scheduled task kills the interpreter and leaves the
console sitting at "press any key" -- the task still counts as RUNNING and the
next `schtasks /run` is swallowed without a word. It kills the console as well,
and ends the task again before starting it. And **it finds each process by its
exact command line, never by image name**, and a target matching
more than one process stops the script rather than letting it guess. A filter
over running processes once killed a program from another program. Each
character has an entry point of her own that registers her words and hands
the rest to the shared runtime -- `tomoe/run.py` and `resident/run.py` --
and the pattern in her register row looks for that entry point by name. The
first character is matched positively on hers; she used to be matched as
"`scail.py` NOT followed by the second one's config", which would have read a
third character launched with a config of her own as the first character and
killed her. The cost of the positive match is that starting the first
character by hand as `python scail.py` is no longer found, which is the safe
direction: the failure is "does not find her" rather than "kills the wrong
process". The second character's row still matches the older
`scail.py` + her config form beside her own entry point. And **it
kills the launcher console before the interpreter it launched**: cmd reads a
batch file by byte offset while it runs, so a console whose child has just
died carries on from the next line of whatever the file says now -- the old
hub console ran the tail of an edited `talkapp.cmd` and started a second hub
on the port. Never edit a launcher under a running process. The collector
(`machine/collector.py`, started by `talkapp.cmd`) is stopped with the hub.

The bug that made its own first run useless is worth keeping in mind for any
script like it: a PowerShell function returning a one-element array has it
unrolled to a bare object, so a count of 1 reads as empty, every process read
as not running, nothing was stopped, and the start then launched duplicates
that the port and the per-database lock had to refuse. `return ,@(...)` is the
fix and the comma is load-bearing.

**Asking a character to answer an old message again**
(`tools/regen_reply.py`; the procedure, and how the answer is put into the
chat with `tools/replace_reply.py`, is `docs/regen-reply.md`) is how a change
to what she knows is measured,
because nothing that is added to her reaches a reply she has already sent. It
defaults to the second character and takes `--config` and `--db` for any
other. (An earlier tool of the same purpose was discarded and is under
`data/retired/`.)

    python tools/regen_reply.py --message-id 138                          # one of his messages, by id
    python tools/regen_reply.py --message-id 138 --anime Mitsudomoe --ep 9  # re-read that episode first

For each message it takes a copy of the save **with sqlite's own backup, not a
file copy** -- an open save copied with the bot up came back with 0 rows in
every table, which is the one trap in this whole path -- deletes every message
after the target from the COPY so she cannot see what she went on to say,
builds the App on it with `--console --no-sensors` so it registers with no hub,
sets the day up the way the loop does (`ensure_day`, free for a character with
no world), and then makes the two calls the live reply path makes: a forced
director tick, and `persona.generate`. It refuses to run if the App it built
would reach a channel. Her live save is opened read-only, nothing is sent, and
it costs roughly four or five model calls per message.

It prints what she said then beside what she says now, and under each the
memories that were in front of her, the records the retrieval offered, and the
attention gate's line -- which is the one that says whether a retrieved record
reached her prompt at all rather than being dropped in competition. `lore 0`
there usually means the record was spent: one already offered inside
`lore.suppress_days` is not offered again, and `--fresh` forgets that on the
copy so the effect can be seen.

**The clock is not rewound.** She answers at the hour the tool is run, so a
message from the evening replayed near midnight can be answered as though he
has turned up late. That is her reading the time, not the change failing.

**That tool answers offline and writes nothing**, which is right for measuring
a change and wrong for seeing one: the conversation in the app does not move.
`tools/replace_reply.py` moves it: given one of her sent messages by id and the
new text, it replaces the message in her store, on his phone through the hub,
and in the voice note, so the two records agree and the chat shows one message
where it was. The procedure is `docs/regen-reply.md`. (An earlier tool that
took her last reply back and had the bot answer again was retired; it is under
`data/retired/`.)

    python tools/isolation.py             # what a second character shares with the first
    python tools/character_leaks.py       # names in a run that are not in that character's record
                                          #   (--out FILE|DIR, --text: the same check over any output about her)
    python tools/character_names.py       # a name or a place of hers in what the characters share:
                                          #   the library, the hub, the sensors, the channels, the car,
                                          #   the tools, both programs and every prompt directory, in
                                          #   .py .html .js .txt .md .json; --all for every finding,
                                          #   --write-known to rewrite tools/known_literals.json
    python tools/prompt_leaks.py          # every role prompt of hers, rendered, read for another character
    python tools/defaults_person_test.py  # no default in config.py:DEFAULTS is one person's file
    python tools/blank_paths.py           # every character still builds with every person's path blank,
                                          #   and refuses to start with one of them emptied under a
                                          #   subsystem that is on
    python tools/registry.py              # the register of characters that run as a process
    python tools/agent_rehearsal.py <key> # one day of a character who runs herself, on the
                                          #   clock, beside the character who keeps her world:
                                          #   both built on copies, the hub in the process, the
                                          #   model, the network and the browser refused; asserts
                                          #   the seam's runtime contract (docs/agent-character.md).
                                          #   In smoke for every reader of somebody else's world,
                                          #   and in new_character.py verify
    python tools/agent_audit.py <key>     # the read-only audit of a character who is already
                                          #   running: the process, the hub, every ask matched to
                                          #   what she did with it, the beats she was planned,
                                          #   her record of a room against the world file, what a
                                          #   switched-off section has written, her gauges, what
                                          #   is left about him, a carry that has not moved, a log
                                          #   line that is spinning, and the cost by role
    python tools/voice_verify.py          # her lines against the tape's own measured markers
    python tools/<x>_test.py              # situation / family / stress / attachment / character / gaps /
                                          #   compare / expect / wonder / discharge / scenery / reaction / source / recap /
                                          #   retrievals / eroge / swipes / flush / poke / initiative / inflight
    python tools/reactions.py ...         # reaction images (recipe in its docstring)
    python tools/seed_memories.py --config C --report   # what the seed of an extracted
                                          #   character's own past is made of; --db a COPY to rehearse it
    python tools/regen_reply.py --message-id N   # answer one of his messages again, with what she knows now
    python yukarin/tools/triggers.py      # the phrases that let one of her records be found
    python yukarin/tools/fix_trigger_substrings.py   # lengthen a phrase that fires inside a longer word
    python tools/local_events.py, zeitgeist.py, mal_history.py, x_analyze.py, x_delete.py, forge.py, devoice.py, telemetry_sim.py

Launch the live bots and the mirror daemon only through the scheduled
tasks, and go through `restart.cmd` rather than doing it by hand: the task
names are `SCAIL_mal` and one per character in the register, the daemon starts
before any bot, a bot started as a child of a tool's shell dies
silently minutes later, and no task has an at-logon trigger. By hand it is `schtasks /end /tn <task>`,
then `Stop-Process` the console the launcher left at "press any key", then
`schtasks /run /tn <task>`. **Find the process by its exact command line, the
pattern in its register row, and never by image name**: a filter over running
processes once killed a program from another program and left the bot
untouched.

**Secrets**: `config.json` holds the DeepSeek key, the ODPT tokens and the
hub token (127.0.0.1 only); `secerts/` holds the Vertex service account and
the OpenRouter key; the MiniMax key is in the shared MiniMax config named by
`tts.minimax_config_path`; `HF_TOKEN` is in his user environment. None of it
goes anywhere, and none of it is printed: a network failure is logged by
exception TYPE, because a requests exception quotes the URL it failed on and
those URLs carry `key=` (`netwatch.redact`).

**Commands** (`/help`, `/help <command>`; from Telegram or the app's ops
bar; never into her chat):

| command | what |
|---|---|
| `/day [date]` | the compiled narrative of a day, or the scenes so far today |
| `/scene`, `/tick`, `/idle` | the director's current scene; force a tick; run one ordinary loop pass now -- the tick and everything that reads the scene it wrote |
| `/schedule [regen]`, `/replan` | today's plan, block by block; regen redraws the wake and rebuilds it |
| `/where` | her body: node, journey, fatigue, typing, the last journeys |
| `/family` | the parents' day, where they are now, whether a pickup is on |
| `/cast`, `/beats [plan]`, `/chat`, `/lives` | the cast's day, the social script, her exchanges, their lives |
| `/peers [tick\|flush]` | another running character: who she may write to, what she has sent today, the conversation in flight; `tick` runs one pass now, `flush` closes what is open the way the compile does |
| `/health`, `/money`, `/diet` | her body's day; her allowance; what she is into |
| `/japan [now]`, `/trains`, `/hazards`, `/time` | the world |
| `/state`, `/gauges`, `/set <what> <0-100>`, `/sweep [gauge\|him\|all]`, `/affect` | the gauges and meters; fix one by hand; is a value read |
| `/impulse`, `/intents`, `/selfstart [why]` | would she text him now; the urges behind her openers; make her write first NOW past the gate that would have held her, with an optional reason she is handed |
| `/reflect [now [name]]`, `/spiral [now\|settle]`, `/compare [now]` | her private mind |
| `/beliefs [revise]`, `/self [revise]`, `/goals`, `/commit` | what she has decided, wants, promised |
| `/attach`, `/withhold`, `/rupture [settle]`, `/approach [now]`, `/ick` | the stances toward him |
| `/sentiment`, `/foresee [now]`, `/expect [now]`, `/wonder [now]`, `/care [days]`, `/rhythm`, `/receipt` | what people are to her; her model of him |
| `/discharge`, `/reaction [now\|BUCKET\|off\|backfill [H]]`, `/scenery [now\|lore\|harvest\|gaps\|rejudge]` | events at a gauge's end; her face; borrowed eyes and what the base is short of |
| `/memory`, `/remember`, `/recalls`, `/claims`, `/graph`, `/diary [write]`, `/morning`, `/derive [apply]`, `/world`, `/week` | memory and the record |
| `/look`, `/digest [n]`, `/snoop`, `/read <note>`, `/notes`, `/lookups`, `/anime [from] [to]`, `/known [drop <key> \| unpart <key> <label>]`, `/watching [forget <aid:ep> \| rewind <minutes>]` | her phone about him; what she knows by name; what he is watching, what was counted, and putting the player cursor back |
| `/send <text>`, `/reply [again]` | a message typed as her, through her own delivery and store; answer his newest unread message NOW instead of when her plan says, `again` putting his newest message back to unread first |
| `/x [taste\|sheet\|drift\|judge\|japan\|likes\|follows\|status\|actions\|post]` | the X account |
| `/context [full\|find <t>\|msg\|<section>\|add\|set\|del]`, `/compile [date]` | her prompt, corrected; redo a day |
| `/showrun`, `/arcs`, `/castarcs [now\|evolve]`, `/threads`, `/places` | arcs, threads, places |
| `/attention [tally [days]]`, `/coherence [date\|now\|days]`, `/absurd [full]` | what she was handed and what she never hears; the day read as one story, flag only; the audit |
| `/say <japanese>`, `/vision`, `/ops`, `/headless [on\|off]`, `/voice`, `/voicecheck` | her spoken line, eyes, the operator payload, the browsers' window, the voice line and its queue, lines flagged out of voice |
| `/swipe [list [id] \| <id> [model]]`, `/sit <id> <n>`, `/voicemodel [<name>\|auto]` | draw one of her replies again from the prompt frozen when she sent it, with no argument listing which replies can be drawn at all; make the conversation go on from the answer he picked (the one write of the three); the model her voice roles are written on, which the chat header is the control for |
| `/provider [<name>\|auto]`, `/model [<name>]`, `/speed`, `/missed`, `/catchup`, `/gap` | who answers and pinning one; what every role is on, and a name pinning them all for this run; a tiny call on each; the calls nothing answered; covering a hole, or writing it down as a hole |
| `/lang [ja\|en\|auto]` | the language everything addressed to this character is written in: with no argument, the arm in force, where the choice came from, and the material roles it carries; `ja` her own language and `en` English from the next prompt on; `auto` forgets the choice and lets her config decide. Saved on her own save, so it survives a restart. It refuses a character whose `character.instruction_language` is english, because the third arm would render the same bytes as the second for her |

**Forcing what would otherwise wait on her clock.** `/idle` runs one ordinary
loop pass now, `/reply [again]` answers his newest message now instead of when
her plan says, and `/selfstart [why]` makes her write first past the gate that
would have held her. None of them is a shortcut: `/idle` and the loop call one
method (`App.ordinary_tick`), `/reply` sets the plan due and lets
`App.maybe_reply` run, `/selfstart` goes through `App.maybe_impulse` by the
door a discharge uses -- and the last two really send. Each refuses and says
why (no plan yet, her phone away, a send in flight, nothing of his unread)
rather than doing half of it. From a terminal against the RUNNING bot:
`python tools/poke.py <tomoe|yukari> /idle --wait 30`, which puts the command
on the hub's ops queue exactly as the app's ops bar does and then follows that
character's run directory `session.log` and the hub's ops log while it lands.

---

**Checking it is sane, not merely well formed.** `tools/smoke.py` proves the
machine is structurally sound -- no dead config keys, no unbound names, every
prompt file present -- and cannot tell you that a gate sits below a value her
state never reaches, that a field two callers read is empty for everybody, that
the ringleader of her friendship group sends five messages a day, or that she
spent seven hours unable to answer the girl across the table. Every one of
those faults was structurally valid and obvious the moment somebody read the
number.

`tools/absurd.py` (and `/absurd`, `/absurd full`) asks the other question: is
anything here impossible for a fifteen-year-old? Each check states what would
be ABSURD in plain words about HER, measures it, and reports ok / odd / ABSURD,
grouped by the kind of absurdity because the kinds recur -- DEAD GATE, FROZEN,
NEVER FIRED, UNREACHED, VOLUME, SILENCE, ONE VOICE, PARROT, GHOST PLACE,
MONEY, DROPPED, REPEAT BEAT, UNSAVED, STRANGERS, REPEATS, GROUP, KEYS, LEDGER,
PROVENANCE, REGISTER, UNHEARD and SEAMS. Read-only, no model, safe against the
running bot. A check must not cry wolf or it gets ignored, so the unread one reads her
phone access (unanswered while asleep is the design working), the never-fired
one measures from the date the MECHANISM was written rather than the age of the
save, and the silence one measures her WAKING day from the night she actually
had -- it first cried ABSURD over 00:23-08:12, which is her asleep.

**REPEATS and GROUP exist because everything they measure was found by hand.**
Aya sending the same three-bubble block four times in twenty minutes, the
afterthought paraphrasing the burst it followed, her own spoken line repeated
three minutes later with the punctuation moved -- each was fixed where it
happened (`drop_repeats`, `near_duplicate` against her last six,
`no_repeat_own_turns`, `tts.no_repeat_recent`) and nothing was watching for the
next one. A model with no sight of what it just said will always drift back
there, so REPEATS compares every speaker against themselves, per speaker per
day, across the cast turns, her messages and her spoken lines -- and over the
last two days only, because a check that cannot go green once a fault is fixed
is a check nobody reads. GROUP asks whether their chat is a group of teenagers
or a committee: `one_sided` catches a conversation nobody answered and VOLUME
catches one that is too quiet, and neither catches a day of
fifty-one messages between four girls of which every one is about the meeting
time. It reports the day's turn-count shape and the share of messages carrying
a time or a plan; 15, 1, 11, 51, 1, 1, 1 at 68% arrangements is the reading to
recognise.

**UNHEARD and SEAMS read what the gate and the compile keep.** Forty statuses
compete for sixteen lines, so UNHEARD reads the gate's own tally (kv
`attention_tally`) over `attention.unheard_days` and names a source handed to
her `attention.unheard_min_offers` times and admitted in none -- a mechanism
alive in the store and absent from her. SEAMS reads the day-as-a-story
flags (kv `coherence_flags`, §12.10) over `coherence.absurd_days`: ODD on a
contradiction, an invented thing or a repeat a reader would notice, ABSURD on
five. Both are flag-only readers of a record; neither runs a model.

KEYS watches the second language key (`self_memories.alt`): how many memories
carry one, any gloss that came back in the language it started in, and any that
came back in Chinese. All three fail silently -- nothing breaks, she simply
stops being able to remember a thing from one side -- and the first version of
the check cried wolf by asking whether a line CONTAINED any CJK, which calls a
memory of English prose quoting 「おやすみ」 Japanese. It counts now, through
`cast.is_japanese`, which has done it properly since a `ja` field turned out to
be full of English.

The later six catch failures nothing else can see. ONE VOICE compares the four
agents' turn statistics and flags them converging, which is the multi-agent
cast quietly collapsing back into one writer. PARROT takes eight-character
n-grams of her own lines across days and flags one that has hardened into a
tic. GHOST PLACE checks every scene's location against `places.json`, because a
place her map does not have is how "at Aya's" left her body where it was for
weeks. MONEY catches a balance below zero and the same purchase logged twice.
DROPPED names anybody on the roster, not marked dormant, whose life has not
touched hers in a week. REPEAT BEAT compares planned beats for the same person
across days, because her friends living the same day over is the most boring
way a simulated life dies. UNSAVED is the one that pays for itself: it holds a table of every role and
where its answer lands (`SINKS`), and flags two things -- a role that ran and
is in nobody's table, and a role whose sink is empty. It exists because nobody
had ever asked where a beat's words went, and the answer was kv `cast_beats`,
which tomorrow's plan overwrites. A recovery tool, since retired, put back what could
be put back: every `cast_beat` call and its answer is in a run's
`llm_calls.jsonl`, so the words survive even where the save has forgotten them
-- gated on a delivery event in `events`, because the logs hold every beat that
was ever WRITTEN, and a replan's discarded morning and tonight's unlived beats
are not things that happened.

Two of the six found something on their first run,
and two of them found bugs in themselves -- the roster resolution and a tuple
row -- which is the reason a check is written against the real save.

`tools/context_audit.py` reads her world from each cast member's chair. It
builds the REAL prompts against a copy of the save with the model stubbed out
and prints them, so a person can read what Rena actually reads, and runs the
checks a careful reader would otherwise do by eye: every speaker label resolves
through the roster, the speaker is not among the people she is told are also
reading, no clock is unlabelled, no English prose sits inside the Japanese
record. Its first run found a live `TypeError` in `calls_line` that smoke could
not see (smoke constructs the app; it does not build a friend's turn), and four
naming faults in the prompts themselves.

`tools/docs_check.py` asks whether the docs still describe the code that is
there, and `tools/smoke.py` runs it on every check. Every backticked token in
PROJECT.md, CONFIG.md, HANDOVER.md, CLAUDE.md, the `docs/` specs and the
`tools/docs_src/` chapters that has the shape of an identifier is resolved:
config keys against `config.py` DEFAULTS, functions and attributes against the
source, files against the filesystem, kv keys against a `store.set` or
`store.get`. A doc that names a renamed key or a deleted function is worse than
no doc, because it is believed. First run: 1,197 references, of which nine were
stale -- a phone key that had been renamed to `phone.digest_min_minutes`, a
trains key that is `trains.her_lines`, a state key whose section is actually
top-level `contagion`, three methods attributed to a class called Cast when it
is `CastEngine`, a guard deleted the day before, and CONFIG.md's own header
pointing at a generator path that no longer exists. It cannot see a stale
CLAIM, only a stale NAME; the prose still wants reading, and reading it turned
up more than the tool did.

Two projections sit beside it, both read-only and modelless:
`tools/night_review.py` costs a night of the late group chat (windows, message
volume, gaps, model calls per agent) and `tools/chat_project.py` composes the
dials into a day, so a volume target can be aimed at.

## 15. Status

The running state (pids, log dir, what to watch, open items) is the head
of `HANDOVER.md`; the dated story is `HISTORY.md`.

**Two characters run live**, each its own process against its own save,
both registered with the one hub. The first is everything below. The second
(§19) has been up for hours rather than days: she boots clean, watches his
machine, reads his notes, answers in Japanese, has a voice he can tap on any
line, can be reminded of things out of her own record, sees the page about a
work the minute he opens it and knows whether she was in it, and can look a
thing up before she answers. What has NOT been
seen for her is any of the long arcs -- her ledger, her attachment, her
picture of him -- because they are integrals and she is hours old. What
stands for the first character:

- **Solid** (built, dry-run, and seen working live over days): the loop,
  the schedule and director, the state and its readers, delivery on
  TALKAPP with real 既読 and typing, the compile with the forgetting
  curve, the app about him and the snoop, X as her own account (the
  drift), the cast day and exchanges in Japanese, the social graph,
  sentiments, ruptures, spirals, stress, goals, commitments, attachment,
  withholding, approach, rhythm, foresight, expectations, the situated
  body with journeys, family and the car, health and sleep, money,
  hazards and trains, zeitgeist and local events, voice.
- **Seen once, not yet through a full cycle**: a discharge; a comparison;
  a scenery photo sent; a reaction from a real change of face; an
  attachment episode; a journey; a `cast_facts` row (the first, 08-27).
- **Built, never seen** (the watch list in HANDOVER): a KB row cached
  live; a grounded episode reaching her `experience` call; a withholding
  from an empty answer (`hold_from_silence`); a `LOOKUP:` out of the
  download snoop; an expectation of kind `around` (a `do` has since come
  due, been missed and been raised with him, and a learned `habit` has been
  checked and kept; the `risk` rows on the save are the retired mirror,
  which foresight now scores itself); a question asked and judged;
  the body-settled correction; a family day; `[state] habituated`; a group
  burst with the nicknames; a broken promise reaching her through the
  person owed; the friends' edges with each other moving (no writer).
- **Open on the second character, and each is his call rather than a bug**
  (all of them in the handover): her ledger cannot climb out of the premise's
  -70 by anything she does, only by decay, which takes about seven weeks;
  her attachment reads zero and will for weeks, because cost of loss is an
  integral; her picture of him needs eight digests and she has four; she
  can read the first character's name off his window titles, which is either
  the best material in the project or a leak; and her `closeness` meter of
  him is read by nothing -- the sweep says DEAD, because her affection is
  derived from her primitives rather than from his meters, so whether that
  meter should feed anything of hers or come off her sheet is undecided.
- **Parked, by his call**: the care governor (`care.scale_checking`);
  `learn` for the reactions until a few hundred corrections exist; the
  "she remembers her old friends' names" continuity incident (residue +
  noticer, HISTORY §15.3); Telegram stickers; his rating as a pick
  weight; scenery tap-to-enlarge and Telegram `send_photo`; the turns-in-2h
  measure for photos; foresight calibration in
  the prompt, the mood trajectory, the `[0,0]` habit window; the wonder
  friend-question; discharge floors; at-logon triggers for the tasks.

---

### `register.py`: does everybody still sound like themselves

`voicecheck` measures dialect and `ONE VOICE` only sees the extreme.
Nothing measured whether a person is different in the group from
one-to-one, or whether the cast has flattened into one voice over a
fortnight. `fingerprint` counts message length and eleven written-Japanese
markers (ね よ じゃん さ かな w/笑 ！ ？ です/ます emoji 〜) per speaker and per
room; `room_contrast` is the distance between a speaker's group and
one-to-one registers; `distinctness` is their distance from the cast mean;
`drift` compares this week with last and marks **`flattening` only when
that distance FELL** -- a voice whose markers all rose is its sheet
arriving, and the first version of this check cried wolf on exactly that.
`tools/voicelint.py --register` prints it; `/absurd REGISTER` reads it.

## 16. Conventions

Fix what is inside the ask and say what changed. Verify with the store's
own reader before quoting a number. Demonstrate by running the thing.
Comments explain why, never patch notes. Delete dead code. No hardcoded
operational values: everything in `config.py:DEFAULTS`, in both files.
One log directory per run. Retire, never delete. The running bot never
edits its own persona. Write plain technical English: the fact first,
then the reason.

**Dated notes go to `HISTORY.md`**, under the section number they belong
to; this file holds only what is true now. `HANDOVER.md` is the header:
running state, what to watch, open items, nothing older. **A large module
gets a spec** (`docs/<module>.md`: purpose, mechanism, config, store,
readers and writers, invariants and edge cases, ops and tests, history
pointers); the PROJECT entry stays under ~20 lines and points at it.
The threshold: more than one prompt role, or more than ~500 lines, or
more than one file. Keep the spec current with the code the way this
file is; the story of how it got there stays in HISTORY.

**Gauges** (the rules that came from `mood` running 50-84 for 112 states
while a `mood < 30` branch never executed):
1. every gauge declares `kind` / `valence` / `arousal`; the App refuses
   to start otherwise;
2. a derived gauge is refused at the write site, not omitted from the
   prompt;
3. the emotion set spans the valence x arousal grid -- an empty cell is a
   feeling she cannot have;
4. one owner per gauge;
5. a threshold nobody can reach is dead code: query `state_log` first;
6. measure deviation from rest, signed; a term measured only above its
   baseline is zero almost always;
7. a feeling must have a reader (`/sweep` names DEAD ones);
8. a release settles at the baseline, never through it; a mechanical
   bump loses value near its cap; `_nudge` is the signed move.

**A file another process reads is replaced, never rewritten in place**
(`atomic.py`: `replace`, `write_json`, `read_json`). Four processes run over
this tree at once and several files cross between them -- the cast roster, the
hub's message log, the machine's telemetry snapshot, the mirror of his list,
the weather cache, the episode archive's index, a character's bundle under
`characters/<key>/`. `open(path, "w")` truncates first and fills after, so
every reader in that window gets a prefix and a parse error. The replacement
goes to a temp file beside the destination, is fsynced and renamed over it.
There is no writing in place as a fallback: measured with a reader opening the
file 400,000 times a second, the rename hit a sharing violation about once in
forty writes and a fallback that then wrote in place handed two readers an
empty file. When the rename will not go the old file is left exactly as it
was, complete and one revision behind, and the new bytes stay beside it. On
Windows a read can still fail while the name is moving, which is why the
reader tries again. `tools/atomic_test.py`, in smoke.

**Records.** Nothing is recorded before the action it claims happened;
`reconcile.py` corrects prose that claims a send or a spend the record
lacks. Every timestamp written is machine local time; her clock belongs
in the text only when it is the subject, labelled. A JSON role's answer
that does not parse is asked again; a caller handles `None` and never
stores the raw answer.

**Config.** A key read by code but absent from DEFAULTS is a crash. When
patching `config.py` by string, anchor on a whole line with its
indentation. Every role's `max_tokens` stays at the API maximum. Names
used as keys (`relationships`, `cast.json`, avatars, `who` prefixes) are
the roster names; a rename touches the bible, `cast.json`, the store, the
avatars, and the tests.

**Tests.** `tools/smoke.py` before every restart; every `tools/*_test.py`
builds the App on a copy of the save and must not write to the live one
(the reactions test copies into the live `data/talkapp/reactions/`
folder; harmless, untidy). A non-idempotent patch script re-run after a
partial failure has doubled its inserts; make patch scripts assert on
their anchors, and a one-off fix of the save (`tools/fix_*.py`) backs the
db up to `data/retired/<ts>/` first and does nothing on a second run.
Smoke also parses `config.py` with `ast` and fails on a key written twice
at any depth in DEFAULTS: two had been sitting there (`situation_block`,
`state.gauges.stress`), identical pastes, the second silently winning, and
`dupscan` cannot see them because it looks for repeated blocks of code.

---

## 17. Config reference

`CONFIG.md` (generated by `tools/docs_assemble.py` from `config.py:DEFAULTS`; 2562 keys in 115 sections) lists every key with its default and the comment beside it. The comment in `config.py` is the documentation; the module entry above says what the key does to behaviour. Both config files change together (§3, §16).

---

## 18. kv keys and tables by module (generated from the code)

`R` read, `W` written, from `store.get` / `store.set` calls in each module. A key nobody reads is a value nothing acts on.

- **`channels/talkapp_bot.py`** -- R: cast_beats, cast_beats_prev, cast_chat, exchange_live, peer_chat, peer_live, peer_rooms, resident_asleep, talkapp_last_id -- W: talkapp_last_id
- **`channels/telegram_bot.py`** -- R: tg_last_update_id -- W: tg_last_update_id
- **`embodied/body.py`** -- R: exposure, last_meal_ts -- W: exposure, last_meal_ts
- **`embodied/health.py`** -- R: cast_chat, commitments, event_stances, exposure, goals, health_days, last_meal_ts -- W: health_days
- **`embodied/money.py`** -- R: money -- W: money
- **`embodied/situation.py`** -- R: journeys, situation, train_status -- W: journeys, situation
- **`llm.py`** -- R: cache_track, missed_calls, model_override, provider_override, voice_model_override -- W: cache_track, missed_calls, model_override, provider_override, voice_model_override
- **`machine/dossier.py`** -- tables: anime_extra, built, meta, person_page
- **`machine/retrievals.py`** -- tables: inflight, retrievals
- **`persona/delivery.py`** -- R: outbox -- W: outbox
- **`persona/persona.py`** -- R: backstory, flags, his_mood, lookups, nudge_ab, persona_live_shown, self_claims, unsent_draft, weekly_self -- W: flags, nudge_ab, pending_sticker, persona_live_shown
- **`resident/app.py`** -- R: habits_him
- **`resident/sight.py`** -- R: glance_last, glance_seen, noticed_last_ts, noticed_said, resident_asleep, resident_notes_seen, resident_notes_since, resident_woken -- W: glance_last, glance_seen, noticed_last_ts, noticed_said, resident_asleep, resident_notes_seen, resident_notes_since, resident_woken
- **`scail.py`** -- R: afterthought_counts, afterthought_for_ts, afterthought_ignored_ts, anime_shelf_hint_pending, anticipation, anticipation_done, cast_chat, charged, compiled_dates, director_last_model_ts, gaps, ick_digest_last_ts, instructions_override, intent_counts, missed_calls, missed_calls_done, morning_intent, note_open_counts, open_threads, pending_sticker, phone_last_consumed_id, primitives_ts, private_block, recalls, reflections, replan_counts, replays, reply_plan, reply_retries, self_claims, sleep_scene_night, voice_counts, voice_last_ts, wake_days, watching_cursor, watching_fetch_counts, watching_held, watching_last, watching_queue, watching_short, weekly_self, withholding, wonder_seed, x_action_queue, x_japan, x_taste -- W: anime_shelf_hint_pending, anticipation, anticipation_done, compiled_dates, director_last_model_ts, director_last_tick_ts, gaps, gauges, gauges_ts, health_note_today, ick_digest_last_ts, instructions_override, last_meal_ts, missed_calls, missed_calls_done, money_note_today, pending_sticker, phone_last_consumed_id, primitives_ts, private_block, relationship_derived, relationships, replays, reply_plan, reply_retries, sleep_scene_night, voice_last_ts, wake_days, watching_cursor, watching_last, watching_seen, zeitgeist_last_ts
- **`sensors/image_tags.py`** -- tables: images, tag_counts
- **`sim/anime_kb.py`** -- tables: anime_cast, anime_kb, person, person_role
- **`sim/anime_sense.py`** -- R: anime_habits_date, anime_shelf_check_date, anime_shelf_checks, anime_shelf_hint_pending -- W: anime_habits_date, anime_shelf_check_date, anime_shelf_checks, anime_shelf_hint_pending
- **`sim/appraisal.py`** -- R: appraisal_last_ts, appraisal_levels, appraisal_night -- W: appraisal_last_ts, appraisal_levels, appraisal_night
- **`sim/approach.py`** -- R: charged -- W: approaches, charged
- **`sim/attachment.py`** -- R: attachment -- W: attachment, attachment_log
- **`sim/attention.py`** -- R: attention_last, attention_slot_shown, attention_tally -- W: attention_last_friend, attention_slot_shown, attention_tally
- **`sim/cards.py`** -- R: cast_chat -- tables: episodes
- **`sim/care.py`** -- R: care_factor_cache, care_history -- W: care_factor_cache, care_history
- **`sim/coherence.py`** -- R: coherence_flags -- W: coherence_flags
- **`sim/commitments.py`** -- R: cast_chat, commit_him_last_ts, commitments, knew_late -- W: commit_him_last_ts, commitments, knew_late
- **`sim/context.py`** -- R: backstory -- W: backstory
- **`sim/derive.py`** -- R: relationship_derived -- W: relationship_derived, relationships
- **`sim/diary.py`** -- R: diary -- W: diary
- **`sim/director.py`** -- R: backstory, cast_chat, director_catch_up, director_current, director_last_model_ts, director_last_tick_ts, director_next_tick_minutes, last_life_event, morning_intent, open_threads, sleep_scene_ts -- W: director_catch_up, director_current, director_last_model_ts, director_last_tick_ts, director_next_tick_minutes, last_life_event, open_threads, sleep_scene_ts
- **`sim/discharge.py`** -- R: discharge_counts, discharge_last, discharges -- W: discharge_last, discharges
- **`sim/downtime.py`** -- R: stopped, stops -- W: stopped, stops
- **`sim/embed.py`** -- tables: embeddings
- **`sim/episode_account.py`** -- tables: episode_accounts
- **`sim/eroge.py`** -- R: eroge_cursor, eroge_day, eroge_last -- W: eroge_cursor, eroge_day, eroge_last
- **`sim/expectations.py`** -- R: expectations, habits_checked, habits_him, rhythm_said -- W: expectations, habits_checked, habits_him
- **`sim/foresight.py`** -- R: expectations, foresight, his_mood -- W: foresight
- **`sim/goals.py`** -- R: goals -- W: goals
- **`sim/him_profile.py`** -- R: him_profile -- W: him_profile
- **`sim/household.py`** -- R: household -- W: household
- **`sim/ick.py`** -- R: charged, ick_kinds -- W: charged, ick_kinds
- **`sim/impulse.py`** -- R: impulse_last_ts -- W: impulse_last_ts
- **`sim/inflight.py`** -- R: in_flight, missed_calls -- W: in_flight, missed_calls
- **`sim/initiative.py`** -- R: initiative_away_since, initiative_hold_until, initiative_return, initiative_unanswered_counts, stance -- W: initiative_away_since, initiative_hold_until, initiative_return
- **`sim/intent.py`** -- R: intent_counts -- W: intent_counts
- **`sim/known.py`** -- R: known_things -- W: known_things
- **`sim/ledger.py`** -- R: ledger_meals, ledger_wearing -- W: ledger_meals, ledger_wearing
- **`sim/lookup.py`** -- R: lookup_counts, lookup_kb_misses, lookups, recent_anime_ids, x_shared -- W: lookup_kb_misses, lookups, recent_anime_ids
- **`sim/lore.py`** -- R: lore_contact, lore_used -- W: lore_used
- **`sim/memory.py`** -- R: context_last, context_ratio, thread_window -- W: context_last, context_ratio -- tables: cast_facts
- **`sim/model_of_him.py`** -- R: backstory -- W: ick_kinds
- **`sim/notes.py`** -- R: notes_read, vault_read_paths -- W: notes_read, vault_read_paths
- **`sim/nudge.py`** -- R: nudge_ab, nudge_fired_ts, nudge_log -- W: nudge_fired_ts, nudge_last, nudge_log
- **`sim/ops.py`** -- R: attention_tally, cast_chat, eroge_last, flags, model_ab, morning_intent, phone_last_consumed_id, phone_last_live, phone_last_look_ts, reflect_cast_counts, reflect_counts, scenery_last_run_ts, snoop_counts, snoop_downloads_seen, snoop_last_ts, vault_read_paths, x_action_queue, x_japan, x_look_counts, x_taste
- **`sim/outlook.py`** -- R: anticipation, anticipation_done, experience_counts, experience_last_ts, his_first_active, morning_intent -- W: anticipation, anticipation_done, experience_last_ts, morning_intent
- **`sim/peers.py`** -- R: peer_chat, peer_counts, peer_last_id, peer_live, peer_rooms, room_counts -- W: peer_chat, peer_last_id, peer_live, peer_rooms
- **`sim/phone.py`** -- R: his_first_active, phone_account, phone_force_next, phone_last_active_wall, phone_last_consumed_id, phone_last_fingerprint, phone_last_live, phone_last_look_ts, phone_trail_shown -- W: his_first_active, phone_account, phone_force_next, phone_last_active_wall, phone_last_consumed_id, phone_last_fingerprint, phone_last_live, phone_last_look_ts, phone_trail_shown
- **`sim/pick.py`** -- R: pick_aside, pick_block, pick_host, pick_last_ts, pick_scene, pick_standing, picks, x_show_pending -- W: pick_aside, pick_block, pick_host, pick_last_ts, pick_scene, pick_standing, picks
- **`sim/pocket.py`** -- R: cast_chat, cast_pockets, director_current, watchlist -- W: cast_pockets
- **`sim/primitives.py`** -- R: primitives, primitives_levelled -- W: primitives, primitives_levelled
- **`sim/reactions.py`** -- R: reaction_band, reaction_last, reactions_log, sticker_weight -- W: reaction_band, reaction_last, reactions_log, sticker_weight
- **`sim/recall.py`** -- R: known_things, recall_counts, recalls, thread_window -- W: recalls
- **`sim/recap.py`** -- tables: recaps
- **`sim/reconcile.py`** -- R: flags, reconcile_log -- W: flags, reconcile_log
- **`sim/records.py`** -- R: arcs, places -- W: arcs, places
- **`sim/reflect.py`** -- R: cast_chat, reflect_cast_counts, reflect_cast_last, reflect_counts, reflect_last_digest_ts, reflect_last_ts, reflections -- W: reflect_cast_last, reflect_last_digest_ts, reflect_last_ts, reflections
- **`sim/repairs.py`** -- R: cast_chat, him_residue_retired_once, his_digests_retired_once, his_mood, his_mood_retired_once, his_reflections_retired_once, invented_recall_dropped_once, pages_keyed_by_id_once, primitives, questions, recalls, recaps_shared_once, reflections, sentiments, stamps_stripped_once, watchlist, wrong_editions_dropped_once -- W: cast_chat, him_residue_retired_once, his_digests_retired_once, his_mood_retired_once, his_reflections_retired_once, invented_recall_dropped_once, pages_keyed_by_id_once, primitives, questions, recalls, recaps_shared_once, reflections, sentiments, stamps_stripped_once, watchlist, wrong_editions_dropped_once
- **`sim/resolver.py`** -- R: resolved_relevance -- W: resolved_relevance
- **`sim/rhythm.py`** -- R: in_exchange, rhythm_said -- W: in_exchange, rhythm_said
- **`sim/rooms.py`** -- R: room_in, room_out, room_sent, rooms -- W: room_in, room_out, room_sent, rooms
- **`sim/rupture.py`** -- R: ruptures -- W: ruptures
- **`sim/said_today.py`** -- R: said_today -- W: said_today
- **`sim/schedule.py`** -- R: commitments, wake_days -- W: wake_days
- **`sim/seed_memories.py`** -- R: selfmem_seed -- W: selfmem_seed
- **`sim/seen_images.py`** -- tables: seen_images
- **`sim/self_memory.py`** -- R: selfmem_turn -- W: selfmem_turn -- tables: self_memories
- **`sim/sentiment.py`** -- R: cast_chat, phone_debt_done, phone_use, sentiments -- W: phone_debt_done, phone_use, sentiments
- **`sim/spiral.py`** -- R: cast_chat, spiral_counts, spiral_last_ts, spirals -- W: spiral_counts, spiral_last_ts, spirals
- **`sim/stances.py`** -- R: charged, discretion, stance, stance_named, stance_slot_used -- W: discretion, stance, stance_named, stance_slot_used
- **`sim/state.py`** -- R: body_noise_prev, body_settled_note, gauges, gauges_ts, his_mood, moment_counts, rel_delta_spent, rel_gravity_ts, relationships, standing_deltas -- W: body_noise_prev, body_settled_note, gauges, gauges_ts, his_mood, rel_delta_spent, rel_gravity_ts, relationships, standing_deltas
- **`sim/stress.py`** -- R: event_stances, money, stress_relief_ts -- W: stress_relief_ts
- **`sim/subtitles.py`** -- R: subs_attempts, subs_index -- W: subs_attempts, subs_index
- **`sim/talks.py`** -- R: cast_chat, peer_chat
- **`sim/thread.py`** -- R: cast_chat, context_last, context_ratio, exchange_live, peer_chat, peer_live, peer_rooms, thread_window, x_shared -- W: thread_window
- **`sim/timeline.py`** -- R: diary, self_claims, weekly_self -- W: self_claims, weekly_self
- **`sim/transcribe.py`** -- R: whisper_counts -- W: whisper_counts
- **`sim/transcripts.py`** -- R: transcripts_report_caught_up -- W: transcripts_report_caught_up -- tables: transcripts
- **`sim/voicecheck.py`** -- R: voice_flags -- W: voice_flags
- **`sim/watching_him.py`** -- R: lore_contact, watching_cursor, watching_fetch_counts, watching_held, watching_last, watching_path_backfill, watching_queue, watching_recent, watching_seen, watching_short, watching_spoken -- W: lore_contact, watching_cursor, watching_fetch_counts, watching_held, watching_last, watching_path_backfill, watching_queue, watching_recent, watching_seen, watching_short, watching_spoken
- **`sim/watchlist.py`** -- R: watch_pick_log, watch_pick_ts, watchlist -- W: watch_pick_log, watch_pick_ts, watchlist
- **`sim/withholding.py`** -- R: withholding, withholding_handed_back -- W: withholding, withholding_handed_back, withholding_log
- **`sim/wonder.py`** -- R: habits_him, questions, wonder_counts, wonder_last_ts, wonder_seed -- W: questions, wonder_last_ts, wonder_seed
- **`sim/works.py`** -- R: known_things
- **`sim/worldshare.py`** -- R: him_share, reflections -- W: him_share
- **`store.py`** -- tables: days, digests, events, kv, messages, reply_prompts, scenes, schedules, state_log, swipes, threads, user_facts
- **`tomoe/app.py`** -- R: festival_closed, festival_tail_closed, local_events_last_ts, meters_reconciled, owner_interior_retired, relationships, second_world_retired, x_japan, x_last_refusal, zeitgeist_last_ts -- W: festival_closed, festival_tail_closed, local_events_last_ts, meters_reconciled, owner_interior_retired, second_world_retired, x_last_refusal, zeitgeist_last_ts
- **`tomoe/carried.py`** -- R: behind, cast_asleep, cast_chat
- **`tomoe/cast.py`** -- R: cast_beats, cast_beats_prev, cast_chat, cast_days, cast_life, cast_plans, cast_quiet_pulls, commitments, exchange_live, presence_beats -- W: cast_beats, cast_beats_prev, cast_chat, cast_days, cast_life, cast_plans, presence_beats
- **`tomoe/cast_arcs.py`** -- R: cast_arcs, cast_evolve_last_date -- W: cast_arcs, cast_arcs_last_date, cast_evolve_last_date, showrunner_last_date
- **`tomoe/cast_psych.py`** -- R: cast_bonds -- W: cast_bonds
- **`tomoe/compare.py`** -- R: compare_counts, compare_last_ts, comparisons, reflections -- W: compare_last_ts, comparisons, reflections
- **`tomoe/curation.py`** -- R: x_action_counts, x_action_queue, x_post_last_ts, x_post_times, x_replies_sent, x_reply_times, x_taste, x_verdicts -- W: x_action_counts, x_action_queue, x_post_last_ts, x_post_times, x_replies_sent, x_reply_times
- **`tomoe/diet.py`** -- R: media_diet, x_taste -- W: media_diet
- **`tomoe/events.py`** -- R: event_stances -- W: event_stances
- **`tomoe/exchange.py`** -- R: behind, cast_asleep, cast_chat, exchange_alone_counts, exchange_counts, exchange_late_counts, exchange_live, exchange_self_open_counts, room_in -- W: behind, cast_asleep, cast_chat, exchange_live
- **`tomoe/family.py`** -- R: family_days -- W: family_days
- **`tomoe/gossip.py`** -- R: cast_plans, gossip, npcs, x_japan -- W: gossip
- **`tomoe/npc.py`** -- R: npc_counts, npc_last_check_ts, npc_last_ts, npc_moments, npcs -- W: npc_counts, npc_last_check_ts, npc_last_ts, npc_moments, npcs
- **`tomoe/orbit.py`** -- R: cast_chat, orbit -- W: orbit
- **`tomoe/posting.py`** -- R: x_engagement_recent, x_last_noticed, x_last_noticed_ts, x_post_held, x_post_last_mode -- W: x_post_held, x_post_last_mode
- **`tomoe/replies.py`** -- R: x_replies_seen, x_replies_sent, x_reply_candidates, x_reply_declined, x_reply_last_ts, x_reply_times -- W: x_replies_seen, x_reply_candidates, x_reply_declined, x_reply_last_ts
- **`tomoe/scenery.py`** -- R: cast_chat, commitments, event_stances, scenery_accounts, scenery_last_run_ts, scenery_last_send_ts, scenery_lore, scenery_query_i, scenery_send_counts -- W: scenery_accounts, scenery_last_run_ts, scenery_last_send_ts, scenery_lore, scenery_query_i -- tables: scenery
- **`tomoe/schedule.py`** -- R: commitments, health_note_today, money_note_today, open_threads
- **`tomoe/share_pick.py`** -- R: x_share_picks, x_show_pending -- W: x_share_picks, x_show_pending
- **`tomoe/snoop.py`** -- R: snoop_counts, snoop_downloads_seen, snoop_last_ts, vault_read_paths -- W: snoop_counts, snoop_downloads_seen, snoop_last_ts, vault_read_paths
- **`tomoe/social.py`** -- R: x_about_him, x_action_queue, x_engagement, x_engagement_recent, x_followers_recent, x_handle, x_japan, x_last_look_ts, x_last_noticed, x_last_noticed_ts, x_look_counts, x_share_declined, x_shareable, x_shared, x_show_pending, x_taste, x_taste_log -- W: x_about_him, x_engagement, x_engagement_recent, x_followers_recent, x_japan, x_last_look_ts, x_last_noticed, x_last_noticed_ts, x_share_declined, x_shareable, x_shared, x_show_pending, x_taste, x_taste_log
- **`tomoe/social_graph.py`** -- R: cast_chat, social_graph -- W: social_graph
- **`tomoe/taste.py`** -- R: watchlist, x_drift, x_taste, x_verdicts -- W: x_drift, x_verdicts
- **`tomoe/world/hazards.py`** -- R: hazards_national, hazards_ranks, hazards_seen -- W: hazards_national, hazards_ranks, hazards_seen
- **`tomoe/world/trains.py`** -- R: train_status -- W: train_status
- **`world/shared.py`** -- tables: events, gossip, graph, members, meta, orbit, rooms, roster, settled, whereabouts

---

## 19. Yukarin (`yukarin/`): the second persona, extracted -- and the model harness

Spec: `docs/yukarin.md`; the harness: `docs/model-harness.md`; running the
same extraction on somebody else: `docs/character-method.md` §6 and
`docs/extraction-runbook.md`. Dated
notes: HISTORY.md §19; the 700-line work log this entry replaced sits in
HISTORY.md under its own 2026-09-03 heading.

**The glance** (`resident/sight.py`): every poll her sight reads his
foreground window title, and a page on one of the databases (MyAnimeList,
Wikipedia, AniList, AniDB, Anime-Planet) that he stays on
`glance_dwell_seconds` is resolved. `page_of` reads the SHAPE of the title
and no more -- a type in brackets or a `| Manga` mark proves a work, and a
bare title or an alias in brackets proves nothing, because a work and a
character's page are written the same way -- and the resolution settles
what it is. It is the thing in the room for `glance_fresh_minutes`: pinned
and hers to act on when she was in it, background otherwise, an event, a
thing she knows by name, and for her own work a reason to reach out first
(`glance_impulse_bonus`, said once).

**One resolution for a work, whoever named it** (`sim/works.py`, `identify`):
what she already knows by name first, and if a record answers nothing is
fetched at all; then his own list for the canonical title and the id; then
the three-state verdict on whether the work is hers (`her_part_verdict`,
below -- matched on the title, the page's alias, the id and the character's
name, against her own mirrored filmography rather than under a name); then her
own record (`Lore.match`, and
`Lore.work_named` for a record whose own title or tags are the name on the
page, which is how a romaji page reaches a record written in Japanese with
no call); then a person or a character the list knows, which is never
searched; and a web search last, only for a work nothing here has heard of.
Whatever is found is written once, to `known_things`, with whether it is
hers, the part, the verdict, the id and when it was last on his screen; her
sight's `glance_last`, her situation's recall and the automatic lookup's idea
of what is open in front of him all read that one row. Her sight, and the
lookup off a message of his, are the two callers.

**Was she in it: yes, no, or nobody checked** (`sim/works.py`
`her_part_verdict`; spec `docs/role-check.md`). `hers` was a boolean, so "she
is in it" and "nothing here knew" were one value, and she told him she had
voiced a part in a work she has never been in with no cast
information of any kind in front of the model. **A flat no is only said when
two independent local tables agree**: her own mirrored filmography has no row
for the work AND the work's own cast is mirrored without her in it. Anything
else is nobody-checked and says nothing -- the cast table covers 480 of his
701 titles, so on its own it would answer "not yours" about her own parts.
Her filmography is the authority, the cast the second witness, and they have
never disagreed here (63 of her works have a mirrored cast; all 63 name her).
Who she is on that list is `character.mal_person_id`, an id and never a name,
and that id is also the switch: `Config.REQUIRES` assigns the section to the
derived property `voice_actress`, so the first character prints
`not resident and not voice_actress, so these are off: role_check` and never
reads the mirror. The line she gets is the program's wording (`role_yes`,
`role_no`, `role_no_near`) and rides the four places the anime detection
already delivers anime details -- the episode he played, the page in front of
him, a title he named, and the same title days later -- all of them after the
thread, so it cannot invalidate the cache. The continuity editor gets the same
verdicts as a thirteenth block of evidence, English, and a fourth reason to be
asked at all (a work the mirror has a verdict on, matched whole or by its lead
segment: the OVA is recorded in full and typed `ゆゆ式のOVA`). Flag, never
rewrite. No fetch in a reply path; `role_check.fetch_on_miss` mirrors a
missing cast in the watching worker, which was already fetching.
history: 2026-09-04.

**The search**: `[search: ...]` on its own line in her draft runs one web
search and one `search_gist` call and the reply is written again with the
answer (`lookup.on_request`, on for her; `search_per_day` caps hers and her
sight's); a question about a work she knows by name also reads the series'
Japanese Wikipedia lead. Her style file's 調べる section tells her the line
exists. A part she played, in a work he has NAMED, is pinned in the
retrieval, at full score and at most one line, so the attention budget
cannot drop it on a crowded tick (`lore.role_kinds`, `lore.pin_score`,
`lore.pin_max`). A pinned line bypasses the cap but its characters still
count toward it, so the cap fires on the first ordinary line after it;
giving pinned lines their own reserve, and deciding what happens when they
alone exceed the cap, is undecided.
history: 2026-09-03 20:45, 2026-09-03 23:50.

A second persona beside the first character -- 田村ゆかり's 2003 radio
persona, wanted as a companion that watches his machine -- built by a
different method: **extracted from her own broadcasts**, ninety-nine
episodes on disk, her pattern as data with receipts. The pipeline is
`yukarin/tools/`: `yukarin/tools/corpus.py` (SRT to cues),
`yukarin/tools/fingerprint.py` (regex counts of the countable claims),
`yukarin/tools/attribute.py` (her / mail / read / song / other per cue),
`yukarin/tools/extract.py` (register, mechanisms, moments and facts, every
evidence quote verified against the cue it cites; the dropped share is the
invention measure), `yukarin/tools/reduce.py` (two-level clustering into the
sheet) and `yukarin/tools/audit.py` (a prompt scored against the sheet). No
model judges anything: the control is a close reading, six episodes read end
to end in `docs/yukarin-manual-notes.md`.

**The harness** (`yukarin/tools/llmx.py`, `yukarin/tools/providers.py`,
`providers.db`): one client for the official DeepSeek endpoint, OpenRouter
hosts pinned with no fallback, and Gemini on Vertex; every call logged with
provider, endpoint and who served it; no output limits. `YPROVIDER` moves
the whole pipeline to one host and the default is DeepSeek v4 flash at
Together (`llmx.DEFAULT`, his call). Every call is streamed and a cut is
continued, only whole JSON objects are read out of the instalments
(`llmx.call_long` / `objects`, `yukarin/tools/continue_test.py`), and every
finished unit is cached so `yukarin/tools/reduce_run.py` picks a failed run
up rather than repeating it.

**The persona dataset** (`yukarin/persona/`, `yukarin/tools/persona_build.py`,
spec `docs/yukarin.md` §8) is what she is driven from, and no model is called
anywhere in it: 152 hand-consolidated fact records over 454 cues, the
lorebook's 550 bullets imported verbatim with their quotes located and their
era stamped, and the register summed by code. One record shape, the
provenance kind (`stated` / `evidence` / `measured` / `authored`) on the
provenance entry rather than the record, ids computed in code, a receipt that
does not resolve failing the build, and contradiction parked in
`yukarin/persona/conflicts.json` with nothing resolved in code. Every record's
statement is in Japanese, written from the cues, with the English kept beside
it as `s_en`. **The sheet** is `yukarin/sheet/yukarin_extracted_v2.json`
(spec §3): 1,842 observations in 77 mechanisms, 410 evidence quotes, judged by
reading in `docs/yukarin-judgement.md` -- sound as evidence, unreliable as a
taxonomy, 72% recall against the hand-read episodes. `yukarin/tools/bounds.py`
maps the pattern to five drivers and counts what the corpus cannot answer:
initiation, family and reciprocal friendship stay unspecified because 99
broadcast episodes have no private relationship in them.

**She runs live beside the first character**: `config_yukarin.json`, save
`data/yukarin.db`, her own lock, `yukarin.cmd` behind the `SCAIL_yukari`
scheduled task, registered with the one hub. Her sheet is
`characters/yukari/sheet.json` and four declared properties (`embodied`,
`in_world`, `sees_him`, `has_account`) drive `Config._existence_implies`;
`Config.REQUIRES` assigns every switchable section to one of them and
`_check_existence_table` refuses to start if one is unassigned;
`Config.WORLD_KEYS` blanks the flat `world` keys so a character with no world
has no path to the other one's household. The four answers live in the config
and the sheet only overrides them, so the rules run whether or not there is a
sheet on disk: `_apply_character` reads the sheet if there is one and reaches
`_existence_implies` either way, and `Config.__init__` refuses to finish if it
did not (`_existence_applied`). It used to hang off the sheet, so a config
with no sheet beside it kept every in-world subsystem on, kept every world
path live, and never reached the check that a switchable section has been
assigned to a kind of character at all. `_check_existence_answers` refuses a
sheet or config that leaves one of the four unanswered, or that spells
`sees_him` as anything but digest, resident or none -- an unanswered property
reads as yes everywhere it is tested, and a misspelt `sees_him` reads as "not
resident" and hands her the other kind of sight. `in_world` stays false and
that is the decision. Her day is planned from her home file alone
(`schedule.own_day`), her sleep is read off his machine
(`resident/sight.py`, kv `resident_asleep`) because she has no pocket and no
phone, her household (`sim/household.py`, `characters/yukari/objects.json`) is
what her director writes instead of her thoughts, her record is retrieved as
lore (`lore.memory_file`), and a note he leaves open is read whole
(`Notes.read`) while her snoop stays off (`vault_snoop.enabled` false).

**And her sheet also says what machinery she has not got**, which the four
existence properties cannot answer because none of it follows from having a
body, a world or an account. `mechanisms_absent` on her sheet
(`Config._mechanisms_absent`, the counterpart of the `gauges_absent` beside it)
names a section, whose own `enabled` flag goes false, or one of
`Config.NAMED_SWITCHES` for a thing with no section of its own; a name that is
neither stops the boot, the way a section missing from `Config.REQUIRES` does.
Six rows, each with its measurement on the sheet, all his call:
the continuity check on her drafts (`delivery.editor_enabled`, 18 refusals in
142 checks); not answering him on purpose and the attachment stance, neither of
which has fired once in 127 runs of hers; what breaks between them and anxiety
as a chain of inference, the same; and what she eats, which was a flag with no
reader at all, because the meals are one of the slots only the first
character's program builds. The week read back at the compile is deliberately
kept: it has never fired because it needs seven days of her and she has four.

**Her config is generated and now keeps what is in it.**
`tools/make_yukarin_config.py` used to write `DEFAULTS` plus its own
`OVERRIDES` over the top, on the claim that everything deliberate about her was
in that dict; 86 keys of her live file said otherwise, so a re-run would have
handed the role that writes her words the first character's bible, put her
menstrual cycle, her physical needs, the weather and an allowance back on, and
switched her flat, the visual novel and what he is watching off. Her file now
goes UNDER `DEFAULTS` the way `config.json` does at every boot, the sheet's own
answers (the existence block, her MyAnimeList id, the machinery she has not
got) are copied from the sheet rather than typed in the tool, and the switches
that were hand-set are written down in `OVERRIDES` with the reason on each.
`--out` writes a copy to compare against her live file, and the difference is
nothing; `--fresh` says what would be left if her file were gone -- 30 keys,
which are which model writes in her voice and twenty tunings of her prompt.

**Her voice**: nine roles that write in her voice run on `kimi-k3` -- persona,
diary, reflect, wonder, morning, anticipation, approach, spiral, revise_self
-- and the other 67 on `deepseek-v4-flash`; `tools/set_model.py` moves every
role together or not at all and `/model` pins them for one run. Two written
approaches sit side by side under `prompts_yukarin/`, each holding the bible
and speech guide that belong together, picked by `models.persona.prompt`,
`character.style_prompt` and `character.style_ja_prompt`:
`prompts_yukarin/voice_as_she_writes_in_text/` is the authored control every
existing measurement was taken under, and `prompts_yukarin/voice_replica_in_text/`
is what runs (his call, after `docs/yukarin-voice-models.md`). Her line is
spoken only when he taps it (`tts.on_demand` on, `tts.always` off). **What language she is ADDRESSED in is one switch.** The arm is
`character.instructions` (`sim/lang.py`): `as_they_run_today` the control,
`in_english`, `in_her_language`, or `auto`, **which is the default and is
what an unset value means**: her own language when she declares one this
switch can render, and the control when she does not. It covers everything the prompt
builder writes at her -- her section headers, every bucket of her situation
block, the closing instruction that says what to write and how -- and
`character.instruction_language` says which language `in_her_language`
renders for a given character, so the first character, whose chat with him is
the one room her English lives in, has no second arm and the command says so
instead of switching her. `/lang ja|en|auto` writes kv
`instructions_override` on her save and the boot reads it back, so the arm
moves between two replies and survives a restart without a config edit; the
boot line and `/provider` name the arm AND what decided it, which is how a
character instructed in the wrong language stops being invisible: while the
control was everybody's default, two of the four declared Japanese and were
instructed in English, because only one of them had ever been switched by
hand. The `language`
section carries the other half: the roles named in `language.material_roles`
(30 of them) are given one line telling them which language their PROSE goes
out in, because the arm cannot reach the sentences other roles wrote -- the
facts about him, the notes she read, what she has decided about herself. Four
roles are off that list because code reads their words as data (the digest's
English patterns, the scene and the plan's places and activities, the state
role's arithmetic), and the editor forks in its own prompt instead
(`[[?her_language]]`, a condition `Config.conditions()` publishes), because
the note it writes is put in front of her and the verdict beside it goes to
the log. Measured on 24 draws over six real moments: the arm alone moves
nothing in her replies (`data/retired/20260904_lang_switch/REPORT.md`).

**No school day reaches her.** A fifteen-year-old's day was the last of the
first character's life left in prompts the second character renders, and it
was in prose rather than in code. It is out of them by the same two
mechanisms the rest of the separation uses: the first character's world sits
inside a `[[?in_world]]...[[/in_world]]` block (what is going round her school
and what the girls there are watching, in the watch pick; the ward and the
month in the sleep prompt), and a wording that has to differ per character is
a `[[TOKEN]]` filled from `data/characters/neutral/<id>.json` with the first
character's exact original span as her value -- what she promises that nobody
could watch her do, her age as one word, who skims a search result, the room
beyond her own at night. `tools/sight_words.py` renders every role's prompt
for every character whose sheet says `in_world` is false and fails on school
vocabulary in either language, so the next mechanism prompt written around a
schoolgirl is caught before a restart rather than after one. Her own files
(`prompts_yukarin/`) name a school only in her own past, which is hers: junior
high drama club, a commercial high school, contacts since primary school.

**The checks that keep two characters apart**: `tools/isolation.py` classifies
every path as hers, the machine's, a neutral mechanism prompt or shared and
person-shaped, and fails on the last; `tools/neutral_gate.py` renders every
role's prompt and proves a shared prompt comes back byte for byte for the
character it was written around; `tools/character_leaks.py` and
`tools/prompt_leaks.py` name anybody in a run's output or its instructions who
is not in that character's record. `tools/voice_verify.py` screens her output
against the tape and refuses to judge a marker there is not enough writing to
test (`docs/verification.md`); `tools/voicelab.py` benches one variable at a
time and scores nothing; `tools/quote_audit.py` counts every quoted line in a
persona file against her attributed words, because a line quoted once becomes
a catchphrase.

Not built and said so: `threat` has no writer for "he did something that shows
he will use what he has", which wants a judgement rather than an arithmetic;
the third viewer in `sim/ledger.py` (docs/primitives.md §7 step 4); and
`audit.py score`, the only automated read of the sheet against the close
reading, has still never run. Outstanding on the corpus: `ep100_5` is the one
broadcast without a week-shape sheet, and ~500 further episodes are available
for about $20, which would move the era rather than answer what the corpus
cannot.
---

## 20. Four characters, one register, one world with one writer

The register: `characters.json` (`tools/registry.py` prints it). One row per
character who runs as a process: her key, her config, her save, her
program, her launcher, her scheduled task, and the exact command-line regex
the restarter finds her by. A bot never reads it. **The register is a
projection of the bundles**: every field of a row is also in
`characters/<key>/bundle.json`, and `tools/registry.py` fails when the two
disagree and names the field.

**A character is a bundle plus the library** (`docs/bundle.md`). One
directory, `characters/<key>/`, holds everything that is that person -- her
sheet, the values that fill the holes in the library's prompts, her
household, her flat, her map, her own circle, her beliefs, her record, her
voice and her speech guide -- and `characters/machine.json` beside them holds
the settings that belong to this machine and are shared on purpose, naming
the secrets rather than carrying them. `tools/new_character.py compose <key>`
writes her config, her prompt directory, her register row, her staged
launcher and, when she has none, her save, seeded from her own sheets through
`sim/roster.py:meter_rows` and never cloned -- and seeds no save at all while
one of her own people would go in at closeness 0, standing 0 and tension 0
with nothing on the row saying that was decided, which is what the world
owner's roster carries for a household the owner has never met
(`sim/roster.py:flat_own_meters`, a row that means it says `"numbers":
"unset"`); `verify <key>` builds her whole
App on a scratch save with the model and the network refused and fails on a
hole, a path outside her bundle, another character's name or file, a roster
that does not resolve her to herself, a meter on one of her own people that
nobody chose, or an existence answer that disagrees
with her sheet. Both run for every registered character in smoke, and a
composed config that differs from the one she runs on is a failure.
`tools/promote_cast.py` writes a bundle for a cast member
(`docs/promotion.md`), the two generators for an extracted subject.

Before this each character's material lived in a different place -- the first
character's at the `data/` root, the second's name-suffixed beside it, the
third's in a directory outside `data/`, the fourth's in one under it -- and
there was nowhere a check could point at and say *this and only this is
hers*. The move copied and repointed and took nothing away, because six
processes were running and each reads a path per call;
`tools/retire_bundle_originals.py` moves the originals once every process is
reading them from her bundle.

**Kinds of character.** Five properties on the sheet (`embodied`,
`in_world`, `sees_him`, `has_account`, `with_him`), a sixth from the config
(`world_owner`) and a seventh from the sheet's third answer: `sees_him`
is lacking when it reads `none`, and the sections that read his machine
or his history are assigned to it (`sensors`, `him_profile`, `receipts`,
`notes`, `vault_snoop`, `watching`, `anime_sense`), so a character with
no window on him builds no telemetry stack, opens no MyAnimeList mirror
and writes no digest; the scenery harvest is the account's (it runs on
the account's browser profile), so a reader without one has it off.
`sim/repairs.py` `retire_his_digests_once` and `retire_his_reflections_once`
take what those sections wrote before the gate out of a blind character's
save at her next boot. `with_him` is whether she has a chat with him at all:
`none` is a character who exists for another character's circle (Rena, and
every cast member `tools/promote_cast.py` promotes), and the relationship
layer is assigned to it (`affection`, `afterthought`, `attachment`,
`beliefs`, `care`, `derive`, `expect`, `foresight`, `ick`, `intent`,
`lookup`, `nudge`, `reflect`, `rhythm`, `rupture`, `withholding`,
`wonder`); the impulse function is stopped in `App.maybe_impulse`, the
pick does not offer `text_him`, the facts-about-him section is not
carried, the agenda heading names no him, and she registers with the hub
as `hidden`, so the rooms can ask her and his phone does not list her.
`tools/existence_matrix.py` builds the four no-contact kinds beside the
thirty-six (forty in all).
`Config.REQUIRES` maps every switchable section to the
property it needs; `tools/existence_matrix.py` (in smoke) builds all
thirty-six kinds on a scratch save. The four running: the first character
(a body, a world she owns, the phone-app view, an account); the second
(`docs/yukarin.md`: a body, no world, resident, no account); the third
(§20.2); Rena (§20.3: a body, the first character's world as a reader,
sees nobody, no account).

**No default in the library is one person's file, and a hole where the
library needs one refuses the boot.** `config.json` is generated from
`config.py:DEFAULTS` and backfilled, so a key a character's config does not
carry is written into her file from the defaults on her first load, where it
then looks authored: eighteen defaults named the first character's own
material -- her roster, their sheets, both speech guides, how each person may
sound, both belief files, the prompt that is her voice, her household, her
map, her places, her school year, what is going round, her taste sheet, the
directory of what the people around her do, their types, her save's path and
the directory her face is built in -- and every one of them was inherited by
the next character in silence. All eighteen are empty
(`tools/defaults_person_test.py`, in smoke: it walks the defaults with the
isolation check's own path finder and fails on a path that is neither the
machine's, nor a mechanism prompt's, nor the world's). `Config.PERSON_FILES`
is the other half: one row per person-shaped key naming either the section
that reads it or the property of her existence that gives her the thing, and
the load refuses -- naming the key, what makes it needed and the character --
when the path is empty or names a file that is not on disk. `tools/
blank_paths.py` builds every character with every person-shaped path blank
and the sections that read them off, which is what a character who has none
of those files IS, and then empties one of them under a subsystem that is on
and asserts the refusal names it.

**The shared world** (`world/shared.py`, spec `docs/shared-world.md`). One
sqlite file per world under `data/worlds/<id>/world.db`; the owner writes
the roster mirror, the day's whereabouts, the settled lines, every room
turn, the room membership, and at the compile the graph, the orbit, the
gossip pool and the events, each row the moment it exists; a reader opens
it read-only through a `mode=ro` URI, never a copy, and has the seven
sections that write it switched off by the fifth property, reading the
file's rows where those sections' outputs were read
(`tools/world_reader_test.py`). A harness build gets a scratch world of its
own (`tools/harness.py`). The first character owns `tokyo`; Rena reads it.

**A promoted cast member** (`docs/peer-talk.md` §4b, `sim/rooms.py`,
`tools/agent_seam_test.py`). A cast row marked `agent: <hub id>` is the
operator's statement that the person runs herself. From that mark the
owner's exchange and planner write none of her words: a room is a
first-class thing with a membership written to the world, a turn in it
goes to every member who is an agent through the hub's peer mailbox, the
room waits `exchange.agent_turn_deadline_seconds` (180) and proceeds
without her if nothing comes, and what comes back is appended by the one
path a turn already takes; a joiner receives only what was said after she
joined. A beat the planner writes for her is KEPT with no words in it -- that
is what the ask path is for -- and an unplanned moment in the same room goes
the same way; an answer that is empty is a silence she chose, sent back as an
answer so the room settles at once rather than sitting out its deadline
(`sim/rooms.SILENT`). Her own process answers in a room it does not own
through her own friend-room persona and her own record (`sim/peers.py`,
`sim/lore_rooms.py`), and which side of a room a process is on is decided by
whether it holds a membership for that room (kv `rooms`) rather than by
looking the sender up on the roster, whose `self` row carries the world
owner's own hub id. A room turn spends `peer_talk.room_max_per_day` in kv
`room_counts` and not the peer conversation's day budget.

**The cast as mechanisms** (`docs/cast-mechanisms.md`, `docs/codebook.md`,
`docs/character-method.md` §3.1). The codebook `data/codebook/v0.1.json`: 189
entries over twenty families, 138 anchored in a record and 51 from the
scope alone, each with a definition, trigger, suppressor, occasions,
variation, exclusions against its neighbour and provenance;
`tools/codebook_check.py` in smoke; the ids frozen per version. A person's
file `data/cast_mechanisms/<key>.json` holds her instances: authored ones
with a `code` from the loss ledger, and a derived layer written by
`tools/compile_type.py` from her private type (`data/cast_types.json`, or
`data/characters/types/<key>.json`) through the compile table
`data/codebook/compile_v0.1.json`, with a loop and a grip keyed to her
gauges. The renderer puts the block into the three calls where she speaks
or is planned, and for the first character into her own system prompt
after her bible; the type's letters and the function names reach no prompt
(smoke greps for them). Rena is the test bed: her day harness and the
observation table are under `data/rena/harness/`.

### 20.2 The third character (`asumin/`): 阿澄佳奈's 2010 programme, extracted

Report of the run: `asumin/REPORT.md` (decisions first, every path);
what to read before judging her: `asumin/CAVEATS.md`; the method as it
stands: `docs/character-method.md`. Fifty-seven episodes, 55.7 hours,
attributed and read; 363 records with receipts, 227 dated memories, 795
cue phrases; two cards built blind (with and without the master
question-and-answer pass), the records-only card chosen; a resident
character (`config_asumin.json`, `characters/asumin/sheet.json`,
`prompts_asumin/`, `data/asumin.db`), the second character's models,
running (HISTORY §19 for the date). The coded pilot on three of her episodes
(`asumin/pilot/BASELINE.md`) is the codebook's first reliability figure.
**Her past is in her memory store as well as in her retrieval**: the 182
dated once-events of `characters/asumin/timeline.json` are `self_memories` rows
with source `seed`, written at boot from `character.timeline_file`
(`sim/seed_memories.py`, `docs/memory.md` §7a), so a trip, an illness or a
purchase can be reached by meaning and by the deliberate search and not only
by a message naming it; her 227 quoted moments are the retrieval's and are
not written into the store. **She has a voice and the app speaks her lines**:
her own `tts.voice_id`, `tts.enabled` and `tts.on_demand` both true, and the
vendor's two paths set, which is the pair her bot declares to the hub at
registration and the pair the client draws the speaker on
(`channels/talkapp_bot.py`, `asumin/CAVEATS.md` section 16). Which model
writes in her voice has two answers and the live one wins: her config names
`sakana-namazu` for the ten voice roles and a pin on her own save
(kv `voice_model_override`, set by `/voicemodel`) puts them on DeepSeek v4
flash, his pick. The pin is named on the boot line
(`LLM.voice_pin_line`), because it survives a restart and used to be
invisible.

### 20.3 Rena (`data/rena/`): the first cast member promoted

Written from a type and specialised, not extracted (`docs/promotion.md`,
"Rena, promoted"). Her sheet `characters/rena/sheet.json`, `config_rena.json`
(the world program, a reader of `tokyo`, no contact with him), `prompts_rena/`, `data/rena.db`;
her own circle `characters/rena/cast.json` with sheets under `prompts_rena/cast/`
(`docs/shared-world.md` section 9: two people the first character does not
know, a dance-class senior and a middle-school friend, and her own family;
her process plans their days, speaks their words and opens rooms with them,
all in her own save, and still answers in the owner's rooms when asked);
her record under `data/rena/` (81 standing facts, 34 dated events, 30
memories, 320 cue phrases, every row receipted, the invented ones marked);
her people, household and flat; her brother and mother as sheets under
`prompts/cast/` with dormant roster rows; her mechanisms file with 14
authored and 15 derived instances, a loop on anxiety and a grip on shame.
Her cast row carries `agent: "rena"`; running (HISTORY §9 for the date).

**And she says where she is.** Her own day planner writes the windows of her
day into the world file under her own id as her day is settled and at every
re-plan, and the lines her own plan settled go in under her own planner's
name; the first character's planner prefers those windows over its own draw
of her week where it lists who is where, decides how reachable somebody is
and picks the hour of a beat for her (`docs/shared-world.md` §2, the
partition; `world_shared.reader_writes_own_rows` switches her writes off).
Who she is with is not written: the people beside her are her own circle's.

**Who she is in her own process.** Her row in the world's cast is her, not a
second girl: `sim/roster._table` finds the row whose `agent` is her hub id and
folds it into her own entry, so `Rena-chan`, `香芝玲奈` and every nickname
resolve to `self` and `roster.handle` still returns the key the shared record
is keyed by. The world file's `self` block is a person on her roster (`Tomoe`,
role `world_owner`, `agent: "tomoe"`), so the name her own fills use for the
girl whose world she reads resolves. A name two people share is hers:
`お母さん` is her own mother. Her own circle's calls carry her circle's world
only -- her own people's whereabouts, her own threads, her own settled lines
(`docs/shared-world.md` section 9). What her save carried from the character
it was copied from -- bonds with that household, four arcs, a thread, the day
planned under the old fills, an orbit -- is retired once at her boot
(`tomoe/app.py retire_owner_interior_once`, `tools/promoted_save_retire.py`,
`docs/shared-world.md` section 7a).

**And what she has of her own.** Her map is hers (`characters/rena/map.json`): her
flat by Ekoda on the north side, her seven-minute walk, her three stops in,
her shopping street, her Wednesday studio by the Ikebukuro east exit, her
grandmother's Nakano -- with the school and the ward's two parks copied from
the world's map because they are the same places and each of those says so,
and everything her own material does not establish marked invented. She read
the owner's map until then, so her day planner was handed the owner's address
under the heading HER MAP. Her own mother and brother are marked `family` on
her own roster, which is what stopped the five family role ids making the
OWNER's mother her family and her own mother a member of the group chat, and
what takes the owner's father and brother out of where-everybody-is-today and
out of her own circle's planner. Her meters are her own four people, the two
girls she is at school with and the girl whose world she reads, whose meter is
seeded from her own sheet's opening values; what each of them is to her agrees
with that list (`docs/shared-world.md` section 7b). Her own absence, which the
owner's plan writes about her into the world file, is no longer read back to
her as a row about somebody else.
