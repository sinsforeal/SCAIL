"""Attention is what the situation block says once, and who gets the slot.

A line is a claim with a weight: the mechanisms already have the numbers
(severity, confidence, heat, pressure), and where they do not, the source
has a default. `admit` ranks each section, suppresses a claim already made
by a source that covers it (the ledger covers the promises and the money),
lets a one-per-source source say it once, and hands back the single
heaviest ACTION -- the nag, the thing she wanted to show him, a promise of
his come due, a thread that has waited long enough -- to sit last, where
she will read it.

Three rules stand between an action and that slot, because the line reads
as an order ("this is in this message") and an order should be worth
giving. It has to be heavy enough (`attention.slot_min_weight`): a link to
share held the slot twenty-five times in a week at 0.35, the lowest number
in the table, in blocks whose heaviest lines are 0.85, and it held it
because it was the only action offered. It must not be the thing she is
braced against: `veto=` is a set of sources or a predicate over the line,
built by `veto_from_text` from what the live prediction says may land
badly -- on 2026-09-04 the slot told her to raise the follow she had
objected to while another line six above it said raising it is what she is
half braced for. And it may not hold the slot reply after reply while she
answers with something else: `charge` counts the showings of one line and
tells the source (`declined`), which retires its own item. An action
blocked by the floor or the veto is not dropped: it rides as an ordinary
line in its own section, without the imperative. Nothing is dropped for room: until 2026-09-04 the gate
kept each section's heaviest lines inside a [lines, chars] budget and the
block under a total, and was cutting 25 lines to 15 on an ordinary reply
-- what happened today, at 0.83, dropped -- while the one budget over her
prompt (`context.target_tokens`) had room for all of it. The weights still
order the block and still pick the slot. The
others queue in their own stores and take the slot when they are the
heaviest; a hint is charged a showing only when it actually held the slot.

`Line` is a `str` with a tag, so a caller that appends plain strings still
works and gets the section's default weight. Instrument: one `[attention]`
log line per call and kv `attention_last` for `/attention` -- a source
whose line is never admitted is a dead line, the way a gauge nobody reads
is a dead gauge.
"""
import re

import logger


class Line(str):
    def __new__(cls, text, source="", weight=None, kind="fact", pin=False):
        o = super().__new__(cls, text)
        o.source, o.weight, o.kind, o.pin = source, weight, kind, pin
        return o


def tag(text, source, weight=None, kind="fact", pin=False):
    """Tag a line; an empty text stays empty so `if line:` keeps working."""
    if not text:
        return ""
    return Line(text, source, weight, kind, pin)


_LATIN = re.compile(r"[a-z][a-z'\-]{3,}")
_JA = re.compile(r"[぀-ヿ一-鿿]{2,}")


def _tokens(text):
    t = str(text or "").lower()
    out = set(_LATIN.findall(t))
    for run in _JA.findall(t):
        out |= {run[i:i + 2] for i in range(len(run) - 1)}
    return out


# words that name nothing: they are in every second line and would make any
# two sentences look like they were about the same thing
_EVERYDAY = frozenset("""the and for you that this with was are not but all one out get got had has have
    her him his she they them from way day now too its our your see say said know think want come some
    into over about when then than here there still only also even more most much very well good bad new
    old big off own back down were been being because before after while where which these those thing
    things really kinda sorta maybe okay sure thanks thank sorry yes yea nah nope ugh hmm haha lmao omg
    dont cant wont didnt isnt wasnt gonna wanna gotta right left just like lol yeah what why how who
    again already might read left going keep keeps thought told tell says""".split())
_WORD = re.compile(r"[a-z][a-z'\-]{2,}")


def _subject_words(text):
    """The words in `text` that could name a thing: three letters or more,
    the everyday ones out, Japanese as bigrams."""
    t = str(text or "")
    out = set(_WORD.findall(t.lower())) - _EVERYDAY
    for run in _JA.findall(t):
        out |= {run[i:i + 2] for i in range(len(run) - 1)}
    return out


def _names(words, subject):
    """Do any of `words` name `subject`? Whole, or by a stem of three
    letters or more, which is what a risk written in English and an item
    named in Japanese usually have between them: a short English word
    against the front of the handle the source says its item is about."""
    s = str(subject or "").lower().lstrip("@")
    if not s:
        return False
    if s in words:
        return True
    return len(s) >= 5 and any(len(w) >= 3 and (s.startswith(w) or w.startswith(s)) for w in words)


def _veto_pred(veto):
    """`veto` is a set of sources, or a predicate over the line, or None."""
    if veto is None:
        return lambda l: False
    if callable(veto):
        return veto
    srcs = {str(s) for s in veto}
    return lambda l: (getattr(l, "source", "") or "") in srcs


class Attention:
    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock
        self.hooks = {}          # source -> callable, charged when that source held the slot
        self.declined = {}       # source -> callable(showings): she read its line and answered something else
        self.subjects = {}       # source -> callable: the words its action is about, for the veto
        self.last = {}           # the last admit: what was kept, the slot, what was demoted, what queued

    def _weight(self, line, section, cue):
        c = self.config.attention
        w = getattr(line, "weight", None)
        src = getattr(line, "source", "") or ""
        if w is None:
            w = float(c.weights.get(src) if src and c.weights.get(src) is not None else c.section_default.get(section, 0.5))
        if cue and src not in ("clock", "scene"):
            lt = _tokens(line)
            if lt:
                overlap = len(lt & cue) / max(4.0, float(len(lt)))
                w += min(float(c.cue_bonus), overlap * float(c.cue_bonus) * 4.0)
        return round(float(w), 3)

    def veto_from_text(self, text, min_overlap=2):
        """A predicate over an action line: does `text` -- what the live
        prediction says may land badly, free prose -- warn against THIS
        action? Two ways, because the two are as often as not written in
        different languages. The narrow one: the source says in words what
        its action is about (`subjects`, filled by the program: the handles
        the item names), and the risk names one of them. The wide one: the
        risk and the line share `min_overlap` words that are not everyday.
        None when the risk has nothing to match on."""
        words = _subject_words(text)
        if not words:
            return None
        subjects = dict(self.subjects)
        n = max(1, int(min_overlap))

        def _vetoed(line):
            src = getattr(line, "source", "") or ""
            fn = subjects.get(src)
            if fn:
                try:
                    for s in (fn() or ()):
                        if _names(words, s):
                            return True
                except Exception as e:
                    logger.log(f"[attention] what {src} is about was not read: {type(e).__name__}: {e}")
            return len(words & _subject_words(line)) >= n
        return _vetoed

    def admit(self, sections, cue_text="", label="", veto=None, veto_by="foresight"):
        """sections: {name: [lines]} in prompt order. Returns (kept lines in
        order, the slot line or '', a one-line report). `veto` names actions
        that may not take the slot this call -- a set of sources or a
        predicate over the line -- and `veto_by` is who says so, for the
        report."""
        c = self.config.attention
        cue = _tokens(cue_text) if cue_text else set()
        present = {getattr(l, "source", "") for ls in sections.values() for l in ls if getattr(l, "source", "")}
        covered = set()
        for cover, under in dict(c.covered_by).items():
            if cover in present:
                covered |= set(under)
        ranked = []       # (section, index, weight, line)
        for name, ls in sections.items():
            for i, l in enumerate(ls):
                if not l:
                    continue
                src = getattr(l, "source", "") or ""
                if src in covered and not getattr(l, "pin", False):
                    ranked.append((name, i, -1.0, l))      # suppressed: a heavier source said it
                    continue
                ranked.append((name, i, self._weight(l, name, cue), l))
        # The slot: the heaviest ACTION across every section, if it is heavy
        # enough to be worth ordering and the foresight is not braced against
        # it. An action that fails either is not dropped -- the heaviest of
        # them rides where its section put it, as a plain line, without the
        # imperative.
        # The floor is the room with him, which is the room the fault was
        # measured in. Her turns with her own people rank on their own scale:
        # the only action ever offered there is a rumour, at 0.45, and 99 of
        # the 103 filled slots on record are under 0.5 -- the same number
        # would empty that line rather than raise its bar.
        floor = 0.0 if label else float(getattr(c, "slot_min_weight", 0.0) or 0.0)
        is_vetoed = _veto_pred(veto)
        actions = sorted([r for r in ranked if getattr(r[3], "kind", "") == "action" and r[2] >= 0],
                         key=lambda r: (-r[2], r[0], r[1]))
        slot, blocked = None, []
        for r in actions:
            asrc = getattr(r[3], "source", "") or "action"
            if is_vetoed(r[3]):
                blocked.append((r, "vetoed", f"{veto_by} vetoed {asrc}"))
                continue
            if r[2] < floor:
                blocked.append((r, "under the floor", f"heaviest action {asrc} at {r[2]:.2f} under the floor"))
                continue
            slot = r
            break
        blocked_why = {id(r[3]): why for r, why, _note in blocked}
        demoted = {id(blocked[0][0][3])} if blocked else set()
        blocked_note = blocked[0][2] if blocked else ""
        queued_actions = []
        kept, dropped, per = [], [], {}
        total_chars = 0
        # no line is dropped for room (module docstring): what goes is a claim
        # a heavier source already made, an action that is not the heaviest,
        # and a second line from a source that says its piece once
        for name, ls in sections.items():
            rows = [r for r in ranked if r[0] == name]
            chosen, chars, seen_src = [], 0, set()
            for r in sorted(rows, key=lambda r: (-int(bool(getattr(r[3], "pin", False))), -r[2], r[1])):
                _n, i, w, l = r
                src = getattr(l, "source", "") or ""
                if slot is not None and r is slot:
                    continue
                if w < 0:
                    dropped.append((src or name, "covered"))
                    continue
                if getattr(l, "kind", "") == "action":
                    if id(l) in demoted:
                        pass                                    # blocked from the slot; it rides as a plain line
                    elif id(l) in blocked_why:
                        dropped.append((src or name, blocked_why[id(l)]))
                        continue
                    else:
                        dropped.append((src or name, "queued"))  # only the heaviest action rides
                        queued_actions.append(r)
                        continue
                if src and src in seen_src and src in set(c.one_per_source):
                    dropped.append((src, "dup"))
                    continue
                chosen.append(r)
                chars += len(l)
                seen_src.add(src)
            chosen.sort(key=lambda r: r[1])          # back into prompt order
            kept += [r[3] for r in chosen]
            per[name] = len(chosen)
            total_chars += chars
        n_in = sum(len([l for l in ls if l]) for ls in sections.values())
        slot_line = slot[3] if slot else ""
        lab = f" {label}" if label else ""
        slot_src = (getattr(slot_line, "source", "") or "action") if slot else ""
        report = (f"[attention]{lab} {n_in} -> {len(kept)} lines ({', '.join(f'{k} {v}' for k, v in per.items())}; {total_chars} chars)"
                  + (f" | slot: {slot_src} ({slot[2]:.2f})" if slot else " | slot: none")
                  + (f" ({blocked_note})" if blocked_note else "")
                  + (" | dropped: " + ", ".join(f"{s}({why})" for s, why in dropped[:12]) if dropped else ""))
        # what the second reader may be shown (`persona._admit`): the lines
        # this kept and the actions still waiting, never one it decided against
        self.last = {"kept": list(kept), "slot": slot_line, "report": report,
                     "demoted": [r[3] for r, _why, _note in blocked[:1]],
                     "queued": [r[3] for r in queued_actions]}
        try:
            self._tally(ranked, kept, slot, "friend" if label else "him")
        except Exception as e:
            logger.log(f"[attention] tally failed: {type(e).__name__}: {e}")
        try:
            self.store.set("attention_last_friend" if label else "attention_last", {
                "ts": self.clock.now_ts(), "report": report,
                "ranked": [{"section": r[0], "source": getattr(r[3], "source", "") or "", "weight": r[2],
                            "kind": getattr(r[3], "kind", ""), "kept": (r[3] in kept) or (slot is not None and r is slot),
                            "text": str(r[3])[:90]} for r in ranked]})
        except Exception:
            pass
        return kept, slot_line, report

    def _tally(self, ranked, kept, slot, room):
        """Per day, per room, per source: offered, admitted, held the slot,
        covered. A source that is offered every call and admitted in none
        is a dead line with a config block behind it -- forty statuses
        compete for sixteen lines, and this is the count that says which
        of them she never hears. kv `attention_tally`, `attention.tally_days`."""
        c = self.config.attention
        tally = self.store.get("attention_tally", {}) or {}
        day = self.clock.date_str()
        d = tally.setdefault(day, {}).setdefault(room, {})
        for sec, _i, w, l in ranked:
            src = getattr(l, "source", "") or sec
            e = d.setdefault(src, [0, 0, 0, 0])
            e[0] += 1
            if (l in kept) or (slot is not None and l is slot[3]):
                e[1] += 1
            if slot is not None and l is slot[3]:
                e[2] += 1
            if w < 0:
                e[3] += 1
        keep = int(getattr(c, "tally_days", 14) or 14)
        for k in sorted(tally.keys())[:-keep]:
            tally.pop(k, None)
        self.store.set("attention_tally", tally)

    @staticmethod
    def tally_totals(tally, days=7, today=None):
        """{room: {source: [offered, admitted, slot, covered]}} over the
        last `days` dates on record."""
        import datetime as _dt
        today = today or _dt.date.today().isoformat()
        lo = (_dt.date.fromisoformat(today) - _dt.timedelta(days=days - 1)).isoformat()
        out = {}
        for day, rooms in (tally or {}).items():
            if not (lo <= str(day) <= today):
                continue
            for room, srcs in (rooms or {}).items():
                r = out.setdefault(room, {})
                for src, e in (srcs or {}).items():
                    t = r.setdefault(src, [0, 0, 0, 0])
                    for i in range(4):
                        t[i] += int((e or [0, 0, 0, 0])[i] if i < len(e) else 0)
        return out

    def tally_report(self, days=7):
        tot = self.tally_totals(self.store.get("attention_tally", {}) or {}, days, self.clock.date_str())
        if not tot:
            return "attention: no tally yet"
        out = [f"what she was handed over the last {days} day(s), per room and source: offered / admitted / held the slot (covered = a heavier source said it)"]
        for room in sorted(tot):
            out.append(f"  with {'him' if room == 'him' else 'her own people'}:")
            rows = sorted(tot[room].items(), key=lambda kv: (kv[1][1] + kv[1][2] > 0, -(kv[1][0])))
            for src, (off, adm, slot, cov) in rows:
                live = off - cov
                rate = (adm / live) if live else 0.0
                mark = "NEVER" if live >= 5 and adm == 0 else ("rare " if live >= 20 and rate < 0.05 else "     ")
                out.append(f"    {mark} {src:14} {off:4} offered  {adm:4} admitted  {slot:3} slot" + (f"  {cov:3} covered" if cov else "") + (f"  ({rate:.0%})" if live else ""))
        return "\n".join(out)

    def charge(self, slot_line):
        """The source that held the slot is charged a showing; nothing else."""
        self.charge_source(getattr(slot_line, "source", "") if slot_line else "")
        self._count_showing(slot_line)

    def _count_showing(self, slot_line):
        """How many replies running the same line has held the slot while she
        answered something else. A source retires its own item the moment she
        says it -- the bubble that has left is matched against it -- so the
        same text holding the slot a second time IS the answer that did not
        take it up. Every showing tells the source the count (`declined`) and
        the source decides whether to put its item away; it says so by
        returning true, and the count starts again. kv `attention_slot_shown`."""
        src = getattr(slot_line, "source", "") if slot_line else ""
        if not src:
            return
        text = str(slot_line)[:200]
        rec = self.store.get("attention_slot_shown", {}) or {}
        same = rec.get("source") == src and rec.get("text") == text
        n = (int(rec.get("n", 0) or 0) + 1) if same else 1
        self.store.set("attention_slot_shown", {"source": src, "text": text, "n": n})
        fn = self.declined.get(src)
        if not fn:
            return
        try:
            if fn(n):
                self.store.set("attention_slot_shown", {})
        except Exception as e:
            logger.log(f"[attention] {src} was not told she left it: {type(e).__name__}: {e}")

    def charge_source(self, src):
        """The same, by source tag: what the nudge decided happens is what
        was shown."""
        fn = self.hooks.get(src)
        if fn:
            try:
                fn()
            except Exception as e:
                logger.log(f"[attention] charge {src}: {type(e).__name__}: {e}")

    def report(self):
        r = self.store.get("attention_last") or {}
        if not r:
            return "attention: nothing admitted yet this run"
        out = [r.get("report", ""), ""]
        for x in sorted(r.get("ranked", []), key=lambda x: -x["weight"]):
            out.append(f"  {'*' if x['kept'] else ' '} {x['weight']:5.2f} {x['section']:5} {x['source'] or '-':14} {x['kind']:6} {x['text']}")
        return "\n".join(out)
