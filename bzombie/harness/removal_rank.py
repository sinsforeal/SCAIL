"""Rank the parts of her mind by what they cost, to pick removal-test targets (tk-lmv step 1).

python -m bzombie.harness.removal_rank <run_id> [<run_id> ...] [--json out.json]

Per run (read-only): calls, prompt tokens and cost per role (the role of a call comes from the traces' `calls`
lists: calls.jsonl rows carry no role), and the mean characters each trace input (prompt section) puts into her
reply prompt. Roles and sections are mapped to config sections by ROLE_SECTION / SECTION_SECTION below.
"""
from __future__ import annotations

import collections
import json
import sys

from ..common import read_json, read_jsonl, run_dir

# role of an llm call -> the config section whose `enabled` gates it (None: not a removable mind part)
ROLE_SECTION = {
    "foresee": "foresight", "commit_him": "commitments", "scene_director": "scene_director",
    "recall": "recall", "coherence": "coherence", "episode_cards": "episodes", "timeline": None,
    "morning": "morning", "weekly": "weekly", "editor": None, "state": None, "gloss": None, "persona": None,
    "watch_pick": None, "spiral": "spiral", "wonder": "wonder", "reflect": "reflect", "withhold": "withholding",
    "diary": "diary", "settle_beliefs": "beliefs", "expect_him": "expect", "approach": "approach",
}
# trace input name (prompt section) -> config section
SECTION_SECTION = {
    "primitives": "primitives", "goals": "goals", "gate": "attachment", "feel": "emotion", "his_mood": "sentiment",
    "rhythm": "rhythm", "yesterday": "diary", "morning": "morning", "recall": "recall", "digest": "phone",
    "ledger": "ledger", "scene": "scene_director", "shape_of_day": "schedule", "today": "agenda",
}


def role_map(run_id: str) -> dict:
    rd = run_dir(run_id)
    m = {}
    for p in (rd / "traces").glob("*.json"):
        t = read_json(p) or {}
        for c in t.get("calls", []):
            m[c["call_id"]] = c.get("role") or "(blank)"
    return m


def by_role(run_id: str) -> dict:
    m = role_map(run_id)
    out = collections.defaultdict(lambda: {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_micro": 0})
    for r in read_jsonl(run_dir(run_id) / "calls.jsonl"):
        if r.get("endpoint") != "chat/completions":
            role = "(embeddings)"
        else:
            role = m.get(r["call_id"], "(not in a trace)")
        u = r.get("usage") or {}
        o = out[role]
        o["calls"] += 1
        o["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
        o["completion_tokens"] += int(u.get("completion_tokens") or 0)
        o["cost_micro"] += int(r.get("cost_micro") or 0)
    return dict(out)


def section_chars(run_id: str) -> dict:
    """Mean chars of each trace input name over the traces that carry it, and in how many traces it shows."""
    n = 0
    tot, cnt = collections.Counter(), collections.Counter()
    for p in (run_dir(run_id) / "traces").glob("*.json"):
        t = read_json(p) or {}
        if "inputs" not in t:
            continue
        n += 1
        seen = collections.Counter()
        for i in t["inputs"]:
            tot[i.get("name", "?")] += len(i.get("text", ""))
            seen[i.get("name", "?")] += 1
        for k in seen:
            cnt[k] += 1
    return {k: {"mean_chars_per_trace": round(tot[k] / max(n, 1), 1), "in_traces": cnt[k], "traces": n} for k in tot}


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    js = a[a.index("--json") + 1] if "--json" in a else None
    runs = [x for i, x in enumerate(a) if x != "--json" and (i == 0 or a[i - 1] != "--json")]
    res = {r: {"roles": by_role(r), "sections": section_chars(r)} for r in runs}
    allroles = collections.defaultdict(lambda: collections.Counter())
    for r, d in res.items():
        for role, v in d["roles"].items():
            allroles[role].update(v)
    print("per role, summed over", ", ".join(runs))
    for role, v in sorted(allroles.items(), key=lambda kv: -kv[1]["calls"]):
        print(f"  {role:18} calls {v['calls']:5} prompt_tok {v['prompt_tokens']:8} cost_micro {v['cost_micro']:7} "
              f"-> {ROLE_SECTION.get(role)}")
    names = sorted({k for d in res.values() for k in d["sections"]})
    print("mean chars per trace of each prompt section (mean over runs)")
    for k in sorted(names, key=lambda k: -sum(d["sections"].get(k, {}).get("mean_chars_per_trace", 0) for d in res.values())):
        v = [d["sections"][k]["mean_chars_per_trace"] for d in res.values() if k in d["sections"]]
        print(f"  {k:30} {sum(v) / len(v):7.1f}  (section {SECTION_SECTION.get(k)})")
    if js:
        with open(js, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
