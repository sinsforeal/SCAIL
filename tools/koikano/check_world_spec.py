"""Check the koikano world spec and the light cast cards (design 6 stage 0).

    python tools/koikano/check_world_spec.py [--record DIR] [--require-record]

Checks, on characters/momoka/world/koikano_world.json and characters/*/card.json:
  1. Every fact has a receipt (scene:line) that exists in the record, and its anchor
     string occurs in that line (or its bg id belongs to the named place, or the
     "absent" pattern does not match). Facts of kind "parameter" (a tuning number,
     with a basis) and "computed" (a statistic re-derivable from the corpus) may have
     no receipt; nothing else may.
  2. No age, grade (年生, 歳, 才 as an age), birthplace or named parent in any string.
     A parent word appears only in a fact with kind "parent" and "named": false.
  3. Every place id exists in sim/scene.py PLACE_BACKGROUNDS and its bg matches.

The record is stage_state.jsonl of the koikano corpus. When the corpus is not on this
machine the receipt text check is skipped and said so (exit 0), unless --require-record.
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

DEFAULT_RECORD = os.environ.get(
    "KOIKANO_RECORD", r"F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work")
SPEC = os.path.join(ROOT, "characters", "momoka", "world", "koikano_world.json")
RID = re.compile(r"^[a-z]?\d\d_\d\d:\d{4}$")

AGE = re.compile(r"[0-9０-９一二三四五六七八九十]+\s*(歳|才)|年生|\bage\b|\bgrade\b|years? old|[0-9]+歳|歳")
BIRTH = re.compile(r"出身|生まれ|生誕|誕生日|birthplace|born in|hometown")
PARENT = re.compile(r"父|母|パパ|ママ|お父さん|お母さん|奥様|ご主人様|parent|mother|father")
NAMED_PARENT = re.compile(r"(千代田|十川|七瀬|九重|榎本|小野坂|宮国|百花|真優|千奈|真里亜|アリス)(さん|様|氏)?の?(父|母|パパ|ママ|お父さん|お母さん)")
PARENT_NAME_FIELD = re.compile(r"parent.*name|name.*parent", re.I)


def load_record(record_dir):
    path = os.path.join(record_dir, "stage_state.jsonl")
    if not os.path.isfile(path):
        return None
    idx = {}
    with open(path, encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            bg = ((d.get("stage") or {}).get("bg") or {}).get("id") or ""
            idx["%s:%04d" % (d["scene"], d["source_line"])] = (d.get("text") or "", bg)
    return idx


def places_table():
    from sim.scene import PLACE_BACKGROUNDS
    return PLACE_BACKGROUNDS


def walk(node, path=()):
    yield path, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, path + (i,))


def receipts_of(d):
    out = []
    if isinstance(d.get("receipt"), dict):
        out.append(d["receipt"])
    for r in d.get("receipts") or []:
        out.append(r)
    return out


def check_file(path, record, errors, stats):
    name = os.path.relpath(path, ROOT).replace("\\", "/")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    pb = places_table()
    bg2place = {v[2:4]: k for k, v in pb.items()}

    for p, node in walk(data):
        where = name + ":" + ".".join(str(x) for x in p)
        key = p[-1] if p else ""

        # 3. place ids
        if key in ("place", "home") and isinstance(node, str):
            stats["place_refs"] += 1
            if node not in pb:
                errors.append("%s: unknown place id %r" % (where, node))
        if key == "place_ids" and isinstance(node, list):
            for x in node:
                stats["place_refs"] += 1
                if x not in pb:
                    errors.append("%s: unknown place id %r" % (where, x))
        if isinstance(node, dict) and "place" in node and "bg" in node and isinstance(node.get("bg"), str) and node["place"] in pb:
            if pb[node["place"]] != node["bg"]:
                errors.append("%s: place %s has bg %s, scene.py says %s" % (where, node["place"], node["bg"], pb[node["place"]]))

        # facts and receipts
        if isinstance(node, dict) and ("fact" in node or ("text" in node and "pattern" in node) or "receipts" in node or "receipt" in node) \
                and not ("form" in node and "n" in node and "receipt" not in node):
            rs = receipts_of(node)
            kind = node.get("kind")
            if "fact" in node or "text" in node:
                stats["facts"] += 1
                if not rs and kind not in ("parameter", "computed", "hole"):
                    errors.append("%s: fact without a receipt" % where)
                if kind == "parameter" and not node.get("basis"):
                    errors.append("%s: parameter without a basis" % where)
            for r in rs:
                stats["receipts"] += 1
                rid = r.get("id")
                if not rid or not RID.match(str(rid)):
                    errors.append("%s: bad receipt id %r" % (where, rid))
                    continue
                if record is None:
                    stats["unverified"] += 1
                    continue
                hit = record.get(rid)
                if hit is None:
                    errors.append("%s: receipt %s is not in the record" % (where, rid))
                    continue
                text, bg = hit
                if r.get("anchor") and r["anchor"] not in text:
                    errors.append("%s: anchor %r not in %s" % (where, r["anchor"], rid))
                if r.get("bg"):
                    if not bg.startswith(r["bg"][:4]):
                        errors.append("%s: %s has bg %s, receipt says %s" % (where, rid, bg, r["bg"]))
                if r.get("absent") and re.search(r["absent"], text):
                    errors.append("%s: %s matches the absent pattern" % (where, rid))
                if not (r.get("anchor") or r.get("bg") or r.get("absent")):
                    errors.append("%s: receipt %s has no anchor, bg or absent test" % (where, rid))

        # 2. forbidden words in strings (not the receipt anchors: those are record text
        # and are checked above for the same words below)
        if isinstance(node, str):
            if key == "anchor" and AGE.search(node):
                errors.append("%s: anchor carries an age or grade word %r" % (where, node))
                continue
            if key in ("anchor", "pattern", "absent", "id", "bg"):
                continue
            # notes, holes and rule statements may name what is forbidden
            if any(isinstance(x, str) and (x.startswith("_") or x in ("holes", "rules")) for x in p):
                continue
            if AGE.search(node):
                errors.append("%s: age or grade word in %r" % (where, node[:60]))
            if BIRTH.search(node):
                errors.append("%s: birthplace word in %r" % (where, node[:60]))
            if PARENT.search(node):
                stats["parent_strings"] += 1
                if NAMED_PARENT.search(node):
                    errors.append("%s: named parent in %r" % (where, node[:60]))
    # parent words only in kind parent facts
    for p, node in walk(data):
        if isinstance(node, dict) and node.get("kind") == "parent":
            if node.get("named") is not False:
                errors.append("%s:%s: parent fact must say named false" % (name, ".".join(str(x) for x in p)))
    return data


def parent_scope(data, name, errors):
    """Parent words (other than in a kind parent fact, a hole or a rule line) are errors."""
    for p, node in walk(data):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str) and k in ("fact", "text") and PARENT.search(v) and node.get("kind") not in ("parent", "hole", "rule"):
                    errors.append("%s:%s: parent word outside a parent fact: %r" % (name, ".".join(str(x) for x in p + (k,)), v[:50]))


def run(record_dir=DEFAULT_RECORD, require_record=False, spec=SPEC, cards=None):
    errors = []
    stats = {"facts": 0, "receipts": 0, "unverified": 0, "place_refs": 0, "parent_strings": 0}
    record = load_record(record_dir)
    if record is None and require_record:
        errors.append("record not found at %s" % record_dir)
    paths = []
    if os.path.isfile(spec):
        paths.append(spec)
    else:
        errors.append("missing %s" % spec)
    paths += sorted(cards if cards is not None else glob.glob(os.path.join(ROOT, "characters", "*", "card.json")))
    summary = {}
    for p in paths:
        data = check_file(p, record, errors, stats)
        parent_scope(data, os.path.basename(os.path.dirname(p)), errors)
        if p == spec:
            summary = {
                "places": len(data.get("places", [])),
                "anchors": len(data.get("anchors", [])),
                "rows": len(data.get("rows", {})),
            }
    summary.update(stats)
    summary["cards"] = len(paths) - (1 if os.path.isfile(spec) else 0)
    summary["record"] = "checked" if record is not None else "absent: receipt text not verified"
    return errors, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default=DEFAULT_RECORD)
    ap.add_argument("--require-record", action="store_true")
    a = ap.parse_args()
    errors, s = run(a.record, a.require_record)
    print("world spec: %d places, %d anchors, %d rows, %d cards, %d facts, %d receipts, record %s" % (
        s.get("places", 0), s.get("anchors", 0), s.get("rows", 0), s.get("cards", 0), s["facts"], s["receipts"], s["record"]))
    for e in errors:
        print("  FAIL " + e)
    print("world spec: %s" % ("%d problem(s)" % len(errors) if errors else "ok"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
