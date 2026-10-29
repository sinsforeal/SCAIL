"""Request policy: one thinking policy, token floor and language pin for both arms.

Pure functions, no I/O, so the unit tests can hit them directly.
Rules come from bzombie/CONTRACT.md (Gateway) and the precheck notebook.
"""
import copy

DEEPSEEK = "deepseek-v4.1-flash-1017"
GLM = "glm-5.3"
MODELS = (DEEPSEEK, GLM)

PINS = {
    "ja": "キャラクターとしての文章はすべて自然な日本語で書く。",
    "en": "Write everything the character says in natural English.",
}

MAX_TOKENS_FLOOR = 1024


def _pin_text(content, pin, where):
    """Add the pin to a message content (str or list of parts)."""
    if isinstance(content, str):
        return pin + "\n\n" + content if where == "head" else content + "\n\n" + pin
    if isinstance(content, list):
        parts = list(content)
        part = {"type": "text", "text": pin}
        if where == "head":
            return [part] + parts
        return parts + [part]
    if content is None:
        return pin
    return content


def apply_pin(messages, lang):
    pin = PINS.get(lang)
    if not pin or not isinstance(messages, list):
        return messages
    msgs = [dict(m) if isinstance(m, dict) else m for m in messages]
    # head: first system message, or a new one in front
    first_sys = next((i for i, m in enumerate(msgs)
                      if isinstance(m, dict) and m.get("role") in ("system", "developer")), None)
    if first_sys is None:
        msgs.insert(0, {"role": "system", "content": pin})
    else:
        msgs[first_sys]["content"] = _pin_text(msgs[first_sys].get("content"), pin, "head")
    # tail: last user message
    last_user = None
    for i in range(len(msgs) - 1, -1, -1):
        if isinstance(msgs[i], dict) and msgs[i].get("role") == "user":
            last_user = i
            break
    if last_user is not None:
        msgs[last_user]["content"] = _pin_text(msgs[last_user].get("content"), pin, "tail")
    return msgs


FOLD_VARIANT = "fold_prefill_tail"
FOLD_LINE = ("Write only the character's next message, continuing from the text of the last line above. "
             "No other characters' turns, no commentary.")
FOLD_TAIL_CHARS = 400
JUNK_MARKERS = ("<｜", "ds_safety", "Valid channels:")


def fold_prefill(messages):
    """Surplus starts a fresh turn after a trailing assistant message (template junk in 15 of 21
    prefill samples, tk-7gn). Drop that message and tell the model, in the last user message,
    to continue from its tail. Returns (messages, variant or None). Input is not changed.
    The reply is the message text only, same shape a first-party continuation has (no prefill echo)."""
    if not isinstance(messages, list) or len(messages) < 2:
        return messages, None
    last = messages[-1]
    if not isinstance(last, dict) or last.get("role") != "assistant" or last.get("tool_calls"):
        return messages, None
    pre = last.get("content")
    if not isinstance(pre, str) or not pre:
        return messages, None
    msgs = [dict(m) if isinstance(m, dict) else m for m in messages[:-1]]
    last_user = next((i for i in range(len(msgs) - 1, -1, -1)
                      if isinstance(msgs[i], dict) and msgs[i].get("role") == "user"), None)
    if last_user is None:
        return messages, None
    add = "\n\n" + FOLD_LINE + "\nThe text to continue ends with:\n" + pre[-FOLD_TAIL_CHARS:]
    c = msgs[last_user].get("content")
    if isinstance(c, str):
        msgs[last_user]["content"] = c + add
    elif isinstance(c, list):
        msgs[last_user]["content"] = list(c) + [{"type": "text", "text": add.lstrip("\n")}]
    else:
        return messages, None
    return msgs, FOLD_VARIANT


def detect_junk(text):
    """True if the text carries a chat-template leak. Flag only, never edits."""
    return isinstance(text, str) and any(m in text for m in JUNK_MARKERS)


def response_texts(obj):
    """Message contents of a non-stream chat response."""
    out = []
    for c in (obj or {}).get("choices") or []:
        t = (c.get("message") or {}).get("content")
        if isinstance(t, str):
            out.append(t)
    return out


def apply_policy(body, model, lang):
    """Return the body to send upstream. The caller's dict is not changed."""
    b = copy.deepcopy(body)
    b["model"] = model
    has_tools = bool(b.get("tools"))
    if model == DEEPSEEK:
        b["reasoning_effort"] = "none"
        b.pop("thinking", None)
        b.pop("frequency_penalty", None)
        b.pop("presence_penalty", None)
    elif model == GLM:
        b["reasoning_effort"] = "low"
        b.pop("thinking", None)
        b.pop("clear_thinking", None)  # top-level form behaves differently, only the kwargs form is used
        kw = dict(b.get("chat_template_kwargs") or {})
        if has_tools:
            kw.pop("clear_thinking", None)  # keep the caller's prior reasoning blocks
        else:
            kw["clear_thinking"] = True
        if kw:
            b["chat_template_kwargs"] = kw
        else:
            b.pop("chat_template_kwargs", None)
    for key in ("max_tokens", "max_completion_tokens"):
        v = b.get(key)
        if isinstance(v, (int, float)) and v < MAX_TOKENS_FLOOR:
            b[key] = MAX_TOKENS_FLOOR
    if "messages" in b:
        b["messages"] = apply_pin(b["messages"], lang)
    if b.get("stream"):
        so = dict(b.get("stream_options") or {})
        so["include_usage"] = True
        b["stream_options"] = so
    return b
