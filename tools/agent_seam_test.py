"""A cast member who runs as her own process speaks for herself.

    python tools/agent_seam_test.py          # exit 1 on any failure; run by smoke

Builds the first character on a COPY of her save with every model call
answered by a recorder that spends nothing and a hub that lives in this
process, marks one cast row in the COPY's cast file as running herself, and
drives the two paths her words used to come out of:

  the exchange -- at her turn nothing is written for her, the room asks her
  and waits, her turn arriving late is appended where it lands and reaches
  the record and the shared world's rooms table with her as the speaker, and
  at the deadline the room says so and goes on without her;

  the beat -- the plan still puts her there, no words are written for her,
  the moment goes to her mailbox and the beat waits for what comes back. One
  case goes through the PLANNER rather than putting a beat in the store by
  hand, because the planner deleted every beat it wrote for her for two days:
  the writer refuses her words, correctly, and the line under it dropped every
  beat that had none.

And a silence: when the room asks and she would say nothing, that answer goes
back as an answer, so the room settles at once instead of sitting out its
deadline, and neither record gains an empty turn.

It also proves the two things that are easy to lose. **The unmarked case is
byte for byte what it was**: the same speaker's prompt, rendered with the mark
on somebody else's row and without it, is the same bytes. And **a room is a
thing you can join and leave**: a turn goes to the members who were in the
room when it was said, and to nobody who joined after it or left before it.

Nothing is started, nothing live is opened for writing, and the live cast file
is never marked.
"""
import io
import json
import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FAILURES = []
# Whose row is marked, whose hub id her process would register under, and
# who is in the room with her. Taken off the roster of whatever character
# this is run against rather than written here: these were three of her
# people by name, in a check smoke runs before every restart, so pointing
# it at a second character tested nobody.
WHO = HUB = OTHER = ""


def _fixture_people(config):
    """(the one who runs herself, her hub id, one other person in the room).

    Two people on her roster who are neither her, nor him, nor family: a
    family row is not in the group chat, and the group is what the seam is
    driven through."""
    from sim import roster
    keys = []
    for role, rec in roster.everyone(config).items():
        key = str(rec.get("key") or role)
        if str(rec.get("role_id") or "") in ("self", "partner"):
            continue
        if roster.is_family(config, key):
            continue
        keys.append(key)
    keys.sort()
    # the row that already runs herself first, because the case this drives
    # is what happens when one does
    keys.sort(key=lambda k: (not roster.agent_of(config, k), k))
    if len(keys) < 2:
        raise SystemExit("[seam] this character has fewer than two people in her group; "
                         "there is no room to drive the seam through")
    who = keys[0]
    return who, (roster.agent_of(config, who) or who.lower().replace("-", "")), keys[1]


def check(ok, what, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILURES.append(what)
    return ok


# ---------------------------------------------------------------- the stubs

class Recorder:
    """Every model call, recorded and answered from a canned reply. Attached
    to the App's one LLM object, which every module was handed at build."""

    def __init__(self, app):
        self.calls = []
        self.messages = []
        # what a canned day script hands back, set by the caller that drives
        # the planner, and whether she would say nothing when a room asks
        self.beats = []
        self.silent = False
        app.llm.call = self.call
        app.llm.call_json = self.call_json

    def call(self, role, messages, *a, **k):
        self.calls.append(role)
        self.messages.append(messages)
        return "recorded answer"

    def call_json(self, role, messages, *a, **k):
        self.calls.append(role)
        self.messages.append(messages)
        if role == "peer_reply":
            return {"messages": [] if self.silent else ["recorded answer"], "gist": "recorded"}, ""
        if role == "cast_day":
            return {"beats": list(self.beats), "settled": [], "notes": ""}, ""
        return {"turns": [{"who": "?", "ja": "録音された返事"}], "gist": "", "about_him": ""}, ""

    def count(self, role, since=0):
        return self.calls[since:].count(role)


class Hub:
    """The hub, in this process. `peer_send` is what leaves; `deliver` is what
    another character's process would have put in this one's mailbox."""

    def __init__(self):
        self.out = []
        self.inbox = []
        self.n = 100000          # past any cursor a copied save is carrying

    def peer_send(self, to, text, room=None):
        self.out.append({"to": str(to), "text": str(text), "room": room})
        return True

    def peer_updates(self, after=0):
        return [dict(m) for m in self.inbox if int(m["id"]) > int(after or 0)]

    def deliver(self, frm, text, room, ts=0.0):
        self.n += 1
        self.inbox.append({"id": self.n, "from": frm, "name": frm, "text": text,
                           "ts": ts, "room": room})
        return self.n

    def last(self, to=None):
        rows = [r for r in self.out if to is None or r["to"] == to]
        return rows[-1] if rows else None


def marked_cast(app, tmp, mark=True):
    """A copy of the cast file beside the scratch save, with one row marked as
    running her own process. The live `data/cast.json` is never touched."""
    src = app.config.character.cast_file
    with io.open(os.path.join(ROOT, "data", "cast.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    if mark:
        data["people"][WHO]["agent"] = HUB
    else:
        # nobody is marked: every row, not only hers. One of them already
        # carries `agent` in the live file, and stripping only hers left the
        # "nobody runs herself" case with somebody who does.
        for row in data["people"].values():
            if isinstance(row, dict):
                row.pop("agent", None)
    dst = os.path.abspath(tmp) + (".cast_marked.json" if mark else ".cast_plain.json")
    with io.open(dst, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    app.config.character.cast_file = dst
    return src


# ------------------------------------------------------------------- the run

def main():
    from tools import harness
    from sim import roster
    from sim.rooms import name_for

    tmp = os.path.join(tempfile.gettempdir(), "agent_seam_test.db")
    print("[seam] building the first character on a copy of her save, no model call, no network")
    harness.refuse_network()
    app = harness.build_on(tmp, "config.json", "data/world.db")
    global WHO, HUB, OTHER
    WHO, HUB, OTHER = _fixture_people(app.config)
    print("[seam] the fixture is her roster's own: %s (hub %s) and %s"
          % (WHO, HUB, OTHER))
    rec = Recorder(app)
    hub = Hub()
    app.tg.peer_send = hub.peer_send
    app.tg.peer_updates = hub.peer_updates
    app.peers.rooms.channel = app.tg

    # one moment, held still: two renders of the same prompt taken a second
    # apart differ in the clock line, and this compares bytes
    T = app.clock.now_ts()
    app.clock.now_ts = lambda: T
    # ...and what each person has to bring up today, which the call that is
    # shown it SPENDS -- offering it again tomorrow is how a pocket becomes a
    # script. A second render of the SAME moment has to start from the same
    # pocket, so it is put back the way the clock is held. Until 2026-09-08
    # nobody had ever had a pocket item and the renders matched by accident.
    _pockets = json.dumps(app.store.get("cast_pockets", {}) or {}, ensure_ascii=False)

    def hold_still():
        app.store.set("cast_pockets", json.loads(_pockets))
    ex, cast = app.exchange, app.cast
    today = app.clock.date_str()
    turns = [{"who": roster.record_name(app.config, WHO), "ja": "ねえ、週末どうする？", "hm": "12:30", "ts": T - 300}]

    # ---- 1. nobody is marked: what it was
    marked_cast(app, tmp, mark=False)
    check(not roster.agents(app.config), "with no row marked, the roster says nobody runs herself")
    random.seed(7)
    hold_still()
    n = len(rec.calls)
    ex._one_speaker(OTHER, "line", turns)
    plain = rec.messages[-1] if len(rec.calls) > n else None
    random.seed(7)
    hold_still()
    n = len(rec.calls)
    ex._one_speaker(OTHER, "line", turns)
    again = rec.messages[-1] if len(rec.calls) > n else None
    check(plain is not None and plain == again,
          "the same prompt rendered twice is the same bytes (the comparison is worth making)")

    # ---- 2. the mark, and what it does not change
    marked_cast(app, tmp, mark=True)
    check(roster.agent_of(app.config, WHO) == HUB,
          f"a row carrying `agent` reads back as her hub id", roster.agent_of(app.config, WHO))
    check(roster.is_agent(app.config, WHO) and not roster.is_agent(app.config, OTHER),
          "and only her row; everybody else is still this process's to write")
    check((roster.by_agent(app.config, HUB) or {}).get("key") == WHO,
          "a turn arriving under that hub id resolves to her roster row")
    check(bool(roster.rec_of(app.config, WHO).get("ja")) and bool(roster.rec_of(app.config, WHO).get("role_id")),
          "her sheet, her role and her name are untouched by the mark")
    random.seed(7)
    hold_still()
    n = len(rec.calls)
    ex._one_speaker(OTHER, "line", turns)
    marked = rec.messages[-1] if len(rec.calls) > n else None
    check(marked == plain,
          "and somebody else's prompt is byte for byte what it was before the mark")

    # ---- 3. her turn is not written here
    n = len(rec.calls)
    out, _g, _ah = ex._one_speaker(WHO, "line", turns)
    check(out == [] and len(rec.calls) == n,
          "at her turn the speaker call writes nothing and costs nothing",
          f"{len(rec.calls) - n} model call(s)")

    # ---- 4. an exchange that would have been hers
    room = name_for("line", WHO)
    beat = {"time": app.clock.hm(), "who": roster.record_name(app.config, WHO), "kind": "line",
            "ja": "ねえ、週末どうする？", "text": "she asks about the weekend", "salience": 3}
    live = ex.start(beat, {"phone_access": "free"})
    members = ex._rooms().members(room)
    check(WHO in members and members[WHO].get("agent") == HUB,
          "the room has a membership, and she is in it as somebody who writes her own turns",
          ", ".join(sorted(members)))
    check(len(members) == 2, "a two-person exchange is a room of two", ", ".join(sorted(members)))
    app.peers.tick(None)
    check(hub.last(HUB) is None,
          "the opener is hers, and a room never sends anybody her own words back",
          str(len(hub.out)) + " message(s) out")

    # her turn comes round: the room asks and waits, and pays nothing
    live = ex.live()
    live["side"], live["next_ts"] = "theirs", 0
    ex._save_live(live)
    n = len(rec.calls)
    ex.tick({"phone_access": "free"})
    live = ex.live()
    check(live is not None and live.get("awaiting") and live["awaiting"][0]["key"] == WHO,
          "the exchange waits on her instead of writing her")
    check(len(rec.calls) == n, "and no model call was made for her turn",
          f"{len(rec.calls) - n} call(s)")
    app.peers.tick(None)
    ask = hub.last(HUB)
    check(ask is not None and ask["room"]["asking"] and ask["room"]["present"],
          "her mailbox has the ask: the room, who is in it, and how long it will wait",
          f"waits {(ask or {}).get('room', {}).get('wait_s')}s")
    before = len(live.get("turns") or [])
    n = len(rec.calls)
    ex.tick({"phone_access": "free"})
    check(len(ex.live().get("turns") or []) == before and len(rec.calls) == n,
          "a pass while it waits adds nothing and spends nothing")

    # her own process answers
    hub.deliver(HUB, "土曜なら空いてるよ", dict(ask["room"], asking=False), ts=T)
    app.peers.tick(None)
    ex.tick({"phone_access": "free"})
    live = ex.live() or {}
    last = (live.get("turns") or [])[-1] if live.get("turns") else {}
    check(last.get("ja") == "土曜なら空いてるよ",
          "her own words are appended to the record, at the end where they landed",
          f"{last.get('hm')} {last.get('who')}")
    check(last.get("who") == roster.record_name(app.config, WHO),
          "with her as the speaker, by the name the record uses", str(last.get("who")))
    check(not live.get("awaiting") and live.get("side") == "hers",
          "the room is no longer waiting, and it is her turn again")
    rows = [r for r in (app.world_shared.turns(today, room) or []) if r.get("ja") == "土曜なら空いてるよ"]
    check(bool(rows), "and the turn is in the shared world's rooms table",
          f"{len(app.world_shared.turns(today, room) or [])} row(s) in {room}")
    wrote = app.world_shared.members(room) or []
    check(any(r.get("member") == WHO and r.get("agent") == HUB for r in wrote),
          "the membership is in the world file too, for a process that is not this one",
          f"{len(wrote)} member row(s)")

    # ---- 5. the deadline
    live["side"], live["next_ts"], live["awaiting"] = "theirs", 0, []
    ex._save_live(live)
    ex.tick({"phone_access": "free"})
    live = ex.live() or {}
    check(bool(live.get("awaiting")), "asked again on her next turn")
    wait = float(app.config.exchange.agent_turn_deadline_seconds)
    app.clock.now_ts = lambda: T + wait + 1
    n = len(rec.calls)
    ex.tick({"phone_access": "free"})
    after = ex.live()
    check(after is None or WHO in (after.get("agent_gave_up") or []),
          "at the deadline the room goes on without her")
    check(len(rec.calls) == n, "and still nothing was written in her voice",
          f"{len(rec.calls) - n} call(s)")
    app.clock.now_ts = lambda: T

    # ---- 6. the beat
    ex.store.set("exchange_live", None)
    b = {"time": app.clock.hm(), "who": roster.record_name(app.config, WHO), "kind": "line",
         "ja": "", "text": "she opens about the weekend", "salience": 3, "done": True}
    cast.store.set("cast_beats", {"date": today, "beats": [dict(b)]})
    n = len(rec.calls)
    check(cast._speak_beat(dict(b), today) == "" and len(rec.calls) == n,
          "the planner writes no words for a beat of hers, and pays for none")
    got = cast.deliver([dict(b)])
    check(got == [], "and the beat is not delivered while it has no words")
    stored = (cast.beats_for(today) or {}).get("beats", [{}])[0]
    check(stored.get("done") is False and stored.get("agent_asked_ts"),
          "the beat waits, put back with the moment it was asked for")
    app.peers.tick(None)
    ask = hub.last(HUB)
    check(ask is not None and ask["room"]["about"] == "beat" and "weekend" in ask["room"]["cue"],
          "her mailbox has the moment: the time, the room, and what the plan has her opening about",
          (ask or {}).get("text", "")[:60])
    hub.deliver(HUB, "土曜あいてる？", dict(ask["room"], asking=False), ts=T)
    app.peers.tick(None)
    got = cast.deliver([dict(b)])
    check(len(got) == 1, "and when her words arrive the beat is delivered like any other",
          str(got))

    # ---- 6a. the planner's own filter keeps a wordless beat of hers
    #
    # Section 6 puts the beat in the store by hand, which is how the planner
    # deleting every beat it planned for her went unseen for two days: the
    # writer refuses to write her words, correctly, and the line under it
    # dropped every beat with no words in it. This drives `plan_day` and
    # asserts hers is in what comes back.
    hers = roster.record_name(app.config, WHO)
    theirs = roster.record_name(app.config, OTHER)
    cast.store.set("cast_beats", {})
    cast.store.set("cast_beats_prev", {})
    rec.beats = [{"time": "12:35", "who": hers, "kind": "line", "salience": 3,
                  "about": "she says what time everybody is meeting"},
                 {"time": "12:40", "who": theirs, "kind": "line", "salience": 2,
                  "about": "she asks whether anybody has the homework"}]
    plan = cast.plan_day(app.store.get_schedule(today) or {}, today, force=True) or {}
    kept = {b.get("who"): b for b in (plan.get("beats") or [])}
    check(hers in kept and not str(kept.get(hers, {}).get("ja") or "").strip(),
          "the planner keeps her beat with no words in it: a beat with no words is what the "
          "ask path is for",
          "kept: " + (", ".join(sorted(kept)) or "none"))
    check(theirs not in kept,
          "and a beat for somebody this process DOES write for, with no words, is still dropped")

    # ---- 7. joining and leaving
    rooms = ex._rooms()
    g = name_for("group", "")
    rooms.settle(g, [OTHER, WHO], at_ts=T - 1000)
    rooms.leave(g, WHO, at_ts=T - 500)
    n = len(hub.out)
    rooms.post_turn(g, "group", today, {"who": OTHER, "ja": "誰かいる？", "hm": "20:00", "ts": T}, OTHER)
    app.peers.tick(None)
    check(len(hub.out) == n, "somebody who has left the room is sent nothing said after she left")
    rooms.join(g, WHO, at_ts=T + 10)
    n = len(hub.out)
    rooms.post_turn(g, "group", today, {"who": OTHER, "ja": "まだいる？", "hm": "20:05", "ts": T + 5}, OTHER)
    app.peers.tick(None)
    check(len(hub.out) == n, "and nothing said between her leaving and her joining again")
    rooms.post_turn(g, "group", today, {"who": OTHER, "ja": "おかえり", "hm": "20:10", "ts": T + 20}, OTHER)
    app.peers.tick(None)
    check(len(hub.out) == n + 1, "what is said after she joins reaches her, and only that",
          (hub.last(HUB) or {}).get("text", ""))
    rows = {r.get("member"): r for r in (app.world_shared.members(g) or [])}
    check(WHO in rows and float(rows[WHO].get("joined_ts") or 0) == T + 10,
          "and the world file carries the moment she joined", str(rows.get(WHO, {}).get("joined")))

    # ---- 8. the other end: a room somebody else owns
    n = rec.count("peer_reply")
    hub.deliver("someoneelse", "20:20 — group. it is your turn",
                {"id": "group", "kind": "group", "date": today, "hm": "20:20", "asking": True,
                 "turns": [{"who": "誰か", "ja": "ねえ", "hm": "20:19", "ts": T}],
                 "present": ["誰か"], "cue": "the room is waiting for you", "about": "turn",
                 "beat_id": "", "wait_s": 180}, ts=T)
    out_before = len(hub.out)
    app.peers.tick(None)
    check(rec.count("peer_reply") == n + 1,
          "asked for a turn in a room she does not own, she writes it through her own persona",
          f"{rec.count('peer_reply') - n} peer_reply call(s)")
    back = hub.last("someoneelse")
    check(len(hub.out) > out_before and back is not None
          and back["room"]["id"] == "group" and back["room"]["asking"] is False,
          "and it goes back to whoever asked, as one more turn in that room",
          (back or {}).get("text", ""))
    seen = (app.store.get("peer_rooms", {}) or {}).get("group", {})
    check(len(seen.get("turns") or []) >= 2,
          "she keeps the words that arrived and the words she sent, and nothing else",
          f"{len(seen.get('turns') or [])} turn(s), keys: {sorted(seen)}")

    # ---- 8a. a chosen silence goes back as an answer, not as nothing
    rec.silent = True
    out_before = len(hub.out)
    hub.deliver("someoneelse", "20:30 — group. it is your turn",
                {"id": "group", "kind": "group", "date": today, "hm": "20:30", "asking": True,
                 "turns": [{"who": "誰か", "ja": "どう思う？", "hm": "20:29", "ts": T}],
                 "present": ["誰か"], "cue": "the room is waiting for you", "about": "turn",
                 "beat_id": "", "wait_s": 180}, ts=T)
    app.peers.tick(None)
    back = hub.last("someoneelse")
    check(len(hub.out) > out_before and back is not None and back["room"].get("silent") is True,
          "when she would say nothing the room is told so at once, rather than waiting out its "
          "deadline for an answer that has already been given",
          (back or {}).get("text", ""))
    seen = (app.store.get("peer_rooms", {}) or {}).get("group", {})
    check(all(str(t.get("ja") or "").strip() for t in (seen.get("turns") or [])),
          "and her own record of the room gains no empty turn",
          f"{len(seen.get('turns') or [])} turn(s)")
    rec.silent = False

    # ---- 8b. and the owner's side settles on it
    room = name_for("line", WHO)
    live = {"date": today, "who": roster.record_name(app.config, WHO), "kind": "line",
            "turns": [], "side": "theirs", "rounds": 0,
            "awaiting": [{"key": WHO, "who": WHO, "room": room, "hub": HUB,
                          "asked_ts": T, "deadline_ts": T + 180}]}
    ex._rooms().put(WHO, {"id": room, "kind": "line", "about": "turn"}, "", who=WHO)
    ex._take_agent_turns(live)
    check(not live.get("awaiting") and WHO in (live.get("agent_gave_up") or []),
          "the room reads an empty answer as a settled wait and goes on without her",
          f"awaiting {live.get('awaiting')}, gave up {live.get('agent_gave_up')}")
    check(not live.get("turns"), "and the record gains no empty turn either",
          str(live.get("turns")))
    ex.store.set("exchange_live", None)

    print()
    if FAILURES:
        print(f"[seam] {len(FAILURES)} failure(s): " + "; ".join(FAILURES[:6]))
        return 1
    print("[seam] the seam holds: nothing writes a promoted person's words, the room waits, "
          "her own turn lands in the record and in the world, and an unmarked row renders "
          "byte for byte what it did")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
