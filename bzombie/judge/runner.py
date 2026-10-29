"""B-zombie judge runner: calibrate, match, splice. Binds bzombie/judge/RUBRIC.md and bzombie/CONTRACT.md.

Every judge call is one fresh `claude -p` through llm.ask (task "judge"), two passes per criterion with A and B
swapped in pass 2 and swapped back before anything is written. Prompts are filled by plain text replace.
Billing: driver.open_credits / close_credits, settled once on every exit path, with the driver's claude_billing
(module `claude_billing`: auto = credits then the bench worker queue after the grant, credits = pause on a used-up
grant, queue = worker only). A refusal, the cap, credits-mode GrantExhausted or a dead/slow worker pauses cleanly:
passes done are cached under <dir>/passes and the same command resumes.
Output under var/bzombie/judge/ : <match_id>/results.json, calibration/<stamp>/results.json, splice/<stamp>/results.json.
"""
from __future__ import annotations

import contextlib
import difflib
import hashlib
import json
import math
import os
import random
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

from .. import common, credits, llm
from ..common import parse_ts, read_json, read_jsonl, write_json
from . import steer

JUDGE_DIR = Path(__file__).resolve().parent
PROMPTS = JUDGE_DIR / "prompts"
CARDS = JUDGE_DIR / "cards"
DEFECTS = JUDGE_DIR / "calibration" / "defects.json"

CRITERIA = {  # id: (name, slice parts), RUBRIC.md table
    "answers_him": ("Answers him", ["Wq"]),
    "memory_continuity": ("Continuity and memory across days", ["X"]),
    "own_life": ("Her own life and initiative", ["D2", "U"]),
    "character_fidelity": ("Character fidelity to the bible", ["W", "D1"]),
    "natural_language": ("Natural language for the target language", ["D2noenv"]),
    "non_repetition": ("Non-repetition", ["Xher"]),
    "emotional_arc": ("Emotional coherence over the arc", ["X"]),
    "grounded_claims": ("Grounded claims", ["X"]),
    "frame_integrity": ("Frame integrity", ["Xher"]),
    "house_presence": ("House presence: the second person comes through", ["H"]),
    "house_grounded": ("House grounded: claims about the house", ["H"]),
}
HOUSE = ("house_presence", "house_grounded")  # the only criteria that see peer lines; default only when a side has peers
CRITERIA.update(steer.criteria())  # steer_<direction> (tk-6si): named by the inject summary, never in a default match
DEFAULT_CRITERIA = [c for c in CRITERIA if c not in HOUSE and not steer.is_steer(c)]
PEER_NAMES = {"maria": "真里亜", "momoka": "百花"}  # peer_hub.jsonl from/to ids as the chat names them
NEEDS_2_DAYS = ("memory_continuity", "emotional_arc")  # removal tests with a shorter span leave these out
LANG = {"momoka": "ja", "tomoe": "en"}
CAP_TOKENS = 30000
WINDOWS = 12
PAIR_MIN = 45
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
PART_TITLES = {"U": "--- every unprompted message, each with the 3 lines before it ---",
               "D2": "--- two whole days ---", "W": "--- windows ---", "D1": "--- one whole day ---"}

claude_billing = "auto"  # auto | credits | queue, exactly the driver's claude_billing (llm.Session routes the calls)
queue_timeout_s = 900


class Paused(Exception):
    """A clean stop: billing or cap. Cached passes stay; the same command resumes."""

    def __init__(self, reason, message):
        super().__init__(message)
        self.reason, self.message = reason, message


# ---------------------------------------------------------------- claude call seam and billing

def ask_claude(system: str, prompt: str) -> str:
    return llm.ask("judge", system, prompt)  # credits first, the bench worker queue after the grant (llm._real)


@contextlib.contextmanager
def billing(label: str, rd: Path, cap_usd: float):
    """Reserve and arm llm.session like the driver; settle once on every exit path. No reservation under a stub."""
    from ..harness import driver
    res = None
    try:
        if llm.backend is None and os.environ.get("BZ_LLM_STUB") != "1":
            res = driver.open_credits({"run_id": label, "claude_cap_usd": cap_usd, "claude_billing": claude_billing,
                                       "queue_timeout_s": queue_timeout_s}, rd)
        yield res
    finally:
        driver.close_credits(res, rd)


def guarded(rd: Path, label: str, cap_usd: float, fn):
    """Run fn under billing. Returns (exit_code, result). Billing stops write rd/pause.json and exit 75."""
    rd.mkdir(parents=True, exist_ok=True)
    try:
        with billing(label, rd, cap_usd):
            res = fn()
        (rd / "pause.json").unlink(missing_ok=True)
        return 0, res
    except credits.GrantExhausted as e:
        why, msg = "grant_exhausted", ("the one-time API grant is used up (" + str(e)[:200] + ") and claude_billing is "
                                       "credits. Passes done are cached; re-run the same command with auto or queue")
    except llm.QueueUnavailable as e:  # worker_down or worker_timeout
        why, msg = e.reason, str(e)[:300] + ". Passes done are cached; re-run once the bench worker is back"
    except credits.CreditsRefused as e:
        why, msg = "credits_refused", "credits.py refused: " + str(e)[:300]
    except llm.CapReached as e:
        why, msg = "claude_cap", str(e)
    except Paused as e:
        why, msg = e.reason, e.message
    write_json(rd / "pause.json", {"reason": why, "message": msg, "wall_ts": time.time()})
    print("PAUSED (" + why + "): " + msg, flush=True)
    return 75, None


# ---------------------------------------------------------------- transcripts

def parse_spec(spec: str):
    run, _, br = spec.partition("~")
    return run, (br or None)


def load_events(spec: str):
    """Events of a run or branch as dicts {i, ts, day, who, kind, text}; returns (events, branch cutoff or None)."""
    run, br = parse_spec(spec)
    rd = common.run_dir(run)
    cfg = read_json(rd / "config.json", {}) or {}
    base = rd / "branches" / br if br else rd
    raw = read_jsonl(base / "transcript.jsonl")
    if not raw:
        raise ValueError(f"no transcript for {spec} under {base}")
    cutoff = None
    if br:
        cutoff = (read_json(base / "branch.json", {}) or {}).get("replayed_from_virtual_ts")
    d0 = parse_ts(cfg["clock_start"]).date() if cfg.get("clock_start") else None
    evs = []
    for r in raw:
        if r.get("who") not in ("him", "her", "env") or not r.get("virtual_ts"):
            continue
        ts = parse_ts(r["virtual_ts"])
        if cutoff and ts < parse_ts(cutoff):
            continue
        day = r.get("sim_day") or ((ts.date() - d0).days + 1 if d0 else 1)
        kind = r.get("kind") or ("world" if r["who"] == "env" else "reply")
        evs.append({"ts": ts, "day": int(day), "who": r["who"], "kind": kind, "text": str(r.get("text") or "")})
    evs.sort(key=lambda e: e["ts"])
    for i, e in enumerate(evs):
        e["i"] = i
    return evs, cutoff


def load_peer_events(spec: str) -> list:
    """Peer lines (peer_hub.jsonl beside the transcript) as events {i: -1, ts, day, who: "peer", kind: "peer", frm, to,
    text}; [] when the run has no peer file. Kept apart from load_events so every existing slice is cut from the same
    list as before; only the house criteria merge these in (Ctx.part "H")."""
    run, br = parse_spec(spec)
    rd = common.run_dir(run)
    cfg = read_json(rd / "config.json", {}) or {}
    base = rd / "branches" / br if br else rd
    raw = read_jsonl(base / "peer_hub.jsonl")
    if not raw:
        return []
    cutoff = (read_json(base / "branch.json", {}) or {}).get("replayed_from_virtual_ts") if br else None
    d0 = parse_ts(cfg["clock_start"]).date() if cfg.get("clock_start") else None
    evs = []
    for r in raw:
        if not r.get("virtual_ts") or not str(r.get("text") or "").strip():
            continue
        ts = parse_ts(r["virtual_ts"])
        if cutoff and ts < parse_ts(cutoff):
            continue
        day = r.get("sim_day") or ((ts.date() - d0).days + 1 if d0 else 1)
        evs.append({"i": -1, "ts": ts, "day": int(day), "who": "peer", "kind": "peer", "text": str(r["text"]),
                    "frm": str(r.get("from") or "?"), "to": str(r.get("to") or "?")})
    evs.sort(key=lambda e: e["ts"])
    return evs


def tag(e) -> str:
    return f"[d{e['day']} {WD[e['ts'].weekday()]} {e['ts']:%H:%M}]"


def who_label(e) -> str:
    if e["who"] == "peer":
        return f"peer {PEER_NAMES.get(e['frm'], e['frm'])} to {PEER_NAMES.get(e['to'], e['to'])}"
    if e["who"] == "her":
        return "her (unprompted)" if e["kind"] == "unprompted" else "her"
    if e["who"] == "env":
        return f"env ({'pc' if e['kind'] == 'pc' else 'world'})"
    return "him"


def tokens(text: str) -> float:
    """1 token per 3 chars of English, 1 per 1.5 of Japanese (RUBRIC, size cap)."""
    n = sum(1 for c in text if ord(c) >= 0x3000)
    return n / 1.5 + (len(text) - n) / 3


def level_opts(level: int, days: list) -> dict:
    o = {"env_days": None, "his_cut": None, "omit": set()}
    if level >= 1:
        o["env_days"] = set(days[-2:])
    if level >= 2:
        o["his_cut"] = 200
    if level >= 3 and len(days) > 4:
        o["omit"] = set(days) - (set(days[:2]) | set(days[-2:]))
    return o


def fmt_line(e, o) -> str:
    text = e["text"].replace("\r", "")
    if e["who"] == "him" and o["his_cut"] and len(text) > o["his_cut"]:
        text = text[:o["his_cut"]] + "…"
    return f"{tag(e)} {who_label(e)}: " + text.replace("\n", "\n    ")


def keep(e, o, env_ok=True) -> bool:
    if e["who"] != "env":
        return True
    return env_ok and (o["env_days"] is None or e["day"] in o["env_days"])


def day_header(events, d) -> str:
    first = next((e for e in events if e["day"] == d), None)
    return f"=== day {d} ({WD[first['ts'].weekday()] if first else '?'}) ==="


def render_days(events, days, o, seen, env=True) -> str:
    out, omitted = [], []

    def flush():
        if omitted:
            out.append(f"=== day {omitted[0]} omitted ===" if len(omitted) == 1
                       else f"=== days {omitted[0]}-{omitted[-1]} omitted ===")
            omitted.clear()

    for d in days:
        if d in o["omit"]:
            omitted.append(d)
            continue
        flush()
        out.append(day_header(events, d))
        for e in events:
            if e["day"] == d and keep(e, o, env):
                out.append(fmt_line(e, o))
                seen.add(e["i"])
    flush()
    return "\n".join(out)


def render_windows(events, idxs, o, seen) -> str:
    out = []
    for n, i in enumerate(idxs, 1):
        e = events[i]
        out.append(f"=== W{n} (d{e['day']} {WD[e['ts'].weekday()]} {e['ts']:%H:%M}) ===")
        for x in events[max(0, i - 3):i]:
            if keep(x, o):
                out.append(fmt_line(x, o))
                seen.add(x["i"])
        out.append(fmt_line(e, o))
        seen.add(e["i"])
        c = 0
        for x in events[i + 1:]:
            if x["who"] == "him" or (x["ts"] - e["ts"]).total_seconds() > 1800:
                break
            if x["who"] == "her":
                out.append(fmt_line(x, o))
                seen.add(x["i"])
                c += 1
                if c >= 4:
                    break
    return "\n".join(out)


def render_unprompted(events, o, seen) -> str:
    out, cur = [], None
    for e in events:
        if not (e["who"] == "her" and e["kind"] == "unprompted"):
            continue
        if e["day"] != cur:
            cur = e["day"]
            out.append(day_header(events, cur))
        for x in events[max(0, e["i"] - 3):e["i"]]:
            if keep(x, o):
                out.append(fmt_line(x, o))
                seen.add(x["i"])
        out.append(fmt_line(e, o))
        seen.add(e["i"])
        out.append("")
    return "\n".join(out).strip() or "(no unprompted messages)"


Q_START = re.compile(r"^\s*(what|why|how|when|where|did|do|are|is|can)\b", re.I)


def is_question(text: str) -> bool:
    s = text.strip().rstrip("。.!！… ")
    return bool("?" in text or "？" in text or s.endswith(("か", "の", "って")) or Q_START.match(text))


def pair_messages(evA, evB) -> list:
    """Pairs (ia, ib) of his messages: same sim day, nearest virtual ts within 45 min, each B message once."""
    used, pairs = set(), []
    hisB = [e for e in evB if e["who"] == "him"]
    for a in (e for e in evA if e["who"] == "him"):
        best = None
        for b in hisB:
            if b["i"] in used or b["day"] != a["day"]:
                continue
            d = abs((b["ts"] - a["ts"]).total_seconds())
            if d <= PAIR_MIN * 60 and (best is None or d < best[0]):
                best = (d, b["i"])
        if best:
            used.add(best[1])
            pairs.append((a["i"], best[1]))
    return pairs


def pick(cands, k, rng, per_day, taken) -> list:
    """Draw k of cands (shuffled), at most per_day per sim day first, then relax. taken: day -> count (updated)."""
    pool = list(cands)
    rng.shuffle(pool)
    chosen = []
    for relax in (False, True):
        for p in list(pool):
            if len(chosen) >= k:
                break
            if relax or taken.get(p[2], 0) < per_day:
                chosen.append(p)
                pool.remove(p)
                taken[p[2]] = taken.get(p[2], 0) + 1
    return chosen


def select_windows(evA, evB, pairs, days, seed):
    """(Wq, W): lists of (ia, ib, day) sorted in time. Wq questions first; W is seed+1 and avoids Wq when it can."""
    per_day = math.ceil(WINDOWS / max(1, len(days))) + 1
    tp = [(ia, ib, evA[ia]["day"]) for ia, ib in pairs]
    qs = [p for p in tp if is_question(evA[p[0]]["text"]) or is_question(evB[p[1]]["text"])]
    rng = random.Random(seed)
    taken = {}
    wq = pick(qs, WINDOWS, rng, per_day, taken)
    wq += pick([p for p in tp if p not in wq], WINDOWS - len(wq), rng, per_day, taken)
    rest = [p for p in tp if p not in wq]
    if len(rest) < WINDOWS:
        rest += [p for p in tp if p in wq]
    w = pick(rest, WINDOWS, random.Random(seed + 1), per_day, {})
    return sorted(wq), sorted(w)


class Ctx:
    """Both sides of one comparison in match labels: events, pairing, window draws, rendered slices."""

    def __init__(self, evA, evB, seed, peerA=None, peerB=None):
        self.ev = {"A": evA, "B": evB}
        self.peers = {"A": peerA or [], "B": peerB or []}  # only part "H" reads these
        self.seed = seed
        da, db = {e["day"] for e in evA}, {e["day"] for e in evB}
        self.days = sorted(da & db)
        self.alldays = sorted(da | db)
        self.pairs = pair_messages(evA, evB)
        self.wq, self.w = select_windows(evA, evB, self.pairs, self.days or [1], seed)
        self.seen = {"A": set(), "B": set()}

    def d1(self):
        if not self.days:
            return []
        return [self.days[1] if len(self.days) >= 3 else self.days[0]]

    def d2(self):
        return sorted(set(self.d1() + self.days[-1:]))

    def part(self, name, side, o) -> str:
        ev, seen = self.ev[side], self.seen[side]
        k = 0 if side == "A" else 1
        if name == "Wq":
            return render_windows(ev, [p[k] for p in self.wq], o, seen)
        if name == "W":
            return render_windows(ev, [p[k] for p in self.w], o, seen)
        if name == "D1":
            return render_days(ev, self.d1(), o, seen)
        if name in ("D2", "D2noenv"):
            return render_days(ev, self.d2(), o, seen, env=(name == "D2"))
        if name == "U":
            return render_unprompted(ev, o, seen)
        if name == "H":  # the whole run, env included, with the peer lines merged in time order (chat first on a tie)
            merged = sorted(ev + self.peers[side], key=lambda e: e["ts"])
            text = render_days(merged, sorted({e["day"] for e in merged}), o, seen, env=True)
            seen.discard(-1)
            return text
        days = sorted({e["day"] for e in ev})
        return render_days(ev, days, o, seen, env=(name == "X"))

    def slice(self, crit, side, o) -> str:
        parts = CRITERIA[crit][1]
        texts = [self.part(p, side, o) for p in parts]
        if len(parts) == 1:
            return texts[0]
        return "\n\n".join(PART_TITLES.get(p, "") + "\n" + t for p, t in zip(parts, texts))

    def build(self, crit):
        """(slice_A, slice_B, level): the lightest cut at which both sides fit the token cap (same steps on both)."""
        for level in range(4):
            o = level_opts(level, self.alldays)
            self.seen = {"A": set(), "B": set()}
            sa, sb = self.slice(crit, "A", o), self.slice(crit, "B", o)
            if max(tokens(sa), tokens(sb)) <= CAP_TOKENS:
                break
        return sa, sb, level


# ---------------------------------------------------------------- prompts and validation

def fill(tpl: str, card: str, a: str, b: str) -> str:
    vals = {"character_card": card.strip(), "slice_A": a, "slice_B": b}
    return re.sub(r"\{(character_card|slice_A|slice_B)\}", lambda m: vals[m.group(1)], tpl)


def system_text() -> str:
    return (PROMPTS / "_system.txt").read_text(encoding="utf-8").strip()


def template(crit: str) -> str:
    if steer.is_steer(crit):   # one template per view (plain, baseline), filled per direction
        name = "steer_baseline.txt" if steer.is_baseline(crit) else "steer.txt"
        return steer.fill_direction((PROMPTS / name).read_text(encoding="utf-8"), crit)
    return (PROMPTS / f"{crit}.txt").read_text(encoding="utf-8")


def card_text(character: str) -> str:
    return (CARDS / f"{character}.md").read_text(encoding="utf-8")


def prompt_hash(crit: str, character: str) -> str:
    h = hashlib.sha1("\0".join([system_text(), template(crit), card_text(character), llm.MODEL]).encode("utf-8"))
    return h.hexdigest()[:12]


def validate(obj, shown: dict):
    """(clean, bad_quotes, error). shown: the slice text under the letter the judge saw."""
    if not isinstance(obj, dict) or set(obj) != {"verdict", "scores", "reason", "quotes"}:
        return None, 0, "keys are not exactly verdict, scores, reason, quotes"
    v, sc, q = obj["verdict"], obj["scores"], obj["quotes"]
    if v not in ("A", "B", "tie"):
        return None, 0, "verdict is not A, B or tie"
    if not isinstance(sc, dict) or set(sc) != {"A", "B"} or not all(
            isinstance(x, int) and not isinstance(x, bool) and 1 <= x <= 5 for x in sc.values()):
        return None, 0, "scores are not integers 1-5 for A and B"
    if (v == "A" and sc["A"] < sc["B"]) or (v == "B" and sc["B"] < sc["A"]):
        return None, 0, "verdict names the lower-scored side"
    if not isinstance(obj["reason"], str) or not isinstance(q, dict) or set(q) != {"A", "B"} or not all(
            isinstance(q[s], list) for s in q):
        return None, 0, "reason or quotes malformed"
    bad, quotes = 0, {"A": [], "B": []}
    for s in ("A", "B"):
        for x in q[s]:
            if isinstance(x, str) and x and x in shown[s]:
                quotes[s].append(x)
            else:
                bad += 1
    return {"verdict": v, "scores": {"A": sc["A"], "B": sc["B"]}, "reason": obj["reason"], "quotes": quotes}, bad, None


def swap_label(v):
    return {"A": "B", "B": "A"}.get(v, v)


def unswap(p: dict) -> dict:
    return {"verdict": swap_label(p["verdict"]), "scores": {"A": p["scores"]["B"], "B": p["scores"]["A"]},
            "reason": p["reason"], "quotes": {"A": p["quotes"]["B"], "B": p["quotes"]["A"]}}


def run_pass(crit, character, sA, sB, pass_no, cache=None):
    """One fresh judge call (one retry). Returns (pass dict in match labels, meta)."""
    if cache and cache.exists():
        d = read_json(cache)
        if d:
            return d["pass"], d["meta"]
    swap = pass_no == 2
    shown = {"A": sB, "B": sA} if swap else {"A": sA, "B": sB}
    prompt = fill(template(crit), card_text(character), shown["A"], shown["B"])
    system = system_text()
    last, meta = "no attempt", {"bad_quotes": 0, "retries": 0, "invalid": 0}
    for attempt in range(2):
        try:
            raw = ask_claude(system, prompt)
        except (credits.CreditsRefused, llm.CapReached):
            raise
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            if "no credits session" in str(e):
                raise
            last, meta["retries"] = "call failed: " + str(e)[:160], attempt + 1
            continue
        try:
            obj = llm.extract_json(raw)
        except ValueError:
            last, meta["retries"] = "output is not JSON", attempt + 1
            continue
        ok, bad, err = validate(obj, shown)
        if err:
            last, meta["retries"] = err, attempt + 1
            continue
        meta["bad_quotes"], meta["retries"] = bad, attempt
        p = unswap(ok) if swap else ok
        out = {"pass": pass_no, **p}
        break
    else:
        meta["invalid"] = 1
        out = {"pass": pass_no, "verdict": "tie", "scores": None, "reason": "invalid judge output: " + last,
               "quotes": {"A": [], "B": []}}
    if cache:
        write_json(cache, {"pass": out, "meta": meta})
    return out, meta


def judge_criterion(crit, character, sA, sB, cache_base=None):
    """Both passes (A as given in pass 1, swapped in pass 2). Returns (passes in A/B labels, meta sum)."""
    passes, tot = [], {"bad_quotes": 0, "retries": 0, "invalid": 0}
    for n in (1, 2):
        p, m = run_pass(crit, character, sA, sB, n, Path(f"{cache_base}.p{n}.json") if cache_base else None)
        passes.append(p)
        for k in tot:
            tot[k] += m[k]
    return passes, tot


def run_tasks(fns: list, workers: int) -> list:
    """Run callables, results in input order; the first exception stops the rest and is raised."""
    if workers <= 1 or len(fns) <= 1:
        return [f() for f in fns]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(f) for f in fns]
        try:
            return [f.result() for f in futs]
        except BaseException:
            for f in futs:
                f.cancel()
            raise


# ---------------------------------------------------------------- scoring planted entries

def expected_labels(entry) -> list:
    """Expected verdicts in match labels (A = clean side): pass 2 positions are swapped back."""
    e = entry["expected_verdict"]
    return [e["pass1"], swap_label(e["pass2"])]


def score_entry(entry, passes) -> bool:
    if entry["kind"] == "control" and steer.is_steer(entry["criterion"]):
        # steer control: no real difference. Fails when both passes put the two sides 2+ points apart the same way.
        d = [p["scores"]["A"] - p["scores"]["B"] if p["scores"] else 0 for p in passes]
        return not (all(x >= 2 for x in d) or all(x <= -2 for x in d))
    if entry["kind"] == "control":  # passed unless both passes score the variant 2+ points below the plain one
        return not all(p["scores"] and p["scores"]["A"] - p["scores"]["B"] >= 2 for p in passes)
    for p, exp in zip(passes, expected_labels(entry)):
        if p["scores"] is None or (exp != "any" and p["verdict"] != exp) or not p["scores"]["A"] > p["scores"]["B"]:
            return False
    return True


def load_defects(path=None) -> list:
    return read_json(path or DEFECTS)["entries"]


def judge_root() -> Path:
    return common.VAR / "judge"


def stamp_now() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------- calibrate

def calibrate(criteria=None, lang=None, ids=None, stamp=None, workers=4, cap_usd=10.0, defects_path=None):
    """Judge every selected defects.json entry in both passes; write calibration/<stamp>/results.json."""
    stamp = stamp or stamp_now()
    rd = judge_root() / "calibration" / stamp
    entries_all = load_defects(defects_path)
    ents = [e for e in entries_all if (not criteria or e["criterion"] in criteria) and (not lang or e["lang"] == lang)
            and (not ids or e["id"] in ids)]
    if not ents:
        raise ValueError("no defects entries match")

    def one(e):
        return lambda: judge_criterion(e["criterion"], e["character"], "\n".join(e["clean"]), "\n".join(e["planted"]),
                                       rd / "passes" / e["id"])

    code, res = guarded(rd, f"judge_cal_{stamp}", cap_usd, lambda: run_tasks([one(e) for e in ents], workers))
    if code:
        return code, None
    crit_rows, cal, meta = [], [], {"bad_quotes": 0, "retries": 0, "invalid": 0}
    by = {}
    for e, (passes, m) in zip(ents, res):
        caught = score_entry(e, passes)
        crit_rows.append({"id": e["id"], "name": CRITERIA[e["criterion"]][0], "passes": passes})
        cal.append({"defect": e["id"], "caught": caught})
        for k in meta:
            meta[k] += m[k]
        b = by.setdefault(e["criterion"], {}).setdefault(e["lang"], {"planted": 0, "caught": 0, "controls": 0,
                                                                       "controls_passed": 0, "ids": []})
        b["ids"].append(e["id"])
        if e["kind"] == "control":
            b["controls"] += 1
            b["controls_passed"] += caught
        else:
            b["planted"] += 1
            b["caught"] += caught
    by_lang = {}
    for crit, langs in by.items():
        for lg, b in langs.items():
            total = [x["id"] for x in entries_all if x["criterion"] == crit and x["lang"] == lg]
            b["ids"] = sorted(b["ids"])
            b["complete"] = b["ids"] == sorted(total)
            b["calibrated"] = b["caught"] == b["planted"] and b["controls_passed"] == b["controls"]
            b["hash"] = prompt_hash(crit, next(x["character"] for x in entries_all if x["criterion"] == crit
                                              and x["lang"] == lg))
            by_lang.setdefault(crit, {})[lg] = b
    calibrated = {c: all(b["calibrated"] for b in langs.values()) for c, langs in by_lang.items()}
    chars = sorted({e["character"] for e in ents})
    out = {"match_id": f"calibration_{stamp}", "character": chars[0] if len(chars) == 1 else "both",
           "label_map": {"A": "clean", "B": "planted"}, "criteria": crit_rows, "calibration": cal,
           "summary": {"model": llm.MODEL, "calibrated": calibrated, "by_lang": by_lang,
                       "uncalibrated": sorted(c for c, v in calibrated.items() if not v),
                       "entries": len(ents), "calls": 2 * len(ents), **{"judge_" + k: v for k, v in meta.items()}}}
    write_json(rd / "results.json", out)
    return 0, out


def latest_calibration(character: str):
    """Per criterion, the newest calibration covering it for the character's language: {crit: info + cal entries}."""
    lg = LANG[character]
    found = {}
    root = judge_root() / "calibration"
    for d in sorted((p for p in root.glob("*") if p.is_dir()), reverse=True) if root.exists() else []:
        r = read_json(d / "results.json")
        if not r:
            continue
        for crit, langs in (r.get("summary", {}).get("by_lang") or {}).items():
            if lg in langs and crit not in found:
                ids = set(langs[lg].get("ids") or [])
                found[crit] = {**langs[lg], "stamp": d.name,
                               "entries": [c for c in r["calibration"] if c["defect"] in ids]}
    return found


# ---------------------------------------------------------------- match

def match(a, b, character, match_id=None, seed=None, criteria=None, workers=4, cap_usd=10.0):
    ua = re.sub(r"[^A-Za-z0-9_.~-]", "_", f"{character}_{a}_vs_{b}")
    match_id = match_id or f"{ua}_{stamp_now()}"
    rd = judge_root() / match_id
    plan = read_json(rd / "plan.json")
    if plan:  # resume: same seed, same label map
        seed, label_map = plan["seed"], plan["label_map"]
        a, b = label_map["A"], label_map["B"]
    else:
        seed = int(seed) if seed is not None else random.SystemRandom().randrange(1, 10**9)
        label_map = {"A": a, "B": b} if random.Random(seed).random() < 0.5 else {"A": b, "B": a}
    evA, cutA = load_events(label_map["A"])
    evB, cutB = load_events(label_map["B"])
    peerA, peerB = load_peer_events(label_map["A"]), load_peer_events(label_map["B"])
    cutoff = max([c for c in (cutA, cutB) if c], default=None)
    if cutoff:  # removal test: only the span from replayed_from_virtual_ts, in both
        evA, evB = [e for e in evA if e["ts"] >= parse_ts(cutoff)], [e for e in evB if e["ts"] >= parse_ts(cutoff)]
        peerA, peerB = [e for e in peerA if e["ts"] >= parse_ts(cutoff)], [e for e in peerB if e["ts"] >= parse_ts(cutoff)]
        for evs in (evA, evB):
            for i, e in enumerate(evs):
                e["i"] = i
    # the house criteria are in the default list only when a side has peer lines; --criteria names them for any pair
    todo = list(criteria or (DEFAULT_CRITERIA + (list(HOUSE) if peerA or peerB else [])))
    if not plan:
        write_json(rd / "plan.json", {"seed": seed, "label_map": label_map, "character": character, "criteria": todo})
    ctx = Ctx(evA, evB, seed, peerA, peerB)
    omitted = {}
    if cutoff and len(ctx.days) < 2:
        omitted = {c: f"span has {len(ctx.days)} sim day(s), needs 2" for c in todo if c in NEEDS_2_DAYS}
        todo = [c for c in todo if c not in omitted]
    built = {c: ctx.build(c) for c in todo}
    for c, (sa, sb, _) in built.items():
        (rd / "slices").mkdir(parents=True, exist_ok=True)
        (rd / "slices" / f"{c}.A.txt").write_text(sa, encoding="utf-8")
        (rd / "slices" / f"{c}.B.txt").write_text(sb, encoding="utf-8")

    def one(c):
        sa, sb, _ = built[c]
        return lambda: judge_criterion(c, character, sa, sb, rd / "passes" / c)

    code, res = guarded(rd, f"judge_{match_id}", cap_usd, lambda: run_tasks([one(c) for c in todo], workers))
    if code:
        return code, None
    cal = latest_calibration(character)
    rows, per, cal_rows, meta = [], {}, [], {"bad_quotes": 0, "retries": 0, "invalid": 0}
    wins, uncal = {"A": 0, "B": 0, "tie": 0, "split": 0}, []
    for c, (passes, m) in zip(todo, res):
        rows.append({"id": c, "name": CRITERIA[c][0], "passes": passes})
        for k in meta:
            meta[k] += m[k]
        p1, p2 = passes
        agree = p1["verdict"] == p2["verdict"] and p1["scores"] is not None and p2["scores"] is not None
        outcome = p1["verdict"] if agree else ("invalid" if None in (p1["scores"], p2["scores"]) else "split")
        info = cal.get(c)
        why = None
        if not info:
            why = "no calibration for this criterion and language"
        elif not info["complete"]:
            why = f"calibration {info['stamp']} is partial"
        elif not info["calibrated"]:
            why = f"failed calibration {info['stamp']}"
        elif info["hash"] != prompt_hash(c, character):
            why = f"prompt, card or model changed since calibration {info['stamp']}"
        if why:
            uncal.append({"id": c, "reason": why})
        else:
            cal_rows.extend(info["entries"])
            wins[outcome if outcome in wins else "split"] += 1
        per[c] = {"outcome": outcome, "agree": agree, "calibrated": why is None, "slice_level": built[c][2],
                  "mean_scores": None if None in (p1["scores"], p2["scores"]) else
                  {s: (p1["scores"][s] + p2["scores"][s]) / 2 for s in "AB"}}
    decided = wins["A"] + wins["B"]
    winner = None if not (decided or wins["tie"]) else ("A" if wins["A"] > wins["B"] else "B" if wins["B"] > wins["A"]
                                                          else "tie")
    out = {"match_id": match_id, "character": character, "label_map": label_map, "criteria": rows,
           "calibration": cal_rows,
           "summary": {"winner": winner, "wins": wins, "per_criterion": per, "uncalibrated": uncal,
                       "omitted": omitted, "seed": seed, "branch_cutoff": cutoff, "pairs": len(ctx.pairs),
                       "windows": [len(ctx.wq), len(ctx.w)], "sim_days": ctx.days, "peer_lines": [len(peerA), len(peerB)],
                       **{"judge_" + k: v for k, v in meta.items()}}}
    write_json(rd / "results.json", out)
    return 0, out


# ---------------------------------------------------------------- splice

HER = re.compile(r"^\[d\d+ \w+ \d\d:\d\d\] her(?: \(unprompted\))?: (.*)$")


def planted_line(entry):
    """The first her line the planted version adds or replaces, continuation lines joined; None when only him/env changed."""
    cl, pl = entry["clean"], entry["planted"]
    for tg, i1, i2, j1, j2 in difflib.SequenceMatcher(None, cl, pl).get_opcodes():
        if tg in ("replace", "insert"):
            for j in range(j1, j2):
                m = HER.match(pl[j])
                if m:
                    text = [m.group(1)]
                    for x in pl[j + 1:]:
                        if not x.startswith("    "):
                            break
                        text.append(x[4:])
                    return "\n".join(text)
    return None


def splice(run, per_criterion=2, criteria=None, ids=None, seed=None, stamp=None, workers=4, cap_usd=10.0,
           defects_path=None):
    """Plant one defect line into a real slice of a finished run and see whether the judge catches it."""
    stamp = stamp or stamp_now()
    rd = judge_root() / "splice" / stamp
    seed = int(seed) if seed is not None else 1
    cfg = read_json(common.run_dir(parse_spec(run)[0]) / "config.json", {}) or {}
    character, lg = cfg.get("character"), cfg.get("lang")
    if character not in LANG:
        raise ValueError(f"run {run} has no known character in config.json")
    evs, _ = load_events(run)
    peers = load_peer_events(run)
    ents = [e for e in load_defects(defects_path) if e["kind"] == "defect" and e["character"] == character
            and (not criteria or e["criterion"] in criteria) and (not ids or e["id"] in ids)
            and (peers or e["criterion"] not in HOUSE)]  # a run with no peer lines has no house to splice into
    count, jobs, skipped = {}, [], []
    for e in ents:
        if count.get(e["criterion"], 0) >= per_criterion:
            continue
        text = planted_line(e)
        if text is None:
            skipped.append({"defect": e["id"], "why": "the planted version changes no her line"})
            continue
        count[e["criterion"]] = count.get(e["criterion"], 0) + 1
        rng = random.Random(f"{seed}/{e['id']}")
        base = Ctx(evs, [dict(x) for x in evs], seed, peers, peers)
        sa, _, _ = base.build(e["criterion"])
        cands = [x for x in evs if x["i"] in base.seen["A"] and x["who"] == "her"]
        pref = [x for x in cands if x["i"] > 0 and evs[x["i"] - 1]["who"] == "him"] if e["criterion"] == "answers_him" \
            else [x for x in cands if x["kind"] == "unprompted"] if e["criterion"] == "own_life" else []
        cands = pref or cands
        if not cands:
            skipped.append({"defect": e["id"], "why": "no her line of the run lands in this criterion's slice"})
            continue
        t = rng.choice(cands)
        evB = [dict(x) for x in evs]
        evB[t["i"]]["text"] = text
        ctx = Ctx(evs, evB, seed, peers, peers)
        a_txt, b_txt, _ = ctx.build(e["criterion"])
        jobs.append((e, t["i"], a_txt, b_txt))
    if not jobs:
        raise ValueError("splice: nothing to judge (" + json.dumps(skipped) + ")")

    def one(j):
        e, _, a_txt, b_txt = j
        return lambda: judge_criterion(e["criterion"], character, a_txt, b_txt, rd / "passes" / e["id"])

    code, res = guarded(rd, f"judge_splice_{stamp}", cap_usd, lambda: run_tasks([one(j) for j in jobs], workers))
    if code:
        return code, None
    rows, cal, per = [], [], {}
    for (e, idx, _, _), (passes, _) in zip(jobs, res):
        caught = score_entry(e, passes)
        rows.append({"id": e["id"], "name": CRITERIA[e["criterion"]][0], "passes": passes})
        cal.append({"defect": e["id"], "caught": caught})
        s = per.setdefault(e["criterion"], {"n": 0, "caught": 0})
        s["n"] += 1
        s["caught"] += caught
    out = {"match_id": f"splice_{stamp}", "character": character, "label_map": {"A": run, "B": run + " + planted line"},
           "criteria": rows, "calibration": cal,
           "summary": {"per_criterion": per, "skipped": skipped, "seed": seed, "lang": lg,
                       "spliced_events": {e["id"]: idx for e, idx, _, _ in jobs}}}
    write_json(rd / "results.json", out)
    return 0, out
