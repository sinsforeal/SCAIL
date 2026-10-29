"""B-zombie gateway: OpenAI-compatible proxy in front of Surplus.

Port 18330, 127.0.0.1 only. Spec: bzombie/CONTRACT.md (Gateway).
Path: /arm/<S|P|X>/<run_id>/v1/{chat/completions,embeddings,models}; GET /status; POST /shutdown.

Standard library only, plus torch and sentence_transformers for embeddings
(loaded on the first embeddings call, GPU if there, else CPU).

Arm X only (harness-side calls such as the model check) may pick the model
and language per call with the headers x-bz-model and x-bz-lang, because one
modelcheck run covers both models and both languages. S and P always get the
run's config.json values.
"""
import argparse
import http.client
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import policy  # noqa: E402

DEFAULT_VAR = r"H:\SCAIL\bzombie\var"
DEFAULT_KEY = r"F:\REPS2\SCAILV4\secerts\surplus.txt"
DEFAULT_UPSTREAM = "https://api.surplusintelligence.ai/v1"
PORT = 18330
EMBED_MODEL = "intfloat/multilingual-e5-small"
RETRIES = 5
HEDGE_AFTER_S = 60.0  # no response byte after this long: start a second identical try (env BZ_HEDGE_AFTER_S, 0 = off)


class LocalEmbedder:
    """multilingual-e5-small, loaded on first use. Normalised vectors, dim 384."""

    def __init__(self, name=EMBED_MODEL):
        self.name = name
        self.device = None
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is not None:
                return
            import torch
            from sentence_transformers import SentenceTransformer
            dev = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = SentenceTransformer(self.name, device=dev)
            self.device = dev

    def encode(self, texts, prefix="passage: "):
        self._load()
        vecs = self._model.encode([prefix + t for t in texts], normalize_embeddings=True,
                                  batch_size=32, show_progress_bar=False)
        return [[float(x) for x in v] for v in vecs]


class Run:
    def __init__(self, run_id):
        self.run_id = run_id
        self.spent_micro = 0
        self.calls = 0
        self.errors = 0
        self.arms = {}  # arm -> {"calls", "cost_micro", "errors"}
        self.cap_events = 0
        self.loaded = False

    def add(self, arm, cost, err):
        a = self.arms.setdefault(arm, {"calls": 0, "cost_micro": 0, "errors": 0})
        a["calls"] += 1
        a["cost_micro"] += cost
        self.calls += 1
        self.spent_micro += cost
        if err:
            a["errors"] += 1
            self.errors += 1


class Gateway:
    def __init__(self, var_dir=DEFAULT_VAR, key_file=DEFAULT_KEY, upstream=DEFAULT_UPSTREAM,
                 embedder=None, backoff=1.0, hedge_after_s=None):
        if hedge_after_s is None:
            try:
                hedge_after_s = float(os.environ.get("BZ_HEDGE_AFTER_S", HEDGE_AFTER_S))
            except ValueError:
                hedge_after_s = HEDGE_AFTER_S
        self.hedge_after_s = hedge_after_s  # 0 disables
        self.var_dir = var_dir
        self.runs_dir = os.path.join(var_dir, "runs")
        self.key_file = key_file
        self.upstream = upstream.rstrip("/")
        self.embedder = embedder or LocalEmbedder()
        self.backoff = backoff
        self.lock = threading.Lock()
        self.runs = {}
        self.started = time.time()
        self._balance = (0.0, None)
        self._key = None

    # ---- small helpers
    def key(self):
        if self._key is None:
            with open(self.key_file, "r", encoding="utf-8") as f:
                self._key = f.read().strip()
        return self._key

    def run_dir(self, run_id):
        return os.path.join(self.runs_dir, run_id)

    def read_config(self, run_id):
        p = os.path.join(self.run_dir(run_id), "config.json")
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def virtual_ts(self, run_id):
        p = os.path.join(self.run_dir(run_id), "clock.json")
        try:
            with open(p, "r", encoding="utf-8") as f:
                c = json.load(f)
        except (OSError, ValueError):
            return None
        if isinstance(c, dict):
            for k in ("virtual_ts", "now", "ts", "virtual_now", "time", "clock"):
                if k in c:
                    return c[k]
            return c
        return c

    def run(self, run_id):
        """Run totals, rebuilt from calls.jsonl the first time a run is seen."""
        with self.lock:
            r = self.runs.get(run_id)
            if r is None:
                r = self.runs[run_id] = Run(run_id)
            if not r.loaded:
                r.loaded = True
                p = os.path.join(self.run_dir(run_id), "calls.jsonl")
                if os.path.exists(p):
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                d = json.loads(line)
                            except ValueError:
                                continue
                            r.add(d.get("arm", "?"), int(d.get("cost_micro") or 0), bool(d.get("error")))
            return r

    def log_call(self, rec):
        run_id = rec["run_id"]
        d = self.run_dir(run_id)
        os.makedirs(d, exist_ok=True)
        r = self.run(run_id)
        line = json.dumps(rec, ensure_ascii=False) + "\n"
        with self.lock:
            with open(os.path.join(d, "calls.jsonl"), "a", encoding="utf-8") as f:
                f.write(line)
            r.add(rec["arm"], int(rec.get("cost_micro") or 0), bool(rec.get("error")))

    # ---- upstream
    def _conn(self, timeout=600):
        u = urlparse(self.upstream)
        cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
        return cls(u.hostname, u.port, timeout=timeout), u.path

    def _attempt(self, method, path, data, headers, timeout):
        """One upstream try: request, headers, and the first body byte. Returns (conn, resp).
        Raises OSError/HTTPException (conn closed). peek(1) blocks until the first response byte
        (non-stream: start of the body; stream: first chunk) without consuming it."""
        conn = None
        try:
            conn, base = self._conn(timeout)
            conn.request(method, base + path, body=data, headers=headers)
            resp = conn.getresponse()
            resp.peek(1)
            return conn, resp
        except BaseException:
            if conn:
                conn.close()
            raise

    def _hedged_round(self, method, path, data, headers, timeout, info):
        """One attempt round with a hedge. The first try runs in a thread; if it has produced no
        response byte after hedge_after_s, an identical second try starts in parallel (at most one).
        First to deliver wins, the other is abandoned: its connection is closed when it ends or at once.
        Fills info["hedged"] and info["hedge_won"] ("first"/"second"). Returns (conn, resp) or raises."""
        import queue
        q = queue.Queue()
        lock = threading.Lock()
        state = {"done": False, "conns": {}}

        def run(tag):
            try:
                conn, resp = self._attempt(method, path, data, headers, timeout)
            except (OSError, http.client.HTTPException) as e:
                q.put((tag, None, None, e))
                return
            with lock:
                if state["done"]:
                    conn.close()  # lost the race: abandon
                    return
            q.put((tag, conn, resp, None))

        def start(tag):
            threading.Thread(target=run, args=(tag,), daemon=True).start()

        start("first")
        pending = 1
        hedge_wait = self.hedge_after_s
        last_exc = None
        while pending:
            try:
                tag, conn, resp, exc = q.get(timeout=hedge_wait)
            except queue.Empty:
                # no response byte yet: hedge once, then wait for whichever delivers
                hedge_wait = None
                info["hedged"] = True
                start("second")
                pending += 1
                continue
            pending -= 1
            if exc is not None:
                last_exc = exc
                continue
            with lock:
                state["done"] = True
            if info.get("hedged"):
                info["hedge_won"] = tag
            # a loser that delivered at the same moment is sitting in the queue: close it
            while True:
                try:
                    _t, c2, _r, _e = q.get_nowait()
                except queue.Empty:
                    break
                if c2:
                    c2.close()
            return conn, resp
        with lock:
            state["done"] = True
        raise last_exc or OSError("hedged round failed")

    def open_upstream(self, method, path, body=None, info=None):
        """Open an upstream response with retries. Returns (conn, resp, retries) or raises OSError.
        429 and 5xx-transient are retried; the final non-ok response is returned as is.
        Hedge: POSTs with hedge_after_s > 0 run each try through _hedged_round; `info` (dict) receives
        hedged / hedge_won of the last round."""
        if info is None:
            info = {}
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"Authorization": "Bearer " + self.key(), "Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        last_exc = None
        # Surplus hangs ~2% of non-stream calls until the socket timeout (cl1 runs 10-22: 10 of 550 P calls and
        # 3 of 26 sim-him calls sat 600 s, then the retry answered in seconds). The timeout is per socket read:
        # stream = longest gap between chunks; non-stream = the whole answer (8192 tokens is well under 200 s).
        timeout = 120 if (body or {}).get("stream") else 240
        hedge = method == "POST" and self.hedge_after_s > 0
        for attempt in range(RETRIES + 1):
            conn = None
            info.clear()
            try:
                if hedge:
                    conn, resp = self._hedged_round(method, path, data, headers, timeout, info)
                else:
                    conn, base = self._conn(timeout)
                    conn.request(method, base + path, body=data, headers=headers)
                    resp = conn.getresponse()
                if resp.status in (429, 502, 503, 504) and attempt < RETRIES:
                    ra = resp.getheader("Retry-After")
                    resp.read()
                    conn.close()
                    try:
                        wait = min(float(ra), 30.0) if ra else None
                    except ValueError:
                        wait = None
                    if wait is None:
                        wait = self.backoff * (2 ** attempt)
                    time.sleep(wait)
                    continue
                return conn, resp, attempt
            except (OSError, http.client.HTTPException) as e:
                last_exc = e
                if conn:
                    conn.close()
                if attempt < RETRIES:
                    time.sleep(self.backoff * (2 ** attempt))
                    continue
        raise OSError("upstream unreachable: %s" % type(last_exc).__name__)

    def balance(self):
        now = time.time()
        if now - self._balance[0] < 60 and self._balance[1] is not None:
            return self._balance[1]
        try:
            conn, resp, _ = self.open_upstream("GET", "/payments/balance")
            raw = resp.read()
            conn.close()
            val = json.loads(raw.decode("utf-8")) if resp.status == 200 else {"error": resp.status}
        except Exception as e:  # noqa: BLE001
            val = {"error": type(e).__name__}
        self._balance = (now, val)
        return val

    def status(self):
        for name in (os.listdir(self.runs_dir) if os.path.isdir(self.runs_dir) else []):
            if os.path.exists(os.path.join(self.runs_dir, name, "calls.jsonl")):
                self.run(name)
        out = {"uptime_s": round(time.time() - self.started), "embed_model": self.embedder.name
               if hasattr(self.embedder, "name") else None,
               "embed_device": getattr(self.embedder, "device", None), "runs": {}}
        with self.lock:
            runs = list(self.runs.values())
        for r in runs:
            cfg = self.read_config(r.run_id) or {}
            out["runs"][r.run_id] = {
                "spent_micro": r.spent_micro, "spent_usd": r.spent_micro / 1e6,
                "cap_usd": cfg.get("cap_usd"), "calls": r.calls, "errors": r.errors,
                "cap_events": r.cap_events, "arms": r.arms, "model": cfg.get("model"),
            }
        out["balance"] = self.balance()
        return out


def make_handler(gw):
    class H(BaseHTTPRequestHandler):
        server_version = "bzgateway/1"

        def log_message(self, fmt, *args):  # no per-request stderr noise
            pass

        # ---- output helpers
        def send_json(self, status, obj, call_id=None):
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            if call_id:
                self.send_header("x-bz-call-id", call_id)
            self.end_headers()
            self.wfile.write(raw)

        def err(self, status, etype, msg, call_id=None):
            self.send_json(status, {"error": {"type": etype, "message": msg}}, call_id)

        # ---- routing
        def parse(self):
            parts = [p for p in urlparse(self.path).path.split("/") if p]
            if len(parts) >= 5 and parts[0] == "arm" and parts[3] == "v1":
                return parts[1], parts[2], "/".join(parts[4:])
            return None

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/status":
                return self.send_json(200, gw.status())
            r = self.parse()
            if r and r[2] == "models":
                arm, run_id, _ = r
                cfg = gw.read_config(run_id)
                model = (cfg or {}).get("model") or policy.DEEPSEEK
                return self.send_json(200, {"object": "list", "data": [
                    {"id": model, "object": "model", "owned_by": "surplus"}]})
            self.err(404, "not_found", "no such path")

        def do_POST(self):
            if urlparse(self.path).path == "/shutdown":
                self.send_json(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            r = self.parse()
            if not r:
                return self.err(404, "not_found", "no such path")
            arm, run_id, ep = r
            if arm not in ("S", "P", "X") or "/" in run_id or run_id in (".", ".."):
                return self.err(400, "bad_path", "arm must be S, P or X")
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
            except ValueError:
                return self.err(400, "bad_json", "request body is not JSON")
            if ep == "chat/completions":
                return self.chat(arm, run_id, body)
            if ep == "embeddings":
                return self.embeddings(arm, run_id, body)
            self.err(404, "not_found", "no such endpoint")

        # ---- embeddings
        def embeddings(self, arm, run_id, body):
            call_id = str(uuid.uuid4())
            t0 = time.time()
            inp = body.get("input")
            texts = [inp] if isinstance(inp, str) else inp
            rec = {"call_id": call_id, "arm": arm, "run_id": run_id, "wall_ts": datetime.now().isoformat(),
                   "virtual_ts": gw.virtual_ts(run_id), "endpoint": "embeddings",
                   "model": gw.embedder.name if hasattr(gw.embedder, "name") else "local",
                   "request": {k: v for k, v in body.items() if k != "input"} | {"n_inputs": len(texts or [])},
                   "response": None, "usage": {}, "cost_micro": 0, "latency_s": 0, "error": None}
            if not isinstance(texts, list) or not texts or not all(isinstance(t, str) for t in texts):
                rec["error"] = "bad_input"
                gw.log_call(rec)
                return self.err(400, "invalid_request_error", "input must be a string or list of strings", call_id)
            prefix = "query: " if body.get("input_type") == "query" else "passage: "
            try:
                vecs = gw.embedder.encode(texts, prefix)
            except Exception as e:  # noqa: BLE001
                rec["error"] = "embed_failed: %s" % type(e).__name__
                gw.log_call(rec)
                return self.err(500, "server_error", "embedding failed", call_id)
            resp = {"object": "list", "model": body.get("model") or "multilingual-e5-small",
                    "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vecs)],
                    "usage": {"prompt_tokens": 0, "total_tokens": 0}}
            rec["response"] = {"n_vectors": len(vecs), "dim": len(vecs[0]) if vecs else 0}
            rec["latency_s"] = round(time.time() - t0, 3)
            gw.log_call(rec)
            self.send_json(200, resp, call_id)

        # ---- chat
        def chat(self, arm, run_id, body):
            call_id = str(uuid.uuid4())
            t0 = time.time()
            cfg = gw.read_config(run_id)
            if cfg is None:
                return self.err(404, "run_not_found", "no config.json for run " + run_id, call_id)
            model = cfg.get("model")
            lang = cfg.get("lang")
            if arm == "X":
                model = self.headers.get("x-bz-model") or model
                lang = self.headers.get("x-bz-lang") or lang
            if model not in policy.MODELS:
                return self.err(400, "bad_run_config", "run model must be one of %s" % (policy.MODELS,), call_id)
            run = gw.run(run_id)
            cap = cfg.get("cap_usd")
            sent = policy.apply_policy(body, model, lang)
            # trailing assistant message (prefill): Surplus starts a fresh turn and leaks template junk
            folded, fold_variant = policy.fold_prefill(sent.get("messages"))
            if fold_variant:
                sent["messages"] = folded
            stream = bool(sent.get("stream"))
            want_usage = bool((body.get("stream_options") or {}).get("include_usage"))
            rec = {"call_id": call_id, "arm": arm, "run_id": run_id, "wall_ts": datetime.now().isoformat(),
                   "virtual_ts": gw.virtual_ts(run_id), "endpoint": "chat/completions", "model": model,
                   "lang": lang, "request": body, "request_sent": sent, "response": None, "usage": None,
                   "cost_micro": 0, "latency_s": 0, "error": None, "retries": 0}
            if fold_variant:
                rec["prefill_fold"] = fold_variant
            if cap is not None and run.spent_micro >= float(cap) * 1e6:
                rec["error"] = "budget_exhausted"
                with gw.lock:
                    run.cap_events += 1
                gw.log_call(rec)
                return self.err(402, "budget_exhausted",
                                "run %s spent %.6f of cap %.2f usd" % (run_id, run.spent_micro / 1e6, float(cap)),
                                call_id)
            hinfo = {}
            try:
                conn, resp, retries = gw.open_upstream("POST", "/chat/completions", sent, hinfo)
            except OSError as e:
                rec["error"] = str(e)
                rec["latency_s"] = round(time.time() - t0, 3)
                gw.log_call(rec)
                return self.err(502, "upstream_unreachable", str(e), call_id)
            rec["retries"] = retries
            # hedged: the second try ran in parallel; cost below is the winner's usage only, the abandoned
            # loser's cost is unknown (it never reports usage to us).
            rec["hedged"] = bool(hinfo.get("hedged"))
            if rec["hedged"] and hinfo.get("hedge_won"):
                rec["hedge_won"] = hinfo["hedge_won"]
            ctype = resp.getheader("Content-Type") or ""
            try:
                if resp.status != 200:
                    raw = resp.read()
                    rec["error"] = "upstream_%d" % resp.status
                    try:
                        rec["response"] = json.loads(raw.decode("utf-8"))
                    except ValueError:
                        rec["response"] = raw.decode("utf-8", "replace")[:2000]
                    rec["latency_s"] = round(time.time() - t0, 3)
                    gw.log_call(rec)
                    self.send_response(resp.status)
                    self.send_header("Content-Type", ctype or "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.send_header("x-bz-call-id", call_id)
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                if not stream:
                    raw = resp.read()
                    try:
                        obj = json.loads(raw.decode("utf-8"))
                    except ValueError:
                        obj = None
                    usage = (obj or {}).get("usage") or {}
                    rec["response"] = obj if obj is not None else raw.decode("utf-8", "replace")[:2000]
                    rec["usage"] = usage
                    if any(policy.detect_junk(t) for t in policy.response_texts(obj)):
                        rec["template_junk"] = True
                    rec["cost_micro"] = int(usage.get("buyer_cost_micro") or 0)
                    if obj is None:
                        rec["error"] = "upstream_not_json"
                    rec["latency_s"] = round(time.time() - t0, 3)
                    gw.log_call(rec)
                    self.send_response(200)
                    self.send_header("Content-Type", ctype or "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.send_header("x-bz-call-id", call_id)
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                self.stream_through(resp, rec, want_usage, t0, call_id)
            finally:
                conn.close()

        def stream_through(self, resp, rec, want_usage, t0, call_id):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("x-bz-call-id", call_id)
            self.end_headers()
            acc = {"content": "", "reasoning": "", "tool_calls": {}, "finish_reason": None, "id": None}
            usage = None
            skip_blank = False
            try:
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    s = line.decode("utf-8", "replace").rstrip("\r\n")
                    if s == "" and skip_blank:
                        skip_blank = False
                        continue
                    forward = True
                    if s.startswith("data:"):
                        payload = s[5:].strip()
                        if payload and payload != "[DONE]":
                            try:
                                ch = json.loads(payload)
                            except ValueError:
                                ch = None
                            if ch:
                                acc["id"] = ch.get("id") or acc["id"]
                                if ch.get("usage"):
                                    usage = ch["usage"]
                                    if not ch.get("choices") and not want_usage:
                                        forward = False
                                        skip_blank = True
                                    elif not want_usage and "usage" in ch:
                                        # usage riding on a content chunk (GLM): drop it from what the caller sees
                                        ch2 = {k: v for k, v in ch.items() if k != "usage"}
                                        line = ("data: " + json.dumps(ch2, ensure_ascii=False) + "\n").encode("utf-8")
                                for c in ch.get("choices") or []:
                                    dl = c.get("delta") or {}
                                    acc["content"] += dl.get("content") or ""
                                    acc["reasoning"] += dl.get("reasoning_content") or dl.get("reasoning") or ""
                                    for tc in dl.get("tool_calls") or []:
                                        slot = acc["tool_calls"].setdefault(tc.get("index", 0), {
                                            "id": None, "type": "function", "function": {"name": "", "arguments": ""}})
                                        slot["id"] = tc.get("id") or slot["id"]
                                        fn = tc.get("function") or {}
                                        slot["function"]["name"] += fn.get("name") or ""
                                        slot["function"]["arguments"] += fn.get("arguments") or ""
                                    if c.get("finish_reason"):
                                        acc["finish_reason"] = c["finish_reason"]
                    if forward:
                        self.wfile.write(line)
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                rec["error"] = "stream_broken: %s" % type(e).__name__
            msg = {"role": "assistant", "content": acc["content"]}
            if acc["reasoning"]:
                msg["reasoning_content"] = acc["reasoning"]
            if acc["tool_calls"]:
                msg["tool_calls"] = [acc["tool_calls"][k] for k in sorted(acc["tool_calls"])]
            rec["response"] = {"id": acc["id"], "choices": [{"index": 0, "message": msg,
                                                             "finish_reason": acc["finish_reason"]}],
                               "usage": usage, "streamed": True}
            rec["usage"] = usage
            if policy.detect_junk(acc["content"]):
                rec["template_junk"] = True
            rec["cost_micro"] = int((usage or {}).get("buyer_cost_micro") or 0)
            if usage is None and not rec["error"]:
                rec["error"] = "stream_no_usage"
            rec["latency_s"] = round(time.time() - t0, 3)
            gw.log_call(rec)

    return H


def make_server(gw, host="127.0.0.1", port=PORT):
    if host != "127.0.0.1":
        raise ValueError("gateway binds 127.0.0.1 only")
    srv = ThreadingHTTPServer((host, port), make_handler(gw))
    srv.daemon_threads = True
    return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--var", default=DEFAULT_VAR)
    ap.add_argument("--key-file", default=DEFAULT_KEY)
    ap.add_argument("--upstream", default=DEFAULT_UPSTREAM)
    ap.add_argument("--no-ticket", action="store_true", help="skip the limits ticket (tests only)")
    a = ap.parse_args()
    os.makedirs(a.var, exist_ok=True)
    # pythonw has no console: send output to a log (never the key)
    log = open(os.path.join(a.var, "gateway.log"), "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log
    ticket = None
    if not a.no_ticket:
        # limits ticket (contract Processes): the gateway with the embed model is a long GPU/RAM run.
        # Held by this pid while it lives, released on stop. Fail-open if the manager is absent.
        sys.path.insert(0, r"F:\REPS2\Meta_Orchestrator\tools\limits")
        import client as limits_client
        ticket = limits_client.request("scail/bz_gateway", {"cpu": 1, "mem_gb": 2, "vram_mb": 1000},
                                       host="here", prio="high", ttl_s=12 * 3600, pid=os.getpid())
        if not ticket.wait(3600):
            print(datetime.now().isoformat(), "no limits grant in 3600 s, exiting")
            ticket.release()
            return
        print(datetime.now().isoformat(), "limits ticket", ticket.ticket)
    gw = Gateway(a.var, a.key_file, a.upstream)
    srv = make_server(gw, "127.0.0.1", a.port)
    with open(os.path.join(a.var, "gateway.pid"), "w") as f:
        f.write(str(os.getpid()))
    print(datetime.now().isoformat(), "gateway up on 127.0.0.1:%d upstream %s" % (a.port, gw.upstream))
    try:
        srv.serve_forever()
    finally:
        if ticket:
            ticket.release()
        print(datetime.now().isoformat(), "gateway down")


if __name__ == "__main__":
    main()
