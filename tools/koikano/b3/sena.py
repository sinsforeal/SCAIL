# B3 reading for 千奈 (sena), written 2026-10-23 from her own lines.
#
# Method: her 3493 spoken lines were set against the other six named heroines' spoken
# lines over the whole record (11,120). Endings, openers and word lists were ranked by
# her rate over the control rate; the ones below are the moves that are hers by that
# ranking AND read as a rhetorical move (not just a vocabulary item). The 15 default
# mechanisms (百花's) are not used: most of them fire 0 to 8 times on her.
#
# Same shape as the default list in koikano_bible.py. Every matcher is a regex over the
# line with the 「」 quote marks removed (the builder strips them before matching).
# The tier values here are the first guess from the counts above; tools-side the tier
# rule in characters/sena/tier_pass.py is the authority and rewrites them in bible.json.
# Receipts (scene:line) are produced by the builder: the first three matching lines.

MATCHERS = {}

MECHANISM_SPECS = [
    {
        "key": "stammers_the_first_syllable",
        "name": "Stammers the first syllable of a word",
        "definition": "Breaks a word open with its first kana and a comma before saying it whole (さ、さすが, ち、違います, み、見ないで).",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"(?<![ぁ-んァ-ヶ一-龠])([ぁ-ん])、\1",
        "method": "regex: one hiragana, a comma, then the same hiragana starting the next word, not preceded by another letter.",
        "note": "The surface stutter, not a pause. It marks flustering and it carries the line into the word she then says whole. Other heroines stammer too, so the rate against the control is the test, not the existence of the move.",
    },
    {
        "key": "addresses_him_by_title",
        "name": "Addresses the other person by 先輩 as a call",
        "definition": "Puts the other person's name and 先輩 (みゃー先輩, 十川先輩, 一悟先輩) in the line as a vocative, usually at the clause end.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"先輩(?:[、！？…っ♪]|$)",
        "method": "regex: 先輩 followed by a punctuation mark or the end of the line.",
        "note": "This is the call, not the topic: 先輩は / 先輩が (a third-person mention of him) is not counted. The control rate is 0: no other heroine addresses anyone by 先輩 in this way.",
    },
    {
        "key": "presses_with_ndesu_ka",
        "name": "Presses for an account with んですか",
        "definition": "Turns a surprise or a complaint into a polite demand to explain (なにしてるんですか, どういうことなんですか).",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"んですか",
        "method": "regex: contains んですか.",
        "note": "A question in the polite register that is a reproach more than a request. Nothing in the record says what she does with the answer; the move is the asking.",
    },
    {
        "key": "explains_with_ndesu",
        "name": "Explains or justifies herself with んです",
        "definition": "Closes a reason, a correction or a confession with んです / んですよ instead of stating it flatly.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"んです(?!か)",
        "method": "regex: contains んです not followed by か.",
        "note": "The explaining んです (ち、違うんです, 思ったんです). It pairs with the stammer: she often stammers into it.",
    },
    {
        "key": "snaps_a_polite_ending_shut",
        "name": "Snaps a polite ending shut with っ",
        "definition": "Ends a です / ます line on a glottal stop (ですっ, ますっ), clipped, as an objection or an emphasis.",
        "class": "hers", "tier": "thin", "confidence": "medium",
        "pattern": r"(?:です|ます)っ[！？…]*$",
        "method": "regex: です or ます, then っ, then optional marks, at the end of the line.",
        "note": "A subset of the glottal-っ rule in speech_guide, taken where it closes a polite sentence. Count is small, rate against the control is not.",
    },
    {
        "key": "scolds_improper_conduct",
        "name": "Scolds improper conduct with a prim word",
        "definition": "Names what she finds indecent with ハレンチ / いやらしい / 不潔 / 不健全 and holds it against the other person.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"ハレンチ|はれんち|破廉恥|いやらしい|不潔|不健全|不謹慎|ふしだら",
        "method": "regex over a fixed word list.",
        "note": "The prim vocabulary only; エッチ / えっち is left out because the other heroines use it freely. Mostly outside H; inside H the same words turn up in the lines she says while refusing.",
    },
    {
        "key": "denies_with_chigaimasu",
        "name": "Denies with 違います",
        "definition": "Meets a teasing or a guess with 違います / 違うんです, often after a stammered ち、.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"違います|ちがいます|違うん|違うの|違いますよ",
        "method": "regex over a fixed word list.",
        "note": "A flat polite denial. It overlaps the @否定 gesture in speech_guide but is the spoken move, not the gesture.",
    },
    {
        "key": "stops_him_with_a_polite_prohibition",
        "name": "Stops him with a polite prohibition",
        "definition": "Forbids with ないでください / いけません / だめです instead of an order or a scream.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"ないでください|いけません|(?:だめ|ダメ|駄目)です|(?:だめ|ダメ)っ",
        "method": "regex over a fixed set of prohibition frames.",
        "note": "Shares ground with scolds_improper_conduct: the scold names the thing, this stops it.",
    },
    {
        "key": "squeaks_before_the_words",
        "name": "Squeaks before the words come",
        "definition": "Opens a line on a squeak or a gasp (ひゃ, きゃ, ふぇ, はぅ, ふぁ) and then speaks.",
        "class": "hers", "tier": "firm", "confidence": "medium",
        "pattern": r"^(?:ひゃ|きゃ|ふぇ|はぅ|ひぅ|ひあ|ふぁ)",
        "method": "regex: the line starts with one of the squeak syllables.",
        "note": "Distinct from the sound-effect-as-action move: this is a reflex at the line start, not a stage direction. Other heroines squeak in H lines too, so the rate against the control is moderate.",
    },
    {
        "key": "talks_shop_as_a_writer",
        "name": "Talks shop as a novelist, and guards it",
        "definition": "Brings her writing in through 小説 / 作家 / 原稿 / 締め切り, and treats the pen name and the job as a secret.",
        "class": "hers", "tier": "thin", "confidence": "medium",
        "pattern": r"小説|ペンネーム|夏天|作家|原稿|締め切り|締切|担当編集|機密|企業秘密",
        "method": "regex over a fixed word list.",
        "note": "Content as much as rhetoric: she brings the same topic back in several routes. The secrecy is in the lines (他の人には秘密), not in the matcher.",
    },
]
