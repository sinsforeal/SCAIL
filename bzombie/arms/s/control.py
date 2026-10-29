"""S arm control server (bzombie/CONTRACT.md, "Arm control API"). One process per live run,
127.0.0.1:1833x. Stepped time: the virtual clock moves only inside /control/advance, in steps
of 5 virtual seconds, one App.run_pass() per step.

    pythonw bzombie/arms/s/control.py --port 18331      (use launch.py: hidden, TEMP=F:\\temp)

Env BZ_BASE_URL (template with {run_id}) points the arm at another OpenAI server (tests);
BZ_NO_TICKET=1 skips the compute ticket; BZ_RUNS overrides var/bzombie/runs.
"""

import argparse
import datetime
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import make_run  # noqa: E402
import bench_seed  # noqa: E402

STEP = 5.0
LIMITS = r"F:\REPS2\Meta_Orchestrator\tools\limits\client.py"
TZ = "Asia/Tokyo"
ALIASES = {"constant_cut": "cut_constant", "change_words": "trend", "reality_labels": "reality",
           "mood_tags": "keep_mood_tags", "register": "keep_register"}
REPLY_ROLES = ("persona", "reply", "draft")


def parse_local(s, tz=TZ):
    from zoneinfo import ZoneInfo
    s = str(s).replace("T", " ")
    d = datetime.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=ZoneInfo(tz))
    return d.timestamp()


def to_ts(v):
    """A virtual time as epoch seconds: a number, or an ISO string in Tokyo time."""
    if isinstance(v, (int, float)):
        return float(v)
    return parse_local(v)


def sim_day(start_ts, ts):
    return int((ts - start_ts) // 86400) + 1


def out_kind(text, was_reply):
    return "reply" if was_reply else "unprompted"


def apply_switch(app, name, value):
    """bz.<switch> on/off: the config object and the Bz instance, when the bz/s6 build is there."""
    cfgsec = getattr(app.config, "bz", None)
    if cfgsec is None:
        raise KeyError("no bz section in this build")
    name = ALIASES.get(name, name)
    if not hasattr(cfgsec, name):
        raise KeyError(f"unknown bz switch {name}")
    setattr(cfgsec, name, value)   # sim/bz.py Bz.on() reads app.config.bz per call


# Removal tests (tk-lmv). `section.<name>` false switches the config section <name> off (its `enabled`), `bz_s10.<key>`
# is one of the two surface checks, `noop` changes nothing (a branch for the drift baseline).
# BOOT_ONLY: parts the App builds only when enabled, so a runtime flip leaves the object running; the arm records
# the override, writes it into the config file and rebuilds the App over the restored save (Arm.inject).
# Every other section is read per call (`c = self.config.<name>; if not c.enabled`), so the flip is honoured at once.
BOOT_ONLY = {("primitives", "enabled")}


def removal_key(target):
    """(section, key) of a section./bz_s10. target, or None for any other target. section.<name> means <name>.enabled."""
    if target.startswith("section."):
        return target[8:], "enabled"
    if target.startswith("bz_s10."):
        return "bz_s10", target[7:]
    return None


def apply_removal(app, target, value):
    sec_key = removal_key(target)
    name, key = sec_key
    sec = getattr(app.config, name, None)
    if sec is None or not hasattr(sec, key):
        raise KeyError(f"unknown removal target {target}")
    if not isinstance(value, bool):
        raise ValueError(f"{target} takes true or false")
    setattr(sec, key, value)
    return sec_key


def write_overrides(cfg_path, overrides, overlays=()):
    """Put the recorded overrides, and the named overlays, into the config file the next App is built from."""
    if not overrides and not overlays:
        return
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    for (name, key), v in overrides.items():
        cfg.setdefault(name, {})[key] = v
    for name in overlays:
        deep_merge(cfg, load_overlay(name))
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=1)


# Config overlays (tk-6si steer_fix): bench-only JSON files in overlays/<name>.json, merged into the config file the
# App is built from (objects merge key by key, lists and scalars replace). `--variant tags` injects `overlay.tags`;
# the live config_momoka.json and her prompts are never touched. The overlay lands at an App build, so the Arm
# rebuilds the App over the restored save (like a BOOT_ONLY removal); anything injected before it that lives only
# in the old App (a bz.<switch>) is lost, so the branch runner injects overlays first.
OVERLAY_DIR = os.path.join(HERE, "overlays")


def load_overlay(name):
    path = os.path.join(OVERLAY_DIR, f"{name}.json")
    if not os.path.isfile(path):
        raise KeyError(f"unknown overlay {name}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def deep_merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


class PinnedGauges(dict):
    """The gauge dict with some keys pinned (steer tests, tk-6si). A write to a pinned key stores the pin instead,
    whoever writes it (decay, appraisal, derive, reactions). Without this a `gauge.<name>` inject decays back toward
    its baseline at decay_per_hour (anger 85 is half gone in about six hours) and his next lines move it again, so the
    reply would be written from a different state than the one injected."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.pins = {}

    def __setitem__(self, k, v):
        super().__setitem__(k, self.pins.get(k, v))

    def update(self, *a, **kw):
        for k, v in dict(*a, **kw).items():
            self[k] = v


def apply_hold(app, gauge, value):
    """`hold.<gauge>` value N: set the gauge to N and pin it there for the rest of the run (until the next restore
    rebuilds the App; the Arm re-applies its holds then). value null/None releases the pin. Derived gauges (mood)
    are refused, like set_value does."""
    st = app.state
    if value is None:
        if isinstance(st.gauges, PinnedGauges):
            st.gauges.pins.pop(gauge, None)
        return None
    if isinstance(st.gauges, PinnedGauges):
        st.gauges.pins.pop(gauge, None)   # a new value on a pinned gauge must land, not be eaten by the old pin
    msg = st.set_value(gauge, value)
    if msg and ("not a number" in str(msg) or "derived" in str(msg) or str(msg).startswith("unknown")
                or "no such" in str(msg)):
        raise ValueError(str(msg))
    if gauge not in st.gauges:
        raise KeyError(f"no gauge {gauge} in this character")
    if not isinstance(st.gauges, PinnedGauges):
        st.gauges = PinnedGauges(st.gauges)
    st.gauges.pins[gauge] = st.gauges[gauge]
    return None


def apply_set(app, gauge, value):
    """`set.<gauge>` value N (tk-6si decay variant): set the gauge to N once, NOT pinned. The normal tick decay runs
    on it from then on (anger 7/h, boredom 6/h, ...) and his lines move it like any other, so the question is whether
    a one-shot feeling lasts long enough to steer her replies. Same refusals as a hold (derived, unknown, not a
    number); null is refused, there is nothing to release. A pin left on the gauge by an earlier hold is dropped."""
    if value is None:
        raise ValueError("set.<gauge> takes a number; a one-shot set has nothing to release")
    st = app.state
    if isinstance(st.gauges, PinnedGauges):
        st.gauges.pins.pop(gauge, None)
    msg = st.set_value(gauge, value)
    if msg and ("not a number" in str(msg) or "derived" in str(msg) or str(msg).startswith("unknown")
                or "no such" in str(msg)):
        raise ValueError(str(msg))
    if gauge not in st.gauges:
        raise KeyError(f"no gauge {gauge} in this character")
    return None


def set_pairs(target, value):
    """[(gauge, value)] of a set. target `set.<gauge>` takes a number; target `set.multi` takes an object
    `{"anxiety": 90, "stress": 70}` and sets every gauge in it once (the twin of hold.multi)."""
    if target == "set.multi":
        if not isinstance(value, dict) or not value:
            raise ValueError("set.multi takes an object {gauge: value, ...}")
        return [(str(g), v) for g, v in value.items()]
    return [(target[4:], value)]


def hold_pairs(target, value):
    """[(gauge, value)] of a hold. target `hold.<gauge>` takes a number (or null to release); target `hold.multi`
    takes an object `{"energy": 10, "fatigue": 75}` and pins every gauge in it at once (tk-6si steer_fix); null
    releases nothing there (name the gauges: `{"energy": null}`)."""
    if target == "hold.multi":
        if not isinstance(value, dict) or not value:
            raise ValueError("hold.multi takes an object {gauge: value, ...}")
        return [(str(g), v) for g, v in value.items()]
    return [(target[5:], value)]


def apply_inject(app, target, value):
    if target == "noop":
        return None
    if removal_key(target):
        return apply_removal(app, target, value)
    if target.startswith("hold."):
        for g, v in hold_pairs(target, value):
            apply_hold(app, g, v)
        return None
    if target.startswith("set."):
        for g, v in set_pairs(target, value):
            apply_set(app, g, v)
        return None
    if target.startswith("bz."):
        apply_switch(app, target[3:], value)
    elif target in ("mood_tags", "stances", "memory_cards"):
        apply_switch(app, target, value)
    elif target.startswith("gauge."):
        msg = app.state.set_value(target[6:], value)
        if msg and "not a number" in str(msg) or (msg and "derived" in str(msg)):
            raise ValueError(str(msg))
    else:
        raise KeyError(f"unknown target {target}")


PC_EVENTS_KEY = "bz_pc_events"
_ACTIVE_WORDS = ("wake", "opens", "open ", "launch", "signed in", "playing", "plays")
_IDLE_WORDS = ("idle", "asleep", "away", "sleep", "turns off", "locked")


def pc_idle_min(ev):
    """Minutes he has been off the machine at this pc event, or 0 when he is at it. An explicit idle_min wins,
    then 'idle for N', else 60 for an idle/sleep/away text. A wake or open word means he is back."""
    text = str(ev.get("text", ""))
    low = text.lower() + " "
    if ev.get("idle_min"):
        return int(ev["idle_min"])
    if any(w in low for w in _ACTIVE_WORDS) and "idle" not in low:
        return 0
    if any(w in low for w in _IDLE_WORDS):
        import re
        m = re.search(r"idle for (\d+)", low)
        return int(m.group(1)) if m else 60
    return 0


def _hm(app, ts):
    try:
        return app.clock.to_user(ts).strftime("%H:%M")
    except Exception:
        return datetime.datetime.fromtimestamp(ts).strftime("%H:%M")


def pc_account_text(app, events, now):
    """The account of the rolling window, as the digest would give it: every pc event inside the window,
    oldest first, each with his clock time. One row replaced by the next lost every event that fell between two
    of her passes (run cl2_s_momoka: 8 of 15 never reached a prompt)."""
    hours = float(getattr(getattr(app.config, "phone", None), "rolling_hours", 2) or 2)
    keep = [e for e in events if now - e[0] <= hours * 3600]
    return "; ".join(f"{_hm(app, t)} {x}" for t, x in keep)


def pc_live_text(app, now):
    """The 'right now' line the live monitor gives her every tick: the newest pc event while he is at the machine
    and it is fresh. Empty when he is away (latest_digest says that from phone_last_live) or nothing is recent."""
    ll = app.store.get("phone_last_live") or {}
    text = str(ll.get("text") or "")
    if not text or ll.get("bz_pc") is None or ll.get("idle_min"):
        return ""
    age = float(getattr(getattr(app.config, "phone", None), "live_line_max_age_minutes", 45) or 45)
    return text if now - float(ll.get("ts") or 0) <= age * 60 else ""


def pc_install(app):
    """Bench stand-in for the monitor behind Phone.live_line (self.mon is None on the bench, sensors off): the
    resident path reads it every tick. Instance-level, so the live class is untouched."""
    ph = getattr(app, "phone", None)
    if ph is not None:
        ph.live_line = lambda: pc_live_text(app, app.clock.now_ts())


def ground_install(app):
    """Grounding arm C, honest absence (tk-6r3): her situation block gets one more day line, where she is, who is
    there and that nothing happened. Instance-level like pc_install; no event is written."""
    from sim.attention import tag
    p = app.persona
    orig = p._day

    def _day(m):
        day = orig(m)
        day.append(tag(make_run.ABSENCE_SITUATION, "absence", kind="fact", pin=True))
        return day
    p._day = _day


def pc_idle_refresh(app, now):
    """The live idle figure grows while he is away; keep phone_last_live's idle_min in step (once a minute)."""
    ll = app.store.get("phone_last_live") or {}
    since = ll.get("bz_idle_since")
    if since is None or not ll.get("idle_min"):
        return
    mins = max(int(ll["idle_min"]), int((now - since) // 60) + int(ll.get("bz_idle0") or 0))
    if mins != ll["idle_min"]:
        ll["idle_min"] = mins
        app.store.set("phone_last_live", ll)


def pc_view(app):
    """What of his machine reaches her now, for the trace: the account of the window and the live line."""
    now = app.clock.now_ts()
    acct = ""
    try:
        acct = str(app.phone.account().get("text") or "")
    except Exception:
        pass
    live = pc_live_text(app, now)
    ll = app.store.get("phone_last_live") or {}
    if ll.get("idle_min"):
        live = f"idle {ll['idle_min']} min"
    return acct, live


def env_apply(app, ev, ts):
    """pc: his machine, through the phone account (the path latest_digest reads): the rolling window of events
    as the account, the newest as the live line (pc_install). Nothing is added to her prompt directly.
    world: an event row of salience 2, which her situation block shows for the day."""
    kind, text = ev.get("kind"), str(ev.get("text", ""))
    if kind == "pc":
        events = [tuple(e) for e in (app.store.get(PC_EVENTS_KEY) or [])]
        events.append((ts, text))
        events = events[-40:]
        app.store.set(PC_EVENTS_KEY, [list(e) for e in events])
        app.store.set("phone_account", {"ts": ts, "text": pc_account_text(app, events, ts),
                                        "from_ts": events[0][0], "to_ts": ts})
        idle = pc_idle_min(ev)
        row = {"ts": ts, "text": text, "idle_min": idle, "bz_pc": 1}
        if idle:
            row["bz_idle_since"] = ts
            row["bz_idle0"] = idle
        app.store.set("phone_last_live", row)
    elif kind == "world":
        d = datetime.datetime.fromtimestamp(ts, tz=app.clock.char_tz).strftime("%Y-%m-%d")
        app.store.add_event(ts, d, "world", text, 2)
    else:
        raise ValueError(f"unknown env kind {kind}")


class Arm:
    def __init__(self):
        self.lock = threading.RLock()
        self.app = None
        self.ch = None
        self.run_id = ""
        self.character = ""
        self.lang = ""
        self.vt = 0.0
        self.start_ts = 0.0
        self.sends = []        # (ts, text)
        self.env = []          # (ts, event)
        self.outputs = {}      # output_id -> output
        self.n_out = 0
        self.call_cursor = 0
        self.ticket = None
        self.runs_root = os.environ.get("BZ_RUNS") or make_run.RUNS
        self.run_dir = ""
        self.cfg_path = ""
        self.last_his = ""
        self.arm_variant = ""
        self.last_input = []
        self.burst_kind = None   # kind of a delivery still sending, so its tail bubbles keep it
        self.peer_key = ""       # set for the second and later minds of a run (tk-1pl): output ids and the hub id
        self.peer_out = []       # what she wrote to another mind in the steps of one advance, for the driver
        self.overrides = {}      # (section, key) -> value from removal injects; written into the config before a build
        self.last_restore = ""   # name of the snapshot last restored, for a boot-only inject's rebuild
        self.holds = {}          # gauge -> pinned value (hold.<gauge> injects), re-applied after every App build
        self.overlays = []       # names of config overlays (overlay.<name> injects), merged into the config before a build
        self.seed_him = False    # seed.him inject (tk-xhv): his live primitives go into the save at every restore

    # ---- boot
    def _build_app(self):
        os.chdir(ROOT)
        import scail
        write_overrides(self.cfg_path, self.overrides, self.overlays)
        sys.argv = ["scail", "--config", self.cfg_path, "--console", "--no-sensors"]
        args = scail.parse_args()
        self.app = scail.App(args)
        self.ch = self.app.tg
        pc_install(self.app)
        if self.arm_variant == "absence":  # a restore builds a new App: the variant hook goes on it again
            ground_install(self.app)
        self.app.clock.set_virtual(self.vt)
        for g, v in self.holds.items():   # a rebuilt App (restore) keeps the pinned gauges
            apply_hold(self.app, g, v)
        self.call_cursor = len(self.app.llm.call_ids)
        # the save may already hold messages (a resume or restore): the channel's ids go on after them
        try:
            with self.app.store.lock:
                top = self.app.store.conn.execute("SELECT MAX(tg_id) FROM messages").fetchone()[0]
            self.ch.seed_ids(top or 0)
        except Exception:
            traceback.print_exc()

    def start(self, d):
        with self.lock:
            self.run_id, self.character = d["run_id"], d["character"]
            self.lang = d.get("lang", "")
            self.run_dir = os.path.join(self.runs_root, self.run_id)
            tpl = os.environ.get("BZ_BASE_URL")
            self.cfg_path = make_run.build(self.run_id, self.character, d["clock_start"].replace("T", " ")[:16],
                                           runs_root=self.runs_root, port_base_url=tpl,
                                           arm_variant=d.get("arm_variant", ""), seed=int(d.get("seed") or 0),
                                           peer_contacts=d.get("peer_contacts"), role=d.get("role", "primary"),
                                           peer_key=d.get("peer_key", ""))
            self.peer_key = d.get("peer_key", "")
            self.overrides, self.last_restore, self.holds, self.overlays = {}, "", {}, []
            self.vt = self.start_ts = parse_local(d["clock_start"])
            self._ticket()
            self.arm_variant = d.get("arm_variant", "")
            self._build_app()
            self._clock_file()
            return {"ok": True, "virtual_ts": self.vt}

    def _ticket(self):
        if os.environ.get("BZ_NO_TICKET") == "1" or not os.path.exists(LIMITS):
            return
        # mem: 1,686 MB peak over a stub day (10-22 18:30) before embeddings moved to the gateway (tk-y11, 123 MB WS)
        # and the OpenBLAS cut (c6caf19, 112 MB private at day 0), so 1 GB with margin (was 2 GB).
        # Wait up to 4 h, the harness start timeout.
        r = subprocess.run([sys.executable, LIMITS, "wait", "--who",
                            f"scail/bz_s_{self.run_id}" + (f"#{self.peer_key}" if self.peer_key else ""), "--cpu", "1",
                            "--mem-gb", "1", "--vram-mb", "0", "--host", "here", "--prio", "high",
                            "--timeout", "14400"], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            raise RuntimeError(f"compute ticket refused (exit {r.returncode})")
        parts = r.stdout.split()
        self.ticket = parts[-1] if parts else None

    def _release(self):
        if self.ticket and os.path.exists(LIMITS):
            subprocess.run([sys.executable, LIMITS, "release", self.ticket], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.ticket = None

    def _clock_file(self):
        p = os.path.join(self.run_dir, "clock.json")
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"virtual_ts": self.vt, "sim_day": sim_day(self.start_ts, self.vt)}, fh)
        os.replace(tmp, p)

    # ---- time
    def _deliver_due(self):
        due = [e for e in self.env if e[0] <= self.vt]
        self.env = [e for e in self.env if e[0] > self.vt]
        for ts, ev in sorted(due, key=lambda x: x[0]):
            env_apply(self.app, ev, ts)
        dues = [s for s in self.sends if s[0] <= self.vt]
        self.sends = [s for s in self.sends if s[0] > self.vt]
        for ts, text in sorted(dues, key=lambda x: x[0]):
            self.ch.push(text)
            self.last_his = text

    def advance(self, to):
        with self.lock:
            to = to_ts(to)
            outs = []
            self.peer_out = []
            while self.vt < to:
                self._deliver_due()
                self.app.clock.set_virtual(self.vt)
                if int(self.vt) % 60 < STEP:
                    pc_idle_refresh(self.app, self.vt)
                self._clock_file()
                was_reply = bool(self.last_his)
                try:
                    self.app.run_pass()
                except Exception:
                    traceback.print_exc()
                    raise
                self._settle_delivery()
                self._take_peer_out()
                got = self.ch.take_outputs()
                if got:
                    kind = "reply" if was_reply else (self.burst_kind or "unprompted")
                    outs.extend(self._record(got, kind))
                    self.last_his = ""
                    busy = self._delivery_busy()
                    self.burst_kind = kind if busy else None
                elif not self._delivery_busy():
                    self.burst_kind = None
                self.vt = min(self.vt + STEP, to)
            self.app.clock.set_virtual(self.vt)
            self._clock_file()
            return {"outputs": outs, "virtual_ts": self.vt, "peer_out": self.peer_out, "place": self.place()}

    def _take_peer_out(self):
        """What she wrote to another mind in this pass, with the calls that wrote it (peeked: the bubbles of the
        same pass consume the cursor in _record)."""
        take = getattr(self.ch, "take_peer_out", None)
        rows = take() if take else []
        if not rows:
            return
        ids = [c["call_id"] for c in self.app.llm.call_ids[self.call_cursor:]]
        for r in rows:
            self.peer_out.append({**r, "call_ids": ids})
        if not self.ch._outputs:   # no bubble to him in this pass will claim those calls
            self.call_cursor = len(self.app.llm.call_ids)

    def place(self):
        """Where she is now, from her own scene: the id the home file's plan gave it."""
        cur = getattr(getattr(self.app, "director", None), "current", None) or {}
        return {"location": str(cur.get("location") or ""), "activity": str(cur.get("activity") or "")}

    def _delivery_busy(self):
        try:
            return bool(self.app.delivery.busy())
        except Exception:
            return False

    def _settle_delivery(self, limit=20.0):
        """The delivery thread sends the bubbles of one reply a moment after the pass that drafted
        them. Wait (wall time, bounded) until it has sent them all, so one reply is one take: same
        virtual second, same kind, same call ids. Found 10-22: a reply split over passes, its tail
        classed unprompted with no call ids."""
        end = time.time() + limit
        while self._delivery_busy() and time.time() < end:
            time.sleep(0.02)

    def _record(self, bubbles, kind):
        calls = self.app.llm.call_ids[self.call_cursor:]
        self.call_cursor = len(self.app.llm.call_ids)
        ids = [c["call_id"] for c in calls]
        final = ""
        for c in reversed(calls):
            if c["role"] in REPLY_ROLES:
                final = c["call_id"]
                break
        if not final and calls:
            final = calls[-1]["call_id"]
        res = []
        for i, b in enumerate(bubbles):
            self.n_out += 1
            oid = f"{self.run_id}_{self.peer_key + '_' if self.peer_key else ''}o{self.n_out:04d}"
            out = {"output_id": oid, "virtual_ts": b["virtual_ts"], "text": b["text"], "kind": kind,
                   "call_ids": ids}
            self.outputs[oid] = out
            self._write_trace(out, calls, final)
            res.append(out)
        return res

    def _write_trace(self, out, calls, final):
        app = self.app
        inputs = []
        if self.last_his:
            inputs.append({"name": "his message", "kind": "his_words", "source": "channel", "text": self.last_his})
        causal = {"admitted": [], "gauges": {}, "stances": None}
        try:
            for ln in (getattr(app.attention, "last", {}) or {}).get("kept", []):
                src = str(getattr(ln, "source", "") or "")
                w = getattr(ln, "weight", None)
                causal["admitted"].append({"source": src, "weight": w, "text": str(ln)})
                kind = "state" if src.startswith(("gauge", "state", "mood")) else \
                    "memory" if "mem" in src or "recall" in src else "env_event" if "event" in src or "phone" in src else "state"
                inputs.append({"name": src or "line", "kind": kind, "source": src, "text": str(ln)})
        except Exception:
            pass
        # his machine reaches her through the phone account (latest_digest), a prompt block outside attention.kept
        try:
            acct, live = pc_view(app)
            if acct:
                inputs.append({"name": "phone account (his machine)", "kind": "env_event", "source": "phone_account",
                               "text": acct})
            if live:
                inputs.append({"name": "phone live line (his machine)", "kind": "env_event", "source": "phone_live",
                               "text": live})
        except Exception:
            pass
        causal["gauges"] = self._gauges()
        causal["stances"] = self._stances()
        if self.overrides:
            causal["removed"] = self.removed()
        if self.holds:
            causal["held"] = dict(self.holds)
        bzi = getattr(getattr(app, "persona", None), "bz", None) or getattr(app, "bz", None)
        last = getattr(bzi, "last", None)
        if not last:
            try:
                last = json.loads(app.store.get("bz_last") or "{}")
            except Exception:
                last = None
        if isinstance(last, dict) and last:
            causal["bz"] = json.loads(json.dumps(last, ensure_ascii=False, default=str))
        tr = {"output_id": out["output_id"], "arm": "S", "run_id": self.run_id, "virtual_ts": out["virtual_ts"],
              "text": out["text"], "final_call_id": final,
              "calls": [{"call_id": c["call_id"], "role": c["role"]} for c in calls],
              "inputs": inputs, "state_at_output": self.state(), "causal": causal}
        p = os.path.join(self.run_dir, "traces", out["output_id"] + ".json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(tr, fh, ensure_ascii=False, indent=1)

    def _gauges(self):
        try:
            return {k: round(float(v), 2) for k, v in self.app.state.gauges.items() if isinstance(v, (int, float))}
        except Exception:
            return {}

    def _stances(self):
        try:
            st = self.app.stances.current(self.last_his) if self.app.stances else None
            return st if isinstance(st, (str, list, dict, type(None))) else str(st)
        except Exception:
            return None

    # ---- verbs
    def send(self, text, ts=None):
        with self.lock:
            ts = self.vt if ts is None else to_ts(ts)
            if ts > self.vt:
                self.advance(ts)
            self.sends.append((ts, str(text)))
            return {"ok": True, "virtual_ts": ts}

    def add_env(self, events):
        with self.lock:
            for ev in events:
                self.env.append((to_ts(ev["ts"]), ev))
            return {"ok": True, "queued": len(self.env)}

    def _snapdir(self, name):
        return os.path.join(self.run_dir, "snapshots", "S", name)

    def snapshot(self, name):
        with self.lock:
            d = self._snapdir(name)
            os.makedirs(d, exist_ok=True)
            dst = sqlite3.connect(os.path.join(d, "save.db"))
            with self.app.store.lock:
                self.app.store.conn.backup(dst)
            dst.close()
            with open(os.path.join(d, "arm.json"), "w", encoding="utf-8") as fh:
                json.dump({"virtual_ts": self.vt, "sends": self.sends, "env": self.env,
                           "n_out": self.n_out}, fh, default=str)
            return {"ok": True, "virtual_ts": self.vt}

    def restore(self, name):
        with self.lock:
            d = self._snapdir(name)
            meta = json.load(open(os.path.join(d, "arm.json"), encoding="utf-8"))
            db = self.app.store.conn
            path = None
            try:
                path = self.app.config.logging.db_path
                db.close()
            except Exception:
                pass
            for suf in ("", "-wal", "-shm"):
                try:
                    os.remove(path + suf)
                except OSError:
                    pass
            shutil.copyfile(os.path.join(d, "save.db"), path)
            if self.seed_him:   # the working copy only, never the snapshot file
                bench_seed.apply_to_db(path, meta["virtual_ts"])
            self.vt = meta["virtual_ts"]
            self.sends = [tuple(s) for s in meta["sends"]]
            self.env = [tuple(e) for e in meta["env"]]
            self.n_out = meta["n_out"]
            self.last_restore = name
            self._build_app()
            self._clock_file()
            return {"ok": True, "virtual_ts": self.vt}

    def peer_in(self, msgs):
        with self.lock:
            self.ch.peer_in(msgs)
            return {"ok": True}

    def inject(self, target, value):
        with self.lock:
            if target == "seed.him":
                # bench default (tk-xhv): his live relationship primitives into the save, so he is admitted. Lands
                # on the running App's store now and at every later restore; false turns it off (stranger mode).
                if not isinstance(value, bool):
                    raise ValueError("seed.him takes true or false")
                self.seed_him = value
                changed = bench_seed.apply_to_store(self.app.store, self.vt) if value else {}
                return {"ok": True, "seeded": sorted(changed), "removed": self.removed(), "held": dict(self.holds),
                        "overlays": list(self.overlays)}
            if target.startswith("overlay."):
                name = target[8:]
                load_overlay(name)   # KeyError on an unknown name, before anything changes
                if value is not True:
                    raise ValueError(f"{target} takes true (an overlay is merged at an App build, not undone)")
                if not self.last_restore:
                    raise ValueError(f"{target} is applied at boot: restore a snapshot first")
                if name not in self.overlays:
                    self.overlays.append(name)
                self.restore(self.last_restore)   # same save, App rebuilt from the config with the overlay in it
                return {"ok": True, "removed": self.removed(), "held": dict(self.holds), "overlays": list(self.overlays)}
            sk = apply_inject(self.app, target, value)
            if target.startswith("hold."):
                for g, v in hold_pairs(target, value):
                    if v is None:
                        self.holds.pop(g, None)
                    else:
                        self.holds[g] = float(self.app.state.gauges[g])
            if sk:
                self.overrides[sk] = value   # a later restore builds its App with it too
                if sk in BOOT_ONLY and value is False:
                    if not self.last_restore:
                        raise ValueError(f"{target} is applied at boot: restore a snapshot first")
                    self.restore(self.last_restore)   # same save, App rebuilt with the override
            return {"ok": True, "removed": self.removed(), "held": dict(self.holds), "overlays": list(self.overlays)}

    def removed(self):
        return sorted(f"{n}.{k}={v}" for (n, k), v in self.overrides.items())

    def state(self):
        a = self.app
        s = {"virtual_ts": self.vt, "sim_day": sim_day(self.start_ts, self.vt), "gauges": self._gauges(),
             "stances": self._stances(), "open_expectations": []}
        try:
            ex = a.expectations
            rows = getattr(ex, "open", None)
            rows = rows() if callable(rows) else rows
            s["open_expectations"] = [str(r)[:200] for r in (rows or [])][:20]
        except Exception:
            pass
        return s

    def stop(self):
        with self.lock:
            try:
                self.app.shutdown()
            except Exception:
                traceback.print_exc()
            try:
                self.app.store.conn.close()
            except Exception:
                pass
            self._release()
            return {"ok": True}


ARM = Arm()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _reply(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def do_GET(self):
        try:
            if self.path.startswith("/control/trace/"):
                oid = self.path.rsplit("/", 1)[1]
                p = os.path.join(ARM.run_dir, "traces", oid + ".json")
                if not os.path.exists(p):
                    return self._reply(404, {"error": "no such output"})
                return self._reply(200, json.load(open(p, encoding="utf-8")))
            if self.path == "/control/state":
                return self._reply(200, ARM.state())
            self._reply(404, {"error": "not found"})
        except Exception as e:
            self._reply(500, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        try:
            d = self._body()
            p = self.path
            if p == "/control/start":
                r = ARM.start(d)
            elif p == "/control/advance":
                r = ARM.advance(d["to"])
            elif p == "/control/send":
                r = ARM.send(d["text"], d.get("ts"))
            elif p == "/control/peer_in":
                r = ARM.peer_in(d["messages"])
            elif p == "/control/env":
                r = ARM.add_env(d["events"])
            elif p == "/control/snapshot":
                r = ARM.snapshot(d["name"])
            elif p == "/control/restore":
                r = ARM.restore(d["name"])
            elif p == "/control/inject":
                r = ARM.inject(d["target"], d["value"])
            elif p == "/control/stop":
                r = ARM.stop()
                self._reply(200, r)
                # tk-1zr: only a process made by main() exits on stop. An in-process server (tests, a
                # harness that cycles stop/start/restore) keeps serving; shutting it down left the
                # next POST in the listen backlog until the 900 s client timeout.
                if getattr(self.server, "exit_on_stop", False):
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            else:
                return self._reply(404, {"error": "not found"})
            self._reply(200, r)
        except (KeyError, ValueError) as e:
            self._reply(409, {"error": f"{type(e).__name__}: {e}"})
        except BaseException as e:   # a SystemExit from the App's boot is an answer, not a dead socket
            traceback.print_exc()
            self._reply(500, {"error": f"{type(e).__name__}: {e}"})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, required=True)
    a = p.parse_args()
    if not (18331 <= a.port <= 18339 or 18361 <= a.port <= 18369) and os.environ.get("BZ_ANY_PORT") != "1":
        raise SystemExit("S control ports are 18331-18339, a run's other minds 18361-18369")
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    srv.exit_on_stop = True
    srv.serve_forever()


if __name__ == "__main__":
    main()
