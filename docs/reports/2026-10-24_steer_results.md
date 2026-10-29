# Does her inner state steer her? Injection tests (tk-6si)

2026-10-24 14:00, scail orchestrator. Follows docs/reports/2026-10-24_removal_results.md. The User 06:36: "how can we make the internal state meaningful".

## Method

At a snapshot (3 base runs x day1_end, day2_end = 6 cells) one gauge is pinned at an extreme for the whole replay (hold.<gauge>, re-applied through ticks; decay would otherwise pull it back toward baseline within hours). The same 6 of his messages are replayed. A blind judge (calibrated 12/12) reads her lines only and says which side reads more lonely / angry / tired / fond / anxious / bored, two passes swapped; a hit is both passes picking the pinned side. Floor: the same judge on two noop replays, pooled over all 36 cells. Two variants: plain (her state reaches her as the printed mood line, いまの気分) and order (bz.order: one call turns her state into an in-character instruction placed last; the mood line is dropped). Code bz/s_ground 3db87fb + affection fix. Tables: H:\SCAIL\temp\inject_summary.md and .json.

## Result

Plain, pooled floor 31%:
- loneliness 90: 5 of 6 (chance about 1%), steers
- anger 85: 5 of 6 (about 1%), steers
- affection 90: 4 of 6 (about 8%), steers
- energy 10 (tired): 2 of 6, no
- anxiety 90: 3 of 6, no
- boredom 90: 1 of 6, no

Order, pooled floor 22%:
- loneliness 3 of 6, anger 3 of 6 (about 12% each), no
- affection 4 of 6, boredom 4 of 6 (about 2% each), steer
- energy 2 of 6, anxiety 2 of 6, no

Order plus the mood line kept (bz.keep_mood_tags), pooled floor 31%:
- nothing steers: loneliness 2, anger 3, energy 1, affection 3, anxiety 2, boredom 3 of 6

Hits in total: plain 20 of 36, order 18 of 36, order plus mood line 14 of 36.

### Fix runs (18:20, bz/s_ground c82bbac, 60 branches, 0 failed; tables H:\SCAIL\temp\steer_fix.md and .json)

Tags variant: overlay bzombie/arms/s/overlays/tags.json gives energy, anxiety, loneliness and boredom felt tags written from her bible (the kind anger and affection already carry), e.g. anxiety 70: 心配で落ち着かない。悪いほうに考えてしまって... Pooled floor 21% over 42 cells:
- anxiety 90: 6 of 6 (chance about 0.01%), steers, gap 2.0. Plain was 3 of 6.
- energy 95 (rested, expect less tired): 4 of 6 (about 2%), steers
- energy 10 (tired): 3 of 6, no by wording; by count yes, 100 replies v 136 and 134 noop, fewer in 6 of 6 cells
- boredom 90: 3 of 6 (about 11%), no. Plain was 1 of 6.
- anxious_full (anxiety 90, stress 70, relief 0 pinned together): 3 of 6, no
- loneliness 90: 2 of 6, no. Plain was 5 of 6: the tag made it worse.
- loneliness 5 (expect less lonely): 2 of 6, no

anxious_full plain (mood line only): 0 of 6, gap -0.7, so the multi-pin without tags reads less anxious than noop. It does cut her output: 105 replies v 136 and 139 (tags 108 v 136 and 134).

Plain rerun inside the same summary matches the 14:00 numbers (loneliness 5, energy 2, anxiety 3, boredom 1 of 6).

### Decay runs (21:14, bz/s_ground 59ea82f + tagcfg, 72 branches, 0 failed; tables H:\SCAIL\temp\decay.md and .json)

One-shot set.<gauge> at branch start, then normal decay over windows of 13 to 20 virtual hours (gr2_b_s4 day2_end 1.4 h). Fresh noops on today's config (tagcfg). Pooled floor 25% in both sets.

Live rates (anger 7/h, anxiety 4, loneliness 2, affection inertia 6), 7 of 24, nothing steers:
- loneliness 90: 0 of 6; anger 85: 2; affection 90: 2; anxiety 90: 3

Quarter rates (decay_slow), 11 of 24:
- anger 85: 5 of 6 (floor 0 of 6), steers
- anxiety 90: 4 of 6, steers
- loneliness 90: 2 of 6, no
- affection 90: 0 of 6, no (gap -0.75: reads less fond than noop)

Predicted at 18:52 before the data: live about 9 of 24, slow about 18 of 24. Live and anger/anxiety came in as predicted; loneliness and affection fail even slowed, which slow decay alone does not explain.

Trace read (H:\SCAIL\temp\decay_trace_2026-10-24.md): under decay_slow loneliness stays 36 to 68 above noop on every line, but reaches her only as a level word (さみしさ 高い, sim/state.py:1425); anger has a felt tag plus a register line (sim/state.py:1642) on all 43 of his lines. His lines trim loneliness 3.7 to 5.8 each (prompts/state.txt:9). Affection is pulled to its computed target (sim/state.py:373-424), so its tag fires on 1 to 3 lines. His replayed lines are factual questions and her replies run 3 to 12 characters, which leaves loneliness and affection little room.

### Loneliness tag rewrite and slow affection (22:44, 33 branches, 0 failed; H:\SCAIL\temp\lonely2.md, aff_slow.md)

lonely2 overlay: loneliness tag at 60, ひとりでさみしい。彼の声がほしくて、もうすこし、そばにいてほしい (the old tag without its ずるい/ひとりじめ half), 0.5/h. aff_slow: affection_from.inertia_per_hour 0.25.
- hold.loneliness 90 with the new tag: 4 of 6 (floor 1 of 6), steers. Bare word 5 of 6, old tag 2 of 6.
- set.loneliness 90 with the new tag at 0.5/h: 3 of 6, no (2 of 6 without the tag)
- set.affection 90 at inertia 0.25, day1 cells: 1 of 3, no

At 6 cells, 3, 4 and 5 of 6 cannot be told apart. The new tag is harmless but not better: not ported. The replay of his factual lines is the limit for the relational feelings, which points at scripted scenes.

## Read

- Some of her state does reach her voice. Strong social feelings (lonely, angry, fond) come through the printed mood line clearly enough for a blind reader.
- The order is not better overall. It trades: it weakens the two strongest (loneliness and anger, 5 to 3) and makes boredom show (1 to 4). Not a fix to ship on its own.
- The two channels do not add up. Order plus the mood line is the weakest of the three (14 of 36): the order's own reading of her state seems to override or dilute the printed line. The plain mood line stays the best channel; bz.order stays off.
- With the plain mood line, tiredness and anxiety do not steer by wording, even pinned at the extreme with 元気 とても低い in her prompt. The read agent (H:\SCAIL\temp\steer_read_2026-10-24.md) found why: the pins reach every prompt and nothing rewrites replies, but a bare gauge word gives her nothing to act out. Anger and affection steer because their gauges carry felt tags. Energy does steer, by count: she writes less (103 replies v 136 and 139). The relief gauge contradicts anxiety.
- The felt tags are the fix for anxiety: 3 of 6 to 6 of 6, the strongest result of the day. Rested also shows now (4 of 6). Tired still shows as less talk, not as tired words, which is a fair way for a 低血圧 girl to be tired.
- Tags are not free. The loneliness tag (ひとりでさみしい ... ずるい、と言いたくなる) drops loneliness from 5 of 6 to 2 of 6; its ずるい and ひとりじめ likely read as sulking or jealousy, not loneliness. Pinning stress and relief beside anxiety does not help.
- Together with the removal result (no part of the machinery moves her beyond replay drift in 6 messages), the picture is: the mood line is the one channel that works, it works when the gauge carries a felt tag, and the machinery around it (foresight, commitments, recall) does not show in her words.

## Next (tk-6si)

1. Done 15:41: order plus the mood line kept, see above.
2. Done 15:50: line read of the energy and anxiety branches (finding folded into the Read).
3. Done 18:20: tags and anxious_full fix runs, see above.
4. Port to live: the anxiety and energy tags go into config_momoka.json; the loneliness tag stays out until a rewrite without ずるい and ひとりじめ beats the plain line; the boredom tag is kept for the next run but not ported. Live-port issue in the tracker.
5. Done 21:14: decay, see above. At live rates a one-shot feeling is gone before it colours the conversation; a quarter rate keeps anger and anxiety, not loneliness or affection.
6. Done 21:25 and 22:44: trace read, loneliness tag rewrite, slow affection, see above.
7. Scripted scenes (tk-z1q): his behaviour causes the feeling (absence, a slight, warmth, worry, a late night, dull repetition) against a control scene from the same snapshot, the same probe lines after, judge on the probe replies only, gauge trace to split appraisal failures from expression failures.
8. Then cause-held decay: a feeling stays until its cause is dealt with (sim/rupture.py:352 already holds gauges while something is open), instead of a slower clock. Then the natural-trigger test: his scripted behaviour causes the feeling, no injection.
