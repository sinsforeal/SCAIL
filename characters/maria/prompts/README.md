# maria prompts

Feed order: bible.md first, then style.md, both as the system prompt. sheet.json is never sent.

Built from the koikano 真里亜 record: 65 scenes, 1228 spoken lines. Every number in the two files is checked by `python characters/maria/check_prompt_numbers.py` (0 misses is the bar).

No age, grade, birthday, birthplace or family detail is written anywhere. Parents appear only as the words 「ご主人様と奥様」, unnamed.

## Open limits

- No route of her own. Every scene of hers is someone else's route, so her record is her side of other people's stories.
- Mechanisms are thin: 14 own mechanisms, 8 firm, 4 thin, 2 weak. reminds_them_of_what_was_said (6 lines) and teases (6) are too thin for the holdout to say anything.
- rules_beat_bigram: see characters/maria/gate_checks.json and docs/reports/2026-10-23_b3_maria_notebook.md for the measured result.
- Expression labels are hypotheses; the H scenes carry no faces.
