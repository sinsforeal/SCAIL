# 千奈 prompts, 2026-10-23

Two files are fed to the model, in this order: bible.md, then style.md, as the system prompt. sheet.json (one level up) is never sent. The bible and the type vocabulary stay out of both files.

## Files

- bible.md: who she is, in Japanese. Relationships, record facts, the secret (pen name 夏天すとら), limits of the record. No age, no grade, parents light and unnamed, never writes 一悟's lines.
- style.md: how she talks. Rules from speech_guide (25, tiered), then "あなたの手": ten moves from her own B3 reading (tools/koikano/b3/sena.py), then what is not hers.
- ../sheet.json: identity, existence answers, holes, and the derived `type` (never in a prompt; exempt in tools/cast_mechanisms_test.py).

Every number in both files is checked by ../b5_check_numbers.py against ../bible.json. The check proves the number exists in the bible, not that it sits on the right thing. Last run: no misses, 52 record ids, 0 bad.

## How they were made

B0-B3 rebuilt with the per-subject B3 hook, B4 gate rerun, ../b5_receipts.py, ../b5_rewrite_speech.py, ../tier_pass.py. Order and commands are in docs/reports/2026-10-23_b3_sena_notebook.md.

## Open limits

- Gate is 5/6, as measured, not tuned. rules_beat_bigram fails: the rule detector scores 0.738 against a plain bigram at 0.837. That check reads speech_guide rules, which this pass did not change, so it did not move.
- mechanisms_distinctive passes at 9 of 10 on the holdout. The room control is small for some moves (the heroine set is six, and some moves have 0 control hits), so the pass is easy where the control is 0.
- Tiers: speech_guide has 5 thin and 1 weak (rule 22, the H vocabulary list is 百花's and matches 0 of her lines). Rule 6 (おおー) and rule 21 (dozing) are firm absence rules by the 1 percent rule; they are "not hers" facts, not habits.
- Rules that rest on expression labels (11 to 14, 16, 23) inherit the C4 label hypothesis (8 of 16 units agreed). Firm here means the count is large, not that the label is true.
- bible_readable.md is the tool's render before the B5 text rewrite and the tier pass: its rule texts are 百花's and its tiers are old. bible.json is the authority.
- Not in any matcher: her plain-form turns after 百花 speaks (164 lines, 65 without です/ます, in b5_receipts.with_百花), because it needs the previous speaker.
- B2 alias table misses みゃー先輩 and takes 十川先輩 as 一悟 in the address terms; counted by hand in b5_receipts.address.
- The record has no family, birthday, age or life outside the 72 scenes. The prompts invent none.
- The type is a coherence check, N axis at 0.4 is thin (see ../sheet.json near_miss).
