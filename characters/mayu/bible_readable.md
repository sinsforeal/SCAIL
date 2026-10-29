# koikano authored expression bible - 真優 (CA)

Date: 2026-09-16. Build: b0-b3/1 (authored-expression-bible/1). Phases B0+B1+B2+B3. B0-B2 are mechanical (no model spend, standard library); B3 is the builder's reading of the rhetorical moves, recorded in `mechanisms`. Route a. Source: `F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work\game_logic.jsonl` joined to the authored stage directions.

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
| her lines | 3826 |
| - spoken | 3546 |
| - inner voice | 280 |
| her scenes | 78 |
| room lines (others in her scenes) | 24320 |
| - room spoken | 13497 |
| - room inner | 10823 |

The scope's section 5.1 figure for 真優 is 2,781 lines, 211 inner and 70 scenes. This build reproduces all three.

## Voice: her dialogue, her inner voice, the room

`dispersion` is scene document frequency: the share of her scenes in which the n-gram appears. `distinctive` is the log-odds of the channel against the other two channels pooled.

| channel | lines | tokens | token types | TTR |
| --- | --- | --- | --- | --- |
| her dialogue | 3546 | 13643 | 7603 | 0.5573 |
| her inner voice | 280 | 591 | 572 | 0.9679 |
| the room (spoken) | 13497 | 35241 | 20538 | 0.5828 |

Distinctive tokens (log-odds, top 12):

- **her_dialogue**: あんっ (60), おちんちん (43), れるっ (32), えへへぇ (28), んちゅっ (26), わたしも (22), あはっ (17), 一悟ぉ (15), ああぁっ (13), んくっ (38), ちゅぷっ (12), むぅぅ (12)
- **her_inner**: ご褒美 (2), 夏休みや冬休みに (2), 榎本先生って (2), ――って (1), ――でも (1), ある日一悟が (1), あんなに苦しんでるのは (1), いい人だけど (1), いっぱい褒めてくれて (1), いつからなんだろう (1), いつもならすぐ振り払うけど (1), いつもなら日付が変わる頃までごろごろしながら一緒にいてくれるのに (1)
- **the_room**: 真優 (225), 百花 (145), ありがとうございます (140), そうですね (118), いえ (98), そうだな (96), そうか (90), お嬢様 (85), おおー (76), 宮国様 (64), 真優ちゃん (63), わんっ (62)

### B2 surface: turn length, line-final, punctuation, self-reference

Turn length, kept characters per line (shares are in `bible.json`):

| channel | 1-5 | 6-10 | 11-20 | 21-40 | 41-80 | 81+ | mean | median | p90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| her_spoken | 274 | 330 | 825 | 1881 | 206 | 0 | 23.4 | 24 | 38 |
| her_inner | 8 | 21 | 88 | 143 | 19 | 0 | 23.33 | 23 | 39 |
| the_room_spoken | 1595 | 1722 | 3829 | 5232 | 925 | 0 | 20.15 | 19 | 38 |

Line-final morphemes, string suffixes of the kept text (top 10):

- **her spoken last token**: っ 63, 一悟 63, んんっ 29, んっ 27, ありがと 18, ちゅっ 17, ああっ 14, あっ 12, 千奈 12, え 10
- **her spoken 2-char suffix**: だよ 155, から 140, もん 132, んっ 104, しょ 77, 一悟 68, ぁっ 63, って 62, いよ 61, よね 61
- **her inner last token**: かな 3, ――って 1, あとは 1, いい人だけど 1, いつかは 1, うまくいかない 1, うん 1, お昼休みも一緒にいてくれなかった 1, か 1, かける言葉もないんだろうな 1
- **her inner 2-char suffix**: った 42, ない 17, けど 11, いた 9, から 9, する 9, れる 7, かな 6, いる 5, くる 5

Line-final particles, matched by suffix against a fixed list (top 10 by spoken lines):

| ending | spoken lines | spoken share | inner lines | inner share |
| --- | --- | --- | --- | --- |
| っ | 619 | 0.1746 | 0 | 0.0 |
| よ | 331 | 0.0933 | 2 | 0.0071 |
| ね | 265 | 0.0747 | 1 | 0.0036 |
| ん | 197 | 0.0556 | 6 | 0.0214 |
| の | 194 | 0.0547 | 1 | 0.0036 |
| だよ | 155 | 0.0437 | 0 | 0.0 |
| から | 140 | 0.0395 | 9 | 0.0321 |
| でしょ | 76 | 0.0214 | 0 | 0.0 |
| よね | 61 | 0.0172 | 0 | 0.0 |
| ー | 54 | 0.0152 | 0 | 0.0 |

Punctuation, full-width marks:

| mark | spoken count | spoken/line | inner count | room/line |
| --- | --- | --- | --- | --- |
| … | 8089 | 2.2812 | 72 | 0.8798 |
| ！ | 1409 | 0.3973 | 4 | 0.1134 |
| ？ | 1083 | 0.3054 | 10 | 0.2731 |
| 、 | 5743 | 1.6196 | 266 | 0.9435 |
| 。 | 780 | 0.22 | 264 | 0.3618 |
| ー | 628 | 0.1771 | 19 | 0.1345 |
| ～ | 30 | 0.0085 | 0 | 0.0042 |
| 「 | 3533 | 0.9963 | 0 | 0.9961 |

Self-reference: spoken 真優 10 occurrences on 9 lines; spoken 私 24 occurrence(s) on 22 line(s); inner 真優 1 occurrence(s) on 1 line(s).

- **her dialogue vs the room, tokens**: あんっ (60), おちんちん (43), れるっ (32), えへへぇ (28), んちゅっ (26), わたしも (22), あはっ (17), わたしは (17), 一悟ぉ (15), ああぁっ (13)
- **her dialogue vs the room, bigrams**: おち (121), ゅく (49), っれ (45), ゅぢ (28), よぉ (84), だぁ (26), るぅ (26), ぢゅ (116)
- **her dialogue vs her inner, tokens**: んっ (309), 一悟 (226), あっ (219), はぁ (176), んんっ (155), ん (123), えへへ (115), ああっ (112), っ (100), はぁっ (99)
- **her dialogue vs her inner, bigrams**: んっ (809), ああ (616), っあ (551), っん (476), はぁ (403), ちゅ (396), ぁぁ (375), ぁっ (346)

## Expressions (C4 hypotheses)

The repertoire is her own faces only (message face or sprite tag carrying the `CA` prefix). Confidence is carried from `expression_labels.json`.

| expression | her lines | confidence split |
| --- | --- | --- |
| smile | 618 | {'clear': 618} |
| sad | 532 | {'ambiguous': 532} |
| surprise | 375 | {'clear': 375} |
| neutral | 317 | {'clear': 317} |
| laugh | 194 | {'clear': 194} |
| worried | 192 | {'inferred': 192} |
| angry | 191 | {'explicit': 191} |
| excited | 188 | {'explicit': 181, 'clear': 7} |
| talk | 108 | {'ambiguous': 108} |

### Expression triggers (all eight labels)

One row per label. `lines` is her lines carrying it (a line with two faces counts once here; the repertoire counts occurrences). `with` is the speaker whose turn preceded hers; `(none)` is a scene-opening or unattributed turn. `preceded by` is the last expression she wore earlier in the scene; `co-gesture` is the gesture on the same line. Co-occurrence, not cause.

| expression | lines | with | route | H/normal | mean chars | preceded by | co-gesture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smile | 564 | 一悟 379, 真優 61, 千奈 41 | a 270, common 205, c 42 | H 2, normal 562 | 22.33 | smile 333, neutral 46, sad 41 | @おじぎ 51, @ううっ 26, @否定 23 |
| sad | 494 | 一悟 276, 千奈 72, 百花 33 | a 172, common 166, c 68 | normal 494 | 20.96 | sad 214, surprise 83, smile 56 | @ううっ 84, @おじぎ 45, @否定 44 |
| surprise | 358 | 一悟 175, 千奈 57, 百花 34 | common 161, a 80, c 56 | normal 358 | 19.71 | surprise 127, sad 79, neutral 30 | @ジャンプ 119, @ううっ 49, @否定 23 |
| neutral | 310 | 一悟 176, 千奈 40, 百花 29 | a 131, common 88, c 44 | H 1, normal 309 | 18.05 | neutral 101, smile 53, sad 48 | @ううっ 16, @ジャンプ 16, @おじぎ 15 |
| laugh | 190 | 一悟 152, 千奈 10, アリス 7 | a 118, common 46, b 11 | H 1, normal 189 | 21.58 | laugh 61, smile 49, sad 22 | @ジャンプ 30, @ううっ 29, @おじぎ 29 |
| worried | 190 | 一悟 129, 真優 17, 千奈 14 | a 105, common 53, c 20 | normal 190 | 19.96 | worried 67, sad 34, smile 28 | @ううっ 22, @おじぎ 12, @否定 11 |
| angry | 188 | 一悟 126, 百花 17, 千奈 16 | common 62, a 61, d 31 | normal 188 | 21.46 | sad 35, smile 34, angry 31 | @おじぎ 13, @ううっ 10, @ジャンプ 9 |
| excited | 185 | 一悟 130, 千奈 28, 百花 11 | a 104, common 44, b 16 | normal 185 | 24.64 | excited 68, smile 35, sad 23 | @おじぎ 28, @ジャンプ 19, @ううっ 10 |
| talk | 108 | 一悟 79, 千奈 14, 百花 7 | a 49, common 37, b 11 | H 5, normal 103 | 23.06 | smile 21, excited 20, talk 13 | @ジャンプ 12, @おじぎ 9, @否定 6 |

## Gestures

| gesture | her lines |
| --- | --- |
| @ジャンプ | 293 |
| @ううっ | 267 |
| @おじぎ | 209 |
| @否定 | 155 |
| @キス | 27 |
| @噴飯２ | 18 |
| @キス止め | 10 |
| @抱きつき | 9 |
| @居眠り横 | 8 |
| @息切れ | 3 |
| @なでなで | 2 |
| @噴飯１ | 2 |
| @外から飛び出し | 2 |
| @居眠り縦 | 2 |
| @ひざまずき | 1 |
| @身体眺め | 1 |

Entry/exit: {'enter': 18, 'exit': 3}. Camera (targeted): {'@focus': 13}. Emotion overlays: {'汗': 8, 'ハート02': 6, 'ぽわぽわ': 3, 'キラン': 2, 'はてな': 1, 'びっくり': 1, 'キラキラ': 1, 'ハート01': 1}. Action commands (occurrences): {'@char': 2365, '@focus': 42, '@action': 21, '@move': 11, '@stopAction': 8}.

### Gesture triggers

One row per gesture. `co-face` is the C4 label on the same line; `preceded by` is the last label earlier in the scene; the other columns as above.

| gesture | lines | with | route | H/normal | mean chars | co-face | preceded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| @ジャンプ | 293 | 一悟 156, 千奈 54, 真里亜 28 | common 112, a 73, b 54 | H 1, normal 292 | 21.29 | surprise 129, sad 48, laugh 31 | (scene-start) 86, sad 65, surprise 41 |
| @ううっ | 267 | 一悟 149, 千奈 36, 百花 35 | a 91, common 88, c 34 | H 1, normal 266 | 18.5 | sad 92, surprise 50, smile 31 | (scene-start) 74, sad 44, surprise 44 |
| @おじぎ | 209 | 一悟 145, 千奈 32, アリス 12 | a 89, common 67, c 22 | H 1, normal 208 | 18.5 | smile 56, sad 50, excited 30 | (scene-start) 58, sad 32, smile 31 |
| @否定 | 155 | 一悟 92, 百花 19, 千奈 17 | common 58, a 49, b 21 | H 2, normal 153 | 22.88 | sad 47, smile 26, surprise 23 | (scene-start) 49, surprise 26, sad 24 |
| @キス | 14 | 一悟 14 | a 12, common 2 | H 1, normal 13 | 18.07 | laugh 3, angry 2, excited 2 | (scene-start) 7, excited 2, laugh 2 |
| @噴飯２ | 18 | 一悟 8, 千奈 3, 百花 3 | common 8, b 4, c 4 | normal 18 | 13.67 | surprise 15, neutral 2, laugh 1 | surprise 6, angry 3, (scene-start) 2 |
| @キス止め | 5 | 一悟 5 | a 5 | normal 5 | 27.8 | laugh 2, excited 1 | (scene-start) 3, excited 1, laugh 1 |
| @抱きつき | 9 | 一悟 7, アリス 1, 百花 1 | common 7, a 2 | normal 9 | 8.11 | smile 2, excited 1, talk 1 | (scene-start) 3, neutral 2, talk 2 |
| @居眠り横 | 8 | 一悟 7, アリス 1 | a 4, c 3, common 1 | normal 8 | 11.88 | smile 5, sad 4, excited 1 | smile 3, (scene-start) 2, sad 2 |
| @息切れ | 3 | 一悟 2, ケルベロス 1 | a 2, c 1 | normal 3 | 20.33 | sad 2, angry 1 | sad 2, laugh 1 |
| @なでなで | 2 | 一悟 2 | a 1, b 1 | normal 2 | 14.0 | neutral 1, surprise 1 | angry 1, surprise 1 |
| @噴飯１ | 1 | 真里亜 1 | common 1 | normal 1 | 3.0 | - | smile 1 |
| @外から飛び出し | 1 | 一悟 1 | c 1 | normal 1 | 11.0 | neutral 1 | neutral 1 |
| @居眠り縦 | 2 | 一悟 2 | common 2 | normal 2 | 8.5 | sad 1, smile 1 | sad 1, worried 1 |
| @ひざまずき | 1 | 真里亜 1 | common 1 | normal 1 | 8.0 | worried 1 | neutral 1 |
| @身体眺め | 1 | アリス 1 | common 1 | normal 1 | 5.0 | surprise 1 | surprise 1 |

### Emotion, entry/exit and action triggers

| trigger | lines | with | H/normal | co-face |
| --- | --- | --- | --- | --- |
| emotion 汗 (lines) | 8 | 一悟 3, 百花 2 | normal 8 | sad 3, talk 2 |
| emotion ハート02 (lines) | 6 | 一悟 4, 千奈 2 | normal 6 | excited 1, laugh 1 |
| emotion ぽわぽわ (lines) | 3 | アリス 1, 一悟 1 | normal 3 | laugh 4, neutral 1 |
| emotion キラン (lines) | 2 | 一悟 1, 千奈 1 | normal 2 | excited 2 |
| emotion はてな (lines) | 1 | 千奈 1 | normal 1 | neutral 1 |
| emotion びっくり (lines) | 1 | 千奈 1 | normal 1 | surprise 2 |
| emotion キラキラ (lines) | 1 | 一悟 1 | normal 1 | - |
| emotion ハート01 (lines) | 1 | 一悟 1 | normal 1 | smile 2 |
| enter/exit enter (lines) | 18 | 一悟 14, 百花 2 | normal 18 | excited 4, neutral 4 |
| enter/exit exit (lines) | 3 | 千奈 1, 百花 1 | normal 3 | - |
| action @char (lines) | 2054 | 一悟 1228, 千奈 317 | H 9, normal 2045 | sad 438, smile 434 |
| action @focus (lines) | 13 | アリス 4, 一悟 4 | normal 13 | worried 5, sad 4 |
| action @action (lines) | 15 | 知紗 5, 一悟 3 | normal 15 | laugh 4, smile 3 |
| action @move (lines) | 7 | 千奈 4, 百花 2 | normal 7 | surprise 4, sad 1 |

## Interactions (per relationship)

| speaker | kind | turns | spoken | inner | scenes | her turns | her avg chars | her med chars | exch. her-start | exch. their-start | her expression mix | her gestures | her address |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 一悟 | protagonist | 16232 | 6013 | 10219 | 77 | 2596 | 24.77 | 27 | 16 | 466 | smile 426, sad 300, surprise 184, neutral 181 | @ジャンプ 156, @ううっ 149, @おじぎ 145 | 一悟 725, 一悟くん 1 |
| 千奈 | heroine | 2663 | 2263 | 400 | 62 | 352 | 22.02 | 22 | 1 | 107 | sad 84, surprise 61, neutral 42, smile 41 | @ジャンプ 54, @ううっ 36, @おじぎ 32 | 千奈 68 |
| アリス | heroine | 1758 | 1719 | 39 | 51 | 135 | 16.48 | 15 | 0 | 129 | sad 28, surprise 27, smile 23, neutral 22 | @ジャンプ 18, @ううっ 15, @おじぎ 12 | アリス 7, メイシー 1 |
| 百花 | heroine | 1660 | 1496 | 164 | 58 | 203 | 19.43 | 18 | 0 | 64 | surprise 36, sad 34, neutral 29, smile 20 | @ううっ 35, @ジャンプ 26, @否定 19 | 百花ちゃん 23 |
| 真里亜 | heroine | 889 | 889 | 0 | 59 | 109 | 19.08 | 18 | 0 | 5 | surprise 30, sad 28, neutral 13, angry 10 | @ジャンプ 28, @ううっ 12, @おじぎ 6 | 真里亜さん 3 |
| ひかる | heroine | 410 | 410 | 0 | 37 | 12 | 9.75 | 6 | 0 | 24 | surprise 7, smile 1, talk 1 | @ジャンプ 3, @ううっ 2, @おじぎ 1 | - |
| 知紗 | heroine | 381 | 381 | 0 | 35 | 63 | 19.75 | 21 | 0 | 6 | sad 18, neutral 11, surprise 10, worried 10 | @否定 10, @ううっ 5, @ジャンプ 5 | 榎本先生 11 |
| ケルベロス | heroine | 155 | 155 | 0 | 31 | 25 | 15.72 | 16 | 0 | 12 | surprise 10, neutral 6, sad 3, angry 2 | @ううっ 6, @ジャンプ 2, @おじぎ 1 | ケル 5, ケルベロス 5 |
| 天文部部員 | npc | 30 | 30 | 0 | 5 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 事務所の社長さん | npc | 9 | 9 | 0 | 2 | 10 | 19.6 | 18 | 0 | 0 | smile 17, sad 3, worried 2, angry 1 | @ううっ 1, @否定 1 | - |
| 十川家の母 | npc | 9 | 9 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| ＡＶ女優 | npc | 9 | 9 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 一年生女子 | npc | 8 | 8 | 0 | 3 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 十川家の父 | npc | 8 | 8 | 0 | 1 | 4 | 23.75 | 26 | 0 | 0 | smile 5, excited 1, laugh 1, talk 1 | @おじぎ 1 | - |
| 新聞部部長 | npc | 8 | 8 | 0 | 3 | 1 | 5.0 | 5 | 0 | 0 | sad 1 | @ううっ 1 | - |
| 案内アナウンス | npc | 8 | 8 | 0 | 3 | 3 | 33.33 | 32 | 0 | 0 | - | - | - |
| 芸能記者 | npc | 8 | 8 | 0 | 3 | 6 | 14.67 | 10 | 0 | 0 | laugh 3, neutral 1, sad 1, smile 1 | @ううっ 1 | - |
| 芸能レポーター | npc | 7 | 7 | 0 | 2 | 1 | 10.0 | 10 | 0 | 0 | sad 1, smile 1 | - | - |
| 野村先生 | npc | 7 | 7 | 0 | 3 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 文化祭実行委員 | npc | 6 | 6 | 0 | 3 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 見知らぬ女性Ａ | npc | 6 | 6 | 0 | 3 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 見知らぬ女性Ｂ | npc | 6 | 6 | 0 | 3 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| テニス部部員 | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 弱小部女子生徒Ａ | npc | 5 | 5 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 弱小部女子生徒Ｂ | npc | 5 | 5 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 三年生女子 | npc | 3 | 3 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 女性のお客さんＢ | npc | 3 | 3 | 0 | 2 | 1 | 1.0 | 1 | 0 | 0 | laugh 1, sad 1 | @ううっ 1 | - |
| 映画研究部部長 | npc | 3 | 3 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 野球部部員 | npc | 3 | 3 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 女性のお客さんＡ | npc | 2 | 2 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 女性の店員さん | npc | 2 | 2 | 0 | 1 | 1 | 4.0 | 4 | 0 | 0 | laugh 1, surprise 1 | @ううっ 1 | - |
| 演劇部部員Ｂ | npc | 2 | 2 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 真優＆千奈 | unison | 2 | 2 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
|  | unattributed | 1 | 0 | 1 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 千奈＆アリス＆百花＆ひかる＆真里亜＆知紗 | unison | 1 | 1 | 0 | 1 | 1 | 24.0 | 24 | 0 | 0 | - | - | - |
| 演劇部部員Ａ | npc | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 演劇部部員Ｃ | npc | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 百花＆真里亜 | unison | 1 | 1 | 0 | 1 | 1 | 17.0 | 17 | 0 | 0 | - | @ううっ 1 | - |
| 真優＆千奈＆一悟 | unison | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 観客Ａ | npc | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 観客Ｂ | npc | 1 | 1 | 0 | 1 | 2 | 10.0 | 20 | 0 | 1 | - | - | - |

Scene openings across her scenes: 一悟 26, 真優 17, 百花 9, 千奈 8, アリス 7, ひかる 5, 案内アナウンス 2, ケルベロス 1, 真里亜 1, 芸能レポーター 1, 野村先生 1.

Reply vs initiation (her spoken turns): replies 2444, initiations 17, self-continuations 1085, reply rate 0.993.

### Address terms

How she names the other party, derived from her lines whose preceding speaker is that party. Overall: {"一悟":725,"千奈":68,"百花ちゃん":23,"榎本先生":11,"アリス":7,"ケル":5,"ケルベロス":5,"真里亜さん":3,"メイシー":1,"一悟くん":1}.

B1 built the alias table from charData.csv, which holds only the eight named cast. The protagonist 一悟 is absent, so B1 reported no address term for him; B2 adds 一悟 to the alias table here only. The interaction layer on disk is unchanged.

Relationships where no name term is derivable from her lines: ひかる, 事務所の社長さん, 十川家の父, 新聞部部長, 案内アナウンス, 芸能記者, 芸能レポーター, 女性のお客さんＢ, 女性の店員さん, 千奈＆アリス＆百花＆ひかる＆真里亜＆知紗, 百花＆真里亜, 観客Ｂ.

## Speech guide

Each rule carries a class (hers / the author's / a moment), a tier (firm / thin), a `register` (all / H / non-H / per-register) and an evidence flag (measured / inferred). The receipt is the count or the lines the rule comes from; the example lines are in `bible.json`. Rules whose value differs by register state both.

| rule | class | tier | register | evidence | receipt |
| --- | --- | --- | --- | --- | --- |
| Call yourself わたし: 617 times on 583 spoken lines (468 non-H, 115 H). 私 is the rare form (24 times on 22 lines) and your own name 真優 is said of yourself only 10 times on 9 lines, so you are not a third-person talker. Same in both registers. | hers | firm | all | measured | {"spoken_lines_with_わたし":583,"spoken_occurrences_わたし":617,"spoken_lines_with_私":22,"spoken_occurrences_私":24,"わたし_by_register":{"… |
| Keep turns short and let the register set the length: non-H median 20 kept characters (mean 20.9), H median 32 (mean 29.85); no line over 51 in either register (pooled median 24). | hers | firm | per-register | measured | {"non_H":{"lines":2555,"median_chars":20,"mean_chars":20.9,"max_chars":51},"H":{"lines":991,"median_chars":32,"mean_chars":29.85,… |
| Reply; do not open. 2444 of her turns answer someone and 17 open a scene (reply rate 0.9931). Once she has the floor she keeps it: 1085 more turns continue her own. | hers | firm | all | measured | {"reply":2444,"initiation":17,"self_continuation":1085,"reply_rate":0.9931} |
| End many lines on a glottal っ: 619 spoken lines (0.1746). In H it is 459 of 991 lines (moans, 0.4632); outside H it is 160 of 2555 lines. | hers | firm | per-register | measured | {"lines_ending_っ":619,"share_of_spoken":0.1746,"by_register":{"H":{"lines":459,"n":991},"non_H":{"lines":160,"n":2555}}} |
| Stretch the last syllable with ー only now and then: 54 spoken lines end on ー (0.0152), 52 of them outside H and 2 inside H. | hers | firm | non-H | measured | {"lines_ending_ー":54,"share_of_spoken":0.0152,"by_register":{"H":{"lines":2,"n":991},"non_H":{"lines":52,"n":2555}}} |
| Hum with ん: んっ 309 times (280 in H, 29 outside it), んんっ 155, んん 33 (16 in H, 17 outside it), んーん 2. Outside H it is a small hum of assent or effort; in H it is the moan. | hers | firm | per-register | measured | {"token_んん":33,"token_んーん":2,"token_んっ":309,"token_んんっ":155,"token_んん_by_register":{"H":16,"non_H":17},"token_んっ_by_register":{"H… |
| Do not show delight with おおー / おー: 0 lines carry either. Her delight is えへへ (115 tokens; えへへぇ 28 more as a distinctive token). | hers | firm | non-H | measured | {"token_おおー":0,"token_おー":0,"token_おおー_by_register":{"H":0,"non_H":0},"token_おー_by_register":{"H":0,"non_H":0}} |
| Let a big feeling out in えへへ (115 tokens), with いっぱい (10) and きちゃう (1) far behind: 255 spoken lines carry one of the three, 163 in H and 92 outside it. えへへ is the one that is hers. | hers | thin | per-register | measured | {"token_いっぱい":10,"token_きちゃう":1,"token_えへへ":115,"lines_matched":255,"by_register":{"H":{"lines":163,"n":991},"non_H":{"lines":92,… |
| Speak plain: です / ます is on 65 of 3546 spoken lines (79 tokens). The polite forms go to the student council president and to a teacher (01_01:1228, 01_01:4113, c05_01:1089) or come out as a deadpan claim (01_01:1338); with 一悟 and the other heroines she talks plain. | hers | firm | all | measured | {"lines_with_です_ます":65,"of_spoken_lines":3546,"token_ですます_occurrences":79} |
| Lean on the ellipsis: 1.18 … per non-H spoken line (3015) against 0.8798 for the room, and 5.1201 per H line (5074, moan elongation). The rate varies by block, so the rule holds directionally; do not quote a fixed rate. | hers | firm | per-register | measured | {"…_by_register":{"H":{"count":5074,"per_line":5.1201},"non_H":{"count":3015,"per_line":1.18}},"spoken_lines":3546,"room_per_line… |
| Outside H she uses ！ at 0.3041 per line and ？ at 0.3397 (the room's ！ is 0.1134); in H ！ rises to 0.6377 and ？ falls to 0.217. She asks and cries out in about equal measure outside H. | hers | thin | per-register | measured | {"！_by_register":{"H":{"count":632,"per_line":0.6377},"non_H":{"count":777,"per_line":0.3041}},"？_by_register":{"H":{"count":215,… |
| Smile is her most common face (618 of 2715 hits; 564 lines, 562 of them non-H) but sad is close behind (532) and surprise follows (375). Do not default to smile: she wears sad and surprise nearly as often. H scenes carry no face annotations. | hers | firm | non-H | measured | {"smile_occurrences":618,"all_occurrences":2715,"smile_lines":564,"smile_lines_by_register":{"H":{"lines":2,"n":991},"non_H":{"li… |
| @おじぎ is only third among her gestures (209 lines, 208 non-H; @ジャンプ 293 and @ううっ 267 are ahead of it), and only 56 of the bows come with a smile. | hers | firm | non-H | measured | {"@おじぎ_occurrences":209,"lines":209,"by_register":{"H":{"lines":1,"n":991},"non_H":{"lines":208,"n":2835}},"co_smile":56} |
| When refusing, @否定 (155 lines, 153 non-H) goes more often with a sad face (47) than with a smile (26). | hers | firm | non-H | measured | {"@否定_occurrences":155,"by_register":{"H":{"lines":2,"n":991},"non_H":{"lines":153,"n":2835}},"co_smile":26,"co_sad":47} |
| Jump (@ジャンプ, 293 lines, 292 non-H) mostly when surprised (129 lines) and sometimes when laughing (31). | hers | firm | non-H | measured | {"@ジャンプ_occurrences":293,"by_register":{"H":{"lines":1,"n":991},"non_H":{"lines":292,"n":2835}},"co_surprise":129,"co_laugh":31} |
| Keep the inner voice as bare narration, not speech: 280 lines, none in H, none ending on っ, no quotes. Vocabulary is far wider (type/token 0.9679 against 0.5573 for her speech), median 23 characters, mostly plain verb endings (た 65, る 44, けど 11, かな 6); よ ends 2 lines and ね 1. | hers | firm | non-H | measured | {"inner_lines":280,"inner_median_chars":23,"inner_ttr":0.9679,"spoken_ttr":0.5573,"inner_lines_ending_っ":0,"inner_lines_H":0} |
| Non-H lines carry a face on 0.734 (2081 of 2835) and a gesture on 0.3464 (982); H scenes carry a face on 0.005 and a gesture on 0.0061. Do not dress an H line with a face. | author | firm | per-register | measured | {"non_H":{"lines":2835,"with_expression":2081,"with_gesture":982,"expression_rate":0.734,"gesture_rate":0.3464},"H":{"lines":991,… |
| Use @emotion overlays rarely: 23 lines in all, led by 汗 (8) and ハート02 (6). They are authored colour, not her mood words. | author | firm | all | measured | {"lines_with_emotion":23,"types":{"汗":8,"ハート02":6,"ぽわぽわ":3,"キラン":2,"びっくり":1,"ハート01":1,"はてな":1,"キラキラ":1}} |
| Treat every expression label as a C4 hypothesis (vocabulary 0.2) with a confidence, not a fact. The receipt reads 8/16 classifiable units agreed, the same figure the 百花 bible carries, so read it as a project-level check, not a measurement of her. | author | firm | all | inferred | {"vocabulary_version":"0.2","her_units_agreed":"8/16 classifiable (see docs/koikano-expression-labels.md)"} |
| @おじぎ is the most common gesture corpus-wide (1576 calls), so her 209 bows are partly a house convention and not a trait of hers. | author | thin | all | inferred | {"corpus_@おじぎ_calls":1576,"her_@おじぎ":209} |
| Kiss gestures (@キス, @キス止め) are 19 lines, all with 一悟, 17 of them on route a. | moment | thin | all | measured | {"kiss_lines":19,"with_一悟":19,"route_a":17} |
| Dozing (@居眠り横 / @居眠り縦) is 10 lines, 9 of them with 一悟 (routes a 4, c 3, common 3). It is slept-through mornings and naps, played as ぐー、ぐー. | moment | thin | all | measured | {"lines":10,"with_一悟":9,"routes":{"a":4,"c":3,"common":3}} |
| Keep the sexual vocabulary inside the H scenes: 138 lines carry the matcher's words (the matcher's list is 百花's four, so おちんちん 43 is the one it finds in her), all 138 in H scenes (6) and 0 outside. The count is a lower bound for her real H vocabulary. | moment | firm | H | measured | {"lines_with_H_tokens":138,"in_H_scenes":138,"in_non_H":0,"h_scenes":6} |
| Laughing is a mid-size face for her: 190 laugh lines (189 non-H), only 30 of them with @ジャンプ, so jumping is not its usual partner. | moment | thin | non-H | measured | {"laugh_lines":190,"with_@ジャンプ":30,"by_register":{"H":{"lines":1,"n":991},"non_H":{"lines":189,"n":2835}}} |
| Voice her as a close, teasing and easily flustered talker: わたし (583 lines), sentence ends that lean on よ (331), ね (265), だよ (155), でしょ (76) and もん (132), flustered cries when caught (01_01:0819, 01_01:4188, 01_01:5360). Short outside H (median 20, … 1.18 per line), longer and moan-heavy inside H (median 32, … 5.1201 per line). | hers | firm | per-register | inferred | {"non_H":{"median_chars":20,"ellipsis_per_line":1.18},"H":{"median_chars":32,"ellipsis_per_line":5.1201},"third_person_lines":583} |

Rule split: class {'author': 4, 'hers': 17, 'moment': 4}; tier {'firm': 19, 'thin': 6}; register {'H': 1, 'all': 8, 'non-H': 8, 'per-register': 8}; evidence {'inferred': 3, 'measured': 22}. Unreceipted rules: none.

## Rhetorical mechanisms (B3)

These are the recurring moves in her speech that carry no `@emotion` / `@face` / `@action` - the B2 residue. They are **this builder's reading**, not the author's: the definitions, the class and the tier are interpretive; the line counts come from the fixed matcher named in each `method`, and the receipts are real lines. The surface rules they lean on are measured separately in `speech_guide` and `voice.surface`; this section adds the move, not the mark. A regex count is a lower bound where the move is defined by reading.

| mechanism | class | tier | confidence | lines | non-H / H | control rate | distinctive | receipts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Justifies herself with a sentence-final もん | hers | firm | high | 131 | 108 / 23 | 0.0001 | True | 01_01:0606, 01_01:0870 |
| Opens a reason with だって | hers | firm | medium | 44 | 32 / 12 | 0.0022 | True | 01_01:0606, 01_01:0870 |
| Laughs the えへへ | hers | firm | high | 169 | 75 / 94 | 0.0048 | True | 01_01:0251, 03_01:3203 |
| Puts herself next to 一悟 in one sentence | hers | firm | medium | 63 | 59 / 4 | 0.0 | True | 01_01:0727, 01_01:2570 |
| Speaks of 百花ちゃん by name | hers | firm | medium | 83 | 82 / 1 | 0.0 | True | 03_01:0420, 03_01:2206 |
| Offers to do it for him | hers | firm | medium | 72 | 40 / 32 | 0.0055 | True | 01_01:0654, 01_01:1538 |
| Closes the line on 一悟 | hers | firm | medium | 82 | 74 / 8 | 0.0063 | True | 01_01:1602, 01_01:2898 |
| Rebuts with ないよ / じゃないよ | hers | thin | medium | 33 | 30 / 3 | 0.0011 | True | 01_01:2708, 02_01:5422 |
| Presses a point with でしょ | hers | firm | medium | 76 | 66 / 10 | 0.0021 | True | 01_01:0579, 01_01:0852 |
| Calls for his attention with ねえ | hers | thin | low | 23 | 17 / 6 | 0.0008 | True | 01_01:0209, 01_01:0569 |
| Says 好き outright | hers | firm | medium | 100 | 49 / 51 | 0.0112 | True | 01_01:1291, 01_01:2570 |
| Whimpers the う、うう beat | hers | firm | low | 51 | 50 / 1 | 0.0038 | True | 01_01:0129, 01_01:0510 |
| Stammers on the first sound | hers | weak | high | 102 | 88 / 14 | 0.0423 | False | 02_01:0602, 02_01:3278 |

Mechanism split: class {'hers': 13}; tier {'firm': 10, 'thin': 2, 'weak': 1} (10 firm, 2 thin, 1 weak) over 3546 spoken lines.

Non-distinctive from the control heroines: stammers_first_sound.

Every mechanism is classed `hers` by this reading: each was found by contrasting her spoken lines with the other named speakers' in her scenes (tools/koikano/b3/mayu.py), and the distinctive flag is that contrast on the whole build, not the held-out gate. The class was not checked against the corpus ownership markers. The one move at or under the control share (stammers_first_sound) is kept as `weak`: the script's other speakers stammer as much, so it is house style.

How each was counted, and the weak ones:

- **Justifies herself with a sentence-final もん** (hers, firm, high, 131 line(s), share 0.0369; non-H 108 / H 23; control 0.0001, distinctive True): regex: the line ends (before the final marks) on もん after だ, ん, い, た, る or の. The most separated move she has. The other speakers in her scenes almost never close a line this way.
- **Opens a reason with だって** (hers, firm, medium, 44 line(s), share 0.0124; non-H 32 / H 12; control 0.0022, distinctive True): regex: the line starts with だって. A reproach she gives as an explanation, to 一悟 mostly.
- **Laughs the えへへ** (hers, firm, high, 169 line(s), share 0.0477; non-H 75 / H 94; control 0.0048, distinctive True): regex: contains えへ. Written laugh, one beat, then the sentence. Includes the drawn-out えへへぇ.
- **Puts herself next to 一悟 in one sentence** (hers, firm, medium, 63 line(s), share 0.0178; non-H 59 / H 4; control 0.0, distinctive True): regex: わたし, a case particle, up to three characters, then 一悟. Her own self-reference form is a surface rule in speech_guide; this is the move of ranking herself against him (and against 千奈 and 百花ちゃん in the same breath).
- **Speaks of 百花ちゃん by name** (hers, firm, medium, 83 line(s), share 0.0234; non-H 82 / H 1; control 0.0, distinctive True): regex: contains 百花ちゃん. An address habit tied to one person, kept as a mechanism because no one else in her scenes uses that form.
- **Offers to do it for him** (hers, firm, medium, 72 line(s), share 0.0203; non-H 40 / H 32; control 0.0055, distinctive True): regex: contains てあげ or であげ. Others use the form too (the control share is not zero), she uses it about four times as often.
- **Closes the line on 一悟** (hers, firm, medium, 82 line(s), share 0.0231; non-H 74 / H 8; control 0.0063, distinctive True): regex: the line ends on 一悟, with optional drawn vowel and final marks. The vocative sits at the end, so the line is aimed at him before it is heard.
- **Rebuts with ないよ / じゃないよ** (hers, thin, medium, 33 line(s), share 0.0093; non-H 30 / H 3; control 0.0011, distinctive True): regex: contains じゃないよ / ではないよ (not followed by ね), or ないよ followed by ！. Mostly the jealous scenes with 一悟, quoting his words back at him.
- **Presses a point with でしょ** (hers, firm, medium, 76 line(s), share 0.0214; non-H 66 / H 10; control 0.0021, distinctive True): regex: the line ends on でしょ with optional marks. Rhetorical, not a real question.
- **Calls for his attention with ねえ** (hers, thin, low, 23 line(s), share 0.0065; non-H 17 / H 6; control 0.0008, distinctive True): regex: the line starts with ねえ, ねぇ, ね、 or ねっ. Small count. It is usually followed by 一悟.
- **Says 好き outright** (hers, firm, medium, 100 line(s), share 0.0282; non-H 49 / H 51; control 0.0112, distinctive True): regex: contains 好き (not 物好き) or すき. The word, not the stance. Her love scenes carry most of it; the stage ones (演劇が好き) too.
- **Whimpers the う、うう beat** (hers, firm, low, 51 line(s), share 0.0144; non-H 50 / H 1; control 0.0038, distinctive True): regex: the line starts with two or more う/ぅ followed by っ … ！ or 、, or with う、う. Small count. Can be a hesitation or a sob, the regex does not tell which.
- **Stammers on the first sound** (hers, weak, high, 102 line(s), share 0.0288; non-H 88 / H 14; control 0.0423, distinctive False): regex: the line starts with one kana, 、, and the same kana again. Frequent in her lines, but the other speakers in her scenes stutter just as much (house style of the script), so it is not hers.

## Bounds and the absent list

Emotional pressures (authored `@emotion` types): {'汗': 8, 'ハート02': 6, 'ぽわぽわ': 3, 'キラン': 2, 'はてな': 1, 'びっくり': 1, 'キラキラ': 1, 'ハート01': 1}.

- expression vocabulary never on her lines: cry, blush, embarrassed, serious, shy, other
- gesture macros in the corpus never hers: @主人公視点戻し
- on-screen cast absent from her scenes: none

### What B2 could not derive (the B3 residue)

- address terms for NPCs: Not derivable. The NPC speakers are not in charData.csv, so there is no name form to search her lines for. Only the eight named cast and the protagonist 一悟 have alias forms.
- relationships with no address term: ひかる, 事務所の社長さん, 十川家の父, 新聞部部長, 案内アナウンス, 芸能記者, 芸能レポーター, 女性のお客さんＢ, 女性の店員さん, 千奈＆アリス＆百花＆ひかる＆真里亜＆知紗, 百花＆真里亜, 観客Ｂ
- rhetorical mechanisms deferred to B3: This list is the B2 residue, kept for provenance. B3 addressed it: see the `mechanisms` section. The B2 residue named deflects a topic, changes the subject, teases, jokes, stalls with repetition, or answers a question with a question - none of these carries an authored stage direction.
- trigger causality: Every trigger table is co-occurrence over her lines, not cause. The authored direction is a staging choice on the line; it does not say why.
- expression-label uncertainty: Expression triggers inherit the C4 hypothesis: a label on a line is the merged visual/context guess, not ground truth.
- tokenizer: The surface battery splits on punctuation (a class-based tokenizer), not morphology, so particles are matched by string suffix against a fixed list and the n-grams are character n-grams.
- room definition: The room is every other speaker in her scenes, named cast and NPCs together; the plan leaves this open.

## Spot check: one line carried through the layers

`01_01:0129` (scene 01_01, route common, channel spoken):

> 「うぅ……う……？」

```json
{
  "expressions": [
    {
      "witness": "message_face",
      "id": "CA04A016",
      "unit": "CA|A|016",
      "expression": "sad",
      "pose": "hands_clasped",
      "source": "agreed",
      "hypothesis": {
        "confidence": "ambiguous",
        "agreement": "agreed",
        "winner": "agreed",
        "version": "0.2",
        "provenance": {
          "visual": {
            "label": "sad",
            "confidence": "ambiguous",
            "image": "png/parts/face/ca01a016F.png",
            "note": "sullen frown",
            "alternative": "worried"
          },
          "context": {
            "label": "sad",
            "confidence": "inferred",
            "receipt": "01_01:0111",
            "note": "anchors: 汗 x1"
          }
        }
      }
    },
    {
      "witness": "sprite",
      "id": "CA04A009M",
      "unit": "CA|A|009",
      "expression": "sad",
      "pose": "hands_clasped",
      "source": "agreed",
      "hypothesis": {
        "confidence": "ambiguous",
        "agreement": "agreed",
        "winner": "agreed",
        "version": "0.2",
        "provenance": {
          "visual": {
            "label": "sad",
            "confidence": "ambiguous",
            "image": "png/parts/face/ca01a009F.png",
            "note": "downcast/drowsy",
            "alternative": "worried"
          },
          "context": {
            "label": "sad",
            "confidence": "inferred",
            "receipt": "01_01:0088",
            "note": "anchors: キラキラ x1"
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
        "file": "CA04A009M"
      },
      "macro": null,
      "event_line": 126,
      "conditional": false
    },
    {
      "kind": "gesture",
      "command": "@居眠り横",
      "args": {
        "id": "真優",
        "action": "ActionAdvFrown",
        "width": "10",
        "height": "0",
        "cycle": "5000",
        "count": "-1"
      },
      "macro": "居眠り横",
      "event_line": 127,
      "conditional": false
    }
  ],
  "interlocutor": "一悟"
}
```

This line is in `slice.json` (`her_line_ids`), its face and gesture are in `annotations.json` (`per_line`), and the gesture is in `gestures` in `bible.json`.

## Provenance

Inputs: game_logic.jsonl (37913 records), character_actions.jsonl (16732), expression_labels_lines.jsonl (20509), timing_table.jsonl (37795), expression_labels.json (915 labels), bgm_scene_table.json, charData.csv, data\scenario\*.ks.

Mechanical here: slice, battery, bounds, context, annotations, interactions, the B2 voice surface, the expression and gesture triggers, and the speech guide. B3 added `mechanisms`, a reading by the builder (no API call): the moves are interpretive, their counts are mechanical. Deferred to a model: the fidelity gate (B4). The expression labels are the C4 hypothesis layer, vocabulary version 0.2, and are presented as hypotheses with their confidence.

Corrections: B1 read the alias table from charData.csv, which omits the protagonist 一悟; B2 adds him for the address-term derivation in this bible only. B3 is a reading, not a measurement: the mechanism list is this builder's judgement of what shapes her speech, so class and tier are interpretive even where the count is mechanical. The B2 residue named 'deflects a topic, changes the subject, teases, jokes, stalls with repetition, or answers a question with a question'; those are covered by `doubles_a_key_word`, `closes_a_turn_with_a_short_question`, `names_a_blow_with_a_loanword` and `plays_a_role_with_stock_catchphrases`.
