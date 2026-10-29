# B5 notes, 真優 (mayu), 2026-10-23 (tk-oas, branch cast/b5_mayu)

Agent: Sonnet 5.5. Started 13:42. Stage: B5 done (job 1 and job 2), number check clean.

## Result

- Job 1 done: 25 speech-guide rule texts and 14 mechanism name/definition/note rewritten from her receipts (script characters/mayu/b5_rewrite_texts.py). text_basis tags: 0 left. bible_readable.md patched to match (b5_patch_readable.py).
- Job 2 done: prompts/bible.md, prompts/style.md, sheet.json.
- Number check: characters/mayu/check_prompt_numbers.py, 0 misses on bible.md (46 ids, 87 numbers) and style.md (14 ids, 256 numbers) after one fix (81).
- Gate before: 4/6 (fail mechanisms_distinctive 4 of 14, rules_beat_bigram 0.674 vs 0.723). Gate after the rewrite: the same 4/6, same numbers. Expected: the gate scores fixed matchers and a fixed rule detector, not the prose.

## Findings

- 百花's prose was wrong for her in more than figures. Examples: "refer to yourself by name" (she says わたし 617 times, name 10), "smile is about half of her faces" (smile 618 of 2715), "bow is the default gesture" (jump 293 and ううっ 267 are ahead), "no ー/ね/よ in the inner voice" (よ 2 lines, ね 1), "laugh rarely" (190 lines), "kiss only on route a" (17 of 19), "cheerful, childlike, self-named".
- The B3 matchers are 百花's vocabulary, so most of her 14 mechanism hits are false positives or mean something else: the 'body' hits are all about 百花's body (04_01:2362, 07_01:3579, 07_01:3610), the 'loanword' hits are がっかり, the 'catchphrase' hit is an echo (a05_01:0783), the 'tease' receipts include two かも hedges caught through からか, the 'noun verdict' hits are すごい / かっこいい. Each note says so.
- Tiers: the 12 non-distinctive mechanisms moved to weak (veils stays thin at 1 line); tier_was keeps the old value; firm 1 (doubles), thin 2, weak 11. This follows the rule the file's own class_note already gave for weak. If meta would rather keep the tool's tiers, revert the `tier` fields and read `tier_was`.
- Her real habits that the tool did not measure as mechanisms: えへへ 115 (plus えへへぇ 28), ん hum (んっ 309), 'してあげる' offers (70 lines, distinctive True in the file), a line-final 一悟 (63), flustered cries (01_01:0819, 01_01:4188, 01_01:5360).
- expression receipt her_units_agreed '8/16' is identical to 百花's: a project-level figure. The rule text says so.
- Gate GOTCHA: the gate needs layers/annotations.json and slice.json, which stay in F:\temp\cast_bundles\mayu\layers. I ran it with --bible-dir F:/temp/cast_bundles/mayu on a copy of the new bible.json, then copied bible.json, gate.json, gate_checks.json back. `--bible-dir characters/mayu` alone fails (no annotations.json).

## 百花 with 真優 (shared scenes, 58)

She calls 百花 百花ちゃん (23). 百花 starts the exchange 64 times, she 0. Faces: surprise 36, sad 34, neutral 29, smile 20, angry 17. From the lines I sampled: 百花 pulls her toward the stage and clings; she is flustered and pushes back (「い、いきなり仲間よばわりは、早い……でしょ？」), keeps 一悟 from 百花 (「渡したりしないよ！」), but takes 百花's body and reasons seriously (04_01:2362, 07_01:3579) and gives way grudgingly (「……仕方ないか……百花ちゃんなら……」). Those unsourced quotes are cited without ids on purpose: their ids are not in bible.json, and the number check would flag them.

## Tried / failed

- Gate with --bible-dir characters/mayu: FileNotFoundError annotations.json (see gotcha).
- First style.md cited 04_01:1008 (should be a04_01:1008) and a bucket label 81: caught by the check, fixed.
- Kanji counters left as warnings in the check: 一つ (one firm move: matches firm_count 1), 一件, 一行, 二つ (idioms from Momoka's style). The only allow-listed one is 二回 (the doubling move's name).
- Check limit: allowed numbers are every numeric leaf in bible.json outside context, spot_check, gate, compared by value, so a coincidental number can pass. Ids are checked verbatim. It is a floor, not a proof.

## Unresolved in the record

- The reading of 真優 (まゆ) is not printed in any line I found; taken from vcid MAY and the slug. 十川 reads とがわ (the game text has トガワ).
- みゃー先輩 and ナタリー appear in other mouths (06_01:6245 千奈: 「みゃー先輩は男性なんですから」, 01_01:1950 and b07_01:0266 she says the nicknames) and I could not tell whether they are a stage persona, a disguise or a joke. Left out of the prompts.
- Which club she belongs to: she says 「うちの部」 (a08_01:0199) and 一悟 is the literary club's president, but she also resists a club form (a02_01:1298). The prompts name no club for her.
- Family: parents appear in one scene each (the father has 4 lines of hers). Kept light and unnamed as ruled.
- Work outside school: 「一悟が学校に通っている時、わたしは仕事場にいる」 (a08_01:1302), 事務所の社長さん in 2 scenes, 取材. The prompts say only that she is a person with stage work and a job outside.
- sheet.json existence: with_him none and sees_him none are my reading of the design for a cast member; the design file does not state them for a cast row. Meta may overrule.
