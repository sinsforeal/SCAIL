import json, os, sys, time, glob, threading, urllib.request, urllib.error, random
from concurrent.futures import ThreadPoolExecutor
os.chdir("F:/REPS2/SCAILV4")
OUT = "F:/temp/or_ab/"
RUNS = "var/bzombie/runs/"
N_SAMPLES = 3

def rows(run):
    return [json.loads(l) for l in open(RUNS + run + "/calls.jsonl", encoding="utf-8")]

def transcript(run):
    return [json.loads(l) for l in open(RUNS + run + "/transcript.jsonl", encoding="utf-8")]

def his_last(run, vts):
    last = None
    for t in transcript(run):
        if t["who"] == "him" and t["virtual_ts"][:19] <= vts[:19]:
            last = t["text"]
    return last

def mk(group, rid, run, idx, r, kind, tr=None):
    s = dict(r["request_sent"])
    for k in ("stream", "stream_options", "seed", "tools", "tool_choice"):
        s.pop(k, None)
    out = r["response"]["choices"][0]["message"].get("content") or ""
    keys = None
    try:
        j = json.loads(out)
        if isinstance(j, dict):
            keys = sorted(j.keys())
    except Exception:
        pass
    d = {"id": rid, "group": group, "run": run, "idx": idx, "call_id": r["call_id"], "kind": kind,
         "messages": s["messages"], "temperature": s.get("temperature"), "max_tokens": s.get("max_tokens") or 8192,
         "orig_max_tokens": s.get("max_tokens"), "ctk": s.get("chat_template_kwargs"),
         "orig_out": out, "orig_keys": keys, "orig_usage": r.get("usage"),
         "his_last": his_last(run, r["virtual_ts"]) if kind == "reply" else None,
         "lang": "en" if tr else "ja"}
    return d

def build():
    reqs = []
    P = rows("bz_p_e2e_live_7530")
    # P generator (reply/garbage) calls: 3 messages or leaking outputs
    for idx, kind in [(348, "reply"), (502, "reply"), (426, "reply"), (269, "unprompted"), (336, "struct"), (414, "struct"), (489, "struct")]:
        reqs.append(mk("P_gen", "P%d" % idx, "bz_p_e2e_live_7530", idx, P[idx], kind))
    for idx in (270, 349, 503):
        reqs.append(mk("P_judge", "P%d" % idx, "bz_p_e2e_live_7530", idx, P[idx], "struct"))
    for idx in (262, 263, 275, 279, 280, 281, 295, 298, 333, 338, 339, 341, 352, 357, 417):
        reqs.append(mk("P_struct", "P%d" % idx, "bz_p_e2e_live_7530", idx, P[idx], "struct"))
    S = rows("bz_s_momoka_d1b")
    reqs.append(mk("S_reply", "S14", "bz_s_momoka_d1b", 14, S[14], "reply"))
    for idx in (2, 10, 13, 15, 16, 20, 21, 22, 23, 24):
        reqs.append(mk("S_struct", "S%d" % idx, "bz_s_momoka_d1b", idx, S[idx], "struct"))
    T = rows("bz_s_tomoe_d1c")
    for idx in (4, 35, 42, 77):
        reqs.append(mk("T_reply", "T%d" % idx, "bz_s_tomoe_d1c", idx, T[idx], "reply", tr=True))
    # sanity
    san = [
        ("What is 17 * 23? Answer with only the number.", "num", "391"),
        ("What is 1234 + 5678? Answer with only the number.", "num", "6912"),
        ("What is 15 percent of 240? Answer with only the number.", "num", "36"),
        ("What is the capital of Australia? Answer with one word.", "word", "canberra"),
        ("太郎は花子に本を貸した。花子は翌日、その本を次郎に貸した。いま本を持っているのは誰か。名前だけ答えて。", "word", "次郎"),
        ("田中さんは山田さんより背が高く、山田さんは佐藤さんより背が高い。一番背が低いのは誰か。名前だけ答えて。", "word", "佐藤"),
        ("Reverse the string 'stressed'. Answer with only the reversed string.", "word", "desserts"),
        ("How many days does February have in a leap year? Answer with only the number.", "num", "29"),
        ("Return only a JSON object with keys name (string), age (integer), tags (array of two strings) for a person called Ann, aged 31, with tags x and y. No other text.", "json", {"name": "Ann", "age": 31, "tags": ["x", "y"]}),
        ("Order #4471: 3 apples at 120 yen each, 2 pears at 200 yen each. Return only a JSON object with keys order_id (integer) and total_yen (integer, the total price). No other text.", "json", {"order_id": 4471, "total_yen": 760}),
    ]
    for i, (q, k, a) in enumerate(san):
        reqs.append({"id": "Q%d" % i, "group": "sanity", "run": None, "idx": None, "call_id": None, "kind": "sanity",
                     "messages": [{"role": "user", "content": q}], "temperature": 0.0, "max_tokens": 1024,
                     "orig_max_tokens": None, "ctk": None, "orig_out": None, "orig_keys": None, "orig_usage": None,
                     "his_last": None, "lang": "en", "check": {"type": k, "answer": a}})
    return reqs

HOSTS = {
    "surplus": {"base": "https://api.surplusintelligence.ai/v1", "keyfile": "secerts/surplus.txt", "workers": 4},
    "or_deepseek": {"base": "https://openrouter.ai/api/v1", "keyfile": "secerts/openrouter.txt", "workers": 5, "prov": "deepseek"},
    "or_alibaba": {"base": "https://openrouter.ai/api/v1", "keyfile": "secerts/openrouter.txt", "workers": 5, "prov": "alibaba"},
}

def body_for(host, q):
    h = HOSTS[host]
    b = {"messages": q["messages"], "max_tokens": q["max_tokens"], "stream": False}
    if q["temperature"] is not None:
        b["temperature"] = q["temperature"]
    if host == "surplus":
        b["model"] = "deepseek-v4.1-flash-1017"
        b["reasoning_effort"] = "none"
        if q["ctk"]:
            b["chat_template_kwargs"] = q["ctk"]
    else:
        b["model"] = "deepseek/deepseek-v4.1-flash-1017"
        b["reasoning"] = {"enabled": False}
        b["provider"] = {"order": [h["prov"]], "allow_fallbacks": False}
        b["usage"] = {"include": True}
    return b

lock = threading.Lock()
spent = {"surplus": 0.0, "or_deepseek": 0.0, "or_alibaba": 0.0}
CAP = {"surplus": 1.0, "or_deepseek": 1.2, "or_alibaba": 1.2}

def call(host, q, k):
    h = HOSTS[host]
    key = open(h["keyfile"]).read().strip()
    body = json.dumps(body_for(host, q)).encode("utf-8")
    t0 = time.time()
    err = None
    obj = None
    status = None
    tries = 0
    for tries in range(1, 8):
        rq = urllib.request.Request(h["base"] + "/chat/completions", data=body, method="POST",
                                    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(rq, timeout=240) as resp:
                status = resp.status
                obj = json.loads(resp.read().decode("utf-8"))
            err = None
            break
        except urllib.error.HTTPError as e:
            status = e.code
            txt = e.read().decode("utf-8", "replace")[:600]
            err = "http_%d %s" % (e.code, txt)
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(30, 2 ** tries) + random.random())
                continue
            break
        except Exception as e:  # noqa
            err = "exc %s" % type(e).__name__
            time.sleep(min(20, 2 ** tries))
            continue
    lat = round(time.time() - t0, 2)
    rec = {"rid": q["id"], "host": host, "k": k, "status": status, "tries": tries, "latency_s": lat, "error": err}
    if obj:
        ch = (obj.get("choices") or [{}])[0]
        m = ch.get("message") or {}
        u = obj.get("usage") or {}
        rec.update({"content": m.get("content"), "finish_reason": ch.get("finish_reason"),
                    "has_reasoning": bool(m.get("reasoning") or m.get("reasoning_content")),
                    "reasoning_len": len(m.get("reasoning") or m.get("reasoning_content") or ""),
                    "model_returned": obj.get("model"), "provider_returned": obj.get("provider"),
                    "sys_fp": obj.get("system_fingerprint"), "usage": u,
                    "cost_usd": (u.get("cost") if host != "surplus" else (u.get("buyer_cost_micro") or 0) / 1e6)})
        if obj.get("error"):
            rec["error"] = json.dumps(obj["error"])[:400]
    return rec

def main():
    reqs = build()
    json.dump(reqs, open(OUT + "requests.json", "w", encoding="utf-8"), ensure_ascii=False)
    resf = OUT + "results.jsonl"
    done = set()
    if os.path.exists(resf):
        for l in open(resf, encoding="utf-8"):
            j = json.loads(l)
            if not j.get("error"):
                done.add((j["rid"], j["host"], j["k"]))
    hosts = sys.argv[1:] or list(HOSTS)
    order = sorted(reqs, key=lambda q: {"P_gen": 0, "S_reply": 1, "T_reply": 1, "sanity": 2}.get(q["group"], 3))
    def work(host):
        def one(args):
            q, k = args
            if (q["id"], host, k) in done:
                return
            with lock:
                if spent[host] > CAP[host]:
                    return
            rec = call(host, q, k)
            with lock:
                spent[host] += rec.get("cost_usd") or 0
                with open(resf, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        jobs = [(q, k) for q in order for k in range(N_SAMPLES)]
        with ThreadPoolExecutor(HOSTS[host]["workers"]) as ex:
            list(ex.map(one, jobs))
        print(host, "done spent", round(spent[host], 4), flush=True)
    ts = [threading.Thread(target=work, args=(h,)) for h in hosts]
    [t.start() for t in ts]
    [t.join() for t in ts]
    print("ALL DONE", {k: round(v, 4) for k, v in spent.items()}, flush=True)

if __name__ == "__main__":
    main()
