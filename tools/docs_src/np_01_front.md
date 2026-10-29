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

