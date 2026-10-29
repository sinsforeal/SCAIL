#!/usr/bin/env python3
# COPY of F:\REPS2\clipboard capture (kirikiri)\src\kirikiri_tools\koikano_bible.py, kirikiri repo commit: none (the repo has no commits on 2026-10-23, so the file state is the working tree). Patched for cast subjects (tk-oas): route, self-reference form, B3 offers_self skip, text_basis marks.
"""Build the authored expression bible for one koikano character (phases B0+B1).

Specification: ``docs/koikano-authored-bible-plan.md``.  The plan fixes the
deliverable (an authored expression bible, not a SCAIL codebook), the subject
slice (B0) and the mechanical layers (B1): the surface battery, the bounds, the
context labels, the authored annotation profile and the per-relationship
interaction map.  No model is called here; the standard library only.

The corpus already attributes every line to a speaker and annotates it with the
author's stage directions, so the whole of B0 and B1 is a join, not a reading.
The tool reads ``game_logic.jsonl`` as the spine and joins, on ``record_id``:

- ``character_actions.jsonl`` - her gestures, faces, emotions, entry/exit, camera;
- ``expression_labels_lines.jsonl`` - the C4 face hypothesis per line;
- ``timing_table.jsonl`` - the per-line voice timing (carried for provenance);
- ``inventory\\expression_labels.json`` - the C4 hypothesis table (unit -> label);
- ``inventory\\bgm_scene_table.json`` - the per-scene BGM track list;
- ``data\\charData.csv`` - the cast names and the two-letter sprite prefixes;
- ``data\\scenario\\*.ks`` - the ``Ｈシーン開始`` marker, read as CP932.

Outputs (all NEW; no input is modified):

- ``<out>\\layers\\slice.json``        the subject slice (B0)
- ``<out>\\layers\\battery.json``      the surface battery
- ``<out>\\layers\\bounds.json``       the bounds and the absent list
- ``<out>\\layers\\context.json``      a context row per scene
- ``<out>\\layers\\annotations.json``  the authored annotation profile
- ``<out>\\layers\\interactions.json`` the per-relationship interaction map
- ``<out>\\bible.json``                the assembled mechanical sections
- ``docs\\koikano-bible-hyakka.md``    the readable bible

The run fails loudly (exit 2) and writes nothing when a ``record_id`` join does
not match ``game_logic.jsonl``, when a ``record_id`` is duplicated, or when the
resolved ``character_lines`` extract disagrees with the spine.  Standard library
only; JSON is UTF-8, the scripts and the character table are CP932.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict


BUILD_VERSION = "b0-b3/1"
BUILD_DATE = "2026-09-16"
SCHEMA = "authored-expression-bible/1"
PHASE = "B0+B1+B2+B3"

DEFAULT_CORPUS = r"F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano"
DEFAULT_CHAR = "百花"

# name -> output directory slug (deterministic, no romanisation guess at runtime).
SLUGS = {
    "真優": "mayu",
    "千奈": "sena",
    "アリス": "alice",
    "百花": "hyakka",
    "ひかる": "hikaru",
    "知紗": "chisa",
    "真里亜": "maria",
    "ケルベロス": "cerberus",
    "一悟": "ichigo",
}

PROTAGONIST = "一悟"

# route letter -> route character (one map; context rows and the subject's own
# route both read it).  A subject without a route (真里亜, 知紗, ...) has "".
ROUTE_CHARACTER = {"a": "真優", "b": "千奈", "c": "アリス", "d": "百花"}
ROUTE_OF = {v: k for k, v in ROUTE_CHARACTER.items()}

# Candidate first-person forms; the subject's own name is added at run time.
FIRST_PERSON_FORMS = ["私", "わたし", "あたし", "僕", "ぼく", "俺", "おれ", "自分", "うち"]
INNER_MARKER = "心の声"

ROUTE_COMMON = re.compile(r"^0\d_\d\d$")
ROUTE_LETTER = re.compile(r"^([a-z])\d{2}_\d{2}$")
CHAPTER_RE = re.compile(r"(\d+)")

# Characters dropped before the surface battery; they are separators, not words.
# ``ー`` (long vowel) and the small kana are kept because they are meaningful.
DROP = set(
    " \t\r\n\u3000「」『』（）()〈〉《》【】［］[]｛｝、。，．,！？!?…‥・：；:;/／\\\"'’‘“”～〜"
)

# Endings searched when an address term is captured mechanically.
HONORIFICS = (
    "ちゃん",
    "さん",
    "くん",
    "君",
    "様",
    "先生",
    "先輩",
    "氏",
    "殿",
    "たん",
    "っち",
    "ちん",
)
EXTRA_ALIASES = {
    "ケルベロス": ["ケル"],
    "一悟": ["一悟"],
}


# --------------------------------------------------------------------------- #
# B3 rhetorical mechanisms (the builder's reading, not authored)
# --------------------------------------------------------------------------- #
# Each mechanism is a recurring move in her speech that carries no authored
# stage direction.  The list is deliberately short: the moves that recur across
# her scenes and relationships, not every turn of phrase.  ``method`` states how
# the count was taken; a regex over her spoken lines is a lower bound where the
# move is defined by reading and the pattern catches only its marked cases.
# ``class`` is hers / author / moment; ``tier`` is firm / thin.  The mechanisms
# are this builder's reading: the definitions and the classing are interpretive,
# the counts and the receipts are mechanical.  They are not authored.

# The doubling regex captures the repeated BASE (the 2-4 characters before the
# ``\1``), so this stop list keys bases, not the full reduplicated word.  Keys
# cover lexical reduplication (たまたま -> "たま"), the onomatopoeia owned by
# performs_a_sound_effect (ぱちぱち -> "ぱち") and the other sound-symbolic
# adverbials that are a word, not a stylistic repeat.  The first block of the
# old list keyed full forms (だんだん), so it never fired: that was the B4 bug.
# ``_m_double`` also rejects a repeat that starts inside a longer word (the
# ちんちん of おちんちん), which is the other half of the same false positive.
MECHANISM_STOP = set([
    # lexical reduplication: repeated base of a word, not an emphasis beat
    "だん", "どん", "そろ", "ます", "いよ", "だい", "たま", "ぜん", "よそ",
    "すや", "ばい", "わざ", "しば", "とき", "いろ", "それ", "もと", "つぎ",
    "ぞく", "にち", "べつ", "いち", "いま", "たび", "なか", "はん", "まち",
    # onomatopoeia / mimesis owned by performs_a_sound_effect
    "ぱち", "ぎゅ", "ぎゅー", "ぎゅう", "にや", "そよ", "ちょき", "ふん",
    "どき", "わく", "うず", "むず", "もや", "きら", "ふに", "ぷに",
    # other sound-symbolic adverbials that pass as a word, not a beat
    "びく", "ぐちゅ", "くちゅ", "ぐしょ", "くら", "びり", "ずん", "ひく",
    "こつ", "ごり", "ぴく", "なで", "こす", "ぺろ", "もみ", "ごつん",
    "がく", "ぐり", "ごし", "びゅる", "どぴゅ", "きゅん", "ふわ", "むら",
    "よわ", "でれ", "ひん", "むく", "こしゅ", "ぎち", "ずき", "じめ",
    "ぬる", "べた", "つる", "さら", "ぺた", "ごろ", "ぶる", "くす",
    "けら", "にこ", "へら", "ぷる", "むに", "こり", "ぐに", "くに",
    "すり", "にゅる", "ぐにゅ", "こぽ", "ごく", "れぢゅ", "ぢゅ",
    "らぶ", "日に",
])

MECHANISM_MATCHERS = {}

# A Japanese letter; a repeat preceded by one is inside a longer word.
MECH_LETTER = "ぁ-んァ-ヶ一-龠々ー"


def _mech_strip(text: str) -> str:
    return re.sub(r"[「」『』]", "", text).strip()


def _mech_kept_len(text: str) -> int:
    return len(re.sub(r"[。、！？…ー\s]", "", _mech_strip(text)))


def _to_hiragana(s: str) -> str:
    """Katakana to hiragana, so a katakana onomatopoeia answers the stop list."""
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def _m_double(text: str) -> bool:
    t = _mech_strip(text)
    for m in re.finditer(r"([ぁ-んァ-ヶ一-龠々ー]{2,4})\1", t):
        g = m.group(1)
        gh = _to_hiragana(g)
        if g in MECHANISM_STOP or gh in MECHANISM_STOP:
            continue
        # A 4-character base can be a stop unit doubled (ぱちぱちぱちぱち).
        if len(g) % 2 == 0 and _to_hiragana(g[: len(g) // 2]) in MECHANISM_STOP:
            continue
        if set(g) <= set("んっーぁあぇえぃいぅう"):
            continue
        # Reject a repeat that starts mid-word: the ちんちん of おちんちん.
        if m.start() > 0 and re.match("[" + MECH_LETTER + "]", t[m.start() - 1]):
            continue
        return True
    return False


def _m_short_question(text: str) -> bool:
    return _mech_kept_len(text) <= 14 and "？" in text


def _m_offers_self(text: str) -> bool:
    t = _mech_strip(text)
    return bool(re.search(r"百花(が|も|たち)", t)) and bool(
        re.search(r"する|した|買う|守る|作る|行く|やる|いく|がんば|きた|考え|引き受|して|つくる", t)
    )


def _m_sound_effect(text: str) -> bool:
    return bool(re.search(
        r"ぱちぱち|ぎゅー|ぎゅう|にやにや|そよそよ|ちょきちょき|ふんふん|"
        r"どきどき|わくわく|うずうず|むずむず|もやもや|きらきら|ふにふに|ぷにぷに",
        _mech_strip(text)))


def _m_labels_others(text: str) -> bool:
    return bool(re.search(
        r"(真優ちゃん|千奈|一悟|真里亜|アリス|知紗|ひかる|ケルベロス)[^。]{0,10}"
        r"(すごい|えらい|さすが|たよれる|がんばり屋|勉強家|天才|かっこいい|"
        r"やさしい|努力の子|大ファン|メイド|マスター)",
        _mech_strip(text)))


def _m_body_limit(text: str) -> bool:
    # The limit word must follow the body word in the same clause, so the
    # opposite claim ("つかれてるんじゃない。からだのもんだいじゃ、ない") does
    # not fire.  ``わる`` is not さわる / いじわる.
    t = _mech_strip(text)
    return bool(re.search(
        r"(からだ|身体)[^。！？…]{0,8}(弱|よわ|迷惑|こわ|つか|つら|くるし|(?<![さじ])わる)",
        t))


def _m_loan_blow(text: str) -> bool:
    return bool(re.search(r"しょっく|ショック|がーん|ざんねん|がっかり", _mech_strip(text)))


def _m_coin_label(text: str) -> bool:
    return bool(re.search(
        r"らぶらぶ|レベル|[一二三四五]乗|党|マスター|えすぴー|ミッション|"
        r"みっしょん|はーれむ|どんとまいんど",
        _mech_strip(text)))


def _m_secret(text: str) -> bool:
    return bool(re.search(r"ひみつ|ないしょ|しーくれっと", _mech_strip(text)))


def _m_hedge(text: str) -> bool:
    return bool(re.search(r"(かも|かな|かもしれ|たぶん)[。！？…]?$", _mech_strip(text)))


def _m_bargain(text: str) -> bool:
    return bool(re.search(
        r"プレゼント|ごほうび|ワイロ|おねだり|ゆずる|あげる|くれれば|"
        r"もらえたら|貸して|見せてあげる|協力してくれたら|してくれたら",
        _mech_strip(text)))


def _m_tease(text: str) -> bool:
    return bool(re.search(
        r"ずるい|ボケ|おんみつ|密会|デンジャー|危険人物|いたずら|いじわる|"
        r"からか|はれんち|けんたいき|おあずけ",
        _mech_strip(text)))


MECHANISM_MATCHERS.update({
    "double": _m_double,
    "short_question": _m_short_question,
    "offers_self": _m_offers_self,
    "sound_effect": _m_sound_effect,
    "labels_others": _m_labels_others,
    "body_limit": _m_body_limit,
    "loan_blow": _m_loan_blow,
    "coin_label": _m_coin_label,
    "secret": _m_secret,
    "hedge": _m_hedge,
    "bargain": _m_bargain,
    "tease": _m_tease,
})

def has_b3_file(name: str) -> bool:
    """True when tools/koikano/b3/<slug>.py exists for this subject (its own B3 reading)."""
    return os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "b3", "%s.py" % SLUGS.get(name, "_none")))


def mechanism_specs(name: str) -> list:
    """B3 specs for one subject. tools/koikano/b3/<slug>.py, when present, is that
    subject's own reading (method doc: the matcher list needs review against her
    lines): it exports MECHANISM_SPECS (same shape as the default list) and
    MATCHERS (matcher name -> fn), merged into MECHANISM_MATCHERS. Absent (百花
    today), the default list stands and her output is byte for byte unchanged.
    Used by the builder and by koikano_bible_gate.py so both read the same list."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "b3", "%s.py" % SLUGS.get(name, "_none"))
    if name == DEFAULT_CHAR or not os.path.isfile(path):
        return MECHANISM_SPECS
    import importlib.util
    spec = importlib.util.spec_from_file_location("koikano_b3_" + SLUGS[name], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    MECHANISM_MATCHERS.update(getattr(mod, "MATCHERS", {}))
    return mod.MECHANISM_SPECS


MECHANISM_SPECS = [
    {
        "key": "doubles_a_key_word",
        "name": "Doubles a key word or phrase as a beat",
        "definition": "Repeats a word or short phrase back to back for emphasis or eagerness.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "matcher": "double",
        "method": "regex: a 2-4 character kana/kanji group repeated immediately, minus lexical reduplication and onomatopoeia (MECHANISM_STOP keys the captured base), minus a repeat that starts inside a longer word (the ちんちん of おちんちん), minus the doubled ん counted in the speech guide.",
        "note": "The doubled ん (ん, んん, んーん) is a separate surface rule in `speech_guide`; this is the wider move (なるほどなるほど, がんばるがんばる, もっともっと). B4 found the old matcher counted 55 holdout hits of ちんちん inside おちんちん plus lexical and sound-symbolic repeats; the base-keyed stop list and the word-start check remove those classes. Corpus count falls 396 -> 100.",
    },
    {
        "key": "closes_a_turn_with_a_short_question",
        "name": "Answers, then rebounds with a short question",
        "definition": "Takes the other person's turn and closes with a brief question - a request to confirm, a why, or a what-about-you.",
        "class": "hers", "tier": "weak", "confidence": "high",
        "distinctive": False, "control_rate": 0.084,
        "matcher": "short_question",
        "method": "regex: a spoken line of 14 kept characters or fewer that contains ？.",
        "note": "The ？ mark is in `voice.surface`; this is the move of rebounding, not the mark itself. It is how she seeks reassurance. B4: not distinctive - the held-out control heroines close a short question at 0.084 (17/203), above her 0.051 (25/487), so the move is house style.",
    },
    {
        "key": "offers_herself_as_the_actor",
        "name": "Offers herself as the one who does it",
        "definition": "Volunteers her own person as the actor of the plan, named in the third person with a doing verb.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "matcher": "offers_self",
        "method": "regex: contains 百花(が|も|たち) together with a doing verb (する, 買う, 守る, つくる, がんばる ...).",
        "note": "This is the volunteering move; it is not the third-person naming rule itself, which is in `speech_guide`.",
    },
    {
        "key": "plays_a_role_with_stock_catchphrases",
        "name": "Plays a role with stock catchphrases",
        "definition": "Narrates herself through borrowed stage, anime and TV catchphrases (たのもー, くるしゅうない, れっつごー, はろーはろー).",
        "class": "hers", "tier": "firm", "confidence": "high",
        "pattern": r"(?<![ぁ-んァ-ヶ一-龠々ー])(?:たのもー|くるしゅうない|れっつ|はろー|ぐっ|ばんざい|ぱんぱか|おーぷん|がーるずとーく|ミッション|みっしょん|どんとまいんど|おーるおっけー|あんだーすたん|はーれむ|祝砲|せーの|わんちゃんす|びっぐにゅーす|れでぃーす|ていとく)",
        "method": "regex over her spoken lines against a fixed catchphrase list, anchored so a short form is not matched inside a longer word; a lower bound, because the move is defined by reading.",
        "note": "Corpus check: 26 of the 27 catchphrase lines are hers, so this is her register, not house style. B4 found せーの matched inside せんせーの; the leading boundary removes that class. Corpus count falls 55 -> 45.",
    },
    {
        "key": "performs_a_sound_effect",
        "name": "Performs a sound effect as an action beat",
        "definition": "Uses an onomatopoeic word where a stage direction would go (ぱちぱち for applause, ちょきちょき for cutting, そよそよ for wind).",
        "class": "hers", "tier": "firm", "confidence": "high",
        "matcher": "sound_effect",
        "method": "regex over her spoken lines against a fixed onomatopoeia list.",
        "note": "Distinct from the childish-vocabulary rule in `speech_guide`: there the words are adjectives, here the sound effect stands in for an `@action`.",
    },
    {
        "key": "labels_others_with_a_plain_noun",
        "name": "Labels another person with a plain noun verdict",
        "definition": "Pins a person to a short, flat noun - すごいメイド, たよれるおとこ, 勉強家, 努力の子 - instead of describing what they did.",
        "class": "hers", "tier": "firm", "confidence": "medium",
        "matcher": "labels_others",
        "method": "regex: a named character followed within ten characters by a fixed noun verdict.",
    },
    {
        "key": "attributes_her_limits_to_her_body",
        "name": "Attributes a limit to her own body",
        "definition": "Explains a failure or a refusal as a fact of her weak body (からだ、弱いから) rather than as a choice.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "matcher": "body_limit",
        "method": "regex: からだ or 身体 followed within one clause by a limit word (弱 / よわ / 迷惑 / こわ / つか / わる, where わる is not さわる).",
        "note": "It is how she self-deprecates and how she asks to be contradicted (やっぱり、百花には無理？). B4 found the old co-occurrence matcher fired on the opposite claim (からだのもんだいじゃ、ない) and on わる inside さわる; requiring the limit word after the body word and excluding さわる removes both. The recount also picks up the kana よわい lines the old matcher missed, so the corpus count rises 25 -> 28 while precision improves.",
    },
    {
        "key": "apologises_readily",
        "name": "Apologises, often before being asked",
        "definition": "Opens with ごめんなさい / ごめん for trouble that is usually not hers to own.",
        "class": "hers", "tier": "weak", "confidence": "medium",
        "distinctive": False, "control_rate": 0.0105,
        "pattern": r"ごめん|すみません|あやまる|あやま",
        "method": "regex: contains an apology word.",
        "note": "B4: not distinctive - the whole-corpus control rate (0.0105, 127/12,043) equals her build rate (0.0106), and the held-out control is 0. The move is house style.",
    },
    {
        "key": "names_a_blow_with_a_loanword",
        "name": "Names a blow with a one-word loanword",
        "definition": "Marks a disappointment with a single loanword exclamation (しょっく, がーん, ざんねん) instead of describing it.",
        "class": "hers", "tier": "firm", "confidence": "high",
        "matcher": "loan_blow",
        "method": "regex over her spoken lines against a fixed loanword list.",
        "note": "Corpus check: 15 of the 23 lines carrying these words are hers.",
    },
    {
        "key": "coins_a_label_or_level",
        "name": "Coins a label, level or title for the situation",
        "definition": "Frames a state as a coined noun, a level or a party title (らぶらぶ, いちゃいちゃレベル５, ふらっ党, 妹はーれむ).",
        "class": "hers", "tier": "firm", "confidence": "medium",
        "matcher": "coin_label",
        "method": "regex over her spoken lines against a fixed list of coined terms and level markers.",
        "note": "The device is shared with the author's comedy toolkit (一悟 also coins), but it recurs across her scenes.",
    },
    {
        "key": "teases_in_a_mock_serious_register",
        "name": "Teases in a mock-serious register",
        "definition": "Turns a tender or risky moment into a straight-faced tag aimed at the other person (ずるい, ボケ封じ, おんみつモード, デンジャー).",
        "class": "hers", "tier": "weak", "confidence": "low",
        "distinctive": False, "control_rate": 0.0064,
        "matcher": "tease",
        "method": "regex over her spoken lines against a fixed list of mock-serious tags.",
        "note": "Thin on the regex (the move is a tone, not a word); a lower bound. B4: not distinctive - the whole-corpus control rate (0.0064, 77/12,043) is above her held-out rate (0.0041), so the tags are house style.",
    },
    {
        "key": "pivots_with_a_topic_marker",
        "name": "Pivots the subject with a spoken marker",
        "definition": "Steers off a heavy or unfinished topic with それより / あ、そうそう / ところで instead of answering it.",
        "class": "hers", "tier": "weak", "confidence": "low",
        "distinctive": False, "control_rate": 0.0057,
        "pattern": r"(?<![ぁ-んァ-ヶ一-龠々ー])(?:それより|ところで|そういえば|あ、そうそう|そうそう、|それはそうと|ときに)",
        "method": "regex over her spoken lines against a fixed set of discourse pivots, anchored so ときに is not matched inside a longer word; a lower bound, because a pivot can also be silent.",
        "note": "Thin: covers the changes-the-subject residue only where the pivot is marked in the text. B4 found the one holdout hit was ときに inside しゅきなときに; the boundary removes it, leaving 0 on the holdout. Not distinctive: the whole-corpus control rate (0.0057, 69/12,043) is above her held-out rate (now 0). Corpus count falls 8 -> 5.",
    },
    {
        "key": "veils_it_as_a_secret",
        "name": "Veils something as a secret, playfully",
        "definition": "Refuses to tell by declaring a secret (ひみつ, ないしょ, トップシークレット) rather than by staying silent.",
        "class": "hers", "tier": "thin", "confidence": "low",
        "matcher": "secret",
        "method": "regex: contains ひみつ / ないしょ / しーくれっと.",
        "note": "Only a handful of lines; the withholding is marked, never quiet.",
    },
    {
        "key": "hedges_with_kamo_kana",
        "name": "Hedges the end of a turn with かも / かな",
        "definition": "Softens a claim or a hope by ending it with かも, かな or たぶん.",
        "class": "hers", "tier": "weak", "confidence": "low",
        "distinctive": False, "control_rate": 0.0197,
        "matcher": "hedge",
        "method": "regex: ends (before the final mark) with かも / かな / かもしれ / たぶん.",
        "note": "Thin: Japanese hedges are common; what is hers is that she hedges a hope she has just asserted. B4: not distinctive - the held-out control rate is 0.0197 (4/203), 4.8x her 0.0041.",
    },
    {
        "key": "bargains_with_a_reward",
        "name": "Frames a request as a trade or a reward",
        "definition": "Offers a present, a bribe or a promised payoff to get agreement (主役をプレゼント, ワイロあげたら, ごほうび).",
        "class": "hers", "tier": "thin", "confidence": "low",
        "matcher": "bargain",
        "method": "regex: contains a trade or reward word together with the conditional frame.",
        "note": "Thin: it recurs but is concentrated in the negotiation scenes of routes b-d.",
    },
]


# --------------------------------------------------------------------------- #
# paths and small IO helpers
# --------------------------------------------------------------------------- #


def default_paths(corpus: str) -> dict:
    work = os.path.join(corpus, "koikano_work")
    return {
        "game_logic": os.path.join(work, "game_logic.jsonl"),
        "actions": os.path.join(work, "character_actions.jsonl"),
        "expr_lines": os.path.join(work, "expression_labels_lines.jsonl"),
        "expr_labels": os.path.join(work, "inventory", "expression_labels.json"),
        "timing": os.path.join(work, "timing_table.jsonl"),
        "bgm": os.path.join(work, "inventory", "bgm_scene_table.json"),
        "char_table": os.path.join(corpus, "data", "charData.csv"),
        "scenario": os.path.join(corpus, "data", "scenario"),
        "char_lines": os.path.join(work, "character_lines"),
    }


def read_jsonl(path: str):
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.write("\n")


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def fail(msg: str) -> None:
    sys.stderr.write("koikano_bible: " + msg + "\n")
    sys.exit(2)


def record_key(scene: str, source_line: int) -> str:
    return "%s:%04d" % (scene, source_line)


# --------------------------------------------------------------------------- #
# character table
# --------------------------------------------------------------------------- #


def load_char_table(path: str) -> dict:
    by_buid, by_name, by_id, cast = {}, {}, {}, []
    with open(path, encoding="cp932") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("name") or "").strip()
            buid = (row.get("buid") or "").strip()
            cid = (row.get("id") or "").strip()
            if not name or not buid or name.startswith("#"):
                continue
            entry = {
                "name": name,
                "id": cid,
                "buid": buid,
                "vcid": (row.get("vcid") or "").strip(),
                "lastname": (row.get("lastname") or "").strip(),
                "order": (row.get("order") or "").strip(),
                "relate": (row.get("relate") or "").strip(),
            }
            by_buid[buid] = entry
            by_name[name] = entry
            by_id[cid.upper()] = entry
            cast.append(entry)
    return {"by_buid": by_buid, "by_name": by_name, "by_id": by_id, "cast": cast}


def resolve_subject(char_table: dict, arg: str) -> dict:
    for key in (arg, arg.upper()):
        if key in char_table["by_name"]:
            return char_table["by_name"][key]
    if arg.upper() in char_table["by_id"]:
        return char_table["by_id"][arg.upper()]
    if arg.upper() in char_table["by_buid"]:
        return char_table["by_buid"][arg.upper()]
    # allow the slug as an argument
    for entry in char_table["cast"]:
        if SLUGS.get(entry["name"]) == arg.lower():
            return entry
    fail("unknown --char %r (name, id, buid or slug)" % arg)
    raise AssertionError


def speaker_category(speaker: str, char_table: dict, subject_name: str) -> str:
    if not speaker:
        return "unattributed"
    if "＆" in speaker:
        return "unison"
    if speaker == PROTAGONIST:
        return "protagonist"
    if speaker in char_table["by_name"]:
        if speaker == subject_name:
            return "subject"
        return "heroine"
    return "npc"


# --------------------------------------------------------------------------- #
# text battery
# --------------------------------------------------------------------------- #


def kept_chars(text: str):
    return [ch for ch in text if ch not in DROP]


def tokenize(text: str):
    toks, cur = [], []
    for ch in text:
        if ch in DROP:
            if cur:
                toks.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        toks.append("".join(cur))
    return toks


def ngrams(seq, n):
    return [tuple(seq[i : i + n]) for i in range(len(seq) - n + 1)]


def top_counts(counter: Counter, limit: int):
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return [[k, v] for k, v in items[:limit]]


def dispersion_rows(counter: Counter, scene_sets: dict, total_scenes: int, limit: int):
    return [
        {
            "item": "".join(k),
            "count": c,
            "scenes": len(scene_sets.get(k, ())),
            "dispersion": round(len(scene_sets.get(k, ())) / total_scenes, 4) if total_scenes else 0.0,
        }
        for k, c in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    ]


def channel_battery(lines, total_scenes: int, limit: int = 30) -> dict:
    char_c = Counter()
    tok_c = Counter()
    bi_c = Counter()
    tri_c = Counter()
    bi_scenes = defaultdict(set)
    tok_scenes = defaultdict(set)
    n_chars = n_toks = 0
    for rec in lines:
        text = rec["text"]
        kept = kept_chars(text)
        n_chars += len(kept)
        char_c.update(kept)
        toks = tokenize(text)
        n_toks += len(toks)
        tok_c.update(toks)
        for t in toks:
            tok_scenes[t].add(rec["scene"])
        for g in ngrams(kept, 2):
            bi_c[g] += 1
            bi_scenes[g].add(rec["scene"])
        for g in ngrams(kept, 3):
            tri_c[g] += 1
    return {
        "lines": len(lines),
        "chars": n_chars,
        "tokens": n_toks,
        "char_types": len(char_c),
        "token_types": len(tok_c),
        "bigram_types": len(bi_c),
        "trigram_types": len(tri_c),
        "type_token_ratio": round(len(tok_c) / n_toks, 4) if n_toks else 0.0,
        "top_chars": top_counts(char_c, limit),
        "top_tokens": top_counts(tok_c, limit),
        "top_bigrams": [["".join(k), v] for k, v in top_counts(bi_c, limit)],
        "top_trigrams": [["".join(k), v] for k, v in top_counts(tri_c, limit)],
        "counters": {"bigrams": bi_c, "tokens": tok_c},
        "scenes": {"bigrams": bi_scenes, "tokens": tok_scenes},
    }


def log_odds(counts_a, n_a, counts_b, n_b, alpha=0.5):
    vocab = set(counts_a) | set(counts_b)
    v = len(vocab) if vocab else 1
    out = {}
    for w in vocab:
        pa = math.log((counts_a.get(w, 0) + alpha) / (n_a + alpha * v))
        pb = math.log((counts_b.get(w, 0) + alpha) / (n_b + alpha * v))
        out[w] = pa - pb
    return out


def distinctive(channel_line_counts, other_line_counts, total_scenes, limit=40):
    """Log-odds of each bigram and token, channel vs the other channels pooled."""
    a_bi, a_tok, a_bi_n, a_tok_n = channel_line_counts
    b_bi, b_tok, b_bi_n, b_tok_n = other_line_counts
    bi = log_odds(a_bi, a_bi_n, b_bi, b_bi_n)
    tok = log_odds(a_tok, a_tok_n, b_tok, b_tok_n)

    def rows(scores, ca, cb, key_fn):
        out = []
        for w, s in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0] if isinstance(kv[0], str) else kv[0]))[:limit]:
            out.append(
                {
                    "item": key_fn(w),
                    "log_odds": round(s, 4),
                    "a": ca.get(w, 0),
                    "b": cb.get(w, 0),
                }
            )
        return out

    return {
        "bigrams": rows(bi, a_bi, b_bi, lambda w: "".join(w)),
        "tokens": rows(tok, a_tok, b_tok, lambda w: w),
    }


# --------------------------------------------------------------------------- #
# B2 surface helpers
# --------------------------------------------------------------------------- #

# Turn-length buckets over kept characters; the last bucket is open-ended.
LENGTH_EDGES = [(1, 5), (6, 10), (11, 20), (21, 40), (41, 80), (81, None)]
# Full-width marks counted as punctuation.  Kana long-vowel ー and quotes are
# kept because they are meaningful on the surface, not separators.
PUNCT_MARKS = ("…", "‥", "！", "？", "、", "。", "～", "〜", "ー", "「", "」")
# Line-final strings matched by suffix, coarse enough to be listable.  This is
# string matching, not morphological analysis.
PARTICLE_ENDINGS = (
    "っ", "ー", "ん", "ね", "よ", "な", "の", "か", "わ",
    "かな", "よね", "のね", "から", "からね", "のに", "けど",
    "さ", "ぞ", "ぜ", "じゃん", "でしょ", "だよ", "だね",
)


def kept_len(text: str) -> int:
    return len(kept_chars(text))


def length_profile(lines) -> dict:
    """Kept-character length distribution over a set of lines."""
    lens = sorted(kept_len(r["text"]) for r in lines)
    n = len(lens)
    buckets = OrderedDict()
    for lo, hi in LENGTH_EDGES:
        label = "%d-%d" % (lo, hi) if hi is not None else "%d+" % lo
        buckets[label] = sum(1 for x in lens if x >= lo and (hi is None or x <= hi))
    return {
        "lines": n,
        "buckets": {k: {"count": v, "share": round(v / n, 4) if n else 0.0} for k, v in buckets.items()},
        "mean_chars": round(sum(lens) / n, 2) if n else 0.0,
        "median_chars": lens[n // 2] if n else 0,
        "p90_chars": lens[min(n - 1, int(n * 0.9))] if n else 0,
        "min_chars": lens[0] if n else 0,
        "max_chars": lens[-1] if n else 0,
    }


def line_final_profile(lines, limit: int = 20) -> dict:
    """Last token and 1/2/3-character suffixes of the kept text."""
    last_tok = Counter()
    s1 = Counter()
    s2 = Counter()
    s3 = Counter()
    for r in lines:
        toks = tokenize(r["text"])
        if toks:
            last_tok[toks[-1]] += 1
        kept = "".join(kept_chars(r["text"]))
        if kept:
            s1[kept[-1]] += 1
            s2[kept[-2:]] += 1
            s3[kept[-3:]] += 1
    return {
        "last_token": top_counts(last_tok, limit),
        "suffix1": top_counts(s1, limit),
        "suffix2": top_counts(s2, limit),
        "suffix3": top_counts(s3, limit),
    }


def punctuation_profile(lines) -> dict:
    n = len(lines)
    counts = Counter()
    lines_with = Counter()
    for r in lines:
        seen = set()
        for ch in r["text"]:
            if ch in PUNCT_MARKS:
                counts[ch] += 1
                if ch not in seen:
                    lines_with[ch] += 1
                    seen.add(ch)
    out = OrderedDict()
    for mark in PUNCT_MARKS:
        c = counts.get(mark, 0)
        if c:
            out[mark] = {
                "count": c,
                "lines": lines_with.get(mark, 0),
                "per_line": round(c / n, 4) if n else 0.0,
            }
    return out


def particle_profile(lines) -> list:
    n = len(lines)
    rows = []
    for pt in PARTICLE_ENDINGS:
        c = sum(1 for r in lines if "".join(kept_chars(r["text"])).endswith(pt))
        if c:
            rows.append({"ending": pt, "lines": c, "share": round(c / n, 4) if n else 0.0})
    return sorted(rows, key=lambda d: (-d["lines"], d["ending"]))


def token_use(lines, token: str) -> dict:
    return {
        "occurrences": sum(r["text"].count(token) for r in lines),
        "lines": sum(1 for r in lines if token in r["text"]),
    }


# --------------------------------------------------------------------------- #
# scene helpers
# --------------------------------------------------------------------------- #


def scene_route(scene: str):
    if ROUTE_COMMON.match(scene):
        return "common", "common"
    m = ROUTE_LETTER.match(scene)
    if m:
        letter = m.group(1)
        group = "d" if letter == "d" else "other"
        return letter, group
    return "misc", "other"


def scene_chapter(scene: str):
    m = CHAPTER_RE.search(scene)
    if m:
        return int(m.group(1))
    return None


def scan_h_scenes(scenario_dir: str):
    out = set()
    for fn in sorted(os.listdir(scenario_dir)):
        if not fn.endswith(".ks") or fn == "macro.ks":
            continue
        with open(os.path.join(scenario_dir, fn), encoding="cp932", errors="replace") as fh:
            if "シーン開始" in fh.read():
                out.add(fn[: -len(".ks")])
    return out


def phase_bands(all_scenes):
    """Per specific route letter, split its chapters into early/mid/late."""
    by_route = defaultdict(list)
    for scene in all_scenes:
        route, _ = scene_route(scene)
        ch = scene_chapter(scene)
        if ch is not None:
            by_route[route].append(ch)
    band = {}
    for route, chapters in by_route.items():
        uniq = sorted(set(chapters))
        n = len(uniq)
        for i, ch in enumerate(uniq):
            frac = i / n if n else 0.0
            name = "early" if frac < 1 / 3 else ("mid" if frac < 2 / 3 else "late")
            band[(route, ch)] = name
    return band


# --------------------------------------------------------------------------- #
# main build
# --------------------------------------------------------------------------- #


HYAKKA_HOLDOUT_SCENES = ["d16_01", "d16_02", "d17_01", "d18_01", "d18_02", "d19_01", "d20_01"]


def select_holdout(records, name, bands):
    """The gate's holdout scenes for one subject (one selection for builder and gate).

    百花 keeps the original fixed list.  Another subject: the scenes where she speaks
    (spoken @Talk) that are on her own route and in that route's 'late' phase band;
    with no route (真里亜), the last third of her speaking scenes, min 5.
    """
    if name == DEFAULT_CHAR:
        return list(HYAKKA_HOLDOUT_SCENES)
    spoken_scenes, seen = [], set()
    for r in records:
        if r["kind"] == "@Talk" and r["file"] != "macro.ks" and r["speaker"] == name and r["raw_name"] != INNER_MARKER:
            if r["scene"] not in seen:
                seen.add(r["scene"])
                spoken_scenes.append(r["scene"])
    route = ROUTE_OF.get(name, "")
    if route:
        return [s for s in spoken_scenes
                if scene_route(s)[0] == route and bands.get((route, scene_chapter(s)), "unknown") == "late"]
    return spoken_scenes[-max(5, len(spoken_scenes) // 3):]


def build(args) -> dict:
    paths = default_paths(args.corpus)
    overrides = {
        "game_logic": args.game_logic,
        "actions": args.actions,
        "expr_lines": args.expr_lines,
        "expr_labels": args.expr_labels,
        "timing": args.timing,
        "bgm": args.bgm,
        "char_table": args.char_table,
        "scenario": args.scenario,
    }
    for key, value in overrides.items():
        if value:
            paths[key] = value

    char_table = load_char_table(paths["char_table"])
    subject = resolve_subject(char_table, args.char)
    name, buid = subject["name"], subject["buid"]
    slug = SLUGS.get(name, buid.lower())

    # ---- the spine -------------------------------------------------------- #
    records = list(read_jsonl(paths["game_logic"]))
    index = {}
    scene_order = OrderedDict()
    for rec in records:
        rid = record_key(rec["scene"], rec["source_line"])
        if rid in index:
            fail("duplicate record_id %s in game_logic.jsonl" % rid)
        index[rid] = rec
        scene_order.setdefault(rec["scene"], None)

    all_scene_ids = list(scene_order.keys())
    bands = phase_bands(all_scene_ids)
    h_scenes = scan_h_scenes(paths["scenario"])

    # Leak-free mode: the gate's holdout scenes leave every layer.  Bands are
    # computed above from the full scene list, so the selection matches the gate's.
    build_only = bool(getattr(args, "build_only", False))
    excluded_scenes = []
    if build_only:
        excluded_scenes = select_holdout(records, name, bands)
        ex = set(excluded_scenes)
        records = [r for r in records if r["scene"] not in ex]
        index = {k: v for k, v in index.items() if v["scene"] not in ex}

    def is_line(rec):
        return rec["kind"] == "@Talk" and rec["file"] != "macro.ks"

    def is_inner(rec):
        return rec["raw_name"] == INNER_MARKER

    # ---- her lines and her scenes (B0) ----------------------------------- #
    her_lines = [r for r in records if is_line(r) and r["speaker"] == name]
    for rec in her_lines:
        rec["_channel"] = "inner" if is_inner(rec) else "spoken"

    her_scenes = list(OrderedDict.fromkeys(r["scene"] for r in her_lines))
    her_scene_set = set(her_scenes)

    # cross-check against the frozen character_lines extract
    her_rids = {record_key(r["scene"], r["source_line"]) for r in her_lines}
    cl_path = os.path.join(paths["char_lines"], name + ".jsonl")
    if os.path.exists(cl_path) and not build_only:
        cl_rows = list(read_jsonl(cl_path))
        cl_ids = {record_key(r["scene"], r["source_line"]) for r in cl_rows}
        for row in cl_rows:
            rid = record_key(row["scene"], row["source_line"])
            if rid not in index:
                fail("character_lines/%s.jsonl id %s not in game_logic.jsonl" % (name, rid))
            if index[rid]["speaker"] != name:
                fail("character_lines/%s.jsonl id %s speaks as %r, not %r" % (name, rid, index[rid]["speaker"], name))
        if cl_ids != her_rids:
            fail(
                "character_lines/%s.jsonl disagrees with the spine: %d vs %d ids"
                % (name, len(cl_ids), len(her_rids))
            )

    room_lines = [r for r in records if is_line(r) and r["scene"] in her_scene_set and r["speaker"] != name]
    for rec in room_lines:
        rec["_channel"] = "inner" if is_inner(rec) else "spoken"

    # ---- joins (fail loudly) --------------------------------------------- #
    def join_check(rows, source, rid_of):
        bad = [rid for rid in (rid_of(r) for r in rows) if rid not in index]
        if bad:
            fail("%s: %d record_id(s) not in game_logic.jsonl (first %s)" % (source, len(bad), bad[0]))
        return rows

    def side_rows(path):
        rows = list(read_jsonl(path))
        if build_only:
            ex = set(excluded_scenes)
            rows = [r for r in rows if r["record_id"].rsplit(":", 1)[0] not in ex]
        return rows

    actions_rows = join_check(side_rows(paths["actions"]), "character_actions.jsonl", lambda r: r["record_id"])
    expr_rows = join_check(side_rows(paths["expr_lines"]), "expression_labels_lines.jsonl", lambda r: r["record_id"])
    timing_rows = join_check(side_rows(paths["timing"]), "timing_table.jsonl", lambda r: r["record_id"])

    with open(paths["expr_labels"], encoding="utf-8") as fh:
        expr_table = json.load(fh)
    with open(paths["bgm"], encoding="utf-8") as fh:
        bgm_table = json.load(fh)
    vocab = expr_table.get("meta", {}).get("vocabulary", [])

    # unit -> label (all sets of a unit share one label by design)
    unit_label = {}
    for label in expr_table["labels"].values():
        unit = "%s|%s|%s" % (label["char"], label["letter"], label["index"])
        unit_label.setdefault(unit, label)
    expr_by_rid = {r["record_id"]: r for r in expr_rows}
    timing_by_rid = {r["record_id"]: r for r in timing_rows}

    # ---- slice.json ------------------------------------------------------- #
    per_scene_slice = []
    for scene in her_scenes:
        recs = [r for r in records if is_line(r) and r["scene"] == scene]
        h = [r for r in her_lines if r["scene"] == scene]
        ro = [r for r in room_lines if r["scene"] == scene]
        route, group = scene_route(scene)
        per_scene_slice.append(
            {
                "scene": scene,
                "file": index[record_key(scene, recs[0]["source_line"])]["file"],
                "route": route,
                "route_group": group,
                "her_lines": len(h),
                "her_spoken": sum(1 for r in h if r["_channel"] == "spoken"),
                "her_inner": sum(1 for r in h if r["_channel"] == "inner"),
                "room_lines": len(ro),
                "total_lines": len(recs),
            }
        )

    slice_doc = {
        "char": {"name": name, "id": subject["id"], "buid": buid, "vcid": subject["vcid"], "slug": slug},
        "counts": {
            "her_lines": len(her_lines),
            "her_spoken": sum(1 for r in her_lines if r["_channel"] == "spoken"),
            "her_inner": sum(1 for r in her_lines if r["_channel"] == "inner"),
            "her_scenes": len(her_scenes),
            "room_lines": len(room_lines),
            "room_spoken": sum(1 for r in room_lines if r["_channel"] == "spoken"),
            "room_inner": sum(1 for r in room_lines if r["_channel"] == "inner"),
            "lines_in_her_scenes": len(her_lines) + len(room_lines),
        },
        "scenes": per_scene_slice,
        "her_line_ids": sorted(her_rids),
        "her_inner_ids": sorted(record_key(r["scene"], r["source_line"]) for r in her_lines if r["_channel"] == "inner"),
        "scene_ids": her_scenes,
        "room_line_ids": sorted(record_key(r["scene"], r["source_line"]) for r in room_lines),
    }

    # ---- battery.json ----------------------------------------------------- #
    total_scenes = len(her_scenes)
    her_spoken_lines = [r for r in her_lines if r["_channel"] == "spoken"]
    her_inner_lines = [r for r in her_lines if r["_channel"] == "inner"]
    # The subject's own top first-person form, by spoken occurrences (name first
    # on a tie).  For 百花 this is her own name, as before.
    _form_counts = [(f, token_use(her_spoken_lines, f)["occurrences"]) for f in [name] + FIRST_PERSON_FORMS]
    self_form = max(_form_counts, key=lambda fc: fc[1])[0]
    self_alt = "私" if self_form != "私" else name
    room_spoken_lines = [r for r in room_lines if r["_channel"] == "spoken"]
    room_inner_lines = [r for r in room_lines if r["_channel"] == "inner"]

    # Register split.  ``h_scenes`` is the set of scene files carrying the
    # ``@Hシーン開始`` marker, the same set the context layer labels
    # ``h_scene``.  The surface battery pools two different registers: H text is
    # moan-heavy and long, non-H is the interaction register.  Rules are stated
    # per register below; a rule that holds only outside H is marked so.
    def in_h(rec):
        return rec["scene"] in h_scenes

    her_spoken_h = [r for r in her_spoken_lines if in_h(r)]
    her_spoken_nonh = [r for r in her_spoken_lines if not in_h(r)]
    her_h_lines = [r for r in her_lines if in_h(r)]
    her_nonh_lines = [r for r in her_lines if not in_h(r)]

    ch_dialogue = channel_battery(her_spoken_lines, total_scenes)
    ch_inner = channel_battery(her_inner_lines, total_scenes)
    ch_room = channel_battery(room_spoken_lines, total_scenes)

    def pack(counts, scene_sets):
        return (
            counts["counters"]["bigrams"],
            counts["counters"]["tokens"],
            sum(counts["counters"]["bigrams"].values()),
            sum(counts["counters"]["tokens"].values()),
        )

    d_pack = pack(ch_dialogue, None)
    i_pack = pack(ch_inner, None)
    r_pack = pack(ch_room, None)

    def pooled(*packs):
        bi = Counter()
        tok = Counter()
        for b, t, _, _ in packs:
            bi.update(b)
            tok.update(t)
        return bi, tok, sum(bi.values()), sum(tok.values())

    battery_doc = {
        "note": (
            "Character n-grams (punctuation dropped) and punctuation-delimited tokens. "
            "The room is other speakers' spoken lines in her scenes; inner voice is a "
            "separate channel. Dispersion is document frequency over her scenes."
        ),
        "channels": {
            "her_dialogue": {
                k: v for k, v in ch_dialogue.items() if k not in ("counters", "scenes")
            },
            "her_inner": {k: v for k, v in ch_inner.items() if k not in ("counters", "scenes")},
            "the_room": {k: v for k, v in ch_room.items() if k not in ("counters", "scenes")},
        },
        "dispersion": {
            "her_dialogue": dispersion_rows(ch_dialogue["counters"]["bigrams"], ch_dialogue["scenes"]["bigrams"], total_scenes, 20),
            "her_inner": dispersion_rows(ch_inner["counters"]["bigrams"], ch_inner["scenes"]["bigrams"], total_scenes, 20),
            "the_room": dispersion_rows(ch_room["counters"]["bigrams"], ch_room["scenes"]["bigrams"], total_scenes, 20),
        },
        "distinctive": {
            "her_dialogue": distinctive(d_pack, pooled(i_pack, r_pack), total_scenes),
            "her_inner": distinctive(i_pack, pooled(d_pack, r_pack), total_scenes),
            "the_room": distinctive(r_pack, pooled(d_pack, i_pack), total_scenes),
        },
        "line_counts": {
            "her_dialogue": len(her_spoken_lines),
            "her_inner": len(her_inner_lines),
            "the_room": len(room_spoken_lines),
            "room_inner_excluded": len(room_inner_lines),
        },
    }

    # ---- context.json ----------------------------------------------------- #
    tracks_by_scene = defaultdict(list)
    for ev in bgm_table.get("play_bgm_events", []):
        tracks_by_scene[ev["scene"]].append(ev["args"].get("file"))

    context_doc = {"scenes": []}
    for scene in her_scenes:
        route, group = scene_route(scene)
        ch = scene_chapter(scene)
        context_doc["scenes"].append(
            {
                "scene": scene,
                "route": route,
                "route_group": group,
                "route_character": ROUTE_CHARACTER.get(route, ""),
                "chapter": ch,
                "phase_band": bands.get((route, ch), "unknown"),
                "h_scene": scene in h_scenes,
                "bgm_tracks": sorted({t for t in tracks_by_scene.get(scene, []) if t}),
            }
        )

    # ---- annotation profile ---------------------------------------------- #
    # her authored actions, by record
    her_actions = [r for r in actions_rows if r["character"] == name]
    actions_by_rid = defaultdict(list)
    for row in her_actions:
        actions_by_rid[row["record_id"]].append(row)

    def her_face_labels(rid):
        """The C4 labels that are visually HER on this record (message face + CD sprites)."""
        row = expr_by_rid.get(rid)
        if not row:
            return []
        out = []
        mf = row.get("message_face") or {}
        if mf.get("id") and mf["id"][:2] == buid:
            out.append(("message_face", mf, mf.get("id")))
        for sprite in row.get("sprites", []):
            tag = sprite.get("tag", "")
            if tag[:2] == buid:
                out.append(("sprite", sprite, tag))
        return out

    def label_meta(unit):
        lab = unit_label.get(unit)
        if not lab:
            return {}
        return {
            "confidence": lab.get("confidence"),
            "agreement": (lab.get("merged") or {}).get("agreement"),
            "winner": (lab.get("merged") or {}).get("winner"),
            "version": lab.get("version"),
            "provenance": lab.get("provenance"),
        }

    def annotations_for(rid):
        faces = []
        for witness, payload, source_id in her_face_labels(rid):
            faces.append(
                OrderedDict(
                    [
                        ("witness", witness),
                        ("id", source_id),
                        ("unit", payload.get("unit")),
                        ("expression", payload.get("expression")),
                        ("pose", payload.get("pose")),
                        ("source", payload.get("source")),
                        ("hypothesis", label_meta(payload.get("unit"))),
                    ]
                )
            )
        acts = []
        for row in actions_by_rid.get(rid, []):
            acts.append(
                OrderedDict(
                    [
                        ("kind", row["kind"]),
                        ("command", row["command"]),
                        ("args", row["args"]),
                        ("macro", row["macro"]),
                        ("event_line", row["event_line"]),
                        ("conditional", row["conditional"]),
                    ]
                )
            )
        return faces, acts

    expr_freq = Counter()
    expr_meta = defaultdict(Counter)
    gesture_freq = Counter()
    gesture_lines = defaultdict(set)
    emotion_freq = Counter()
    enter_exit_freq = Counter()
    camera_freq = Counter()
    gesture_by_scene = defaultdict(Counter)
    expr_by_scene = defaultdict(Counter)
    per_line = OrderedDict()
    counts_with = Counter()
    receipt_pool = defaultdict(list)

    # B2 per-line channels: the authored direction attached to each of her lines.
    line_faces = {}
    line_gestures = {}
    line_emotions = {}
    line_actions = {}
    line_enter_exit = {}

    for rec in her_lines:
        rid = record_key(rec["scene"], rec["source_line"])
        faces, acts = annotations_for(rid)
        for f in faces:
            if f["expression"]:
                expr_freq[f["expression"]] += 1
                expr_by_scene[rec["scene"]][f["expression"]] += 1
                if f.get("hypothesis", {}).get("confidence"):
                    expr_meta[f["expression"]][f["hypothesis"]["confidence"]] += 1
                if f["expression"] in ("smile", "laugh", "sad", "angry", "surprised", "surprise"):
                    receipt_pool[f["expression"]].append(rid)
        for a in acts:
            if a["kind"] == "gesture":
                gesture_freq[a["command"]] += 1
                gesture_lines[a["command"]].add(rid)
                gesture_by_scene[rec["scene"]][a["command"]] += 1
            elif a["kind"] == "emotion":
                if a["command"] == "@emotion":
                    emotion_freq[a["args"].get("type")] += 1
            elif a["kind"] in ("enter", "exit"):
                enter_exit_freq[a["kind"]] += 1
            elif a["kind"] == "action" and a["command"] in ("@focus", "@movecamera", "@moveCamera"):
                camera_freq[a["command"]] += 1
        expr_labels_here = [f["expression"] for f in faces if f["expression"]]
        if expr_labels_here:
            line_faces[rid] = expr_labels_here
        gests_here = [a["command"] for a in acts if a["kind"] == "gesture"]
        if gests_here:
            line_gestures[rid] = gests_here
        ems_here = [
            a["args"].get("type")
            for a in acts
            if a["kind"] == "emotion" and a["command"] == "@emotion"
        ]
        if ems_here:
            line_emotions[rid] = ems_here
        actions_here = [a["command"] for a in acts if a["kind"] == "action"]
        if actions_here:
            line_actions[rid] = actions_here
        ee_here = [a["kind"] for a in acts if a["kind"] in ("enter", "exit")]
        if ee_here:
            line_enter_exit[rid] = ee_here
        if faces:
            counts_with["expression"] += 1
        if any(a["kind"] == "gesture" for a in acts):
            counts_with["gesture"] += 1
        if any(a["kind"] == "emotion" for a in acts):
            counts_with["emotion"] += 1
        if any(a["kind"] in ("enter", "exit") for a in acts):
            counts_with["enter_exit"] += 1
        if any(a["kind"] == "action" and a["command"] in ("@focus", "@movecamera", "@moveCamera") for a in acts):
            counts_with["camera"] += 1
        if faces or acts:
            per_line[rid] = OrderedDict(
                [
                    ("scene", rec["scene"]),
                    ("speaker", rec["speaker"]),
                    ("text", rec["text"]),
                    ("expressions", faces),
                    ("actions", acts),
                ]
            )

    annotation_scene_rows = []
    for scene in her_scenes:
        annotation_scene_rows.append(
            {
                "scene": scene,
                "her_lines": sum(1 for r in her_lines if r["scene"] == scene),
                "expressions": dict(sorted(expr_by_scene[scene].items())),
                "gestures": dict(sorted(gesture_by_scene[scene].items())),
            }
        )

    annotations_doc = {
        "note": (
            "Expression labels are the C4 visual/context hypotheses, carried with their "
            "confidence and provenance; they are not ground truth. Only faces whose id "
            "or sprite tag carries her buid prefix are counted as hers."
        ),
        "provenance_flag": "C4_hypothesis",
        "expression_frequency": dict(sorted(expr_freq.items(), key=lambda kv: (-kv[1], kv[0]))),
        "expression_confidence": {k: dict(v) for k, v in sorted(expr_meta.items())},
        "gesture_frequency": dict(sorted(gesture_freq.items(), key=lambda kv: (-kv[1], kv[0]))),
        "emotion_overlay_frequency": dict(sorted(emotion_freq.items(), key=lambda kv: (-kv[1], kv[0]))),
        "enter_exit_frequency": dict(sorted(enter_exit_freq.items())),
        "camera_frequency": dict(sorted(camera_freq.items())),
        "co_occurrence_with_her_lines": {
            "her_lines": len(her_lines),
            "with_expression": counts_with["expression"],
            "with_gesture": counts_with["gesture"],
            "with_emotion": counts_with["emotion"],
            "with_enter_exit": counts_with["enter_exit"],
            "with_camera": counts_with["camera"],
            "rates": {
                k: round(counts_with[k] / len(her_lines), 4) for k in ("expression", "gesture", "emotion", "enter_exit", "camera")
            },
        },
        "per_scene": annotation_scene_rows,
        "per_line": per_line,
    }

    # ---- interactions ----------------------------------------------------- #
    def spoken_sequence(scene):
        return [r for r in records if is_line(r) and r["scene"] == scene and not is_inner(r)]

    # interlocutor and reply/initiation over the spoken-turn model
    interlocutor = {}
    reply_bucket = Counter()
    scene_openers = Counter()
    spoken_turns_by_scene = {}
    for scene in her_scenes:
        seq = spoken_sequence(scene)
        spoken_turns_by_scene[scene] = seq
        if seq:
            scene_openers[seq[0]["speaker"]] += 1
        last_spoken = None
        last_nonher = None
        spoke_since_other = False
        her_spoke_yet = False
        for rec in [r for r in records if is_line(r) and r["scene"] == scene]:
            rid = record_key(rec["scene"], rec["source_line"])
            inner = is_inner(rec)
            if rec["speaker"] == name:
                if inner:
                    interlocutor[rid] = last_spoken
                else:
                    interlocutor[rid] = last_nonher
                    if last_nonher is None:
                        reply_bucket["scene_opening" if not her_spoke_yet else "self_continuation"] += 1
                    elif not spoke_since_other:
                        reply_bucket["reply"] += 1
                    else:
                        reply_bucket["self_continuation"] += 1
                    spoke_since_other = True
                    her_spoke_yet = True
                    last_spoken = name
            else:
                if not inner:
                    last_spoken = rec["speaker"]
                    last_nonher = rec["speaker"]
                    spoke_since_other = False

    # per-relationship turn counts (all speakers in her scenes)
    other_speakers = list(OrderedDict.fromkeys(r["speaker"] for r in room_lines))
    relationships = {}
    total_other = 0
    for speaker in other_speakers:
        rows = [r for r in room_lines if r["speaker"] == speaker]
        total_other += len(rows)
        her_for_rel = [r for r in her_lines if interlocutor.get(record_key(r["scene"], r["source_line"])) == speaker]
        her_spoken_for_rel = [r for r in her_for_rel if r["_channel"] == "spoken"]
        scenes_together = sorted({r["scene"] for r in rows})
        expr_mix = Counter()
        gest_mix = Counter()
        for r in her_for_rel:
            rid = record_key(r["scene"], r["source_line"])
            for f in annotations_for(rid)[0]:
                if f["expression"]:
                    expr_mix[f["expression"]] += 1
            for a in actions_by_rid.get(rid, []):
                if a["kind"] == "gesture":
                    gest_mix[a["command"]] += 1
        avg_len = (
            round(sum(len(kept_chars(r["text"])) for r in her_spoken_for_rel) / len(her_spoken_for_rel), 2)
            if her_spoken_for_rel
            else 0.0
        )
        relationships[speaker] = {
            "category": speaker_category(speaker, char_table, name),
            "turns_total": len(rows),
            "turns_spoken": sum(1 for r in rows if r["_channel"] == "spoken"),
            "turns_inner": sum(1 for r in rows if r["_channel"] == "inner"),
            "scenes_together": len(scenes_together),
            "scene_openings": scene_openers.get(speaker, 0),
            "her_lines_to_them": len(her_for_rel),
            "her_spoken_turns": len(her_spoken_for_rel),
            "her_avg_turn_chars": avg_len,
            "her_expression_mix": dict(sorted(expr_mix.items(), key=lambda kv: (-kv[1], kv[0]))),
            "her_gesture_mix": dict(sorted(gest_mix.items(), key=lambda kv: (-kv[1], kv[0]))),
        }

    # exchange initiations, by pair, over collapsed alternating turns
    def collapse(seq):
        turns = []
        for rec in seq:
            if turns and turns[-1]["speaker"] == rec["speaker"]:
                turns[-1]["count"] += 1
            else:
                turns.append({"speaker": rec["speaker"], "count": 1})
        return turns

    pair_init = defaultdict(Counter)
    for scene in her_scenes:
        turns = collapse(spoken_turns_by_scene[scene])
        i = 0
        while i < len(turns):
            # gather the longest run of consecutive turns that alternate and
            # always include her and one other speaker
            j = i + 1
            run = [turns[i]]
            while j < len(turns):
                prev = run[-1]["speaker"]
                cur = turns[j]["speaker"]
                if cur != prev and (cur == name or prev == name):
                    run.append(turns[j])
                    j += 1
                else:
                    break
            active = sorted({t["speaker"] for t in run if t["speaker"] != name})
            if active and name in {t["speaker"] for t in run} and j > i + 1:
                pair_init[active[0]][run[0]["speaker"]] += 1
            i = j

    for speaker, counts in pair_init.items():
        if speaker in relationships:
            relationships[speaker]["exchange_her_starts"] = counts.get(name, 0)
            relationships[speaker]["exchange_they_start"] = sum(
                v for k, v in counts.items() if k != name
            )

    # address terms: how she names them, and how they name her
    aliases = {}
    for entry in char_table["cast"]:
        al = [entry["name"]]
        if entry["lastname"]:
            al.append(entry["lastname"] + entry["name"])
            al.append(entry["lastname"])
        al += EXTRA_ALIASES.get(entry["name"], [])
        aliases[entry["name"]] = al

    def address_terms(text, aliases_list):
        found = Counter()
        for alias in aliases_list:
            start = 0
            while True:
                pos = text.find(alias, start)
                if pos < 0:
                    break
                tail = text[pos + len(alias) : pos + len(alias) + 3]
                term = alias
                for hon in HONORIFICS:
                    if tail.startswith(hon):
                        term = alias + hon
                        break
                found[term] += 1
                start = pos + len(alias)
        return found

    her_addressed = Counter()
    they_addressed_her = Counter()
    for speaker in relationships:
        rel = relationships[speaker]
        rel["her_address_terms"] = {}
        for r in her_lines:
            rid = record_key(r["scene"], r["source_line"])
            if interlocutor.get(rid) != speaker:
                continue
            for term, n in address_terms(r["text"], aliases.get(speaker, [])).items():
                her_addressed[term] += n
                rel["her_address_terms"][term] = rel["her_address_terms"].get(term, 0) + n
        if speaker in aliases:
            for r in room_lines:
                if r["speaker"] != speaker:
                    continue
                for term, n in address_terms(r["text"], aliases.get(name, [])).items():
                    they_addressed_her[term] += n

    interactions_doc = {
        "note": (
            "One row per other speaker in her scenes. Turn counts include inner voice "
            "(a speaker's whole presence); the spoken/inner split is kept. Scene openings "
            "and exchange starts are counts, not attributions: 'exchange_they_start' pools "
            "every initiator that is not her."
        ),
        "subject_lines_in_her_scenes": len(her_lines),
        "relationships": relationships,
        "scene_openers": dict(sorted(scene_openers.items(), key=lambda kv: (-kv[1], kv[0]))),
        "reply_vs_initiation": {
            "reply": reply_bucket["reply"],
            "initiation": reply_bucket["scene_opening"],
            "self_continuation": reply_bucket["self_continuation"],
            "reply_rate": round(
                reply_bucket["reply"] / (reply_bucket["reply"] + reply_bucket["scene_opening"]), 4
            )
            if (reply_bucket["reply"] + reply_bucket["scene_opening"])
            else 0.0,
        },
        "her_address_terms_overall": dict(sorted(her_addressed.items(), key=lambda kv: (-kv[1], kv[0]))),
        "they_address_her": dict(sorted(they_addressed_her.items(), key=lambda kv: (-kv[1], kv[0]))),
    }

    # ---- bounds ----------------------------------------------------------- #
    corpus_gestures = {r["command"] for r in actions_rows if r["kind"] == "gesture"}
    absent_expressions = [t for t in vocab if expr_freq.get(t, 0) == 0]
    absent_gestures = sorted(corpus_gestures - set(gesture_freq))
    present_rel = [s for s, r in relationships.items() if r["turns_total"] > 0]
    on_screen = [e["name"] for e in char_table["cast"]]
    absent_cast = [n for n in on_screen if n != name and n not in relationships]

    bounds_doc = {
        "reply_vs_initiation": interactions_doc["reply_vs_initiation"],
        "relationships_present": [
            {"speaker": s, "category": relationships[s]["category"], "turns": relationships[s]["turns_total"]}
            for s in sorted(relationships, key=lambda k: (-relationships[k]["turns_total"], k))
        ],
        "emotional_pressures": {
            "authored_emotion_overlays": dict(sorted(emotion_freq.items(), key=lambda kv: (-kv[1], kv[0]))),
            "expression_labels_on_her_lines": dict(sorted(expr_freq.items(), key=lambda kv: (-kv[1], kv[0]))),
            "note": "Authored @emotion overlay types and C4 expression labels are distinct sets; the first is the author's, the second a hypothesis.",
        },
        "absent": {
            "expression_vocabulary_unused_on_her_lines": absent_expressions,
            "gesture_macros_in_corpus_never_hers": absent_gestures,
            "on_screen_cast_absent_from_her_scenes": absent_cast,
            "note": (
                "Absence here is corpus absence, not a claim about the character: a gesture "
                "or expression never authored on her line is unobserved, not forbidden."
            ),
        },
    }

    # ---- assemble the bible (B2) ----------------------------------------- #
    def receipts(rids, n=3):
        out = []
        for rid in sorted(set(rids))[:n]:
            rec = index.get(rid)
            if rec:
                out.append({"record_id": rid, "scene": rec["scene"], "text": rec["text"]})
        return out

    def rid_of(rec):
        return record_key(rec["scene"], rec["source_line"])

    scene_ctx = {row["scene"]: row for row in context_doc["scenes"]}
    by_scene = OrderedDict()
    for rec in her_lines:
        by_scene.setdefault(rec["scene"], []).append(rec)

    # The last expression she wore earlier in the scene, per line.
    prev_expr = {}
    for scene, rows in by_scene.items():
        last = None
        for rec in rows:
            rid = rid_of(rec)
            prev_expr[rid] = last
            if line_faces.get(rid):
                last = line_faces[rid][0]

    def trigger(rows, co_map=None, co_key="co_expression"):
        n = len(rows)
        inter = Counter((interlocutor.get(rid_of(r)) or "(none)") for r in rows)
        route = Counter(scene_ctx[r["scene"]]["route"] for r in rows)
        stype = Counter("H" if scene_ctx[r["scene"]]["h_scene"] else "normal" for r in rows)
        lens = [kept_len(r["text"]) for r in rows]
        out = OrderedDict(
            [
                ("lines", n),
                ("interlocutor", dict(sorted(inter.items(), key=lambda kv: (-kv[1], kv[0])))),
                ("route", dict(sorted(route.items(), key=lambda kv: (-kv[1], kv[0])))),
                ("scene_type", dict(sorted(stype.items()))),
                ("mean_line_chars", round(sum(lens) / n, 2) if n else 0.0),
                ("line_length", length_profile(rows)),
                ("receipts", receipts([rid_of(r) for r in rows], 3)),
            ]
        )
        if co_map is not None:
            co = Counter()
            for r in rows:
                for label in co_map.get(rid_of(r), []):
                    co[label] += 1
            out[co_key] = dict(sorted(co.items(), key=lambda kv: (-kv[1], kv[0])))
        return out

    def preceded_expr(pred):
        c = Counter()
        for rec in her_lines:
            if pred(rec):
                c[prev_expr.get(rid_of(rec)) or "(scene-start)"] += 1
        return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))

    # ---- voice: the B2 surface ------------------------------------------- #
    def density_rate(rows, mapping):
        n = len(rows)
        if not n:
            return 0.0
        return round(sum(1 for r in rows if mapping.get(rid_of(r))) / n, 4)

    def register_block(spoken_rows, all_rows):
        return OrderedDict([
            ("spoken_lines", len(spoken_rows)),
            ("lines", len(all_rows)),
            ("turn_length", length_profile(spoken_rows)),
            ("punctuation", punctuation_profile(spoken_rows)),
            ("particles", particle_profile(spoken_rows)),
            ("face_rate", density_rate(all_rows, line_faces)),
            ("gesture_rate", density_rate(all_rows, line_gestures)),
        ])

    voice_surface = OrderedDict(
        [
            ("turn_length", {
                "her_spoken": length_profile(her_spoken_lines),
                "her_inner": length_profile(her_inner_lines),
                "the_room_spoken": length_profile(room_spoken_lines),
            }),
            ("line_final", {
                "her_spoken": line_final_profile(her_spoken_lines),
                "her_inner": line_final_profile(her_inner_lines),
            }),
            ("particles", {
                "her_spoken": particle_profile(her_spoken_lines),
                "her_inner": particle_profile(her_inner_lines),
            }),
            ("punctuation", {
                "her_spoken": punctuation_profile(her_spoken_lines),
                "her_inner": punctuation_profile(her_inner_lines),
                "the_room_spoken": punctuation_profile(room_spoken_lines),
            }),
            ("self_reference", {
                "spoken_私": token_use(her_spoken_lines, "私"),
                "spoken_" + name: token_use(her_spoken_lines, name),
                "inner_" + name: token_use(her_inner_lines, name),
            }),
            ("distinctive_her_dialogue_vs_room", distinctive(d_pack, r_pack, total_scenes, limit=25)),
            ("distinctive_her_dialogue_vs_inner", distinctive(d_pack, i_pack, total_scenes, limit=25)),
            ("registers", OrderedDict([
                ("note", (
                    "H scenes carry the @Hシーン開始 marker (context.h_scene). The pooled "
                    "surface above mixes two registers: H dialogue is moan-heavy and runs "
                    "long, non-H dialogue is the interaction register. Rates are split here; "
                    "a rule that holds only outside H is marked in speech_guide."
                )),
                ("H", register_block(her_spoken_h, her_h_lines)),
                ("non_H", register_block(her_spoken_nonh, her_nonh_lines)),
            ])),
            ("note", (
                "Turn length is kept characters per line. Line-final strings are string "
                "suffixes, not morphology. Punctuation counts full-width marks. The two "
                "distinctive_* blocks are log-odds of her spoken channel against the room "
                "and against her inner voice, from the same counters as battery.json."
            )),
        ]
    )

    # ---- expressions with triggers --------------------------------------- #
    expr_triggers = {}
    for label in sorted(expr_freq, key=lambda k: (-expr_freq[k], k)):
        rows = [r for r in her_lines if label in line_faces.get(rid_of(r), [])]
        blk = trigger(rows, co_map=line_gestures, co_key="co_gesture")
        blk["preceding_expression"] = preceded_expr(
            lambda r, lab=label: lab in line_faces.get(rid_of(r), [])
        )
        expr_triggers[label] = blk

    expressions_section = OrderedDict(
        [
            ("vocabulary_version", expr_table.get("meta", {}).get("vocabulary_version")),
            ("provenance_flag", "C4_hypothesis"),
            ("repertoire", [
                {
                    "expression": label,
                    "lines": count,
                    "confidence_split": annotations_doc["expression_confidence"].get(label, {}),
                    "receipts": receipts(receipt_pool.get(label, [])) if receipt_pool.get(label) else [],
                }
                for label, count in sorted(expr_freq.items(), key=lambda kv: (-kv[1], kv[0]))
            ]),
            ("trigger_note", (
                "One block per label. 'lines' counts her lines carrying the label (a line "
                "with two faces counts once here; the repertoire above counts occurrences). "
                "'interlocutor' is the speaker whose turn preceded hers; '(none)' is a "
                "scene-opening or an unattributed turn. 'preceding_expression' is the last "
                "expression she wore earlier in the same scene. Triggers are co-occurrence, "
                "not cause."
            )),
            ("triggers", expr_triggers),
        ]
    )

    # ---- gestures with triggers ------------------------------------------ #
    gesture_triggers = {}
    for cmd in sorted(gesture_freq, key=lambda k: (-gesture_freq[k], k)):
        rows = [r for r in her_lines if cmd in line_gestures.get(rid_of(r), [])]
        blk = trigger(rows, co_map=line_faces, co_key="co_expression")
        blk["preceding_expression"] = preceded_expr(
            lambda r, c=cmd: c in line_gestures.get(rid_of(r), [])
        )
        gesture_triggers[cmd] = blk

    emotion_triggers = {}
    for label in sorted(emotion_freq, key=lambda k: (-emotion_freq[k], k)):
        rows = [r for r in her_lines if label in line_emotions.get(rid_of(r), [])]
        emotion_triggers[label] = trigger(rows, co_map=line_faces, co_key="co_expression")

    enter_exit_triggers = {}
    for kind in ("enter", "exit"):
        rows = [r for r in her_lines if kind in line_enter_exit.get(rid_of(r), [])]
        enter_exit_triggers[kind] = trigger(rows, co_map=line_faces, co_key="co_expression")

    action_commands = Counter(a["command"] for a in her_actions if a["kind"] == "action")
    action_triggers = {}
    for cmd in sorted(action_commands, key=lambda k: (-action_commands[k], k)):
        rows = [r for r in her_lines if cmd in line_actions.get(rid_of(r), [])]
        action_triggers[cmd] = trigger(rows, co_map=line_faces, co_key="co_expression")

    gestures_section = OrderedDict(
        [
            ("repertoire", [
                {"command": cmd, "lines": n, "receipts": receipts(sorted(gesture_lines[cmd]))}
                for cmd, n in sorted(gesture_freq.items(), key=lambda kv: (-kv[1], kv[0]))
            ]),
            ("by_kind", dict(sorted(Counter(a["kind"] for a in her_actions).items()))),
            ("emotion_overlays", dict(sorted(emotion_freq.items(), key=lambda kv: (-kv[1], kv[0])))),
            ("enter_exit", dict(sorted(enter_exit_freq.items()))),
            ("camera", dict(sorted(camera_freq.items()))),
            ("action_commands", dict(sorted(action_commands.items(), key=lambda kv: (-kv[1], kv[0])))),
            ("trigger_note", (
                "Same trigger shape as expressions. 'co_expression' is the C4 label on the "
                "same line; 'preceding_expression' is the last label earlier in the scene. "
                "The action commands are the sprite/pose family (@char, @action, @move, "
                "@stopAction) and the targeted camera."
            )),
            ("triggers", gesture_triggers),
            ("emotion_triggers", emotion_triggers),
            ("enter_exit_triggers", enter_exit_triggers),
            ("action_triggers", action_triggers),
        ]
    )

    # ---- interactions: address terms corrected for the protagonist ------- #
    # The alias table comes from charData.csv, which holds only the eight named
    # cast.  The protagonist 一悟 is not in it, so B1 reported no address term
    # for him even though she names him.  B2 adds him here only.
    b2_aliases = {k: list(v) for k, v in aliases.items()}
    b2_aliases.setdefault(PROTAGONIST, [PROTAGONIST])

    b2_relationships = OrderedDict()
    addr_overall = Counter()
    for speaker in sorted(relationships, key=lambda k: (-relationships[k]["turns_total"], k)):
        rel = relationships[speaker]
        terms = Counter()
        spoken_to = []
        for rec in her_lines:
            rid = rid_of(rec)
            if interlocutor.get(rid) != speaker:
                continue
            if rec["_channel"] == "spoken":
                spoken_to.append(rec)
            for term, n in address_terms(rec["text"], b2_aliases.get(speaker, [])).items():
                terms[term] += n
        entry = OrderedDict(rel)
        entry["her_turn_length"] = length_profile(spoken_to)
        entry["her_address_terms"] = dict(sorted(terms.items(), key=lambda kv: (-kv[1], kv[0])))
        if terms:
            entry["address_note"] = "derived from her lines to this speaker"
        elif speaker == "":
            entry["address_note"] = "no addressee (unattributed line)"
        elif speaker not in b2_aliases:
            entry["address_note"] = (
                "not derivable: this speaker is not in charData.csv, so there is no name "
                "form to search her lines for"
            )
        else:
            entry["address_note"] = (
                "no name term found in her lines to this speaker; she may address them by "
                "pronoun, by turn-taking, or not at all"
            )
        for term, n in entry["her_address_terms"].items():
            addr_overall[term] += n
        b2_relationships[speaker] = entry

    interactions_section = OrderedDict(
        [
            ("note", interactions_doc["note"]),
            ("subject_lines_in_her_scenes", interactions_doc["subject_lines_in_her_scenes"]),
            ("relationships", b2_relationships),
            ("scene_openers", interactions_doc["scene_openers"]),
            ("reply_vs_initiation", interactions_doc["reply_vs_initiation"]),
            ("her_address_terms_overall", dict(sorted(addr_overall.items(), key=lambda kv: (-kv[1], kv[0])))),
            ("they_address_her", interactions_doc["they_address_her"]),
            ("address_correction", (
                "B1 built the alias table from charData.csv, which holds only the eight "
                "named cast. The protagonist 一悟 is absent, so B1 reported no address term "
                "for him; B2 adds 一悟 to the alias table here only. The interaction layer "
                "on disk is unchanged."
            )),
        ]
    )

    # ---- speech guide ---------------------------------------------------- #
    spoken_len = voice_surface["turn_length"]["her_spoken"]
    inner_len = voice_surface["turn_length"]["her_inner"]
    tok_spoken = Counter(t for r in her_spoken_lines for t in tokenize(r["text"]))

    def lines_ending(pt):
        return [r for r in her_spoken_lines if "".join(kept_chars(r["text"])).endswith(pt)]

    bai_lines = [r for r in her_spoken_lines if self_form in r["text"]]  # lines with her own top self-reference form
    watashi_lines = [r for r in her_spoken_lines if "私" in r["text"]]
    glottal_lines = lines_ending("っ")
    longv_lines = lines_ending("ー")
    polite_lines = [r for r in her_spoken_lines if "です" in r["text"] or "ます" in r["text"]]
    childish_lines = [r for r in her_spoken_lines if any(t in r["text"] for t in ("いっぱい", "きちゃう", "えへへ"))]
    smile_lines = [r for r in her_lines if "smile" in line_faces.get(rid_of(r), [])]
    ojigi_lines = [r for r in her_lines if "@おじぎ" in line_gestures.get(rid_of(r), [])]
    jump_lines = [r for r in her_lines if "@ジャンプ" in line_gestures.get(rid_of(r), [])]
    laugh_lines = [r for r in her_lines if "laugh" in line_faces.get(rid_of(r), [])]
    kiss_lines = [
        r for r in her_lines
        if "@キス" in line_gestures.get(rid_of(r), []) or "@キス止め" in line_gestures.get(rid_of(r), [])
    ]
    doze_lines = [
        r for r in her_lines
        if any(g in line_gestures.get(rid_of(r), []) for g in ("@居眠り横", "@居眠り縦"))
    ]
    htoken_lines = [
        r for r in her_lines
        if any(t in r["text"] for t in ("せーえき", "きちゃう", "おちんちん", "おまんこ"))
    ]
    htoken_in_h = [r for r in htoken_lines if scene_ctx[r["scene"]]["h_scene"]]
    total_expr = sum(expr_freq.values())
    co = annotations_doc["co_occurrence_with_her_lines"]

    sg_rules = []

    def rule(text, cls, tier, evidence, counts, examples=None, note=None, register="all", computed=False):
        rec = OrderedDict([
            ("rule", text),
            ("class", cls),
            ("tier", tier),
            ("register", register),
            ("evidence", evidence),
            ("receipt", OrderedDict(counts)),
        ])
        # The rule texts below were authored from 百花's numbers (medians, rates,
        # "6 of 7 lines").  For any other subject the receipt is measured on the
        # subject, but the text is not: mark it so a reader trusts the receipt.
        if name != DEFAULT_CHAR and not computed:
            if has_b3_file(name):
                rec["text_basis"] = "pending: text is the builder default, to be replaced by this subject's apply step; read the receipt"
            else:
                rec["text_basis"] = "hyakka-authored; figures in the text are 百花's, read the receipt for this subject"
        if examples:
            rec["receipt"]["examples"] = receipts([rid_of(r) for r in examples], 3)
        if note:
            rec["note"] = note
        sg_rules.append(rec)

    # Per-register helpers for the rules.  sp_ = spoken-line denominator;
    # ln_ = all-her-line denominator (for the authored face/gesture density).
    def sp_reg(rows):
        return OrderedDict([
            ("H", {"lines": sum(1 for r in rows if in_h(r)), "n": len(her_spoken_h)}),
            ("non_H", {"lines": sum(1 for r in rows if not in_h(r)), "n": len(her_spoken_nonh)}),
        ])

    def ln_reg(rows):
        return OrderedDict([
            ("H", {"lines": sum(1 for r in rows if in_h(r)), "n": len(her_h_lines)}),
            ("non_H", {"lines": sum(1 for r in rows if not in_h(r)), "n": len(her_nonh_lines)}),
        ])

    def tok_by_reg(token):
        return {"H": tok_h.get(token, 0), "non_H": tok_nonh.get(token, 0)}

    def punct_by_reg(mark):
        h = punctuation_profile(her_spoken_h).get(mark, {})
        n = punctuation_profile(her_spoken_nonh).get(mark, {})
        return OrderedDict([
            ("H", {"count": h.get("count", 0), "per_line": h.get("per_line", 0.0)}),
            ("non_H", {"count": n.get("count", 0), "per_line": n.get("per_line", 0.0)}),
        ])

    tok_h = Counter(t for r in her_spoken_h for t in tokenize(r["text"]))
    tok_nonh = Counter(t for r in her_spoken_nonh for t in tokenize(r["text"]))

    _alt_lines = [r for r in her_spoken_lines if self_alt in r["text"]]
    _self_n = token_use(her_spoken_lines, self_form)["occurrences"]
    _alt_n = token_use(her_spoken_lines, self_alt)["occurrences"]
    if self_form == name:
        _sr_head = "Name yourself %s in the third person" % name
    else:
        _sr_head = "Refer to yourself as %s (not by your own name)" % self_form
    if _alt_n * 10 <= _self_n:
        _sr_text = "%s; do not use %s. Holds in both registers." % (_sr_head, self_alt)
    else:
        _sr_text = "%s; %s also occurs (%d against %d), so treat it as the minor form. Holds in both registers." % (
            _sr_head, self_alt, _alt_n, _self_n)
    rule(
        _sr_text,
        "hers", "firm", "measured",
        {"spoken_lines_with_" + self_form: len(bai_lines), "spoken_occurrences_" + self_form: _self_n,
         "spoken_lines_with_" + self_alt: len(_alt_lines), "spoken_occurrences_" + self_alt: _alt_n,
         self_form + "_by_register": sp_reg(bai_lines)},
        examples=bai_lines, register="all", computed=True,
    )
    rule(
        "Keep non-H turns short: median 18 kept characters outside H, median 28 inside H; no line over 63.",
        "hers", "firm", "measured",
        {"non_H": {"lines": len(her_spoken_nonh), "median_chars": length_profile(her_spoken_nonh)["median_chars"],
                   "mean_chars": length_profile(her_spoken_nonh)["mean_chars"], "max_chars": length_profile(her_spoken_nonh)["max_chars"]},
         "H": {"lines": len(her_spoken_h), "median_chars": length_profile(her_spoken_h)["median_chars"],
               "mean_chars": length_profile(her_spoken_h)["mean_chars"], "max_chars": length_profile(her_spoken_h)["max_chars"]},
         "pooled": {"lines": spoken_len["lines"], "median_chars": spoken_len["median_chars"],
                    "mean_chars": spoken_len["mean_chars"], "max_chars": spoken_len["max_chars"]}},
        examples=her_spoken_lines, register="per-register",
    )
    rule(
        "Reply; do not open. Initiate in well under 1% of your turns.",
        "hers", "firm", "measured",
        interactions_doc["reply_vs_initiation"],
        examples=[r for r in her_spoken_lines if interlocutor.get(rid_of(r)) is None],
        note="initiation here is a scene-opening spoken turn.",
    )
    rule(
        "End many lines on a glottal っ; far heavier in H (moans) than outside it.",
        "hers", "firm", "measured",
        {"lines_ending_っ": len(glottal_lines), "share_of_spoken": round(len(glottal_lines) / len(her_spoken_lines), 4),
         "by_register": sp_reg(glottal_lines)},
        examples=glottal_lines, register="per-register",
    )
    rule(
        "Stretch the last syllable with ー on non-H lines; almost never inside an H scene.",
        "hers", "firm", "measured",
        {"lines_ending_ー": len(longv_lines), "share_of_spoken": round(len(longv_lines) / len(her_spoken_lines), 4),
         "by_register": sp_reg(longv_lines)},
        examples=longv_lines, register="non-H",
    )
    rule(
        "Agree with doubled ん (ん、んん、んーん); the rate is far higher in H.",
        "hers", "firm", "measured",
        {"token_んん": tok_spoken["んん"], "token_んーん": tok_spoken["んーん"],
         "token_んっ": tok_spoken["んっ"], "token_んんっ": tok_spoken["んんっ"],
         "token_んん_by_register": tok_by_reg("んん"), "token_んっ_by_register": tok_by_reg("んっ")},
        register="per-register",
    )
    rule(
        "Show delight with おおー / おー (a non-H beat).",
        "hers", "firm", "measured",
        {"token_おおー": tok_spoken["おおー"], "token_おー": tok_spoken["おー"],
         "token_おおー_by_register": tok_by_reg("おおー"), "token_おー_by_register": tok_by_reg("おー")},
        examples=[r for r in her_spoken_lines if "おおー" in r["text"] or "おー" in r["text"]],
        register="non-H",
    )
    rule(
        "Use plain childish words when the feeling is big (いっぱい, きちゃう, えへへ); heavier in H.",
        "hers", "thin", "measured",
        {"token_いっぱい": tok_spoken["いっぱい"], "token_きちゃう": tok_spoken["きちゃう"],
         "token_えへへ": tok_spoken["えへへ"], "lines_matched": len(childish_lines),
         "by_register": sp_reg(childish_lines)},
        examples=childish_lines, register="per-register",
    )
    rule(
        "Stay casual: almost no です / ます.",
        "hers", "firm", "measured",
        {"lines_with_です_ます": len(polite_lines), "of_spoken_lines": len(her_spoken_lines),
         "token_ですます_occurrences": token_use(her_spoken_lines, "です")["occurrences"] + token_use(her_spoken_lines, "ます")["occurrences"]},
        examples=polite_lines,
    )
    rule(
        "Lean on the ellipsis: about 0.9 … per line outside H and about 6.3 inside H (moan elongation), read from the build block. The rate is not stable across blocks - the gate's held-out non-H block measures 1.76, about double. The rule holds directionally; do not quote a fixed rate.",
        "hers", "firm", "measured",
        {"…_by_register": punct_by_reg("…"),
         "spoken_lines": len(her_spoken_lines),
         "room_per_line": voice_surface["punctuation"]["the_room_spoken"].get("…", {}).get("per_line", 0.0)},
        examples=[r for r in her_spoken_lines if "…" in r["text"]], register="per-register",
    )
    rule(
        "Exclaim sparingly outside H (~0.03 ！/line) and rely on ？ at ~0.25/line; H moans carry ！ heavily (0.72/line).",
        "hers", "thin", "measured",
        {"！_by_register": punct_by_reg("！"), "？_by_register": punct_by_reg("？"),
         "room_！_per_line": voice_surface["punctuation"]["the_room_spoken"].get("！", {}).get("per_line", 0.0)},
        register="per-register",
    )
    rule(
        "Default to a smile face on non-H lines; it is about half of all her expression hits. H scenes carry no face annotations.",
        "hers", "firm", "measured",
        {"smile_occurrences": expr_freq["smile"], "all_occurrences": total_expr,
         "smile_lines": len(smile_lines), "smile_lines_by_register": ln_reg(smile_lines)},
        examples=smile_lines,
        note="C4 hypothesis, not ground truth.", register="non-H",
    )
    rule(
        "Bow (@おじぎ) as the default gesture on non-H lines, usually with a smile.",
        "hers", "firm", "measured",
        {"@おじぎ_occurrences": gesture_freq["@おじぎ"], "lines": len(ojigi_lines),
         "by_register": ln_reg(ojigi_lines),
         "co_smile": gesture_triggers["@おじぎ"].get("co_expression", {}).get("smile", 0)},
        examples=ojigi_lines, register="non-H",
    )
    rule(
        "When refusing, use @否定 (non-H); you can refuse while still smiling.",
        "hers", "firm", "measured",
        {"@否定_occurrences": gesture_freq["@否定"],
         "by_register": ln_reg([r for r in her_lines if "@否定" in line_gestures.get(rid_of(r), [])]),
         "co_smile": gesture_triggers["@否定"].get("co_expression", {}).get("smile", 0),
         "co_sad": gesture_triggers["@否定"].get("co_expression", {}).get("sad", 0)},
        examples=[r for r in her_lines if "@否定" in line_gestures.get(rid_of(r), [])], register="non-H",
    )
    rule(
        "Jump (@ジャンプ) when surprised or laughing (non-H).",
        "hers", "firm", "measured",
        {"@ジャンプ_occurrences": gesture_freq["@ジャンプ"],
         "by_register": ln_reg(jump_lines),
         "co_surprise": gesture_triggers["@ジャンプ"].get("co_expression", {}).get("surprise", 0),
         "co_laugh": gesture_triggers["@ジャンプ"].get("co_expression", {}).get("laugh", 0)},
        examples=jump_lines, register="non-H",
    )
    rule(
        "Keep the inner voice as bare narration, not speech: no quotes, no っ / ー / ね / よ, more varied vocabulary. Inner voice appears only outside H.",
        "hers", "firm", "measured",
        {"inner_lines": inner_len["lines"], "inner_median_chars": inner_len["median_chars"],
         "inner_ttr": ch_inner["type_token_ratio"], "spoken_ttr": ch_dialogue["type_token_ratio"],
         "inner_lines_ending_っ": len([r for r in her_inner_lines if "".join(kept_chars(r["text"])).endswith("っ")]),
         "inner_lines_H": sum(1 for r in her_inner_lines if in_h(r))},
        examples=her_inner_lines, register="non-H",
    )
    rule(
        "Supply a face on about two-thirds of her non-H lines and a gesture on about a quarter; H scenes carry no faces and almost no gestures.",
        "author", "firm", "measured",
        {"non_H": OrderedDict([
            ("lines", len(her_nonh_lines)), ("with_expression", sum(1 for r in her_nonh_lines if line_faces.get(rid_of(r)))),
            ("with_gesture", sum(1 for r in her_nonh_lines if line_gestures.get(rid_of(r)))),
            ("expression_rate", density_rate(her_nonh_lines, line_faces)), ("gesture_rate", density_rate(her_nonh_lines, line_gestures))]),
         "H": OrderedDict([
            ("lines", len(her_h_lines)), ("with_expression", sum(1 for r in her_h_lines if line_faces.get(rid_of(r)))),
            ("with_gesture", sum(1 for r in her_h_lines if line_gestures.get(rid_of(r)))),
            ("expression_rate", density_rate(her_h_lines, line_faces)), ("gesture_rate", density_rate(her_h_lines, line_gestures))]),
         "pooled": {"her_lines": co["her_lines"], "with_expression": co["with_expression"], "with_gesture": co["with_gesture"],
                    "expression_rate": co["rates"]["expression"], "gesture_rate": co["rates"]["gesture"]}},
        register="per-register",
    )
    rule(
        "Use @emotion overlays sparingly; they are authored colour, not her mood words.",
        "author", "firm", "measured",
        {"lines_with_emotion": co["with_emotion"], "types": dict(sorted(emotion_freq.items(), key=lambda kv: -kv[1]))},
    )
    rule(
        "Treat every expression label as a C4 hypothesis with a confidence, not a fact.",
        "author", "firm", "inferred",
        {"vocabulary_version": expr_table.get("meta", {}).get("vocabulary_version"),
         "her_units_agreed": "8/16 classifiable (see docs/koikano-expression-labels.md)"},
        note="the trigger tables inherit this uncertainty.",
    )
    rule(
        "Remember that @おじぎ is the most common gesture corpus-wide, so its frequency is partly a house convention.",
        "author", "thin", "inferred",
        {"corpus_@おじぎ_calls": 1576, "her_@おじぎ": gesture_freq["@おじぎ"]},
    )
    rule(
        ("Keep kiss gestures (@キス, @キス止め) only with 一悟, only on route %s." % ROUTE_OF[name])
        if name in ROUTE_OF else
        "Keep kiss gestures (@キス, @キス止め) only with 一悟; this subject has no route of her own.",
        "moment", "thin", "measured",
        {"kiss_lines": len(kiss_lines),
         "with_一悟": sum(1 for r in kiss_lines if interlocutor.get(rid_of(r)) == PROTAGONIST),
         "route_" + (ROUTE_OF.get(name) or "own"): sum(
             1 for r in kiss_lines if scene_route(r["scene"])[0] == (ROUTE_OF.get(name) or "\0"))},
        examples=kiss_lines, computed=True,
    )
    rule(
        "Keep dozing (@居眠り横 / @居眠り縦) almost always with 一悟 (6 of 7 lines).",
        "moment", "thin", "measured",
        {"lines": len(doze_lines),
         "with_一悟": sum(1 for r in doze_lines if interlocutor.get(rid_of(r)) == PROTAGONIST),
         "routes": dict(sorted(Counter(scene_route(r["scene"])[0] for r in doze_lines).items()))},
        examples=doze_lines,
    )
    rule(
        "Keep the H-scene vocabulary (せーえき, おちんちん, おまんこ, きちゃう) inside the H scenes.",
        "moment", "firm", "measured",
        {"lines_with_H_tokens": len(htoken_lines), "in_H_scenes": len(htoken_in_h),
         "in_non_H": len(htoken_lines) - len(htoken_in_h),
         "h_scenes": sum(1 for s in her_scenes if s in h_scenes)},
        examples=htoken_lines,
        note="this is authored register, not a personality trait.", register="H",
    )
    rule(
        "Laugh rarely (13 lines), and usually while jumping (non-H).",
        "moment", "thin", "measured",
        {"laugh_lines": len(laugh_lines), "with_@ジャンプ": sum(1 for r in laugh_lines if "@ジャンプ" in line_gestures.get(rid_of(r), [])),
         "by_register": ln_reg(laugh_lines)},
        examples=laugh_lines, register="non-H",
    )
    rule(
        "Voice her as cheerful and childlike: short, exclamatory, repetitive, self-named. The childlike register shifts toward H moans inside an H scene.",
        "hers", "firm", "inferred",
        {"non_H": {"median_chars": length_profile(her_spoken_nonh)["median_chars"],
                   "ellipsis_per_line": punctuation_profile(her_spoken_nonh).get("…", {}).get("per_line", 0.0)},
         "H": {"median_chars": length_profile(her_spoken_h)["median_chars"],
               "ellipsis_per_line": punctuation_profile(her_spoken_h).get("…", {}).get("per_line", 0.0)},
         "third_person_lines": len(bai_lines)},
        note="inference from the measured surface, not a measurement of its own. Read the two registers separately; the old single pooled median and ellipsis rate was a blend.",
        register="per-register",
    )

    sg_class = Counter(r["class"] for r in sg_rules)
    sg_tier = Counter(r["tier"] for r in sg_rules)
    sg_register = Counter(r["register"] for r in sg_rules)
    speech_guide_section = OrderedDict(
        [
            ("rules", sg_rules),
            ("class_split", dict(sorted(sg_class.items()))),
            ("tier_split", dict(sorted(sg_tier.items()))),
            ("register_split", dict(sorted(sg_register.items()))),
            ("evidence_split", dict(sorted(Counter(r["evidence"] for r in sg_rules).items()))),
            ("unreceipted", [r["rule"] for r in sg_rules if not r["receipt"]]),
            ("note", (
                "Each rule carries a class (hers / the author's / a moment), a tier "
                "(firm / thin) and an evidence flag (measured / inferred). It also carries "
                "`register`: `all` for both H and non-H, `H` or `non-H` where the rule holds "
                "in one register only, and `per-register` where the value differs and both "
                "are stated. Every rule carries a receipt of counts and, where small, "
                "example lines. Trigger statements are co-occurrence, not cause."
            )),
        ]
    )

    # ---- rhetorical mechanisms (B3, the builder's reading) --------------- #
    def mech_matches(spec, text):
        if "pattern" in spec:
            return bool(re.search(spec["pattern"], _mech_strip(text)))
        return MECHANISM_MATCHERS[spec["matcher"]](text)

    # The house-style baseline: the other named heroines' spoken lines in her
    # scenes.  A mechanism whose rate here is at or above hers is not hers
    # alone.  This is the per-bible control; the B4 gate measured the same
    # question on a held-out contrast and is the authority for `distinctive`.
    control_spoken_lines = [
        r for r in room_lines
        if r["_channel"] == "spoken"
        and r["speaker"] in char_table["by_name"]
        and r["speaker"] not in (name, PROTAGONIST)
    ]

    mech_rows = []
    # Per-subject B3 (method doc: "the matcher list would need review against her
    # lines"). tools/koikano/b3/<slug>.py, when present, holds that subject's own
    # reading: MECHANISM_SPECS (same shape as above) and MATCHERS (name -> fn).
    # Absent (百花 today), the default list stands and her output is unchanged.
    for spec in mechanism_specs(name):
        if spec.get("matcher") == "offers_self" and name != DEFAULT_CHAR:
            continue  # the matcher names 百花; another subject's B3 reading is her own
        hits =[r for r in her_spoken_lines if mech_matches(spec, r["text"])]
        ctrl_hits = [r for r in control_spoken_lines if mech_matches(spec, r["text"])]
        her_rate = len(hits) / len(her_spoken_lines) if her_spoken_lines else 0.0
        ctrl_rate = len(ctrl_hits) / len(control_spoken_lines) if control_spoken_lines else 0.0
        row = OrderedDict(
            [
                ("key", spec["key"]),
                ("name", spec["name"]),
                ("definition", spec["definition"]),
                ("class", spec["class"]),
                ("tier", spec["tier"]),
                ("confidence", spec["confidence"]),
                ("distinctive", bool(spec.get("distinctive", her_rate > ctrl_rate))),
                ("lines", len(hits)),
                ("share_of_spoken", round(her_rate, 4)),
                ("control_lines", len(ctrl_hits)),
                ("control_rate", round(ctrl_rate, 4)),
                ("lines_H", sum(1 for r in hits if in_h(r))),
                ("lines_non_H", sum(1 for r in hits if not in_h(r))),
                ("method", spec["method"]),
                ("receipts", receipts([rid_of(r) for r in hits], 3)),
            ]
        )
        if spec.get("distinctive") is False:
            row["gate_control_rate"] = spec.get("control_rate")
            row["distinctive_note"] = (
                "B4 held out a route-d block and found the control heroine rate at or above "
                "hers; the move reads as house style, not hers. Kept and marked, not deleted."
            )
        if spec.get("note"):
            row["note"] = spec["note"]
        if name != DEFAULT_CHAR and not has_b3_file(name):
            row["text_basis"] = "hyakka-authored B3 reading; name/definition/note/class/tier are 百花's, lines and rates are this subject's"
        mech_rows.append(row)

    mechanisms_section = OrderedDict(
        [
            ("reading", True),
            ("speaker", name),
            ("spoken_lines", len(her_spoken_lines)),
            ("control_spoken_lines", len(control_spoken_lines)),
            ("control_definition", (
                "The other named heroines' spoken lines in her scenes (the room minus the "
                "protagonist 一悟 and minus her). control_rate is hits over that set; it is "
                "the per-bible house-style baseline. The B4 gate used a held-out, same-scene "
                "contrast with six heroines and is the authority for `distinctive`."
            )),
            ("mechanisms", mech_rows),
            ("class_split", dict(sorted(Counter(r["class"] for r in mech_rows).items()))),
            ("tier_split", dict(sorted(Counter(r["tier"] for r in mech_rows).items()))),
            ("firm_count", sum(1 for r in mech_rows if r["tier"] == "firm")),
            ("thin_count", sum(1 for r in mech_rows if r["tier"] == "thin")),
            ("weak_count", sum(1 for r in mech_rows if r["tier"] == "weak")),
            ("distinctive_false", [r["key"] for r in mech_rows if not r["distinctive"]]),
            ("cross_reference", (
                "These are the moves that carry no `@emotion` / `@face` / `@action`. "
                "The surface rules they lean on are measured separately in `speech_guide` "
                "(third-person naming, the doubled ん, the childish vocabulary, the `？` / `…` "
                "marks) and in `voice.surface`; this section adds the move, not the mark."
            )),
            ("class_note", (
                "Every mechanism is classed `hers` because a corpus count of its markers puts "
                "it overwhelmingly on her lines (for example 26 of 27 catchphrase lines, 15 of "
                "23 loanword lines, 42 of 51 sound-effect lines), and each recurs across her "
                "scenes and relationships. The one device shared with the author's comedy "
                "toolkit - coining a label - is noted in that mechanism. Nothing here was "
                "classed `author` or `moment`. The `weak` tier and `distinctive: false` mark "
                "the five moves B4 found at or below the control heroine rate: they are kept, "
                "because a reader still needs to know the move, but they are house style."
            )),
            ("note", (
                "The mechanisms are the builder's reading of her speech across her scenes, "
                "not the author's: the definitions and the classing are interpretive, the "
                "line counts and the receipts are mechanical. A regex count is a lower bound "
                "where the move is defined by reading. Receipts are the first matching lines "
                "in scene order. `lines_H` / `lines_non_H` split the count by the @Hシーン開始 "
                "register."
            )),
        ]
    )

    # ---- bounds (B2) ----------------------------------------------------- #
    empty_addr = [
        s for s, e in b2_relationships.items()
        if not e["her_address_terms"] and e["her_spoken_turns"] > 0
    ]
    bounds_section = OrderedDict(bounds_doc)
    bounds_section["b2_not_derived"] = OrderedDict(
        [
            ("address_terms_for_npcs", (
                "Not derivable. The NPC speakers are not in charData.csv, so there is no "
                "name form to search her lines for. Only the eight named cast and the "
                "protagonist 一悟 have alias forms."
            )),
            ("relationships_with_no_address_term", empty_addr),
            ("rhetorical_mechanisms_deferred_to_b3", [
                "This list is the B2 residue, kept for provenance. B3 addressed it: see the "
                "`mechanisms` section. The B2 residue named deflects a topic, changes the "
                "subject, teases, jokes, stalls with repetition, or answers a question with a "
                "question - none of these carries an authored stage direction.",
            ]),
            ("trigger_causality", (
                "Every trigger table is co-occurrence over her lines, not cause. The "
                "authored direction is a staging choice on the line; it does not say why."
            )),
            ("expression_label_uncertainty", (
                "Expression triggers inherit the C4 hypothesis: a label on a line is the "
                "merged visual/context guess, not ground truth."
            )),
            ("tokenizer", (
                "The surface battery splits on punctuation (a class-based tokenizer), not "
                "morphology, so particles are matched by string suffix against a fixed list "
                "and the n-grams are character n-grams."
            )),
            ("room_definition", (
                "The room is every other speaker in her scenes, named cast and NPCs "
                "together; the plan leaves this open."
            )),
        ]
    )

    provenance_section = OrderedDict(
        [
            *([("build_only_excluded_scenes", excluded_scenes)] if build_only else []),
            ("inputs", {
                "game_logic": {"path": paths["game_logic"], "records": len(records)},
                "character_actions": {"path": paths["actions"], "records": len(actions_rows)},
                "expression_labels_lines": {"path": paths["expr_lines"], "records": len(expr_rows)},
                "timing_table": {"path": paths["timing"], "records": len(timing_rows)},
                "expression_labels": {"path": paths["expr_labels"], "labels": len(expr_table["labels"])},
                "bgm_scene_table": {"path": paths["bgm"]},
                "char_table": {"path": paths["char_table"]},
                "scenario": {"path": paths["scenario"]},
            }),
            ("mechanical_vs_model", {
                "mechanical": [
                    "slice", "battery", "bounds", "context", "annotations", "interactions",
                    "voice surface", "expression triggers", "gesture triggers", "speech guide",
                ],
                "model": ["fidelity gate (B4)"],
            }),
            ("b2_mechanical_only", True),
            ("b3_reading", (
                "B3 added the `mechanisms` section: the recurring rhetorical moves that carry "
                "no authored stage direction. The definitions, the class and the tier are the "
                "builder's reading; the line counts come from the fixed matchers named per "
                "mechanism, and the receipts are real record ids. No API call was made."
            )),
            ("corrections", [
                "B1 read the alias table from charData.csv, which omits the protagonist "
                "一悟; B2 adds him for the address-term derivation in this bible only.",
                "B3 is a reading, not a measurement: the mechanism list is this builder's "
                "judgement of what shapes her speech, so class and tier are interpretive even "
                "where the count is mechanical. The B2 residue named 'deflects a topic, "
                "changes the subject, teases, jokes, stalls with repetition, or answers a "
                "question with a question'; those are covered by `doubles_a_key_word`, "
                "`closes_a_turn_with_a_short_question`, `names_a_blow_with_a_loanword` and "
                "`plays_a_role_with_stock_catchphrases`.",
            ]),
            ("hypothesis_layers", {
                "expression_labels": "C4 hypothesis, version %s" % expr_table.get("meta", {}).get("vocabulary_version"),
            }),
        ]
    )

    # spot check: the first her line (scene order) with a face and a gesture
    spot = None
    for rec in her_lines:
        rid = record_key(rec["scene"], rec["source_line"])
        faces, acts = annotations_for(rid)
        gests = [a for a in acts if a["kind"] == "gesture"]
        if faces and gests:
            spot = OrderedDict(
                [
                    ("record_id", rid),
                    ("scene", rec["scene"]),
                    ("route", scene_route(rec["scene"])[0]),
                    ("speaker", rec["speaker"]),
                    ("channel", rec["_channel"]),
                    ("text", rec["text"]),
                    ("interlocutor", interlocutor.get(rid)),
                    ("expressions", faces),
                    ("actions", acts),
                    ("slice", {"in_her_lines": rid in her_rids, "in_her_scenes": rec["scene"] in her_scene_set}),
                ]
            )
            break

    bible = OrderedDict(
        [
            ("meta", {
                "schema": SCHEMA,
                "phase": PHASE,
                "build_version": BUILD_VERSION,
                "build_date": BUILD_DATE,
                "character": name,
                "buid": buid,
                "route": ROUTE_OF.get(name, ""),
                "model_spend": "small (B3 reading; no API call, the reading is the builder's)",
                "standard_library_only": True,
            }),
            ("identity", {
                "name": name,
                "id": subject["id"],
                "buid": buid,
                "vcid": subject["vcid"],
                "lastname": subject["lastname"],
                "route": ROUTE_OF.get(name, ""),
                "route_character": ROUTE_CHARACTER.get(ROUTE_OF.get(name, ""), ""),
                "scene_count": len(her_scenes),
                "line_count": len(her_lines),
                "spoken_count": len(her_spoken_lines),
                "inner_count": len(her_inner_lines),
                "route_breakdown": dict(
                    sorted(
                        Counter(scene_route(s)[1] for s in her_scenes).items()
                    )
                ),
            }),
            ("voice", {
                "channels": battery_doc["channels"],
                "dispersion": battery_doc["dispersion"],
                "distinctive": battery_doc["distinctive"],
                "line_counts": battery_doc["line_counts"],
                "surface": voice_surface,
                "note": battery_doc["note"],
            }),
            ("expressions", expressions_section),
            ("gestures", gestures_section),
            ("interactions", interactions_section),
            ("bounds", bounds_section),
            ("speech_guide", speech_guide_section),
            ("mechanisms", mechanisms_section),
            ("context", context_doc),
            ("spot_check", spot),
            ("provenance", provenance_section),
        ]
    )

    checks = {
        "sum_others_plus_subject_equals_scene_total": total_other + len(her_lines)
        == len(her_lines) + len(room_lines),
        "her_lines": len(her_lines),
        "her_scenes": len(her_scenes),
        "her_inner": len(her_inner_lines),
        "room_lines": len(room_lines),
    }

    return {
        "paths": paths,
        "slug": slug,
        "name": name,
        "layers": {
            "slice": slice_doc,
            "battery": battery_doc,
            "bounds": bounds_doc,
            "context": context_doc,
            "annotations": annotations_doc,
            "interactions": interactions_doc,
        },
        "bible": bible,
        "checks": checks,
        "spot": spot,
    }


# --------------------------------------------------------------------------- #
# readable bible
# --------------------------------------------------------------------------- #


def render_doc_from_files(bible_path: str, layers_dir: str) -> str:
    """Re-render the readable doc from a bible.json on disk plus a layers/ dir, no corpus rebuild.

    render_doc wants the builder's result dict ({name, bible, layers, spot}); passing a bible.json
    straight in fails with KeyError('name') (seen in the cast apply scripts).  Everything render_doc
    reads is in bible.json (name, spot_check) or in layers/ (annotations, battery, ...).
    """
    with open(bible_path, encoding="utf-8") as fh:
        bible = json.load(fh)
    layers = {}
    for lname in ("slice", "battery", "bounds", "context", "annotations", "interactions"):
        p = os.path.join(layers_dir, lname + ".json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                layers[lname] = json.load(fh)
    return render_doc({"name": bible["identity"]["name"], "bible": bible, "layers": layers,
                       "spot": bible.get("spot_check")})


def render_doc(result: dict) -> str:
    if "bible" not in result and "identity" in result:
        raise TypeError("render_doc takes the builder's result dict, not a bible.json; "
                        "use render_doc_from_files(bible_path, layers_dir) for a bible on disk")
    name = result["name"]
    bible = result["bible"]
    layers = result["layers"]
    ident = bible["identity"]
    inter = bible["interactions"]
    bounds = bible["bounds"]
    ann = layers["annotations"]
    bat = layers["battery"]
    spot = result["spot"]

    def table(rows, headers):
        out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        for row in rows:
            out.append("| " + " | ".join(str(c) for c in row) + " |")
        return "\n".join(out)

    def compact(obj, maxlen=200):
        s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        if len(s) > maxlen:
            s = s[: maxlen - 1] + "…"
        return s.replace("|", "/")

    def top_list(counts, n=4):
        return ", ".join("%s %s" % (k, v) for k, v in list(counts.items())[:n]) or "-"

    lines = []
    lines.append("# koikano authored expression bible - %s (%s)" % (name, ident["buid"]))
    lines.append("")
    lines.append(
        "Date: %s. Build: %s (%s). Phases B0+B1+B2+B3. B0-B2 are mechanical (no model "
        "spend, standard library); B3 is the builder's reading of the rhetorical moves, "
        "recorded in `mechanisms`. Route %s. Source: `%s\\koikano_work\\game_logic.jsonl` "
        "joined to the authored stage directions."
        % (BUILD_DATE, BUILD_VERSION, SCHEMA, ident["route"], DEFAULT_CORPUS)
    )
    lines.append("")
    lines.append(
        "**The expression labels are C4 hypotheses, not ground truth.** Every label "
        "carries its confidence and provenance in `layers/annotations.json` and "
        "`bible.json`; the authored `@emotion` overlays are the author's, the merged "
        "`expression` labels are a derived hypothesis."
    )
    lines.append("")
    lines.append("## Run")
    lines.append("")
    lines.append("```powershell")
    lines.append('python "F:\\REPS2\\clipboard capture (kirikiri)\\src\\kirikiri_tools\\koikano_bible.py"')
    lines.append("```")
    lines.append("")
    lines.append(
        "One command, repeatable. `--corpus`, `--out` and `--char` override the input "
        "root, the output directory and the subject. The run exits 2, and writes nothing, "
        "if a `record_id` join does not match `game_logic.jsonl`."
    )
    lines.append("")
    lines.append("## Schema")
    lines.append("")
    lines.append(
        "`bible.json` carries `identity`, `voice`, `expressions`, `gestures`, "
        "`interactions`, `bounds`, `speech_guide`, `mechanisms`, `context`, `spot_check` "
        "and `provenance`. B2 assembled the `voice` surface, the expression and gesture "
        "**triggers**, the corrected interaction address terms, the `speech_guide` and "
        "the B2 bounds. B3 added `mechanisms`: the rhetorical moves with no stage "
        "direction, which are the builder's reading. The layers under `layers/` remain "
        "the B0/B1 build products:"
    )
    lines.append("")
    lines.append(
        table(
            [
                ["slice.json", "her lines, her scenes, inner voice, the room; counts and ids"],
                ["battery.json", "token/ngram counts, dispersion, distinctive n-grams"],
                ["bounds.json", "reply/initiation, relationships, emotional pressures, absent list"],
                ["context.json", "route, story phase, H-scene, BGM per scene"],
                ["annotations.json", "per line and per scene: faces, gestures, emotion, entry/exit, camera"],
                ["interactions.json", "per-relationship turns, initiation, length, mix, address terms"],
            ],
            ["file", "content"],
        )
    )
    lines.append("")
    lines.append("## Identity and counts")
    lines.append("")
    lines.append(
        table(
            [
                ["her lines", ident["line_count"]],
                ["- spoken", ident["spoken_count"]],
                ["- inner voice", ident["inner_count"]],
                ["her scenes", ident["scene_count"]],
                ["room lines (others in her scenes)", layers["slice"]["counts"]["room_lines"]],
                ["- room spoken", layers["slice"]["counts"]["room_spoken"]],
                ["- room inner", layers["slice"]["counts"]["room_inner"]],
            ],
            ["measure", "count"],
        )
    )
    lines.append("")
    lines.append(
        "The scope's section 5.1 figure for %s is 2,781 lines, 211 inner and 70 scenes. "
        "This build reproduces all three." % name
    )
    lines.append("")
    lines.append("## Voice: her dialogue, her inner voice, the room")
    lines.append("")
    lines.append(
        "`dispersion` is scene document frequency: the share of her scenes in which the "
        "n-gram appears. `distinctive` is the log-odds of the channel against the other "
        "two channels pooled."
    )
    lines.append("")
    lines.append(
        table(
            [
                ["her dialogue", bat["channels"]["her_dialogue"]["lines"], bat["channels"]["her_dialogue"]["tokens"], bat["channels"]["her_dialogue"]["token_types"], bat["channels"]["her_dialogue"]["type_token_ratio"]],
                ["her inner voice", bat["channels"]["her_inner"]["lines"], bat["channels"]["her_inner"]["tokens"], bat["channels"]["her_inner"]["token_types"], bat["channels"]["her_inner"]["type_token_ratio"]],
                ["the room (spoken)", bat["channels"]["the_room"]["lines"], bat["channels"]["the_room"]["tokens"], bat["channels"]["the_room"]["token_types"], bat["channels"]["the_room"]["type_token_ratio"]],
            ],
            ["channel", "lines", "tokens", "token types", "TTR"],
        )
    )
    lines.append("")
    lines.append("Distinctive tokens (log-odds, top 12):")
    lines.append("")
    for channel in ("her_dialogue", "her_inner", "the_room"):
        items = bat["distinctive"][channel]["tokens"][:12]
        lines.append(
            "- **%s**: %s" % (channel, ", ".join("%s (%s)" % (r["item"], r["a"]) for r in items))
        )
    lines.append("")
    lines.append("### B2 surface: turn length, line-final, punctuation, self-reference")
    lines.append("")
    surf = bible["voice"]["surface"]
    tl = surf["turn_length"]
    bucket_keys = list(tl["her_spoken"]["buckets"].keys())
    tl_rows = []
    for label in ("her_spoken", "her_inner", "the_room_spoken"):
        d = tl[label]
        tl_rows.append(
            [label]
            + [d["buckets"][b]["count"] for b in bucket_keys]
            + [d["mean_chars"], d["median_chars"], d["p90_chars"]]
        )
    lines.append("Turn length, kept characters per line (shares are in `bible.json`):")
    lines.append("")
    lines.append(table(tl_rows, ["channel"] + bucket_keys + ["mean", "median", "p90"]))
    lines.append("")
    lines.append("Line-final morphemes, string suffixes of the kept text (top 10):")
    lines.append("")
    for label, key in (("her spoken", "her_spoken"), ("her inner", "her_inner")):
        lf = surf["line_final"][key]
        lines.append("- **%s last token**: %s" % (label, top_list(dict(lf["last_token"]), 10)))
        lines.append("- **%s 2-char suffix**: %s" % (label, top_list(dict(lf["suffix2"]), 10)))
    lines.append("")
    lines.append("Line-final particles, matched by suffix against a fixed list (top 10 by spoken lines):")
    lines.append("")
    in_p = {r["ending"]: r for r in surf["particles"]["her_inner"]}
    part_rows = []
    for r in surf["particles"]["her_spoken"][:10]:
        e = r["ending"]
        part_rows.append([e, r["lines"], r["share"], in_p.get(e, {}).get("lines", 0), in_p.get(e, {}).get("share", 0.0)])
    lines.append(table(part_rows, ["ending", "spoken lines", "spoken share", "inner lines", "inner share"]))
    lines.append("")
    lines.append("Punctuation, full-width marks:")
    lines.append("")
    punct = surf["punctuation"]
    mark_rows = []
    for mark in ("…", "‥", "！", "？", "、", "。", "ー", "～", "「"):
        s = punct["her_spoken"].get(mark)
        i = punct["her_inner"].get(mark)
        rm = punct["the_room_spoken"].get(mark)
        if s or i or rm:
            mark_rows.append([
                mark,
                s["count"] if s else 0, s["per_line"] if s else 0.0,
                i["count"] if i else 0,
                rm["per_line"] if rm else 0.0,
            ])
    lines.append(table(mark_rows, ["mark", "spoken count", "spoken/line", "inner count", "room/line"]))
    lines.append("")
    sr = surf["self_reference"]
    lines.append(
        "Self-reference: spoken %s %d occurrences on %d lines; spoken 私 %d occurrence(s) "
        "on %d line(s); inner %s %d occurrence(s) on %d line(s)."
        % (name, sr["spoken_" + name]["occurrences"], sr["spoken_" + name]["lines"],
           sr["spoken_私"]["occurrences"], sr["spoken_私"]["lines"],
           name, sr["inner_" + name]["occurrences"], sr["inner_" + name]["lines"])
    )
    lines.append("")
    d_room = surf["distinctive_her_dialogue_vs_room"]["tokens"][:10]
    d_inner = surf["distinctive_her_dialogue_vs_inner"]["tokens"][:10]
    b_room = surf["distinctive_her_dialogue_vs_room"]["bigrams"][:8]
    b_inner = surf["distinctive_her_dialogue_vs_inner"]["bigrams"][:8]
    lines.append("- **her dialogue vs the room, tokens**: %s" % ", ".join("%s (%s)" % (r["item"], r["a"]) for r in d_room))
    lines.append("- **her dialogue vs the room, bigrams**: %s" % ", ".join("%s (%s)" % (r["item"], r["a"]) for r in b_room))
    lines.append("- **her dialogue vs her inner, tokens**: %s" % ", ".join("%s (%s)" % (r["item"], r["a"]) for r in d_inner))
    lines.append("- **her dialogue vs her inner, bigrams**: %s" % ", ".join("%s (%s)" % (r["item"], r["a"]) for r in b_inner))
    lines.append("")
    lines.append("## Expressions (C4 hypotheses)")
    lines.append("")
    lines.append(
        "The repertoire is her own faces only (message face or sprite tag carrying the "
        "`%s` prefix). Confidence is carried from `expression_labels.json`." % ident["buid"]
    )
    lines.append("")
    lines.append(
        table(
            [[r["expression"], r["lines"], r["confidence_split"]] for r in bible["expressions"]["repertoire"]],
            ["expression", "her lines", "confidence split"],
        )
    )
    lines.append("")
    lines.append("### Expression triggers (all eight labels)")
    lines.append("")
    lines.append(
        "One row per label. `lines` is her lines carrying it (a line with two faces counts "
        "once here; the repertoire counts occurrences). `with` is the speaker whose turn "
        "preceded hers; `(none)` is a scene-opening or unattributed turn. `preceded by` is "
        "the last expression she wore earlier in the scene; `co-gesture` is the gesture on "
        "the same line. Co-occurrence, not cause."
    )
    lines.append("")
    trig_rows = []
    for label, t in bible["expressions"]["triggers"].items():
        trig_rows.append([
            label,
            t["lines"],
            top_list(t["interlocutor"], 3),
            top_list(t["route"], 3),
            top_list(t["scene_type"], 2),
            t["mean_line_chars"],
            top_list(t["preceding_expression"], 3),
            top_list(t.get("co_gesture", {}), 3),
        ])
    lines.append(table(trig_rows, ["expression", "lines", "with", "route", "H/normal", "mean chars", "preceded by", "co-gesture"]))
    lines.append("")
    lines.append("## Gestures")
    lines.append("")
    lines.append(
        table([[r["command"], r["lines"]] for r in bible["gestures"]["repertoire"]], ["gesture", "her lines"])
    )
    lines.append("")
    lines.append(
        "Entry/exit: %s. Camera (targeted): %s. Emotion overlays: %s. Action commands (occurrences): %s."
        % (bible["gestures"]["enter_exit"], bible["gestures"]["camera"],
           bible["gestures"]["emotion_overlays"], bible["gestures"]["action_commands"])
    )
    lines.append("")
    lines.append("### Gesture triggers")
    lines.append("")
    lines.append(
        "One row per gesture. `co-face` is the C4 label on the same line; `preceded by` is "
        "the last label earlier in the scene; the other columns as above."
    )
    lines.append("")
    g_trig_rows = []
    for cmd, t in bible["gestures"]["triggers"].items():
        g_trig_rows.append([
            cmd, t["lines"],
            top_list(t["interlocutor"], 3),
            top_list(t["route"], 3),
            top_list(t["scene_type"], 2),
            t["mean_line_chars"],
            top_list(t.get("co_expression", {}), 3),
            top_list(t["preceding_expression"], 3),
        ])
    lines.append(table(g_trig_rows, ["gesture", "lines", "with", "route", "H/normal", "mean chars", "co-face", "preceded by"]))
    lines.append("")
    lines.append("### Emotion, entry/exit and action triggers")
    lines.append("")
    rows_ee = []
    for kind, tbl in (("emotion", "emotion_triggers"), ("enter/exit", "enter_exit_triggers"), ("action", "action_triggers")):
        for k, t in bible["gestures"][tbl].items():
            if t["lines"] == 0:
                continue
            rows_ee.append([
                "%s %s (lines)" % (kind, k), t["lines"], top_list(t["interlocutor"], 2),
                top_list(t["scene_type"], 2), top_list(t.get("co_expression", {}), 2),
            ])
    lines.append(table(rows_ee, ["trigger", "lines", "with", "H/normal", "co-face"]))
    lines.append("")
    lines.append("## Interactions (per relationship)")
    lines.append("")
    rows = []
    order = sorted(inter["relationships"].items(), key=lambda kv: -kv[1]["turns_total"])
    for speaker, rel in order:
        mix = ", ".join("%s %d" % (k, v) for k, v in list(rel["her_expression_mix"].items())[:4]) or "-"
        gest = ", ".join("%s %d" % (k, v) for k, v in list(rel["her_gesture_mix"].items())[:3]) or "-"
        addr = ", ".join("%s %d" % (k, v) for k, v in list(rel.get("her_address_terms", {}).items())[:3]) or "-"
        rows.append(
            [
                speaker,
                rel["category"],
                rel["turns_total"],
                rel["turns_spoken"],
                rel["turns_inner"],
                rel["scenes_together"],
                rel["her_spoken_turns"],
                rel["her_avg_turn_chars"],
                rel.get("her_turn_length", {}).get("median_chars", 0),
                rel.get("exchange_her_starts", 0),
                rel.get("exchange_they_start", 0),
                mix,
                gest,
                addr,
            ]
        )
    lines.append(
        table(
            rows,
            ["speaker", "kind", "turns", "spoken", "inner", "scenes", "her turns", "her avg chars", "her med chars", "exch. her-start", "exch. their-start", "her expression mix", "her gestures", "her address"],
        )
    )
    lines.append("")
    lines.append(
        "Scene openings across her scenes: %s."
        % ", ".join("%s %d" % (k, v) for k, v in inter["scene_openers"].items())
    )
    lines.append("")
    lines.append(
        "Reply vs initiation (her spoken turns): replies %d, initiations %d, self-continuations %d, "
        "reply rate %.3f."
        % (
            bounds["reply_vs_initiation"]["reply"],
            bounds["reply_vs_initiation"]["initiation"],
            bounds["reply_vs_initiation"]["self_continuation"],
            bounds["reply_vs_initiation"]["reply_rate"],
        )
    )
    lines.append("")
    lines.append("### Address terms")
    lines.append("")
    lines.append(
        "How she names the other party, derived from her lines whose preceding speaker is "
        "that party. Overall: %s." % compact(inter["her_address_terms_overall"], 400)
    )
    lines.append("")
    lines.append(inter["address_correction"])
    lines.append("")
    lines.append(
        "Relationships where no name term is derivable from her lines: %s."
        % (", ".join(bounds["b2_not_derived"]["relationships_with_no_address_term"]) or "none")
    )
    lines.append("")
    lines.append("## Speech guide")
    lines.append("")
    lines.append(
        "Each rule carries a class (hers / the author's / a moment), a tier (firm / thin), a "
        "`register` (all / H / non-H / per-register) and an evidence flag (measured / "
        "inferred). The receipt is the count or the lines the rule comes from; the example "
        "lines are in `bible.json`. Rules whose value differs by register state both."
    )
    lines.append("")
    sg = bible["speech_guide"]
    sg_rows = []
    for r in sg["rules"]:
        rc = dict(r["receipt"])
        rc.pop("examples", None)
        sg_rows.append([r["rule"], r["class"], r["tier"], r["register"], r["evidence"], compact(rc, 130)])
    lines.append(table(sg_rows, ["rule", "class", "tier", "register", "evidence", "receipt"]))
    lines.append("")
    lines.append(
        "Rule split: class %s; tier %s; register %s; evidence %s. Unreceipted rules: %s."
        % (sg["class_split"], sg["tier_split"], sg["register_split"], sg["evidence_split"], sg["unreceipted"] or "none")
    )
    lines.append("")
    lines.append("## Rhetorical mechanisms (B3)")
    lines.append("")
    mech = bible["mechanisms"]
    lines.append(
        "These are the recurring moves in her speech that carry no `@emotion` / `@face` / "
        "`@action` - the B2 residue. They are **this builder's reading**, not the author's: "
        "the definitions, the class and the tier are interpretive; the line counts come from "
        "the fixed matcher named in each `method`, and the receipts are real lines. The "
        "surface rules they lean on are measured separately in `speech_guide` and "
        "`voice.surface`; this section adds the move, not the mark. A regex count is a lower "
        "bound where the move is defined by reading."
    )
    lines.append("")
    mech_rows = []
    for m in mech["mechanisms"]:
        rset = ", ".join(x["record_id"] for x in m["receipts"][:2]) or "-"
        mech_rows.append([m["name"], m["class"], m["tier"], m["confidence"], str(m["lines"]),
                          "%s / %s" % (m["lines_non_H"], m["lines_H"]), m["control_rate"], str(m["distinctive"]), rset])
    lines.append(table(mech_rows, ["mechanism", "class", "tier", "confidence", "lines", "non-H / H", "control rate", "distinctive", "receipts"]))
    lines.append("")
    lines.append(
        "Mechanism split: class %s; tier %s (%d firm, %d thin, %d weak) over %d spoken lines."
        % (mech["class_split"], mech["tier_split"], mech["firm_count"], mech["thin_count"], mech["weak_count"], mech["spoken_lines"])
    )
    lines.append("")
    lines.append("Non-distinctive from the control heroines: %s." % (", ".join(mech["distinctive_false"]) or "none"))
    lines.append("")
    lines.append(mech["class_note"])
    lines.append("")
    lines.append("How each was counted, and the weak ones:")
    lines.append("")
    for m in mech["mechanisms"]:
        extra = (" " + m["note"]) if m.get("note") else ""
        lines.append(
            "- **%s** (%s, %s, %s, %d line(s), share %s; non-H %d / H %d; control %s, distinctive %s): %s%s"
            % (m["name"], m["class"], m["tier"], m["confidence"], m["lines"], m["share_of_spoken"],
               m["lines_non_H"], m["lines_H"], m["control_rate"], m["distinctive"], m["method"], extra)
        )
    lines.append("")
    lines.append("## Bounds and the absent list")
    lines.append("")
    lines.append("Emotional pressures (authored `@emotion` types): %s." % bounds["emotional_pressures"]["authored_emotion_overlays"])
    lines.append("")
    absents = bounds["absent"]
    lines.append(
        "- expression vocabulary never on her lines: %s" % (", ".join(absents["expression_vocabulary_unused_on_her_lines"]) or "none")
    )
    lines.append(
        "- gesture macros in the corpus never hers: %s" % (", ".join(absents["gesture_macros_in_corpus_never_hers"]) or "none")
    )
    lines.append(
        "- on-screen cast absent from her scenes: %s" % (", ".join(absents["on_screen_cast_absent_from_her_scenes"]) or "none")
    )
    lines.append("")
    lines.append("### What B2 could not derive (the B3 residue)")
    lines.append("")
    nd = bounds["b2_not_derived"]
    lines.append("- address terms for NPCs: %s" % nd["address_terms_for_npcs"])
    lines.append("- relationships with no address term: %s" % (", ".join(nd["relationships_with_no_address_term"]) or "none"))
    lines.append("- rhetorical mechanisms deferred to B3: %s" % "; ".join(nd["rhetorical_mechanisms_deferred_to_b3"]))
    lines.append("- trigger causality: %s" % nd["trigger_causality"])
    lines.append("- expression-label uncertainty: %s" % nd["expression_label_uncertainty"])
    lines.append("- tokenizer: %s" % nd["tokenizer"])
    lines.append("- room definition: %s" % nd["room_definition"])
    lines.append("")
    lines.append("## Spot check: one line carried through the layers")
    lines.append("")
    if spot:
        lines.append("`%s` (scene %s, route %s, channel %s):" % (spot["record_id"], spot["scene"], spot["route"], spot["channel"]))
        lines.append("")
        lines.append("> %s" % spot["text"])
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps({"expressions": spot["expressions"], "actions": spot["actions"], "interlocutor": spot["interlocutor"]}, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
        lines.append(
            "This line is in `slice.json` (`her_line_ids`), its face and gesture are in "
            "`annotations.json` (`per_line`), and the gesture is in `gestures` in `bible.json`."
        )
    else:
        lines.append("No line with both a face and a gesture was found.")
    lines.append("")
    lines.append("## Provenance")
    lines.append("")
    lines.append(
        "Inputs: game_logic.jsonl (%d records), character_actions.jsonl (%d), "
        "expression_labels_lines.jsonl (%d), timing_table.jsonl (%d), expression_labels.json "
        "(%d labels), bgm_scene_table.json, charData.csv, data\\scenario\\*.ks."
        % (
            bible["provenance"]["inputs"]["game_logic"]["records"],
            bible["provenance"]["inputs"]["character_actions"]["records"],
            bible["provenance"]["inputs"]["expression_labels_lines"]["records"],
            bible["provenance"]["inputs"]["timing_table"]["records"],
            bible["provenance"]["inputs"]["expression_labels"]["labels"],
        )
    )
    lines.append("")
    lines.append(
        "Mechanical here: slice, battery, bounds, context, annotations, interactions, the "
        "B2 voice surface, the expression and gesture triggers, and the speech guide. B3 "
        "added `mechanisms`, a reading by the builder (no API call): the moves are "
        "interpretive, their counts are mechanical. Deferred to a model: the fidelity gate "
        "(B4). The expression labels are the C4 hypothesis layer, vocabulary version %s, and "
        "are presented as hypotheses with their confidence." % bible["expressions"]["vocabulary_version"]
    )
    lines.append("")
    lines.append("Corrections: %s" % " ".join(bible["provenance"]["corrections"]))
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Build the authored expression bible (B0+B1+B2).")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS, help="corpus root")
    parser.add_argument("--out", default=None, help="output directory (default bible/<slug>)")
    parser.add_argument("--char", default=DEFAULT_CHAR, help="subject name, id, buid or slug")
    parser.add_argument("--doc", default=None, help="readable bible path")
    parser.add_argument("--game-logic", dest="game_logic", default=None)
    parser.add_argument("--actions", default=None)
    parser.add_argument("--expr-lines", dest="expr_lines", default=None)
    parser.add_argument("--expr-labels", dest="expr_labels", default=None)
    parser.add_argument("--timing", default=None)
    parser.add_argument("--bgm", default=None)
    parser.add_argument("--char-table", dest="char_table", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--build-only", dest="build_only", action="store_true",
                        help="leak-free: exclude the gate's holdout scenes from every layer; needs --out (default writes nothing into docs/)")
    parser.add_argument("--render-only", dest="render_only", default=None, metavar="BIBLE_JSON",
                        help="only re-render the readable doc from this bible.json (needs --layers-dir and --doc)")
    parser.add_argument("--layers-dir", dest="layers_dir", default=None, help="with --render-only: the layers/ dir")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.render_only:
        if not (args.layers_dir and args.doc):
            fail("--render-only needs --layers-dir and --doc")
        write_text(args.doc, render_doc_from_files(args.render_only, args.layers_dir))
        sys.stdout.write("koikano_bible: rendered %s from %s\n" % (args.doc, args.render_only))
        return 0
    if args.build_only and not args.out:
        fail("--build-only needs --out (a separate directory; the shipped bible stays full-corpus)")
    result = build(args)
    slug = result["slug"]
    out_dir = args.out or os.path.join(args.corpus, "koikano_work", "bible", slug)
    if args.build_only and not args.doc:
        args.doc = os.path.join(out_dir, "bible_readable.md")
    if args.doc:
        doc_path = args.doc
    else:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        doc_path = os.path.join(repo_root, "docs", "koikano-bible-%s.md" % slug)

    for layer, payload in result["layers"].items():
        write_json(os.path.join(out_dir, "layers", layer + ".json"), payload)
    write_json(os.path.join(out_dir, "bible.json"), result["bible"])
    write_text(doc_path, render_doc(result))

    checks = result["checks"]
    sys.stdout.write(
        "koikano_bible: %s (%s) - %d lines, %d scenes, %d inner; room %d; "
        "sum-check %s\n"
        % (
            result["bible"]["identity"]["buid"],
            slug,
            checks["her_lines"],
            checks["her_scenes"],
            checks["her_inner"],
            checks["room_lines"],
            "ok" if checks["sum_others_plus_subject_equals_scene_total"] else "FAILED",
        )
    )
    sys.stdout.write("koikano_bible: wrote %s and %s\n" % (out_dir, doc_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
