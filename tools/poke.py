"""Fire a slash command at a RUNNING bot from the terminal, and watch it land.

    python tools/poke.py yukari /idle --wait 30
    python tools/poke.py tomoe /reply again --wait 60
    python tools/poke.py yukari "/selfstart she is bored of waiting" --wait 60
    python tools/poke.py help

The command goes on the hub's ops queue exactly as the app's ops bar puts it
there (`POST /ops/cmd`, the token out of `config.json`), and the bot picks it
up on its next pass, runs it and posts the answer back. Nothing here opens a
save, builds an App or spends a model call: the running bot does all of it.

`--wait N` follows the character's newest run directory `session.log` for up
to N seconds and prints every line the bot writes after the command was
queued, so what the tick decided is visible in the terminal, and prints the
command's own answer when the bot posts it to the hub.

The character is the id the hub registers: `tomoe` or `yukari`. The leading
slash is optional and is added if it is missing, which is what to do in Git
Bash: that shell rewrites a bare `/idle` into a Windows path before python
ever sees it, and `poke.py yukari idle` gets there intact.
"""
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import requests  # noqa: E402

FORCING = [
    ("/idle", "one ordinary loop pass now: the director tick and everything that reads "
              "the scene it wrote. Costs a tick and a gauge read; delivers nothing"),
    ("/reply [again]", "answer his newest unread message now instead of when her plan says. "
                       "`again` puts his newest message back to unread and answers it a second "
                       "time. SHE REALLY SENDS IT"),
    ("/selfstart [why]", "make her write first now, past the gate that would have held her, "
                         "with an optional reason she is handed. SHE REALLY SENDS IT"),
]
EXISTING = [
    ("/tick", "force a director tick and nothing else"),
    ("/look", "make her take in his machine now (eats the feed, moves her)"),
    ("/impulse", "would she text him now, and why not -- a report, it sends nothing"),
    ("/send <text>", "deliver a text as her, through her own delivery and store"),
]


def usage():
    print(__doc__.strip())
    print("\nforcing what normally waits on her clock:")
    for cmd, what in FORCING:
        print(f"  {cmd:<20} {what}")
    print("\nthe ones that were already there:")
    for cmd, what in EXISTING:
        print(f"  {cmd:<20} {what}")
    print("\n  /help                any bot command; the bot answers with its own list")


def hub_config():
    with io.open(os.path.join(ROOT, "config.json"), encoding="utf-8") as fh:
        c = json.load(fh)
    t = c.get("talkapp", {})
    host = t.get("host") or "127.0.0.1"
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    return f"http://{host}:{int(t.get('port') or 8765)}", str(t.get("token") or "")


def run_dir_of(char):
    """The newest run directory whose bot registered as `char` with the hub.

    A run leaves an ACTIVE file while it is alive; one with the marker wins
    over one without, so a finished run of hers is not tailed while the live
    one is up."""
    base = os.path.join(ROOT, "logs")
    best = None
    for name in os.listdir(base):
        d = os.path.join(base, name)
        log = os.path.join(d, "session.log")
        if not os.path.isdir(d) or not os.path.exists(log):
            continue
        try:
            with io.open(log, encoding="utf-8", errors="replace") as fh:
                head = fh.read(20000)
        except OSError:
            continue
        if f"registered '{char}'" not in head:
            continue
        key = (os.path.exists(os.path.join(d, "ACTIVE")), os.path.getmtime(log))
        if best is None or key > best[0]:
            best = (key, log)
    return best[1] if best else ""


def main(argv):
    args = [a for a in argv[1:] if a]
    if not args or args[0] in ("help", "-h", "--help", "/?"):
        usage()
        return 0
    wait = 0.0
    if "--wait" in args:
        i = args.index("--wait")
        try:
            wait = float(args[i + 1])
        except (IndexError, ValueError):
            print("--wait takes a number of seconds")
            return 2
        del args[i:i + 2]
    char = args[0]
    rest = args[1:]
    if not rest or rest[0] in ("help", "-h", "--help"):
        usage()
        return 0
    text = " ".join(rest).strip()
    if not text.startswith("/"):
        text = "/" + text

    url, token = hub_config()
    if not token:
        print("no talkapp.token in config.json; the hub refuses an unkeyed call")
        return 2
    headers = {"X-Key": token}
    try:
        chars = requests.get(url + "/health", timeout=5).json().get("chars", [])
    except Exception as e:
        print(f"the hub at {url} did not answer ({type(e).__name__}); is talkapp.cmd running?")
        return 2
    if char not in chars:
        print(f"the hub knows {', '.join(chars) or 'nobody'}, not '{char}'")
        return 2

    log_path = run_dir_of(char)
    tail_from = os.path.getsize(log_path) if log_path else 0
    try:
        seen = len(requests.get(url + "/ops", params={"char": char}, headers=headers,
                                timeout=5).json().get("log", []))
    except Exception:
        seen = 0

    r = requests.post(url + "/ops/cmd", json={"char": char, "text": text},
                      headers=headers, timeout=10)
    if r.status_code != 200:
        print(f"the hub refused the command: HTTP {r.status_code}")
        return 2
    print(f"[poke] queued for {char}: {text}"
          + (f"  (waiting up to {wait:.0f}s)" if wait else "  (not waiting; --wait N to watch)"))
    if not wait:
        return 0
    if not log_path:
        print(f"[poke] no run directory found for {char}; only the hub's answer will show")
    else:
        print(f"[poke] following {os.path.relpath(log_path, ROOT)}")

    # The bot answers on its next pass, which is one poll interval away, and
    # what it does then goes into the log line by line. Both are followed:
    # the log says what happened, the hub's ops log says what the command
    # itself answered.
    deadline = time.time() + wait
    answered_at = 0.0
    while time.time() < deadline:
        if log_path:
            try:
                size = os.path.getsize(log_path)
                if size > tail_from:
                    with io.open(log_path, encoding="utf-8", errors="replace") as fh:
                        fh.seek(tail_from)
                        chunk = fh.read()
                    tail_from = size
                    for line in chunk.splitlines():
                        if line.strip():
                            print("   " + line.rstrip())
            except OSError:
                pass
        if not answered_at:
            try:
                rows = requests.get(url + "/ops", params={"char": char}, headers=headers,
                                    timeout=5).json().get("log", [])
            except Exception:
                rows = []
            for row in rows[seen:]:
                if row.get("cmd", "").strip() == text:
                    print("[poke] the bot answers:")
                    print("   " + str(row.get("text", "")).replace("\n", "\n   "))
                    answered_at = time.time()
                    break
        # the answer comes back before her bubbles are typed out, so the tail
        # runs on for a few seconds past it rather than stopping on it
        if answered_at and time.time() - answered_at > 6:
            break
        time.sleep(0.5)
    if not answered_at:
        print(f"[poke] no answer inside {wait:.0f}s. The bot picks the queue up on its next pass; "
              "check that its process is up.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
