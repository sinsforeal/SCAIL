"""One episode log for the three gates that keep one.

The withholding, the approach and the attachment each keep a list of the
times they fired (kv `withholding_log`, `approaches`, `attachment_log`) and
each carried the same three helpers over it. One mixin: `LOG_KEY` names the
list, `_log()` reads it, `_today()` counts today's entries, `_last_ts()` is
the newest timestamp, 0 when the list is empty. The store and the clock are
the host's.

(Her past as cards is `sim/cards.py`, not this.)
"""


class EpisodeLog:
    LOG_KEY = ""

    def _log(self):
        return self.store.get(self.LOG_KEY, [])

    def _today(self):
        d = self.clock.date_str()
        return len([a for a in self._log() if a.get("date") == d])

    def _last_ts(self):
        return max([float(a.get("ts", 0)) for a in self._log()] or [0])
