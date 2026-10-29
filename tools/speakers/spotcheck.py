"""Checking a recognised Japanese line against the English cue for the moment.

This is the quality measure for the case with no Japanese subtitle anywhere.
There is nothing to score the recogniser against -- that is the definition of
the case -- but there is a translation of the same episode, typed by a person
cue by cue, and a Japanese line that says something the English line does not
is either a mis-recognition or a line placed on the wrong cue. Neither is
visible any other way, and both are what the step is looking for.

What this cannot do is measure wording. A translation is not a transcript: it
reorders, it drops a particle, it renders a name as a pronoun. So the model is
asked for one of three verdicts about MEANING and a few words of reason, never
for a corrected Japanese line and never for a score. The verdicts are only
worth having if they agree with the errors a real caption would show, which is
what the comparison against a found caption in the same run is for: run both on
an episode that has a caption, count how often a flagged cue is a
high-error cue, and the flags on the next episode can be trusted or not on the
strength of that number.

The model is asked in batches because a cue is two short lines and a call is a
second of latency; the batch is small enough that one bad answer costs little.
An answer that does not parse is asked once more and then recorded as
unanswered, never stored raw.
"""
import io
import json
import os
import re
import time

# reasoning is left low on purpose: deciding whether two short lines say the
# same thing is not a reasoning problem, and thinking tokens are billed as
# output on every host.
EFFORT = "low"
MODEL = "deepseek-v4-flash"

SYSTEM = (
    "You check a Japanese speech-recognition transcript of an anime episode "
    "against a human English subtitle of the same episode. For each numbered "
    "item you are given the Japanese text a recogniser produced for one "
    "subtitle cue and the English line a translator wrote for that same cue.\n"
    "\n"
    "Decide whether the Japanese could be the original of that English line:\n"
    "  match    -- the Japanese plainly says what the English says\n"
    "  partial  -- part of it lines up and part does not, or one side clearly "
    "covers more speech than the other\n"
    "  mismatch -- they are about different things, or the Japanese is "
    "gibberish, or it is song lyrics where the English is dialogue\n"
    "\n"
    "A translation is not a transcript. Reordering, a dropped particle, a name "
    "rendered as a pronoun, an interjection written as a word: all of that is "
    "still a match. Judge meaning only, never wording or politeness level. "
    "Never rewrite the Japanese.\n"
    "\n"
    "Answer with JSON and nothing else: "
    '{\"verdicts\": [{\"i\": <the item number>, \"verdict\": '
    '\"match\"|\"partial\"|\"mismatch\", \"why\": \"<a few words>\"}]}. '
    "One entry per item, in the order given."
)


def batches(cues, size=40):
    """The cues in groups, each group the items of one call."""
    return [cues[i:i + size] for i in range(0, len(cues), size)]


def render(batch):
    """One call's user message."""
    out = []
    for c in batch:
        out.append("%d.\n  japanese: %s\n  english: %s"
                   % (c["i"], c["text"].replace("\n", " "),
                      (c.get("gloss") or "").replace("\n", " ")))
    return "\n".join(out)


def _client(key_path):
    from openai import OpenAI
    return OpenAI(api_key=io.open(key_path, encoding="utf-8").read().strip(),
                  base_url="https://openrouter.ai/api/v1")


def _parse(text):
    """The answer as a list of verdicts, or None if it is not one.

    A model that has been told to answer JSON still sometimes wraps it in a
    fenced block, which is the one deviation worth recovering from; anything
    else is a failed answer and is asked again.
    """
    s = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.+?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    try:
        d = json.loads(s)
    except ValueError:
        return None
    rows = d.get("verdicts") if isinstance(d, dict) else d
    if not isinstance(rows, list):
        return None
    out = []
    for r in rows:
        if not isinstance(r, dict) or "i" not in r:
            return None
        v = str(r.get("verdict", "")).strip().lower()
        if v not in ("match", "partial", "mismatch"):
            return None
        out.append({"i": int(r["i"]), "verdict": v,
                    "why": str(r.get("why", ""))[:120]})
    return out


def ask(batch, key_path, model_slug, order, log=print, retries=1):
    """One batch's verdicts, or None when the answer never parsed."""
    client = _client(key_path)
    payload = {
        "model": model_slug,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": render(batch)}],
        "temperature": 0.0,
        # the pinned host first, the router's next host for the same model
        # allowed: the running system's rule, so the measurement is made under
        # the conditions the system actually runs under
        "extra_body": {"reasoning": {"effort": EFFORT, "exclude": False},
                       "provider": {"order": list(order), "allow_fallbacks": True}},
    }
    for attempt in range(retries + 1):
        t0 = time.time()
        r = client.chat.completions.create(**payload)
        dt = time.time() - t0
        text = (r.choices[0].message.content or "").strip()
        u = getattr(r, "usage", None)
        usage = {"in": getattr(u, "prompt_tokens", 0) or 0,
                 "out": getattr(u, "completion_tokens", 0) or 0}
        try:
            c = r.model_dump().get("usage", {}).get("cost")
            if c is not None:
                usage["cost"] = float(c)
        except Exception:
            pass
        rows = _parse(text)
        if rows is not None:
            return {"verdicts": rows, "usage": usage, "seconds": round(dt, 1),
                    "attempts": attempt + 1}
        log("  the answer did not parse%s"
            % (", asking again" if attempt < retries else ", recorded unanswered"))
    return {"verdicts": None, "usage": usage, "seconds": round(dt, 1),
            "attempts": retries + 1}


def estimate(cues, size=40, price_in=0.14, price_out=0.28):
    """What the run would cost, from the text that would be sent.

    Japanese runs about one token to the character and English about four
    characters to the token; the mixture is taken at three characters to the
    token, which is the wrong side of right for a Japanese-heavy prompt and so
    over-states rather than under-states.
    """
    groups = batches(cues, size)
    chars = sum(len(SYSTEM) + len(render(b)) for b in groups)
    tok_in = chars / 3.0
    # a verdict and a few words of reason, per cue, plus the JSON around it
    tok_out = 40.0 * len(cues) + 20.0 * len(groups)
    return {"cues": len(cues), "batches": len(groups),
            "tokens_in": int(tok_in), "tokens_out": int(tok_out),
            "usd": tok_in / 1e6 * price_in + tok_out / 1e6 * price_out}


# ------------------------------------------------- the flags against a caption

def coincidence(rows, threshold):
    """How the model's flags line up with the error a real caption shows.

    `rows` are the cues that have both a verdict and a character error rate.
    Flagged means the model said partial or mismatch; high error means the
    recogniser's line differs from the caption's by more than `threshold` of
    its characters. Precision is the share of flagged cues that really are bad,
    recall the share of bad cues the flags found.
    """
    tp = fp = fn = tn = 0
    for r in rows:
        flagged = r["verdict"] in ("partial", "mismatch")
        bad = r["cer"] > threshold
        if flagged and bad:
            tp += 1
        elif flagged:
            fp += 1
        elif bad:
            fn += 1
        else:
            tn += 1
    return {"threshold": threshold, "flagged_bad": tp, "flagged_ok": fp,
            "unflagged_bad": fn, "unflagged_ok": tn,
            "precision": tp / float(tp + fp) if (tp + fp) else 0.0,
            "recall": tp / float(tp + fn) if (tp + fn) else 0.0}


def key_file(root):
    """Where the router's key lives on this machine."""
    return os.path.join(root, "secerts", "openrouter.txt")
