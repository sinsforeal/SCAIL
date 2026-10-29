"""Is this a record of what was in front of her, or something else?

Three roles read a thing of his and write down what was there: the note open
in front of her (`note_read`), his notes folder (`vault`) and his downloads
(`downloads`). Each prompt asks for two to four sentences of record, in her
language, with the lines a reader would stop on quoted as they stand and
nothing at all about how it felt -- the record is put in front of her later
and read back as her own memory, so a sentence about her feelings becomes her
memory of having felt it.

On 2026-09-07 the model holding those prompts on flash broke them three times
in nine: 16:31:31 came back as his file pasted verbatim, 16:32:03 came back in
feelings, and three came back in English. The prompt was right and the model
did not hold it, which is the case a check exists for.

Four refusals, in the order they are cheapest to test:

  too long        the answer is more than `MAX_SHARE` of the skim it was
                  handed. Only where the skim is long enough for that to mean
                  anything: a 127-character skim was legitimately answered at
                  355 and 412 characters on 2026-09-07, because two to four
                  sentences of record about a short note is longer than the
                  note itself.
  a paste         the answer repeats a long run of his file word for word
                  OUTSIDE anything it is quoting. A quotation is short and
                  marked; a paste is neither.
  wrong language  a character instructed in her own language whose prose --
                  what is left once the quotations are out -- is more Latin
                  than Japanese.
  feelings        a phrase from `tools/interior_words.py`, which is the list
                  the prompt checker holds every mechanism prompt to, plus
                  the Japanese forms of the same ask.

A refused answer is asked for once more with the reason appended to the user
message. A second refusal keeps nothing: an event that is not a record is
worse than no event, because it is read back to her as her own memory.
"""
import re

import logger
from sim import lang
from sim.textutil import is_japanese, unquoted

# How much of the skim a record may be. A record is two to four sentences
# about a file; anything approaching the file's own length is the file.
MAX_SHARE = 0.6
# ...and the skim has to be at least this long for that ratio to say
# anything. Below it a full record is honestly longer than what it is about.
MIN_SKIM = 600
# A run this long, word for word out of his file and outside anything the
# answer is quoting, is a paste rather than a quotation.
PASTE_RUN = 80

# The Japanese forms of the ask, as they actually turned up: 「感じさせた」 and
# 「奇妙な緊張感を彼女に与えた」 in the record of 2026-09-07 16:32:03. Each is a claim
# about what the thing DID to her, which is the one thing this role may not
# write. A verb of noticing (目を留めた, 目を引いた) is deliberately not here:
# noticing is what the record is.
_JA_INTERIOR = re.compile(
    r"感じさせ"
    r"|感じた"
    r"|感じられ"
    r"|気がした"
    r"|彼女に[^。]{0,14}?与え"
    r"|胸が"
    r"|動揺")


def _english_interior():
    """The English half of the phrase list: `tools/interior_words.py`'s own,
    which is what the prompt checker holds every mechanism prompt to,
    imported rather than copied so the two cannot drift. None if the tool
    cannot be imported, and then only the Japanese half runs."""
    try:
        from tools.interior_words import ASKS
        return ASKS
    except Exception:
        return None


def refusal(config, answer, skim="", role=""):
    """Why this answer is not a record, or "" if it is one."""
    text = str(answer or "").strip()
    if not text:
        return "it was empty"
    prose = unquoted(text)
    src = str(skim or "")
    if src and len(src) >= MIN_SKIM and len(text) > MAX_SHARE * len(src):
        return (f"it runs to {len(text)} characters against a {len(src)}-character skim, which is a "
                f"copy of his file rather than a record of it")
    run = _shared_run(prose, src, PASTE_RUN)
    if run:
        return (f"it repeats {len(run)} characters of his file word for word outside anything it "
                f"quotes ({run[:40]!r}...), which is a paste rather than a record")
    if lang.reads_ja(config) and prose.strip() and not is_japanese(prose):
        return ("its own prose is in English; she is instructed in her own language and reads this "
                "back as something she is carrying")
    english = _english_interior()
    hit = (english.search(prose) if english is not None else None) or _JA_INTERIOR.search(prose)
    if hit:
        return (f"it says what the thing did to her ({hit.group(0)!r}); this role writes what was "
                f"there and nothing about her")
    return ""


def _shared_run(answer, source, run):
    """The first run of `run` characters the answer takes word for word out of
    the source, or "". Whitespace is squeezed on both sides first, so a paste
    that was re-wrapped on the way out is still a paste."""
    a = " ".join(str(answer or "").split())
    s = " ".join(str(source or "").split())
    if len(a) < run or len(s) < run:
        return ""
    windows = {s[i:i + run] for i in range(len(s) - run + 1)}
    for i in range(len(a) - run + 1):
        if a[i:i + run] in windows:
            return a[i:i + run]
    return ""


def ask(llm, role, messages, config, skim="", tag="notes"):
    """Call a record role and hold it to writing a record.

    One retry, with the reason it was refused appended to the user message --
    the same shape as `LLM.call_json`'s retry for an answer that would not
    parse, and for the same reason: the model is told what was wrong with the
    answer it just gave instead of being asked the identical question again.
    Returns the answer, or "" when nothing may be kept."""
    out = (llm.call(role, messages) or "").strip()
    why = refusal(config, out, skim, role)
    if not why:
        return out
    logger.log(f"[{tag}] the record was refused: {why}; asking again")
    again = [dict(m) for m in messages]
    for m in reversed(again):
        if m.get("role") == "user":
            m["content"] = (m["content"] + "\n\nTHE PREVIOUS ANSWER WAS REFUSED because "
                            + why + ". Write the record again, and do not do that.")
            break
    out2 = (llm.call(role, again) or "").strip()
    why2 = refusal(config, out2, skim, role)
    if not why2:
        return out2
    logger.log(f"[{tag}] no record kept: {why2} twice")
    return ""
