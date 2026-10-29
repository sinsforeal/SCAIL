"""One small OpenRouter chat client.

One provider, one call, no fallback and no retry loop hiding the truth: a
failure raises with the provider's own status and body so the operator sees
what actually happened. `requests` is required (it is already on this machine).
"""

import json
import os
import sys

import requests

try:
    from . import common
except ImportError:
    import common


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(self, cfg=None):
        self.cfg = cfg or common.load_config()
        self.api = self.cfg["llm"]

    def key(self):
        path = common.resolve(self.api["key_file"])
        if not os.path.exists(path):
            raise LLMError(f"key file not found: {path}")
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
        if not key:
            raise LLMError(f"key file is empty: {path}")
        return key

    def chat(self, messages, system=None, model=None, temperature=None, max_tokens=None):
        """Return her reply text. `messages` is [{"role","content"}, ...]."""
        api = self.api
        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend(messages)
        body = {
            "model": model or api["model"],
            "messages": payload_messages,
            "temperature": api["temperature"] if temperature is None else temperature,
        }
        cap = api.get("max_tokens") if max_tokens is None else max_tokens
        if cap:
            body["max_tokens"] = cap
        url = api["base_url"].rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": api.get("referer", ""),
            "X-OpenRouter-Title": api.get("title", ""),
        }
        try:
            r = requests.post(url, json=body, headers=headers, timeout=float(api["timeout_seconds"]))
        except requests.RequestException as e:
            raise LLMError(f"request failed: {type(e).__name__}: {e}") from e
        if r.status_code != 200:
            raise LLMError(f"http {r.status_code} from {url}: {r.text[:600]}")
        try:
            data = r.json()
        except ValueError:
            raise LLMError(f"non-JSON response from {url}: {r.text[:600]}")
        choices = data.get("choices") or []
        if not choices:
            err = data.get("error") or data.get("detail") or data
            raise LLMError(f"no choices in response: {json.dumps(err, ensure_ascii=False)[:600]}")
        content = (choices[0].get("message") or {}).get("content") or ""
        content = content.strip()
        if not content:
            raise LLMError(f"empty reply (finish_reason={choices[0].get('finish_reason')!r})")
        return content


def selftest():
    """One real call, her voice, printed. No fake answer if the call fails."""
    cfg = common.load_config()
    llm = LLM(cfg)
    system = common.system_prompt(cfg)
    print(f"[llm] provider=openrouter model={llm.api['model']} key_file={llm.api['key_file']}")
    try:
        reply = llm.chat([{"role": "user", "content": "百花、こんにちは。"}], system=system)
    except LLMError as e:
        print(f"[llm] FAILED: {e}", file=sys.stderr)
        return 1
    print("[llm] reply:")
    print(reply)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    print("usage: python runtime/llm.py --selftest")
