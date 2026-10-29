# koikano authored expression bible - 千奈 (CB)

Date: 2026-09-16. Build: b0-b3/1 (authored-expression-bible/1). Phases B0+B1+B2+B3. B0-B2 are mechanical (no model spend, standard library); B3 is the builder's reading of the rhetorical moves, recorded in `mechanisms`. Route b. Source: `F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work\game_logic.jsonl` joined to the authored stage directions.

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
| her lines | 3942 |
| - spoken | 3493 |
| - inner voice | 449 |
| her scenes | 72 |
| room lines (others in her scenes) | 23996 |
| - room spoken | 13430 |
| - room inner | 10566 |

The scope's section 5.1 figure for 千奈 is 2,781 lines, 211 inner and 70 scenes. This build reproduces all three.

## Voice: her dialogue, her inner voice, the room

`dispersion` is scene document frequency: the share of her scenes in which the n-gram appears. `distinctive` is the log-odds of the channel against the other two channels pooled.

| channel | lines | tokens | token types | TTR |
| --- | --- | --- | --- | --- |
| her dialogue | 3493 | 15208 | 7304 | 0.4803 |
| her inner voice | 449 | 1014 | 947 | 0.9339 |
| the room (spoken) | 13430 | 34163 | 20687 | 0.6055 |

Distinctive tokens (log-odds, top 12):

- **her_dialogue**: 先輩 (262), あんっ (60), あっあっ (50), あぁぁ (44), あぁぁっ (42), んっんっ (40), せんぱい (36), 十川先輩 (35), ぁぁ (27), せん (21), ですっ (21), 先輩っ (21)
- **her_inner**: いつでも一緒 (2), ほっとしつつ (2), みゃー先輩のことを (2), オカズ (2), 気まずいです (2), あがった呼吸を落ち着けようと深呼吸するのが精いっぱいです (1), あそこまで取り乱したのは恥ずかしかったですし (1), あとはここから立ち去るだけです (1), あのキスをしていた人たちにも感謝しないといけないのかもしれませんが (1), あのキスシーンを目撃してしまったからで (1), あの日以来みゃー先輩とは気まずいままです (1), あの時からすでに (1)
- **the_room**: 一悟 (355), 真優 (174), うん (137), 千奈 (123), 百花ちゃん (117), ごめん (101), そうだな (97), えへへ (87), 分かった (87), そうか (86), おおー (76), ありがと (74)

### B2 surface: turn length, line-final, punctuation, self-reference

Turn length, kept characters per line (shares are in `bible.json`):

| channel | 1-5 | 6-10 | 11-20 | 21-40 | 41-80 | 81+ | mean | median | p90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| her_spoken | 175 | 243 | 709 | 2042 | 293 | 0 | 25.65 | 27 | 40 |
| her_inner | 9 | 20 | 107 | 273 | 38 | 0 | 25.69 | 26 | 39 |
| the_room_spoken | 1641 | 1764 | 3857 | 5135 | 851 | 0 | 19.83 | 18 | 38 |

Line-final morphemes, string suffixes of the kept text (top 10):

- **her spoken last token**: っ 166, みゃー先輩 40, 先輩 35, ありがとうございます 27, あっ 26, です 23, はぁ 22, ですか 19, んっ 18, んんっ 17
- **her spoken 2-char suffix**: です 346, すか 309, ます 214, すね 158, すっ 117, から 113, 先輩 102, んっ 94, すよ 86, した 82
- **her inner last token**: あがった呼吸を落ち着けようと深呼吸するのが精いっぱいです 1, あとはここから立ち去るだけです 1, あのキスをしていた人たちにも感謝しないといけないのかもしれませんが 1, あのキスシーンを目撃してしまったからで 1, あの日以来みゃー先輩とは気まずいままです 1, あの時の感覚が染みついています 1, あまりできません 1, あまりにも恥ずかしいことですが 1, あまりにも衝撃的な光景です 1, ありがちです 1
- **her inner 2-char suffix**: した 89, ます 83, です 74, せん 46, ょう 16, から 11, うか 10, って 8, して 7, んて 7

Line-final particles, matched by suffix against a fixed list (top 10 by spoken lines):

| ending | spoken lines | spoken share | inner lines | inner share |
| --- | --- | --- | --- | --- |
| っ | 770 | 0.2204 | 2 | 0.0045 |
| か | 381 | 0.1091 | 12 | 0.0267 |
| ね | 280 | 0.0802 | 6 | 0.0134 |
| から | 113 | 0.0324 | 11 | 0.0245 |
| よ | 107 | 0.0306 | 0 | 0.0 |
| ん | 72 | 0.0206 | 46 | 0.1024 |
| けど | 67 | 0.0192 | 6 | 0.0134 |
| よね | 59 | 0.0169 | 2 | 0.0045 |
| の | 22 | 0.0063 | 1 | 0.0022 |
| からね | 13 | 0.0037 | 0 | 0.0 |

Punctuation, full-width marks:

| mark | spoken count | spoken/line | inner count | room/line |
| --- | --- | --- | --- | --- |
| … | 9927 | 2.842 | 160 | 0.7989 |
| ！ | 1566 | 0.4483 | 36 | 0.1239 |
| ？ | 985 | 0.282 | 22 | 0.2865 |
| 、 | 6890 | 1.9725 | 453 | 0.8865 |
| 。 | 625 | 0.1789 | 423 | 0.3677 |
| ー | 659 | 0.1887 | 112 | 0.1374 |
| ～ | 33 | 0.0094 | 0 | 0.0046 |
| 「 | 3491 | 0.9994 | 0 | 0.9961 |

Self-reference: spoken 千奈 5 occurrences on 4 lines; spoken 私 477 occurrence(s) on 466 line(s); inner 千奈 0 occurrence(s) on 0 line(s).

- **her dialogue vs the room, tokens**: 先輩 (262), あんっ (60), です (57), あっあっ (50), あぁぁ (44), あぁぁっ (42), んっんっ (40), せんぱい (36), 十川先輩 (35), みゃー先輩 (103)
- **her dialogue vs the room, bigrams**: 輩っ (52), 輩せ (41), んぱ (118), 輩あ (36), っイ (35), 輩は (102), みゃ (303), 輩が (95)
- **her dialogue vs her inner, tokens**: 先輩 (262), あっ (208), んっ (177), あの (139), はい (119), は (107), ん (101), んんっ (98), はぁ (264), そうですね (74)
- **her dialogue vs her inner, bigrams**: ぁぁ (718), んっ (647), あぁ (426), っあ (420), ぁっ (386), っん (280), んん (278), すっ (222)

## Expressions (C4 hypotheses)

The repertoire is her own faces only (message face or sprite tag carrying the `CB` prefix). Confidence is carried from `expression_labels.json`.

| expression | her lines | confidence split |
| --- | --- | --- |
| talk | 1095 | {'clear': 964, 'ambiguous': 131} |
| smile | 327 | {'ambiguous': 239, 'clear': 88} |
| surprise | 290 | {'ambiguous': 282, 'clear': 8} |
| neutral | 245 | {'ambiguous': 245} |
| sad | 194 | {'ambiguous': 178, 'clear': 16} |
| laugh | 120 | {'clear': 120} |
| worried | 12 | {'clear': 3, 'inferred': 9} |
| serious | 9 | {'inferred': 9} |
| shy | 6 | {'ambiguous': 6} |
| excited | 5 | {'inferred': 5} |

### Expression triggers (all eight labels)

One row per label. `lines` is her lines carrying it (a line with two faces counts once here; the repertoire counts occurrences). `with` is the speaker whose turn preceded hers; `(none)` is a scene-opening or unattributed turn. `preceded by` is the last expression she wore earlier in the scene; `co-gesture` is the gesture on the same line. Co-occurrence, not cause.

| expression | lines | with | route | H/normal | mean chars | preceded by | co-gesture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| talk | 970 | 一悟 592, 真優 156, 千奈 91 | b 608, common 250, d 41 | normal 970 | 24.1 | talk 574, smile 103, surprise 92 | @おじぎ 121, @ジャンプ 71, @ううっ 49 |
| smile | 325 | 一悟 205, 真優 41, 百花 30 | b 150, common 118, c 23 | normal 325 | 25.39 | talk 148, smile 64, neutral 36 | @おじぎ 71, @否定 21, @ううっ 18 |
| surprise | 285 | 一悟 159, 真優 45, 百花 29 | b 124, common 121, a 14 | normal 285 | 21.03 | talk 113, surprise 64, neutral 38 | @ジャンプ 81, @ううっ 65, @否定 19 |
| neutral | 244 | 一悟 145, 真優 34, 百花 25 | common 112, b 84, c 21 | normal 244 | 22.38 | talk 104, surprise 39, smile 37 | @おじぎ 36, @ジャンプ 27, @ううっ 23 |
| sad | 190 | 一悟 122, 千奈 26, 真優 17 | b 137, common 46, c 3 | normal 190 | 24.36 | talk 78, sad 40, smile 26 | @ううっ 20, @おじぎ 13, @否定 12 |
| laugh | 120 | 一悟 74, 真優 18, 千奈 15 | b 86, common 25, d 5 | normal 120 | 24.46 | talk 56, surprise 16, neutral 14 | @おじぎ 17, @ううっ 10, @否定 9 |
| worried | 12 | 一悟 12 | b 10, common 2 | normal 12 | 20.25 | surprise 3, talk 3, smile 2 | @ジャンプ 2, @否定 1, @噴飯２ 1 |
| serious | 9 | 一悟 9 | b 7, a 1, common 1 | normal 9 | 32.11 | talk 6, sad 1, smile 1 | @否定 1 |
| shy | 6 | 一悟 3, 千奈 3 | b 5, common 1 | normal 6 | 29.5 | shy 2, sad 1, smile 1 | @ううっ 1, @否定 1 |
| excited | 5 | 一悟 5 | b 5 | normal 5 | 36.8 | talk 4, excited 1 | - |

## Gestures

| gesture | her lines |
| --- | --- |
| @おじぎ | 340 |
| @ううっ | 232 |
| @ジャンプ | 228 |
| @否定 | 144 |
| @噴飯２ | 15 |
| @キス | 4 |
| @噴飯１ | 4 |
| @抱きつき | 3 |
| @キス止め | 2 |
| @息切れ | 2 |
| @居眠り縦 | 1 |

Entry/exit: {'enter': 33, 'exit': 6}. Camera (targeted): {'@focus': 14}. Emotion overlays: {'びっくり': 6, '汗': 5, 'はてな': 2, 'びっくりF': 2, 'ぽわぽわ': 2, 'キラキラ': 2, 'ハート02': 2, 'キラン': 1, 'ピヨピヨF': 1}. Action commands (occurrences): {'@char': 2365, '@focus': 27, '@action': 22, '@move': 12, '@stopAction': 6}.

### Gesture triggers

One row per gesture. `co-face` is the C4 label on the same line; `preceded by` is the last label earlier in the scene; the other columns as above.

| gesture | lines | with | route | H/normal | mean chars | co-face | preceded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| @おじぎ | 340 | 一悟 235, 真優 49, 百花 21 | b 147, common 121, a 35 | H 5, normal 335 | 22.89 | talk 143, smile 71, neutral 36 | talk 116, (scene-start) 98, neutral 41 |
| @ううっ | 232 | 一悟 134, 真優 49, 百花 22 | b 119, common 64, a 23 | H 2, normal 230 | 20.98 | surprise 66, talk 53, neutral 23 | (scene-start) 76, talk 72, surprise 27 |
| @ジャンプ | 228 | 一悟 121, 真優 54, 百花 21 | b 92, common 89, c 18 | normal 228 | 20.44 | surprise 85, talk 80, neutral 27 | talk 73, (scene-start) 60, smile 29 |
| @否定 | 144 | 一悟 99, 真優 21, 百花 15 | b 76, common 43, a 12 | H 1, normal 143 | 27.12 | talk 45, smile 22, neutral 21 | talk 51, (scene-start) 36, smile 20 |
| @噴飯２ | 15 | 一悟 7, 百花 4, 真優 2 | common 7, b 6, c 1 | normal 15 | 10.47 | surprise 6, neutral 3, worried 1 | (scene-start) 5, talk 4, neutral 3 |
| @キス | 2 | 一悟 2 | b 2 | normal 2 | 8.0 | sad 1, smile 1, surprise 1 | smile 1, surprise 1 |
| @噴飯１ | 2 | 一悟 1, 真優 1 | common 2 | normal 2 | 3.5 | laugh 1, talk 1 | surprise 1, talk 1 |
| @抱きつき | 3 | 一悟 2, 真優 1 | b 2, common 1 | normal 3 | 14.67 | smile 1, talk 1 | (scene-start) 1, smile 1, talk 1 |
| @キス止め | 1 | 一悟 1 | b 1 | normal 1 | 34.0 | laugh 1 | laugh 1 |
| @息切れ | 2 | 一悟 2 | common 2 | normal 2 | 32.5 | neutral 1, smile 1 | smile 1, talk 1 |
| @居眠り縦 | 1 | 一悟 1 | c 1 | normal 1 | 10.0 | sad 1 | smile 1 |

### Emotion, entry/exit and action triggers

| trigger | lines | with | H/normal | co-face |
| --- | --- | --- | --- | --- |
| emotion びっくり (lines) | 6 | 一悟 4, 真優 1 | normal 6 | surprise 3, talk 2 |
| emotion 汗 (lines) | 5 | 真優 2, (none) 1 | normal 5 | surprise 3 |
| emotion はてな (lines) | 2 | 一悟 1, 真里亜 1 | normal 2 | surprise 1, talk 1 |
| emotion びっくりF (lines) | 2 | 一悟 2 | normal 2 | surprise 2 |
| emotion ぽわぽわ (lines) | 2 | 一悟 2 | normal 2 | talk 2 |
| emotion キラキラ (lines) | 2 | 一悟 2 | normal 2 | smile 1, talk 1 |
| emotion ハート02 (lines) | 2 | 一悟 2 | normal 2 | - |
| emotion キラン (lines) | 1 | 一悟 1 | normal 1 | talk 2 |
| emotion ピヨピヨF (lines) | 1 | 一悟 1 | normal 1 | sad 1 |
| enter/exit enter (lines) | 33 | 一悟 23, 真優 8 | normal 33 | talk 17, smile 5 |
| enter/exit exit (lines) | 6 | 真優 4, アリス 1 | normal 6 | talk 1 |
| action @char (lines) | 2115 | 一悟 1345, 真優 346 | H 16, normal 2099 | talk 861, smile 268 |
| action @focus (lines) | 14 | 千奈 5, 一悟 3 | normal 14 | sad 3, laugh 2 |
| action @action (lines) | 17 | 一悟 8, 真優 6 | normal 17 | smile 6, talk 6 |
| action @move (lines) | 4 | 一悟 2, 千奈 1 | normal 4 | neutral 1 |

## Interactions (per relationship)

| speaker | kind | turns | spoken | inner | scenes | her turns | her avg chars | her med chars | exch. her-start | exch. their-start | her expression mix | her gestures | her address |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 一悟 | protagonist | 16000 | 5952 | 10048 | 71 | 2642 | 26.84 | 29 | 12 | 401 | talk 675, smile 207, surprise 162, neutral 146 | @おじぎ 235, @ううっ 134, @ジャンプ 121 | 一悟先輩 24, 一悟 2, 一悟さん 1 |
| 真優 | heroine | 2685 | 2418 | 267 | 62 | 393 | 21.71 | 21 | 0 | 65 | talk 182, surprise 45, smile 41, neutral 34 | @ジャンプ 54, @ううっ 49, @おじぎ 49 | 十川先輩 75, 真優先輩 3, 十川 1 |
| 百花 | heroine | 1795 | 1584 | 211 | 58 | 200 | 22.93 | 23 | 0 | 100 | talk 58, surprise 31, smile 30, neutral 25 | @ううっ 22, @おじぎ 21, @ジャンプ 21 | 百花 53 |
| アリス | heroine | 1580 | 1541 | 39 | 50 | 79 | 23.08 | 23 | 0 | 115 | talk 26, surprise 16, smile 11, neutral 8 | @ううっ 11, @ジャンプ 11, @おじぎ 10 | アリス 2 |
| 真里亜 | heroine | 899 | 899 | 0 | 59 | 81 | 21.58 | 20 | 0 | 9 | talk 27, neutral 11, surprise 11, smile 10 | @おじぎ 15, @ううっ 10, @ジャンプ 9 | 真里亜さん 9 |
| ひかる | heroine | 415 | 415 | 0 | 38 | 16 | 19.44 | 17 | 0 | 23 | neutral 3, talk 3, surprise 2, smile 1 | @ジャンプ 5, @ううっ 2, @噴飯２ 1 | 小野坂先輩 1 |
| 知紗 | heroine | 356 | 356 | 0 | 34 | 20 | 17.8 | 19 | 0 | 3 | talk 10, smile 3, surprise 3, neutral 2 | @おじぎ 3, @ジャンプ 3, @否定 2 | 榎本先生 1 |
| ケルベロス | heroine | 133 | 133 | 0 | 30 | 11 | 20.55 | 21 | 0 | 9 | sad 8, neutral 4, surprise 3, talk 3 | @おじぎ 2, @ジャンプ 1, @否定 1 | ケルちゃん 2 |
| 天文部部員 | npc | 30 | 30 | 0 | 5 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| ＡＶ女優 | npc | 9 | 9 | 0 | 1 | 17 | 22.35 | 24 | 0 | 0 | talk 10, sad 5, surprise 5, laugh 3 | @おじぎ 1 | - |
| 一年生女子 | npc | 8 | 8 | 0 | 3 | 1 | 23.0 | 23 | 0 | 1 | smile 1 | - | - |
| 新聞部部長 | npc | 8 | 8 | 0 | 3 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 事務所の社長さん | npc | 7 | 7 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 芸能記者 | npc | 7 | 7 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 野村先生 | npc | 7 | 7 | 0 | 3 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 文化祭実行委員 | npc | 6 | 6 | 0 | 3 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| テニス部部員 | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 弱小部女子生徒Ａ | npc | 5 | 5 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 弱小部女子生徒Ｂ | npc | 5 | 5 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 見知らぬ女性Ａ | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 見知らぬ女性Ｂ | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 三年生女子 | npc | 3 | 3 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 映画研究部部長 | npc | 3 | 3 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 野球部部員 | npc | 3 | 3 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 女性のお客さんＢ | npc | 2 | 2 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 女性の店員さん | npc | 2 | 2 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 案内アナウンス | npc | 2 | 2 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 演劇部部員Ｂ | npc | 2 | 2 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 真優＆千奈 | unison | 2 | 2 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
|  | unattributed | 1 | 0 | 1 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 千奈＆アリス＆百花＆ひかる＆真里亜＆知紗 | unison | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 女性のお客さんＡ | npc | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 演劇部部員Ａ | npc | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 演劇部部員Ｃ | npc | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 百花＆真里亜 | unison | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 真優＆千奈＆一悟 | unison | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |

Scene openings across her scenes: 一悟 26, 千奈 12, 百花 10, 真優 10, アリス 6, ひかる 5, 案内アナウンス 1, 真里亜 1, 野村先生 1.

Reply vs initiation (her spoken turns): replies 2307, initiations 12, self-continuations 1174, reply rate 0.995.

### Address terms

How she names the other party, derived from her lines whose preceding speaker is that party. Overall: {"十川先輩":75,"百花":53,"一悟先輩":24,"真里亜さん":9,"真優先輩":3,"アリス":2,"ケルちゃん":2,"一悟":2,"一悟さん":1,"十川":1,"小野坂先輩":1,"榎本先生":1}.

B1 built the alias table from charData.csv, which holds only the eight named cast. The protagonist 一悟 is absent, so B1 reported no address term for him; B2 adds 一悟 to the alias table here only. The interaction layer on disk is unchanged.

Relationships where no name term is derivable from her lines: ＡＶ女優, 一年生女子.

## Speech guide

Each rule carries a class (hers / the author's / a moment), a tier (firm / thin), a `register` (all / H / non-H / per-register) and an evidence flag (measured / inferred). The receipt is the count or the lines the rule comes from; the example lines are in `bible.json`. Rules whose value differs by register state both.

| rule | class | tier | register | evidence | receipt |
| --- | --- | --- | --- | --- | --- |
| Refer to yourself as 私 (not by your own name); do not use 千奈. Holds in both registers. | hers | firm | all | measured | {"spoken_lines_with_私":466,"spoken_occurrences_私":477,"spoken_lines_with_千奈":4,"spoken_occurrences_千奈":5,"私_by_register":{"H":{"l… |
| Keep non-H turns short: median 18 kept characters outside H, median 28 inside H; no line over 63. | hers | firm | per-register | measured | {"non_H":{"lines":2372,"median_chars":23,"mean_chars":23.65,"max_chars":62},"H":{"lines":1121,"median_chars":32,"mean_chars":29.8… |
| Reply; do not open. Initiate in well under 1% of your turns. | hers | firm | all | measured | {"reply":2307,"initiation":12,"self_continuation":1174,"reply_rate":0.9948} |
| End many lines on a glottal っ; far heavier in H (moans) than outside it. | hers | firm | per-register | measured | {"lines_ending_っ":770,"share_of_spoken":0.2204,"by_register":{"H":{"lines":529,"n":1121},"non_H":{"lines":241,"n":2372}}} |
| Stretch the last syllable with ー on non-H lines; almost never inside an H scene. | hers | firm | non-H | measured | {"lines_ending_ー":11,"share_of_spoken":0.0031,"by_register":{"H":{"lines":4,"n":1121},"non_H":{"lines":7,"n":2372}}} |
| Agree with doubled ん (ん、んん、んーん); the rate is far higher in H. | hers | firm | per-register | measured | {"token_んん":31,"token_んーん":0,"token_んっ":177,"token_んんっ":98,"token_んん_by_register":{"H":21,"non_H":10},"token_んっ_by_register":{"H"… |
| Show delight with おおー / おー (a non-H beat). | hers | firm | non-H | measured | {"token_おおー":0,"token_おー":0,"token_おおー_by_register":{"H":0,"non_H":0},"token_おー_by_register":{"H":0,"non_H":0}} |
| Use plain childish words when the feeling is big (いっぱい, きちゃう, えへへ); heavier in H. | hers | thin | per-register | measured | {"token_いっぱい":5,"token_きちゃう":0,"token_えへへ":0,"lines_matched":21,"by_register":{"H":{"lines":18,"n":1121},"non_H":{"lines":3,"n":2… |
| Stay casual: almost no です / ます. | hers | firm | all | measured | {"lines_with_です_ます":2340,"of_spoken_lines":3493,"token_ですます_occurrences":3133} |
| Lean on the ellipsis: about 0.9 … per line outside H and about 6.3 inside H (moan elongation), read from the build block. The rate is not stable across blocks - the gate's held-out non-H block measures 1.76, about double. The rule holds directionally; do not quote a fixed rate. | hers | firm | per-register | measured | {"…_by_register":{"H":{"count":6000,"per_line":5.3524},"non_H":{"count":3927,"per_line":1.6556}},"spoken_lines":3493,"room_per_li… |
| Exclaim sparingly outside H (~0.03 ！/line) and rely on ？ at ~0.25/line; H moans carry ！ heavily (0.72/line). | hers | thin | per-register | measured | {"！_by_register":{"H":{"count":941,"per_line":0.8394},"non_H":{"count":625,"per_line":0.2635}},"？_by_register":{"H":{"count":263,… |
| Default to a smile face on non-H lines; it is about half of all her expression hits. H scenes carry no face annotations. | hers | firm | non-H | measured | {"smile_occurrences":327,"all_occurrences":2303,"smile_lines":325,"smile_lines_by_register":{"H":{"lines":0,"n":1170},"non_H":{"l… |
| Bow (@おじぎ) as the default gesture on non-H lines, usually with a smile. | hers | firm | non-H | measured | {"@おじぎ_occurrences":340,"lines":340,"by_register":{"H":{"lines":5,"n":1170},"non_H":{"lines":335,"n":2772}},"co_smile":71} |
| When refusing, use @否定 (non-H); you can refuse while still smiling. | hers | firm | non-H | measured | {"@否定_occurrences":144,"by_register":{"H":{"lines":1,"n":1170},"non_H":{"lines":143,"n":2772}},"co_smile":22,"co_sad":12} |
| Jump (@ジャンプ) when surprised or laughing (non-H). | hers | firm | non-H | measured | {"@ジャンプ_occurrences":228,"by_register":{"H":{"lines":0,"n":1170},"non_H":{"lines":228,"n":2772}},"co_surprise":85,"co_laugh":0} |
| Keep the inner voice as bare narration, not speech: no quotes, no っ / ー / ね / よ, more varied vocabulary. Inner voice appears only outside H. | hers | firm | non-H | measured | {"inner_lines":449,"inner_median_chars":26,"inner_ttr":0.9339,"spoken_ttr":0.4803,"inner_lines_ending_っ":2,"inner_lines_H":49} |
| Supply a face on about two-thirds of her non-H lines and a gesture on about a quarter; H scenes carry no faces and almost no gestures. | author | firm | per-register | measured | {"non_H":{"lines":2772,"with_expression":1962,"with_gesture":962,"expression_rate":0.7078,"gesture_rate":0.347},"H":{"lines":1170… |
| Use @emotion overlays sparingly; they are authored colour, not her mood words. | author | firm | all | measured | {"lines_with_emotion":22,"types":{"びっくり":6,"汗":5,"キラキラ":2,"はてな":2,"びっくりF":2,"ハート02":2,"ぽわぽわ":2,"キラン":1,"ピヨピヨF":1}} |
| Treat every expression label as a C4 hypothesis with a confidence, not a fact. | author | firm | all | inferred | {"vocabulary_version":"0.2","her_units_agreed":"8/16 classifiable (see docs/koikano-expression-labels.md)"} |
| Remember that @おじぎ is the most common gesture corpus-wide, so its frequency is partly a house convention. | author | thin | all | inferred | {"corpus_@おじぎ_calls":1576,"her_@おじぎ":340} |
| Keep kiss gestures (@キス, @キス止め) only with 一悟, only on route b. | moment | thin | all | measured | {"kiss_lines":3,"with_一悟":3,"route_b":3} |
| Keep dozing (@居眠り横 / @居眠り縦) almost always with 一悟 (6 of 7 lines). | moment | thin | all | measured | {"lines":1,"with_一悟":1,"routes":{"c":1}} |
| Keep the H-scene vocabulary (せーえき, おちんちん, おまんこ, きちゃう) inside the H scenes. | moment | firm | H | measured | {"lines_with_H_tokens":0,"in_H_scenes":0,"in_non_H":0,"h_scenes":7} |
| Laugh rarely (13 lines), and usually while jumping (non-H). | moment | thin | non-H | measured | {"laugh_lines":120,"with_@ジャンプ":0,"by_register":{"H":{"lines":0,"n":1170},"non_H":{"lines":120,"n":2772}}} |
| Voice her as cheerful and childlike: short, exclamatory, repetitive, self-named. The childlike register shifts toward H moans inside an H scene. | hers | firm | per-register | inferred | {"non_H":{"median_chars":23,"ellipsis_per_line":1.6556},"H":{"median_chars":32,"ellipsis_per_line":5.3524},"third_person_lines":4… |

Rule split: class {'author': 4, 'hers': 17, 'moment': 4}; tier {'firm': 19, 'thin': 6}; register {'H': 1, 'all': 8, 'non-H': 8, 'per-register': 8}; evidence {'inferred': 3, 'measured': 22}. Unreceipted rules: none.

## Rhetorical mechanisms (B3)

These are the recurring moves in her speech that carry no `@emotion` / `@face` / `@action` - the B2 residue. They are **this builder's reading**, not the author's: the definitions, the class and the tier are interpretive; the line counts come from the fixed matcher named in each `method`, and the receipts are real lines. The surface rules they lean on are measured separately in `speech_guide` and `voice.surface`; this section adds the move, not the mark. A regex count is a lower bound where the move is defined by reading.

| mechanism | class | tier | confidence | lines | non-H / H | control rate | distinctive | receipts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Stammers the first syllable of a word | hers | firm | high | 770 | 450 / 320 | 0.0265 | True | 01_01:1699, 01_01:1742 |
| Addresses the other person by 先輩 as a call | hers | firm | high | 445 | 213 / 232 | 0.0 | True | 01_01:1808, 01_01:1932 |
| Presses for an account with んですか | hers | firm | high | 319 | 246 / 73 | 0.0012 | True | 01_01:1825, 01_01:1932 |
| Explains or justifies herself with んです | hers | firm | high | 430 | 330 / 100 | 0.0031 | True | 01_01:1755, 01_01:2050 |
| Snaps a polite ending shut with っ | hers | thin | medium | 90 | 37 / 53 | 0.0 | True | 01_01:1776, 01_01:1957 |
| Scolds improper conduct with a prim word | hers | firm | high | 74 | 54 / 20 | 0.0012 | True | 01_01:1902, 01_01:2636 |
| Denies with 違います | hers | firm | high | 61 | 45 / 16 | 0.001 | True | 01_01:2050, 01_01:2627 |
| Stops him with a polite prohibition | hers | firm | high | 107 | 69 / 38 | 0.0027 | True | 01_01:1902, 01_01:2214 |
| Squeaks before the words come | hers | firm | medium | 187 | 64 / 123 | 0.0033 | True | 01_01:1649, 01_01:1699 |
| Talks shop as a novelist, and guards it | hers | thin | medium | 94 | 87 / 7 | 0.0054 | True | 01_01:5083, 02_01:4791 |

Mechanism split: class {'hers': 10}; tier {'firm': 8, 'thin': 2} (8 firm, 2 thin, 0 weak) over 3493 spoken lines.

Non-distinctive from the control heroines: none.

Every mechanism is classed `hers` because a corpus count of its markers puts it overwhelmingly on her lines (for example 26 of 27 catchphrase lines, 15 of 23 loanword lines, 42 of 51 sound-effect lines), and each recurs across her scenes and relationships. The one device shared with the author's comedy toolkit - coining a label - is noted in that mechanism. Nothing here was classed `author` or `moment`. The `weak` tier and `distinctive: false` mark the five moves B4 found at or below the control heroine rate: they are kept, because a reader still needs to know the move, but they are house style.

How each was counted, and the weak ones:

- **Stammers the first syllable of a word** (hers, firm, high, 770 line(s), share 0.2204; non-H 450 / H 320; control 0.0265, distinctive True): regex: one hiragana, a comma, then the same hiragana starting the next word, not preceded by another letter. The surface stutter, not a pause. It marks flustering and it carries the line into the word she then says whole. Other heroines stammer too, so the rate against the control is the test, not the existence of the move.
- **Addresses the other person by 先輩 as a call** (hers, firm, high, 445 line(s), share 0.1274; non-H 213 / H 232; control 0.0, distinctive True): regex: 先輩 followed by a punctuation mark or the end of the line. This is the call, not the topic: 先輩は / 先輩が (a third-person mention of him) is not counted. The control rate is 0: no other heroine addresses anyone by 先輩 in this way.
- **Presses for an account with んですか** (hers, firm, high, 319 line(s), share 0.0913; non-H 246 / H 73; control 0.0012, distinctive True): regex: contains んですか. A question in the polite register that is a reproach more than a request. Nothing in the record says what she does with the answer; the move is the asking.
- **Explains or justifies herself with んです** (hers, firm, high, 430 line(s), share 0.1231; non-H 330 / H 100; control 0.0031, distinctive True): regex: contains んです not followed by か. The explaining んです (ち、違うんです, 思ったんです). It pairs with the stammer: she often stammers into it.
- **Snaps a polite ending shut with っ** (hers, thin, medium, 90 line(s), share 0.0258; non-H 37 / H 53; control 0.0, distinctive True): regex: です or ます, then っ, then optional marks, at the end of the line. A subset of the glottal-っ rule in speech_guide, taken where it closes a polite sentence. Count is small, rate against the control is not.
- **Scolds improper conduct with a prim word** (hers, firm, high, 74 line(s), share 0.0212; non-H 54 / H 20; control 0.0012, distinctive True): regex over a fixed word list. The prim vocabulary only; エッチ / えっち is left out because the other heroines use it freely. Mostly outside H; inside H the same words turn up in the lines she says while refusing.
- **Denies with 違います** (hers, firm, high, 61 line(s), share 0.0175; non-H 45 / H 16; control 0.001, distinctive True): regex over a fixed word list. A flat polite denial. It overlaps the @否定 gesture in speech_guide but is the spoken move, not the gesture.
- **Stops him with a polite prohibition** (hers, firm, high, 107 line(s), share 0.0306; non-H 69 / H 38; control 0.0027, distinctive True): regex over a fixed set of prohibition frames. Shares ground with scolds_improper_conduct: the scold names the thing, this stops it.
- **Squeaks before the words come** (hers, firm, medium, 187 line(s), share 0.0535; non-H 64 / H 123; control 0.0033, distinctive True): regex: the line starts with one of the squeak syllables. Distinct from the sound-effect-as-action move: this is a reflex at the line start, not a stage direction. Other heroines squeak in H lines too, so the rate against the control is moderate.
- **Talks shop as a novelist, and guards it** (hers, thin, medium, 94 line(s), share 0.0269; non-H 87 / H 7; control 0.0054, distinctive True): regex over a fixed word list. Content as much as rhetoric: she brings the same topic back in several routes. The secrecy is in the lines (他の人には秘密), not in the matcher.

## Bounds and the absent list

Emotional pressures (authored `@emotion` types): {'びっくり': 6, '汗': 5, 'はてな': 2, 'びっくりF': 2, 'ぽわぽわ': 2, 'キラキラ': 2, 'ハート02': 2, 'キラン': 1, 'ピヨピヨF': 1}.

- expression vocabulary never on her lines: angry, cry, blush, embarrassed, other
- gesture macros in the corpus never hers: @なでなで, @ひざまずき, @主人公視点戻し, @外から飛び出し, @居眠り横, @身体眺め
- on-screen cast absent from her scenes: none

### What B2 could not derive (the B3 residue)

- address terms for NPCs: Not derivable. The NPC speakers are not in charData.csv, so there is no name form to search her lines for. Only the eight named cast and the protagonist 一悟 have alias forms.
- relationships with no address term: ＡＶ女優, 一年生女子
- rhetorical mechanisms deferred to B3: This list is the B2 residue, kept for provenance. B3 addressed it: see the `mechanisms` section. The B2 residue named deflects a topic, changes the subject, teases, jokes, stalls with repetition, or answers a question with a question - none of these carries an authored stage direction.
- trigger causality: Every trigger table is co-occurrence over her lines, not cause. The authored direction is a staging choice on the line; it does not say why.
- expression-label uncertainty: Expression triggers inherit the C4 hypothesis: a label on a line is the merged visual/context guess, not ground truth.
- tokenizer: The surface battery splits on punctuation (a class-based tokenizer), not morphology, so particles are matched by string suffix against a fixed list and the n-grams are character n-grams.
- room definition: The room is every other speaker in her scenes, named cast and NPCs together; the plan leaves this open.

## Spot check: one line carried through the layers

`01_01:1995` (scene 01_01, route common, channel spoken):

> 「あ……ありがとうございます……」

```json
{
  "expressions": [
    {
      "witness": "message_face",
      "id": "CB02A016",
      "unit": "CB|A|016",
      "expression": "neutral",
      "pose": "none",
      "source": "agreed",
      "hypothesis": {
        "confidence": "ambiguous",
        "agreement": "agreed",
        "winner": "agreed",
        "version": "0.2",
        "provenance": {
          "visual": {
            "label": "neutral",
            "confidence": "ambiguous",
            "image": "png/parts/face/cb01a016F.png",
            "note": "small mouth, blush",
            "alternative": "worried"
          },
          "context": {
            "label": "neutral",
            "confidence": "weak",
            "receipt": "01_01:1755",
            "note": "anchors: びっくり x1"
          }
        }
      }
    },
    {
      "witness": "sprite",
      "id": "CB02A014M",
      "unit": "CB|A|014",
      "expression": "sad",
      "pose": "none",
      "source": "visual",
      "hypothesis": {
        "confidence": "ambiguous",
        "agreement": "disputed",
        "winner": "vision",
        "version": "0.2",
        "provenance": {
          "visual": {
            "label": "sad",
            "confidence": "ambiguous",
            "image": "png/parts/face/cb02a014F.png",
            "note": "half-lidded frown",
            "alternative": "serious"
          },
          "context": {
            "label": "neutral",
            "confidence": "weak",
            "receipt": "01_01:1995",
            "note": "anchors: ピヨピヨF x2, はてな x1"
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
        "file": "CB02A014M"
      },
      "macro": null,
      "event_line": 1992,
      "conditional": false
    },
    {
      "kind": "gesture",
      "command": "@おじぎ",
      "args": {
        "id": "千奈",
        "action": "ActionAdvBow",
        "height": "10",
        "cycle": "500",
        "count": "1"
      },
      "macro": "おじぎ",
      "event_line": 1993,
      "conditional": false
    }
  ],
  "interlocutor": "ケルベロス"
}
```

This line is in `slice.json` (`her_line_ids`), its face and gesture are in `annotations.json` (`per_line`), and the gesture is in `gestures` in `bible.json`.

## Provenance

Inputs: game_logic.jsonl (37913 records), character_actions.jsonl (16732), expression_labels_lines.jsonl (20509), timing_table.jsonl (37795), expression_labels.json (915 labels), bgm_scene_table.json, charData.csv, data\scenario\*.ks.

Mechanical here: slice, battery, bounds, context, annotations, interactions, the B2 voice surface, the expression and gesture triggers, and the speech guide. B3 added `mechanisms`, a reading by the builder (no API call): the moves are interpretive, their counts are mechanical. Deferred to a model: the fidelity gate (B4). The expression labels are the C4 hypothesis layer, vocabulary version 0.2, and are presented as hypotheses with their confidence.

Corrections: B1 read the alias table from charData.csv, which omits the protagonist 一悟; B2 adds him for the address-term derivation in this bible only. B3 is a reading, not a measurement: the mechanism list is this builder's judgement of what shapes her speech, so class and tier are interpretive even where the count is mechanical. The B2 residue named 'deflects a topic, changes the subject, teases, jokes, stalls with repetition, or answers a question with a question'; those are covered by `doubles_a_key_word`, `closes_a_turn_with_a_short_question`, `names_a_blow_with_a_loanword` and `plays_a_role_with_stock_catchphrases`.
