# 知紗 prompts, 2026-10-24

Two files are fed to the model, in this order: bible.md, then style.md, as the system prompt. sheet.json (one level up) is never sent. The bible and the type vocabulary stay out of both files.

## Files

- bible.md: who she is, in Japanese. The role (PE teacher, adviser of the small clubs), the people, the H scene 08_02 told plainly with scene:line receipts, and a section of marked liberties (week, home, age, inner life). No age, no grade, no family written.
- style.md: how she talks. Rules from speech_guide (tiered), then 16 "hands" from her own B3 (tools/koikano/b3/chisa.py) with counts and the room's rates, then what is not hers.
- ../sheet.json: identity, existence answers, holes, and the derived `type` (never in a prompt).

Every number in both files is checked by ../check_prompt_numbers.py against ../bible.json. The check proves the number exists in the bible, not that it sits on the right thing. The scene:line ids are checked against `b5_receipts.lines`, which ../b5_receipts.py fills from her own line file. Last run: 0 misses (bible.md 123 ids, style.md 46 ids).

## How they were made

B0-B3 built with the per-subject B3 hook (tools/koikano/b3/chisa.py), ../b5_texts.py (rule texts from counts, tier rule, markers), B4 gate (../gate.json), ../b5_receipts.py (receipts for the prompts and the ペニス count correction). Hand-read from the 557 lines in koikano_work/character_lines/知紗.jsonl.

## Liberties (marked "liberty:" in bible.md)

Week, home, age (no number, adult), inner life (no inner line in the record), her ties to colleagues, and anything after the H scene. Family is not a liberty: none is written. Each liberty names the lines it rests on.

## Open limits

- Gate is 5/6 as measured, not tuned. rules_beat_bigram fails (0.704 against a bigram at 0.773).
- The H scene 08_02 is wholly inside the build block: the holdout (106 lines) has no H line, so the gate never tested her H register.
- Rules that rest on expression labels inherit the C4 label hypothesis.
- The record has no family, birthday, age or life outside the 37 scenes. Anything beyond is a marked liberty.
