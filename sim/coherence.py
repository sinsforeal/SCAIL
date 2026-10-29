"""The day read as a story, flag only.

`tools/absurd.py` measures the parts: a gate nobody reaches, a person who
repeats herself, a place that is not on the map. Nothing read the record
as one story, and the seams that break the illusion live between the
parts: she tells him she cannot go to her brother's match, tells her
brother she is coming and, in the same breath, apologises for having
slept through it; she thanks a friend for a notebook no exchange
mentions; she puts the same three titles to him twice, three minutes
apart. Each is structurally valid and visible to anybody who reads the
day, and the only reader was him.

Once a day at the compile (`review`), the `coherence` role is handed the
day's record -- the ledger, the scenes, the events, his chat, every
exchange with her own people -- and names the seams: a CONTRADICTION (two
incompatible things she said, or a thing the ledger or a scene refutes),
an INVENTED thing (an object, event or person with no source anywhere in
the record), a REPEAT (the same thing said again as new). Code keeps them
(kv `coherence_flags`), logs each as `[coherence] FLAG`, and changes
nothing: the record is what happened, and a seam is a signal about a
prompt or a mechanism, never a reason to rewrite her. `/coherence [date]`
runs it by hand and shows the last readings; `/absurd` SEAMS reads them
back for the last `coherence.absurd_days`.
"""
import datetime
from sim import chattext

import logger
from sim import talks

# Every kind either character's auditor prompt asks for. `knew` (a thing she
# says about him that nothing in the record showed her) and `shared` (her own
# past talked about as though he had been there) belong to the resident's
# prompt, which calls the first of them "the important one for her" -- and
# were missing here, so all 81 of them her auditor found between 2026-09-02
# and 2026-09-04 were dropped without a word and her save held one flag.
KINDS = ("contradiction", "invented", "repeat", "compile", "knew", "shared")


class Coherence:
    def __init__(self, config, llm, store, clock, ledger=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.ledger = ledger
        self._her = str(getattr(config.character, "name", "her") or "her").upper()

    # ---------------- store ----------------

    def rows(self):
        return list(self.store.get("coherence_flags", []) or [])

    def _save(self, rows):
        keep = int(getattr(self.config.coherence, "keep", 200) or 200)
        self.store.set("coherence_flags", rows[-keep:])

    # ---------------- the record ----------------

    def record(self, date_str):
        """The whole day as text, every part of it the machine holds, so a
        seam between two parts is visible to one reader."""
        ledger_txt = ""
        if self.ledger is not None:
            try:
                ledger_txt = self.ledger.day_text(date_str)
            except Exception:
                ledger_txt = ""
        scenes = self.store.scenes_for_date(date_str) or []
        events = [e for e in (self.store.events_for_date(date_str) or [])]
        msgs = self.store.messages_for_date(date_str) or []
        scenes_txt = "\n".join(
            f"[{s.get('hm', '')}] {s.get('location', '')} / {s.get('activity', '')} with {s.get('with_who', '')}"
            for s in scenes) or "(none)"
        events_txt = "\n".join(
            f"[{self.clock.hm(e['ts'])}] ({e.get('kind', '')}) {str(e.get('text', ''))[:300]}"
            for e in events) or "(none)"
        msg_txt = chattext.lines(msgs, self.clock, chars=600, labels=("HIM", self._her)) or "(no messages exchanged)"
        talks_txt = talks.compile_rows(self.store, date_str)
        compiled = self._compiled(date_str)
        before = self._days_before(date_str)
        before_block = (f"THE DAYS BEFORE (compiled; a line today that refers back -- a festival she went to, photos "
                        f"she still owes -- is judged against these, not called invented):\n{before}\n\n" if before else "")
        return (f"DATE (her clock): {date_str}\n\n{before_block}"
                f"THE LEDGER (the day's one truth: where she was, with whom, what was settled):\n{ledger_txt or '(none)'}\n\n"
                f"SCENES (her hour, where, what, with whom):\n{scenes_txt}\n\n"
                f"EVENTS:\n{events_txt}\n\n"
                f"HER CHAT WITH HIM (English; times are hers):\n{msg_txt}\n\n"
                f"HER TALKS WITH HER OWN PEOPLE (Japanese; times are hers):\n{talks_txt}\n"
                + (f"\nTHE COMPILED DAY (written by the nightly compile FROM the record above: what she will remember "
                   f"and what she now believes about him. A claim here the record does not support, or that "
                   f"contradicts it, is a seam of kind `compile`):\n{compiled}\n" if compiled else ""))

    def _days_before(self, date_str):
        """The compiled summaries of the previous `coherence.context_days`.
        Without them both readers of 2026-09-01 called 「rena couldn't come. i
        went alone」 a contradiction: it was about the festival two days
        earlier, whose photos she kept not sending (docs/ab-judge-roles.md)."""
        n = int(getattr(self.config.coherence, "context_days", 2) or 0)
        if n <= 0:
            return ""
        out = []
        try:
            d0 = datetime.date.fromisoformat(date_str)
        except ValueError:
            return ""
        for i in range(n, 0, -1):
            d = (d0 - datetime.timedelta(days=i)).isoformat()
            try:
                day = self.store.get_day(d)
            except Exception:
                day = None
            if not day:
                continue
            text = str(day.get("summary") or "").strip() or str(day.get("narrative") or "").strip()[:1500]
            if text:
                out.append(f"[{d}] {text[:1500]}")
        return "\n".join(out)

    def _compiled(self, date_str):
        """The compile's own output for the date: the narrative, the summary,
        the facts about him it wrote, the memories it kept. The reader
        judges them against the record they were written from, so a day
        that was remembered wrong is named the same night."""
        import json as _json
        day = None
        try:
            day = self.store.get_day(date_str)
        except Exception:
            day = None
        if not day:
            return ""
        parts = []
        if day.get("narrative"):
            parts.append(f"NARRATIVE:\n{str(day['narrative'])[:6000]}")
        if day.get("summary"):
            parts.append(f"SUMMARY: {str(day['summary'])[:1200]}")
        facts = day.get("user_facts")
        if isinstance(facts, str):
            try:
                facts = _json.loads(facts)
            except ValueError:
                facts = [facts]
        if facts:
            parts.append("FACTS ABOUT HIM IT WROTE:\n" + "\n".join(f"- {str(f)[:200]}" for f in list(facts)[:12]))
        try:
            with self.store.lock:
                rows = self.store.conn.execute("select source, text from self_memories where date=? order by ts", (date_str,)).fetchall()
            mems = [f"- ({r[0]}) {str(r[1])[:200]}" for r in rows]
            if mems:
                parts.append("MEMORIES KEPT FOR THE DAY:\n" + "\n".join(mems[:14]))
        except Exception:
            pass
        return "\n\n".join(parts)

    # ---------------- the reading ----------------

    def review(self, date_str=None):
        """One call over the day; the seams it names are kept and logged.
        Returns the seams kept (a list), or None when the answer did not
        parse -- a caller never stores a raw answer as data."""
        c = self.config.coherence
        if not c.enabled:
            return []
        date_str = date_str or self.clock.date_str()
        user = self.record(date_str)
        n = int(getattr(c, "max_seams", 12) or 12)
        # The bound the code applies, told to the model. Nothing had ever said
        # it: the prompt asks for a list with no end to it, the loop below
        # keeps the first `max_seams` and throws the rest away, and on
        # 2026-09-03 the reader returned 31 seams that were near-copies of
        # each other and twice fell into writing the same one until the host
        # cut it off. It goes in the system prompt, which is the same bytes
        # every night and so stays cacheable.
        system = self.config.prompt_text("coherence") + (
            f"\n\nReturn at most {n} seams, and never the same seam twice. Anything past the "
            f"{n}th is discarded unread, and so is a seam already in the list. When you have "
            f"written the ones you found, close the list and stop.")
        data, raw = self.llm.call_json("coherence", [
            {"role": "system", "content": system},
            {"role": "user", "content": user}])
        if not isinstance(data, dict) or not isinstance(data.get("seams"), list):
            logger.log(f"[coherence] {date_str}: no usable answer")
            return None
        now = self.clock.now_ts()
        rows = [r for r in self.rows() if not (r.get("date") == date_str and r.get("by") == "review")]
        kept = []
        seen = set()
        for s in data["seams"][:n]:
            if not isinstance(s, dict):
                continue
            kind = str(s.get("kind", "") or "").strip().lower()
            if kind not in KINDS:
                continue
            try:
                sev = max(1, min(3, int(s.get("severity", 1) or 1)))
            except (TypeError, ValueError):
                sev = 1
            what = str(s.get("what", "") or "").strip()[:300]
            if not what:
                continue
            # The same seam written twice is one seam. A reader that has run
            # out of findings repeats its last one rather than closing the
            # list, and a day's flags read as eleven problems when there was
            # one.
            if (kind, what) in seen:
                continue
            seen.add((kind, what))
            row = {"ts": now, "date": date_str, "by": "review", "kind": kind, "severity": sev,
                   "where": str(s.get("where", "") or "").strip()[:120],
                   "what": what, "record": str(s.get("record", "") or "").strip()[:300]}
            kept.append(row)
            logger.log(f"[coherence] FLAG s{sev} {kind} ({row['where']}): {what}" + (f" -- record: {row['record'][:120]}" if row["record"] else ""))
        rows += kept
        self._save(rows)
        logger.log(f"[coherence] {date_str}: {len(kept)} seam(s)" + ("" if kept else " -- the day holds together"))
        return kept

    # ---------------- reading back ----------------

    def recent(self, days=None):
        days = int(days if days is not None else getattr(self.config.coherence, "absurd_days", 2) or 2)
        today = self.clock.now().date()
        lo = (today - datetime.timedelta(days=days)).isoformat()
        return [r for r in self.rows() if str(r.get("date", "")) >= lo]

    def report(self, days=7):
        rows = self.recent(days)
        if not rows:
            return f"coherence: no seams flagged in the last {days} day(s)" + ("" if self.rows() else " (never run)")
        out = [f"coherence: {len(rows)} seam(s) in the last {days} day(s), flag only -- nothing was rewritten"]
        for r in sorted(rows, key=lambda r: (r.get("date", ""), -int(r.get("severity", 1)))):
            out.append(f"  {r.get('date', '')} s{r.get('severity', 1)} {r.get('kind', ''):13} {r.get('where', '')}")
            out.append(f"      {r.get('what', '')}")
            if r.get("record"):
                out.append(f"      record: {r['record']}")
        return "\n".join(out)
