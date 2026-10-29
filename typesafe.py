# -*- coding: utf-8 -*-
"""System One (typesafe.ai): narrow typed judgements for code's half of the split.

The names, settled 2026-09-17: **System One** is the service, **typesafe** is
this client (module, config section, `[typesafe]` log tag, `TypeSafe`), and
**Jev** is the model it calls (`jev-latest`, answers as `jev-1.13.0`). It is
NOT one of her stage roles and never a voice role: `typesafe` is not a key in
`models`, `jev-latest` is not a role model, and the stage's model pickers do
not offer it.

`docs/system-one.md` is the assessment; this is the client it describes.
Nothing here generates text and nothing here decides what she does. It asks a
batch of typed questions about one `state` and returns probabilities and
confidences, so that code can threshold them. A character whose config leaves
`typesafe.enabled` false pays nothing and takes exactly the path it took
before.

The key is read from `typesafe.key_file` (`secerts/typesafe.txt`), the way the
OpenRouter key is read from `api.openrouter_key_file`, so no key ever sits in a
tracked config.

A failure returns None and the caller keeps its own gate: a classifier this
cheap is not a paid answer worth replaying, so nothing is written to
`missed_calls` (`docs/system-one.md` section 4). Every call logs what it decided
and how long it took; the caller logs which side decided.
"""

import json
import os
import time
import urllib.request

import logger
import netwatch

URL = "https://api.typesafe.ai/v1/systemone"


class TypeSafe:
    """One client for one character. Built for every character; only a bundle
    that turns `typesafe` on spends anything."""

    def __init__(self, config, clock=None):
        self.config = config
        self.clock = clock
        c = getattr(config, "typesafe", None)
        self.enabled = bool(getattr(c, "enabled", False))
        self.model = str(getattr(c, "model", "") or "jev-latest")
        self.key_file = str(getattr(c, "key_file", "") or "secerts/typesafe.txt")
        self.root = os.path.dirname(os.path.abspath(__file__))
        self.timeout = _float(getattr(c, "timeout_seconds", 20), 20.0)
        self.floor = _float(getattr(c, "floor", 0.6), 0.6)
        self._key = None
        self.calls = 0
        self.failures = 0
        self.last_error = ""
        self.last_ms = 0

    # ---------------- switches ----------------

    def use(self, name):
        """The named use's threshold, or None when the use is off.

        Off is three things at once: `typesafe.enabled`, the use's own
        `uses.<name>.enabled`, and a readable key. A caller asks this before it
        builds any question, so an off switch costs a dictionary lookup.

        The uses are read from the merged config tree rather than from the
        section object: `uses` is a map of maps, and a section hands back its
        nested maps as sections, so `isinstance(uses, dict)` was false and every
        use read as off while the config said on."""
        if not self.enabled:
            return None
        raw = getattr(self.config, "raw", None)
        ts = raw.get("typesafe") if isinstance(raw, dict) else None
        uses = ts.get("uses") if isinstance(ts, dict) else None
        u = uses.get(name) if isinstance(uses, dict) else None
        if not isinstance(u, dict) or not u.get("enabled"):
            return None
        # Keep action-specific floors beside the use's main floor. The caller
        # owns what it does with each answer; this client only exposes the
        # configured policy and normalizes the shared threshold.
        policy = dict(u)
        policy["threshold"] = _float(u.get("threshold", self.floor), self.floor)
        return policy

    def key(self):
        if self._key is None:
            path = self.key_file if os.path.isabs(self.key_file) else os.path.join(self.root, self.key_file)
            with open(path, encoding="utf-8") as f:
                self._key = f.read().strip()
        return self._key

    def ready(self, name):
        """True when the named use may call. A missing key is logged once, by
        the exception's own name, and never raises into a tick."""
        if self.use(name) is None:
            return False
        try:
            self.key()
        except Exception as e:
            if not self.last_error:
                self.last_error = f"{type(e).__name__}"
                logger.log(f"[typesafe] off: key not readable ({self.last_error}: {self.key_file})")
            return False
        return True

    # ---------------- the one call ----------------

    def ask(self, name, state, questions):
        """One batched call. Returns the answers map, or None on any failure so
        the caller keeps the gate it already had."""
        try:
            body = json.dumps({"state": state, "model": self.model, "questions": questions},
                              ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(URL, data=body, headers={
                "Authorization": "Bearer " + self.key(),
                "Content-Type": "application/json"})
        except Exception as e:
            self.failures += 1
            self.last_error = netwatch.redact(f"{type(e).__name__}: {e}")
            logger.log(f"[typesafe] {name}: not called ({type(e).__name__}); the gate it replaced decides")
            return None
        t0 = time.time()
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            self.failures += 1
            self.last_error = netwatch.redact(f"{type(e).__name__}: {e}")
            logger.log(f"[typesafe] {name}: call failed ({type(e).__name__}); the gate it replaced decides")
            return None
        self.last_ms = (time.time() - t0) * 1000
        answers = data.get("answers") if isinstance(data, dict) else None
        usage = data.get("usage") if isinstance(data, dict) else {}
        logger.log(f"[typesafe] {name}: {len(answers or {})} answer(s) in {self.last_ms:.0f}ms "
                   f"({data.get('model', '')}, in={usage.get('input_tokens')} out={usage.get('output_tokens')})")
        return answers if isinstance(answers, dict) else None

    # ---------------- reading an answer ----------------

    @staticmethod
    def yes(answers, qid):
        """A noul answer as a probability, or None when the question is absent.
        The caller decides what None means; a noul carries no confidence of its
        own, which is why a choice is used wherever a threshold has to travel
        with the answer."""
        a = (answers or {}).get(qid)
        if not isinstance(a, dict) or a.get("type") != "noul":
            return None
        try:
            return float(a.get("noul"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def choice(answers, qid):
        """(chosen option, confidence) for a choice answer, or (None, 0.0)."""
        a = (answers or {}).get(qid)
        if not isinstance(a, dict) or a.get("type") != "choice":
            return None, 0.0
        try:
            conf = float(a.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        return a.get("choice"), conf

    @staticmethod
    def score(answers, qid):
        """(level, confidence) for a score answer, or (None, 0.0).

        A score carries an ordinal level (the API returns a float, e.g. 1.04,
        so the caller rounds) and the same confidence a choice does. Nothing
        read one before the gauge appraisal; `yes` reads a noul and `choice`
        reads a choice."""
        a = (answers or {}).get(qid)
        if not isinstance(a, dict) or a.get("type") != "score":
            return None, 0.0
        try:
            conf = float(a.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        try:
            return float(a.get("score")), conf
        except (TypeError, ValueError):
            return None, 0.0

    def status(self):
        return (f"typesafe {'on' if self.enabled else 'off'} ({self.model}) | "
                f"calls {self.calls} | failed {self.failures} | "
                f"last {self.last_ms:.0f}ms" + (f" | {self.last_error}" if self.last_error else ""))


def _float(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default
