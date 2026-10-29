"""A run's other minds (tk-1pl, tk-bor): second and later full S minds living in one house with the first one.

Config (driver.load_config): "peers": [{"character": "tomoe", "key": "tomoe", "lang": "en"}], optional "house": {...}.
Each peer is its own S arm process (own port from PEER_BASE_PORT, own save under runs/<run>/peers/<key>/), driven in
lockstep with the first arm by the one driver. The talkapp hub of V3 (docs/peer-talk.md) is the model: sim/peers.py
calls channel.peer_send / peer_updates, BzChannel files them, and PeerHub here is the relay the hub was.

  peer line      who "peer:<speaker key>", to "<recipient key>", call_ids, hub_id (transcript.jsonl)
  her line       who "her" is the first mind to him; a peer's own lines to him are who "her:<key>" (nobody hears them)
  house          one set of place ids; House tells each mind, as a world env line, when another is at home or out
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from ..common import (PEER_BASE_PORT, append_jsonl, iso, read_json, read_jsonl, spawn_hidden)

PEER_MAX = 8


def peer_specs(cfg: dict) -> list:
    """The run's peers as full rows: key defaults to the character, lang to en."""
    out = []
    for p in cfg.get("peers") or []:
        out.append({**p, "key": str(p.get("key") or p["character"]), "lang": p.get("lang", "en")})
    return out


def check_config(cfg: dict):
    ps = cfg.get("peers")
    if not ps:
        return
    if cfg["arm"] != "S":
        raise ValueError("peers: only the S arm runs more than one mind")
    if cfg.get("arm_cmd") is None:
        raise ValueError("peers: needs arm_cmd (a peer is its own arm process)")
    if len(ps) > PEER_MAX:
        raise ValueError(f"peers: at most {PEER_MAX}")
    keys = [cfg["character"]]
    for p in peer_specs(cfg):
        if not p.get("character"):
            raise ValueError("peers: every row needs a character")
        if p["key"] in keys:
            raise ValueError(f"peers: key {p['key']} is used twice (the first mind is {cfg['character']})")
        keys.append(p["key"])


class PeerHub:
    """The relay: a mailbox per mind, a log on disk (runs/<run>/peer_hub.jsonl, one row per message, its line number
    is its id). A recipient nobody registered is dropped and logged, as the talkapp hub answers `known` false."""

    def __init__(self, path, known):
        self.path, self.known = path, set(known)
        self.rows = read_jsonl(path)

    def relay(self, frm: str, to: str, text: str, ts: float, virtual_ts: str, name="", room=None, call_ids=()):
        row = {"id": len(self.rows) + 1, "from": frm, "to": to, "name": name or frm, "text": text, "ts": ts,
               "virtual_ts": virtual_ts, "call_ids": list(call_ids), "known": to in self.known}
        if room:
            row["room"] = room
        self.rows.append(row)
        append_jsonl(self.path, row)
        return row

    def mail(self, key: str, after: int = 0) -> list:
        """What was written to `key` after id `after`, in the hub's wire shape (sim/peers.py poll reads these)."""
        return [{k: r[k] for k in ("id", "from", "name", "text", "ts", "room") if k in r}
                for r in self.rows if r["to"] == key and r["id"] > after]

    def truncate(self, n: int):
        self.rows = self.rows[:n]
        self.path.write_text("".join(__import__("json").dumps(r, ensure_ascii=False) + "\n" for r in self.rows),
                             encoding="utf-8")


class House:
    """One house, one set of place ids. Each mind's own plan puts her in a place by id; when that id is one of the
    house's rooms she is home, when it is one of `outside` she is out, anything else says nothing. A mind is told once
    per change, as a world line, where each of the others is (and, the first time she is placed, where the ones
    already placed are)."""

    def __init__(self, rooms: dict, outside=()):
        self.rooms, self.outside = rooms, set(outside)
        self.at = {}

    def _state(self, loc: str):
        loc = (loc or "").strip()
        if loc in self.rooms:
            return loc
        return "out" if loc in self.outside else None

    def _line(self, who, state, lang):
        # who: the name already in the viewer's language
        if state == "out":
            return f"{who}は家を出ている。" if lang == "ja" else f"{who} is out of the house."
        room = self.rooms[state].get("ja" if lang == "ja" else "en") or state
        return f"{who}は{room}にいる。" if lang == "ja" else f"{who} is in {room}."

    def update(self, key: str, loc: str, names: dict, langs: dict) -> list:  # names {"ja": {key: name}, "en": {...}}
        """[(viewer_key, text)] for the viewers who should hear about a change of `key`'s place."""
        new = self._state(loc)
        if new is None or self.at.get(key) == new:
            return []
        first = key not in self.at
        self.at[key] = new
        out = []
        for v in self.at:
            if v == key or self.at[v] == "out":
                continue
            out.append((v, self._line(names[langs[v]][key], new, langs[v])))
        if first:  # she has just been placed: she is told about the ones already home
            for o, st in self.at.items():
                if o != key and st != "out" and new != "out":
                    out.append((key, self._line(names[langs[key]][o], st, langs[key])))
        return out


class PeerArm:
    """One extra S arm process: own port, own runs root (BZ_RUNS) so its save, traces and snapshots stay apart."""

    def __init__(self, cfg: dict, spec: dict, rd):
        from . import driver
        self.spec, self.key, self.character = spec, spec["key"], spec["character"]
        self.rd, self.cfg = rd, cfg
        ports = cfg.setdefault("peer_ports", {})
        if self.key not in ports:
            ports[self.key] = driver.claim_port(f"{cfg['run_id']}#{self.key}", PEER_BASE_PORT)
            c = read_json(rd / "config.json") or {}
            if c:  # persist, so a resume finds the same arm
                c.setdefault("peer_ports", {})[self.key] = ports[self.key]
                driver.write_json(rd / "config.json", c)
        self.port = int(ports[self.key])
        from .armclient import Arm
        self.arm = Arm(self.port)
        self.proc = None
        self.delivered = 0

    def ensure_arm(self) -> bool:
        """True when the process had to be spawned (it then needs /control/start)."""
        from . import driver
        if self.arm.up():
            return False
        cmd = driver.arm_command(self.cfg, self.port)
        (self.rd / "logs").mkdir(parents=True, exist_ok=True)
        root = self.rd / "peers" / self.key
        root.mkdir(parents=True, exist_ok=True)
        self.proc = spawn_hidden(cmd, self.rd / "logs" / f"arm_{self.key}.log", cwd=str(driver.REPO),
                                 env_extra={"BZ_RUNS": str(root)})
        t0 = time.time()
        while time.time() - t0 < driver.START_TIMEOUT_S:
            if self.arm.up():
                return True
            if self.proc.poll() is not None:
                raise driver.Pause("arm_error", f"peer arm {self.key} exited {self.proc.returncode}, see logs/arm_{self.key}.log")
            time.sleep(0.5)
        raise driver.Pause("arm_error", f"peer arm {self.key} did not come up")

    def start(self, minds: list):
        from ..arms.s import make_run
        c = self.cfg
        self.arm.start(c["run_id"], self.character, self.spec["lang"], c["clock_start"],
                       timeout=4 * 3600, extra={"role": "peer", "peer_key": self.key,
                                                "peer_contacts": make_run.peer_contact_rows(minds, self.key, self.spec["lang"])})


class Minds:
    """Everything the driver needs of the other minds of a run: arms, hub, house, and the relay after each step."""

    def __init__(self, sess, cfg: dict, rd):
        from ..arms.s import make_run
        self.sess, self.cfg, self.rd = sess, cfg, rd
        self.specs = peer_specs(cfg)
        self.first = cfg["character"]
        self.minds = [{"key": self.first, "lang": cfg["lang"]}] + [
            {"key": p["key"], "lang": p["lang"], **({"call": p["call"]} if p.get("call") else {})} for p in self.specs]
        self.arms = [PeerArm(cfg, p, rd) for p in self.specs]
        self.hub = PeerHub(rd / "peer_hub.jsonl", [m["key"] for m in self.minds])
        h = cfg.get("house") or {}
        self.house = House(h.get("rooms") or make_run.HOUSE["rooms"], h.get("outside") or ())
        self.langs = {m["key"]: m["lang"] for m in self.minds}
        self.names = {m["key"]: m.get("call") or make_run.PEER_NAMES.get(m["key"], {}).get("name") or m["key"]
                      for m in self.minds}
        self.ja_names = {m["key"]: m.get("call") or make_run.PEER_NAMES.get(m["key"], {}).get("name_ja") or m["key"]
                         for m in self.minds}
        self.first_delivered = 0
        self.pool = ThreadPoolExecutor(max(2, len(self.arms) + 1))

    def contacts_of_first(self) -> list:
        from ..arms.s import make_run
        return make_run.peer_contact_rows(self.minds, self.first, self.cfg["lang"])

    def ensure(self) -> bool:
        spawned = False
        for a in self.arms:
            spawned = a.ensure_arm() or spawned
        return spawned

    def start(self):
        for a in self.arms:
            a.start(self.minds)

    def snapshot(self, name: str):
        for a in self.arms:
            a.arm.snapshot(name)

    def restore(self, name: str, hub_len: int):
        for a in self.arms:
            a.arm.restore(name)
            a.delivered = 0
        self.first_delivered = 0
        self.hub.truncate(hub_len)
        self.house.at = {}

    def stop(self):
        for a in self.arms:
            a.arm.stop()

    def advance(self, target: datetime) -> list:
        """Every arm to `target`, at once; then the relay. Returns the first mind's outputs."""
        sess, t = self.sess, iso(target)
        fut = {a.key: self.pool.submit(a.arm.advance_full, t) for a in self.arms}
        first = sess.arm.advance_full(t)
        res = {self.first: first, **{k: f.result() for k, f in fut.items()}}
        self.relay(res, t)
        for a in self.arms:  # a peer's own lines to him: nobody hears them, kept apart from "her"
            sess.collect(res[a.key].get("outputs", []), who=f"her:{a.key}", arm=a.arm)
        return first.get("outputs", [])

    def relay(self, res: dict, t: str):
        """Peer lines to the hub and the transcript, house presence to each mind as world lines, mail to each arm."""
        from ..common import norm_ts
        sess = self.sess
        sent = sorted(((float(m.get("ts") or 0), key, m) for key, r in res.items() for m in r.get("peer_out") or []),
                      key=lambda x: x[0])
        for ts, key, m in sent:
            vt = norm_ts(ts)
            row = self.hub.relay(key, str(m["to"]), str(m["text"]), ts, vt, name=m.get("name", ""),
                                 room=m.get("room"), call_ids=m.get("call_ids") or [])
            sess.add_line(f"peer:{key}", vt, row["text"], to=row["to"], kind="peer", call_ids=row["call_ids"],
                          hub_id=row["id"], known=row["known"])
        told = {}
        for key, r in res.items():
            for viewer, text in self.house.update(key, (r.get("place") or {}).get("location", ""),
                                                  {"ja": self.ja_names, "en": self.names}, self.langs):
                told.setdefault(viewer, []).append({"ts": t, "kind": "world", "text": text, "source": f"house:{key}"})
        for viewer, evs in told.items():
            if viewer == self.first:
                sess.arm.env(evs)
                for e in evs:
                    sess.add_line("env", e["ts"], e["text"], kind="world", source=e["source"])
            else:
                next(a for a in self.arms if a.key == viewer).arm.env(evs)
        mail = self.hub.mail(self.first, self.first_delivered)
        if mail:
            sess.arm.peer_in(mail)
            self.first_delivered = mail[-1]["id"]
        for a in self.arms:
            mail = self.hub.mail(a.key, a.delivered)
            if mail:
                a.arm.peer_in(mail)
                a.delivered = mail[-1]["id"]

