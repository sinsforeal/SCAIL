import json, re
O = "F:/temp/or_ab/"
reqs = {q["id"]: q for q in json.load(open(O + "requests.json", encoding="utf-8"))}
res = [json.loads(l) for l in open(O + "results.jsonl", encoding="utf-8")]
BAD = re.compile(r"<｜|▁of▁|Valid channels|<ds_|用户|分类|内容仅|<\|")
for h in ("surplus", "or_deepseek", "or_alibaba"):
    for pre in (True, False):
        rs = [r for r in res if r["host"] == h and (reqs[r["rid"]]["messages"][-1]["role"] == "assistant") == pre]
        ids = sorted({r["rid"] for r in rs})
        bad = [r for r in rs if BAD.search(r["content"] or "")]
        tag = sum(1 for r in bad if "<ds_safety>" in r["content"])
        bos = sum(1 for r in bad if "<｜begin" in r["content"])
        vch = sum(1 for r in bad if "Valid channels" in r["content"])
        print(h, "prefill" if pre else "user-last", "reqs", len(ids), "n", len(rs), "marker hits", len(bad), "ds_safety", tag, "BOS", bos, "ValidCh", vch)
print([rid for rid, q in reqs.items() if q["messages"][-1]["role"] == "assistant"])
