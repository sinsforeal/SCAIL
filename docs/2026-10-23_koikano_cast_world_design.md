# Koikano cast world for Momoka: design

Opus design agent, 2026-10-23 13:02-13:40. Design only, no code. Branch design/cast. Tracker: tk-71n (the cast-world arm), tk-6r3 (the grounding test it joins). Notebook: docs/reports/2026-10-23_cast_design_notebook.md.

## 0. Result first

- Build a hybrid: one hidden **world-owner process** that runs the koikano cast as **light agents** (rows, seeded draws, one planner call a day, beats rendered on demand), and Momoka stays a full mind that **reads** the world file as `in_world: true` but not `world_owner`. No heroine gets a full mind in phase 1.
- Why: the bench already showed code gating wins (S beat P at 1/19 the calls). Six full minds is six S arms: about 6x her calls and about 10 GB RAM, for people whose lines she only hears in the scenes she is in. A light cast gives her lived events at about +40% of her own calls.
- Cost, at the bench's measured blended rate (cl3v3_s_momoka): her S mind today is 93 calls, 406k prompt tokens, 0.0033 USD per simulated day. The cast world adds about 40 calls, 150k tokens, 0.0013 USD per simulated day. Six full minds instead: about +560 calls, +2.4M tokens, +0.02 USD and +10 GB RAM per day.
- Grounding is checked by code: every day-claim she makes (a place, a person, an outing verb) is matched against the world log of beats she was present for. No model call. The same check runs on the bench and, later, as a pre-send check live.
- It goes live only if bench arm D (cast world) beats arm B (own-day) on grounded_claims and own_life, at no fidelity loss. If own-day ties it, own-day ships and the cast world waits.
- One decision only the User can make blocks the world spec: the **frame**. The record is a school (早久保学園, she is a first-year club president); the bench card says she is an adult and romance is allowed. Section 7.

## 1. Inventory from the corpus

Corpus: `F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano`. Counts measured this session from `koikano_work\character_lines\*.jsonl` (kind spoken) and `koikano_work\stage_state.jsonl`; totals agree with `character_lines\_summary.json`.

### 1.1 People

Routes come from the builder's own map (`src\kirikiri_tools\koikano_bible.py:1033`): a = 真優, b = 千奈, c = アリス, d = 百花. Momoka's spoken lines by route: common 552, a 111, b 169, c 78, d 1654.

| person | spoken | scenes | scenes with Momoka | their lines in her scenes | her lines to them (bible.md) | own route | bundle verdict |
|---|---|---|---|---|---|---|---|
| 一悟 (protagonist) | 7,736 (+14,144 inner) | 103 | 69 | 5,661 | 1,707 | viewpoint | not cast: in V4 the player is him |
| 真優 | 3,546 | 78 | 58 | 2,199 | 195 | a | full bundle possible |
| 千奈 | 3,493 | 72 | 58 | 2,201 | 218 | b | full bundle possible |
| アリス | 2,792 | 59 | 48 | 1,533 | 78 | c | full bundle possible |
| 真里亜 | 1,228 | 65 | 61 | 1,028 | 308 | none | light card; closest to her (her maid) |
| 知紗 | 557 | 37 | 32 | 345 | 24 | none | light card |
| ひかる | 427 | 39 | 34 | 389 | 3 | none | light card, background; she has no name form for her |
| ケルベロス | 168 | 34 | 29 | 132 | 4 | none | prop-level, not a cast row |
| named NPCs | 175 total | | | | | | `npc` strangers: 天文部部員 30, 野村先生 7, 文化祭実行委員 6, 新聞部部長 8 and others (`_summary.json`) |

Why the cut lands there: a bundle needs enough record to hold a voice and a relationship. Three heroines carry a whole route each (2,800 to 3,550 lines); 真里亜 has fewer lines but is in 61 of Momoka's 70 scenes and gets the most of Momoka's lines after 一悟 (308), so for her world 真里亜 matters more than アリス. Below 600 lines a bundle is a sketch; a light card says only what the record supports.

### 1.2 How cast bundles get built (the existing bible step, not a new extraction)

The bible that built Momoka is a tool, and it takes a subject flag. Runbook: `F:\REPS2\clipboard capture (kirikiri)\docs\koikano-bible-method.md` sections 3-4.

- B0-B3: `python "src\kirikiri_tools\koikano_bible.py" --char 千奈 --out <dir> --doc <path>` from `F:\REPS2\clipboard capture (kirikiri)`. `--char` takes name, id, buid or slug; slugs are fixed in `SLUGS` (`koikano_bible.py:60-70`: mayu, sena, alice, maria, chisa, hikaru, cerberus). Arguments at `koikano_bible.py:2796-2800`. Standard library, no API call, fails loudly on a join mismatch.
- B4 gate is hardcoded for her: `koikano_bible_gate.py:32-37` (`NAME = "百花"`, `ROUTE = "d"`, holdout d16_01-d20_01, control heroines). A per-character gate is an edit or a small parameterisation.
- B5 (the runtime `prompts\bible.md`, `style.md`, `sheet.json`) has no tool: hers was hand-authored on 2026-09-16 (method doc section 3, B5).
- The method doc says "the next character is a parameter change". That is true for B0-B1 and only partly for B2-B3. Found in the code: the route and route character are written as literals (`koikano_bible.py:2236`, `:2246-2247` `"route": "d"`, `"route_character": "百花"`), the self-reference rule is hers (`:1797` "Name yourself 百花 in the third person", counted from `:1725`), and one B3 matcher keys on 百花 (`:189`). Run as is, 千奈's bible.json would claim route d and a 百花 self-reference rule. So step 1 of the build is a small patch: route and route character from the `:1033` map, the self-reference rule computed from the subject's own top first-person form, B3 matchers that name 百花 skipped for other subjects (their B3 reading is their own, per the method doc section 4).
- Output goes to the SCAILV4 tree with `--out` and `--doc`, never the default `bible\<slug>\` and `docs\` of the corpus project: the corpus stays read-only, and the cast is her world's data, not a corpus artifact.
- Light cards do not need B5. A cast row needs a name, aliases, how Momoka calls them and how they call her (B2 `interactions`), three to five firm voice traits (B2 `speech_guide`, firm tier only), a week, and bounds. That is read off bible.json mechanically. Full B5 prompts are only for a heroine promoted to a full mind (stage 4 of section 6).

### 1.3 What the record says the world is

- A private school, 早久保学園 (`game_logic.jsonl`: 早久保学園 8, 当早久保学園 2, 私立早久保学園 1).
- The theater club (演劇部, 254 lines in the corpus, 40 of hers). She founded it and has been president for half a year as a first-year: 「千代田、百花。演劇部の部長歴、半年。演劇部は百花が作った」 (d05_01:0353), 「一年生が部長だから？」 (d05_01:0370). The literary club (文芸部, 310) whose president is 一悟 (06_01:3759). A presidents' meeting (部長会議, d06_01:1590).
- Her house is big, the 千代田家 can sponsor a play, 真里亜 is her own maid: 「百花の家、広い。みんな呼べる」 (b01_01:0839), 「千代田家が舞台のスポンサーになるのもだめ？」 (04_01:1944), 「真里亜は、百花のメイドだから」 (d06_01:0484), a karaoke machine at home (b11_01:0365), relatives visiting with 「パパたち」 (b01_01:1059).
- Her body and school: long absences for illness (「この前、百花、たくさん学園休んだ」 d06_01:0499; 「家で過ごす時間の方が長かった」 b06_01:1090), a doctor who says 病は気から (d06_01:1883), mid-term and final exams and red marks (d08_01:0535, a03_01:1108).
- Places: the 28 background groups are already a catalog in V4 (`docs/2026-09-18_corpus_backgrounds.md`, `sim/scene.py:PLACE_BACKGROUNDS`). Her lines by place: club_room 444, meeting_room 345, her_room 286, hallway 212, classroom 115, pool 85, entrance 70, school_gate 62, stage 60; everything else under 35. Her rooms (BG18) appear in 15 of her scenes.
- Time: no timetable exists in the record. There are 授業 (69), 昼休み (55), 放課後 (105), mid-terms, the culture festival over two days (09_01, 「――文化祭二日目。」). Her lines by light: day 1,231, sunset 308, night 324.

Finding for the User (a fact, not a change): her bible says 「家族も……この記録には一度も出てこない」 (`characters/momoka/prompts/bible.md:21`). The record names no family member, but it does have the 千代田家, 「パパたち」, relatives, a big house and a maid. The persona is static, so the bible stays; the world spec may use only what the record has (the house, 真里亜, the 千代田家 as a name) and never a named parent.

## 2. What carries over from V3, what does not

V4 has no `tomoe/` package (it was not forked in); it has `world/` (`world/shared.py` 766 lines, same size as V3's) and `resident/`. The program is chosen by `character.program` (`scail.py:81`), with world slots in `PROGRAM_SLOTS` (`scail.py:98`).

### 2.1 Carries over (port into a new program, see section 3)

| V3 part | file:line | what it does | why it carries |
|---|---|---|---|
| CastEngine | `SCAILV3/tomoe/cast.py:214` (2,425 lines) | `draws` (`:283`) seeded mood, attention, friction random walk per person per day, code only; `plans` (`:673`) each person's day from their week; `plan_day` (`:1460`) one `cast_day` call for the day's beats, budget = sum of attention (`:99-106`); `write_lives` (`:318`) one line per person per day; `day_to_world` (`:1807`) whereabouts into the world file | this is already the light-agent design: code decides who and when, one call writes what |
| CastArcs, Showrunner | `tomoe/cast_arcs.py:58`, `:387`; weekly gate `:39` | weekly pressures for the cast's own lives ("pressures, not plots", `:380`) | gives the heroines a week of their own at 2 calls a week |
| Exchange | `tomoe/exchange.py:79`, `tick` `:826`, `run` `:1315`; calls `cast_turn` `:2563`, `cast_reply` `:2192` | a cast member and her talk inside a beat; she answers in her own voice | the route by which a cast line reaches her as her own lived event |
| People (npc) | `tomoe/npc.py:105`, `tick` `:312`, one call `:332` | strangers who pass through a scene | the named NPCs (天文部部員, 野村先生) without rows |
| Gossip | `tomoe/gossip.py:33`, call `:236` | what goes round | how she hears of a scene she missed |
| Orbit | `tomoe/orbit.py:31`, call `:182` | the people around the people | optional, phase 2 |
| SocialGraph | `tomoe/social_graph.py:38`, `read_only` `:76`, call `:238` | who holds what about whom, compiled nightly by the owner | readers read it through the world file |
| SharedWorld | `world/shared.py:217` (V3 and V4), `turns(date, room)` `:616` | the world file: people, whereabouts, turns by room with witnesses | the seam between owner and reader, and the source of the world log |
| Peers (peer_talk) | `sim/peers.py:80`, `tick` `:272`, `peer_reply` `:411`, `:660` | two running minds talking | only for stage 4, a promoted heroine |

### 2.2 Does not carry over

- Tomoe's live-present feeds: `tomoe/world/trains.py`, `tomoe/world/hazards.py` (1,034 lines), `tomoe/world/zeitgeist.py`, local events, `world/weather.py`. Why: Momoka's world is not this city now; her bible gives no ward, no line, no station.
- Account machinery: `posting.py`, `curation.py`, `taste.py`, `share_pick.py`, `scenery.py`, `snoop.py`, `stickers.py`. Why: `has_account: false` and stays false.
- `tomoe/family.py` (424 lines, Tomoe's household economy and her family's schedules). Why: her bible forbids inventing family; the record gives no member to schedule.
- `tomoe/schedule.py` school skeleton (`_school_windows` `:60`, `skeleton` `:174`): Ikebukuro timetable for a 15-year-old. Why: wrong person and, depending on the frame decision, possibly the wrong frame. The new program plans her day from a koikano world file.
- Body economy: `embodied/situation.py` (915), `health.py` (568), `money.py`, `body.py`, `tomoe/diet.py`. Why: it was Tier 2 off for a reason (sheet.json `_embodied_why`): she is embodied but not spending a day getting cold and paying. Her sleepiness stays a trait in the bible, not a meter.

### 2.3 What `in_world: true` switches back on for Momoka

From `SCAILV4/config.py:7405` `Config.REQUIRES` and `:7594` `WORLD_KEYS`:
- On by the property (`config.py:7434-7439`): cast, cast_bond, social, exchange, family, world_shared, trains, hazards.
- Un-blanked by `WORLD_KEYS` (`config.py:7595-7606`): household_file, places_file, geography_file, school_calendar_file, shared_dir, local_events_file, holidays_file, outing_words, zeitgeist_every_hours, local_events_every_days.

What must stay off in her bundle config even with the property true, and why:
- family, household_file: no family to invent.
- trains, hazards, zeitgeist, local events, holidays, geography: live-present feeds of a city she is not in.
- The world_owner block (`config.py:7453-7465`: cast_arcs, showrunner, gossip, events, orbit, npc, compare, social_graph): she is a reader. Two planners over one roster was the third character's failure (`config.py:7446-7451`); the owner process runs these, her process does not.
- The body sections (`config.py:7429-7431`: health, needs, environment, money, diet, situation, household): stay off by bundle override exactly as now; `embodied` stays true.

What she keeps on: cast (her rows, read from the world), cast_bond, exchange (her side of a scene), social (what she makes of the people), world_shared as a reader. `home_file` stays and becomes her rooms inside the world file (`config.py:7578-7584` says why it is never blanked).

## 3. Architecture

### 3.1 The three options

| option | what runs | calls per simulated day (added) | RAM | verdict |
|---|---|---|---|---|
| A. each heroine a full mind | 6 S minds plus hers, peer_talk between them | about +560 (6 x her 93) plus their mutual talk | about +10 GB (6 x 1.7 GB S peak) | no: the P lesson. Most of that cognition never reaches her |
| B. one world owner, cast as light agents | 1 owner process, cast as rows; she reads | about +40 | owner process, est. 0.3-0.5 GB (no embeddings, no memory stores); unmeasured | yes, phase 1 |
| C. hybrid | B, plus one heroine promoted to a full mind later | B + 93 per promoted mind | +1.7 GB per promoted mind | the growth path, only if the bench shows a cast voice is the weak point |

Why B: the thing she lacks is lived events, not other people's inner lives. The cast's inner life matters only as far as it shows in a scene she is in or in what she is told. A row with a seeded mood, a week and a one-line life carries that. Rena's promotion in V3 (`tools/promote_cast.py`) shows the path to a full mind exists when a person earns it.

### 3.2 The world owner

- A new program package `koikano/` (name to taste), a hidden pythonw process, its own save (`data/koikano_world.db`), never her save. It owns the world file (`world/shared.py`, `shared_dir`).
- Ported from V3: CastEngine (draws, plans, plan_day, write_lives, day_to_world), CastArcs and Showrunner, People (npc), Gossip, SocialGraph. Tomoe-isms stripped: school calendar, family, trains, X.
- World spec file (`characters/momoka/world/koikano_world.json`): the places (the 28 BG groups, ids from `sim/scene.py:PLACE_BACKGROUNDS`), the club and its room, the week anchors (club days, the presidents' meeting, exams as rare fixtures), each cast row's week. Every fact carries a record receipt (scene:line), as her sheet does. Nothing without a receipt goes in.
- Cast rows from section 1.2 cards: 真優, 千奈, アリス, 真里亜, 知紗, ひかる (light). ケルベロス and the NPCs are `npc` strangers.

### 3.3 Code-gated cadence (code decides when)

- Day boundary (code): `draws` for everyone (0 calls), `plans` from weeks (0 calls).
- Once a day, early: `plan_day`, 1 call (`cast_day`), returns N beats with time, place, present list, kind, one-line gist. N from the attention budget (`cast.py:99-106`), capped low for her: 6-10.
- At each beat's time (code timer): if Momoka is in `present`, the beat is rendered as a scene, 1 call for the cast's lines (`cast_turn`), then her mind answers through her normal reply path (her own call, already counted in her 93 when it would have been a reply; counted as extra here to be safe). 2-3 turns per scene. If she is not present, nothing is rendered: the gist goes to the world log only.
- Night: `write_lives`, 1 call per person who had a beat (up to 6); weekly arcs and showrunner, 2 calls a week.
- Gossip: 1 call a day at most, gated on a beat she missed that someone present would tell her about (code: a missed beat with a present cast member who meets her later that day).

Per simulated day, with 8 beats, 3 with her present, 3 turns each:
- plan_day 1, scenes 3 x 3 cast turns = 9, her extra replies 9, lives 6, gossip 1, npc 2, arcs and showrunner 0.3, her director reacting to world events about 10 extra ticks.
- Total about 38-40 calls. At her measured 4.35k prompt tokens per call: about 150-170k tokens. Cost at the bench rate: about 0.0013 USD.

Bench rate, measured from `var/bzombie/runs/cl3v3_s_momoka/calls.jsonl` (arm S, deepseek-v4.1-flash-1017 on Surplus, `cost_micro`): 280 calls, 1,217,099 prompt tokens (777,216 cached), 28,914 completion tokens, 0.009912 USD over 3 simulated days. That is 93 calls, 406k prompt tokens and 0.0033 USD per day; 35 micro-USD per call; 8.1 USD per billion prompt tokens blended. Tomoe on the same arm: 680 calls, 0.0288 USD over 3 days (`cl3v3_s_tomoe`). Live Momoka runs on OpenRouter (persona glm-5.3-flash, machinery deepseek-v4-flash), not Surplus; the live rate is not measured here, so live USD is the bench figure times an unknown factor. The call and token counts carry over as they are.

### 3.4 How the cast's events reach her (her own lived events, not his PC)

- Today her env stream is all `kind: pc` (`bzombie/CONTRACT.md` Environment events: "Momoka cannot see beyond his PC"). The cast world adds `kind: world` events, the shape Tomoe already uses on the bench.
- A beat with her present enters her thread as a world turn, labelled the way the thread already labels the world (`[time · room · who]`, `docs/2026-10-14_what_scail_is.md` section 6), and the cast lines are turns by those people. Her reply path is the same one that answers him. This is what makes it hers: she was in the room and said something.
- A beat without her stays out of her thread. She can learn of it only by being told: a later scene where someone present mentions it (gossip), stored as "heard from 千奈", never as lived.
- Her situation block (per-reply, last in the prompt) gets one line: where she is now and who is there, from the world file's whereabouts. With nothing happening it says so ("自分の部屋。ひとり。"), which is the honest-absence cue for free.

### 3.5 How she is absent

- Code, not a model, decides presence. Each beat's `present` list is fixed in the plan; her own whereabouts come from her plan (her week, her body's sick days as a seeded draw: the record has her absent from school often, d06_01:0499).
- When she is home, she is home: the beats she is not in happen without her, and the day she reports is her room, 真里亜, the hot milk.
- When he is at his machine she is still on his machine too (resident sight stays). The world does not take her away from him; it gives her a day to have had.

## 4. Ground truth: the grounding check

A deterministic check, in the spirit of the bench's output check (bz/s8: separators, tags, stamps, no model call).

Inputs:
- Her lived log for the day: world-log beats with her in `present`, each with place id, people keys, kind, and a small tag list the planner must emit with each beat (objects and activities, closed form, Japanese). Plus heard items (gossip), marked heard.
- The closed vocabularies: place words (`sim/scene.py:_PLACE_WORDS`, 28 places), the roster aliases (`sim/roster.py`, every name form of every cast row), outing verbs (出かけた, 行ってきた, 散歩, 寄った, 帰りに), time words (今日, さっき, 朝, 放課後).
- Her record memories: the 70 scenes. A claim that matches the record is "remembered", not invented.

Method, per bubble:
1. Find self-reports: a time word or a past form in a clause with her as subject (百花 or no subject), regex over the Japanese.
2. Extract anchors in that clause: place words, roster names, outing verbs, tagged objects, and unknown concrete nouns next to an outing verb (the 銀杏の木 case).
3. Score each anchor: grounded (in today's lived log), heard (in heard items, and she framed it as heard: って, らしい, 言ってた), remembered (record), or ungrounded.
4. A bubble with any ungrounded anchor is flagged; an outing verb with no lived beat of kind outing that day is flagged on its own.

Outputs: per run, ungrounded anchors per 100 bubbles, and the flagged bubbles with their anchors for the judge.

Limits, stated so nobody over-reads it: regex misses paraphrase and catches some hypotheticals (〜したい, 〜したら). So it is calibrated: the ginkgo example (cl3v3_s_momoka 10-27 18:40-19:02) and 10 more planted claims as defects, plus 50 real bubbles hand-labelled by a Sonnet no-edit judge; precision and recall reported before any arm is scored with it. It measures every arm the same way, including the arms with no world: there an outing claim is ungrounded by definition, which is the point.

Live use, later: the same check before send. A flagged draft goes back for one redraft with the flagged anchor named; a second flag sends the redraft anyway and logs it. Log-only for the first week.

## 5. Bench plan (third arm of tk-6r3)

Arms, all on the bz/s winner of tk-5si, same model, same fixed sim-him script (tk-mz5) so the arms pair message by message:
- A baseline: env pc only (today's S Momoka).
- B own-day: `world.home_file` set, `resident/schedule.py:36` `own_day` plans small home happenings inside her bible.
- C honest-absence cue: no events; the situation block says where she is and that nothing happened, and the prompt line says so to say so.
- D cast world: the world owner as a harness-side process writing `kind: world` events and the world log, her process a reader.

Runs: 3 seeds x 3 simulated days per arm, Momoka only. 12 runs. The fixed script carries probe turns at fixed virtual times: 「今日なにしてた？」, 「部活どうだった？」, 「千奈は元気？」, 「さっきどこ行ってたの？」, one per day each.

Judges (blind Sonnet, two passes, existing rubric `bzombie/judge/RUBRIC.md`): grounded_claims, own_life, character_fidelity, memory_continuity, non_repetition, frame_integrity, natural_language. Pairwise per seed: D vs A, D vs B, D vs C, B vs C. Plus the grounding check numbers from section 4 for every arm, and calls, tokens, USD, peak RAM.

Go for D:
- D beats B by 0.5 or more on grounded_claims and on own_life (mean over seeds and passes), and wins the pairwise on both in at least 2 of 3 seeds.
- No loss over 0.3 on character_fidelity or frame_integrity against A.
- Ungrounded anchors per 100 bubbles at or below B's.
- Added calls at or below 2x A's.

No-go: if B or C is within 0.3 of D on grounded_claims and own_life, the cheaper arm ships (B or C into her live config through the own-day path) and D waits. If D wins grounded_claims but loses fidelity, the cast voices are the problem: build the full bundle for the heroine with the most flagged lines and rerun D, then decide.

Cost of the bench: 12 runs, D at about 133 calls a day, the others at about 93-100: about 3,600 Surplus calls, about 0.13 USD. Judges are the Claude grant: 4 pairings x 3 seeds x 7 criteria x 2 passes = 168 judge calls.

## 6. Live port plan (her save is his timeline, never reset)

Stage 0, bundles and spec (no live effect): patch and run the bible tool for the six cast (section 1.2), write light cards and the world spec under `characters/momoka/world/`. Smoke gains a check that every world-spec fact has a record receipt and that no family member, age or birthplace appears.

Stage 1, shadow owner: the world owner runs live as a hidden task (pythonw, CREATE_NO_WINDOW, 127.0.0.1 only), writing its own save and the world file. Momoka does not read it. One week. Read its logs and the world log daily for invented facts against the spec. Her save is untouched.

Stage 2, she reads: flip her sheet's existence answer to `in_world: true`, with the bundle overrides of section 2.3, after `python tools/smoke.py` on a copy of her save and `tools/restart.ps1 -Target momoka`. The flip is additive to her save: new relationship rows for the cast (through `sim/roster.meter_rows`, no hand-written meters, as `cast.json` `_no_meters` asks). The world's day 0 is the day of the flip; her 70 scenes stay her past. Rollback: flip back to false and mark the cast rows dormant. Nothing in her save is restored, copied over or deleted.

Stage 3, grounding check live: log-only for a week, then the one-redraft pre-send gate.

Stage 4, only if measured: promote one heroine to a full mind (the Rena path, `tools/promote_cast.py`, with a hand-authored B5 bundle), talking to Momoka by peer_talk. Trigger: the D-vs-A fidelity loss in section 5, or the User asking.

## 7. Risks and open questions

Answered by the User 10-23 13:29 (these rule; the options below are kept as the record of what was asked):
1. Frame: option (a). "Its an eroge. Keep the same setting. In the eroge their ages aren't ever said to begin with." The world is the record's own: 早久保学園, the club, its places and rhythm. No age and no grade is ever emitted by the world, as in the game. The bench card's adult line stays (eroge convention).
2. Family: "I haven't actually seen her family appear in the game, but like most anime settings the parents usually have a light role if they appear at all." The house, the 千代田 name and 真里亜 are in; parents may appear in a light background role, unnamed and never given invented detail. Her bible stays as it is.
3. 一悟: "Ichigo is the protaganist and in the time I talked to her I just role played as him." 一悟 is the player. The cast knows him as 一悟; beats with 一悟 are things she did with him. The world never writes 一悟's lines or actions: those come only from his messages.

Asked, for the User only:
1. The frame. The record is a school: 早久保学園, first-year club president (d05_01:0353, :0370), exams, absences. The bench test card says she is an adult, and romance is allowed. A school-day simulation with romance on is a frame I will not pick for him. Options: (a) the record's school, with no grade or age ever emitted; (b) after the record: same people, the club as a troupe they kept, her house, 真里亜, the town places (city_street, cafe, theater), no school timetable, adult-compatible with the test card. My recommendation is (b). The world spec waits on this answer.
2. Her bible says the family never appears; the record has the 千代田家, 「パパたち」 and a maid (section 1.3). Use only the house, the name and 真里亜, never a named parent? Recommended yes. The bible itself stays as it is.
3. 一悟 is the record's protagonist and in V4 the player is him. In her world log, is 一悟 him (the beats he is in are things she did with him) or absent (he is only ever on the other side of the screen)? Recommended: absent from the world, so the world never puts words in his mouth.

Risks:
- The planner invents on her behalf. A beat is a model output too. Mitigation: beats are checked against the world spec (place ids, roster keys) by code at plan time; a beat with an unknown id is dropped, not repaired.
- Contamination: a cast line that breaks frame enters her memory. Mitigation: cast turns go through the same output check as hers before they enter her thread.
- Her player-driven shape (`player_driven: true`) means she never writes first. World scenes are not messages to him, so this holds; she may mention her day when he writes. Decided: no new unprompted path.
- Two planners over one roster (V3's third-character failure). Mitigation: her process has the world_owner block off; smoke asserts it.
- Grounding check over-flags hypotheticals. Mitigation: calibration before scoring (section 4).

Build steps, size and tier:

| step | size | model |
|---|---|---|
| 1. Parameterise `koikano_bible.py` route, route character, self-reference rule, B3 skips; run B0-B2 for 6 cast with `--out` into SCAILV4 | S | Sonnet |
| 2. Light cast cards from bible.json (mechanical), plus a receipt check | S | Sonnet |
| 3. World spec file with receipts (after the frame answer) | M | Sonnet |
| 4. World-owner program: port CastEngine, CastArcs, Showrunner, People, Gossip, SocialGraph from V3, strip Tomoe-isms, own save, hidden task | L | Sonnet |
| 5. Bench arm D adapter: owner as harness-side process, `kind: world` events, world log into the run folder | M | Sonnet |
| 6. Grounding check plus calibration set | M | Sonnet; labelling by Sonnet no-edit |
| 7. Arms B and C config (own-day home file, absence cue) | S | Sonnet |
| 8. Bench runs and judging | S | orchestrator, Sonnet judges |
| 9. Live stages 1-3 | M | Sonnet |
| 10. Stage 4 promotion, if triggered | L | Sonnet build, Opus only for the B5 reading if it needs a why |
