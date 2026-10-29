"""Replace one of her sent replies with new text -- in her store, on his phone,
and in the voice note -- so the two records agree and the chat shows one
message where it was.

    python tools/replace_reply.py --message-id 141 --text-file new.txt
    python tools/replace_reply.py --message-id 141 --text "..."          # short texts
    python tools/replace_reply.py --message-id 141 --text-file new.txt --no-voice

The usual source of the text is `tools/regen_reply.py`, which answers one of
his messages again on a copy with the machinery as it is now. This puts that
answer where the old one was. Three things happen, through the running bot
and the hub, never by writing to the live save from outside:

  1. `/context msg set <id> <text>` through the hub's ops queue rewrites the
     row in her store (the bot does the write);
  2. `POST /bot/edit` rewrites the same message on the hub, which the app
     shows at once;
  3. if that message carries a voice note, the new text is rendered through
     her own `TTSQueue.render` (same synthesis, same cache, her voice) and
     attached with `POST /bot/voice attach_to`, replacing the old note.

To ADD a message instead, use the ops command `/send <text>`; to remove one,
`/context msg drop <id>` (store and hub). The `[persona]` and `[sent]` log
lines print only the first 80 characters of a message, so read the store,
not the log, when checking what went out.
"""

import argparse
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import types
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_yukarin.json")
    ap.add_argument("--db", default="data/yukarin.db")
    ap.add_argument("--char", default="yukari", help="the character's id at the hub")
    ap.add_argument("--message-id", type=int, required=True, help="her message in the store")
    ap.add_argument("--text", default="")
    ap.add_argument("--text-file", default="")
    ap.add_argument("--no-voice", action="store_true", help="leave the voice note alone")
    ap.add_argument("--voice-only", action="store_true", help="re-render the voice note for the text as it stands; change nothing else")
    args = ap.parse_args()
    new = io.open(args.text_file, encoding="utf-8").read().strip() if args.text_file else args.text.strip()
    if args.voice_only:
        con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        got = con.execute("SELECT text FROM messages WHERE id=?", (args.message_id,)).fetchone()
        con.close()
        new = (got[0] if got else "").strip()
    if not new:
        print("[replace] no text")
        return 1

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    row = con.execute("SELECT id, role, tg_id, text FROM messages WHERE id=?", (args.message_id,)).fetchone()
    con.close()
    if not row or row[1] != "assistant" or not row[2]:
        print(f"[replace] message {args.message_id} is not one of hers with a hub id")
        return 1
    hub_id = int(row[2])
    print(f"[replace] store {args.message_id} / hub {hub_id}\n   was: {row[3][:80]!r}\n   now: {new[:80]!r}")

    hub = json.load(io.open("config.json", encoding="utf-8"))["talkapp"]

    def post(path, body):
        req = urllib.request.Request(f"http://127.0.0.1:{hub['port']}{path}", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-Key": hub["token"]}, method="POST")
        return json.loads(urllib.request.urlopen(req, timeout=20).read().decode())

    if not args.voice_only:
        print("   store:", post("/ops/cmd", {"char": args.char, "text": f"/context msg set {args.message_id} {new}"}))
        print("   hub:  ", post("/bot/edit", {"char": args.char, "id": hub_id, "text": new}))

    h = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{hub['port']}/history?char={args.char}&key={hub['token']}", timeout=10).read().decode())
    items = h if isinstance(h, list) else (h.get("log") or h.get("items") or h.get("messages"))
    m = next((x for x in items if x["id"] == hub_id), None)
    if m and (m.get("voice") or args.voice_only) and not args.no_voice:
        import logger
        logger.setup = lambda d: None
        logger.log = lambda *a, **k: None
        from config import Config
        from channels.tts_handler import TTSQueue
        tmp = os.path.join(tempfile.gettempdir(), "replace_reply_cfg.json")
        shutil.copy(args.config, tmp)         # Config rewrites the file it is given
        tts = TTSQueue(Config(tmp), types.SimpleNamespace(send_voice=lambda *a, **k: True))
        path = tts.render(new)
        if path:
            print("   voice:", post("/bot/voice", {"char": args.char, "path": os.path.abspath(path), "attach_to": hub_id}))
        else:
            print("   voice: could not render; the old note stays")

    time.sleep(6)
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    got = con.execute("SELECT text FROM messages WHERE id=?", (args.message_id,)).fetchone()
    con.close()
    print("   store now matches:" , bool(got and got[0].strip() == new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
