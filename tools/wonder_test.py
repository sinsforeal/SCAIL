"""Questions about him without the model: the gates, forming (stubbed
call), the intent's candidates, asking, and what his answer does to a
belief / to attachment / to curiosity. On a copy of the save.

    python tools/wonder_test.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import harness  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.setup = lambda out_dir: None
logger.log = lambda m, to_console=True: print("   log:", m[:120])



def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_wonder.db")
    app = harness.build_on(tmp)
    wd, st, store = app.wonder, app.state, app.store
    # This local state test uses a stubbed role; keep the hosted classifier out
    # until the focused verdict check below, where its answer is also stubbed.
    wd.typesafe = None
    fails = []

    def check(label, ok):
        print(("  ok   " if ok else "  FAIL ") + label)
        if not ok:
            fails.append(label)

    store.set("questions", [])
    store.set("wonder_counts", {})
    store.set("wonder_last_ts", 0)
    store.set("wonder_seed", {})
    base = float(app.config.state.gauges["curiosity"]["baseline"])
    st.gauges["curiosity"] = base
    check(f"nothing pulling at rest: {wd.due()}", wd.due()[0] is False)
    st.gauges["curiosity"] = base + 30
    check(f"curiosity over rest -> due: {wd.due()}", wd.due()[0])
    st.gauges["curiosity"] = base
    wd.seed("the app")
    check(f"a look seeds one: {wd.due()}", wd.due()[0])
    # form, with the model stubbed
    real = app.llm.call_json
    answers = {"verdict": "confirmed", "learned": "he does actually watch them", "fact": "he watches what she sends him, usually the same night"}

    def stub(role, messages, max_tokens=None):
        if role == "wonder":
            return ({"questions": [
                {"text": "does he actually watch the stuff i send or just say he did", "kind": "test_him", "belief": "sees_me", "self_belief": "",
                 "if_yes": "he does see me", "if_no": "he says what i want to hear", "charge": 70, "straight": True},
                {"text": "does he get like this too, where he can't say the thing", "kind": "compare_self", "belief": "", "self_belief": "seen_undoes_me",
                 "if_yes": "he is like me", "if_no": "he is not", "charge": 55, "straight": False},
                {"text": "why is he on the charts at 7 every morning", "kind": "understand", "belief": "", "self_belief": "",
                 "if_yes": "", "if_no": "", "charge": 40, "straight": True}]}, "")
        if role == "wonder_answer":
            return (dict(answers), "")
        return real(role, messages, max_tokens)
    app.llm.call_json = stub
    added = wd.maybe({"location": "her room"})
    check(f"three questions formed: {[q['id'] for q in added]}", len(added) == 3 and all(q["state"] == "open" for q in added))
    check("cooldown after forming", wd.due()[1] == "cooldown")
    check("her prompt carries the two she is turning over", wd.situation_line().count("/") == 1 and "wondering" in wd.situation_line())
    il = wd.intent_line()
    check(f"the intent gets them by id, charge first: {il[:60]}", il.startswith(f"[{added[0]['id']}]") and "circle" in il)
    # ask the test_him one; his answer confirms
    q1 = added[0]
    b0 = app.model_of_him.get("sees_me")
    s0 = app.model_of_him.live_strain(b0) if b0 else None
    wd.note_asked(q1["id"], "did u actually watch the thing i sent or")
    check("asked", wd.find(q1["id"])["state"] == "asked")
    r = wd.on_his_message("yeah i watched it last night, the ending was rough")
    b1 = app.model_of_him.get("sees_me")
    check(f"his answer confirms sees_me: {r['answer']['verdict'] if r else None}", r and r["state"] == "answered" and r["answer"]["verdict"] == "confirmed")
    facts = [f["fact"] if isinstance(f, dict) else f for f in store.user_facts()[-3:]]
    check(f"...and a fact is kept: {[str(f)[:50] for f in facts][-1:]}", any("watches what she sends" in str(f) for f in facts))
    # ask the compare_self one; he is like her
    q2 = added[1]
    him = st._him_key() or "him"
    a0 = app.sentiments.live(him, "attachment")
    wd.note_asked(q2["id"], "do u ever just not manage to say the thing")
    answers.update({"verdict": "confirmed", "learned": "he does that too", "fact": ""})
    wd.on_his_message("all the time honestly")
    a1 = app.sentiments.live(him, "attachment")
    check(f"he is like her -> attachment {a0:.1f} -> {a1:.1f}", a1 > a0)
    # ask the understand one; he dodges
    q3 = added[2]
    c0 = st.gauges.get("curiosity", 0)
    wd.note_asked(q3["id"], "whats with the charts every morning")
    answers.update({"verdict": "dodged", "learned": "", "fact": ""})
    wd.on_his_message("lol anyway did you eat")
    q3n = wd.find(q3["id"])
    check(f"dodged: still standing, curiosity {c0:.0f} -> {st.gauges.get('curiosity', 0):.0f}, charge {q3['charge']} -> {q3n['charge']}",
          q3n["state"] == "asked" and st.gauges.get("curiosity", 0) > c0 and q3n["charge"] > 40)
    # a message about something else leaves an asked question open
    wd.note_asked(q3["id"], "no really whats with the charts")
    answers.update({"verdict": "not_answered"})
    r = wd.on_his_message("just had lunch")
    check("a message about something else does not settle it", r is None and wd.find(q3["id"])["state"] == "asked")

    class VerdictClassifier:
        def ready(self, name): return name == "wonder_answer"
        def use(self, name): return {"threshold": 0.5}
        def ask(self, name, state, questions): return {"verdict": "confirmed"}
        def choice(self, answers, key): return answers[key], 0.9

    wd.typesafe = VerdictClassifier()
    answers.update({"verdict": "confirmed", "learned": "he read it", "fact": "he reads her notes"})
    check("classifier keeps agreeing learned text and fact",
          wd._verdict("his answer confirms it") == ("confirmed", "he read it", "he reads her notes"))
    answers["verdict"] = "disconfirmed"
    check("classifier drops prose that contradicts its verdict",
          wd._verdict("his answer confirms it") == ("confirmed", "", ""))
    print(wd.report())
    print(f"\n{len(fails)} failure(s)" if fails else "\nall ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
