import json, re, sys, random, statistics, os
from collections import Counter, defaultdict
OUT = "F:/temp/or_ab/"
reqs = {q["id"]: q for q in json.load(open(OUT + "requests.json", encoding="utf-8"))}
res = [json.loads(l) for l in open(OUT + "results.jsonl", encoding="utf-8")]
HOSTS = ["surplus", "or_deepseek", "or_alibaba"]
LEAK = re.compile(r"<｜|▁of▁|Valid channels|<ds_|用户|分类|内容仅|<\|")

def strip_fence(s):
    s = (s or "").strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.S)
    return m.group(1) if m else s

def parse(s):
    try:
        return json.loads(strip_fence(s)), json.loads((s or "").strip()) if True else None
    except Exception:
        try:
            return json.loads(strip_fence(s)), None
        except Exception:
            return None, None

def ja_purity(s):
    letters = re.findall(r"[A-Za-z]", s or "")
    jp = re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]", s or "")
    tot = len(letters) + len(jp)
    return (len(letters) / tot) if tot else 0.0

def grade(q, txt):
    c = q["check"]; t = (txt or "").strip()
    if c["type"] == "num":
        nums = re.findall(r"\d[\d,]*", t)
        return bool(nums) and nums[-1].replace(",", "") == c["answer"]
    if c["type"] == "word":
        return c["answer"].lower() in t.lower() and len(t) < 80
    if c["type"] == "json":
        try:
            j = json.loads(strip_fence(t))
        except Exception:
            return False
        return j == c["answer"]
    return False

if sys.argv[1] == "blind":
    random.seed(20261022)
    items = []
    for r in res:
        q = reqs[r["rid"]]
        if q["kind"] == "reply" and not r.get("error"):
            items.append((r["rid"], r["host"], r["k"], r.get("content") or ""))
    for rid, q in reqs.items():
        if q["kind"] == "reply":
            items.append((rid, "ORIGINAL", 0, q["orig_out"]))
    random.shuffle(items)
    key = {}
    lines = ["# blind sheet (ratings: 2 takes up his last line, 1 partly, 0 ignores it)", ""]
    for i, (rid, host, k, txt) in enumerate(items):
        lab = "L%03d" % i
        key[lab] = {"rid": rid, "host": host, "k": k}
        q = reqs[rid]
        lines.append("## %s" % lab)
        lines.append("HIS LAST LINE: %s" % (q["his_last"] or "").replace("\n", " / ")[:300])
        lines.append("OUTPUT: %s" % (txt or "<empty>")[:500].replace("\n", " / "))
        lines.append("")
    open(OUT + "blind.md", "w", encoding="utf-8").write("\n".join(lines))
    json.dump(key, open(OUT + "blind_key.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(len(items), "items")
    sys.exit()

# report
by = defaultdict(list)
for r in res:
    by[r["host"]].append(r)
ratings = json.load(open(OUT + "ratings.json")) if os.path.exists(OUT + "ratings.json") else {}
key = json.load(open(OUT + "blind_key.json", encoding="utf-8")) if os.path.exists(OUT + "blind_key.json") else {}
rate_by = defaultdict(list)
rate_by_req = defaultdict(lambda: defaultdict(list))
for lab, v in ratings.items():
    kk = key[lab]
    rate_by[kk["host"]].append(v)
    rate_by_req[kk["rid"]][kk["host"]].append(v)
out = {}
for h in HOSTS:
    L = by[h]
    ok = [r for r in L if not r.get("error") and r.get("content") is not None]
    d = {"n": len(L), "ok": len(ok), "errors": Counter((r.get("error") or "")[:60] for r in L if r.get("error")).most_common(4)}
    d["empty"] = sum(1 for r in ok if not (r["content"] or "").strip())
    d["finish"] = dict(Counter(r.get("finish_reason") for r in ok))
    d["models"] = dict(Counter(r.get("model_returned") for r in ok))
    d["providers"] = dict(Counter(r.get("provider_returned") for r in ok))
    d["has_reasoning"] = sum(1 for r in ok if r.get("has_reasoning"))
    lat = [r["latency_s"] for r in ok]
    d["lat_med"] = round(statistics.median(lat), 2) if lat else None
    d["lat_mean"] = round(statistics.mean(lat), 2) if lat else None
    d["cost"] = round(sum((r.get("cost_usd") or 0) for r in L), 4)
    d["compl_tok_mean"] = round(statistics.mean([(r["usage"] or {}).get("completion_tokens") or 0 for r in ok]), 1) if ok else None
    d["out_chars_mean"] = round(statistics.mean([len(r["content"] or "") for r in ok]), 1) if ok else None
    # leak
    d["leak"] = [(r["rid"], r["k"]) for r in ok if LEAK.search(r["content"] or "")]
    # structured
    st = [r for r in ok if reqs[r["rid"]]["orig_keys"]]
    valid = keyok = 0
    for r in st:
        j, strict = parse(r["content"])
        if j is not None and isinstance(j, dict):
            valid += 1
            if set(reqs[r["rid"]]["orig_keys"]) <= set(j.keys()):
                keyok += 1
    d["struct_n"] = len(st); d["json_valid"] = valid; d["keys_ok"] = keyok
    d["struct_bad"] = [(r["rid"], r["k"]) for r in st if not (parse(r["content"])[0] and isinstance(parse(r["content"])[0], dict) and set(reqs[r["rid"]]["orig_keys"]) <= set(parse(r["content"])[0].keys()))]
    d["struct_strict_fail"] = sum(1 for r in st if parse(r["content"])[1] is None)
    # sanity
    sa = [r for r in ok if reqs[r["rid"]]["kind"] == "sanity"]
    d["sanity_n"] = len(sa); d["sanity_ok"] = sum(1 for r in sa if grade(reqs[r["rid"]], r["content"]))
    d["sanity_fail"] = [(r["rid"], r["k"], (r["content"] or "")[:60]) for r in sa if not grade(reqs[r["rid"]], r["content"])]
    # ja purity on free-text ja generator outputs
    ft = [r for r in ok if reqs[r["rid"]]["kind"] in ("reply", "unprompted") and reqs[r["rid"]]["lang"] == "ja"]
    d["ja_latin_ratio"] = round(statistics.mean([ja_purity(r["content"]) for r in ft]), 3) if ft else None
    d["ja_latin_gt10"] = sum(1 for r in ft if ja_purity(r["content"]) > 0.1)
    d["reply_ratings"] = {"n": len(rate_by[h]), "mean": round(statistics.mean(rate_by[h]), 2) if rate_by[h] else None, "dist": dict(Counter(rate_by[h]))}
    out[h] = d
d = {"reply_ratings": {"n": len(rate_by["ORIGINAL"]), "mean": round(statistics.mean(rate_by["ORIGINAL"]), 2) if rate_by["ORIGINAL"] else None, "dist": dict(Counter(rate_by["ORIGINAL"]))}}
out["ORIGINAL"] = d
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
print("PER REQUEST RATINGS")
for rid, dd in rate_by_req.items():
    print(rid, {h: v for h, v in dd.items()})
