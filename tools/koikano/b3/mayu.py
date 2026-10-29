"""B3 reading for 真優 (mayu): her own mechanisms, read off her lines.

Loaded by koikano_bible.mechanism_specs() for the subject 真優. Same spec shape as
the default (百花) list. Every matcher is a regex over her spoken lines (the builder
strips the 「」 brackets first); each is a lower bound for a move defined by reading.
Receipts (scene:line) come from the builder, three per mechanism.

How the entries were found (2026-10-23, notebook docs/reports/2026-10-23_b3_mayu_notebook.md):
her 3546 spoken lines against the 8088 spoken lines of the other named speakers in her
scenes, character 3- and 4-gram contrast plus a hand list of candidate moves, explicit
(H) lines kept out of the probe so the list is about the person, not the register.
Counts in the notes are the build counts, the builder recomputes them.

Tier rule (one rule for every entry, set from the build counts of this file):
  firm  = lines >= 40 and her share is at least 2x the control share (control 0 counts)
  thin  = lines >= 10 and her share above the control share
  weak  = anything else (fewer than 10 lines, or a share at or under the control's)
The tier fields below were set from the build counts by that rule; characters/mayu/b3_tiers.py
checks them against the build and applies the same rule to the speech_guide rules.
"""

MECHANISM_SPECS = [
    {
        "key": "justifies_with_mon",
        "name": "Justifies herself with a sentence-final もん",
        "definition": "Ends a claim or a complaint on だもん / ないもん / たもん, the pouting 'because it is so' of a childhood friend.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"(だ|ん|い|た|る|の)もん[。！？…っ]*$",
        "method": "regex: the line ends (before the final marks) on もん after だ, ん, い, た, る or の.",
        "note": "The most separated move she has. The other speakers in her scenes almost never close a line this way.",
    },
    {
        "key": "opens_with_datte",
        "name": "Opens a reason with だって",
        "definition": "Starts the line on だって and gives the reason she did or wants something, usually followed by a もん ending.",
        "class": "hers", "tier": "firm", "confidence": "medium",
        "pattern": r"^だって",
        "method": "regex: the line starts with だって.",
        "note": "A reproach she gives as an explanation, to 一悟 mostly.",
    },
    {
        "key": "laughs_ehehe",
        "name": "Laughs the えへへ",
        "definition": "Covers pleasure or embarrassment with a written えへ / えへへ / えへへぇ before going on.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"えへ",
        "method": "regex: contains えへ.",
        "note": "Written laugh, one beat, then the sentence. Includes the drawn-out えへへぇ.",
    },
    {
        "key": "sets_herself_beside_ichigo",
        "name": "Puts herself next to 一悟 in one sentence",
        "definition": "Builds a sentence of わたし plus a case particle and 一悟 within a few characters (わたしも一悟に..., わたしが一悟を...), stating where she stands with him.",
        "class": "hers", "tier": "firm", "confidence": "medium",
        "pattern": r"わたし(は|が|の|を|と|も|に)[^。！？]{0,3}一悟",
        "method": "regex: わたし, a case particle, up to three characters, then 一悟.",
        "note": "Her own self-reference form is a surface rule in speech_guide; this is the move of ranking herself against him (and against 千奈 and 百花ちゃん in the same breath).",
    },
    {
        "key": "names_momoka_with_chan",
        "name": "Speaks of 百花ちゃん by name",
        "definition": "Brings 百花 into the sentence as 百花ちゃん, as the kouhai she looks after, resists or gives way to.",
        "class": "hers", "tier": "firm", "confidence": "medium",
        "pattern": r"百花ちゃん",
        "method": "regex: contains 百花ちゃん.",
        "note": "An address habit tied to one person, kept as a mechanism because no one else in her scenes uses that form.",
    },
    {
        "key": "offers_to_do_for_him",
        "name": "Offers to do it for him",
        "definition": "Volunteers the favour with てあげる / であげる (ご奉仕してあげる, 支えてあげられる), the caring-for-him stance.",
        "class": "hers", "tier": "firm", "confidence": "medium",
        "pattern": r"てあげ|であげ",
        "method": "regex: contains てあげ or であげ.",
        "note": "Others use the form too (the control share is not zero), she uses it about four times as often.",
    },
    {
        "key": "closes_on_his_name",
        "name": "Closes the line on 一悟",
        "definition": "Ends a question or a rebuke by calling his name last (どうしたの、一悟？ / 一悟ぉ).",
        "class": "hers", "tier": "firm", "confidence": "medium",
        "pattern": r"一悟[ぉー]*[。！？…っ]*$",
        "method": "regex: the line ends on 一悟, with optional drawn vowel and final marks.",
        "note": "The vocative sits at the end, so the line is aimed at him before it is heard.",
    },
    {
        "key": "rebuts_with_nai_yo",
        "name": "Rebuts with ないよ / じゃないよ",
        "definition": "Flatly denies what was said to her with じゃないよ or ないよ！ (『どうしたんだ？』じゃないよ！).",
        "class": "hers", "tier": "thin", "confidence": "medium",
        "pattern": r"(じゃ|では)ないよ(?!ね)|ないよ！",
        "method": "regex: contains じゃないよ / ではないよ (not followed by ね), or ないよ followed by ！.",
        "note": "Mostly the jealous scenes with 一悟, quoting his words back at him.",
    },
    {
        "key": "presses_with_desho",
        "name": "Presses a point with でしょ",
        "definition": "Ends on でしょ(？) to make him agree with what she says is obvious (部活見学は、アイディア集めるためでしょ？).",
        "class": "hers", "tier": "firm", "confidence": "medium",
        "pattern": r"でしょ[。！？…]*$",
        "method": "regex: the line ends on でしょ with optional marks.",
        "note": "Rhetorical, not a real question.",
    },
    {
        "key": "opens_with_nee",
        "name": "Calls for his attention with ねえ",
        "definition": "Opens a line on ねえ / ねぇ / ね、 before the name or the request.",
        "class": "hers", "tier": "thin", "confidence": "low",
        "pattern": r"^(ねえ|ねぇ|ね、|ねっ)",
        "method": "regex: the line starts with ねえ, ねぇ, ね、 or ねっ.",
        "note": "Small count. It is usually followed by 一悟.",
    },
    {
        "key": "says_suki_outright",
        "name": "Says 好き outright",
        "definition": "Names her liking in the word 好き / 大好き, about him, about the stage, about the club.",
        "class": "hers", "tier": "firm", "confidence": "medium",
        "pattern": r"(?<!物)好き|すき",
        "method": "regex: contains 好き (not 物好き) or すき.",
        "note": "The word, not the stance. Her love scenes carry most of it; the stage ones (演劇が好き) too.",
    },
    {
        "key": "whimpers_u_u",
        "name": "Whimpers the う、うう beat",
        "definition": "Writes a stuck sound (うう…, う、うう…) as the whole line or its opening when she cannot answer.",
        "class": "hers", "tier": "firm", "confidence": "low",
        "pattern": r"^(う|ぅ){2,}[っ…！、]|^う、う",
        "method": "regex: the line starts with two or more う/ぅ followed by っ … ！ or 、, or with う、う.",
        "note": "Small count. Can be a hesitation or a sob, the regex does not tell which.",
    },
    {
        "key": "stammers_first_sound",
        "name": "Stammers on the first sound",
        "definition": "Splits the opening kana off with a comma (あ、ありがと / ほ、褒めてるよ / そ、それは).",
        "class": "hers", "tier": "weak", "confidence": "high",
        "pattern": r"^([ぁ-んァ-ヶ])、\1",
        "method": "regex: the line starts with one kana, 、, and the same kana again.",
        "note": "Frequent in her lines, but the other speakers in her scenes stutter just as much (house style of the script), so it is not hers.",
    },
]
MATCHERS = {}
