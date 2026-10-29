"""B3 reading for 知紗 (chisa): her own mechanisms, read off her lines.

Loaded by koikano_bible.mechanism_specs() for the subject 知紗. Same spec shape as
the default (百花) list. Every matcher is a regex over her spoken lines (the builder
strips the 「」 brackets first); each is a lower bound for a move defined by reading.
Receipts (scene:line) come from the builder, three per mechanism.

How the entries were found (2026-10-23, notebook docs/reports/2026-10-23_side_cast_notebook.md):
her 395 non-H spoken lines (the H scene 08_02 left out of the probe, so the list is about
the person, not the register) against the 10,329 spoken lines of the other named speakers
(百花, 真優, 千奈, アリス, 真里亜, ひかる, 一悟) in the scenes she speaks in: ending, opener and
3- to 5-character-gram contrast, then a hand list of candidate moves read off her lines. The
record is thin for her (557 spoken lines), so several moves are small; the tier rule says so.

Tier rule (the same one the 真優 pass used, applied by characters/chisa/b3_apply.py):
  firm  = lines >= 40 and her share is at least 2x the control share (control 0 counts)
  thin  = lines >= 10 and her share above the control share
  weak  = anything else (fewer than 10 lines, or a share at or under the control's)
The tier fields below are provisional; b3_apply.py sets them from the build counts and fails if one differs.
"""

MECHANISM_SPECS = [
    {
        "key": "calls_students_by_surname_and_san_kun",
        "name": "Calls the people in front of her by surname and さん / 君",
        "definition": "Puts the other person's family name and さん or 君 into the line (十川さん, 千代田さん, 七瀬さん, 宮国君, アリス会長), as a vocative or as a topic. A teacher's way of speaking to students.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"(?:十川|千代田|七瀬|宮国|真里亜|アリス)(?:さん|君|会長)",
        "method": "regex: one of the six names followed by さん, 君 or 会長.",
        "note": "Nobody else in her scenes speaks this way: the heroines use first names, ちゃん or 先輩. 宮国君 is the player's name in her mouth; the world never writes his lines, it only has her say it.",
    },
    {
        "key": "closes_on_wa",
        "name": "Closes a line on a soft わ",
        "definition": "Ends a statement on わ, わね, わよ or だわ, the grown woman's closing (そうね, 手伝うわ, 楽しみだわ).",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"(?:わ|わね|わよ|だわ)[。！？…っ]*$|わよ|わね",
        "method": "regex: the line ends on わ, わね, わよ or だわ before the final marks, or contains わよ or わね.",
        "note": "The move that sets her apart from the students most plainly. Among the students the same ending is almost absent.",
    },
    {
        "key": "explains_with_noyo",
        "name": "Explains or gives the reason with のよ / のね",
        "definition": "Closes a reason, a correction or a confidence on のよ or のね, gently, the way a teacher lays a thing out (総顧問を引き受けているの, 常連なのよ).",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"のよ|のね",
        "method": "regex: contains のよ or のね.",
        "note": "Explaining, not scolding. It carries her secrets too (保健室の常連なのよ).",
    },
    {
        "key": "wonders_with_kashira",
        "name": "Wonders aloud with かしら",
        "definition": "Turns a question into a mild, self-addressed wondering (どう、かしら？, 問題は解けてるかしら？).",
        "class": "hers", "tier": "thin", "confidence": "high",
        "pattern": r"かしら",
        "method": "regex: contains かしら.",
        "note": "A soft way to ask a student something. The control speakers almost never say it.",
    },
    {
        "key": "names_herself_sensei",
        "name": "Calls herself 先生",
        "definition": "Says 先生 of herself in the first person (先生も協力するわよ, 先生、相談に乗るわよ, 先生として), beside the 私 she also uses.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"先生(?:は|が|も|として|だって|、|ね|の|よ|に)|先生、|先生用",
        "method": "regex: 先生 followed by a particle or a comma. Also catches a few lines where it names another teacher (清水先生ったら is excluded by the particle list; 榎本先生は quoted by someone is not).",
        "note": "A regex lower bound and slightly over-counts quoted uses. It is her role said aloud, to students, never to another adult.",
    },
    {
        "key": "says_seishun",
        "name": "Reaches for 青春",
        "definition": "Names whatever the students are doing 青春 (青春だわ, 青春ね, 青春を昼ドラ化しないこと), her catchphrase for other people's youth.",
        "class": "hers", "tier": "thin", "confidence": "high",
        "pattern": r"青春",
        "method": "regex: contains 青春.",
        "note": "Close to hers alone: the control speakers say it almost never. It is warm and slightly wistful; it is also how she lets herself be moved.",
    },
    {
        "key": "opens_with_ara",
        "name": "Opens on あら",
        "definition": "Starts on あら, あらあら or あらっ at the sight of someone or something (あら、宮国君じゃない, あら、大変ね).",
        "class": "hers", "tier": "thin", "confidence": "medium",
        "pattern": r"あら",
        "method": "regex: contains あら.",
        "note": "Mild surprise, not alarm. The unflustered first beat before she is flustered.",
    },
    {
        "key": "contracts_with_chau",
        "name": "Slides into ちゃう / ちゃった",
        "definition": "Says a loss of control as ちゃう, ちゃった, ちゃって (張り切っちゃう, 感動しちゃったわ, 嬉しくなっちゃった): her feeling gets ahead of her.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"(?:ち|じ)ゃ(?:う|った|って|っ|いそう|わ)",
        "method": "regex: ちゃ or じゃ followed by う, った, って, っ, いそう or わ.",
        "note": "Colloquial contraction, common in the cast, so the rate against the control matters, not the form. Hers runs high.",
    },
    {
        "key": "reaches_for_sport",
        "name": "Reaches for sport",
        "definition": "Uses the gym, the pool or a game as her way of saying a thing (スリーポイント, リバウンド王, ゴール, ダンク, 短期戦, イエローカード, 始末書, ジョギング, 水中ウォーキング).",
        "class": "hers", "tier": "thin", "confidence": "high",
        "pattern": r"スリーポイント|リバウンド|シュート|ゴール|ダンク|試合|スポーツ|ジョギング|プール|体育|ウォーキング|短期戦|イエローカード|始末書",
        "method": "regex: one of the sport and pool words.",
        "note": "The one place the PE teacher shows in her speech as a habit. She gives advice as a coach: 試合はこれからなのっ.",
    },
    {
        "key": "comes_back_to_wounds",
        "name": "Comes back to cuts and the infirmary",
        "definition": "Brings up injuries, bandages, the first-aid kit or the infirmary (ケガ, 傷, 絆創膏, 救急セット, 保健室), mostly about herself, once about others.",
        "class": "hers", "tier": "thin", "confidence": "medium",
        "pattern": r"保健|ケガ|怪我|傷|絆創膏|救急|転ぶ|けほ|げほ",
        "method": "regex: one of the injury words or a cough.",
        "note": "Her clumsiness is the secret she keeps (保健室の常連). Includes the stage coughs (けほっ, げほ).",
    },
    {
        "key": "jokes_about_her_age",
        "name": "Jokes against her own age",
        "definition": "Turns on her age or her lack of a boyfriend with a laugh or a wail (大人げない, 年甲斐もなく, 彼氏いない歴イコール年齢, ジェネレーションギャップ).",
        "class": "hers", "tier": "weak", "confidence": "medium",
        "pattern": r"大人げ|年甲斐|年長|ジェネレーション|年って|大人だもの|年上|年下|彼氏いない|女の子って年|年齢",
        "method": "regex: one of the age words.",
        "note": "Few lines, and no one else in her scenes makes this joke. Kept because it is the sorest point she lets show.",
    },
    {
        "key": "laughs_it_off",
        "name": "Laughs it off with あはは / ふふ",
        "definition": "Covers a beat with a written laugh (あはは, ふふっ, にしし, うくく, んっふっふ) before going on.",
        "class": "hers", "tier": "weak", "confidence": "medium",
        "pattern": r"あはは|ふふ|フフ|にしし|うくく|んっふっふ",
        "method": "regex: contains one of the written laughs.",
        "note": "Her rate is over the control's but not by much: others laugh in writing too. Her varieties (にしし, うくく, んっふっふ) are the part that is hers.",
    },
    {
        "key": "mock_laments",
        "name": "Wails at herself in a mock lament",
        "definition": "Drops into a comic lament when a student misses her point (ううっ, よよよ, ぎくぅ, くぅうう).",
        "class": "hers", "tier": "thin", "confidence": "medium",
        "pattern": r"ううっ|よよよ|ぎくぅ|くぅうう|がぁあ",
        "method": "regex: contains one of the lament sounds.",
        "note": "The comic of a woman who is not as composed as she wants to look. Rare in lines, vivid when it comes.",
    },
    {
        "key": "apologizes_at_once",
        "name": "Apologizes at once",
        "definition": "Says ごめんなさい, ごめんね or 申し訳 the moment she has been loud, late or blunt (つい力が入ってしまって, 遅刻しちゃってごめんなさい).",
        "class": "hers", "tier": "thin", "confidence": "medium",
        "pattern": r"ごめんなさい|ごめんね|申し訳",
        "method": "regex: contains ごめんなさい, ごめんね or 申し訳.",
        "note": "To students as readily as to colleagues. She does not hold a teacher's rank over the apology.",
    },
    {
        "key": "confirms_with_nanone",
        "name": "Takes a thing in with なのね / ものね",
        "definition": "Repeats what she has just been told as a settled fact (そうなのね, ものなのね, 気持ちいいことなのね), a listening move that doubles as learning.",
        "class": "hers", "tier": "thin", "confidence": "medium",
        "pattern": r"(?:な|の|も)のね[。？…！]|ものね|なのね|のよね|のね[。？…！]*$",
        "method": "regex: なのね, ものね, のよね, or のね at the line end.",
        "note": "Used both in class (そうなのね) and in the H scene, where it is how she takes in what she is shown.",
    },
    {
        "key": "plays_the_teacher_card",
        "name": "Plays the teacher card",
        "definition": "Backs a claim with her job (これでも先生だからねっ, 先生なんだから, 先生だもの, えっへん).",
        "class": "hers", "tier": "thin", "confidence": "medium",
        "pattern": r"先生(?:だから|なんだから|として|だもの)|これでも先生|えっへん",
        "method": "regex: 先生 with だから, なんだから, として or だもの, or これでも先生, or えっへん.",
        "note": "Pride in the role, said as if to convince herself. No control speaker says it.",
    },
]
