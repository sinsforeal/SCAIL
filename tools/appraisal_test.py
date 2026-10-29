# -*- coding: utf-8 -*-
"""The gauge appraisal's acceptance tests.

Design section 5 ("'Derived from context' as a testable acceptance criterion")
and section 14.4's list. Read-only apart from a scratch save in the temp
directory; it makes no network call and spends nothing (the classifier is a
stub). Run from the repo root:

    python tools/appraisal_test.py
"""

import io
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from config import Config, DEFAULTS              # noqa: E402
from store import Store                          # noqa: E402
from world.clock import WorldClock               # noqa: E402
from sim.state import State                      # noqa: E402
from sim import appraisal_gauge as ag            # noqa: E402
from typesafe import TypeSafe                    # noqa: E402

FAILS = []


def check(ok, what, detail=""):
    print("  %s  %s%s" % ("ok  " if ok else "FAIL", what, (" -- %s" % detail) if detail else ""))
    if not ok:
        FAILS.append(what)
    return ok


# ---------------- the stub classifier ----------------

class FakeTS:
    """Answers a fixed map; records what was asked. No network, no key."""

    def __init__(self, answers, threshold=0.6):
        self.answers = answers
        self.threshold = threshold
        self.sent = None
        self.calls = 0

    def ready(self, name):
        return True

    def use(self, name):
        return {"threshold": self.threshold}

    def ask(self, name, state, questions):
        self.sent = {"name": name, "state": state, "questions": questions}
        self.calls += 1
        return self.answers

    def score(self, answers, qid):
        a = (answers or {}).get(qid)
        if not isinstance(a, dict) or a.get("type") != "score":
            return None, 0.0
        try:
            return float(a.get("score")), float(a.get("confidence") or 0.0)
        except (TypeError, ValueError):
            return None, 0.0

    def choice(self, answers, qid):
        a = (answers or {}).get(qid)
        if not isinstance(a, dict) or a.get("type") != "choice":
            return None, 0.0
        return a.get("choice"), float(a.get("confidence") or 0.0)


def score(v, c=0.9):
    return {"type": "score", "score": v, "confidence": c}


def pick(v, c=0.9):
    return {"type": "choice", "choice": v, "confidence": c}


def clean_answers():
    """Every dimension clear and above its floor, chosen so the combination is
    hand-checkable. `how_activating` is 0, so the negative gain is 0.6."""
    return {
        "how_good_or_bad": score(4),
        "how_activating": score(0),
        "is_this_new": pick("new"),
        "whose_doing": pick("him"),
        "unfairness": score(4),
        "wanted_and_blocked": score(4),
        "exposure": score(4),
        "achievement": score(4),
        "uncertainty": score(4),
        "holding_back": pick("holding_something"),
        "her_fault": score(4),
        "warmth_from_him": score(4),
        "attention_from_him": pick("answered_properly"),
        "who_else_has_him": score(4),
        "his_valence": score(3),
        "his_arousal": score(4),
    }


# expected from clean_answers(), computed by hand from config's weights:
#   relief 3 (good) + 3 (warmth) = 6;  sadness -2 (good) + 1.2 = -0.8 -> -1
#   anxiety -2 (good) + 1.2 = -0.8 -> -1;  anger 3*0.6=1.8 -> 2
#   shame 2*0.6=1.2 -> 1;  pride 2;  curiosity 2*0.6 + 2*0.6 = 2.4 -> 2
#   unsaid 1*0.6 + 2 = 2.6 -> 3;  guilt 2*0.6=1.2 -> 1
#   validation_craving -2 (warmth) + -2 (attention) = -4
#   loneliness -2 (warmth) + -1 (attention) = -3;  jealousy 2*0.6=1.2 -> 1
CLEAN_EXPECTED = {
    "relief": 6, "sadness": -1, "anxiety": -1, "anger": 2, "shame": 1, "pride": 2,
    "curiosity": 2, "unsaid": 3, "guilt": 1,
    "validation_craving": -4, "loneliness": -3, "jealousy": 1,
}


def main():
    tmp = os.path.join(tempfile.gettempdir(), "appraisal_test.db")
    if os.path.exists(tmp):
        os.remove(tmp)
    cfg = Config("config_momoka.json")
    store = Store(tmp)
    clock = WorldClock(cfg)
    state = State(cfg, store, clock, typesafe=None)

    print("== 1. one builder: the state's keys and the renderer come from one list ==")
    d = state.appraisal_state(scene={"location": "her room", "with_who": "", "events": []},
                              events=[{"text": "a thing happened", "salience": 3}],
                              user_msg_text="おはよう", digest_text="", his_side="")
    check(list(d.keys()) == list(ag.APPRAISAL_FIELDS),
          "appraisal_state()'s keys are APPRAISAL_FIELDS in order",
          str(list(d.keys())))
    rendered = state.render_appraisal_state(d)
    missing = [k for k, v in d.items() if isinstance(v, str) and v and v not in rendered]
    check(not missing, "every non-empty string field appears in the rendered role string",
          ", ".join(missing))
    for label in ("TIME:", "GAUGES:", "RELATIONSHIPS:", "\nSCENE:", "EVENTS:", "MESSAGE FROM HIM:"):
        check(label in rendered, "the role string carries %r" % label)
    d2 = dict(d)
    d2["present"] = "Rena-chan (closeness 70, standing 60, tension 5)"
    check("Rena-chan" in state.render_appraisal_state(d2),
          "changing a field changes the rendering (present)")

    print("\n== 2. no score without a field ==")
    keys = set(d.keys())
    for dim in ag.DIMENSIONS:
        named = [k for k in keys if k in dim["instructions"]]
        check(bool(named), "%s names a field: %s" % (dim["id"], ",".join(named) or "NONE"))

    print("\n== 3. the outgoing questions are score/choice only ==")
    qs = ag.questions()
    bad_type = [q for q, v in qs.items() if v.get("type") not in ("score", "choice")]
    check(not bad_type, "every question is score or choice", ", ".join(bad_type))
    check(all(set(v) == {"type", "instructions", "criteria"} for v in qs.values()),
          "every question carries only type/instructions/criteria")
    src = io.open(os.path.join(ROOT, "sim", "appraisal_gauge.py"), encoding="utf-8").read()
    reads = set(re.findall(r"typesafe\.(\w+)", src))
    check(reads <= {"ready", "use", "ask", "score", "choice"},
          "the module calls only the client's typed readers", ", ".join(sorted(reads)))
    a = {"q": {"type": "score", "score": 3.0, "confidence": 0.8}}
    check(TypeSafe.score(a, "q") == (3.0, 0.8), "TypeSafe.score reads score/confidence")
    c = {"q": {"type": "choice", "choice": "b", "confidence": 0.7}}
    check(TypeSafe.choice(c, "q") == ("b", 0.7), "TypeSafe.choice reads choice/confidence")

    print("\n== 4. every weight is a real, movable gauge on her spec ==")
    weights = cfg.raw["state"]["appraisal"]["weights"]
    movable = set(state.movable())
    spec = cfg.state.gauges
    for dim, table in sorted(weights.items()):
        for gauge in sorted(table):
            check(gauge in spec and gauge in movable,
                  "%s -> %s is in the spec and movable" % (dim, gauge))

    print("\n== 5. fixed answers normalise and combine to the expected deltas ==")
    ts = FakeTS(clean_answers())
    got = ag.appraise(ts, d, cfg, clock)
    check(got is not None, "a full clear returns a result")
    if got:
        deltas, his_mood, fresh, prov = got
        check(deltas == CLEAN_EXPECTED, "deltas equal the hand-computed table",
              "%s vs %s" % (deltas, CLEAN_EXPECTED))
        check(fresh is True, "is_this_new=new gives fresh True")
        check(his_mood.get("valence") == 1.0 and his_mood.get("arousal") == 2.0,
              "his_valence/his_arousal scale to -2..+2", str(his_mood))
        check(bool(his_mood.get("line")), "his_mood carries a templated line")
        # how_activating=4 sets the gain to 1.2: anger 3*1.2=3.6 -> 4
        up = clean_answers()
        up["how_activating"] = score(4)
        d2, _, _, _ = ag.appraise(FakeTS(up), d, cfg, clock)
        check(d2.get("anger") == 4, "a jolting event scales anger by 1.2 (3.6 -> 4)",
              str(d2.get("anger")))

    print("\n== 6. a dimension under its floor abstains; none clearing returns None ==")
    under = clean_answers()
    under["unfairness"] = score(4, 0.2)
    got = ag.appraise(FakeTS(under), d, cfg, clock)
    check(got is not None and "anger" not in got[0], "unfairness under its floor omits anger")
    if got:
        check(("unfairness", 0.2) in got[3]["abstained"], "the abstain is recorded by name and confidence")
    dead = {q: score(0, 0.1) for q in qs}
    check(ag.appraise(FakeTS(dead), d, cfg, clock) is None, "no dimension clearing returns None")
    check(ag.appraise(FakeTS({}), d, cfg, clock) is None, "no answers at all returns None")

    print("\n== 7. every delta shows its source; reasons_line is a line ==")
    got = ag.appraise(FakeTS(clean_answers()), d, cfg, clock)
    deltas, _, _, prov = got
    for gauge in deltas:
        src = prov["gauges"].get(gauge) or []
        check(bool(src) and src[0][0] in ag.DIMENSION_BY_ID,
              "delta %s names a dimension" % gauge, str(src))
    line = ag.reasons_line(prov)
    check(0 < len(line) <= 300, "reasons_line is non-empty and within 300 chars",
          "%d chars" % len(line))
    check(bool(ag.reasons_line({})), "reasons_line is never empty")

    print("\n== 8. fresh follows is_this_new, defaulting True under its floor ==")
    standing = clean_answers()
    standing["is_this_new"] = pick("standing")
    got = ag.appraise(FakeTS(standing), d, cfg, clock)
    check(got is not None and got[2] is False, "is_this_new=standing gives fresh False")
    quiet = clean_answers()
    quiet["is_this_new"] = pick("new", 0.1)
    got = ag.appraise(FakeTS(quiet), d, cfg, clock)
    check(got is not None and got[2] is True, "is_this_new under its floor defaults fresh True")
    no_him = dict(d)
    no_him["his_message"] = "(none this tick)"
    got = ag.appraise(FakeTS(clean_answers()), no_him, cfg, clock)
    check(got is not None and got[1] == {}, "no message from him leaves his_mood unwritten")

    print("\n== 9. the use is off in DEFAULTS and named for the character's bundle ==")
    check(DEFAULTS["typesafe"]["uses"]["state_appraisal"]["enabled"] is False,
          "uses.state_appraisal is disabled in DEFAULTS")
    check("state_appraisal" in cfg.raw["typesafe"]["uses"],
          "the character's config carries the use")

    if FAILS:
        print("\nappraisal_test: %d FAILED: %s" % (len(FAILS), "; ".join(FAILS)))
        return 1
    print("\nappraisal_test: all clear")
    return 0


if __name__ == "__main__":
    sys.exit(main())
