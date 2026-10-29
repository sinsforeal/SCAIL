"""Compile a person's private prior into the mechanisms a call actually reads.

    python tools/compile_type.py <key> [--dry-run] [--health typical] [--all]

The prior is four letters, a stack, a health setting and the contradictions
the record forces (`docs/type-compile.md` section 1). It lives in
`data/characters/types/<key>.json` for a character and in the author's type
file for somebody on the roster, and **no prompt ever reads either**. This
tool reads it with the compile table (`data/codebook/compile_v0.1.json`) and
writes three things:

- the DERIVED layer of her mechanisms file: one instance per code of her
  four cells, with the cell's trigger and suppressor, the frequency band the
  health setting leaves it at, and the wordings in the language the call
  that renders it is written in. The hand-written instances already in the
  file are kept exactly as they are and gain a `code` field from the loss
  ledger, or `code: null` with the ledger's reason;
- the two stress modes, as instances carrying the gauge reading that starts
  them -- one that begins when a gauge has sat above a line for a span of
  hours, one that begins when a gauge reaches its end;
- her gauge baselines with a line each saying where the number came from,
  and the markers block in her type file.

**The four letters, the function names and the position words go into no
output.** Every string this writes into a mechanisms file or a type file's
markers is behavioural; `tools/cast_mechanisms_test.py` greps for the
vocabulary and fails on a hit.

It refuses when the compile table's version and the codebook's differ, and
when a person's stack reaches a cell the table has no wordings for: an empty
line rendered into somebody's prompt is worse than a refusal that names the
cell.

No model call, no save, no network.
"""
import argparse
import copy
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

VERSION = "0.1"
TABLE = os.path.join("data", "codebook", "compile_v%s.json" % VERSION)
CODEBOOK = os.path.join("data", "codebook", "v%s.json" % VERSION)
COMPANION = os.path.join("data", "codebook", "v%s_theory.json" % VERSION)
LEDGER = os.path.join("data", "codebook", "loss_ledger.json")
CHARACTER_TYPES = os.path.join("data", "characters", "types")

BANDS = ["high", "medium", "low", "rare"]
CAST_READERS = ["cast_turn", "cast_beat", "cast_day"]
OWN_CALLS = ["cast_turn", "cast_beat"]

# The markers a counting tool can actually see (`tools/cast_type_test.py`,
# STRUCTURAL). A marker outside this vocabulary and outside Japanese counts
# zero for ever and reads as absent behaviour, so the compile refuses to
# write one.
COUNTABLE = ("opens the exchange", "answers last", "asks a question back", "names a time",
             "sends more than one message in a row", "one-word reply", "a long message",
             "sends a stamp", "sends a picture")


def load(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, doc):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")


def band_step(band, steps):
    """A band moved `steps` places toward the frequent end; the ends hold."""
    return BANDS[max(0, min(len(BANDS) - 1, BANDS.index(band) - steps))]


def phrase(code):
    """The id's own phrase, in words, for a human reading the file. Never
    rendered into a call: the `name` field is the author's."""
    return code.split(".", 1)[1].replace("-", " ")


class Compiler:
    def __init__(self, config):
        self.config = config
        self.table = load(TABLE)
        if self.table.get("version") != VERSION or self.table.get("codebook_version") != VERSION:
            raise SystemExit("the compile table is version %r against codebook %r; this tool is "
                             "written for %s, and a mismatch would bind instances to ids from "
                             "another instrument"
                             % (self.table.get("version"), self.table.get("codebook_version"), VERSION))
        book = load(CODEBOOK)
        if book.get("version") != VERSION:
            raise SystemExit("the codebook is version %r, not %s" % (book.get("version"), VERSION))
        self.entries = {e["id"]: e for e in book["entries"]}
        if os.path.isfile(COMPANION):
            comp = load(COMPANION)
            if comp.get("version") != VERSION:
                raise SystemExit("the companion codebook is version %r, not %s"
                                 % (comp.get("version"), VERSION))
            for e in comp.get("entries") or []:
                self.entries[e["id"]] = e
        self.ledger = load(LEDGER) if os.path.isfile(LEDGER) else {}
        self.cells = {(c["function"], c["position"]): c for c in self.table["cells"]}
        self.mech_dir = str(getattr(config.cast, "mechanisms_dir", "") or "data/cast_mechanisms")

    # ---------------------------------------------------------------- the prior

    def prior_for(self, key):
        """(prior, where it came from, whether she has a sheet of her own)."""
        p = os.path.join(CHARACTER_TYPES, "%s.json" % key.lower())
        if os.path.isfile(p):
            return load(p), p, True
        types = load(str(getattr(self.config.cast, "types_file", "") or ""))
        types = types.get("types", types)
        if key in types:
            return types[key], "the author's type file", False
        raise SystemExit("no prior for %r: neither %s nor a row in the author's type file" % (key, p))

    def stack_of(self, prior):
        letters = str(prior.get("type") or "").upper()
        stack = self.table["stacks"].get(letters)
        if not stack:
            raise SystemExit("the prior's four letters (%r) name no stack in the table" % letters)
        return letters, stack

    # ------------------------------------------------------------- the four cells

    def cells_for(self, stack):
        out = []
        for fn, position in zip(stack, self.table["positions"]):
            c = self.cells.get((fn, position))
            if not c:
                raise SystemExit("the table has no cell for %s/%s" % (fn, position))
            out.append(c)
        return out

    @staticmethod
    def renderable(cell):
        return all(r.get("response") and (r.get("ja") or {}).get("response") for r in cell["codes"])

    # ------------------------------------------------------------ the instances

    def instance(self, who, cell, row, health, readers):
        code = row["code"]
        entry = self.entries.get(code)
        if not entry:
            raise SystemExit("%s names %s, which is in neither codebook" % (who, code))
        steps = {"auxiliary": health["auxiliary_band_steps"],
                 "tertiary": health["tertiary_band_steps"],
                 "inferior": health["inferior_band_steps"]}.get(cell["position"], 0)
        band = band_step(row["band"], steps)
        ja = dict(row.get("ja") or {})
        if cell.get("suppressor_ja"):
            ja["unless"] = cell["suppressor_ja"]
        return {
            "id": "%s.derived.%s" % (who, code),
            "name": phrase(code),
            "code": code,
            "tier": "derived",
            "trigger": row.get("trigger") or cell["trigger_template"],
            "suppressor": cell["suppressor_template"],
            "function": entry["function"],
            "variation": list(entry.get("variation") or []),
            "frequency": band,
            "class": "hers",
            "en": {"trigger": row.get("trigger") or cell["trigger_template"],
                   "response": row.get("response") or "",
                   "unless": cell["suppressor_template"]},
            "ja": ja,
            "readers": list(readers if band in ("high", "medium") else
                            [r for r in readers if r in OWN_CALLS + ["persona"]]),
        }

    def mode_instance(self, who, cell, health, readers):
        """The loop or the grip: one instance carrying the gauge reading that
        starts it. The renderer turns a gauge reading into a conditional in
        the block, and puts the mode's own line in front of the call only
        while the reading holds."""
        m = cell["mode"]
        kind = m["kind"]
        rows = cell["codes"][:2]
        gt = {"mode": kind, "gauge": m["gauge"]}
        if kind == "loop":
            gt["at"] = m["at"] + health["loop_at_delta"]
            gt["hours"] = max(1, m["hours"] + health["loop_hours_delta"])
        else:
            gt["at"] = m["at"] + health["grip_at_delta"]
            if m.get("floor") is not None:
                gt["floor"] = m["floor"] + health["grip_at_delta"]
        steps = health["tertiary_band_steps"] if kind == "loop" else health["inferior_band_steps"]
        return {
            "id": "%s.%s" % (who, kind),
            "name": "what happens when it has been like this for a long time" if kind == "loop"
                    else "what happens at the very end of it",
            "code": rows[0]["code"],
            "tier": "derived",
            "gauge_trigger": gt,
            "trigger": cell["trigger_template"],
            "suppressor": cell["suppressor_template"],
            "function": self.entries[rows[0]["code"]]["function"],
            "variation": [r.get("response") or phrase(r["code"]) for r in cell["codes"]],
            "frequency": band_step("low" if kind == "loop" else "rare", steps),
            "class": "hers",
            "en": {"trigger": cell["trigger_template"],
                   "response": "; ".join(r.get("response") or "" for r in rows).strip("; "),
                   "unless": cell["suppressor_template"]},
            "ja": {"trigger": rows[0]["ja"]["trigger"],
                   "response": "".join((r["ja"]["response"] for r in rows)),
                   "unless": cell.get("suppressor_ja") or ""},
            "line": m["line"],
            "line_ja": m["line_ja"],
            # a mode is about the person who is in it, so it reaches the two
            # calls where she speaks for herself and never the day planner,
            # which writes for everybody at once
            "readers": [r for r in readers if r in OWN_CALLS + ["persona"]],
        }

    # ------------------------------------------------------------- the baselines

    def baselines(self, stack, health_name, sheet):
        """Her gauge baselines with a line each saying where the number came
        from. The deltas belong to the dominant function; a healthy setting
        moves the same gauges half as far the other way. A person with no
        sheet gets the deltas alone, for the promotion tool to apply."""
        table = self.table["health"]["baselines_unhealthy"].get(stack[0], {})
        sign = {"unhealthy": 1.0, "typical": 0.0, "healthy": -0.5}[health_name]
        have = ((sheet or {}).get("temperament") or {}).get("gauge_baselines") or {}
        out = {}
        for gauge, delta in sorted(table.items()):
            d = int(round(delta * sign))
            basis = ("the %s setting leaves %s where the sheet rests it; it is one of the "
                     "gauges a person who runs on this default would rest differently on at "
                     "another setting" % (health_name, gauge) if not d else
                     "the %s setting for somebody who runs on this default moves %s %+d from "
                     "where the sheet rests it" % (health_name, gauge, d))
            row = {"delta": d, "sheet": have.get(gauge), "gauge_basis": basis}
            if have.get(gauge) is not None:
                row["proposed"] = max(0, min(100, int(have[gauge]) + d))
            out[gauge] = row
        return out

    # --------------------------------------------------------------- the markers

    def markers(self, stack):
        """Per axis, per pole, from the first two cells her stack selects.

        Only the first two, and the first letter from the first alone. The
        four letters are a name for the top two of the stack: what the third
        and the fourth do is the two stress modes, and those are measured by
        whether a mode fires at the gauge reading the compile set, not by
        counting markers. Emitting all four cells' markers put common
        structural facts on BOTH poles of an axis and moved two people's
        counts off the pole they were written as, which is a fault of the
        marker set rather than a finding about them.

        So a derived marker only ever speaks for the pole the prior names,
        and a marker count over them is not evidence FOR the prior: it can
        show that the described behaviour is present or absent, and nothing
        further (`docs/cast-mechanisms.md`, what the measurement cannot
        show).

        A marker outside what the counting tool can see is refused here
        rather than counting zero for ever in the record.
        """
        poles = self.table["function_poles"]
        out = {}
        for i, (fn, position) in enumerate(zip(stack, self.table["positions"])):
            if i > 1:
                break
            cell = self.cells[(fn, position)]
            for axis, pole in poles[fn].items():
                if axis == "EI" and i != 0:
                    continue        # the first letter is the first function's alone
                for m in cell["markers"]:
                    if m.isascii() and m not in COUNTABLE:
                        raise SystemExit("the %s/%s cell names a marker nothing can count: %r"
                                         % (fn, position, m))
                    out.setdefault(axis, {}).setdefault(pole, [])
                    if m not in out[axis][pole]:
                        out[axis][pole].append(m)
        return out

    # ------------------------------------------------------------------ the codes

    def code_for_authored(self, m):
        """The code a hand-written instance binds to, from the loss ledger and
        never from the file itself: the ledger is where the mapping from a
        real mechanism to an entry lives, so a re-compile after the ledger
        moves picks the move up. A person on the roster is found by her
        instance's id; the first character's bible entries carry the row of
        the ledger they came from, because the bible has no ids of its own."""
        for row in (self.ledger.get("cast_mechanisms") or []):
            if row.get("id") == m.get("id"):
                covered = row.get("covered_by") or []
                if covered:
                    return covered[0], covered[1:], ""
                return None, [], row.get("lost") or "the ledger sends it nowhere"
        ref = m.get("ledger_row")
        if ref:
            for row in (self.ledger.get("first_character_bible") or []):
                if row.get("what") == ref:
                    covered = row.get("covered_by") or []
                    if covered:
                        return covered[0], covered[1:], ""
                    return None, [], row.get("lost") or "the ledger sends it nowhere"
            return None, [], "the ledger has no row reading %r" % ref
        return None, [], "no row in the loss ledger"

    # ---------------------------------------------------------------- the compile

    def run(self, key, health_name=None, dry=False):
        prior, where, has_sheet = self.prior_for(key)
        letters, stack = self.stack_of(prior)
        cells = self.cells_for(stack)
        missing = [c for c in cells if not self.renderable(c)]
        if missing:
            raise SystemExit("the table has no wordings for %d of this stack's cells: %s. Write "
                             "them in data/retired/20260906_compile/build_compile_table.py and "
                             "run it again."
                             % (len(missing), ", ".join("%s/%s" % (c["function"], c["position"])
                                                        for c in missing)))
        path = os.path.join(self.mech_dir, "%s.json" % key)
        doc = load(path) if os.path.isfile(path) else {"who": key, "mechanisms": []}
        health_name = (health_name or (doc.get("compiled") or {}).get("health")
                       or prior.get("health") or "typical")
        if health_name not in ("healthy", "typical", "unhealthy"):
            raise SystemExit("the health setting %r is none of healthy, typical, unhealthy" % health_name)
        health = self.table["health"][health_name]

        readers = ["persona"] if has_sheet else list(CAST_READERS)
        who = key.split("-")[0].lower()

        authored = []
        for m in doc.get("mechanisms") or []:
            if str(m.get("tier")) == "derived":
                continue
            m = copy.deepcopy(m)
            code, also, reason = self.code_for_authored(m)
            m["code"] = code
            if also:
                m["codes_also"] = also
            elif "codes_also" in m:
                del m["codes_also"]
            if code is None:
                m["code_reason"] = reason
            elif "code_reason" in m:
                del m["code_reason"]
            authored.append(m)

        derived = []
        for cell in cells:
            for row in cell["codes"]:
                derived.append(self.instance(who, cell, row, health, readers))
        for cell in cells:
            if cell.get("mode"):
                derived.append(self.mode_instance(who, cell, health, readers))

        # one instance per code: a code that two of her cells name is one
        # behaviour of hers, at the higher of the two bands
        seen = {}
        merged = []
        for inst in derived:
            hit = seen.get(inst["code"])
            if hit is not None and not inst.get("gauge_trigger"):
                if BANDS.index(inst["frequency"]) < BANDS.index(hit["frequency"]):
                    hit["frequency"] = inst["frequency"]
                continue
            if not inst.get("gauge_trigger"):
                seen[inst["code"]] = inst
            merged.append(inst)

        doc["who"] = doc.get("who") or key
        doc["mechanisms"] = authored + merged
        doc["baselines"] = self.baselines(stack, health_name, load("data/characters/%s.json" % key.lower())
                                          if has_sheet and os.path.isfile("data/characters/%s.json" % key.lower())
                                          else None)
        doc["compiled"] = {
            "table_version": VERSION,
            "codebook_version": VERSION,
            "health": health_name,
            "prior": where,
            "_note": "the derived instances were written from the prior and the compile table; "
                     "the authored ones are the author's and were only given their codes. "
                     "Nothing here names the prior's own vocabulary.",
        }
        marks = self.markers(stack)

        if dry:
            print("  would write %s: %d authored, %d derived (%d of them a mode)"
                  % (path, len(authored), len(merged),
                     len([m for m in merged if m.get("gauge_trigger")])))
        else:
            save(path, doc)
            self.write_markers(key, has_sheet, marks)
        return {"key": key, "letters": letters, "health": health_name, "path": path,
                "authored": len(authored), "derived": len(merged),
                "coded": len([m for m in authored if m.get("code")]),
                "uncoded": len([m for m in authored if not m.get("code")]),
                "modes": [m["gauge_trigger"] for m in merged if m.get("gauge_trigger")],
                "markers": marks}

    def write_markers(self, key, has_sheet, marks):
        """Into her type file, beside the author's own markers rather than
        over them: a hand-written marker is the author's operationalisation
        and this adds to it."""
        if has_sheet:
            p = os.path.join(CHARACTER_TYPES, "%s.json" % key.lower())
            doc = load(p)
            doc["markers"] = self._merge_markers(doc.get("markers") or {}, marks)
            save(p, doc)
            return
        p = str(getattr(self.config.cast, "types_file", "") or "")
        doc = load(p)
        row = doc["types"][key]
        row["markers"] = self._merge_markers(row.get("markers") or {}, marks)
        save(p, doc)

    NOTE = ("Some of these were compiled from the prior rather than written by hand, and a "
            "compiled one only ever speaks for the pole the prior already names -- so a count "
            "over this block agrees with the author more than it did before, by construction. "
            "It can show that a described behaviour is present or absent in the record. It is "
            "not evidence that anybody is a type, and it never was.")

    @staticmethod
    def _merge_markers(have, new):
        out = copy.deepcopy(have)
        out["_note"] = Compiler.NOTE
        for axis, poles in new.items():
            if not isinstance(poles, dict):
                continue
            for pole, items in poles.items():
                cur = out.setdefault(axis, {}).setdefault(pole, [])
                for m in items:
                    if m not in cur:
                        cur.append(m)
        return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("key", nargs="?", default="", help="a roster key, or a character id")
    ap.add_argument("--all", action="store_true", help="everybody in the author's type file")
    ap.add_argument("--health", default="", choices=["", "healthy", "typical", "unhealthy"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()

    import logger
    logger.log = lambda m, to_console=True: None
    from config import Config
    cfg = Config(args.config)
    c = Compiler(cfg)

    keys = [args.key] if args.key else []
    if args.all:
        types = load(str(getattr(cfg.cast, "types_file", "") or ""))
        keys = [k for k in types.get("types", types) if not str(k).startswith("_")]
    if not keys:
        ap.error("name a key, or --all")

    print("compile table %s, codebook %s" % (VERSION, VERSION))
    for k in keys:
        r = c.run(k, args.health or None, args.dry_run)
        print("  %-12s %s, %d authored (%d coded, %d not), %d derived, modes on %s"
              % (r["key"], r["health"], r["authored"], r["coded"], r["uncoded"], r["derived"],
                 ", ".join("%s %s%d%s" % (m["mode"], "at ", m["at"],
                                          " for %dh" % m["hours"] if m.get("hours") else "")
                           for m in r["modes"]) or "nothing"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
