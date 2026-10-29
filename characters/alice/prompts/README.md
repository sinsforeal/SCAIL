# アリス prompts, working notes (B3, 2026-10-23)

Two files, sent in this order as her system prompt:

1. bible.md (who she is, who is around her, what the record has and lacks)
2. style.md (how she types: counts, endings, marks, her hands, the amounts)

characters/alice/sheet.json is never sent. It holds her type and the existence answers; nothing reads the type into a prompt or a rule (character-method 3.6). No type letters appear in bible.md, style.md or bible.json.

Every number in both files must exist in bible.json. Check: `python -X utf8 characters/alice/B5_check_numbers.py`. Now: 0 misses on both files.

Rebuild order: build with koikano_bible.py --char alice, run B3_apply.py (rule texts, 17 mechanisms, tiers, own-rule markers), run the gate, refresh the two prompt files by hand from bible.json, rerun the number check.

## Open limits

- Gate 5/6. rules_beat_bigram fails. With her own 14 markers on the full corpus: 0.717 against the plain bigram 0.760. Leak-free (build block only): 0.579 against 0.760. The bigram reads every character of the line; 14 single-feature markers cannot match it. 14 of her 28 speech_guide rules have no marker because they are not a property of one spoken line (length, reply rate, face and gesture rates, inner voice, kiss, dozing, emotion overlays).
- No held-out test of her own rules exists. The gate's calibration rows are 百花's markers, so rule tiers rest on the n clause only (rule 17 and others thin, rule 18 weak).
- Thin and weak tiers: 7 of 17 mechanisms are weak (thanks, office voice, hearsay, teasing by noticing, joint move, praise, dog) because the holdout rate is at or under the control rate. style.md files them under "do not spread".
- S/N of her type is not settled (no separation from control); recorded in sheet.json at low confidence.
- The record is silent on her country, her birthday and her looks. bible.md says so and tells her not to fill it.
- ひかる: no address form in the record; bible.md says do not call by name.
- Two kiss counts: 15 lines (style.md, speech) against @キス 20 and @キス止め 10 (bible.md, gestures). Different units (spoken text vs gesture calls); not reconciled.
- bible_readable.md is stale: render_doc fails with KeyError('name') on this branch after the merge from master (not investigated; it was last rendered before). The 百花-era "Corrections" footer paragraph is still in it.
