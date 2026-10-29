"""Answer one of his messages again, on a copy of a save, with the machinery as
it is NOW -- and print what she said then beside what she says today.

    python tools/regen_reply.py --config config_yukarin.json --db data/yukarin.db --message-id 138
    python tools/regen_reply.py ... --anime Mitsudomoe --ep 9     # re-read that episode first

What it does, in order: takes a consistent copy of the save with sqlite's
backup API (a plain file copy of an open database returns a stale image --
HANDOVER); deletes every message after the one named and marks it unread, so
the App on the copy sees exactly what it saw then; builds the whole App on the
copy, console channel, no sensors, so nothing can reach him or the live save;
optionally re-runs the watching module's fetch for one episode synchronously
(the synopsis comes from the recap cache, so no browser), which also makes the
digest; then runs the same reply path `App` runs for an inbound message and
prints the result. Nothing is delivered and the live save is not opened for
writing.

It spends model calls: a director tick, the state role, the digest once, the
persona, and the continuity check on her draft for a character who has that
check (it says so at the top of the run when she has not). Well under a dollar.
"""

import argparse
import io
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# the copy and the cut are `sim/reconstruct.py`, which the runtime's redraw
# also uses when the message he tapped kept no prompt of its own
from sim.reconstruct import consistent_copy, cut_to  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_yukarin.json")
    ap.add_argument("--db", default="data/yukarin.db")
    ap.add_argument("--message-id", type=int, required=True, help="his message to answer again")
    ap.add_argument("--anime", default="", help="re-run the watching fetch for this show first (title as his list spells it)")
    ap.add_argument("--ep", type=int, default=0)
    ap.add_argument("--quiet", action="store_true", help="hide the App's own log lines")
    args = ap.parse_args()

    tmp = os.path.join(tempfile.gettempdir(), "scail_regen.db")
    consistent_copy(args.db, tmp)
    con = sqlite3.connect(tmp)
    # Everything the save learned AFTER his message goes too, or the reply
    # knows the future: a regenerated answer to message 140 once quoted what
    # he said in message 142, because the fact and the event it had become
    # were still in the copy. Tables with a timestamp are cut at his message;
    # kv rows are not (they hold no per-row time) and are the known remainder.
    got = cut_to(con, args.message_id)
    con.close()
    if not got:
        print(f"[regen] message {args.message_id} is not one of his")
        return 1
    then = got["then"]
    print(f"[regen] {got['cut']} row(s) newer than his message removed from the copy (kv is not cut)")
    print(f"[regen] copy at {tmp}; history cut back to message {args.message_id}: {got['text'][:80]!r}")

    import logger
    logger.setup = lambda out_dir: None
    logger.finish = lambda: None
    keep = ("[watching]", "[recap]", "[known]", "[household]", "[director]", "[attention]", "[persona]", "[llm:persona]", "[editor]", "[repeat]", "[voice]", "[context]", "[lore]")
    logger.log = (lambda m, to_console=True: None) if args.quiet else (
        lambda m, to_console=True: print("   " + str(m)[:300]) if any(k in str(m) for k in keep) else None)
    logger.log_llm = lambda *a, **k: None
    logger.write_artifact = lambda *a, **k: None

    import scail
    argv = sys.argv
    sys.argv = ["scail.py", "--console", "--no-sensors", "--config", args.config, "--db", tmp]
    try:
        real = scail.parse_args()
    finally:
        sys.argv = argv
    app = scail.App(real)
    # so a run cannot be read as "the check passed": with the check off there
    # is no [editor] line at all, and that used to look exactly like a gate
    # that declined
    for _role, _why in sorted((app.config.roles_off() or {}).items()):
        print(f"[regen] the {_role} role is never called for this character: {_why}")

    if args.anime and app.watching:
        hit = app.anime_kb.resolve_strict(args.anime) if app.anime_kb else None
        if not hit:
            print(f"[regen] {args.anime!r} is not on his list under that spelling")
            return 1
        print(f"[regen] re-reading {hit[1]} ep{args.ep} (synchronously; synopsis from the cache)")
        app.watching._work({"anime_id": hit[0], "title": hit[1], "ep": args.ep})
    if app.watching:
        it = app.watching.current()
        if it:
            print(f"[regen] the thing in the room: {it.get('ja') or it.get('title')} ep{it.get('ep')}, "
                  f"synopsis {len(it.get('summary') or '')} chars, digest {len(it.get('digest') or '')} chars")
            for line in app.watching.situation_lines(it, ja=getattr(app.persona, 'ja', False)):
                print("   > " + line[:400])
        else:
            print("[regen] nothing he is watching is fresh in this save")

    # what App.run does before any tick: the day boundary and today's plan
    app.ensure_day()
    app.maybe_generate_schedule()
    unread = app.store.unread_user_messages()
    text = "\n".join(m["text"] for m in unread)
    # the loop starts a lookup on an inbound message during her read delay;
    # here it runs and is waited for, so the reply sees what she looked up
    looked = None
    if app.lookup and unread:
        if app.lookup.start(text, unread[-1]["ts"]):
            print("[regen] she is looking something up")
            looked = app.lookup.take()
            if looked:
                print(f"[regen] looked up '{looked['term']}' via {looked['source']}: {looked['gist'][:300]}")
    scene, digest = app.tick(force=True, reading_text=text)
    bubbles, voice = app.persona.generate(scene, digest, unread, looked_up=looked)

    print("\nTHEN, what she sent:")
    for t in then or ["(nothing recorded)"]:
        print("   " + t.replace("\n", "\n   "))
    print("\nNOW, with the machinery as it is:")
    for b in bubbles or ["(nothing)"]:
        print("   " + b.replace("\n", "\n   "))
    if voice:
        print(f"   (aloud: {voice})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
