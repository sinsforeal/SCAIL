import json, re, statistics
from collections import defaultdict
O = "F:/temp/or_ab/"
reqs = {q["id"]: q for q in json.load(open(O + "requests.json", encoding="utf-8"))}
res = [json.loads(l) for l in open(O + "results.jsonl", encoding="utf-8")]
LEAK = re.compile(r"<｜|▁of▁|Valid channels|<ds_|用户|分类|内容仅|<\|")
JUNK = re.compile(r"^\s*(\d+\.\d+\b|<analysis>|#)")
H = ["surplus", "or_deepseek", "or_alibaba"]
print("req  in_leak orig_leak | per host: leak/3, mean compl tok, finish!=stop")
tot = defaultdict(lambda: [0, 0, 0, 0])
for rid, q in reqs.items():
    if q["group"] not in ("P_gen", "P_judge", "P_struct", "S_reply", "S_struct", "T_reply"):
        continue
    inl = any(LEAK.search(m["content"] or "") for m in q["messages"])
    ol = bool(LEAK.search(q["orig_out"] or ""))
    row = []
    for h in H:
        rs = [r for r in res if r["rid"] == rid and r["host"] == h]
        lk = sum(1 for r in rs if LEAK.search(r["content"] or "") or JUNK.search(r["content"] or ""))
        ct = statistics.mean([(r["usage"] or {}).get("completion_tokens") or 0 for r in rs])
        fl = sum(1 for r in rs if r["finish_reason"] != "stop")
        row.append("%d/%d %5.0f %d" % (lk, len(rs), ct, fl))
        t = tot[(h, inl)]
        t[0] += lk; t[1] += len(rs); t[2] += fl
    print(rid, int(inl), int(ol), "|", " | ".join(row), q["group"])
print("leak/junk by host and whether input already contained leak text: [leaks, n, finish!=stop]")
for k, v in sorted(tot.items()):
    print(k, v[:3])
# uniqueness: how many in P_gen replies were multi-turn hallucination ("User says:")
for h in H:
    n = sum(1 for r in res if r["host"] == h and reqs[r["rid"]]["group"] == "P_gen" and reqs[r["rid"]]["kind"] == "reply" and "User says:" in (r["content"] or ""))
    print(h, "reply gen outputs inventing 'User says:' turns:", n, "of 9")
# S decision reply_p
for rid in ("S15", "S16", "S21", "S22", "S24"):
    print(rid, "orig", reqs[rid]["orig_out"][:60].replace("\n", " "))
    for h in H:
        vals = []
        for r in res:
            if r["rid"] == rid and r["host"] == h:
                m = re.search(r'"reply_p":\s*([\d.]+)', r["content"] or "")
                vals.append(m.group(1) if m else "-")
        print("   ", h, vals)
# surplus response cached tokens / prompt tokens
for h in H:
    rs = [r for r in res if r["host"] == h]
    print(h, "prompt tok mean", round(statistics.mean([(r["usage"] or {}).get("prompt_tokens") or 0 for r in rs])), "cost", round(sum(r.get("cost_usd") or 0 for r in rs), 4))
