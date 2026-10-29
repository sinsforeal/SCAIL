"""Two pure checks for the S arm of the B-zombie bench (tk-7wb, tk-wnp).

Code decides when and how much; the model decides what. No model call in
here, no store, no clock: the persona hands in text and gets text or a list
back, so every rule is a unit test.

1. Bubble budget. How many bubbles a reply may have comes from how much he
   wrote (words for English, characters for Japanese) and, when the state
   gives a clean signal, how tired or hurt she is. The reply prompt states
   the number and `merge_to_budget` enforces it at the split: extra lines
   are folded into the last bubble, never dropped.

2. Repetition check. A draft is compared with her last N sent lines and
   with his last message. Six findings: a near-duplicate line, a phrase run
   she has already used, a repeated opener or sign-off, a question she
   already asked that he has not answered, an opener that parrots his
   words. A hit sends the draft back once (persona.generate owns that).

The numbers live in the `bz_s10` config section (config.py); the defaults
here only back a missing key.
"""
import re

_PUNCT = "、。，．,.!?！？…・;；:：「」『』()（）[]【】\"'`~〜ー-"
_CJK = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")
_CLAUSE = re.compile(r"[、。，．,.!?！？…;；:：\n]+")
_FILLER = {"lol", "lmao", "haha", "hah", "ok", "okay", "oh", "ah", "hm", "hmm", "um", "uh", "so", "well", "yeah", "yep", "no",
           "alright", "anyway", "and", "but", "the", "a", "i", "it", "is", "that", "this", "you", "to", "of", "in", "its", "im"}
_JA_EVAL_TAIL = re.compile(r"(?:いいね|いいな|よかった|すごい|いいよ|ね|な|よ|か)+$")

DEFAULTS = {
    "budget": False,
    "budget_table_en": [[3, 1], [10, 2], [25, 3], [60, 4]],
    "budget_table_ja": [[6, 1], [20, 2], [50, 3], [120, 4]],
    "budget_over": 5,
    "budget_min": 1,
    "budget_tired_energy": 30,
    "budget_upset_from": 40,
    "budget_state_delta": -1,
    "repeat_check": False,
    "repeat_window": 40,
    "repeat_dice": 0.6,
    "repeat_min_chars": 8,
    "repeat_phrase_words": 4,
    "repeat_phrase_ja_chars": 8,
    "repeat_echo": 0.6,
    "repeat_reask": 0.4,
    "repeat_kinds": ["near_dup", "phrase", "opener", "signoff", "reask", "echo"],
}


def opt(cfg, key):
    """One key of the bz_s10 section, from a Section, a dict or nothing."""
    if cfg is not None:
        v = cfg.get(key) if isinstance(cfg, dict) else getattr(cfg, key, None)
        if v is not None:
            return v
    return DEFAULTS[key]


# ---------------------------------------------------------------- text helpers

def is_ja(text):
    """Mostly Japanese: a third of the non-space characters are kana or kanji."""
    t = re.sub(r"\s+", "", str(text or ""))
    return bool(t) and len(_CJK.findall(t)) * 3 >= len(t)


def size_of(text):
    """(unit, count): characters for Japanese, words for everything else."""
    t = str(text or "").strip()
    if is_ja(t):
        return "ja", len(re.sub(r"\s+", "", t))
    return "en", len(t.split())


def _kata_to_hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def norm(text):
    """Lowercase, katakana as hiragana, punctuation and spaces folded away."""
    t = _kata_to_hira(str(text or "").lower())
    t = re.sub(r"\[[^\]]*\]", " ", t)
    t = "".join(" " if c in _PUNCT else c for c in t)
    return re.sub(r"\s+", " ", t).strip()


def _grams(s, n):
    s = s.replace(" ", "")
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def dice(a, b):
    """Character n-gram Dice similarity of two lines (trigrams, bigrams for Japanese)."""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    n = 2 if (is_ja(na) or is_ja(nb)) else 3
    ga, gb = _grams(na, n), _grams(nb, n)
    if not ga or not gb:
        return 0.0
    return 2.0 * len(ga & gb) / (len(ga) + len(gb))


def _tokens(text):
    return norm(text).split()


def _content(text):
    return [w for w in _tokens(text) if w not in _FILLER and len(w) > 1]


def clauses(text):
    return [c.strip() for c in _CLAUSE.split(str(text or "")) if c.strip()]


# ---------------------------------------------------------------- 1. the budget

def budget_for(his_text, cfg, energy=None, upset=None):
    """Bubbles she may send for this message of his, or None when there is
    nothing of his to match (she is writing first) or the switch is off."""
    if not opt(cfg, "budget"):
        return None
    t = str(his_text or "").strip()
    if not t:
        return None
    unit, n = size_of(t)
    table = opt(cfg, "budget_table_ja" if unit == "ja" else "budget_table_en")
    k = int(opt(cfg, "budget_over"))
    for limit, bubbles in table:
        if n <= int(limit):
            k = int(bubbles)
            break
    # state: only a clean signal moves it, and only down (tired or hurt
    # says less; nothing in her state makes her say more than he did)
    delta = int(opt(cfg, "budget_state_delta"))
    if energy is not None and float(energy) < float(opt(cfg, "budget_tired_energy")):
        k += delta
    elif upset is not None and float(upset) >= float(opt(cfg, "budget_upset_from")):
        k += delta
    return max(int(opt(cfg, "budget_min")), k)


def budget_line(n, his_text, ja_room):
    """The sentence in her reply prompt that states the budget."""
    unit, size = size_of(his_text)
    if ja_room:
        how = f"彼は{size}字" if unit == "ja" else f"彼は{size}語"
        return (f"長さ -- {how}。今回送る吹き出しは多くても{n}つ。少なくていい。"
                "彼の言葉が少ないなら一言で返すのが正しい。吹き出しと吹き出しのあいだは空行。どれにもかぎ括弧はつけない。")
    how = f"{size} characters" if unit == "ja" else f"{size} words"
    return (f"LENGTH -- he wrote {how}. send at most {n} bubble{'s' if n != 1 else ''} this time; fewer is fine, "
            "and one word back to one word is right. A BLANK LINE between each bubble, and no quotation marks around any of them.")


def merge_to_budget(parts, n, ja=False):
    """Fold every bubble past the n-th into the n-th. Nothing is dropped."""
    parts = [p for p in (parts or []) if p]
    if not n or n < 1 or len(parts) <= n:
        return parts
    glue = "" if ja else " "
    head = parts[:n - 1]
    tail = glue.join(p.strip() for p in parts[n - 1:])
    return head + [tail]


# ------------------------------------------------------------ 2. the repetition

def _first_clause(text):
    cs = clauses(text)
    return cs[0] if cs else ""


def _last_clause(text):
    cs = clauses(text)
    return cs[-1] if cs else ""


def _clause_ok(c):
    """A clause worth comparing: not a filler, long enough to mean something."""
    if is_ja(c):
        return len(norm(c).replace(" ", "")) >= 5
    toks = _tokens(c)
    return len(toks) >= 2 and any(w not in _FILLER for w in toks)


def _runs(text, k):
    toks = _tokens(text)
    return {" ".join(toks[i:i + k]) for i in range(len(toks) - k + 1)} if len(toks) >= k else set()


_WH = {"what", "why", "how", "who", "where", "when", "which", "did", "do", "does", "was", "were", "is", "are", "can",
       "could", "will", "would", "have", "has", "should"}


_WH_STRONG = {"what", "why", "how", "who", "where", "when", "which"}


def _is_question(text):
    """A question mark, or a clause that opens with a question word (she often
    writes a question with no mark)."""
    if "?" in text or "？" in text:
        return True
    for c in clauses(text):
        toks = _tokens(c)
        if toks and toks[0] in _WH:
            return True
        if any(w in _WH_STRONG for w in toks[:3]):
            return True
    return False


def _echo_stem(clause):
    c = norm(clause).replace(" ", "")
    return _JA_EVAL_TAIL.sub("", c)


# _check: findings for a draft as a list of (kind, note); empty when clean.
# bubbles = the draft; her_lines = her sent lines, oldest first; him_lines =
# his messages, the last one being what she answers (empty when she writes
# first); since_his_last = her lines sent after his last message.
def _check(bubbles, her_lines, him_lines, cfg, since_his_last=()):
    kinds = set(opt(cfg, "repeat_kinds"))
    window = int(opt(cfg, "repeat_window"))
    sent = [s for s in (str(x or "").strip() for x in (her_lines or [])) if s][-window:]
    bubbles = [b for b in (bubbles or []) if str(b or "").strip()]
    if not bubbles or not sent:
        return []
    his = str(him_lines[-1]) if him_lines else ""
    his_runs = {k: _runs(his, k) for k in (int(opt(cfg, "repeat_phrase_words")),)}
    out = []
    mn = int(opt(cfg, "repeat_min_chars"))
    thr = float(opt(cfg, "repeat_dice"))

    # near-duplicate line
    if "near_dup" in kinds:
        for b in bubbles:
            if len(norm(b).replace(" ", "")) < mn:
                continue
            best = max(sent, key=lambda s: dice(b, s))
            if dice(b, best) >= thr:
                out.append(("near_dup", f"\"{b[:60]}\" is nearly a line you already sent: \"{best[:60]}\""))
                break

    # a run of words she has already used (and that is not just his own)
    if "phrase" in kinds and not any(k == "near_dup" for k, _ in out):
        kw = int(opt(cfg, "repeat_phrase_words"))
        jc = int(opt(cfg, "repeat_phrase_ja_chars"))
        for b in bubbles:
            if is_ja(b):
                nb = norm(b).replace(" ", "")
                runs = {nb[i:i + jc] for i in range(len(nb) - jc + 1)}
                hit = next((s for s in sent if any(r in norm(s).replace(" ", "") for r in runs)), None)
                shared = next((r for r in runs if hit and r in norm(hit).replace(" ", "")), "")
                if hit and shared not in norm(his).replace(" ", ""):
                    out.append(("phrase", f"you already used \"{shared}\" in \"{hit[:60]}\""))
                    break
            else:
                mine = _runs(b, kw)
                for s in sent:
                    both = (mine & _runs(s, kw)) - his_runs[kw]
                    if both:
                        out.append(("phrase", f"you already said \"{sorted(both)[0]}\" in \"{s[:60]}\""))
                        break
                if any(k == "phrase" for k, _ in out):
                    break

    # opener and sign-off: the first clause of the first bubble, the last
    # clause of the last bubble, seen before as the same clause of her lines
    def seen_as(clause, picker):
        key = norm(clause)
        n = sum(1 for s in sent if picker(s) and norm(picker(s)) == key)
        return n

    if "opener" in kinds:
        c = _first_clause(bubbles[0])
        if c and _clause_ok(c):
            need = 1 if (len(_tokens(c)) >= 3 or is_ja(c)) else 2
            if seen_as(c, _first_clause) >= need:
                out.append(("opener", f"you open with \"{c[:40]}\" again; it is how you have opened before"))
    if "signoff" in kinds:
        c = _last_clause(bubbles[-1])
        if c and _clause_ok(c):
            need = 1 if (len(_tokens(c)) >= 3 or is_ja(c)) else 2
            if seen_as(c, _last_clause) >= need:
                out.append(("signoff", f"you end with \"{c[:40]}\" again; it is how you have ended before"))

    # a question she asked that is still unanswered
    if "reask" in kinds:
        pending = [s for s in (since_his_last or ()) if _is_question(s)]
        rt = float(opt(cfg, "repeat_reask"))
        for b in bubbles:
            if not _is_question(b):
                continue
            for q in pending:
                a, c = set(_content(b)), set(_content(q))
                ov = (len(a & c) / min(len(a), len(c))) if (a and c) else dice(b, q)
                if is_ja(b):
                    ov = dice(b, q)
                if ov >= rt:
                    out.append(("reask", f"you already asked \"{q[:60]}\" and he has not answered it"))
                    break
            if any(k == "reask" for k, _ in out):
                break

    # an opener that parrots his words
    if "echo" in kinds and his:
        c = _first_clause(bubbles[0])
        if c:
            hn = norm(his).replace(" ", "")
            if is_ja(c):
                stem = _echo_stem(c)
                if len(stem) >= 3:
                    g = _grams(stem, 2)
                    cover = len(g & _grams(hn, 2)) / len(g) if g else 0.0
                    if cover >= float(opt(cfg, "repeat_echo")) and len(norm(bubbles[0]).replace(" ", "")) <= len(stem) + 8:
                        out.append(("echo", f"you open by repeating his words (\"{c[:30]}\"); answer instead of echoing"))
            else:
                toks = _content(c)
                hs = set(_tokens(his))
                if len(toks) >= 2 and sum(1 for w in toks if w in hs) / len(toks) >= 0.75 and len(_tokens(bubbles[0])) <= 6:
                    out.append(("echo", f"you open by repeating his words (\"{c[:30]}\"); answer instead of echoing"))
    return out


def check(bubbles, history, cfg):
    """`history` is the thread as (who, text) pairs, who in {"her", "him"},
    oldest first. The window, his last message and her unanswered lines
    since it are taken from it."""
    her = [t for w, t in history if w == "her"]
    him = [t for w, t in history if w == "him"]
    idx = max([i for i, (w, _t) in enumerate(history) if w == "him"], default=-1)
    since = [t for w, t in history[idx + 1:] if w == "her"]
    return _check(bubbles, her, him, cfg, since_his_last=since)


def revise_note(findings, ja_room):
    """The one short note that goes back with the draft."""
    what = "; ".join(n for _k, n in findings[:3])
    if ja_room:
        return (f"\n（送る前に、繰り返し: {what}。同じ言い方は使わない。別の言い方にするか、別のことを言う。あなたのままで。）")
    return (f"\n(before you send, you are repeating yourself: {what}. do not reuse those words; say it another way "
            "or say something else. stay in character.)")
