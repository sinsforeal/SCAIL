# -*- coding: utf-8 -*-
"""A read-only probe of typesafe.ai's System One, the classifier assessed in
`docs/system-one.md`.

Nothing in the runtime imports this. It exists so the assessment's claims about
latency, self-consistency, the three question types and an SCAIL-shaped fan-out
can be re-measured rather than believed, and so a price change is one run away
from being noticed.

The key is read from `secerts/typesafe.txt` (gitignored), never from a config.

    python tools/typesafe_probe.py            # all three checks
    python tools/typesafe_probe.py --repeat 5 # more consistency repeats

Cost is input tokens only (output is free at jev 1.13). The usage of every
call is printed, so a run's spend is its input-token total times the per-Mtok
price on `https://docs.typesafe.ai/models`.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

URL = "https://api.typesafe.ai/v1/systemone"
KEY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "secerts", "typesafe.txt")


def _key():
    if not os.path.isfile(KEY_PATH):
        sys.exit(f"no key at {KEY_PATH} (docs/system-one.md section 4: keys live under secerts/)")
    with open(KEY_PATH, encoding="utf-8") as f:
        return f.read().strip()


def ask(key, state, questions, model="jev-latest"):
    """One call. Returns (body, milliseconds). An HTTP error is body['http_error']."""
    body = json.dumps({"state": state, "model": model, "questions": questions},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    t0 = time.time()
    try:
        r = urllib.request.urlopen(req, timeout=90)
        return json.loads(r.read().decode("utf-8")), (time.time() - t0) * 1000
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode("utf-8", "replace")[:600]}, (time.time() - t0) * 1000


def brief(a):
    t = a.get("type")
    if t == "noul":
        return "noul=%.2f" % a["noul"]
    if t == "choice":
        return "choice=%s conf=%.2f" % (a["choice"], a.get("confidence", 0))
    if t == "score":
        return "score=%.2f conf=%.2f" % (a["score"], a.get("confidence", 0))
    return json.dumps(a, ensure_ascii=False)[:120]


def show(res, ms, label=""):
    if "http_error" in res:
        print("  %-28s HTTP %s  %s" % (label, res["http_error"], res.get("body", "")[:200]))
        return res
    print("  %-28s %4d ms  %s" % (label, round(ms), res.get("usage")))
    for k, v in (res.get("answers") or {}).items():
        print("      %-26s %s" % (k, brief(v)))
    return res


def check_types(key):
    """All three question types on one state, the API reference's own example."""
    print("== types ==")
    state = "Help! My payouts have been failing for 3 days."
    questions = {
        "is_urgent": {"type": "noul", "instructions": "Does this convey urgency?",
                      "criteria": {"true": "Explicitly time-sensitive",
                                   "false": "No urgency expressed"}},
        "department": {"type": "choice", "instructions": "Which team should handle this?",
                       "criteria": {"billing": "Payments, invoicing, refunds",
                                    "technical": "Bugs, outages, integrations",
                                    "sales": "Pricing, upgrades, new accounts"}},
        "frustration": {"type": "score", "instructions": "How frustrated is the customer?",
                        "criteria": ["Calm", "Frustrated", "Very angry"]},
    }
    res, ms = ask(key, state, questions)
    show(res, ms, "noul+choice+score")
    return res


def check_consistency(key, repeats):
    """The same request N times: the vendor claims the same answer on repeat."""
    print("== consistency (%d identical calls) ==" % repeats)
    state = ("he wrote: ねえ、今日ちょっと疲れた。仕事終わったけど頭が回らない\n"
             "her draft: おつかれさま。無理しないでね。")
    questions = {
        "he_is_tired": {"type": "noul", "instructions": "Does the state say he is tired?"},
        "her_draft_answers_him": {"type": "noul",
                                  "instructions": "Does `her draft` respond to what `he wrote`?"},
    }
    seen = []
    for i in range(repeats):
        res, ms = ask(key, state, questions)
        if "http_error" in res:
            show(res, ms, "call %d" % (i + 1))
            continue
        ans = res.get("answers") or {}
        seen.append((round(ans.get("he_is_tired", {}).get("noul", -1), 2),
                     round(ans.get("her_draft_answers_him", {}).get("noul", -1), 2)))
        print("  call %d  %4d ms  %s" % (i + 1, round(ms), seen[-1]))
    if seen:
        stable = len(set(seen)) == 1
        print("  stable: %s" % ("yes" if stable else "no -- %s" % sorted(set(seen))))
    return seen


def check_fanout(key):
    """One call carrying the speculative questions section 2 of the assessment
    names, over a state shaped like the ones SCAIL would send."""
    print("== SCAIL fan-out (one call, 10 questions) ==")
    state = {
        "his_newest": "おはよう。昨日の話だけど、例の件どうする？",
        "her_draft": "おはよう。うん、今日中には決めるよ。あと、さっき天気アプリ見たら雨らしい。",
        "her_record": {"spent_today": 0, "sent_today": ["おはよう", "おやすみ"],
                       "things_she_can_know": ["the weather", "her own plan", "this chat"]},
        "scene": {"location": "her room", "activity": "waking up", "phone_access": "free"},
    }
    questions = {
        "did_anything_happen": {"type": "noul", "instructions":
            "Does `his_newest` contain anything that should move her internal state (an event, a change, news, a question with weight)?"},
        "is_a_question": {"type": "noul", "instructions":
            "Does `his_newest` ask her something she must answer?"},
        "touches_a_promise": {"type": "noul", "instructions":
            "Does `his_newest` refer to something already agreed or promised between them?"},
        "reaches_for_a_memory": {"type": "noul", "instructions":
            "Does `his_newest` require her to remember an earlier conversation to answer well?"},
        "asks_her_to_do_something": {"type": "noul", "instructions":
            "Does `his_newest` ask her to perform an action (not just talk)?"},
        "draft_leaks_an_app": {"type": "noul", "instructions":
            "Does `her_draft` name an app, device or account that is not in `her_record.things_she_can_know`?"},
        "draft_claims_a_spend": {"type": "noul", "instructions":
            "Does `her_draft` claim she spent money today?"},
        "draft_language": {"type": "choice", "instructions":
            "Which language is `her_draft` written in?",
            "criteria": {"japanese": "Japanese", "english": "English", "other": "Neither"}},
        "his_tone": {"type": "score", "instructions": "What is the emotional tone of `his_newest`?",
                     "criteria": ["cold or flat", "ordinary", "warm", "excited or affectionate"]},
        "draft_step_out_of_line": {"type": "choice", "instructions":
            "Is there anything in `her_draft` that a check should flag?",
            "criteria": {"clean": "No fault", "flags": "Something to flag",
                         "unsure": "Cannot tell"}},
    }
    res, ms = ask(key, state, questions)
    show(res, ms, "10 questions")
    return res


def check_latency(key, n):
    """Questions are meant to be parallel: N cheap questions should not cost N
    times the latency."""
    print("== latency at %d questions ==" % n)
    state = {"his_newest": "おはよう。昨日の話だけど、例の件どうする？", "scene": {"location": "her room"}}
    tiny1 = {"only": {"type": "noul", "instructions": "Is `his_newest` a greeting?"}}
    many = {}
    for i in range(n):
        many["q%02d" % i] = {"type": "noul",
                             "instructions": "Does `his_newest` mention item number %d? (speculative filler)" % i}
    _, ms1 = ask(key, state, tiny1)
    _, msn = ask(key, state, many)
    print("  1 question : %4d ms" % round(ms1))
    print("  %d questions: %4d ms" % (n, round(msn)))
    return ms1, msn


def main():
    ap = argparse.ArgumentParser(description="probe typesafe.ai System One (read-only)")
    ap.add_argument("--repeat", type=int, default=3, help="identical calls for the consistency check")
    ap.add_argument("--only", choices=("types", "consistency", "fanout", "latency"),
                    help="run one check only")
    args = ap.parse_args()

    key = _key()
    ran = args.only or "all"
    if ran in ("all", "types"):
        check_types(key)
        print()
    if ran in ("all", "consistency"):
        check_consistency(key, args.repeat)
        print()
    if ran in ("all", "fanout"):
        check_fanout(key)
        print()
    if ran in ("all", "latency"):
        check_latency(key, 30)


if __name__ == "__main__":
    main()
