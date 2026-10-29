"""B3 reading for アリス (alice). Loaded by koikano_bible.mechanism_specs() when the subject is アリス.

Read off her own lines (2,792 spoken, 59 scenes) and a log-odds read of her character
n-grams against the other named heroines in her scenes, not off 百花's list. Every
spec runs on her spoken lines through _mech_strip (the 「」 are removed first), so
"^" is the start of the line. All patterns are regex; there are no function matchers,
so MATCHERS is empty. The class is "hers" for the draft; tier and distinctive are
set by the tool from the counts, and the tier is re-applied by the fixed rule in
characters/alice/B3_tiers.py after the gate (firm / thin / weak from the counts).

The definitions and the classing are the builder's reading. The counts and receipts
(scene:line, first three in scene order) are mechanical. A regex is a lower bound
where the move is defined by reading.
"""

MATCHERS = {}


def _spec(key, name, definition, pattern, method, note, conf="medium"):
    return {
        "key": key,
        "name": name,
        "definition": definition,
        "class": "hers",
        "tier": "thin",       # placeholder; re-applied from the counts by B3_tiers.py
        "confidence": conf,
        "pattern": pattern,
        "method": method,
        "note": note,
    }


MECHANISM_SPECS = [
    _spec(
        "asks_with_kai",
        "Asks in the soft masculine form, かい / んだい",
        "Closes a question on かい, のかい or んだい, the courteous older-sibling question (どうしたんだい？, 大丈夫かい？).",
        r"(かい|だい)[？]",
        "regex: かい or だい immediately before ？ (the 〜かい？ and 〜んだい？ endings).",
        "Her ordinary way to ask. The form is plain in her lines, e.g. 01_01:1117 and 01_01:1240.",
        "high",
    ),
    _spec(
        "half_questions_with_kana",
        "Turns a statement into a half-question with かな",
        "Ends a claim or an offer on かな, asking and asserting at once (気のせいかな？, 〜でもいいかな？).",
        r"かな[。！？…]*$",
        "regex: かな at the end of the line (before closing punctuation).",
        "Different from the かも-hedge: かな is addressed to him, a request for his view.",
        "high",
    ),
    _spec(
        "confirms_with_darou",
        "Checks agreement with だろう / じゃないか",
        "Closes on だろう？ or じゃないか, a rhetorical check that carries the point (知らない仲じゃないだろう？).",
        r"(だろう|だろうか|じゃないか|ではないか|ないか)[。！？…]*$",
        "regex: だろう, だろうか, じゃないか, ではないか or ないか at the end of the line.",
        "The president's tag question. She uses it to lead him to the answer she already has.",
        "high",
    ),
    _spec(
        "opens_by_noticing",
        "Opens on a noticing interjection",
        "Starts the turn with おや, おやおや, ほう, ふむ, やあ or いやはや before she answers.",
        r"^(おや|ほう|ふむ|やあ|はて|いやはや|いやいや)",
        "regex: the line starts with おや, ほう, ふむ, やあ, はて, いやはや or いやいや.",
        "The notice comes first and the answer after it.",
        "high",
    ),
    _spec(
        "laughs_in_words",
        "Laughs in words at the start of a turn",
        "Starts on ふふ, ふっ, はは, あはは or くす, a written soft laugh, then speaks.",
        r"^(ふふ|ふっ|はは|あはは|くす)",
        "regex: the line starts with ふふ, ふっ, はは, あはは or くす.",
        "Not the H-scene sounds; those start with はぁ / ぁ and are not matched.",
        "high",
    ),
    _spec(
        "thanks_and_apologises_courteously",
        "Thanks and apologises in courteous set phrases",
        "Uses ありがとう, すまない, 悪いね, ごめん or 失礼 as a social move, often to him or to the dog.",
        r"ありがとう|すまな|悪いね|悪いな|ごめん|失礼|詫び|申し訳",
        "regex: ありがとう, すまな-, 悪いね, 悪いな, ごめん, 失礼, 詫び or 申し訳.",
        "The set phrases carry the courtesy; none of them is childlike.",
        "high",
    ),
    _spec(
        "asks_by_soft_command",
        "Asks by a soft command, てくれ / たまえ",
        "Gives a request as a polite order: 〜てくれ, 〜てくれたまえ, 〜してもらえるかな, 頼む.",
        r"てくれ(?!る)|たまえ|てもらえ(る|ない)|頼む|てほしい|てくれないか",
        "regex: てくれ (not てくれる), たまえ, てもらえる / てもらえない, 頼む, てほしい or てくれないか.",
        "She asks as one who is used to being obeyed and says please by tone, not by pleading.",
    ),
    _spec(
        "concedes_then_turns",
        "Concedes, then turns on けれど / のだが",
        "Grants the point and turns in the same turn with けれど, けれども, だけれど, のだが or だが.",
        r"けれど|のだが|んだが|だが|ですが",
        "regex: けれど, けれども, のだが, んだが, だが or ですが anywhere in the line.",
        "Shows as 〜のだけれど、 and 〜んだが……; the pause after it is hers (see the ellipsis rule).",
    ),
    _spec(
        "addresses_by_name_suffix_or_kimi",
        "Addresses people by name with a suffix, or as 君",
        "Calls him 一悟くん and others 真優ちゃん, 千奈ちゃん, or says 君 to him; the plain name is rare.",
        r"一悟くん|真優ちゃん|千奈ちゃん|君",
        "regex: 一悟くん, 真優ちゃん, 千奈ちゃん or 君 in the line.",
        "The address table has the counts; this is the mechanism that carries the intimacy into a line.",
        "high",
    ),
    _spec(
        "speaks_as_the_office",
        "Speaks as the student council president",
        "Uses the office: 生徒会, 我々, 諸君, 予算, 部活動, 責任, 文化祭 as the frame of a request or a decision.",
        r"生徒会|我々|諸君|予算|部活動|責任|文化祭|会長",
        "regex: 生徒会, 我々, 諸君, 予算, 部活動, 責任, 文化祭 or 会長 in the line.",
        "Frame vocabulary of the role; the topic is the school, the move is deciding from the chair.",
    ),
    _spec(
        "cites_hearsay_or_proverb",
        "Cites what is said or known to back the point",
        "Backs a point with というじゃないか, と聞く, とは言う, らしい, と言われ.",
        r"というじゃないか|と聞く|と聞いて|とは言う|らしいね|らしい|と言われ|というもの|という話",
        "regex: というじゃないか, と聞く, と聞いて, とは言う, らしい, と言われ, というもの or という話.",
        "She argues by what is generally said (お菓子は別腹というじゃないか, 02_01:2574).",
        "low",
    ),
    _spec(
        "teases_by_noticing_his_reaction",
        "Teases by remarking on his reaction",
        "Names what she sees him do, as a tease: 顔を赤く, 照れ, 視線, 気のせい, 可愛い, 意地悪, 妬け.",
        r"顔を赤|照れ|視線|気のせい|可愛い|意地悪|妬け|からか|赤くし",
        "regex: 顔を赤, 照れ, 視線, 気のせい, 可愛い, 意地悪, 妬け, からか or 赤くし.",
        "The tease is the question that names his face (01_01:1050).",
    ),
    _spec(
        "stammers_when_flustered",
        "Breaks into a stammer when flustered",
        "Loses the composed frame: a bare あっ / えっ / っ opener, a broken あ、い、 start or その…… when caught.",
        r"^(あっ|えっ|わあ|ふあっ|っ)|^(あ|い|え|そ|な|う)、|その…",
        "regex: the line starts with あっ, えっ, わあ, ふあっ or っ, or with a single kana and 、, or has その….",
        "The break is the contrast with her usual composure; it fires when he says something direct.",
        "low",
    ),
    _spec(
        "proposes_a_joint_move",
        "Closes by proposing the next step together",
        "Ends a turn with しよう, いこう, ましょう or しようか, a next step offered as joint.",
        r"(しよう|いこう|ましょう|ようか|こうか|そうしよう|始めよう|行こう)[。！？…]*$",
        "regex: しよう, いこう, ましょう, ようか, こうか or 始めよう / 行こう at the end of the line.",
        "The chair moves the meeting on and takes him with her.",
    ),
    _spec(
        "praises_in_a_formal_register",
        "Praises him in a measured register",
        "Gives credit as a verdict: さすが, 頼もしい, 感心, 素晴らしい, 見事, 上手, たいした.",
        r"さすが|頼もしい|感心|素晴らしい|見事|上手|たいした|えらい",
        "regex: さすが, 頼もしい, 感心, 素晴らしい, 見事, 上手, たいした or えらい.",
        "Praise comes as an assessment from above, warm but measured.",
    ),
    _spec(
        "closes_on_stiff_declarative",
        "Closes on a stiff declarative, のだ / だな / だぞ",
        "Ends on のだ, ものだ, だな, だぞ, であろう, なかろう, the stiff declarative.",
        r"(のだ|ものだ|だな|だぞ|であろう|なかろう|だとも)[。！？…]*$",
        "regex: のだ, ものだ, だな, だぞ, であろう, なかろう or だとも at the end of the line.",
        "Her stiff mode, used for announcements and for the dog.",
    ),
    _spec(
        "treats_the_dog_as_partner",
        "Treats the dog Kerberos as a partner",
        "Names ケルベロス or the 相棒 and speaks to the dog as to a colleague.",
        r"相棒|ケルベロス|ケルベロ",
        "regex: 相棒, ケルベロス or ケルベロ in the line.",
        "A recurring beat of her scenes; the 相棒 form is hers (01_01:1505, 09_01:5171).",
    ),
]
