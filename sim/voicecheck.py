"""Is this line in the voice it is supposed to be in?

Every speaker in her world has a sheet that says how they sound, and until
today nothing checked the output against it. Reading all 299 turns by hand
found a father written in his wife's register, a brother calling his sister
君, one region's dialect in the mouth of a girl from another, and 绫 -- a
simplified Chinese character -- in a Japanese sentence. All of it had been
sitting in the record for days, teaching the next call.

This flags. It does not rewrite: a line that is off is a signal about the
prompt, and silently correcting it hides the signal and puts words in
somebody's mouth twice over. Flags go to the log and to kv `voice_flags`,
where `/voice` reads them.

The rules live in the file the CHARACTER's own config names
(`character.voice_rules_file`; there is one per character and nothing here
knows which), keyed by a speaker's roster handle, by role (`role:diary`), or
`_all` for everything. Adding a person or
a role is an entry in that file and no code here. The file is re-read whenever
it changes, like `cast.json` and `places.json`. A set may `inherit` another's
rules, and may declare a `context` that is always true of it -- which is how
the roles that are her private mind are exempt from the dialect rule without
the caller knowing anything about her.
"""
import json
import os
import re
import time

import logger
from sim.textutil import unquoted

_CACHE = {"path": None, "mtime": 0, "rules": {}, "compiled": {}}


def _load(path):
    """The rule file, re-read on change. A broken file flags nothing rather
    than taking the bot down over a comma."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    if _CACHE["path"] == path and _CACHE["mtime"] == mtime:
        return _CACHE["rules"]
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        logger.log(f"[voice] rules unreadable, checking nothing: {type(e).__name__}: {e}")
        return {}
    rules, compiled = {}, {}
    for key, block in raw.items():
        if key.startswith("_comment") or not isinstance(block, dict):
            continue
        out = []
        for r in block.get("rules", []) or []:
            try:
                out.append({"id": r.get("id", "?"), "why": r.get("why", ""),
                            "find": re.compile(r["find"]),
                            "unless": re.compile(r["unless"]) if r.get("unless") else None,
                            # what the rule is measured ON. "unquoted" is her
                            # own prose with the quotations, the code, the
                            # links, the paths and the file names taken out:
                            # a rule about how SHE writes cannot read the
                            # lines she is quoting out of his file, and the
                            # Latin-prose rule did, on the answers that were
                            # obeying their prompt. Anything else, including
                            # nothing, is the whole line.
                            "measure": str(r.get("measure") or ""),
                            "skip_when": tuple(r.get("skip_when") or ())})
            except (KeyError, re.error) as e:
                logger.log(f"[voice] rule {key}/{r.get('id')} is broken: {type(e).__name__}")
        rules[key] = block
        compiled[key] = out
    _CACHE.update({"path": path, "mtime": mtime, "rules": rules, "compiled": compiled})
    logger.log(f"[voice] rules loaded: {len(rules)} set(s), {sum(len(v) for v in compiled.values())} rule(s)")
    return rules


def check(config, text, who="", role="", context=()):
    """Every rule this line breaks: [(set, id, why, what matched)]. `_all`
    always applies; the speaker's set and the role's set apply when named.

    `context` is what the caller knows about the moment that a regex cannot
    see -- "family" for the kitchen, "slip" when her state says the mask is
    down. A rule naming one of those in `skip_when` does not fire there. It
    is how a conditional rule (a dialect that is hers at home and a slip in the
    group chat) lives in the rule file instead of in a second copy of the
    patterns in the caller."""
    path = getattr(config.character, "voice_rules_file", "")
    if not path or not text:
        return []
    _load(path)
    out = []
    keys = ["_all"]
    if who:
        # "Rena" and "Rena-chan" are one girl with two labels in the record --
        # the group burst prefixes her short, the LINE turns use the roster
        # name -- so the match goes both ways: the label itself, its base, and
        # any rule set whose base is this label.
        who = str(who)
        base = who.split("-")[0]
        keys += [who, base]
        keys += [k for k in _CACHE["compiled"] if k.split("-")[0] == base and k != who]
        # the record names its speakers in Japanese (香芝玲奈) and the rule sets
        # are keyed by the roster handle, so the speaker has to be resolved or
        # a whole person's rules silently never run. This is not hypothetical:
        # relabelling the record took every flag to zero until it was added.
        from sim import roster
        keys += [roster.key_of(config, who), roster.role_of(config, who)]
    if role:
        keys.append(f"role:{role}")
    # a role set may `inherit` a speaker's rules rather than restate them:
    # reflect, spiral, morning and the rest are all HER voice, and the rules
    # for her voice should live in one place
    for key in list(keys):
        src = (_CACHE["rules"].get(key) or {}).get("inherit")
        if src and src not in keys:
            keys.append(src)
    seen = set()
    ctx = set(context or ())
    # a rule set can also declare what is always true of the moment it covers.
    # Her anticipation, her reflect and her diary are her own head, and a mask
    # is for other people, so the dialect rule does not apply there -- and the
    # caller cannot say so, because llm.py has a role name and nothing else.
    for key in keys:
        ctx.update((_CACHE["rules"].get(key) or {}).get("context") or ())
    for key in keys:
        for r in _CACHE["compiled"].get(key, []):
            if (key, r["id"]) in seen:
                continue
            if ctx.intersection(r["skip_when"]):
                continue
            subject = unquoted(text) if r["measure"] == "unquoted" else text
            m = r["find"].search(subject)
            if not m:
                continue
            if r["unless"] and r["unless"].search(subject):
                continue
            seen.add((key, r["id"]))
            out.append((key, r["id"], r["why"], m.group(0)))
    return out


def note(config, store, text, who="", role="", where="", context=()):
    """Check and record. Returns the flags; the caller carries on regardless,
    because nothing here changes what was written. `store` may be None (a
    tool's own LLM), and then it only logs."""
    flags = check(config, text, who, role, context)
    if not flags:
        return []
    if store is None:
        for key, rid, why, hit in flags:
            logger.log(f"[voice] {who or role or key}: {rid} -- {why} ({hit!r})")
        return flags
    rows = store.get("voice_flags", []) or []
    for key, rid, why, hit in flags:
        logger.log(f"[voice] {who or role or key}: {rid} -- {why} ({hit!r}) in {text[:60]!r}")
        rows.append({"ts": time.time(), "who": who, "role": role, "where": where,
                     "rule": rid, "why": why, "hit": hit, "line": text[:200]})
    keep = int(getattr(config.character, "voice_flags_keep", 200) or 200)
    store.set("voice_flags", rows[-keep:])
    return flags


def report(config, store, limit=20):
    rows = (store.get("voice_flags", []) or [])[-limit:]
    if not rows:
        _load(getattr(config.character, "voice_rules_file", ""))
        sets = ", ".join(sorted(k for k in _CACHE["compiled"] if k != "_all"))
        return f"nothing flagged. rule sets: _all, {sets}"
    out = [f"{len(rows)} flag(s), newest last:"]
    for r in rows:
        when = time.strftime("%m-%d %H:%M", time.localtime(r.get("ts", 0)))
        out.append(f"  {when} {r.get('who') or r.get('role') or '?'} [{r.get('rule')}] {r.get('why')}")
        out.append(f"        {r.get('hit')!r} in {r.get('line', '')[:80]}")
    return "\n".join(out)
