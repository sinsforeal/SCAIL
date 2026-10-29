"""Why a pick is due: something changed since her last look (tk-y7j).

`PhonePick.due` used to let a block or scene moment through every
`pick.min_gap_minutes`, so a quiet morning became a clock: she looked at her
phone, found nothing new, and with a text_him on the menu poked him at 07:55,
08:20, 08:45. With `pick.due_on_change` on, the gap is only a floor. Past it a
look needs a reason, and code names the reason here, from the save alone, no
model call:

- he wrote (a new message of his), or his machine said something new (a pc
  event) or he came back from idle;
- the world moved (an event of salience `event_salience` or more);
- a gauge moved `gauge_move` points or more from where it was at her last look;
- something she was waiting for came due (an open expectation whose due time
  passed since the last look);
- his silence crossed a step (`silence_steps_hours`, e.g. 2h, 6h);
- the ceiling: `ceiling_minutes` since the last look, so she is never frozen.

`base` is what the last look saw, written by `snapshot` when the look is
spent. No change, no reasons: the moment is refused with "nothing changed".
"""


def snapshot(store, state, now):
    """What this look saw, to compare the next one against."""
    gauges = {}
    try:
        for k, v in (getattr(state, "gauges", None) or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                gauges[str(k)] = float(v)
    except Exception:
        gauges = {}
    live = store.get("phone_last_live") or {}
    return {"ts": float(now), "gauges": gauges,
            "idle": int((live or {}).get("idle_min") or 0) if isinstance(live, dict) else 0}


def reasons(c, store, state, now, base, since_min):
    """The list of why a look is due now; [] when nothing changed. `c` is
    config.pick, `base` the dict `snapshot` wrote at the last look (or {})."""
    out = []
    base = base if isinstance(base, dict) else {}
    bts = float(base.get("ts") or 0)
    if bts <= 0:
        return ["first look"]
    ceiling = float(getattr(c, "ceiling_minutes", 0) or 0)
    if ceiling > 0 and since_min >= ceiling:
        out.append(f"ceiling ({since_min:.0f} min since the last look)")

    his = store.last_message("user")
    his_ts = float(his["ts"]) if his else 0.0
    if his_ts > bts:
        out.append("he wrote")

    pa = store.get("phone_account") or {}
    pl = store.get("phone_last_live") or {}
    pts = max(float(pa.get("ts") or 0) if isinstance(pa, dict) else 0.0,
              float(pl.get("ts") or 0) if isinstance(pl, dict) else 0.0)
    if bts < pts <= now:
        out.append("pc event")
        if isinstance(pl, dict) and int(pl.get("idle_min") or 0) == 0 and int(base.get("idle") or 0) > 0:
            out.append("he is back at his machine")

    sal = int(getattr(c, "event_salience", 2) or 2)
    try:
        evs = store.recent_events(40)
    except Exception:
        evs = []
    n_ev = [e for e in evs if bts < float(e.get("ts") or 0) <= now and int(e.get("salience") or 0) >= sal]
    if n_ev:
        out.append(f"world event ({str(n_ev[-1].get('text') or '')[:40]})")

    move = float(getattr(c, "gauge_move", 0) or 0)
    if move > 0:
        was = base.get("gauges") or {}
        try:
            now_g = getattr(state, "gauges", None) or {}
            for k, v in now_g.items():
                if k in was and isinstance(v, (int, float)) and abs(float(v) - float(was[k])) >= move:
                    out.append(f"gauge {k} {float(was[k]):.0f}->{float(v):.0f}")
        except Exception:
            pass

    try:
        rows = store.get("expectations", []) or []
    except Exception:
        rows = []
    for r in rows:
        try:
            if r.get("state") == "open" and bts < float(r.get("due_ts") or 0) <= now:
                out.append("expectation came due")
                break
        except Exception:
            continue

    if his_ts > 0:
        for h in list(getattr(c, "silence_steps_hours", None) or []):
            edge = his_ts + float(h) * 3600.0
            if bts < edge <= now:
                out.append(f"his silence reached {float(h):g}h")
    return out
