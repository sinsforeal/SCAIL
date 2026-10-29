# B5 notes, アリス (tk-oas, branch cast/b5_alice), 2026-10-23

Agent: Sonnet 5.5, 13:43-13:55. Stage: done (both jobs, number check clean).

## Result

- Gate before 4/6 (fails mechanisms_distinctive 3 of 14, rules_beat_bigram 0.550 vs 0.760). After 4/6, same two fails, same numbers. Cause: both fails are computed from the tool's fixed matchers (SPECS, 百花's markers: です/ます, っ, ー, ん, おー, childish words), not from the rule text. The text rewrite cannot move them. Fixing them means new アリス matchers in tools/koikano (outside my write scope).
- Gate run form: `python tools/koikano/koikano_bible_gate.py --char alice --bible-dir F:/temp/cast_bundles/alice --bible characters/alice/bible.json --out characters/alice/gate.json` (the big layers live in the scratch dir, not in characters/alice/layers; --bible-dir characters/alice fails on annotations.json).
- Job 1: characters/alice/B5_apply_speech_guide.py rewrote 24 rule texts (rule 0 was already hers, 20 is a moment rule with no tag), removed every text_basis tag (rules and mechanisms), added 3 rules of her own (soft particles, noticing sounds, address terms), recomputed mechanism distinctive/tier/gate_control_rate from her own gate.json holdout, rewrote the 14 mechanism notes and the block-level class_note/cross_reference/note. bible_readable.md patched with B5_patch_readable.py (render_doc needs the full build result, not available).
- Job 2: prompts/bible.md, prompts/style.md, sheet.json.
- Number check: B5_check_numbers.py, 0 misses in bible.md (59 distinct numbers) and style.md (146). Single-digit integers were read by eye and are right.

## Found in 百花's carry-over (fixed in bible.json)

- Mechanisms: all 14 were distinctive:false and tiers were 百花's (7 firm incl. 5 with 0 lines for her). Her own holdout: 3 of 14 above control (apologises, teases, hedges). Tiers now firm 2, thin 1, weak 11; 6 mechanisms have 0 lines (absent_in_her_lines).
- gate_control_rate/distinctive_note in the mechanism rows were 百花's (0.084 = 17/203 etc.). Replaced with her gate numbers (control 157 lines).
- Rule 11 said smile is half of expression hits; her ratio is 509 of 1709. Rule 21 said 6 of 7 dozing lines; hers is 0.
- Rule 18 receipt 8/16 is a 百花 figure; noted in the rule, no figure of her own exists.

## Record facts used (ids are scene:line)

生徒会長 04_01:0189; slogan 01_01:4970; 実家が劇場 01_01:1160; parents' trade only 07_01:4834; 留学 07_01:4776; homestay at 百花's 01_01:4627, 07_01:4882; 相棒 01_01:1505; 百花's health 07_01:3909, 07_01:4733; cheering 百花 07_01:5004; おねだり上手 07_01:2800; 百花's singing a01_01:1887; reading nights 09_01:6047; route c: c02_01:1645, c02_01:1699, c03_01:1610, c03_02:1373.

## Not resolved

- Where she is from: record says 留学 and a childhood arrival, no country. Kept as a hole.
- ひかる: the address table finds 小野坂くん 3 times in lines after ひかる's turns; not confirmed to be about ひかる. No name form set.
- Her kiss counts differ by source: speech_guide kiss_lines 15, relationship gesture table @キス 20 / @キス止め 10. Bible says 15 lines in style.md, 20/10 gestures in bible.md. Both are in bible.json.
- Hit: rules_beat_bigram stays failed. If she is promoted to a full mind, a hand check of the prompts against her lines is worth more than this gate.
- The bible.md line about 百花 and the hosting (homestay) is the record's, and not in 百花's own bible (which says no family appears). Consistent with the design ruling (house, 千代田 name, 真里亜 in; parents light).

## Gotchas

- bible.json is written with indent 2, sort_keys True (the gate rewrites it the same way). The apply script is not idempotent (it appends 3 rules); do not rerun it on the edited file.
- Scratch: F:/temp/cast_bundles/alice (layers, original bible.json).
