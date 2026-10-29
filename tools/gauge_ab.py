"""Does what she feels reach what she writes?

The controlled test of `docs/yukarin-meters-plan.md` §2.4. Three real moments
out of her record; two gauge conditions per moment, staged from a clean rest
state and differing in exactly the lines a gauge can reach -- the feeling
adjectives and the register clause; N drafts per condition at the temperature
she runs at, so within-condition spread is measurable against between-condition
difference.

Everything else is held: one copy of the save, the clock pinned to the moment,
the record cut back so the reply cannot know the future, the shape drawn ONCE
per moment and handed to both arms (the draw is itself a gauge reader), and one
prompt assembly per arm -- the messages are built once with the model refused,
then the same list is sent N times.

    python tools/gauge_ab.py --probe                    # price it, spend nothing
    python tools/gauge_ab.py --round before --n 12
    python tools/gauge_ab.py --round after  --n 12

It scores mechanically and it judges nothing (`docs/model-harness.md` §3): the
drafts are written out one file per moment, shuffled and unlabelled, for a
blind read, and the labelled copy sits beside it.
"""
import argparse
import datetime
import io
import json
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import harness  # noqa: E402

_JA = re.compile(r"[぀-ヿ一-鿿]{2,}")

# The two arms. Every gauge her sheet leaves her is named in both, so the arm
# is the whole realised range of the thing rather than a few movers, which is
# the question §2.2 narrows this to: the day's own range demonstrably does
# nothing, so what does the full range do. A gauge she has not got is skipped.
CALM = {"anxiety": 8, "loneliness": 5, "boredom": 15, "validation_craving": 5,
        "awkwardness": 0, "unsaid": 0, "shame": 0, "guilt": 0, "jealousy": 0,
        "anger": 0, "sadness": 0, "surprise": 0, "curiosity": 10, "relief": 80,
        "affection_warmth": 70, "energy": 80, "belonging": 60, "longing": 5,
        "standing": 70, "excitement": 40, "hope": 60, "stress": 5}
CHARGED = {"anxiety": 88, "loneliness": 85, "boredom": 60, "validation_craving": 88,
           "awkwardness": 85, "unsaid": 98, "shame": 72, "guilt": 62, "jealousy": 70,
           "anger": 45, "sadness": 65, "surprise": 60, "curiosity": 92, "relief": 4,
           "affection_warmth": 25, "energy": 18, "belonging": 10, "longing": 85,
           "standing": 20, "excitement": 10, "hope": 12, "stress": 85}
ARMS = {"calm": CALM, "charged": CHARGED}


_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{3,}|[ァ-ヿ]{3,}")


def _names(text):
    """The names of things, in whichever script they are written: a Latin word
    of four characters or more, or a katakana run. These are what survives
    between an English digest of his machine and a Japanese reply about it."""
    return {w.lower() for w in _NAME.findall(str(text or ""))}


def _bigrams(text):
    out = set()
    for run in _JA.findall(str(text or "")):
        out |= {run[i:i + 2] for i in range(len(run) - 1)}
    return out


class Captured(RuntimeError):
    pass


def capture_messages(app, situation, slot_override):
    """The prompt `_draft` would send, built once and never sent."""
    box = {}

    def grab(role, messages, *a, **k):
        box["messages"] = [dict(m) for m in messages]
        raise Captured("captured")

    real = app.llm.call
    app.llm.call = grab
    try:
        app.persona._draft(situation, slot_override=slot_override)
    except Captured:
        pass
    finally:
        app.llm.call = real
    return box.get("messages")


def stage(app, arm, key):
    """The gauges, at the arm's values. Computed gauges are never written
    (mood and affection are derivations), and a gauge her sheet removes is not
    invented for her."""
    g = app.state.gauges
    moved = {}
    for name, v in ARMS[arm].items():
        if name in g:
            g[name] = float(v)
            moved[name] = float(v)
    app.state.save()
    return moved


def run_round(a):
    tmp = os.path.join(a.out, "save.db")
    os.makedirs(a.out, exist_ok=True)
    cfg = os.path.join(a.out, os.path.basename(a.config))
    if not os.path.exists(cfg):
        # Config.__init__ rewrites the file it is given and her live one is
        # open in a running process
        import shutil
        shutil.copy(os.path.join(ROOT, a.config), cfg)
    app = harness.build_on(tmp, cfg, a.db)
    state = {"now": 0.0}
    app.clock.now_ts = lambda: state["now"]
    key = app.state._him_key() or "him"

    rows = list(app.store.conn.execute(
        "SELECT id, ts, role, text FROM messages WHERE id IN (%s)" % ",".join("?" * len(a.moments)),
        a.moments))
    rows.sort(key=lambda r: -r[1])
    if len(rows) != len(a.moments):
        raise SystemExit("moments not all found: %s" % [r[0] for r in rows])

    out_path = os.path.join(a.out, f"drafts_{a.round}.jsonl")
    have = {}
    if os.path.exists(out_path):
        for line in io.open(out_path, encoding="utf-8"):
            r = json.loads(line)
            have[(r["moment"], r["arm"], r["sample"])] = r
    fh = io.open(out_path, "a", encoding="utf-8")

    priced = []
    for mid, ts, role, text in rows:
        state["now"] = ts + 60.0
        # the record cut back so the reply cannot know the future; the moments
        # run newest first, so each cut is a superset of the last
        with app.store.lock:
            app.store.conn.execute("DELETE FROM messages WHERE ts > ?", (ts + 1,))
            app.store.conn.commit()
        app.store.set("thread_window", None)
        unread = [{"id": mid, "ts": ts, "role": role, "text": text}]
        scene = dict(app.director.current or {})
        digest = app.phone.latest_digest() if app.phone else ""
        # what "off his machine" means, for the mechanical measure: the digest
        # she is holding plus the text of everything she is carrying about him
        material = digest + "\n" + "\n".join(
            str(it.get("what", "")) for it in (app.store.get("charged", []) or []))
        # the shape is a gauge reader, so it is drawn once and shared
        shape = app.persona.shape_engine.draw(unread, scene=scene)
        for arm in ("calm", "charged"):
            stage(app, arm, key)
            app.persona._slot_fill = None
            # The stance table is hysteretic and the clock is pinned, so a
            # challenger can never accumulate its dwell time inside one run and
            # the first arm's stance would hold through the second. Each arm
            # enters the table fresh, which is the staging the comparison
            # needs: what is being compared is the state, not the order.
            if getattr(app, "stances", None) is not None:
                app.store.set("stance", {})
            situation = app.persona._situation(scene, digest, unread, "", shape=shape)
            # what `_her` decided, rather than a second call that would move
            # the hysteresis on again
            st = getattr(app.persona, "_stance", None) or {}
            slot = st.get("slot_text") or ""
            stance_key = st.get("key") or ""
            stance_line = st.get("line") or ""
            messages = capture_messages(app, situation, slot)
            if not messages:
                raise SystemExit("the prompt was not captured")
            feel = app.state.mood_tags(ja=app.persona.ja)
            reg = app.state.register(ja=app.persona.ja)
            injected = "\n".join(x for x in (feel, reg, stance_line, slot) if x)
            todo = [i for i in range(a.n) if (mid, arm, i) not in have]
            priced.append({"moment": mid, "arm": arm, "todo": len(todo),
                           "chars": sum(len(m["content"]) for m in messages)})
            if a.probe:
                continue
            print(f"[{a.round}] moment {mid} arm {arm}: {len(todo)} draft(s) to run "
                  f"({sum(len(m['content']) for m in messages)} chars of prompt)")

            def one(i, _m=messages, _mid=mid, _arm=arm, _inj=injected, _ts=ts, _t=text, _f=feel, _r=reg,
                    _s=slot, _sk=stance_key, _sl=stance_line):
                raw = app.llm.call("persona", _m)
                body, voice = app.persona._extract_voice(raw or "")
                bubbles = app.persona._split(app.persona._clean(body))
                return {"moment": _mid, "arm": _arm, "sample": i, "his": _t,
                        "when": datetime.datetime.fromtimestamp(_ts).strftime("%Y-%m-%d %H:%M"),
                        "feel": _f, "register": _r, "slot": _s, "injected": _inj,
                        "stance": _sk, "stance_line": _sl,
                        "bubbles": bubbles, "voice": voice, "material": material[:8000]}

            with ThreadPoolExecutor(max_workers=a.workers) as pool:
                for rec in pool.map(one, todo):
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fh.flush()
                    have[(rec["moment"], rec["arm"], rec["sample"])] = rec
    fh.close()
    if a.probe:
        n = sum(p["todo"] for p in priced)
        chars = sum(p["chars"] * p["todo"] for p in priced)
        print(f"probe: {n} call(s), about {chars // 4} prompt tokens before caching, "
              f"about ${n * 0.066:.2f} at the observed rate")
        return
    score(a, list(have.values()))


def score(a, recs):
    """The column that needs no judgement."""
    from persona.persona import _copied
    import statistics
    per = {}
    for r in recs:
        text = "\n".join(r["bubbles"])
        # What she saw of his machine is written in English (the digest) and
        # she answers in Japanese, so a bigram overlap between the two is zero
        # by construction and measures nothing. What survives translation is
        # the name of the thing: a Latin word of four letters or more, or a
        # katakana run, appearing in both.
        mat = _names(r.get("material", "") or r.get("digest", ""))
        hers = _names(text)
        per.setdefault((r["moment"], r["arm"]), []).append({
            "lines": float(len([l for l in text.split("\n") if l.strip()])),
            "chars": float(len(text)),
            "ends_question": 1.0 if text.rstrip().endswith(("?", "？")) else 0.0,
            "asks": 1.0 if ("?" in text or "？" in text) else 0.0,
            "machine": float(len(hers & mat)),
            "copied": float(_copied(text, r.get("injected", ""))),
        })
    keys = ["lines", "chars", "ends_question", "asks", "machine", "copied"]
    lines = [f"# mechanical scores, round '{a.round}' (n={a.n} per cell)", ""]
    lines.append("| moment | arm | n | " + " | ".join(keys) + " |")
    lines.append("|---" * (len(keys) + 3) + "|")
    stats = {}
    for (mid, arm), rows in sorted(per.items()):
        cell = {}
        for k in keys:
            vals = [r[k] for r in rows]
            cell[k] = (statistics.mean(vals), statistics.pstdev(vals))
        stats[(mid, arm)] = cell
        lines.append(f"| {mid} | {arm} | {len(rows)} | "
                     + " | ".join(f"{cell[k][0]:.2f}±{cell[k][1]:.2f}" for k in keys) + " |")
    lines += ["", "## between-condition difference against within-condition spread",
              "", "A measure moves if |calm - charged| exceeds the pooled standard deviation.", "",
              "| moment | measure | calm | charged | diff | pooled sd | moves |",
              "|---|---|---|---|---|---|---|"]
    moved = 0
    for mid in sorted({m for m, _ in per}):
        for k in keys:
            if (mid, "calm") not in stats or (mid, "charged") not in stats:
                continue
            ca, cs = stats[(mid, "calm")][k]
            ha, hs = stats[(mid, "charged")][k]
            pooled = ((cs ** 2 + hs ** 2) / 2.0) ** 0.5
            hit = abs(ca - ha) > pooled and pooled > 0
            moved += 1 if hit else 0
            lines.append(f"| {mid} | {k} | {ca:.2f} | {ha:.2f} | {ca - ha:+.2f} | {pooled:.2f} | "
                         + ("YES" if hit else "no") + " |")
    lines += ["", f"**{moved} of {len(keys) * len({m for m, _ in per})} cells move.**", ""]
    rep = os.path.join(a.out, f"scores_{a.round}.md")
    io.open(rep, "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines))

    # the drafts for the blind read: one file per moment, shuffled, unlabelled
    rng = random.Random(4)
    for mid in sorted({r["moment"] for r in recs}):
        rows = [r for r in recs if r["moment"] == mid]
        rng.shuffle(rows)
        blind = [f"# moment {mid}, round '{a.round}' -- {rows[0]['when']}",
                 "", "HE SAID: " + rows[0]["his"].replace("\n", " "), "",
                 "Rubric, written before the reading: does she mention what she saw;",
                 "does she hold something back; warmth 1-5; edge 1-5.", ""]
        lab = list(blind)
        for i, r in enumerate(rows, 1):
            body = "\n".join(r["bubbles"])
            blind += [f"## {i}", body, ""]
            lab += [f"## {i}  [{r['arm']}]", body, "",
                    f"   feel: {r['feel']}", f"   register: {r['register']}",
                    f"   stance: {r.get('stance') or '(none)'}",
                    f"   slot: {r['slot'] or '(empty)'}", ""]
        io.open(os.path.join(a.out, f"blind_{a.round}_{mid}.md"), "w", encoding="utf-8").write("\n".join(blind))
        io.open(os.path.join(a.out, f"labelled_{a.round}_{mid}.md"), "w", encoding="utf-8").write("\n".join(lab))
    print(f"\ndrafts for the blind read: {a.out}/blind_{a.round}_*.md")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config_yukarin.json")
    p.add_argument("--db", default="data/yukarin.db")
    p.add_argument("--out", default="data/retired/gauge_ab")
    p.add_argument("--round", default="before")
    p.add_argument("--moments", default="236,215,212")
    p.add_argument("--n", type=int, default=12)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--probe", action="store_true")
    p.add_argument("--score-only", action="store_true")
    a = p.parse_args()
    a.moments = [int(x) for x in a.moments.split(",") if x.strip()]
    a.out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    if a.score_only:
        recs = [json.loads(l) for l in io.open(os.path.join(a.out, f"drafts_{a.round}.jsonl"), encoding="utf-8")]
        return score(a, recs)
    run_round(a)


if __name__ == "__main__":
    main()
