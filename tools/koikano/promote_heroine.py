"""Turn a koikano heroine's bible bundle into a character bundle that can run.

    python tools/koikano/promote_heroine.py maria                  # into characters/maria/
    python tools/koikano/promote_heroine.py maria --root H:/x/chars # scratch root
    python tools/koikano/promote_heroine.py maria --check           # write nothing, say what is missing

The V3 path (`tools/promote_cast.py`) reads V3 roster files, which this tree
does not have. This is the adapter from what a koikano heroine HAS: her
`sheet.json` (existence answers, name, relationships), her `bible.json`, her
prompts, and the hand-authored sources beside this file under
`heroine_src/<key>/`:

    fills_src.json   token -> {"value", "receipt"}   (only what is hand-read)
    cast_src.json    her roster rows, each with a receipt from HER lines
    world_src.json   her rooms and her week, each with a receipt or "silent"

What the tool writes, all mechanical from those and from the sheet:

    bundle.json   the manifest: Momoka's resident shape with her own name,
                  prompt paths, quality caps, vn paths, existence answers
    fills.json    mechanical tokens (name forms) + fills_src.json, one value per
                  token the library's prompts leave open; a token with no source
                  is a hole and the tool refuses
    cast.json     roster rows from cast_src.json (role_id, name, aliases, note)
    world/        her view of the house, from world_src.json plus her week row
                  in characters/momoka/world/koikano_world.json

No model is called. Persona text is hand-built; this only assembles it.
"""
import argparse
import copy
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "tools", "koikano", "heroine_src")
CORPUS = "extracted_games/koikano"
SLUG_DIRS = {"mayu": "MAYU_真優", "sena": "SENA_千奈", "alice": "ALICE_アリス",
             "maria": "MARIA_真里亜", "chisa": "CHISA_知紗", "hikaru": "HIKARU_ひかる"}
# CA..CI: the character letters in the koikano expression labels
LETTER = {"mayu": "CA", "sena": "CB", "alice": "CC", "momoka": "CD",
          "hikaru": "CE", "chisa": "CF", "maria": "CG"}
VOICE_PREFIX = {"mayu": "MAY", "sena": "SEN", "alice": "ALI", "maria": "MRA",
                "chisa": "CHI", "hikaru": "HIK"}   # only maria's is confirmed; check others from character_lines
# the bench's shared house (bz/two_minds bzombie/arms/s/make_run.py HOUSE): ids every mind's home file uses
HOUSE_IDS = {"her_room": "Momoka's room", "house": "the main part of the house", "maid_room": "the maid room"}
VN_PORT ={"maria": 8771, "mayu": 8772, "sena": 8773, "alice": 8774}


def load(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {} if default is None else default


def dump(path, tree):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(tree, indent=2, ensure_ascii=False) + "\n")


def momoka_tokens(root):
    """The token names Momoka's fills carry: the set of [[TOKEN]]s that survive in
    the roles a character of this shape keeps. A heroine of the same shape needs
    the same set."""
    f = load(os.path.join(root, "momoka", "fills.json"))
    return [k for k in f if not k.startswith("_") and k != "id"]


def quality_caps(sheet, src):
    """Caps from her own marks: the tics that are hers, capped per draft."""
    return src.get("caps") or {}


def build_bundle(key, sheet, src, root):
    mom = load(os.path.join(root, "momoka", "bundle.json"))
    ov = copy.deepcopy(mom["config_overrides"])
    nm = sheet["name"]
    given = nm.get("given") or nm.get("japanese")
    ex = {k: v for k, v in sheet["existence"].items() if not k.startswith("_")}
    pdir = "prompts_" + key
    for role in ov["models"]:
        if ov["models"][role].get("prompt"):
            ov["models"][role]["prompt"] = pdir + "/bible.md"
    ov["character"].update({
        "name": nm["full"].split()[-1] if " " in nm["full"] else nm["full"],
        "name_ja": given,
        "reading_ja": nm.get("reading_ja") or nm.get("kana"),
        "style_prompt": pdir + "/style.md",
        "style_ja_prompt": pdir + "/style.md",
        "existence": ex,
    })
    ov["tts"] = {"enabled": False, "on_demand": True, "voice_mode": "exact",
                 "minimax_script_path": "minimax/minimax_tts.py",
                 "minimax_config_path": "minimax/config.json",
                 "voice_id": "", "emotion_enabled": True, "language_boost": "Japanese",
                 "pronunciation_dict": {"tone": src.get("tone") or []},
                 "interjection_tags": True,
                 "_note": src.get("tts_note", "off until a MiniMax clone exists (docs/voice.md)")}
    ov["tts"].pop("_note")
    vn = ov["vn"]
    vn.update({"enabled": False, "port": VN_PORT.get(key, 8779),
               "character_dir": "%s/by_character/%s" % (CORPUS, SLUG_DIRS[key]),
               "reviewed_labels": "characters/%s/expression_labels_unreviewed.json" % key})
    ov["quality"]["caps"] = src.get("caps") or {"phrases": {}, "doubled_group": 2}
    ov["logging"] = {"db_path": "data/%s.db" % key}
    out = {k: mom[k] for k in ("_note",)}
    out["_note"] = ("Everything that is %s and nothing that is not. Shape: Momoka's resident bundle "
                    "(docs/bundle.md) with her own name, prompts, quality caps and existence answers; "
                    "built by tools/koikano/promote_heroine.py from sheet.json and heroine_src/%s/. "
                    "Not in the operator's register: `registered` is false, so compose leaves "
                    "characters.json and the launcher alone." % (given, key))
    out.update({
        "key": key, "name": nm["full"], "hub_id": key, "config": "config_%s.json" % key,
        "db": "data/%s.db" % key, "program": "resident", "launcher": "%s.cmd" % key,
        "task": "SCAIL_%s" % key,
        "match": "resident[\\\\/]run\\.py.*config_%s|scail\\.py.*config_%s" % (key, key),
        "registered": False,
        "world": {"id": "", "owner": False},
        "prompts_dir": pdir, "prompts_generated": True,
        "files": {"character.cast_file": "cast.json", "character.neutral_file": "fills.json",
                  "world.character_file": "sheet.json"},
        "holes": src.get("holes") or [],
        "blank": mom["blank"],
        "config_overrides": ov,
    })
    return out


MECH = ("NAME", "NAME_CAPS", "FULLNAME", "WHO", "WHO_IN", "WHO_SHORT", "WHO_PAREN",
        "WHO_ORIGIN", "WHO_ORIGIN_B", "WHO_SCHOOL_B")


def build_fills(key, sheet, src, root, want):
    nm = sheet["name"]
    given = nm.get("given") or nm.get("japanese")
    full = nm.get("japanese") or given
    mech = {"NAME": given, "NAME_CAPS": given, "FULLNAME": full}
    for k in MECH[3:]:
        mech[k] = full
    fills = {"_note": ("Values for the [[TOKEN]] holes in the shared mechanism prompts for %s. Built by "
                       "tools/koikano/promote_heroine.py: name forms are mechanical from sheet.json, every "
                       "other value is hand-read from her record (heroine_src/%s/fills_src.json) with a "
                       "receipt (scene:line) or says the record is silent. Nothing here is invented."
                       % (full, key)),
             "id": key}
    miss, record, silent = [], 0, 0
    hand = src.get("tokens") or {}
    for t in want:
        if t in mech:
            fills[t] = mech[t]
            continue
        h = hand.get(t)
        if not h:
            miss.append(t)
            continue
        fills[t] = h["value"]
        if h.get("receipt"):
            record += 1
        else:
            silent += 1
    fills["_receipts"] = {t: hand[t].get("receipt") or "record is silent" for t in want if t in hand}
    return fills, miss, record, silent


def build_cast(key, sheet, src):
    people = {}
    for pk, p in (src.get("people") or {}).items():
        row = {"role_id": p["role_id"], "name": p["name"], "role": p["role"], "note": p["note"],
               "aliases": p["aliases"], "receipts": p.get("receipts") or []}
        for opt in ("calls", "numbers", "closeness", "standing", "tension", "ja"):
            if opt in p:
                row[opt] = p[opt]
        people[pk] = row
    nm = sheet["name"]
    return {"_note": src.get("cast_note", "Her roster, from her own lines only."),
            "self": {"key": key, "ja": nm.get("given") or nm.get("japanese"),
                     "calls": src.get("self_calls") or {}},
            "people": people}


def build_world(key, sheet, src, root):
    w = copy.deepcopy(src)
    ids = w.get("place_ids") or []
    bad = [i for i in ids if i not in HOUSE_IDS]
    if bad:
        sys.exit("world_src place_ids not in the shared house ids %s: %s" % (list(HOUSE_IDS), bad))
    w["house_id"] = "chiyoda"
    w["places"] = {i: HOUSE_IDS[i] for i in ids}
    return w


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("key")
    ap.add_argument("--root", default=os.path.join(ROOT, "characters"))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    key = a.key
    if key not in SLUG_DIRS:
        sys.exit("unknown heroine key %r: add her to SLUG_DIRS (and LETTER) first" % key)
    bdir = os.path.join(a.root, key)
    sheet = load(os.path.join(bdir, "sheet.json"))
    if not sheet:
        sys.exit("no sheet.json for %s in %s" % (key, bdir))
    sd = os.path.join(SRC, key)
    fsrc = load(os.path.join(sd, "fills_src.json"))
    csrc = load(os.path.join(sd, "cast_src.json"))
    wsrc = load(os.path.join(sd, "world_src.json"))
    bsrc = load(os.path.join(sd, "bundle_src.json"))
    want = momoka_tokens(a.root)
    fills, miss, rec, sil = build_fills(key, sheet, fsrc, a.root, want)
    print("fills: %d tokens, %d from record, %d record is silent, %d missing" % (len(want), rec, sil, len(miss)))
    if miss:
        print("  missing: " + ", ".join(miss))
    if a.check:
        return 1 if miss else 0
    if miss:
        sys.exit("refusing: fills_src.json lacks tokens")
    dump(os.path.join(bdir, "bundle.json"), build_bundle(key, sheet, bsrc, a.root))
    dump(os.path.join(bdir, "fills.json"), fills)
    dump(os.path.join(bdir, "cast.json"), build_cast(key, sheet, csrc))
    dump(os.path.join(bdir, "world", "%s_house.json" % key), build_world(key, sheet, wsrc, a.root))
    print("wrote bundle.json fills.json cast.json world/%s_house.json in %s" % (key, bdir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
