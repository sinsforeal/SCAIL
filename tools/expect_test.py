"""Expectations of him without the model: a promise heard (stubbed call),
kept off a message, missed past due, raised by her, foresight's risk
scored off his mood, and a habit checked against the digests. On a copy
of the save.

    python tools/expect_test.py
"""
import os
import sys
import tempfile
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import harness  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.setup = lambda out_dir: None
logger.log = lambda m, to_console=True: print("   log:", m[:120])



def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_expect.db")
    app = harness.build_on(tmp)
    ex, st, store = app.expectations, app.state, app.store
    fails = []

    def check(label, ok):
        print(("  ok   " if ok else "  FAIL ") + label)
        if not ok:
            fails.append(label)

    cols = {r["name"] for r in store.conn.execute("PRAGMA table_info(messages)").fetchall()}

    def say(role, text, ts):
        fields = ["ts", "role", "text"] + (["date"] if "date" in cols else [])
        vals = [ts, role, text] + ([app.clock.date_str(ts)] if "date" in cols else [])
        with store.lock:
            store.conn.execute(f"INSERT INTO messages({','.join(fields)}) VALUES({','.join('?' * len(fields))})", vals)
            store.conn.commit()

    def digest(text, from_ts, to_ts):
        with store.lock:
            store.conn.execute("INSERT INTO digests(ts,date,text,from_ts,to_ts) VALUES(?,?,?,?,?)",
                               (to_ts, app.clock.date_str(to_ts), text, from_ts, to_ts))
            store.conn.commit()

    now = app.clock.now_ts()
    store.set("expectations", [])
    store.set("habits_him", [])
    store.set("habits_checked", {})
    # --- hear, with the model stubbed
    real = app.llm.call_json
    app.llm.call_json = lambda role, messages, max_tokens=None: ({"found": True, "expectations": [
        {"what": "watch episode 3 of Frieren", "quote": "i'll watch ep 3 tonight", "due_in_minutes": 120, "by": "any",
         "words": ["frieren", "ep 3", "episode 3"], "belief": "chose_me", "confidence": 0.8},
        {"what": "send the photo of the cat", "quote": "will send the cat pic", "due_in_minutes": 30, "by": "message",
         "words": ["cat", "photo", "pic"], "belief": "chose_me", "confidence": 0.7}]}, "") if role == "expect_him" else real(role, messages, max_tokens)
    added = ex.hear("ok i'll watch ep 3 tonight, will send the cat pic in a bit")
    check(f"two expectations heard: {[r['what'] for r in added]}", len(added) == 2 and all(r["state"] == "open" for r in added))
    check("a trigger-less message asks nothing", ex.hear("lol") == [])
    check("her prompt carries what she is expecting", "you are expecting it" in ex.situation_line())
    # --- kept: his message carries the words before due
    say("user", "watched frieren ep 3, that was rough", now + 60)
    b0 = app.model_of_him.get("chose_me")
    ex.tick()
    rows = ex.rows()
    fr = [r for r in rows if "Frieren" in r["what"]][0]
    check(f"kept off his message: {fr['state']} -- {fr.get('note', '')[:50]}", fr["state"] == "kept")
    # --- missed: the cat photo past due + grace
    cat = [r for r in rows if "cat" in r["what"]][0]
    cat["due_ts"] = now - 3600
    ex._save(rows)
    him = st._him_key() or "him"
    t0 = float(st.relationships.get(him, {}).get("tension", 0))
    r0 = app.sentiments.live(him, "resentment")
    ex.tick()
    cat = [r for r in ex.rows() if "cat" in r["what"]][0]
    t1 = float(st.relationships.get(him, {}).get("tension", 0))
    check(f"missed past the deadline: tension {t0:.0f} -> {t1:.0f}, resentment {r0:.1f} -> {app.sentiments.live(him, 'resentment'):.1f}", cat["state"] == "missed" and t1 > t0)
    evs = [e for e in store.events_for_date(app.clock.date_str()) if e["kind"] == "expect"]
    check("...and it is an event on the record", any("cat" in e["text"] for e in evs))
    check("...and raisable in her prompt", "did not; you have not brought it up" in ex.situation_line())
    if "did not; you have not brought it up" not in ex.situation_line():
        print("   her prompt line was:", ex.situation_line()[:600])
        print("   unmet rows:", [(r["what"][:30], r["state"], r.get("raised"), round((app.clock.now_ts() - r.get("settled_ts", 0)) / 3600, 1)) for r in ex._unmet_rows()])
    say("assistant", "so where's my cat photo", now + 120)
    ex.tick()
    cat = [r for r in ex.rows() if "cat" in r["what"]][0]
    check("she raised it herself -> no longer nagging her prompt", cat.get("raised") and "brought it up" not in ex.situation_line())
    # --- the risk foresight named, scored by foresight itself off his mood
    store.set("foresight", [{"ts": now - 100, "kind": "reply", "pred": {"reply_p": 0.5, "reply_minutes": 30, "risk": "the token line may land as a dig", "silence_means": "", "tone": "", "plan": ""}, "outcome": None}])
    g0 = st.gauges.get("guilt", 0)
    store.set("his_mood", {"ts": now + 50, "valence": -1.5, "arousal": 0})
    app.foresight.score_risks()
    rk = [r for r in app.foresight.rows() if "token line" in (r.get("pred") or {}).get("risk", "")]
    check(f"risk scored off his next mood: {rk[0].get('risk_state') if rk else None}, guilt {g0:.0f} -> {st.gauges.get('guilt', 0):.0f}", rk and rk[0].get("risk_state") == "happened" and st.gauges.get("guilt", 0) > g0)
    check("no expectation row is made of it any more", not [r for r in ex.rows() if r["kind"] == "risk" and "token line" in r["what"]])
    # --- habits checked against the digests
    his = ex._his_local(now)
    a = (his.hour - 4) % 24
    b = (his.hour - 2) % 24
    store.set("habits_him", [{"what": "on the news", "hours": [a, b], "days": "any", "words": ["newsfeed", "reader"], "confidence": 0.8, "since": app.clock.date_str()},
                             {"what": "on twitter", "hours": [a, b], "days": "any", "words": ["x.com", "twitter"], "confidence": 0.6, "since": app.clock.date_str()}])
    start = his.replace(hour=a, minute=0, second=0, microsecond=0).timestamp()
    end = his.replace(hour=b, minute=0, second=0, microsecond=0).timestamp()
    digest("He was on a newsfeed reader for 40 min, then a terminal.", start + 60, end - 60)
    c0 = st.gauges.get("curiosity", 0)
    ex.tick()
    chk = store.get("habits_checked", {})
    check(f"habit kept and habit missed from the same digest: {chk}", any(v == "kept" for v in chk.values()) and any(v == "missed" for v in chk.values()))
    check(f"a missed habit is an event and warms curiosity {c0:.0f} -> {st.gauges.get('curiosity', 0):.0f}",
          any("on twitter" in e["text"] for e in store.events_for_date(app.clock.date_str()) if e["kind"] == "expect") and st.gauges.get("curiosity", 0) > c0)
    check("...and her prompt says so", "unlike him" in ex.situation_line())
    ex.tick()
    check("a habit is checked once a day", store.get("habits_checked", {}) == chk)
    print(ex.report())
    print(f"\n{len(fails)} failure(s)" if fails else "\nall ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
