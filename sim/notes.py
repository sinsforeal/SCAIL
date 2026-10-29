import re
import logger
from sim import lang
from sim import record_guard
from sim import sight
from sim import wiring
from sensors import vault_monitor

# Reading his notes on purpose, in daylight. Three ways in: he names a note
# in a message, the director decides she opens one (open_note), or /read.
# The file itself never enters any prompt except the one call that produces
# her takeaway; what persists is a takeaway event for today plus a one-line
# gist in kv "notes_read", which is the compact list the persona sees.


class Notes:
    # her reaction to what she just read, which is written by a role that
    # has her sheet and is a row of its own
    WIRES = ('reflection',)

    def __init__(self, config, llm, store, clock, state):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        wiring.declare(self)

    def index(self):
        return self.store.get("notes_read", [])

    def index_text(self, limit=None):
        idx = self.index()
        n = limit or self.config.notes.index_in_prompt
        return "\n".join(f"- {e['basename']} ({e['date']}): {e['gist']}" for e in idx[-n:])

    def find_mentioned(self, text):
        """A vault file he named in his message, or None."""
        if not text or not self.config.sensors.vault_path:
            return None
        # explicit [[wikilinks]] or a filename with extension first
        m = re.search(r"\[\[([^\]]+)\]\]", text)
        cands = [m.group(1)] if m else []
        cands += re.findall(r"([\w\-. ]+\.(?:md|txt))", text, re.I)
        for cnd in cands:
            # "my banger quotes.md" -> try "my banger quotes.md", "banger quotes.md", "quotes.md"
            words = cnd.strip().split()
            for i in range(len(words)):
                q = " ".join(words[i:])
                f = vault_monitor.find(self.config.sensor_view, q, self.config.notes.skim_chars, self.config.notes.skim_pieces, self.clock.date_str())
                if f:
                    return f
        # quoted title
        for q in re.findall(r"[\"“”'‘’]([^\"“”'‘’]{3,60})[\"“”'‘’]", text):
            f = vault_monitor.find(self.config.sensor_view, q.strip(), self.config.notes.skim_chars, self.config.notes.skim_pieces, self.clock.date_str())
            if f:
                return f
        return None

    def read(self, query_or_file, reason, scene=None, reason_label=None):
        """Returns dict {basename, takeaway, salience, gist} or None.

        `reason` is why the note came to be in front of her, either one
        string or an (English, her language) pair: the role is machinery
        and reads the English, the sentence she reads is her arm.
        `reason_label` is the resident's, for whom the note was not opened
        by her but was on his screen (resident/sight.py)."""
        f = query_or_file if isinstance(query_or_file, dict) else vault_monitor.find(
            self.config.sensor_view, query_or_file, self.config.notes.skim_chars, self.config.notes.skim_pieces, self.clock.date_str())
        if not f or not f.get("content"):
            return None
        where = ""
        if scene:
            where = f"{scene.get('location', '')}: {scene.get('activity', '')}"
        reason_en, reason_hers = reason if isinstance(reason, tuple) else (reason, reason)
        user = (
            f"TIME: {self.clock.both()}\nWHERE SHE IS: {where or 'unknown'}\n"
            f"{reason_label or 'WHY SHE OPENED IT'}: {reason_en}\n\nWHAT SHE SKIMMED (pieces of the note, [...] marks what she scrolled past):\n=== {f['basename']} ===\n{f['content']}"
        )
        # through the guard rather than straight to the model: this answer
        # becomes an event she reads back as her own memory, so an answer that
        # is his file pasted back, or written in feelings, or in the wrong
        # language is asked for again and then dropped
        # (`sim/record_guard.py`).
        out = record_guard.ask(
            self.llm, "note_read",
            [{"role": "system", "content": self.config.prompt_text("note_read")},
             {"role": "user", "content": user}],
            self.config, skim=f.get("content", ""), tag="notes")
        if not out:
            return None
        sal = 3
        gist = ""
        m = re.search(r"IMPACT:\s*(\d)", out)
        if m:
            sal = max(1, min(5, int(m.group(1))))
        g = re.search(r"GIST:\s*(.+)", out)
        if g:
            gist = g.group(1).strip()
        takeaway = re.split(r"\n\s*IMPACT:", out)[0].strip()
        gist = gist or takeaway[:140]
        t = lang.say(self.config)
        text = t(*sight.w2(self.config, "note_event_line", basename=f["basename"], reason=reason_hers)) + " " + takeaway
        self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "note_read", text, sal)
        idx = [e for e in self.index() if e.get("path") != f["path"]]
        idx.append({"path": f["path"], "basename": f["basename"], "date": self.clock.date_str(), "gist": gist})
        self.store.set("notes_read", idx[-self.config.notes.index_max:])
        already = set(self.store.get("vault_read_paths", []))
        already.add(f["path"])
        self.store.set("vault_read_paths", sorted(already))
        logger.log(f"[notes] read {f['basename']} ({reason_en}) s{sal}: {gist[:120]}")
        # what it did to her is hers, and it is asked for now rather than at
        # the next scene: the record it reads is written above, and the
        # director and the state read both a moment later
        if self.reflection is not None:
            try:
                self.reflection.after_reading(scene, sight.w(self.config, "reflect_why_note"), text)
            except Exception as e:
                logger.log(f"[reflect] not asked after the note: {type(e).__name__}: {e}")
        return {"basename": f["basename"], "takeaway": takeaway, "salience": sal, "gist": gist, "text": text}
