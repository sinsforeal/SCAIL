"""How much of her world is him, measured from the record.

His ask (2026-08-26): "want to see her world being mostly me decrease over
time with our changes". This is the ruler. Each figure is the share of rows
of one kind that mention him, per day: what the director wrote as her inner
line, the day's events, the state model's reasons, her private thoughts,
her own memories of the day, and the message ratio. `composite` is the mean
of the shares that exist. Recorded at the compile (kv `him_share`, one row
per day) and printed by `/world`. Nothing reads it back into her; it is a
ruler, not a lever.
"""
import re

HIM = re.compile(r"\b(he|him|his|he's|he'd|he'll|the man|the guy|the app|his (?:pc|notes?|messages?|chat|screen))\b", re.I)


def _share(rows):
    rows = [r for r in rows if r and str(r).strip()]
    if not rows:
        return None
    return sum(1 for r in rows if HIM.search(str(r))) / len(rows)


def measure(store, date):
    with store.lock:
        cx = store.conn
        inner = [r[0] for r in cx.execute("SELECT inner FROM scenes WHERE date=?", (date,))]
        events = [r[0] for r in cx.execute("SELECT text FROM events WHERE date=?", (date,))]
        reasons = [r[0] for r in cx.execute("SELECT reasons FROM state_log WHERE date=?", (date,))]
        mems = [r[0] for r in cx.execute("SELECT text FROM self_memories WHERE date=?", (date,))]
        hers, his = cx.execute("SELECT SUM(role!='user'), SUM(role='user') FROM messages WHERE date=?", (date,)).fetchone()
    refl = [r for r in store.get("reflections", []) if r.get("date") == date]
    out = {
        "inner": _share(inner),
        "events": _share(events),
        "reasons": _share(reasons),
        "thoughts": (sum(1 for r in refl if r.get("about", "him") == "him") / len(refl)) if refl else None,
        "memories": _share(mems),
        "messages": {"hers": int(hers or 0), "his": int(his or 0)},
        "n": {"inner": len(inner), "events": len(events), "reasons": len(reasons), "thoughts": len(refl), "memories": len(mems)},
    }
    parts = [v for k, v in out.items() if k in ("inner", "events", "reasons", "thoughts", "memories") and v is not None]
    out["composite"] = sum(parts) / len(parts) if parts else None
    return out


def record(store, clock, date, keep=60):
    m = measure(store, date)
    hist = store.get("him_share", {})
    hist[date] = m
    store.set("him_share", {k: hist[k] for k in sorted(hist)[-keep:]})
    return f"{date}: composite {_pct(m['composite'])} (inner {_pct(m['inner'])}, events {_pct(m['events'])}, reasons {_pct(m['reasons'])}, thoughts {_pct(m['thoughts'])}, memories {_pct(m['memories'])}; msgs her {m['messages']['hers']} / him {m['messages']['his']})"


def _pct(v):
    return "  - " if v is None else f"{v * 100:3.0f}%"


def report(store, clock, days=14):
    hist = store.get("him_share", {})
    today = clock.date_str()
    # today and any day the compile has not recorded yet, live
    with store.lock:
        dates = [r[0] for r in store.conn.execute("SELECT DISTINCT date FROM scenes ORDER BY date DESC LIMIT ?", (days,))]
    lines = ["how much of her day is him (share of rows that mention him)",
             "date        comp  inner events reasn thoug memor  msgs(her/him)"]
    for d in sorted(dates):
        m = hist.get(d) or measure(store, d)
        tag = "" if d in hist else ("  (live)" if d == today else "  (not recorded)")
        lines.append(f"{d}  {_pct(m['composite'])}  {_pct(m['inner'])}  {_pct(m['events'])}   {_pct(m['reasons'])}  {_pct(m['thoughts'])}  {_pct(m['memories'])}  {m['messages']['hers']}/{m['messages']['his']}{tag}")
    return "\n".join(lines)
