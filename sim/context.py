import io
import os
import copy
import logger

# Her prompt, opened up. Everything she is told about herself and about him
# is assembled from a dozen stores and then thrown away after the call, so
# until now the only visible trace was a line of token counts. This reads the
# prompt back exactly as the persona model would receive it, and lets the
# parts that are stored rather than computed be corrected in place -- a fact
# that came out wrong, a claim she never made, a diary entry about a photo she
# cannot send. Nothing here calls a model.
#
# Sections that are files (bible, style) or another program's data (his anime
# shelf) are shown and not edited: the persona files are edited on disk, and
# the shelf belongs to tools/mal_history.py.

# section -> (kv key, the field inside each item that is the text)
_KV_LISTS = {
    "claims": ("self_claims", "text"),
    "diet": ("media_diet", "text"),
    "reflect": ("reflections", "thought"),
    "diary": ("diary", "text"),
    "weekly": ("weekly_self", "text"),
    "notes": ("notes_read", "gist"),
}

_READ_ONLY = {"beliefs": "her picture of him; /beliefs shows it, data/beliefs.json seeds a fresh save",
              "selfbeliefs": "what she has decided about herself; /self shows it, data/self_beliefs.json seeds a fresh save",
              "spiral": "what she is going over; /spiral shows it",
              "rupture": "what is broken between them and what never got mended; /rupture shows it",
              "sentiment": "what these people are to her; /sentiment shows it",
              "charged": "what she is sitting on; /ick shows it",
              "selfmem": "her own life; /remember shows it",
              "bible": "prompts/bible.md on disk",
              "style": "prompts/style.md on disk",
              "shelf": "his MAL list, written by tools/mal_history.py"}

# the order the model receives them in: the persona's table, not a copy of it
from persona import sections as _sections
from persona.sections import ORDER as _ORDER
from sim import sight as _sight


def _flat(text):
    return " ".join((text or "").split())


class ContextView:
    def __init__(self, config, store, clock, persona, memory, state, director=None, phone=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.persona = persona
        self.memory = memory
        self.state = state
        self.director = director
        self.phone = phone

    # ---------------- reading it back ----------------

    def snapshot(self, fit=True):
        """The prompt as it stands: the system sections, the literal history and
        the situation block. `fit` applies the same trimming a real call would,
        so what he reads is what she would be sent."""
        p = self.persona
        p._system(cue_text="")
        sections = copy.deepcopy(p._sections)
        history = p._history()
        scene = (self.director.current if self.director else None) or {}
        digest = self.phone.latest_digest() if self.phone else ""
        unread = self.store.unread_user_messages()
        situation = p._situation(scene, digest, unread, "")
        trimmed = []
        if fit and self.memory:
            sections, history, trimmed = self.memory.fit(sections, history, situation)
        carried = _sections.carried(sections, p.t(*_sight.w2(p.config, "facts_head")))
        return {"sections": sections, "history": history, "situation": situation,
                "trimmed": trimmed, "system": p._assemble(sections), "carried": carried}

    def overview(self):
        snap = self.snapshot()
        lines = []
        tok = self.memory.tokens if self.memory else (lambda t: len(t or "") // 4)
        for name in _ORDER:
            text = snap["sections"].get(name) or ""
            if not text:
                continue
            n = self.count(name)
            if name in _READ_ONLY:
                where = "read-only"
            elif n is None:
                where = "computed"
            else:
                live = _flat(text)
                here = sum(1 for pr in self.probes(name) if pr and _flat(pr)[:60] in live)
                where = f"{here} of {n} stored in it"
            lines.append(f"  {name:10s} {tok(text):6d} tok  {len(text):7d} ch  {where}")
        h = sum(tok(m["content"]) for m in snap["history"])
        lines.append(f"  {'history':10s} {h:6d} tok  {len(snap['history']):7d} turns  /context msg")
        lines.append(f"  {'situation':10s} {tok(snap['situation']):6d} tok  {len(snap['situation']):7d} ch  computed every call")
        head = self.memory.report() if self.memory else ""
        tail = ("\ntrimmed to fit: " + ", ".join(snap["trimmed"])) if snap["trimmed"] else ""
        return (head + "\n\nwhat is in it right now:\n" + "\n".join(lines) + tail
                + "\n\n/context <section> to read it, /context full for the whole prompt as a file,"
                  "\n/context add|set|del <section> [n] <text> to change it, /context find <text>")

    def show(self, name):
        """One section, numbered where its items can be addressed."""
        if name in ("situation", "sit"):
            return self.snapshot()["situation"]
        if name in ("system", "prompt"):
            snap = self.snapshot()
            return snap["system"] + ("\n\n" + snap["carried"] if snap["carried"] else "")
        snap = self.snapshot()
        if name not in snap["sections"]:
            return f"no section '{name}'. sections: " + ", ".join(k for k in _ORDER if snap["sections"].get(k))
        items = self.items(name)
        if items is None:
            note = f"[{_READ_ONLY[name]}]\n" if name in _READ_ONLY else ""
            return note + (snap["sections"][name] or "(empty)")
        if not items:
            return f"{name}: nothing stored"
        # Stored is not the same as in front of her: the diary keeps ten
        # entries and shows two, facts below the fade line are not there at
        # all. A dot means this one is in the prompt she would be sent now.
        live = _flat(snap["sections"][name])
        probes = self.probes(name)
        shown = 0
        out = []
        for i, t in enumerate(items, 1):
            here = _flat(probes[i - 1])[:60] in live if probes[i - 1] else False
            shown += 1 if here else 0
            out.append(f"{'*' if here else ' '} {i:3d}. {t}")
        head = (f"{name}: {len(items)} stored, {shown} in her prompt now (*), "
                f"/context set {name} <n> <text> or /context del {name} <n>")
        return head + "\n" + "\n".join(out)

    def find(self, needle):
        """Where a thing appears in what she is told. The answer to 'why does
        she keep saying that' is usually one line in one section."""
        needle = (needle or "").strip().lower()
        if not needle:
            return "find what?"
        snap = self.snapshot()
        hits = []
        for name, text in snap["sections"].items():
            for line in (text or "").split("\n"):
                if needle in line.lower():
                    hits.append(f"[{name}] {line.strip()[:200]}")
        for line in snap["situation"].split("\n"):
            if needle in line.lower():
                hits.append(f"[situation] {line.strip()[:200]}")
        for m in snap["history"]:
            if needle in m["content"].lower():
                who = "him" if m["role"] == "user" else "her"
                hits.append(f"[history/{who}] {m['content'][:200]}")
        if not hits:
            return f"'{needle}' is nowhere in her prompt"
        return f"{len(hits)} place(s):\n" + "\n".join(hits[:60])

    def dump(self):
        """The whole prompt to a file, in the order the model receives it."""
        snap = self.snapshot()
        d = os.path.join("data", "context")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"prompt_{self.clock.now().strftime('%Y%m%d_%H%M%S')}.txt")
        parts = [f"# her prompt as of {self.clock.now():%Y-%m-%d %H:%M} her time"
                 f" / {self.clock.user_now():%Y-%m-%d %H:%M} his",
                 f"# trimmed to fit: {', '.join(snap['trimmed']) or 'nothing'}",
                 "", "=" * 70, "SYSTEM", "=" * 70, snap["system"], "", "=" * 70,
                 f"HISTORY ({len(snap['history'])} turns, as the model sees them)", "=" * 70]
        for m in snap["history"]:
            parts.append(f"--- {m['role'].upper()} ---")
            parts.append(m["content"])
        parts += ["", "=" * 70, "SITUATION (appended to the last turn)", "=" * 70, snap["situation"]]
        text = "\n".join(parts)
        io.open(path, "w", encoding="utf-8").write(text)
        return path, len(text), (self.memory.tokens(text) if self.memory else 0)

    # ---------------- the addressable items ----------------

    def items(self, name):
        """The section's items as plain strings, oldest first, 1-based when
        addressed. None means the section has no items to address."""
        if name == "facts":
            return [f"w{r['weight']} x{r['mentions']}  {r['fact']}" for r in self.memory.rows()]
        if name == "backstory":
            b = self.store.get("backstory", "")
            return [b] if b else []
        if name == "cast":
            out = []
            for who, r in sorted(self.state.relationships.items()):
                if who == "him":
                    continue
                bit = r.get("situation", "") or "(nothing)"
                if r.get("unresolved"):
                    bit += f" | between them: {r['unresolved']}"
                out.append(f"{who}: {bit}")
            return out
        if name in _KV_LISTS:
            key, field = _KV_LISTS[name]
            rows = self.store.get(key, []) or []
            out = []
            for r in rows:
                when = r.get("date") or (self.clock.to_char(r["ts"]).strftime("%m-%d") if r.get("ts") else "")
                head = f"{r.get('basename', '')} " if name == "notes" else ""
                out.append(f"{when} {head}{str(r.get(field, '')).strip()[:400]}".strip())
            return out
        return None

    def probes(self, name):
        """The bare text of each item, in the same order, for testing whether
        it made it into the prompt (the display strings carry weights and
        dates that the prompt does not)."""
        if name == "facts":
            return [r["fact"] for r in self.memory.rows()]
        if name == "backstory":
            b = self.store.get("backstory", "")
            return [b] if b else []
        if name == "cast":
            return [(self.state.relationships[w].get("situation") or "") for w in self._cast_names()]
        if name in _KV_LISTS:
            key, field = _KV_LISTS[name]
            return [str(r.get(field, "")) for r in (self.store.get(key, []) or [])]
        return []

    def count(self, name):
        it = self.items(name)
        return None if it is None else len(it)

    def _cast_names(self):
        return [w for w in sorted(self.state.relationships) if w != "him"]

    # ---------------- changing it ----------------

    def delete(self, name, n):
        items = self.items(name)
        if items is None:
            return f"'{name}' is not editable here ({_READ_ONLY.get(name, 'it is computed every call')})"
        if not 1 <= n <= len(items):
            return f"{name} has {len(items)} item(s)"
        gone = items[n - 1]
        if name == "facts":
            rid = self.memory.rows()[n - 1]["rid"]
            with self.store.lock:
                self.store.conn.execute("DELETE FROM user_facts WHERE rowid=?", (rid,))
                self.store.conn.commit()
        elif name == "backstory":
            self.store.set("backstory", "")
        elif name == "cast":
            who = self._cast_names()[n - 1]
            r = self.state.relationships[who]
            r["situation"] = ""
            r["unresolved"] = ""
            self.state.save()
        else:
            key, _ = _KV_LISTS[name]
            rows = self.store.get(key, []) or []
            rows.pop(n - 1)
            self.store.set(key, rows)
        logger.log(f"[context] he removed {name} #{n}: {gone[:120]}")
        return f"removed from {name}:\n{gone}"

    def replace(self, name, n, text):
        items = self.items(name)
        if items is None:
            return f"'{name}' is not editable here ({_READ_ONLY.get(name, 'it is computed every call')})"
        if not 1 <= n <= len(items):
            return f"{name} has {len(items)} item(s)"
        was = items[n - 1]
        if name == "facts":
            rid = self.memory.rows()[n - 1]["rid"]
            with self.store.lock:
                self.store.conn.execute("UPDATE user_facts SET fact=? WHERE rowid=?", (text, rid))
                self.store.conn.commit()
        elif name == "backstory":
            self.store.set("backstory", text)
        elif name == "cast":
            who = self._cast_names()[n - 1]
            self.state.relationships[who]["situation"] = text
            self.state.save()
        else:
            key, field = _KV_LISTS[name]
            rows = self.store.get(key, []) or []
            rows[n - 1][field] = text
            self.store.set(key, rows)
        logger.log(f"[context] he rewrote {name} #{n}: {text[:120]}")
        return f"{name} #{n} was:\n{was}\n\nnow:\n{text}"

    def add(self, name, text):
        if name == "facts":
            w = 3
            if text[:2].lower().startswith("w") and text[1:2].isdigit():
                w, text = int(text[1]), text[2:].strip()
            r = self.memory.add_fact(text, weight=w)
            logger.log(f"[context] he added a fact (w{w}, {r}): {text[:120]}")
            return f"fact {r} (weight {w}): {text}"
        if name == "backstory":
            return self.replace("backstory", 1, text) if self.store.get("backstory", "") else (
                self.store.set("backstory", text) or f"backstory set:\n{text}")
        if name == "cast":
            if ":" not in text:
                return "cast: <name>: <what is going on with them>"
            who, bit = text.split(":", 1)
            who = who.strip()
            if who not in self.state.relationships:
                return f"no such person. she knows: {', '.join(self._cast_names())}"
            self.state.relationships[who]["situation"] = bit.strip()
            self.state.save()
            logger.log(f"[context] he rewrote the cast sheet for {who}: {bit.strip()[:120]}")
            return f"{who}: {bit.strip()}"
        if name in _KV_LISTS:
            key, field = _KV_LISTS[name]
            rows = self.store.get(key, []) or []
            rows.append({"date": self.clock.date_str(), "ts": self.clock.now_ts(), field: text})
            self.store.set(key, rows)
            logger.log(f"[context] he added to {name}: {text[:120]}")
            return f"added to {name}:\n{text}"
        return f"'{name}' is not editable here ({_READ_ONLY.get(name, 'it is computed every call')})"

    # ---------------- the literal chat ----------------

    def messages(self, n=20):
        rows = self.store.recent_messages(n)
        out = [f"the last {len(rows)} turns as she holds them (id · time · who)."
               " /context msg set <id> <text>, /context msg del <id>"]
        for m in rows:
            stamp = self.clock.to_char(m["ts"]).strftime("%a %H:%M")
            who = "him" if m["role"] == "user" else "her"
            flag = "" if m["role"] == "user" else (" ·sent" if m.get("delivered_ts") else " ·NOT SENT")
            out.append(f"{m['id']:5d} {stamp} {who}{flag}: {m['text'][:220]}")
        return "\n".join(out)

    def message_set(self, mid, text):
        row = self.store.message_by_id(mid)
        if not row:
            return f"no message {mid}"
        self.store.update_message(mid, text)
        logger.log(f"[context] he rewrote message {mid}: {text[:120]}")
        return f"{mid} was:\n{row['text']}\n\nnow:\n{text}"

    def message_del(self, mid):
        row = self.store.message_by_id(mid)
        if not row:
            return f"no message {mid}"
        self.store.delete_message(mid)
        logger.log(f"[context] he deleted message {mid}: {row['text'][:120]}")
        return f"deleted {mid} ({'him' if row['role'] == 'user' else 'her'}):\n{row['text'][:400]}"
