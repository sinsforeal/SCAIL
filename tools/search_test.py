"""The two ways a search happens, on a copy of the live save.

    python tools/search_test.py                       # the first character
    python tools/search_test.py config_yukarin.json data/yukarin.db

Three cases, in order: a draft that asks for a search is honoured and the
marker never reaches him; a draft that asks while her day gives her no way
to look is refused by code, with the refusal in the log; a thing the
automatic lookup off his message already fetched is answered out of what she
knows, with no web request and no model call. The first case spends one
cheap call (`search_gist`) and one web request; the other two spend nothing,
and the harness proves it by making every model call raise.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from tools import harness  # noqa: E402


def line(s=""):
    print(s, flush=True)


def main():
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    db = sys.argv[2] if len(sys.argv) > 2 else "data/world.db"
    tmp = os.path.join(tempfile.gettempdir(), "search_test.db")
    app = harness.build_on(tmp, cfg, db)
    lk, per = app.lookup, app.persona
    line(f"config {cfg} / save {db} (copy at {tmp})")
    line(f"lookup.on_request={app.config.lookup.on_request}  search_per_day={app.config.lookup.search_per_day}"
         f"  search_known_hours={getattr(app.config.lookup, 'search_known_hours', 6.0)}")
    scene = app.store.last_scene() or {}
    line(f"the newest scene in the save: {scene.get('hm')} {scene.get('activity')} (phone {scene.get('phone_access')})"
         f" -> she is cut off: {lk._cut_off()}")
    spent = app.store.today_count("search_counts", app.clock.date_str())
    line(f"searches spent today on this save: {spent}")

    # ---- 1. she asks, and it runs -------------------------------------
    line()
    line("1. a draft that asks for a search")
    draft = ["ohh wait", "[search: is there a second season of k-on]", "hold on"]
    bubbles = per._take_search(list(draft))
    asked = getattr(per, "_search_asked", "")
    per._search_asked = ""
    line(f"   the draft: {draft}")
    line(f"   what leaves for him: {bubbles}")
    line(f"   what she asked for: {asked!r}")
    assert asked and not any("search" in b for b in bubbles), "the marker reached him"
    rec = lk.search(asked, why="she wanted to know it before answering him", by="her", access="free")
    if rec:
        line(f"   asked_by={rec['asked_by']}  from_known={rec.get('from_known', False)}  source={rec['source']}")
        line(f"   gist: {rec['gist'][:220]}")
        assert rec["asked_by"] == "her", rec["asked_by"]
    else:
        line("   nothing came back (no network, or the results did not answer it) -- the reply stands as drafted")
    after = app.store.today_count("search_counts", app.clock.date_str())
    line(f"   searches spent now: {after} (was {spent})")

    # ---- 2. her day gives her no way to look --------------------------
    line()
    line("2. the same ask while she has no way to look")
    harness.refuse_model(app)
    before = app.store.today_count("search_counts", app.clock.date_str())
    rec = lk.search("is there a second season of k-on", why="she wanted to know", by="her", access="none")
    line(f"   returned: {rec!r}")
    line(f"   searches spent: {app.store.today_count('search_counts', app.clock.date_str())} (was {before})")
    assert rec is None, "a search ran with no way to look"
    assert app.store.today_count("search_counts", app.clock.date_str()) == before

    # ---- 3. the automatic lookup already fetched it -------------------
    line()
    line("3. the same ask for a thing that arrived off his message an hour ago")
    key = "anime:search_test"
    lk.known.add(key, ["Bocchi the Rock", "ぼっち・ざ・ろっく"], "anime",
                 "A 12-episode 2022 CloverWorks anime about a girl who cannot talk to anyone joining a band; "
                 "he scored it 9 and it is the one he brings up when he talks about guitars.",
                 source="his history (series card)")
    lk._mark_known(key, {"asked_by": "arrived", "ts": app.clock.now_ts() - 3600})
    before = app.store.today_count("search_counts", app.clock.date_str())
    rec = lk.search("what year did Bocchi the Rock come out", why="she wanted to know", by="her", access="free")
    line(f"   returned: from_known={rec and rec.get('from_known')}  asked_by={rec and rec.get('asked_by')}"
         f"  known_key={rec and rec.get('known_key')}")
    line(f"   gist: {(rec or {}).get('gist', '')[:200]}")
    line(f"   searches spent: {app.store.today_count('search_counts', app.clock.date_str())} (was {before})")
    assert rec and rec.get("from_known"), "it went and fetched a thing she already had"
    assert rec["asked_by"] == "arrived", "answering out of what arrived must not read as her having searched"
    assert app.store.today_count("search_counts", app.clock.date_str()) == before
    lk.known.drop(key)

    line()
    line("all three cases as designed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
