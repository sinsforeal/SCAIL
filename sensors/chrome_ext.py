import os
import json

# uBlock Origin in the scraping browsers, so ads are never read as content.
# Three things are needed together on Chrome 138, and none of them work alone:
#
# 1. --load-extension is ignored on its own. Chrome 137 added a feature switch
#    that disables it for automated sessions, so it has to be turned back off
#    with --disable-features=DisableLoadExtensionCommandLineSwitch.
# 2. --disable-extensions, which both drivers used to pass, cancels the load.
# 3. An unpacked extension stays present but DISABLED until the profile has
#    developer mode on. That is a per-profile preference, not a flag, and
#    Chrome rewrites Preferences when it first creates a profile -- so it has
#    to be written while Chrome is closed, into a profile that already exists.
#    A brand new profile therefore needs one throwaway launch first; both live
#    profiles (F:\Chrome_Profiles\SCAIL_tomoe and SCAIL_mal) are long
#    established.
#
# Verified on Chrome 138.0.7204.169 with uBlock Origin 1.73.0: without the
# switch the extension list is empty, with the switch but no developer mode it
# is present and disabled, with both it is enabled.

FLAG = "--disable-features=DisableLoadExtensionCommandLineSwitch"


def _enable_developer_mode(profile_dir):
    """Set extensions.ui.developer_mode in the profile. No-op if the profile
    has not been created yet (Chrome would overwrite it on first run)."""
    path = os.path.join(profile_dir, "Default", "Preferences")
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as fh:
            prefs = json.load(fh)
        if prefs.get("extensions", {}).get("ui", {}).get("developer_mode") is True:
            return True
        prefs.setdefault("extensions", {}).setdefault("ui", {})["developer_mode"] = True
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(prefs, fh)
        return True
    except (OSError, ValueError):
        return False


def apply(options, ext_dir, profile_dir, log=None):
    """Add the extension to a ChromeOptions. Returns True if it was applied.
    Call before the driver is created, while Chrome is not holding the
    profile. Any failure is non-fatal: the scrape just runs without it."""
    if not ext_dir:
        return False
    ext_dir = os.path.abspath(ext_dir)
    if not os.path.isdir(ext_dir) or not os.path.exists(os.path.join(ext_dir, "manifest.json")):
        if log:
            log(f"[chrome] extension not found at {ext_dir}; running without it")
        return False
    dev = _enable_developer_mode(profile_dir) if profile_dir else False
    options.add_argument(FLAG)
    options.add_argument(f"--load-extension={ext_dir}")
    if log and not dev:
        log("[chrome] extension loaded but the profile has no developer mode yet; "
            "it stays disabled until the next launch")
    return True

def settle(driver, log=None):
    """Close anything the browser opened for itself and leave exactly one tab.

    The first launch after an extension becomes enabled opens its own pages --
    uBlock showed three tabs on that launch and one on every launch after. The
    scraper then holds element references from one window while the driver's
    context is another, and dies three seconds in with
    StaleElementReferenceException. That is what killed the 02:11 look on
    2026-08-20. Cheap to call every time; a no-op when there is one tab."""
    try:
        handles = driver.window_handles
        if len(handles) <= 1:
            return 0
        keep = handles[0]
        closed = 0
        for h in handles[1:]:
            try:
                driver.switch_to.window(h)
                driver.close()
                closed += 1
            except Exception:
                pass
        driver.switch_to.window(keep)
        if log and closed:
            log(f"[chrome] closed {closed} tab(s) the browser opened for itself")
        return closed
    except Exception:
        return 0
