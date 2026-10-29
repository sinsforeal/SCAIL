"""Small text tests shared by the writers.

`near_duplicate` exists because a model asked for two or three short messages
sometimes writes the same one twice with a word moved, and nothing caught it.
Both halves of it reached the record: two near-identical bubbles went to him

    "so you're saying my english is fine and i should stop worrying about it.
     sure. i'll just write that on the blank page tonight"
    "so you're saying i'm fine and i should stop worrying. sure. i'll write
     that on the blank page tonight"

and the same fault stored 「なしてぇ? まだ決めてないって言ったやん。試すって決めたと?」
twice in one exchange. A person sending a burst does repeat themselves, but
they do not paraphrase themselves.
"""
import difflib
import re

import logger


def near_duplicate(a, b, ratio=0.86):
    """Is `b` the same message as `a` with the words moved? Compared without
    whitespace, so a line break is not what makes two texts different."""
    x = "".join(str(a or "").split())
    y = "".join(str(b or "").split())
    if not x or not y:
        return False
    if x == y:
        return True
    # a short line repeated is usually deliberate ("no no", "yeah"); the fault
    # is a paraphrase, which needs length to be one
    if min(len(x), len(y)) < 12:
        return False
    return difflib.SequenceMatcher(None, x, y).ratio() >= ratio


def drop_repeats(items, text_of=lambda x: x, ratio=0.86, why=""):
    """`items` with any run of near-identical consecutive entries collapsed to
    the first. Logged when it fires, because how often it fires says whether
    the prompt is the problem."""
    out = []
    for it in items:
        if out and near_duplicate(text_of(out[-1]), text_of(it), ratio):
            logger.log(f"[dedup] dropped a near-duplicate{(' ' + why) if why else ''}: "
                       f"{str(text_of(it))[:70]!r}")
            continue
        out.append(it)
    return out

# ------------------------------------------- a sentence said twice in a room

# `near_duplicate` compares two WHOLE messages, and a room loops under it in
# two ways it cannot see. One is a sentence repeated inside a longer message:
# the girl who wrote 「……ひなちゃんが「どうしたい？」って聞いてくれたの、なんか嬉しかった」
# at 07:17 and again at 07:21 wrapped it in different second bubbles both
# times, so the messages were 40% alike and the sentence inside them was
# identical. The other is an echo of somebody ELSE: at 21:44 one girl wrote
# 「ひな、クリップ二つ並べるとめっちゃいいね！！セミの銀、かっこいい〜」 and two minutes
# later another wrote it back almost word for word. Both filters below were
# checked against the speaker's own last turns only, so both passed.
#
# A line inside brackets is a marker the record puts there rather than
# something anybody typed (a sticker, a photo), and a short deliberate echo
# ("no no", "yeah") is how people talk. Neither is counted.
_SENTENCE = re.compile(r"[。．！？!?\n]+")


def sentences(text, min_chars=0):
    """The sentences of one message, markers dropped.

    `min_chars` is measured without whitespace, so a line break inside a
    sentence does not change its length."""
    out = []
    for part in _SENTENCE.split(str(text or "")):
        s = part.strip()
        if not s or (s.startswith("[") and s.endswith("]")):
            continue
        if min_chars and len("".join(s.split())) < min_chars:
            continue
        out.append(s)
    return out


def echoed_by(text, prior, min_chars=12, ratio=0.86):
    """Who this message is repeating, when more than half of it is a repeat.

    `prior` is the room's recent turns as (who, text) pairs, from ANY speaker
    including this one. A message whose long sentences are more than half
    already-said is an echo; the answer is who said the first of them, so the
    caller's log can name them. ("", "") when it is not one."""
    mine = sentences(text, min_chars=min_chars)
    if not mine:
        return "", ""
    hits = []
    for s in mine:
        for who, said in prior or ():
            if any(near_duplicate(old, s, ratio) for old in sentences(said, min_chars=min_chars)):
                hits.append((str(who or ""), s))
                break
    if len(hits) * 2 <= len(mine):
        return "", ""
    return hits[0]


def drop_echoes(items, prior, text_of=lambda x: x, who_of=lambda x: "", min_chars=12,
                ratio=0.86, why=""):
    """`items` with every message that echoes the room dropped, and each drop
    logged. Whatever survives joins `prior` for the messages behind it, so one
    burst cannot repeat itself either.

    Flagged and dropped, never rewritten: a message that says what has already
    been said is a signal about the prompt, and asking again for content is
    the one retry this project does not make."""
    seen = list(prior or ())
    out = []
    for it in items:
        txt = text_of(it)
        who, line = echoed_by(txt, seen, min_chars=min_chars, ratio=ratio)
        if who or line:
            logger.log(f"[dedup] dropped a bubble{(' ' + why) if why else ''} that echoed "
                       f"{who or 'the room'}: {str(line)[:70]!r}")
            continue
        seen.append((who_of(it), txt))
        out.append(it)
    return out

# ---------------------------------------------------------------- matching

_LATIN = re.compile(r"[A-Za-z][A-Za-z'-]*")
_CJK = re.compile(r"[぀-ヿ一-鿿]{2,}")


def words(text, min_latin=3):
    """The tokens two texts are compared on, in either language.

    Six modules carried the same regex -- `[A-Za-z][A-Za-z'-]{3,}|[CJK]{2,}` --
    and it is right for English and wrong for Japanese. Japanese has no spaces,
    so a maximal run of kana and kanji is a whole CLAUSE: 「彼は生きていた。ただ朝で、
    浴衣の話しか返してこなかっただけ。」 came out as three tokens, one per clause,
    and 「浴衣のこと」 shared none of them despite both being about the yukata. A
    Japanese memory was therefore unrecallable in ANY language, and the
    duplicate test that uses the same tokens could not see two Japanese lines
    saying the same thing either.

    Character bigrams are the standard cheap answer for a language without
    spaces and without dragging in a morphological analyser: 浴衣の話 gives
    浴衣, 衣の, の話, and 浴衣のこと gives 浴衣, 衣の, のこ, こと, so the two
    overlap on what they are actually about.

    `min_latin` keeps each caller's old English threshold -- `memory` wanted 4,
    `ick` wanted 2 -- because those were tuned against real text."""
    out = set()
    t = str(text or "")
    for w in _LATIN.findall(t):
        if len(w) >= min_latin:
            out.add(w.lower())
    for run in _CJK.findall(t):
        for i in range(len(run) - 1):
            out.add(run[i:i + 2])
    return out

def is_japanese(text):
    """Is this actually Japanese? A `ja` field is only named ja -- nothing
    checked it, so a call that answered in English stored English as the
    words somebody said. Counted rather than sniffed: a kaomoji or a stray
    LINE / OK is not enough to make an English line Japanese, and a line with
    no Latin letters in it (a "…", a sticker) is not English either.

    Her chat with him is the one place English is correct and does not come
    through here."""
    t = (text or "").strip()
    if not t:
        return True
    # a group burst carries its speakers as Latin prefixes ("Rena: ...") by
    # design, and on a short burst those letters outnumber the words: "Rena:
    # うん" is 4 Latin against 2 Japanese. The prefix is not the message.
    t = re.sub(r"^[A-Za-z][A-Za-z -]{0,20}:", "", t, flags=re.M).strip()
    ja = sum(1 for c in t if "぀" <= c <= "ヿ" or "一" <= c <= "鿿" or "ぁ" <= c <= "ゟ")
    latin = sum(1 for c in t if c.isascii() and c.isalpha())
    return latin == 0 or (ja > 0 and ja >= latin)

# ------------------------------------------------- her prose, not his lines

# A record of a thing of his quotes the lines a reader would stop on as they
# stand, and those lines are HIS: they may be English, they may be a path,
# they may be half a config file. A check on how SHE writes has to skip them
# or it fires on the compliant answers and the broken ones alike, which is
# what the Latin-prose voice rule did on 2026-09-07 -- four of the second
# character's note records flagged, two of them correctly Japanese, on the
# strength of an English file name quoted out of his note.
_QUOTED = re.compile(
    r"```.*?```"                                    # a fenced block
    r"|「[^」]*」|『[^』]*』"                          # a quotation, her punctuation
    r"|“[^”]*”|\"[^\"\n]*\""                        # ...and his
    r"|`[^`\n]*`"                                   # inline code
    r"|https?://\S+"                                # a link
    r"|[\w~.-]*[/\\][\w~./\\-]+"                    # a path
    r"|[\w-]+\.(?:md|txt|py|json|jsonl|db|log|cmd|ps1|html|js|css|yml|yaml"
    r"|ini|csv|zip|ogg|mp3|mp4|png|jpg|jpeg|webp|exe)\b"
    # ...and the labels a role ends its answer on for the caller to parse off
    # (IMPACT, GIST, LOOKUP). Those are the machine addressing itself in the
    # middle of an answer of hers; only the label goes, never the value.
    r"|(?-i:^[A-Z][A-Z_ ]{1,20}:)",
    re.I | re.M | re.S)


def unquoted(text):
    """`text` with everything it quotes taken out: quotations in either
    language, inline and fenced code, links, paths and file names.

    What is left is the prose the writer wrote herself, which is the only
    part a judgement about her language or her register can be made on."""
    return _QUOTED.sub(" ", str(text or ""))

