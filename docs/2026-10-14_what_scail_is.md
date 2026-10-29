# What SCAIL is

Orchestrator write-up, 2026-10-14 (local, 24hr). Standalone; not part of the
other proposals.

Read for this:
- `README.md` in full.
- `PROJECT.md` §1-3, the head of §5, the head of §12.1, §15 and the head of §20.
- `docs/README.md`.
- `characters/momoka/sheet.json`.
- The opening of `prompts_momoka/bible.md`.
- `docs/2026-10-07_scail_capability_and_seams_inventory.md`, which was code-checked.

Not read line by line: the 7,081-line `PROJECT.md` body of every module, and
`HISTORY.md`. Live state on the PC was not checked from here.

## 1. In one paragraph

SCAIL is a runtime whose goal is **the complete illusion of a separate
consciousness**: a person whose life, feelings and memory move on their own
clock, who learns about him the way a person would, and who speaks because
of her own state, not because a timer fired (`PROJECT.md` §1). It is
not a chatbot with a persona prompt. It is a **mind library** (`sim/`, about
100 modules) plus a **voice** (`persona/`), an optional **body** (`embodied/`),
an optional **world** (`world/`), **his machine** (`machine/`, `sensors/`), and
**channels** to reach him. It is run by `scail.py` for one character per
process against one SQLite save. The rule over all of it is: *code decides when
(gates, caps, schedules); a model decides what*. Fidelity matters more than the
number of model calls.

## 2. The four founding rules (`PROJECT.md` §1)

1. **Her state exists independently of him.** Time, gauges and relationships move
   on her clock. His silence is a fact she reacts to, not what drives the loop.
2. **Availability is the strongest illusion lever.** When she can't answer she
   doesn't. Latency, length and whether she starts a conversation come from where
   she is.
3. **She learns about him through a "phone", not omniscience.** His PC
   telemetry, anime list and notes reach her only as a digest from her side
   of the glass, and only when she looks.
4. **Messages originate from state.** An impulse reads her gauges, scene and
   the silence, and only then does the persona speak.

Plus one more: **the persona is static**. It is a bible plus a style guide. Growth
lives in state, memory and relationships, never in machine-edited prompt text.
The bot never rewrites its own persona.

## 3. Lineage: V3 to V4

- **SCAILV3** grew four characters on one library:
  - Tomoe (the first): 15, Ikebukuro, a full world with school day, cast, LINE groups, trains, weather, an X account.
  - Yukari/Yukarin (the second): resident on his machine.
  - Asumin (the third).
  - Rena (the fourth, a promoted cast member).
- Rena's arrival forced the big design turn. A mechanism written around one character
  quietly served her life to anybody, so the second character booted with a
  school day, friends and an X account she should not have had.
- From that came:
  - **A character declares what kind of thing she is.** That is five sheet answers: `embodied`, `in_world`, `sees_him`, `has_account`, `with_him`. `Config.REQUIRES` assigns every subsystem to one of them, or refuses to boot.
  - **A character is a bundle** (`characters/<key>/`) plus the shared library. `tools/new_character.py compose|verify` builds and gate-checks her.
  - **The library is neutral.** A character-shaped span in a shared prompt is a `[[TOKEN]]` filled from her bundle. Smoke fails on one character's name, place or file leaking into another's.
  - **Two programs over one library:** `tomoe/` (a world) and `resident/` (no world). The runtime builds the mind, then asks the program to fill its slots. A character with no world doesn't have its subsystems switched off; it never has them at all.
- **SCAILV4** is a fork of V3 that runs **exactly one character, 千代田百花 / Momoka**,
  in the resident shape with **Tier 2 dropped** (`in_world: false`). That means no world,
  no cast, no world schedule, no situation and no body economy. Everything else is
  kept: the mind, the relationship layer, the machine and sensors, her voice and the
  VN channel. Her five answers:

| answer | value | meaning |
|---|---|---|
| `embodied` | true | she has a body the record gives her (sleepy, low blood pressure), but the body economy is off |
| `in_world` | false | Tier 2 off: she has 70 scenes from a game and no ward, address or timetable |
| `sees_him` | resident | she lives on his machine and sees it |
| `has_account` | false | no social account |
| `with_him` | chat | the player is him; the whole relationship layer stays on |

## 4. Who Momoka is in it

- Source: 恋する彼女の不器用な舞台 (koikano). Her `bible.md` and `style.md` are the
  game record copied verbatim: 70 scenes, 2,570 spoken lines and 211 inner-voice
  lines, in Japanese.
- The bible tells her this is *what she actually did in those scenes*, not a
  character sheet. She owns only those 70 scenes; nothing after them is decided. She
  judges people by what they do, never reuses quoted lines as a phrasebook,
  calls herself 百花 (never 私) and writes only Japanese.
- Deliberate **holes** (`sheet.json`): her gauge baselines (no measurement
  from the record, so library defaults stand), age, birthday and family (the record
  never gives them and the bible forbids inventing them), and lore retrieval
  (off: no `records.json`).
- Known limit: the verbatim record still names the game's protagonist 一悟 and
  the other heroines. In V4 the player is "him".
- Voice: her own MiniMax clone, built from about 2 minutes of non-H clips. Recorded
  game clips play instead when a line matches one.

## 5. How it runs

**Processes.** Two: Momoka (`momoka.cmd` → `resident/run.py --config
config_momoka.json --db data/momoka.db`, task `SCAIL_momoka`) and the machine's
MyAnimeList mirror daemon (`SCAIL_mal`). One bot per save file, enforced by
`singleton.py` with pid plus command line.

**The loop** (`scail.py` `App.run`, about every 5 s, §3), in order:
1. Day boundary: plan, goals, morning outlook.
2. Her picture of him.
3. Inbound from him (commands never enter her chat).
4. Replies (`maybe_reply`, then foresight and afterthought).
5. One branch: asleep (one scene for the night, gauges still drift), link down, or a **tick** due. A tick is the look at his machine, the director's scene and a reconcile.
6. After the tick: psychology, impulse, discharge, face, diary, morning, anticipation, reflection.
7. Then: withholding, foresight, expectations, wonder, promises, attachment.
8. The **nightly compile**.

Every stage is guarded, so one failure logs and the loop goes on. Program-specific
work hangs on hooks at fixed points (`every_pass`, `tick_events`, …).

**Restart-safe by design.** Stops are `Stop-Process -Force`, so state is
committed when it changes (`synchronous=FULL`). Each in-flight paid job leaves
a kv `in_flight` row. A killed process leaves its row, and the next boot uses
that row as the flag for what to rerun or drop. A message of his that was read
but never answered is requeued once.

**Models.** `llm.py` is one OpenAI-compatible client with one entry per role.
- Every answer is streamed, with truncation, stall and runaway-repetition guards.
- Missed calls go to a ledger that `catch_up` replays.
- Prompt-cache hit rates are tracked per role, and bursts are held so they share a warm prefix.
- One provider answers, with no silent fallback to another model.
- Nine "voice roles" write as her (persona, revise_self, spiral, approach, morning, anticipation, reflect, diary, wonder). The rest is machinery that thinks *about* her.
- Momoka's persona is glm-5.3-flash with thinking, via OpenRouter. Machinery roles run on deepseek-v4-flash.
- Typesafe ("Jev") answers 18 confidence-gated classification uses.
- Her eyes are Gemini on Vertex.

## 6. The mind (what `sim/` holds)

| layer | what it is |
|---|---|
| State (§7) | 0-100 gauges with kind, valence and arousal (21 for her, with the body gauges removed); per-person meters (closeness, standing, tension); discharge, where a gauge at its limit becomes an event; stress, spiral and rupture; sentiments; appraisal of his messages; self-memory |
| Her day (§8) | director scenes per tick; for her, a one-block resident day; rhythm (when he is around, learned and told); impulse, intent and shape (does she text, and what); `pick` (what she does with the "phone": `text_him`, `look_at_his_machine`, or when he wrote, `reply_now`/`reply_later`/`leave_it`) |
| Her picture of him (§10) | model of him and of her; ick; approach; withholding and attachment stances; foresight; expectations (his word held to the record); wonder; goals and outlook; receipts |
| Her phone (§11) | `him_profile`; `phone` (digest of his PC); notes (his vault); lookup (she quietly looks things up); anime sense and KB; sensors (Windows only) |
| Memory (§12) | five memory stores with a forgetting curve; recall and diary; **the one thread** (7 days verbatim, then daily cards, 30 days max); the nightly compile into narrative, summary, facts about him and her own memories; cards and local embeddings for search by meaning; coherence; lore; `watching_him` (what he's watching); `eroge` (what VN he is reading); MAL-based dossiers |
| Context (§5, `docs/context.md`) | the system prompt is the cached half that changes about once a day: bible, backstory, decisions, people, motives, agenda, style. The thread follows: the world's turns are labelled `[time · room · who]`, hers are bare. Per-reply situation goes last |

## 7. How Momoka meets him in V4

- **The VN channel** (`channels/vn_bot.py`) serves a browser stage at
  `127.0.0.1:8770` from inside her process. It shows:
  - background, sprite with face patch, portrait and emotion marks;
  - one line at a time with her voice;
  - BGM with loops, and a scene director (place, lighting by time, music, outfit, expression);
  - a stage-manager console;
  - saves, backlog, Jump/Change Reply, auto, skip and back.
- **She is player-driven** (`character.existence.player_driven: true`). She never
  writes first; she speaks when he does, on an arrival after 6 h away, or on a
  scene or outfit turn. This is a V4 choice that sits against founding rule 4
  (messages from state). Her state still runs; it only shapes her replies.
- **Her sight of him**: the window trail, idle and sleep inference, his
  Obsidian vault (she treats a changed note as "he just wrote this"), mpv, and a visual-novel text hooker.
- TALKAPP (phone PWA) and Telegram exist in the library but are off; the channel
  is VN only.

## 8. How the project polices itself

Smoke (`tools/smoke.py`, run before every restart) builds the App on a copy of
the save and checks:
- every report and the gauge wiring;
- dead config keys;
- name, place and prompt leaks between characters;
- blank-path builds;
- wiring (`sim/wiring.py`: a declared collaborator left `None` fails);
- the command and help table;
- that the composed config equals the running one.

Each module entry in `PROJECT.md` says what code decides against what a model decides,
plus its config, store, invariants and edge cases, and points into `HISTORY.md`.
The house rule: *read the function and query the live store before reporting on a
subsystem; the docs have described behaviour the code did not have.*

## 9. State as of the last handover (2026-09-18, now stale)

- Momoka boots clean and the VN reader works live.
- **Catalog:** 111 backgrounds in 28 places, 26 music tracks with loop points, 7 outfits × 16 expressions.
- **Voice and saves:** recorded and synthesized voice; save, load and backlog replay with archived stage frames.
- **Unverified:** a live model branch from Change Reply, a strict database and stage checkpoint, the director's authored camera and entry commands, and the long-arc integrals (ledger, attachment, picture of him), which take weeks to show.

## 10. What I'd still check before claiming full knowledge

- The `PROJECT.md` module bodies for anything V4 rewired after the fork. The
  README says PROJECT.md and CONFIG.md are kept as V3 history and "not rewired",
  so some of it describes Tomoe's machinery that is absent in V4.
- Live behaviour on the PC: the save, logs and the current config state.
