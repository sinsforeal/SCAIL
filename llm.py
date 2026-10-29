import time
import re
import json
from openai import OpenAI
import logger
import netwatch
from sim import downtime


class RunawayAnswer(RuntimeError):
    """A streamed answer that had begun repeating itself word for word.

    A model that loses the thread of a structured answer does not stop: it
    writes the last thing it wrote again, and again, until the host's own
    output ceiling. The day auditor did exactly that five times over
    2026-09-03 and 2026-09-04 -- one real seam, then the same seam object
    1,595 times, 468,147 characters, 131,072 completion tokens, nineteen
    minutes on the loop thread, and it did not parse at the end of it. This
    is raised where the repetition starts instead."""


# The repetition test: the last _REPEAT_WINDOW characters of the answer so
# far, counted against everything written before them. The window is wider
# than one repeated JSON object (the auditor's were about 290 characters), so
# a periodic loop still matches itself exactly whatever the period; and the
# test only runs every _REPEAT_STEP characters of growth, so a normal answer
# pays for at most a couple of string scans. Measured against all 8,354 calls
# on disk: it fires on the five runaways and on nothing else.
_REPEAT_WINDOW = 400
_REPEAT_STEP = 2000


class LLM:
    """One provider, receipts on every call, and a failure is a failure.

    `api.provider` names who answers -- a host on OpenRouter (kind
    `openrouter`, key from `openrouter_key_file`, no max_tokens sent, the
    role's `thinking` flag mapped to `reasoning`, the host order pinned with
    no fallback outside it) or the official DeepSeek endpoint (kind
    `deepseek`, key `api.api_key`, the API-maximum max_tokens sent). Every
    provider in `api.providers` is defined and pinnable (`/provider <name>`,
    kv `provider_override`); nothing is ever fallen to. A call that fails
    after the bot's own retries returns "" and is written to kv
    `missed_calls`, which `App.catch_up` reads when the host is back.

    There is no chain, no strike and no cooldown, his call: a fallback maps
    a model NAME to another host's slug and so can change the MODEL and not
    just the host, and nothing downstream reads which model actually
    answered. And with one host the cooldown demoted the only host there was
    and answered nothing for thirty minutes on a wobble (2026-09-03)."""

    # The roles that write in HER words, as against the machinery that thinks
    # about her. The chat's model toggle moves exactly these: a character
    # answering on one model with her director, her state read and her judges
    # on another is how both characters already run, and a toggle that moved
    # everything would change the simulation as well as the voice.
    VOICE_ROLES = ("persona", "revise_self", "spiral", "approach", "morning",
                   "anticipation", "reflect", "diary", "wonder", "peer_reply",
                   "quality_rewrite")

    def __init__(self, config, store=None):
        self.config = config
        self.store = store          # kv: provider_override, model_override, missed_calls
        self._clients = {}
        self.last_usage = {}
        self.last_provider = None
        self.last_reasoning = ""
        self._last_dt = 0.0
        # what has been asked of the model this run, for the operator's view:
        # the last few hundred calls with role, seconds and tokens, plus a
        # count of errors. llm_calls.jsonl has every prompt; this is the tally.
        from collections import deque
        self.calls = deque(maxlen=600)
        self.errors = 0
        self.empties = 0
        self.truncated = 0
        self.cut_off = 0
        self.runaways = 0
        self.abandoned = 0
        # the burst gate: per role, the system prefix of the last call, when
        # it finished, whether it came back cold, and whether this burst has
        # already paid its one wait (`_hold_for_burst`)
        self._burst = {}
        import threading as _th
        self._tl = _th.local()
        self.call_ids = []          # gateway call ids in order, each with the role that asked
        self.burst_holds = 0
        self.burst_held_seconds = 0.0
        self.last_runaway = False
        self.cache_track = {}     # per role, when there is no store to keep it in
        self.missed = 0
        self.last_ok_ts = 0

    # ---- providers -------------------------------------------------------

    def _providers(self):
        api = self.config.raw["api"]
        provs = dict(api.get("providers") or {})
        if "official" not in provs:
            provs["official"] = {"kind": "deepseek", "base_url": api.get("base_url"), "models": {}}
        return provs

    def active_provider(self):
        """The one provider that answers: the pin if there is one, else `api.provider`."""
        provs = self._providers()
        override = self.store.get("provider_override") if self.store is not None else None
        if override and override in provs:
            return override
        name = self.config.raw["api"].get("provider") or "official"
        return name if name in provs else next(iter(provs))

    def _client(self, name):
        if name not in self._clients:
            p = self._providers()[name]
            api = self.config.raw["api"]
            if p.get("kind") == "openrouter":
                key_file = api.get("openrouter_key_file", "secerts/openrouter.txt")
                key = open(key_file, encoding="utf-8").read().strip()
                self._clients[name] = OpenAI(api_key=key, base_url=p.get("base_url") or "https://openrouter.ai/api/v1",
                                             default_headers={"HTTP-Referer": "https://scail.local/bot",
                                                              "X-OpenRouter-Title": "SCAIL"},
                                             timeout=float(api.get("request_timeout_seconds", 600)), max_retries=0)
            elif p.get("kind") == "bz":
                # The B-zombie bench: every call goes through the gateway, which forces the
                # model and the thinking policy; the id it stamps on each response is kept
                # against the role that asked, so a trace can link its calls (bzombie/CONTRACT.md).
                import httpx
                self._clients[name] = OpenAI(api_key="bz", base_url=p["base_url"],
                                             http_client=httpx.Client(event_hooks={"response": [self._note_call_id]}),
                                             timeout=float(api.get("request_timeout_seconds", 600)), max_retries=0)
            else:
                self._clients[name] = OpenAI(api_key=api["api_key"], base_url=p.get("base_url") or api["base_url"],
                                             timeout=float(api.get("request_timeout_seconds", 600)), max_retries=0)
        return self._clients[name]

    def _note_call_id(self, response):
        cid = response.headers.get("x-bz-call-id")
        if cid:
            self.call_ids.append({"call_id": cid, "role": getattr(self._tl, "role", ""),
                                  "wall_ts": time.time()})

    def _payload(self, name, m, messages, max_tokens, tools=None, tool_choice=None):
        """The request as this provider wants it. DeepSeek official: its
        `thinking` body and the API-maximum max_tokens (a low cap fails
        silently). OpenRouter: the slug the model name maps to, the host order
        (the pinned host first, OpenRouter's other hosts for the same slug
        after it when `api.host_fallback` is on), `reasoning` on or off as the
        role says, and no max_tokens at all (hosts cap output differently and
        refuse a number above theirs).

        `tools` and `tool_choice` go at the TOP LEVEL of the body, never
        inside `extra_body`, and on OpenRouter they bring
        `provider.require_parameters` with them: the fall-through is on, and a
        host for the same slug that accepts the request and drops the tools
        answers as if none had been offered, which nothing downstream could
        tell from a model that declined to call one. `parallel_tool_calls` is
        never sent -- one endpoint of the forty-eight across this project's
        three slugs advertises it, so naming it under `require_parameters`
        would empty the host list for two of the three."""
        p = self._providers()[name]
        slug = (p.get("models") or {}).get(m["model"], m["model"])
        temperature = m["temperature"]
        if p.get("max_temperature") is not None:
            temperature = min(temperature, p["max_temperature"])   # Z.AI refuses above 1.0
        payload = {"model": slug, "messages": messages, "temperature": temperature}
        if p.get("kind") == "bz":
            # one model name for every role; the gateway owns thinking and the floor on max_tokens
            payload["max_tokens"] = min(int(max_tokens or m["max_tokens"]), int(p.get("max_tokens", 8192)))
        elif p.get("kind") == "openrouter":
            extra = {"reasoning": ({"effort": m.get("effort") or "high", "exclude": False}
                                   if m.get("thinking") else {"enabled": False})}
            order = (p.get("order") or {}).get(slug)
            if order:
                # the pinned host first; when it fails, OpenRouter's next host
                # for the SAME slug answers (api.host_fallback, his call after
                # Together returned 503 on every kimi-k3 call for a stretch).
                # The slug does not change, so the model does not; the receipt
                # names who served
                extra["provider"] = {"order": list(order),
                                     "allow_fallbacks": bool(self.config.raw["api"].get("host_fallback", True))}
            if tools:
                extra.setdefault("provider", {})["require_parameters"] = True
            payload["extra_body"] = extra
        else:
            payload["max_tokens"] = max_tokens or m["max_tokens"]
            if m.get("thinking"):
                # the API reference puts reasoning_effort INSIDE the thinking
                # object (low | high | max); the release examples show it at the
                # top level. Both, so whichever the server reads, it reads ours.
                payload["extra_body"] = {"thinking": {"type": "enabled"}}
                if m.get("effort"):
                    payload["extra_body"]["thinking"]["reasoning_effort"] = m["effort"]
                    payload["reasoning_effort"] = m["effort"]
            else:
                payload["extra_body"] = {"thinking": {"type": "disabled"}}
        if tools:
            payload["tools"] = list(tools)
            payload["tool_choice"] = tool_choice or "auto"
        return payload, slug

    # ---- the call --------------------------------------------------------

    def model_cmd(self, arg=""):
        """`/model` -- what each role is on and what the provider can serve;
        `/model <name>` puts EVERY role on one model for this run (kv
        `model_override`); `/model auto` gives them back their config entries.

        The pin is deliberately all-or-nothing and deliberately not written to
        the config file. Switching a character's model used to mean editing
        every one of 73 role entries by hand, and a half-done edit leaves a
        character speaking in two voices with nothing to say so. Use this to
        try a model; `tools/set_model.py` to keep it.
        """
        arg = (arg or "").strip()
        provs = self._providers()
        name = self.active_provider()
        known = {}
        for model_name, slug in ((provs.get(name) or {}).get("models") or {}).items():
            known.setdefault(model_name, set()).add(f"{name}:{slug}")
        if arg == "auto":
            self.store.set("model_override", None)
            return "model override cleared; every role is back on its config entry"
        if arg:
            if arg not in known:
                return (f"no model '{arg}' in {name}'s table; mapped: {', '.join(sorted(known))}. "
                        f"Add it to api.providers.{name}.models in config.py DEFAULTS and this character's config, both.")
            self.store.set("model_override", arg)
            return (f"every role pinned to {arg} for this run ({'; '.join(sorted(known[arg]))}). "
                    f"/model auto to unpin; tools/set_model.py to make it permanent.")
        override = self.store.get("model_override") if self.store is not None else None
        roles = self.config.raw.get("models") or {}
        # A role this character never calls is still in `models`, because
        # `models` is the mechanism's and is the same for everybody. Named
        # here, or the continuity check prints with its model beside the roles
        # that do run and reads as live.
        try:
            off = self.config.roles_off() or {}
        except Exception:
            off = {}
        by_model = {}
        for r, m in roles.items():
            by_model.setdefault(m.get("model"), []).append(r)
        lines = [f"override: {override or 'none'} | provider: {name}"]
        for m, rs in sorted(by_model.items(), key=lambda kv: -len(kv[1])):
            shown = sorted(r + (" (never called)" if r in off else "") for r in rs)
            lines.append(f"  {m}: {len(rs)} role(s)" + ("" if len(rs) > 6 else " -- " + ", ".join(shown)))
        for r, why in sorted(off.items()):
            lines.append(f"  {r} is never called for this character: {why}")
        lines.append(f"mapped at {name}: " + ", ".join(sorted(known)))
        return "\n".join(lines)

    def stage_model_report(self):
        """The stage-roles pin as the second picker draws it: the model every
        role that is NOT one of her voice roles is on ("" for each role's own
        config entry), and the names the provider can serve."""
        pin = ""
        if self.store is not None:
            pin = str(self.store.get("stage_model_override") or "")
        return {"model": pin, "models": self.voice_models()}

    def stage_model_cmd(self, name=""):
        """The stage-roles picker: an empty pick gives every stage role its
        config entry back; a name pins them for this run (kv
        `stage_model_override`, kept on the save).

        Her VOICE roles are not moved by this -- they have their own toggle
        (`voice_model_cmd`) -- so her words and the machinery behind the stage
        can sit on two different models, which is what he asked for
        (2026-09-17). 79 of her 90 roles are the machinery."""
        name = (name or "").strip()
        if not name:
            if self.store is not None:
                self.store.set("stage_model_override", None)
            return {"model": "", "ok": True}
        provs = self._providers()
        pname = self.active_provider()
        known = (provs.get(pname) or {}).get("models") or {}
        if name not in known:
            return {"model": self.stage_model_report()["model"], "ok": False,
                    "error": f"no model '{name}' in {pname}'s table"}
        if self.store is not None:
            self.store.set("stage_model_override", name)
        logger.log(f"[llm] the stage roles pinned to {name} from the stage at "
                   f"{time.strftime('%Y-%m-%d %H:%M:%S')}, saved on her save")
        return {"model": name, "ok": True}

    def voice_models(self):
        """The names the chat's toggle offers, cut to the ones the provider
        that is actually answering can serve. A name the provider has no slug
        for goes out as a literal and the host rejects it, so it is not
        offered."""
        provs = self._providers()
        known = ((provs.get(self.active_provider()) or {}).get("models") or {})
        return [n for n in (self.config.raw["api"].get("voice_models") or []) if n in known]

    def voice_model_report(self):
        """What the control in the chat header draws itself from: the model
        her words are written on now, the names it may offer, and whether the
        one showing is a choice he made or her config's own."""
        return {"model": self.effective_model("persona"),
                "models": self.voice_models(),
                "pinned": bool(self.store.get("voice_model_override")) if self.store is not None else False}

    def voice_pin_line(self):
        """The boot line for a pin on the roles that write in her voice, or "".

        `/voicemodel` writes kv `voice_model_override` on her own save, so a
        pin outlives the run it was set in and the next boot obeys it in
        silence. On 2026-09-07 two characters had been writing their replies
        on a model neither config names, with no line anywhere saying so and
        no record of who set it. A pin in force is now named at every boot
        with the model, where it is kept and what it overrides."""
        if self.store is None:
            return ""
        pin = self.store.get("voice_model_override")
        if not pin:
            return ""
        named = ""
        try:
            named = str((self.config.model("persona") or {}).get("model", "") or "")
        except Exception:
            named = ""
        over = f", over her config's {named}" if named and named != str(pin) else ""
        return (f"[llm] voice roles pinned to {pin} by /voicemodel, saved on her save"
                f"{over}: {', '.join(self.VOICE_ROLES)}")

    def effective_model(self, role="persona"):
        """The model this role would go out on right now: her voice toggle for a
        voice role, the stage toggle for any other role, then the all-roles pin
        from `/model`, then its config entry. The two stage toggles are separate
        on purpose -- her words and the machinery behind the stage are different
        jobs and may sit on different models (2026-09-17)."""
        if self.store is not None:
            if role in self.VOICE_ROLES:
                v = self.store.get("voice_model_override")
                if v:
                    return str(v)
            else:
                s = self.store.get("stage_model_override")
                if s:
                    return str(s)
            p = self.store.get("model_override")
            if p:
                return str(p)
        try:
            return str((self.config.model(role) or {}).get("model", "")) or ""
        except Exception:
            return ""

    def voice_model_cmd(self, arg=""):
        """`/voicemodel` -- which model writes in her voice, where that comes
        from, and what the chat's toggle offers; `/voicemodel <name>` moves the
        nine voice roles for this run (kv `voice_model_override`);
        `/voicemodel auto` gives them back their config entries.

        Live only, like `/model`: nothing is written to the config file. The
        toggle in the chat is a thing he flicks between two replies, and a
        choice he wants to keep is `tools/set_model.py`."""
        arg = (arg or "").strip()
        offered = self.voice_models()
        name = self.active_provider()
        if arg == "auto":
            self.store.set("voice_model_override", None)
            logger.log(f"[llm] the voice pin was cleared by /voicemodel auto at "
                       f"{time.strftime('%Y-%m-%d %H:%M:%S')}; every voice role is back on her config")
            return ("her voice is back on its config entries: "
                    + ", ".join(f"{r}={self.effective_model(r)}" for r in self.VOICE_ROLES[:3]) + " ...")
        if arg:
            known = ((self._providers().get(name) or {}).get("models") or {})
            if arg not in known:
                return (f"no model '{arg}' in {name}'s table; mapped: {', '.join(sorted(known))}. "
                        f"Add it to api.providers.{name}.models in config.py DEFAULTS and this "
                        f"character's config, both.")
            self.store.set("voice_model_override", arg)
            # into the log as well as into the chat: the key is kept on her
            # save and outlives the run, so a month later the only record of
            # who put her voice on that model is this line
            logger.log(f"[llm] voice roles pinned to {arg} ({known[arg]}) by /voicemodel at "
                       f"{time.strftime('%Y-%m-%d %H:%M:%S')}, saved on her save")
            return (f"her voice is on {arg} ({known[arg]}) for this run -- the next reply and any "
                    f"swipe. /voicemodel auto to unpin; tools/set_model.py to keep it.")
        pin = self.store.get("voice_model_override") if self.store is not None else None
        on = self.effective_model("persona")
        lines = [f"her voice: {on}" + (" (toggled in the chat)" if pin else " (from her config)")
                 + f" | provider: {name}",
                 "the toggle offers: " + (", ".join(offered) or "(nothing this provider can serve)")]
        for r in self.VOICE_ROLES:
            lines.append(f"  {r}: {self.effective_model(r)}")
        return "\n".join(lines)

    def _model_for(self, role, _model=None):
        """The model entry this role goes out on right now, with both live pins
        applied. One reader, so a second entry point cannot answer on a
        different model from `call` while both say they are this role."""
        m = _model or self.config.model(role)
        # `/model <name>`: one model for every role, this run only. Checked
        # here rather than in Config because Config has no store and is built
        # once at boot, and the point of this switch is not restarting.
        if _model is None and self.store is not None:
            pin = self.store.get("model_override")
            if pin:
                m = dict(m, model=pin)
        # The chat's own toggle (`/voicemodel`, kv `voice_model_override`):
        # the nine roles above and nothing else. It is the narrower switch, so
        # it wins over `/model` for those roles -- picking a model in the chat
        # header has to move her voice even when every role is pinned.
        if _model is None and self.store is not None and role in self.VOICE_ROLES:
            vpin = self.store.get("voice_model_override")
            if vpin:
                m = dict(m, model=vpin)
        return m

    def call(self, role, messages, max_tokens=None, _model=None, _provider=None, _json=False, on_delta=None):
        m = self._model_for(role, _model)
        name = _provider or self.active_provider()
        content = self._call_on(name, role, m, messages, max_tokens, _json=_json, on_delta=on_delta)
        if content is not None:
            return content
        logger.log(f"  [llm:{role}] no answer from {name}; the call is missed")
        # the ledger of what never got an answer: the loop reads it when the
        # provider is back and catches the record up (App.catch_up). On
        # 2026-08-31 the official account ran dry at 20:00 and seven director
        # ticks, seven phone looks and her X look went by with nobody writing
        # them; nothing knew afterwards.
        self.missed += 1
        if self.store is not None:
            rows = list(self.store.get("missed_calls", []) or [])
            rows.append({"ts": time.time(), "role": role})
            self.store.set("missed_calls", rows[-200:])
        return ""

    def _prefix_key(self, payload):
        """(a key for the system half of this prompt, how many bytes it is).

        The system prompt is the part that holds still for about a day
        (`persona/sections.py`), and it is the prefix the provider caches. Two
        calls of one role with different system prompts cannot read each
        other's entry, so they are not one burst."""
        import hashlib
        head = "".join(str(m.get("content") or "") for m in (payload.get("messages") or [])
                       if m.get("role") == "system")
        return hashlib.sha1(head.encode("utf-8", "replace")).hexdigest()[:16], len(head)

    def _hold_for_burst(self, role, payload):
        """Wait, at most once per burst, so the rest of the burst can read the
        first call's cached prefix. Returns the seconds waited.

        The rule: this call goes out inside the settle window of a call of the
        SAME role on the SAME system prefix, and that call came back cold. It
        is therefore the second call of a burst, and the entry the first one
        wrote is not readable yet. Waiting out the remainder of the window
        makes it readable, and every call after this one in the burst then
        reads it without waiting -- so fifteen calls cost one wait, not
        fifteen. A burst whose host does not cache at all still costs one:
        `held` stays set until a settle-length gap ends the burst.

        Nothing is held for a small prompt (a probe), because nothing is
        measured for one either."""
        api = self.config.api
        settle = float(getattr(api, "cache_settle_seconds", 15) or 0)
        if not settle or not bool(getattr(api, "cache_burst_hold", True)):
            return 0.0
        key, size = self._prefix_key(payload)
        if size < 8000:      # about 2,000 tokens, the floor `_track_cache` uses
            return 0.0
        prev = self._burst.get(role)
        if not prev or prev.get("prefix") != key or prev.get("held") or not prev.get("cold"):
            return 0.0
        gap = time.time() - float(prev.get("finish") or 0)
        if gap < 0 or gap >= settle:
            return 0.0
        wait = settle - gap
        logger.log(f"  [cache] {role}: held {wait:.0f}s so the burst reads the first call's "
                   f"prefix (the previous call of this role came back cold {gap:.0f}s ago, "
                   f"inside api.cache_settle_seconds {settle:.0f}s)")
        prev["held"] = True
        self.burst_holds += 1
        self.burst_held_seconds += wait
        time.sleep(wait)
        return wait

    def _note_burst(self, role, payload, in_tok, cached):
        """What the gate reads next time: this call's prefix, when it
        finished, whether it came back cold, and whether the burst it belongs
        to has already paid its wait."""
        settle = float(getattr(self.config.api, "cache_settle_seconds", 15) or 0)
        if not settle:
            return
        key, _size = self._prefix_key(payload)
        prev = self._burst.get(role) or {}
        now = time.time()
        same_burst = (prev.get("prefix") == key
                      and (now - float(prev.get("finish") or 0)) < settle)
        self._burst[role] = {"prefix": key, "finish": now,
                             "cold": (cached / float(in_tok or 1)) < 0.5,
                             "held": bool(prev.get("held")) if same_burst else False}

    def _call_on(self, name, role, m, messages, max_tokens, _json=False, on_delta=None):
        """One provider, the bot's own retries; returns the text, or None when
        the call is given up on."""
        payload, slug = self._payload(name, m, messages, max_tokens)
        self._tl.role = role
        # the first call of a burst goes out alone, and the rest of the burst
        # waits for its cached prefix to become readable -- once, not once
        # each (`_hold_for_burst`)
        self._hold_for_burst(role, payload)
        self.last_runaway = False
        fails = 0
        backoff = 2
        empties = 0
        while fails < self.config.api.max_retries:
            try:
                t0 = time.time()
                t_first = None
                if bool(getattr(self.config.api, "stream", True)):
                    content, reasoning, finish, usage, served, t_first = self._stream(name, payload, role, on_delta=on_delta)
                else:
                    resp = self._client(name).chat.completions.create(**payload)
                    raw = resp.model_dump()
                    usage = raw.get("usage", {}) or {}
                    msg = resp.choices[0].message
                    content = msg.content or ""
                    reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None) or ""
                    finish = raw.get("choices", [{}])[0].get("finish_reason")
                    served = raw.get("provider")
                self.last_usage = dict(usage or {}, role=role)
                self.last_reasoning = reasoning
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                dt = time.time() - t0
                self._last_dt = dt
                served = served or ("official" if self._providers()[name].get("kind") != "openrouter" else name)
                self.last_provider = (name, served)
                pinned = ((self._providers()[name].get("order") or {}).get(slug) or [None])[0]
                if pinned and served and str(served).lower().replace(" ", "") != str(pinned).lower().replace(" ", ""):
                    logger.log(f"  [llm:{role}] served by {served}, not {pinned}: the pinned host failed and the call fell through to OpenRouter's next host (api.host_fallback)")
                det = (usage or {}).get("completion_tokens_details") or {}
                pdet = (usage or {}).get("prompt_tokens_details") or {}
                cached = int(pdet.get("cached_tokens") or 0)
                out_tok = int(usage.get("completion_tokens") or 0)
                think_tok = int((det or {}).get("reasoning_tokens") or 0)
                self.calls.append({"ts": time.time(), "role": role, "s": round(dt, 1),
                                   "in": int(usage.get("prompt_tokens") or 0), "out": out_tok,
                                   "think": think_tok, "empty": not content, "provider": name, "served_by": served,
                                   "finish": finish, "cached": cached})
                if finish == "length" and content:
                    # the host's own output cap stopped the answer mid-word.
                    # Half a reply is not a reply: it is asked again once,
                    # like an empty one, and then given up on rather than sent
                    self.truncated += 1
                    logger.log(f"  [llm:{role}] TRUNCATED by {name}/{served} (finish length, completion {out_tok}, "
                               f"reasoning {think_tok}): the host's output cap cut the answer off")
                    if empties < int(getattr(self.config.api, "empty_retries", 1)):
                        empties += 1
                        logger.log(f"  [llm:{role}] cut off; asking once more")
                        continue
                    return None
                if not content:
                    self.empties += 1
                    # the guard used to require finish_reason 'length'; DeepSeek
                    # returned None and the persona silently produced nothing
                    logger.log(f"  [llm:{role}] EMPTY ANSWER from {name}/{served} (finish {finish}, completion "
                               f"{usage.get('completion_tokens', 0)}, reasoning {det.get('reasoning_tokens', 0)}); "
                               f"if reasoning used the whole budget, raise models.{role}.max_tokens")
                    # once more before anyone reads meaning into it: on
                    # 2026-08-31 122 tokens of reasoning and no words became
                    # "she read it and chose not to answer (90 min)" -- the
                    # withholding reads a repeated silence, not a hiccup
                    if finish != "length" and empties < int(getattr(self.config.api, "empty_retries", 1)):
                        empties += 1
                        logger.log(f"  [llm:{role}] empty answer; asking once more")
                        continue
                    return None
                if out_tok >= self.config.api.long_answer_warn:
                    # nothing bounds an answer any more, so an unusual one has to
                    # announce itself instead of just costing money quietly
                    logger.log(f"  [llm:{role}] LONG ANSWER: {out_tok} tokens")
                logger.log(f"  [llm:{role}] {dt:.1f}s" + (f" (first token {t_first:.1f}s)" if t_first else "")
                           + f" in={usage.get('prompt_tokens', 0)} out={out_tok}"
                           + (f" think={think_tok}" if think_tok else "") + f" via {name}/{served}"
                           + (f" cache={cached * 100 // max(1, int(usage.get('prompt_tokens') or 1))}%" if usage else " (no usage reported)"))
                # `t0` is when this request went out: the tracker measures the
                # idle gap from the previous call FINISHING to this one going
                # out, not finish to finish, so a slow answer does not inflate
                # the gap its successor is judged on
                self._track_cache(role, int(usage.get("prompt_tokens") or 0), cached, time.time(), started=t0)
                self._note_burst(role, payload, int(usage.get("prompt_tokens") or 0), cached)
                logger.log_llm(role, messages, content, reasoning, usage, dt,
                               extra={"provider": name, "served_by": served, "model": slug,
                                      "finish": finish, "first_token_s": round(t_first, 2) if t_first else None})
                self.last_ok_ts = time.time()
                # every role's output passes through here, so this is the one
                # place a voice check reaches all of them -- including roles
                # that do not exist yet. It FLAGS and returns the answer
                # untouched (`data/voice_rules.json`); the speaker-level check
                # happens where the speaker is known, in the exchange and the
                # beats.
                #
                # An answer that has to parse as JSON is machinery: its keys
                # are English by construction and so are the fields the code
                # reads back, so a rule about how a person writes cannot mean
                # anything about it. It is passed as `machinery` rather than
                # skipped, so a rule that IS true of any answer -- Hangul, a
                # simplified Chinese character -- still runs.
                try:
                    from sim import voicecheck
                    voicecheck.note(self.config, self.store, content, role=role, where="llm",
                                    context=("machinery",) if _json else ())
                except Exception:
                    pass
                return content
            except RunawayAnswer as e:
                # Not an error of the host's and not a retry with backoff: the
                # model looped. Asked once more, like an empty answer or a
                # truncated one, and then given up on -- the flag stops
                # `call_json` re-asking, because a re-ask after a loop loops
                # again and its first attempt is now the prompt.
                self.runaways += 1
                logger.log(f"  [llm:{role}] RUNAWAY from {name} ({e}); the answer was abandoned")
                if empties < int(getattr(self.config.api, "empty_retries", 1)):
                    empties += 1
                    logger.log(f"  [llm:{role}] repeating itself; asking once more")
                    continue
                self.last_runaway = True
                return None
            except Exception as e:
                fails += 1
                self.errors += 1
                err = str(e)
                if "onnection" in err or "imeout" in err or "getaddrinfo" in err:
                    netwatch.WATCH.fail(name, err)
                elif "402" in err or "alance" in err:
                    # a spent balance looked like any other error and the bot
                    # would go quiet retrying it; it is the one failure no
                    # retry fixes -- and if it really is an empty account then
                    # every character on this machine is a minute from the
                    # same answer, so the machine stops itself and every save
                    # gets the reason (`sim/downtime.py`)
                    logger.log(f"  [llm:{role}] OUT OF BALANCE at {name} ({err[:120]})")
                    downtime.no_credit(self.config, self.store, name, role, err, exc=e)
                    return None
                else:
                    logger.log(f"  [llm:{role}] {name} error ({fails}/{self.config.api.max_retries}): {err[:200]}")
                time.sleep(backoff)
                backoff *= 2
        logger.log(f"  [llm:{role}] {name}: {fails} errors in a row; giving up on this call")
        return None

    # ---- a call whose answer is a decision, not words --------------------

    def call_tools(self, role, messages, tools, tool_choice="auto", max_tokens=None,
                   _model=None, _provider=None):
        """One call that offers `tools` and hands back what the model picked.

        The same provider, the same pin, the same reasoning effort and the same
        receipts as `call`; `call` itself is untouched and grows no loop,
        because what a tool does, what it is capped at and whether this moment
        is one to look on are the program's and never the library's.

        Returns a dict -- `calls` (each with the id, the name, the parsed
        `arguments` or None when they did not parse, and the raw string),
        `text`, `finish`, `usage`, `served_by`, `seconds`, `first_token_s`,
        `faults` -- or None when the call was given up on, which is written to
        kv `missed_calls` like any other failure.

        `finish_reason: "tool_calls"` with no content is a NORMAL answer here.
        In `call` it is not reachable, and if it ever became reachable it would
        hit the empty-answer branch: logged as EMPTY ANSWER, asked once more,
        counted as missed, and the character would say nothing.

        There is no loop and no dispatch. One call, one answer, the caller
        decides what to do with it. Nothing is written into her history: an
        assistant message carrying tool calls and a `tool` message carrying a
        result are not things anybody said, and putting them in the record
        would break the alternation the thread is rebuilt on and move every
        byte behind them (`docs/tool-calling.md` §10)."""
        m = self._model_for(role, _model)
        name = _provider or self.active_provider()
        got = self._call_tools_on(name, role, m, messages, tools, tool_choice, max_tokens)
        if got is not None:
            return got
        logger.log(f"  [llm:{role}] no answer from {name}; the call is missed")
        self.missed += 1
        if self.store is not None:
            rows = list(self.store.get("missed_calls", []) or [])
            rows.append({"ts": time.time(), "role": role})
            self.store.set("missed_calls", rows[-200:])
        return None

    def _call_tools_on(self, name, role, m, messages, tools, tool_choice, max_tokens):
        """One provider, the bot's own retries; the answer as a dict, or None.

        Always streamed, whatever `api.stream` says: the fragments a tool call
        arrives in only exist in a stream, and a non-streamed body would have
        to be read a second way for no gain."""
        payload, slug = self._payload(name, m, messages, max_tokens,
                                      tools=tools, tool_choice=tool_choice)
        self._hold_for_burst(role, payload)
        fails = 0
        backoff = 2
        empties = 0
        while fails < self.config.api.max_retries:
            try:
                t0 = time.time()
                tools_out = {"calls": {}, "faults": []}
                content, reasoning, finish, usage, served, t_first = self._stream(
                    name, payload, role, tools_out=tools_out)
                self.last_usage = dict(usage or {}, role=role)
                self.last_reasoning = reasoning
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                dt = time.time() - t0
                self._last_dt = dt
                served = served or ("official" if self._providers()[name].get("kind") != "openrouter" else name)
                self.last_provider = (name, served)
                pinned = ((self._providers()[name].get("order") or {}).get(slug) or [None])[0]
                if pinned and served and str(served).lower().replace(" ", "") != str(pinned).lower().replace(" ", ""):
                    logger.log(f"  [llm:{role}] served by {served}, not {pinned}: the pinned host failed and the "
                               f"call fell through to OpenRouter's next host (api.host_fallback)")
                calls = []
                for i in sorted(tools_out["calls"]):
                    slot = tools_out["calls"][i]
                    raw = slot.get("arguments") or ""
                    args = None
                    try:
                        parsed = json.loads(raw) if raw.strip() else {}
                        args = parsed if isinstance(parsed, dict) else None
                        if args is None:
                            tools_out["faults"].append(
                                f"{slot.get('name')}: the arguments were a {type(parsed).__name__}, not an object")
                    except json.JSONDecodeError as e:
                        tools_out["faults"].append(f"{slot.get('name')}: the arguments did not parse ({e.msg})")
                    calls.append({"id": slot.get("id") or "", "name": slot.get("name") or "",
                                  "arguments": args, "raw": raw})
                det = (usage or {}).get("completion_tokens_details") or {}
                pdet = (usage or {}).get("prompt_tokens_details") or {}
                cached = int(pdet.get("cached_tokens") or 0)
                out_tok = int((usage or {}).get("completion_tokens") or 0)
                think_tok = int((det or {}).get("reasoning_tokens") or 0)
                self.calls.append({"ts": time.time(), "role": role, "s": round(dt, 1),
                                   "in": int((usage or {}).get("prompt_tokens") or 0), "out": out_tok,
                                   "think": think_tok, "empty": not (content or calls),
                                   "provider": name, "served_by": served, "finish": finish,
                                   "cached": cached, "tool_calls": len(calls)})
                if finish == "length" and (content or calls):
                    self.truncated += 1
                    logger.log(f"  [llm:{role}] TRUNCATED by {name}/{served} (finish length, completion {out_tok}, "
                               f"reasoning {think_tok}): the host's output cap cut the answer off")
                    if empties < int(getattr(self.config.api, "empty_retries", 1)):
                        empties += 1
                        logger.log(f"  [llm:{role}] cut off; asking once more")
                        continue
                    return None
                # A picked tool IS the answer. `finish_reason: "tool_calls"`
                # comes back with no content by design, so an answer is empty
                # only when neither words nor a call arrived.
                if not content and not calls:
                    self.empties += 1
                    logger.log(f"  [llm:{role}] EMPTY ANSWER from {name}/{served} (finish {finish}, completion "
                               f"{out_tok}, reasoning {think_tok}, no tool call)")
                    if finish != "length" and empties < int(getattr(self.config.api, "empty_retries", 1)):
                        empties += 1
                        logger.log(f"  [llm:{role}] empty answer; asking once more")
                        continue
                    return None
                if tools_out["faults"]:
                    logger.log(f"  [llm:{role}] tool call read with faults: "
                               + "; ".join(tools_out["faults"][:3]))
                logger.log(f"  [llm:{role}] {dt:.1f}s" + (f" (first token {t_first:.1f}s)" if t_first else "")
                           + f" in={(usage or {}).get('prompt_tokens', 0)} out={out_tok}"
                           + (f" think={think_tok}" if think_tok else "")
                           + f" via {name}/{served} finish={finish} "
                           + (("picked " + ", ".join(c["name"] for c in calls)) if calls else "picked nothing")
                           + (f" cache={cached * 100 // max(1, int((usage or {}).get('prompt_tokens') or 1))}%" if usage else " (no usage reported)"))
                self._track_cache(role, int((usage or {}).get("prompt_tokens") or 0), cached, time.time(), started=t0)
                self._note_burst(role, payload, int((usage or {}).get("prompt_tokens") or 0), cached)
                logger.log_llm(role, messages, content, reasoning, usage, dt,
                               extra={"provider": name, "served_by": served, "model": slug,
                                      "finish": finish, "first_token_s": round(t_first, 2) if t_first else None,
                                      "tools_offered": [((t.get("function") or {}).get("name") or "") for t in (tools or [])],
                                      "tool_calls": [{"name": c["name"], "arguments": c["raw"]} for c in calls],
                                      "tool_faults": tools_out["faults"]})
                self.last_ok_ts = time.time()
                return {"calls": calls, "text": content, "finish": finish, "usage": usage or {},
                        "served_by": served, "provider": name, "model": slug,
                        "seconds": round(dt, 3), "first_token_s": round(t_first or 0, 3),
                        "reasoning": reasoning, "faults": tools_out["faults"]}
            except RunawayAnswer as e:
                self.runaways += 1
                logger.log(f"  [llm:{role}] RUNAWAY from {name} ({e}); the answer was abandoned")
                if empties < int(getattr(self.config.api, "empty_retries", 1)):
                    empties += 1
                    logger.log(f"  [llm:{role}] repeating itself; asking once more")
                    continue
                self.last_runaway = True
                return None
            except Exception as e:
                fails += 1
                self.errors += 1
                err = str(e)
                if "onnection" in err or "imeout" in err or "getaddrinfo" in err:
                    netwatch.WATCH.fail(name, err)
                elif "402" in err or "alance" in err:
                    logger.log(f"  [llm:{role}] OUT OF BALANCE at {name} ({err[:120]})")
                    downtime.no_credit(self.config, self.store, name, role, err, exc=e)
                    return None
                else:
                    logger.log(f"  [llm:{role}] {type(e).__name__} ({fails}/{self.config.api.max_retries}): {err[:200]}")
                time.sleep(backoff)
                backoff *= 2
        logger.log(f"  [llm:{role}] {name}: {fails} errors in a row; giving up on this call")
        return None

    def _note_abandoned(self, name, role, payload, e, chunks, seconds,
                        content, reasoning, usage, served):
        """A stream that ended in anything but an answer, written to the run's
        record of model calls so the ledger and `/provider` count it.

        The host has been generating for as long as this ran and bills for
        it. Nothing wrote it down: the call went round the retry, the retry
        answered, and only the retry left a row -- ten minutes of a paid model
        with no trace, on 2026-09-07 at 16:13:56.

        The receipt's own numbers where the last chunk carried them. Where it
        did not, the prompt is measured off the bytes that went out and the
        answer off the bytes that came back, at four characters to the token,
        and the row says `estimated` so nothing reads the figure as the
        host's. Priced the way `tools/llmstats.py` prices any row with no
        cost on it: the published rates for the slug that answered."""
        try:
            text, think = "".join(content), "".join(reasoning)
            u = dict(usage or {})
            estimated = not u.get("prompt_tokens")
            if estimated:
                sent = sum(len(str(m.get("content") or "")) for m in payload.get("messages") or [])
                u["prompt_tokens"] = int(sent / 4)
                u["completion_tokens"] = int((len(text) + len(think)) / 4)
                u["total_tokens"] = u["prompt_tokens"] + u["completion_tokens"]
            self.abandoned += 1
            self.calls.append({"ts": time.time(), "role": role, "s": round(seconds, 1),
                               "in": int(u.get("prompt_tokens") or 0),
                               "out": int(u.get("completion_tokens") or 0),
                               "think": 0, "empty": not text, "provider": name,
                               "served_by": served, "finish": "abandoned", "cached": 0})
            logger.log(f"  [llm:{role}] ABANDONED after {seconds:.0f}s and {chunks} chunk(s), "
                       f"{len(text)} char(s) written ({type(e).__name__}); recorded as a paid call"
                       + (" with estimated tokens" if estimated else " with the host's own usage"))
            logger.log_llm(role, payload.get("messages") or [], text, think, u, seconds,
                           extra={"provider": name, "served_by": served,
                                  "model": payload.get("model"), "finish": "abandoned",
                                  "abandoned_reason": f"{type(e).__name__}: {str(e)[:200]}",
                                  "chunks": chunks, "estimated": bool(estimated)})
        except Exception as inner:
            logger.log(f"  [llm:{role}] the abandoned stream was not recorded: {type(inner).__name__}")

    def _stream(self, name, payload, role, tools_out=None, on_delta=None):
        """The answer read as it is written, chunk by chunk, so that a bad one
        announces itself instead of arriving as a shorter-than-usual body: a
        stream that ends with no finish reason was CUT OFF (the connection
        dropped, the host died mid-answer) and raises, which sends the call
        round the retry; no bytes for `api.stream_stall_seconds` is a dead
        host, not a slow one, and raises there rather than at the ten-minute
        request timeout, which still bounds the whole answer; an `error`
        object a host sends inside the stream raises with its message.
        Returns (content, reasoning, finish_reason, usage, served_by,
        seconds to the first token). Usage arrives in the last chunk
        (`stream_options.include_usage`); a host that sends none leaves it
        empty and the log says so.

        `tools_out`, when a caller passes one, is where the streamed tool
        calls are reassembled: `{"calls": {index: slot}, "faults": [...]}`,
        filled in place so the return shape every other caller reads does not
        move. Reassembly is BY INDEX and it is not optional -- measured on the
        wire (`docs/tool-calling.md` §4), one call arrives as five fragments
        under one index: the first carries the id and the function name with
        empty arguments, the second carries nothing but the index, the next
        two carry the arguments one character at a time, and the last carries
        the finish reason with `tool_calls: null`. Anything that reads the
        name off the last fragment, or concatenates arguments in arrival order
        across indexes, gets nothing usable."""
        import httpx
        api = self.config.api
        stall = float(getattr(api, "stream_stall_seconds", 240) or 0) or None
        req = dict(payload, stream=True, stream_options={"include_usage": True})
        if stall:
            req["timeout"] = httpx.Timeout(stall, connect=min(30.0, stall))
        t0 = time.time()
        self._partial = (0, [], [], {}, None)
        try:
            return self._stream_body(name, payload, req, role, tools_out, t0, on_delta=on_delta)
        except Exception as e:
            # The host has been writing for as long as this ran and bills for
            # it, whether the stream timed out, stalled, was cut off, sent an
            # error object or looped. A call that never got a chunk is a
            # failure to connect and cost nothing, so it is not recorded here.
            n, content, reasoning, usage, served = self._partial
            if n:
                self._note_abandoned(name, role, payload, e, n, time.time() - t0,
                                     content, reasoning, usage, served)
            raise

    def _stream_body(self, name, payload, req, role, tools_out, t0, on_delta=None):
        """The loop itself. What it has read so far is kept on `_partial` so
        that the caller above can write a row for a stream that never
        finished."""
        api = self.config.api
        total = float(getattr(api, "request_timeout_seconds", 600) or 600)
        content, reasoning = [], []
        finish, usage, served, t_first = None, {}, None, None
        n = 0
        guard_at = int(getattr(api, "repeat_guard_chars", 6000) or 0)
        copies = int(getattr(api, "repeat_guard_copies", 4) or 4)
        chars = 0
        next_check = guard_at
        self._partial = (0, content, reasoning, usage, None)
        with self._client(name).chat.completions.create(**req) as st:
            for chunk in st:
                n += 1
                now = time.time()
                if t_first is None:
                    t_first = now - t0
                if now - t0 > total:
                    raise TimeoutError(f"stream timeout: {total:.0f}s and still writing after {n} chunks "
                                       f"({sum(map(len, content))} chars); the answer is a runaway")
                d = chunk.model_dump() if hasattr(chunk, "model_dump") else dict(chunk)
                if d.get("error"):
                    err = d["error"]
                    raise RuntimeError(f"error in stream: {err.get('message') if isinstance(err, dict) else err}"[:300])
                served = served or d.get("provider")
                if d.get("usage"):
                    usage = d["usage"]
                for ch in d.get("choices") or []:
                    delta = ch.get("delta") or {}
                    if delta.get("content"):
                        content.append(delta["content"])
                        chars += len(delta["content"])
                        # a channel that shows her reply as it is written
                        # (`channels/vn_bot.py`) reads it through this: the
                        # text so far, never a chunk, so the reader replaces
                        # rather than reassembles. A sink that raises must not
                        # break the call it is only watching.
                        if on_delta is not None:
                            try:
                                on_delta("".join(content))
                            except Exception:
                                on_delta = None
                    r = delta.get("reasoning_content") or delta.get("reasoning")
                    if r:
                        reasoning.append(r)
                    if tools_out is not None:
                        for frag in (delta.get("tool_calls") or []):
                            idx = frag.get("index")
                            if idx is None:
                                tools_out["faults"].append("a tool-call fragment arrived with no index")
                                idx = len(tools_out["calls"])
                            slot = tools_out["calls"].setdefault(
                                idx, {"id": "", "type": "function", "name": "", "arguments": ""})
                            if frag.get("id"):
                                if slot["id"] and slot["id"] != frag["id"]:
                                    tools_out["faults"].append(f"index {idx} was given a second id")
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
                # A model that has started repeating itself will not stop on
                # its own, and nothing else here would notice: it streams
                # steadily, so the stall timeout never fires, and it ends at
                # the host's ceiling, which bills for every token of it. The
                # answer is ended where the repetition starts -- about 1.5%
                # of the way into each of the five auditor runaways.
                if guard_at and chars >= next_check:
                    whole = "".join(content)
                    tail = whole[-_REPEAT_WINDOW:]
                    if tail and whole.count(tail) >= copies:
                        raise RunawayAnswer(
                            f"REPEATING: after {len(whole)} characters the last {_REPEAT_WINDOW} "
                            f"had already been written {whole.count(tail) - 1} times")
                    next_check = chars + _REPEAT_STEP
                self._partial = (n, content, reasoning, usage, served)
        self._partial = (n, content, reasoning, usage, served)
        if finish is None:
            self.cut_off += 1
            raise ConnectionError(f"CUT OFF: the stream ended after {n} chunks and {sum(map(len, content))} chars "
                                  f"with no finish reason; the answer was not complete")
        return "".join(content), "".join(reasoning), finish, usage or {}, served, t_first

    def _track_cache(self, role, in_tok, cached, now, started=None):
        """The provider's prompt cache as a measured thing. Per role: the last
        hit rate, how many calls came back warm and how many came back cold,
        the longest idle gap after which a call still came back warm, and the
        shortest and the most recent after which it came back cold. A prompt
        under 2000 tokens is not tracked (probes). The answer to "how long
        does this host keep the entry" is the pair of gaps: warm up to N, cold
        by M; when M is well above the provider's stated lifetime the cold
        call was a changed prefix, not an expiry.

        A cold call is counted whenever the hit rate is under half and this
        role has a previous call to measure the gap from, whatever that call
        did. The count used to require the PREVIOUS call to have come back
        warm, so a role that is cold every time recorded nothing at all and
        the table read "never gone cold" while every single call was missing
        (both live saves, the OpenRouter audit of 2026-09-04:
        `data/retired/20260904_openrouter_audit/REPORT.md` §5).

        The gap is measured from the previous tracked call FINISHING to this
        one going out, which is the interval the entry has to survive. A call
        that goes out inside `api.cache_settle_seconds` of that finish is
        counted on its own line and never as cold: the write has not landed
        yet. Measured on Z.AI at 44k tokens, the entry a call writes is not
        readable for about ten seconds after that call completes, which is
        what a 0% on the second of two calls nineteen seconds apart was."""
        if in_tok < 2000:
            return
        try:
            ratio = cached / float(in_tok)
            warm = ratio >= 0.5
            tr = (self.store.get("cache_track", {}) if self.store is not None else self.cache_track) or {}
            r = dict(tr.get(role) or {})
            last_ts = float(r.get("last_ts") or 0)
            gap = (float(started or now) - last_ts) if last_ts else 0.0
            settle = float(getattr(self.config.api, "cache_settle_seconds", 15) or 0)
            was_warm = float(r.get("last_ratio") or 0) >= 0.5
            if warm:
                r["warm_events"] = int(r.get("warm_events") or 0) + 1
                if gap:
                    r["warm_gap_max"] = max(float(r.get("warm_gap_max") or 0), gap)
                if not was_warm:
                    r["warm_since"] = now
            elif last_ts and gap < settle:
                # under the settle window, or negative: two calls of one role
                # running at once (the compile fans out), where the second went
                # out before the first had finished writing anything at all
                r["settling"] = int(r.get("settling") or 0) + 1
                r["settling_gap_last"] = round(gap, 1)
                logger.log(f"  [cache] {role}: {ratio * 100:.0f}% cached, sent "
                           + (f"{gap:.0f}s after the previous call of this role finished" if gap >= 0
                              else "while the previous call of this role was still running")
                           + f" -- inside api.cache_settle_seconds ({settle:.0f}s), so the entry it wrote was "
                             f"probably not readable yet; not counted as cold")
            elif last_ts:
                r["cold_events"] = int(r.get("cold_events") or 0) + 1
                r["cold_gap_last"] = round(gap, 1)
                r["cold_gap_min"] = min(float(r.get("cold_gap_min") or 1e12), gap)
                r["warm_since"] = None
                if was_warm:
                    logger.log(f"  [cache] {role}: COLD after {_gap_words(gap)} idle (was {float(r.get('last_ratio') or 0) * 100:.0f}% cached; "
                               f"the longest gap that still came back warm: {_gap_words(r.get('warm_gap_max'))})")
            r.update({"last_ts": now, "last_ratio": round(ratio, 3), "last_in": in_tok, "last_cached": cached})
            tr[role] = r
            if self.store is not None:
                self.store.set("cache_track", tr)
            else:
                self.cache_track = tr
        except Exception as e:
            logger.log(f"  [cache] not tracked: {type(e).__name__}: {e}")

    # ---- the operator's view -------------------------------------------

    def summary(self):
        """Calls this run: the last hour and the last day by role, seconds and
        tokens, empties and errors, and the last few calls."""
        now = time.time()
        calls = list(self.calls)
        def agg(rows):
            by = {}
            for r in rows:
                b = by.setdefault(r["role"], {"n": 0, "s": 0.0, "in": 0, "out": 0, "think": 0})
                b["n"] += 1
                b["s"] += r["s"]
                b["in"] += r["in"]
                b["out"] += r["out"]
                b["think"] += r["think"]
            for b in by.values():
                b["s"] = round(b["s"] / max(1, b["n"]), 1)
            return dict(sorted(by.items(), key=lambda kv: -kv[1]["n"]))
        hour = [r for r in calls if now - r["ts"] <= 3600]
        day = [r for r in calls if now - r["ts"] <= 86400]
        return {"hour": len(hour), "day": len(day), "run": len(calls),
                "tokens_hour": sum(r["in"] + r["out"] for r in hour),
                "tokens_day": sum(r["in"] + r["out"] for r in day),
                "seconds_hour": round(sum(r["s"] for r in hour), 1),
                "by_role_hour": agg(hour), "by_role_day": agg(day),
                "errors": self.errors, "empties": self.empties, "missed": self.missed,
                "truncated": self.truncated, "cut_off": self.cut_off,
                "runaways": self.runaways,
                "provider": self.active_provider(),
                "last": [{"ago": int(now - r["ts"]), "role": r["role"], "s": r["s"], "out": r["out"],
                          "via": f"{r.get('provider')}/{r.get('served_by')}"} for r in calls[-8:]][::-1]}

    def provider_cmd(self, arg=""):
        """`/provider` -- who answers and what each provider maps; `/provider
        <name>` pins one (kv provider_override); `/provider auto` clears the
        pin. A pin is a decision somebody takes; nothing is fallen to."""
        arg = (arg or "").strip()
        provs = self._providers()
        if arg == "auto":
            self.store.set("provider_override", None)
            return f"provider override cleared; api.provider decides: {self.active_provider()}"
        if arg:
            if arg not in provs:
                return f"no provider '{arg}'; configured: {', '.join(provs)}"
            self.store.set("provider_override", arg)
            return f"provider pinned: {arg} (/provider auto to unpin)"
        override = self.store.get("provider_override") if self.store is not None else None
        lines = [f"active: {self.active_provider()}" + (" (pinned by /provider)" if override else "")
                 + f" | missed calls this run: {self.missed}, errors {self.errors}, empties {self.empties}, "
                 + f"truncated {self.truncated}, cut off {self.cut_off}, runaways {self.runaways}, "
                 + f"abandoned streams {self.abandoned} (each one billed and on the record)"
                 + (f"; {self.burst_holds} burst(s) held {self.burst_held_seconds:.0f}s in total "
                    f"so the calls behind the first could read its prefix" if self.burst_holds else ""),
                 "rule: one provider, no fallback; a failed call is logged and caught up when the host is back"]
        for name, p in provs.items():
            models = ", ".join(f"{k}->{v}" for k, v in (p.get("models") or {}).items()) or "(names as given)"
            lines.append(f"- {name} [{p.get('kind', 'deepseek')}]\n    {models}")
        tr = (self.store.get("cache_track", {}) if self.store is not None else self.cache_track) or {}
        if tr:
            lines.append("prompt cache, per role: last hit rate | calls that came back warm, and the longest idle gap one "
                         "survived | calls that came back cold, the last gap and the shortest | calls sent too soon after "
                         "the one before to have read its entry (api.cache_settle_seconds)")
            for role, r in sorted(tr.items(), key=lambda kv: -float(kv[1].get("last_in") or 0))[:10]:
                warm_max = float(r.get("warm_gap_max") or 0)
                cold_min = float(r.get("cold_gap_min") or 0)
                # a row written before the counts existed has the gaps and no
                # tally: one cold call is the least it can have seen
                n_warm = int(r.get("warm_events") or 0) or (1 if warm_max else 0)
                n_cold = int(r.get("cold_events") or 0) or (1 if cold_min else 0)
                settling = int(r.get("settling") or 0)
                parts = [f"{float(r.get('last_ratio') or 0) * 100:.0f}% ({int(r.get('last_cached') or 0)} of {int(r.get('last_in') or 0)})",
                         (f"warm {n_warm}x" + (f", up to {_gap_words(warm_max)} idle" if warm_max else "")
                          if n_warm else "never come back warm"),
                         (f"cold {n_cold}x" + (f", last after {_gap_words(r.get('cold_gap_last'))}" if r.get("cold_gap_last") else "")
                          + (f", shortest {_gap_words(cold_min)}" if cold_min else "")
                          if n_cold else "never gone cold")]
                if settling:
                    parts.append(f"{settling} sent inside the settle window")
                lines.append(f"- {role}: " + " | ".join(parts))
        last = [r for r in list(self.calls)[-6:]][::-1]
        if last:
            lines.append("last calls: " + "; ".join(f"{r['role']} {r['s']}s via {r.get('provider')}/{r.get('served_by')}" for r in last))
        return "\n".join(lines)

    def speed_probe(self, names=None):
        """`/speed` -- one small call on every configured provider (the pinned
        host order as configured), seconds and tokens per second, who served
        it. Nothing is stored."""
        rows = []
        m = dict(self.config.raw["models"]["voice"], thinking=False, temperature=0.0)
        messages = [{"role": "system", "content": "Reply with exactly the word OK."}, {"role": "user", "content": "ping"}]
        for name in (names or list(self._providers())):
            t0 = time.time()
            text = self.call("probe", messages, _model=m, _provider=name)
            dt = time.time() - t0
            served = self.last_provider[1] if self.last_provider and self.last_provider[0] == name else "?"
            u = self.last_usage or {}
            out = int(u.get("completion_tokens") or 0)
            rows.append(f"- {name}: {'ok' if text else 'NO ANSWER'} {dt:.1f}s, {out} tok" +
                        (f", {out / dt:.0f} tok/s" if text and dt else "") + f" via {served}" +
                        (f" -> {text[:30]!r}" if text and text.strip() != "OK" else ""))
        return "speed probe (voice model, tiny prompt, thinking off):\n" + "\n".join(rows)

    def call_json(self, role, messages, max_tokens=None):
        # Models wrap JSON in fences or prose; pull the first {...} block.
        text = self.call(role, messages, max_tokens, _json=True)
        data = parse_json_block(text)
        # An answer that is not JSON is asked for again, `api.json_retries`
        # times, with the bad answer in the conversation so the model fixes
        # its own text rather than writing a new one. Before this a single
        # malformed answer was the caller's problem, and the compile of
        # 2026-08-26 stored 7.5k of broken JSON as the day she remembered.
        tries = int(self.config.api.json_retries)
        if self.last_runaway:
            # The answer repeated itself until it was abandoned. There is
            # nothing here for the model to repair, and asking again with the
            # same prompt produced the same loop three times out of three on
            # 2026-09-03 and 2026-09-04. The call is already in `missed_calls`
            # for `App.catch_up`; the caller gets None and says so.
            logger.log(f"  [llm:{role}] the answer ran away; not asking again")
            return None, ""
        # A judge whose first answer is not JSON and reads as HER has stopped
        # judging and started being her. It is caught and re-asked below, and
        # before this line the re-ask was all the log said: the continuity
        # checker answered as the second character at 08:41:07 on 2026-09-04,
        # in her voice, addressed to him, and the opening sentence was the one
        # she sent eighteen seconds later -- found by reading the log five days
        # afterwards. Said once, on the first answer only.
        if data is None:
            why = reads_as_her(text, self.config)
            if why:
                flat = " ".join(str(text).split())[:60]
                logger.log(f"  [llm:{role}] the answer is not a verdict, it is HER "
                           f"({why}): {flat!r}")
        while data is None and tries > 0:
            tries -= 1
            big = int(getattr(self.config.api, "json_retry_max_chars", 8000) or 0)
            if text and big and len(text) > big:
                # The re-ask exists so the model can repair its own
                # punctuation, and it hands the bad answer back to do it. A
                # bad answer of half a megabyte is not repairable and sending
                # it costs its whole length as prompt: two of the auditor's
                # runaways went out at 150,000 prompt tokens that way. Ask the
                # original question again instead.
                logger.log(f"  [llm:{role}] answer was not JSON and is too long to send back "
                           f"({len(text)} chars > {big}); asking the original question again")
                again = messages
            elif text:
                logger.log(f"  [llm:{role}] answer was not JSON ({len(text)} chars), asking for it again")
                again = messages + [{"role": "assistant", "content": text},
                                    {"role": "user", "content": "That was not valid JSON (it failed to parse). Return exactly the same content "
                                                                "as ONE valid JSON object and nothing else: every value a proper string, "
                                                                "list or object, no bare text after a comma, no comments, no trailing commas."}]
            else:
                logger.log(f"  [llm:{role}] no answer to parse, asking again")
                again = messages
            text = self.call(role, again, max_tokens, _json=True)
            data = parse_json_block(text)
        return data, text


# Whether an answer that should have been a verdict reads as the character
# instead. No model call: her name as her own sheet spells it, or a
# first-person marker standing beside an address to him. Used only on an
# answer that already failed to parse, so a false positive costs one log line.
_AS_HER_I = ("私", "わたし", "あたし", "僕", "俺", "うち")
_AS_HER_YOU = ("あんた", "きみ", "君", "お前")
# Case-insensitive and word-bounded on the English side, because a model
# writing as her writes "i'm", never "I'm": the check missed "i'm just lying
# here thinking about you" while it was anchored on the capital.
_EN_I = re.compile(r"\b(i|i'm|i've|i'll|me|my|myself)\b", re.I)
_EN_YOU = re.compile(r"\b(you|you're|your|yours)\b", re.I)


def _name_forms(config):
    """Her name the ways her own sheet spells it, longer than one character."""
    ch = getattr(config, "character", None)
    out = set()
    for key in ("name", "name_ja", "reading_ja"):
        v = str(getattr(ch, key, "") or "").strip()
        if not v:
            continue
        out.add(v)
        out.update(p for p in v.replace("\u3000", " ").split() if len(p) > 1)
    return {n for n in out if len(n) > 1}


def reads_as_her(text, config):
    """The reason this answer reads as the character, or "" if it does not."""
    t = str(text or "")
    if not t.strip():
        return ""
    for n in _name_forms(config):
        if n in t:
            return f"it says {n!r}"
    said_i = [m for m in _AS_HER_I if m in t]
    said_you = [m for m in _AS_HER_YOU if m in t]
    m_i, m_you = _EN_I.search(t), _EN_YOU.search(t)
    if m_i:
        said_i.append(m_i.group(0))
    if m_you:
        said_you.append(m_you.group(0))
    if said_i and said_you:
        return f"first person ({said_i[0]}) speaking to him ({said_you[0].strip()})"
    return ""


def _gap_words(seconds):
    """An idle gap as a reader wants it: seconds while they still mean
    something, minutes once they do not. The cache table used to print every
    gap in whole minutes, so the seven-second gap the second character's two
    consecutive persona calls were actually apart read as "0 min"."""
    s = float(seconds or 0)
    return f"{s:.0f}s" if s < 90 else f"{s / 60:.0f} min"


def parse_json_block(text):
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        block = text[start:end + 1]
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass
        # Two repairs, tried in turn, before the answer is given up on.
        # A trailing comma before a closing brace or bracket is the one thing
        # these models get wrong often enough to be worth repairing rather
        # than throwing the whole answer away: the ick role lost a complete,
        # correct scoring to a comma on 2026-08-20. Only touches commas that
        # sit outside a string. The other is a string value written as
        # several strings ("narrative": "para", "para", ...), which flash did
        # to the whole compile of 2026-08-26.
        for cand in (_strip_trailing_commas(block), _strip_trailing_commas(_join_split_strings(block))):
            try:
                return json.loads(cand)
            except json.JSONDecodeError:
                continue
    return None


def _strip_trailing_commas(block):
    out, in_str, esc = [], False, False
    for ch in block:
        if esc:
            esc = False
        elif ch == "\\" and in_str:
            esc = True
        elif ch == '"':
            in_str = not in_str
        if not in_str and ch in "}]":
            while out and out[-1].isspace():
                out.pop()
            if out and out[-1] == ",":
                out.pop()
        out.append(ch)
    return "".join(out)


def _str_end(s, i):
    """Index of the quote that closes the string opening at s[i]."""
    j = i + 1
    while j < len(s):
        if s[j] == "\\":
            j += 2
            continue
        if s[j] == '"':
            return j
        j += 1
    return len(s) - 1


def _join_split_strings(s):
    """`"key": "one", "two", "three"` inside an object becomes one string with
    paragraph breaks. Only a string that follows a colon in an object is a
    candidate, and only a following string that is not itself a key (no
    colon after it) is joined, so arrays and ordinary keys are untouched."""
    out, i, n, stack, prev = [], 0, len(s), [], ""
    while i < n:
        ch = s[i]
        if ch == '"':
            j = _str_end(s, i)
            is_value = prev == ":" and stack and stack[-1] == "{"
            out.append(s[i:j])
            i = j + 1
            while is_value:
                k = i
                while k < n and s[k].isspace():
                    k += 1
                if k >= n or s[k] != ",":
                    break
                m = k + 1
                while m < n and s[m].isspace():
                    m += 1
                if m >= n or s[m] != '"':
                    break
                e = _str_end(s, m)
                q = e + 1
                while q < n and s[q].isspace():
                    q += 1
                if q < n and s[q] == ":":
                    break
                out.append("\\n\\n" + s[m + 1:e])
                i = e + 1
            out.append('"')
            prev = '"'
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]" and stack:
            stack.pop()
        if not ch.isspace():
            prev = ch
        out.append(ch)
        i += 1
    return "".join(out)
