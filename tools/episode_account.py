"""Read up one episode until the account of it is complete, and show it.

This is the on-demand surface for `sim/episode_account.py`: the account is
built by the watching worker when he plays something, and this is how an
episode is read up (or read up AGAIN) without waiting for him to play it, how
an account that came out thin is repaired, and how the whole record for an
episode is read back with its sources.

    python tools/episode_account.py --print --ja エグザンプル --ep 6
    python tools/episode_account.py --ja エグザンプル --ep 6 --id 24031 \
        --english "Example Show"
    python tools/episode_account.py --plays 10          # the last plays of his
    python tools/episode_account.py --refetch --ja ... --ep 6

It builds on a COPY of a save (`tools/harness.build_on`), never on a live one.
The machine's own store is NOT copied: an account is about a television
episode and not about anybody, so one written here is one the running
characters never have to pay for -- which is the whole point of that store.

`--print` fetches nothing and spends nothing.

spec: docs/recap.md section 3e
"""
import argparse
import io
import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ja", default="", help="the show's Japanese title")
    p.add_argument("--english", default="", help="the title his list writes")
    p.add_argument("--ep", type=int, default=0)
    p.add_argument("--id", type=int, default=0, help="the work's MyAnimeList id")
    p.add_argument("--plays", type=int, default=0,
                   help="instead of one episode: the last N plays of his player's history")
    p.add_argument("--print", dest="show_only", action="store_true",
                   help="what is on file already; fetches nothing, spends nothing")
    p.add_argument("--refetch", action="store_true",
                   help="drop the account and the page first, so both are read up again")
    p.add_argument("--config", default="config.json")
    p.add_argument("--db", default="data/world.db", help="the save to build a COPY of")
    p.add_argument("--json", action="store_true", help="the row as JSON rather than as prose")
    p.add_argument("--video", default="",
                   help="the file he played. A subtitle beside it is read first, and it is what "
                        "is transcribed when no archive carries the show. Taken from the "
                        "player's own state file when it names this episode and this is omitted.")
    p.add_argument("--watched", type=float, default=0.0,
                   help="unpaused seconds he has watched of it -- the transcription's own gate. "
                        "Read from the player's state file with the video when both are omitted.")
    p.add_argument("--log", action="store_true",
                   help="print the pipeline's own log lines -- which pages were tried and why "
                        "each was dropped, which is the only way to see why a set came out thin")
    return p.parse_args()


def _plays(app, n):
    """The last N distinct (work, episode) plays of his player, newest first,
    off the module that already reads that file."""
    w = getattr(app, "watching", None)
    if w is None:
        print("this character has no watching module; --plays needs one")
        return []
    out, seen = [], set()
    try:
        rows = w._from_player(0) or []
    except Exception as e:
        print(f"the player's history did not read: {type(e).__name__}")
        return []
    for r in reversed(rows):
        aid, ep = r.get("anime_id"), int(r.get("ep") or 0)
        key = (aid or r.get("title"), ep)
        if key in seen or not ep:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= n:
            break
    return out


def _entry(app, ja, english, aid):
    """What the pipeline is asked with. His own mirror answers the Japanese
    title and the edition where the work is on his list, so a caller who knows
    only the id still gets a complete entry."""
    row = {}
    kb = getattr(app, "anime_kb", None)
    if aid and kb is not None:
        try:
            row = kb.entry(aid) or {}
        except Exception:
            row = {}
        if not ja:
            try:
                ja = kb.japanese_title(aid) or ""
            except Exception:
                ja = ""
    return {"title": english or row.get("title", "") or ja, "ja": ja or english,
            "kind": "anime", "aid": aid or None, "mtype": row.get("type", ""),
            "eps": row.get("eps", 0)}


def show(row, as_json=False):
    if not row:
        print("  nothing on file")
        return
    if as_json:
        print(json.dumps(row, ensure_ascii=False, indent=1))
        return
    built = row.get("built_at") or 0
    print(f"  level: {row.get('level')}   {row.get('chars')} characters   "
          f"{len(row.get('scenes') or [])} scene(s)   "
          f"written {time.strftime('%Y-%m-%d %H:%M', time.localtime(built)) if built else '?'}")
    print(f"  anchored on: {row.get('anchor_kind') or '(nothing)'}")
    used = [s for s in (row.get("sources") or []) if s.get("used")]
    print(f"  sources: {len(used)} of {len(row.get('sources') or [])} used")
    for s in (row.get("sources") or []):
        print(f"    [{'x' if s.get('used') else ' '}] {s.get('kind')}, "
              f"{s.get('chars')}c  {s.get('url', '')[:90]}")
    print("\n--- account ---")
    print(row.get("account") or "")
    for head, key in (("scenes", "scenes"), ("parts", "parts"), ("gags", "gags"),
                      ("quotes", "quotes"), ("references", "references"),
                      ("not settled", "missing")):
        rows = row.get(key) or []
        if rows:
            print(f"\n--- {head} ---")
            for i, s in enumerate(rows, 1):
                print(f"{i:>2}. {s}")
    if row.get("endcard"):
        print(f"\n--- how it ends ---\n{row['endcard']}")


def main():
    a = parse_args()
    if not a.plays and not (a.ja or a.id):
        print("name a show (--ja / --id) or ask for --plays N")
        return 2
    # ONE SCRATCH SAVE PER RUN. A transcription holds its build open for
    # minutes, and a second run of this tool against the same path cannot even
    # delete the file to copy over it -- so the process id is in the name and
    # two readings-up can go at once.
    tmp = os.path.join(tempfile.gettempdir(), "scail_episode_account_%d.db" % os.getpid())
    from tools import harness
    app = harness.build_on(tmp, config=a.config, db=a.db)
    print(f"built on a copy of {a.db} at {tmp}")
    if a.log:
        # the harness stubs the logger so a tool leaves no run directory; put
        # it back on the console AFTER the build, so the build stays silent and
        # the reading-up says what it did
        import logger
        logger.log = lambda m, to_console=True: print("  |", m)
    rc = app.recap
    if rc is None:
        print("this character has no recap module")
        return 2
    wants = []
    if a.plays:
        for r in _plays(app, a.plays):
            wants.append((_entry(app, r.get("ja", ""), r.get("title", ""), r.get("anime_id")),
                          int(r.get("ep") or 0)))
    else:
        wants.append((_entry(app, a.ja, a.english, a.id), a.ep))
    for entry, ep in wants:
        ja = entry.get("ja") or entry.get("title")
        print(f"\n===== {ja} ep{ep} " + (f"(mal:{entry['aid']})" if entry.get("aid") else "") + " =====")
        if a.refetch:
            _drop(rc, app, entry, ep)
        if a.show_only:
            show(rc.account(entry, ep), a.json)
            continue
        t0 = time.time()
        video, watched = _video_for(a, ep)
        if video:
            print(f"  the file he played: {os.path.basename(video)}, "
                  f"{watched / 60:.0f} min watched")
        got = rc.synopsis(entry, ep, llm=app.llm, anime_id=entry.get("aid"),
                          english=entry.get("title", ""),
                          titles=[entry.get("title", ""), ja],
                          video=video, watched_seconds=watched)
        if not got:
            print("  nothing was found for it")
            continue
        print(f"  the page: {len(got.get('text') or '')} characters, {got.get('confidence')}, "
              f"{(got.get('source') or '')[:90]}")
        show(got.get("account") or rc.account(entry, ep), a.json)
        print(f"  ({time.time() - t0:.0f}s)")
    return 0


def _video_for(a, ep):
    """The file he played for this episode and how long he sat through it, or
    ("", 0). His own two flags win; otherwise the player's state file answers,
    and only when the file it names carries this episode's number -- reading
    up episode 7 must never hand the transcriber episode 6 because that is
    what happened to be open."""
    if a.video:
        return a.video, float(a.watched or 0)
    p = os.path.expandvars(os.path.join("%APPDATA%", "mpv", "mpv_now.json"))
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return "", 0.0
    path = str(d.get("path") or "")
    if not path or not os.path.exists(path):
        return "", 0.0
    import re
    stem = os.path.splitext(os.path.basename(path))[0]
    nums = [int(n) for n in re.findall(r"(?:\b|_|-\s*|E)(\d{1,3})(?=\D*$)", stem)]
    if int(ep) not in nums:
        return "", 0.0
    return path, float(d.get("watched") or 0)


def _drop(rc, app, entry, ep):
    """Forget what is on file for this episode, in BOTH stores, so the next
    call reads it up rather than answering from the cache. The machine's copy
    goes too -- leaving it there would have the rebuild adopt exactly the row
    it was asked to replace."""
    ja = entry.get("ja") or entry.get("title")
    aid = entry.get("aid")
    skey = rc._shared_key("anime", ja, ep, aid, rc._edition(aid, entry.get("mtype", "")))
    try:
        with app.store.lock:
            app.store.conn.execute("DELETE FROM recaps WHERE ja=? AND ep=?", (ja, int(ep)))
            app.store.conn.execute("DELETE FROM episode_accounts WHERE ja=? AND ep=?",
                                   (ja, int(ep)))
            app.store.conn.commit()
    except Exception as e:
        print(f"  her own rows were not dropped: {type(e).__name__}")
    r = getattr(rc, "retrievals", None)
    if r is not None:
        for pool in ("recap", "episode_account"):
            try:
                r.drop(pool, skey)
            except Exception as e:
                print(f"  the machine's {pool} row was not dropped: {type(e).__name__}")
    print(f"  dropped what was on file for {skey}")


if __name__ == "__main__":
    raise SystemExit(main())
