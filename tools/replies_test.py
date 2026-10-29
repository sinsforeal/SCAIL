"""Answering somebody who answered her, proved end to end on a COPY of the
save with the browser stubbed out. Nothing is sent and nothing real is written:
the X store is redirected to a temporary directory and the sender is a stub
that says the reply left the box.

    python tools/replies_test.py

What it shows, in order: the first read-in is a baseline and answers nothing;
a reply under a post from before the cutoff never becomes a candidate; a reply
whose id is already in her sent record is refused; the one left gets a judge
call with no character sheet and a voice call with her whole assembly; the
record that she answered is written only after the send confirms.
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from tools.dbcopy import copy_db as _copy_save  # noqa: E402

LOG = []


def main():
    tmpdb = os.path.join(tempfile.gettempdir(), "scail_replies_test.db")
    _copy_save("data/world.db", tmpdb)
    print(f"[test] copied data/world.db -> {tmpdb} (sqlite backup of a live save)")

    import logger
    logger.setup = lambda out_dir: None
    logger.finish = lambda: None
    logger.log_llm = lambda *a, **k: None
    logger.write_artifact = lambda *a, **k: None

    def cap(m, to_console=True):
        LOG.append(str(m))
    logger.log = cap

    # the account's own files go to a scratch directory: this test never
    # appends a row to the real action log
    xdir = os.path.join(tempfile.gettempdir(), "scail_replies_x")
    os.makedirs(xdir, exist_ok=True)
    # a re-run starts clean, so the action log it reads back is this run's
    for f in os.listdir(xdir):
        os.remove(os.path.join(xdir, f))
    from sensors import x_monitor as xm
    xm._paths = lambda config: {
        "feed": os.path.join(xdir, "feed.jsonl"), "seen": os.path.join(xdir, "seen.json"),
        "sessions": os.path.join(xdir, "sessions.json"), "actions": os.path.join(xdir, "actions.jsonl"),
        "likes": os.path.join(xdir, "likes.jsonl"), "likes_seen": os.path.join(xdir, "likes_seen.json"),
        "following": os.path.join(xdir, "following.json"), "followers": os.path.join(xdir, "followers.json"),
        "accounts": os.path.join(xdir, "accounts.json"), "status": os.path.join(xdir, "status.json"),
        "follow_changes": os.path.join(xdir, "follow_changes.jsonl"),
        "trends": os.path.join(xdir, "trends.json"),
    }

    import scail
    argv = sys.argv
    sys.argv = ["scail.py", "--config", "config.json", "--console", "--no-sensors", "--db", tmpdb]
    try:
        args = scail.parse_args()
    finally:
        sys.argv = argv
    app = scail.App(args)
    rp, cur = app.replies, app.social.curation
    print(f"[test] cutoff: nothing before {app.config.x.replies_not_before}; "
          f"cap {app.config.x.replies_max_per_day} in 24h, cooldown {app.config.x.reply_cooldown_minutes} min")

    old_post = {"status_id": "2090000000000000001", "status_path": "/her/status/2090000000000000001",
                "text": "彼の頃のポスト", "timestamp": "2026-08-20T11:00:00.000Z"}
    new_post = {"status_id": "2096154937608597662", "status_path": "/her/status/2096154937608597662",
                "text": "電車の中、みんなスマホ見てる。私もその一人。", "timestamp": "2026-09-02T13:50:00.000Z"}
    r_old = {"status_id": "3000000000000000001", "status_path": "/a/status/3000000000000000001",
             "author": "old_reader", "text": "これ懐かしい"}
    r_new = {"status_id": "3000000000000000002", "status_path": "/b/status/3000000000000000002",
             "author": "kesentm", "text": "わかる、私も昨日同じこと思った"}
    r_dupe = {"status_id": "3000000000000000003", "status_path": "/c/status/3000000000000000003",
              "author": "gyawa2525", "text": "また会えたね"}

    # ---- 1. the first read-in of all is a baseline
    LOG.clear()
    rp.store.set("x_replies_seen", None)
    rp.store.set("x_reply_candidates", [])
    rp.store.set("x_replies_sent", {})
    got = rp.take_in(new_post, [{"status_id": "2999999999999999999", "author": "backlog",
                                 "text": "a fortnight of these", "status_path": "/z/status/1"}])
    print("\n1. THE FIRST BOOT WITH THIS CODE")
    print(f"   candidates: {len(got)}")
    for m in LOG:
        print("   log:", m)

    # ---- 2. a reply under a post from before the cutoff
    LOG.clear()
    got = rp.take_in(old_post, [r_old])
    print("\n2. A REPLY UNDER A POST FROM BEFORE THE CUTOFF")
    print(f"   candidates: {len(got)}")
    for m in LOG:
        print("   log:", m)
    assert not got, "a pre-cutoff reply became a candidate"
    assert r_old["status_id"] not in (rp.store.get("x_replies_seen") or []), \
        "a pre-cutoff reply was even written to her seen list"

    # ---- 3. two under a post of hers, one of them already answered
    LOG.clear()
    sent = rp.store.get("x_replies_sent", {}) or {}
    sent[r_dupe["status_id"]] = {"at": rp.clock.now_ts(), "to": r_dupe["author"], "text": "うん"}
    rp.store.set("x_replies_sent", sent)
    got = rp.take_in(new_post, [r_new, r_dupe])
    print("\n3. TWO UNDER A POST OF HERS, ONE ALREADY ANSWERED")
    print(f"   candidates: {[c['author'] for c in got]}")
    for m in LOG:
        print("   log:", m)
    assert [c["id"] for c in got] == [r_new["status_id"]], "the already-answered reply was taken in again"
    print("   her prompt:", app.social.replies_line())

    # ---- 4. the gate, the judge, the voice
    scene = {"phone_access": "free", "where": "her room", "inner": ""}
    ok, why = rp.may_reply(scene, busy=False)
    print("\n4. THE GATE")
    print(f"   may_reply: {ok} -- {why}")
    print(f"   mid-conversation with him: {rp.may_reply(scene, busy=True)}")

    seen_calls = {}

    def fake_json(role, messages, max_tokens=None):
        seen_calls[role] = messages
        if role == "x_reply_judge":
            return {"answer": r_new["status_id"], "why": "she said the same thing back, it lands"}, ""
        if role == "x_reply":
            return {"text": "ほんとそれ。昨日ずっと考えてた", "why": "short, warm, closes it"}, ""
        raise AssertionError(f"unexpected role {role}")
    app.llm.call_json = fake_json

    LOG.clear()
    text = rp.run(scene, busy=False)
    print("\n5. THE TWO CALLS")
    print(f"   she wrote: {text}")
    for m in LOG:
        print("   log:", m)
    jsys = seen_calls["x_reply_judge"][0]["content"]
    vsys = seen_calls["x_reply"][0]["content"]
    vuser = seen_calls["x_reply"][1]["content"]
    sheet = app.config.prompt_text("persona")
    print(f"   judge system prompt: {len(jsys)} chars, character sheet in it: {sheet[:200] in jsys}")
    print(f"   judge user, first line: {seen_calls['x_reply_judge'][1]['content'].splitlines()[0]}")
    core = app.persona.system_for("friend")
    print(f"   voice system prompt: {len(vsys)} chars, starts with persona.system_for('friend'): "
          f"{vsys.startswith(core[:400])}")
    ci, ti = vuser.find("<carrying>"), vuser.find("@kesentm REPLIED TO IT")
    print(f"   voice user: thread at {ti}, carried block at {ci} -> carried is after the thread: {ci > ti > 0}")
    print("   voice user excerpt:")
    for line in vuser.splitlines()[:12]:
        print("     |", line[:100])
    assert sheet[:200] not in jsys, "the judge was handed her character sheet"
    assert vsys.startswith(core[:400]), "the reply did not build from persona.system_for"
    assert ci > ti > 0, "the carried block is not after the thread"

    # ---- 5. queued, and NOT yet recorded as said
    q = [r for r in (rp.store.get("x_action_queue") or []) if r.get("kind") == "reply"]
    print("\n6. QUEUED, AND NOTHING YET SAYS SHE SAID IT")
    print(f"   queue: {[(r['kind'], r['target'], r['text'][:20]) for r in q]}")
    print(f"   candidates now: {rp.pending()}")
    print(f"   in her sent record: {r_new['status_id'] in (rp.store.get('x_replies_sent') or {})}")
    assert q and r_new["status_id"] not in (rp.store.get("x_replies_sent") or {})

    # ---- 6. the stubbed send, then the record
    sends = []

    def fake_send(driver, config, status_path, text, log=print):
        sends.append((status_path, text))
        return True
    xm.reply_to_status = fake_send
    LOG.clear()
    done = cur.run_queue(None, log=cap)
    print("\n7. THE SEND (STUBBED) AND THE RECORD AFTER IT")
    print(f"   sent: {sends}")
    print(f"   actions done: {done}")
    rec = (rp.store.get("x_replies_sent") or {}).get(r_new["status_id"])
    print(f"   her record: {rec}")
    print(f"   replies in the last 24h: {rp.replies_recently()}")
    ev = [e for e in rp.store.events_for_date(rp.clock.date_str()) if "answered @" in e["text"]]
    print(f"   her event: {ev[-1]['text'] if ev else '(none)'}")
    print(f"   her prompt now: {app.social.replies_line() or '(nothing waiting)'}")
    print(f"   what she did lately: {cur.her_line()[-120:]}")
    assert rec and sends and ev, "the reply was not recorded after the send"

    # ---- 7. the same reply cannot be taken in twice
    LOG.clear()
    got = rp.take_in(new_post, [r_new])
    print("\n8. THE SAME REPLY AGAIN")
    print(f"   candidates: {len(got)} (it is in her sent record)")
    assert not got

    print("\n[test] all clear")


if __name__ == "__main__":
    main()
