# -*- coding: utf-8 -*-
"""Delete one of her own posts from X, by the text it starts with.

Her posts are hers, and the bot never deletes on its own -- this is an operator
tool, run by hand, for the case where a post asserts something the world has
since been corrected on. It is deliberately not wired into `curation.py`: a
mechanism that can retract her own words is a different thing from one that can
write them, and only the second was ever asked for.

    python tools/x_delete.py --starts "寝ようと思ったのに" [--yes]

Without --yes it finds the post, prints it, and stops.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import Config
from sensors import x_monitor


def find_and_delete(driver, config, starts, do_it, log=print):
    handle = x_monitor.logged_in_handle(driver, config)
    if not handle:
        log("[x] not logged in on this profile")
        return False
    log(f"[x] @{handle}")
    driver.get(f"https://x.com/{handle}")
    try:
        WebDriverWait(driver, config.x_page_wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']")))
    except TimeoutException:
        log("[x] the timeline did not load")
        return False
    time.sleep(2.0)

    target = None
    for art in driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']"):
        try:
            body = art.find_elements(By.CSS_SELECTOR, "[data-testid='tweetText']")
            txt = (body[0].text if body else "") or ""
        except WebDriverException:
            continue
        if starts and starts in txt:
            target = art
            log(f"[x] found: {txt.splitlines()[0][:70]}")
            break

    if target is None:
        log(f"[x] no post of hers on the first page contains {starts!r}")
        return False
    if not do_it:
        log("[x] --yes not given; nothing deleted")
        return False

    try:
        caret = target.find_element(By.CSS_SELECTOR, "[data-testid='caret']")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
        time.sleep(0.8)
        caret.click()
        # the menu renders late: at 1.2s it is present but empty, which read as
        # "no delete item" on a post that had one
        item = None
        for _ in range(12):
            time.sleep(0.5)
            for el in driver.find_elements(By.CSS_SELECTOR, "[role='menuitem']"):
                t = (el.text or "")
                if "削除" in t or "Delete" in t:
                    item = el
                    break
            if item is not None:
                break
        if item is None:
            log("[x] no delete item in the menu (is this her post?)")
            return False
        item.click()
        time.sleep(1.2)
        for el in driver.find_elements(By.CSS_SELECTOR, "[data-testid='confirmationSheetConfirm']"):
            el.click()
            break
        else:
            log("[x] no confirmation button")
            return False
        time.sleep(2.5)
        toast = driver.find_elements(By.CSS_SELECTOR, "[data-testid='toast']")
        if toast:
            log(f"[x] X says: {(toast[0].text or '').splitlines()[0][:60]}")
        return True
    except WebDriverException as e:
        log(f"[x] delete failed: {type(e).__name__}: {e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--starts", required=True, help="text the post contains")
    ap.add_argument("--yes", action="store_true", help="actually delete it")
    args = ap.parse_args()

    cfg = Config("config.json").sensor_view
    x_monitor.close_orphans(cfg)
    driver = x_monitor.open_driver(cfg)
    try:
        ok = find_and_delete(driver, cfg, args.starts, args.yes)
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        x_monitor.close_orphans(cfg)
    print("deleted" if ok else "not deleted")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
