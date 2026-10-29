"""Her talks with the people around her, as rows the record can read.

The exchange engine (`tomoe/exchange.py`) writes kv `cast_chat` and peer talk
(`sim/peers.py`) writes kv `peer_chat`; the compile, the coherence read and
recall want those rows without wanting either engine, and a character with no
cast and no peers simply has none. Two readers, no engine.
"""


def _all(store):
    """Both records, oldest first. A conversation with another running
    character is a conversation of hers and belongs in her day."""
    return list(store.get("cast_chat", []) or []) + list(store.get("peer_chat", []) or [])


def all_rows(store):
    """Every room row she has, oldest first: her cast exchanges and her talks
    with another running character, as one record. The name a caller outside
    this module uses -- the phone pick asks what is unanswered in her rooms
    and has no business reaching for a private."""
    return _all(store)


def compile_rows(store, date_str):
    """The day's talks verbatim, for the compile: the record of her day must
    hold what a friend said the way it holds what he said."""
    rows = [x for x in _all(store) if x.get("date") == date_str]
    out = []
    for x in rows:
        out.append(f"[{x['hm']}] with {x['who']} ({x['kind']}):")
        for t in x["turns"]:
            out.append(f"    {t['who']}: {(t.get('ja') or '').strip()}")
    return "\n".join(out) or "(no talks recorded)"


def search_rows(store):
    """(when, who, kind, turns, gist) for recall: her talks are part of the
    record it searches, not only his messages and the compiled days. The gist
    rides along because the turns are Japanese and his cue words are not."""
    return [(f"{x.get('date', '')} {x.get('hm', '')}", x.get("who", "?"), x.get("kind", ""),
             x.get("turns", []), x.get("gist", ""))
            for x in _all(store)]
