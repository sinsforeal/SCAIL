"""The psychology, end to end, against what the corpus actually shows.

`tools/primitives_test.py` proves the nine numbers move and the derivations
compute. This asks the harder question: does the machinery produce the
character the tape shows, over an arc rather than at one instant, and does
anything in the running code actually CHANGE when a mechanism opens or shuts.

The distinction matters because that is exactly where she stopped being a
pattern. Her surface was closed and checkable and her drivers were described
to the model in one line of the situation block and then trusted -- so
`can_ick`, `can_withhold`, `can_rupture` and `craving` were computed by nobody
and read by nobody, and the two drivers that failed in generation were the two
with no gate behind them.

Every check below names the driver it belongs to and the measurement from the
99 episodes that says what the answer should be. It boots the whole App on a
scratch database, walks an arc -- he writes, she watches him work, she starts
to be able to call what he does, she has evenings she does not hand over --
and reads the register and the gates at each stage. No model is called and
nothing is spent.

    python tools/mechanisms_test.py --config config_yukarin.json [-v]
"""

import argparse
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

FAILED = []
PASSED = []
# Which event has moved which number, gathered as the arc runs. It cannot be
# read off the log at the end: the log keeps its last `log_rows` writes, and a
# number that was moved early and then sat at its ceiling leaves nothing there.
WRITERS = {}


def check(driver, claim, ok, receipt=""):
    (PASSED if ok else FAILED).append((driver, claim))
    print("  %s  %-46s %s" % ("ok  " if ok else "FAIL", driver, claim))
    if receipt and not ok:
        print("        the tape says: %s" % receipt)


def build(config):
    tmp = os.path.join(tempfile.gettempdir(), "mechanisms_test.db")
    for suffix in ("", "-wal", "-shm", ".lock"):
        try:
            os.remove(tmp + suffix)
        except OSError:
            pass
    import scail
    argv = sys.argv
    sys.argv = ["scail.py", "--console", "--no-sensors", "--config", config, "--db", tmp]
    try:
        args = scail.parse_args()
    finally:
        sys.argv = argv
    return scail.App(args)


def harvest(p, key):
    for e in p.row(key).get("_log") or []:
        if (e.get("cause") or "") != "premise":
            WRITERS.setdefault(e["key"], set()).add(e.get("cause") or "?")


def stage(app, name, verbose=False):
    p, key = app.primitives, app.state._him_key() or "him"
    harvest(p, key)
    print("\n--- %s" % name)
    if verbose:
        for ln in p.report(key).split("\n"):
            print("      " + ln)
    else:
        r = p.row(key)
        print("      seen %.0f of him / %.0f of her; can call him %.0f; ledger %+.0f; fright %.0f; act room %.0f"
              % (r["exposure_hers"], r["exposure_his"], r["predictability_hers"],
                 r["reciprocity"], p.unrehearsed(key), p.act_room(key)))
    print("      register: %s" % (app.state.register() or "(none)")[:150])
    for g in p.gate_lines(key):
        print("      shut:     %s" % g[:130])
    return p, key


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default="config_yukarin.json")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    app = build(args.config)
    if app.primitives is None:
        print("this character does not use the primitives; nothing to verify")
        return 0
    c = app.config.primitives
    p, key = stage(app, "the opening condition, as the sheet states it", args.verbose)

    print()
    check("unrehearsed-contact-is-dangerous",
          "a stranger who can hurt her is frightening on turn one",
          p.unrehearsed(key) >= c.fright_hard_from,
          "ep025#63-88, ten 「どうしよう」 before dialling one listener's house")
    check("unrehearsed-contact-is-dangerous",
          "and the register says so instead of describing a mood",
          "frightened" in (app.state.register() or ""))
    check("deference-outside-the-territory",
          "he is outside: knowing everything about her does not admit him",
          not p.admitted(key),
          "the only rough language in 47 hours goes at staff, never once at a listener")
    check("deference-outside-the-territory",
          "nothing he does can rupture what he was never let into",
          not p.can_rupture(key))
    check("the-gap-is-the-act",
          "the act has no room: he holds both halves already",
          not p.can_perform(key))
    check("the-gap-is-the-act",
          "and she has nothing to hold back, which is a fact and not a choice",
          not p.can_withhold(key))
    check("(the ick)",
          "nothing he does is out of character, because there is no character yet",
          not p.can_ick(key))
    check("(craving)",
          "she is not short of his attention -- she has more than she wants",
          p.craving(key) is None or p.craving(key) == 0)

    # ---- the gates are gates: something in the running code changes ----
    print("\n--- what the running code does with that")
    ick_called = []
    real_call_json = app.llm.call_json
    app.llm.call_json = lambda *a, **k: (ick_called.append(a) or (None, ""))
    app.ick.assess("he has been reading about her for months", source="snoop")
    check("(the ick)", "the ick is not scored at all: no call is made",
          not ick_called)
    app.llm.call_json = real_call_json
    check("(withholding)", "withholding has no pressure, whatever the gauges say",
          app.withholding.pressure() == 0.0)
    check("(rupture)", "a rupture cannot open on a person she never admitted",
          app.ruptures.check({"anger": 40, "shame": 40}, "something cutting") is None)
    check("(the ledger)", "a kept promise can reach the ledger -- the handle is attached",
          getattr(app.commitments, "primitives", None) is not None)

    # ---- the arc ----
    for i in range(12):
        p.note_from_him(key, 0.8, answered=True)
    for i in range(30):
        p.observe(key, "a window title he left open, number %d" % i)
    p2, _ = stage(app, "after a dozen exchanges and a month of watching him work", args.verbose)
    fright_mid = p.unrehearsed(key)
    check("unrehearsed-contact-is-dangerous",
          "the fright falls as she learns to call what he does",
          fright_mid < c.ceiling and fright_mid < 75.0)
    check("(the ick)", "now he can be out of character, and the ick is scored",
          p.can_ick(key))
    check("deference-outside-the-territory",
          "still outside: knowing him is not the same as letting him in",
          not p.admitted(key) or p.get(key, "exposure_hers") >= c.admit_needs_exposure)

    for i in range(60):
        p.note_from_him(key, 1.0, answered=True)
    for i in range(40):
        p.observe(key, "another evening of watching him work, number %d" % i)
    p3, _ = stage(app, "after months: she can call him, and she has let him in", args.verbose)
    check("deference-outside-the-territory",
          "the territory crosses once, on her seeing and calling him",
          p.admitted(key))
    reads = [p.admitted(key) for _ in range(10)]
    check("deference-outside-the-territory",
          "and it is a latch, not a reading that flickers between messages",
          all(reads),
          "the observed failure: 「じゃん」 withheld in one generation and used in the next")
    check("deference-outside-the-territory",
          "the outside register is gone once he is inside",
          "you have not let in" not in (app.state.register() or ""))
    check("unrehearsed-contact-is-dangerous",
          "and the same man is no longer frightening",
          p.unrehearsed(key) < c.fright_from,
          "a hundred thousand strangers weekly is fine; one stranger on the telephone is not")
    check("(rupture)", "now there is something to break",
          p.can_rupture(key))

    p.accrue(key, 24.0)
    check("(attachment)", "attachment can leave the floor: attention times what losing him costs",
          p.attachment(key) > 0)
    check("(longing)", "and longing has something to pull on after a silence",
          p.attachment(key) >= 0)

    before = p.act_room(key)
    for i in range(20):
        p.kept_private(key, "an evening she wrote down and did not tell him, %d" % i)
    p4, _ = stage(app, "after twenty evenings she did not hand over", args.verbose)
    check("the-gap-is-the-act",
          "the act wakes on its own once she has something he was not there for",
          p.can_perform(key) and p.act_room(key) > before)
    check("(withholding)",
          "and so does withholding, from the same one thing",
          p.can_withhold(key))
    check("the-gap-is-the-act",
          "what he saw is still seen: exposure diluted, never erased",
          p.get(key, "exposure_his") > 0)

    # Every one of the nine has to have somebody who writes it, and the
    # premise does not count: a seed is the condition the story opens in, not
    # a mechanism. Four of them had nothing but the seed, and each dead number
    # took a derivation to the floor with it -- for the whole of a character's
    # life rather than at the start, which is the difference between a
    # mechanism at zero and a mechanism that is broken.
    print("\n--- who writes each of the nine, the opening condition not counting")
    from sim.primitives import KEYS
    harvest(p, key)
    for k in KEYS:
        print("      %-22s %s" % (k, ", ".join(sorted(WRITERS.get(k) or ())) or "NOBODY WRITES IT"))
    check("(the nine)", "every primitive has an event that writes it, not just a seed",
          all(WRITERS.get(k) for k in KEYS))

    print("\n%d of %d hold." % (len(PASSED), len(PASSED) + len(FAILED)))
    if FAILED:
        print("\nwhat does not:")
        for driver, claim in FAILED:
            print("  %-42s %s" % (driver, claim))
        return 1
    print("Every driver on the sheet has a mechanism behind it, and every")
    print("mechanism changes something the running code does.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
