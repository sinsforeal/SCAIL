# -*- coding: utf-8 -*-
"""What a call costs is on the record even when the answer never arrives, and
a burst of calls waits once so the calls behind the first can read its cached
prefix.

    python tools/provider_test.py      # in smoke; no network, no money, no save

Nothing here reaches a host: the API client is replaced with one that hands
back a scripted stream. Two behaviours are checked.

A stream that is abandoned used to leave nothing behind. On 2026-09-07 at
16:13:56 a cast-beat call streamed for its full ten-minute ceiling, produced
13,235 chunks and no words, was retried inside the same call and answered;
only the retry left a row in `llm_calls.jsonl`, so ten minutes of a paid
model were invisible to the spend ledger and to `/provider`.

And at the day boundary about fifteen calls of one role go out back to back,
each inside the window in which the entry the one before wrote is not
readable yet, so every one of them was billed at the uncached rate. The gate
waits out that window ONCE per burst.
"""
import io
import json
import os
import sys
import tempfile
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

import logger  # noqa: E402
import llm as llm_mod  # noqa: E402

fails = []


def check(ok, what, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what + (("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(what)
    return ok


API = {
    "provider": "fake", "max_retries": 3, "stream": True, "empty_retries": 1,
    "long_answer_warn": 100000, "cache_settle_seconds": 15, "cache_burst_hold": True,
    "request_timeout_seconds": 1, "stream_stall_seconds": 30,
    "repeat_guard_chars": 0, "repeat_guard_copies": 4, "host_fallback": True,
    "api_key": "", "base_url": "",
    # the slug is a real one, so the row the ledger reads is priced the way a
    # live row with no cost on the receipt is priced
    "providers": {"fake": {"kind": "deepseek", "base_url": "",
                           "models": {"a-model": "deepseek/deepseek-v4-flash-0731"}}},
}
MODEL = {"model": "a-model", "thinking": False, "temperature": 1.0, "effort": "low",
         "max_tokens": 4096}


def fake_config():
    """Everything `LLM` reads and nothing else."""
    cfg = types.SimpleNamespace()
    cfg.raw = {"api": dict(API)}
    cfg.api = types.SimpleNamespace(**API)
    cfg.model = lambda role: dict(MODEL)
    return cfg


class _Stream:
    def __init__(self, chunks, pause=0.0):
        self.chunks, self.pause = chunks, pause

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        for c in self.chunks:
            if self.pause:
                time.sleep(self.pause)
            yield c


class FakeClient:
    """Hands out the scripted streams in order."""

    def __init__(self, streams):
        self.streams = list(streams)
        self.sent = []
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self._create))

    def _create(self, **req):
        self.sent.append(req)
        return self.streams.pop(0)


def _thinking_chunk():
    return {"choices": [{"delta": {"reasoning": "考え" * 20}}], "provider": "a host"}


def _answer(text):
    return [{"choices": [{"delta": {"content": text}}], "provider": "a host"},
            {"choices": [{"delta": {}, "finish_reason": "stop"}],
             "usage": {"prompt_tokens": 4000, "completion_tokens": 12,
                       "prompt_tokens_details": {"cached_tokens": 0}},
             "provider": "a host"}]


def abandoned_checks(tmp):
    print("\nA STREAM THAT RAN TO ITS CEILING AND WROTE NOTHING")
    logger._llm_log = os.path.join(tmp, "llm_calls.jsonl")
    runaway = _Stream([_thinking_chunk() for _ in range(200)], pause=0.02)
    client = FakeClient([runaway, _Stream(_answer("the answer, second time round"))])
    llm = llm_mod.LLM(fake_config())
    llm._clients["fake"] = client
    messages = [{"role": "system", "content": "a system prompt"},
                {"role": "user", "content": "write the beat"}]
    got = llm._call_on("fake", "cast_beat", dict(MODEL), messages, None)
    check(got == "the answer, second time round", "the retry inside the call answered", str(got))
    with io.open(logger._llm_log, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    check(len(rows) == 2, "two rows on the record, not one", f"{len(rows)} row(s)")
    if len(rows) != 2:
        return
    first, second = rows
    check(first.get("finish") == "abandoned", "the first says the stream was abandoned",
          str(first.get("finish")))
    check("TimeoutError" in str(first.get("abandoned_reason")), "and why",
          str(first.get("abandoned_reason"))[:80])
    check(int(first.get("chunks") or 0) > 0, "and how many chunks it had written",
          str(first.get("chunks")))
    check(first.get("seconds", 0) > 0, "and how long it ran", str(first.get("seconds")))
    check(bool(first.get("estimated")), "the tokens are marked estimated, the receipt gave none")
    check(int((first.get("usage") or {}).get("prompt_tokens") or 0) > 0,
          "and there is a prompt-token figure for the ledger to price",
          str((first.get("usage") or {}).get("prompt_tokens")))
    check(second.get("finish") == "stop", "the second row is the answer, as before",
          str(second.get("finish")))
    check(llm.abandoned == 1, "and /provider counts it", str(llm.abandoned))

    from tools import llmstats
    usd, how = llmstats._cost(first, first.get("usage") or {})
    check(usd > 0 and how == "rates", "the spend ledger prices it", f"${usd:.6f} by {how}")


def burst_checks():
    print("\nTHE FIRST CALL OF A BURST GOES OUT ALONE")
    llm = llm_mod.LLM(fake_config())
    payload = {"messages": [{"role": "system", "content": "x" * 40000},
                            {"role": "user", "content": "one beat"}]}
    other = {"messages": [{"role": "system", "content": "y" * 40000},
                          {"role": "user", "content": "one beat"}]}
    small = {"messages": [{"role": "system", "content": "a probe"},
                          {"role": "user", "content": "ping"}]}
    slept = []
    was = llm_mod.time.sleep
    llm_mod.time.sleep = lambda s: slept.append(s)
    try:
        check(llm._hold_for_burst("cast_beat", payload) == 0.0,
              "the first call of the day waits for nothing")
        llm._note_burst("cast_beat", payload, 44000, 0)          # came back cold
        held = llm._hold_for_burst("cast_beat", payload)
        check(14.0 < held <= 15.0, "the second waits out what is left of the settle window",
              f"{held:.1f}s")
        check(llm._hold_for_burst("cast_beat", payload) == 0.0,
              "the third does not wait: one wait pays for the whole burst")
        llm._note_burst("cast_beat", payload, 44000, 0)          # still cold
        check(llm._hold_for_burst("cast_beat", payload) == 0.0,
              "and a burst whose host does not cache still pays only the one")
        check(llm.burst_holds == 1, "one hold, whatever the burst's length",
              str(llm.burst_holds))

        llm._burst["cast_beat"]["finish"] -= 60                  # a minute of quiet
        llm._note_burst("cast_beat", payload, 44000, 0)
        check(llm._hold_for_burst("cast_beat", payload) > 0,
              "a gap longer than the window ends the burst, and the next one holds again")

        llm._burst.clear()
        llm._note_burst("cast_beat", payload, 44000, 40000)      # came back warm
        check(llm._hold_for_burst("cast_beat", payload) == 0.0,
              "nothing is held behind a call that was already warm")

        llm._burst.clear()
        llm._note_burst("cast_beat", payload, 44000, 0)
        check(llm._hold_for_burst("cast_beat", other) == 0.0,
              "nor behind a call whose system prompt was different bytes")

        llm._burst.clear()
        llm._note_burst("probe", small, 40, 0)
        check(llm._hold_for_burst("probe", small) == 0.0,
              "nor for a prompt too small to be cached at all")

        llm2 = llm_mod.LLM(fake_config())
        llm2.config.api.cache_burst_hold = False
        llm2._note_burst("cast_beat", payload, 44000, 0)
        check(llm2._hold_for_burst("cast_beat", payload) == 0.0,
              "api.cache_burst_hold off holds nothing")
    finally:
        llm_mod.time.sleep = was


def main():
    tmp = tempfile.mkdtemp(prefix="provider_test_")
    was_log = logger._llm_log
    try:
        abandoned_checks(tmp)
        burst_checks()
    finally:
        logger._llm_log = was_log
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if fails:
        print(f"FAIL: {len(fails)} check(s): " + "; ".join(fails[:6]))
        return 1
    print("all checks passed: an abandoned stream is on the record, and a burst waits once")
    return 0


if __name__ == "__main__":
    sys.exit(main())
