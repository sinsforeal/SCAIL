"""What the model work costs: calls, tokens and dollars by day and by role.

Reads every `llm_calls.jsonl` under `logs/` (the zipped runs too) and prices
each call. The host's own figure comes first: an OpenRouter answer carries
`usage.cost` (USD, for that call, at whatever the serving host charged), and
that is the truth for the call. A row without it is priced from the slug
that answered (`model` on the row, since 2026-08-31) at OpenRouter's
published per-token rates below; a row with neither -- the official DeepSeek
endpoint before the move -- at DeepSeek's old list rates, off-peak.
`python tools/llmstats.py [--days N] [--roles]`, or `/stats` from the ops bar.

OPENROUTER is USD per 1M tokens (prompt, completion, cached prompt), read
from https://openrouter.ai/api/v1/models on 2026-09-03. `python
tools/llmstats.py --refresh` re-reads it and prints the table to paste in.
"""
import datetime
import glob
import io
import json
import os
import sys
import zipfile
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OPENROUTER = {   # slug: (prompt, completion, cached prompt) USD per 1M tokens
    "deepseek/deepseek-v4-flash-0731": (0.065, 0.18, 0.016),
    "deepseek/deepseek-v4-flash": (0.079, 0.159, 0.016),
    "deepseek/deepseek-v4-pro": (1.031, 2.062, 0.086),
    "moonshotai/kimi-k3": (3.0, 15.0, 0.30),
    "qwen/qwen3.8-flash": (0.15, 0.47, 0.016),
    "deepseek/deepseek-v4-pro-0813": (0.5795, 1.7384, 0.0193),
    "google/gemini-3.8-flash": (0.75, 3.75, 0.075),
    "z-ai/glm-5.3-flash": (0.075, 0.25, 0.015),
    "z-ai/glm-5.3": (1.4, 4.4, 0.14),
    "sakana/sakana-namazu": (0.95, 4.0, 0.15),
}
# the official endpoint before 2026-08-31, off-peak list rates (hit, miss, out)
DEEPSEEK_LEGACY = {
    "deepseek-v4-flash": (0.007, 0.22, 0.66),
    "deepseek-v4-pro": (0.022, 0.66, 1.98),
}


def _cost(row, usage):
    """USD for one call: the host's figure, else the slug's rates, else legacy."""
    c = usage.get("cost")
    if c is None:
        c = ((usage.get("cost_details") or {}).get("upstream_inference_cost"))
    if c is not None:
        try:
            return float(c), "host"
        except (TypeError, ValueError):
            pass
    prompt = int(usage.get("prompt_tokens") or 0)
    out = int(usage.get("completion_tokens") or 0)
    cached = int(((usage.get("prompt_tokens_details") or {}).get("cached_tokens")) or usage.get("prompt_cache_hit_tokens") or 0)
    slug = str(row.get("model") or "")
    if slug in OPENROUTER:
        p_in, p_out, p_cache = OPENROUTER[slug]
        return (max(0, prompt - cached) * p_in + cached * p_cache + out * p_out) / 1e6, "rates"
    base = slug.split("/")[-1].replace("-0731", "") if slug else "deepseek-v4-flash"
    hit, miss, po = DEEPSEEK_LEGACY.get(base, DEEPSEEK_LEGACY["deepseek-v4-flash"])
    h = int(usage.get("prompt_cache_hit_tokens") or 0)
    m = usage.get("prompt_cache_miss_tokens")
    if m is None:
        m = prompt - h
    return (h * hit + m * miss + out * po) / 1e6, "legacy"


def _files():
    """Every llm_calls.jsonl on disk, live or zipped, as (name, text stream)."""
    logs = os.path.join(ROOT, "logs")
    for z in sorted(glob.glob(os.path.join(logs, "*.zip"))):
        try:
            zf = zipfile.ZipFile(z)
            for n in zf.namelist():
                if n.endswith("llm_calls.jsonl"):
                    yield z, io.TextIOWrapper(zf.open(n), encoding="utf-8", errors="replace")
        except zipfile.BadZipFile:
            continue
    for p in sorted(glob.glob(os.path.join(logs, "*", "llm_calls.jsonl"))):
        yield p, open(p, encoding="utf-8", errors="replace")


def gather(days=7):
    """{day: {...}}, {role: {...}}, {model: {...}} over the last `days` machine-local days."""
    since = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
    blank = lambda: {"calls": 0, "prompt": 0, "cached": 0, "out": 0, "secs": 0.0, "usd": 0.0, "empty": 0,
                     "host": 0, "rates": 0, "legacy": 0}
    by_day, by_role, by_model = defaultdict(blank), defaultdict(blank), defaultdict(blank)
    for _name, fh in _files():
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            wall = str(d.get("wall", ""))
            day = wall[:10]
            if day < since:
                continue
            u = d.get("usage") or {}
            role = d.get("role", "?")
            usd, how = _cost(d, u)
            cached = int(((u.get("prompt_tokens_details") or {}).get("cached_tokens")) or u.get("prompt_cache_hit_tokens") or 0)
            for b in (by_day[day], by_role[role], by_model[str(d.get("model") or "(official)")]):
                b["calls"] += 1
                b["prompt"] += int(u.get("prompt_tokens") or 0)
                b["cached"] += cached
                b["out"] += int(u.get("completion_tokens") or 0)
                b["secs"] += d.get("seconds") or 0
                b["usd"] += usd
                b["empty"] += 0 if (d.get("content") or "").strip() else 1
                b[how] += 1
    return dict(by_day), dict(by_role), dict(by_model)


def report(days=7, config=None, roles=True):
    by_day, by_role, by_model = gather(days)
    if not by_day:
        return f"no model calls on disk in the last {days} day(s)"
    out = [f"model calls, last {days} day(s) (USD: the host's own figure per call where the log has it, "
           f"else OpenRouter's published rates for the slug that answered):",
           f"{'day':10} {'calls':>6} {'prompt':>10} {'cached':>7} {'output':>8} {'api s':>6} {'usd':>7}"]
    tot = {"calls": 0, "prompt": 0, "cached": 0, "out": 0, "secs": 0.0, "usd": 0.0, "empty": 0, "host": 0, "rates": 0, "legacy": 0}
    for day in sorted(by_day):
        b = by_day[day]
        out.append(f"{day:10} {b['calls']:>6} {b['prompt']/1e6:>9.2f}M {100*b['cached']/max(1,b['prompt']):>6.0f}% "
                   f"{b['out']/1e3:>7.0f}k {b['secs']:>6.0f} {b['usd']:>7.2f}")
        for k in tot:
            tot[k] += b[k]
    out.append(f"{'total':10} {tot['calls']:>6} {tot['prompt']/1e6:>9.2f}M {100*tot['cached']/max(1,tot['prompt']):>6.0f}% "
               f"{tot['out']/1e3:>7.0f}k {tot['secs']:>6.0f} {tot['usd']:>7.2f}")
    n = max(1, len(by_day))
    out.append(f"per day: {tot['calls']/n:.0f} calls, {tot['prompt']/n/1e6:.2f}M prompt tokens, "
               f"{tot['out']/n/1e3:.0f}k output, ${tot['usd']/n:.2f}; {tot['empty']} empty answer(s) in the window; "
               f"priced by the host {tot['host']}, by rates {tot['rates']}, legacy {tot['legacy']}")
    out.append("")
    out.append(f"{'model':34} {'calls':>6} {'prompt/call':>12} {'out/call':>9} {'usd':>7} {'usd/call':>9}")
    for m, b in sorted(by_model.items(), key=lambda kv: -kv[1]["usd"]):
        out.append(f"{m[:34]:34} {b['calls']:>6} {b['prompt']//max(1,b['calls']):>12,} {b['out']//max(1,b['calls']):>9,} "
                   f"{b['usd']:>7.2f} {b['usd']/max(1,b['calls']):>9.4f}")
    if roles and by_role:
        out.append("")
        out.append(f"{'role':18} {'calls':>6} {'prompt/call':>12} {'cached':>7} {'out/call':>9} {'usd':>7}")
        for r, b in sorted(by_role.items(), key=lambda kv: -kv[1]["usd"])[:16]:
            out.append(f"{r:18} {b['calls']:>6} {b['prompt']//max(1,b['calls']):>12,} "
                       f"{100*b['cached']/max(1,b['prompt']):>6.0f}% {b['out']//max(1,b['calls']):>9,} {b['usd']:>7.2f}")
    return "\n".join(out)


def refresh():
    """Read OpenRouter's public price list for the slugs in the table and
    print the table to paste in. No key needed."""
    import urllib.request
    data = json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30))["data"]
    for m in data:
        if m["id"] in OPENROUTER:
            p = m.get("pricing") or {}
            f = lambda k: round(float(p.get(k) or 0) * 1e6, 4)
            print(f'    "{m["id"]}": ({f("prompt")}, {f("completion")}, {f("input_cache_read")}),')


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)
    sys.stdout.reconfigure(encoding="utf-8")
    if "--refresh" in sys.argv:
        refresh()
        sys.exit(0)
    days = 7
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    print(report(days, None, roles=True))
