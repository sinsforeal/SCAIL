# SCAIL vs private-machine: comparison, ideas to take, suggestions back

Orchestrator report, 2026-10-22 15:41. Asked by the User: review flamingrickpat/private-machine, compare with SCAIL, list what we could improve and what they could.

What I read. Theirs, at commit e338fbf (2026-10-21): README, docs/concepts/architecture.md, docs/ghost.md, docs/subsystems/{cognition, emotional-dynamics, codelets, private-ontology, introspection, private-loop, experienced-memory, cognitive-evaluation}.md, docs/work_items/alpha-plan/previous-attempts.md, dev/review/README.md. Docs only, not their code; every claim about them below is what their docs say. Ours: docs/2026-10-14_what_scail_is.md, docs/2026-10-14_b_zombie_poc_design.md, headers of sim/attention.py, sim/appraisal.py, sim/wonder.py, sim/expectations.py, sim/state.py:1383 (mood_tags), sim/sweep.py:11.

## 1. One paragraph each

**private-machine (pm).** An AI companion harness built as a cognitive architecture: LIDA and Global Workspace Theory, ported from four earlier generations of the same author's code. Every stimulus runs one fixed 12-phase cycle (intake, triage, appraise, retrieve, codelets, structures, attention, experience, goals, decide, route, commit). Twelve "codelets" (boredom, wounded pride, jealousy, a joke, recall an analogous episode, theory of mind...) compete; winners enter workspace shards; only what wins attention becomes causal for the mood. A second timer loop thinks privately every 30 s. Runs on local Qwen; the README calls it "SLOW AF" even at 400 tok/s. Optional Minecraft body and MCP tools. Character is a card plus personality values; any character can be imported. Heavy evaluation: a 16-scenario conversation suite judged by independent reviewer panels, plus a human review desk.

**SCAIL.** A mind library of about 100 single-purpose modules (sim/) on a 5 s loop, one character per process, one SQLite save. Rule: code decides when, a model decides what. State is 0-100 gauges plus per-person meters; she lives on his PC and sees it through digests (window trail, vault, MAL, VNs). Momoka is the one character, built from a game record (70 scenes verbatim). Hosted models via OpenRouter: one persona model writes as her, cheap models do machinery. Channel is the VN reader. Policing is structural (smoke.py: wiring, leaks, dead keys, dead gauges), not behavioural.

## 2. Where we match

| Idea | pm | SCAIL |
| --- | --- | --- |
| State lives apart from the user | mental-state vector with EMA over time | gauges drift per hour on her clock (sim/state.py:12) |
| Code decides when, model decides what | private loop: deterministic triggers, idle tick costs 0 calls | every module has a `due` gate (sim/wonder.py header) |
| Expectations settled against the record | ExpectationRecord pending/supported/contradicted/unmet; surprise feeds affect | sim/expectations.py: his `do`, `around`, `habit`, settled off the record, missed ones cost |
| Internal calls never in assistant voice | every call is "story writer simulating the mind from inside" (D25) | machinery roles think about her in 3rd person; nine voice roles write as her |
| Shared byte-equal prompt prefix for cache | StoryPrefix identical across a cycle's calls | bursts held to share a warm prefix, cache hit rate per role |
| Kill a mechanism nobody reads | none found in the docs I read | sim/sweep.py flags DEAD gauges; attention.py logs dead lines |
| Separate entities do not leak | stimulus groups get their own shards | smoke fails on a cross-character name/place leak |

## 3. Where we differ

| Axis | pm | SCAIL |
| --- | --- | --- |
| Shape | one deep pipeline per stimulus, ~12+ model calls before a reply | many shallow modules, most on their own schedule; a reply is mostly one persona call |
| Speed and cost | local, slow, "patience" is a stated requirement | hosted, cheap machinery models, latency is a designed feature (availability) |
| Emotion math | EMA baseline, z-score readout via tanh; shows change against recent mood, a level that holds reads as neutral. Temporary "ALPHA" clamps after one stimulus swung valence +0.78 to -1.0 | absolute gauges, deterministic drift to baseline, discharge when a gauge hits its limit, warmth judged once a day over the whole day (sim/appraisal.py) |
| Causality | a percept is `causal` only if it won attention; a felt state is `reportable` only if a causal driver exists | no per-reply causal record; attention.py ranks lines, kv `attention_last` keeps the last block only |
| Feeling words | private ontology: each word bound to an implemented state field; "smell" is not a word because no mechanism exists; unsupported labels flagged (advisory) | mood_tags turns gauges into at most 5 adjectives (sim/state.py:1383); nothing checks what she then says about her feelings |
| Self-knowledge | she can read her own source under a grant; capability beliefs per state (intended, implemented, enabled, observed) | none; persona static, she owns 70 scenes, no self-inspection |
| Canon | imported history is "background": proves what the source says, not lived senses | the bible is what she actually did; canon is her lived past by design |
| Reality labels | every private thought tagged observed / remembered / internal / inferred / imagined | grep for imagined, inferred, reality in sim/record_guard.py, known.py, self_memory.py found nothing |
| Inner monologue | one loop, 15 operations, disclosure choice candid/withhold per thought | spread over wonder, reflect, diary, spiral, foresight, withholding, each its own module |
| World | Minecraft body, MCP tools; she acts | his PC, MAL, vault, VNs; she watches |
| Regenerate | forbidden by design ("illusion is never broken") | VN reader has Change Reply and Jump (a VN feature, branch on a save) |
| Persistence | one pickle checkpoint rewritten whole per commit (113 MB with vectors); no durable bus replay | SQLite synchronous=FULL, kv `in_flight` rows, missed-call ledger with `catch_up`, unanswered message requeued once |
| Evaluation | A18B: 16 scripted conversations, 12 criteria, two independent panel passes, calibration on planted defects, frozen evidence, human review desk with a "Thoughts & routing" view | smoke.py (structure), test_vn_saves; no behavioural eval. The ablation in the B-zombie POC was never run |

## 4. Ideas to take into SCAIL (ranked)

1. **Per-reply causal record.** Store, per delivered line, what went into the prompt: admitted attention lines with weights, mood_tags, register, memory cards. pm keeps this as `causal` flags plus a turn trace. For us it is cheap (attention.py already computes it; it just keeps only the last block) and it is the data B-zombie instrument 2.1 (sign-graph trace) needs. Size S.
2. **Feeling-word ontology as a check.** Bind each Japanese feeling word (sim/lang.py `feeling_ja`) to the gauge that backs it; after a reply, flag a feeling she claims that no gauge supports at that moment. Advisory, log only, like pm. This is "red is only its relations" turned into a data structure, and it is the classifier B-zombie instrument 2.3 needs (bound term = relational; unbound claim = qualia talk from the corpus). Size S-M.
3. **Behavioural eval on a fork.** Scripted scenes run against a copy of her save, judged per criterion by independent calls that never see each other's verdicts, plus a page where the User rates replies with the inside view beside them. That page is the same thing as the two-column view in B-zombie 2.1, and the harness is the same one the ablation battery (2.2) needs. Size M. Biggest gap we have.
4. **Reality labels on her self-generated text.** wonder, foresight and spiral produce guesses; nothing I found marks them as guesses, so a nightly compile can turn one into a "fact" she later recalls. Tag each row observed / inferred / imagined and have recall render the tag. Size S-M; first an audit of compile and recall to confirm the leak exists.
5. **Felt velocity.** pm reports how fast a feeling moves, not only its level. mood_tags could add "rising" / "easing" words from the gauge history we already keep. Size S. Low priority.

Not taking: the 12-phase cycle per message (it is why pm is slow, and our availability rule wants fewer calls, not more); self-inspection of source code for Momoka (breaks a game heroine; worth it only on a fork as a B-zombie experiment); pickle checkpoints.

## 5. Suggestions for private-machine

1. **Do less per message.** Let triage return a budget of 0 and skip codelets, structures and attention for small talk; judge low-stakes appraisal in a daily batch over the whole day (our sim/appraisal.py does warmth once a night, which also smooths the one-stimulus swing their ALPHA clamps patch). Run machinery on a small model and keep the big one for speech.
2. **Bounded state instead of a z-score readout.** With a short history their scale is small and one change pins near a bound; that is the +0.78 to -1.0 swing. Gauges with a baseline, hourly drift and an explicit discharge event at the limit fail more gently. Or seed the scale from the personality prior.
3. **Persistence.** Rewriting a 113 MB pickle per commit will not scale with history. SQLite with WAL, or an append journal plus periodic snapshot. Add kill-safe in-flight rows: a paid job leaves a row, the next boot reruns or drops it; a read but unanswered user message is requeued once. Their docs say a crash after save can lose the bus event; this closes that.
4. **Availability as a feature.** Their companion is always present. Sleep, latency and not answering, driven from state and a learned rhythm of the user, are the strongest illusion lever we have found.
5. **Hold the user's word to the record.** Their expectations cover the companion's own actions. Ours also track what the user said he would do and when he is usually around, and a missed one strains a belief and can be raised later.
6. **Dead-mechanism sweep.** A codelet whose percepts never win attention, or a state axis nothing reads, should fail a check. Our sweep.py does this for gauges.
7. **Cross-character leak test.** They ship Sunny, Rowan and Spamuel with placeholder-only codelets.yaml; a test that boots each home and fails on another character's names in prompts would guard that.

## 6. Tie-in with the B-zombie POC

pm is close to an engineered B-zombie already: the ontology forbids words for senses it has no mechanism for, and the causal gate makes "subjective" reports follow the processes (criteria 1 and 3). It has the same Stage 3 problem we named: Qwen has read every human qualia report, and the ontology is advisory, so unbound labels still get through. Ideas 1-3 above are the POC's three instruments in engineering form, so building them pays twice. Two extra experiments their design suggests, fork only: run the origination probe with an ontology check on and off; and give a fork of Momoka read access to her own trace (not her code) and see whether she reasons like the essay's stubborn materialist.

## 7. Why pm runs a 12-phase cycle (added 15:50, on the User's question)

Sources: docs/work_items/alpha-plan/baseline/original-brief.md, decision-register.md (D16, D22, D25, D26, D28), cognitive-sources.md, work-items/a19f.md.

1. **Theory first, from day one.** The brief names the LIDA pipeline (Franklin's cognitive cycle: triage, appraisal, codelets, attention, goals, workspace, action selection) as the target; v0 `pm_lida.py` already ran all of it. Every generation since kept the shape and changed only how modular it was. D22 (10-18) rebuilt it as "a typed LIDA-style cycle", with old-generation code as the reference design.
2. **Speed was ruled out as a criterion.** D16 (10-14): quality over latency. D26: "Quality comes before speed. More agent sessions are allowed." cognitive-sources.md lists "fixed low inference counts or a faster response" as an excluded criterion.
3. **The failure that triggered the rebuild was voice collapse, not missing depth.** A19 review run, tick 816: only appraisal wrote in character; the workspace call had no character card and wrote a wholesome "mutual agreement" monologue; action selection turned it into a planner ticket; no codelet noticed the fourth repetition, so boredom stayed 0; 135 narratives were never used. Their fix was more separation: every call gets the card and the same story frame (D25), each codelet argues one concern at full strength with no softeners ("other codelets and attention supply the balance"), and capability rules move to a separate routing call so they cannot pull the decision into assistant voice (D28).
4. **The causal claim needs attention as its own step.** A percept changes the mood only if it wins attention; that needs a distinct attention phase whose output is a record.

What is not there: no ablation. Nothing in the docs I read measures what dropping a phase does to replies; A18B grades whole conversations. Only 9 of the 12 phases call a model (intake, retrieve and commit are Python), but codelets alone run 2 calls each (agent ones run whole sessions) and triage's budget floor is 1, never 0. So at a default budget of 4, one message costs roughly 15 or more calls before dialogue and its review. Their own "Departures" list calls shards, budgets and cooldown engineering choices, not LIDA requirements. The split is reasoned from theory plus one failure case, not measured.

## 8. Follow-up

Ideas 1-4 are filed in the tracker (owner scail). The B-zombie POC itself still waits on the User's four decisions in docs/2026-10-14_b_zombie_poc_design.md section 6.
