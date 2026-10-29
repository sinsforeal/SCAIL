# SCAIL public snapshot

As-is and unmaintained. MIT (see LICENSE). This is a one-time snapshot of a private project, published so the work can be reused. Issues and pull requests are not watched.

**What it is.** A runtime for one long-lived companion character: a mind library (`sim/`: state, memory, appraisal, stances, the pick of what she does), a character bundle (`characters/momoka/`, the working example), sensors for the user's PC (`sensors/`, `machine/`), and a browser visual-novel reader (`channels/vn_bot.py`, `view/`, served at 127.0.0.1:8770). The `bzombie` branch adds the B-Zombie behavioural bench (`bzombie/`) with its results in `docs/reports/`; those results are experiment logs, and the owner never used the bench day to day or judged its fidelity.

**Run it.**
- Tested on Python 3.14 (Windows). An OpenRouter key in `secerts/openrouter.txt` (the folder is gitignored).
- Dry boot, no model calls and no network: `python tools/boot_her.py --config config_momoka.json`.
- Live: `python resident/run.py --config config_momoka.json --db data/momoka.db` (or `momoka.cmd`). A fresh save is seeded on first boot.
- The VN reader draws the character from extracted game art that is not in this repo (`vn.character_dir` and the inventory paths in `config_momoka.json`). Without it, set `"vn": {"enabled": false}` in the config; everything else boots.
- Optional keys (MiniMax voice, ODPT trains, gelbooru, MAL) are blank in the config; each feature stays off until you fill its key. `data/minimax/config.example.json` is the MiniMax template.

**Where to read.** `docs/INDEX.md` lists every doc. Start with `docs/2026-10-14_what_scail_is.md`, `docs/FEATURES.md` and `docs/character-method.md`.

The rest of this file is the original build note from the day the one-character fork was made (2026-09-16). Paths in it refer to the author's machine.

---

# SCAILV4 — the SCAIL runtime for one character: 百花 / Momoka

A fork of the SCAIL runtime (`F:\REPS2\SCAILV3`) that runs exactly one
character, **千代田百花 / Chiyoda Momoka**, in the SCAIL default shape for a
resident character (`asumin` / `yukari`) with **Tier 2 dropped**: no world, no
cast, no schedule from a world, no situation, no body economy. Everything else
stays: the mind (state, memory, context, stances, pick, the tick, the
relationship with him), the machine/sensors/accounts/peers/multi-role split,
her voice, the VN channel, and the ops tooling. The player is him.

The VN channel is **built** (`channels/vn_bot.py`): it implements the channel
surface and serves the stage at `127.0.0.1:8770` from inside her own process —
sprite, expression, message window, voice. `momoka.cmd` boots the whole of her,
channel included, in one click.

---

## What is in this tree

```
SCAILV4/
  scail.py llm.py config.py store.py atomic.py singleton.py logger.py netwatch.py
  resident/  talkapp/  channels/  sim/  persona/  world/  embodied/
  machine/  sensors/  tools/  prompts/  docs/  data/
  characters/
    machine.json            the machine's shared settings (no secrets)
    momoka/                 HER BUNDLE — everything that is this person
      bundle.json           the manifest
      sheet.json            the five existence answers, temperament, holes
      cast.json             her roster: him, and nobody else
      fills.json            her values for the shared prompts' [[TOKENS]]
      prompts/bible.md      her voice  (copied from the koikano record)
      prompts/style.md      her speech guide (copied from the koikano record)
  prompts_momoka/           written by compose: a copy of characters/momoka/prompts
  config_momoka.json        written by compose
  data/momoka.db            her save, seeded by compose
  characters.json           the operator's register: one row, momoka
  momoka.cmd                her launcher
  restart.cmd startall.cmd stopall.cmd run.cmd mal_daemon.cmd ...
  README.md                 this file
```

### A pre-existing VN prototype was in this folder

`F:\REPS2\SCAILV4` was **not empty** when this fork was made. It already held a
minimal visual-novel prototype: `serve.py`, `runtime/`, a top-level `momoka/`
(a `sheet.json` and prompts), `data/audio/` and `data/voice_cache/`. That
prototype is neither the SCAIL runtime nor the channel she runs; it was left in
place, not deleted, and its README is preserved at
`docs/PREEXISTING_VN_PROTOTYPE_README.md`. Ignore `serve.py`, `runtime/` and the
top-level `momoka/` when reading this fork. Her bundle is
`characters/momoka/`, and her channel is `channels/vn_bot.py`, which serves the
shared `view/` from inside her process.

---

## What was excluded from the SCAILV3 fork

Copied with `robocopy F:\REPS2\SCAILV3 F:\REPS2\SCAILV4 /E`, excluding:

| excluded | why |
|---|---|
| `logs/`, `reports/`, `data/retired/`, `data/backups/` | run history, not code |
| `data/*.db`, `*.db-shm`, `*.db-wal`, `*.db.lock`, `*.db.daemon.lock` | every other character's save, and the world file |
| `characters/tomoe/`, `characters/yukari/`, `characters/asumin/`, `characters/rena/` | the other characters' bundles |
| `tomoe/`, `tomoe/world/` | the first character's program package and its world adapter; `resident` is the only program this fork carries |
| `config.json`, `config_yukarin.json`, `config_asumin.json`, `config_rena.json` | the other characters' live configs; this fork has one, `config_momoka.json` |
| `asumin/`, `yukarin/`, `prompts_asumin/`, `prompts_rena/`, `prompts_yukarin/` | the other characters' working material |
| `megumi/`, `car/`, `tomoe_data/`, `x_scrape/`, `data/model_test/`, `data/voicelab/`, `data/mal_export/`, `data/rena/` | unused corpora and benches |
| `secerts/` | **keys** — nothing secret enters V4; keys are reused by path from `F:\REPS2\SCAILV3\secerts\` and `minimax/config.json` |
| `UI proposal/` | not runtime |
| `__pycache__/` | build artefacts |
| `uBlock0_1.73.0.chromium.zip`, `grep.exe.stackdump` | an extension bundle and a crash dump |
| `asumin.cmd`, `yukarin.cmd`, `rena.cmd` | launchers for characters that do not exist here |

Kept: `scail.py`, `llm.py`, `config.py`, `store.py`, `atomic.py`, `singleton.py`,
`logger.py`, `netwatch.py`, `sim/`, `persona/`, `world/`, `embodied/`,
`channels/`, `machine/`, `sensors/`, `tools/`, `prompts/`,
`characters/machine.json`, `docs/`, `resident/`, `talkapp/`, and the
launcher/restart scripts.

`characters.json` was then rewritten to an empty list, and `compose` wrote one
row: `momoka`.

---

## Her five existence answers, and why

| answer | value | why |
|---|---|---|
| `embodied` | `true` | Matches the resident shape. The record gives her a body and body lines: 低血圧 and sleepy (`01_01:3403` 「ん。ちょっとねむい。百花、低血圧だから」), and she attributes limits to the body (`03_01:2298`, `07_01:5261`), one of her eight firm speech moves. |
| `in_world` | `false` | **Tier 2.** Her record is 70 scenes inside a game; she has no ward, address, station, line or timetable of her own, so there is no present a second process could plan a day through. This is the switch that turns off the world, the cast and the world-owned machinery. |
| `sees_him` | `resident` | Matches `yukari`/`asumin`. He is the one she is with and the one she answers; the VN player is him. Keeps `eroge` and `resident_sight` alive. |
| `has_account` | `false` | Matches both residents. Nothing in her record is an account: no posts, no feed, no followers. |
| `with_him` | `chat` | The player **is** him. This is the one answer a promoted cast member would not have: the whole relationship layer (affection, attachment, care, contagion, expect, foresight, ick, intent, nudge, reflect, rhythm, rupture, withholding, wonder) stays on, and `sim/pick.py` offers her `text_him`. |

She is embodied but the **body economy is switched off** by her bundle's config
overrides (`diet`, `money`, `environment`, `needs`, `health`, `situation`,
`household`), exactly as `yukari` does it, and the four body gauges
(`hunger`, `fatigue`, `physical_comfort`, `unwell`) are `gauges_absent` on her
sheet. That is the "no situation, no body" half of Tier 2.

`holes` on her sheet and in her bundle name what is deliberately not authored:
gauge baselines, her age/birthday/family/description (the record says in as many
words that none of them appears, and her bible forbids inventing them), and a
`lore` record — so `lore` is off and she retrieves nothing from records yet.

---

## What the tools said

**compose** — `python tools\new_character.py compose momoka`:

```
wrote config_momoka.json
wrote 2 file(s) into prompts_momoka
wrote her row in characters.json
[config] not in_world and not has_account and not voice_actress, so these are off:
         cast, cast_arcs, cast_bond, compare, curation, events, exchange, family,
         gossip, hazards, npc, orbit, posting, role_check, scenery, share_pick,
         showrunner, social, social_graph, trains, x
seeded an empty save at data/momoka.db: 1 meter(s) from her roster
```
(The line `note 8 secret(s) not carried over` is expected: she has no prior
config to read keys from. **No key is written into V4.** Paste them into
`config_momoka.json` — or point at the existing key paths — before a live run.)

**verify** — `python tools\new_character.py verify momoka`, model and network
refused, on a scratch save: **all eleven gates pass.**

```
ok  every role prompt her existence keeps renders with no hole left
ok  every path in her config is her bundle, the machine, a mechanism prompt or the world
ok  no other character's name or place is in her prompts or her seeded save
ok  no file in her bundle is another character's, byte for byte
ok  her own key on her roster is her, and nobody else's   (Momoka -> self)
ok  no name on her roster means two people
ok  she is not a reader of somebody else's world: no owner to look for
ok  every meter is on somebody her roster has, or on him  (1 meter)
ok  what kind of thing she is comes from her sheet and her config agrees
    (embodied=True, in_world=False, sees_him=resident, has_account=False, with_him=chat)
ok  every one of her own people's meters is a number somebody chose
ok  she keeps her own world or is in none: there is no seam to live a day on
```

**rehearsal** — `python tools\agent_rehearsal.py momoka` **declines by
design**: *"momoka keeps her own world or is in none; this rehearses a character
who READS somebody else's."* That tool lives a day on the seam between two
characters in one world; she has no world, so there is no seam. Boot is proved
instead by the project's own full-construction check and by `verify`'s build.

**boot** — `python tools\boot_her.py --config config_momoka.json` constructs the
whole App and runs every report: **nothing failed.**

```
[boot] one clock, his: 2026-09-16 | she has no world of her own to keep a time in | clock real
[boot] instructions: in_her_language | her instruction language: japanese | 30 role(s) told to write in Japanese
[pick] LIVE: she decides what she does with the phone ... Tools: nothing, text_him, look_at_his_machine;
       when he has just written: reply_now, reply_later, leave_it
[boot] constructed.
  ok  persona._system (her whole prompt)   9127 chars
  ok  goals.report / ledger.text / state.system_prompt ...
  ok  situation (off: her existence)   health (off: her existence)
  ok  cast / social / schedule (not constructed)
nothing failed. She constructs and reports as she is.
```

---

## Tier 2 is off, and nothing else was switched off

The switch is `in_world: false` (`Config.REQUIRES` / `Config.WORLD_KEYS`), plus
her bundle's body/situation overrides. From the loaded config:

**Off by `Config.REQUIRES` from her answers**
- `in_world` → cast, cast_bond, exchange, family, hazards, social, trains, world_shared
- `world_owner` (she has no world she keeps) → cast_arcs, compare, events, gossip, npc, orbit, showrunner, social_graph
- `has_account` → curation, posting, scenery, share_pick, x
- `voice_actress` (no MyAnimeList id) → role_check

**Blanked by `Config.WORLD_KEYS`** — every path to a map, a school calendar, a
household, a place graph, a zeitgeist feed and a national/local event feed:
`world.{geography_file, holidays_file, household_file, local_events_file,
local_events_every_days, outing_words, places_file, school_calendar_file,
shared_dir, taste_file, zeitgeist_every_hours}` and `world.weather_enabled`.
The seven account keys under `sensors.x_*` are blanked too.

**Off by her bundle's overrides (the Tier-2 body/situation half)** — `diet`,
`money`, `environment`, `needs`, `health`, `situation`, `household`, and the
things she has no material for: `reactions` (no face crops for her),
`vault_snoop`. `watching` and `lore` were switched on in the running config on
2026-09-18 (3e222dd) and the bundle composes them on since 2026-10-22; `lore`
has no records file, so it retrieves nothing yet.

**Still on** — the mind and the relationship and the machine:
affection, afterthought, agenda, anime_sense, anticipation, approach,
attachment, attention, beliefs, care, coherence, commitments, contagion,
derive, diary, downtime, embed, episodes, eroge, expect, experience, foresight,
goals, him_profile, ick, intent, language, lookup, memory, morning, notes, pick,
primitives, recall, recap, receipts, reconcile, reflect, resident_sight, rhythm,
rupture, self_memory, sensors, sentiment, shape, spiral, stances, stress,
talkapp, tts, vision, weekly, which_one, withholding, wonder.

Two sections read as off but were **not** switched off by anything here:
`nudge` and `peer_talk` are `enabled: false` in the library's `DEFAULTS` — off
for every character until somebody writes them in. That is the whole of the
"off" surface: nothing beyond Tier 2 and what she has no material for.

---

## Boot her

```powershell
cd F:\REPS2\SCAILV4
python resident\run.py --config config_momoka.json --db data\momoka.db
```

or double-click `momoka.cmd`, which runs the same command and is the line her
scheduled task (`SCAIL_momoka`) would run.

**What a first boot does:** `resident/run.py` registers her words (the machine
she lives on), `scail.App` builds her config, save, clock, LLM, channel, the
mind and every slot her existence keeps, seeds her save once from her roster
(one meter, on him), plans her day from `world.home_file` — which she has not
got, so it falls back to `resident/schedule.py:resident_day()`, the one-block
day for a character with no world — and enters the 5-second loop. On a live run
the first model calls are her first tick and her first reply to him; they need a
live key at `secerts/openrouter.txt` (her config's `api.openrouter_key_file`).

**A dry boot with no spend** (model and network refused), which is what this
phase used:

```powershell
python tools\boot_her.py --config config_momoka.json
```

---

## What is not done

The VN channel and her voice are built. What is still open:

- Her prompts are the koikano record verbatim and still name the game's
  protagonist and the other heroines (see *Honest limits* below).
- `lore` is off: no `records.json`, so she retrieves nothing from her own
  record.
- The pre-existing prototype (`serve.py`, `runtime/`, the top-level `momoka/`)
  stays in the tree as legacy; nothing in the fork uses it.
- The v3-only tooling is kept, not rewired: `PROJECT.md`, `CONFIG.md`, `tools/docs_src/`, and the tools that still default to `config.json` / `config_yukarin.json`.

**Voice is hers.** Her `tts.voice_id` is her own MiniMax clone,
`YOUR_VOICE_ID`, set in `config_momoka.json`
and `characters\momoka\bundle.json`. The clone was made from
`...\bible\hyakka\voice\hyakka_voice_sample_2min.mp3` (123.0 s, 35 non-H clips);
see `docs/voice.md`. Synthesised lines are in her own voice, and her recorded
clips still play from tape where her line matches one.

## Honest limits

- Her prompts (`bible.md`, `style.md`) are the koikano record **copied
  verbatim**. They name 一悟 (the game's protagonist) and the other heroines of
  her scenes; in this fork the player is him, so the copy has to be adapted to
  call him. The record's own text was not rewritten, so its names are still in
  the system prompt.
- Her gauge baselines are the library's defaults, not hers. Her temperament is
  not authored yet.
- `lore` is off: no `records.json`, so she retrieves nothing from her own
  record. The mind's five memory stores still work; the record retrieval does
  not.
- `data/momoka.db` was seeded by compose on a build with the model and network
  refused. It holds one relationship meter and nothing else.
