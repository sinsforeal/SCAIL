"""Her flat and her week as things with a STATE, moved by the director under a
budget, met by her as facts.

The director for a character with no world of her own had nothing to move.
Her day is a plan of blocks and her flat is prose, and prose does not change
state, so for three hours it wrote the same green laptop and then, starved,
started writing her thoughts instead -- which she typed. The one thing a
second agent adds to fidelity here is time: something has to make the hours
between his messages have happened, so that when he comes back there is a
fact he did not put there and she did not decide on.

So this is the small piece of world she does have, made stateful. The seed
(`household.file`) lists her objects and, for each, the states it can be in
and the moves between them -- every one taken from her home file, which is
every one something she said on air. The director is shown the state and the
allowed moves, and returns `household_changes`; code checks the object and
the state exist, holds the day's budget (`household.incidents_per_day`),
applies the move, and writes it into the record as an event. She meets the
state in her situation as one line of facts, in her language. A thought
cannot be false; a dead tube can.

kv `household`: {"objects": {id: {"state", "since"}}, "incidents": [{"date", "ts", "object", "to", "note"}]}.
"""

import io
import json
import os

import logger


class Household:
    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock
        self.seed = {}
        self._load_seed()

    # ---------------- the seed and the state ----------------

    def _load_seed(self):
        path = str(getattr(self.config.household, "file", "") or "")
        if not path or not os.path.exists(path):
            logger.log(f"[household] no seed file at {path!r}; nothing to move")
            return
        try:
            data = json.load(io.open(path, encoding="utf-8"))
            self.seed = {o["id"]: o for o in data.get("objects", []) if o.get("id")}
        except Exception as e:
            logger.log(f"[household] seed not read: {type(e).__name__}")
            self.seed = {}

    def _kv(self):
        d = self.store.get("household", None)
        if not isinstance(d, dict) or "objects" not in d:
            d = {"objects": {}, "incidents": []}
        # every seeded object has a state; a new object in the seed starts
        # at the seed's state, an old one keeps what the record says
        changed = False
        for oid, o in self.seed.items():
            if oid not in d["objects"]:
                d["objects"][oid] = {"state": o.get("state", ""), "since": self.clock.now_ts()}
                changed = True
        if changed:
            self.store.set("household", d)
        return d

    def incidents_today(self):
        today = self.clock.date_str()
        return [i for i in self._kv().get("incidents", []) if i.get("date") == today]

    # ---------------- for the director ----------------

    def director_text(self):
        """The state as it stands, and what may happen to it. English: the
        machine talking to the machine."""
        if not self.seed:
            return ""
        d = self._kv()
        c = self.config.household
        budget = int(getattr(c, "incidents_per_day", 2) or 2)
        used = len(self.incidents_today())
        lines = ["HER HOUSEHOLD, AS IT STANDS (facts; each holds until a move changes it):"]
        for oid, o in self.seed.items():
            st = d["objects"].get(oid, {}).get("state", o.get("state", ""))
            since = d["objects"].get(oid, {}).get("since")
            desc = (o.get("states", {}).get(st) or {}).get("en", st)
            when = ""
            try:
                if since:
                    hrs = (self.clock.now_ts() - float(since)) / 3600.0
                    when = f" (since {self.clock.to_char(float(since)).strftime('%a %H:%M')})" if hrs < 48 else f" (for {int(hrs // 24)} days)"
            except Exception:
                when = ""
            lines.append(f"- {oid}: {o.get('name', oid)} -- {desc}{when}")
        lines.append(f"MOVES YOU MAY MAKE (object -> state: how it happens). Budget today: {budget}, used: {used}. "
                     f"Most ticks move nothing. A move is a fact with a consequence, from her plan's current block or her own habits, never a thought:")
        for oid, o in self.seed.items():
            cur = d["objects"].get(oid, {}).get("state", "")
            for m in o.get("moves", []):
                if m.get("to") == cur:
                    continue
                lines.append(f"- {oid} -> {m['to']}: {m.get('how', '')}")
        return "\n".join(lines) + "\n"

    def apply(self, changes):
        """The director's `household_changes`, checked and applied under the
        budget. Returns the events written, as (text, salience)."""
        if not self.seed or not isinstance(changes, list):
            return []
        c = self.config.household
        budget = int(getattr(c, "incidents_per_day", 2) or 2)
        d = self._kv()
        used = len(self.incidents_today())
        out = []
        for ch in changes:
            if not isinstance(ch, dict):
                continue
            oid = str(ch.get("object", "")).strip()
            to = str(ch.get("state", "")).strip()
            note = " ".join(str(ch.get("note", "")).split())[:160]
            o = self.seed.get(oid)
            if not o:
                logger.log(f"[household] no such object {oid!r}; ignored")
                continue
            move = next((m for m in o.get("moves", []) if m.get("to") == to), None)
            if not move or to == d["objects"].get(oid, {}).get("state"):
                logger.log(f"[household] {oid}: no move to {to!r} from {d['objects'].get(oid, {}).get('state')!r}; ignored")
                continue
            if used >= budget:
                logger.log(f"[household] budget spent ({used}/{budget}); {oid} -> {to} not applied")
                break
            d["objects"][oid] = {"state": to, "since": self.clock.now_ts()}
            text = f"{o.get('name', oid)}: {note or move.get('how', to)}"
            sal = int(move.get("salience", 2) or 2)
            d.setdefault("incidents", []).append({"date": self.clock.date_str(), "ts": self.clock.now_ts(),
                                                  "object": oid, "to": to, "note": text})
            d["incidents"] = d["incidents"][-200:]
            used += 1
            out.append((text, sal))
            logger.log(f"[household] {oid} -> {to}: {text}")
        if out:
            self.store.set("household", d)
        return out

    # ---------------- for her ----------------

    def situation_line(self, ja=False):
        """One line of facts about her own flat and week, in her language."""
        if not self.seed:
            return ""
        d = self._kv()
        cap = int(getattr(self.config.household, "situation_max_objects", 8) or 8)
        bits = []
        for oid, o in list(self.seed.items())[:cap]:
            st = d["objects"].get(oid, {}).get("state", o.get("state", ""))
            s = o.get("states", {}).get(st) or {}
            name = o.get("ja") if ja else o.get("name", oid)
            desc = s.get("ja" if ja else "en", st)
            bits.append(f"{name}: {desc}")
        head = "身の回りの事実（本当のこと。報告するものではなく、ただそうなっている）: " if ja else \
               "your flat and your week, as they stand (facts, not things to report; they are simply so): "
        return head + ("／" if ja else "; ").join(bits)
