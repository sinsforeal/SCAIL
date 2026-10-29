"""The live bot's model test: the last N calls of every role in a run,
replayed as sent on candidate providers, beside the official DeepSeek
reply the bot actually used and a control written by hand.

    python tools/bot_model_test.py extract logs/<run> [n]        -> data/model_test/<ts>/cases.jsonl
    python tools/bot_model_test.py run <dir> gemini|coreweave|qwen [workers]
    python tools/bot_model_test.py show <dir> <case> [tail]      the case as the bot sent it, for reading
    python tools/bot_model_test.py report <dir>                  summary table + every answer side by side

Running the bot and extracting a persona are different tasks (his
words), so this is its own test: every case keeps the role's own
temperature and thinking flag, no output limit, no fallback host. The
reply written by hand goes to <dir>/fable/<case>.json as {"content": ...}.
"""
import json
import os
import sys
import time
import glob
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "yukarin", "tools"))
from llm import parse_json_block          # the bot's own parser, so "parses" means what it means to the bot
import llmx                                # the Vertex token/url and the OpenRouter key

PROVIDERS = {
    # slug on OpenRouter, host pin; the DeepSeek revision the bot runs is v4 flash (0731)
    "coreweave": {"kind": "openrouter", "model": "deepseek/deepseek-v4-flash-0731", "pin": "coreweave"},
    "relace": {"kind": "openrouter", "model": "deepseek/deepseek-v4-flash-0731", "pin": "relace"},
    "together": {"kind": "openrouter", "model": "deepseek/deepseek-v4-flash-0731", "pin": "together"},
    "deepinfra": {"kind": "openrouter", "model": "deepseek/deepseek-v4-flash-0731", "pin": "deepinfra"},
    "parasail": {"kind": "openrouter", "model": "deepseek/deepseek-v4-flash-0731", "pin": "parasail"},
    "glm-zai": {"kind": "openrouter", "model": "z-ai/glm-5.3-flash", "pin": "z-ai", "max_temp": 1.0},   # Z.AI: 400 above 1.0
    "glm-relace": {"kind": "openrouter", "model": "z-ai/glm-5.3-flash", "pin": "relace"},
    "qwen": {"kind": "openrouter", "model": "qwen/qwen3.8-flash", "pin": "alibaba"},
    "gemini": {"kind": "vertex", "model": None},
}
OR_URL = "https://openrouter.ai/api/v1/chat/completions"


def _config():
    return json.load(open(os.path.join(REPO, "config.json"), encoding="utf-8"))


def extract(run_dir, n=2):
    rows = [json.loads(l) for l in open(os.path.join(run_dir, "llm_calls.jsonl"), encoding="utf-8")]
    models = _config()["models"]
    by = {}
    for i, r in enumerate(rows):
        if r.get("content"):
            by.setdefault(r["role"], []).append((i, r))
    out = os.path.join(REPO, "data", "model_test", time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(out)
    with open(os.path.join(out, "cases.jsonl"), "w", encoding="utf-8") as f:
        for role, v in by.items():
            m = models.get(role, {})
            for i, r in v[-n:]:
                case = {"id": f"{role}_{i:02d}", "role": role, "idx": i, "run": os.path.basename(run_dir),
                        "temperature": m.get("temperature", 1.0), "thinking": bool(m.get("thinking")),
                        "effort": m.get("effort") or "low", "messages": r["messages"],
                        "official": {"content": r["content"], "seconds": r.get("seconds"),
                                     "usage": r.get("usage"), "reasoning_chars": len(r.get("reasoning") or "")}}
                f.write(json.dumps(case, ensure_ascii=False) + "\n")
    cases = load(out)
    print(f"{len(cases)} cases from {len(by)} roles -> {out}")
    return out


def load(d):
    return [json.loads(l) for l in open(os.path.join(d, "cases.jsonl"), encoding="utf-8")]


_vx = None
_vx_lock = threading.Lock()


def _vertex():
    global _vx
    with _vx_lock:
        if _vx is None:
            _vx = llmx._Vertex()
    return _vx


def _gemini_body(case):
    sys_txt = "\n\n".join(m["content"] for m in case["messages"] if m["role"] == "system")
    contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in case["messages"] if m["role"] != "system"]
    if not contents:
        contents = [{"role": "user", "parts": [{"text": ""}]}]
    gen = {"temperature": case["temperature"]}
    # the role's thinking flag, as the bot sets it for DeepSeek: on -> a
    # generous budget; off -> none. A model that refuses 0 says so in the
    # error and the case records it.
    gen["thinkingConfig"] = {"thinkingBudget": 32768 if case["thinking"] else 0}
    body = {"contents": contents, "generationConfig": gen}
    if sys_txt:
        body["systemInstruction"] = {"parts": [{"text": sys_txt}]}
    return body


RAW_DIR = None   # set by run(); every response is written here as it lands


def _dump_raw(case, provider, attempt, d):
    if RAW_DIR:
        os.makedirs(RAW_DIR, exist_ok=True)
        json.dump(d, open(os.path.join(RAW_DIR, f"{provider}_{case['id']}_a{attempt}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)


def call_case(provider, case, timeout=900, retries=0):
    p = PROVIDERS[provider]
    last = None
    for attempt in range(retries + 1):
        t0 = time.time()
        meta = {"provider": provider, "attempt": attempt, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            if p["kind"] == "vertex":
                vx = _vertex()
                body = _gemini_body(case)
                if attempt and last and "thinking" in (last or "").lower() and not case["thinking"]:
                    body["generationConfig"].pop("thinkingConfig", None)   # the model refused budget 0
                    meta["note"] = "thinkingBudget 0 refused; default thinking"
                r = requests.post(vx.url(None), headers={"Authorization": f"Bearer {vx.token()}",
                                                         "Content-Type": "application/json"},
                                  json=body, timeout=timeout)
                meta["seconds"] = round(time.time() - t0, 1)
                meta["status"] = r.status_code
                meta["served_by"] = f"vertex:{vx.region}"
                meta["model"] = vx.model
                if r.status_code != 200:
                    last = r.text[:400]
                    meta["error"] = last
                    time.sleep(5 * (attempt + 1))
                    continue
                d = r.json()
                _dump_raw(case, provider, attempt, d)
                u = d.get("usageMetadata") or {}
                meta.update({"in": u.get("promptTokenCount"), "out": u.get("candidatesTokenCount"),
                             "think": u.get("thoughtsTokenCount")})
                cands = d.get("candidates") or [{}]
                meta["finish"] = cands[0].get("finishReason")
                text = "".join(pt.get("text", "") for pt in (cands[0].get("content") or {}).get("parts", [])
                               if not pt.get("thought")).strip()
            else:
                temp = case["temperature"]
                if p.get("max_temp") is not None and temp > p["max_temp"]:
                    temp = p["max_temp"]          # the host refuses the role's setting; the row says so
                    meta["note"] = f"temperature clamped {case['temperature']} -> {temp}"
                body = {"model": p["model"], "messages": case["messages"], "temperature": temp,
                        "provider": {"order": [p["pin"]], "allow_fallbacks": False},
                        "reasoning": ({"effort": case["effort"], "exclude": False} if case["thinking"]
                                      else {"enabled": False})}
                headers = {"Authorization": f"Bearer {llmx._openrouter_key()}", "Content-Type": "application/json",
                           "HTTP-Referer": "https://scail.local/bot", "X-OpenRouter-Title": "SCAIL bot model test"}
                r = requests.post(OR_URL, headers=headers, json=body, timeout=timeout)
                meta["seconds"] = round(time.time() - t0, 1)
                meta["status"] = r.status_code
                meta["model"] = p["model"]
                if r.status_code != 200:
                    last = r.text[:400]
                    meta["error"] = last
                    time.sleep((20 if r.status_code == 429 else 5) * (attempt + 1))
                    continue
                d = r.json()
                _dump_raw(case, provider, attempt, d)
                if d.get("error"):
                    last = json.dumps(d["error"])[:400]
                    meta["error"] = last
                    time.sleep(5 * (attempt + 1))
                    continue
                u = d.get("usage") or {}
                det = u.get("completion_tokens_details") or {}
                meta.update({"in": u.get("prompt_tokens"), "out": u.get("completion_tokens"),
                             "think": det.get("reasoning_tokens"), "served_by": d.get("provider")})
                ch = (d.get("choices") or [{}])[0]
                meta["finish"] = ch.get("finish_reason")
                msg = ch.get("message") or {}
                text = (msg.get("content") or "")
                if msg.get("reasoning"):
                    meta["reasoning_chars"] = len(msg["reasoning"])
                    meta["reasoning_tail"] = msg["reasoning"][-400:]
                import re
                text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            meta["chars"] = len(text)
            if not text:
                # 2026-08-31: two answers that arrived with empty content were
                # dropped and re-asked in silence, and the re-asks were killed.
                # An empty answer is a result; it is written, with the raw
                # body beside it, and the run says so.
                meta["error"] = "empty answer"
                print(f"  {case['id']:<20} {provider}: EMPTY content (finish {meta.get('finish')}, out {meta.get('out')}, "
                      f"think {meta.get('think')}, reasoning_chars {meta.get('reasoning_chars')})", flush=True)
            return text, meta
        except requests.RequestException as e:
            meta["seconds"] = round(time.time() - t0, 1)
            last = str(e)[:300]
            meta["error"] = last
            time.sleep(5 * (attempt + 1))
    return "", {"provider": provider, "error": last}


def run(d, provider, workers=4, timeout=900):
    global RAW_DIR
    RAW_DIR = os.path.join(d, "raw")
    cases = load(d)
    out = os.path.join(d, provider)
    os.makedirs(out, exist_ok=True)
    todo = [c for c in cases if not os.path.exists(os.path.join(out, c["id"] + ".json"))]
    print(f"{provider}: {len(todo)} of {len(cases)} cases to run, {workers} workers", flush=True)

    def work(c):
        text, meta = call_case(provider, c, timeout=timeout)
        rec = dict(meta, content=text, id=c["id"], role=c["role"])
        json.dump(rec, open(os.path.join(out, c["id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return rec

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(work, c) for c in todo]):
            r = fut.result()
            print(f"  {r['id']:<20} {'ERR ' + str(r.get('error'))[:60] if r.get('error') and not r.get('content') else ''}"
                  f"{r.get('chars', 0)} chars, {r.get('seconds')}s, think {r.get('think')}, {r.get('served_by')}", flush=True)


def show(d, cid, tail=None):
    for c in load(d):
        if c["id"] == cid:
            msgs = c["messages"]
            if tail:
                sys_msgs = [m for m in msgs if m["role"] == "system"]
                rest = [m for m in msgs if m["role"] != "system"]
                msgs = sys_msgs + rest[-int(tail):]
            print(f"### {cid}  role={c['role']} temp={c['temperature']} thinking={c['thinking']} msgs={len(c['messages'])}")
            for m in msgs:
                print(f"\n----- [{m['role']}] -----\n{m['content']}")
            print(f"\n===== OFFICIAL ({c['official']['seconds']}s) =====\n{c['official']['content']}")
            return
    print("no such case")


def report(d):
    cases = load(d)
    provs = [p for p in list(PROVIDERS) + ["fable"] if os.path.isdir(os.path.join(d, p))]
    lines = [f"# Bot model test -- {os.path.basename(d)}", "",
             "Every case is a real call from the run, replayed as sent (same messages, the role's temperature and",
             "thinking flag, no output limit, no fallback host). `official` is the DeepSeek reply the bot used;",
             "`fable` is the control written by hand from the same context. `json` = the bot's parser accepts it",
             "(only shown for roles whose official answer was JSON). Seconds are wall time of the one call.", "",
             "| case | official chars/s | " + " | ".join(f"{p} chars/s/think/json" for p in provs) + " |",
             "|---|---|" + "---|" * len(provs)]
    detail = []
    for c in cases:
        off = c["official"]
        is_json = parse_json_block(off["content"]) is not None
        cells = []
        detail.append(f"\n\n## {c['id']}  (temp {c['temperature']}, thinking {c['thinking']})\n\n"
                      f"### official ({off['seconds']}s)\n\n```\n{off['content']}\n```")
        for p in provs:
            f = os.path.join(d, p, c["id"] + ".json")
            if not os.path.exists(f):
                cells.append("--")
                continue
            r = json.load(open(f, encoding="utf-8"))
            txt = r.get("content") or ""
            if not txt:
                cells.append(f"ERR {str(r.get('error'))[:40]}")
                detail.append(f"\n### {p}: ERROR {r.get('error')}")
                continue
            js = ("ok" if parse_json_block(txt) is not None else "BAD") if is_json else "-"
            cells.append(f"{len(txt)}/{r.get('seconds', '')}/{r.get('think') or 0}/{js}")
            detail.append(f"\n### {p} ({r.get('seconds')}s, think {r.get('think')}, served {r.get('served_by')}"
                          f"{', ' + r['note'] if r.get('note') else ''})\n\n```\n{txt}\n```")
        lines.append(f"| {c['id']} | {len(off['content'])}/{off['seconds']} | " + " | ".join(cells) + " |")
    dest = os.path.join(d, "report.md")
    open(dest, "w", encoding="utf-8").write("\n".join(lines) + "".join(detail))
    print("\n".join(lines))
    print("->", dest)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "extract":
        extract(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2)
    elif cmd == "run":
        run(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 4,
            int(sys.argv[5]) if len(sys.argv) > 5 else 900)   # run <dir> <provider> [workers] [timeout s]
    elif cmd == "show":
        show(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "report":
        report(sys.argv[2])
