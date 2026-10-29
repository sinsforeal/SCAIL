"""Bench default (tk-xhv): a branch save holds his live relationship primitives, so he is admitted.

Bench saves never admitted him: predictability_hers stays 0.0 (it only rises when `answered`, scail.py `answered =
bool(wonder_seed)`), so ruptures, her inside register and the ick math ran as for a stranger. In this public
snapshot seeds/primitives_him.json is SYNTHETIC: a bench save's own row with predictability raised to an admitted
level. The private tree extracted it once from a live save instead.

apply_to_rows() puts them into the kv `primitives` rows of a save, with one _log row per changed key (why, cause
"bench_seed"), through no other path. The off switch is the branch variant `stranger` (branch.py): no seed, the save
as the base run left it, so past stranger-mode results stay reproducible.
"""
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
SEED_PATH = os.path.join(HERE, "seeds", "primitives_him.json")
VARIANT_OFF = "stranger"
LOG_ROWS = 200


def load_seed(path=None):
    with open(path or SEED_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def seed_tag(seed=None):
    """What branch.json records for a seeded branch; a branch without it is stranger-mode."""
    seed = seed or load_seed()
    return "primitives_him@" + str(seed.get("extracted"))


def _person_key(rows, seed):
    """The bench save's row for him: the seed's own key when the save has it, else the only row, else the seed's."""
    p = seed.get("person_in_live_save") or "him"
    if p in rows:
        return p
    if len(rows) == 1:
        return next(iter(rows))
    return p


def apply_to_rows(rows, ts, seed=None):
    """Return (rows, changed): rows with his seeded values written in. Keys already equal are left alone."""
    seed = seed or load_seed()
    rows = dict(rows or {})
    person = _person_key(rows, seed)
    r = dict(rows.get(person) or {})
    log = list(r.get("_log") or [])
    changed = {}
    why = "bench seed: live relationship values (extracted %s)" % seed.get("extracted")
    for k, v in (seed.get("primitives") or {}).items():
        if k == "threat_kinds":
            if v and not r.get("threat_kinds"):
                r["threat_kinds"] = list(v)
            continue
        before = float(r.get(k, 0.0) or 0.0)
        if before == float(v):
            continue
        r[k] = float(v)
        changed[k] = (before, float(v))
        log.append({"ts": ts, "key": k, "from": round(before, 1), "to": round(float(v), 1),
                    "why": why[:160], "cause": "bench_seed"})
    r["_log"] = log[-LOG_ROWS:]
    r["_bench_seed"] = seed_tag(seed)
    rows[person] = r
    return rows, changed


def apply_to_db(db_path, ts, seed=None):
    """Seed a closed save file in place (the Arm's working copy after a restore, never a snapshot, never the live save)."""
    con = sqlite3.connect(db_path)
    try:
        row = con.execute("SELECT value FROM kv WHERE key='primitives'").fetchone()
        rows = json.loads(row[0]) if row and row[0] else {}
        rows, changed = apply_to_rows(rows, ts, seed)
        con.execute("INSERT OR REPLACE INTO kv(key,value) VALUES('primitives',?)", (json.dumps(rows),))
        con.commit()
    finally:
        con.close()
    return changed


def apply_to_store(store, ts, seed=None):
    """Seed a running App's store (kv through the store's own lock)."""
    rows, changed = apply_to_rows(store.get("primitives", {}) or {}, ts, seed)
    store.set("primitives", rows)
    return changed
