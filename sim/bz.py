"""B-zombie experiment, S arm: the six starting changes (config section `bz`).

Every change has its own switch and all are off by default. One object per
persona (`persona.bz`), wired by the app. Per reply it builds `self.last`, the
dict the trace reads:

    order            the in-character order text ("" when bz.order is off)
    order_called     whether the order call was made
    constant_flagged prompt lines byte-identical across the last N persona calls
    constant_cut     the subset actually dropped (bz.cut_constant on)
    addressed        True / False / None (None = nothing of his to answer)
    echo             {"hers": n, "his": n, "threshold": x}
    trend            list of trend words, e.g. ["loneliness rising"]
    ungrounded       reply claims matching no input
    switches         the switch states used for this reply

It is also stored as json in the save's kv under `bz_last`.
"""
import json
import re
from collections import deque
from pathlib import Path

import logger

_ROOT = Path(__file__).resolve().parent.parent
SWITCHES = ("order", "cut_constant", "answer_first", "echo", "trend", "reality")
LABELS = ("observed", "inferred", "imagined")


def _txt(x):
    if isinstance(x, dict):
        return str(x.get("text", "") or "")
    try:
        return str(x["text"] or "")
    except Exception:
        return str(x or "")


def _bigrams(s):
    s = re.sub(r"\s+", "", s.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def label_row(text, kind):
    """Prefix a row text with its reality label. kind in LABELS."""
    kind = kind if kind in LABELS else "imagined"
    return f"[{kind}] {text}"


def row_label(text):
    """The label a row carries, or None."""
    m = re.match(r"^\[(observed|inferred|imagined)\]\s*", str(text or ""))
    return m.group(1) if m else None


def render_label(text, ja=False):
    """How recall shows a labelled row: the label as a plain phrase."""
    m = re.match(r"^\[(observed|inferred|imagined)\]\s*(.*)$", str(text or ""), re.S)
    if not m:
        return str(text or "")
    words = {"observed": ("(seen)", "（見たこと）"), "inferred": ("(guess from what she saw)", "（見たことからの推測）"),
             "imagined": ("(imagined, not so)", "（想像。事実ではない）")}[m.group(1)]
    return f"{words[1] if ja else words[0]} {m.group(2)}"


def reality_on(config):
    """True when config.bz.reality is on. The writers and renderers of the
    wonder / foresight / spiral rows call this; off = they behave as before."""
    try:
        return bool(getattr(getattr(config, "bz", None), "reality", False))
    except Exception:
        return False


def label_phrase(kind, ja=False):
    """The bare phrase for a label, e.g. '(guess from what she saw)'."""
    return render_label(f"[{kind}] ", ja).strip()


def show(text, config=None, ja=None):
    """Recall / diary renderer for any text that may carry a label prefix.
    No prefix = returned unchanged, so rows from before the switch read as before.
    `config` (or `ja`) picks the language of the phrase."""
    t = str(text if text is not None else "")
    if not row_label(t):
        return t
    if ja is None:
        try:
            from sim.lang import reads_ja
            ja = bool(config is not None and reads_ja(config))
        except Exception:
            ja = False
    return render_label(t, ja)


class Bz:
    def __init__(self, config, llm, store, state, embed=None, log=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.state = state
        self.embed = embed
        self.log = log or logger.log
        self.last = {}
        self._snapped = False
        self._snaps = deque(maxlen=max(2, int(self._c("constant_window", 8))))
        self._hist = deque(maxlen=max(3, int(self._c("trend_history", 12))))

    # ---- config ----
    def _c(self, name, default=None):
        sec = getattr(self.config, "bz", None)
        v = getattr(sec, name, None) if sec is not None else None
        return default if v is None else v

    def on(self, name):
        return bool(self._c(name, False))

    def any_on(self):
        return any(self.on(s) for s in SWITCHES)

    def ja(self):
        return str(getattr(self.config.character, "writes_to_him", "english")).lower().startswith("ja")

    # ---- per reply ----
    def begin(self):
        self._snapped = False
        self.last = {"order": "", "order_called": False, "constant_flagged": [], "constant_cut": [],
                     "addressed": None, "echo": {}, "trend": [], "ungrounded": [],
                     "switches": {s: self.on(s) for s in SWITCHES}}
        # gauges are sampled once per reply for the trend
        try:
            self._hist.append(dict(self.state.gauges))
        except Exception:
            pass

    def _save(self):
        try:
            self.store.set("bz_last", json.dumps(self.last, ensure_ascii=False))
        except Exception as e:
            self.log(f"[bz] kv not written: {type(e).__name__}: {e}")

    # ---- 5. change, not level ----
    def trend_words(self):
        """Gauges that moved against their own recent level. A gauge at its
        usual level says nothing."""
        delta = float(self._c("trend_delta", 6.0))
        hist = list(self._hist)
        if len(hist) < 3:
            return []
        out = []
        now = hist[-1]
        for k, v in now.items():
            prior = [h[k] for h in hist[:-1] if k in h and isinstance(h[k], (int, float))]
            if not prior or not isinstance(v, (int, float)):
                continue
            usual = sum(prior) / len(prior)
            d = v - usual
            if d >= delta:
                out.append(f"{k} rising")
            elif d <= -delta:
                out.append(f"{k} easing")
        return out

    def mood_line(self, original):
        """The text of the 'you feel' line. With trend on: change words only
        (empty string = line dropped). With order on and keep_mood_tags off:
        dropped."""
        if self.on("trend"):
            words = self.trend_words()
            self.last["trend"] = words
            original = ", ".join(words)
        if self.on("order") and not self.on("keep_mood_tags"):
            return ""
        return original

    def keep_register(self):
        return not (self.on("order") and not self.on("keep_register"))

    # ---- 4. echo ----
    def _threshold(self):
        t = float(self._c("echo_threshold", 0.0) or 0.0)
        if t > 0:
            return t
        pool = str(self._c("echo_pool", "messages"))
        e = self.embed
        try:
            return float((getattr(e, "_floors", {}) or {}).get(pool) and e._floors[pool][0] or e._configured(pool)[0])
        except Exception:
            return 0.85

    def echo_counts(self):
        """How many of her earlier lines the newest one echoes, and the same
        for his. Cosine at or above the pool floor."""
        thr = self._threshold()
        res = {"hers": 0, "his": 0, "threshold": round(thr, 3)}
        if self.embed is None:
            return res
        try:
            rows = list(reversed(self.store.recent_messages(int(self._c("echo_window", 12)))))
            for role, key in (("assistant", "hers"), ("user", "his")):
                texts = [_txt(r) for r in rows if r["role"] == role and _txt(r).strip()]
                if len(texts) < 2:
                    continue
                vecs = self.embed._encode(texts, "passage: ")
                if vecs is None:
                    continue
                newest = vecs[-1]
                res[key] = int(sum(1 for v in vecs[:-1] if float(newest @ v) >= thr))
        except Exception as e:
            self.log(f"[bz] echo not read: {type(e).__name__}: {e}")
        return res

    # ---- 2. constant lines ----
    def constant_lines(self, situation):
        """Record this call's lines; flag the ones present, byte-identical, in
        each of the previous N calls. Returns (situation, flagged)."""
        lines = situation.split("\n")
        minc = int(self._c("constant_min_chars", 12))
        protect = [str(p).lower() for p in (self._c("protect", []) or [])]
        flagged = []
        if len(self._snaps) >= self._snaps.maxlen:
            common = set.intersection(*[set(s) for s in self._snaps])
            for ln in lines:
                if ln in common and len(ln.strip()) >= minc and not any(p in ln.lower() for p in protect):
                    flagged.append(ln)
        self._snaps.append(list(lines))
        self.last["constant_flagged"] = list(flagged)
        if flagged:
            self.log(f"[bz] constant lines ({len(flagged)}): " + " | ".join(f[:60] for f in flagged))
        if flagged and self.on("cut_constant"):
            fs = set(flagged)
            situation = "\n".join(ln for ln in lines if ln not in fs)
            self.last["constant_cut"] = list(flagged)
        return situation, flagged

    def process_situation(self, situation):
        """Hook in _draft, before the tail is placed."""
        if not self.last:
            self.begin()
        if self._snapped:
            # a redraft inside one reply: same cut, no second snapshot
            fs = set(self.last.get("constant_cut") or [])
            return "\n".join(ln for ln in situation.split("\n") if ln not in fs) if fs else situation
        self._snapped = True
        if self.on("cut_constant"):
            return self.constant_lines(situation)[0]
        if self.any_on():
            self.constant_lines(situation)
        return situation

    def expecting(self, expectations, ja=False):
        """His open promises (sim/expectations.py situation_line): what she is
        waiting on and what he owes her. '' when none or the module is absent."""
        if expectations is None:
            return ""
        try:
            return str(expectations.situation_line(ja) or "")
        except Exception as e:
            self.log(f"[bz] expectations not read: {type(e).__name__}: {e}")
            return ""

    def finish(self, messages, his_text="", stance="", expectations=""):
        """Hook in _draft after place_tail: the order, once per reply, last."""
        if not self.on("order"):
            return messages
        if not self.last.get("order_called"):
            self.build_order(his_text, stance, expectations)
        return self.place_order(messages, self.last.get("order", ""))

    # ---- 1. + 3. + 4. the order ----
    def _recent(self, n=6):
        try:
            rows = list(reversed(self.store.recent_messages(n)))
            return [("him" if r["role"] == "user" else "her") + ": " + _txt(r) for r in rows]
        except Exception:
            return []

    def build_order(self, his_text="", stance="", expectations=""):
        """One machinery call. Returns the order text ('' when off or failed)."""
        if not self.on("order"):
            return ""
        if not self.last:
            self.begin()
        parts = ["LANGUAGE: " + ("japanese" if self.ja() else "english")]
        try:
            parts.append("GAUGES: " + ", ".join(f"{k} {v:.0f}" for k, v in self.state.gauges.items()
                                                 if isinstance(v, (int, float))))
        except Exception:
            pass
        if self.on("trend") or self.last.get("trend"):
            tw = self.last.get("trend") or self.trend_words()
            self.last["trend"] = tw
            parts.append("CHANGES: " + (", ".join(tw) if tw else "none"))
        if stance:
            parts.append("STANCE: " + str(stance))
        if expectations:
            parts.append("EXPECTING: " + str(expectations))
        if self.on("echo"):
            ec = self.echo_counts()
            self.last["echo"] = ec
            note = []
            if ec.get("hers"):
                note.append(f"her newest line echoes {ec['hers']} of her earlier lines")
            if ec.get("his"):
                note.append(f"his newest line echoes {ec['his']} of his earlier lines")
            parts.append("ECHO: " + ("; ".join(note) if note else "none"))
        recent = self._recent()
        if recent:
            parts.append("LAST LINES:\n" + "\n".join(recent))
        if self.on("answer_first") and his_text.strip():
            parts.append("HE SAID: " + his_text.strip()[:600])
        try:
            system = (_ROOT / "prompts" / "bz_order.txt").read_text(encoding="utf-8")
            out = self.llm.call("bz_order", [{"role": "system", "content": system},
                                             {"role": "user", "content": "\n".join(parts)}])
            order = str(out or "").strip()
        except Exception as e:
            self.log(f"[bz] order not written: {type(e).__name__}: {e}")
            order = ""
        self.last["order_called"] = True
        self.last["order"] = order
        return order

    def place_order(self, messages, order):
        """Append the order to the last message: last in her prompt."""
        if not order or not messages:
            return messages
        msgs = [dict(m) for m in messages]
        last = msgs[-1]
        last["content"] = str(last.get("content", "")) + "\n\n" + order
        msgs[-1] = last
        return msgs

    # ---- 3. answered him? ----
    def check_addressed(self, his_text, reply):
        his_text = str(his_text or "").strip()
        reply = str(reply or "").strip()
        if not his_text:
            return None
        ok = False
        a, b = _bigrams(his_text), _bigrams(reply)
        if a and b and len(a & b) >= min(2, len(a)):
            ok = True
        if not ok and self.embed is not None:
            try:
                v = self.embed._encode([his_text, reply], "passage: ")
                if v is not None:
                    ok = float(v[0] @ v[1]) >= self._threshold() - 0.25
            except Exception:
                pass
        return bool(ok)

    # ---- 6. claims that match no input ----
    @staticmethod
    def _claims(text):
        toks = set(re.findall(r"\d[\d:.,]*", text))
        toks |= set(re.findall(r"(?<=[a-z,] )[A-Z][a-z]{2,}", text))
        toks |= set(re.findall(r"[ァ-ヿ]{3,}", text))
        return toks

    def ungrounded(self, reply, messages):
        corpus = "\n".join(str(m.get("content", "")) for m in messages or [])
        return sorted(c for c in self._claims(str(reply or "")) if c not in corpus)

    # ---- end of reply ----
    def after_reply(self, reply, his_text, messages):
        if not self.last:
            self.begin()
        if self.on("answer_first"):
            self.last["addressed"] = self.check_addressed(his_text, reply)
            self.log(f"[bz] addressed={self.last['addressed']}")
        if self.on("reality"):
            self.last["ungrounded"] = self.ungrounded(reply, messages)
            if self.last["ungrounded"]:
                self.log("[bz] ungrounded: " + ", ".join(self.last["ungrounded"]))
        self._save()
        return self.last
