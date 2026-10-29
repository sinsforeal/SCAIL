"""Drawing one of her replies again, and choosing which answer stands.

    python tools/swipes_test.py             # the whole thing, on a copy of the second character's save
    python tools/swipes_test.py --store     # the two tables and their readers only (what smoke runs)

No model call is ever made: `LLM.call` is replaced by a stub that returns a
fixed text and counts what it was asked, so what is checked is the wiring --
that the prompt kept against a delivered reply is byte for byte the one the
persona was actually sent, that looking at another answer changes nothing in
her record or in the thread she is next handed, and that keeping one changes
both and carries no other candidate with it.

What it checks, in order:

1. a reply delivered through the real path leaves a `reply_prompts` row whose
   messages are the persona call's own messages;
2. two draws leave two candidates under the models they were drawn on, and
   the reply she actually sent is candidate 0;
3. looking at a candidate leaves her record and the thread exactly as they
   were;
4. keeping candidate 2 puts its words in her record, in the thread's
   rendering of that message, and in the next thread build -- and puts no
   other candidate anywhere;
5. the toggle moves the model the next call in her voice goes out on, and
   leaves a role that is not her voice alone.
"""
import io
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FAILURES = []


def check(ok, what, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILURES.append(what)
    return ok


# ---------------------------------------------------------------- the tables

def store_only():
    """The two tables and their readers, on a temp save, with no App. This is
    the half smoke runs: it needs no character and no model."""
    from store import Store
    path = os.path.join(tempfile.gettempdir(), "swipes_tables.db")
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.remove(path + suffix)
    st = Store(path)
    ts = time.time()
    a = st.add_message(ts, "2026-09-04", "assistant", "one", tg_id=1801)
    b = st.add_message(ts + 1, "2026-09-04", "assistant", "two", tg_id=1802)
    messages = [{"role": "system", "content": "who she is"},
                {"role": "user", "content": "what he said"}]
    st.add_reply_prompt(a, "her", ts, "kimi-k3", messages, {"temperature": 1.0}, [a], "one\n\ntwo")
    st.extend_reply_prompt(a, b)
    got = st.reply_prompt(a)
    check(got is not None and got["messages"] == messages,
          "the prompt comes back the way it went in")
    check(got and got["msg_ids"] == [a, b], "every row of the burst is named on it",
          str(got and got["msg_ids"]))
    check((st.reply_prompt_for(b) or {}).get("msg_id") == a,
          "a swipe asked for on the second bubble finds the first bubble's prompt")
    check((st.message_by_tg_id(1802) or {}).get("id") == b,
          "a row is found by the channel's own id")
    check(st.next_swipe_n(a) == 0, "the first candidate is number 0")
    st.add_swipe(a, 0, "kimi-k3", "one\n\ntwo", ts=ts, prompt_tokens=100,
                 completion_tokens=10, cached_tokens=90, cost=0.001)
    st.add_swipe(a, 1, "glm-5.3", "another", ts=ts, prompt_tokens=100,
                 completion_tokens=12, cached_tokens=0, cost=0.002)
    check(st.next_swipe_n(a) == 2, "the next one after that is 2")
    rows = st.swipes_for(a)
    check([r["model"] for r in rows] == ["kimi-k3", "glm-5.3"],
          "the candidates come back in order, each under the model it was drawn on")
    check(rows[0]["cached_tokens"] == 90 and rows[1]["cached_tokens"] == 0,
          "what the host answered out of its cache is kept per candidate")
    st.add_swipe(a, 1, "glm-5.3", "another, again", ts=ts)
    check(len(st.swipes_for(a)) == 2 and st.swipes_for(a)[1]["text"] == "another, again",
          "a candidate written twice replaces itself rather than doubling")
    check((st.reply_prompt(a) or {})["sat"] == 0, "nothing is sitting until it is sat")
    st.sit_swipe(a, 1)
    check((st.reply_prompt(a) or {})["sat"] == 1, "and then that one is")
    check(a in st.reply_prompt_ids(5), "the reply is listed as one that can be drawn again")
    st.conn.close()


# ------------------------------------------------------------ the whole path

class Stub:
    """Every model call, answered from a script and counted. The role and the
    model each call went out on are kept, because what this test is about is
    which prompt and which model reached the client."""

    def __init__(self, config):
        self.config = config
        self.calls = []
        self.answers = {}
        self.default = "stub answer"

    def call(self, role, messages, max_tokens=None, _model=None, _provider=None, _json=False):
        model = (_model or self.config.model(role) or {}).get("model", "")
        self.calls.append({"role": role, "messages": list(messages), "model": model})
        return self.answers.get(role, self.default)

    def call_json(self, role, messages, max_tokens=None):
        self.call(role, messages, _json=True)
        return None, ""

    def last(self, role):
        for c in reversed(self.calls):
            if c["role"] == role:
                return c
        return None


def full():
    from tools import harness
    from sim.thread import Thread
    tmp = os.path.join(tempfile.gettempdir(), "swipes_test.db")
    print("[swipes] building the second character on a copy of her save")
    app = harness.build_on(tmp, "config_yukarin.json", "data/yukarin.db")

    # No model call, ever. The stub keeps the LLM's own reporting surface
    # alive (`last_usage`, `effective_model`, the voice roles) because the
    # code under test reads it.
    real = app.llm
    stub = Stub(app.config)
    stub.VOICE_ROLES = real.VOICE_ROLES
    stub.last_usage = {"prompt_tokens": 41000, "completion_tokens": 90,
                       "prompt_tokens_details": {"cached_tokens": 39000}}
    stub.active_provider = real.active_provider
    stub.effective_model = real.effective_model
    stub.voice_models = real.voice_models
    stub.voice_model_cmd = real.voice_model_cmd
    stub.voice_model_report = real.voice_model_report
    stub.store = real.store
    app.llm = stub
    app.persona.llm = stub
    stub.answers["persona"] = "the answer she sent\n\nand a second bubble"

    # ---- 1. a reply through the real path
    scene = app.store.last_scene() or {"location": "home", "activity": "sitting",
                                       "phone_access": "free", "with": "", "inner": ""}
    unread = [{"id": 0, "ts": app.clock.now_ts(), "text": "say something",
               "role": "user", "date": app.clock.date_str()}]
    bubbles, voice = app.persona.generate(dict(scene), "", unread)
    check(bool(bubbles), "the reply came out of the real persona path",
          " // ".join(b[:40] for b in bubbles))
    receipt = stub.last("persona")
    app.delivery.send_bubbles(bubbles, self_started=False)
    for _ in range(200):
        if not app.delivery.busy():
            break
        time.sleep(0.05)
    rows = [m for m in app.store.recent_messages(6) if m["role"] == "assistant"][-len(bubbles):]
    anchor = rows[0]["id"]
    got = app.store.reply_prompt(anchor)
    check(got is not None, "the delivered reply left the prompt it was drawn from")
    if got:
        check(got["messages"] == receipt["messages"],
              "and that prompt is the persona call's own messages, byte for byte",
              f"{len(got['messages'])} messages, {sum(len(m['content']) for m in got['messages'])} chars")
        check([int(i) for i in got["msg_ids"]] == [r["id"] for r in rows],
              "every bubble of the burst is named on it", str(got["msg_ids"]))
        check(got["model"] == real.effective_model("persona"),
              "under the model her voice was on", str(got["model"]))
        cand0 = app.store.swipes_for(anchor)
        check(len(cand0) == 1 and cand0[0]["n"] == 0,
              "what she actually sent is candidate 0")
        check(cand0 and cand0[0]["cached_tokens"] == 39000,
              "with what the host answered out of its cache")

    # ---- 2. two draws, on two models
    from persona import delivery as swipes
    stub.answers["persona"] = "a second way of saying it"
    out = swipes.swipe(app, anchor, model="stub-model-one")
    check("answer 1 on stub-model-one" in out, "the first draw is answer 1", out.splitlines()[0][:80])
    stub.answers["persona"] = "a third way, quite different"
    out = swipes.swipe(app, anchor, model="stub-model-two")
    check("answer 2 on stub-model-two" in out, "the second draw is answer 2", out.splitlines()[0][:80])
    cands = app.store.swipes_for(anchor)
    check([c["model"] for c in cands][1:] == ["stub-model-one", "stub-model-two"],
          "each candidate is under the model it was drawn on")
    check(stub.last("persona")["messages"] == got["messages"],
          "a draw sends the FROZEN prompt, not one rebuilt from where she is now")

    # ---- 3. looking changes nothing
    before_text = [app.store.message_by_id(r["id"])["text"] for r in rows]
    thread = Thread(app.config, app.store, app.clock)
    before_thread = thread.build()
    check(before_text == bubbles, "her record still holds what she sent", str(before_text)[:80])
    check(not any("a third way" in m["content"] for m in before_thread),
          "and the thread she is next handed carries no candidate she did not send")

    # ---- 4. keeping candidate 2
    out = swipes.sit(app, anchor, 2)
    print("   " + out.replace("\n", "\n   ")[:600])
    after = [app.store.message_by_id(r["id"]) for r in rows]
    after = [a["text"] for a in after if a]
    check(any("a third way" in t for t in after),
          "her record now holds the answer he kept", str(after)[:80])
    check((app.store.reply_prompt(anchor) or {})["sat"] == 2, "and the record says which one is sitting")
    after_thread = Thread(app.config, app.store, app.clock).build()
    joined = "\n".join(m["content"] for m in after_thread)
    check("a third way" in joined, "the next thread build carries it")
    check("a second way of saying it" not in joined and "the answer she sent" not in joined,
          "and carries no other candidate and not the reply it replaced")

    # ---- 5. the toggle
    offered = real.voice_models()
    check(bool(offered), "the toggle has models to offer", ", ".join(offered))
    pick = offered[-1]
    print("   " + real.voice_model_cmd(pick))
    check(real.effective_model("persona") == pick, "her voice is on the one he picked")
    check(real.effective_model("state") != pick or pick == app.config.model("state")["model"],
          "and a role that is not her voice is left alone",
          f"state is on {real.effective_model('state')}")
    stub.answers["persona"] = "drawn on the toggled model"
    swipes.swipe(app, anchor)
    check(stub.last("persona")["model"] == pick,
          "and a draw with no model named goes out on it", stub.last("persona")["model"])
    real.voice_model_cmd("auto")
    check(real.effective_model("persona") == app.config.model("persona")["model"],
          "auto gives the roles back their config entries")
    print(f"[swipes] {len(stub.calls)} stubbed model call(s), none paid for")


def main():
    if "--store" in sys.argv:
        store_only()
    else:
        store_only()
        full()
    print(f"[swipes] {'FAILED: ' + ', '.join(FAILURES) if FAILURES else 'all clear'}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
