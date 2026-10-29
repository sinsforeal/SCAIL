"""The prompt a reply was drawn from, rebuilt for a reply that kept none.

A reply delivered before the freeze existed has no `reply_prompts` row, and
the array it went out on cannot be recovered from the record -- only rebuilt.
This is the rebuild, and it is the method `tools/regen_reply.py` already
uses to answer an old message again: a consistent copy of the save through
sqlite's backup API, the history and every timestamped table cut back to the
moment of the message she was answering, the whole runtime built on that copy
in console mode with no sensors, and the assembly run once with the model
stubbed so it costs nothing. What the assembly produces is the array.

The two callers:

* `tools/regen_reply.py` imports the copy and the cut, so the two halves
  cannot drift apart;
* the runtime's redraw command runs this module as a CHILD PROCESS when the
  message he tapped has no kept prompt. A child rather than a thread: the
  runtime's log directory, its network watch and its one-per-save lock are
  process-wide, and a second runtime built beside a live one inside the same
  process would take all three over.

    python -m sim.reconstruct --config <cfg> --db <save> --message-id <hers>
                              --out <file.json>

What comes back is not what she was given. It is the same assembly over the
same record at the same minute, and the parts of it that are read out of the
record -- her history, what she carries, her own words -- are the same bytes.
The parts that were live at the time and are not kept per-minute are rebuilt
from the nearest thing the record holds, so the row is marked as rebuilt and
everything drawn from it says so.
"""
import argparse
import io
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Everything the save learned AFTER his message goes, or the rebuilt prompt
# knows the future: an answer to one message once quoted a message two later,
# because the fact and the event it had become were still in the copy. kv rows
# carry no time of their own and are not cut; that is the known remainder, and
# the gauges are lifted out of the state log by hand for the same reason.
TIMED_TABLES = (("events", "ts"), ("user_facts", "ts"), ("self_memories", "ts"),
                ("scenes", "ts"), ("state_log", "ts"), ("digests", "ts"),
                ("threads", "created_ts"), ("cast_facts", "ts"))


def consistent_copy(src, dst):
    """A coherent image of a save another process is writing to.

    sqlite's own backup through a read-only connection: a plain file copy of
    an open database returns the on-disk image from before that process
    started writing, and one such copy showed no rows at all."""
    from tools.dbcopy import copy_db
    return copy_db(src, dst)


def _cut_tables(con, ts):
    cut = 0
    for table, col in TIMED_TABLES:
        try:
            cut += con.execute(f"DELETE FROM {table} WHERE {col}>?", (float(ts),)).rowcount
        except sqlite3.Error:
            pass
    return cut


def cut_to(con, message_id, unread_run=False):
    """Cut an open copy back to the moment one of HIS messages arrived.

    Every message after it deleted, that one marked unread, and every row
    newer than it removed from the tables that carry a time. Returns what was
    found, including the reply that followed, for the comparison the caller
    wants to print.

    `unread_run` unmarks everything he said in that same breath rather than
    only the last of it: she read the run of them together and answered all
    of them at once, so a rebuilt prompt has to be given all of them. Off by
    default, because the tool that answers one named message again has always
    answered that one."""
    row = con.execute("SELECT id, role, text, ts FROM messages WHERE id=?",
                      (int(message_id),)).fetchone()
    if not row or row[1] != "user":
        return None
    his_ts = float(row[3])
    then = [r[0] for r in con.execute(
        "SELECT text FROM messages WHERE id>? AND role='assistant' ORDER BY id LIMIT 1",
        (int(message_id),))]
    con.execute("DELETE FROM messages WHERE id>?", (int(message_id),))
    if unread_run:
        con.execute("UPDATE messages SET read_ts=NULL WHERE id<=? AND role='user' AND id>"
                    "(SELECT COALESCE(MAX(id), 0) FROM messages WHERE id<=? AND role='assistant')",
                    (int(message_id), int(message_id)))
    else:
        con.execute("UPDATE messages SET read_ts=NULL WHERE id=?", (int(message_id),))
    cut = _cut_tables(con, his_ts)
    con.commit()
    return {"id": int(row[0]), "text": row[2], "ts": his_ts, "then": then, "cut": cut}


def cut_before(con, message_id):
    """Cut an open copy back to the instant before SHE spoke.

    For a message she started herself: there is nothing of his to answer, so
    the moment is her own row and her own row goes too."""
    row = con.execute("SELECT id, role, text, ts FROM messages WHERE id=?",
                      (int(message_id),)).fetchone()
    if not row:
        return None
    ts = float(row[3])
    con.execute("DELETE FROM messages WHERE id>=?", (int(message_id),))
    cut = _cut_tables(con, ts - 0.001)
    con.commit()
    return {"id": int(row[0]), "text": row[2], "ts": ts, "then": [row[2]], "cut": cut}


# ------------------------------------------------------------------ the burst

def answered_message(store, her_msg_id):
    """The message of his that the reply at `her_msg_id` was answering: the
    newest user-role row before it."""
    row = store.message_by_id(int(her_msg_id))
    if not row:
        return None
    with store.lock:
        got = store.conn.execute(
            "SELECT * FROM messages WHERE id<? AND role='user' ORDER BY id DESC LIMIT 1",
            (int(row["id"]),)).fetchone()
    return dict(got) if got else None


# ------------------------------------------------------------- the rebuild

def _no_charge(app, answer="(the assembly only; no model was asked)"):
    """Every model call on this runtime answered from nothing, for free.

    The assembly is what is wanted, not an answer: the array is kept as the
    call goes out (`Persona._draft`), so a stub that returns anything at all
    leaves the same array behind."""
    def call(role, messages, max_tokens=None, _model=None, _provider=None, _json=False):
        return answer

    def call_json(role, messages, max_tokens=None):
        return None, ""
    app.llm.call = call
    app.llm.call_json = call_json
    return app


def rebuild(config_path, db_path, her_msg_id, say=print):
    """The array one old reply would have gone out on, rebuilt.

    `db_path` is read read-only and copied; it is never opened for writing and
    nothing here writes to it. The caller files the result."""
    import tempfile
    from config import Config
    from store import Store
    from world.clock import WorldClock

    cfg = Config(config_path)
    # the same key the delivery files a kept prompt under, and the same one
    # the messenger's adapter registers with
    who = "".join(str(cfg.character.name).lower().split()) or "her"
    tmp = os.path.join(tempfile.gettempdir(), f"scail_rebuild_{who}.db")
    consistent_copy(db_path, tmp)

    probe = Store(tmp)
    her = probe.message_by_id(int(her_msg_id))
    if not her or her["role"] != "assistant":
        probe.conn.close()
        return {"ok": False, "why": f"message {her_msg_id} is not one of hers"}
    # A reply is one row on both characters (`delivery.split_on_blank_lines`
    # is off for both), so the row he tapped is the whole burst and is the
    # anchor the prompt is filed under. A burst of more than one cannot be
    # told apart afterwards from a run of messages she started minutes apart,
    # and guessing wrong would file one prompt against two different replies.
    anchor = int(her["id"])
    sent = str(her["text"] or "")
    started = bool(her.get("self_started"))
    his = None if started else answered_message(probe, anchor)
    probe.conn.close()
    if not started and not his:
        return {"ok": False, "why": f"nothing of his comes before message {her_msg_id}"}

    con = sqlite3.connect(tmp)
    # a message she started herself has no message of his to cut back to, so
    # the moment is her own row and the cut takes that row with it
    cutinfo = cut_before(con, anchor) if started else cut_to(con, int(his["id"]), unread_run=True)
    con.close()
    if not cutinfo:
        return {"ok": False, "why": f"message {(his or her)['id']} could not be cut back to"}
    moment = float(cutinfo["ts"])
    say(f"[rebuild] copy at {tmp}; cut back to "
        f"{'her own message ' + str(anchor) if started else 'his message ' + str(his['id'])}, "
        f"{cutinfo['cut']} later row(s) removed")

    # The clock is set to the minute SHE SPOKE, in her own time -- not to the
    # minute of the message she was answering. The hour in the situation block
    # is then the hour she was in, and, more than that, the history reaches up
    # to the moment: a clock set to his message is a few seconds BEFORE it,
    # and the thread then leaves out the very message being answered.
    when = WorldClock(cfg).to_char(float(her["ts"])).strftime("%Y-%m-%d %H:%M")

    from tools import harness
    app = harness.build_on(tmp, config_path, db_path, copy=False,
                           extra=["--sim", when, "--speed", "1"])
    _no_charge(app)

    # The gauges are a kv row, which carries no time and is not cut, so the
    # copy boots holding today's. The state log does carry a time, and its
    # newest row at his message is what she was feeling.
    _at, was = app.store.gauges_at(moment)
    if was:
        for k, v in was.items():
            if k in app.state.gauges:
                app.state.gauges[k] = v
    scene = app.store.last_scene() or {}
    digests = app.store.recent_digests(1)
    digest = str((digests[0] or {}).get("text", "")) if digests else ""
    unread = app.store.unread_user_messages()
    say(f"[rebuild] her time {when}, scene {str(scene.get('activity', ''))[:60]!r}, "
        f"{len(was or {})} gauge(s) put back, {len(unread)} message(s) of his to answer")

    app.persona.generate(dict(scene), digest, unread)
    kept = dict(getattr(app.persona, "last_reply_prompt", None) or {})
    messages = list(kept.get("messages") or [])
    if not messages:
        return {"ok": False, "why": "the assembly produced no prompt"}
    return {"ok": True, "anchor": anchor, "msg_ids": [anchor],
            "his_id": int(his["id"]) if his else 0, "moment": moment,
            "her_ts": float(her["ts"]), "self_started": started,
            "text": sent, "messages": messages,
            "params": dict(kept.get("params") or {}),
            "model": str(kept.get("model") or ""),
            "char": who, "when": when, "cut": int(cutinfo["cut"]),
            "chars": sum(len(m.get("content") or "") for m in messages)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--message-id", type=int, required=True, help="one of HER messages")
    ap.add_argument("--out", default="", help="write the result here as JSON")
    args = ap.parse_args()
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    os.chdir(ROOT)
    t0 = time.time()
    try:
        got = rebuild(args.config, args.db, args.message_id)
    except Exception as e:
        import traceback
        traceback.print_exc()
        got = {"ok": False, "why": f"{type(e).__name__}: {e}"}
    got["seconds"] = round(time.time() - t0, 1)
    if args.out:
        with io.open(args.out, "w", encoding="utf-8") as f:
            json.dump(got, f, ensure_ascii=False)
    print(f"[rebuild] {'ok' if got.get('ok') else 'no'}: "
          f"{got.get('why') or str(len(got.get('messages') or [])) + ' messages, ' + str(got.get('chars', 0)) + ' chars'}"
          f" in {got['seconds']}s")
    return 0 if got.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
