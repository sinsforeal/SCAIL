"""Her X (Twitter) account, read through a real logged-in Chrome profile.

Read-only for now. Two things it can do: catalogue who the account follows
(handle, name, bio) and scroll the *Following* timeline the way a person
does: a few scrolls, uneven pauses, then leave. Never the For You tab, never
recommendations, never fast. It runs with no window (`sensors.x_headless`);
`/x headless off` puts the window back when the parsing needs watching.
Everything it sees goes to
data/x/ as plain files that the simulation reads later, when she looks.

The parsing is lifted from x_scrape/x_watch.py, which has been reading X
through the same kind of profile for months: a tweet is the article whose
own permalink anchor wraps a <time>; nothing else identifies it reliably.
"""

import json

import atomic
import os
import contextlib
import threading
import random
import re
import time

from bs4 import BeautifulSoup, NavigableString

from sensors import chrome_ext

try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:  # the simulation must import without selenium installed
    webdriver = None

FOLLOWING_TAB_LABELS = ("Following", "フォロー中")

# The badge X puts on a user cell or a profile when that account follows the
# one we are logged in as, in both interface languages, and the label on the
# padlock a protected account carries. Both are read, never guessed: an
# account that follows her back is never unfollowed, and neither is one that
# has since gone private.
FOLLOWS_YOU_LABELS = ("follows you", "フォローされています")
PRIVATE_LABELS = ("protected account", "非公開アカウント", "鍵アカウント")


def _paths(config):
    base = config.x_data_dir
    # A character with no account has this key blanked (`Config.ACCOUNT_KEYS`),
    # and a blank path is the empty case, not an error: every reader below
    # gets a path that does not exist and returns its default, the way the
    # calendar loads nothing for a character with no world. The media diet
    # asked for her liked accounts on the first prompt of a character in a
    # world with no account and this made a directory from ''.
    # One list of names, so the empty case cannot drift from the full one. It
    # did: `follow_changes` and `followers` were added to the dict below and
    # not to the blank dict above, so a character with no account got a
    # KeyError instead of an empty path the moment anything asked what he had
    # followed -- which is the reflection role, on every run of it.
    names = {
        "following": "following.json",
        "accounts": "accounts.json",
        "feed": "feed.jsonl",
        "seen": "seen.json",
        "status": "status.json",
        "sessions": "sessions.json",
        "likes": "likes.jsonl",
        "likes_seen": "likes_seen.json",
        "actions": "actions.jsonl",
        "follow_changes": "follow_changes.jsonl",
        "followers": "followers.json",
    }
    if not base:
        return {k: "" for k in names}
    os.makedirs(base, exist_ok=True)
    return {k: os.path.join(base, v) for k, v in names.items()}


def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _save(path, data):
    atomic.write_json(path, data, indent=1)


def _pause(config, factor=1.0):
    time.sleep(random.uniform(config.x_scroll_pause_min, config.x_scroll_pause_max) * factor)


def _text(element):
    out = ""
    for child in element.children:
        if isinstance(child, NavigableString):
            out += str(child)
        elif child.name == "img":
            out += child.get("alt", "")
        elif child.name:
            out += child.get_text()
    return out.strip()


# ---------------- browser ----------------

# One Chrome profile, three things that want it: the scenery harvester on its
# own thread, her X look, and her posting. `open_driver` puts them all on the
# same `user-data-dir`, and a second Chrome on a held profile kills the first --
# which is the `InvalidSessionIdException: session deleted as the browser has
# closed the connection` that has been ending her look and her harvest mid-run.
# The harvester already stood aside for her (`Scenery.due(social_busy=...)`);
# nothing stood aside for the harvester. This is that lock, and it is taken by
# whoever opens the profile rather than by each caller remembering to.
_PROFILE_LOCK = threading.Lock()


@contextlib.contextmanager
def profile_lock(timeout=0.0, who=""):
    """Hold the Chrome profile, or yield False at once. Nobody waits on the
    main loop for a harvest that runs for minutes: her look skips this pass
    and comes back, which is what a person with a phone does anyway."""
    got = _PROFILE_LOCK.acquire(timeout=timeout) if timeout else _PROFILE_LOCK.acquire(blocking=False)
    try:
        yield got
    finally:
        if got:
            _PROFILE_LOCK.release()


def open_driver(config, profile_dir=""):
    """Chrome on her profile, headless unless `sensors.x_headless` is off.
    Raises if selenium is missing or the profile is held by another Chrome
    (close the login window first).

    `profile_dir` opens a DIFFERENT logged-in copy of the same account. Her
    look, her posting and the scenery harvest share the one profile and take
    turns for it, so an offline tool that wanted a session had to wait for a
    gap between her looks. A copy of the profile is a second session on the
    same account, and the tools use it (`sensors.x_tools_profile_dir`)."""
    if webdriver is None:
        raise RuntimeError("selenium is not installed")
    profile = profile_dir or config.x_profile_dir
    headless = bool(getattr(config, "x_headless", True))
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-data-dir={profile}")
    # uBlock, so an ad never reaches the feed as a post. Must come before the
    # driver is created and cannot coexist with --disable-extensions.
    chrome_ext.apply(options, getattr(config, "chrome_extension_dir", ""), profile,
                     log=lambda m: print(m))
    if headless:
        options.add_argument("--headless=new")
    if config.x_window_size:
        options.add_argument(f"--window-size={config.x_window_size}")
    # Reap on the way in, which is the rule `sensors/chrome_reaper.py` states
    # in its own docstring and which this path -- the one her look, her posting
    # and the scenery harvest all use -- was never following. Orphans only: the
    # MAL daemon runs against this same profile and a start that took the
    # profile off everybody would cut it off mid-run.
    try:
        from sensors import chrome_reaper
        chrome_reaper.reap_orphans(profile, log=lambda m: print(m))
    except Exception:
        pass
    driver = webdriver.Chrome(options=options)
    _hide_automation(driver, headless)
    chrome_ext.settle(driver, log=print)
    return driver


def _hide_automation(driver, headless):
    """Two things X can see. `navigator.webdriver` is true in every fresh
    document, so it is patched through CDP (a plain execute_script only holds
    until the next navigation). Headless Chrome also calls itself
    "HeadlessChrome/138.0.0.0" in the user agent; the UA is read back from the
    browser and the word replaced, so the version never has to be guessed or
    kept in config."""
    patch = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": patch})
    except Exception:
        pass
    try:
        driver.execute_script(patch)
    except Exception:
        pass
    if not headless:
        return
    try:
        ua = driver.execute_script("return navigator.userAgent") or ""
        if "HeadlessChrome" in ua:
            driver.execute_cdp_cmd("Network.setUserAgentOverride",
                                   {"userAgent": ua.replace("HeadlessChrome", "Chrome")})
    except Exception as e:
        print(f"[x] user agent not rewritten: {type(e).__name__}")


def logged_in_handle(driver, config):
    driver.get("https://x.com/home")
    try:
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='AppTabBar_Profile_Link']")))
    except TimeoutException:
        return None
    href = driver.find_element(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Profile_Link']").get_attribute("href") or ""
    m = re.search(r"x\.com/([A-Za-z0-9_]+)", href)
    return m.group(1) if m else None


# ---------------- following list ----------------

def _badge(cell, labels, testids=()):
    """Is one of these badges on this user cell (or profile header)? Read from
    the markup rather than inferred: a test id when X gives one, then an
    aria-label, then an element whose whole text IS the label. Whole text,
    because a bio that happens to contain the words is not the badge."""
    for tid in testids:
        if cell.find(attrs={"data-testid": tid}):
            return True
    for el in cell.find_all(attrs={"aria-label": True}):
        if str(el.get("aria-label", "")).strip().lower() in labels:
            return True
    for el in cell.find_all(["span", "div"]):
        if el.get_text(strip=True).lower() in labels:
            return True
    return False


def _parse_user_cells(soup, found):
    for cell in soup.find_all(attrs={"data-testid": "UserCell"}):
        handle = None
        for a in cell.find_all("a", href=True):
            h = a["href"]
            if re.fullmatch(r"/[A-Za-z0-9_]{1,15}", h):
                handle = h[1:]
                break
        if not handle or handle in found:
            continue
        name = ""
        for sp in cell.find_all("span"):
            t = sp.get_text(strip=True)
            if t and not t.startswith("@") and t.lower() not in ("follow", "following", "フォロー", "フォロー中", "フォローする"):
                name = t
                break
        bio_el = cell.find(attrs={"data-testid": "UserDescription"})
        bio = _text(bio_el) if bio_el else ""
        if not bio:
            # the last dir=auto block in the cell is the bio when it exists
            blocks = [b for b in cell.find_all("div", {"dir": "auto"}) if b.get_text(strip=True)]
            for b in reversed(blocks):
                t = _text(b)
                if (t and not t.startswith("@") and t != name and t.lower() not in ("follows you", "フォローされています")
                        and not t.startswith("クリックして") and not t.lower().startswith("click to")):
                    bio = t
                    break
        found[handle] = {"handle": handle, "name": name, "bio": bio[:400],
                         "follows_you": _badge(cell, FOLLOWS_YOU_LABELS, ("userFollowIndicator",)),
                         "private": _badge(cell, PRIVATE_LABELS, ("icon-lock",))}


def profile_counts(driver, config, handle):
    """(following, followers) as shown on the profile page, or (None, None)."""
    driver.get(f"https://x.com/{handle}")
    try:
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, f"a[href='/{handle}/following']")))
    except TimeoutException:
        return None, None
    def num(sel):
        try:
            t = driver.find_element(By.CSS_SELECTOR, sel).text
        except NoSuchElementException:
            return None
        m = re.search(r"([\d,.]+)\s*([KM万千]?)", t.replace(chr(10), " "))
        if not m:
            return None
        v = float(m.group(1).replace(",", ""))
        mult = {"K": 1e3, "M": 1e6, "万": 1e4, "千": 1e3}.get(m.group(2), 1)
        return int(v * mult)
    return num(f"a[href='/{handle}/following']"), num(f"a[href='/{handle}/verified_followers'], a[href='/{handle}/followers']")


def _at_bottom(driver):
    y = driver.execute_script("return window.pageYOffset + window.innerHeight")
    h = driver.execute_script("return document.body.scrollHeight")
    return y >= h - 5, h


def _scroll_following_page(driver, config, found, log, quick_until=0):
    """Scroll one loaded following page to its end, harvesting cells. X pages
    the list from the server and sometimes leaves a spinner hanging; when
    growth stops we nudge (scroll up and back) a few times, then give up and
    return False so the caller can reload and resume. quick_until: while
    fewer than this many are known, scroll faster (re-passing cells we have)."""
    stale = 0
    while True:
        _parse_user_cells(BeautifulSoup(driver.page_source, "html.parser"), found)
        before = len(found)
        driver.execute_script("window.scrollBy(0, Math.floor(window.innerHeight * (0.7 + Math.random()*0.5)));")
        _pause(config, 0.35 if len(found) < quick_until else 0.8)
        bottom, h = _at_bottom(driver)
        if not bottom:
            continue
        grew = False
        for _ in range(5):
            time.sleep(2.0)
            _parse_user_cells(BeautifulSoup(driver.page_source, "html.parser"), found)
            if driver.execute_script("return document.body.scrollHeight") > h or len(found) > before:
                grew = True
                break
        if grew:
            stale = 0
            continue
        stale += 1
        if stale > 3:
            return False
        # nudge: a person scrolls up a bit and comes back when a spinner hangs
        driver.execute_script("window.scrollBy(0, -Math.floor(window.innerHeight * 1.5));")
        time.sleep(random.uniform(2.0, 4.0))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(4.0, 7.0))
        _parse_user_cells(BeautifulSoup(driver.page_source, "html.parser"), found)
        if len(found) > before:
            stale = 0
            continue
        spinner = driver.find_elements(By.CSS_SELECTOR, "[role='progressbar']")
        if not spinner:
            return True   # a real end: no spinner, nothing more
        log(f"[x] following: spinner hanging at {len(found)}, nudge {stale}")


def _fetch_user_list(driver, config, handle, tab, expected, log=print):
    """One of the account's two user lists (`following` or `followers`),
    scrolled to its end at a human pace. X throttles the fetch mid-way (a
    spinner that never resolves); the page is then reloaded and re-scrolled
    quickly past what is already known, up to x_following_reloads times.
    Returns the dict of handles found, which is partial when it gave up."""
    url = f"https://x.com/{handle}/{tab}"
    found = {}
    reloads = 0
    while True:
        driver.get(url)
        try:
            WebDriverWait(driver, config.x_page_wait_seconds).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='UserCell']")))
        except TimeoutException:
            log(f"[x] {tab} page showed no user cells (login wall? wrong handle?)")
            return found or None
        time.sleep(random.uniform(1.0, 2.0))
        done = _scroll_following_page(driver, config, found, log, quick_until=len(found))
        log(f"[x] {tab}: {len(found)} so far" + (f" of {expected}" if expected else ""))
        if done or (expected and len(found) >= expected):
            return found
        reloads += 1
        if reloads > config.x_following_reloads:
            log(f"[x] {tab}: giving up after reloads; partial list saved")
            return found
        wait = random.uniform(config.x_following_reload_wait_min, config.x_following_reload_wait_max)
        log(f"[x] {tab}: reloading in {wait:.0f}s")
        time.sleep(wait)


def fetch_following(driver, config, handle, log=print):
    """Everyone the account follows. Saved to following.json with the fetch
    time and the count the profile claims. Each entry carries whether that
    account follows back and whether it is private, which is what stops an
    unfollow of a mutual or of an account that has since locked itself."""
    expected, followers = profile_counts(driver, config, handle)
    log(f"[x] profile says following {expected}, followers {followers}")
    time.sleep(random.uniform(1.5, 3.0))
    found = _fetch_user_list(driver, config, handle, "following", expected, log=log)
    if not found:
        return None
    data = {"handle": handle, "fetched": time.time(), "count": len(found), "expected": expected, "followers": followers,
            "complete": bool(expected) and len(found) >= expected * 0.97, "accounts": found}
    _save(_paths(config)["following"], data)
    log(f"[x] following: {len(found)} account(s) saved" + (f" (profile says {expected})" if expected else ""))
    return data


def fetch_followers(driver, config, handle, log=print):
    """Everyone who follows the account, the same way. followers.json is what
    `Curation` reads to know a mutual (never unfollowed) and who is owed a
    follow back. Handles already known keep their first-seen time, so the
    follow-back only ever fires on somebody genuinely new."""
    following, expected = profile_counts(driver, config, handle)
    log(f"[x] profile says followers {expected}, following {following}")
    time.sleep(random.uniform(1.5, 3.0))
    found = _fetch_user_list(driver, config, handle, "followers", expected, log=log)
    if not found:
        return None
    known = _load(_paths(config)["followers"], None) or {}
    old = known.get("accounts") or {}
    now = time.time()
    first_run = not old
    accounts = {}
    for h, acc in found.items():
        was = next((v for k, v in old.items() if k.lower() == h.lower()), None)
        accounts[h] = dict(acc, since=(was or {}).get("since", now), baseline=(was or {}).get("baseline", first_run))
    data = {"handle": handle, "fetched": now, "count": len(accounts), "expected": expected,
            "complete": bool(expected) and len(accounts) >= expected * 0.97, "accounts": accounts}
    _save(_paths(config)["followers"], data)
    log(f"[x] followers: {len(accounts)} account(s) saved" + (f" (profile says {expected})" if expected else "")
        + (" (baseline: nobody counts as new)" if first_run else ""))
    return data


def check_new_followers(driver, config, handle, log=print):
    """The cheap per-look version: read the top of the followers page, newest
    first, for a couple of screens, and record anybody not already known.
    Returns the new ones. The first run is a baseline and returns nothing --
    302 accounts that have followed the account for years are not news, and
    following all of them back in one afternoon is how an account is banned."""
    p = _paths(config)
    known = _load(p["followers"], None)
    now = time.time()
    if not known:
        # No list yet: build one from this page alone and count it a baseline.
        known = {"handle": handle, "fetched": 0, "count": 0, "expected": None, "complete": False, "accounts": {}}
        baseline = True
    else:
        baseline = False
    driver.get(f"https://x.com/{handle}/followers")
    try:
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='UserCell']")))
    except TimeoutException:
        log("[x] followers page showed no user cells")
        return []
    found = {}
    for _ in range(max(1, int(config.x_followers_scrolls))):
        _parse_user_cells(BeautifulSoup(driver.page_source, "html.parser"), found)
        driver.execute_script("window.scrollBy(0, Math.floor(window.innerHeight * 0.9));")
        _pause(config, 0.7)
    _parse_user_cells(BeautifulSoup(driver.page_source, "html.parser"), found)
    accs = known.setdefault("accounts", {})
    lower = {h.lower() for h in accs}
    fresh = []
    for h, acc in found.items():
        if h.lower() in lower:
            # a known follower, but the badges are newer than the stored ones
            key = next((k for k in accs if k.lower() == h.lower()), h)
            accs[key].update({"follows_you": acc.get("follows_you"), "private": acc.get("private")})
            continue
        accs[h] = dict(acc, since=now, baseline=baseline)
        if not baseline:
            fresh.append(accs[h])
    known["count"] = len(accs)
    known["fetched"] = now
    _save(p["followers"], known)
    if baseline:
        log(f"[x] followers: baseline of {len(accs)} from the top of the list; nobody counts as new")
    elif fresh:
        log("[x] new follower(s): " + ", ".join("@" + f["handle"] for f in fresh))
    return fresh


def load_followers(config):
    return _load(_paths(config)["followers"], None)


def follows_back(config):
    """The handles that follow the account, lowercased. Two sources, because
    either can be stale on its own: everybody on the followers list, and
    anybody on the following list whose cell carried the `follows you` badge
    when it was last read."""
    out = {h.lower() for h in ((load_followers(config) or {}).get("accounts") or {})}
    for h, acc in ((load_following(config) or {}).get("accounts") or {}).items():
        if isinstance(acc, dict) and acc.get("follows_you"):
            out.add(h.lower())
    return out


def private_accounts(config):
    """The handles known to be private (the padlock), from either list."""
    out = set()
    for data in (load_followers(config), load_following(config)):
        for h, acc in ((data or {}).get("accounts") or {}).items():
            if isinstance(acc, dict) and acc.get("private"):
                out.add(h.lower())
    return out


# ---------------- the Following timeline ----------------

def _click_following_tab(driver, config):
    """The home page opens on For You unless X remembers Following. Find the
    tab by label, click it if it is not selected, and confirm. Tabs can take
    a moment to render; try a few times, reload once."""
    for attempt in range(2):
        for _ in range(int(config.x_page_wait_seconds)):
            tabs = driver.find_elements(By.CSS_SELECTOR, "a[role='tab'], div[role='tab']")
            for t in tabs:
                # Every touch of t must be inside the guard. X re-renders the
                # header constantly, so the element found a moment ago may
                # already be gone -- and with an ad blocker stripping nodes it
                # re-renders more, which is why this only started failing when
                # uBlock went in. Reading the label was guarded; the
                # get_attribute and the click that followed were not, and that
                # killed the 02:11 look on 2026-08-20.
                try:
                    label = t.text.strip().split(chr(10))[0]
                    if label not in FOLLOWING_TAB_LABELS:
                        continue
                    if t.get_attribute("aria-selected") != "true":
                        t.click()
                        time.sleep(random.uniform(1.5, 3.0))
                    return True
                except WebDriverException:
                    continue      # it went stale: fall through and look again
            time.sleep(1.0)
        if attempt == 0:
            driver.get("https://x.com/home")
            time.sleep(random.uniform(3.0, 5.0))
    return False


def parse_articles(soup, found):
    for tweet in soup.find_all("article"):
        path = None
        time_element = None
        for candidate in tweet.find_all("time"):
            anchor = candidate.find_parent("a")
            href = anchor.get("href") if anchor else None
            if href and "/status/" in href:
                path, time_element = href, candidate
                break
        if not path or path in found:
            continue
        author = path.split("/")[1]
        # promoted posts carry an "Ad" / "広告" / "プロモーション" label; they are not the feed
        labels = {sp.get_text(strip=True) for sp in tweet.find_all("span")}
        if labels & {"Ad", "Promoted", "広告", "プロモーション"}:
            continue
        text_element = tweet.find("div", {"data-testid": "tweetText"})
        photo_divs = tweet.find_all("div", {"data-testid": "tweetPhoto"})
        media = len(photo_divs)
        # the picture itself, for the vision pass. pbs.twimg.com is public, so
        # these can be fetched later without the browser or the session. X
        # serves a small variant by default; ask for a bigger one.
        media_urls = []
        for div in photo_divs:
            img = div.find("img")
            src = img.get("src") if img else None
            if not src or "pbs.twimg.com" not in src:
                continue
            src = re.sub(r"([?&]name=)[^&]+", r"\1medium", src)
            if src not in media_urls:
                media_urls.append(src)
        video = bool(tweet.find("div", {"data-testid": "videoPlayer"})) or bool(tweet.find("video"))
        counts = _counts(tweet)
        ctx_el = tweet.find(attrs={"data-testid": "socialContext"})
        ctx = _text(ctx_el) if ctx_el else ""
        name = ""
        un = tweet.find(attrs={"data-testid": "User-Name"})
        if un:
            sp = un.find("span")
            if sp:
                name = sp.get_text(strip=True)
        quoted = ""
        # a quoted tweet renders a second tweetText inside the article
        texts = tweet.find_all("div", {"data-testid": "tweetText"})
        if len(texts) > 1:
            quoted = _text(texts[1])[:280]
        found[path] = {
            "status_path": path,
            "status_id": path.rsplit("/", 1)[-1],
            "url": f"https://x.com{path}",
            "author": author,
            "author_name": name,
            "context": ctx,          # "X reposted", "Xさんがリポスト", replies, etc.
            "is_repost": bool(ctx) and ("repost" in ctx.lower() or "リポスト" in ctx),
            "timestamp": time_element.get("datetime") if time_element else None,
            "text": _text(text_element) if text_element else "",
            "quoted": quoted,
            "media": media,
            "media_urls": media_urls,
            "video": video,
            "counts": counts,        # {replies, reposts, likes} the post has drawn, or None
        }


_N = r"(\d[\d,\.]*)\s*([KM万]?)"


def _num(s):
    m = re.search(_N, s or "")
    if not m:
        return 0
    return int(float(m.group(1).replace(",", "")) * {"K": 1e3, "M": 1e6, "万": 1e4}.get(m.group(2), 1))


def _counts(tweet):
    """What a post has drawn. The action bar's group carries one aria-label
    with everything ("3 replies, 5 reposts, 20 likes, 900 views" or the
    Japanese), and each button its own ("20 Likes. Like"); the group first,
    the buttons as the fallback. None when the article has no bar."""
    grp = tweet.find(attrs={"role": "group", "aria-label": True})
    out = {"replies": None, "reposts": None, "likes": None}
    if grp:
        lab = grp.get("aria-label") or ""
        for key, words in (("replies", r"repl|返信"), ("reposts", r"repost|リポスト"), ("likes", r"like|いいね")):
            m = re.search(_N + r"\s*(?:件の)?\s*(?:" + words + r")", lab, re.I)
            if m:
                out[key] = _num(m.group(0))
    for key, ids in (("replies", ("reply",)), ("reposts", ("retweet", "unretweet")), ("likes", ("like", "unlike"))):
        if out[key] is None:
            for tid in ids:
                el = tweet.find(attrs={"data-testid": tid, "aria-label": True})
                if el:
                    out[key] = _num(el.get("aria-label") or "")
                    break
    if all(v is None for v in out.values()):
        return None
    return {k: (v or 0) for k, v in out.items()}


def fetch_replies(driver, config, status_path, handle, limit=6, log=print):
    """The replies under one of her posts: the articles on its page that are
    not hers. Nothing recorded here; the look decides what they were to her."""
    try:
        driver.get(f"https://x.com{status_path}")
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article")))
    except TimeoutException:
        return []
    time.sleep(random.uniform(1.0, 2.0))
    found = {}
    parse_articles(BeautifulSoup(driver.page_source, "html.parser"), found)
    out = [it for it in found.values()
           if (it.get("author") or "").lower() != (handle or "").lower() and it.get("status_path") != status_path]
    return out[:limit]


def scroll_following(driver, config, scrolls=None, log=print):
    """One human-paced look at the Following timeline: land on home, switch
    tab, read a few screens. New posts are appended to feed.jsonl; returns
    (new_items, articles_seen)."""
    p = _paths(config)
    driver.get("https://x.com/home")
    if not _click_following_tab(driver, config):
        log("[x] could not find the Following tab")
        _write_status(config, ok=False, why="no following tab")
        return [], 0
    try:
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article")))
    except TimeoutException:
        _write_status(config, ok=False, why="no articles")
        return [], 0
    time.sleep(random.uniform(1.0, 2.5))
    n = scrolls or random.randint(config.x_feed_scrolls_min, config.x_feed_scrolls_max)
    found = {}
    parse_articles(BeautifulSoup(driver.page_source, "html.parser"), found)
    for _ in range(n):
        # a person scrolls a screen or so at a time and sometimes drifts back up
        driver.execute_script("window.scrollBy(0, Math.floor(window.innerHeight * (0.6 + Math.random()*0.7)));")
        _pause(config)
        if random.random() < 0.15:
            driver.execute_script("window.scrollBy(0, -Math.floor(window.innerHeight * 0.3));")
            _pause(config, 0.5)
        parse_articles(BeautifulSoup(driver.page_source, "html.parser"), found)
    seen = set(_load(p["seen"], []))
    fresh = [it for it in found.values() if it["status_path"] not in seen and it["timestamp"]]
    fresh.sort(key=lambda i: i["timestamp"])
    now = time.time()
    if fresh:
        with open(p["feed"], "a", encoding="utf-8") as fh:
            for it in fresh:
                it["seen_at"] = now
                fh.write(json.dumps(it, ensure_ascii=False) + "\n")
        seen.update(it["status_path"] for it in fresh)
        _save(p["seen"], sorted(seen)[-20000:])
    _write_status(config, ok=True, articles=len(found), new=len(fresh), scrolls=n)
    sessions = _load(p["sessions"], [])
    sessions.append({"at": now, "articles": len(found), "new": len(fresh), "scrolls": n})
    _save(p["sessions"], sessions[-500:])
    log(f"[x] following feed: {len(found)} article(s) on screen, {len(fresh)} new, {n} scroll(s)")
    return fresh, len(found)


# ---------------- likes: whose are they ----------------
#
# X keeps one Likes list per account, so it cannot tell his likes from hers.
# We can: every like she ever makes goes through log_action() before it is
# sent, so a like on the account that is not in her log is his. The Likes
# tab is read at the end of a look (one page, a scroll or two) and new
# entries are attributed and appended to likes.jsonl.

def log_action(config, kind, target, why="", dry_run=True, extra=None):
    rec = {"at": time.time(), "kind": kind, "target": target, "why": why, "dry_run": bool(dry_run)}
    if extra:
        rec.update(extra)
    with open(_paths(config)["actions"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def her_actions(config, kind=None):
    out = []
    try:
        with open(_paths(config)["actions"], "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if kind is None or r.get("kind") == kind:
                    out.append(r)
    except OSError:
        pass
    return out


def fetch_likes(driver, config, handle, scrolls=2, log=print):
    """New entries on the account's Likes tab, attributed: 'her' if the status
    is in her action log (a like she made, dry-run ones excluded), else 'him'.
    First run records the existing likes as his baseline."""
    p = _paths(config)
    driver.get(f"https://x.com/{handle}/likes")
    try:
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article")))
    except TimeoutException:
        log("[x] likes tab showed nothing")
        return []
    time.sleep(random.uniform(1.0, 2.0))
    found = {}
    parse_articles(BeautifulSoup(driver.page_source, "html.parser"), found)
    for _ in range(scrolls):
        driver.execute_script("window.scrollBy(0, Math.floor(window.innerHeight * (0.7 + Math.random()*0.5)));")
        _pause(config, 0.8)
        parse_articles(BeautifulSoup(driver.page_source, "html.parser"), found)
    seen = set(_load(p["likes_seen"], []))
    hers = {a.get("target") for a in her_actions(config, "like") if not a.get("dry_run")}
    first_run = not seen and not os.path.exists(p["likes"])
    now = time.time()
    fresh = []
    for it in found.values():
        if it["status_path"] in seen:
            continue
        it["liked_by"] = "her" if (it["status_path"] in hers or it["status_id"] in hers) else "him"
        it["seen_at"] = now
        it["baseline"] = first_run
        fresh.append(it)
    if fresh:
        with open(p["likes"], "a", encoding="utf-8") as fh:
            for it in fresh:
                fh.write(json.dumps(it, ensure_ascii=False) + "\n")
        seen.update(it["status_path"] for it in fresh)
        _save(p["likes_seen"], sorted(seen)[-20000:])
    log(f"[x] likes tab: {len(found)} on screen, {len(fresh)} new" + (" (baseline, all counted as his)" if first_run else ""))
    return fresh


def check_follow_changes(driver, config, handle, log=print):
    """Cheap per-look check of the account's follow list against following.json.
    The profile's following count is read; if it grew, the top of the
    following page (newest first) is scanned a couple of screens for handles
    not yet known. New handles not in her action log are his follows; a
    lower count is recorded as unfollows (whose, unknown until a full
    refetch). Appends to follow_changes.jsonl and adds new accounts to
    following.json (uncarded until x_analyze --cards runs)."""
    p = _paths(config)
    known = _load(p["following"], None)
    if not known:
        return []
    count, followers = profile_counts(driver, config, handle)
    if count is None:
        return []
    last = known.get("expected") or known.get("count", 0)
    changes = []
    now = time.time()
    if count > last:
        time.sleep(random.uniform(1.5, 3.0))
        driver.get(f"https://x.com/{handle}/following")
        try:
            WebDriverWait(driver, config.x_page_wait_seconds).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='UserCell']")))
        except TimeoutException:
            return []
        found = {}
        for _ in range(3):
            _parse_user_cells(BeautifulSoup(driver.page_source, "html.parser"), found)
            driver.execute_script("window.scrollBy(0, Math.floor(window.innerHeight * 0.9));")
            _pause(config, 0.7)
        _parse_user_cells(BeautifulSoup(driver.page_source, "html.parser"), found)
        hers = {str(a.get("target", "")).lstrip("@").lower() for a in her_actions(config, "follow") if not a.get("dry_run")}
        for h, acc in found.items():
            if h in known["accounts"]:
                continue
            by = "her" if h.lower() in hers else "him"
            known["accounts"][h] = dict(acc, added=now, added_by=by)
            changes.append({"at": now, "kind": "follow", "handle": h, "name": acc.get("name", ""), "bio": acc.get("bio", ""), "by": by})
    elif count < last:
        changes.append({"at": now, "kind": "unfollow_count", "delta": last - count, "by": "unknown"})
    if count != last:
        known["expected"] = count
        known["count"] = len(known["accounts"])
        known["followers"] = followers
        _save(p["following"], known)
    if changes:
        with open(p["follow_changes"], "a", encoding="utf-8") as fh:
            for c in changes:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")
        log(f"[x] follow changes: " + ", ".join(f"{c['kind']} @{c.get('handle', '')} ({c['by']})" if c["kind"] == "follow" else f"{c['delta']} unfollowed" for c in changes))
    return changes


def his_follows_since(config, since_ts, limit=20):
    out = []
    try:
        with open(_paths(config)["follow_changes"], "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    it = json.loads(line)
                except ValueError:
                    continue
                if it.get("kind") == "follow" and it.get("by") == "him" and it.get("at", 0) >= since_ts:
                    out.append(it)
    except OSError:
        pass
    return out[-limit:]


def his_likes_since(config, since_ts, limit=30):
    out = []
    try:
        with open(_paths(config)["likes"], "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    it = json.loads(line)
                except ValueError:
                    continue
                if it.get("liked_by") == "him" and not it.get("baseline") and it.get("seen_at", 0) >= since_ts:
                    out.append(it)
    except OSError:
        pass
    return out[-limit:]


def _write_status(config, **fields):
    fields["at"] = time.time()
    _save(_paths(config)["status"], fields)


# ---------------- pacing (the ban-safety knobs) ----------------

def sessions_today(config, day_start_ts):
    return [s for s in _load(_paths(config)["sessions"], []) if s["at"] >= day_start_ts]


def last_session_ts(config):
    s = _load(_paths(config)["sessions"], [])
    return s[-1]["at"] if s else 0


def may_open_session(config, day_start_ts):
    """True if pacing allows another look now: gap since the last one and
    the daily cap. The simulation adds its own gate (does she have her
    phone, is she bored) on top."""
    if time.time() - last_session_ts(config) < config.x_session_min_gap_minutes * 60:
        return False
    return len(sessions_today(config, day_start_ts)) < config.x_max_sessions_per_day


# ---------------- reading what was saved ----------------

def load_following(config):
    return _load(_paths(config)["following"], None)


def load_accounts(config):
    return _load(_paths(config)["accounts"], {})


def save_accounts(config, accounts):
    _save(_paths(config)["accounts"], accounts)


def feed_since(config, since_ts, limit=200):
    out = []
    try:
        with open(_paths(config)["feed"], "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    it = json.loads(line)
                except ValueError:
                    continue
                if it.get("seen_at", 0) >= since_ts:
                    out.append(it)
    except OSError:
        pass
    return out[-limit:]


def feed_all(config):
    return feed_since(config, 0, limit=100000)


# ---------------- her actions on the account ----------------
#
# Each of these is one thing a person does with a thumb: open the post and
# tap like, open the profile and tap follow / unfollow, type a short post.
# They are slow on purpose, they are only ever called by tomoe/curation.py
# after log_action() has written the intent (so attribution stays exact),
# and they return True only when the page confirmed the change.

def _type_slowly(element, text):
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(0.05, 0.18))
        if ch in "。、!?！？\n":
            time.sleep(random.uniform(0.3, 0.9))


def like_status(driver, config, status_path, log=print):
    """Open the post and tap like. Returns 'liked', 'already', or '' on failure."""
    driver.get(f"https://x.com{status_path}")
    try:
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article")))
    except TimeoutException:
        return ""
    _pause(config, 0.8)
    articles = driver.find_elements(By.CSS_SELECTOR, "article")
    for art in articles:
        try:
            if art.find_elements(By.CSS_SELECTOR, "[data-testid='unlike']"):
                return "already"
            btn = art.find_elements(By.CSS_SELECTOR, "[data-testid='like']")
            if not btn:
                continue
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn[0])
            time.sleep(random.uniform(0.6, 1.4))
            btn[0].click()
            time.sleep(random.uniform(1.0, 2.0))
            if art.find_elements(By.CSS_SELECTOR, "[data-testid='unlike']"):
                return "liked"
            return ""
        except WebDriverException as e:
            log(f"[x] like failed: {type(e).__name__}")
            return ""
    return ""


def repost_status(driver, config, status_path, log=print):
    """Open the post and repost it. Returns 'reposted', 'already', or ''."""
    driver.get(f"https://x.com{status_path}")
    try:
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article")))
    except TimeoutException:
        return ""
    _pause(config, 0.8)
    for art in driver.find_elements(By.CSS_SELECTOR, "article"):
        try:
            if art.find_elements(By.CSS_SELECTOR, "[data-testid='unretweet']"):
                return "already"
            btn = art.find_elements(By.CSS_SELECTOR, "[data-testid='retweet']")
            if not btn:
                continue
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn[0])
            time.sleep(random.uniform(0.6, 1.4))
            btn[0].click()
            time.sleep(random.uniform(0.8, 1.6))
            confirm = driver.find_elements(By.CSS_SELECTOR, "[data-testid='retweetConfirm']")
            if not confirm:
                return ""
            confirm[0].click()
            time.sleep(random.uniform(1.0, 2.0))
            if art.find_elements(By.CSS_SELECTOR, "[data-testid='unretweet']"):
                return "reposted"
            return ""
        except WebDriverException as e:
            log(f"[x] repost failed: {type(e).__name__}")
            return ""
    return ""


def profile_flags(driver, config):
    """(follows_you, private) for the profile page already open, or (None,
    None) when the page cannot be read. The name block is where X puts the
    padlock and the `follows you` pill; the test id is looked for across the
    whole column as well, because the layout moves."""
    try:
        col = driver.find_element(By.CSS_SELECTOR, "[data-testid='primaryColumn']")
        soup = BeautifulSoup(col.get_attribute("innerHTML") or "", "html.parser")
    except (NoSuchElementException, WebDriverException):
        return None, None
    name = soup.find(attrs={"data-testid": "UserName"})
    follows = bool(soup.find(attrs={"data-testid": "userFollowIndicator"}))
    if not follows and name is not None:
        follows = _badge(name, FOLLOWS_YOU_LABELS)
    private = bool(soup.find(attrs={"data-testid": "icon-lock"}))
    if not private and name is not None:
        private = _badge(name, PRIVATE_LABELS, ("icon-lock",))
    return follows, private


def set_follow(driver, config, handle, follow=True, log=print):
    """Open the profile and tap follow (or unfollow + confirm). Returns
    'followed' / 'unfollowed' / 'already' / 'refused: ...' / ''.

    The last guard against an unfollow she may not make is here rather than
    only at the decision, because the decision was made off a list that may be
    days old: the profile in front of us is what says whether this account
    follows her back or has since gone private, and either one refuses."""
    driver.get(f"https://x.com/{handle}")
    try:
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='UserName']")))
    except TimeoutException:
        return ""
    _pause(config, 0.8)
    if not follow:
        mutual, private = profile_flags(driver, config)
        if mutual:
            log(f"[x] unfollow @{handle} refused: this account follows her")
            return "refused: it follows her"
        if private:
            log(f"[x] unfollow @{handle} refused: this account is private now")
            return "refused: it is private now"
    try:
        unfollow_btn = driver.find_elements(By.CSS_SELECTOR, "[data-testid$='-unfollow']")
        follow_btn = driver.find_elements(By.CSS_SELECTOR, "[data-testid$='-follow']")
        if follow:
            if unfollow_btn:
                return "already"
            if not follow_btn:
                return ""
            follow_btn[0].click()
            time.sleep(random.uniform(1.5, 2.5))
            return "followed" if driver.find_elements(By.CSS_SELECTOR, "[data-testid$='-unfollow']") else ""
        else:
            if not unfollow_btn:
                return "already" if follow_btn else ""
            unfollow_btn[0].click()
            time.sleep(random.uniform(0.8, 1.6))
            conf = driver.find_elements(By.CSS_SELECTOR, "[data-testid='confirmationSheetConfirm']")
            if conf:
                conf[0].click()
            time.sleep(random.uniform(1.5, 2.5))
            return "unfollowed" if driver.find_elements(By.CSS_SELECTOR, "[data-testid$='-follow']") else ""
    except WebDriverException as e:
        log(f"[x] follow action failed: {type(e).__name__}")
        return ""


def post_tweet(driver, config, text, log=print):
    """Type a post the way a person does and send it. Returns True when the
    composer closed without an error."""
    driver.get("https://x.com/compose/post")
    try:
        box = WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='tweetTextarea_0']")))
    except TimeoutException:
        return False
    _pause(config, 0.6)
    try:
        box.click()
        time.sleep(random.uniform(0.5, 1.2))
        _type_slowly(box, text)
        time.sleep(random.uniform(1.5, 4.0))
        btn = driver.find_elements(By.CSS_SELECTOR, "[data-testid='tweetButton']")
        if not btn or not btn[0].is_enabled():
            return False
        btn[0].click()
        time.sleep(random.uniform(2.5, 4.0))
        # Success is the text having left the composer, not the composer being
        # gone: /compose/post carries TWO tweetTextarea_0 elements (the modal
        # and the inline one on the page behind it), so "no textarea anywhere"
        # was false even on a clean post. That reported every successful post
        # as a failure, which in turn would leave curation retrying a post that
        # had already gone out (2026-08-20: the test post landed and returned
        # False).
        # A toast is not an error. X raises one on success too -- the first
        # attempt at this check read "ポストを送信しました。" (your post was
        # sent) and called it a rejection. Log it and judge by the box.
        toast = driver.find_elements(By.CSS_SELECTOR, "[data-testid='toast']")
        if toast:
            try:
                log(f"[x] X says: {(toast[0].text or '').splitlines()[0][:60]}")
            except WebDriverException:
                pass
        head = text.strip()[:12]
        for ta in driver.find_elements(By.CSS_SELECTOR, "[data-testid='tweetTextarea_0']"):
            try:
                if head and head in (ta.text or ""):
                    return False      # still sitting in the box: it did not send
            except WebDriverException:
                continue
        return True
    except WebDriverException as e:
        log(f"[x] post failed: {type(e).__name__}")
        return False


def reply_to_status(driver, config, status_path, text, log=print):
    """Answer a post: open it, type into the reply box under it, send.
    The same shape as post_tweet -- success is the text having left the box,
    and X raises a toast on a good send as well as a bad one, so the toast is
    logged and the box is what decides."""
    driver.get(f"https://x.com{status_path}")
    try:
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='tweetTextarea_0']")))
    except TimeoutException:
        return False
    _pause(config, 0.6)
    try:
        box = driver.find_elements(By.CSS_SELECTOR, "[data-testid='tweetTextarea_0']")[0]
        box.click()
        time.sleep(random.uniform(0.5, 1.2))
        _type_slowly(box, text)
        time.sleep(random.uniform(1.5, 4.0))
        btn = (driver.find_elements(By.CSS_SELECTOR, "[data-testid='tweetButtonInline']")
               or driver.find_elements(By.CSS_SELECTOR, "[data-testid='tweetButton']"))
        if not btn or not btn[0].is_enabled():
            return False
        btn[0].click()
        time.sleep(random.uniform(2.5, 4.0))
        toast = driver.find_elements(By.CSS_SELECTOR, "[data-testid='toast']")
        if toast:
            try:
                log(f"[x] X says: {(toast[0].text or '').splitlines()[0][:60]}")
            except WebDriverException:
                pass
        head = text.strip()[:12]
        for ta in driver.find_elements(By.CSS_SELECTOR, "[data-testid='tweetTextarea_0']"):
            try:
                if head and head in (ta.text or ""):
                    return False      # still sitting in the box: it did not send
            except WebDriverException:
                continue
        return True
    except WebDriverException as e:
        log(f"[x] reply failed: {type(e).__name__}")
        return False


def her_posts(config, limit=20):
    return [a for a in her_actions(config, "post") if not a.get("dry_run")][-limit:]


def close_orphans(config, log=print):
    """Chrome windows left on HER profile by a look that was killed mid-way
    (a restart during a scroll). Matched on the --user-data-dir argument
    only, so another program's profile is never touched. Windows only."""
    import subprocess
    prof = os.path.normpath(config.x_profile_dir).lower()
    killed = 0
    try:
        out = subprocess.run(["wmic", "process", "where", "name='chrome.exe'", "get", "ProcessId,CommandLine", "/format:csv"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", timeout=20).stdout
    except Exception as e:
        log(f"[x] orphan check failed: {type(e).__name__}")
        return 0
    for line in out.splitlines():
        if "user-data-dir" not in line or "--type=" in line:
            continue
        m = re.search(r"user-data-dir=\"?([^\" ]+)", line)
        if not m or os.path.normpath(m.group(1)).lower() != prof:
            continue
        pid = line.rstrip().rsplit(",", 1)[-1].strip()
        if pid.isdigit():
            subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            killed += 1
    if killed:
        log(f"[x] closed {killed} leftover Chrome window(s) on her profile")
    return killed


# ---------------- what Japan is on about, and what she goes looking for ----------------

def fetch_user_posts(driver, config, handle, scrolls=1, log=print):
    """One account's own timeline, a screen or two, nothing recorded on her
    side (tomoe/scenery.py harvests from a watchlist this way)."""
    try:
        driver.get(f"https://x.com/{handle}")
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article")))
    except TimeoutException:
        log(f"[x] @{handle}: nothing rendered")
        return []
    time.sleep(random.uniform(1.0, 2.0))
    found = {}
    parse_articles(BeautifulSoup(driver.page_source, "html.parser"), found)
    for _ in range(scrolls):
        driver.execute_script("window.scrollBy(0, Math.floor(window.innerHeight * (0.6 + Math.random()*0.7)));")
        _pause(config)
        parse_articles(BeautifulSoup(driver.page_source, "html.parser"), found)
    out = [it for it in found.values() if it["timestamp"] and (it.get("author") or "").lower() == handle.lower()]
    out.sort(key=lambda i: i["timestamp"], reverse=True)
    return out


def fetch_trends(driver, config, log=print):
    """The Trending tab, one page: the trend names in order. Written to
    data/x/trends.json for tools/zeitgeist.py, which reads it beside the
    public feeds. X's trends need a login, which the look session has."""
    p = _paths(config)
    path = os.path.join(config.x_data_dir, "trends.json")
    try:
        driver.get("https://x.com/explore/tabs/trending")
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='trend']")))
    except TimeoutException:
        log("[x] trends: nothing rendered")
        return []
    time.sleep(random.uniform(1.0, 2.0))
    soup = BeautifulSoup(driver.page_source, "html.parser")
    names = []
    for cell in soup.find_all(attrs={"data-testid": "trend"}):
        spans = [sp.get_text(strip=True) for sp in cell.find_all("span")]
        # the cell reads "N · Trending in Japan / #name / 12.3K posts": the
        # name is the longest span that is not a count or a category line
        cands = [t for t in spans if t and not re.search(r"(posts|件のポスト|Trending|トレンド|·)", t) and not re.fullmatch(r"[\d,.]+[KM万]?", t)]
        if cands:
            name = max(cands, key=len)
            if name not in names:
                names.append(name)
    _save(path, {"at": time.time(), "trends": names[:30]})
    log(f"[x] trends: {len(names)} on the tab" + (f" ({', '.join(names[:5])}...)" if names else ""))
    return names


def search_posts(driver, config, query, scrolls=2, log=print, record=True):
    """One search she typed, Latest tab, a couple of screens. Items carry
    `via: search` and the query, are appended to feed.jsonl like the
    timeline's, and the read labels them so the model knows she went
    looking. This is where accounts of her own come from: the Following
    tab only ever shows her his."""
    from urllib.parse import quote
    p = _paths(config)
    try:
        driver.get(f"https://x.com/search?q={quote(query)}&src=typed_query&f=live")
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article")))
    except TimeoutException:
        log(f"[x] search '{query}': nothing rendered")
        return []
    time.sleep(random.uniform(1.0, 2.5))
    found = {}
    parse_articles(BeautifulSoup(driver.page_source, "html.parser"), found)
    for _ in range(scrolls):
        driver.execute_script("window.scrollBy(0, Math.floor(window.innerHeight * (0.6 + Math.random()*0.7)));")
        _pause(config)
        parse_articles(BeautifulSoup(driver.page_source, "html.parser"), found)
    if not record:
        # machinery, not her: nothing of this reaches feed.jsonl or seen.json,
        # so it can never surface in her read as something she looked for
        out = [it for it in found.values() if it["timestamp"]]
        out.sort(key=lambda i: i["timestamp"])
        log(f"[x] quiet search '{query}': {len(out)} post(s)")
        return out
    seen = set(_load(p["seen"], []))
    fresh = [it for it in found.values() if it["status_path"] not in seen and it["timestamp"]]
    fresh.sort(key=lambda i: i["timestamp"])
    now = time.time()
    for it in fresh:
        it["seen_at"] = now
        it["via"] = "search"
        it["query"] = query
    if fresh:
        with open(p["feed"], "a", encoding="utf-8") as fh:
            for it in fresh:
                fh.write(json.dumps(it, ensure_ascii=False) + "\n")
        seen.update(it["status_path"] for it in fresh)
        _save(p["seen"], sorted(seen)[-20000:])
    log(f"[x] she searched '{query}': {len(found)} post(s), {len(fresh)} new")
    return fresh
