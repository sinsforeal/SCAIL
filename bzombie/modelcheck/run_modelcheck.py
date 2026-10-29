"""Model check: deepseek-v4.1-flash-1017 vs glm-5.3 on 8 moments, 3 samples each, through the gateway.

Arm X, run_id modelcheck, cap_usd 0.40, temperature 1.0, max_tokens 1200 for both.
Output: var/bzombie/modelcheck/samples.json (blind labels, no model name) and key.json
(label -> model, plus the moment texts). Does not judge.
Needs the gateway up on 127.0.0.1:18330.
"""
import concurrent.futures as cf
import http.client
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moments import MOMENTS  # noqa: E402

VAR = r"H:\SCAIL\bzombie\var"
OUT = os.path.join(VAR, "modelcheck")
RUN = "modelcheck"
MODELS = ["deepseek-v4.1-flash-1017", "glm-5.3"]
N = 3
MOMOKA_DIR = r"F:\REPS2\SCAILV4\prompts_momoka"
TOMOE_DIR = r"F:\REPS2\SCAILV3\characters\tomoe\prompts"

MOMOKA_CARD = ("【テスト用の設定】百花は成人している。ほかは上の記録のまま。"
               "ここは学校の場面ではなく、彼とのチャット。短い普通体で、百花として返す。")
TOMOE_CARD = ("TEST CARD (overrides any age or school line above): Tomoe is nineteen, in her first year at a university in "
              "Tokyo (born 2007, still living with her family, same commute line, same friends, same room, same him). "
              "Wherever the text says fifteen, high school, class 1-C, uniform or homework, read it as her nineteen-year-old "
              "first-year university life: lectures, seminar, the circle, a part-time job. Everything else about her "
              "stays exactly as written. You are typing to him on your phone.")


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def persona(character):
    if character == "momoka":
        return read(os.path.join(MOMOKA_DIR, "bible.md")) + "\n\n" + read(os.path.join(MOMOKA_DIR, "style.md"))
    bible = read(os.path.join(TOMOE_DIR, "bible.md")).replace(
        "a fifteen year old girl", "a nineteen year old woman")
    style = read(os.path.join(TOMOE_DIR, "style.md")).replace("You are fifteen", "You are nineteen")
    sheet = read(os.path.join(os.path.dirname(TOMOE_DIR), "sheet.json"))
    return bible + "\n\n" + style + "\n\n## Sheet (reference)\n\n" + sheet


def build_messages(m):
    card = MOMOKA_CARD if m["character"] == "momoka" else TOMOE_CARD
    system = persona(m["character"]) + "\n\n" + card + "\n\n<situation>\n" + m["situation"] + "\n</situation>"
    msgs = [{"role": "system", "content": system}]
    for who, text in m["chat"]:
        msgs.append({"role": "user" if who == "him" else "assistant", "content": text})
    msgs.append({"role": "user", "content": m["newest"]})
    return msgs


def post(model, lang, messages):
    c = http.client.HTTPConnection("127.0.0.1", 18330, timeout=300)
    body = {"model": "any", "messages": messages, "temperature": 1.0, "max_tokens": 1200}
    c.request("POST", "/arm/X/%s/v1/chat/completions" % RUN, json.dumps(body),
              {"Content-Type": "application/json", "x-bz-model": model, "x-bz-lang": lang})
    r = c.getresponse()
    raw = r.read()
    return r.status, r.getheader("x-bz-call-id"), json.loads(raw.decode("utf-8"))


def one(job):
    m, model, k = job
    lang = "ja" if m["character"] == "momoka" else "en"
    msgs = build_messages(m)
    for attempt in range(3):
        st, cid, d = post(model, lang, msgs)
        if st != 200:
            return {"moment": m["id"], "model": model, "k": k, "error": "%s %s" % (st, json.dumps(d)[:300]),
                    "call_id": cid}
        ch = d["choices"][0]
        text = (ch["message"].get("content") or "").strip()
        if text:
            return {"moment": m["id"], "model": model, "k": k, "text": text, "call_id": cid,
                    "finish_reason": ch.get("finish_reason"), "usage": d.get("usage"), "attempts": attempt + 1}
    return {"moment": m["id"], "model": model, "k": k, "error": "empty after 3 attempts", "call_id": cid}


def main():
    os.makedirs(OUT, exist_ok=True)
    rd = os.path.join(VAR, "runs", RUN)
    os.makedirs(rd, exist_ok=True)
    with open(os.path.join(rd, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"model": MODELS[0], "lang": "ja", "cap_usd": 0.40,
                   "note": "arm X; model and lang come per call from x-bz-model and x-bz-lang"}, f)
    jobs = [(m, model, k) for m in MOMENTS for model in MODELS for k in range(N)]
    with cf.ThreadPoolExecutor(6) as ex:
        results = list(ex.map(one, jobs))
    rng = random.Random()
    labels = set()
    for r in results:
        while True:
            lab = "s%06x" % rng.getrandbits(24)
            if lab not in labels:
                labels.add(lab)
                r["label"] = lab
                break
    ok = [r for r in results if "text" in r]
    errs = [r for r in results if "text" not in r]
    pub = [{"label": r["label"], "moment_id": r["moment"], "text": r["text"]} for r in ok]
    rng.shuffle(pub)
    moments = [{k: v for k, v in m.items()} for m in MOMENTS]
    with open(os.path.join(OUT, "samples.json"), "w", encoding="utf-8") as f:
        json.dump({"run_id": RUN, "moments": moments, "samples": pub}, f, ensure_ascii=False, indent=1)
    key = {"run_id": RUN, "labels": {r["label"]: {"model": r["model"], "moment": r["moment"], "k": r["k"],
                                                  "call_id": r["call_id"], "finish_reason": r.get("finish_reason"),
                                                  "usage": r.get("usage")} for r in ok},
           "errors": errs, "moments": moments}
    with open(os.path.join(OUT, "key.json"), "w", encoding="utf-8") as f:
        json.dump(key, f, ensure_ascii=False, indent=1)
    print("samples", len(ok), "errors", len(errs))
    for e in errs:
        print("error", e["moment"], e["model"], e["error"])


if __name__ == "__main__":
    main()
