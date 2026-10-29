"""One source of truth for each subject's own-rule markers: tools/koikano/markers/<slug>.json.

{ "<speech_guide rule index>": "<regex over the kept spoken text>" }

The subject's apply script (characters/<slug>/...) and run_leak_free.py both read it.
load_rule_markers in koikano_bible_gate.py reads the "marker" field these write into bible.json.
百花 has no file: she keeps the gate's default 13 markers.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "markers")


def path(slug):
    return os.path.join(DIR, slug + ".json")


def load(slug):
    """{int rule index: regex}; empty dict when the subject has no file."""
    p = path(slug)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as fh:
        return {int(k): v for k, v in json.load(fh).items()}


def apply_to_bible(bible, slug):
    """Set rules[i]['marker'] = {'pattern': regex} for the subject's markers. Returns the count set."""
    m = load(slug)
    rules = bible["speech_guide"]["rules"]
    # The apply steps (characters/<slug>/*apply*.py) append rules after the builder's list.  A raw build
    # is shorter; pad with stubs so the marker keeps the index the apply step gives it.  The gate reads
    # only the marker pattern, so a stub changes nothing else.
    while m and len(rules) <= max(m):
        rules.append({"rule": "stub: rule added by the subject's apply step; carries its marker only", "stub": True})
    for i, pat in m.items():
        rules[i]["marker"] = {"pattern": pat}
    return len(m)


def apply_to_dir(bible_dir, slug):
    """Same on <bible_dir>/bible.json, in place (key order and indent as the builder writes)."""
    p = os.path.join(bible_dir, "bible.json")
    with open(p, encoding="utf-8") as fh:
        bible = json.load(fh)
    n = apply_to_bible(bible, slug)
    if n:
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(bible, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
    return n
