# -*- coding: utf-8 -*-
"""Her own record reaches her in the rooms with her own people, and does not
say the same thing twice.

`tools/lore_test_rena.py` asks whether the retrieval finds the right record
for a phrase. This asks the question one layer up: does a turn of hers in her
own room actually CARRY that record's line into the prompt the model is sent.
It did not until 2026-09-06 -- only her reply to him asked -- and a character
whose past is in a record file remembered none of it where most of her words
are written.

Three cases, on the promoted character because she is the one with a record:

  1. a friend names her brother: the record's own words are in her assembled
     prompt, under the header that says knowing a thing is not being asked to
     say it;
  2. the next turn in the same room, where only HER own reply names him
     again: nothing, because an anecdote she has just told feeding itself is
     what `lore.own_words_days` exists to stop;
  3. a room where nobody names anything of hers: no header and no line.

Nothing here spends a model call or reaches the network, and it builds on a
fresh save in a temporary directory, never on a live one.

    python tools/lore_rooms_test.py

Run by `tools/smoke.py`; a failure stops a restart.
"""
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

CONFIG = "config_rena.json"
TRIGGERS = os.path.join("data", "rena", "triggers.json")
# The record the cases are built on: one her sheet states outright, whose
# phrases are names rather than grammar, and whose line is unmistakable in a
# prompt. Its cue phrase is read out of her own trigger file rather than
# written here, so editing her triggers moves this test with them.
RECORD = "rn.household.brother-keita"
WHEN = "2026-09-07 12:40"


class Captured(Exception):
    """Her assembled request, caught on its way to the provider."""

    def __init__(self, messages):
        Exception.__init__(self, "captured")
        self.messages = messages


def cue_phrase():
    d = json.load(io.open(TRIGGERS, encoding="utf-8"))
    phrases = (d.get("records", d) or {}).get(RECORD) or []
    if not phrases:
        raise SystemExit("[lore-rooms] %s has no cue phrase in %s" % (RECORD, TRIGGERS))
    # the longest, because a short phrase can be a substring of an ordinary
    # sentence and the third case has to be genuinely silent
    return sorted((str(p) for p in phrases), key=len)[-1]


def build(tmp):
    from tools import harness
    harness.refuse_network()
    harness.refuse_model_before_build()
    db = os.path.join(tmp, "rooms.db")
    real, sys.stdout = sys.stdout, io.StringIO()
    try:
        app = harness.build_on(db, config=CONFIG, copy=False,
                               extra=["--sim", WHEN, "--speed", "1"])
    finally:
        sys.stdout = real
    return app


def a_friend(app):
    """Somebody in her world to be talked to, from her own cast rather than
    written here."""
    from sim import roster
    for key in roster.classmates(app.config):
        if roster.is_self(app.config, key):
            continue
        name = roster.record_name(app.config, key)
        if name:
            return str(name)
    raise SystemExit("[lore-rooms] her cast has nobody to talk to")


def prompt_for(app, who, kind, turns):
    """The text of the request her room would send, without sending it."""
    def _capture(role, messages, *a, **k):
        raise Captured(messages)
    app.llm.call_json = _capture
    scene = {"location": "the classroom", "activity": "lunch at her desk",
             "with": who, "phone_access": "free"}
    try:
        app.exchange._her_turns(who, kind, list(turns), scene)
    except Captured as c:
        return "\n\n".join(str(m.get("content") or "") for m in c.messages)
    raise SystemExit("[lore-rooms] her room answered without asking anything")


def record_texts(app):
    lore = app.lore
    lore._load()
    for r in lore._recs:
        if r["id"] == RECORD:
            return [str(t) for t in r["texts"] if str(t).strip()]
    raise SystemExit("[lore-rooms] %s is not in her record" % RECORD)


def carried(prompt, texts, head):
    """Is the record in this prompt, under its header?"""
    said = [t for t in texts if t[:40] in prompt]
    return said, (head[:60] in prompt)


def main():
    # A tree without the promoted character, or with her record switched off,
    # has nothing here to be wrong: the retrieval returns nothing for a
    # character with no record and that is the case the byte-identical proof
    # covers. Said out loud rather than passed silently.
    if not (os.path.exists(CONFIG) and os.path.exists(TRIGGERS)):
        print("[lore-rooms] no character with a record of her own in this tree; nothing to check")
        return 0
    tmp = tempfile.mkdtemp(prefix="scail_lore_rooms_")
    fails = []
    try:
        app = build(tmp)
        if app.lore is None:
            print("[lore-rooms] her record is switched off; nothing to check")
            app.store.conn.close()
            return 0
        from sim import lore_rooms
        head = lore_rooms.preamble(app.config)
        her = str(getattr(app.config.character, "name_ja", "") or app.config.character.name)
        friend = a_friend(app)
        texts = record_texts(app)
        phrase = cue_phrase()
        print("[lore-rooms] %s, record %s, cue phrase %s" % (app.config.character.name, RECORD, phrase))

        # 1. a friend names it
        turns = [{"who": friend, "ja": "%sってどんな人なん？" % phrase, "hm": "12:31"}]
        p1 = prompt_for(app, friend, "line", turns)
        said, headed = carried(p1, texts, head)
        print("  named by a friend: %d line(s) of the record in the prompt, header %s"
              % (len(said), "there" if headed else "MISSING"))
        for t in said:
            print("    " + t[:90])
        if not said:
            fails.append("a friend named her brother and the record was not in her prompt")
        if not headed:
            fails.append("the record was in her prompt with no header over it")

        # 2. the same room one turn on, where only her own reply names it
        turns += [{"who": her, "ja": "%sは十九やけん、まあ普通", "hm": "12:33"},
                  {"who": friend, "ja": "そっか、わかった", "hm": "12:36"}]
        p2 = prompt_for(app, friend, "line", turns)
        said2, headed2 = carried(p2, texts, head)
        print("  named again only by her own reply: %d line(s), header %s"
              % (len(said2), "there" if headed2 else "absent"))
        if said2 or headed2:
            fails.append("she was offered the same record again off her own telling")

        # 3. a room where nothing of hers is named
        quiet = [{"who": friend, "ja": "おはよう。今日眠い", "hm": "07:44"}]
        p3 = prompt_for(app, friend, "line", quiet)
        said3, headed3 = carried(p3, texts, head)
        print("  nothing named: %d line(s), header %s"
              % (len(said3), "THERE" if headed3 else "absent"))
        if said3 or headed3:
            fails.append("a room that named nothing of hers still carried her record")

        # 4. a room she is only a member of, run by somebody else's process
        # (`sim/peers.py`). Her turn there is built by her own persona but
        # not by the exchange, so it is a second place the record has to
        # reach and it is asked here for the same phrase.
        env = {"id": "room-test", "kind": "group", "date": WHEN[:10], "hm": "12:31",
               "present": [friend], "cue": ""}
        rec = {"kind": "group", "turns": [{"who": friend, "ja": "%sってどんな人なん？" % phrase, "hm": "12:31"}]}
        p4 = app.peers._room_user(env, rec, {"from": "hub-test", "name": friend})
        said4, headed4 = carried(p4, texts, head)
        print("  a room she does not own: %d line(s), header %s"
              % (len(said4), "there" if headed4 else "MISSING"))
        if not said4 or not headed4:
            fails.append("a room she does not own did not carry her record")

        app.store.conn.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if fails:
        print("")
        for f in fails:
            print("[lore-rooms] FAIL: " + f)
        return 1
    print("[lore-rooms] her record reaches her rooms, once")
    return 0


if __name__ == "__main__":
    sys.exit(main())
