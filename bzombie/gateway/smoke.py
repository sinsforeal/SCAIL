"""Live smoke against the running gateway (127.0.0.1:18330) and real Surplus.
One non-stream and one stream chat call per model, one embeddings call, then /status.
Run ids bz_smoke_ds and bz_smoke_glm, cap_usd 0.05 each. Prints numbers only, never the key.
"""
import http.client
import json
import os
import time

VAR = r"H:\SCAIL\bzombie\var"
PORT = 18330


def mkrun(run_id, model):
    d = os.path.join(VAR, "runs", run_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"model": model, "lang": "ja", "cap_usd": 0.05}, f)
    with open(os.path.join(d, "clock.json"), "w", encoding="utf-8") as f:
        json.dump({"virtual_ts": "2026-10-23T08:00:00+09:00"}, f)


def call(path, body, method="POST"):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=180)
    t = time.time()
    c.request(method, path, json.dumps(body) if body is not None else None, {"Content-Type": "application/json"})
    r = c.getresponse()
    raw = r.read()
    return r.status, r.getheader("x-bz-call-id"), raw.decode("utf-8", "replace"), round(time.time() - t, 2)


def main():
    msgs = [{"role": "system", "content": "あなたは百花。短く答える。"},
            {"role": "user", "content": "今日の天気はどう?"}]
    for rid, model in (("bz_smoke_ds", "deepseek-v4.1-flash-1017"), ("bz_smoke_glm", "glm-5.3")):
        mkrun(rid, model)
        base = "/arm/X/%s/v1" % rid
        st, cid, raw, dt = call(base + "/chat/completions", {"model": "any", "messages": msgs, "max_tokens": 300})
        d = json.loads(raw)
        print(model, "nonstream", st, "%ss" % dt, "cost_micro", d["usage"].get("buyer_cost_micro"),
              "reasoning_tokens", (d["usage"].get("completion_tokens_details") or {}).get("reasoning_tokens"),
              "text", repr(d["choices"][0]["message"]["content"][:60]), "call", cid)
        st, cid, raw, dt = call(base + "/chat/completions", {"model": "any", "messages": msgs, "stream": True,
                                                              "max_tokens": 300})
        text = "".join(json.loads(l[5:])["choices"][0]["delta"].get("content") or ""
                       for l in raw.splitlines() if l.startswith("data:") and "[DONE]" not in l
                       and json.loads(l[5:]).get("choices"))
        print(model, "stream", st, "%ss" % dt, "text", repr(text[:60]), "usage_in_body", "buyer_cost_micro" in raw,
              "call", cid)
    st, cid, raw, dt = call("/arm/X/bz_smoke_ds/v1/embeddings", {"model": "e5", "input": ["こんにちは", "hello"]})
    d = json.loads(raw)
    print("embeddings", st, "%ss" % dt, "n", len(d["data"]), "dim", len(d["data"][0]["embedding"]))
    st, _, raw, _ = call("/status", None, "GET")
    s = json.loads(raw)
    for k, v in s["runs"].items():
        if k.startswith("bz_smoke"):
            print("status", k, "spent_micro", v["spent_micro"], "cap_usd", v["cap_usd"], "calls", v["calls"],
                  "errors", v["errors"])
    print("status device", s["embed_device"], "balance", s["balance"])


if __name__ == "__main__":
    main()
