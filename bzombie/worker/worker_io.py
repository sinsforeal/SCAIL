"""Queue helper for the bench worker session. Stdlib only. Queue folder: $BZ_VAR/claude_queue (default
H:\\SCAIL\\bzombie\\var\\claude_queue). Commands:
  list                      pending requests, oldest first (one line each: id, task, model, chars); refreshes worker.json
  show <req_id>             the full agent prompt for that request: system text, blank line, prompt text, answer-only line
  model <req_id>            the request's model (default sonnet)
  answer <req_id> [--error MSG] [--model M]
                            reads claude_queue/<req_id>.ans.txt (the reply, via the Write tool), writes
                            <req_id>.ans.json atomically (tmp then rename), moves the .txt to done/, refreshes worker.json
  beat [--label L]          refresh worker.json
  watch [--label L]         for a Monitor: prints "REQ <id>" once per new request, refreshes worker.json every 30 s
The worker never edits anything else in the queue folder.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

Q = Path(os.environ.get("BZ_VAR", r"H:\SCAIL\bzombie\var")) / "claude_queue"
TAIL = "Answer with the reply text only. Use no tools."


def _replace(src, dst):
    """os.replace that waits out Windows sharing violations (the harness may be reading dst)."""
    for n in range(40):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if n == 39:
                raise
            time.sleep(0.05)


def beat(label="bench-worker"):
    Q.mkdir(parents=True, exist_ok=True)
    tmp = Q / "worker.tmp"
    tmp.write_text(json.dumps({"pid": os.getppid(), "session_label": label, "last_seen_wall": time.time()}),
                   encoding="utf-8")
    _replace(tmp, Q / "worker.json")


def pending():
    out = []
    for p in Q.glob("*.req.json"):
        rid = p.name[:-len(".req.json")]
        if (Q / f"{rid}.ans.json").exists():
            continue
        try:
            out.append((p.stat().st_mtime, rid, json.loads(p.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda x: x[0])


def load(rid):
    return json.loads((Q / f"{rid}.req.json").read_text(encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("list", "beat", "watch"):
        sp = sub.add_parser(n)
        sp.add_argument("--label", default="bench-worker")
    for n in ("show", "model", "answer"):
        sp = sub.add_parser(n)
        sp.add_argument("req_id")
        if n == "answer":
            sp.add_argument("--error", default=None)
            sp.add_argument("--model", default="sonnet")
    a = ap.parse_args(argv)
    if a.cmd == "beat":
        beat(a.label)
    elif a.cmd == "list":
        beat(a.label)
        for _, rid, r in pending():
            print(f"{rid} {r.get('task')} {r.get('model', 'sonnet')} {len(r.get('system', '')) + len(r.get('prompt', ''))}")
    elif a.cmd == "show":
        r = load(a.req_id)
        sys.stdout.reconfigure(encoding="utf-8")
        print(f"{r.get('system', '')}\n\n{r.get('prompt', '')}\n\n{TAIL}")
    elif a.cmd == "model":
        print(load(a.req_id).get("model") or "sonnet")
    elif a.cmd == "answer":
        txt = Q / f"{a.req_id}.ans.txt"
        text = txt.read_text(encoding="utf-8") if txt.exists() else ""
        err = a.error or (None if text.strip() else "empty answer")
        tmp = Q / f"{a.req_id}.ans.tmp"
        tmp.write_text(json.dumps({"req_id": a.req_id, "text": text.strip() if not a.error else "",
                                   "is_error": bool(err), "error": err, "answered_wall": time.time(),
                                   "agent_model": a.model}, ensure_ascii=False), encoding="utf-8")
        _replace(tmp, Q / f"{a.req_id}.ans.json")
        if txt.exists():  # keep the raw reply next to the answer the harness will move
            (Q / "done").mkdir(parents=True, exist_ok=True)
            _replace(txt, Q / "done" / txt.name)
        beat()
    elif a.cmd == "watch":
        sys.stdout.reconfigure(line_buffering=True)
        seen, last = set(), 0.0
        while True:
            for _, rid, _r in pending():
                if rid not in seen:
                    seen.add(rid)
                    print(f"REQ {rid}")
            if time.time() - last > 30:
                beat(a.label)
                last = time.time()
            time.sleep(1)


if __name__ == "__main__":
    main()
