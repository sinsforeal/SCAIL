"""One resolution path for a work: the window titles, the order, one fetch.

    python tools/work_resolve_test.py            # the whole thing
    python tools/work_resolve_test.py --shape    # the title table only (no db)

Three things are checked and each of them was broken on 2026-09-03, the
evening he mentioned a 2010 lead of hers and she denied it.

**The title table.** Every row is a real window title out of
`data/telemetry_feed.jsonl`, with what the SHAPE of it may claim: "work" when
the brackets or the bar prove it, "name" when the shape settles the subject,
"unknown" for the many it cannot, and None for a window that is not a page
about a thing at all. "B-gata H-kei (Yamada's First Time: B Gata H Kei)" and
"Mitsuba Marui (Mitsudomoe)" are the same shape and one is a work and one a
character, which is why the shape is not allowed to guess and the knowledge
base settles it.

**The order.** Her own record and the roles the knowledge base lists for her
are asked first and locally: the exact case resolves to hers, with the part
named, with every network call made to raise. A search is the last resort and
does not run when something local answered.

**One fetch.** The record the resolution writes is the record every other
path reads: asked a second time, nothing is fetched; her sight's line, the
automatic lookup's idea of what is open in front of him and her situation's
recall all come off that one row.
"""
import io
import os
import shutil
import sys
import tempfile
import urllib.request

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from resident.sight import page_of          # noqa: E402
from sim import works                        # noqa: E402

CHROME = "chrome.exe"

# (window title, the kind the shape may claim, the subject it must give)
TITLES = [
    # a type in the brackets: a work, and the year is optional
    ("Midori no Hibi (Midori Days, TV 2004) - MyAnimeList.net - Google Chrome", "work", "Midori no Hibi"),
    ("Example Show (TV 2007) - MyAnimeList.net", "work", "Example Show"),
    ("Kodomo no Jikan (TV) - MyAnimeList.net", "work", "Kodomo no Jikan"),
    ("Oniichan dakedo Ai sae Areba Kankeinai yo ne! Specials (Special 2012) - MyAnimeList.net", "work",
     "Oniichan dakedo Ai sae Areba Kankeinai yo ne! Specials"),
    ("Cardcaptor Sakura: Clear Card-hen (Zoku-hen) (Unknown) - MyAnimeList.net", "work",
     "Cardcaptor Sakura: Clear Card-hen (Zoku-hen)"),
    ("Yojouhan Time Machine Blues (The Tatami Time Machine Blues, ONA 2022) - MyAnimeList.net", "work",
     "Yojouhan Time Machine Blues"),
    # a medium after the bar: also a work
    ("Osake wa Fuufu ni Natte kara | Manga - MyAnimeList.net", "work", "Osake wa Fuufu ni Natte kara"),
    ("Asobi no Kankei (Playful Relationships) | Light Novel - MyAnimeList.net", "work", "Asobi no Kankei"),
    # brackets that are only an alias -- THE CASE. A work, but the shape
    # cannot prove it, so it says so and the knowledge base answers.
    ("B-gata H-kei (Yamada's First Time: B Gata H Kei) - MyAnimeList.net", "unknown", "B-gata H-kei"),
    ("Kantai Collection: KanColle (KanColle) - MyAnimeList.net", "unknown", "Kantai Collection: KanColle"),
    ("IS: Infinite Stratos (Infinite Stratos) - MyAnimeList.net", "unknown", "IS: Infinite Stratos"),
    # the same shape, and a character page
    ("Mitsuba Marui (Mitsudomoe) - MyAnimeList.net", "unknown", "Mitsuba Marui"),
    ("Rebecca Miyamoto (Paniponi Dash!) - MyAnimeList.net", "unknown", "Rebecca Miyamoto"),
    # no brackets at all: a work, a person, or a character
    ("Fragtime - MyAnimeList.net", "unknown", "Fragtime"),
    ("Zatsu Tabi: That's Journey - MyAnimeList.net", "unknown", "Zatsu Tabi: That's Journey"),
    ("Minako Kotobuki - MyAnimeList.net", "unknown", "Minako Kotobuki"),
    # a subpage of a work is the work
    ("Mitsudomoe (TV 2010) - Characters & Staff - MyAnimeList.net", "work", "Mitsudomoe"),
    # not a page about a thing
    ("user's Profile - MyAnimeList.net", None, ""),
    ("user's Anime List - MyAnimeList.net", None, ""),
    ("MyAnimeList.net - Panel", None, ""),
    ("Login - MyAnimeList.net", None, ""),
    ("MyAnimeList.net", None, ""),
    ("Mitsudomoe Episode 7 Discussion - Forums - MyAnimeList.net", None, ""),
    # a work's own forum is a page about the work, and his reading it is the
    # same fact as his reading the work's page
    ("Mitsudomoe (TV 2010) - Forum - MyAnimeList.net", "work", "Mitsudomoe"),
    # Wikipedia: anything at all, and the image viewer puts the article last
    ("苺ましまろ - Wikipedia", "unknown", "苺ましまろ"),
    ("田村ゆかり - Wikipedia — Mozilla Firefox", "unknown", "田村ゆかり"),
    ("Life Is Strange (video game) - Wikipedia", "unknown", "Life Is Strange"),
    ("Surat Diamond Bourse - Wikipedia", "unknown", "Surat Diamond Bourse"),
    ("Apple Street View Van - Look Around (Apple) - Wikipedia", "unknown", "Look Around"),
    # not a browser at all
    ("B-gata H-kei (Yamada's First Time: B Gata H Kei) - MyAnimeList.net", None, "", "notepad++.exe"),
]

fails = []


def shape_table():
    print("== what the shape of a window title may claim ==")
    for row in TITLES:
        title, want_kind, want_subject = row[0], row[1], row[2]
        proc = row[3] if len(row) > 3 else CHROME
        got = page_of(title, proc)
        kind = got["kind"] if got else None
        subject = got["subject"] if got else ""
        ok = (kind == want_kind) and (not want_kind or subject == want_subject)
        if not ok:
            fails.append(f"page_of({title!r}) -> {kind!r} {subject!r}, wanted {want_kind!r} {want_subject!r}")
        print(f"  {'ok ' if ok else 'FAIL'} {str(kind):8} {subject[:44]:46} {title[:58]}")


def _no_network():
    """Every HTTP request raises: this case must be answered out of her own
    record and the local knowledge base, and a test that quietly reached the
    MyAnimeList API would pass for the wrong reason."""
    def refuse(*a, **k):
        raise AssertionError("this case must not touch the network")
    urllib.request.urlopen = refuse


class Screen:
    """His machine, with one window on it: the shape `monitor.right_now`
    returns (`machine/monitor_client.py`), and nothing else of his."""

    def __init__(self, title, proc=CHROME, seconds=600.0):
        self.title, self.proc, self.seconds = title, proc, seconds

    def right_now(self):
        return self.proc, self.title, self.seconds, 5.0

    def seconds_since_input(self):
        return 5.0


TITLE = "B-gata H-kei (Yamada's First Time: B Gata H Kei) - MyAnimeList.net"


def resolution():
    from tools import harness
    tmp = os.path.join(tempfile.gettempdir(), "work_resolve_test.db")
    app = harness.build_on(tmp, "config_yukarin.json", "data/yukarin.db")
    harness.refuse_model(app)
    _no_network()
    if app.sight is None:
        fails.append("her sight was not built: the resolution cannot be replayed")
        return
    known = app.lookup.known
    # a save copied for the test still carries the evening it came from: the
    # case is the FIRST time this page is in front of him
    known.drop("work:B-gata H-kei")
    app.store.set("glance_last", None)
    app.store.set("glance_seen", {})

    day = app.clock.date_str()
    searches = app.store.today_count("search_counts", day)

    print("\n== the page in front of him, seen and resolved ==")
    print(f"  window: {TITLE}")
    app.sight.monitor = Screen(TITLE)
    app.sight.glance()
    it = app.store.get("glance_last") or {}
    print(f"  kind={it.get('kind')} subject={it.get('subject')!r} hers={it.get('hers')} "
          f"part={it.get('part')!r} source={it.get('source')!r}")
    if not it.get("hers"):
        fails.append("the page for a work she was in did not resolve as hers")
    elif not it.get("part"):
        fails.append("it resolved as hers with no part named")
    if app.store.today_count("search_counts", day) != searches:
        fails.append("a search ran for a work her own record and her roles both know")
    if "her roles on MyAnimeList" not in (it.get("source") or "") \
            and "her own record" not in (it.get("source") or ""):
        fails.append(f"the answer came from {it.get('source')!r}, not from her record or her roles")

    # the record: one row, and it carries the Japanese name her record knows
    row = known.get(it.get("known_key") or "")
    if not row:
        fails.append("nothing was written to what she knows by name")
    else:
        print(f"  one record: {row['key']} names={row['names']} hers={row.get('hers')} part={row.get('part')!r}")
        print(f"    text: {row['text'][:120]}")
        if not any(_ja(n) for n in row["names"]):
            fails.append("the record carries no Japanese name, so a message of his in Japanese cannot reach it")

    print("\n== the same page, and then the same name typed: nothing fetched ==")
    app.store.set("glance_seen", {})
    app.sight._glance_on = None
    app.sight.glance()
    typed = works.identify(["B型H系"], config=app.config, store=app.store, clock=app.clock,
                           known=known, anime_kb=app.anime_kb, lore=app.lore,
                           search=app.lookup.search, allow_search=False)
    print(f"  typed 『B型H系』 -> from_known={typed and typed.get('from_known')} key={typed and typed.get('key')}")
    if not (typed and typed.get("from_known")):
        fails.append("the name he typed did not land on the record the page had already written")
    if app.store.today_count("search_counts", day) != searches:
        fails.append("the same work was fetched a second time")
    rows = [r for r in (app.store.get("known_things") or []) if str(r.get("key", "")).endswith("B-gata H-kei")]
    print(f"  rows in what she knows for this work: {len(rows)}")
    if len(rows) != 1:
        fails.append(f"{len(rows)} records for one work; there is meant to be one")

    print("\n== her own record, by the name he types ==")
    hit = app.lore.match("B型H系") if app.lore else []
    ids = [r.get("id") for r, _t in hit]
    print(f"  lore.match('B型H系') -> {ids}")
    if "yk.career.yamada" not in ids:
        fails.append("her own record for that part is not reachable by the name he types")

    print("\n== the retrieval, when he names the part she played ==")
    lines = app.lore.lines("B型H系って知ってる？山田の声やってたよね") if app.lore else []
    for l in lines:
        print(f"  [{getattr(l, 'source', '')}{' pinned' if getattr(l, 'pin', False) else ''} "
              f"{getattr(l, 'weight', 0):.2f}] {str(l)[:90]}")
    if not any(getattr(l, "pin", False) for l in lines):
        fails.append("a part she played, named by him at full score, was not pinned: "
                     "the whole block's character cap can throw it away")

    print("\n== what the lookup thinks is open in front of him ==")
    ctx = app.lookup._in_play()
    print("  " + (ctx.replace("\n", "\n  ") or "(nothing)"))
    if "B" not in ctx and "B型H系" not in ctx:
        fails.append("the lookup's context does not name the page in front of him")
    if "episode" in ctx.split("PLAYING RIGHT NOW")[0]:
        fails.append("the lookup's context still names the player's episode as what is open")

    print("\n== the line her situation gets ==")
    lines = app.sight.glance_lines(lambda en, ja=None: ja or en) if app.store.get("glance_last") else []
    for line, kind, pin in lines:
        print(f"  [{kind}{' pinned' if pin else ''}] {str(line)[:160]}")
    shutil.rmtree(tmp, ignore_errors=True) if os.path.isdir(tmp) else None


def _ja(s):
    return any("぀" <= c <= "鿿" for c in str(s or ""))


def main():
    shape = "--shape" in sys.argv
    shape_table()
    if not shape:
        resolution()
    print("")
    if fails:
        for f in fails:
            print("FAIL " + f)
        print(f"[work_resolve] {len(fails)} failure(s)")
        return 1
    print(f"[work_resolve] {len(TITLES)} window titles hold"
          if shape else "[work_resolve] the titles, the order and the one record all hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
