"""The situation block she was actually handed at a moment on the record.

`tools/gauge_ab.py` stages two invented gauge conditions and spends model
calls; this is the same staging with neither. One copy of the save, the
clock pinned to a message she answered, the record cut so the reply cannot
know the future, the shape drawn once, and then the block printed. Nothing
is sent: the model is refused.

    python tools/situation_probe.py --moments 236 215 212 --out <dir>/before
    python tools/situation_probe.py --moments 236 215 212 --out <dir>/after

Per moment it writes `<id>.txt` (his message, the feeling line, the register
clause, and the whole block) and prints a one-line summary, so a before and
an after directory diff line for line. `--feel-only` prints just the feeling
line and the register clause for each moment, which is the check that a
gauge reaches the words at all.
"""
import argparse
import io
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import harness  # noqa: E402


def build(out, config, db):
    os.makedirs(out, exist_ok=True)
    cfg = os.path.join(out, os.path.basename(config))
    if not os.path.exists(cfg):
        # Config.__init__ rewrites the file it is given and the live one is
        # open in a running process
        shutil.copy(os.path.join(ROOT, config), cfg)
    app = harness.build_on(os.path.join(out, "save.db"), cfg, db)
    harness.refuse_model(app)
    return app


def run(a):
    app = build(a.out, a.config, a.db)
    state = {"now": 0.0}
    app.clock.now_ts = lambda: state["now"]

    rows = list(app.store.conn.execute(
        "SELECT id, ts, role, text FROM messages WHERE id IN (%s)" % ",".join("?" * len(a.moments)),
        a.moments))
    rows.sort(key=lambda r: -r[1])
    if len(rows) != len(a.moments):
        raise SystemExit("moments not all found: %s" % [r[0] for r in rows])

    for mid, ts, role, text in rows:
        state["now"] = ts + 60.0
        with app.store.lock:
            app.store.conn.execute("DELETE FROM messages WHERE ts > ?", (ts + 1,))
            app.store.conn.commit()
        app.store.set("thread_window", None)
        unread = [{"id": mid, "ts": ts, "role": role, "text": text}]
        scene = dict(app.director.current or {})
        digest = app.phone.latest_digest() if app.phone else ""
        shape = app.persona.shape_engine.draw(unread, scene=scene)
        situation = app.persona._situation(scene, digest, unread, "", shape=shape)
        feel = app.state.mood_tags(ja=app.persona.ja)
        reg = app.state.register(ja=app.persona.ja)
        if a.feel_only:
            print(f"[{mid}] feel: {feel}")
            print(f"[{mid}] register: {reg}")
            continue
        body = (f"# moment {mid}\nhis message: {text}\n\nfeel: {feel}\n\nregister: {reg}\n\n{situation}\n")
        io.open(os.path.join(a.out, f"{mid}.txt"), "w", encoding="utf-8").write(body)
        print(f"[{mid}] {len(situation)} chars, {situation.count(chr(10))} lines -> {a.out}/{mid}.txt")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--moments", nargs="+", type=int, required=True)
    p.add_argument("--config", default="config_yukarin.json")
    p.add_argument("--db", default="data/yukarin.db")
    p.add_argument("--out", required=True)
    p.add_argument("--feel-only", action="store_true")
    run(p.parse_args())


if __name__ == "__main__":
    main()
