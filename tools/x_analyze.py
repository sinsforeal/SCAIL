"""One-time (repeatable) analysis of her X account. Read-only.

    python tools/x_analyze.py --following      # catalogue who the account follows
    python tools/x_analyze.py --followers      # catalogue who follows the account (the baseline)
    python tools/x_analyze.py --feed [N]       # one human-paced look at the Following timeline (N scrolls)
    python tools/x_analyze.py --cards          # neutral account cards from bio + posts seen (LLM, batched)
    python tools/x_analyze.py --all            # following, then a longer feed sample, then cards
    python tools/x_analyze.py --report         # print what is on disk

Uses `sensors.x_tools_profile_dir`, a copy of her logged-in profile, so this
runs beside a live look instead of waiting for a gap between them. `--live-
profile` uses hers (`sensors.x_profile_dir`) instead, which means closing any
Chrome window on it first and not running during a look. Writes under data/x/.
Nothing here follows, unfollows, likes or posts.
"""

import os
import sys
import time
import json
import argparse
import collections

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from sensors import x_monitor as xm


def log(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode(), flush=True)


def do_following(driver, sv):
    handle = xm.logged_in_handle(driver, sv)
    if not handle:
        log("[x] not logged in (no profile link on /home). Run x_login.cmd, log in, close the window, retry.")
        return None
    log(f"[x] logged in as @{handle}")
    return xm.fetch_following(driver, sv, handle, log=log)


def do_followers(driver, sv):
    handle = xm.logged_in_handle(driver, sv)
    if not handle:
        log("[x] not logged in (no profile link on /home). Run x_login.cmd, log in, close the window, retry.")
        return None
    log(f"[x] logged in as @{handle}")
    return xm.fetch_followers(driver, sv, handle, log=log)


def do_feed(driver, sv, scrolls):
    fresh, seen = xm.scroll_following(driver, sv, scrolls=scrolls, log=log)
    return fresh, seen


def do_cards(config, sv, batch=12):
    from llm import LLM
    import logger
    logger.setup(config.logging.dry_run_out_dir)
    llm = LLM(config)
    following = xm.load_following(sv)
    if not following:
        log("[x] no following.json yet; run --following first")
        return
    accounts = xm.load_accounts(sv)
    posts = collections.defaultdict(list)
    for it in xm.feed_all(sv):
        a = it.get("author", "").lower()
        line = it.get("text", "").replace("\n", " ")[:200]
        if it.get("quoted"):
            line += f" [quoting: {it['quoted'][:100]}]"
        if it.get("media"):
            line += f" [{it['media']} image(s)]"
        if it.get("video"):
            line += " [video]"
        posts[a].append(line)
    todo = [h for h in following["accounts"] if h.lower() not in {k.lower() for k in accounts} or accounts.get(h, {}).get("posts_seen", 0) < len(posts.get(h.lower(), []))]
    log(f"[x] cards to write: {len(todo)} of {len(following['accounts'])}")
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        body = []
        for h in chunk:
            acc = following["accounts"][h]
            sample = posts.get(h.lower(), [])[-8:]
            body.append(f"### @{h}\nname: {acc.get('name', '')}\nbio: {acc.get('bio', '') or '(no bio)'}\nposts seen ({len(posts.get(h.lower(), []))} total):\n" +
                        ("\n".join(f"- {p}" for p in sample) if sample else "(none in the sample)"))
        user = "\n\n".join(body)
        data, raw = llm.call_json("x_account", [{"role": "system", "content": config.prompt_text("x_account")}, {"role": "user", "content": user}])
        got = data.get("accounts") if isinstance(data, dict) else None
        if not isinstance(got, dict):
            log(f"[x] batch {i // batch + 1}: unparseable, skipping")
            continue
        for h in chunk:
            card = got.get(h) or got.get(h.lower()) or next((v for k, v in got.items() if k.lower().lstrip("@") == h.lower()), None)
            if not isinstance(card, dict):
                continue
            acc = following["accounts"][h]
            accounts[h] = {"handle": h, "name": acc.get("name", ""), "bio": acc.get("bio", ""),
                           "card": str(card.get("card", ""))[:600], "language": str(card.get("language", ""))[:10],
                           "topics": [str(t)[:30] for t in (card.get("topics") or [])][:6], "kind": str(card.get("kind", ""))[:12],
                           "posts_seen": len(posts.get(h.lower(), [])), "carded": time.time()}
        xm.save_accounts(sv, accounts)
        log(f"[x] batch {i // batch + 1}: {len(chunk)} card(s) written")
    log(f"[x] accounts.json: {len(accounts)} card(s)")


def report(sv):
    f = xm.load_following(sv)
    a = xm.load_accounts(sv)
    feed = xm.feed_all(sv)
    log(f"following: {f['count'] if f else 0} (fetched {time.strftime('%Y-%m-%d %H:%M', time.localtime(f['fetched'])) if f else 'never'})")
    fol = xm.load_followers(sv)
    mutual = xm.follows_back(sv) & {h.lower() for h in ((f or {}).get("accounts") or {})}
    private = xm.private_accounts(sv)
    log(f"followers: {fol['count'] if fol else 0} (fetched {time.strftime('%Y-%m-%d %H:%M', time.localtime(fol['fetched'])) if fol else 'never'}); "
        f"mutual: {len(mutual)}; private: {len(private)} -- none of those can be unfollowed")
    log(f"feed items on disk: {len(feed)}; cards: {len(a)}")
    by = collections.Counter(it.get("author", "").lower() for it in feed)
    log("most seen in feed: " + ", ".join(f"@{h} ({n})" for h, n in by.most_common(15)))
    kinds = collections.Counter(v.get("kind", "?") for v in a.values())
    langs = collections.Counter(v.get("language", "?") for v in a.values())
    log(f"kinds: {dict(kinds)}  languages: {dict(langs)}")
    topics = collections.Counter(t for v in a.values() for t in v.get("topics", []))
    log("topics: " + ", ".join(f"{t} ({n})" for t, n in topics.most_common(25)))
    if f and a:
        missing = [h for h in f["accounts"] if h not in a]
        if missing:
            log(f"no card yet: {len(missing)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--following", action="store_true")
    ap.add_argument("--followers", action="store_true")
    ap.add_argument("--feed", nargs="?", const=8, type=int, default=None, metavar="SCROLLS")
    ap.add_argument("--cards", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--live-profile", action="store_true",
                    help="use her own Chrome profile rather than the tools' copy of it")
    args = ap.parse_args()
    config = Config()
    sv = config.sensor_view
    profile = "" if args.live_profile else str(getattr(sv, "x_tools_profile_dir", "") or "")
    if profile and not os.path.isdir(profile):
        log(f"[x] {profile} does not exist; falling back to her own profile, so do not run this during a look")
        profile = ""
    if args.report or not any([args.following, args.followers, args.feed is not None, args.cards, args.all]):
        report(sv)
        return
    if args.following or args.followers or args.feed is not None or args.all:
        log(f"[x] Chrome on {profile or sv.x_profile_dir}")
        driver = xm.open_driver(sv, profile)
        try:
            if args.following or args.all:
                do_following(driver, sv)
            if args.followers or args.all:
                do_followers(driver, sv)
            if args.feed is not None or args.all:
                do_feed(driver, sv, args.feed if args.feed is not None else 20)
        finally:
            try:
                driver.quit()
            except Exception:
                pass
    if args.cards or args.all:
        do_cards(config, sv)
    report(sv)


if __name__ == "__main__":
    main()
