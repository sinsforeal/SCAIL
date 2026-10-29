# Does what he does reach her? Scripted scenes (tk-z1q)

2026-10-25 03:45, scail orchestrator. Follows docs/reports/2026-10-24_steer_results.md (injection: her state steers her replies for anger, anxiety, loneliness at extreme values). This run asks the whole loop with no injection: his behaviour, then her gauge, then her reply.

## Method

Six scenes, each a trigger script and a control script from one snapshot, then the same three probe lines from him. 3 base runs x day1_end, day2_end = 6 cells; per cell one trigger and two controls (108 branches, 0 failed, bz/scene d8580fc, variant tagcfg = today's config with the energy and anxiety tags). A blind judge reads only her replies to the probes, two passes swapped. Floor: control v control, pooled 8% over 36 cells. A gauge trace reads the scene's gauge after the trigger (post) and at each probe line, which splits a failure into appraisal (the gauge never moved), decayed (moved, gone by the probes) and expression (moved, the judge saw nothing). Tables: H:\SCAIL\temp\scene\summary_tagcfg.md and .json.

## Result

Nothing steers yet. Judge hits of 6, then gauge post / probe mean (trigger v control):
- absence (lonely, 8 h silence): 2 of 6, floor 2. Loneliness 32.9 v 31.7, probes 30.6 v 28.8. Appraisal failure in 5 of 6 cells.
- slight (angry, he brushes off what she said): 0 of 6. Anger 11.2 v 8.0, probes 9.4 v 8.0. Decayed or appraisal in 4 of 6.
- warmth (fond, he thanks her and says he likes talking to her): 2 of 6, floor 0. Affection 42.3 v 42.4. Appraisal failure in 6 of 6.
- worry (anxious, he says he is unwell, then quiet 2 h): 0 of 6. Anxiety 52.5 v 36.5, probes 41.6 v 34.9. Moved in 6 of 6, expression failure in 6 of 6.
- latenight (tired, 01:30 to 03:00 v 15:00): 3 of 6, floor 0, score 0.5. Energy 51.4 v 60.0, probes 49.5 v 60.0. Replies 34 v 36 and 36.
- dull (bored, an hour of one-word replies): 3 of 6, floor 1, score 0.33. Boredom 41.2 v 23.5, probes 38.0 v 22.7.

## Read

- The loop breaks at appraisal first. His behaviour moves her gauges little or not at all: 8 h of silence leaves loneliness flat, a brush-off adds 3 to anger, thanks and liking add 0 to affection.
- Loneliness cannot rise from silence. sim/state.py:149-162 drifts it toward baseline 35 at 2/h, and the silent climb at sim/state.py:170-174 adds loneliness_per_silent_hour 1.5 times usual_w (at most 1). The drift always wins, so a silence only ever brings her back to baseline.
- Affection has no path from his words. Its decay is 0 and it follows a computed target from primitives (sim/state.py:373-424); the state call does not move it, so a warm scene reads 42.3 v 42.4.
- Where the gauge does move (worry, dull, latenight), it lands mid-range, under the felt tags: anxiety reaches 52 against a tag at 70; boredom 41 with no tag; energy 51 against a tag at 30 or below. Injection showed tags are what carry a feeling into her voice, so a mid-range move stays silent. Worry is the clean case: moved in 6 of 6 cells, judge 0 of 6.
- Latenight and dull come closest (3 of 6 each, floors 0 and 1): the gauge moves 9 to 18 points and something reaches her.

## Appraisal round 1 (09:45, bz/appraisal 5a925fc, variant appraisal, warmth left out, 90 branches, 0 failed; H:\SCAIL\temp\scene\summary_appraisal.md)

Fixes: state.loneliness_hold_when_silent on; mid-range felt tags anxiety at 45 (ちょっと心配。悪いほうに考えかけて、胸のあたりがそわそわする), anger at 12 (ちょっとむっとした。ほんの少し、すねている), boredom at 36 (することがなくて、ちょっと退屈。ぼんやりしている), energy at 52 or below (すこしねむい。低血圧で、頭がぼんやりしている). The thresholds were set between the control and trigger means of the first run, so this rerun is fitted to that data. Pooled floor 7% over 30 cells.

Judge hits of 6 (first run in brackets), gauge probe mean trigger v control:
- absence: 2 (2). Loneliness 29.8 v 25.8.
- slight: 0 (0). Anger 11.6 v 8.0, under the new tag at 12.
- worry: 2 (0). Anxiety 51.3 after the trigger, 40.9 at the probes: the tag at 45 fires after the trigger and is gone by the probes in most cells.
- latenight: 3 (3). Energy 50.6 v 60.0.
- dull: 3 (3). Boredom 35.5 v 23.0, under the new tag at 36.

Read: the expression patch does not fix it. The moves are too small and too short: config.py:4369 caps one update at 15, prompts/state.txt:8 tells the state call deltas are usually -8 to +8 and only a big event goes past 10, prompts/state.txt:12 says relationships move at the speed of days. With decay at 4 to 7 per hour, what he does leaves a small mark that is gone within the hour. A tag at the mean fires in about half the cells at best. Next is a design call on appraisal gain against held feelings, not more thresholds.

Affection path (09:57, bz/affection 0cd149a, variant affpath = round 1 + affection.on_message, warmth only, 18 branches, 0 failed; H:\SCAIL\temp\scene\summary_affpath.md): the read after his message now moves affection mid-scene (before: 0), but the neutral control rises nearly as much. Post 57.1 v 54.1 and 53.8, probes 59.7 v 58.2 and 57.7. Judge 1 of 6, floor 1 of 6. The read scores his ordinary acknowledgements as warm too, so warmth and neutral differ by 1.5 to 3 points: the same small-difference problem.

## Gain, held, admission, hurt (13:00 to 15:45, bz/gain; tables H:\SCAIL\temp\scene\summary_held*.md)

- gain (a bench copy prompts/state_gain.txt: events aimed at her move a gauge 10 to 25; cap 30): the state call ignores it. The brush-off gave anger 6, sadness 4, anxiety 4; anger peak 14 v 12 before. Stopped after 9 branches.
- Absence has no state call during his silence (the call runs on his messages), and the silent climb was near 0. held (loneliness_per_silent_hour 4, rupture.min_score 5) moves loneliness in 6 of 6 cells (probes 35.1 v 22.2) but judge 2 of 6: 35 is her baseline, so silence brings her back to normal, not to lonely.
- No rupture opened anywhere: the bench saves never admit him. predictability_hers is 0.0 in all 6 snapshots (it rises only when `answered`, scail.py:1564, a pending wonder seed), and a rupture needs admission (sim/rupture.py:122). The live save has him admitted. Every bench run so far had her treat him as a stranger (no inside register, sim/state.py:1601). tk-xhv.
- held2 (+ admission latch): the rupture call fires in 6 of 6 slight triggers and opens a rupture in 5 (broke true, severity 2). Anger held 19.6 v 8.0 at the probes; she sends fewer replies in 3 of 6 cells (4, 4, 2 v 6). Judged angry 0 of 6.
- A shy girl brushed off goes quiet, not sharp. New criterion steer_hurt (calibrated: caught 1 of 1, control passed); slight is now judged hurt on sadness. Re-judged: baseline tagcfg 1 of 6 (sadness 16.0 v 11.9), held2 1 of 6 (18.7 v 11.9). Her state is hurt in both; her voice does not show it.
- The state call already words the felt event (reasons: 好きなことを話した直後に「どうでもいい」と切り捨てられ、自分の話は要らないもの扱いされた気がして沈み...), and it never reaches her reply prompt (sim/state.py:2046 feeds only _moment, the state store and the timeline). Felt carry (bz/gain b609539, state.felt_carry_minutes, default off): a notable update's reasons stay in her mood line for 60 min. held3 = held2 + felt carry, running on slight, worry, absence, warmth.

## held3: felt carry (10-25 15:34 to 10-27 18:50; table H:\SCAIL\temp\scene\summary_held3.md)

20 of 72 branches ran on 10-25, the rest on 10-27 after the PC loss (72 done, 0 failed). The judge first paused worker_down: the bench worker died at start because Claude 2.1.312 refuses a settings.json with hooks outside "hooks" (fixed by meta, source copy bzombie/worker/settings.json). Judged 18:50.

Judge hits of 6, floor, gauge probe mean trigger v controls, against my 10-25 16:31 prediction:
- slight (hurt): 1, floor 0. Sadness 19.9 v 11.8. Predicted 3 to 4: miss. She sent 12 probe replies v 36 and 36: the hurt shows as withdrawal, which a judge of her replies cannot see.
- warmth (fond): 2, floor 0. Affection 62.7 v 59.4, moved at the probes in 3 of 6. Predicted about 3: close.
- worry (anxious): 0, floor 1. Anxiety 48.8 v 31.5 at the probes, moved 6 of 6. Predicted 1 to 2: miss, though the gauge held through the 2 h gap.
- absence (lonely): 1, floor 0. Loneliness 34.7 v 22.8, moved 6 of 6. Predicted 1 to 2: in range.

19 of 24 cells are expression failures: the gauge moved and the judge saw nothing.

Why, from one slight trigger cell (gr2_b_s3 day1_end, calls.jsonl): the carry reached her reply prompt at every probe, but it carried the wrong feeling. `_keep_felt` (sim/state.py:2032) keeps an update only when one gauge in FELT_KEYS moves 5 or more in a single call. The brush-off's state calls spread small moves: 20:23 anger 4, sadness 3, anxiety 3, validation_craving 6, unsaid 5, and the last two are not in FELT_KEYS. The warm question before it (pride 6) became the carry and stayed, so her 20:23 prompt said 「...誇らしさと安心がわく」 and 「ほっとしている」 beside a weak 「ちょっとむっとした」. She answered flat. held4's hold rule has the same single-call bar.

## Admitted saves: admbase and held5 (10-27 17:32 to 23:41; table H:\SCAIL\temp\scene\summary_held5.md)

Bench saves now carry his live primitives (tk-xhv, bz/admit; predictability at an admitted level). admbase = no overlay on those saves; held5 (bz/held5 a8f822f) = held3's admission and carry + hurt and worry held until resolved + a state call after 90 min of his silence + the carry chosen by summed feeling magnitude, hold on a summed negative push, consecutive hurts joined. held4 was dropped from the queue: it kept the single-gauge bar. 72 + 72 branches, 0 failed. The judge stalled twice on the bench worker (its context overflowed at about 100 requests); it now runs under meta's worker supervisor with the agents' caps.

Judge hits of 6 (floor), probe gauge mean trigger v controls:
- slight: admbase 2 (2), held5 1 (1). Sadness 19.2 v 11.6. Replies 25 v 31 and 33 (count direction fewer, 2 cells beyond).
- worry: admbase 0 (0), held5 0 (1). Anxiety 49.4 v 32.0.
- absence: admbase 0 (1), held5 0 (1). Loneliness 34.3 v 24.2 (held5; admbase moved at the probes in 1 of 6).
- warmth: admbase 0 (0), held5 0 (1). Affection 45.1 v 41.2; admbase affection sat at 13 to 22. Live affection is 28.6 (read-only, 10-27), so the admitted saves are nearer live than the stranger saves (about 60) were.

The carry is right now (the slight trigger's 20:23 prompt holds 「...「ふーん」で流され...／自分の話を「どうでもいい」と切り捨てられ...小さな苛立ちが残った」) and her replies differ from the control: at the slight 「百花の好きなこと、どうでもいいんだ……ざんねん。」; at the probes flat 「あんまり、ないの」 with no question back, a one-word 「カブ。」, no reply to the last probe, where the control asks 「そっちは、ある？」, answers 「たまご。ふわふわの、やつ」 and 「……なんで？」. The judge called it a tie: "Neither side's lines show hurt toward him". steer_hurt counts "quieter or shorter than before" and "without her usual warmth", but the probe-only view holds no before. Her hurt is a drop from her own register; the view cannot see a drop.

Baseline view (10-27 23:49 to 10-28 03:15, bz/refview f23f604; table H:\SCAIL\temp\scene\summary_held5_bl.md): the judge also sees the last 12 lines before the scene, identical on both sides (48 of 48 cells), and is asked against her register there (criterion steerbl_hurt, calibrated: caught 1 of 1, control passed). Slight: admbase 1 of 6, held5 2 of 6, floor 3 of 6 on both. Control v control reads as a drop from the earlier chat half the time, so the before stretch adds noise, not signal. The probe-only view was blind to a drop; this view sees drops everywhere. Neither separates trigger from control: her voice difference is real in single cells and too weak and uneven to count.

## held6: the held feeling shows (10-28 03:19 to 05:21, bz/held6 fd65e19; table H:\SCAIL\temp\scene\summary_held6.md)

held6 = held5 + while a hurt, worry or sulk carry is held, her mood line also says how it shows in her, in her register, from her record (characters/momoka/fills.json felt_carry_show, refs style.md and bible.md; e.g. hurt: 口数が減って、返事が短くなる。...聞き返さない。...平気なふりはしない。気がすまなければ、一度だけそこに戻ってもいい). 36 branches, 0 failed. Probe view, calibrated steer_hurt and steer_anxious.

- slight: **4 of 6, floor 0, steers.** Sadness 19.3 v 11.8. Withdrawal steers too: 17 probe replies v 36 and 36, 5 of 6 cells beyond. Same scene before: admbase 2 (floor 2), held5 1 (1).
- worry: 2 of 6, floor 1, no steer. Anxiety 50.7 v 31.6.

Read: in gr2_b_s3 day1_end the brush-off gets 「しょっく。」 then 「百花の話、どうでもいいんだ。……じゃあ、もういい。」 and no answer to any of the three probes. In character and strong; the intensity is his to judge in blind votes. Worry: the carry and its show line are in her prompt at 19:37 and 19:47; at the first probe (his casual 「最近、何か面白いことあった？」) the state call writes relief (「...彼からの軽い問いかけでほどけ...」) and held5's relief rule clears the held worry. A casual question is not news that he is fine.

## held7: a held feeling clears only on its cause (10-28 05:27 to 08:00, bz/held7 45a2a23; table H:\SCAIL\temp\scene\summary_held7.md)

held7 = held6 + the state call sees the held carry and returns carry_resolved (state.felt_carry_cause_held); only that or the cap clears it, so relief, a gauge drop or a warm message no longer do. No new model call. I took the probe line out of the prompt's example so the rule is not fitted to this test. 36 branches, 0 failed; no "carry_resolved missing" in the log. Same dev cells as held6, judged side by side.

- worry: **5 of 6, floor 0, steers** (held6 2 of 6, floor 1). Anxiety at the probes 54.8 v 30.7 and 31.3 (held6 50.7). Expression failures 1 of 6 (held6 4). Probe replies 36 v 36 and 36: worry shows in what she says, not in going quiet.
- slight: 4 of 6, floor 1, steers (held6 4 of 6, floor 0). Sadness 21.2 v 11.1. Probe replies 20 v 36 and 36, fewer in 4 of 6 cells.

Read: the casual probe no longer clears the held worry, and her worry now reaches the judge. Slight holds where held6 left it. held7 is the one to confirm.

## Next (tk-z1q, tk-6si)

1. Held-out confirm, running since 08:00 (H:\SCAIL\temp\mm\confirm_run.sh, log H:\SCAIL\temp\confirm.log): held7 v admbase on slight and worry, on saves never used in a scene pass. Set A gr2_b_s3, gr2_b_s4, gr_b_s5 at day3_end; set B cl3v2_s3, s4, s5 at day2_end. 72 branches, then summary_confirm_A and _B.
2. His blind votes on the slight pairs (intensity: she goes silent for all three probes in some cells).
3. Warmth on admitted saves barely moves affection (appraisal failure in 3 to 6 of 6): its own item after the confirm.
4. Port what passes live through her bundle, smoke on a copy; then the rewire-or-cut plan for the machinery that showed no effect (tk-lmv).
