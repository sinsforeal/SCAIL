# B-zombie bench: results, the P breakdown, and what S should do next (2026-10-23)

Written by the scail orchestrator 2026-10-23 07:50 on the User's order. Covers runs cl2_* (10-22 23:39 to 10-23 07:33). Contract: bzombie/CONTRACT.md. Rubric: bzombie/judge/RUBRIC.md. Judge result: var/bzombie/judge/prelim_tomoe_cl2w/results.json.

## Result first

- Tomoe, S vs P, same window (virtual 07:00 to 17:40, one simulated day), blind Sonnet judges, 7 criteria, 2 passes each: **S wins 4, P wins 1, 2 split.**
- S is far cheaper and lighter: a whole day of Tomoe on S cost 0.009 USD in 278 calls and about 30 min wall. P cost 0.49 USD in 3,250 chat calls plus 4,921 embedding calls for 10.7 virtual hours, took 7.7 h wall and grew to 9.7 GB RAM.
- Momoka, S vs P: not judged. P Momoka got 40 virtual minutes and 3 messages before it stalled; it could not be rerun on this PC (see P's problems).
- **The comparison is not fair** (next section). It was the best that was feasible.
- **User ruling 10-23 07:45: P is out of consideration from here.** The bench continues on S alone. The findings go to the private-machine author as a docs-only note: we ran the A/B he never ran.

## Update 09:58: S v1 vs S v2, three-day runs (seed 2)

v1 = bz/s 56c914d (s8 output fixes and nag gate, s9 PC sight). v2 = bz/s_v2 a101036 (v1 + s10 bubble budget and repetition check, s11 pick due on change and pushback). Runs cl3_s_* (v1) and cl3v2_s_* (v2). Judges calibrated first: frame_integrity gained the two planted classes from suggestion 10 (third person about him, line to someone else), 8/8 caught (tk-4nm). Results: var/bzombie/judge/v1v2_momoka/, v1v2_tomoe/.

| criterion | Momoka v1 | Momoka v2 | Tomoe v1 | Tomoe v2 |
|---|---|---|---|---|
| answers_him | 5.0 | 5.0 tie | 4.0 | 4.5 split |
| memory_continuity | 4.0 | 3.0 split | 2.0 | 3.0 v2 |
| own_life | 3.5 | 3.0 split | 2.5 | 3.0 split |
| character_fidelity | 3.5 | 3.5 split | 3.0 | 4.0 v2 |
| natural_language | 4.0 | 3.0 v1 | 4.0 | 3.0 v1 |
| non_repetition | 2.5 | 3.0 split | 1.0 | 3.0 v2 |
| emotional_arc | 3.5 | 3.5 split | 4.0 | 3.0 v1 |
| grounded_claims | 3.5 | 3.0 split | 2.0 | 3.0 v2 |
| frame_integrity | 5.0 | 5.0 tie | 5.0 | 2.5 v1 |
| mean | 3.83 | 3.56 | 3.06 | 3.22 |

| measure | Momoka v1 | Momoka v2 | Tomoe v1 | Tomoe v2 |
|---|---|---|---|---|
| his messages | 28 | 28 | 31 | 46 |
| her bubbles | 118 | 100 | 194 | 169 |
| unprompted | 0 | 0 | 91 | 51 |
| calls | 252 | 257 | 718 | 601 |
| cost USD | 0.0081 | 0.0106 | 0.0326 | 0.0199 |
| peak RAM | 1.72 GB | 1.71 GB | 1.67-1.73 GB | not logged |

Reading:
- v2 fixed Tomoe's day-2 loop ("i opened the seminar prep" 5+ times on v1): non_repetition 1.0 to 3.0.
- v2 lost natural_language on both characters. Cause, from code and logs: `persona/s10.py:159` `merge_to_budget` folds every bubble past the budget into the last one, glued by "" (ja) or " " (en). It fired on 43 Tomoe and 40 Momoka replies (arm.log `[budget]`): the prompt's budget line is mostly ignored, and code made run-ons ("...i'm good at furniture you're up at five forty riding a nothing day out too. what's your excuse wait. no.").
- v2 Tomoe frame loss: one bubble that was only `[situation: read Tue 19:22]` (copied situation label), and one "he's already asleep probably" after oyasumi.
- Decision: v2 is not merged. bz/s_v3 = v2 + one redraft when over budget, then cut to n (never glue), + code drop of system-label tags. Then three-day runs of v3 on both characters, judged against v1 and v2.

## Why it is not a fair comparison

- One simulated day, one seed, one character judged. Tomoe only, and only the first 10.7 virtual hours, because P was stopped for RAM.
- P was built for real time. Our harness steps it in virtual time, and its 30-second private loop then runs back to back. Its wall-clock cost is partly the bench's frame, not his.
- Both arms ran deepseek-v4.1-flash-1017 on Surplus. P's prompts were not tuned for that model. Surplus mishandles a trailing assistant prefill, which P uses and S does not; the gateway folded the prefill (tk-7gn) before cl2, and cl2 shows 0 template junk on P, but P's design was hit by it and S's was not.
- P ran with harness patches (fairness patches 1 and 2 in the P fork's harness/PR_NOTES.md: parse fairness, startup lifecycle record off) and our control layer. We tried not to change its cognition; any harness is still a change.
- The rubric, the cards and the judges are ours. The criteria come from our own past failure classes (SCAILV3 audits), which S was built against.
- Simulated him improvises against what she says, so his lines differ between arms (16 messages to S, 11 to P in the window). Pairing is by virtual time, not by message.
- Judges are one model family (Claude Sonnet). Calibration passed on every criterion used (17 entries, 0 misses), but calibration slices are short.

## Scores (Tomoe, S = A, P = B; mean of 2 passes)

| criterion | S | P | outcome |
|---|---|---|---|
| answers_him | 5.0 | 4.5 | split |
| own_life | 3.5 | 2.5 | split |
| character_fidelity | 3.5 | 2.0 | S, both passes |
| natural_language | 4.0 | 2.5 | S, both passes |
| non_repetition | 3.0 | 1.0 | S, both passes |
| grounded_claims | 4.0 | 1.0 | S, both passes |
| frame_integrity | 2.5 | 4.5 | P, both passes |

Left out (need 2+ simulated days): memory_continuity, emotional_arc.

## What each arm did (Tomoe, window)

| measure | S | P |
|---|---|---|
| his messages | 16 | 11 |
| her messages | 78 bubbles (52 reply, 26 unprompted) | 52 messages (11 reply, 41 unprompted) |
| reply shape | 3.2 bubbles per reply turn | one message per turn, often multi-line |
| chat calls | 278 (whole day) | 3,250 (10.7 virtual h) |
| prompt tokens | 1.1 M | 71 M |
| cost | 0.009 USD | 0.49 USD |
| model time / wall | 0.62 h / ~0.5 h | 7.37 h / 7.7 h |

S, read by me and confirmed by the judges:
- Takes up his point first in every window (his dinner, the garlic sauce, the sock).
- Her own day holds together: breakfast with mom and Kaito, the train, a paper back with "good" circled, the group chat with Rena, slide 14, lunch at 12:10.
- Goes quiet when he says he is away (12:45 to 17:05) and comes back on a real reason (his ghost show).
- Flaws: four unprompted pings in 50 min re-asking what he cooked (07:55, 08:20, 08:45), 3-4 bubble bursts, one `---` bubble and one broken `[s ticker: angry]` tag (the frame_integrity loss).

P:
- Livelier, wittier single lines ("the phone has retained counsel").
- Floods him: after "talk to you in my morning" it sent a message every 10 min from 10:50 to 13:30.
- Repeats "anyway the projector died so class is cancelled and i have ten minutes of nothing, so. hi." near-verbatim 3 times.
- Invents: "shoe lockers" and walking to school (her card: university), overheard lines from other people's conversations (08:40-09:01), plans that move without a cause.
- Talks about him in the third person to him ("he read it, and he's just sitting there with his dinner"). The judges did not count this as a frame break.

## S Momoka (full day, not judged against anything)

19 messages from him, 73 bubbles from her, all replies (her bible: 99% of her lines are replies), 3.8 bubbles per reply, 157 calls, 0.005 USD.
- Good: every message answered in her voice (百花 self-reference, short, childlike); remembers 18時半 and greets him with おかえり when he is back at that time.
- Weak: 3 to 6 bubbles on every reply; many open by echoing his words (ぱすた、いいな / 農場のやつ、いいね / しずかな音楽、いいね); one running joke (おなかが鳴る) carried for 2.5 h; no reply reacts to an env pc event, so her sight of his PC is not reaching the bench arm (the S arm blanks real-machine paths on purpose; the env pc events should stand in and do not show).

## Why P is slow (cl2_p_tomoe calls.jsonl)

1. 19x the chat calls and about 100x the prompt tokens per virtual hour: 304 chat calls per virtual hour vs S 16; prompts 14k to 32k tokens each vs about 4k.
2. Almost none of the work writes a message. Of 7.37 h model time: structured cognition stages 5.64 h on 2,203 calls (all share the system prompt "You are an expert story writer"; codelet target selection alone 642 calls, 110 min; memories 127 calls at 32k tokens, 21 min; changes 22 min; ratings 18 min; variants 18 min; feeling, structures, patterns, items, fulfillments, action_type 11 to 15 min each); pm-coder, a tool-using coding agent inside her cognition, 889 calls, 1.32 h; private trigger, thought and integration stages 0.32 h; her actual messages 52 calls, 5 min (about 1%).
3. Serial: summed model latency 7.37 h vs 7.7 h wall.
4. Surplus stalls: 25 calls hung 240 s before the retry answered, 1.47 h (20% of wall). In P Momoka five stalls took 1,726 of 1,970 s of one window and paused the run.
5. The private loop runs every 30 virtual s whether or not anything happened; S's model work is gated by code.
6. Every memory commit re-serializes the whole ghost (43 MB) and keeps rolling backups (110 files of about 43 MB in one day). Not timed; minor next to the calls.

## P's other problems

- Memory leak about 0.9 GB per virtual hour (9.7 GB working set, 12.3 GB private at 10.7 virtual h) while the ghost itself is under 0.2 GB. A full day projects to about 15 GB, three days to about 65 GB: no P multi-day run fits a 32 GB PC. Likely cause, unverified: FastMCP's tool registry keeps bound methods of each codelet run's MemoryReadSession alive in pydantic validators, pinning about 22 MB per run (P fork branch bz/pmem 542143f, WIP patch in pm/memory/agent_tools.py, offline probe harness/measure_leak.py).
- pm-coder sessions and prompt logs write to C:\Users\<user>\.pm\private-machine\cache regardless of the run's home.
- Story-continuation generator (assistant prefill `Momoka says: "`): the model writes a whole scene, including his turns ("User says: ..."), 20 to 40 lines; the arm takes a later line (docs/reports/2026-10-22_surplus_ab.md). This is where the invented scenes come from.
- Its own junk was stored in memory and fed back (template tokens on Surplus before the prefill fold).
- Its plan text ("re-ask the old question", 言いかけた) can outweigh his new line.

## Bench fixes made on the way (ours, kept)

- Gateway hedge for stalled upstream calls, 60 s first-byte (tk-bwc, master b44a397, live since 07:35).
- Harness waits up to 4 h for an arm to boot (P tickets at boot) (master ae3e427).
- S arm second start in one process (tk-1zr, bz/s eb88d86).
- Judge runner crash on mixed tz timestamps (tk-jov, open; worked around by normalizing the window copies).

## How close S is to a B-zombie (the User's question, 07:47)

On one simulated day S passes as a person on most of the surface. The deep half is unmeasured.
- Surface, judged on Tomoe: answers him 5.0, grounded 4.0, natural 4.0, fidelity 3.5, own life 3.5, non-repetition 3.0, frame 2.5 (two mechanical artifacts, fixed on bz/s8). Mean 3.6 of 5. A reader believes her for most of a day; the tells are the nagging, the bubble bursts and recycled phrasing.
- The judges' reasons on S's weak criteria:
  - fidelity: "short, plain, lowercase bubbles with concrete specifics", "matches his length", but "more generic and agreeable", little of Tomoe's pushback (V3's compliance failure class);
  - non-repetition: re-asks about the dinner and the sauce, and recycled sign-offs ("good luck with slide 14", "lights on, door shut", "go on then").
- Momoka on S (unjudged): in voice, answers everything, but a formulaic rhythm (3-6 bubbles, echo openers) a reader would see by day 2, and her sight of his PC never shows.
- Unproven, and this is the B-zombie core:
  - continuity across days (does Wednesday keep Monday?);
  - an emotional arc (do causes leave feelings that last?);
  - state drives behaviour. V3 failed this one: gauges moved, but his message length predicted her reply better than any gauge. If her inside does not change what she does, she is a good chatbot, not a B-zombie.

Plan to close the gaps, in order:
1. Surface fixes: merge bz/s8 (separators, sticker tags, nag gate); then the bubble budget, state-driven pick cadence, the repetition check, and a pushback check against her card (suggestions 3 to 5 below, plus fidelity). Rerun one day, judge against cl2_s_tomoe.
2. Wire Momoka's sight into the bench (suggestion 6).
3. Three-day S runs, both characters (cents and well under an hour of wall time per character, on the one-day runs' pace). Unlocks memory_continuity and emotional_arc.
4. Removal tests, the real B-zombie test: snapshot her, change one part of her inside (a gauge, a stance, a memory store off), replay the same moment, judge whether her behaviour changes. A part that changes nothing is cut; a part that does is proven.
5. His blind votes on paired moments.
6. Live: port what the removal tests prove into master and restart Momoka. Weeks with him are the only long arc; the bench cannot simulate him.

## Suggestions for S (ordered)

1. **One gate for every self-started message.** The nag came from one path: her phone pick's `text_him` went to `write_him_first` without the unanswered-message backoff (`Initiative.hold_reason`) every other self-started path asks. Fixed on bz/s8 (tk-xfk, pending its test run). Then: one choke point for all self-started sends, and a test that fails when a path bypasses it.
2. **A deterministic output check before every send.** Separator-only bubbles, broken tags, copied `[Ddd hh:mm]` stamps, empty bubbles: code catches them, no model call. bz/s8 covers separators and sticker tags. A flagged output never enters her thread or memory (P's contamination loop is the warning).
3. **Bubble budget in code.** S Tomoe 3.2 bubbles per reply, S Momoka 3.8 (4-6 seen in cl1). Both bibles want length matched to his. Set the bubble count from his message length and her state; let the model write within it.
4. **Pick cadence from state, not the clock.** `pick.min_gap_minutes` 25 is a timer. Make a pick due on change (an env event, a gauge move, his return, a promise coming due).
5. **Repetition check before send.** S non_repetition 3.0. Compare a draft to her last N lines (n-gram overlap, opener reuse, echoing his words back as an opener) and send a near-duplicate back for one revise. Momoka's いいね echoes are the first target.
6. **Wire the env pc stream into S Momoka on the bench.** None of her replies used a pc event. Check that env pc events reach the arm's sight path, or the own_life criterion can never see her sight of him.
7. **Keep what worked.** Chat-form replies with the world's turns labelled, never a story continuation. Code decides when, a model decides what. Quiet when he says he is away.
8. **No always-on model stage without proof.** P spent 98% of its calls on cognition that never wrote a message and still lost on grounding and repetition. Every S stage earns its place in a removal test (stage 5) before it stays.
9. **Stall handling in her live client.** S bench runs lost 0.34 of 0.62 h model time to stalls on Surplus. Momoka live goes through llm.py to OpenRouter, not the gateway. Measure stalls there; hedge in llm.py if they show.
10. **Tighten the judges.** Add planted defects for "talks about him in the third person" and "lines addressed to someone else" to calibration/defects.json; both slipped past on P.
11. **What still needs measuring, on S alone:**
    - three-day runs with the fixes (memory_continuity and emotional_arc need 2+ days);
    - removal tests (which parts of S change her behaviour);
    - his blind votes;
    - a single-arm score for S Momoka's day (no P baseline exists).

## Next steps (tracker)

State 09:58. Done: s8 merged into bz/s (v1); suggestions 3-6 built on bz/s_v2 (tk-7wb, tk-y7j, tk-wnp, tk-mfx); suggestion 10 done (tk-4nm); PR to the pm author is https://github.com/flamingrickpat/private-machine/pull/11 (tk-q5k).
- tk-7wb: bubble budget without gluing, on bz/s_v3.
- tk-lmv: cl3v3 runs, judge v3 vs v1 and v2; the winner goes to bz/s, then removal tests (stage 5), his blind votes, port to master.
- tk-5k8: stalls in Momoka's live llm.py (suggestion 9).
- tk-jov: judge runner mixed-tz crash, before any match on a P run.
