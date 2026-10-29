"""Does a value actually do anything?

His ask (2026-08-26): the ability to fix gauges by hand, and a smoke test
that shows whether those values have a meaningful effect on behaviour. A
gauge with no reader is a tag nothing acts on -- the fault `social_standing`
was deleted for -- and the wiring report only says who WRITES a gauge. This
sweeps each value across its range and asks the code-side readers what they
would do: her read delay, how long she takes to compose, her register line,
the impulse score, the withholding pressure, the shape she would draw, the
posting mode, and her felt affect. A gauge that moves none of them between
0 and 100 is flagged DEAD. Nothing is changed: the gauges are restored
after every probe.

Run in-app as `/sweep [gauge|him|all]`, or offline:
    python tools/sweep.py [gauge]
"""


READERS = ("delay", "compose", "register", "impulse", "withhold", "shape", "post", "wonder", "valence", "tags")
# DEAD is judged on the readers that are BEHAVIOUR. The last two are
# arithmetic over the gauge spec -- the affect is a weighted sum of every
# gauge's declared valence, the tag count follows any gauge past its
# threshold -- so every gauge moves them by construction, and while they
# counted, the DEAD line could never print: a gauge nothing acts on read
# as alive because it had a valence. They stay in the table as information.
BEHAVIOUR = READERS[:8]


def _probe(app, silent_hours=3.0):
    st = app.state
    out = {}
    try:
        out["delay"] = round(st.delay_factor(), 2)
    except Exception:
        out["delay"] = None
    try:
        out["compose"] = round(st.compose_factor(), 2)
    except Exception:
        out["compose"] = None
    try:
        out["register"] = (st.register() or "-")[:38]
    except Exception:
        out["register"] = None
    try:
        out["impulse"] = round(app.impulse.score(st, app.director.current or {}, silent_hours), 1)
    except Exception:
        out["impulse"] = None
    try:
        # a reader that cannot act is not a reader: the pressure is computed
        # whatever the section says, and for a character whose sheet says she
        # has not got the decision not to answer, a gauge whose only mover was
        # this column would have read as alive
        out["withhold"] = (round(app.withholding.pressure(), 2)
                           if app.config.withholding.enabled else None)
    except Exception:
        out["withhold"] = None
    try:
        d = app.persona.shape_engine.draw([{"text": "hey, what are you doing"}], "", app.director.current or {})
        out["shape"] = d.get("kind") if d else "-"
    except Exception:
        out["shape"] = None
    try:
        out["post"] = app.posting.mode()
    except Exception:
        out["post"] = None
    try:
        # the last gate of `Wonder.due`, curiosity alone: the opportunity
        # gates before it (the day's cap, the cooldown) would hide the
        # gauge's reader on most probes
        out["wonder"] = app.wonder.pull()[1][:38]
    except Exception:
        out["wonder"] = None
    try:
        out["valence"] = round(st.affect("valence"), 1)
    except Exception:
        out["valence"] = None
    try:
        out["tags"] = len(st.mood_tags().split(", "))
    except Exception:
        out["tags"] = None
    return out


def _him_meters(app):
    key = app.state._him_key() or "him"
    return key, app.state.relationships.get(key, {})


def sweep(app, what="all"):
    """Text table. `what`: a gauge name, "him" (his meters and the two
    sentiments), or "all"."""
    st = app.state
    spec = app.config.state.gauges
    saved = dict(st.gauges)
    rest = {k: float(v["baseline"]) for k, v in spec.items() if k in st.gauges}
    key, him = _him_meters(app)
    saved_him = dict(him)
    lines = []
    dead = []
    targets = []
    if what in ("all", "gauges"):
        # a gauge whose owning section is switched off for this character is
        # not dead, it is absent: sweeping it would report DEAD for every
        # character who was never meant to have it
        targets += [("gauge", k) for k, v in spec.items()
                    if v.get("kind") != "derived" and not st.owner_off(k)]
    elif what in spec:
        targets.append(("gauge", what))
    if what in ("all", "him"):
        targets += [("him", m) for m in ("closeness", "standing", "tension")]
    if not targets:
        return f"unknown: {what}. a gauge name, him, or all"
    header = "value  " + "  ".join(f"{r:>8s}" for r in READERS)
    for kind, name in targets:
        if kind == "gauge":
            base = float(spec[name]["baseline"])
            points = [0.0, base, 100.0]
            if name == "affection":
                points = [0.0, 15.0, 30.0, base, 70.0, 100.0]
        else:
            base = float(saved_him.get(name, 50) or 50)
            points = [0.0, base, 100.0]
        rows = []
        for v in points:
            # from rest, so the value under test is the only thing that
            # differs between rows: with anger at 80 in the live state every
            # register read "clipped" and nothing else could show
            st.gauges.update(rest)
            him.update(saved_him)
            if kind == "gauge":
                st.gauges[name] = v
            else:
                him[name] = v
            try:
                # affection is computed from his meters, so a meter sweep
                # lets it follow; a sweep of affection itself must not, or
                # the value snaps back to its target before anything reads it
                if kind == "him":
                    st._derive_affection(1000.0)
                st._derive_mood(1000.0)
            except Exception:
                pass
            rows.append((v, _probe(app)))
        st.gauges.update(saved)
        him.update(saved_him)
        moved = [r for r in READERS if len({str(p[1].get(r)) for p in rows}) > 1]
        acted = [r for r in moved if r in BEHAVIOUR]
        label = f"{name} ({'his meter' if kind == 'him' else spec[name].get('kind', '')}, rest {base:.0f})"
        lines.append(f"{label}: behavioural readers moved {len(acted)}/{len(BEHAVIOUR)}"
                     + (f" -- {', '.join(moved)}" if acted else
                        "  ** DEAD: no behaviour reads it **" + (f" (only {', '.join(moved)})" if moved else "")))
        lines.append("  " + header)
        for v, p in rows:
            lines.append(f"  {v:5.0f}  " + "  ".join(f"{str(p.get(r)):>8s}"[:8] for r in READERS))
        if not acted:
            dead.append(name)
    try:
        st._derive_affection(1000.0)
        st._derive_mood(1000.0)
    except Exception:
        pass
    st.gauges.update(saved)
    him.update(saved_him)
    head = [f"sweep: {len(targets)} value(s) x {len(READERS)} readers (delay / compose / register / impulse / withhold / shape / post / wonder are behaviour; valence / tag count are the affect arithmetic, shown and not judged); gauges restored after"]
    if dead:
        head.append("DEAD (no behavioural reader moved between 0 and 100): " + ", ".join(dead))
    else:
        head.append("nothing dead: every value moved at least one behavioural reader")
    return "\n".join(head + lines)
