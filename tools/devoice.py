"""Rewrite the poisoned text already in the save, in her register.

The prompts were fixed, and the loops that fed her own phrasing back to her
were cut, but the store still holds months of text written in a voice she does
not have: similes that land, feelings located in her ribs, sentences built so
the good part arrives last. All of it comes back into her context -- messages
as literal history, scenes as the director's recent record, memories and day
narratives through recall -- so it keeps teaching.

This rewrites HER SIDE ONLY. His messages are never touched, never rewritten,
never shown to the model as something to change: what he said is what he said.
Rows are addressed by primary key, which every row has, rather than by any
Telegram id, which only her recent bubbles carry.

Nothing that happened is allowed to change. Same facts, same events, same
order, same length roughly, same Japanese and kaomoji: only the phrasing moves.

    python tools/devoice.py scan
    python tools/devoice.py run --dry [--table messages] [--limit 40]
    python tools/devoice.py run --yes

A copy of the database is made before anything is written.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.dbcopy import copy_db  # noqa: E402

from config import Config
from llm import LLM

# Whose save. Taken from the config she is named on rather than written
# here: a tool with one character's save built into it is a tool that
# rewrites the first character's text whoever asked for it.

# The shape of the fault, not a list of phrases: a simile, a feeling given a
# place or a size, a clause built to land. Deliberately wide -- the model is
# the judge, this only decides what is worth showing it.
SUSPECT = re.compile(
    r"\b(like (a|an|the|it|nothing|someone|somebody|she|he|they)\b"
    r"|as (if|though)\b"
    r"|in (my|her) (chest|ribs|stomach|throat|gut|bones)"
    r"|behind (my|her) (ribs|eyes|teeth)"
    r"|the way (a|an|the|people|someone)\b"
    r"|sits (in|on|behind|between)"
    r"|something (in|about) (my|her) (chest|throat|stomach))", re.I)

# The character is a token, filled from her own file at run time
# (`Config.fill`), the way every other instruction in this project is. It
# used to open by naming the first character, her home town, her ward and
# her school's ward -- in a tool any character's process can call, whose
# whole job is to rewrite what is already in a save.
SYSTEM = """You are correcting the register of text that belongs to one person: [[WHO_ORIGIN]]. The text is in English but she is not thinking in English: it is casual spoken Japanese rendered into English and it should read that way.

Rewrite each item so it says exactly the same thing in her voice.

WHAT MUST NOT CHANGE. The facts, the events, what anybody did or said, the order, the people, the places, the times and numbers, any Japanese or dialect words, any kaomoji, and roughly the length. You are not editing her life, you are only fixing how it is worded. If an item is already fine, return it unchanged.

WHAT TO FIX:
- Similes and metaphors she would not have made. She reuses worn phrases; she does not invent images and never extends one into a second clause.
- Feelings given a body or a size. A feeling does not sit anywhere, press on anything, live in her chest or ribs, or have a width, weight or temperature. Say what she did instead: what she checked, what she typed and deleted, how many minutes it had been.
- Sentences built so the good part arrives at the end. Put the plain fact first and stop.
- Long sentences with clauses inside them. Casual Japanese chains short clauses with から/し/けど; in English that is short sentences joined by so, and, but. One thought per line.
- Naming a situation as if it were a place or an object: a gap, a silence, a space, a distance, a weight, a hole. She does not turn what is happening into a noun and then put herself inside it. She says the plain fact: nobody has replied, the chat stopped, he has not said anything since 2am.
- Anything that sounds written rather than said.

KEEP OR ADD WHERE IT FITS: hedges (kind of, I guess, maybe, or something, right?), fillers (like, I mean, anyway, honestly), one flat intensity word doing the work (insane, no way, rough, so annoying), trailing off on but/so/though, repeating herself, contradicting herself in the next line, and specifics over feelings.

Output ONLY this JSON, one entry per item given, keyed by the same id:
{"items": [{"id": 12, "text": "..."}]}"""


def _rows(con, table):
    if table == "messages":
        return [(r[0], r[1]) for r in con.execute(
            "SELECT id, text FROM messages WHERE role != 'user' AND text IS NOT NULL AND length(text) > 12")]
    if table == "scenes":
        return [(r[0], r[1]) for r in con.execute(
            "SELECT id, inner FROM scenes WHERE inner IS NOT NULL AND length(inner) > 12")]
    if table == "self_memories":
        return [(r[0], r[1]) for r in con.execute(
            "SELECT rowid, text FROM self_memories WHERE text IS NOT NULL AND length(text) > 12")]
    if table == "days":
        # days is keyed by date and has no id column; rowid exists on every
        # ordinary sqlite table and is the safe way to address any of them
        return [(r[0], r[1]) for r in con.execute(
            "SELECT rowid, narrative FROM days WHERE narrative IS NOT NULL AND length(narrative) > 12")]
    return []


def _write(con, table, rowid, text):
    if table == "messages":
        con.execute("UPDATE messages SET text=? WHERE id=?", (text, rowid))
    elif table == "scenes":
        con.execute("UPDATE scenes SET inner=? WHERE id=?", (text, rowid))
    elif table == "self_memories":
        con.execute("UPDATE self_memories SET text=? WHERE rowid=?", (text, rowid))
    elif table == "days":
        con.execute("UPDATE days SET narrative=? WHERE rowid=?", (text, rowid))


TABLES = ("messages", "scenes", "self_memories", "days")


def scan(args):
    con = sqlite3.connect(f"file:{_db(args)}?mode=ro", uri=True)
    total = flagged = 0
    for t in TABLES:
        rows = _rows(con, t)
        hits = [r for r in rows if SUSPECT.search(r[1] or "")]
        total += len(rows)
        flagged += len(hits)
        print(f"  {t:14s} {len(hits):4d} suspect of {len(rows):4d}")
        for _, txt in hits[:2]:
            print(f"       - {' '.join(txt.split())[:96]}")
    d = con.execute("SELECT value FROM kv WHERE key='diary'").fetchone()
    n = len(json.loads(d[0])) if d else 0
    print(f"  {'diary (kv)':14s} {n:4d} entries, all rewritten by --table diary")
    print(f"\n{flagged} suspect of {total} rows; his messages are not counted and never touched")


def run(args):
    cfg = Config(args.config)
    llm = LLM(cfg)
    system = cfg.fill(SYSTEM, "devoice")
    db = _db(args)
    if not args.dry:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        keep = os.path.join("data", "retired", stamp)
        os.makedirs(keep, exist_ok=True)
        copy_db(db, os.path.join(keep, os.path.basename(db)))
        print(f"copy of the save kept in {keep}\n")
    con = sqlite3.connect(db, timeout=30.0)
    tables = [args.table] if args.table else list(TABLES)
    done = 0
    for t in tables:
        if t == "diary":
            continue
        rows = [r for r in _rows(con, t) if SUSPECT.search(r[1] or "")]
        if args.limit:
            rows = rows[:args.limit]
        print(f"[{t}] {len(rows)} to rewrite")
        for i in range(0, len(rows), args.batch):
            chunk = rows[i:i + args.batch]
            payload = [{"id": rid, "text": txt} for rid, txt in chunk]
            data, _ = llm.call_json("devoice", [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps({"items": payload}, ensure_ascii=False)}])
            got = {int(x["id"]): str(x.get("text", "")).strip()
                   for x in (data or {}).get("items", []) if isinstance(x, dict) and "id" in x}
            for rid, old in chunk:
                new = got.get(rid, "")
                if not new or new == old:
                    continue
                # a rewrite that loses half the content is a summary, not a
                # rewrite, and would quietly delete something that happened
                if len(new) < len(old) * 0.5:
                    print(f"    ! {rid} refused: {len(old)} -> {len(new)} chars")
                    continue
                if args.dry:
                    print(f"    - {' '.join(old.split())[:88]}")
                    print(f"    + {' '.join(new.split())[:88]}")
                else:
                    _write(con, t, rid, new)
                done += 1
            if not args.dry:
                con.commit()
            print(f"  {min(i + args.batch, len(rows))}/{len(rows)}")
    if args.table in (None, "diary"):
        r = con.execute("SELECT value FROM kv WHERE key='diary'").fetchone()
        entries = json.loads(r[0]) if r else []
        # one entry per call: a diary entry is several hundred words, and four
        # of them in one call came back echoed rather than rewritten
        got = {}
        for n, e in enumerate(entries):
            txt = e.get("text", "")
            if not txt:
                continue
            data, _ = llm.call_json("devoice", [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(
                    {"items": [{"id": n, "text": txt}]}, ensure_ascii=False)}])
            for x in (data or {}).get("items", []):
                if isinstance(x, dict) and "id" in x:
                    got[int(x["id"])] = str(x.get("text", "")).strip()
        if entries:
            for n, e in enumerate(entries):
                new = got.get(n, "")
                if new and len(new) >= len(e.get("text", "")) * 0.5:
                    if args.dry:
                        print(f"    diary {e.get('date')}: {' '.join(new.split())[:88]}")
                    else:
                        e["text"] = new
                    done += 1
            if not args.dry:
                con.execute("INSERT OR REPLACE INTO kv(key,value) VALUES('diary',?)",
                            (json.dumps(entries, ensure_ascii=False),))
                con.commit()
    print(f"\n{done} rewritten{' (dry run, nothing written)' if args.dry else ''}")


def _db(args):
    """Her save, off her own config."""
    return str(Config(args.config).logging.db_path or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json", help="whose save and whose voice")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.set_defaults(func=scan)
    r = sub.add_parser("run")
    r.add_argument("--table", choices=list(TABLES) + ["diary"])
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--batch", type=int, default=8)
    r.add_argument("--dry", action="store_true")
    r.add_argument("--yes", action="store_true")
    r.set_defaults(func=run)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
