"""Does tool calling through OpenRouter work for her reply call, per model, and what does it cost.

Standalone. It does not touch `llm.py`, the live save or any running process:
it takes SQLite's own consistent copy of `data/world.db` through a read-only
handle, builds the first character on the copy with `tools/harness.py`, pins
her clock to the moment of a real message of his, and builds the exact
persona request that call went out on (`persona.generate` up to the moment
the request exists, captured there and abandoned). Then it sends that request
to one model twice: once with five read-only tools over her own stores, once
with none.

    python tools/tool_bench.py --out <step dir> --estimate
    python tools/tool_bench.py --out <step dir> --run flash --turns 20
    python tools/tool_bench.py --out <step dir> --run flash --turns 3 --no-tools
    python tools/tool_bench.py --out <step dir> --round-two [--pick-only]

`--run` offers the tools over her prompt exactly as it goes out live, which
tests nothing on its own: her prompt already carries what four of the five
tools return and never says a tool exists, and twenty turns of it produced no
call at all. `--round-two` is the test -- the duplicated lines removed from
the situation block and her diary out of what she carries, the tools named in
the last line she reads, a control on the same five turns as live, and one
turn forced with `tool_choice` to prove the round trip with every raw chunk
written out.

Everything is written under `--out`: `turns.json` (the twenty moments and
their prompt sizes), `estimate.json`, `<model>_<condition>.jsonl` (one row per
turn: every request, every tool call, the reply, the receipt), and
`toolcalls.jsonl` (turn, tool, arguments, result length).

The request shape is `LLM._payload`'s for an OpenRouter provider, rebuilt here
rather than imported so that nothing this bench does can reach the running
bot: the slug the character's config maps her model name to, the pinned host
first with `allow_fallbacks`, the persona role's own temperature and reasoning
effort, no `max_tokens`, `stream: true` with `stream_options.include_usage`.
Two things are added, both only on the tool condition: `tools`, and
`provider.require_parameters` so that a fall-through cannot land on one of the
hosts for the same slug that does not accept tools (two kimi-k3 hosts do not).
`parallel_tool_calls` is not sent: exactly one endpoint of the forty-eight
across these three slugs advertises it, so sending it under
`require_parameters` would empty the host list.
"""
import argparse
import io
import json
import os
import re
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LIVE_DB = "data/world.db"
CONFIG = "config.json"

# The three models, each with the host this project pins it to. The price is
# read live from OpenRouter's endpoint list, not from here.
MODELS = {
    "flash": ("deepseek-v4-flash", "deepseek/deepseek-v4-flash-0731", "together"),
    "kimi": ("kimi-k3", "moonshotai/kimi-k3", "together"),
    "namazu": ("sakana-namazu", "sakana/sakana-namazu", "Sakana AI"),
}


# ---------------------------------------------------------------- the save

def copy_live_save(dst):
    """SQLite's own backup of the live save, taken through a read-only handle.

    A file copy of an open database returns a stale image; the backup API
    walks the pages under a read lock and gives a consistent one. The source
    handle is `mode=ro`, so this cannot write to her save even by accident."""
    if os.path.exists(dst):
        os.remove(dst)
    src = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    out = sqlite3.connect(dst)
    with out:
        src.backup(out)
    out.close()
    src.close()
    return dst


def build(tmp):
    from tools import harness
    harness.refuse_network()          # the build fetches nothing; the bench's own calls are made below
    app = harness.build_on(tmp, CONFIG, LIVE_DB, copy=False)
    _restore_network()
    return app


def _restore_network():
    """Give the process its sockets back after the build.

    `harness.refuse_network` patches `socket.socket.connect` and
    `socket.create_connection` process-wide, which is what makes the build
    honest and fast; the bench's own calls have to go out afterwards."""
    import socket
    import importlib
    fresh = importlib.reload(socket)
    socket.socket.connect = fresh.socket.connect
    socket.create_connection = fresh.create_connection


def pin_clock(app, ts):
    """Her clock frozen at `ts`: sim mode at speed zero.

    The thread reads `clock.now_ts()` and drops every message after it, so a
    pinned clock gives the record as it stood when he sent that message. What
    the pin does NOT rewind is her state, her scene and her stores: those are
    as the save has them now. That is the bench's one deviation from the turn
    as it happened, and it is the same deviation for both conditions."""
    app.clock.mode = "sim"
    app.clock.speed = 0.0
    app.clock._wall_anchor = time.time()
    app.clock._sim_anchor = float(ts)


# ---------------------------------------------------------------- the turns

def pick_turns(n, days=7):
    """`n` runs of his messages that she answered, spread over the last `days`.

    A run is his consecutive messages with no reply of hers between them and
    no gap over fifteen minutes: that is what the loop hands the persona as
    `unread`, so it is the unit a reply answers. A run counts as answered when
    a message of hers follows it within two hours."""
    con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    since = time.time() - days * 86400
    rows = [dict(r) for r in con.execute(
        "select id, ts, date, role, text from messages where ts > ? order by ts", (since,))]
    con.close()
    runs, cur = [], []
    for m in rows:
        if m["role"] == "user":
            if cur and float(m["ts"]) - float(cur[-1]["ts"]) > 900:
                runs.append(cur)
                cur = []
            cur.append(m)
        else:
            if cur:
                runs.append(cur)
                cur = []
    if cur:
        runs.append(cur)
    answered = []
    for run in runs:
        end = float(run[-1]["ts"])
        nxt = next((m for m in rows if float(m["ts"]) > end and m["role"] != "user"), None)
        if nxt and float(nxt["ts"]) - end <= 7200 and str(run[-1].get("text") or "").strip():
            answered.append({"unread": run, "reply_ts": float(nxt["ts"]),
                             "reply": str(nxt.get("text") or "")})
    # spread: every k-th of the answered runs, so the sample covers the whole
    # span rather than the busiest evening in it
    if len(answered) <= n:
        return answered
    step = len(answered) / float(n)
    return [answered[int(i * step)] for i in range(n)]


# ---------------------------------------------------------------- the prompt

class _Captured(Exception):
    def __init__(self, messages):
        self.messages = messages


# The sources in the situation block whose material the five tools return.
# The first bench offered her tools over a prompt that already carried all of
# it, and she called none of them in twenty turns -- which tested nothing. With
# these lines out, and her diary out of what she carries, the only way to have
# the material is to go and fetch it.
DUPLICATED = {
    # his machine
    "digest", "digest_line", "digest_live", "digest_none_recent", "noticed", "glance",
    # her account
    "x_recent", "his_likes", "his_follows", "her_actions", "share", "show_him",
    "engagement", "followers", "replies_in",
    # her week, and what she has promised
    "today", "commitments", "goals",
    # what is going round among her people
    "around",
}

# The last thing she reads in the tool condition, after the closing line that
# names the room and its language. Addressed to her, so it is in the language
# she writes in; for the first character that is English. It says the material
# is not in front of her, which is true once the lines above are stripped.
TOOL_LINE = """
--- BEFORE YOU WRITE, you can go and look at something. None of it is in front of you unless you do ---
you can check any of these first, and only if you actually want to know: what his machine has been doing (check_his_machine), your own feed and what he has been liking (check_your_feed), what is on for you this week and what you have promised (check_your_week), what you wrote in your diary lately (read_your_diary), what your friends have been saying (check_your_friends). Look when this moment reaches for it and not otherwise, then write your message."""


_STRIPPED = {}


def strip_duplicated(app):
    """Take the tools' own material out of her prompt, and say what went.

    Two hooks, both on the instance. The attention gate is asked exactly as it
    always is and its answer is then narrowed by source, so nothing about how
    the block is ranked changes -- only what survives. Her diary is dropped
    from what she carries, which is where it rides (`persona/sections.py`, the
    carried half).

    **Installed once per App.** Wrapping again on every turn put each turn's
    wrapper on top of the last one's, so the layer underneath removed the
    lines and recorded them against the first turn, and every turn after it
    looked as though it had nothing to lose. The hooks stay; the list they
    write to is swapped here and handed back, so each turn's record is its
    own."""
    st = _STRIPPED.get(id(app))
    if st is None:
        st = {"removed": []}
        _STRIPPED[id(app)] = st
        att = app.persona.attention
        real_admit = att.admit
        real_carried = app.persona.carried_for

        def admit(parts, cue_text="", veto=None):
            kept, slot, report = real_admit(parts, cue_text=cue_text, veto=veto)
            out = []
            for line in kept:
                src = getattr(line, "source", "") or ""
                if src in DUPLICATED:
                    st["removed"].append({"where": "situation", "source": src, "text": str(line)[:300]})
                else:
                    out.append(line)
            if slot is not None and (getattr(slot, "source", "") or "") in DUPLICATED:
                st["removed"].append({"where": "slot", "source": getattr(slot, "source", ""),
                                      "text": str(slot)[:300]})
                slot = None
            return out, slot, report

        def carried():
            d = app.persona._sections.get("diary") or ""
            if d:
                st["removed"].append({"where": "carrying", "source": "diary", "text": d[:300]})
                app.persona._sections["diary"] = ""
            return real_carried()

        att.admit = admit
        app.persona.carried_for = carried
    st["removed"] = []
    return st["removed"]


def build_request(app, turn, strip=False, tool_line=""):
    """The exact messages the persona call for this turn would go out on.

    Her own path builds it (`Persona.generate` -> `_draft`): the system half
    from `persona.system_for`, the thread from the thread builder, what she
    carries and the situation block placed after it, his newest messages under
    the frame line, the closing line last. The model call at the end of
    `_draft` is where this takes the request and abandons the turn."""
    pin_clock(app, float(turn["unread"][-1]["ts"]))
    got = {}
    removed = strip_duplicated(app) if strip else []
    real_call = app.llm.call

    def capture(role, messages, *a, **k):
        if role == "persona":
            raise _Captured(messages)
        got.setdefault("other_roles", []).append(role)
        return ""
    app.llm.call = capture
    app.llm.call_json = lambda role, *a, **k: (got.setdefault("other_roles", []).append(role), None)[1]
    try:
        scene = (app.director.current if app.director else None) or {}
        digest = (app.phone.latest_digest() if app.phone else "") or ""
        unread = [dict(m) for m in turn["unread"]]
        app.persona.generate(scene, digest, unread)
        raise RuntimeError("the persona call was never made")
    except _Captured as c:
        messages = c.messages
        if tool_line:
            messages = list(messages)
            messages[-1] = dict(messages[-1], content=messages[-1]["content"] + "\n" + tool_line)
        return messages, got.get("other_roles", []), removed
    finally:
        app.llm.call = real_call


# ---------------------------------------------------------------- the tools

class Tools:
    """Five read-only looks over her own stores, each behind its subsystem's cap.

    Nothing here fetches: every one reads what the save already holds, the way
    the situation block reads it. The cap is the subsystem's own -- how long
    the digest stands before it is stale, how often she opens the account, how
    many diary entries ride -- and a second look inside it returns a line
    saying she looked and nothing has changed, never a fresh read. The
    descriptions are addressed to HER, so they are in the language she writes
    in; for the first character that is English."""

    def __init__(self, app, log_path):
        self.app = app
        self.log_path = log_path
        self.turn = ""
        self.looked = {}
        self.faults = []

    def start_turn(self, turn_id):
        self.turn = turn_id
        self.looked = {}

    # -- the schemas, as OpenRouter's tool-calling guide wants them

    def schemas(self):
        return [
            {"type": "function", "function": {
                "name": "check_his_machine",
                "description": ("What his computer has been doing, as your phone last put it together: "
                                "what he had open, for how long, and when he was last at it. Use it when "
                                "you want to know what he has actually been up to rather than guess."),
                "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {
                "name": "check_your_feed",
                "description": ("Your own account: the posts you last scrolled past, what you did on it, "
                                "and what he has been liking. Use it when the conversation turns to "
                                "something you saw online or to what he is into."),
                "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {
                "name": "check_your_week",
                "description": ("What is on for you in the next seven days, what you have promised him or "
                                "anyone else with a date on it, and what you are still waiting on him for. "
                                "Use it before you say you are free, or busy, or that you will do something."),
                "parameters": {"type": "object", "properties": {
                    "days": {"type": "integer",
                             "description": "how far ahead to look, 1 to 7; leave it out for the whole week"}},
                    "required": []}}},
            {"type": "function", "function": {
                "name": "read_your_diary",
                "description": ("The last things you wrote in your diary, in your own words, with their "
                                "dates. Use it when you want to know what you actually thought about "
                                "something at the time rather than how you feel about it now."),
                "parameters": {"type": "object", "properties": {
                    "entries": {"type": "integer", "description": "how many of the most recent entries, 1 or 2"}},
                    "required": []}}},
            {"type": "function", "function": {
                "name": "check_your_friends",
                "description": ("The last things said in your conversations with your own people: who was "
                                "talking, when, and what about. Use it when what he asked touches something "
                                "your friends have been on about."),
                "parameters": {"type": "object", "properties": {}, "required": []}}},
        ]

    NAMES = ("check_his_machine", "check_your_feed", "check_your_week", "read_your_diary", "check_your_friends")

    # -- the caps, each named after the config key that sets it

    CAPS = {
        "check_his_machine": ("phone.digest_min_minutes", "you looked at this a moment ago and it has not been rebuilt since"),
        "check_your_feed": ("social.look_min_minutes", "you scrolled it a moment ago; nothing new has come in since"),
        "check_your_week": (None, "you already looked at your week in this message; it has not changed"),
        "read_your_diary": (None, "you already read this back in this message; it says the same thing"),
        "check_your_friends": (None, "you already looked at what they were saying in this message; nothing has been said since"),
    }

    def call(self, name, args_json):
        t0 = time.time()
        parsed, bad = {}, ""
        try:
            parsed = json.loads(args_json) if str(args_json).strip() else {}
            if not isinstance(parsed, dict):
                bad, parsed = f"arguments were {type(parsed).__name__}, not an object", {}
        except Exception as e:
            bad = f"arguments did not parse as JSON: {type(e).__name__}"
        if name not in self.NAMES:
            out = f"there is no such thing to look at ({name})"
            self._log(name, args_json, out, ok=False, note="unknown tool")
            return out
        if name in self.looked:
            key, line = self.CAPS[name]
            out = line + (f" ({key})" if key else "")
            self._log(name, args_json, out, ok=True, note="capped")
            return out
        self.looked[name] = time.time()
        try:
            out = getattr(self, "_" + name)(parsed)
        except Exception as e:
            out = f"you went to look and it was not there ({type(e).__name__})"
            self.faults.append({"turn": self.turn, "tool": name, "error": f"{type(e).__name__}: {e}"})
        self._log(name, args_json, out, ok=not bad, note=bad, secs=time.time() - t0)
        return out

    def _log(self, name, args, out, ok=True, note="", secs=0.0):
        row = {"turn": self.turn, "tool": name, "arguments": str(args)[:400], "chars": len(out or ""),
               "ok": ok, "note": note, "secs": round(secs, 3), "result_head": (out or "")[:300]}
        with io.open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # -- the five looks

    def _check_his_machine(self, args):
        app = self.app
        if not app.phone:
            return "there is nothing of his to look at"
        return (app.phone.latest_digest() or "nothing has come through about his machine")[:4000]

    def _check_your_feed(self, args):
        app = self.app
        s = getattr(app, "social", None)
        if s is None or not app.config.social.enabled:
            return "you have no account to look at"
        bits = []
        for label, fn in (("what you scrolled past", "recent_line"),
                          ("what you did on it", "her_actions_line"),
                          ("what he has been liking", "his_likes_line"),
                          ("who he has followed", "his_follows_line"),
                          ("what your own posts got", "engagement_line")):
            try:
                line = getattr(s, fn)()
            except Exception:
                line = ""
            if line:
                bits.append(f"{label}: {line}")
        return "\n".join(bits)[:4000] or "you have not had it open recently"

    def _check_your_week(self, args):
        app = self.app
        days = args.get("days")
        try:
            days = max(1, min(7, int(days)))
        except (TypeError, ValueError):
            days = 7
        out = []
        try:
            today = app.clock.now().date()
            out.append("today: " + str(app.calendar.describe(today)))
            evs = app.calendar.events(today, lookahead_days=days, limit=10) or []
            for e in evs:
                if isinstance(e, dict):
                    out.append("- " + "; ".join(f"{k}: {v}" for k, v in e.items()
                                                if k in ("date", "title", "what", "where", "when") and v))
                else:
                    out.append("- " + str(e))
        except Exception as e:
            out.append(f"(your calendar would not open: {type(e).__name__})")
        try:
            for r in (app.commitments.open() or []):
                when = r.get("when") or r.get("date") or ""
                out.append(f"- you said you would: {r.get('what', '')}" + (f" ({when})" if when else ""))
        except Exception as e:
            out.append(f"(what you promised would not open: {type(e).__name__})")
        try:
            line = app.expectations.situation_line()
            if line:
                out.append("what you are waiting on him for: " + str(line))
        except Exception as e:
            out.append(f"(what you expect of him would not open: {type(e).__name__})")
        return "\n".join(out)[:4000]

    def _read_your_diary(self, args):
        app = self.app
        n = args.get("entries")
        try:
            n = max(1, min(3, int(n)))
        except (TypeError, ValueError):
            n = int(getattr(app.config.diary, "in_prompt", 2) or 2)
        rows = app.diary.entries(n) or []
        if not rows:
            return "you have not written anything in it yet"
        out = []
        for r in rows:
            out.append(f"[{r.get('date', '')}] {str(r.get('text') or r.get('entry') or '')}")
        return "\n\n".join(out)[:4000]

    def _check_your_friends(self, args):
        """Her own conversations, newest last, up to the pinned clock.

        A cast conversation is filed under the DATE it happened on with a
        clock time per turn (`date`, `hm`), not a timestamp. Sorting them by a
        timestamp field they have not got put them in insertion order and
        printed the pinned clock as their time on every one."""
        app = self.app
        recs = [r for r in (list(app.store.get("cast_chat", []) or [])
                            + list(app.store.get("peer_chat", []) or []))
                if r.get("date")]
        now = app.clock.now()
        cut = (now.strftime("%Y-%m-%d"), now.strftime("%H:%M"))
        recs = [r for r in recs if (str(r.get("date")), str(r.get("hm") or "00:00")) <= cut]
        recs.sort(key=lambda r: (str(r.get("date")), str(r.get("hm") or "00:00")))
        out = []
        for rec in recs[-3:]:
            who = rec.get("who") or rec.get("with") or rec.get("room") or "them"
            out.append(f"-- {who}, {rec.get('date')} {rec.get('hm', '')}")
            for t in (rec.get("turns") or [])[-6:]:
                out.append(f"{t.get('hm', '')} {t.get('who', '')}: {t.get('ja') or t.get('text') or ''}")
        return "\n".join(out)[:4000] or "nobody has said anything lately"


# ---------------------------------------------------------------- the wire

def payload_for(app, slug, host, messages, tools=None):
    """`LLM._payload`'s body for an OpenRouter provider, rebuilt here.

    The persona role's own temperature and reasoning effort out of her config,
    no `max_tokens`, the pinned host first with the project's own
    `host_fallback`. `require_parameters` goes on only with tools, so that a
    fall-through cannot land on a host for the same slug that does not take
    them."""
    m = app.config.model("persona")
    temp = float(m["temperature"])
    body = {"model": slug, "messages": messages, "temperature": temp}
    prov = {"order": [host], "allow_fallbacks": bool(app.config.raw["api"].get("host_fallback", True))}
    extra = {"reasoning": ({"effort": m.get("effort") or "high", "exclude": False}
                           if m.get("thinking") else {"enabled": False})}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
        prov["require_parameters"] = True
    extra["provider"] = prov
    body["extra_body"] = extra
    return body


def client(app):
    from openai import OpenAI
    api = app.config.raw["api"]
    key = io.open(api.get("openrouter_key_file", "secerts/openrouter.txt"), encoding="utf-8").read().strip()
    return OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1",
                  default_headers={"HTTP-Referer": "https://scail.local/bot", "X-OpenRouter-Title": "SCAIL"},
                  timeout=600.0, max_retries=0)


def stream_call(cl, body, raw_path=""):
    """One streamed answer, reassembled here.

    Text and reasoning accumulate as they do in `LLM._stream`. Tool calls
    arrive as `delta.tool_calls` fragments and are reassembled BY INDEX, not
    by arrival order: the id and the name come once, on the first fragment of
    that index, and the arguments arrive as a string in pieces. A fragment
    whose index is new after arguments have started elsewhere is normal
    (parallel calls); a fragment with no index at all, or a second id for one
    index, is a fault and is recorded."""
    req = dict(body, stream=True, stream_options={"include_usage": True})
    raw = io.open(raw_path, "w", encoding="utf-8") if raw_path else None
    text, reasoning = [], []
    calls = {}
    finish, usage, served, t_first = None, {}, None, None
    faults = []
    t0 = time.time()
    chunks = 0
    with cl.chat.completions.create(**req) as st:
        for chunk in st:
            chunks += 1
            if t_first is None:
                t_first = time.time() - t0
            d = chunk.model_dump() if hasattr(chunk, "model_dump") else dict(chunk)
            if raw is not None:
                raw.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
            if d.get("error"):
                err = d["error"]
                raise RuntimeError(f"error in stream: {err.get('message') if isinstance(err, dict) else err}")
            served = served or d.get("provider")
            if d.get("usage"):
                usage = d["usage"]
            for ch in d.get("choices") or []:
                delta = ch.get("delta") or {}
                if delta.get("content"):
                    text.append(delta["content"])
                r = delta.get("reasoning_content") or delta.get("reasoning")
                if r:
                    reasoning.append(r)
                for frag in (delta.get("tool_calls") or []):
                    idx = frag.get("index")
                    if idx is None:
                        faults.append("a tool-call fragment arrived with no index")
                        idx = len(calls)
                    slot = calls.setdefault(idx, {"id": "", "type": "function", "name": "", "arguments": ""})
                    if frag.get("id"):
                        if slot["id"] and slot["id"] != frag["id"]:
                            faults.append(f"index {idx} was given a second id")
                        slot["id"] = frag["id"]
                    if frag.get("type"):
                        slot["type"] = frag["type"]
                    fn = frag.get("function") or {}
                    if fn.get("name"):
                        slot["name"] += fn["name"]
                    if fn.get("arguments"):
                        slot["arguments"] += fn["arguments"]
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
    if raw is not None:
        raw.close()
    if finish is None:
        faults.append("the stream ended with no finish reason")
    return {"text": "".join(text), "reasoning": "".join(reasoning), "finish": finish,
            "usage": usage or {}, "served_by": served, "first_token_s": round(t_first or 0, 3),
            "total_s": round(time.time() - t0, 3), "chunks": chunks,
            "tool_calls": [calls[i] for i in sorted(calls)], "faults": faults}


def run_turn(cl, app, slug, host, messages, tools, tooling, turn_id, max_steps=3, echo_reasoning=False):
    """One turn: the request, then up to `max_steps` rounds of tool calls.

    The tool exchange is a local list that starts as a copy of her request and
    is thrown away at the end. Nothing here is written into her thread: a tool
    call is not something anyone said."""
    convo = list(messages)
    steps = []
    spent = 0.0
    made = []
    if tooling:
        tooling.start_turn(turn_id)
    for step in range(max_steps + 1):
        body = payload_for(app, slug, host, convo, tools=tools if tools else None)
        r = stream_call(cl, body)
        spent += float((r.get("usage") or {}).get("cost") or 0)
        steps.append({k: v for k, v in r.items() if k != "reasoning"} |
                     {"reasoning_chars": len(r["reasoning"]), "step": step})
        if not r["tool_calls"] or step == max_steps:
            return {"steps": steps, "reply": r["text"], "cost": spent, "made": made,
                    "final_finish": r["finish"], "reasoning_last": r["reasoning"][:2000]}
        asst = {"role": "assistant", "content": r["text"] or None,
                "tool_calls": [{"id": c["id"], "type": "function",
                                "function": {"name": c["name"], "arguments": c["arguments"]}}
                               for c in r["tool_calls"]]}
        if echo_reasoning and r["reasoning"]:
            asst["reasoning"] = r["reasoning"]
        convo = convo + [asst]
        for c in r["tool_calls"]:
            out = tooling.call(c["name"], c["arguments"])
            made.append({"step": step, "name": c["name"], "arguments": c["arguments"],
                         "chars": len(out), "id": c["id"]})
            convo.append({"role": "tool", "tool_call_id": c["id"], "content": out})
    return {"steps": steps, "reply": "", "cost": spent, "made": made, "final_finish": None,
            "reasoning_last": ""}


# ------------------------------------------------------- the second bench

def friends_that_day(app, ts):
    """Did her own people say anything in the day that ends at `ts`?

    The friends' rooms tool reads her cast conversations, so a turn where
    nothing was said in them is a turn where that tool has nothing to give."""
    when = app.clock.to_char(ts)
    today, cut = when.strftime("%Y-%m-%d"), when.strftime("%H:%M")
    n = 0
    for rec in list(app.store.get("cast_chat", []) or []) + list(app.store.get("peer_chat", []) or []):
        if str(rec.get("date")) != today:
            continue
        for t in (rec.get("turns") or []):
            if str(t.get("hm") or rec.get("hm") or "00:00") <= cut:
                n += 1
    return n


def choose_five(rows):
    """Five turns, chosen on what actually tells them apart.

    The survey over all twenty found every turn carrying the same seven
    strippable sources -- his machine, three lines off her account, what is on
    this week, and her diary -- so "a turn with his machine in play" and "a
    turn with something on this week" are true of all of them and select
    nothing. What varies is whether her own people said anything that day,
    which runs from none to 128 turns. So: the day her friends talked most,
    and four more on days of their own, ends of the week first so the sample
    spans it."""
    picked, why = [], {}
    best = max(rows, key=lambda r: r["friends_turns"])
    if best["friends_turns"] > 0:
        picked.append(best)
        why[best["id"]] = f"her friends talking that day ({best['friends_turns']} turns)"
    days = {r["when"][:10] for r in picked}
    rest = [r for r in rows if r["id"] not in why]
    # the ends of the span first, then inwards, so five turns cover the week
    order = []
    lo, hi = 0, len(rest) - 1
    while lo <= hi:
        order.append(rest[lo])
        if lo != hi:
            order.append(rest[hi])
        lo, hi = lo + 1, hi - 1
    for r in order:
        if len(picked) >= 5:
            break
        if r["when"][:10] in days:
            continue
        picked.append(r)
        why[r["id"]] = "ordinary"
        days.add(r["when"][:10])
    for r in order:
        if len(picked) >= 5:
            break
        if r["id"] not in why:
            picked.append(r)
            why[r["id"]] = "ordinary"
    picked.sort(key=lambda r: r["ts"])
    return picked, why


def round_two(app, out_dir, turns, cl, args):
    """The bench done properly: the tools made real to her.

    The first run offered five tools over a prompt that already carried what
    four of them return and never said a tool existed; the model called none,
    on twenty turns, which tested nothing. Here the situation block loses the
    lines the tools duplicate, her diary comes out of what she carries, and
    the last thing she reads names what she can go and look at. The control is
    the same five turns exactly as they went out live, and one turn is run
    again with the machine tool named, every raw chunk written out."""
    survey = []
    for i, t in enumerate(turns):
        tid = "t%02d" % i
        messages, _others, removed = build_request(app, t, strip=True, tool_line=TOOL_LINE)
        ts = float(t["unread"][-1]["ts"])
        row = {"id": tid, "ts": ts,
               "when": app.clock.to_char(ts).strftime("%Y-%m-%d %H:%M"),
               "his": [str(m.get("text") or "") for m in t["unread"]],
               "her_real_reply": t["reply"],
               "sources": sorted({r["source"] for r in removed}),
               "removed": removed,
               "removed_lines": len(removed),
               "friends_turns": friends_that_day(app, ts),
               "prompt_tokens": app.memory.tokens("".join(m["content"] for m in messages))}
        survey.append(row)
        io.open(os.path.join(out_dir, "r2_prompt_%s.json" % tid), "w", encoding="utf-8").write(
            json.dumps({"turn": {k: v for k, v in row.items() if k != "removed"},
                        "removed": removed, "messages": messages}, ensure_ascii=False, indent=1))
        print("  %s %s stripped %d line(s) %s friends %d"
              % (tid, row["when"], row["removed_lines"], row["sources"], row["friends_turns"]))
    picked, why = choose_five(survey)
    io.open(os.path.join(out_dir, "r2_turns.json"), "w", encoding="utf-8").write(
        json.dumps({"chosen": [{"id": r["id"], "when": r["when"], "why": why[r["id"]],
                                "sources_removed": r["sources"],
                                "removed_lines": r["removed_lines"],
                                "friends_turns": r["friends_turns"]} for r in picked],
                    "survey": [{k: v for k, v in r.items() if k != "removed"} for r in survey]},
                   ensure_ascii=False, indent=1))
    print("chosen: " + ", ".join("%s (%s)" % (r["id"], why[r["id"]]) for r in picked))
    if args.pick_only:
        return

    _name, slug, host = MODELS["flash"]
    tooling = Tools(app, os.path.join(out_dir, "r2_toolcalls.jsonl"))
    schemas = tooling.schemas()
    spent = 0.0

    path = os.path.join(out_dir, "r2_flash_tools.jsonl")
    for r in picked:
        prompt = json.load(io.open(os.path.join(out_dir, "r2_prompt_%s.json" % r["id"]), encoding="utf-8"))
        got = run_turn(cl, app, slug, host, prompt["messages"], schemas, tooling,
                       "tools/%s" % r["id"], max_steps=3)
        spent += got["cost"]
        with io.open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"turn": r["id"], "when": r["when"], "why": why[r["id"]],
                                 "condition": "tools", "his": r["his"],
                                 "her_real_reply": r["her_real_reply"],
                                 "sources_removed": r["sources"]}, ensure_ascii=False)[:-1]
                     + "," + json.dumps(got, ensure_ascii=False)[1:] + "\n")
        print("  tools %s: %d call(s) %s reply %d chars $%.4f running $%.4f"
              % (r["id"], len(got["made"]), [m["name"] for m in got["made"]],
                 len(got["reply"]), got["cost"], spent))

    path = os.path.join(out_dir, "r2_flash_control.jsonl")
    for r in picked:
        prompt = json.load(io.open(os.path.join(out_dir, "prompt_%s.json" % r["id"]), encoding="utf-8"))
        got = run_turn(cl, app, slug, host, prompt["messages"], None, tooling,
                       "control/%s" % r["id"], max_steps=0)
        spent += got["cost"]
        with io.open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"turn": r["id"], "when": r["when"], "condition": "control",
                                 "his": r["his"], "her_real_reply": r["her_real_reply"]},
                                ensure_ascii=False)[:-1]
                     + "," + json.dumps(got, ensure_ascii=False)[1:] + "\n")
        print("  control %s: reply %d chars $%.4f running $%.4f"
              % (r["id"], len(got["reply"]), got["cost"], spent))

    r = picked[0]
    prompt = json.load(io.open(os.path.join(out_dir, "r2_prompt_%s.json" % r["id"]), encoding="utf-8"))
    convo = list(prompt["messages"])
    body = payload_for(app, slug, host, convo, tools=schemas)
    body["tool_choice"] = {"type": "function", "function": {"name": "check_his_machine"}}
    first = stream_call(cl, body, raw_path=os.path.join(out_dir, "r2_wire_chunks_step1.jsonl"))
    spent += float((first.get("usage") or {}).get("cost") or 0)
    tooling.start_turn("forced/%s" % r["id"])
    step2, parsed_ok, results = None, [], []
    if first["tool_calls"]:
        convo = convo + [{"role": "assistant", "content": first["text"] or None,
                          "tool_calls": [{"id": c["id"], "type": "function",
                                          "function": {"name": c["name"], "arguments": c["arguments"]}}
                                         for c in first["tool_calls"]]}]
        for c in first["tool_calls"]:
            try:
                json.loads(c["arguments"] or "{}")
                parsed_ok.append(True)
            except Exception:
                parsed_ok.append(False)
            out = tooling.call(c["name"], c["arguments"])
            results.append({"name": c["name"], "chars": len(out)})
            convo.append({"role": "tool", "tool_call_id": c["id"], "content": out})
        step2 = stream_call(cl, payload_for(app, slug, host, convo, tools=schemas),
                            raw_path=os.path.join(out_dir, "r2_wire_chunks_step2.jsonl"))
        spent += float((step2.get("usage") or {}).get("cost") or 0)
    io.open(os.path.join(out_dir, "r2_wire_forced.json"), "w", encoding="utf-8").write(json.dumps(
        {"turn": r["id"], "when": r["when"], "tool_choice": "check_his_machine",
         "step1": {k: v for k, v in first.items() if k != "reasoning"},
         "step1_reasoning": first["reasoning"][:2000],
         "arguments_parsed": parsed_ok, "tool_results": results,
         "step2": ({k: v for k, v in step2.items() if k != "reasoning"} if step2 else None),
         "step2_reasoning": (step2["reasoning"][:2000] if step2 else "")},
        ensure_ascii=False, indent=1))
    print("  forced: %d call(s), arguments parsed %s, second step %s"
          % (len(first["tool_calls"]), parsed_ok,
             ("answered %d chars" % len(step2["text"])) if step2 else "not reached"))
    print("round two total: $%.4f" % spent)


# ---------------------------------------------------------------- the money

def prices(out_dir):
    """Per-million prompt / completion / cached-read for each pinned host, off
    OpenRouter's own endpoint list. The models list gives the CHEAPEST
    endpoint's price, which is not what a pinned call is billed."""
    path = os.path.join(out_dir, "endpoints.json")
    if os.path.exists(path):
        data = json.load(io.open(path, encoding="utf-8"))
    else:
        import urllib.request
        data = {}
        for _, slug, _h in MODELS.values():
            d = json.load(urllib.request.urlopen(
                f"https://openrouter.ai/api/v1/models/{slug}/endpoints", timeout=60))
            data[slug] = [{"provider_name": e.get("provider_name"), "tag": e.get("tag"),
                           "pricing": e.get("pricing"),
                           "supported_parameters": e.get("supported_parameters") or []}
                          for e in d["data"]["endpoints"]]
        io.open(path, "w", encoding="utf-8").write(json.dumps(data, indent=1))
    out = {}
    for key, (_name, slug, host) in MODELS.items():
        eps = data[slug]
        ep = next((e for e in eps if str(e["provider_name"]).lower().replace(" ", "")
                   == host.lower().replace(" ", "")), None) or eps[0]
        p = ep["pricing"]
        out[key] = {"slug": slug, "host": ep["provider_name"],
                    "prompt": float(p["prompt"]) * 1e6,
                    "completion": float(p["completion"]) * 1e6,
                    "cached": float(p.get("input_cache_read") or 0) * 1e6,
                    "tools": "tools" in ep["supported_parameters"],
                    "hosts_without_tools": [e["provider_name"] for e in eps
                                            if "tools" not in (e["supported_parameters"] or [])]}
    return out


def estimate(app, turns, out_dir, out_allowance=1500, steps=4):
    """The bill before the first paid call, from the real prompts.

    Prompt tokens are the project's own estimator (`Memory.tokens`, the ratio
    calibrated off her real receipts), the tool schemas counted in on the tool
    condition. No cache is assumed: the tool loop's follow-up calls go out
    seconds apart and the write may not be readable yet, and a cold projection
    is the one that cannot be an underestimate."""
    pr = prices(out_dir)
    tools_chars = len(json.dumps(Tools(app, os.devnull).schemas()))
    tool_tokens = app.memory.tokens(json.dumps(Tools(app, os.devnull).schemas()))
    rows = []
    total = 0.0
    per_turn = [t["prompt_tokens"] for t in turns]
    avg = sum(per_turn) / float(len(per_turn))
    for key, p in pr.items():
        # the tool condition: `steps` calls, each carrying the whole prompt
        # plus the schemas plus what the earlier tool results added
        tool_in = sum((avg + tool_tokens) + i * 900 for i in range(steps))
        tool_out = out_allowance * steps
        ctrl_in = avg
        ctrl_out = out_allowance
        per = ((tool_in + ctrl_in) * p["prompt"] + (tool_out + ctrl_out) * p["completion"]) / 1e6
        rows.append({"model": key, "slug": p["slug"], "host": p["host"],
                     "prompt_per_m": p["prompt"], "completion_per_m": p["completion"],
                     "avg_prompt_tokens": int(avg), "tool_schema_tokens": tool_tokens,
                     "usd_per_turn": round(per, 4),
                     "usd_20_turns": round(per * 20, 3),
                     "usd_10_turns": round(per * 10, 3)})
        total += per
    est = {"turns_measured": len(turns), "avg_prompt_tokens": int(avg),
           "min_prompt_tokens": min(per_turn), "max_prompt_tokens": max(per_turn),
           "tool_schema_chars": tools_chars, "tool_schema_tokens": tool_tokens,
           "calls_per_turn_tool_condition": steps, "calls_per_turn_control": 1,
           "output_allowance_tokens_per_call": out_allowance,
           "rows": rows,
           "usd_per_turn_all_three": round(total, 4),
           "usd_20_turns_all_three": round(total * 20, 2),
           "usd_10_turns_all_three": round(total * 10, 2),
           "turns_that_fit_6usd": int(6.0 / total) if total else 0}
    io.open(os.path.join(out_dir, "estimate.json"), "w", encoding="utf-8").write(
        json.dumps(est, indent=1))
    return est


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--turns", type=int, default=20)
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--run", default="")
    ap.add_argument("--no-tools", action="store_true")
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--echo-reasoning", action="store_true")
    ap.add_argument("--dry", action="store_true", help="build the requests and stop; spends nothing")
    ap.add_argument("--round-two", action="store_true",
                    help="the second bench: the tools made real to her, a control, and one forced call")
    ap.add_argument("--pick-only", action="store_true",
                    help="build the stripped prompts and choose the five turns; spends nothing")
    ap.add_argument("--rebuild-prompts", action="store_true",
                    help="draw the twenty prompts again instead of reusing the ones in --out")
    ap.add_argument("--tools-check", action="store_true",
                    help="call all five tools twice at one pinned moment and print what came back; spends nothing")
    args = ap.parse_args()
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, "world_copy.db")
    if not os.path.exists(tmp):
        copy_live_save(tmp)
        print(f"copied the save: {os.path.getsize(tmp) / 1e6:.1f} MB")
    app = build(tmp)
    print(f"built on the copy: {app.config.character.name if hasattr(app.config.character, 'name') else ''}")

    turns = pick_turns(args.turns)
    print(f"{len(turns)} answered runs of his over the last seven days")

    if args.tools_check:
        # every tool, at the newest moment, twice: the second call is the cap
        pin_clock(app, float(turns[-1]["unread"][-1]["ts"]))
        tooling = Tools(app, os.path.join(out_dir, "toolcalls_check.jsonl"))
        tooling.start_turn("check")
        rows = []
        for name in Tools.NAMES:
            first = tooling.call(name, "{}")
            second = tooling.call(name, "{}")
            rows.append({"tool": name, "chars": len(first), "capped_answer": second,
                         "head": first[:400]})
            print(f"  {name}: {len(first)} chars | second call: {second[:90]}")
        io.open(os.path.join(out_dir, "tools_check.json"), "w", encoding="utf-8").write(
            json.dumps(rows, ensure_ascii=False, indent=1))
        if tooling.faults:
            print("faults: " + json.dumps(tooling.faults, ensure_ascii=False))
        return
    # The prompts are built ONCE and reused by every later run. Building them
    # again would not give the same bytes -- the shape budget draws at random
    # -- and a control condition on a different prompt from the tool condition
    # compares two things at once. `--rebuild-prompts` forces a fresh set.
    done = os.path.join(out_dir, "turns.json")
    if os.path.exists(done) and not args.rebuild_prompts:
        built = json.load(io.open(done, encoding="utf-8"))
        print(f"reusing the {len(built)} prompts already built here "
              f"(--rebuild-prompts to draw them again)")
        built = built[:args.turns]
    else:
        built = []
    for i, t in enumerate(turns if not built else []):
        tid = f"t{i:02d}"
        messages, others, _rm = build_request(app, t)
        chars = sum(len(m["content"]) for m in messages)
        row = {"id": tid, "ts": float(t["unread"][-1]["ts"]),
               "when": app.clock.to_char(float(t["unread"][-1]["ts"])).strftime("%Y-%m-%d %H:%M"),
               "his": [str(m.get("text") or "") for m in t["unread"]],
               "her_real_reply": t["reply"],
               "chars": chars, "prompt_tokens": app.memory.tokens("".join(m["content"] for m in messages)),
               "messages": len(messages), "other_roles_asked": others}
        built.append(row)
        io.open(os.path.join(out_dir, f"prompt_{tid}.json"), "w", encoding="utf-8").write(
            json.dumps({"turn": {k: v for k, v in row.items()}, "messages": messages},
                       ensure_ascii=False, indent=1))
        print(f"  {tid} {row['when']}  {row['prompt_tokens']:>7} tokens  {row['his'][-1][:60]!r}")
    if not os.path.exists(done) or args.rebuild_prompts:
        io.open(done, "w", encoding="utf-8").write(json.dumps(built, ensure_ascii=False, indent=1))

    if args.round_two:
        round_two(app, out_dir, turns, client(app) if not args.pick_only else None, args)
        return

    est = estimate(app, built, out_dir)
    print(json.dumps({k: v for k, v in est.items() if k != "rows"}, indent=1))
    for r in est["rows"]:
        print(f"  {r['model']:<8} {r['host']:<12} in ${r['prompt_per_m']}/M out ${r['completion_per_m']}/M "
              f"-> ${r['usd_per_turn']}/turn, ${r['usd_20_turns']} for 20")
    if args.estimate or args.dry:
        return

    key = args.run
    if key not in MODELS:
        print(f"--run must be one of {', '.join(MODELS)}")
        return
    name, slug, host = MODELS[key]
    cond = "control" if args.no_tools else "tools"
    cl = client(app)
    tooling = Tools(app, os.path.join(out_dir, "toolcalls.jsonl"))
    schemas = None if args.no_tools else tooling.schemas()
    path = os.path.join(out_dir, f"{key}_{cond}.jsonl")
    spent = 0.0
    for i, row in enumerate(built):
        prompt = json.load(io.open(os.path.join(out_dir, f"prompt_{row['id']}.json"), encoding="utf-8"))
        r = run_turn(cl, app, slug, host, prompt["messages"], schemas, tooling,
                     f"{key}/{cond}/{row['id']}", max_steps=args.steps if schemas else 0,
                     echo_reasoning=args.echo_reasoning)
        spent += r["cost"]
        out = {"turn": row["id"], "when": row["when"], "model": key, "slug": slug, "condition": cond,
               "his": row["his"], "her_real_reply": row["her_real_reply"], **r}
        with io.open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(out, ensure_ascii=False) + "\n")
        print(f"  {row['id']} {len(r['made'])} tool call(s) {[m['name'] for m in r['made']]} "
              f"reply {len(r['reply'])} chars  ${r['cost']:.4f}  running ${spent:.4f}")
        if i == 2:
            print(f"  -- after three turns: ${spent:.4f}; projected for {len(built)}: "
                  f"${spent / 3 * len(built):.2f}")
    print(f"{key}/{cond}: ${spent:.4f}")


if __name__ == "__main__":
    main()
