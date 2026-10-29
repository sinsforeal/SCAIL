# -*- coding: utf-8 -*-
"""The last look at her draft before it goes: the slop, the repeats, the length.

This is a post-processor on what she wrote, never a change to her prompt. It
exists because the same faults arrive from a model that completed a reply the
way a model completes one: the openers ("I see...", "それはそうと"), a phrase
she leans on, a sentence said twice in one message, and a draft that is simply
longer than the moment wanted.

Four passes, all local unless the draft is too long and a rewrite role is on:

* forbidden phrases -- the ones her config names are rewritten or dropped.
* capped tics -- the marks the authored bible measures on her lines (`caps`)
  are capped per draft, not banned, so the habit stays hers without a model
  saying it every bubble.
* repeated openers and duplicate bubbles inside one draft.
* a run shared with one of her own recent messages (`store.recent_messages`),
  the same test `Persona._repeats_recent` runs for the editor gate.
* the length: over `quality.max_chars`, the `quality_rewrite` role is asked to
  shorten it in her voice when the model is on, and the draft is cut at a
  sentence boundary otherwise.

Every finding is returned as a note so the caller can log it. Nothing is
written to her record here.
"""

import os
import re

# punctuation that ends a sentence, Japanese and English
_SENTENCE_END = "。．.!?！？\n"


class Quality:
    """The slop, repeat and length guard over one draft."""

    def __init__(self, config, store=None, clock=None, llm=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.llm = llm
        c = getattr(config, "quality", None)
        self.enabled = bool(getattr(c, "enabled", False))
        self.use_model = bool(getattr(c, "use_model", False)) and llm is not None
        self.max_chars = int(getattr(c, "max_chars", 0) or 0)
        self.repeat_run = int(getattr(c, "repeat_run", 16) or 16)
        self.recent_n = int(getattr(c, "recent_messages", 8) or 8)
        self.openers = bool(getattr(c, "openers", True))
        forb = getattr(c, "forbidden", None)
        self.forbidden = dict(forb) if isinstance(forb, dict) else {}
        caps = getattr(c, "caps", None)
        self.caps = dict(caps) if isinstance(caps, dict) else {}
        self.cap_phrases = {}
        _ph = self.caps.get("phrases")
        if isinstance(_ph, dict):
            for _k, _v in _ph.items():
                try:
                    self.cap_phrases[str(_k)] = int(_v)
                except (TypeError, ValueError):
                    continue
        try:
            self.cap_doubled = int(self.caps.get("doubled_group") or 0)
        except (TypeError, ValueError):
            self.cap_doubled = 0
        self.caps_source = str(self.caps.get("source") or "")
        self.root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # ---------------- the passes ----------------

    def _forbidden(self, bubbles, notes):
        if not self.forbidden:
            return bubbles
        out = []
        for b in bubbles:
            text = str(b)
            for phrase, repl in self.forbidden.items():
                if phrase and phrase in text:
                    if text.replace(phrase, "") != text or True:
                        notes.append(f"the phrase {phrase!r} was removed")
                    text = text.replace(phrase, str(repl or ""))
            text = re.sub(r"[ \t]{2,}", " ", text)
            # a phrase lifted out from the front leaves its comma behind
            text = text.strip().lstrip("、,. 　").strip()
            if text:
                out.append(text)
        return out or bubbles

    def _tidy(self, text):
        """What is left of a bubble after a mark is lifted out of it: no run of
        spaces, no run of 、, and nothing left hanging at the front."""
        text = re.sub(r"[ \t]{2,}", " ", str(text))
        text = re.sub(r"、{2,}", "、", text)
        text = re.sub(r"^[、,.。\s　]+", "", text)
        return text.strip()

    def _caps(self, bubbles, notes):
        """The tics that are HERS, capped per draft rather than banned.

        Each phrase is a mark the authored bible measures on her lines; the
        cap keeps the first `max` occurrences across the whole draft and drops
        the rest, so the habit still reads as hers instead of as a model's
        fill. `doubled_group` caps the wider immediate-repeat move by count.
        The register split the bible measures is not available here, so the
        caps are set loose enough to leave an H scene's moans alone.

        The guard never empties her: a draft the cap would take everything
        from stands as she wrote it."""
        if not self.cap_phrases and not self.cap_doubled:
            return bubbles
        out = [str(b) for b in bubbles]
        for phrase, mx in self.cap_phrases.items():
            if not phrase or mx < 1:
                continue
            seen = 0
            kept = []
            for b in out:
                if phrase not in b:
                    kept.append(b)
                    continue
                buf, j = [], 0
                while True:
                    k = b.find(phrase, j)
                    if k < 0:
                        buf.append(b[j:])
                        break
                    seen += 1
                    if seen <= mx:
                        buf.append(b[j:k + len(phrase)])
                    else:
                        notes.append("the tic %r was over its cap of %d in one draft; the extra was dropped"
                                     % (phrase, mx))
                    j = k + len(phrase)
                kept.append("".join(buf))
            out = kept
        if self.cap_doubled:
            out, over = self._cap_doubled(out)
            if over:
                notes.append("the draft doubled a word %d time(s), over its cap of %d"
                             % (over, self.cap_doubled))
        out = [self._tidy(b) for b in out]
        out = [b for b in out if b]
        return out or bubbles

    def _cap_doubled(self, bubbles):
        """A 2-4 character kana/kanji group said twice immediately, capped by
        count. The doubled ん the guide counts separately is 1-3 characters
        and never matches, and a sound-symbolic repeat a draft carries once is
        under the cap; only genuine over-use -- the same move three times or
        more -- loses its extra doublings."""
        pat = re.compile(r"(.{2,4})\1")
        total = sum(len(pat.findall(str(b))) for b in bubbles)
        if total <= self.cap_doubled:
            return [str(b) for b in bubbles], 0
        seen = [0]

        def repl(m):
            seen[0] += 1
            return m.group(1) if seen[0] > self.cap_doubled else m.group(0)

        return [pat.sub(repl, str(b)) for b in bubbles], total

    def _openers(self, bubbles, notes):
        """A draft that opens two bubbles the same way, and one that says the
        same bubble twice."""
        out, seen_open = [], set()
        for b in bubbles:
            text = str(b).strip()
            if not text:
                continue
            low = text.lower()
            if low in {str(x).strip().lower() for x in out}:
                notes.append("a bubble was said twice in one draft")
                continue
            head = re.split(r"[。．.!?！？\s]", text, maxsplit=1)[0][:12]
            if head and head in seen_open and len(text) > len(head):
                # the second bubble that opens with the same words loses them
                rest = text[len(head):].lstrip("、。,. 　")
                if rest:
                    notes.append(f"a second bubble opened with {head!r} again")
                    text = rest
            seen_open.add(head)
            out.append(text)
        return out

    def _self_repeat(self, bubbles, notes):
        """A run repeated inside the draft: keep the first, drop the rest."""
        whole = " ".join(str(b) for b in bubbles)
        run = self.repeat_run
        if run < 4 or len(whole) < run * 2:
            return bubbles
        low = whole.lower()
        dropped = False
        for i in range(0, len(low) - run):
            seg = low[i:i + run]
            if not seg.strip():
                continue
            if low.count(seg) > 1 and seg.count(" ") < run // 2:
                notes.append(f"the draft repeated a run ({seg[:24]!r})")
                dropped = True
                break
        if not dropped:
            return bubbles
        # cut at the end of the sentence the repetition began in
        cut = whole.find(seg)
        head = whole[:cut]
        for end in _SENTENCE_END:
            pos = head.rfind(end)
            if pos > 0:
                head = head[:pos + 1]
                break
        return [head.strip()] if head.strip() else bubbles

    def _recent_repeat(self, bubbles, notes):
        """A run shared with one of her own last messages."""
        run = self.repeat_run
        if run < 4 or self.store is None:
            return bubbles
        try:
            recent = [m for m in (self.store.recent_messages(self.recent_n) or [])
                      if m.get("role") != "user"]
        except Exception:
            recent = []
        if not recent:
            return bubbles
        for b in bubbles:
            low = str(b).lower()
            for m in recent:
                rl = str(m.get("text") or "").lower()
                for i in range(0, max(0, len(rl) - run)):
                    seg = rl[i:i + run]
                    if seg.strip() and seg in low:
                        notes.append(f"she is saying again what she already said ({seg.strip()[:24]!r})")
                        return []
        # Nothing shared: the draft stands. This `return` is the fix for a live
        # fault -- the function used to fall off the end here and hand back
        # None, and `_length` then iterated it, so `review` raised
        # `TypeError: 'NoneType' object is not iterable` on every draft that
        # repeated nothing. That is nearly every draft, so the whole guard --
        # the forbidden phrases, the caps, the openers, the length -- was
        # quietly skipped whenever it had nothing to say.
        return bubbles

    def _length(self, bubbles, notes):
        if not self.max_chars:
            return bubbles
        total = sum(len(str(b)) for b in bubbles)
        if total <= self.max_chars:
            return bubbles
        joined = "\n".join(str(b) for b in bubbles)
        if self.use_model:
            short = self._rewrite(joined)
            if short:
                parts = [p.strip() for p in re.split(r"\n+", short) if p.strip()]
                notes.append(f"the draft was {total} chars; rewritten to {sum(len(p) for p in parts)}")
                return parts
        cut = joined[: self.max_chars]
        for end in _SENTENCE_END:
            pos = cut.rfind(end)
            if pos > self.max_chars // 2:
                cut = cut[:pos + 1]
                break
        notes.append(f"the draft was {total} chars; cut to {len(cut)} at a sentence end")
        return [cut.strip()] if cut.strip() else bubbles

    def _rewrite(self, text):
        """The `quality_rewrite` role: the same words, fewer of them."""
        if not self.use_model:
            return ""
        try:
            system = self.config.role_system("quality_rewrite")
            messages = [{"role": "system", "content": system},
                        {"role": "user", "content": text}]
            out = self.llm.call("quality_rewrite", messages)
        except Exception:
            return ""
        return str(out or "").strip()

    # ---------------- the one callers make ----------------

    def review(self, bubbles, notes=None):
        """The draft after the guard. Returns (bubbles, notes)."""
        notes = notes if notes is not None else []
        if not self.enabled or not bubbles:
            return bubbles, notes
        out = [str(b) for b in bubbles if str(b).strip()]
        out = self._forbidden(out, notes)
        out = self._caps(out, notes)
        if self.openers:
            out = self._openers(out, notes)
        out = self._self_repeat(out, notes)
        out = self._recent_repeat(out, notes)
        out = self._length(out, notes)
        if not out:
            # the guard never empties her; a draft that trips every pass is
            # sent as she wrote it rather than as silence
            notes.append("the guard found nothing left to send; the draft stands")
            return bubbles, notes
        return out, notes

    def verify(self):
        return {"enabled": self.enabled, "use_model": self.use_model,
                "max_chars": self.max_chars, "forbidden": len(self.forbidden),
                "caps": len(self.cap_phrases), "doubled_group": self.cap_doubled,
                "caps_source": self.caps_source}


if __name__ == "__main__":
    import json
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)

    class _Q:
        enabled = True
        use_model = False
        max_chars = 40
        repeat_run = 12
        recent_messages = 8
        openers = True
        forbidden = {"要するに": ""}

    class _C:
        quality = _Q()

    q = Quality(_C())
    draft = ["要するに、そういうことだよ。", "そういうことだよ。", "今日は晴れていたね今日は晴れていたね"]
    out, notes = q.review(draft)
    print("out:", out)
    print("notes:", notes)
    raise SystemExit(0)
