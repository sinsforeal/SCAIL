"""Readers and stats for the b-zombie viewer. Read-only over the data tree, except votes.

Every reader tolerates missing files, partial last lines and malformed JSON:
a run that is still being written must never crash a page.
"""
import json
import os
import re
import threading
import time
from datetime import datetime, timezone

DEFAULT_DATA = r"H:\SCAIL\bzombie\var"
SEP = "~"  # ref = "<run_id>" or "<run_id>~<branch_id>"
_SAFE = re.compile(r"^[A-Za-z0-9_.\-]+$")
STALE_S = 600  # a "running" run with no file change for this long shows "stale"
LIVE_FILES = ("clock.json", "transcript.jsonl", "calls.jsonl", "state.json")
# every bz_* run is setup-era (10-22, before the fixes); clean judged runs are named cl<n>_* (User 20:18)
_DEV_ID = re.compile(r"^(bz_|cl1_|simhim_probe)")


def run_kind(run, cfg):
    for k in ("dummy", "smoke", "live", "time"):
        if k in run:
            return k
    return "full" if isinstance((cfg or {}).get("sim_days"), (int, float)) else "dev"


def canned_flag(run, cfg, calls, tr, status, models=()):
    """DUMMY or STUB when what she says cannot be a real model reply, else None.
    The harness records nothing about BZ_LLM_STUB today, so this reads: id says dummy, config says stub or
    runs the stub arm, a model named stub, or no gateway calls although lines exist."""
    cfg = cfg or {}
    cmd = " ".join(str(x) for x in (cfg.get("arm_cmd") or []) if isinstance(x, str)) if isinstance(cfg.get("arm_cmd"), list) else str(cfg.get("arm_cmd") or "")
    if "dummy" in run or "dummy" in json.dumps(cfg).lower():
        return "DUMMY"
    if cfg.get("stub") or cfg.get("llm_stub") or "stub_arm" in cmd or any("stub" in str(m or "").lower() for m in models):
        return "STUB"
    if not calls and (tr or status in ("done", "failed", "stale")):
        return "STUB"
    return None


def start_ts(cfg):
    v = (cfg or {}).get("started_wall")
    if isinstance(v, (int, float)):
        return float(v)
    dt = parse_ts(v) or parse_ts((cfg or {}).get("clock_start"))
    return dt.timestamp() if dt else 0.0


def is_dev(run, cfg):
    """Agent test runs: no sim_days in config (real bench runs come from the harness templates, which set it),
    a test id pattern, or the modelcheck folder."""
    sd = (cfg or {}).get("sim_days")
    if isinstance(sd, bool) or not isinstance(sd, (int, float)):
        return True
    return run == "modelcheck" or bool(_DEV_ID.match(run))
_DROP_KEYS = {"authorization", "x-api-key", "api_key", "api-key", "proxy-authorization"}


def safe_name(s):
    return isinstance(s, str) and bool(_SAFE.match(s)) and s not in (".", "..")


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def scrub(obj):
    """Drop credentials from anything shown."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if str(k).lower() not in _DROP_KEYS}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


class JsonlTail:
    """Incremental jsonl reader. Keeps (offset, length, summary) per good line.
    A trailing line with no newline that does not parse is left for the next read."""

    def __init__(self, path, summarize=None):
        self.path = path
        self.summarize = summarize or (lambda o: o)
        self.pos = 0
        self.items = []  # summaries
        self.spans = []  # (offset, length)
        self.bad = 0
        self.lock = threading.Lock()

    def refresh(self):
        with self.lock:
            try:
                size = os.path.getsize(self.path)
            except OSError:
                self.pos, self.items, self.spans, self.bad = 0, [], [], 0
                return self.items
            if size < self.pos:
                self.pos, self.items, self.spans, self.bad = 0, [], [], 0
            if size == self.pos:
                return self.items
            try:
                with open(self.path, "rb") as f:
                    f.seek(self.pos)
                    data = f.read()
            except OSError:
                return self.items
            off = 0
            while off < len(data):
                nl = data.find(b"\n", off)
                end = len(data) if nl < 0 else nl + 1
                raw = data[off:end]
                text = raw.strip()
                if text:
                    try:
                        obj = json.loads(text.decode("utf-8"))
                        if isinstance(obj, dict):
                            self.items.append(self.summarize(obj))
                            self.spans.append((self.pos + off, len(raw)))
                        else:
                            self.bad += 1
                    except (ValueError, UnicodeDecodeError):
                        if nl < 0:
                            break  # partial last line: wait for the rest
                        self.bad += 1
                off = end
            self.pos += off
            return self.items

    def read_span(self, i):
        try:
            off, ln = self.spans[i]
            with open(self.path, "rb") as f:
                f.seek(off)
                return json.loads(f.read(ln).decode("utf-8"))
        except (OSError, ValueError, IndexError):
            return None


def parse_ts(s):
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def summarize_call(o):
    u = o.get("usage") or {}
    resp = o.get("response") or {}
    if not u and isinstance(resp, dict):
        u = resp.get("usage") or {}
    err = o.get("error")
    return {
        "call_id": o.get("call_id"),
        "arm": o.get("arm"),
        "wall_ts": o.get("wall_ts"),
        "virtual_ts": o.get("virtual_ts"),
        "model": o.get("model"),
        "prompt_tokens": _num(u.get("prompt_tokens", u.get("input_tokens"))),
        "completion_tokens": _num(u.get("completion_tokens", u.get("output_tokens"))),
        "cost_micro": _num(o.get("cost_micro")),
        "latency_s": _num(o.get("latency_s")),
        "error": (err if isinstance(err, str) else json.dumps(err, ensure_ascii=False)) if err else None,
    }


def _num(v):
    if isinstance(v, bool):
        return 0
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


# ---------- text metrics ----------

def _script_counts(text):
    jp = lat = other = 0
    for ch in text:
        c = ord(ch)
        if 0x3040 <= c <= 0x30FF or 0x4E00 <= c <= 0x9FFF or 0x3400 <= c <= 0x4DBF or c == 0x30FC or 0xFF66 <= c <= 0xFF9F:
            jp += 1
        elif ch.isalpha() and c < 0x250:
            lat += 1
        elif ch.isalpha():
            other += 1
    return jp, lat, other


def language_purity(texts, lang):
    jp = lat = other = 0
    for t in texts:
        a, b, c = _script_counts(t or "")
        jp, lat, other = jp + a, lat + b, other + c
    total = jp + lat + other
    if not total:
        return None
    return ((jp if lang == "ja" else lat) / total)


def _norm(t):
    return re.sub(r"[\s\W_]+", "", (t or "").lower())


def _bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}


def repetition_rate(texts, window=20, thresh=0.8):
    prev, rep, n = [], 0, 0
    for t in texts:
        s = _norm(t)
        if not s:
            continue
        n += 1
        g = _bigrams(s)
        hit = False
        for p, pg in prev[-window:]:
            if p == s:
                hit = True
                break
            u = len(g | pg)
            if u and len(g & pg) / u >= thresh:
                hit = True
                break
        rep += hit
        prev.append((s, g))
    return (rep / n) if n else None


def percentile(vals, q):
    if not vals:
        return None
    v = sorted(vals)
    k = (len(v) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def length_hist(lens, edges=(0, 10, 20, 40, 80, 160, 320)):
    out = []
    for i, lo in enumerate(edges):
        hi = edges[i + 1] if i + 1 < len(edges) else None
        n = sum(1 for x in lens if x >= lo and (hi is None or x < hi))
        out.append({"lo": lo, "hi": hi, "n": n})
    return out


def causal_stats(traces):
    """S traces: causal.admitted = [{text, weight, constant?}]. Uses explicit fields when present."""
    shares, consts, with_causal = [], [], 0
    for t in traces:
        c = t.get("causal") if isinstance(t, dict) else None
        if not isinstance(c, dict) or not c:
            continue
        with_causal += 1
        if isinstance(c.get("causal_share"), (int, float)):
            shares.append(float(c["causal_share"]))
        adm = c.get("admitted") or c.get("attention") or []
        if isinstance(adm, list) and adm:
            w = [float(x.get("weight", 0) or 0) for x in adm if isinstance(x, dict)]
            if sum(w) > 0 and not isinstance(c.get("causal_share"), (int, float)):
                top = max(w)
                shares.append(top / sum(w))
            cl = [x for x in adm if isinstance(x, dict) and x.get("constant")]
            consts.append(len(cl) / len(adm))
        if isinstance(c.get("constant_lines"), list) and not adm:
            consts.append(len(c["constant_lines"]))
    return {
        "traces_with_causal": with_causal,
        "causal_share": (sum(shares) / len(shares)) if shares else None,
        "constant_line_share": (sum(consts) / len(consts)) if consts else None,
    }


def compute_stats(config, transcript, calls, traces=None, day_of=None):
    """Pure function. transcript: list of dicts; calls: list of call summaries."""
    config = config or {}
    traces = traces or []
    day_of = day_of or (lambda ts: None)
    her = [x for x in transcript if x.get("who") == "her"]
    him = [x for x in transcript if x.get("who") == "him"]
    env = [x for x in transcript if x.get("who") == "env"]
    replies = [x for x in her if x.get("kind") != "unprompted"]
    unprompted = [x for x in her if x.get("kind") == "unprompted"]
    lat = [c["latency_s"] for c in calls if c.get("latency_s")]
    cost = sum(c.get("cost_micro") or 0 for c in calls)
    per_day = {}
    for c in calls:
        d = day_of(c.get("virtual_ts"))
        e = per_day.setdefault(d, {"day": d, "cost_usd": 0.0, "calls": 0})
        e["cost_usd"] += (c.get("cost_micro") or 0) / 1e6
        e["calls"] += 1
    days = sorted(per_day.values(), key=lambda e: (e["day"] is None, e["day"] or 0))
    texts = [x.get("text") or "" for x in her]
    lens = [len(t) for t in texts]
    tcalls = [len(t.get("calls") or []) for t in traces if isinstance(t, dict)]
    cpr = (sum(tcalls) / len(tcalls)) if tcalls else ((len(calls) / len(replies)) if replies else None)
    models = sorted({c["model"] for c in calls if c.get("model")})
    return {
        "calls": len(calls),
        "errors": sum(1 for c in calls if c.get("error")),
        "models_seen": models,
        "prompt_tokens": int(sum(c.get("prompt_tokens") or 0 for c in calls)),
        "completion_tokens": int(sum(c.get("completion_tokens") or 0 for c in calls)),
        "cost_usd": cost / 1e6,
        "latency": {
            "mean": (sum(lat) / len(lat)) if lat else None,
            "p50": percentile(lat, 0.5), "p95": percentile(lat, 0.95),
            "max": max(lat) if lat else None,
        },
        "calls_per_reply": cpr,
        "cost_per_day": days,
        "cost_per_reply_usd": (cost / 1e6 / len(replies)) if replies else None,
        "lines": {"him": len(him), "her": len(her), "env": len(env)},
        "replies": len(replies),
        "unprompted": len(unprompted),
        "reply_len": {
            "mean": (sum(lens) / len(lens)) if lens else None,
            "median": percentile(lens, 0.5), "p90": percentile(lens, 0.9),
            "max": max(lens) if lens else None,
            "hist": length_hist(lens),
        },
        "repetition_rate": repetition_rate(texts),
        "language_purity": language_purity(texts, config.get("lang", "en")),
        "causal": causal_stats(traces),
    }


# ---------- the data tree ----------

class Store:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self._tails = {}
        self._lock = threading.Lock()
        self._trace_cache = {}
        self._vote_lock = threading.Lock()
        self.now = time.time  # tests replace it

    # paths
    def run_dir(self, ref):
        run, _, br = (ref or "").partition(SEP)
        if not safe_name(run) or (br and not safe_name(br)):
            return None
        d = os.path.join(self.root, "runs", run)
        if br:
            d = os.path.join(d, "branches", br)
        return d if os.path.isdir(d) else None

    def _tail(self, path, kind):
        with self._lock:
            t = self._tails.get(path)
            if t is None:
                t = JsonlTail(path, summarize_call if kind == "calls" else None)
                self._tails[path] = t
        t.refresh()
        return t

    def transcript(self, ref):
        d = self.run_dir(ref)
        if not d:
            return []
        return list(self._tail(os.path.join(d, "transcript.jsonl"), "tr").items)

    def calls(self, ref):
        d = self.run_dir(ref)
        if not d:
            return []
        return list(self._tail(os.path.join(d, "calls.jsonl"), "calls").items)

    def call_detail(self, ref, call_id):
        d = self.run_dir(ref)
        if not d or not call_id:
            return None
        # a call may live in the parent run's log when a branch replays
        t = self._tail(os.path.join(d, "calls.jsonl"), "calls")
        for i, c in enumerate(t.items):
            if c.get("call_id") == call_id:
                o = t.read_span(i)
                return scrub(o) if o else None
        if SEP in ref:
            return self.call_detail(ref.split(SEP)[0], call_id)
        return None

    def trace(self, ref, output_id):
        d = self.run_dir(ref)
        if not d or not safe_name(output_id):
            return None
        return scrub(read_json(os.path.join(d, "traces", output_id + ".json")))

    def traces(self, ref):
        d = self.run_dir(ref)
        out = []
        td = os.path.join(d, "traces") if d else None
        if not td or not os.path.isdir(td):
            return out
        try:
            names = sorted(os.listdir(td))
        except OSError:
            return out
        for n in names:
            if not n.endswith(".json"):
                continue
            p = os.path.join(td, n)
            try:
                st = os.stat(p)
            except OSError:
                continue
            key = (p, st.st_mtime_ns, st.st_size)
            if key not in self._trace_cache:
                self._trace_cache[key] = read_json(p)
            v = self._trace_cache[key]
            if isinstance(v, dict):
                out.append(v)
        return out

    def config(self, ref):
        d = self.run_dir(ref)
        if not d:
            return None
        run = ref.partition(SEP)[0]
        cfg = read_json(os.path.join(self.root, "runs", run, "config.json"), {}) or {}
        if not isinstance(cfg, dict):
            cfg = {}
        cfg.setdefault("run_id", run)
        return cfg

    def clock(self, ref):
        d = self.run_dir(ref)
        if not d:
            return {}
        c = read_json(os.path.join(d, "clock.json"))
        if c is None and SEP in ref:
            c = read_json(os.path.join(self.root, "runs", ref.split(SEP)[0], "clock.json"))
        return c if isinstance(c, dict) else {}

    def day_of_fn(self, ref, transcript=None):
        cfg = self.config(ref) or {}
        tr = transcript if transcript is not None else self.transcript(ref)
        m = {}
        for x in tr:
            dt = parse_ts(x.get("virtual_ts"))
            if dt and isinstance(x.get("sim_day"), int):
                m.setdefault(dt.date(), x["sim_day"])
        start = parse_ts(cfg.get("clock_start"))

        def f(ts):
            dt = parse_ts(ts)
            if not dt:
                return None
            if dt.date() in m:
                return m[dt.date()]
            if start:
                return (dt.date() - start.date()).days + 1
            return None
        return f

    def stats(self, ref):
        cfg = self.config(ref)
        if cfg is None:
            return None
        tr = self.transcript(ref)
        return compute_stats(cfg, tr, self.calls(ref), self.traces(ref), self.day_of_fn(ref, tr))

    def branch_ids(self, run):
        bd = os.path.join(self.root, "runs", run, "branches")
        try:
            return sorted(n for n in os.listdir(bd) if os.path.isdir(os.path.join(bd, n)))
        except OSError:
            return []

    def last_activity(self, d):
        """Newest mtime among the run's live files; config.json only when none exist."""
        best = None
        for n in LIVE_FILES:
            try:
                m = os.stat(os.path.join(d, n)).st_mtime
            except OSError:
                continue
            best = m if best is None or m > best else best
        if best is None:
            try:
                best = os.stat(os.path.join(d, "config.json")).st_mtime
            except OSError:
                pass
        return best

    def run_row(self, ref):
        cfg = self.config(ref)
        if cfg is None:
            return None
        run, _, br = ref.partition(SEP)
        d = self.run_dir(ref)
        tr = self.transcript(ref)
        calls = self.calls(ref)
        clock = self.clock(ref)
        her = [x for x in tr if x.get("who") == "her"]
        him = [x for x in tr if x.get("who") == "him"]
        row = {
            "ref": ref, "run_id": run, "branch_id": br or None,
            "arm": cfg.get("arm"), "character": cfg.get("character"), "lang": cfg.get("lang"),
            "model": cfg.get("model"), "status": cfg.get("status") or "unknown",
            "sim_days": cfg.get("sim_days"), "cap_usd": cfg.get("cap_usd"),
            "virtual_ts": clock.get("virtual_ts"), "sim_day": clock.get("sim_day"),
            "messages": len(tr), "her": len(her), "him": len(him),
            "calls": len(calls),
            "cost_usd": sum(c.get("cost_micro") or 0 for c in calls) / 1e6,
            "errors": sum(1 for c in calls if c.get("error")),
            "started_wall": cfg.get("started_wall"), "updated_wall": cfg.get("updated_wall"),
        }
        if br:
            b = read_json(os.path.join(d, "branch.json"), {}) or {}
            row["branch"] = b
            row["status"] = b.get("status") or cfg.get("status") or "unknown"
        # computed only, never written: "running" with no file change for STALE_S is "stale"
        if row["status"] == "running":
            act = self.last_activity(d)
            if act is not None and self.now() - act > STALE_S:
                row["status"] = "stale"
        row["dev"] = is_dev(run, cfg)
        row["kind"] = run_kind(run, cfg)
        row["canned"] = canned_flag(run, cfg, calls, tr, row["status"], [c.get("model") for c in calls[:3]])
        row["start_ts"] = start_ts(cfg)
        days = row["sim_day"] if isinstance(row["sim_day"], int) else max([x["sim_day"] for x in tr if isinstance(x.get("sim_day"), int)] or [0])
        row["days_done"] = days
        row["calls_per_day"] = (len(calls) / days) if days else None
        row["cost_per_day_usd"] = (row["cost_usd"] / days) if days else None
        return row

    def runs(self):
        rd = os.path.join(self.root, "runs")
        out = []
        try:
            names = sorted(n for n in os.listdir(rd) if not n.startswith("_") and os.path.isdir(os.path.join(rd, n)))
        except OSError:
            return out
        for n in names:
            r = self.run_row(n)
            if r:
                out.append(r)
            for b in self.branch_ids(n):
                r = self.run_row(n + SEP + b)
                if r:
                    out.append(r)
        return out

    # ---------- judged ----------
    def matches(self):
        jd = os.path.join(self.root, "judge")
        try:
            names = sorted(n for n in os.listdir(jd) if os.path.isfile(os.path.join(jd, n, "results.json")))
        except OSError:
            return []
        out = []
        for n in names:
            r = read_json(os.path.join(jd, n, "results.json"))
            if isinstance(r, dict):
                out.append(judge_view(n, r))
        return out

    def calibrations(self):
        """judge/calibration/<stamp>/results.json, newest first."""
        cd = os.path.join(self.root, "judge", "calibration")
        try:
            stamps = sorted((n for n in os.listdir(cd) if os.path.isfile(os.path.join(cd, n, "results.json"))), reverse=True)
        except OSError:
            return []
        out = []
        for n in stamps:
            r = read_json(os.path.join(cd, n, "results.json"))
            if isinstance(r, dict):
                out.append(calibration_view(n, r, os.path.join(cd, n, "claude_calls.jsonl")))
        return out

    def match(self, mid):
        if not safe_name(mid):
            return None
        r = read_json(os.path.join(self.root, "judge", mid, "results.json"))
        return judge_view(mid, r) if isinstance(r, dict) else None

    def modelcheck(self):
        d = os.path.join(self.root, "modelcheck")
        s, k, j = (read_json(os.path.join(d, n + ".json")) for n in ("samples", "key", "judgments"))
        if s is None and k is None and j is None:
            return None
        return {"samples": s, "key": k, "judgments": j, "view": modelcheck_view(s, k, j)}

    # ---------- votes ----------
    def _votes(self):
        t = JsonlTail(os.path.join(self.root, "votes.jsonl"))
        return t.refresh()

    def pairs(self):
        pd = os.path.join(self.root, "pairs")
        try:
            names = sorted(n[:-5] for n in os.listdir(pd) if n.endswith(".json"))
        except OSError:
            return []
        votes = {}
        for v in self._votes():
            votes[v.get("pair_id")] = v
        out = []
        for n in names:
            if not safe_name(n):
                continue
            p = read_json(os.path.join(pd, n + ".json")) or {}
            out.append({"pair_id": n, "character": p.get("character"), "label": p.get("label"),
                        "voted": n in votes, "choice": votes.get(n, {}).get("choice")})
        return out

    def pair(self, pid):
        """A and B only. The hidden mapping never leaves the server."""
        if not safe_name(pid):
            return None
        p = read_json(os.path.join(self.root, "pairs", pid + ".json"))
        if not isinstance(p, dict):
            return None
        out = {}
        src = p.get("outputs") if isinstance(p.get("outputs"), dict) else p
        for k in ("A", "B"):
            v = src.get(k)
            out[k] = v.get("text", "") if isinstance(v, dict) else (v if isinstance(v, str) else "")
        prior = [v for v in self._votes() if v.get("pair_id") == pid]
        return {"pair_id": pid, "A": out["A"], "B": out["B"], "vote": prior[-1] if prior else None}

    def record_vote(self, pid, choice, note):
        if choice not in ("A", "B", "tie"):
            return None, "choice must be A, B or tie"
        if not safe_name(pid) or not os.path.isfile(os.path.join(self.root, "pairs", pid + ".json")):
            return None, "no such pair"
        rec = {"pair_id": pid, "choice": choice, "note": str(note or "")[:2000],
               "wall_ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
        with self._vote_lock:
            os.makedirs(self.root, exist_ok=True)
            with open(os.path.join(self.root, "votes.jsonl"), "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec, None

    # ---------- options ----------
    def options(self, dev=False):
        rows = [r for r in self.runs() if dev or not r.get("dev")]
        def u(k):
            return sorted({str(r[k]) for r in rows if r.get(k) not in (None, "")})
        days = set()
        for r in rows:
            if isinstance(r.get("sim_days"), int):
                days.update(range(1, r["sim_days"] + 1))
        return {"arm": u("arm"), "character": u("character"), "model": u("model"),
                "status": u("status"), "days": sorted(days),
                "branches": sorted({r["branch_id"] for r in rows if r.get("branch_id")})}

    # ---------- side by side ----------
    def compare(self, a, b, env=True):
        cols = {}
        for key, ref in (("a", a), ("b", b)):
            if self.run_dir(ref) is None:
                return None
            tr = self.transcript(ref)
            df = self.day_of_fn(ref, tr)
            cols[key] = []
            for x in tr:
                if not env and x.get("who") == "env":
                    continue
                dt = parse_ts(x.get("virtual_ts"))
                day = x.get("sim_day") if isinstance(x.get("sim_day"), int) else df(x.get("virtual_ts"))
                cols[key].append((day, dt.hour if dt else None, x))
        rows = {}
        for key in ("a", "b"):
            for day, hr, x in cols[key]:
                rows.setdefault((day if day is not None else -1, hr if hr is not None else -1),
                                {"day": day, "hour": hr, "a": [], "b": []})[key].append(x)
        out = [rows[k] for k in sorted(rows)]
        return {"a": self.run_row(a), "b": self.run_row(b), "rows": out,
                "stats": {"a": self.stats(a), "b": self.stats(b)}}


def judge_view(mid, r):
    crits = []
    agree = tot = 0
    tally = {"A": 0, "B": 0, "tie": 0}
    sums = {"A": [], "B": []}
    for c in r.get("criteria") or []:
        if not isinstance(c, dict):
            continue
        passes = [p for p in (c.get("passes") or []) if isinstance(p, dict)]
        verdicts = [p.get("verdict") for p in passes]
        ag = len(verdicts) >= 2 and len(set(verdicts)) == 1
        if len(verdicts) >= 2:
            tot += 1
            agree += ag
            if ag and verdicts[0] in tally:
                tally[verdicts[0]] += 1
        for p in passes:
            for k in ("A", "B"):
                s = (p.get("scores") or {}).get(k)
                if isinstance(s, (int, float)):
                    sums[k].append(s)
        crits.append({"id": c.get("id"), "name": c.get("name"), "passes": passes, "agree": ag if len(verdicts) >= 2 else None})
    cal = [x for x in (r.get("calibration") or []) if isinstance(x, dict)]
    caught = sum(1 for x in cal if x.get("caught"))
    return {
        "match_id": mid, "character": r.get("character"), "label_map": r.get("label_map"),
        "criteria": crits, "calibration": cal, "summary": r.get("summary"),
        "agreement": {"agreed": agree, "of": tot, "rate": (agree / tot) if tot else None},
        "tally_agreed": tally,
        "mean_scores": {k: (sum(v) / len(v) if v else None) for k, v in sums.items()},
        "calibration_caught": {"caught": caught, "of": len(cal)},
    }


def calibration_view(stamp, r, calls_path):
    """One calibration run: per criterion and language planted/caught/controls/calibrated plus the entries."""
    summ = r.get("summary") if isinstance(r.get("summary"), dict) else {}
    caught = {}
    for x in r.get("calibration") or []:
        if isinstance(x, dict) and isinstance(x.get("defect"), str):
            caught[x["defect"]] = bool(x.get("caught"))
    rows = []
    by_lang = summ.get("by_lang") if isinstance(summ.get("by_lang"), dict) else {}
    for crit, langs in by_lang.items():
        if not isinstance(langs, dict):
            continue
        for lang, v in langs.items():
            if not isinstance(v, dict):
                continue
            rows.append({"criterion": crit, "lang": lang, "planted": v.get("planted"), "caught": v.get("caught"),
                         "controls": v.get("controls"), "controls_passed": v.get("controls_passed"),
                         "calibrated": bool(v.get("calibrated")),
                         "entries": [{"id": i, "caught": caught.get(i)} for i in (v.get("ids") or [])]})
    cost, ncalls = None, None
    try:
        cost, ncalls = 0.0, 0
        with open(calls_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if isinstance(o, dict):
                    ncalls += 1
                    cost += _num(o.get("cost_usd"))
    except OSError:
        cost, ncalls = None, None
    return {"stamp": stamp, "match_id": r.get("match_id"), "model": summ.get("model"),
            "rows": rows, "calibrated": sum(1 for x in rows if x["calibrated"]), "of": len(rows),
            "uncalibrated": summ.get("uncalibrated") or [], "entries": summ.get("entries"),
            "cost_usd": cost, "calls": ncalls if ncalls is not None else summ.get("calls")}


def modelcheck_view(samples, key, judg):
    """Join samples.json, key.json, judgments.json into summary + per-moment rows. Tolerates missing parts."""
    samples = samples if isinstance(samples, dict) else {}
    key = key if isinstance(key, dict) else {}
    judg = judg if isinstance(judg, dict) else {}
    labels = key.get("labels") if isinstance(key.get("labels"), dict) else {}
    passes = [p for p in (judg.get("passes") or []) if isinstance(p, dict)]
    by_moment = {}
    for s in samples.get("samples") or []:
        if isinstance(s, dict):
            by_moment.setdefault(s.get("moment_id"), []).append(s)
    moments = []
    for m in samples.get("moments") or []:
        if not isinstance(m, dict):
            continue
        rows = []
        for s in by_moment.get(m.get("id"), []):
            lab = s.get("label")
            kv = labels.get(lab) or {}
            u = kv.get("usage") or {}
            cost = u.get("buyer_cost_micro")
            ps = []
            for p in passes:
                sc = (p.get("scores") or {}).get(lab) or {}
                rk = (p.get("ranks") or {}).get(m.get("id")) or []
                ps.append({"pass": p.get("pass"), "kino": sc.get("kino"), "natural": sc.get("natural"),
                           "flags": sc.get("flags") or [], "rank": (rk.index(lab) + 1) if lab in rk else None})
            rows.append({"label": lab, "text": s.get("text"), "model": kv.get("model"), "finish_reason": kv.get("finish_reason"),
                         "cost_micro": cost, "cost_usd": (cost / 1e6) if isinstance(cost, (int, float)) else None,
                         "completion_tokens": u.get("completion_tokens"), "passes": ps})
        moments.append({"id": m.get("id"), "character": m.get("character"), "mood": m.get("mood"),
                        "situation": m.get("situation"), "chat": m.get("chat") or [], "newest": m.get("newest"), "samples": rows})
    return {"run_id": judg.get("run_id") or samples.get("run_id") or key.get("run_id"), "judge": judg.get("judge"),
            "criteria": judg.get("criteria"), "summary": judg.get("summary") if isinstance(judg.get("summary"), dict) else {},
            "agreement": judg.get("winner_model_agreement_moments"), "pass_count": len(passes), "moments": moments}
