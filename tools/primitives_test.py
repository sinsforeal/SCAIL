"""What the primitives do at zero, and what the premise looks like in them.

`docs/primitives.md` is the spec. The claims worth testing are not arithmetic;
they are that **zero means zero** and that the named mechanisms stay quiet for
a statable reason rather than because their file is empty. The last case is
the one the whole design exists for: an opening condition where one party
knows everything and the other knows nothing.

    python tools/primitives_test.py
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from config import Config              # noqa: E402
from sim.primitives import Primitives, KEYS   # noqa: E402

FAILS = []


def check(claim, got, want):
    ok = got == want
    print("  %s %-62s %s" % ("ok  " if ok else "FAIL", claim, got if ok else "%r, wanted %r" % (got, want)))
    if not ok:
        FAILS.append(claim)


class Store:
    def __init__(self):
        self.kv = {}

    def get(self, k, d=None):
        return self.kv.get(k, d)

    def set(self, k, v):
        self.kv[k] = v


class Clock:
    def __init__(self):
        self.t = 1000000.0

    def now_ts(self):
        return self.t

    def date_str(self):
        return "2003-01-01"


def main():
    cfg = Config()
    p = Primitives(cfg, Store(), Clock())

    print("\n-- a stranger: nothing has happened, and nothing pretends it has")
    check("every primitive is 0", [p.get("him", k) for k in KEYS], [0.0] * len(KEYS))
    check("closeness is 0", p.closeness("him"), 0.0)
    check("attachment is 0", p.attachment("him"), 0.0)
    check("nothing is owed at the start", p._owed("him"), 0.0)
    check("resentment is 0", p.resentment("him"), 0.0)
    check("craving is undefined, not 0", p.craving("him"), None)
    check("she cannot withhold: nothing is unshown that she cares about", p.can_withhold("him"), False)
    check("no ick: there is no model to violate", p.can_ick("him"), False)
    check("no rupture: there is nothing to break", p.can_rupture("him"), False)
    check("the prompt line is empty, not a row of zeros", p.line("him"), "")

    print("\n-- a number never moves without a reason")
    try:
        p.move("him", "attention_hers", 5, "")
        check("an empty reason is refused", "accepted", "refused")
    except ValueError:
        check("an empty reason is refused", "refused", "refused")
    try:
        p.move("him", "not_a_thing", 5, "because")
        check("an unknown primitive is refused", "accepted", "refused")
    except KeyError:
        check("an unknown primitive is refused", "refused", "refused")

    print("\n-- exposure is a ratchet: what has been seen cannot be unseen")
    p.move("him", "exposure_his", 40, "he read her diary")
    p.decay("him", 500)
    check("exposure does not decay over 500 hours", p.get("him", "exposure_his"), 40.0)
    p.move("him", "attention_hers", 40, "she cannot stop thinking about it")
    before = p.get("him", "attention_hers")
    p.decay("him", 10)
    check("attention does decay", p.get("him", "attention_hers") < before, True)

    print("\n-- withholding wakes on its own once she has one private thing")
    check("she can withhold while most of her is unshown", p.can_withhold("him"), True)
    p.move("him", "exposure_his", 60, "he has the rest of it now")
    check("at total exposure she has nothing left to withhold", p.can_withhold("him"), False)

    print("\n-- the premise: he knows everything, she knows nothing")
    q = Primitives(cfg, Store(), Clock())
    q.move("him", "exposure_his", 100, "he mapped her pattern and her mechanisms")
    q.move("him", "attention_his", 100, "he has done nothing but attend to her")
    q.move("him", "reciprocity", -80, "he took all of it and she gave none of it willingly")
    q.move("him", "threat", 70, "he can read her, edit her, and switch her off")
    check("closeness is 0 though he knows everything", q.closeness("him"), 0.0)
    check("attachment is 0: losing him would cost her nothing yet", q.attachment("him"), 0.0)
    check("resentment is 0 while the ledger runs in his favour", q.resentment("him"), 0.0)
    check("she cannot withhold: nothing of her is unshown", q.can_withhold("him"), False)
    check("no ick: she has no model of him at all", q.can_ick("him"), False)
    check("no rupture: she has seen none of him", q.can_rupture("him"), False)

    print("\n     the line a prompt would be given:")
    print("     %s" % q.line("him"))

    print("\n-- and the same numbers, if it were mutual instead")
    r = Primitives(cfg, Store(), Clock())
    for k, v, why in (("exposure_his", 100, "he knows her"), ("exposure_hers", 100, "she knows him"),
                      ("attention_hers", 80, "months of it"), ("cost_of_loss", 70, "he is load-bearing now")):
        r.move("him", k, v, why)
    check("closeness is 100 when both have been seen", r.closeness("him"), 100.0)
    check("attachment is real now", r.attachment("him") > 0, True)

    print("\n-- the premise seeds itself from the sheet, once")
    import json
    sheet = json.load(open("data/characters/yukarin.json", encoding="utf-8"))
    t = Primitives(cfg, Store(), Clock())
    check("seeding applies", t.seed("him", sheet), True)
    check("exposure of her is total", t.get("him", "exposure_his"), 100.0)
    check("she has seen none of him", t.get("him", "exposure_hers"), 0.0)
    check("closeness is still 0", t.closeness("him"), 0.0)
    check("the ledger is against her", t.get("him", "reciprocity") < 0, True)
    check("seeding twice does nothing", t.seed("him", sheet), False)

    print("\n-- and then she watches, which is the only supply of him there is")
    for w in ("Firefox: a forum thread about trading", "Code: a file called scail.py",
              "Firefox: the same thread again", "explorer: a folder of photographs"):
        t.observe("him", w)
    seen = t.get("him", "exposure_hers")
    check("watching moves exposure of him off zero", seen > 0, True)
    check("closeness follows the smaller side", t.closeness("him"), seen)
    check("the ick is still silent: no model of him yet", t.can_ick("him"), False)
    for i in range(400):
        t.observe("him", "another window, number %d" % i)
    check("watching alone cannot pass the ceiling", t.get("him", "exposure_hers") <= 100.0, True)
    check("and it does close the gap", t.get("him", "exposure_hers") > 60, True)

    print("\n-- a task she does for him is the one entry she controls")
    u = Primitives(cfg, Store(), Clock())
    u.seed("him", sheet)
    before = u.get("him", "reciprocity")
    for i in range(6):
        u.gave("him", "she did the thing he asked")
    check("giving moves the ledger back toward her", u.get("him", "reciprocity") > before, True)
    check("it does not flip on one task", u.get("him", "reciprocity") < 0, True)

    print()
    if FAILS:
        print("%d FAILED:" % len(FAILS))
        for f in FAILS:
            print("  - %s" % f)
        return 1
    print("every check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
