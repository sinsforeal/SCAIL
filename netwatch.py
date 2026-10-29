import re
import time
import threading

import logger

# A failure detail is usually the text of a requests exception, and that text
# quotes the URL it failed on. Two of the URLs in this project carry a secret
# in the query string -- the hub token, and anything else added later that
# authenticates that way -- so every detail passing through here is redacted
# before it is written. The truncation below happened to cut just short of the
# token; that was luck, and luck is not a control.
_SECRET_IN_URL = re.compile(r"((?:key|token|api_key|access_token)=)[^&\s'\")]+", re.I)


def redact(s):
    return _SECRET_IN_URL.sub(r"\1<redacted>", str(s or ""))

# Whether this machine can reach the outside world, and one place to say so.
#
# On 2026-08-20 the machine lost DNS for 66 minutes (03:30-04:36). What that
# looked like in the log was ~90 identical "poll error" lines, a director call
# burning all three LLM retries against a dead network, and a bubble of hers
# that failed to send and was recorded as delivered anyway. Nothing said
# "the network is down", so nothing read as an outage -- it read as noise.
#
# So: every network failure reports here instead of logging its own line.
# The first one says the network went, once. Repeats are counted, not printed.
# Recovery says how long it lasted and how many errors were swallowed. While
# it is down the loop skips work that can only fail, and her outbound bubbles
# wait instead of being thrown away.


class NetWatch:
    def __init__(self, config=None):
        c = getattr(config, "network", None) if config else None
        self.down_after = getattr(c, "down_after_failures", 3)
        self.recheck_seconds = getattr(c, "recheck_seconds", 30)
        self._lock = threading.Lock()
        self._fails = 0
        self._down_since = 0.0
        self._suppressed = 0
        self._last_source = ""

    # ---------- reporting ----------

    def fail(self, source, detail=""):
        """A network call failed. Logs once on the way down, counts after."""
        detail = redact(detail)
        with self._lock:
            self._fails += 1
            self._last_source = source
            if self._down_since:
                self._suppressed += 1
                return
            if self._fails >= self.down_after:
                self._down_since = time.time()
                self._suppressed = 0
                logger.log(f"[network] down: {source} unreachable"
                           + (f" ({detail[:80]})" if detail else "")
                           + ". Suppressing repeats until it is back.")
            elif self._fails == 1 and detail:
                # one-off blips still deserve a line, just not a hundred
                logger.log(f"[network] {source} hiccup: {detail[:80]}")

    def ok(self, source=""):
        """A network call succeeded."""
        with self._lock:
            if self._down_since:
                mins = (time.time() - self._down_since) / 60.0
                logger.log(f"[network] back after {mins:.0f} min"
                           f" ({self._suppressed} error(s) suppressed)")
                self._down_since = 0.0
                self._suppressed = 0
            self._fails = 0

    # ---------- asking ----------

    def offline(self):
        with self._lock:
            return bool(self._down_since)

    def down_minutes(self):
        with self._lock:
            return (time.time() - self._down_since) / 60.0 if self._down_since else 0.0

    def status(self):
        with self._lock:
            if not self._down_since:
                return "online"
            mins = (time.time() - self._down_since) / 60.0
            return (f"offline for {mins:.0f} min ({self._last_source}), "
                    f"{self._suppressed} error(s) suppressed")


# One shared instance: sensors, the LLM client and the loop all report to it.
WATCH = NetWatch()


def configure(config):
    global WATCH
    WATCH = NetWatch(config)
    return WATCH
