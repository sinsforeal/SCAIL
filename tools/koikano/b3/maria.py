# B3 reading for 真里亜 (slug maria), 2026-10-23, branch cast/b3_maria.
# Read off her own 1,228 spoken lines (no inner voice), not from 百花's list.
# Loaded by koikano_bible.mechanism_specs() when the subject is 真里亜.
# Exports MECHANISM_SPECS (same shape as the default list) and MATCHERS.
# Every matcher is a regex over the line with the 「」 quotes stripped.
# Counts and receipts (scene:line) come from the builder, not from here.
import re

TIER_RULE = "firm: 50 or more of her lines and distinctive; thin: 10 to 49 lines; weak: fewer than 10 lines or not distinctive"


def _s(text):
    return re.sub(r"[「」『』]", "", text).strip()


TITLES = r"(お嬢様|宮国様|真優様|千奈様|アリス様|小野坂様|榎本先生|ご主人様|奥様)"


def _m_title_frame(text):
    # A title address (X様 / 榎本先生) in the first 10 or the last 12 characters of the line.
    t = _s(text)
    for m in re.finditer(TITLES, t):
        if m.start() <= 10 or len(t) - m.end() <= 12:
            return True
    return False


def _m_service_formula(text):
    return bool(re.search(
        r"失礼いたし|かしこまり|承知いたし|承知しました|させていただ|させて頂|お待ちしており|"
        r"恐縮|僭越|お手伝い|ご案内いたし|お届け|お持ちし", _s(text)))


def _m_offers_service(text):
    return bool(re.search(
        r"いたしましょうか|いたしますわ|いたしますね|お支え|お守り|お任せ|お力になり|"
        r"させてくださ|ご用意いたし|私がいたし", _s(text)))


def _m_wa_final(text):
    # Clause-final わ in the ladylike register: ですわ / ますわ / でしたわ / ですわね / ませんわ.
    return bool(re.search(r"(です|ます|ません|でした|ました|ですの|たい|ない|ある|いる)わ(?![ぁ-ん])", _s(text)))


def _m_aara_opener(text):
    return bool(re.match(r"(あら|あらあら|まあ|まぁ)", _s(text).lstrip("…")))


def _m_soft_laugh(text):
    return bool(re.search(r"うふふ|ふふ|くすくす|あはは|うふっ", _s(text)))


def _m_reminds(text):
    t = _s(text)
    return bool(re.search(r"(仰|おっしゃ)っていた", t)) or bool(re.search(
        r"(先日|先ほど|さきほど|昨日|さっき)[^。]*(ではないですか|ではありませんか|でしたよね|ましたよね)", t))


def _m_maid_frame(text):
    return bool(re.search(r"メイド", _s(text)))


def _m_directs(text):
    return bool(re.search(
        r"くださいませ|てください|ていただけ|いただけませんか|してみて|なさって|ご覧ください|ごらんください",
        _s(text)))


def _m_hedged_opinion(text):
    return bool(re.search(
        r"かと思います|かもしれません|ではないでしょうか|でしょうか[。…]?$|と思いますわ|ように思います|ように思えます",
        _s(text)))


def _m_praises(text):
    return bool(re.search(r"さすが|素敵|素晴らし|お見事|立派|頼もしい|凛々しい|感服|感動", _s(text)))


def _m_self_blame(text):
    return bool(re.search(r"申し訳|失態|失格|不手際|ご無礼|お詫び|至らな", _s(text)))


def _m_tease(text):
    return bool(re.search(r"いけず|つれない|おとぼけ|意地悪|いじわる|お人が悪い|悪戯|いたずら|からかい", _s(text)))


def _m_yes_no_first(text):
    return bool(re.match(r"(はい|ええ|いいえ|いえ)[、。…！]", _s(text)))


MATCHERS = {
    "m_title_frame": _m_title_frame,
    "m_service_formula": _m_service_formula,
    "m_offers_service": _m_offers_service,
    "m_wa_final": _m_wa_final,
    "m_aara_opener": _m_aara_opener,
    "m_soft_laugh": _m_soft_laugh,
    "m_reminds": _m_reminds,
    "m_maid_frame": _m_maid_frame,
    "m_directs": _m_directs,
    "m_hedged_opinion": _m_hedged_opinion,
    "m_praises": _m_praises,
    "m_self_blame": _m_self_blame,
    "m_tease": _m_tease,
    "m_yes_no_first": _m_yes_no_first,
}


def _spec(key, name, definition, matcher, method, note, confidence="high", tier="firm"):
    # tier from the count rule (see TIER_RULE): firm >= 50 lines, thin 10-49, weak < 10 or not distinctive.
    return {
        "key": key, "name": name, "definition": definition,
        "class": "hers", "tier": tier, "confidence": confidence,
        "matcher": matcher, "method": method, "note": note,
    }


MECHANISM_SPECS = [
    _spec("frames_a_turn_with_a_title",
          "Frames the turn with the listener's title",
          "Puts the listener's name and 様 (お嬢様, 宮国様, 真優様, 千奈様, アリス様) or 先生 at the start or end of the line.",
          "m_title_frame",
          "regex: one of お嬢様 / 宮国様 / 真優様 / 千奈様 / アリス様 / 小野坂様 / 榎本先生 / ご主人様 / 奥様 within the first 10 or the last 12 characters.",
          "How she addresses people. 宮国様 is 一悟 (the record gives him the family name; she does not say 一悟)."),
    _spec("uses_service_formulas",
          "Uses fixed service formulas",
          "Opens or closes a turn with a set maid phrase: 失礼いたします, かしこまりました, させていただく, お待ちしております.",
          "m_service_formula",
          "regex: 失礼いたし / かしこまり / 承知 / させていただ / お待ちしており / 恐縮 / 僭越 / お手伝い / ご案内いたし / お届け / お持ちし.",
          "Formulas, so repetition is the point. Exact repeats such as 「失礼いたします」 appear 4 times."),
    _spec("offers_to_do_it_for_them",
          "Offers to do or carry it",
          "Offers to take the task, protect, support or arrange: お支えいたします, お守りします, お任せください, いたしましょうか.",
          "m_offers_service",
          "regex: いたしましょうか / いたしますわ / いたしますね / お支え / お守り / お任せ / お力になり / させてくださ / ご用意いたし / 私がいたし.",
          "The service stance as a move. A lower bound: offers phrased another way are not caught."),
    _spec("closes_the_clause_with_wa",
          "Closes the clause with わ",
          "Ends a clause in the ladylike register: ですわ, ますわ, でしたわ, ですわね.",
          "m_wa_final",
          "regex: です / ます / ません / でした / ました / ですの / たい / ない / ある / いる followed by わ and no further kana.",
          "A surface habit, counted here because it is the commonest ending she has. ですわ alone ends 83 lines."),
    _spec("opens_with_aara",
          "Opens with あら / まあ",
          "Starts the turn with a soft surprise or notice: あら, あらあら, まあ.",
          "m_aara_opener",
          "regex: line starts (after leading …) with あら / あらあら / まあ / まぁ.",
          "Often the lead-in to a gentle correction or a tease."),
    _spec("laughs_softly",
          "Laughs softly in the text",
          "Writes a soft laugh into the line: うふふ, ふふ, ふふっ, くすくす.",
          "m_soft_laugh",
          "regex: うふふ / ふふ / くすくす / あはは / うふっ anywhere in the line.",
          "Sound, not words, but it recurs across her scenes and relationships."),
    _spec("reminds_them_of_what_was_said",
          "Reminds them of what was said or arranged",
          "Points back to a stated plan with ではないですか, 仰っていた, でしたよね.",
          "m_reminds",
          "regex: 仰っていた / おっしゃっていた anywhere, or 先日 / 先ほど / 昨日 / さっき followed in the same sentence by ではないですか / ではありませんか / でしたよね / ましたよね.",
          "How she corrects without contradicting: she cites the person's own words.",
          confidence="medium", tier="weak"),
    _spec("frames_herself_as_the_maid",
          "Frames herself as the maid",
          "Names her role (メイド) when she explains a duty, a joy or a failure.",
          "m_maid_frame",
          "regex: メイド anywhere in the line.",
          "Includes lines that name another person's maid. Read the receipts.", tier="thin"),
    _spec("directs_with_kudasaimase",
          "Directs with くださいませ / てください",
          "Tells the listener what to do in the polite imperative: くださいませ, てください, いただけませんか, なさって.",
          "m_directs",
          "regex: くださいませ / てください / ていただけ / いただけませんか / してみて / なさって / ご覧ください.",
          "The same form carries service talk (ご安心くださいませ) and, in the H scenes, instruction to お嬢様."),
    _spec("hedges_an_opinion_politely",
          "Gives an opinion hedged and polite",
          "States a view as かと思います, かもしれません, ではないでしょうか.",
          "m_hedged_opinion",
          "regex: かと思います / かもしれません / ではないでしょうか / と思いますわ / ように思います / ように思えます / line-final でしょうか.",
          "Opinion without pushing it.",
          confidence="medium", tier="thin"),
    _spec("praises_a_person",
          "Praises a person",
          "Praises the listener or a third party: さすが, 素敵, 素晴らしい, 立派, 頼もしい.",
          "m_praises",
          "regex: さすが / 素敵 / 素晴らし / お見事 / 立派 / 頼もしい / 凛々しい / 感服 / 感動.",
          "Praise of things (a play, a plan) is included. Read the receipts.", tier="thin"),
    _spec("blames_herself_formally",
          "Blames herself in set terms",
          "Apologises or calls herself at fault: 申し訳ありません, 失態, メイド失格, 至らず.",
          "m_self_blame",
          "regex: 申し訳 / 失態 / 失格 / 不手際 / ご無礼 / お詫び / 至らな.",
          "Thin by count; kept because it is the one place she names her own failing.",
          confidence="medium", tier="thin"),
    _spec("teases_gently",
          "Teases gently",
          "Mock-complains or needles in a soft register: いけず, つれない, おとぼけ.",
          "m_tease",
          "regex: いけず / つれない / おとぼけ / 意地悪 / いじわる / お人が悪い / 悪戯 / いたずら / からかい.",
          "A lower bound: her teasing often has no marker word.",
          confidence="medium", tier="weak"),
    _spec("answers_yes_or_no_first",
          "Answers yes or no first",
          "Starts with はい / ええ / いいえ / いえ and a pause mark, then explains.",
          "m_yes_no_first",
          "regex: line starts with はい / ええ / いいえ / いえ followed by 、 。 … or ！.",
          "A reply move; she answers far more than she starts."),
]
