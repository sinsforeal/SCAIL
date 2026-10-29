"""Run driver: owns virtual time, drives one arm through simulated days with simulated him and the env script.

Layout per run (var/bzombie/runs/<run_id>/): config.json, clock.json, state.json, transcript.jsonl, env/day_<n>.json,
traces/<output_id>.json, snapshots/<arm>/<name>/ (arm side) and snapshots/harness/<name>.json (harness side), logs/.
"""
from __future__ import annotations

import contextlib
import json
import os
import socket
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from .. import credits, llm
from ..common import (ARM_BASE_PORT, GATEWAY, VAR, append_jsonl, day_start, iso, norm_ts, parse_ts, read_json, read_jsonl,
                      run_dir, spawn_hidden, to_him, write_json)
from ..env import writer
from ..sim_him import him
from . import script as hscript  # run_day has a local named script (the env script)
from .armclient import Arm, ArmError

REPO = Path(__file__).resolve().parents[2]
START_TIMEOUT_S = 4 * 3600  # matches the arms' ticket wait (S control.py --timeout); a ticket queue is not an error
# use_limits false: meta 10-22 17:14, the driver itself needs no compute ticket (code path kept).
# claude_cap_usd: credits reservation for the run's claude -p children. cap_usd: gateway cap for the arm's model calls.
DEFAULTS = {"step_s": 600, "max_him_turns_per_day": 60, "use_limits": False, "cpu": 2, "mem_gb": 4,
            "min_look_gap_s": 120, "cap_usd": 5.0, "seed": 1, "claude_cap_usd": 10.0,
            "model": "deepseek-v4.1-flash-1017", "claude_billing": "auto", "queue_timeout_s": 900,
            # simulated him: "gateway" = the run's model as arm X (User 10-22 20:10, not Claude); "claude" = llm.ask
            # "script" = his lines come verbatim from him_script (a run id or a JSONL path), no model call (tk-mz5)
            "him_via": "gateway"}
REQUIRED = ("run_id", "arm", "character", "lang", "sim_days", "clock_start")


class Pause(Exception):
    def __init__(self, reason, error=""):
        self.reason, self.error = reason, error


def load_config(path_or_dict) -> dict:
    cfg = path_or_dict if isinstance(path_or_dict, dict) else read_json(path_or_dict)
    if not cfg:
        raise ValueError(f"cannot read config {path_or_dict}")
    cfg = {**DEFAULTS, **cfg}
    miss = [k for k in REQUIRED if k not in cfg]
    if miss:
        raise ValueError(f"config missing {miss}")
    if cfg["arm"] not in ("S", "P"):
        raise ValueError("arm must be S or P")
    hscript.check_config(cfg)  # him_via script: refuse a missing, empty or other-character script at load
    return cfg


def arm_command(cfg: dict, port: int):
    c = cfg.get("arm_cmd")
    if c == "stub":
        return [sys.executable, "-m", "bzombie.harness.stub_arm", "--port", str(port), "--arm", cfg["arm"]]
    if not c:
        return None
    return [str(x).format(port=port, run_id=cfg["run_id"], arm=cfg["arm"]) for x in c]


def free_port(base: int, span: int = 9) -> int:
    for p in range(base, base + span):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise RuntimeError(f"no free arm port in {base}..{base + span - 1}")


def _listening(p: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", p)) == 0


def claim_port(run_id: str, base: int, span: int = 9) -> int:
    """One arm port per run (10-22 18:42: two S runs both took 18331 and drove one arm; the second run's stop killed
    the first). Claims live in var/bzombie/ports/<port>.json. A claim is ours, or stale when its run is not running
    and nothing listens on the port; a fresh claim is created with O_EXCL so two drivers cannot take the same port."""
    d = VAR / "ports"
    d.mkdir(parents=True, exist_ok=True)
    for p in range(base, base + span):
        f = d / f"{p}.json"
        held = read_json(f)
        if held and held.get("run_id") == run_id:
            return p
        if held:
            st = read_json(run_dir(held.get("run_id", "?")) / "state.json")
            try:
                age = time.time() - datetime.fromisoformat(held.get("claimed", "")).timestamp()
            except ValueError:
                age = 1e9
            # stale only when its run is over, or it never got a state and the claim is old; a created, running
            # or paused run keeps its port (a paused run resumes on it)
            over = (st or {}).get("status") in ("done", "failed") or (st is None and age > 120)
            if not over or _listening(p):
                continue
            # take over atomically: only one driver can rename the stale claim aside (10-22 20:41: two drivers both
            # overwrote a stale 18331 claim, both read back their own write, and cl1_s_tomoe drove Momoka's arm)
            try:
                os.replace(f, d / f"{p}.stale.{os.getpid()}.{held.get('run_id', 'x')}")
            except OSError:
                continue
        if _listening(p):
            continue
        try:
            fd = os.open(str(f), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"run_id": run_id, "claimed": iso(datetime.now())}))
        return p
    raise RuntimeError(f"no free arm port in {base}..{base + span - 1}")


class Session:
    """One run folder plus one live arm process."""

    def __init__(self, cfg: dict, port: int | None = None, out: Path | None = None):
        self.cfg = cfg
        self.rd = run_dir(cfg["run_id"])  # config.json, clock.json, snapshots: what the gateway and arm use
        self.out = out or self.rd  # transcript.jsonl and traces/: a branch writes into branches/<id>/
        if port is None and not cfg.get("arm_port"):
            port = claim_port(cfg["run_id"], ARM_BASE_PORT[cfg["arm"]])
            c = read_json(self.rd / "config.json") or {}
            if c:  # persist, so a resume finds the same arm
                c["arm_port"] = port
                write_json(self.rd / "config.json", c)
            cfg["arm_port"] = port
        self.port = port or int(cfg["arm_port"])
        self.arm = Arm(self.port)
        self.proc = None
        self.spawned = False
        self.env_seen = set()

    def sim_day(self, ts) -> int:
        """1-based simulated day number of a virtual time."""
        t = ts if isinstance(ts, datetime) else parse_ts(ts)
        return (t.date() - parse_ts(self.cfg["clock_start"]).date()).days + 1

    # files
    def set_clock(self, dt):
        write_json(self.rd / "clock.json", {"virtual_ts": iso(dt) if isinstance(dt, datetime) else dt,
                                            "sim_day": self.sim_day(dt), "wall_ts": time.time()})
        if time.time() - getattr(self, "_touched", 0) > 5:
            self._touched = time.time()
            if self.out == self.rd:
                touch_config(self.rd)

    def transcript(self) -> list:
        return read_jsonl(self.out / "transcript.jsonl")

    def add_line(self, who, ts, text, **extra) -> dict:
        rec = {"i": len(self.transcript()), "virtual_ts": ts, "who": who, "text": text,
               "sim_day": self.sim_day(ts), **extra}
        append_jsonl(self.out / "transcript.jsonl", rec)
        return rec

    def add_env(self, events: list, upto: datetime):
        """Env lines go into the transcript when virtual time passes them (kind world|pc)."""
        for e in events:
            if parse_ts(e["ts"]) <= upto and e["ts"] + e["text"] not in self.env_seen:
                self.env_seen.add(e["ts"] + e["text"])
                self.add_line("env", e["ts"], e["text"], kind=e["kind"], source=e.get("source"))

    def collect(self, outputs: list, **extra):
        for o in outputs:
            o["virtual_ts"] = norm_ts(o["virtual_ts"])
            self.add_line("her", o["virtual_ts"], o["text"], output_id=o["output_id"], kind=o.get("kind"),
                          call_ids=o.get("call_ids", []), **extra)
            try:
                tr = self.arm.trace(o["output_id"])
            except ArmError as e:
                if e.budget or e.status == 0:
                    raise
                tr = {"output_id": o["output_id"], "error": str(e)}
            if "virtual_ts" in tr:
                tr["virtual_ts"] = norm_ts(tr["virtual_ts"])
            write_json(self.out / "traces" / f"{o['output_id']}.json", tr)

    def truncate_transcript(self, n: int):
        keep = self.transcript()[:n]
        p = self.out / "transcript.jsonl"
        p.write_text("".join(__import__("json").dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")

    # arm process
    def ensure_arm(self) -> bool:
        """Make sure an arm answers on its port; returns True when it had to be spawned (needs /control/start)."""
        if self.arm.up():
            try:
                rid = (self.arm.state() or {}).get("run_id")
            except ArmError:
                rid = None
            if rid and rid != self.cfg["run_id"]:  # never drive another run's arm
                raise Pause("arm_error", f"port {self.port} serves run {rid}, not {self.cfg['run_id']}")
            return False
        cmd = arm_command(self.cfg, self.port)
        if cmd is None:
            raise Pause("arm_error", f"no arm on port {self.port} and config has no arm_cmd")
        (self.rd / "logs").mkdir(parents=True, exist_ok=True)
        self.proc = spawn_hidden(cmd, self.rd / "logs" / "arm.log", cwd=str(REPO))
        self.spawned = True
        # P's server takes its compute ticket at boot, before it listens (S takes it in /control/start), so a
        # queued ticket looks like a slow boot: wait as long as a ticket may (cl2_p_momoka paused at 300 s, 10-23)
        save_state(self.rd, phase="arm_boot", note="waiting for the arm to boot (P: its compute ticket)")
        t0 = time.time()
        while time.time() - t0 < START_TIMEOUT_S:
            if self.arm.up():
                return True
            if self.proc.poll() is not None:
                raise Pause("arm_error", f"arm exited {self.proc.returncode}, see logs/arm.log")
            time.sleep(0.5)
        raise Pause("arm_error", f"arm did not come up in {START_TIMEOUT_S} s")

    def start_arm(self):
        c = self.cfg
        rd = run_dir(c["run_id"])
        # the arm takes its compute ticket inside /control/start; on a busy PC that wait can be long (10-22 18:29:
        # both S runs died at the old 1800 s client timeout while the limits manager held their memory)
        save_state(rd, phase="arm_start", note="waiting for the arm's compute ticket and boot")
        self.arm.start(c["run_id"], c["character"], c["lang"], c["clock_start"], timeout=START_TIMEOUT_S)
        save_state(rd, phase="running", note="")

    def harness_snapshot(self, name: str, **fields):
        self.arm.snapshot(name)
        write_json(self.rd / "snapshots" / "harness" / f"{name}.json",
                   {"name": name, "transcript_len": len(self.transcript()), **fields})


@contextlib.contextmanager
def ticket(cfg: dict):
    """Limits ticket for a simulated run (who scail/bz_run_<run_id>, prio high, host here)."""
    if not cfg.get("use_limits", False):
        yield None
        return
    from . import limits_client
    with limits_client.granted(who=f"scail/bz_run_{cfg['run_id']}", need={"cpu": cfg["cpu"], "mem_gb": cfg["mem_gb"],
                                                                         "vram_mb": 0},
                               host="here", prio="high", ttl_s=cfg.get("ttl_s", 86400),
                               timeout_s=cfg.get("ticket_timeout_s", 7200)) as t:
        yield t


VIEWER_STATUS = {"created": "running", "running": "running", "paused": "paused", "done": "done", "failed": "failed"}


def touch_config(rd: Path, status: str | None = None):
    """config.json carries status, started_wall, updated_wall for the viewer (contract, Files the viewer reads)."""
    c = read_json(rd / "config.json")
    if c is None:
        return
    if status:
        c["status"] = VIEWER_STATUS[status]
    c.setdefault("started_wall", time.time())
    c["updated_wall"] = time.time()
    write_json(rd / "config.json", c)


def save_state(rd: Path, **kv):
    st = read_json(rd / "state.json", {}) or {}
    st.update(kv, updated=iso(datetime.now()))
    write_json(rd / "state.json", st)
    touch_config(rd, kv.get("status"))
    return st


def init_run(cfg: dict) -> Path:
    rd = run_dir(cfg["run_id"])
    if (rd / "state.json").exists():
        raise ValueError(f"run {cfg['run_id']} exists; use resume")
    rd.mkdir(parents=True, exist_ok=True)
    write_json(rd / "config.json", cfg)  # the gateway reads model, lang, cap_usd from here
    save_state(rd, status="created", day=0, cursor=cfg["clock_start"], next_look=None, snapshot=None)
    return rd


def drive(run_id: str):
    """Run or resume. Blocks. Pauses cleanly on budget, arm error, claude error, pause flag, ticket timeout."""
    rd = run_dir(run_id)
    cfg = load_config(rd / "config.json")
    if os.environ.get("BZ_LLM_STUB") == "1":  # canned him/env/judge answers: the viewer badges the run STUB
        c = read_json(rd / "config.json") or {}
        if not c.get("stub"):
            write_json(rd / "config.json", {**c, "stub": True})
        cfg["stub"] = True
    res = None
    try:
        with ticket(cfg):
            res = open_credits(cfg, rd)
            _drive(cfg, rd)
    except TimeoutError as e:
        save_state(rd, status="paused", reason="limits_ticket", error=str(e)[:400])
    except credits.GrantExhausted as e:  # one-time grant used up: resume on the bench session's queue (normal agents)
        save_state(rd, status="paused", reason="grant_exhausted", error=str(e)[:600])
    except credits.CreditsRefused as e:  # claude -p never runs on the subscription
        save_state(rd, status="paused", reason="credits_refused", error=str(e)[:600])
    except Pause as p:
        save_state(rd, status="paused", reason=p.reason, error=p.error[:600])
    except Exception as e:  # a bug, not a resumable condition
        save_state(rd, status="failed", reason="exception", error=f"{type(e).__name__}: {e}"[:600])
        raise
    finally:
        close_credits(res, rd)


def open_credits(cfg: dict, rd: Path):
    """Reserve and dispatch the run's claude credits, then arm llm.session. None when BZ_LLM_STUB=1 (no real claude)."""
    if os.environ.get("BZ_LLM_STUB") == "1":
        return None
    billing = cfg.get("claude_billing", "auto")
    if billing not in ("auto", "credits", "queue"):
        raise ValueError(f"claude_billing must be auto, credits or queue, not {billing!r}")
    qt = cfg.get("queue_timeout_s", 900)
    if billing == "queue":  # no reservation at all
        llm.session = llm.Session(None, rd, cfg["claude_cap_usd"], "queue", qt)
        return None
    res = credits.Reservation(f"scail/bzombie_{cfg['run_id']}", cfg["claude_cap_usd"], os.getpid())
    try:
        res.open()
    except credits.GrantExhausted:
        if billing != "auto":
            raise
        llm.session = llm.Session(None, rd, cfg["claude_cap_usd"], "auto", qt)  # grant gone: straight to the queue
        llm.session.mode = "queue"
        return None
    llm.session = llm.Session(res, rd, cfg["claude_cap_usd"], billing, qt)
    return res


def close_credits(res, rd: Path):
    """Settle once with the summed child costs; runs on done, pause, stop and crash."""
    llm.session = None
    if res is None:
        return
    try:
        res.settle()
    except credits.CreditsRefused as e:
        save_state(rd, settle_error=f"settle failed (spent {res.spent_usd:.4f}): {e}"[:600])


def _drive(cfg: dict, rd: Path):
    st = read_json(rd / "state.json")
    (rd / "logs").mkdir(parents=True, exist_ok=True)
    flag = rd / "pause.flag"
    if flag.exists():
        flag.unlink()
    sess = Session(cfg)
    save_state(rd, status="running", pid=os.getpid(), reason=None, error=None)
    try:
        spawned = sess.ensure_arm()
        if st.get("snapshot"):
            if spawned:
                sess.start_arm()
            h = read_json(rd / "snapshots" / "harness" / f"{st['snapshot']}.json")
            sess.arm.restore(st["snapshot"])
            sess.truncate_transcript(h["transcript_len"])
            cursor, next_look, day = parse_ts(h["cursor"]), h.get("next_look"), h["day"]
        else:
            sess.start_arm()
            cursor, next_look, day = parse_ts(cfg["clock_start"]), None, 0
            sess.set_clock(cursor)
            sess.harness_snapshot("start", cursor=iso(cursor), next_look=None, day=0)
            save_state(rd, snapshot="start")
        sess.set_clock(cursor)
        profile = {} if cfg.get("him_via") == "script" else him.load_profile(cfg["character"])
        while day < cfg["sim_days"]:
            next_look = run_day(sess, cfg, rd, profile, day, cursor, next_look)
            day += 1
            cursor = day_start(cfg["clock_start"], day)
            name = f"day{day}_end"
            sess.harness_snapshot(name, cursor=iso(cursor), next_look=next_look, day=day)
            save_state(rd, day=day, cursor=iso(cursor), snapshot=name, next_look=next_look)
        if day:  # leave the clock at the last simulated moment and the last day run, not the next day's 00:00
            sess.set_clock(cursor - timedelta(seconds=1))
        save_state(rd, status="done")
        sess.arm.stop()
    except ArmError as e:
        sess.arm.stop() if not e.budget else None
        raise Pause("budget" if e.budget else "arm_error", str(e))
    except llm.CapReached as e:
        sess.arm.stop()
        raise Pause("claude_cap", str(e))
    except llm.QueueUnavailable as e:  # worker_down or worker_timeout; resume after the worker is back
        sess.arm.stop()
        raise Pause(e.reason, str(e))
    except (RuntimeError, ValueError, OSError) as e:
        if isinstance(e, Pause):
            raise
        raise Pause("error", f"{type(e).__name__}: {e}")
    except Pause:
        sess.arm.stop()
        raise
    except Exception:  # a bug: still never leave an arm process running
        sess.arm.stop()
        raise


def world_runner(sess: Session, cfg: dict, rd: Path):
    """One castworld.bench.WorldRunner per session. cfg["world"]: {} or {"spec": path, "seed": n, "gateway": url}."""
    if getattr(sess, "_world", None) is None:
        sys.path.insert(0, str(REPO)) if str(REPO) not in sys.path else None
        from castworld.bench import WorldRunner
        w = cfg["world"] if isinstance(cfg["world"], dict) else {}
        sess._world = WorldRunner(rd, cfg["run_id"], w, seed=cfg.get("seed", 1))
    return sess._world


def run_day(sess: Session, cfg: dict, rd: Path, profile: dict, day: int, cursor: datetime, next_look):
    ds = day_start(cfg["clock_start"], day)
    de = ds + timedelta(days=1)
    cursor = max(cursor, ds)
    tz = cfg.get("him_timezone")  # his zone (IANA name); None = the transcript's Tokyo clock
    script = writer.day_script(cfg["character"], cfg["seed"], day, ds, tz)
    if cfg.get("world") is not None:  # arm D (tk-71n): the cast world owner adds kind world events (castworld/bench.py)
        script = {**script, "events": sorted(list(script["events"]) + world_runner(sess, cfg, rd).day(day, iso(ds)[:10]),
                                             key=lambda e: e["ts"])}
    write_json(rd / "env" / f"day_{day}.json", script)
    evs =[e for e in script["events"] if parse_ts(e["ts"]) >= cursor]
    if evs:
        sess.arm.env(evs)
    plan = script.get("him_plan", "")
    for e in script["events"]:  # lines already in the transcript (replay after a restore never doubles them)
        if parse_ts(e["ts"]) < cursor:
            sess.env_seen.add(e["ts"] + e["text"])
    step = timedelta(seconds=cfg["step_s"])
    gap = timedelta(seconds=cfg["min_look_gap_s"])
    nl = parse_ts(next_look) if next_look else cursor
    turns = 0
    scripted = cfg.get("him_via") == "script"
    if scripted:
        sc = hscript.load(cfg["him_script"], cfg["character"])
        # his lines of this day not yet in the transcript, at their own ts; no model call, no turn cap
        slines = [(parse_ts(l["virtual_ts"]), l["text"]) for l in sc["lines"] if cursor <= parse_ts(l["virtual_ts"]) < de]
        si = 0
        if ds > parse_ts(sc["last_ts"]) and not (read_json(rd / "state.json", {}) or {}).get("script_ended"):
            # the reference ran fewer days: stop sending, say so once (state.json + driver log)
            note = f"day {day + 1}: script {sc['source']} ends at {sc['last_ts']}, no more lines of his from here"
            save_state(rd, script_ended=note)
            print("him_script:", note, flush=True)
    while cursor < de:
        if (rd / "pause.flag").exists():
            raise Pause("pause_flag")
        if scripted:
            while si < len(slines) and slines[si][0] <= cursor:  # due now; the arm may be asleep or mid-reply: it copes
                sess.set_clock(cursor)
                sess.arm.send(slines[si][1], iso(slines[si][0]))
                sess.add_line("him", iso(slines[si][0]), slines[si][1])
                si += 1
            target = min(cursor + step, de, slines[si][0] if si < len(slines) else de)
            sess.set_clock(target)
            outs = sess.arm.advance(iso(target))
            sess.add_env(script["events"], target)
            sess.collect(outs)
            cursor = target
            continue
        if nl <= cursor and turns < cfg["max_him_turns_per_day"]:
            conv = sess.transcript()
            today = iso(to_him(cursor, tz))[:10]  # his calendar day
            today_me = sum(1 for e in conv if e["who"] == "him" and iso(to_him(parse_ts(e["virtual_ts"]), tz))[:10] == today)
            d = him.decide(profile, conv, plan, cursor, cfg["lang"], today_me, him_tz=tz,
                           run_id=cfg["run_id"] if cfg.get("him_via") == "gateway" else None)
            turns += 1
            sess.set_clock(cursor)
            if d["write"]:
                sess.arm.send(d["text"], iso(cursor))
                sess.add_line("him", iso(cursor), d["text"])
            nl = max(parse_ts(d["next_look"]) if d["next_look"] else cursor, cursor + gap)
            continue
        if turns >= cfg["max_him_turns_per_day"] and nl <= cursor:
            nl = de
        target = min(cursor + step, de, nl if nl > cursor else de)
        sess.set_clock(target)
        outs = sess.arm.advance(iso(target))
        sess.add_env(script["events"], target)
        sess.collect(outs)
        cursor = target
    return iso(nl)
