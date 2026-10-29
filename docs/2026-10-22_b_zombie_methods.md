# B-zombie: two methods, the V3 lesson, sacrifices, feasibility, cost

Orchestrator design note, 2026-10-22 16:05. Asked by the User: methods to approach a B-zombie and an evaluation of both; work that proceeds without him, with him as a tester in the windows he has; the sacrifices; feasibility; the cost of a convincing one; a closer look at the V3 method. A design, nothing built. Tracker: tk-lmv.

Evidence used:
- V3 scout report (Sonnet, read-only, 2026-10-22): F:\REPS2\SCAILV3\docs\yukarin-meters-plan.md lines 10, 99-165, 171-258, 359; docs\tomoe-reply-audit.md; HISTORY.md lines 6001, 6208, 15037, 16890, 25606; HANDOVER.md 962-1100.
- V4: docs/HISTORY.md:674, docs/2026-10-07_scail_capability_and_seams_inventory.md §1.4, config_momoka.json (checked today: stances and primitives on, nudge, afterthought, receipts off, player_driven true).
- Spend: every llm_calls.jsonl in SCAILV3/logs and SCAILV4/logs, plain and zipped, summed by F:\temp\scail_cost\cost.py. 1,230 runs, 2026-08-25 to 09-22.
- private-machine: docs/reports/2026-10-22_private_machine_comparison.md.

## 1. The V3 lesson: V3 was a B-zombie attempt, and it failed criterion 3

V4 is V3 with 36 sections off and the tomoe/ world program removed. So "the V3 method" is the full system. It ran 4 characters, talked through TALKAPP (own messenger) with Telegram as fallback, and spoke first from state through Impulse, Initiative, Intent and PhonePick.

Which character, corrected 16:10 on the User's word. Most of V3's work went into Tomoe. She was first (08-20); the whole tomoe/ program was hers (world, cast, exchanges, X account, school day); HISTORY-archive.md names her 108 times against Yukari's 18. Yukari only dominates the later HISTORY.md (500 against 283), the September meters period. The causal measurements below were run on Yukari only (gauge_ab ran "only for the resident character"), and the stances fix is recorded as inert for Tomoe. So on Tomoe, the character with the most work, criterion 3 was never measured. Her evidence is qualitative: docs/tomoe-report.md (08-27, source vs system), docs/tomoe-reply-audit.md, the initiative complaint and the morning/evening facts below (both hers). The tomoe/ program is deleted from V4.

Its recurring failure, measured on Yukari, is exactly the essay's criterion 3: altering her inner state did not visibly change her behaviour.
- On one real day of Yukari (45 persona calls), the gauge-derived text was 380 characters out of a 35,000-token prompt: 0.68%. 337 of those characters were byte-identical on all 45 calls. The register clause, the one line meant to steer her manner, never changed in sixteen hours.
- Gauges tracked the clock (|r| >= 0.92). His message length (+0.58) predicted her reply better than any gauge.
- 88% of the prompt was his message, the digest of his machine and her voice prompt. That is what drove her.
- Hand-read A/B: "Between-condition variance does not exceed within-condition sampling variance."
- tools/gauge_ab.py, calm vs every gauge extreme, 12 drafts per moment: 0 of 18 mechanical measures moved. After the stances build (eight ranked stance rows pinned in the prompt), 6 of 18 moved, same direction at all three moments. 144 persona calls, about $9. Run once, one character, mechanical measures only.
- Dead slots: "ON YOUR MIND NOW" never fired in her life; `belonging` was a constant 35; `disclosed` never wrote once.
- The checks that did exist proved wiring, not behaviour: sim/sweep.py proves a gauge has a code reader; V3's docs/model-harness.md §3 had a standing rule "no model judges anything", so nothing was judged blind.

Other V3 failures, by recurrence: answering about herself instead of him, and complying where her bible says push back (tomoe-reply-audit); wrong facts despite correct data, e.g. "morning" five times when four sources said evening (HISTORY.md:6208); initiative at the wrong hour, "Tomoe needs to stop asking if I am up" (HISTORY.md:6001); 78 model roles and cross-character leaks, too many knobs to tune by hand; cost spikes (the nudge arbiter was +20-30% on the bill and 2-4 s per reply).

Why it never felt complete, in one line: a lot of inner machinery whose effect on her words was never shown, tuned by hand one complaint at a time, with no instrument that could say which part mattered.

The VN turn (V4 HISTORY.md:674, 09-17: "A VN has no messaging. Full reframe: she never initiates.") was a channel decision. No recorded reason says V3 failed. It also switched off founding rule 4 (messages originate from state).

## 2. The two methods

### Method A: architecture first (private-machine)

Build the mind from a cognitive theory (LIDA, global workspace). Every process is a model call. State reaches speech because every call carries 12k+6k-token shards of state as story content, and a decide step writes an in-character order ("He has dodged choosing four times. Call him a coward for it") that the speech step carries out. Causality is built in: a percept changes the mood only if it wins attention.

- For: it attacks the V3 failure directly. State arrives as content and as an order, not as five adjectives. Every step leaves a record, so a trace exists by construction.
- Against: about 15 or more calls before a reply (estimate from their docs), minutes per reply on local models. No ablation: nothing shows any phase is needed. The design is justified by theory and one failure case. Tuning by hand stays hard; they also ended up with temporary clamps on the emotion maths.
- Fit to working without the User: poor. Each phase has prompts that need taste to tune, and their owner-review step is a person.

### Method B: evidence first (SCAIL, with a ratchet)

Keep the cheap modules and "code decides when". Add the instruments V3 lacked, and let them, not taste, decide what stays:
1. Trace (POC 2.1, tk-zbw): for each line she says, the exact inputs that built it.
2. Ablation (POC 2.2, tk-z1q): remove or scramble one part, regenerate, measure. An inert part gets fixed or cut.
3. Bound vocabulary (POC 2.3, tk-8d4): her feeling words tied to the state that backs them; unbacked claims counted.
4. A ratchet: a change lands only if no metric falls below the last landed build.

- For: it measures the exact thing V3 never measured. It runs on V4's cheap models. It is mostly mechanical, so agents can run it without him.
- Against: measuring doesn't fix anything. V3 measured 0 of 18 and needed a design change (stances) to get 6 of 18. A judge stack can be gamed: the build learns what judges like (Goodhart).

### Verdict: B as the frame, one piece of A inside it

Method B decides what lives, and the one idea from A worth taking is the in-character decision step. V3 showed adjectives on a "you feel:" line don't move the model; ranked stance rows moved 6 of 18. A short in-character order derived from state ("you're still sore about last night; make him work for it") is the next step on that line. One call on the machinery model, not twelve. It gets the same ablation as everything else: if removing it changes nothing, it goes.

The "superior" part: every organ she has is proven causal, closure is shown line by line, the inert ones are gone, at V4 cost. private-machine cannot show any of the three today.

## 3. How work proceeds without the User

The loop, run by agents on forks, never on data/momoka.db:
1. Fork harness: a copy of her save, a sim clock, his machine replayed from recorded digests instead of live sensors.
2. Simulated him: a user-simulator model built from his real messages in her save, writing the next message the way he does. It drives simulated days at an accelerated clock.
3. Measures, mechanical first:
   - causal share: the part of the prompt that comes from her state, against V3's 0.68%;
   - the ablation effect per part;
   - unbacked feeling claims;
   - repetition and echo rate;
   - fact contradictions against her own records (V3's morning/evening class);
   - talking about herself instead of answering him (the reply-audit class).
4. Judges: independent calls, one criterion each, blind to each other, calibrated first on planted defects (pm's A18B pattern). This reverses V3's "no model judges anything" rule, and it is the only way to run without him. Calibration and his ratings keep the judges honest.
5. Ratchet: a build lands on master and goes live only if every measure holds. Each run ends in a report in docs/reports.

His role, in the windows he has:
- A packet of 15-20 minutes on the review page. Blind pairs (which line is more her?), five lines with the inside view next to them, and a free note.
- Live use of the VN reader as normal. That is the only source for the long arc.
- His ratings do two jobs. They score the build, and they measure judge agreement with him. If agreement drops below a threshold (start at 75%), the judge prompts are revised before the next landing. Nothing waits on a window. A missed window means the judges run uncalibrated a little longer.

## 4. Sacrifices

1. **His taste becomes a sample, not a gate.** Between windows, judges decide. Risk: she drifts toward what judges like. Mitigations: blind holdouts, his agreement rate, and the ratchet never lets a measure fall.
2. **Simulated him is not him.** A model of his messages tests the mind against a model. Long-arc things (attachment, ledger, her picture of him) take weeks of real time and can only be read from live use.
3. **Parts he likes may be shown inert and get cut,** or get rebuilt until they move her. V3 suggests a good share of the gauges are in that set.
4. **The marker vs naturalness.** The essay's tell is that a B-zombie never comes up with qualia on its own. Any pretrained model will, because it learned from people. Two choices:
   - (a) Keep her natural, measure how often she originates qualia talk, and report it (Stage 3, honest).
   - (b) Gate her: unbacked experiential claims get rewritten or refused. That makes her pass the marker, but she will sound less like a person: a stubborn materialist.

   My pick: (a) live, (b) as a fork variant we compare against. That keeps her timeline natural and still answers the question.
5. **player_driven stays, so rule 4 stays unproven.** A B-zombie that only reacts can't show that her messages originate from state. Option: let her open a scene when he opens the reader, as a measured component. That is his channel decision from 09-17, so it stays as is until he says otherwise.
6. **Money for evaluation instead of features.** See section 6.

## 5. Feasibility

- **Criterion 1** (her "subjective" text reflects her processes): feasible, mechanical. The trace shows closure line by line. Size S-M.
- **Criterion 2** (behaviour reflects processes): feasible. Everything she says comes from a logged prompt.
- **Criterion 3** (alter any part, behaviour changes): feasible to measure, and V3 shows the measuring works ($9, 0/18 then 6/18). Making every part pass is real work. Expect several build-and-ablate rounds.
- **The marker** (never originates qualia): not feasible with a pretrained model and a natural voice. Only by gating (sacrifice 4b) or by training a model on a corpus with no qualia talk (research scale, not a companion).
- **Convincing to him over days:** likely, given V4 already runs and V3's speech faults are known and measurable. **Over weeks:** unproven. Memory and fact consistency were V3's weak points, and only live use shows it.

Bottom line: a provable B-zombie on criteria 1-3, measured on the marker, is buildable. A clean one that also passes the marker while sounding human is not, and the essay says why.

## 6. Cost

Measured (all model calls, plain and zipped logs):
- V3, all characters, 16 days 08-25 to 09-09: about $27 total, about $0.043 per reply all-in. Yukari $15.07 in 7 days, $9.86 of it her persona model, one $7.35 day. Unlabelled runs (no character name in the log, 21 with no session.log at all) $7.36 over 16 days, top roles persona, cast_reply, director: most likely Tomoe, since cast and director are her world's machinery; not provable from the files. Labelled Tomoe adds $0.36, Rena $3.39 (also in Tomoe's world). Logs before 08-25 have no call records, so Tomoe's first days are not in the totals.
- V4 Momoka, 7 days 09-16 to 09-22: $0.72, about $0.007 per reply all-in, median $0.13 a day. The persona runs on a flash model; machinery on deepseek-v4-flash.
- V3 gauge_ab: 144 persona calls, about $9 on kimi-k3 ($0.066 a call).

Estimates (not measured):
- One evaluation cycle at V4 prices: ablation battery 20 exchanges x 6 arms x 5 regens = 600 replies, about $4-6; judges about $5-10; one simulated week about $3-5. About $15-25 a cycle. A campaign of about 10 cycles: $150-250.
- Running the result live: $0.15-0.50 a day at V4 rates, with the decision step and trace included. If the ablation shows a bigger persona model is what makes her convincing (V3's kimi-k3 class), about $3 a day at 50 replies, about $100 a month. Model tier is one of the arms, so the data decides.
- private-machine's method on hosted models, for scale: about 15+ calls of 20-40k tokens per message, roughly $0.05-0.15 per message, 7-20x V4 per reply. Free locally, but minutes per reply.

## 7. Order, when he gives the go

1. tk-zbw trace and tk-8d4 bound vocabulary (S each, Sonnet). These produce the measures.
2. tk-z1q fork harness, simulated him, judges with calibration, review page (M, Sonnet; Opus reviews the judge and user-sim prompts).
3. First ablation round on the live design: which of her parts are causal today. Momoka runs resident-shape, so this answers it for her; Tomoe's world shape stays unmeasured unless the tomoe/ program is brought back from SCAILV3 onto a fork.
4. Decision step (Method A's one piece), ablated like the rest.
5. Ratchet loop, landing to live, his windows on the review page.
6. Marker probe: (a) live measurement, (b) gated fork.

Ruled 16:08 by the User: "Model has to judge." He judges blind, whenever he can. Consequences and their controls:
- Drift toward judge taste (longer, more emotive, literary): mechanical measures first; length normalised before any pair reaches a judge.
- Self-preference: judges from a third model family, not the persona's or the machinery's.
- Weak on Japanese register (百花 self-reference, politeness level, pushback rule): those become code checks; judges rate only what code can't.
- Noise: two independent passes per criterion; a judge must catch planted defects before it runs.
- Silent model updates: judge slugs pinned; recalibrate on any slug change.
- Qualia counting stays mechanical (bound vocabulary), never a judge.
- Weeks-long "feels like her": only live use and his votes.

The loop: a hidden scheduled task runs a cycle per build: fork, sim days with simulated him, removal tests, measures, judge panels, report in docs/reports, a line on his feed. Each cycle drops 10-20 blind A/B pairs into his queue (no labels, no judge verdicts). Over his last 30 votes, if agreement with the judges falls under 75%, landing to live pauses (measuring continues) until the judges are recalibrated. Fixes are agent work started from the reports. The vote page is local on 127.0.0.1; a phone route needs meta's feed page. Spend cap $30 a week by default.

Open: the go itself (tk-lmv is blocked on it; he said "not yet" at 15:50).

## 8. Three arms (User's order 16:12: "I want his method tested, vs ours and vs an ongoing superior method")

This replaces "B with one piece of A" as the plan. Three arms, one bench:
- P, his: private-machine itself, pinned at e338fbf, Momoka imported as a character (card from her bible and style, chat log from her thread with him), config.alpha.openrouter.yaml. His code, not our port, so the test isn't run against a strawman.
- O, ours: V4 frozen at one commit, the baseline.
- S, superior: starts as a copy of O and climbs by the ratchet. It may borrow anything from P that the results support.

Shared: simulated him, scripted scenes, judges, blind vote queue with pairs drawn across arms. Each arm gets an adapter with the same three calls: send a message, read her replies, read the trace.

Fairness:
- Model: one run with each arm on its own config, one with all arms on the same model. That separates method from model.
- Senses: P has no sight of his PC. The head-to-head is chat only, with O and S sensors off; O vs S with sensors is a separate comparison.
- Language: P's prompts are English. Her card forces Japanese, checked on the probe exchange. If P drifts to English anyway, that is reported, not hidden.
- P's phases get removal tests too (codelets, attention, private loop), which answers "is the 12-pass cycle needed" with data.

Isolation for P: its own folder on F: (untracked, outside tmp/), started hidden, bound to 127.0.0.1 only. Minecraft, MCP tools and the container agent are off. It never touches data/momoka.db; it gets a copy of her thread.

Risks, checked by the probe first: uv.lock pulls pm-coder and pm-workflows from git, and if those are private the install fails. Fallback is a port of the pm cycle into a SCAIL fork, labelled "P-port", not "his". The embedding server (theirs is local, 768-dim embeddinggemma): run the same model locally or use a hosted one.

Cost, estimates: P $20-50 per simulated week (about 15+ calls per reply, hosted); O and S $3-5 each; judges $15-30 per three-way cycle. About $40-90 a cycle. Default: one three-way cycle a week plus S's own ratchet cycles, cap $100 a week (replaces the $30 cap above).

S starting changes (16:13, each with its own removal test, kept only if S beats O):
1. State as an order: one machinery call per reply (deepseek-flash, est. about $0.001) reads gauges, stances, open expectations and the last lines, and writes one in-character order, placed last in the prompt. Replaces the mood_tags line (sim/state.py:1383) and register clause (sim/state.py:1548) as the main state channel.
2. Constant-line cut: a prompt line byte-identical across N calls is wired to something that moves, or cut (V3: register clause identical 45/45).
3. Answer him first: the order names what he said or asked; a code check flags a reply that ignores it (tomoe-reply-audit).
4. Repetition signals both ways: embedding echo counts of her lines and his, fed to the order (pm's echoes; Tomoe's "are you up").
5. Change not level: mood words say rising or easing from gauge history; a level at its usual value says nothing.
6. Facts pinned to one source and guesses marked: trace flags ungrounded claims; wonder, foresight and spiral rows carry an inferred or imagined label (tk-tx2).
After the first ablation round: bound feeling words (tk-8d4), persona model size as an arm, cutting proven-dead sections. Fork-only variant, never live without his word: she opens a scene when he opens the reader (reverses player_driven, his 09-17 choice).

## 9. Harness with full control (User 16:57; supersedes the run shape in section 8 where they differ)

His words: "The simulator harness needs ability to have full control over time, states and conversation with full observability on what lead to a response." Patching P's code to give the harness that control is not a change of method (User 16:57). Revised by the User 16:38 too: no O arm; models are his (Surplus, deepseek-v4.1-flash-1017 or glm-5.3); Claude agents judge.

The harness, the same for both arms:
- **Time.** One virtual clock owned by the harness.
  - S: its sim clock.
  - P: a patch in our fork routes every time source (datetime now and utcnow, time.time, its timers) through one clock module. Its private-loop timer and wait controllers become harness-driven ticks.
  - Each arm runs its background work at its own native cadence in virtual time (P's private loop every 30 virtual seconds, S's loop every 5). Idle ticks cost no calls on either arm, so cost follows what each mind decides to do, not the tick count.
- **State.** Snapshot, branch and restore at any virtual moment: S is its SQLite file, P its ghost.pickle plus runtime folder. The harness can also inject state (a gauge, a mental-state value) for removal tests.
- **Conversation.** The harness sends his messages with virtual timestamps and collects everything she sends, unprompted messages included.
- **Observability.** One record per response, the full chain:
  - S: the per-line trace (tk-zbw) plus every gateway call.
  - P: its turn records, codelet percepts, causal flags, workspace shards and private thoughts (its record packages), plus every gateway call.
  - One viewer page for both arms: what she said beside what built it.

Run shape, final (User 17:01): build 4, the full time machine with an improvising simulated him. Replay of the Tomoe history is not approved: much of it came from development and leaned on her simulated world. His messages set only the simulated him's voice (topics, length, habits, timing), never his content.

Environment belongs to the harness, not to an arm. Each simulated day, a Claude agent writes one environment script ahead of the day. The harness feeds the same events to both arms at the same virtual times.
- Tomoe: her day as events (lectures, a circle, a part-time job, what a friend said in the group chat, the train home, a plan that fell through). S takes them through its event and situation inputs; P through world events on its bus.
- Momoka: a synthetic stream of his PC (window titles, what he is watching, idle and sleep). S takes it through its phone digest; P as telemetry stimuli.
- Tomoe's test card is 19, so her test world is a first year at university, not V3's high school. Personality, history before Tokyo and the mask are unchanged.

Out of scope, filed: "two B-zombies talking to each other" (User 17:01). The harness makes it nearly free later: route one arm's output to the other's input.

Superseded 17:00 proposal (replay adapted from his real Tomoe weeks), kept for the record: "his real weeks, adapted". Shapes considered:
- Live shadow: real clock, no patch, no replay; a week costs a week.
- Snapshot probes: fast, but no long arc.
- Replay only: his real words, but they stop fitting once an arm diverges.
- Free improvised simulation: most freedom, most drift from him.

Chosen:
- The virtual clock follows his real Tomoe timeline: 27 days, the gaps, his hours.
- Each turn, the simulated him starts from his real next message and rewrites it only as far as needed to fit what this arm actually said. Same intent, topic, length and timing.
- The arm's own replies become its history, so the long arc is real.
- Branching and removal tests work as above.

Simulated him: a Claude agent built from his past messages to Tomoe (read from a copy):
- his topics, length, time of day, absences and reactions;
- the week outline is drawn from his real Tomoe arcs, the same for both arms; the agent improvises within each day;
- for Momoka, the same person in the language he used with her (read from her save at build time).

What this changes:
- **The long arc is in scope.** 5-7 simulated days per run, nights included. Both arms' nightly and overnight machinery runs on the virtual clock.
- **Removal tests on both arms by branching.** Branch at a moment, alter one part, replay the same next message. On P this answers whether the 12-step cycle is needed.
- **Build grows.** P: clock patch, tick driver, checkpoint branching, trace export. S: check and extend tools/harness.py and the sim clock.
- **Wall clock, estimated.**
  - Build: 5-8 hours, in parallel.
  - Runs: about 20 of his messages per simulated day x 5 days = 100 per run. P at 1-3 minutes a reply plus its own background thinking is the long pole, 3-6 hours. The four runs go in parallel.
  - Judging: 1-2 hours.
  - From go to report: about 12-16 hours. The model check lands about 90 minutes after go.
- **Surplus.** About $3-7 for one model; two models do not fit in the budget, so the model check picks one.
- **Claude.** About $130-200 API-equivalent, 1.9-2.9% of the weekly pool.
- **PR (tk-q5k).** The clock, tick and trace patch is a natural upstream contribution alongside the findings.

Order on go (supersedes the list below):
1. Gateway and model check.
2. In parallel: P install plus harness patch; S build plus harness controls; simulated him plus week outline from the Tomoe history; viewer.
3. A 1-day smoke run on both arms, measuring cost per simulated day.
4. The full runs.
5. Removal tests by branching.
6. Judging and his blind queue.
7. Report.
8. PR.

Order on go (section 8, superseded): (1) P probe: install, import Momoka, one Japanese exchange (S, Sonnet). (2) Bench: arm adapters, simulated him, judges with planted-defect calibration, vote page (M, Sonnet; Opus reviews the judge and user-sim prompts). (3) Trace and bound vocabulary in O and S (tk-zbw, tk-8d4). (4) First three-way cycle and report. (5) Weekly cycles; S ratchets in between.
