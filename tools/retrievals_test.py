"""One fetch about the world, claimed once and read by both characters.

    python tools/retrievals_test.py --store   # the store alone: no App, no save, no call
    python tools/retrievals_test.py           # and both characters, built on copies

`--store` is what `tools/smoke.py` runs: it builds a store in a temp file and
checks the thing the whole design rests on -- that a second asker gets the row
the first one paid for, that two askers at the same moment produce one fetch,
and that a fetch which found nothing leaves neither a row nor a claim.

The whole run also builds the two characters on COPIES of their saves, with
`sensors.retrievals_db` pointed at a temp file, and checks that a page one of
them stores is read by the other without a fetch, and that the one-off pass
that hands the machine what each save already holds did its work. Every model
call on those Apps is refused (`harness.refuse_model`), so nothing here spends.
"""
import argparse
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from machine.retrievals import Retrievals  # noqa: E402

fails = []


def check(ok, what, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what + (("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(what)
    return ok


class Counter:
    """A fetch that says how many times it actually ran."""

    def __init__(self, text="the page", delay=0.0, answer=True):
        self.n = 0
        self.text = text
        self.delay = delay
        self.answer = answer

    def __call__(self):
        self.n += 1
        if self.delay:
            time.sleep(self.delay)
        return {"text": self.text, "source": "a page on the web"} if self.answer else None


# ---------------------------------------------------------------- the store

def store_checks(tmp):
    path = os.path.join(tmp, "retrievals.db")
    her = Retrievals(path, by="tomoe", stale_seconds=3, wait_seconds=6, poll_seconds=0.2)
    other = Retrievals(path, by="yukari", stale_seconds=3, wait_seconds=6, poll_seconds=0.2)

    print("\nONE FETCH, READ BY BOTH")
    f = Counter("what happens in episode 9")
    a = her.get_or_fetch("recap", "anime|みつどもえ|ep9", f)
    b = other.get_or_fetch("recap", "anime|みつどもえ|ep9", f)
    check(f.n == 1, "the second character does not fetch what the first already has",
          f"the fetch ran {f.n} time(s)")
    check(bool(a) and bool(b) and a["text"] == b["text"] == "what happens in episode 9",
          "both are handed the same text")
    check(bool(b) and b.get("by") == "tomoe" and b.get("reused") is True,
          "the row names who paid for it", str((b or {}).get("by")))
    check(a.get("reused") is False, "the one who fetched it is not told it was reused")

    print("\nA DIFFERENT MODEL IS A DIFFERENT ROW")
    g = Counter("digested by another model")
    other.get_or_fetch("page_digest", "a page", g, model="kimi-k3")
    her.get_or_fetch("page_digest", "a page", g, model="deepseek-v4-flash")
    check(g.n == 2, "a digest by another model is fetched rather than read",
          f"the fetch ran {g.n} time(s)")

    print("\nTWO PROCESSES REACHING THE SAME THING AT THE SAME MOMENT")
    slow = Counter("the slow page", delay=1.5)
    out = {}

    def first():
        out["a"] = her.get_or_fetch("recap", "anime|けいおん|ep15", slow)

    t = threading.Thread(target=first)
    t.start()
    time.sleep(0.4)                      # long enough for the claim to be in
    t0 = time.time()
    second = other.get_or_fetch("recap", "anime|けいおん|ep15", slow)
    waited = time.time() - t0
    t.join()
    check(slow.n == 1, "the fetch ran once for the two of them", f"it ran {slow.n} time(s)")
    check(bool(second) and second.get("text") == "the slow page",
          "the one who waited got the row the other fetched")
    check(0.3 < waited < 6, "and waited for it rather than returning empty",
          f"{waited:.1f}s")

    print("\nTHREE PROCESSES REACHING ONE EPISODE AT THE SAME MOMENT")
    # This is the shape `sim/recap.py` uses: the claim is held across a whole
    # reading-up -- a web search, four page fetches, a digest each and one
    # judge -- because what has to happen once for the machine is the SEARCH.
    # Three characters resolved Example Show episode 5 inside twenty-three
    # seconds on 2026-09-07 and each ran her own.
    searches = Counter("what happens in episode 5", delay=1.2)
    third = Retrievals(path, by="asumikana", stale_seconds=3, wait_seconds=6, poll_seconds=0.2)
    outcome = {}

    def reading_up(store, who, key, answer=None):
        mine, held = store.claim("recap", key)
        if not mine:
            row = store.wait_for("recap", key, held=held)
            if row:
                outcome[who] = ("waited and read it", row.get("text"))
                return
            mine, held = store.claim("recap", key)
        got = (answer or searches)()
        if not got:
            store.fail("recap", key, "no page had a section for it")
            outcome[who] = ("searched, found nothing", "")
            return
        store.finish("recap", key, got["text"], source=got["source"])
        outcome[who] = ("searched and found it", got["text"])

    key5 = "anime|mal:24031|tv|ep5"
    threads = [threading.Thread(target=reading_up, args=(s, w, key5))
               for s, w in ((her, "tomoe"), (other, "yukari"), (third, "asumikana"))]
    for t in threads:
        t.start()
        time.sleep(0.25)
    for t in threads:
        t.join()
    for who, (what, _text) in sorted(outcome.items()):
        print(f"    {who}: {what}")
    check(searches.n == 1, "one search for the three of them", f"it ran {searches.n} time(s)")
    check(all(v[1] == "what happens in episode 5" for v in outcome.values()),
          "and all three hold the page",
          "; ".join(f"{k}={len(v[1] or '')} chars" for k, v in sorted(outcome.items())))
    check(sum(1 for v in outcome.values() if v[0].startswith("waited")) == 2,
          "two of them waited rather than searching")

    print("\nA CLAIMANT WHOSE SEARCH FOUND NOTHING")
    outcome.clear()
    empty = Counter(answer=False, delay=0.8)
    found = Counter("found on the second try")
    t = threading.Thread(target=reading_up, args=(her, "tomoe", "anime|mal:24031|tv|ep6", empty))
    t.start()
    time.sleep(0.3)
    t0 = time.time()
    reading_up(other, "yukari", "anime|mal:24031|tv|ep6", found)
    waited = time.time() - t0
    t.join()
    check(outcome.get("tomoe", ("", ""))[0] == "searched, found nothing",
          "the first one comes back empty")
    check(outcome.get("yukari", ("", ""))[1] == "found on the second try",
          "the second one searches rather than being handed nothing",
          str(outcome.get("yukari")))
    check(waited < 5, "and is let go the moment the first gives up, not at the timeout",
          f"{waited:.1f}s of a 6s timeout")

    print("\nA FETCH THAT FOUND NOTHING")
    empty = Counter(answer=False)
    got = her.get_or_fetch("web_search", "anime|nothing at all", empty)
    check(got is None, "nothing is returned")
    check(her.get("web_search", "anime|nothing at all") is None, "and nothing is stored")
    again = Counter("found it the second time")
    row = other.get_or_fetch("web_search", "anime|nothing at all", again)
    check(bool(row) and again.n == 1,
          "the claim was dropped, so the other character may try")

    print("\nA CLAIM LEFT BEHIND BY A PROCESS THAT WAS KILLED")
    her._claim("recap", "anime|abandoned|ep1")     # claimed and never finished
    with her.lock:                                 # and the process is long gone
        her.con.execute("UPDATE inflight SET started=? WHERE key=?",
                        (time.time() - 60, "anime|abandoned|ep1"))
        her.con.commit()
    stuck = Counter("fetched after the claim went stale")
    t0 = time.time()
    row = other.get_or_fetch("recap", "anime|abandoned|ep1", stuck)
    check(bool(row) and stuck.n == 1, "a stale claim is taken over rather than waited on")
    check(time.time() - t0 < 5, "and it is not waited out in full", f"{time.time() - t0:.1f}s")

    print("\nWHAT GOES OUT OF DATE, AND WHAT IS DROPPED")
    her.put("web_search", "a stale search", "last month's results", fetched_at=time.time() - 100)
    check(her.get("web_search", "a stale search", ttl=10) is None,
          "a row older than the window reads as absent")
    check(her.get("web_search", "a stale search") is not None,
          "and is still there for a caller that set no window")
    her.put("recap", "anime|wrong page|ep9", "a bookstore listing")
    her.drop("recap", "anime|wrong page|ep9")
    check(her.get("recap", "anime|wrong page|ep9") is None,
          "a page that turned out to be the wrong one is dropped for both")

    print("\nTWO SAVES HOLDING A ROW FOR ONE THING")
    her.put_if_newer("recap", "anime|both|ep1", "the older page", fetched_at=100.0)
    her.put_if_newer("recap", "anime|both|ep1", "the newer page", fetched_at=200.0)
    her.put_if_newer("recap", "anime|both|ep1", "an older page again", fetched_at=150.0)
    row = her.get("recap", "anime|both|ep1")
    check(bool(row) and row["text"] == "the newer page", "the later fetch wins",
          (row or {}).get("text"))

    print("\n" + her.report())


# ------------------------------------------------------- the two characters

def temp_config(src, tmp, retrievals_db):
    """A copy of a character's config with the machine's store pointed at a
    temp file, so a test never writes into the live one."""
    with io.open(os.path.join(ROOT, src), encoding="utf-8") as f:
        raw = json.load(f)
    raw.setdefault("sensors", {})["retrievals_db"] = retrievals_db
    out = os.path.join(tmp, src)
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    return out


def app_checks(tmp):
    from tools import harness
    shared = os.path.join(tmp, "shared_retrievals.db")
    apps = []
    for name, cfg, db in (("the first character", "config.json", "data/world.db"),
                          ("the second character", "config_yukarin.json", "data/yukarin.db")):
        if not os.path.exists(os.path.join(ROOT, db)):
            print(f"  .. {name}: no save at {db}; skipped")
            continue
        print(f"\nBUILDING {name.upper()} ON A COPY")
        app = harness.build_on(os.path.join(tmp, os.path.basename(db)),
                               temp_config(cfg, tmp, shared), db)
        harness.refuse_model(app)
        apps.append((name, app))
        check(app.retrievals is not None and app.retrievals.path == shared,
              f"{name} opens the machine's store", app.retrievals.path)
        check(app.recap.retrievals is not None, f"{name}: the recap fetcher is wired to it")
        check(app.lookup.retrievals is not None, f"{name}: the lookup is wired to it")
        flag = app.store.get("recaps_shared_once") or {}
        check(bool(flag), f"{name}: the one-off pass ran", json.dumps(flag, ensure_ascii=False))

    if not apps:
        print("  .. no saves to build on")
        return

    print("\nWHAT THE MIGRATION CARRIED ACROSS")
    r = apps[0][1].retrievals
    counts = r.counts()
    print("  " + (", ".join(f"{k}: {n}" for k, n in counts.items()) or "(empty)"))
    print("  by character: " + (", ".join(f"{k} {n}" for k, n in r.by_character().items()) or "-"))
    check(r.total() > 0, "the machine's store holds what the saves held", str(r.total()))
    if len(apps) == 2:
        both = 0
        for name, app in apps:
            with app.store.lock:
                both += int(app.store.conn.execute("SELECT COUNT(*) FROM recaps").fetchone()[0])
        print(f"  the two saves hold {both} row(s) between them; the machine holds {r.total()}")

    if len(apps) < 2:
        return
    print("\nA PAGE ONE OF THEM STORES, READ BY THE OTHER WITHOUT A FETCH")
    first, second = apps[0][1], apps[1][1]
    entry = {"title": "A Test Programme", "ja": "テスト番組", "kind": "anime", "ep": 4}
    first.recap._store(entry, 4, "第4話のあらすじ、テスト用。", "a page on the web",
                       judged=1, confidence="anchored", scenes=["場面1", "場面2"])
    got = second.recap.cached("テスト番組", 4)
    check(bool(got) and got[0] == "第4話のあらすじ、テスト用。",
          "the second character reads the page the first fetched", str(got and got[0])[:40])
    check(second.recap.confidence("テスト番組", 4) == "anchored",
          "and how far it was trusted came with it",
          second.recap.confidence("テスト番組", 4))
    row = second.recap.row("テスト番組", 4)
    check(bool(row) and (row.get("scenes") or []) == ["場面1", "場面2"],
          "and the scenes the judge kept", str((row or {}).get("scenes")))
    mine = second.recap._local_row("テスト番組", 4)
    check(mine is not None,
          "reading it wrote her own record of having been told it")
    check(second.recap._shared_row("テスト番組", 4) is not None,
          "and the machine's copy is still the machine's")

    print("\nA PAGE THAT TURNED OUT TO BE THE WRONG ONE")
    first.recap._unshare("テスト番組", 4, text="第4話のあらすじ、テスト用。")
    check(first.recap._shared_row("テスト番組", 4) is None,
          "is dropped from the machine's store, not only from her save")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--store", action="store_true",
                    help="the store alone: no App, no save, no model call")
    args = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="retrievals_test_")
    try:
        store_checks(tmp)
        if not args.store:
            app_checks(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if fails:
        print(f"FAIL: {len(fails)} check(s): " + "; ".join(fails[:6]))
        return 1
    print("all checks passed: one fetch about the world, read by both")
    return 0


if __name__ == "__main__":
    sys.exit(main())
