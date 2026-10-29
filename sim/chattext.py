"""His chat with her as lines of prompt text.

Twenty modules each formatted the same block by hand -- a stamp, a label for
his side and one for hers, the text cut to a length -- and three of them had
the first character's name in the label. One function; every caller keeps
its own labels, its own cut and its own "(nothing recent)", so the bytes a
prompt carried before are the bytes it carries now.
"""


def lines(msgs, clock=None, chars=None, labels=("HIM", "HER"), stamps=True, sep="\n"):
    """`msgs` are store rows (`role`, `text`, `ts`); his side is the user role.
    `chars` cuts each text (None: whole); `stamps` puts `[HH:MM]` of her
    clock first; the join is `sep`. Empty input gives "" so a caller's
    `or "(nothing)"` still applies."""
    him, her = labels
    out = []
    for m in msgs:
        text = str(m.get("text") or "")
        if chars is not None:
            text = text[:chars]
        who = him if m.get("role") == "user" else her
        stamp = f"[{clock.hm(m['ts'])}] " if stamps else ""
        out.append(f"{stamp}{who}: {text}")
    return sep.join(out)
