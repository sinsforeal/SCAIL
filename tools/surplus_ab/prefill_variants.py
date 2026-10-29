"""Prefill variants on Surplus for the 7 trailing-assistant requests (tk-7gn).
Reads F:/temp/or_ab/requests.json, writes F:/temp/or_ab/prefill_results.jsonl. Key read in code only."""
import json, os, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

ROOT = "F:/REPS2/SCAILV4"
OUT = "F:/temp/or_ab/prefill_results.jsonl"
BASE = "https://api.surplusintelligence.ai/v1"
KEY = open(ROOT + "/secerts/surplus.txt").read().strip()
IDS = ["P348", "P502", "P426", "P269", "P336", "P414", "P489"]
N = 3

LINE = "Write only the character's next message, continuing from the text of the last line above. No other characters' turns, no commentary."


def fold_text(prefill):
    return ("\n\n" + LINE + "\nThe text to continue ends with:\n" + prefill[-400:])


def mk(variant, q):
    msgs = [dict(m) for m in q["messages"]]
    b = {"model": "deepseek-v4.1-flash-1017", "reasoning_effort": "none", "stream": False,
         "temperature": q["temperature"], "max_tokens": 4096}
    if q["ctk"]:
        b["chat_template_kwargs"] = dict(q["ctk"])
    last = msgs[-1]
    assert last["role"] == "assistant"
    if variant == "a_asis":
        pass
    elif variant == "b1_fold_line":
        msgs.pop()
        msgs[-1]["content"] = msgs[-1]["content"] + "\n\n" + LINE
    elif variant == "b2_fold_prefill":
        pre = msgs.pop()["content"]
        msgs[-1]["content"] = msgs[-1]["content"] + fold_text(pre)
    elif variant == "c_prefix_true":
        last["prefix"] = True
    elif variant == "d1_continue_final":
        b["continue_final_message"] = True
        b["add_generation_prompt"] = False
    elif variant == "d2_ctk_continue":
        kw = b.setdefault("chat_template_kwargs", {})
        kw["continue_final_message"] = True
        kw["add_generation_prompt"] = False
    b["messages"] = msgs
    return b


def call(variant, q, k):
    body = json.dumps(mk(variant, q), ensure_ascii=False).encode("utf-8")
    t0 = time.time()
    rec = {"rid": q["id"], "variant": variant, "k": k}
    for tries in range(4):
        rq = urllib.request.Request(BASE + "/chat/completions", data=body, method="POST",
                                    headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(rq, timeout=240) as r:
                obj = json.loads(r.read().decode("utf-8"))
            ch = obj["choices"][0]
            rec.update(status=200, content=ch["message"].get("content"), finish=ch.get("finish_reason"),
                       usage=obj.get("usage"))
            break
        except urllib.error.HTTPError as e:
            rec.update(status=e.code, error=e.read().decode("utf-8", "replace")[:300])
            if e.code in (429, 502, 503, 504):
                time.sleep(2 ** tries)
                continue
            break
        except Exception as e:  # noqa
            rec.update(status=None, error=type(e).__name__)
            time.sleep(2)
    rec["latency_s"] = round(time.time() - t0, 2)
    return rec


def main():
    variants = sys.argv[1].split(",")
    n = int(sys.argv[2]) if len(sys.argv) > 2 else N
    ids = sys.argv[3].split(",") if len(sys.argv) > 3 else IDS
    reqs = [q for q in json.load(open("F:/temp/or_ab/requests.json", encoding="utf-8")) if q["id"] in ids]
    jobs = [(v, q, k) for v in variants for q in reqs for k in range(n)]
    with ThreadPoolExecutor(4) as ex, open(OUT, "a", encoding="utf-8") as f:
        for rec in ex.map(lambda j: call(*j), jobs):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    print("done", len(jobs))


if __name__ == "__main__":
    main()
