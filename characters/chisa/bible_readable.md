# koikano authored expression bible - 知紗 (CF)

Date: 2026-09-16. Build: b0-b3/1 (authored-expression-bible/1). Phases B0+B1+B2+B3. B0-B2 are mechanical (no model spend, standard library); B3 is the builder's reading of the rhetorical moves, recorded in `mechanisms`. Route . Source: `F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work\game_logic.jsonl` joined to the authored stage directions.

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
| her lines | 557 |
| - spoken | 557 |
| - inner voice | 0 |
| her scenes | 37 |
| room lines (others in her scenes) | 17886 |
| - room spoken | 10787 |
| - room inner | 7099 |

The scope's section 5.1 figure for 知紗 is 2,781 lines, 211 inner and 70 scenes. This build reproduces all three.

## Voice: her dialogue, her inner voice, the room

`dispersion` is scene document frequency: the share of her scenes in which the n-gram appears. `distinctive` is the log-odds of the channel against the other two channels pooled.

| channel | lines | tokens | token types | TTR |
| --- | --- | --- | --- | --- |
| her dialogue | 557 | 2164 | 1513 | 0.6992 |
| her inner voice | 0 | 0 | 0 | 0.0 |
| the room (spoken) | 10787 | 28557 | 17080 | 0.5981 |

Distinctive tokens (log-odds, top 12):

- **her_dialogue**: 宮国君 (18), そうね (13), いいのよ (7), 大丈夫よ (7), そうよね (6), 千代田さん (6), アリスさん (4), すごいわ (3), んくぅうっ (3), んくううっ (3), 分かったわ (3), あぁんっ (2)
- **her_inner**: Will (0), a (0), cake (0), have (0), havesome (0), you (0), ――――っ (0), ――っ (0), ――と (0), ――はっ (0), ――ま (0), ――将来 (0)
- **the_room**: 一悟 (231), 真優 (130), いや (124), ありがとうございます (110), 百花 (102), そうですね (85), ナタリー (79), 百花ちゃん (79), あの (73), みゃー先輩 (68), いえ (67), まあ (66)

### B2 surface: turn length, line-final, punctuation, self-reference

Turn length, kept characters per line (shares are in `bible.json`):

| channel | 1-5 | 6-10 | 11-20 | 21-40 | 41-80 | 81+ | mean | median | p90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| her_spoken | 17 | 35 | 131 | 312 | 62 | 0 | 26.44 | 28 | 41 |
| her_inner | 0 | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| the_room_spoken | 1241 | 1366 | 3012 | 4261 | 758 | 0 | 20.38 | 19 | 38 |

Line-final morphemes, string suffixes of the kept text (top 10):

- **her spoken last token**: っ 12, って 4, 十川さん 4, ううっ 3, どうして 3, ね 3, ふあっ 3, んんぅ 3, 宮国君 3, ああっ 2
- **her spoken 2-char suffix**: から 20, たわ 18, のよ 18, わね 17, いわ 16, もの 16, しら 15, って 14, のね 13, んっ 13
- **her inner last token**: -
- **her inner 2-char suffix**: -

Line-final particles, matched by suffix against a fixed list (top 10 by spoken lines):

| ending | spoken lines | spoken share | inner lines | inner share |
| --- | --- | --- | --- | --- |
| っ | 87 | 0.1562 | 0 | 0.0 |
| ね | 78 | 0.14 | 0 | 0.0 |
| わ | 61 | 0.1095 | 0 | 0.0 |
| の | 48 | 0.0862 | 0 | 0.0 |
| よ | 40 | 0.0718 | 0 | 0.0 |
| から | 20 | 0.0359 | 0 | 0.0 |
| ん | 16 | 0.0287 | 0 | 0.0 |
| のね | 13 | 0.0233 | 0 | 0.0 |
| よね | 12 | 0.0215 | 0 | 0.0 |
| けど | 11 | 0.0197 | 0 | 0.0 |

Punctuation, full-width marks:

| mark | spoken count | spoken/line | inner count | room/line |
| --- | --- | --- | --- | --- |
| … | 938 | 1.684 | 0 | 0.9309 |
| ！ | 267 | 0.4794 | 0 | 0.1341 |
| ？ | 201 | 0.3609 | 0 | 0.2749 |
| 、 | 938 | 1.684 | 0 | 0.9654 |
| 。 | 159 | 0.2855 | 0 | 0.3415 |
| ー | 60 | 0.1077 | 0 | 0.1423 |
| ～ | 3 | 0.0054 | 0 | 0.0033 |
| 「 | 547 | 0.982 | 0 | 0.9963 |

Self-reference: spoken 知紗 2 occurrences on 2 lines; spoken 私 67 occurrence(s) on 65 line(s); inner 知紗 0 occurrence(s) on 0 line(s).

- **her dialogue vs the room, tokens**: 宮国君 (18), そうね (13), いいのよ (7), 大丈夫よ (7), そうよね (6), 千代田さん (6), アリスさん (4), すごいわ (3), んくぅうっ (3), んくううっ (3)
- **her dialogue vs the room, bigrams**: 国君 (68), 夫よ (8), 目よ (6), ねれ (5), ぬる (4), ズン (4), 春ね (4), い騒 (3)
- **her dialogue vs her inner, tokens**: あっ (38), んっ (23), そ (19), っ (19), ん (18), 宮国君 (18), ああっ (16), でも (16), んんっ (16), ええ (15)
- **her dialogue vs her inner, bigrams**: って (217), さん (152), ない (122), から (116), った (114), して (106), そう (100), あっ (93)

## Expressions (C4 hypotheses)

The repertoire is her own faces only (message face or sprite tag carrying the `CF` prefix). Confidence is carried from `expression_labels.json`.

| expression | her lines | confidence split |
| --- | --- | --- |
| smile | 116 | {'clear': 116} |
| surprise | 81 | {'ambiguous': 74, 'clear': 7} |
| talk | 67 | {'clear': 38, 'ambiguous': 29} |
| excited | 55 | {'explicit': 55} |
| neutral | 44 | {'ambiguous': 44} |
| sad | 24 | {'ambiguous': 24} |
| worried | 7 | {'ambiguous': 7} |

### Expression triggers (all eight labels)

One row per label. `lines` is her lines carrying it (a line with two faces counts once here; the repertoire counts occurrences). `with` is the speaker whose turn preceded hers; `(none)` is a scene-opening or unattributed turn. `preceded by` is the last expression she wore earlier in the scene; `co-gesture` is the gesture on the same line. Co-occurrence, not cause.

| expression | lines | with | route | H/normal | mean chars | preceded by | co-gesture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smile | 116 | 一悟 60, 真優 23, 真里亜 12 | common 56, a 25, c 19 | normal 116 | 28.18 | smile 27, surprise 22, talk 21 | @おじぎ 18, @ジャンプ 8, @否定 6 |
| surprise | 77 | 一悟 34, 真優 26, 真里亜 7 | a 41, common 21, c 7 | normal 77 | 24.68 | surprise 45, talk 11, neutral 6 | @ジャンプ 18, @おじぎ 9, @ううっ 6 |
| talk | 65 | 一悟 30, 真里亜 9, 野村先生 8 | common 40, b 10, a 6 | normal 65 | 24.91 | talk 27, smile 14, neutral 7 | @ジャンプ 16, @おじぎ 7, @ううっ 2 |
| excited | 55 | 一悟 26, 真里亜 9, 真優 8 | common 27, a 10, c 7 | normal 55 | 24.85 | smile 17, talk 15, surprise 11 | @ジャンプ 12, @おじぎ 11, @ううっ 8 |
| neutral | 40 | 一悟 29, 真里亜 5, 真優 4 | common 25, a 8, c 4 | normal 40 | 26.3 | neutral 17, smile 12, surprise 4 | @ううっ 4, @ジャンプ 3, @否定 3 |
| sad | 24 | 一悟 14, 千奈 3, 真里亜 3 | common 9, a 7, b 3 | normal 24 | 27.67 | surprise 9, neutral 5, smile 4 | @ううっ 4, @おじぎ 3, @否定 2 |
| worried | 7 | 一悟 4, 千奈 1, 真優 1 | a 3, d 2, b 1 | normal 7 | 28.43 | surprise 4, smile 2, sad 1 | @ううっ 1, @おじぎ 1 |

## Gestures

| gesture | her lines |
| --- | --- |
| @ジャンプ | 61 |
| @おじぎ | 51 |
| @ううっ | 33 |
| @否定 | 19 |
| @噴飯２ | 5 |
| @噴飯１ | 2 |

Entry/exit: {'enter': 14}. Camera (targeted): {}. Emotion overlays: {'キラン': 2, '汗': 2, 'はてな': 1, 'びっくり': 1, 'ぽわぽわ': 1, 'キラキラ': 1, 'ハート02': 1}. Action commands (occurrences): {'@char': 401, '@action': 8, '@move': 7, '@focus': 5, '@stopAction': 1}.

### Gesture triggers

One row per gesture. `co-face` is the C4 label on the same line; `preceded by` is the last label earlier in the scene; the other columns as above.

| gesture | lines | with | route | H/normal | mean chars | co-face | preceded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| @ジャンプ | 61 | 一悟 26, 真里亜 12, 真優 6 | common 37, a 9, c 7 | H 5, normal 56 | 22.0 | surprise 20, talk 16, excited 12 | (scene-start) 14, talk 13, smile 11 |
| @おじぎ | 51 | 一悟 29, 真優 8, 真里亜 5 | common 24, a 13, d 7 | H 3, normal 48 | 24.25 | smile 18, excited 11, surprise 9 | (scene-start) 13, talk 11, surprise 9 |
| @ううっ | 33 | 一悟 16, 真優 6, 真里亜 6 | common 14, d 7, c 5 | H 3, normal 30 | 24.3 | excited 8, surprise 7, neutral 4 | (scene-start) 10, talk 7, neutral 5 |
| @否定 | 19 | 一悟 13, 真優 3, 百花 2 | common 5, d 5, a 4 | normal 19 | 28.63 | smile 6, neutral 3, surprise 3 | smile 6, (scene-start) 4, surprise 4 |
| @噴飯２ | 5 | 百花 2, 一悟 1, 千奈 1 | c 3, common 1, d 1 | normal 5 | 24.6 | excited 1, neutral 1, surprise 1 | (scene-start) 3, neutral 1, surprise 1 |
| @噴飯１ | 1 | 一悟 1 | common 1 | normal 1 | 17.0 | talk 1 | talk 1 |

### Emotion, entry/exit and action triggers

| trigger | lines | with | H/normal | co-face |
| --- | --- | --- | --- | --- |
| emotion キラン (lines) | 2 | 一悟 1, 千奈 1 | normal 2 | excited 1 |
| emotion 汗 (lines) | 2 | 千奈 1, 真優 1 | normal 2 | sad 1 |
| emotion はてな (lines) | 1 | 千奈 1 | normal 1 | surprise 1 |
| emotion びっくり (lines) | 1 | 百花 1 | normal 1 | - |
| emotion ぽわぽわ (lines) | 1 | 真優 1 | normal 1 | - |
| emotion キラキラ (lines) | 1 | 真優 1 | normal 1 | talk 1 |
| emotion ハート02 (lines) | 1 | 一悟 1 | normal 1 | smile 1, talk 1 |
| enter/exit enter (lines) | 14 | 一悟 5, 千奈 3 | normal 14 | smile 2, surprise 2 |
| action @char (lines) | 366 | 一悟 177, 真優 57 | H 19, normal 347 | smile 100, surprise 71 |
| action @action (lines) | 5 | 一悟 2, 真優 2 | normal 5 | excited 3, surprise 1 |
| action @move (lines) | 3 | 真優 2, ケルベロス 1 | normal 3 | excited 2, surprise 1 |

## Interactions (per relationship)

| speaker | kind | turns | spoken | inner | scenes | her turns | her avg chars | her med chars | exch. her-start | exch. their-start | her expression mix | her gestures | her address |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 一悟 | protagonist | 10490 | 3937 | 6553 | 36 | 240 | 27.81 | 30 | 0 | 94 | smile 60, surprise 36, neutral 31, talk 31 | @おじぎ 29, @ジャンプ 26, @ううっ 16 | - |
| 真優 | heroine | 1797 | 1683 | 114 | 35 | 60 | 24.17 | 23 | 0 | 6 | surprise 28, smile 23, excited 8, talk 6 | @おじぎ 8, @ううっ 6, @ジャンプ 6 | 十川さん 19 |
| 千奈 | heroine | 1748 | 1488 | 260 | 34 | 24 | 22.46 | 21 | 0 | 14 | smile 5, talk 5, surprise 4, sad 3 | @ジャンプ 3, @ううっ 2, @噴飯２ 1 | 七瀬さん 3 |
| 百花 | heroine | 1279 | 1140 | 139 | 32 | 24 | 22.29 | 24 | 0 | 11 | excited 4, talk 3, surprise 2, sad 1 | @ジャンプ 5, @否定 2, @噴飯２ 2 | 千代田さん 3 |
| アリス | heroine | 1241 | 1209 | 32 | 33 | 24 | 27.25 | 30 | 0 | 26 | smile 8, excited 3, neutral 2, talk 2 | @おじぎ 4, @ジャンプ 2, @ううっ 1 | アリスさん 2 |
| 真里亜 | heroine | 851 | 851 | 0 | 36 | 163 | 26.85 | 28 | 0 | 8 | smile 12, excited 9, talk 9, neutral 7 | @ジャンプ 12, @ううっ 6, @おじぎ 5 | 真里亜さん 24, 真里亜 2 |
| ひかる | heroine | 306 | 306 | 0 | 26 | 9 | 22.22 | 22 | 0 | 19 | excited 2, sad 1, smile 1, surprise 1 | @ジャンプ 4 | - |
| ケルベロス | heroine | 93 | 93 | 0 | 20 | 3 | 16.67 | 15 | 0 | 1 | talk 2, surprise 1 | @ううっ 1, @ジャンプ 1 | ケル 1, ケルベロス 1 |
| 天文部部員 | npc | 30 | 30 | 0 | 5 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 一年生女子 | npc | 8 | 8 | 0 | 3 | 1 | 8.0 | 8 | 0 | 1 | smile 1 | @おじぎ 1 | - |
| 文化祭実行委員 | npc | 6 | 6 | 0 | 3 | 1 | 19.0 | 19 | 0 | 0 | surprise 1 | @ジャンプ 1 | - |
| 見知らぬ女性Ａ | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 見知らぬ女性Ｂ | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 野村先生 | npc | 5 | 5 | 0 | 2 | 8 | 27.75 | 31 | 0 | 0 | talk 9, smile 5, excited 1, surprise 1 | @おじぎ 3, @ジャンプ 1 | - |
| 新聞部部長 | npc | 4 | 4 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 三年生女子 | npc | 3 | 3 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 映画研究部部長 | npc | 3 | 3 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 野球部部員 | npc | 3 | 3 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| テニス部部員 | npc | 2 | 2 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 案内アナウンス | npc | 2 | 2 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
|  | unattributed | 1 | 0 | 1 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 千奈＆アリス＆百花＆ひかる＆真里亜＆知紗 | unison | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 真優＆千奈 | unison | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 真優＆千奈＆一悟 | unison | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 芸能記者 | npc | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |

Scene openings across her scenes: 一悟 16, 百花 5, 真優 5, 千奈 4, アリス 3, ひかる 1, ケルベロス 1, 案内アナウンス 1, 真里亜 1.

Reply vs initiation (her spoken turns): replies 430, initiations 0, self-continuations 127, reply rate 1.000.

### Address terms

How she names the other party, derived from her lines whose preceding speaker is that party. Overall: {"真里亜さん":24,"十川さん":19,"七瀬さん":3,"千代田さん":3,"アリスさん":2,"真里亜":2,"ケル":1,"ケルベロス":1}.

B1 built the alias table from charData.csv, which holds only the eight named cast. The protagonist 一悟 is absent, so B1 reported no address term for him; B2 adds 一悟 to the alias table here only. The interaction layer on disk is unchanged.

Relationships where no name term is derivable from her lines: 一悟, ひかる, 一年生女子, 文化祭実行委員, 野村先生.

## Speech guide

Each rule carries a class (hers / the author's / a moment), a tier (firm / thin / weak, see tier_rule in bible.json), a `register` (all / H / non-H / per-register) and an evidence flag (measured / inferred). The receipt is the count or the lines the rule comes from; the example lines are in `bible.json`. Rules whose value differs by register state both.

| rule | class | tier | register | evidence | receipt |
| --- | --- | --- | --- | --- | --- |
| Call yourself 私: 68 of 557 spoken lines (H 26, non-H 42). You also call yourself 先生 (51 lines, 先生、相談に乗るわよ 01_01:4181) and twice by name (d05_01:0399, d05_01:0711). | hers | firm | all | measured | {"spoken_lines_with_私":65,"spoken_occurrences_私":67,"spoken_lines_with_知紗":2,"spoken_occurrences_知紗":2,"私_by_register":{"H":{"lin… |
| Keep turns medium: median 28 kept characters pooled (non-H 27, H 29), no line over 59. | hers | firm | per-register | measured | {"non_H":{"lines":395,"median_chars":27,"mean_chars":26.11,"max_chars":54},"H":{"lines":162,"median_chars":29,"mean_chars":27.23,… |
| Reply; do not open. 430 of her turns answer someone and 0 open a scene (reply rate 1.0); 127 more continue her own turn. | hers | firm | all | measured | {"reply":430,"initiation":0,"self_continuation":127,"reply_rate":1.0} |
| A glottal っ ending is mostly an H habit: 87 lines end on っ, 65 of them in H (of 162) and 22 outside it (of 395). | hers | firm | per-register | measured | {"lines_ending_っ":87,"share_of_spoken":0.1562,"by_register":{"H":{"lines":65,"n":162},"non_H":{"lines":22,"n":395}}} |
| Do not stretch the last syllable with ー: 0 of 395 non-H lines end on ー, and 1 of the 162 H lines does (08_02:4057 いつまでも寝ていられないわよー！). | hers | weak | all | measured | {"lines_ending_ー":1,"share_of_spoken":0.0018,"by_register":{"H":{"lines":1,"n":162},"non_H":{"lines":0,"n":395}}} |
| Hum with ん mostly in H: んっ 23 (all in H), んん 8 (6 in H, 2 outside), んんっ 16 more; んーん 0. | hers | thin | H | measured | {"token_んん":8,"token_んーん":0,"token_んっ":23,"token_んんっ":16,"token_んん_by_register":{"H":6,"non_H":2},"token_んっ_by_register":{"H":23,… |
| Do not show delight with おおー / おー: 0 lines end on either; the one line with おー is a cheer (d17_01:1223 えいえいおー). | hers | weak | all | measured | {"token_おおー":0,"token_おー":0,"token_おおー_by_register":{"H":0,"non_H":0},"token_おー_by_register":{"H":0,"non_H":0}} |
| Childish words are not her habit: 8 spoken lines match any of いっぱい, きちゃう, えへへ (H 5, non-H 3). | hers | weak | all | measured | {"token_いっぱい":0,"token_きちゃう":1,"token_えへへ":0,"lines_matched":8,"by_register":{"H":{"lines":5,"n":162},"non_H":{"lines":3,"n":395}… |
| Speak plain: です or ます is on 14 of 557 spoken lines (15 tokens), all of them outside H, mostly to other teachers or strangers (03_01:0644 野村先生). Her base register is plain with soft endings (わ, のよ, のね, かしら), not polite and not rough. | hers | firm | all | measured | {"lines_with_です_ます":14,"of_spoken_lines":557,"token_ですます_occurrences":15} |
| Ellipsis runs 0.5772 … per line outside H (228 in 395) and 4.3827 inside H (710 in 162, moan elongation); the room runs at 0.9309 per line. | hers | firm | per-register | measured | {"…_by_register":{"H":{"count":710,"per_line":4.3827},"non_H":{"count":228,"per_line":0.5772}},"spoken_lines":557,"room_per_line"… |
| She exclaims and asks: outside H ！ 159 times (0.4025 per line) and ？ 146 (0.3696); in H ！ is 108 (0.6667 per line) and ？ 55 (0.3395). The room runs at 0.1341 ！ per line, so she is loud for the cast. | hers | firm | per-register | measured | {"！_by_register":{"H":{"count":108,"per_line":0.6667},"non_H":{"count":159,"per_line":0.4025}},"？_by_register":{"H":{"count":55,"… |
| Smile is her commonest face outside H: 116 of 395 lines carry one; her 394 face hits are smile 116, surprise 81, talk 67, excited 55, neutral 44, sad 24, worried 7. H scenes carry no face (0 of 162). | hers | firm | non-H | measured | {"smile_occurrences":116,"all_occurrences":394,"smile_lines":116,"smile_lines_by_register":{"H":{"lines":0,"n":162},"non_H":{"lin… |
| Bow (@おじぎ) on 51 lines, 48 of them outside H and 18 with a smile. | hers | firm | non-H | measured | {"@おじぎ_occurrences":51,"lines":51,"by_register":{"H":{"lines":3,"n":162},"non_H":{"lines":48,"n":395}},"co_smile":18} |
| When refusing, @否定 (19 lines, all outside H); 6 of them go with a smile and 2 with a sad face. | hers | thin | non-H | measured | {"@否定_occurrences":19,"by_register":{"H":{"lines":0,"n":162},"non_H":{"lines":19,"n":395}},"co_smile":6,"co_sad":2} |
| Jump (@ジャンプ) is common for her: 61 lines (56 outside H, 5 in H), 20 of them with surprise and 0 with a laugh. | hers | firm | non-H | measured | {"@ジャンプ_occurrences":61,"by_register":{"H":{"lines":5,"n":162},"non_H":{"lines":56,"n":395}},"co_surprise":20,"co_laugh":0} |
| She has no inner voice in the record (0 inner lines). Do not write inner narration for her. | hers | weak | all | measured | {"inner_lines":0,"inner_median_chars":0,"inner_ttr":0.0,"spoken_ttr":0.6992,"inner_lines_ending_っ":0,"inner_lines_H":0} |
| Non-H lines carry a face on 0.7949 (314 of 395) and a gesture on 0.4025 (159); H scenes carry a face on 0.0 (0 of 162) and a gesture on 0.0679 (11). | author | firm | per-register | measured | {"non_H":{"lines":395,"with_expression":314,"with_gesture":159,"expression_rate":0.7949,"gesture_rate":0.4025},"H":{"lines":162,"… |
| @emotion overlays are rare: 9 lines in all (キラン 2, 汗 2, はてな 1, びっくり 1, ぽわぽわ 1, キラキラ 1, ハート02 1). They are authored colour, not her mood words. | author | weak | all | measured | {"lines_with_emotion":9,"types":{"キラン":2,"汗":2,"ぽわぽわ":1,"ハート02":1,"はてな":1,"キラキラ":1,"びっくり":1}} |
| Treat every expression label as a C4 hypothesis (vocabulary 0.2) with a confidence, not a fact. The receipt 8/16 is a project-level figure shared by every subject, not a measure of her. | author | weak | all | inferred | {"vocabulary_version":"0.2","her_units_agreed":"8/16 classifiable (see docs/koikano-expression-labels.md)"} |
| @おじぎ is the most common gesture corpus-wide (1576 calls), so her 51 bows are partly a house convention and not a trait of hers. | author | weak | all | inferred | {"corpus_@おじぎ_calls":1576,"her_@おじぎ":51} |
| Kiss gestures (@キス, @キス止め) are never hers: 0 lines. The kissing in 08_02 is written as sounds in her text (08_02:0414, 08_02:0445), not as a gesture. | moment | weak | all | measured | {"kiss_lines":0,"with_一悟":0,"route_own":0} |
| Dozing gestures (@居眠り横 / @居眠り縦) are never hers: 0 lines. | moment | weak | all | measured | {"lines":0,"with_一悟":0,"routes":{}} |
| The H-scene vocabulary stays inside the H scene 08_02: 精液 or せーえき 6 lines, セックス 5, 中出し or 膣内 4, きちゃう 4, all in H and 0 outside. She does not say おちんちん or おまんこ (0 lines); she says ペニス on 8 lines (7 in H, 1 outside in d10_01:2212, where she repeats a student's question in a health class). | moment | thin | H | measured | {"lines_with_H_tokens":4,"in_H_scenes":4,"in_non_H":0,"h_scenes":1} |
| Laugh faces are never hers: 0 lines carry one. Her laugh is in the text instead: あは… on 17 lines (14 outside H, 3 in H), 20 with any laugh word. | moment | weak | all | measured | {"laugh_lines":0,"with_@ジャンプ":0,"by_register":{"H":{"lines":0,"n":162},"non_H":{"lines":0,"n":395}}} |
| Voice her as a warm, flustered adult teacher: plain forms with soft closings (のよ 47 lines, のね 38, かしら 27, わ-type closings 113), surname plus さん or 君 for every student, 先生 for herself, medium-length turns, and she replies far more than she opens. Not childlike, not polite-formal, not self-named by given name. | hers | firm | all | inferred | {"non_H":{"median_chars":27,"ellipsis_per_line":0.5772},"H":{"median_chars":29,"ellipsis_per_line":4.3827},"third_person_lines":6… |

Rule split: class {'author': 4, 'hers': 17, 'moment': 4}; tier {'firm': 12, 'thin': 3, 'weak': 10}; register {'H': 1, 'all': 8, 'non-H': 8, 'per-register': 8}; evidence {'inferred': 3, 'measured': 22}. Unreceipted rules: none.

## Rhetorical mechanisms (B3)

These are the recurring moves in her speech that carry no `@emotion` / `@face` / `@action` - the B2 residue. They are **this builder's reading**, not the author's: the definitions, the class and the tier are interpretive; the line counts come from the fixed matcher named in each `method`, and the receipts are real lines. The surface rules they lean on are measured separately in `speech_guide` and `voice.surface`; this section adds the move, not the mark. A regex count is a lower bound where the move is defined by reading.

| mechanism | class | tier | confidence | lines | non-H / H | control rate | distinctive | receipts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Calls the people in front of her by surname and さん / 君 | hers | firm | high | 168 | 138 / 30 | 0.0124 | True | 01_01:4120, 01_01:4212 |
| Closes a line on a soft わ | hers | firm | high | 113 | 94 / 19 | 0.0275 | True | 01_01:4181, 02_01:1174 |
| Explains or gives the reason with のよ / のね | hers | firm | high | 85 | 63 / 22 | 0.0095 | True | 01_01:4161, 04_01:2957 |
| Wonders aloud with かしら | hers | thin | high | 27 | 20 / 7 | 0.0004 | True | 01_01:4148, 02_01:1223 |
| Calls herself 先生 | hers | firm | high | 51 | 40 / 11 | 0.0069 | True | 01_01:4181, 01_01:4269 |
| Reaches for 青春 | hers | thin | high | 17 | 14 / 3 | 0.0007 | True | 08_02:0231, 08_02:0260 |
| Opens on あら | hers | thin | medium | 17 | 17 / 0 | 0.0111 | True | 01_01:4161, 01_01:4195 |
| Slides into ちゃう / ちゃった | hers | firm | high | 50 | 39 / 11 | 0.0096 | True | 01_01:4269, 03_01:0644 |
| Reaches for sport | hers | thin | high | 19 | 19 / 0 | 0.0047 | True | 03_01:0663, 06_01:0362 |
| Comes back to cuts and the infirmary | hers | thin | medium | 15 | 14 / 1 | 0.0032 | True | 01_01:4284, 01_01:4299 |
| Jokes against her own age | hers | weak | medium | 9 | 6 / 3 | 0.0003 | True | 06_01:0779, 06_01:0787 |
| Laughs it off with あはは / ふふ | hers | weak | medium | 23 | 21 / 2 | 0.0417 | False | 02_01:1223, 04_01:3200 |
| Wails at herself in a mock lament | hers | thin | medium | 15 | 9 / 6 | 0.0016 | True | 04_01:2992, 05_01:3661 |
| Apologizes at once | hers | thin | medium | 16 | 16 / 0 | 0.0083 | True | 01_01:4195, 02_01:1122 |
| Takes a thing in with なのね / ものね | hers | thin | medium | 34 | 22 / 12 | 0.0027 | True | 06_01:0333, 07_01:1533 |
| Plays the teacher card | hers | thin | medium | 10 | 6 / 4 | 0.0 | True | 05_01:3742, 08_02:0469 |

Mechanism split: class {'hers': 16}; tier {'firm': 5, 'thin': 9, 'weak': 2} (5 firm, 9 thin, 2 weak) over 557 spoken lines.

Non-distinctive from the control heroines: laughs_it_off.

Every mechanism is classed `hers`: the matchers in tools/koikano/b3/chisa.py were written from her own lines (found by contrasting her non-H lines with the other named speakers in her scenes), and each recurs across her scenes. Nothing was classed `author` or `moment`. The `distinctive` flag compares her rate with those speakers; the B4 gate re-tested it on the holdout. Tiers follow the mechanism tier rule (see tier_rule).

How each was counted, and the weak ones:

- **Calls the people in front of her by surname and さん / 君** (hers, firm, high, 168 line(s), share 0.3016; non-H 138 / H 30; control 0.0124, distinctive True): regex: one of the six names followed by さん, 君 or 会長. Nobody else in her scenes speaks this way: the heroines use first names, ちゃん or 先輩. 宮国君 is the player's name in her mouth; the world never writes his lines, it only has her say it.
- **Closes a line on a soft わ** (hers, firm, high, 113 line(s), share 0.2029; non-H 94 / H 19; control 0.0275, distinctive True): regex: the line ends on わ, わね, わよ or だわ before the final marks, or contains わよ or わね. The move that sets her apart from the students most plainly. Among the students the same ending is almost absent.
- **Explains or gives the reason with のよ / のね** (hers, firm, high, 85 line(s), share 0.1526; non-H 63 / H 22; control 0.0095, distinctive True): regex: contains のよ or のね. Explaining, not scolding. It carries her secrets too (保健室の常連なのよ).
- **Wonders aloud with かしら** (hers, thin, high, 27 line(s), share 0.0485; non-H 20 / H 7; control 0.0004, distinctive True): regex: contains かしら. A soft way to ask a student something. The control speakers almost never say it.
- **Calls herself 先生** (hers, firm, high, 51 line(s), share 0.0916; non-H 40 / H 11; control 0.0069, distinctive True): regex: 先生 followed by a particle or a comma. Also catches a few lines where it names another teacher (清水先生ったら is excluded by the particle list; 榎本先生は quoted by someone is not). A regex lower bound and slightly over-counts quoted uses. It is her role said aloud, to students, never to another adult.
- **Reaches for 青春** (hers, thin, high, 17 line(s), share 0.0305; non-H 14 / H 3; control 0.0007, distinctive True): regex: contains 青春. Close to hers alone: the control speakers say it almost never. It is warm and slightly wistful; it is also how she lets herself be moved.
- **Opens on あら** (hers, thin, medium, 17 line(s), share 0.0305; non-H 17 / H 0; control 0.0111, distinctive True): regex: contains あら. Mild surprise, not alarm. The unflustered first beat before she is flustered.
- **Slides into ちゃう / ちゃった** (hers, firm, high, 50 line(s), share 0.0898; non-H 39 / H 11; control 0.0096, distinctive True): regex: ちゃ or じゃ followed by う, った, って, っ, いそう or わ. Colloquial contraction, common in the cast, so the rate against the control matters, not the form. Hers runs high.
- **Reaches for sport** (hers, thin, high, 19 line(s), share 0.0341; non-H 19 / H 0; control 0.0047, distinctive True): regex: one of the sport and pool words. The one place the PE teacher shows in her speech as a habit. She gives advice as a coach: 試合はこれからなのっ.
- **Comes back to cuts and the infirmary** (hers, thin, medium, 15 line(s), share 0.0269; non-H 14 / H 1; control 0.0032, distinctive True): regex: one of the injury words or a cough. Her clumsiness is the secret she keeps (保健室の常連). Includes the stage coughs (けほっ, げほ).
- **Jokes against her own age** (hers, weak, medium, 9 line(s), share 0.0162; non-H 6 / H 3; control 0.0003, distinctive True): regex: one of the age words. Few lines, and no one else in her scenes makes this joke. Kept because it is the sorest point she lets show.
- **Laughs it off with あはは / ふふ** (hers, weak, medium, 23 line(s), share 0.0413; non-H 21 / H 2; control 0.0417, distinctive False): regex: contains one of the written laughs. Her rate is over the control's but not by much: others laugh in writing too. Her varieties (にしし, うくく, んっふっふ) are the part that is hers.
- **Wails at herself in a mock lament** (hers, thin, medium, 15 line(s), share 0.0269; non-H 9 / H 6; control 0.0016, distinctive True): regex: contains one of the lament sounds. The comic of a woman who is not as composed as she wants to look. Rare in lines, vivid when it comes.
- **Apologizes at once** (hers, thin, medium, 16 line(s), share 0.0287; non-H 16 / H 0; control 0.0083, distinctive True): regex: contains ごめんなさい, ごめんね or 申し訳. To students as readily as to colleagues. She does not hold a teacher's rank over the apology.
- **Takes a thing in with なのね / ものね** (hers, thin, medium, 34 line(s), share 0.061; non-H 22 / H 12; control 0.0027, distinctive True): regex: なのね, ものね, のよね, or のね at the line end. Used both in class (そうなのね) and in the H scene, where it is how she takes in what she is shown.
- **Plays the teacher card** (hers, thin, medium, 10 line(s), share 0.018; non-H 6 / H 4; control 0.0, distinctive True): regex: 先生 with だから, なんだから, として or だもの, or これでも先生, or えっへん. Pride in the role, said as if to convince herself. No control speaker says it.

## Bounds and the absent list

Emotional pressures (authored `@emotion` types): {'キラン': 2, '汗': 2, 'はてな': 1, 'びっくり': 1, 'ぽわぽわ': 1, 'キラキラ': 1, 'ハート02': 1}.

- expression vocabulary never on her lines: laugh, angry, cry, blush, embarrassed, serious, shy, other
- gesture macros in the corpus never hers: @なでなで, @ひざまずき, @キス, @キス止め, @主人公視点戻し, @外から飛び出し, @居眠り横, @居眠り縦, @息切れ, @抱きつき, @身体眺め
- on-screen cast absent from her scenes: none

### What B2 could not derive (the B3 residue)

- address terms for NPCs: Not derivable. The NPC speakers are not in charData.csv, so there is no name form to search her lines for. Only the eight named cast and the protagonist 一悟 have alias forms.
- relationships with no address term: 一悟, ひかる, 一年生女子, 文化祭実行委員, 野村先生
- rhetorical mechanisms deferred to B3: This list is the B2 residue, kept for provenance. B3 addressed it: see the `mechanisms` section. The B2 residue named deflects a topic, changes the subject, teases, jokes, stalls with repetition, or answers a question with a question - none of these carries an authored stage direction.
- trigger causality: Every trigger table is co-occurrence over her lines, not cause. The authored direction is a staging choice on the line; it does not say why.
- expression-label uncertainty: Expression triggers inherit the C4 hypothesis: a label on a line is the merged visual/context guess, not ground truth.
- tokenizer: The surface battery splits on punctuation (a class-based tokenizer), not morphology, so particles are matched by string suffix against a fixed list and the n-grams are character n-grams.
- room definition: The room is every other speaker in her scenes, named cast and NPCs together; the plan leaves this open.

## Spot check: one line carried through the layers

`01_01:4136` (scene 01_01, route common, channel spoken):

> 「いいじゃない、いいじゃない。ここは部室なんだから」

```json
{
  "expressions": [
    {
      "witness": "sprite",
      "id": "CF03A002M",
      "unit": "CF|A|002",
      "expression": "excited",
      "pose": "fists_up",
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
            "image": "png/parts/face/cf03a002F.png",
            "note": "closed eyes, open mouth; キラン/ぽわぽわ"
          },
          "context": {
            "label": "excited",
            "confidence": "explicit",
            "receipt": "01_01:4136",
            "note": "anchors: キラン x1, ぽわぽわ x1"
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
        "file": "CF03A002M"
      },
      "macro": null,
      "event_line": 4133,
      "conditional": false
    },
    {
      "kind": "gesture",
      "command": "@おじぎ",
      "args": {
        "id": "知紗",
        "action": "ActionAdvBow",
        "height": "10",
        "cycle": "500",
        "count": "2"
      },
      "macro": "おじぎ",
      "event_line": 4134,
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
