# koikano authored expression bible - アリス (CC)

Date: 2026-09-16. Build: b0-b3/1 (authored-expression-bible/1). Phases B0+B1+B2+B3. B0-B2 are mechanical (no model spend, standard library); B3 is the builder's reading of the rhetorical moves, recorded in `mechanisms`. Route c. Source: `F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work\game_logic.jsonl` joined to the authored stage directions.

**The expression labels are C4 hypotheses, not ground truth.** Every label carries its confidence and provenance in `layers/annotations.json` and `bible.json`; the authored `@emotion` overlays are the author's, the merged `expression` labels are a derived hypothesis.

## Run

```powershell
python "F:\REPS2\clipboard capture (kirikiri)\src\kirikiri_tools\koikano_bible.py"
```

One command, repeatable. `--corpus`, `--out` and `--char` override the input root, the output directory and the subject. The run exits 2, and writes nothing, if a `record_id` join does not match `game_logic.jsonl`.

## Schema

`bible.json` carries `identity`, `voice`, `expressions`, `gestures`, `interactions`, `bounds`, `speech_guide`, `mechanisms`, `context`, `spot_check` and `provenance`. B2 assembled the `voice` surface, the expression and gesture **triggers**, the corrected interaction address terms, the `speech_guide` and the B2 bounds. B3 added `mechanisms`: the rhetorical moves with no stage direction, which are the builder's reading. The layers under `layers/` remain the B0/B1 build products:

| file | content |
| --- | --- |
| slice.json | her lines, her scenes, inner voice, the room; counts and ids |
| battery.json | token/ngram counts, dispersion, distinctive n-grams |
| bounds.json | reply/initiation, relationships, emotional pressures, absent list |
| context.json | route, story phase, H-scene, BGM per scene |
| annotations.json | per line and per scene: faces, gestures, emotion, entry/exit, camera |
| interactions.json | per-relationship turns, initiation, length, mix, address terms |

## Identity and counts

| measure | count |
| --- | --- |
| her lines | 2831 |
| - spoken | 2792 |
| - inner voice | 39 |
| her scenes | 59 |
| room lines (others in her scenes) | 21671 |
| - room spoken | 12410 |
| - room inner | 9261 |

The scope's section 5.1 figure for アリス is 2,781 lines, 211 inner and 70 scenes. This build reproduces all three.

## Voice: her dialogue, her inner voice, the room

`dispersion` is scene document frequency: the share of her scenes in which the n-gram appears. `distinctive` is the log-odds of the channel against the other two channels pooled.

| channel | lines | tokens | token types | TTR |
| --- | --- | --- | --- | --- |
| her dialogue | 2792 | 10814 | 5497 | 0.5083 |
| her inner voice | 39 | 101 | 99 | 0.9802 |
| the room (spoken) | 12410 | 32251 | 18832 | 0.5839 |

Distinctive tokens (log-odds, top 12):

- **her_dialogue**: 一悟くん (76), おや (50), ぁむ (25), はぁあ (25), あああっ (23), はぁん (22), ふぁああっ (20), ふぁあっ (20), はぁああっ (18), んぁああっ (18), んふ (18), んぁ (17)
- **her_inner**: and (2), the (2), All (1), all (1), men (1), merely (1), players. (1), s (1), stage (1), women (1), world (1), あの日 (1)
- **the_room**: はい (205), そうですね (118), 百花ちゃん (104), ナタリー (92), いえ (78), みゃー先輩 (77), お嬢様 (76), わんっ (66), おおー (64), えへへ (63), すみません (60), アリス会長 (59)

### B2 surface: turn length, line-final, punctuation, self-reference

Turn length, kept characters per line (shares are in `bible.json`):

| channel | 1-5 | 6-10 | 11-20 | 21-40 | 41-80 | 81+ | mean | median | p90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| her_spoken | 173 | 204 | 727 | 1455 | 214 | 0 | 24.16 | 24 | 39 |
| her_inner | 2 | 2 | 9 | 21 | 5 | 0 | 25.31 | 24 | 44 |
| the_room_spoken | 1529 | 1688 | 3552 | 4707 | 761 | 0 | 19.65 | 18 | 37 |

Line-final morphemes, string suffixes of the kept text (top 10):

- **her spoken last token**: っ 38, 一悟くん 29, あああっ 17, ああっ 16, んん 16, ありがとう 15, ね 13, んんっ 13, ふふふっ 12, 私は 12
- **her spoken 2-char suffix**: あっ 134, かな 133, だね 101, だよ 98, んだ 85, ああ 79, かい 66, んっ 63, るよ 57, から 55
- **her inner last token**: players. 1, あんな 1, あんなことがあったばかりで 1, ここへやってくるのはまだ先のことだろう 1, このざわめくような感情に気付きもしないまま 1, すぐに限界だった 1, その真ん中へと強引に引っ張り出そうとする 1, だ 1, ちょっとした危機に見舞われている 1, どうしようもなく漏れてしまう 1
- **her inner 2-char suffix**: いる 4, から 3, ろう 3, った 2, s. 1, ある 1, いた 1, いだ 1, いて 1, しい 1

Line-final particles, matched by suffix against a fixed list (top 10 by spoken lines):

| ending | spoken lines | spoken share | inner lines | inner share |
| --- | --- | --- | --- | --- |
| っ | 404 | 0.1447 | 0 | 0.0 |
| ね | 332 | 0.1189 | 0 | 0.0 |
| よ | 278 | 0.0996 | 0 | 0.0 |
| な | 189 | 0.0677 | 1 | 0.0256 |
| ん | 138 | 0.0494 | 0 | 0.0 |
| かな | 133 | 0.0476 | 0 | 0.0 |
| だね | 101 | 0.0362 | 0 | 0.0 |
| だよ | 98 | 0.0351 | 0 | 0.0 |
| か | 80 | 0.0287 | 0 | 0.0 |
| から | 55 | 0.0197 | 3 | 0.0769 |

Punctuation, full-width marks:

| mark | spoken count | spoken/line | inner count | room/line |
| --- | --- | --- | --- | --- |
| … | 4488 | 1.6074 | 18 | 0.8919 |
| ！ | 775 | 0.2776 | 0 | 0.1517 |
| ？ | 621 | 0.2224 | 0 | 0.2834 |
| 、 | 4997 | 1.7898 | 33 | 0.9367 |
| 。 | 1006 | 0.3603 | 40 | 0.3361 |
| ー | 152 | 0.0544 | 3 | 0.1402 |
| ～ | 29 | 0.0104 | 0 | 0.0062 |
| 「 | 2788 | 0.9986 | 0 | 0.9958 |

Self-reference: spoken アリス 14 occurrences on 14 lines; spoken 私 403 occurrence(s) on 393 line(s); inner アリス 0 occurrence(s) on 0 line(s).

- **her dialogue vs the room, tokens**: 一悟くん (76), おや (50), ぁむ (25), はぁあ (25), あああっ (23), はぁん (22), ふぁああっ (20), ふぁあっ (20), はぁああっ (18), んぁああっ (18)
- **her dialogue vs the room, bigrams**: 悟く (213), ゅる (55), むち (54), ぁむ (50), 奈ち (45), んぁ (134), っぁ (42), 精液 (38)
- **her dialogue vs her inner, tokens**: あ (301), ん (193), ああ (182), うん (134), っ (115), ふふ (107), ぁ (99), んん (98), 一悟くん (76), んぅ (62)
- **her dialogue vs her inner, bigrams**: ああ (1118), ぁあ (682), んん (505), あぁ (380), っん (347), っあ (344), はぁ (344), んっ (321)

## Expressions (C4 hypotheses)

The repertoire is her own faces only (message face or sprite tag carrying the `CC` prefix). Confidence is carried from `expression_labels.json`.

| expression | her lines | confidence split |
| --- | --- | --- |
| smile | 509 | {'clear': 509} |
| talk | 431 | {'ambiguous': 394, 'clear': 37} |
| excited | 377 | {'explicit': 377} |
| neutral | 178 | {'clear': 55, 'ambiguous': 123} |
| surprise | 82 | {'ambiguous': 47, 'explicit': 27, 'inferred': 8} |
| sad | 66 | {'ambiguous': 66} |
| worried | 42 | {'clear': 42} |
| serious | 24 | {'clear': 24} |

### Expression triggers (all eight labels)

One row per label. `lines` is her lines carrying it (a line with two faces counts once here; the repertoire counts occurrences). `with` is the speaker whose turn preceded hers; `(none)` is a scene-opening or unattributed turn. `preceded by` is the last expression she wore earlier in the scene; `co-gesture` is the gesture on the same line. Co-occurrence, not cause.

| expression | lines | with | route | H/normal | mean chars | preceded by | co-gesture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smile | 492 | 一悟 332, 千奈 42, 真優 30 | common 236, c 186, a 29 | normal 492 | 26.64 | smile 161, talk 158, excited 115 | @おじぎ 96, @否定 25, @ううっ 18 |
| talk | 415 | 一悟 283, 千奈 33, 真優 31 | common 196, c 164, a 32 | normal 415 | 23.46 | talk 124, smile 115, excited 75 | @おじぎ 77, @ううっ 24, @否定 21 |
| excited | 366 | 一悟 259, 真優 31, 千奈 29 | c 165, common 156, b 18 | normal 366 | 23.71 | excited 161, smile 95, talk 74 | @おじぎ 68, @ううっ 56, @ジャンプ 16 |
| neutral | 178 | 一悟 128, 真優 12, 千奈 11 | c 99, common 62, a 6 | normal 178 | 15.25 | smile 42, talk 29, excited 28 | @ジャンプ 14, @おじぎ 11, @ううっ 10 |
| surprise | 82 | 一悟 64, ケルベロス 6, 真優 4 | c 58, common 22, b 1 | normal 82 | 14.39 | neutral 21, surprise 21, talk 14 | @ううっ 24, @ジャンプ 8, @否定 6 |
| sad | 66 | 一悟 45, 真優 6, アリス 5 | c 45, common 18, a 2 | normal 66 | 19.0 | talk 15, smile 13, excited 11 | @おじぎ 12, @否定 5, @ううっ 2 |
| worried | 42 | 一悟 34, 真優 5, 真里亜 2 | c 34, common 6, a 1 | normal 42 | 21.52 | sad 12, surprise 6, talk 6 | @おじぎ 3, @否定 3, @息切れ 1 |
| serious | 24 | 一悟 20, 千奈 2, 真優 2 | c 19, common 5 | normal 24 | 22.29 | talk 7, surprise 5, excited 4 | @ううっ 4, @おじぎ 1, @ジャンプ 1 |

## Gestures

| gesture | her lines |
| --- | --- |
| @おじぎ | 301 |
| @ううっ | 139 |
| @否定 | 74 |
| @ジャンプ | 48 |
| @キス | 20 |
| @キス止め | 10 |
| @噴飯２ | 3 |
| @抱きつき | 3 |
| @主人公視点戻し | 1 |
| @息切れ | 1 |

Entry/exit: {'enter': 21}. Camera (targeted): {'@focus': 10}. Emotion overlays: {'キラン': 5, '汗': 3, 'びっくり': 1, 'びっくりF': 1, 'キラキラ': 1, 'ハート01': 1}. Action commands (occurrences): {'@char': 1610, '@focus': 25, '@action': 9, '@move': 4}.

### Gesture triggers

One row per gesture. `co-face` is the C4 label on the same line; `preceded by` is the last label earlier in the scene; the other columns as above.

| gesture | lines | with | route | H/normal | mean chars | co-face | preceded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| @おじぎ | 301 | 一悟 214, 真優 20, 千奈 15 | c 146, common 102, a 22 | normal 301 | 23.6 | smile 101, talk 84, excited 69 | smile 77, talk 74, excited 50 |
| @ううっ | 139 | 一悟 109, 千奈 7, ケルベロス 6 | c 75, common 44, d 9 | normal 139 | 19.63 | excited 57, talk 25, surprise 24 | excited 30, talk 29, smile 25 |
| @否定 | 74 | 一悟 52, 真優 10, 千奈 4 | c 38, common 26, b 5 | normal 74 | 27.15 | smile 27, talk 21, excited 9 | talk 20, excited 15, smile 14 |
| @ジャンプ | 48 | 一悟 29, ケルベロス 9, 真優 3 | c 24, common 22, a 2 | normal 48 | 13.9 | excited 16, neutral 14, talk 9 | smile 12, talk 11, excited 10 |
| @キス | 10 | 一悟 10 | c 10 | normal 10 | 9.2 | neutral 5, excited 3, smile 2 | neutral 4, excited 3, smile 2 |
| @キス止め | 5 | 一悟 5 | c 5 | normal 5 | 24.0 | excited 2, neutral 2, surprise 1 | excited 2, neutral 2, surprise 1 |
| @噴飯２ | 3 | 一悟 2, ケルベロス 1 | c 3 | normal 3 | 10.67 | surprise 3 | excited 1, surprise 1, talk 1 |
| @抱きつき | 3 | 一悟 3 | c 2, common 1 | normal 3 | 6.0 | neutral 1, surprise 1, talk 1 | neutral 1, surprise 1, talk 1 |
| @主人公視点戻し | 1 | 真優 1 | c 1 | normal 1 | 24.0 | sad 1 | (scene-start) 1 |
| @息切れ | 1 | 千奈 1 | common 1 | normal 1 | 3.0 | worried 1 | neutral 1 |

### Emotion, entry/exit and action triggers

| trigger | lines | with | H/normal | co-face |
| --- | --- | --- | --- | --- |
| emotion キラン (lines) | 5 | 一悟 3, ひかる 1 | normal 5 | excited 3, neutral 1 |
| emotion 汗 (lines) | 3 | 一悟 2, 千奈 1 | normal 3 | talk 2, sad 1 |
| emotion びっくり (lines) | 1 | 一悟 1 | normal 1 | surprise 1 |
| emotion びっくりF (lines) | 1 | ケルベロス 1 | normal 1 | surprise 1 |
| emotion キラキラ (lines) | 1 | 一悟 1 | normal 1 | excited 1 |
| emotion ハート01 (lines) | 1 | 一悟 1 | normal 1 | excited 1 |
| enter/exit enter (lines) | 21 | 一悟 12, 真優 3 | normal 21 | talk 11, smile 5 |
| action @char (lines) | 1476 | 一悟 992, 千奈 111 | normal 1476 | smile 439, talk 361 |
| action @focus (lines) | 10 | 一悟 5, アリス 1 | normal 10 | smile 5, talk 3 |
| action @action (lines) | 8 | 一悟 5, 百花 2 | normal 8 | excited 4, smile 1 |
| action @move (lines) | 2 | 一悟 1, 千奈 1 | normal 2 | smile 1, worried 1 |

## Interactions (per relationship)

| speaker | kind | turns | spoken | inner | scenes | her turns | her avg chars | her med chars | exch. her-start | exch. their-start | her expression mix | her gestures | her address |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 一悟 | protagonist | 13927 | 5322 | 8605 | 58 | 2216 | 23.98 | 24 | 10 | 254 | smile 345, talk 295, excited 267, neutral 128 | @おじぎ 214, @ううっ 109, @否定 52 | 一悟くん 146, 一悟 103 |
| 真優 | heroine | 2329 | 2066 | 263 | 51 | 129 | 24.33 | 24 | 0 | 20 | excited 32, talk 31, smile 30, neutral 12 | @おじぎ 20, @否定 10, @ううっ 6 | 真優ちゃん 19, 真優 2, 十川 1 |
| 千奈 | heroine | 2029 | 1822 | 207 | 50 | 130 | 26.32 | 26 | 0 | 61 | smile 45, talk 36, excited 29, neutral 11 | @おじぎ 15, @ううっ 7, @否定 4 | 千奈ちゃん 14 |
| 百花 | heroine | 1541 | 1356 | 185 | 48 | 66 | 27.59 | 30 | 0 | 38 | smile 16, talk 10, excited 9, neutral 6 | @おじぎ 12, @否定 4, @ううっ 2 | 百花 12 |
| 真里亜 | heroine | 805 | 805 | 0 | 50 | 78 | 26.28 | 28 | 1 | 9 | smile 20, talk 15, excited 12, neutral 8 | @おじぎ 12, @ううっ 6 | 真里亜 11 |
| ひかる | heroine | 398 | 398 | 0 | 34 | 32 | 24.38 | 23 | 1 | 29 | excited 7, smile 7, talk 6, neutral 2 | @否定 2, @ううっ 1, @おじぎ 1 | 小野坂くん 3 |
| 知紗 | heroine | 367 | 367 | 0 | 33 | 28 | 27.54 | 30 | 0 | 1 | smile 10, talk 8, excited 6, sad 2 | @おじぎ 3, @ジャンプ 1, @否定 1 | - |
| ケルベロス | heroine | 168 | 168 | 0 | 34 | 65 | 21.45 | 20 | 0 | 66 | smile 21, talk 20, excited 11, surprise 6 | @おじぎ 14, @ジャンプ 9, @ううっ 6 | ケル 16, ケルベロス 16 |
| 天文部部員 | npc | 22 | 22 | 0 | 4 | 2 | 10.5 | 13 | 0 | 0 | neutral 1, talk 1 | @ジャンプ 1 | - |
| 女子生徒 | npc | 9 | 9 | 0 | 1 | 4 | 11.5 | 14 | 0 | 1 | excited 1, smile 1 | @おじぎ 2, @ジャンプ 1 | - |
| 一年生女子 | npc | 8 | 8 | 0 | 3 | 2 | 13.5 | 14 | 0 | 1 | smile 1, talk 1 | - | - |
| 新聞部部長 | npc | 8 | 8 | 0 | 3 | 5 | 30.6 | 18 | 0 | 1 | smile 2, talk 1 | - | - |
| 事務所の社長さん | npc | 7 | 7 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 文化祭実行委員 | npc | 6 | 6 | 0 | 3 | 3 | 33.33 | 34 | 0 | 1 | smile 3 | @おじぎ 1 | - |
| テニス部部員 | npc | 5 | 5 | 0 | 2 | 2 | 33.0 | 37 | 0 | 1 | smile 2 | @おじぎ 1 | - |
| 弱小部女子生徒Ａ | npc | 5 | 5 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 弱小部女子生徒Ｂ | npc | 5 | 5 | 0 | 1 | 3 | 5.67 | 1 | 0 | 0 | neutral 2, surprise 1 | - | - |
| 見知らぬ女性Ａ | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 見知らぬ女性Ｂ | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 野村先生 | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 三年生女子 | npc | 3 | 3 | 0 | 1 | 3 | 10.0 | 10 | 0 | 1 | excited 2, talk 1 | @ううっ 1, @おじぎ 1 | - |
| 映画研究部部長 | npc | 3 | 3 | 0 | 1 | 4 | 17.75 | 21 | 0 | 0 | smile 3, talk 1 | @おじぎ 1 | - |
| 野球部部員 | npc | 3 | 3 | 0 | 1 | 2 | 22.0 | 28 | 0 | 0 | excited 1, smile 1 | @ううっ 1, @ジャンプ 1 | - |
| 案内アナウンス | npc | 2 | 2 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 真優＆千奈 | unison | 2 | 2 | 0 | 2 | 2 | 23.5 | 41 | 0 | 0 | - | - | - |
|  | unattributed | 1 | 0 | 1 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 千奈＆アリス＆百花＆ひかる＆真里亜＆知紗 | unison | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 真優＆千奈＆一悟 | unison | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 芸能記者 | npc | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |

Scene openings across her scenes: 一悟 19, アリス 12, 千奈 7, 真優 7, 百花 6, ひかる 5, ケルベロス 1, 案内アナウンス 1, 真里亜 1.

Reply vs initiation (her spoken turns): replies 1733, initiations 12, self-continuations 1047, reply rate 0.993.

### Address terms

How she names the other party, derived from her lines whose preceding speaker is that party. Overall: {"一悟くん":146,"一悟":103,"真優ちゃん":19,"ケル":16,"ケルベロス":16,"千奈ちゃん":14,"百花":12,"真里亜":11,"小野坂くん":3,"真優":2,"十川":1,"十川真優":1}.

B1 built the alias table from charData.csv, which holds only the eight named cast. The protagonist 一悟 is absent, so B1 reported no address term for him; B2 adds 一悟 to the alias table here only. The interaction layer on disk is unchanged.

Relationships where no name term is derivable from her lines: 知紗, 天文部部員, 女子生徒, 一年生女子, 新聞部部長, 文化祭実行委員, テニス部部員, 弱小部女子生徒Ｂ, 三年生女子, 映画研究部部長, 野球部部員, 真優＆千奈.

## Speech guide

Each rule carries a class (hers / the author's / a moment), a tier (firm / thin), a `register` (all / H / non-H / per-register) and an evidence flag (measured / inferred). The receipt is the count or the lines the rule comes from; the example lines are in `bible.json`. Rules whose value differs by register state both.

| rule | class | tier | register | evidence | receipt |
| --- | --- | --- | --- | --- | --- |
| Refer to yourself as 私 (not by your own name); do not use アリス. Holds in both registers. | hers | firm | all | measured | {"spoken_lines_with_アリス":14,"spoken_lines_with_私":393,"spoken_occurrences_アリス":14,"spoken_occurrences_私":403,"私_by_register":{"H"… |
| Speak in mid-length turns: median 23 kept characters outside H and 27 inside H (24 pooled over 2792 spoken lines); no line is longer than 57. Length does not separate her registers; H differs by marks and sounds, not by running longer. | hers | firm | per-register | measured | {"H":{"lines":961,"max_chars":52,"mean_chars":25.66,"median_chars":27},"non_H":{"lines":1831,"max_chars":57,"mean_chars":23.37,"m… |
| Reply; do not open. Her reply rate is 0.9931 (1733 replies, 12 scene openings), and she keeps going inside her own turn (1047 self-continuations): answer first, then run on, never start the exchange. | hers | firm | all | measured | {"initiation":12,"reply":1733,"reply_rate":0.9931,"self_continuation":1047} |
| Close a line on a clipped っ only when the line is a decree, a catch or an exasperated call (だから私は生徒会長の責務として、このような決定を下すことにしたっ; まったく、ケルベロスっ; に、逃がすかっ). It ends 404 lines (0.1447 of her spoken lines), 304 of them in H (moans) and 100 outside it, so outside H it is occasional, not a habit. | hers | firm | per-register | measured | {"by_register":{"H":{"lines":304,"n":961},"non_H":{"lines":100,"n":1831}},"lines_ending_っ":404,"share_of_spoken":0.1447} |
| Do not stretch a last syllable with ー. It ends 2 of her spoken lines (0.0007), 0 in H, and both are a breath or a sigh (ふぅー……), not a drawl. Her sentence ends are the soft particles (ね, よ, かな), not ー. | hers | firm | non-H | measured | {"by_register":{"H":{"lines":0,"n":961},"non_H":{"lines":2,"n":1831}},"lines_ending_ー":2,"share_of_spoken":0.0007} |
| The doubled ん is a moan token for her, not an agreement: んん appears 98 times (89 in H, 9 outside), んっ 27 (24 in H, 3 outside), んんっ 33, んーん 0. Outside H she agrees in words: うん (134), そうだね (46), そうか (39). | hers | firm | per-register | measured | {"token_うん":134,"token_そうか":39,"token_そうだね":46,"token_んっ":27,"token_んっ_by_register":{"H":24,"non_H":3},"token_んん":98,"token_んん_by… |
| Do not show delight with おおー / おー: both have 0 hits in both registers. Her delight is a written laugh, ふふ (107) and ふふっ (41), and noticing is おや (50). | hers | firm | non-H | measured | {"token_おおー":0,"token_おおー_by_register":{"H":0,"non_H":0},"token_おや":50,"token_おー":0,"token_おー_by_register":{"H":0,"non_H":0},"tok… |
| Plain childish words are not her register: 27 lines match (21 in H, 6 outside), えへへ 0, きちゃう 1, and the outside-H hits are an adult いっぱい (めいっぱい, 今週いっぱい, 力いっぱい). Do not add えへへ or childish exclamations. | hers | firm | per-register | measured | {"by_register":{"H":{"lines":21,"n":961},"non_H":{"lines":6,"n":1831}},"lines_matched":27,"token_いっぱい":5,"token_えへへ":0,"token_きちゃ… |
| Stay in plain form with a courteous edge: です / ます turns up in 25 of 2792 spoken lines (32 occurrences), a formal turn now and then (それは助かりますが……), never the base. | hers | firm | all | measured | {"lines_with_です_ます":25,"of_spoken_lines":2792,"token_ですます_occurrences":32} |
| Use the ellipsis as a held beat before the line lands (おや……？, ああ、なるほど……): 0.8749 per line outside H (1602 marks), 3.0031 per line inside H (2886 marks, moan elongation). The room outside her runs 0.8919, so outside H she sits at the room's rate. Read it as direction, not a fixed rate. | hers | firm | per-register | measured | {"room_per_line":0.8919,"spoken_lines":2792,"…_by_register":{"H":{"count":2886,"per_line":3.0031},"non_H":{"count":1602,"per_line… |
| Exclaim sparingly outside H (0.0453 ！ per line, 83 marks) and ask often: ？ runs 0.2572 per line outside H (471 marks). H moans carry ！ heavily (0.7201 per line, 692 marks); the room outside her averages 0.1517 ！ per line. | hers | firm | per-register | measured | {"room_！_per_line":0.1517,"！_by_register":{"H":{"count":692,"per_line":0.7201},"non_H":{"count":83,"per_line":0.0453}},"？_by_regi… |
| Default to a smile face on non-H lines: 492 of 1870 non-H lines carry one (509 smile hits of 1709 expression hits in all). H scenes carry no face annotations (0 of 961 lines). | hers | firm | non-H | measured | {"all_occurrences":1709,"smile_lines":492,"smile_lines_by_register":{"H":{"lines":0,"n":961},"non_H":{"lines":492,"n":1870}},"smi… |
| Bow (@おじぎ) as the default gesture outside H: 301 of 1870 non-H lines, 101 of them with a smile; none in H (0 of 961). | hers | firm | non-H | measured | {"@おじぎ_occurrences":301,"by_register":{"H":{"lines":0,"n":961},"non_H":{"lines":301,"n":1870}},"co_smile":101,"lines":301} |
| When refusing, use @否定 (74 lines, non-H only) and keep smiling: 27 of them carry a smile and 5 a sad face. Her refusals are the teasing おやおや / いやいや kind (誰にでもなんてことはないよ？), not a hard no. | hers | firm | non-H | measured | {"@否定_occurrences":74,"by_register":{"H":{"lines":0,"n":961},"non_H":{"lines":74,"n":1870}},"co_sad":5,"co_smile":27} |
| Jump (@ジャンプ) on surprise, not on laughter: 48 lines, non-H only, 8 of them with a surprise face and 0 with a laugh face (おや、それならどうして？; 本当かい？). | hers | firm | non-H | measured | {"@ジャンプ_occurrences":48,"by_register":{"H":{"lines":0,"n":961},"non_H":{"lines":48,"n":1870}},"co_laugh":0,"co_surprise":8} |
| Keep the inner voice as bare written narration, not speech: 39 lines, 0 in H, median 24 characters, no quotes, no っ (0 lines end in it), type-token ratio 0.9802 against 0.5083 for her speech. It speaks of 私 and 一悟くん in plain narrating form (だろう, ている); never アリス. | hers | firm | non-H | measured | {"inner_lines":39,"inner_lines_H":0,"inner_lines_ending_っ":0,"inner_median_chars":24,"inner_ttr":0.9802,"spoken_ttr":0.5083} |
| Supply a face on most of her non-H lines (rate 0.8032, 1502 of 1870) and a gesture on about three in ten (rate 0.3123, 584); H scenes carry no faces and no gestures (0 of 961). | author | firm | per-register | measured | {"H":{"expression_rate":0.0,"gesture_rate":0.0,"lines":961,"with_expression":0,"with_gesture":0},"non_H":{"expression_rate":0.803… |
| Use @emotion overlays sparingly: 12 lines in all (キラン 5, 汗 3, びっくり 1, びっくりF 1, キラキラ 1, ハート01 1); they are authored colour, not her mood words. | author | thin | all | measured | {"lines_with_emotion":12,"types":{"びっくり":1,"びっくりF":1,"キラキラ":1,"キラン":5,"ハート01":1,"汗":3}} |
| Treat every expression label as a C4 hypothesis with a confidence, not a fact. The agreement figure in the receipt was measured on 百花's units; no figure of her own exists. | author | weak | all | inferred | {"her_units_agreed":"8/16 classifiable (see docs/koikano-expression-labels.md)","vocabulary_version":"0.2"} |
| Remember that @おじぎ is the most common gesture corpus-wide (1576 calls), so her 301 bow lines are partly a house convention. | author | thin | all | inferred | {"corpus_@おじぎ_calls":1576,"her_@おじぎ":301} |
| Keep kiss gestures (@キス, @キス止め) only with 一悟, only on route c. | moment | thin | all | measured | {"kiss_lines":15,"route_c":15,"with_一悟":15} |
| Do not give her dozing (@居眠り横 / @居眠り縦): 0 lines in the record, 0 with 一悟. Leave sleepiness out. | moment | firm | all | measured | {"lines":0,"routes":{},"with_一悟":0} |
| Keep the H-scene vocabulary (the matcher's list: せーえき, おちんちん, おまんこ, きちゃう) inside the H scenes: 99 lines carry it, all in the 5 H scenes and 0 outside. Her own spellings include 精液 (38 bigram hits) and おちんちん (29 tokens). | moment | firm | H | measured | {"bigram_精液":38,"h_scenes":5,"in_H_scenes":99,"in_non_H":0,"lines_with_H_tokens":99,"token_おちんちん":29} |
| Laughter is not tagged on her lines (0 laugh-face lines, 0 with @ジャンプ); it is written into the words: ふふ (107) and ふふっ (41). | moment | firm | non-H | measured | {"by_register":{"H":{"lines":0,"n":961},"non_H":{"lines":0,"n":1870}},"laugh_lines":0,"token_ふふ":107,"token_ふふっ":41,"with_@ジャンプ":… |
| Voice her as composed, teasing and theatrical: plain-form sentences with soft particles (ね, よ, かな, だね, だよ), 私 for herself, mid-length turns (median 23 characters outside H, 27 inside), the ellipsis as a held beat (0.8749 per line outside H). Where the register shifts toward moans inside an H scene it shifts by sound (3.0031 … per line), not by childishness. | hers | thin | per-register | inferred | {"H":{"ellipsis_per_line":3.0031,"median_chars":27},"non_H":{"ellipsis_per_line":0.8749,"median_chars":23},"third_person_lines":3… |
| Close a turn on a soft particle, not a bare verb: ね ends 332 of her spoken lines (0.1189), よ 278 (0.0996), な 189, かな 133 (0.0476), だね 101, だよ 98, ん 138. That is the composed, explaining frame of her voice (…だよ, …だね, …かな). | hers | firm | all | measured | {"line_final_かな":133,"line_final_かな_share":0.0476,"line_final_だね":101,"line_final_だよ":98,"line_final_な":189,"line_final_ね":332,"l… |
| Notice before you answer and laugh in words: おや is 50 of her tokens, ふふ 107, ふふっ 41, ああ 182, うん 134, ありがとう 59. The notice (おや……？, ん？) comes first, the answer after it. | hers | firm | all | measured | {"source":"voice.channels.her_dialogue.top_tokens","token_ああ":182,"token_ありがとう":59,"token_うん":134,"token_おや":50,"token_ふふ":107,"t… |
| Name him 一悟くん (146) or 一悟 (103) and call the people she likes by name with a suffix: 真優ちゃん 19, 千奈ちゃん 14; bare 百花 12, 真里亜 11; ケルベロス 16 and ケル 16. The room calls her アリス 80, アリス様 41, アリスさん 16. | hers | firm | all | measured | {"her_address_terms_overall":{"ケル":16,"ケルベロス":16,"一悟":103,"一悟くん":146,"十川":1,"十川真優":1,"千奈ちゃん":14,"小野坂くん":3,"百花":12,"真優":2,"真優ちゃん":… |

Rule split: class {'author': 4, 'hers': 20, 'moment': 4}; tier {'firm': 23, 'thin': 4, 'weak': 1}; register {'H': 1, 'all': 11, 'non-H': 8, 'per-register': 8}; evidence {'inferred': 3, 'measured': 25}. Unreceipted rules: none.

## Rhetorical mechanisms (B3)

These are the recurring moves in her speech that carry no `@emotion` / `@face` / `@action` - the B2 residue. They are **this builder's reading**, not the author's: the definitions, the class and the tier are interpretive; the line counts come from the fixed matcher named in each `method`, and the receipts are real lines. The surface rules they lean on are measured separately in `speech_guide` and `voice.surface`; this section adds the move, not the mark. A regex count is a lower bound where the move is defined by reading.

| mechanism | class | tier | confidence | lines | non-H / H | control rate | distinctive | receipts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Asks in the soft masculine form, かい / んだい | hers | firm | high | 137 | 124 / 13 | 0.0003 | True | 01_01:1117, 01_01:1265 |
| Turns a statement into a half-question with かな | hers | firm | high | 133 | 113 / 20 | 0.0062 | True | 01_01:1070, 01_01:1144 |
| Checks agreement with だろう / じゃないか | hers | thin | high | 73 | 70 / 3 | 0.0007 | True | 01_01:1193, 01_01:4509 |
| Opens on a noticing interjection | hers | firm | high | 103 | 99 / 4 | 0.0016 | True | 01_01:0952, 01_01:1117 |
| Laughs in words at the start of a turn | hers | firm | high | 154 | 136 / 18 | 0.0173 | True | 01_01:1050, 01_01:1144 |
| Thanks and apologises in courteous set phrases | hers | weak | high | 145 | 120 / 25 | 0.0339 | False | 01_01:1144, 01_01:1429 |
| Asks by a soft command, てくれ / たまえ | hers | firm | medium | 171 | 132 / 39 | 0.0281 | True | 01_01:1516, 01_01:4509 |
| Concedes, then turns on けれど / のだが | hers | firm | medium | 135 | 122 / 13 | 0.0162 | True | 01_01:1070, 01_01:1381 |
| Addresses people by name with a suffix, or as 君 | hers | firm | high | 558 | 439 / 119 | 0.0298 | True | 01_01:0967, 01_01:1050 |
| Speaks as the student council president | hers | weak | medium | 107 | 102 / 5 | 0.0291 | False | 01_01:1254, 01_01:1265 |
| Cites what is said or known to back the point | hers | weak | low | 35 | 25 / 10 | 0.0095 | False | 01_01:4963, 02_01:2574 |
| Teases by remarking on his reaction | hers | weak | medium | 41 | 37 / 4 | 0.008 | False | 01_01:1050, 01_01:1070 |
| Breaks into a stammer when flustered | hers | firm | low | 172 | 69 / 103 | 0.0643 | True | 02_01:1261, 02_01:1629 |
| Closes by proposing the next step together | hers | weak | medium | 27 | 26 / 1 | 0.0062 | False | 02_01:3704, 04_01:0288 |
| Praises him in a measured register | hers | weak | medium | 40 | 35 / 5 | 0.012 | False | 01_01:1277, 02_01:2953 |
| Closes on a stiff declarative, のだ / だな / だぞ | hers | thin | medium | 16 | 16 / 0 | 0.0 | True | 02_01:1310, 02_01:1444 |
| Treats the dog Kerberos as a partner | hers | weak | medium | 63 | 63 / 0 | 0.0032 | False | 01_01:1444, 01_01:1479 |

Mechanism split: class {'hers': 17}; tier {'firm': 8, 'thin': 2, 'weak': 7} (8 firm, 2 thin, 7 weak) over 2792 spoken lines.

Non-distinctive from the control heroines: thanks_and_apologises_courteously, speaks_as_the_office, cites_hearsay_or_proverb, teases_by_noticing_his_reaction, proposes_a_joint_move, praises_in_a_formal_register, treats_the_dog_as_partner.

These 17 mechanisms are the tools/koikano/b3/alice.py reading, made from her own lines and not from 百花's list. Every one is classed hers by the builder's reading; the gate holdout decides distinctive. 10 are above the control rate there, 7 are not (thanks_and_apologises_courteously, speaks_as_the_office, cites_hearsay_or_proverb, teases_by_noticing_his_reaction, proposes_a_joint_move, praises_in_a_formal_register, treats_the_dog_as_partner). The marginal ones are in their rows.

How each was counted, and the weak ones:

- **Asks in the soft masculine form, かい / んだい** (hers, firm, high, 137 line(s), share 0.0491; non-H 124 / H 13; control 0.0003, distinctive True): regex: かい or だい immediately before ？ (the 〜かい？ and 〜んだい？ endings). 137 lines (124 outside H, 13 inside), 0.0491 of her spoken lines; the other heroines in her scenes run 2 lines at 0.0003. Her holdout (late route-c block): 14 of 396 against 0 of 157 for the control. Her ordinary way to ask. The form is plain in her lines, e.g. 01_01:1117 and 01_01:1240.
- **Turns a statement into a half-question with かな** (hers, firm, high, 133 line(s), share 0.0476; non-H 113 / H 20; control 0.0062, distinctive True): regex: かな at the end of the line (before closing punctuation). 133 lines (113 outside H, 20 inside), 0.0476 of her spoken lines; the other heroines in her scenes run 43 lines at 0.0062. Her holdout (late route-c block): 9 of 396 against 0 of 157 for the control. Different from the かも-hedge: かな is addressed to him, a request for his view.
- **Checks agreement with だろう / じゃないか** (hers, thin, high, 73 line(s), share 0.0261; non-H 70 / H 3; control 0.0007, distinctive True): regex: だろう, だろうか, じゃないか, ではないか or ないか at the end of the line. 73 lines (70 outside H, 3 inside), 0.0261 of her spoken lines; the other heroines in her scenes run 5 lines at 0.0007. Her holdout (late route-c block): 1 of 396 against 0 of 157 for the control. The president's tag question. She uses it to lead him to the answer she already has.
- **Opens on a noticing interjection** (hers, firm, high, 103 line(s), share 0.0369; non-H 99 / H 4; control 0.0016, distinctive True): regex: the line starts with おや, ほう, ふむ, やあ, はて, いやはや or いやいや. 103 lines (99 outside H, 4 inside), 0.0369 of her spoken lines; the other heroines in her scenes run 11 lines at 0.0016. Her holdout (late route-c block): 5 of 396 against 0 of 157 for the control. The notice comes first and the answer after it.
- **Laughs in words at the start of a turn** (hers, firm, high, 154 line(s), share 0.0552; non-H 136 / H 18; control 0.0173, distinctive True): regex: the line starts with ふふ, ふっ, はは, あはは or くす. 154 lines (136 outside H, 18 inside), 0.0552 of her spoken lines; the other heroines in her scenes run 121 lines at 0.0173. Her holdout (late route-c block): 11 of 396 against 3 of 157 for the control. Not the H-scene sounds; those start with はぁ / ぁ and are not matched.
- **Thanks and apologises in courteous set phrases** (hers, weak, high, 145 line(s), share 0.0519; non-H 120 / H 25; control 0.0339, distinctive False): regex: ありがとう, すまな-, 悪いね, 悪いな, ごめん, 失礼, 詫び or 申し訳. 145 lines (120 outside H, 25 inside), 0.0519 of her spoken lines; the other heroines in her scenes run 237 lines at 0.0339. Her holdout (late route-c block): 14 of 396 against 9 of 157 for the control. The set phrases carry the courtesy; none of them is childlike.
- **Asks by a soft command, てくれ / たまえ** (hers, firm, medium, 171 line(s), share 0.0612; non-H 132 / H 39; control 0.0281, distinctive True): regex: てくれ (not てくれる), たまえ, てもらえる / てもらえない, 頼む, てほしい or てくれないか. 171 lines (132 outside H, 39 inside), 0.0612 of her spoken lines; the other heroines in her scenes run 196 lines at 0.0281. Her holdout (late route-c block): 16 of 396 against 5 of 157 for the control. She asks as one who is used to being obeyed and says please by tone, not by pleading.
- **Concedes, then turns on けれど / のだが** (hers, firm, medium, 135 line(s), share 0.0484; non-H 122 / H 13; control 0.0162, distinctive True): regex: けれど, けれども, のだが, んだが, だが or ですが anywhere in the line. 135 lines (122 outside H, 13 inside), 0.0484 of her spoken lines; the other heroines in her scenes run 113 lines at 0.0162. Her holdout (late route-c block): 8 of 396 against 3 of 157 for the control. Shows as 〜のだけれど、 and 〜んだが……; the pause after it is hers (see the ellipsis rule).
- **Addresses people by name with a suffix, or as 君** (hers, firm, high, 558 line(s), share 0.1999; non-H 439 / H 119; control 0.0298, distinctive True): regex: 一悟くん, 真優ちゃん, 千奈ちゃん or 君 in the line. 558 lines (439 outside H, 119 inside), 0.1999 of her spoken lines; the other heroines in her scenes run 208 lines at 0.0298. Her holdout (late route-c block): 47 of 396 against 3 of 157 for the control. The address table has the counts; this is the mechanism that carries the intimacy into a line.
- **Speaks as the student council president** (hers, weak, medium, 107 line(s), share 0.0383; non-H 102 / H 5; control 0.0291, distinctive False): regex: 生徒会, 我々, 諸君, 予算, 部活動, 責任, 文化祭 or 会長 in the line. 107 lines (102 outside H, 5 inside), 0.0383 of her spoken lines; the other heroines in her scenes run 203 lines at 0.0291. Her holdout (late route-c block): 8 of 396 against 10 of 157 for the control. Frame vocabulary of the role; the topic is the school, the move is deciding from the chair.
- **Cites what is said or known to back the point** (hers, weak, low, 35 line(s), share 0.0125; non-H 25 / H 10; control 0.0095, distinctive False): regex: というじゃないか, と聞く, と聞いて, とは言う, らしい, と言われ, というもの or という話. 35 lines (25 outside H, 10 inside), 0.0125 of her spoken lines; the other heroines in her scenes run 66 lines at 0.0095. Her holdout (late route-c block): 1 of 396 against 2 of 157 for the control. She argues by what is generally said (お菓子は別腹というじゃないか, 02_01:2574).
- **Teases by remarking on his reaction** (hers, weak, medium, 41 line(s), share 0.0147; non-H 37 / H 4; control 0.008, distinctive False): regex: 顔を赤, 照れ, 視線, 気のせい, 可愛い, 意地悪, 妬け, からか or 赤くし. 41 lines (37 outside H, 4 inside), 0.0147 of her spoken lines; the other heroines in her scenes run 56 lines at 0.008. Her holdout (late route-c block): 1 of 396 against 1 of 157 for the control. The tease is the question that names his face (01_01:1050).
- **Breaks into a stammer when flustered** (hers, firm, low, 172 line(s), share 0.0616; non-H 69 / H 103; control 0.0643, distinctive True): regex: the line starts with あっ, えっ, わあ, ふあっ or っ, or with a single kana and 、, or has その…. 172 lines (69 outside H, 103 inside), 0.0616 of her spoken lines; the other heroines in her scenes run 449 lines at 0.0643. Her holdout (late route-c block): 30 of 396 against 4 of 157 for the control. The break is the contrast with her usual composure; it fires when he says something direct.
- **Closes by proposing the next step together** (hers, weak, medium, 27 line(s), share 0.0097; non-H 26 / H 1; control 0.0062, distinctive False): regex: しよう, いこう, ましょう, ようか, こうか or 始めよう / 行こう at the end of the line. 27 lines (26 outside H, 1 inside), 0.0097 of her spoken lines; the other heroines in her scenes run 43 lines at 0.0062. Her holdout (late route-c block): 0 of 396 against 0 of 157 for the control. The chair moves the meeting on and takes him with her.
- **Praises him in a measured register** (hers, weak, medium, 40 line(s), share 0.0143; non-H 35 / H 5; control 0.012, distinctive False): regex: さすが, 頼もしい, 感心, 素晴らしい, 見事, 上手, たいした or えらい. 40 lines (35 outside H, 5 inside), 0.0143 of her spoken lines; the other heroines in her scenes run 84 lines at 0.012. Her holdout (late route-c block): 1 of 396 against 2 of 157 for the control. Praise comes as an assessment from above, warm but measured.
- **Closes on a stiff declarative, のだ / だな / だぞ** (hers, thin, medium, 16 line(s), share 0.0057; non-H 16 / H 0; control 0.0, distinctive True): regex: のだ, ものだ, だな, だぞ, であろう, なかろう or だとも at the end of the line. 16 lines (16 outside H, 0 inside), 0.0057 of her spoken lines; the other heroines in her scenes run 0 lines at 0.0. Her holdout (late route-c block): 2 of 396 against 0 of 157 for the control. Her stiff mode, used for announcements and for the dog.
- **Treats the dog Kerberos as a partner** (hers, weak, medium, 63 line(s), share 0.0226; non-H 63 / H 0; control 0.0032, distinctive False): regex: 相棒, ケルベロス or ケルベロ in the line. 63 lines (63 outside H, 0 inside), 0.0226 of her spoken lines; the other heroines in her scenes run 22 lines at 0.0032. Her holdout (late route-c block): 2 of 396 against 2 of 157 for the control. A recurring beat of her scenes; the 相棒 form is hers (01_01:1505, 09_01:5171).

## Bounds and the absent list

Emotional pressures (authored `@emotion` types): {'キラン': 5, '汗': 3, 'びっくり': 1, 'びっくりF': 1, 'キラキラ': 1, 'ハート01': 1}.

- expression vocabulary never on her lines: laugh, angry, cry, blush, embarrassed, shy, other
- gesture macros in the corpus never hers: @なでなで, @ひざまずき, @噴飯１, @外から飛び出し, @居眠り横, @居眠り縦, @身体眺め
- on-screen cast absent from her scenes: none

### What B2 could not derive (the B3 residue)

- address terms for NPCs: Not derivable. The NPC speakers are not in charData.csv, so there is no name form to search her lines for. Only the eight named cast and the protagonist 一悟 have alias forms.
- relationships with no address term: 知紗, 天文部部員, 女子生徒, 一年生女子, 新聞部部長, 文化祭実行委員, テニス部部員, 弱小部女子生徒Ｂ, 三年生女子, 映画研究部部長, 野球部部員, 真優＆千奈
- rhetorical mechanisms deferred to B3: This list is the B2 residue, kept for provenance. B3 addressed it: see the `mechanisms` section. The B2 residue named deflects a topic, changes the subject, teases, jokes, stalls with repetition, or answers a question with a question - none of these carries an authored stage direction.
- trigger causality: Every trigger table is co-occurrence over her lines, not cause. The authored direction is a staging choice on the line; it does not say why.
- expression-label uncertainty: Expression triggers inherit the C4 hypothesis: a label on a line is the merged visual/context guess, not ground truth.
- tokenizer: The surface battery splits on punctuation (a class-based tokenizer), not morphology, so particles are matched by string suffix against a fixed list and the n-grams are character n-grams.
- room definition: The room is every other speaker in her scenes, named cast and NPCs together; the plan leaves this open.

## Spot check: one line carried through the layers

`01_01:1181` (scene 01_01, route common, channel spoken):

> 「おやおや、誰にでもなんてことはないよ？」

```json
{
  "expressions": [
    {
      "witness": "message_face",
      "id": "CC02A012",
      "unit": "CC|A|012",
      "expression": "excited",
      "pose": "none",
      "source": "context",
      "hypothesis": {
        "confidence": "explicit",
        "agreement": "disputed",
        "winner": "context",
        "version": "0.2",
        "provenance": {
          "visual": {
            "label": "laugh",
            "confidence": "clear",
            "image": "png/parts/face/cc01a012F.png",
            "note": "closed-eye open smile; キラン/キラキラ"
          },
          "context": {
            "label": "excited",
            "confidence": "explicit",
            "receipt": "01_01:1050",
            "note": "anchors: キラン x2, キラキラ x2, びっくりF x1, 汗 x1"
          }
        }
      }
    },
    {
      "witness": "sprite",
      "id": "CC02A016M",
      "unit": "CC|A|016",
      "expression": "talk",
      "pose": "none",
      "source": "visual",
      "hypothesis": {
        "confidence": "ambiguous",
        "agreement": "disputed",
        "winner": "vision",
        "version": "0.2",
        "provenance": {
          "visual": {
            "label": "talk",
            "confidence": "ambiguous",
            "image": "png/parts/face/cc01a016F.png",
            "note": "closed eyes, open mouth",
            "alternative": "smile"
          },
          "context": {
            "label": "neutral",
            "confidence": "inferred",
            "receipt": "01_01:1117",
            "note": "anchors: 汗 x2"
          }
        }
      }
    }
  ],
  "actions": [
    {
      "kind": "action",
      "command": "@char",
      "args": {
        "file": "CC02A016M"
      },
      "macro": null,
      "event_line": 1178,
      "conditional": false
    },
    {
      "kind": "gesture",
      "command": "@否定",
      "args": {
        "id": "アリス",
        "action": "ActionAdvWave",
        "width": "5",
        "height": "0",
        "cycle": "500",
        "count": "1"
      },
      "macro": "否定",
      "event_line": 1179,
      "conditional": false
    }
  ],
  "interlocutor": "真優"
}
```

This line is in `slice.json` (`her_line_ids`), its face and gesture are in `annotations.json` (`per_line`), and the gesture is in `gestures` in `bible.json`.

## Provenance

Inputs: game_logic.jsonl (37913 records), character_actions.jsonl (16732), expression_labels_lines.jsonl (20509), timing_table.jsonl (37795), expression_labels.json (915 labels), bgm_scene_table.json, charData.csv, data\scenario\*.ks.

Mechanical here: slice, battery, bounds, context, annotations, interactions, the B2 voice surface, the expression and gesture triggers, and the speech guide. B3 added `mechanisms`, a reading by the builder (no API call): the moves are interpretive, their counts are mechanical. Deferred to a model: the fidelity gate (B4). The expression labels are the C4 hypothesis layer, vocabulary version 0.2, and are presented as hypotheses with their confidence.

Corrections: B1 read the alias table from charData.csv, which omits the protagonist 一悟; B2 adds him for the address-term derivation in this bible only. B3 is a reading, not a measurement: the mechanism list is this builder's judgement of what shapes her speech, so class and tier are interpretive even where the count is mechanical. The B2 residue named 'deflects a topic, changes the subject, teases, jokes, stalls with repetition, or answers a question with a question'; those are covered by `doubles_a_key_word`, `closes_a_turn_with_a_short_question`, `names_a_blow_with_a_loanword` and `plays_a_role_with_stock_catchphrases`.
