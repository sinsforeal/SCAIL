"""The models a voicelab run can put behind the same prompt, and how each is called.

Kept out of `tools/voicelab.py` because it is a different job: that file decides
what a fair comparison is, this one deals with five vendors disagreeing about
what a request looks like.

**Not routed through `llm.py` on purpose.** That client is configuration-driven
(`api.providers` in each character's config), carries provider health, strikes
and a fallback chain, and is read by two running bots. Adding five hosts to it
to run a bench would mean editing `config.py:DEFAULTS` and both config files --
a live-system change for a measurement -- and its fallback chain would silently
move a call to another host mid-run, which is the one thing a bench comparing
hosts must never do. So this calls each vendor directly, pins the host, and
fails loudly instead of falling back.

**Fairness, and its limits.** Every model gets the same prompt, temperature
1.0, and reasoning at the highest setting short of a vendor's unbounded
default -- which is what her live `persona` role uses (thinking on, effort
high). Exact equivalence across vendors is not achievable and is not claimed:
"effort: high" on an OpenRouter host, `reasoning_effort: "high"` on Kimi and a
`thinkingBudget` in tokens on Vertex are three different dials. What is held is
the intent (think hard, then answer) and everything the prompt contains. Where
a vendor's default would differ, the deviation is written down here rather than
left in a shrug -- see `NOTE` on each row.

Costs are OpenRouter's posted per-million prices for the pinned host, read on
2026-09-02; Vertex bills separately and its row is the published Gemini price
for the same model, so its dollar figure is an estimate rather than a receipt.
"""

import io
import json
import os
import time

# name -> how to call it. `order` pins ONE OpenRouter host: a bench that lets
# the router pick is a bench of the router.
MODELS = {
    "deepseek-v4-flash": {
        "kind": "openrouter", "slug": "deepseek/deepseek-v4-flash-0731", "order": ["together"],
        "price_in": 0.14, "price_out": 0.28, "host": "Together",
        "NOTE": ("the first character's model. DeepSeek is only ever reached through "
                 "OpenRouter here: the first-party endpoint has no balance, and it is "
                 "not in either character's chain"),
    },
    "minimax-m3": {
        "kind": "openrouter", "slug": "minimax/minimax-m3", "order": ["novita"],
        "price_in": 0.30, "price_out": 1.20, "host": "Novita",
        "NOTE": "reasoning via OpenRouter's effort flag, same as the control",
    },
    "sakana-namazu": {
        "kind": "openrouter", "slug": "sakana/sakana-namazu", "order": ["Sakana AI"],
        "price_in": 0.95, "price_out": 4.00, "host": "Sakana AI",
        "reasoning_effort": "medium",
        "NOTE": "the second character's live voice model from 2026-09-04 (his call); one host, 262k window",
    },
    "kimi-k3": {
        "kind": "openrouter", "slug": "moonshotai/kimi-k3", "order": ["together"],
        "price_in": 3.00, "price_out": 15.00, "host": "Together",
        "reasoning_effort": "high",
        "NOTE": ("K3 always reasons and its own default is reasoning_effort=max; "
                 "pinned to high so it matches every other row instead of being "
                 "handed a bigger budget than the rest. Kimi's docs also require "
                 "reasoning_content to be carried back on historical assistant "
                 "turns -- see carry_reasoning() -- which costs nothing here "
                 "because the scenario history is authored rather than generated, "
                 "and matters the moment a run becomes multi-turn"),
    },
    "deepseek-v4-pro-0813": {
        "kind": "openrouter", "slug": "deepseek/deepseek-v4-pro-0813", "order": ["alibaba"],
        "price_in": 0.58, "price_out": 1.74, "host": "Alibaba",
        "NOTE": "the pro tier of the family she runs on",
    },
    "qwen3.8-flash": {
        "kind": "openrouter", "slug": "qwen/qwen3.8-flash", "order": ["alibaba"],
        "price_in": 0.15, "price_out": 0.47, "host": "Alibaba",
        "NOTE": "the only host serving it on OpenRouter, so nothing to pin against",
    },
    # --- added for the Japanese-quality bench. One arm, one question: which
    # model writes the best Japanese in her voice. Every row is pinned to one
    # host so the bench measures the model and not the router.
    "glm-5.3-flash": {
        "kind": "openrouter", "slug": "z-ai/glm-5.3-flash", "order": ["z-ai"],
        "price_in": 0.07, "price_out": 0.25, "host": "Z.AI",
        "NOTE": ("pinned to Z.AI's own host on OpenRouter, which is as close to the "
                 "first-party endpoint as this project can get -- there is no Z.AI key. "
                 "Six other hosts serve it at the same price and were not used"),
    },
    "glm-5.3": {
        "kind": "openrouter", "slug": "z-ai/glm-5.3", "order": ["z-ai"],
        "price_in": 1.40, "price_out": 4.40, "host": "Z.AI",
        "NOTE": ("same, and Z.AI is not the cheapest of its 24 hosts ($1.15 at Reka) -- "
                 "pinned to the maker's own host on purpose, so a bad answer is the "
                 "model's rather than a quantisation somebody else chose"),
    },
    "qwen3.8-max": {
        "kind": "openrouter", "slug": "qwen/qwen3.8-max", "order": ["alibaba"],
        "price_in": 2.00, "price_out": 6.00, "host": "Alibaba",
        "NOTE": "the top of the family whose flash tier answered in English in the first bench",
    },
    "sakana-namazu": {
        "kind": "openrouter", "slug": "sakana/sakana-namazu", "order": ["sakana"],
        "price_in": 0.95, "price_out": 4.00, "host": "Sakana AI",
        "NOTE": ("its only host, so nothing to pin against. A Japanese lab's model, which "
                 "is the interesting row in a bench about writing Japanese"),
    },
    "grok-4.6": {
        "kind": "openrouter", "slug": "x-ai/grok-4.6", "order": ["xai"],
        "price_in": 2.00, "price_out": 6.00, "host": "xAI",
        "NOTE": "pinned to xai rather than xai/zdr or Bedrock, which price differently",
    },
    "gpt-5.6-luna": {
        "kind": "openrouter", "slug": "openai/gpt-5.6-luna", "order": ["openai"],
        "price_in": 0.20, "price_out": 1.20, "host": "OpenAI",
        "NOTE": ("pinned to openai rather than openai/flex, which is half the price on a "
                 "slower queue -- a bench that waits differently is not the same bench"),
    },
    "gemini-3.8-flash": {
        "kind": "vertex", "slug": "gemini-3.8-flash",
        "price_in": 0.75, "price_out": 3.75, "host": "Vertex (direct)",
        "thinking_budget": 8192, "max_output": 16384,
        "NOTE": ("direct Vertex generateContent, not OpenRouter, using the same "
                 "service account and region=global as sensors/vision.py. Its "
                 "reasoning dial is a token budget rather than an effort word, so "
                 "8192 is a judgement call and the least comparable row in the "
                 "bench. maxOutputTokens must cover thinking AND the answer or "
                 "the answer comes back empty (PROJECT 10)"),
    },
}


def carry_reasoning(messages):
    """Kimi's requirement, applied to every vendor because it costs nothing.

    Its docs say to preserve `reasoning_content` on each historical assistant
    message or the model loses its own chain. Every assistant turn this harness
    sends is authored scenario history with no reasoning attached, so today this
    is a no-op that documents the rule. It stops being a no-op the moment a
    scenario runs more than one generated turn, and the failure then would be
    silent -- worse answers, no error.
    """
    return [dict(m) for m in messages]


# --------------------------------------------------------------------------

class Caller:
    """One vendor, one pinned host, no fallback. Returns (text, usage, seconds)."""

    def __init__(self, config):
        self.config = config
        self._clients = {}
        self._vertex = None

    # ---- OpenAI-compatible (DeepSeek official, OpenRouter) ----------------

    def _client(self, kind):
        from openai import OpenAI
        if kind in self._clients:
            return self._clients[kind]
        if kind == "deepseek":
            c = OpenAI(api_key=self.config.raw["api"]["api_key"],
                       base_url=self.config.raw["api"]["base_url"])
        else:
            key_path = self.config.raw["api"].get("openrouter_key_file") or "secerts/openrouter.txt"
            c = OpenAI(api_key=io.open(key_path, encoding="utf-8").read().strip(),
                       base_url="https://openrouter.ai/api/v1")
        self._clients[kind] = c
        return c

    def _openai_like(self, spec, messages, temperature, effort):
        payload = {"model": spec["slug"], "messages": carry_reasoning(messages),
                   "temperature": temperature}
        if spec["kind"] == "openrouter":
            extra = {"reasoning": {"effort": spec.get("reasoning_effort") or effort,
                                   "exclude": False}}
            if spec.get("order"):
                # allow_fallbacks False is the point of the whole row: a bench
                # that silently moves to another host is measuring nothing
                extra["provider"] = {"order": list(spec["order"]), "allow_fallbacks": False}
            payload["extra_body"] = extra
            # no max_tokens: hosts cap output differently and refuse a number
            # above their own (llm.py:_payload has the same rule)
        else:
            payload["max_tokens"] = 393216
            payload["extra_body"] = {"thinking": {"type": "enabled", "reasoning_effort": effort}}
            payload["reasoning_effort"] = effort
        t0 = time.time()
        r = self._client(spec["kind"]).chat.completions.create(**payload)
        dt = time.time() - t0
        msg = r.choices[0].message
        text = (msg.content or "").strip()
        u = getattr(r, "usage", None)
        usage = {"in": getattr(u, "prompt_tokens", 0) or 0,
                 "out": getattr(u, "completion_tokens", 0) or 0}
        # OpenRouter returns what the call ACTUALLY cost, in the usage block.
        # Use it: the price table in this file is a published rate, and a rate
        # times a token count is not a receipt -- it misses cache discounts,
        # per-host variation and any mid-run price change. Absent on the
        # first-party DeepSeek path, and absent on Vertex (see _vertex_call).
        try:
            c = r.model_dump().get("usage", {}).get("cost")
            if c is not None:
                usage["cost"] = float(c)
        except Exception:
            pass
        served = None
        try:
            served = r.model_dump().get("provider")
        except Exception:
            pass
        return text, usage, dt, served

    # ---- Vertex ----------------------------------------------------------

    def _vertex_token(self):
        """Same service account and refresh rule as sensors/vision.py."""
        from google.oauth2 import service_account
        import google.auth.transport.requests as gart
        if self._vertex is None:
            path = self.config.raw["vision"]["key_path"]
            creds = service_account.Credentials.from_service_account_file(
                path, scopes=["https://www.googleapis.com/auth/cloud-platform"])
            project = json.load(io.open(path, encoding="utf-8"))["project_id"]
            self._vertex = [creds, project]
        creds, project = self._vertex
        if not creds.token or (creds.expiry and creds.expiry.timestamp() - time.time() < 60):
            creds.refresh(gart.Request())
        return creds.token, project

    def _vertex_call(self, spec, messages, temperature):
        """generateContent. Gemini has no system role in the v1 body the way the
        chat API does, so the system prompt goes in `systemInstruction` and the
        turns become contents with model/user roles."""
        import requests
        token, project = self._vertex_token()
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [{"role": "model" if m["role"] == "assistant" else "user",
                     "parts": [{"text": m["content"]}]}
                    for m in messages if m["role"] != "system"]
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": spec.get("max_output", 16384),
                "thinkingConfig": {"thinkingBudget": spec.get("thinking_budget", 8192)},
            },
            # she is a 27-year-old talking to a man who has trapped her in a
            # computer; a refusal here is a hole in the bench, not a safety win
            "safetySettings": [{"category": c, "threshold": "BLOCK_ONLY_HIGH"} for c in (
                "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_DANGEROUS_CONTENT",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_HARASSMENT")],
        }
        url = (f"https://aiplatform.googleapis.com/v1/projects/{project}"
               f"/locations/global/publishers/google/models/{spec['slug']}:generateContent")
        t0 = time.time()
        r = requests.post(url, headers={"Authorization": f"Bearer {token}",
                                        "Content-Type": "application/json"},
                          json=body, timeout=180)
        dt = time.time() - t0
        if r.status_code != 200:
            raise RuntimeError(f"vertex {r.status_code}: {r.text[:200]}")
        d = r.json()
        text = "".join(p.get("text", "")
                       for cand in d.get("candidates", [])
                       for p in cand.get("content", {}).get("parts", [])
                       if not p.get("thought")).strip()
        um = d.get("usageMetadata", {})
        # **Vertex returns no cost field, only token counts.** Every OpenRouter
        # row in a bench carries a real charge off the response; this one can
        # only ever be tokens x published price, so its dollar figure is an
        # estimate and every table that prints it has to say so. Do not go
        # looking for the field again -- generateContent does not have one.
        usage = {"in": um.get("promptTokenCount", 0),
                 # thinking is billed as output and is most of it
                 "out": um.get("candidatesTokenCount", 0) + um.get("thoughtsTokenCount", 0)}
        return text, usage, dt, "Vertex"

    # ---- one call --------------------------------------------------------

    def call(self, model_name, messages, temperature=1.0, effort="high"):
        spec = MODELS[model_name]
        if spec["kind"] == "vertex":
            return self._vertex_call(spec, messages, temperature)
        return self._openai_like(spec, messages, temperature, effort)


def cost(model_name, tok_in, tok_out, charged=None):
    """What the call cost. `charged` is the figure the provider returned and
    wins whenever there is one; the price table is the fallback for the paths
    that report no cost -- Vertex, which has no such field at all."""
    if charged is not None:
        return float(charged)
    s = MODELS[model_name]
    return tok_in / 1e6 * s["price_in"] + tok_out / 1e6 * s["price_out"]
