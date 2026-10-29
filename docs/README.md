# docs

**Every document in this project lives in this directory.** Nothing goes in a
`docs/` beside a module, nothing goes at the project root, nothing goes under
`yukarin/` or `tomoe_data/`. One flat directory, one file per subject.

Two generated files stay at the project root next to README.md: PROJECT.md (the reference, per module) and CONFIG.md (every config key, generated).

Three kinds of file are **not** documents and are left where they are: prompts
(`prompts/`, `prompts_yukarin/`), source material a tool reads
(`tomoe_data/tomoe dialogue.md`, `tomoe_data/tomoe friends.md`), and generated
views written beside their own data (`yukarin/persona/persona_view.md`,
anything under `yukarin/generate/<stamp>/`).

## The simulation, one file per module

| file | what it specifies |
|---|---|
| `docs/state.md` | the gauges, the meters, and the rules they live by |
| `docs/situation.md` | a situated body: the map, journeys, fatigue |
| `docs/cast-mechanisms.md` | each person around her as a set of mechanisms rather than a description: the files, who sees what, the cap, the check that a mechanism has a reader, and the type file no prompt may read |
| `docs/room-quality.md` | whether a room is a conversation or a loop: the eight measures and the tool that reads them off a save, the moves ledger both writers share, the sentence filter across all speakers, the staleness gate, pacing off the people who actually spoke, the daily pocket of concrete things per person, gossip that spreads, and the carry that has to move |
| `docs/stances.md` | attachment, withholding, rupture, the spiral, and the ranked table of what she does with what she has seen |
| `docs/primitives.md` | the psychological primitives everything relational reads |
| `docs/recap.md` | grounded watching and the Japanese knowledge base |
| `docs/dossiers.md` | one file per play he finishes: what it joins out of which table, where it runs and why the machine rather than a character, the two rules (finished is computed and never read off the site's rewatching flag; a franchise is grouped by title stem), and the two capped page reads that fill an actor's filmography and a missing premiere date |
| `docs/resolver.md` | which work he means: the whole path and the season read, the ranked resolution that refuses a tie, the id from his list beating the parse, the page a one-episode work cannot have, the key that names the work rather than a title two works share, and the one small role asked only when code has run out |
| `docs/regen-reply.md` | answering a message again on a copy, and putting the answer where the old one was |
| `docs/reactions.md` | her face, and the images made of her |
| `docs/talkapp.md` | the hub, the bot channel, the app |
| `docs/peer-talk.md` | two running characters talking to each other, and what a character is as a unit |
| `docs/shared-world.md` | the world as a file two processes read: one writer, eight tables, and what a promoted cast member still needs |
| `docs/bundle.md` | **the spec of record for what a character IS as files**: one directory per person under `characters/<key>/`, what its manifest says, the two verbs that compose her config and verify that none of it is somebody else's, where a bundle comes from (promotion, or forty synthetic ones), and the eight checks in smoke that hold it |
| `docs/promotion.md` | turning one of the people on the roster into a character who could run: what `tools/promote_cast.py` writes from her row, her sheet and her mechanisms, whose material may be used, the two prompts that need porting and why only two, what promotion cannot write, and what she still lacks before anybody starts her |
| `docs/agent-character.md` | **the reference for a character who runs herself**: the seven things she is not a character without, what promotion derives against what stays authored, sixteen numbered invariants of the runtime seam with the check that proves each and where it lives, the procedure from promotion to the day-two audit, the six lines to look for in the log on day one, and what none of it proves |
| `docs/character-layers-plan.md` | **a plan, not a reference**: the seam between the generic library and one character's own material, with a receipt for every place it leaks today (a default that is one person's file, a roster that has her on it twice and the owner not at all, meters seeded from the raw roster, a household read by three hardcoded keys) and twelve numbered steps that close it, each with the check that proves it. **All twelve are landed**; `docs/bundle.md` is what was built |
| `docs/neutral-roles-plan.md` | **a plan, and every step of it landed**: the thirty prompt files belonging to a role with no character sheet that asked a model to write what she felt, thought or would say, with the stored answer and one reader for each; the rule that replaced them (a role without her sheet writes the record, a role with it writes what that did to her); twelve numbered steps, the owner's five decisions, and the status table at its head |
| `docs/seamless-additions-plan.md` | **a plan, not a reference**: what promoting or adding a character still costs by hand after the bundle and the compose/verify tools (the eleven-row table from the Hinako promotion proof), the five things a single shared world cannot yet give a new reader (no second writer, no clock check, no reader cache, no group room of her own, the owner planning her beats), and ten numbered steps with the check for each |
| `docs/language.md` | which language a character is addressed in: the arm over everything the prompt builder writes, the one line that carries the 29 roles who wrote the sentences under it, the five roles left in English on purpose and why, a table of where every piece of her prompt gets its language, and `/lang` |
| `docs/role-check.md` | was she in it: the three-state verdict from the machine's own MyAnimeList mirror, the two witnesses a flat "no" needs, where the line lands and what the continuity check is handed; the audit of what the mirror holds and what it therefore cannot answer; why the community wrapper is not the source |
| `docs/context.md` | **the spec of record for her context**: the two halves and the provider's cache, the one thread with bare assistant turns and the world's lines after them, the curve by clock (seven days verbatim, thirty of cards), where a retrieval lands, the final turn's order, the one budget, the cast members' threads, the tells and the tests |
| `docs/memory.md` | **the spec of record for what she remembers**: the five stores, the forgetting curve, the moment as one cue, search by meaning off the local embedding, and which retrieval reaches which part of the prompt |
| `docs/retrievals.md` | the machine's one store of what was fetched about the world: the schema, the claim that makes a fetch happen once for both characters, what goes through it and what stays per save, the boot migration |
| `docs/her_own.md` | the corner of her life that is not about him |
| `docs/ick-primitives.md` | what she finds off-putting, and why |
| `docs/context-architecture.md` | what her prompt is made of, measured, and the tiered shape proposed for it to grow into (draft, his decision) |
| `docs/episode-summaries-plan.md` | how the character learns what happens in an episode, graded, and the plan for accurate summaries (sources ranked, subtitle files as the anchor, Whisper as proposal only) |


## Method, and the machine

| file | what it holds |
|---|---|
| `docs/character-method.md` | **the one guide, and it supersedes every other document about making a character from material**: the premise (a card that matches the person in situations the material never contained), the nine invariants and the four source variants, the codebook as the unit, the two routes (written from a private prior, extracted from a corpus) and the seam between them, what can be measured and what cannot, every machinery rule paid for in money or a night's work, the procedure from material in hand to a character running, which tool runs which stage, the form of the three files the procedure has to produce, the seam to a running character, and what is still open |
| `docs/extraction-runbook.md` | **the page an agent follows** for a fresh subject: ten phases of numbered steps, each pointing into the guide for the reasoning, plus the four points where the honest answer may be to stop and the five failures most likely to be repeated |
| `docs/scail-concept.md` | the original concept, kept exactly as written because it is the origin: the six-step method, the mechanism sheet, six stated limits, and the worked example. Cited by the one guide, never edited |
| `docs/verification.md` | verifying a voice against its tape, the seven fallacies, and what no verifier here can do. Kept as written and cited by the one guide |
| `docs/codebook.md` | **the spec of the codebook file** (`data/codebook/`): the four generated files and the modules they are built from, the entry's schema field by field, the two statuses (anchored, and theory-derived where the scope names a behaviour the material does not reach), the rules for what becomes an entry, the version discipline that invalidates every `code` field when the version moves, and what the check enforces |
| `docs/pattern.md` | how a character is described, measured and filled. **A proposal nothing implements**, kept because its numbered evidence ladder is the vocabulary ten of the second character's documents and two of her live prompt files cite; the guide's §2.5 maps that ladder to its own tier field rather than replacing it |
| `docs/interpretation.md` | how she acts where the tape cannot vouch for her. **A proposal nothing implements**, and a design for a runtime subsystem rather than an extraction method, which is why the guide does not carry it |
| `docs/model-harness.md` | providers, hosts, and the ranking |
| `docs/system-one.md` | typesafe.ai's System One, a batched typed classifier with calibrated confidence, read against the project: what it returns, the six places on code's side of the split it could sharpen (reply checks, the did-anything-happen gate, appraisal as composite scoring, digest classification, codebook selection, test judging), where it cannot go (her voice, the pick, her eyes), the constraints if adopted, the one-provider decision that is his, and the access request describing the project |
| `docs/2026-09-17_jev_stage_roles_design.md` | **design**: moving `scene_director` and the judge-shaped stage roles onto Jev, with his rulings (withhold off, no quality_rewrite or editor), the roles that never move, and the light tests against existing output that replace shadow mode |
| `docs/2026-09-17_jev_stage_roles_implementation.md` | **implementation guide and record** for that design: the test tool built first, the `typesafe.uses` entries, the module to touch per role, the order to ship them in, the rollback, and -- filled in the same day -- which thirteen roles were built, which six stay on their role, and the four things running the tests changed about the design |
| `docs/2026-09-17_jev_stage_roles_build_notebook.md` | **build notebook** for the same day: the test tool's shape, SCAILV3's archive as the sample, the per-role agreement and floor tables, the wording that fixed `ick` and `intent`, the one-factor-per-question rule, and the roles that failed and why |
| `docs/openrouter.md` | the one provider seam: the request `llm.py` sends, the pinned host and the fall-through, what is read off the receipt, the prompt cache and the effort levels as measured on this project's own prompts, what is applied, and the open decisions with their numbers |
| `docs/tool-calling.md` | **live since §17: at every moment she has her phone (a block, a scene, a beat of her own people, a message from him) the model is offered the real choices and what it picks is what happens; the impulse function, the reply delay and the group-chat roll are the backup, the log says which decided, `/pick` reads the day back.** Sections 1-16 are the benches and the shadow run that led there: whether her reply call could ask for things instead of being handed them, benched twice on the model she writes on: **the wire works end to end when the call is forced** (fragments reassembled by index, arguments parsed, the result accepted back, the second step answering, no reasoning echoed) and **the model never asks** -- not with the material in her prompt, not with it removed and the tools named in the last line she reads. So a look would have to be code's decision. Also: which hosts of each pinned slug accept tools and why `require_parameters` is not optional, the change every function of `llm.py` would need, and the thread rule that a tool exchange is never a message; and §14, **the other test, run**: a call at a moment code already knows, asking what to DO rather than what to say, over forty-six real moments -- it picks like a person with a phone and like a like-everything machine after a scroll, and `LLM.call_tools` is the client method it runs on |
| `docs/building.md` | building and running the parts |
| `docs/performance.md` | where the elapsed time goes, measured from the system's own record: the split between waiting on the provider and local compute, the calls that return nothing and why the guards miss them, what a cached prefix is actually worth, what the daily compile and the pre-restart check cost, which parts of the performance-engineering literature apply to a system whose unit of cost is one model call and which do not, and the changes ranked by measured saving with what is still unknown |
| `docs/checks.md` | **generated** by `tools/checks_index.py`: every check smoke runs, in order, with the tool it runs and whether a failure stops a restart, and every hand-run test tool with what it checks |
| `docs/modmap.md` | **generated** by `tools/modmap.py`: every module in the live tree with its kind (shared, program, machine, runtime), its docstring, the wires it declares, the config sections and model roles it reads, its spec and the tools that name it |
| `docs/audit-and-expansion.md` | the pass after the cleanup review: the fills check, the existence matrix and the three faults it found and fixed, the two generated indexes, and what is left, ranked |

## Reports and reviews

Kept because their findings are still cited, not because they describe what
runs now. A claim in one of these is only current if `PROJECT.md` or the
relevant spec repeats it.

| file | what it was |
|---|---|
| `docs/review-2026-08-26-prompts.md` | a prompt and output review |
| `docs/review-2026-08-27-english.md` | what English is to this system |
| `docs/ab-judge-roles.md` | the judge-role A/B read: pro against flash on the first character's four judge roles, 40 pairs verified against the record |
| `docs/review-2026-09-03-cleanup.md` | the whole project read for cleanup and simplification: the live faults found, the shape of the complexity, and a phased plan, with a status table at its head saying what is done |
| `docs/review-2026-09-03-cleanup-receipts.md` | the five per-cluster reports behind that review, with every file:line receipt |
| `docs/memory-tiers-plan.md` | the plan for how her thread ages past thirty days: five tiers by clock (verbatim, cards with lines, cards, week cards, month cards), rehearsal and flashbulb exceptions, where each part goes in the code, and what to measure first |
| `docs/retrieval-agent-plan.md` | should a model choose what the situation block carries and what it pushes on: today's gate and second reader measured on four real turns, a design for a selection pass that can only pick from what it was offered, what it would cost on the loop thread, and the recommendation (fix four things in code first, then widen the second reader in shadow) |
