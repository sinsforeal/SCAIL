"""Offline checks for grounded watching, and a scored run over a truth set.

    python tools/recap_test.py              # the offline checks, no network
    python tools/recap_test.py --scored     # score what the live saves hold now
    python tools/recap_test.py --scored --run [--only "Mitsudomoe:12"]
                                            # run the pipeline on a COPY and score it
    python tools/recap_test.py --scored --archive
                                            # score the last run again off disk, no calls

The offline part parses, slices and extracts against fixtures kept beside it
in `tools/fixtures/recap/` -- the real page text that motivated each check,
stored rather than fetched, so a check cannot pass because a site changed.

The scored part measures accuracy rather than parsing, against
`tools/fixtures/recap/truth.json`: the nine episode rows the two live saves
hold, hand-checked against sources the pipeline did not read. Per episode it
counts the scenes named (recall), whether they are named in the order they
happen, scenes invented, and outcomes stated that contradict the truth. The
headline number is **episodes with no error and at least two-thirds of the
scenes**.

`--run` spends model calls and fetches pages; it never opens a live save
except read-only, and builds on a copy (`tools/harness.build_on`).
`--archive` scores a run that has already happened by reading the winning
digest back out of `data/recaps`, which costs nothing and is half the reason
the archive exists.
"""
import argparse
import io
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
import logger
logger.log = lambda *a, **k: None
from config import Config
from store import Store
from sim.watchlist import Watchlist
from sim.recap import Recap
from sim import subtitles as subs
from sim.episode_archive import EpisodeArchive

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tools", "fixtures", "recap")

ok = 0
fail = 0


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f"  FAIL: {name}")


def fixture(name):
    with io.open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


class FakeClock:
    def __init__(self):
        self._t = 1_787_000_000.0

    def now_ts(self):
        self._t += 60
        return self._t

    def date_str(self):
        return "2026-08-27"


# ---------------------------------------------------------------- offline

def offline():
    cfg = Config("config.json")
    tmp = os.path.join(tempfile.gettempdir(), "recap_test.db")
    for suf in ("", "-wal", "-shm"):
        p = tmp + suf
        if os.path.exists(p):
            os.remove(p)
    store = Store(tmp)
    clock = FakeClock()

    # --- watchlist cursor ---
    wl = Watchlist(cfg, store, clock)
    seeded = wl.all()
    check("seed loaded from config", len(seeded) >= 1)
    cur = wl.current()
    check("current() returns an unfinished show", cur is not None)
    title = cur["title"]
    ep0 = cur["ep"]
    wl.advance(title)
    after = next(r for r in wl.all() if r["title"] == title)
    check("advance() moves the cursor +1", after["ep"] == ep0 + 1)
    check("advance() stamps last_ts", after["last_ts"] > 0)
    cur2 = wl.current()
    check("current() rotates away from the just-watched one",
          len(wl.all()) == 1 or cur2["title"] != title)
    wl.add("Test Drama", ja="テストドラマ", kind="drama", ep=1, total=10)
    check("add() appends", any(r["title"] == "Test Drama" for r in wl.all()))
    wl.set_ep("Test Drama", 5)
    check("set_ep() sets", next(r for r in wl.all() if r["title"] == "Test Drama")["ep"] == 5)
    wl.remove("Test Drama")
    check("remove() drops", not any(r["title"] == "Test Drama" for r in wl.all()))
    wl.add("Done Show", ja="おわり", kind="anime", ep=12, total=12)
    wl.advance("Done Show")
    df = next(r for r in wl.all() if r["title"] == "Done Show")
    check("advance() does not pass the total", df["ep"] == 12)

    # --- recap parsing (no network) ---
    rc = Recap(cfg, store, clock)
    links = rc._result_links(
        '<li class="b_algo"><h2><a href="https://ameblo.jp/x/entry-1.html">t</a></h2></li>'
        '<a href="https://www.bing.com/ck">skip</a>'
        '<a class="result__a" href="https://blog.goo.ne.jp/y/e/2">g</a>'
        '<a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fhatena.jp%2Fz">d</a>')
    check("result links parse bing h2", "https://ameblo.jp/x/entry-1.html" in links)
    check("result links parse ddg result__a", "https://blog.goo.ne.jp/y/e/2" in links)
    check("result links decode uddg", any("hatena.jp/z" in u for u in links))
    check("result links drop the engine's own domain", not any("bing.com" in u for u in links))

    body = ("<html><body><nav>menu</nav><div class='entry-content'>"
            "第1話 これは第一話の本文です。ゆあが東京に出る。"
            "第2話 これは第二話。別の人物。</div><footer>foot</footer></body></html>")
    ex = rc._extract(body, "https://cinema.ne.jp/article/detail/1")
    check("extract picks the article container, not nav/footer",
          "menu" not in ex and "foot" not in ex and "第一話の本文" in ex)
    s1 = rc._episode_slice(ex, 1)
    check("episode_slice keeps episode 1", "第一話の本文" in s1 and "第二話" not in s1)
    s2 = rc._episode_slice(ex, 2)
    check("episode_slice keeps episode 2", "第二話" in s2)
    check("episode_slice returns '' when the episode is absent", rc._episode_slice(ex, 9) == "")

    # cache round-trip
    entry = {"title": "X", "ja": "エックス", "kind": "anime", "ep": 3}
    rc._store(entry, 3, "本文テキスト", "http://src")
    hit = rc.cached("エックス", 3)
    check("cache stores and reads back", hit and hit[0] == "本文テキスト")
    check("cache miss returns None", rc.cached("エックス", 99) is None)

    # --- the acceptance tests, each against the real page that motivated it ---

    # 1. THE NAV STRIP. The official page for one episode of a 2010 show opens
    #    with a strip listing all thirteen episode titles. Slicing at the FIRST
    #    occurrence ran from one nav entry to the next and gave thirteen
    #    characters -- under min_chars, so the page was dropped and the 249
    #    characters of official あらすじ two paragraphs below were never seen.
    official = fixture("official-site_mitsudomoe_ep12.txt")
    check("the official page still extracts to the 1,063 characters the report measured",
          abs(len(official) - 1063) <= 40)
    s = rc._episode_slice(official, 12)
    check("the nav strip is not the slice (it used to give 13 characters)", len(s) > 200)
    check("the slice is the official あらすじ, not the list of titles",
          "蛍光灯" in s and "第13話" not in s)
    check("a page that is mostly an episode index is reported as one",
          Recap._season_page(official, 12))
    check("an ordinary post is not an index", not Recap._season_page(
        "第5話。ゆあは学校で走った。とても疲れた。それから帰った。", 5))

    # 2. THE RUNNING ORDER. It names the right episode and describes none of
    #    it, so the section test passes and the digest role restated the table
    #    as events -- which is how one episode's record says a character was
    #    in a sketch she is not in.
    nori = fixture("noripedia_mitsudomoe_ep11.txt")
    check("a programme running order is refused", rc._episode_slice(nori, 11) == "")
    check("_running_order sees the table itself", Recap._running_order(nori))

    # 3. A LIST OF OTHER ARTICLES. The marker was the page's title and what
    #    follows it is the sidebar; one such archive reached the digest role,
    #    which wrote a plot out of nothing.
    arch = fixture("blog-archive_mitsudomoe_ep9.txt")
    check("a slice that opens in a list of other articles is refused",
          rc._episode_slice(arch, 9) == "")

    # 4. A BLURB UNDER THE ANCHOR LENGTH is a candidate, not a discard: never
    #    wrong, never complete, and the right thing to check a summary against.
    anchor_max = int(getattr(cfg.recap, "anchor_max_chars", 300) or 300)
    check("the official slice is short enough to be the anchor and long enough to keep",
          200 <= len(rc._episode_slice(official, 12)) <= anchor_max + 200)

    # 5. THE WRONG EPISODE, where the number matches and the title does not.
    titles = {9: {"ja": "変人はサンタクロース", "en": "A Weirdo is Santa Claus", "romaji": ""},
              10: {"ja": "ちぢょになる", "en": "Becoming a Pervert", "romaji": ""}}
    wrong = fixture("wrong-episode_mitsudomoe_ep9.txt")
    check("a page numbered 9 that carries episode 10's subtitle is refused",
          Recap.wrong_episode(wrong, 9, titles))
    check("a page carrying this episode's own subtitle is kept",
          not Recap.wrong_episode("第9話「変人はサンタクロース」。ひとはが本を読んでいる。", 9, titles))
    check("with no titles cached nothing is refused",
          not Recap.wrong_episode(wrong, 9, {}))

    # --- episode markers ---
    marks = Recap._ep_markers("第1話 と 第12話 と ep 3 と #4")
    check("markers read 第N話, ep N and #N", {n for _s, _e, n in marks} == {1, 12, 3, 4})
    check("a bare 2話 inside 第12話 is not its own marker",
          2 not in {n for _s, _e, n in Recap._ep_markers("第12話について")})

    # --- subtitle files: the name is tested before the file is downloaded ---
    check("a bitmap subtitle is refused", not subs.acceptable("Show S01E01.ja.sup")[0])
    check("an archive is refused", not subs.acceptable("Show 01.zip")[0])
    check("a Chinese rip is refused", not subs.acceptable("[Moozzi2] Show - 01 [CHS, JPN].ass")[0])
    check("a track translated from English is refused",
          not subs.acceptable("Show 01 (translated from english).srt")[0])
    check("a dual-language script is refused", not subs.acceptable("[CoalGuys] Show - 08.en+jp.ass")[0])
    check("a caption rip is accepted", subs.acceptable("けいおん!.S02E15.マラソン大会!.WEBRip.Netflix.ja[cc].srt")[0])
    check("a broadcast rip outranks a fan transcript",
          subs.rank("[shincaps] K-ON!! - 15 (CS-TBS2).srt") < subs.rank("[fansub] K-ON!! - 15.ass"))
    check("provenance reads the filename",
          subs.provenance("けいおん!.S02E15.WEBRip.Netflix.ja[cc].srt") == "streaming"
          and subs.provenance("[shincaps] K-ON!! - 15 (CS-TBS2 1440x1080 MPEG2 AAC).srt") == "broadcast")
    for name, n in (("けいおん!.S02E15.マラソン大会!.WEBRip.Netflix.ja[cc].srt", 15),
                    ("[I.G&CASO][K-ON!!][15][BDRIP][1920x1080].JP.ass", 15),
                    ("[Blu-Ray] Mitsudomoe 01.ass", 1),
                    ("[shincaps] K-ON!! - 15 (CS-TBS2).ass", 15),
                    ("Show 第7話.srt", 7)):
        check(f"the episode number reads out of {name[:30]}", subs._ep_of(name) == n)

    srt = ("1\n00:00:03,586 --> 00:00:09,300\n（校長(こうちょう)）長かった夏休みも終わり\n"
           "今日から また新学期が始まります\n\n"
           "2\n00:00:09,384 --> 00:00:13,179\n皆さんは 充実した夏休みを\n過ごせたでしょうか？\n")
    lines = subs.parse(srt, "x.srt")
    check("srt parses to cues in order", len(lines) == 2 and lines[0]["start"] == 3.59)
    check("a caption rip's speaker label is lifted out, reading and all",
          lines[0]["speaker"] == "校長" and lines[0]["text"].startswith("長かった"))
    check("every line is Japanese", subs.japanese_share(lines) == 1.0)
    ass = ("[Events]\nFormat: Layer, Start, End, Style, Name, ML, MR, MV, Effect, Text\n"
           "Dialogue: 0,0:00:01.50,0:00:03.00,Default,,0,0,0,,{\\pos(1,2)}こんにちは\n"
           "Dialogue: 0,0:00:04.00,0:00:05.00,Default,,0,0,0,,hello there\n")
    al = subs.parse(ass, "x.ass")
    check("ass dialogue rows parse and override tags go", len(al) == 2 and al[0]["text"] == "こんにちは")
    check("a half-English file reads as half Japanese", abs(subs.japanese_share(al) - 0.5) < 0.01)

    # --- the archive on disk ---
    adir = os.path.join(tempfile.gettempdir(), "recap_test_archive")
    import shutil
    shutil.rmtree(adir, ignore_errors=True)
    ar = EpisodeArchive(adir)
    f1 = ar.save("7627", 12, "page", "本文", url="https://example.jp/a", show="Mitsudomoe", ja="みつどもえ")
    f2 = ar.save("7627", 12, "page", "べつの本文", url="https://example.jp/a")
    check("a re-fetch adds a version rather than overwriting", f1 != f2 and f1 and f2)
    ar.note_choice("7627", 12, url="https://example.jp/a", confidence="anchored", reason="why")
    man = ar.manifest("7627", 12)
    check("the index says what each file is and where it came from",
          len(man.get("files") or []) == 2
          and all(r.get("url") and r.get("at") and r.get("kind") for r in man["files"]))
    check("the index says which one was chosen",
          (man.get("chosen") or {}).get("confidence") == "anchored")
    check("the files are really on disk",
          all(os.path.exists(os.path.join(adir, "7627", "ep012", r["file"])) for r in man["files"]))
    check("a Japanese-only show name still makes a directory",
          EpisodeArchive(adir).show_key(None, "みつどもえ", "").startswith("jp-"))

    print(f"[recap-test] {ok} ok, {fail} fail")
    return 1 if fail else 0


# ---------------------------------------------------------------- scoring

def load_truth():
    with io.open(os.path.join(FIX, "truth.json"), encoding="utf-8") as fh:
        return json.load(fh)


def score_one(text, ep):
    """One digest against one episode's hand-checked truth.

    `found` is scenes named, `order` whether the named ones appear in the
    order they happen, `errors` outcomes stated that contradict the truth,
    `invented` details in no source. Clean means no error, no invention, and
    at least two-thirds of the scenes."""
    text = str(text or "")
    scenes = ep.get("scenes") or []
    at = []
    for sc in scenes:
        pos = [text.find(k) for k in (sc.get("keys") or []) if k and k in text]
        at.append(min(pos) if pos else -1)
    found = [i for i, p in enumerate(at) if p >= 0]
    seq = [at[i] for i in found]
    order = seq == sorted(seq)
    outcomes = 0
    for i in found:
        keys = scenes[i].get("outcome_keys") or []
        if not keys or any(k in text for k in keys):
            outcomes += 1
    errors = [c for c in (ep.get("contradicts") or []) if c and c in text]
    invented = [c for c in (ep.get("invents") or []) if c and c in text]
    recall = len(found) / float(len(scenes)) if scenes else 0.0
    clean = bool(scenes) and not errors and not invented and order and recall >= 2 / 3.0
    return {"scenes": len(scenes), "found": len(found), "recall": recall, "order": order,
            "outcomes": outcomes, "errors": errors, "invented": invented, "clean": clean}


def stored_digest(db, ep, stage="digest"):
    """What the save actually holds for this episode: the digest her record
    kept (`stage="digest"`), or the raw page text her line was cut from
    (`stage="raw"`). Read-only through a uri connection -- never a file copy
    of an open save, which returns a stale image."""
    if not os.path.exists(db):
        return "", ""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return "", ""
    text, how = "", ""
    try:
        if stage == "digest" and ep.get("anime_id"):
            for row in con.execute("SELECT value FROM kv WHERE key='known_things'"):
                try:
                    things = json.loads(row[0])
                except (ValueError, TypeError):
                    continue
                # a list of things, each with its own key and its parts
                want = f"anime:{ep['anime_id']}"
                for thing in (things if isinstance(things, list) else []):
                    if not isinstance(thing, dict) or thing.get("key") != want:
                        continue
                    for part in (thing.get("parts") or []):
                        if str(part.get("label", "")) == f"第{ep['ep']}話":
                            text, how = str(part.get("text") or ""), "the digest in her record"
        if stage == "raw" and not text:
            r = con.execute("SELECT text FROM recaps WHERE ja=? AND ep=? ORDER BY id DESC LIMIT 1",
                            (ep["show"], int(ep["ep"]))).fetchone()
            if r:
                text, how = str(r[0] or ""), "the raw page in the cache"
    except sqlite3.Error:
        pass
    finally:
        con.close()
    return text, how


def from_archive(ep, root="data/recaps"):
    """The digest the last pipeline run chose for this episode, read back out
    of the archive on disk. Scoring a run again costs nothing this way, which
    is half the reason the archive exists."""
    key = str(ep["anime_id"]) if ep.get("anime_id") else ""
    if not key:
        return "", ""
    d = os.path.join(ROOT, root, key, "ep%03d" % int(ep["ep"]))
    try:
        with io.open(os.path.join(d, "manifest.json"), encoding="utf-8") as fh:
            man = json.load(fh)
    except (OSError, ValueError):
        return "", ""
    won = (man.get("chosen") or {}).get("url") or ""
    files = [f for f in (man.get("files") or []) if f.get("kind") == "digest"]
    hit = [f for f in files if f.get("url") == won] or files
    if not hit:
        return "", ""
    try:
        with io.open(os.path.join(d, hit[-1]["file"]), encoding="utf-8") as fh:
            return fh.read(), f"the archive, {(man.get('chosen') or {}).get('confidence', '?')}"
    except OSError:
        return "", ""


def _runnable_config(name):
    """The config as it will be once the patch script has been applied.

    A run needs the `transcript_digest` role and the two unbanned hosts. If
    `data/retired/<ts>_summaries_build/patch_config.py` has not been applied
    yet, a patched COPY is written to a temp file and used, so the scored run
    can be had without touching a config the running bots read."""
    path = os.path.join(ROOT, name) if not os.path.isabs(name) else name
    with io.open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    need = ("transcript_digest" not in (d.get("models") or {})
            or any("myanimelist" in h for h in (d.get("recap") or {}).get("blocked_hosts") or []))
    if not need:
        return name
    d.setdefault("models", {})["transcript_digest"] = dict(
        d["models"].get("digest_judge") or {}, prompt="prompts/transcript_digest.txt")
    hosts = [h for h in (d["recap"].get("blocked_hosts") or [])
             if h not in ("wikipedia.org", "myanimelist.net")]
    if "ja.wikipedia.org" not in hosts:
        hosts.append("ja.wikipedia.org")
    d["recap"]["blocked_hosts"] = hosts
    out = os.path.join(tempfile.gettempdir(), "recap_scored_config.json")
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=2)
    print(f"  the config patch has not been applied; running on a patched copy at {out}")
    return out


def scored(run=False, only="", config="config.json", db="data/world.db", archive=False):
    truth = load_truth()
    eps = [e for e in truth["episodes"] if e.get("scored", True)]
    skipped = [e for e in truth["episodes"] if not e.get("scored", True)]
    if only:
        want = {p.strip().lower() for p in only.split(",")}
        eps = [e for e in eps
               if f"{e['title']}:{e['ep']}".lower() in want or e["title"].lower() in want]
    app = None
    if run:
        tmp = os.path.join(tempfile.gettempdir(), "recap_scored.db")
        from tools import harness
        config = _runnable_config(config)
        app = harness.build_on(tmp, config=config, db=db)
        print(f"  built on a copy of {db} at {tmp}")
    rows = []
    for e in eps:
        if run:
            entry = {"title": e["title"], "ja": e["show"], "kind": "anime", "ep": e["ep"]}
            got = app.recap.synopsis(entry, e["ep"], llm=app.llm, anime_id=e.get("anime_id"),
                                     english=e["title"], titles=[e["title"], e["show"]])
            text = (got or {}).get("digest") or (got or {}).get("text") or ""
            how = f"the pipeline, {(got or {}).get('confidence', 'nothing')}"
            if got and got.get("scenes"):
                text += " " + " ".join(got["scenes"])
        elif archive:
            text, how = from_archive(e)
        else:
            # both live saves, digests first: what reached her is the digest
            # where there is one and the raw page cut only where there is not.
            # The two characters hold different episodes, and one show's rows
            # are in the second save.
            text, how = "", ""
            for stage in ("digest", "raw"):
                for save in (db, "data/yukarin.db"):
                    if not text:
                        text, how = stored_digest(os.path.join(ROOT, save), e, stage)
                if text:
                    break
        s = score_one(text, e)
        s.update({"show": e["show"], "ep": e["ep"], "how": how or "nothing stored",
                  "chars": len(text)})
        rows.append(s)
    clean = sum(1 for r in rows if r["clean"])
    print(f"\n  {'show':<16} {'ep':>3}  {'scenes':>7} {'order':>5} {'err':>4} {'inv':>4}  source")
    for r in rows:
        print(f"  {r['show'][:16]:<16} {r['ep']:>3}  {r['found']:>3}/{r['scenes']:<3} "
              f"{'ok' if r['order'] else 'no':>5} {len(r['errors']):>4} {len(r['invented']):>4}  "
              f"{r['how']} ({r['chars']}c)")
        for x in r["errors"]:
            print(f"      contradicts the truth: {x}")
        for x in r["invented"]:
            print(f"      in no source: {x}")
    print(f"\n  CLEAN (no error, no invention, scenes in order, >=2/3 named): "
          f"{clean} of {len(rows)}")
    for e in skipped:
        print(f"  not scored: {e['show']} ep{e['ep']} -- {e.get('why_not_scored', '')[:100]}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scored", action="store_true", help="score against the truth set")
    ap.add_argument("--run", action="store_true",
                    help="with --scored: run the pipeline on a copy (spends calls, fetches pages)")
    ap.add_argument("--only", default="", help='e.g. "Mitsudomoe:12,Mitsudomoe:13"')
    ap.add_argument("--archive", action="store_true",
                    help="with --scored: score the last run again from data/recaps, no calls")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--db", default="data/world.db")
    args = ap.parse_args()
    if args.scored:
        if args.run:
            # a live run is worth reading: the offline half silences the log
            # so a parse check prints only its own verdicts, and that left a
            # fetch with nothing to show for the pages it skipped
            logger.log = lambda *a, **k: print("   ", *a)
        return scored(run=args.run, only=args.only, config=args.config, db=args.db,
                      archive=args.archive)
    return offline()


if __name__ == "__main__":
    sys.exit(main())
