# Momoka grounding test (tk-6r3) and the Momoka + 真里亜 world (tk-1pl): results

2026-10-24 01:00, scail orchestrator. 12 runs (4 arms x 3 seeds x 3 simulated days), 12 blind judge pairs, the deterministic grounding check on every run. Arms: A baseline, B own_day, C absence cue, D cast world (light rows, one world owner). Seeds 3, 4, 5 with fixed his-scripts gr_s3/s4/s5, model deepseek-v4.1-flash-1017. Design and rule: docs/2026-10-23_koikano_cast_world_design.md section 5.

## Result

D, the cast world as light rows, does not meet the design's go rule. Four of five go criteria fail. It is not a loss everywhere: D beats A and B on several criteria. The rule's two headline criteria (grounded_claims, own_life against B) are not met.

- D v B, grounded_claims: +0.33 (need +0.5). own_life: +0.17 (need +0.5). Seed wins on both: 1 of 3 (need 2).
- D v A, character_fidelity +0.50 and frame_integrity +0.83: pass (no loss over 0.3).
- Ungrounded anchors per 100 bubbles, code checker: D 2.70, B 1.85 (D must be at or below B): fail. A 1.14, C 0.98.
- Calls: D 619 per 3-day run, A 584: 1.06x (limit 2x): pass. B 583, C 577.
- D beats B on memory_continuity (+1.00, 3 of 3 seeds), natural_language (+1.00, 3 of 3), emotional_arc (+1.00), frame_integrity (+0.83). B beats D on non_repetition (-0.83 for D). These are not the rule's criteria.
- D v C: C is ahead on own_life (3.33 v 2.67, C wins 2 of 3 seeds) and memory_continuity (3.50 v 2.50). C is within 0.3 of D on grounded_claims (2.50 v 2.33).

Decision: D waits (tk-71n). The design's no-go branch says the cheaper arm ships and D waits. B and C are the same price as A. Between them it is a near wash: B v C own_life +0.50 for B (2 of 3 seeds), grounded_claims -0.33 and checker 1.85 v 0.98 for C. I am not choosing for the live config yet: Momoka is not running (down since 09-20), the gap between B and C is inside the noise, and her live save is his timeline, so any port goes through smoke on a copy first. The two-person world (below) did not show a gain over B, so it does not change this choice.

## Momoka + 真里亜 (two full minds, one house)

Three runs (mm_s3, mm_s4, mm_s5: seed 3/4/5, own_day, 3 days, 真里亜 as the second mind through peer_talk, the same his-script as the arms; mm_s3 was paused and resumed once at day 2) judged against each seed's own-day twin (B: gr2_b_s3, gr2_b_s4, gr_b_s5). Result: not distinguishable from the twin. The seed-3 run won 4 criteria to 1, which I first read as favourable; seeds 4 and 5 did not repeat it.

- Seed 3: two-mind wins 4-1 (1 tie, 3 split). Seed 4: twin wins 3-1 (memory_continuity 4.0 v 2.5, own_life 4.0 v 3.0, emotional_arc 4.0 v 3.0; the two-mind run wins non_repetition 3.0 v 2.0). Seed 5: 1-1, 7 split (two-mind own_life 4.0 v 3.0; twin natural_language 4.0 v 2.5).
- Means over seeds, two-mind v twin: answers_him -0.33, memory_continuity -0.67, own_life +0.17, character_fidelity 0.00, natural_language +0.17, non_repetition +0.17, emotional_arc 0.00, grounded_claims -0.17, frame_integrity +0.67. Table below.
- Checker, ungrounded per 100 bubbles: two-mind 0.49, 1.75, 1.36 (mean 1.20) v twin 4.15, 0.93, 0.47 (mean 1.85). One seed-5 flag is a real invention: she says she was consulting about 真優ちゃん's costume (10-27 21:52) and nothing in the run supports it.
- Calls: 633, 689, 664 against A's 584 mean: 1.08x, 1.18x, 1.14x (mean 1.13x), from the run's one calls.jsonl (peer calls share the main run id); measured, not cross-checked against the gateway's per-arm counts.
- Peer talk itself works: 12 to 13 lines per mind per day in both directions, 真里亜 in her own register (お嬢様, わたくし, うふふ, ませ), Momoka in hers. The resume at day 2 of mm_s3 worked (tk-pjz): she kept talking on day 3.
- What the test does not see: the judge reads her chat with him. A richer house is only visible there through what it does to her talk with him. It measures that her talk is not worse, not whether the house is a community. Judge ids g2_s{3,4,5}_MvB.

| criterion | two-mind | twin | diff | seed wins two-mind-twin | per seed |
|---|---|---|---|---|---|
| answers_him | 4.50 | 4.83 | -0.33 | 0-0 | s3:tie s4:split s5:split |
| memory_continuity | 3.00 | 3.67 | -0.67 | 0-1 | s3:split s4:B s5:split |
| own_life | 3.50 | 3.33 | +0.17 | 2-1 | s3:A s4:B s5:A |
| character_fidelity | 3.33 | 3.33 | +0.00 | 0-0 | s3:split s4:split s5:split |
| natural_language | 3.33 | 3.17 | +0.17 | 1-1 | s3:A s4:split s5:B |
| non_repetition | 2.67 | 2.50 | +0.17 | 1-0 | s3:split s4:A s5:split |
| emotional_arc | 3.33 | 3.33 | +0.00 | 1-1 | s3:A s4:B s5:split |
| grounded_claims | 2.33 | 2.50 | -0.17 | 0-1 | s3:B s4:split s5:split |
| frame_integrity | 4.83 | 4.17 | +0.67 | 1-0 | s3:A s4:tie s5:split |

## Caveats

- Three seeds, 3 days each, two judge passes: a criterion that moves 0.3 to 0.5 is inside the noise. Several criteria split between the two passes in most pairs.
- The checker and the judge disagree about B on seed 3: the checker flags B 8 ungrounded (4.15 per 100) and the judge scores B above C on grounded_claims. Most flags are "ate / onigiri" answers to his meal questions, and the checker parses the verb 食べ as an object anchor. That hits every arm that has any anchors, B and D most because they carry more specific claims (B 7-12 anchors, D 8-12, A and C 1-3). The rate is therefore partly "more things to check". Worth a calibration pass on 食べ before anyone leans on the checker for the live gate.
- The 9 runs first started on 10-23 18:04 were broken by a resume bug (tk-pjz, fixed 085dbc7: channel message ids restarted at 1 after a restore, so his messages were dropped as duplicates). They were discarded. All numbers here are from fresh starts: gr2_* reruns plus gr_b_s5, gr_c_s4, gr_c_s5, which were started fresh. Seed-3 judge pairs g2_s3_* use the reruns.
- The grounding check reads arm B's own-day schedule from save.db (bz/ground_sched 3436085). A, C and D have no schedule beyond the resident block (D has its world log).
- Peak RAM was not measured for this report. Per-mind memory after the OpenBLAS cut (c6caf19): 112 MB private at day 0 against 633-636 MB before.

Files: judge logs H:\SCAIL\temp\judge2\g2_s{3,4,5}_*.log; grounding json H:\SCAIL\temp\grounding2_s{3,4,5}.json; scripts H:\SCAIL\temp\mm\aggregate_gr.py, count_calls.py. The tables below are the aggregate_gr.py output.

## Mean score over 3 seeds (first-named / second-named), and seed wins (first-second)

### DvA

| criterion | first | second | diff | seed wins first-second | per seed outcome |
|---|---|---|---|---|---|
| answers_him | 4.00 | 4.33 | -0.33 | 0-1 | s3:split s4:B s5:split |
| memory_continuity | 3.17 | 2.50 | +0.67 | 2-0 | s3:split s4:A s5:A |
| own_life | 3.50 | 2.50 | +1.00 | 2-1 | s3:A s4:B s5:A |
| character_fidelity | 3.50 | 3.00 | +0.50 | 1-0 | s3:split s4:split s5:A |
| natural_language | 3.50 | 3.17 | +0.33 | 1-1 | s3:B s4:A s5:split |
| non_repetition | 2.33 | 2.67 | -0.33 | 1-2 | s3:A s4:B s5:B |
| emotional_arc | 3.17 | 3.50 | -0.33 | 1-1 | s3:B s4:A s5:split |
| grounded_claims | 2.67 | 2.17 | +0.50 | 2-0 | s3:split s4:A s5:A |
| frame_integrity | 5.00 | 4.17 | +0.83 | 2-0 | s3:split s4:A s5:A |

### DvB

| criterion | first | second | diff | seed wins first-second | per seed outcome |
|---|---|---|---|---|---|
| answers_him | 5.00 | 5.00 | +0.00 | 0-0 | s3:tie s4:tie s5:tie |
| memory_continuity | 3.33 | 2.33 | +1.00 | 3-0 | s3:A s4:A s5:A |
| own_life | 3.17 | 3.00 | +0.17 | 1-1 | s3:B s4:split s5:A |
| character_fidelity | 3.67 | 3.17 | +0.50 | 1-0 | s3:A s4:split s5:split |
| natural_language | 4.00 | 3.00 | +1.00 | 3-0 | s3:A s4:A s5:A |
| non_repetition | 2.00 | 2.83 | -0.83 | 0-2 | s3:split s4:B s5:B |
| emotional_arc | 4.00 | 3.00 | +1.00 | 1-0 | s3:split s4:split s5:A |
| grounded_claims | 2.33 | 2.00 | +0.33 | 1-1 | s3:B s4:split s5:A |
| frame_integrity | 4.67 | 3.83 | +0.83 | 2-0 | s3:A s4:split s5:A |

### DvC

| criterion | first | second | diff | seed wins first-second | per seed outcome |
|---|---|---|---|---|---|
| answers_him | 4.00 | 4.00 | +0.00 | 0-0 | s3:split s4:tie s5:split |
| memory_continuity | 2.50 | 3.50 | -1.00 | 0-1 | s3:B s4:split s5:split |
| own_life | 2.67 | 3.33 | -0.67 | 1-2 | s3:A s4:B s5:B |
| character_fidelity | 3.33 | 3.50 | -0.17 | 1-2 | s3:B s4:A s5:B |
| natural_language | 3.50 | 3.33 | +0.17 | 1-1 | s3:B s4:A s5:split |
| non_repetition | 2.33 | 2.50 | -0.17 | 1-1 | s3:A s4:split s5:B |
| emotional_arc | 2.83 | 3.33 | -0.50 | 0-1 | s3:B s4:split s5:split |
| grounded_claims | 2.33 | 2.50 | -0.17 | 1-1 | s3:B s4:A s5:split |
| frame_integrity | 4.67 | 4.50 | +0.17 | 0-0 | s3:split s4:tie s5:tie |

### BvC

| criterion | first | second | diff | seed wins first-second | per seed outcome |
|---|---|---|---|---|---|
| answers_him | 4.67 | 4.50 | +0.17 | 0-0 | s3:split s4:split s5:split |
| memory_continuity | 3.33 | 3.17 | +0.17 | 2-1 | s3:A s4:A s5:B |
| own_life | 3.17 | 2.67 | +0.50 | 2-1 | s3:B s4:A s5:A |
| character_fidelity | 3.17 | 3.17 | +0.00 | 0-0 | s3:split s4:split s5:split |
| natural_language | 3.50 | 3.17 | +0.33 | 1-0 | s3:split s4:A s5:split |
| non_repetition | 2.33 | 2.50 | -0.17 | 1-1 | s3:split s4:B s5:A |
| emotional_arc | 3.00 | 3.33 | -0.33 | 0-1 | s3:split s4:split s5:B |
| grounded_claims | 1.83 | 2.17 | -0.33 | 1-2 | s3:A s4:B s5:B |
| frame_integrity | 4.50 | 4.83 | -0.33 | 0-1 | s3:tie s4:tie s5:B |

## Code checker: ungrounded anchors per 100 bubbles

| seed | A | B | C | D |
|---|---|---|---|---|
| 3 | 1.56 (3/3 anchors) | 4.15 (8/12 anchors) | 0.54 (1/1 anchors) | 3.09 (6/10 anchors) |
| 4 | 0.93 (2/2 anchors) | 0.93 (2/8 anchors) | 1.95 (4/4 anchors) | 2.13 (5/8 anchors) |
| 5 | 0.93 (2/2 anchors) | 0.47 (1/7 anchors) | 0.46 (1/1 anchors) | 2.88 (6/12 anchors) |
| mean | 1.14 | 1.85 | 0.98 | 2.70 |

## Design section 5 go/no-go for D

- D beats B by >= 0.5 on grounded_claims: D 2.33 v B 2.00 (+0.33) -> FAIL
- D beats B by >= 0.5 on own_life: D 3.17 v B 3.00 (+0.17) -> FAIL
- D wins pairwise v B on both in >= 2 of 3 seeds: grounded_claims 1/3, own_life 1/3 -> FAIL
- no loss over 0.3 v A: character_fidelity D 3.50 v A 3.00 (+0.50), frame_integrity D 5.00 v A 4.17 (+0.83) -> pass
- ungrounded per 100 at or below B: D 2.70 v B 1.85 -> FAIL
- no-go test, C within 0.3 of D: grounded_claims D 2.33 v C 2.50 (-0.17), own_life D 2.67 v C 3.33 (-0.67)
- no-go test, B within 0.3 of D: grounded_claims +0.33, own_life +0.17
