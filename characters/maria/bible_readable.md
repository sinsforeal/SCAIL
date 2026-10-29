# koikano authored expression bible - 真里亜 (CG)

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
| her lines | 1228 |
| - spoken | 1228 |
| - inner voice | 0 |
| her scenes | 65 |
| room lines (others in her scenes) | 25209 |
| - room spoken | 14878 |
| - room inner | 10331 |

The scope's section 5.1 figure for 真里亜 is 2,781 lines, 211 inner and 70 scenes. This build reproduces all three.

## Voice: her dialogue, her inner voice, the room

`dispersion` is scene document frequency: the share of her scenes in which the n-gram appears. `distinctive` is the log-odds of the channel against the other two channels pooled.

| channel | lines | tokens | token types | TTR |
| --- | --- | --- | --- | --- |
| her dialogue | 1228 | 4004 | 2588 | 0.6464 |
| her inner voice | 0 | 0 | 0 | 0.0 |
| the room (spoken) | 14878 | 40989 | 23277 | 0.5679 |

Distinctive tokens (log-odds, top 12):

- **her_dialogue**: 宮国様 (90), お嬢様 (120), うふふ (79), かしこまりました (21), 千奈様 (15), うふふふふ (14), ですわ (12), アリス様 (9), うふふっ (8), お嬢様は (8), そうですわね (8), 申し訳ありません (8)
- **her_inner**: Sorry (0), Will (0), cake (0), have (0), havesome (0), sinA (0), you (0), ―――― (0), ――――っ (0), ――え (0), ――この帯の文句を考えたのは一悟くんだそうだね (0), ――と (0)
- **the_room**: 一悟 (356), そ (251), え (190), いや (170), 百花 (169), 真優 (164), うん (147), い (141), 百花ちゃん (139), それじゃあ (107), ナタリー (100), みゃー先輩 (96)

### B2 surface: turn length, line-final, punctuation, self-reference

Turn length, kept characters per line (shares are in `bible.json`):

| channel | 1-5 | 6-10 | 11-20 | 21-40 | 41-80 | 81+ | mean | median | p90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| her_spoken | 34 | 54 | 249 | 692 | 194 | 0 | 28.01 | 29 | 43 |
| her_inner | 0 | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| the_room_spoken | 1751 | 1904 | 4156 | 5914 | 943 | 0 | 20.13 | 19 | 38 |

Line-final morphemes, string suffixes of the kept text (top 10):

- **her spoken last token**: お嬢様 28, 宮国様 26, っ 16, 真優様 11, ありがとうございます 9, うふふふふ 9, ふふふっ 7, ふふっ 6, うふふ 5, 千奈様 5
- **her spoken 2-char suffix**: すわ 171, ます 84, です 76, から 55, すか 54, ませ 53, すね 47, した 43, ょう 41, わね 38
- **her inner last token**: -
- **her inner 2-char suffix**: -

Line-final particles, matched by suffix against a fixed list (top 10 by spoken lines):

| ending | spoken lines | spoken share | inner lines | inner share |
| --- | --- | --- | --- | --- |
| わ | 192 | 0.1564 | 0 | 0.0 |
| ね | 139 | 0.1132 | 0 | 0.0 |
| か | 97 | 0.079 | 0 | 0.0 |
| っ | 84 | 0.0684 | 0 | 0.0 |
| から | 55 | 0.0448 | 0 | 0.0 |
| よ | 29 | 0.0236 | 0 | 0.0 |
| ん | 15 | 0.0122 | 0 | 0.0 |
| のね | 13 | 0.0106 | 0 | 0.0 |
| よね | 11 | 0.009 | 0 | 0.0 |
| のに | 6 | 0.0049 | 0 | 0.0 |

Punctuation, full-width marks:

| mark | spoken count | spoken/line | inner count | room/line |
| --- | --- | --- | --- | --- |
| … | 1736 | 1.4137 | 0 | 1.0602 |
| ！ | 100 | 0.0814 | 0 | 0.1611 |
| ？ | 172 | 0.1401 | 0 | 0.2968 |
| 、 | 1572 | 1.2801 | 0 | 1.0083 |
| 。 | 483 | 0.3933 | 0 | 0.3482 |
| ー | 88 | 0.0717 | 0 | 0.1475 |
| ～ | 0 | 0.0 | 0 | 0.0056 |
| 「 | 1223 | 0.9959 | 0 | 0.9963 |

Self-reference: spoken 真里亜 2 occurrences on 2 lines; spoken 私 159 occurrence(s) on 156 line(s); inner 真里亜 0 occurrence(s) on 0 line(s).

- **her dialogue vs the room, tokens**: 宮国様 (90), お嬢様 (120), うふふ (79), かしこまりました (21), 千奈様 (15), うふふふふ (14), ですわ (12), アリス様 (9), うふふっ (8), お嬢様は (8)
- **her dialogue vs the room, bigrams**: 国様 (204), 奈様 (69), ス様 (41), お嬢 (268), 嬢様 (268), 様お (34), 優様 (71), をご (22)
- **her dialogue vs her inner, tokens**: お嬢様 (120), 宮国様 (90), うふふ (79), あら (47), ふふっ (44), ええ (41), ふふふ (39), ふふ (33), あらあら (25), ありがとうございます (24)
- **her dialogue vs her inner, bigrams**: です (725), ます (421), すわ (407), いま (342), ふふ (321), お嬢 (268), 嬢様 (268), って (243)

## Expressions (C4 hypotheses)

The repertoire is her own faces only (message face or sprite tag carrying the `CG` prefix). Confidence is carried from `expression_labels.json`.

| expression | her lines | confidence split |
| --- | --- | --- |
| smile | 535 | {'clear': 237, 'inferred': 72, 'ambiguous': 226} |
| neutral | 210 | {'clear': 185, 'ambiguous': 25} |
| surprise | 36 | {'ambiguous': 25, 'clear': 11} |
| sad | 11 | {'inferred': 11} |

### Expression triggers (all eight labels)

One row per label. `lines` is her lines carrying it (a line with two faces counts once here; the repertoire counts occurrences). `with` is the speaker whose turn preceded hers; `(none)` is a scene-opening or unattributed turn. `preceded by` is the last expression she wore earlier in the scene; `co-gesture` is the gesture on the same line. Co-occurrence, not cause.

| expression | lines | with | route | H/normal | mean chars | preceded by | co-gesture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smile | 505 | 一悟 193, 百花 145, 真優 52 | common 238, d 102, a 65 | normal 505 | 25.74 | smile 314, neutral 137, (scene-start) 37 | @おじぎ 111, @ううっ 56, @否定 27 |
| neutral | 207 | 一悟 96, 百花 45, 千奈 25 | common 105, d 39, a 24 | normal 207 | 28.89 | smile 126, neutral 55, surprise 12 | @おじぎ 29, @否定 11, @ううっ 7 |
| surprise | 34 | 一悟 17, 百花 10, アリス 2 | common 23, d 7, c 2 | normal 34 | 21.38 | smile 13, surprise 12, neutral 7 | @ジャンプ 5, @おじぎ 4, @否定 1 |
| sad | 11 | 一悟 4, アリス 3, 百花 2 | d 6, common 3, a 2 | normal 11 | 33.0 | smile 7, surprise 3, neutral 1 | @おじぎ 2, @否定 2 |

## Gestures

| gesture | her lines |
| --- | --- |
| @おじぎ | 185 |
| @ううっ | 86 |
| @否定 | 50 |
| @ジャンプ | 7 |
| @噴飯１ | 2 |
| @身体眺め | 1 |

Entry/exit: {'enter': 15}. Camera (targeted): {'@focus': 2}. Emotion overlays: {'キラキラ': 3, 'キラン': 1, '汗': 1}. Action commands (occurrences): {'@char': 958, '@focus': 8, '@action': 7, '@move': 6}.

### Gesture triggers

One row per gesture. `co-face` is the C4 label on the same line; `preceded by` is the last label earlier in the scene; the other columns as above.

| gesture | lines | with | route | H/normal | mean chars | co-face | preceded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| @おじぎ | 185 | 一悟 76, 百花 45, アリス 21 | common 75, d 48, a 24 | H 3, normal 182 | 24.59 | smile 117, neutral 29, surprise 4 | smile 86, (scene-start) 54, neutral 37 |
| @ううっ | 86 | 一悟 39, 百花 18, 真優 11 | common 41, d 20, b 13 | H 3, normal 83 | 24.27 | smile 59, neutral 7 | smile 47, (scene-start) 21, neutral 16 |
| @否定 | 50 | 一悟 22, 百花 13, アリス 8 | common 19, d 13, a 8 | H 1, normal 49 | 29.66 | smile 31, neutral 11, sad 2 | smile 29, (scene-start) 11, neutral 9 |
| @ジャンプ | 7 | 一悟 3, ひかる 1, アリス 1 | d 4, common 2, c 1 | normal 7 | 12.14 | surprise 5, smile 1 | neutral 3, smile 3, (scene-start) 1 |
| @噴飯１ | 1 | 一悟 1 | common 1 | normal 1 | 24.0 | neutral 1, smile 1 | neutral 1 |
| @身体眺め | 1 | 一悟 1 | common 1 | normal 1 | 4.0 | smile 1 | smile 1 |

### Emotion, entry/exit and action triggers

| trigger | lines | with | H/normal | co-face |
| --- | --- | --- | --- | --- |
| emotion キラキラ (lines) | 3 | 一悟 2, 千奈 1 | normal 3 | smile 2 |
| emotion キラン (lines) | 1 | 一悟 1 | normal 1 | smile 1 |
| emotion 汗 (lines) | 1 | 百花 1 | normal 1 | - |
| enter/exit enter (lines) | 15 | 一悟 6, 百花 6 | normal 15 | smile 7, neutral 4 |
| action @char (lines) | 843 | 一悟 340, 百花 220 | H 15, normal 828 | smile 466, neutral 181 |
| action @focus (lines) | 2 | 一悟 1, 百花 1 | H 1, normal 1 | smile 1 |
| action @action (lines) | 2 | 百花 2 | normal 2 | smile 2 |
| action @move (lines) | 1 | 千奈 1 | normal 1 | smile 1 |

## Interactions (per relationship)

| speaker | kind | turns | spoken | inner | scenes | her turns | her avg chars | her med chars | exch. her-start | exch. their-start | her expression mix | her gestures | her address |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 一悟 | protagonist | 15077 | 5647 | 9430 | 64 | 478 | 27.53 | 29 | 1 | 331 | smile 197, neutral 98, surprise 18, sad 4 | @おじぎ 76, @ううっ 39, @否定 22 | 一悟様 1 |
| 千奈 | heroine | 2703 | 2303 | 400 | 59 | 88 | 26.74 | 27 | 0 | 59 | smile 47, neutral 25, surprise 2 | @おじぎ 15, @ううっ 6, @ジャンプ 1 | 千奈様 20 |
| 真優 | heroine | 2496 | 2246 | 250 | 59 | 89 | 26.0 | 27 | 0 | 18 | smile 59, neutral 15, sad 2, surprise 2 | @おじぎ 14, @ううっ 11, @否定 4 | 真優様 24 |
| 百花 | heroine | 2044 | 1833 | 211 | 61 | 342 | 27.64 | 28 | 0 | 102 | smile 153, neutral 46, surprise 11, sad 2 | @おじぎ 45, @ううっ 18, @否定 13 | 千代田 7, 千代田百花 1, 百花 1 |
| アリス | heroine | 1689 | 1650 | 39 | 50 | 82 | 29.71 | 31 | 0 | 88 | smile 52, neutral 18, sad 3, surprise 2 | @おじぎ 21, @否定 8, @ううっ 7 | アリス様 13 |
| 知紗 | heroine | 540 | 540 | 0 | 36 | 136 | 31.55 | 32 | 0 | 15 | smile 19, neutral 6, surprise 1 | @おじぎ 11, @ううっ 5, @否定 1 | 榎本先生 24, 榎本 1 |
| ひかる | heroine | 401 | 401 | 0 | 35 | 7 | 26.29 | 25 | 0 | 14 | smile 4, neutral 1 | @おじぎ 2, @否定 2, @ジャンプ 1 | 小野坂様 2 |
| ケルベロス | heroine | 139 | 139 | 0 | 30 | 5 | 36.0 | 37 | 0 | 3 | smile 4, neutral 1 | @おじぎ 1 | - |
| 天文部部員 | npc | 30 | 30 | 0 | 5 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| ＡＶ女優 | npc | 9 | 9 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 一年生女子 | npc | 8 | 8 | 0 | 3 | 0 | 0.0 | 0 | 0 | 1 | - | - | - |
| 新聞部部長 | npc | 8 | 8 | 0 | 3 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 事務所の社長さん | npc | 7 | 7 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 文化祭実行委員 | npc | 6 | 6 | 0 | 3 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| テニス部部員 | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 弱小部女子生徒Ａ | npc | 5 | 5 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 弱小部女子生徒Ｂ | npc | 5 | 5 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 見知らぬ女性Ａ | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 見知らぬ女性Ｂ | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 野村先生 | npc | 5 | 5 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 三年生女子 | npc | 3 | 3 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 映画研究部部長 | npc | 3 | 3 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 野球部部員 | npc | 3 | 3 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 案内アナウンス | npc | 2 | 2 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 演劇部部員Ｂ | npc | 2 | 2 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 真優＆千奈 | unison | 2 | 2 | 0 | 2 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
|  | unattributed | 1 | 0 | 1 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 千奈＆アリス＆百花＆ひかる＆真里亜＆知紗 | unison | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 演劇部部員Ａ | npc | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 演劇部部員Ｃ | npc | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 百花＆真里亜 | unison | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 真優＆千奈＆一悟 | unison | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |
| 芸能記者 | npc | 1 | 1 | 0 | 1 | 0 | 0.0 | 0 | 0 | 0 | - | - | - |

Scene openings across her scenes: 一悟 25, 百花 12, 真優 9, 千奈 8, アリス 6, ひかる 3, 案内アナウンス 1, 真里亜 1.

Reply vs initiation (her spoken turns): replies 1033, initiations 1, self-continuations 194, reply rate 0.999.

### Address terms

How she names the other party, derived from her lines whose preceding speaker is that party. Overall: {"榎本先生":24,"真優様":24,"千奈様":20,"アリス様":13,"千代田":7,"小野坂様":2,"一悟様":1,"千代田百花":1,"榎本":1,"百花":1}.

B1 built the alias table from charData.csv, which holds only the eight named cast. The protagonist 一悟 is absent, so B1 reported no address term for him; B2 adds 一悟 to the alias table here only. The interaction layer on disk is unchanged.

Relationships where no name term is derivable from her lines: ケルベロス.

## Speech guide

Each rule carries a class (hers / the author's / a moment), a tier (firm / thin / weak, see tier_rule in bible.json), a `register` (all / H / non-H / per-register) and an evidence flag (measured / inferred). The receipt is the count or the lines the rule comes from; the example lines are in `bible.json`. Rules whose value differs by register state both.

| rule | class | tier | register | evidence | receipt |
| --- | --- | --- | --- | --- | --- |
| Call yourself 私: 159 times on 156 of 1228 spoken lines (H 48 lines, non-H 108). Your own name 真里亜 is said of yourself twice, so you are not a third-person talker. | hers | firm | all | measured | {"spoken_lines_with_私":156,"spoken_occurrences_私":159,"spoken_lines_with_真里亜":2,"spoken_occurrences_真里亜":2,"私_by_register":{"H":{… |
| Keep turns medium: median 29 kept characters pooled (non-H 28, H 32), no line over 60. | hers | firm | per-register | measured | {"non_H":{"lines":933,"median_chars":28,"mean_chars":26.89,"max_chars":55},"H":{"lines":295,"median_chars":32,"mean_chars":31.56,… |
| Reply; do not open. 1033 of her turns answer someone and 1 opens a scene (reply rate 0.999); 194 more continue her own turn. | hers | firm | all | measured | {"reply":1033,"initiation":1,"self_continuation":194,"reply_rate":0.999} |
| A glottal っ ending is an H habit: 84 lines end on っ, 74 of them in H (of 295 H lines) and 10 outside it (of 933). | hers | firm | per-register | measured | {"lines_ending_っ":84,"share_of_spoken":0.0684,"by_register":{"H":{"lines":74,"n":295},"non_H":{"lines":10,"n":933}}} |
| Do not stretch the last syllable with ー: 0 spoken lines end on ー. | hers | weak | all | measured | {"lines_ending_ー":0,"share_of_spoken":0.0,"by_register":{"H":{"lines":0,"n":295},"non_H":{"lines":0,"n":933}}} |
| Hum with ん only in H: んっ 24 and んん 5, all of them in H scenes and none outside; んんっ 11 more. | hers | thin | H | measured | {"token_んん":5,"token_んーん":0,"token_んっ":24,"token_んんっ":11,"token_んん_by_register":{"H":5,"non_H":0},"token_んっ_by_register":{"H":24,… |
| Do not show delight with おおー / おー: 0 lines carry either. | hers | weak | all | measured | {"token_おおー":0,"token_おー":0,"token_おおー_by_register":{"H":0,"non_H":0},"token_おー_by_register":{"H":0,"non_H":0}} |
| Childish words are not her habit: 6 spoken lines match any of いっぱい, きちゃう, えへへ (いっぱい 2, きちゃう 0, えへへ 0). | hers | weak | all | measured | {"token_いっぱい":2,"token_きちゃう":0,"token_えへへ":0,"lines_matched":6,"by_register":{"H":{"lines":4,"n":295},"non_H":{"lines":2,"n":933}… |
| Speak polite: です or ます is on 894 of 1228 spoken lines (1146 tokens), with everyone and in H scenes too. Polite is her base register, not an exception. | hers | firm | all | measured | {"lines_with_です_ます":894,"of_spoken_lines":1228,"token_ですます_occurrences":1146} |
| Ellipsis runs 0.5445 … per line outside H (508) and 4.1627 inside H (1228, moan elongation); the room runs at 1.0602 per line. | hers | firm | per-register | measured | {"…_by_register":{"H":{"count":1228,"per_line":4.1627},"non_H":{"count":508,"per_line":0.5445}},"spoken_lines":1228,"room_per_lin… |
| Outside H she asks (？ 119 times, 0.1275 per line) and rarely exclaims (！ 17, 0.0182 per line); in H ！ rises to 83 (0.2814 per line) and ？ is 53. | hers | firm | per-register | measured | {"！_by_register":{"H":{"count":83,"per_line":0.2814},"non_H":{"count":17,"per_line":0.0182}},"？_by_register":{"H":{"count":53,"pe… |
| Smile is her common face outside H: 505 of 933 lines carry one, and 535 of her 792 face hits are smile. H scenes carry no face (0 of 295). | hers | firm | non-H | measured | {"smile_occurrences":535,"all_occurrences":792,"smile_lines":505,"smile_lines_by_register":{"H":{"lines":0,"n":295},"non_H":{"lin… |
| Bow (@おじぎ) on 185 lines, 182 of them outside H and 117 with a smile. | hers | firm | non-H | measured | {"@おじぎ_occurrences":185,"lines":185,"by_register":{"H":{"lines":3,"n":295},"non_H":{"lines":182,"n":933}},"co_smile":117} |
| When refusing, @否定 (50 lines, 49 outside H); 31 of them go with a smile and 2 with a sad face. | hers | firm | non-H | measured | {"@否定_occurrences":50,"by_register":{"H":{"lines":1,"n":295},"non_H":{"lines":49,"n":933}},"co_smile":31,"co_sad":2} |
| Jump (@ジャンプ) is rare for her: 7 lines, all outside H, 5 of them with surprise. | hers | weak | non-H | measured | {"@ジャンプ_occurrences":7,"by_register":{"H":{"lines":0,"n":295},"non_H":{"lines":7,"n":933}},"co_surprise":5,"co_laugh":0} |
| She has no inner voice in the record (0 inner lines). Do not write inner narration for her. | hers | weak | all | measured | {"inner_lines":0,"inner_median_chars":0,"inner_ttr":0.0,"spoken_ttr":0.6464,"inner_lines_ending_っ":0,"inner_lines_H":0} |
| Non-H lines carry a face on 0.7663 (715 of 933) and a gesture on 0.3462 (323); H scenes carry a face on 0.0 and a gesture on 0.0237 (7 of 295). | author | firm | per-register | measured | {"non_H":{"lines":933,"with_expression":715,"with_gesture":323,"expression_rate":0.7663,"gesture_rate":0.3462},"H":{"lines":295,"… |
| @emotion overlays are rare: 5 lines in all (キラキラ 3, キラン 1, 汗 1). They are authored colour, not her mood words. | author | weak | all | measured | {"lines_with_emotion":5,"types":{"キラキラ":3,"キラン":1,"汗":1}} |
| Treat every expression label as a C4 hypothesis (vocabulary 0.2) with a confidence, not a fact. The receipt 8/16 is a project-level figure shared by every subject, not a measure of her. | author | weak | all | inferred | {"vocabulary_version":"0.2","her_units_agreed":"8/16 classifiable (see docs/koikano-expression-labels.md)"} |
| @おじぎ is the most common gesture corpus-wide (1576 calls), so her 185 bows are partly a house convention and not a trait of hers. | author | weak | all | inferred | {"corpus_@おじぎ_calls":1576,"her_@おじぎ":185} |
| Kiss gestures (@キス, @キス止め) are never hers: 0 lines. | moment | weak | all | measured | {"kiss_lines":0,"with_一悟":0,"route_own":0} |
| Dozing gestures (@居眠り横 / @居眠り縦) are never hers: 0 lines. | moment | weak | all | measured | {"lines":0,"with_一悟":0,"routes":{}} |
| The H-scene vocabulary (せーえき, おちんちん, おまんこ, きちゃう) stays inside H scenes: 45 lines there, 0 outside. | moment | thin | H | measured | {"lines_with_H_tokens":45,"in_H_scenes":45,"in_non_H":0,"h_scenes":2} |
| Laugh faces are never hers: 0 lines carry one. Her laugh is written into the text instead (うふふ, ふふ). | moment | weak | all | measured | {"laugh_lines":0,"with_@ジャンプ":0,"by_register":{"H":{"lines":0,"n":295},"non_H":{"lines":0,"n":933}}} |
| Voice her as a composed, polite maid: ladylike endings (ですわ, ますわ), a title for everyone (お嬢様 for 百花, 宮国様 for 一悟), soft laughter, medium-length turns, and she replies far more than she opens. Not cheerful or childlike, and not self-named. | hers | firm | all | inferred | {"non_H":{"median_chars":28,"ellipsis_per_line":0.5445},"H":{"median_chars":32,"ellipsis_per_line":4.1627},"third_person_lines":1… |

Rule split: class {'author': 4, 'hers': 17, 'moment': 4}; tier {'firm': 12, 'thin': 2, 'weak': 11}; register {'H': 1, 'all': 8, 'non-H': 8, 'per-register': 8}; evidence {'inferred': 3, 'measured': 22}. Unreceipted rules: none.

## Rhetorical mechanisms (B3)

These are the recurring moves in her speech that carry no `@emotion` / `@face` / `@action` - the B2 residue. They are **this builder's reading**, not the author's: the definitions, the class and the tier are interpretive; the line counts come from the fixed matcher named in each `method`, and the receipts are real lines. The surface rules they lean on are measured separately in `speech_guide` and `voice.surface`; this section adds the move, not the mark. A regex count is a lower bound where the move is defined by reading.

| mechanism | class | tier | confidence | lines | non-H / H | control rate | distinctive | receipts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Frames the turn with the listener's title | hers | firm | high | 473 | 395 / 78 | 0.0023 | True | 01_01:3435, 01_01:3478 |
| Uses fixed service formulas | hers | firm | high | 80 | 77 / 3 | 0.0013 | True | 01_01:3466, 01_01:3478 |
| Offers to do or carry it | hers | firm | high | 52 | 47 / 5 | 0.001 | True | 03_01:1170, 03_01:1747 |
| Closes the clause with わ | hers | firm | high | 369 | 250 / 119 | 0.0016 | True | 01_01:3478, 01_01:4379 |
| Opens with あら / まあ | hers | firm | high | 95 | 76 / 19 | 0.0041 | True | 01_01:3583, 01_01:4330 |
| Laughs softly in the text | hers | firm | high | 231 | 149 / 82 | 0.0232 | True | 01_01:4367, 01_01:4391 |
| Reminds them of what was said or arranged | hers | weak | medium | 6 | 4 / 2 | 0.0001 | True | 01_01:3583, 08_02:0129 |
| Frames herself as the maid | hers | thin | high | 31 | 23 / 8 | 0.0004 | True | 03_01:2399, 03_01:2420 |
| Directs with くださいませ / てください | hers | firm | high | 128 | 73 / 55 | 0.0093 | True | 02_01:0426, 02_01:5236 |
| Gives an opinion hedged and polite | hers | thin | medium | 43 | 38 / 5 | 0.003 | True | 02_01:5558, 03_01:3006 |
| Praises a person | hers | thin | high | 45 | 33 / 12 | 0.0114 | True | 03_01:1973, 04_01:1539 |
| Blames herself in set terms | hers | thin | medium | 17 | 14 / 3 | 0.0026 | True | 04_01:2295, 08_02:2242 |
| Teases gently | hers | weak | medium | 6 | 5 / 1 | 0.0022 | True | b03_01:1117, b04_01:0862 |
| Answers yes or no first | hers | firm | high | 75 | 63 / 12 | 0.0133 | True | 01_01:3466, 01_01:3610 |

Mechanism split: class {'hers': 14}; tier {'firm': 8, 'thin': 4, 'weak': 2} (8 firm, 4 thin, 2 weak) over 1228 spoken lines.

Non-distinctive from the control heroines: none.

Every mechanism is classed `hers`: the matchers in tools/koikano/b3/maria.py were written from her own lines, and each recurs across her scenes. Nothing was classed `author` or `moment`. The `distinctive` flag compares her rate with the other heroines in her scenes; the B4 gate re-tested it on the holdout. Tiers follow one count rule (see tier_rule): firm 50 lines or more, thin 10 to 49, weak under 10 or not distinctive.

How each was counted, and the weak ones:

- **Frames the turn with the listener's title** (hers, firm, high, 473 line(s), share 0.3852; non-H 395 / H 78; control 0.0023, distinctive True): regex: one of お嬢様 / 宮国様 / 真優様 / 千奈様 / アリス様 / 小野坂様 / 榎本先生 / ご主人様 / 奥様 within the first 10 or the last 12 characters. How she addresses people. 宮国様 is 一悟 (the record gives him the family name; she does not say 一悟).
- **Uses fixed service formulas** (hers, firm, high, 80 line(s), share 0.0651; non-H 77 / H 3; control 0.0013, distinctive True): regex: 失礼いたし / かしこまり / 承知 / させていただ / お待ちしており / 恐縮 / 僭越 / お手伝い / ご案内いたし / お届け / お持ちし. Formulas, so repetition is the point. Exact repeats such as 「失礼いたします」 appear 4 times.
- **Offers to do or carry it** (hers, firm, high, 52 line(s), share 0.0423; non-H 47 / H 5; control 0.001, distinctive True): regex: いたしましょうか / いたしますわ / いたしますね / お支え / お守り / お任せ / お力になり / させてくださ / ご用意いたし / 私がいたし. The service stance as a move. A lower bound: offers phrased another way are not caught.
- **Closes the clause with わ** (hers, firm, high, 369 line(s), share 0.3005; non-H 250 / H 119; control 0.0016, distinctive True): regex: です / ます / ません / でした / ました / ですの / たい / ない / ある / いる followed by わ and no further kana. A surface habit, counted here because it is the commonest ending she has. ですわ alone ends 83 lines.
- **Opens with あら / まあ** (hers, firm, high, 95 line(s), share 0.0774; non-H 76 / H 19; control 0.0041, distinctive True): regex: line starts (after leading …) with あら / あらあら / まあ / まぁ. Often the lead-in to a gentle correction or a tease.
- **Laughs softly in the text** (hers, firm, high, 231 line(s), share 0.1881; non-H 149 / H 82; control 0.0232, distinctive True): regex: うふふ / ふふ / くすくす / あはは / うふっ anywhere in the line. Sound, not words, but it recurs across her scenes and relationships.
- **Reminds them of what was said or arranged** (hers, weak, medium, 6 line(s), share 0.0049; non-H 4 / H 2; control 0.0001, distinctive True): regex: 仰っていた / おっしゃっていた anywhere, or 先日 / 先ほど / 昨日 / さっき followed in the same sentence by ではないですか / ではありませんか / でしたよね / ましたよね. How she corrects without contradicting: she cites the person's own words.
- **Frames herself as the maid** (hers, thin, high, 31 line(s), share 0.0252; non-H 23 / H 8; control 0.0004, distinctive True): regex: メイド anywhere in the line. Includes lines that name another person's maid. Read the receipts.
- **Directs with くださいませ / てください** (hers, firm, high, 128 line(s), share 0.1042; non-H 73 / H 55; control 0.0093, distinctive True): regex: くださいませ / てください / ていただけ / いただけませんか / してみて / なさって / ご覧ください. The same form carries service talk (ご安心くださいませ) and, in the H scenes, instruction to お嬢様.
- **Gives an opinion hedged and polite** (hers, thin, medium, 43 line(s), share 0.035; non-H 38 / H 5; control 0.003, distinctive True): regex: かと思います / かもしれません / ではないでしょうか / と思いますわ / ように思います / ように思えます / line-final でしょうか. Opinion without pushing it.
- **Praises a person** (hers, thin, high, 45 line(s), share 0.0366; non-H 33 / H 12; control 0.0114, distinctive True): regex: さすが / 素敵 / 素晴らし / お見事 / 立派 / 頼もしい / 凛々しい / 感服 / 感動. Praise of things (a play, a plan) is included. Read the receipts.
- **Blames herself in set terms** (hers, thin, medium, 17 line(s), share 0.0138; non-H 14 / H 3; control 0.0026, distinctive True): regex: 申し訳 / 失態 / 失格 / 不手際 / ご無礼 / お詫び / 至らな. Thin by count; kept because it is the one place she names her own failing.
- **Teases gently** (hers, weak, medium, 6 line(s), share 0.0049; non-H 5 / H 1; control 0.0022, distinctive True): regex: いけず / つれない / おとぼけ / 意地悪 / いじわる / お人が悪い / 悪戯 / いたずら / からかい. A lower bound: her teasing often has no marker word.
- **Answers yes or no first** (hers, firm, high, 75 line(s), share 0.0611; non-H 63 / H 12; control 0.0133, distinctive True): regex: line starts with はい / ええ / いいえ / いえ followed by 、 。 … or ！. A reply move; she answers far more than she starts.

## Bounds and the absent list

Emotional pressures (authored `@emotion` types): {'キラキラ': 3, 'キラン': 1, '汗': 1}.

- expression vocabulary never on her lines: laugh, angry, cry, blush, embarrassed, worried, serious, shy, excited, talk, other
- gesture macros in the corpus never hers: @なでなで, @ひざまずき, @キス, @キス止め, @主人公視点戻し, @噴飯２, @外から飛び出し, @居眠り横, @居眠り縦, @息切れ, @抱きつき
- on-screen cast absent from her scenes: none

### What B2 could not derive (the B3 residue)

- address terms for NPCs: Not derivable. The NPC speakers are not in charData.csv, so there is no name form to search her lines for. Only the eight named cast and the protagonist 一悟 have alias forms.
- relationships with no address term: ケルベロス
- rhetorical mechanisms deferred to B3: This list is the B2 residue, kept for provenance. B3 addressed it: see the `mechanisms` section. The B2 residue named deflects a topic, changes the subject, teases, jokes, stalls with repetition, or answers a question with a question - none of these carries an authored stage direction.
- trigger causality: Every trigger table is co-occurrence over her lines, not cause. The authored direction is a staging choice on the line; it does not say why.
- expression-label uncertainty: Expression triggers inherit the C4 hypothesis: a label on a line is the merged visual/context guess, not ground truth.
- tokenizer: The surface battery splits on punctuation (a class-based tokenizer), not morphology, so particles are matched by string suffix against a fixed list and the n-grams are character n-grams.
- room definition: The room is every other speaker in her scenes, named cast and NPCs together; the plan leaves this open.

## Spot check: one line carried through the layers

`01_01:3435` (scene 01_01, route common, channel spoken):

> 「おはようございます。宮国様、千奈様」

```json
{
  "expressions": [
    {
      "witness": "sprite",
      "id": "CG02B006M",
      "unit": "CG|B|006",
      "expression": "smile",
      "pose": "none",
      "source": "visual",
      "hypothesis": {
        "confidence": "clear",
        "agreement": "disputed",
        "winner": "vision",
        "version": "0.2",
        "provenance": {
          "visual": {
            "label": "smile",
            "confidence": "clear",
            "image": "png/parts/face/cg02b006F.png",
            "note": "closed eyes, open mouth"
          },
          "context": {
            "label": "neutral",
            "confidence": "weak",
            "receipt": "03_01:1731",
            "note": "plain dialogue; no @emotion anchor"
          }
        }
      }
    }
  ],
  "actions": [
    {
      "kind": "enter",
      "command": "@enter",
      "args": {
        "file": "CG02B006M",
        "x": "300",
        "right": "100"
      },
      "macro": null,
      "event_line": 3431,
      "conditional": false
    },
    {
      "kind": "gesture",
      "command": "@おじぎ",
      "args": {
        "id": "真里亜",
        "action": "ActionAdvBow",
        "height": "10",
        "cycle": "500",
        "count": "1"
      },
      "macro": "おじぎ",
      "event_line": 3433,
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
