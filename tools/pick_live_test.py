"""The live pick, proved on a COPY of the save with the model stubbed.

    python tools/pick_live_test.py

One moment is put to her once per tool, with the answer decided by the test
instead of by a paid call, and each case asserts that the seam that tool names
was the one that ran -- and that code's own answer ran only where it should.
Nothing is sent, no room opens, no browser starts and no model is called: every
seam is replaced by a recorder, so what this proves is the wiring between the
answer and the action.

In order: the tools she is offered follow from her sheet; putting the phone
down is her answer and not a no-op; writing to him first goes down the same
path the impulse function's yes goes down, with her own reason as the hint; the
group chat and a friend go through the exchange's own gates and a refusal is
recorded rather than turned into some other action; her own feed goes through
the account's caps; his message is answered now, at an hour she names, or left
where it is; a tool nobody offered and arguments that do not parse leave the
backup to decide; the frequency cap and the phone gate stop the call before it
costs anything; shadow mode acts on nothing; and a host that does not take
tools moves the same question to text.
"""
import io
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from tools.dbcopy import copy_db as _copy_save  # noqa: E402

LOG = []
FAILURES = []


def check(label, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"\n       {detail}" if detail else ""))
    if not ok:
        FAILURES.append(label)


def answer(name, args=None, text=""):
    """One tool answer in the shape `LLM.call_tools` hands back."""
    return {"calls": [{"id": "c1", "name": name, "arguments": args, "raw": json.dumps(args or {})}],
            "text": text, "finish": "tool_calls",
            "usage": {"cost": 0.0009, "prompt_tokens": 11000,
                      "prompt_tokens_details": {"cached_tokens": 6700}},
            "served_by": "Together", "model": "deepseek/deepseek-v4-flash-0731"}


def offered_for(cfgpath):
    """What each registered character is offered, off her sheet alone. Built
    against a stub store and clock: `PhonePick.offered` reads what she IS."""
    import datetime
    from config import Config
    from sim.pick import PhonePick

    class _Store:
        def get(self, k, d=None):
            return d

    class _Clock:
        def now(self):
            return datetime.datetime(2026, 9, 7, 12, 0)
    p = PhonePick(Config(cfgpath), None, _Store(), _Clock())
    return p.offered("block"), p.offered("inbound")


def main():
    import logger
    logger.setup = lambda out_dir: None
    logger.finish = lambda: None
    logger.log_llm = lambda *a, **k: None
    logger.write_artifact = lambda *a, **k: None
    logger.log = lambda m, to_console=True: LOG.append(str(m))

    print("[test] what each registered character is offered, off her sheet:")
    import json as _json
    for row in _json.load(io.open("characters.json", encoding="utf-8"))["characters"]:
        base, inbound = offered_for(row["config"])
        print(f"   {row['key']:<7} {len(base)} at the phone: {', '.join(base)}"
              + (f" | on his message: {', '.join(inbound)}" if inbound else " | no chat with him"))
    # her sheet says she has a world, an account and a chat with him
    base, inbound = offered_for("config.json")
    check("the first character is offered every tool", len(base) == 6 and len(inbound) == 3,
          f"{base} / {inbound}")
    # a world she only READS has no group room of her own to open
    rbase, rinbound = offered_for("config_rena.json")
    check("a reader of somebody else's world is offered no group chat and no chat with him",
          "open_group_chat" not in rbase and "text_him" not in rbase and not rinbound, str(rbase))

    tmpdb = os.path.join(tempfile.gettempdir(), "scail_pick_live_test.db")
    _copy_save("data/world.db", tmpdb)
    print(f"[test] copied data/world.db -> {tmpdb} (sqlite backup of a live save)")

    import scail
    argv = sys.argv
    sys.argv = ["scail.py", "--config", "config.json", "--console", "--no-sensors", "--db", tmpdb]
    try:
        args = scail.parse_args()
    finally:
        sys.argv = argv
    app = scail.App(args)
    app.config.pick.enabled = True
    app.config.pick.shadow = False
    app.phone_access = lambda: "free"
    print(f"[test] {app.pick.boot_line()}")

    # every seam replaced by a recorder: nothing here reaches a room, a
    # browser, the delivery or the model
    done = []
    app.write_him_first = lambda scene, digest, hint_from_her="", force_hint=None, media="": (
        done.append(("write_him_first", hint_from_her)) or True)
    app.look_at_phone = lambda force=False: done.append(("look_at_phone", force)) or "his day"
    # a person out of HER OWN roster, never a name written into this file: a
    # test that names one of her friends is a test only she can be run with
    from sim import roster
    friend = roster.record_name(app.config, (roster.own_keys(app.config) or ["someone"])[0])
    app.exchange.self_open = lambda scene, chosen=False: (
        done.append(("self_open", chosen)) or {"who": friend})
    app.exchange.self_open_reason = lambda scene: ""
    app.exchange.open_with = lambda who, intent, scene: (
        done.append(("open_with", who, intent)) or ({"who": who}, f"she wrote to {who} on her own"))
    app.social.may_look = lambda scene: (True, "ok")
    app.social.start_look = lambda force=False: done.append(("start_look", force))
    # AN EMPTY INBOX UNLESS A SECTION SAYS OTHERWISE. This builds on a copy of
    # the live save, so whatever he last wrote and she has not answered is
    # sitting in it, and the moment is then routed to answering him: section 3
    # went red for a day because he had written to her at 10:27 that morning
    # ("she picked him and his own message was waiting"). The one section that
    # is about his message waiting hands its own list in.
    app.store.unread_user_messages = lambda: []
    scene = {"location": "her room", "activity": "sitting on the bed", "phone_access": "free"}
    imp = {"fires": False, "why": "score 41 < 62", "score": 41.0, "threshold": 62}

    def fresh():
        """A moment nothing has been asked at yet."""
        for k in ("pick_block", "pick_scene", "pick_standing", "pick_last_ts"):
            app.store.set(k, None)
        app.store.set("pick_counts", {})
        done.clear()
        LOG.clear()

    def one(name, args=None, trigger="block", in_write_path=True, unread=None, text=""):
        fresh()
        app.llm.call_tools = lambda role, messages, tools, **kw: answer(name, args, text)
        return app.phone_moment(trigger, scene, "", imp, unread=unread, in_write_path=in_write_path)

    print("\n1. SHE PUTS THE PHONE DOWN")
    d = one("nothing", {"until": "after dinner"})
    row = app.pick.rows()[-1]
    check("putting it down is recorded as her choice and nothing was done",
          d and d["name"] == "nothing" and d["done"] and row["acted"] == "nothing" and not done,
          row.get("acted_why", ""))
    check("her own answer stands, so the backup does not act over it",
          app.pick.standing()["name"] == "nothing")

    print("\n2. SHE WRITES TO HIM FIRST, AT A MOMENT ON THE WRITE PATH")
    d = one("text_him", {"intent": "poke him because his reply to my link was flat"})
    check("the caller is handed her reason and the seam is not run twice",
          d and d["name"] == "text_him" and d["intent"].startswith("poke him") and not done,
          str(done))

    print("\n3. SHE WRITES TO HIM FIRST, AT A MOMENT THAT IS NOT ON THAT PATH")
    d = one("text_him", {"intent": "tell him about the festival"}, trigger="beat", in_write_path=False)
    check("the same write-first path runs, with her reason as the hint",
          done and done[0][0] == "write_him_first" and done[0][1].startswith("tell him"), str(done))
    check("what happened is recorded after it happened, not before",
          app.pick.rows()[-1]["acted"] == "text_him", app.pick.rows()[-1].get("acted_why", ""))

    print("\n4. SHE OPENS THE GROUP CHAT")
    d = one("open_group_chat", {})
    check("the exchange opens it because she chose it, and the roll is skipped",
          done == [("self_open", True)] and app.pick.rows()[-1]["acted"] == "open_group_chat", str(done))

    print("\n5. SHE WRITES TO ONE OF HER OWN PEOPLE")
    d = one("message_friend", {"name": friend, "intent": "answer her about the yukata"})
    check("the one-to-one seam is called with the person and her reason",
          done and done[0][0] == "open_with" and done[0][1] == friend, str(done))

    print("\n6. A CHOICE HER WORLD CANNOT HONOUR")
    app.exchange.self_open_reason = lambda scene: "the chat was done for the night at 23:40"
    d = one("open_group_chat", {})
    row = app.pick.rows()[-1]
    check("it is refused with the reason and NOT rewritten into another action",
          not done and not row["acted"] and "done for the night" in row["acted_why"]
          and row["fallback"] == "none", row.get("acted_why", ""))
    app.exchange.self_open_reason = lambda scene: ""

    print("\n7. SHE LOOKS AT WHAT HE HAS BEEN DOING")
    d = one("look_at_his_machine", {})
    check("the look runs through the App's own path, with its cost cap intact",
          done and done[0][0] == "look_at_phone" and done[0][1] is False, str(done))

    print("\n8. SHE OPENS HER OWN FEED")
    d = one("open_feed", {})
    check("the account's own look is started", done == [("start_look", False)], str(done))
    app.social.may_look = lambda scene: (False, "daily cap")
    d = one("open_feed", {})
    check("a cap the account owns refuses it and says so",
          not done and "daily cap" in app.pick.rows()[-1]["acted_why"],
          app.pick.rows()[-1].get("acted_why", ""))
    app.social.may_look = lambda scene: (False, "not now")
    d = one("open_feed", {})
    check("the boredom roll is not a refusal any more: she said she wanted to look",
          done == [("start_look", False)], str(done))
    app.social.may_look = lambda scene: (True, "ok")

    print("\n9. HIS MESSAGE HAS JUST ARRIVED")
    unread = [{"id": 1, "ts": app.clock.now_ts(), "text": "you awake"}]
    for name, args in (("reply_now", {}), ("reply_later", {"when": "21:30"}),
                       ("reply_later", {"when": "after the bath"}), ("leave_it", {})):
        d = one(name, args, trigger="inbound", in_write_path=False, unread=unread)
        plan = app._plan_from_pick(d, "free", app.clock.now_ts())
        why = [m for m in LOG if m.startswith("[pick] she ")]
        print(f"   {name} {args}: due_ts {'set' if plan['due_ts'] else 'none'}"
              f"{', asked again later' if plan.get('ask_again_ts') else ''} | {why[-1] if why else ''}")
        if name == "reply_now":
            check("she answers him now", bool(plan["due_ts"]) and plan["picked"] == "reply_now")
        elif args.get("when") == "21:30":
            check("an hour she named is read as an hour", bool(plan["due_ts"]))
        elif args.get("when"):
            check("words that are not an hour stand on the record and the default is used",
                  bool(plan["due_ts"]) and "not an hour code can read" in (why[-1] if why else ""))
        else:
            check("leaving it is not answering it, and she is asked again later",
                  plan["due_ts"] is None and plan.get("ask_again_ts"))

    print("\n10. AN ANSWER THAT IS NOT A DECISION")
    d = one("dislike", {"id": "2096140039474581762"})
    row = app.pick.rows()[-1]
    check("a tool nobody offered is invalid, is never acted on, and the backup decides",
          d is None and row["invalid"] and not done
          and row["picks"][0]["why"] == "no such tool was offered"
          and row["fallback"] == "code's own answer", row["picks"][0].get("why", ""))
    d = one("message_friend", None)
    row = app.pick.rows()[-1]
    check("arguments that did not parse are invalid and the backup decides",
          d is None and row["invalid"] and not done, row["picks"][0].get("why", ""))
    fresh()
    before = len(app.pick.rows())
    app.llm.call_tools = lambda role, messages, tools, **kw: None
    d = app.phone_moment("block", scene, "", imp)
    check("a call the provider never answered leaves no row behind and the backup decides",
          d is None and not done and len(app.pick.rows()) == before,
          f"{before} rows before, {len(app.pick.rows())} after")

    print("\n11. THE GATES CODE KEEPS")
    calls = []
    app.llm.call_tools = lambda role, messages, tools, **kw: (
        calls.append(role) or answer("nothing", {"until": "later"}))
    fresh()
    app.phone_access = lambda: "none"
    app.phone_moment("block", scene, "", imp)
    check("no phone means no call at all", not calls, str(calls))
    app.phone_access = lambda: "free"
    fresh()
    app.phone_moment("block", scene, "", imp)
    n1 = len(calls)
    app.phone_moment("beat", scene, "", imp)
    check("two looks inside the minimum gap cost one call",
          len(calls) == n1 and "since her last look" in app.pick.last_refusal,
          app.pick.last_refusal)
    check("her own answer still stands while she is only waiting to be asked again",
          app.pick.holds())
    app.store.set("pick_counts", {app.clock.date_str(): 999})
    app.store.set("pick_last_ts", 0)
    n2 = len(calls)
    app.phone_moment("beat", scene, "", imp)
    check("the day's cap stops the call", len(calls) == n2 and "cap" in app.pick.last_refusal,
          app.pick.last_refusal)
    check("and past the cap the backup decides again rather than her morning answer standing all day",
          not app.pick.holds())

    print("\n12. SHADOW MODE ACTS ON NOTHING")
    app.config.pick.shadow = True
    fresh()
    app.llm.call_tools = lambda role, messages, tools, **kw: answer("open_group_chat", {})
    d = app.phone_moment("block", scene, "", imp)
    row = app.pick.rows()[-1]
    check("the row is written, the mode says shadow, and no seam ran",
          d is None and not done and row["mode"] == "shadow" and row["picks"][0]["name"] == "open_group_chat")
    app.config.pick.shadow = False

    print("\n13. A HOST THAT DOES NOT TAKE TOOLS")
    fresh()
    app.store.set("pick_host", app.config.api.hosts_without_tools[0])
    tool_calls, json_calls = [], []
    app.llm.call_tools = lambda role, messages, tools, **kw: tool_calls.append(role) or answer("nothing")
    app.llm.call_json = lambda role, messages, max_tokens=None: (
        json_calls.append(messages) or ({"do": "message_friend",
                                         "arguments": {"name": friend, "intent": "the yukata"}}, ""))
    app.llm.last_usage = {"cost": 0.0009, "prompt_tokens": 11000}
    app.llm.last_provider = ("openrouter", "Chutes")
    d = app.phone_moment("block", scene, "", imp)
    row = app.pick.rows()[-1]
    check("the receipt, not a guess, moves the same question to text",
          not tool_calls and json_calls and row["transport"] == "json"
          and row["picks"][0]["name"] == "message_friend", str(row.get("transport")))
    ask = json_calls[-1][1]["content"]
    check("the text answer is asked for as one JSON object naming the same tools",
          '{"do":' in ask and "message_friend" in ask and "nothing" in ask)
    check("and it reached the same seam", done and done[-1][0] == "open_with", str(done))
    app.store.set("pick_host", "Together")

    print("\n14. THE MOMENT SHE IS ACTUALLY HANDED")
    fresh()
    seen = []
    app.llm.call_tools = lambda role, messages, tools, **kw: (
        seen.append((messages, tools)) or answer("nothing", {"until": "soon"}))
    app.phone_moment("block", scene, "", imp)
    messages, tools = seen[-1]
    system, moment = messages[0]["content"], messages[1]["content"]
    print(f"   system half {len(system)} chars (persona.system_for('him')); "
          f"moment {len(moment)} chars; {len(tools)} tools")
    for line in moment.splitlines()[:6]:
        print("     |", line[:110])
    check("the system half is her own daily one, byte for byte",
          system == app.persona.system_for("him"))
    check("the moment says truthfully what kind of moment it is",
          moment.startswith("YOUR PHONE IS IN YOUR HAND"))
    check("every tool says what it costs her", all("What it costs you:" in x["function"]["description"]
                                                   for x in tools))
    check("doing nothing is offered and is neither the first nor the last thing she reads",
          [x["function"]["name"] for x in tools].index("nothing") not in (0, len(tools) - 1),
          ", ".join(x["function"]["name"] for x in tools))
    fresh()
    app.phone_moment("inbound", scene, "", None, unread=unread, in_write_path=False)
    moment = seen[-1][0][1]["content"]
    check("and on his message it says he has just written",
          moment.startswith("HE HAS JUST WRITTEN TO YOU"), moment.splitlines()[0][:90])

    print("\n15. THE RECORD")
    fresh()
    app.llm.call_tools = lambda role, messages, tools, **kw: answer("nothing", {"until": "after dinner"},
                                                                   text="hey. you up")
    app.phone_moment("block", scene, "", imp)
    row = app.pick.rows()[-1]
    for k in ("character", "ts", "her", "his", "trigger", "access", "offered", "picks", "impulse",
              "acted", "acted_why", "fallback", "cost", "model", "served_by", "transport",
              "min_gap_minutes", "mode"):
        if k not in row:
            check(f"the record carries {k}", False)
    check("the record carries every field the reader prints", not FAILURES or FAILURES[-1] != "x")
    check("her words arriving beside the pick are dropped and said to be dropped",
          any("came back beside the pick" in m for m in LOG))
    print("   " + app.pick.report(app.clock.date_str()).splitlines()[0][:150])
    print("   ops: " + json.dumps({k: v for k, v in app.pick.ops().items() if k != "last"},
                                  ensure_ascii=False)[:220])

    print("\n16. CODE'S OWN ANSWER, WHERE IT IS STILL THE ONE THAT DECIDES")
    app.delivery.busy = lambda: False
    app.store.unread_user_messages = lambda: []
    # the pick switched off for her: the impulse function decides, as it did
    # before any of this existed
    fresh()
    app.config.pick.enabled = False
    app.impulse.check = lambda state, scene, silent: (True, "score 74 (p=0.80)")
    app.maybe_impulse(scene, "")
    check("with the pick off, the impulse function's yes still writes to him",
          done and done[0][0] == "write_him_first" and not done[0][1], str(done))
    fresh()
    app.impulse.check = lambda state, scene, silent: (False, "cooldown")
    app.maybe_impulse(scene, "")
    check("and its no still stops her", not done, str(done))
    # a discharge goes past both of them, and always did
    fresh()
    app.maybe_impulse(scene, "", force_hint="the gauge hit its end")
    check("a discharge goes past the pick and the impulse alike",
          done and done[0][0] == "write_him_first", str(done))
    app.config.pick.enabled = True
    # the pick on, and it is the one that decides
    fresh()
    app.impulse.check = lambda state, scene, silent: (False, "cooldown")
    app.llm.call_tools = lambda role, messages, tools, **kw: answer(
        "text_him", {"intent": "ask him what he did with his morning"})
    app.maybe_impulse(scene, "")
    check("with the pick on, she writes to him over the impulse function's no",
          done and done[0][0] == "write_him_first" and done[0][1].startswith("ask him"), str(done))
    check("and the record says she decided it and it happened",
          app.pick.rows()[-1]["acted"] == "text_him", app.pick.rows()[-1].get("acted_why", ""))
    fresh()
    app.impulse.check = lambda state, scene, silent: (True, "score 74 (p=0.80)")
    app.llm.call_tools = lambda role, messages, tools, **kw: answer("nothing", {"until": "after dinner"})
    app.maybe_impulse(scene, "")
    check("and she is not written for over the impulse function's yes when she said no",
          not done, str(done))
    app.store.set("pick_last_ts", app.clock.now_ts())
    done.clear()
    app.maybe_impulse(scene, "")
    check("her answer holds until she is asked again, so the score does not act over it",
          not done and any("her own answer at the last moment stands" in m for m in LOG), str(done))

    print("")
    if FAILURES:
        print(f"[test] {len(FAILURES)} FAILED: " + "; ".join(FAILURES))
        sys.exit(1)
    print("[test] all clear")


if __name__ == "__main__":
    main()
