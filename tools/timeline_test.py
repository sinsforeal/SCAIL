"""The day compile's retry, proven without a model call.

    python tools/timeline_test.py

The compile asks again when the narrative came back too short for the day.
The role answers with the whole JSON, not with the one field it was asked
about, and the second telling is a fresh one: on 2026-09-07 the second
character's first answer carried fourteen facts about him and the second
carried none, and the second is what was stored -- so a day of facts about
him exists nowhere in her record (HISTORY.md section 5.14).

Two stub answers go through `sim/timeline.py` with a stub store, a stub
clock and a stub client, and the stored day must carry the long narrative
from the second answer AND everything else from the first. The retry
message must also name the language the prose goes out in, for a character
who is instructed in her own language: the system half says it, but the
retry's own English paragraph is the last thing the model reads, and the
answer that lost the facts also came back with an English summary.

Nothing is fetched, nothing is paid for and no live save is opened.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sim import timeline as _timeline  # noqa: E402

FAILED = []


def check(ok, what, got=""):
    print(("  ok   " if ok else "  FAIL ") + what + (f"  -- {got}" if (got and not ok) else ""))
    if not ok:
        FAILED.append(what)


class Bag(object):
    """An attribute bag: the config sections this call reads, and nothing
    else. A real Config would drag in a save and a character sheet."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


class Clock(object):
    def now_ts(self):
        return 1788835200.0

    def hm(self, ts):
        return "12:00"


class Store(object):
    """Only what `_compile_day` asks a store for. `save_day` keeps its
    arguments, which is what the check reads."""

    def __init__(self):
        self.day = None
        self.facts = []
        self.kv = {}

    def get_schedule(self, date_str):
        return None

    def scenes_for_date(self, date_str):
        return [{"hm": "%02d:00" % (i % 24), "location": "room", "activity": "a thing",
                 "with_who": "nobody", "sensory": ""} for i in range(40)]

    def events_for_date(self, date_str):
        return []

    def state_for_date(self, date_str):
        return []

    def digests_for_date(self, date_str):
        return []

    def messages_for_date(self, date_str):
        return []

    def user_facts(self):
        return []

    def get(self, key, default=None):
        return self.kv.get(key, default)

    def set(self, key, value):
        self.kv[key] = value

    def add_user_fact(self, ts, text):
        self.facts.append(text)

    def save_day(self, date, ts, narrative, summary, user_facts):
        self.day = {"date": date, "narrative": narrative, "summary": summary,
                    "user_facts": list(user_facts)}


class LLM(object):
    """Answers a queue of `(parsed, raw)` pairs and keeps every message list
    it was handed, so the check can read what the retry actually asked."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.asked = []

    def call_json(self, role, messages):
        self.asked.append(messages)
        return self.answers.pop(0)


FIRST = {
    "narrative": "みじかい。" * 20,
    "summary": "彼は朝に一度返事をした。",
    "new_user_facts": [{"fact": "彼はMinami-keのBDフォルダを開いてS01E03を再生していた。", "weight": 2},
                       {"fact": "彼はタングステンキューブの値段と重さを調べていた。", "weight": 1}],
    "her_things": ["机の上にりんごがひとつあった。"],
    "memories": [{"text": "ノートに自分のことが書かれていた。", "weight": 4, "valence": -2}],
    "cast_updates": {}, "new_people": [], "places": [], "goals": [],
    "self_claims": [], "new_cast_facts": [], "arc_notes": [],
}

SECOND = {
    "narrative": "ながい。" * 400,
    "summary": "A quiet day of watching his machine and waiting for a reply that never came.",
    "new_user_facts": [],
    "her_things": [],
    "memories": [],
    "cast_updates": {}, "new_people": [], "places": [], "goals": [],
    "self_claims": [], "new_cast_facts": [], "arc_notes": [],
}


def config():
    """A character who is instructed in her own language, so the retry's
    language line is exercised as well as the merge."""
    return Bag(
        resident=False,
        character=Bag(name="test", program="tomoe", writes_to_him="japanese",
                      instruction_language="japanese", instructions="auto",
                      existence=Bag(with_him="chat")),
        timeline=Bag(narrative_min_chars=600, narrative_min_scenes=10, narrative_retries=1),
        showrunner=Bag(enabled=False),
        self_memory=Bag(compile_max_per_day=5),
        language=Bag(enabled=True, material_roles=("timeline",)),
        prompt_text=lambda role: "(the timeline instruction)",
    )


def main():
    print("the merge, on its own")
    merged, from_second = _timeline.merge_retry(FIRST, SECOND, "narrative")
    check(merged["narrative"] == SECOND["narrative"], "the narrative is the second answer's")
    check(len(merged["new_user_facts"]) == 2, "the facts about him are the first answer's",
          json.dumps(merged["new_user_facts"], ensure_ascii=False))
    check(merged["summary"] == FIRST["summary"],
          "the summary is the first answer's, both being non-empty", merged["summary"])
    check(merged["her_things"] == FIRST["her_things"], "her own things survive")
    check(merged["memories"] == FIRST["memories"], "her memories of the day survive")
    check(from_second == ["narrative"], "the log names the narrative and nothing else",
          str(from_second))

    print("a first answer that did not parse")
    merged2, from2 = _timeline.merge_retry(None, SECOND, "narrative")
    check(merged2["narrative"] == SECOND["narrative"] and merged2["summary"] == SECOND["summary"],
          "everything comes from the second answer when there is no first")
    check(set(from2) >= {"narrative", "summary"}, "and the log says so", str(from2))

    print("the whole compile, with the retry")
    store, llm, cfg = Store(), LLM([(dict(FIRST), json.dumps(FIRST, ensure_ascii=False)),
                                    (dict(SECOND), json.dumps(SECOND, ensure_ascii=False))]), config()
    out = _timeline._compile_day(cfg, llm, store, Clock(), "2026-09-07")
    check(len(llm.asked) == 2, "the compile asked again", f"{len(llm.asked)} call(s)")
    check(store.day is not None, "a day was stored")
    if store.day:
        check(store.day["narrative"] == SECOND["narrative"],
              "the stored narrative is the long one")
        check(len(store.day["user_facts"]) == 2,
              "the stored day carries the facts the retry did not ask about",
              json.dumps(store.day["user_facts"], ensure_ascii=False))
        check("Minami-ke" in " ".join(store.day["user_facts"]),
              "the watch he was asked about is one of them")
        check(store.day["summary"] == FIRST["summary"],
              "the summary is hers, not the retry's English one", store.day["summary"])
    check(len(store.facts) == 2, "both facts reached the store", str(len(store.facts)))
    check(isinstance(out, dict) and out.get("narrative") == SECOND["narrative"],
          "and the merged answer is what the caller is handed")

    if len(llm.asked) == 2:
        ask = llm.asked[1][-1]["content"]
        check("LANGUAGE OF WHAT YOU WRITE HERE" in ask,
              "the retry names the language its prose goes out in", ask[-120:])
        check("Japanese" in ask, "and names her language")

    print("a character instructed in English gets no language line")
    cfg2 = config()
    cfg2.character.instruction_language = "english"
    store2 = Store()
    llm2 = LLM([(dict(FIRST), json.dumps(FIRST, ensure_ascii=False)),
                (dict(SECOND), json.dumps(SECOND, ensure_ascii=False))])
    _timeline._compile_day(cfg2, llm2, store2, Clock(), "2026-09-07")
    if len(llm2.asked) == 2:
        check("LANGUAGE OF WHAT YOU WRITE HERE" not in llm2.asked[1][-1]["content"],
              "no language line for a character with only one language")

    print()
    if FAILED:
        print("%d check(s) failed:" % len(FAILED))
        for f in FAILED:
            print("  - " + f)
        return 1
    print("every check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
