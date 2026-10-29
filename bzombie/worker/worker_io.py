"""Queue helper for the bench worker session. Stdlib only. Queue folder: $BZ_VAR/claude_queue (default
H:\\SCAIL\\bzombie\\var\\claude_queue). Commands:
  list                      pending requests, oldest first (one line each: id, task, model, chars; "skipped" marker);
                            then GONE lines for requests withdrawn in the last 15 min; refreshes worker.json
  show <req_id>             the full agent prompt for that request: system text, blank line, prompt text, answer-only line.
                            A request that is gone prints one GONE line (reason, who, age from the tombstone) and exits 2
  prompt-file <req_id>      writes the same prompt `show` prints to <queue>/<req_id>.prompt.txt (UTF-8) and prints only its
                            absolute path, so the worker never holds the prompt in its own context. Gone: same GONE line,
                            exit 2. answer and skip remove the .prompt.txt; list removes orphans whose request is gone
  model <req_id>            the request's model (default sonnet); GONE line and exit 2 when the request is gone
  answer <req_id> [--error MSG] [--model M]
                            reads claude_queue/<req_id>.ans.txt (the reply, via the Write tool), writes
                            <req_id>.ans.json atomically (tmp then rename), moves the .txt to done/, refreshes worker.json
  skip <req_id>             leave a request queued on purpose (pool says no new agents): watch stops waking for it
  beat [--label L]          refresh worker.json
  watch [--label L] [--beat-s 30] [--poll-s 1]
                            for `run_in_background` (no timeout): beats worker.json every --beat-s by itself and exits
                            0 after printing "REQ <id>" for every pending, not skipped request as soon as one exists.
                            Also exits 0 with "STOP" on SIGINT/SIGTERM/SIGBREAK or when claude_queue/worker.stop exists
                            (the file is removed). Never exits on its own otherwise. Starts no child process.
  stop                      create claude_queue/worker.stop so a running watch exits
The worker never edits anything else in the queue folder. Tombstones the harness leaves are in claude_queue/_gone/.
"""
import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

Q = Path(os.environ.get("BZ_VAR", r"H:\SCAIL\bzombie\var")) / "claude_queue"
TAIL = "Answer with the reply text only. Use no tools."
GONE_RECENT_S = 900  # list reports tombstones this young (answered ones never)


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


def _skipped():
    try:
        return set(json.loads((Q / "worker.skip.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _save_skipped(ids):
    tmp = Q / "worker.skip.tmp"
    tmp.write_text(json.dumps(sorted(ids)), encoding="utf-8")
    _replace(tmp, Q / "worker.skip.json")


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


def prompt_text(r):
    return f"{r.get('system', '')}\n\n{r.get('prompt', '')}\n\n{TAIL}"


def drop_prompt_file(rid):
    try:
        (Q / f"{rid}.prompt.txt").unlink()
    except OSError:
        pass


def tombstone(rid):
    try:
        return json.loads((Q / "_gone" / f"{rid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def gone_line(rid, t=None):
    """One line saying why a request is not in the queue: from its tombstone, else from done/, else 'nobody recorded'."""
    t = t or tombstone(rid)
    if t:
        at = time.strftime("%H:%M:%S", time.localtime(t.get("gone_wall", 0)))
        line = (f"GONE {rid} {t.get('reason')} by {t.get('who')} after {t.get('age_s')} s at {at} "
                f"run={t.get('run_id')} task={t.get('task')}")
        return line + (f" ({t['detail']})" if t.get("detail") else "")
    moved = sorted(p.name for p in (Q / "done").glob(f"{rid}.*"))
    if moved:
        return f"GONE {rid} moved to done/: {', '.join(moved)} (no tombstone)"
    return f"GONE {rid} no request file and no tombstone: nothing recorded why (deleted by something other than the harness)"


def recent_gone():
    out = []
    for p in (Q / "_gone").glob("*.json"):
        try:
            t = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if t.get("reason") != "answered" and time.time() - float(t.get("gone_wall", 0)) < GONE_RECENT_S:
            out.append((t.get("gone_wall", 0), t.get("req_id") or p.stem, t))
    return [gone_line(rid, t) for _, rid, t in sorted(out, key=lambda x: x[0])]


def watch(label="bench-worker", beat_s=30.0, poll_s=1.0, out=None, stop=None):
    """Beat worker.json on its own and return the list of new request ids as soon as one exists ([] on stop).
    `stop` is a threading.Event-like object (tests, signal handler); worker.stop in the queue folder also stops it."""
    out = out or (lambda s: print(s, flush=True))
    last = 0.0
    while True:
        if stop is not None and stop.is_set():
            out("STOP")
            return []
        if (Q / "worker.stop").exists():
            try:
                (Q / "worker.stop").unlink()
            except OSError:
                pass
            out("STOP")
            return []
        if time.time() - last >= beat_s:
            try:
                beat(label)
            except OSError:
                pass  # a sharing violation must not end the heartbeat; the next beat retries
            last = time.time()
        skip = _skipped()
        ids = [rid for _, rid, _r in pending() if rid not in skip]
        if ids:
            for rid in ids:
                out(f"REQ {rid}")
            return ids
        time.sleep(poll_s)


class _Flag:
    def __init__(self):
        self._v = False

    def set(self):
        self._v = True

    def is_set(self):
        return self._v


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("list", "beat", "watch"):
        sp = sub.add_parser(n)
        sp.add_argument("--label", default="bench-worker")
        if n == "watch":
            sp.add_argument("--beat-s", type=float, default=30.0)
            sp.add_argument("--poll-s", type=float, default=1.0)
    sub.add_parser("stop")
    for n in ("show", "prompt-file", "model", "answer", "skip"):
        sp = sub.add_parser(n)
        sp.add_argument("req_id")
        if n == "answer":
            sp.add_argument("--error", default=None)
            sp.add_argument("--model", default="sonnet")
    a = ap.parse_args(argv)
    if a.cmd == "beat":
        beat(a.label)
    elif a.cmd == "stop":
        Q.mkdir(parents=True, exist_ok=True)
        (Q / "worker.stop").write_text("stop", encoding="utf-8")
    elif a.cmd == "skip":
        _save_skipped(_skipped() | {a.req_id})
        drop_prompt_file(a.req_id)
    elif a.cmd == "list":
        beat(a.label)
        skip = _skipped()
        live = pending()
        if skip - {rid for _, rid, _r in live}:  # forget skips whose request is gone
            _save_skipped(skip & {rid for _, rid, _r in live})
        live_ids = {rid for _, rid, _r in live}
        for p in Q.glob("*.prompt.txt"):  # orphans: the harness withdrew or timed out the request
            if p.name[:-len(".prompt.txt")] not in live_ids:
                drop_prompt_file(p.name[:-len(".prompt.txt")])
        for _, rid, r in live:
            print(f"{rid} {r.get('task')} {r.get('model', 'sonnet')} {len(r.get('system', '')) + len(r.get('prompt', ''))}"
                  + (" skipped" if rid in skip else ""))
        for line in recent_gone():
            print(line)
    elif a.cmd in ("show", "prompt-file", "model"):
        try:
            r = load(a.req_id)
        except (OSError, ValueError):
            drop_prompt_file(a.req_id)
            print(gone_line(a.req_id))
            sys.exit(2)
        if a.cmd == "show":
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(prompt_text(r))
        elif a.cmd == "prompt-file":
            pf = Q / f"{a.req_id}.prompt.txt"
            tmp = Q / f"{a.req_id}.prompt.tmp"
            tmp.write_bytes((prompt_text(r) + "\n").encode("utf-8"))  # same bytes `show` prints
            _replace(tmp, pf)
            print(pf.resolve())
        else:
            print(r.get("model") or "sonnet")
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
        if a.req_id in _skipped():
            _save_skipped(_skipped() - {a.req_id})
        drop_prompt_file(a.req_id)
        beat()
    elif a.cmd == "watch":
        stop = _Flag()
        for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), lambda *_: stop.set())
        watch(a.label, a.beat_s, a.poll_s, stop=stop)


if __name__ == "__main__":
    main()
