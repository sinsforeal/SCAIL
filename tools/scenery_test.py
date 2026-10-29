"""Borrowed eyes without the network or the models: discovery with a
stubbed search and judge, harvest with a stubbed vision, the picker
against her scene / season / hour / weather / lore, the offer gates,
adoption and the lore line. On a copy of the save.

    python tools/scenery_test.py
"""
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import harness  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.setup = lambda out_dir: None
logger.log = lambda m, to_console=True: print("   log:", m[:120])

import tomoe.scenery as scmod


def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_scenery.db")
    app = harness.build_on(tmp)
    sc, st, store = app.scenery, app.state, app.store
    sc.img_dir = lambda: os.path.join(tempfile.gettempdir(), "scail_scenery_img")
    os.makedirs(sc.img_dir(), exist_ok=True)
    fails = []

    def check(label, ok):
        print(("  ok   " if ok else "  FAIL ") + label)
        if not ok:
            fails.append(label)

    with store.lock:
        store.conn.execute("DELETE FROM scenery")
        store.conn.commit()
    for k in ("scenery_accounts", "scenery_lore", "scenery_send_counts", "scenery_follow_counts", "x_action_queue"):
        store.set(k, {} if k != "x_action_queue" else [])
    store.set("scenery_last_send_ts", 0)

    # --- stubs
    class V:
        enabled = True

        def fetch_image(self, url):
            return ("image/jpeg", ("IMG" + url).encode())

        def look(self, images, instruction, date_str="", label="", max_tokens=None):
            if label == "scenery-judge":
                return "A snapshot of a station platform at dusk; a person's own photo."
            u = images[0][1].decode()
            kind = "street" if "str" in u else "station" if "sta" in u else "konbini" if "kon" in u else "park"
            names = ["Nerima Station"] if "sta1" in u else ["Kichijoji Station"] if "sta2" in u else []
            # the shop signs a real street carries: a barber's name is not a
            # claim about which ward this is, and a station name is
            text = ["理容 なかの", "03-6913-1858"] if "str1" in u else ["吉祥寺駅"] if "str2" in u else names
            return json.dumps({"place_kind": kind, "setting": "outdoor", "time_of_day": "evening", "season": "summer", "weather": "clear",
                               "objects": ["yellow seibu train", "vending machine", "wet platform"], "text_visible": text, "names": names,
                               "region": "kyoto" if "kyoto" in u else "tokyo",
                               "faces": "face" in u, "portrait": "face" in u, "people": 2, "screen": False, "plausible_hers": True, "quality": 4,
                               "caption": f"a {kind} at dusk"})
    sc.vision = V()
    real = app.llm.call_json
    app.llm.call_json = lambda role, messages, max_tokens=None: ({"verdict": "follow", "kind": "student daily life", "why": "own snapshots of the train home"}, "") if role == "scenery_judge" else real(role, messages, max_tokens)
    items = [
        {"author": "yuki_days", "author_name": "yuki", "text": "帰り道", "media_urls": ["http://x/sta1.jpg"], "url": "https://x.com/yuki/1", "timestamp": "2026-08-26T09:00:00Z", "is_repost": False},
        {"author": "yuki_days", "author_name": "yuki", "text": "ファミマ", "media_urls": ["http://x/kon1.jpg"], "url": "https://x.com/yuki/2", "timestamp": "2026-08-26T09:10:00Z", "is_repost": False},
        {"author": "mao_o", "author_name": "mao", "text": "駅", "media_urls": ["http://x/sta2.jpg"], "url": "https://x.com/mao/1", "timestamp": "2026-08-26T09:20:00Z", "is_repost": False},
        {"author": "mao_o", "author_name": "mao", "text": "友達と", "media_urls": ["http://x/sta3face.jpg"], "url": "https://x.com/mao/2", "timestamp": "2026-08-26T09:30:00Z", "is_repost": False},
        {"author": "mao_o", "author_name": "mao", "text": "旅行", "media_urls": ["http://x/sta4kyoto.jpg"], "url": "https://x.com/mao/3", "timestamp": "2026-08-26T09:40:00Z", "is_repost": False},
        {"author": "yuki_days", "author_name": "yuki", "text": "散歩", "media_urls": ["http://x/str1.jpg"], "url": "https://x.com/yuki/3", "timestamp": "2026-08-26T09:50:00Z", "is_repost": False},
        {"author": "yuki_days", "author_name": "yuki", "text": "散歩", "media_urls": ["http://x/str2.jpg"], "url": "https://x.com/yuki/4", "timestamp": "2026-08-26T09:55:00Z", "is_repost": False},
    ]
    scmod.xm.search_posts = lambda driver, sv, q, scrolls=2, log=print, record=True: items
    q0 = len(store.get("x_action_queue", []))
    sc.discover(driver=None)
    accts = sc.accounts()
    check(f"discover: {len(accts)} judged, {len(sc.followed())} on the watchlist", len(accts) == 2 and len(sc.followed()) == 2)
    check("no X follow queued: a watchlist, not her account", len(store.get("x_action_queue", [])) == q0)
    rows = sc.rows()
    check(f"harvested {len(rows)} image(s) from watchlist accounts", len(rows) == 7)
    check("an image that says it is in Kyoto is never usable",
          any(r["rejected"].startswith("kyoto") for r in rows) and all(r["region"] == "kyoto" for r in rows if r["rejected"].startswith("kyoto")))
    scmod.xm.fetch_user_posts = lambda driver, sv, h, scrolls=1, log=print: [it for it in items if it["author"] == h]
    check("a watchlist pass re-fetches and skips what is known", sc.harvest_watchlist(driver=None) == 0 and all("visited_ts" in a for a in sc.accounts().values()))
    store.set("scenery_last_run_ts", 0)
    check("a run is due on its own clock, never while she is looking", sc.due() and not sc.due(social_busy=True))
    check("a portrait is kept on file but never usable", any(r["rejected"] == "a selfie or a portrait" for r in rows) and all(r["rejected"] for r in rows if r["portrait"]))
    check("re-harvest skips what is known", sc.harvest(items) == 0)
    # --- picking
    st.gauges["energy"] = 50
    scene_sta = {"location": "Nerima station platform", "setting": "outdoors", "activity": "waiting"}
    import datetime
    sc._tod_now = lambda: "evening"
    sc._season_now = lambda: "summer"
    row, why = sc.pick(scene_sta)
    check(f"the station scene picks the local station photo: {row['names'] if row else why}", row and "Nerima" in row["names"])
    row2, why2 = sc.pick({"location": "her room", "setting": "indoors", "activity": "lying down"})
    check(f"no room photo -> nothing: {why2}", row2 is None)
    sc._tod_now = lambda: "morning"
    row3, why3 = sc.pick(scene_sta)
    check(f"wrong hour for an outdoor photo -> nothing: {why3}", row3 is None)
    sc._tod_now = lambda: "evening"
    row4, why4 = sc.pick(scene_sta, weather={"precip_mm": 3.0})
    check(f"rain vs a clear photo -> nothing: {why4}", row4 is None)
    # --- where she actually is: the node, the leg, and her own words
    check("'homework with Aya' is not the word 'home'", sc.kind_of_text("homework with Aya") == "")
    check("the node she stands on beats the scene's words",
          sc.place_kind_of({"location": "her room"}, node="library") == "library"
          and sc.place_kind_of({"location": "the Nerima ward library", "activity": "homework with Aya"}, node="library") == "library")
    check("the exhibition and the library are places the map has now",
          sc.place_kind_of({}, node="koto") == "museum" and sc.place_kind_of({"location": "CREVIA BASE Tokyo"}) == "museum")
    check("mid-journey it is the leg she is on, not the place she left",
          sc.place_kind_of({"location": "home"}, leg_mode="train") == "train"
          and sc.place_kind_of({"location": "home"}, leg_mode="walk") == "street"
          and sc.place_kind_of({"location": "home"}, leg_mode="car") == "")
    check("longest keyword wins, in either language",
          sc.kind_of_text("商店街のたい焼き") == "shotengai" and sc.kind_of_text("図書館なう") == "library"
          and sc.kind_of_text("池袋で乗り換え") == "station")
    check("her own words name the place when nothing else does",
          sc.place_kind_of({}, said="あやと図書館で勉強してる") == "library")
    rowv, whyv = sc.pick(scene_sta, said="図書館なう、あやと勉強中")
    check(f"a photo that contradicts what she has just said does not go: {whyv}",
          rowv is None and "just said" in whyv)
    check("a barber's name is not a claim about the ward; a station name is",
          sc._consistent({"names": "[]", "text_visible": '["理容 なかの", "03-6913-1858"]'}, "street")[0]
          and not sc._consistent({"names": "[]", "text_visible": '["吉祥寺駅"]'}, "street")[0])
    # --- offer gates and adoption
    r, h = sc.offer(scene_sta, awake=False)
    check(f"asleep -> no offer: {h}", r is None)
    # A forced offer still has to have something that FITS: the harvested pool
    # holds one station photo and at 23:00 a daytime one does not match the
    # scene, so this used to pass or fail on whatever the harvester happened to
    # have caught. Put a station photo in that fits the scene being asked for.
    with store.lock:
        store.conn.execute("INSERT INTO scenery(ts,author,url,posted,img_url,path,place_kind,setting,time_of_day,season,weather,"
                           "faces,people,screen,plausible,quality,names,objects,text_visible,caption,venue,portrait,region,event,used_ts,rejected) "
                           "VALUES(?,?,?,?,?,?,?,?,?,?,?,0,2,0,1,4,'[]','[]','[]',?,'unknown',0,'unknown','',NULL,'')",
                           (app.clock.now_ts(), "station_guy", "https://x.com/s/1", "", "http://x/s1.jpg", "s1.jpg",
                            "station", "outdoor", sc._tod_now(), sc._season_now(),
                            "clear", "a platform with the train pulling in"))
        store.conn.commit()
    r, h = sc.offer(scene_sta, force=True)
    check(f"forced offer returns the photo and a hint: {h if r is None else 'ok'}",
          r is not None and "JUST TAKEN A PHOTO" in h and sc.pending is r)
    sc.adopt(r, "the train was late again")
    check("adopted: used, lore, count", r["used_ts"] is None and store.get("scenery_lore", {}).get("station") and sc._sent_today() == 1)
    check("lore reaches her prompt", "photos you have sent him" in sc.lore_line() and "station" in sc.lore_line())
    r5, why5 = sc.pick(scene_sta)
    check(f"the other station photo (Kichijoji) is refused by the lore / locality: {why5}", r5 is None)
    r, h = sc.offer(scene_sta)
    check(f"one a day: {h}", r is None and h == "sent today already")
    # --- aiming the harvest: demand, coverage, gaps, the next query
    store.conn.execute("DELETE FROM scenes")
    now = app.clock.now_ts()
    for i, (hm, loc, act) in enumerate([("09:10", "Nerima station", "on the platform"),
                                        ("09:30", "Nerima station", "waiting"),
                                        ("12:00", "the FamilyMart on the park side", "an ice"),
                                        ("15:00", "her room, home", "phone")]):
        store.conn.execute("INSERT INTO scenes(ts,date,hm,location,activity,phone_access,with_who,sensory,inner,share_worthy,events,raw) "
                           "VALUES(?,?,?,?,?,'free','alone','','',0,'[]','{}')", (now - 3600 * (i + 1), app.clock.date_str(), hm, loc, act))
    store.conn.commit()
    dem = sc.demand()
    check(f"demand is read off her own scenes: {dem}",
          dem.get("station", {}).get("morning") == 2 and dem.get("konbini", {}).get("midday") == 1 and "home" in dem)
    cov = {r["kind"]: r for r in sc.coverage()}
    # station scenes = the 2 inserted above plus whatever the live plan adds:
    # the route is demand too, so pinning the total would break every time
    # the day changes
    check(f"a kind she is never in is not a gap; home is not sendable (station {cov['station']['scenes']})",
          "home" not in cov and cov["station"]["bands"].get("morning", 0) >= 2 and cov["river"]["missing"] == 0)
    check("the station rows on file do not cover the morning she is there",
          cov["station"]["per_band"]["morning"] == 0 and cov["station"]["per_band"]["evening"] == 1
          and cov["station"]["missing"] > 0)
    q, why, ev = sc.next_query()
    check(f"the next search is aimed at a gap: {why}",
          bool(q) and any(g["kind"] in why for g in sc.gaps()) and "row(s) for" in why and ev == "")
    # --- the event she is going to
    store.set("event_stances", {"date": app.clock.date_str(), "events": [
        {"name": "諏訪神社盆踊り", "when": "today", "stance": "going", "pusher": "", "why": "the group is going"},
        {"name": "summer homework panic", "when": "today", "stance": "going", "pusher": "", "why": "the pile"},
    ]})
    evs = sc.events_soon()
    check(f"only a real event with a venue is searchable: {[e['core'] for e in evs]}",
          len(evs) == 1 and evs[0]["core"] == "諏訪神社盆踊り" and evs[0]["node"] == "shrine")
    check("the edition number and the subtitle come off the name",
          sc._event_core("第67回 東京高円寺阿波おどり") == "東京高円寺阿波おどり"
          and sc._event_core("「ピクサーの世界展」あなたが夢見た物語の世界へ") == "ピクサーの世界展")
    q2, why2, ev2 = sc.next_query()
    check(f"an event she is going to today jumps the gap queue: {why2}",
          ev2 == "諏訪神社盆踊り" and "諏訪神社盆踊り" in q2 and "she is going" in why2)
    check("she is at it when she is standing on its node, and not otherwise",
          sc.event_now({}, node="shrine") == "諏訪神社盆踊り" and sc.event_now({}, node="home") == "")
    # one row of the festival, and it goes out there and nowhere else
    with store.lock:
        store.conn.execute("INSERT INTO scenery(ts,author,url,posted,img_url,path,place_kind,setting,time_of_day,season,weather,"
                           "faces,people,screen,plausible,quality,names,objects,text_visible,caption,venue,portrait,region,event,used_ts,rejected) "
                           "VALUES(?,?,?,?,?,?,?,?,?,?,?,0,3,0,1,4,'[]','[]','[]',?,'unknown',0,'unknown',?,NULL,'')",
                           (app.clock.now_ts(), "matsuri_guy", "https://x.com/m/1", "", "http://x/f1.jpg", "f1.jpg",
                            "other", "outdoor", "evening", "summer", "clear", "paper lanterns over a shrine yard",
                            "諏訪神社盆踊り"))
        store.conn.commit()
    store.set("scenery_send_counts", {})
    store.set("scenery_last_send_ts", 0)
    r_at, why_at = sc.pick({"location": "the shrine"}, node="shrine", event="諏訪神社盆踊り")
    check(f"at the festival, its own photo goes -- kind gate and all: {why_at if not r_at else r_at['caption'][:40]}",
          bool(r_at) and r_at["author"] == "matsuri_guy")
    r_not, why_not = sc.pick({"location": "her room"}, node="home")
    check(f"the festival photo never goes from anywhere else: {why_not}",
          not r_not or r_not["author"] != "matsuri_guy")
    check("the next two days' plan is demand too, not just an ordering",
          set(sc.route_bands()) == set(sc.route_kinds())
          and all(isinstance(v, dict) for v in sc.route_bands().values()))
    check("gaps are ranked, and a kind with no query is skipped",
          all(g["missing"] > 0 or g["on_route"] for g in sc.gaps()))
    check("coverage_report prints the table and the next search",
          "next search:" in sc.coverage_report() and "station" in sc.coverage_report())
    accts = sc.accounts()
    accts["some_shop"] = {"verdict": "skip", "why": "a shop", "kind": "business"}
    accts["ward_parks"] = {"verdict": "place", "why": "the ward's own park feed", "kind": "ward park feed"}
    store.set("scenery_accounts", accts)
    check("a `place` verdict is on the watchlist: the ward's own feed photographs her park",
          "ward_parks" in sc.followed())
    forgotten = sc.forget_skips()
    check(f"rejudge forgets the {forgotten} skip(s) and keeps the watchlist",
          forgotten == 1 and "some_shop" not in sc.accounts() and sc.followed() == {"yuki_days", "mao_o", "ward_parks"})
    print(sc.report())
    print(f"\n{len(fails)} failure(s)" if fails else "\nall ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
