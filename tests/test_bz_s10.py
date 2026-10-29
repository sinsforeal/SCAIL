"""bz/s10 (tk-7wb bubble budget, tk-wnp repetition check): persona/s10.py and its hooks in Persona.
Real lines come from var/bzombie/runs/cl2_s_tomoe and cl2_s_momoka transcripts (read-only; skipped when absent).
Run: python -m unittest tests.test_bz_s10 -v"""

import json
import os
import sys
import unittest
from types import SimpleNamespace as NS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from persona import s10  # noqa: E402
from persona.persona import Persona  # noqa: E402

RUNS = os.environ.get("BZ_RUNS_DIR") or "F:/REPS2/SCAILV4/var/bzombie/runs"


def load(run):
    """{i: (who, text)} for the him/her rows of a run's transcript."""
    p = os.path.join(RUNS, run, "transcript.jsonl")
    if not os.path.exists(p):
        raise unittest.SkipTest(f"{p} not found")
    out = {}
    for line in open(p, encoding="utf-8"):
        d = json.loads(line)
        if d.get("who") in ("him", "her"):
            out[d["i"]] = (d["who"], d["text"])
    return out


def thread(rows, upto):
    """History as (who, text) up to and including row `upto`."""
    return [rows[i] for i in sorted(rows) if i <= upto]


def only(*kinds):
    return {"repeat_kinds": list(kinds)}


# ------------------------------------------------------------------ budget

class BudgetMapping(unittest.TestCase):
    ON = {"budget": True}

    def b(self, text, **kw):
        return s10.budget_for(text, self.ON, **kw)

    def test_off_and_empty(self):
        self.assertIsNone(s10.budget_for("hello there you", {}))
        self.assertIsNone(s10.budget_for("hello there you", {"budget": False}))
        self.assertIsNone(self.b(""))
        self.assertIsNone(self.b("   "))

    def test_english_words(self):
        self.assertEqual(self.b("hey"), 1)
        self.assertEqual(self.b("ok go"), 1)
        self.assertEqual(self.b("how was the lecture today"), 2)
        self.assertEqual(self.b(" ".join(["word"] * 20)), 3)
        self.assertEqual(self.b(" ".join(["word"] * 50)), 4)
        self.assertEqual(self.b(" ".join(["word"] * 200)), 5)

    def test_japanese_characters(self):
        self.assertEqual(self.b("おやすみ"), 1)
        self.assertEqual(self.b("今日は簡単にパスタの予定です"), 2)
        self.assertEqual(self.b("うん、作ります。今日は簡単にパスタの予定です。百花も食べられたらいいのに、なんて。"), 3)

    def test_language_is_read_from_his_message(self):
        self.assertEqual(s10.size_of("ねむい")[0], "ja")
        self.assertEqual(s10.size_of("so sleepy")[0], "en")
        self.assertEqual(s10.size_of("so sleepy"), ("en", 2))

    def test_state_only_lowers(self):
        long_msg = " ".join(["word"] * 20)
        self.assertEqual(self.b(long_msg), 3)
        self.assertEqual(self.b(long_msg, energy=10), 2)
        self.assertEqual(self.b(long_msg, upset=60), 2)
        self.assertEqual(self.b(long_msg, energy=10, upset=60), 2)   # one delta, not two
        self.assertEqual(self.b(long_msg, energy=80, upset=5), 3)
        self.assertEqual(self.b("hey", energy=10), 1)                # floor

    def test_table_comes_from_config(self):
        cfg = {"budget": True, "budget_table_en": [[100, 2]], "budget_over": 3, "budget_min": 2}
        self.assertEqual(s10.budget_for("hey", cfg), 2)
        self.assertEqual(s10.budget_for("hey", cfg, energy=0), 2)    # min 2
        self.assertEqual(s10.budget_for(" ".join(["w"] * 101), cfg), 3)

    def test_real_messages_tomoe(self):
        rows = load("cl2_s_tomoe")
        long_him = rows[0][1]           # "evening. just finished cooking dinner, ..."
        short_him = rows[87][1]         # "ok go. slide 14 and me. bye"
        self.assertEqual(self.b(short_him), 2)
        self.assertGreater(self.b(long_him), self.b(short_him))

    def test_real_messages_momoka(self):
        rows = load("cl2_s_momoka")
        self.assertEqual(self.b(rows[39][1]), 1)       # おかえり。 (him)
        self.assertGreaterEqual(self.b(rows[69][1]), 3)

    def test_line_states_the_number(self):
        en = s10.budget_line(2, "how was the lecture today", False)
        self.assertIn("at most 2 bubbles", en)
        self.assertIn("BLANK LINE", en)
        self.assertIn("at most 1 bubble ", s10.budget_line(1, "hey", False))
        ja = s10.budget_line(2, "おやすみ", True)
        self.assertIn("多くても2つ", ja)


class MergeEnforcement(unittest.TestCase):
    def test_extra_lines_fold_into_last(self):
        parts = ["a one", "b two", "c three", "d four", "e five"]
        got = s10.merge_to_budget(parts, 3)
        self.assertEqual(len(got), 3)
        self.assertEqual(got[:2], ["a one", "b two"])
        self.assertEqual(got[2], "c three d four e five")

    def test_nothing_dropped(self):
        parts = [f"line {i}" for i in range(6)]
        got = s10.merge_to_budget(parts, 2)
        self.assertEqual(" ".join(got).split(), " ".join(parts).split())

    def test_within_budget_untouched(self):
        self.assertEqual(s10.merge_to_budget(["a", "b"], 2), ["a", "b"])
        self.assertEqual(s10.merge_to_budget(["a", "b"], 5), ["a", "b"])
        self.assertEqual(s10.merge_to_budget([], 2), [])
        self.assertEqual(s10.merge_to_budget(["a", "b"], None), ["a", "b"])

    def test_one_bubble_budget(self):
        self.assertEqual(s10.merge_to_budget(["ok", "fine", "go"], 1), ["ok fine go"])

    def test_japanese_joins_without_space(self):
        self.assertEqual(s10.merge_to_budget(["うん。", "そうだね。", "おやすみ。"], 2, ja=True), ["うん。", "そうだね。おやすみ。"])

    def test_one_word_back_to_one_word_is_kept(self):
        self.assertEqual(s10.merge_to_budget(["ok"], 1), ["ok"])


class FakeStore:
    def __init__(self, msgs=None):
        self.d = {}
        self.msgs = msgs or []

    def set(self, k, v):
        self.d[k] = v

    def get(self, k, default=None):
        return self.d.get(k, default)

    def recent_messages(self, n):
        return self.msgs[-n:]


def persona_stub(store=None, **s10cfg):
    p = object.__new__(Persona)
    p.config = NS(delivery=NS(split_on_blank_lines=True, no_repeat_recent=12), bz_s10=dict(s10cfg),
                  character=NS(writes_to_him="english"))
    p.store = store or FakeStore()
    p.last_all_repeats = False
    p._search_asked = ""
    p._resolve_shares = lambda parts: parts
    p.state = NS(gauges={"energy": 70})
    p.shape_engine = NS(upset=lambda: 0)
    return p


class SplitIntegration(unittest.TestCase):
    DRAFT = "ok first\n\nsecond thing here\n\nthird bit\n\nfourth\n\nfifth one"

    def test_budget_merges_at_split(self):
        p = persona_stub(budget=True)
        p._s10_set_budget([{"text": "hey"}])
        self.assertEqual(p._s10_budget, 1)
        out = p._split(self.DRAFT)
        self.assertEqual(out, ["ok first second thing here third bit fourth fifth one"])

    def test_budget_two(self):
        p = persona_stub(budget=True)
        p._s10_set_budget([{"text": "how was the lecture today"}])
        self.assertEqual(p._s10_budget, 2)
        out = p._split(self.DRAFT)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0], "ok first")

    def test_off_leaves_split_alone(self):
        p = persona_stub(budget=False)
        p._s10_set_budget([{"text": "hey"}])
        self.assertIsNone(p._s10_budget)
        self.assertEqual(len(p._split(self.DRAFT)), 5)

    def test_no_budget_when_she_writes_first(self):
        p = persona_stub(budget=True)
        p._s10_set_budget([])
        self.assertIsNone(p._s10_budget)

    def test_missing_section_is_off(self):
        p = persona_stub()
        p.config = NS(delivery=p.config.delivery)
        p._s10_set_budget([{"text": "hey"}])
        self.assertIsNone(p._s10_budget)


# ----------------------------------------------------------------- repetition

class RepetitionTomoe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load("cl2_s_tomoe")

    def kinds(self, draft, upto, *kinds):
        found = s10.check(draft, thread(self.rows, upto), only(*kinds))
        return [k for k, _n in found]

    def test_near_duplicate_line(self):
        # her line 6: "ok you're dodging. i asked what you cooked and you just said domestic god"
        d = ["ok you're dodging, i asked what you cooked and you just said domestic god lol"]
        self.assertEqual(self.kinds(d, 11, "near_dup"), ["near_dup"])

    def test_near_duplicate_clean_and_short(self):
        self.assertEqual(self.kinds(["sauce was good, a bit too much garlic"], 11, "near_dup"), [])
        self.assertEqual(self.kinds(["ok go"], 95, "near_dup"), [])           # under min chars-ish, different anyway

    def test_recycled_phrase(self):
        # her line 82: "go on then. lights on, door shut, no messages during three"
        d = ["fine. lights on, door shut, and i will stay away"]
        self.assertEqual(self.kinds(d, 83, "phrase"), ["phrase"])

    def test_phrase_in_his_message_is_not_a_repeat(self):
        d = ["lights on, door shut. yes"]
        # he has just said it, so repeating his words is not her recycling (her row 82 had it too)
        hist = thread(self.rows, 83) + [("him", "lights on door shut, yes")]
        self.assertEqual(s10.check(d, hist, only("phrase")), [])

    def test_repeated_opener(self):
        # her line 82 opens "go on then"
        self.assertEqual(self.kinds(["go on then. take your time"], 88, "opener"), ["opener"])
        self.assertEqual(self.kinds(["not much to say yet. take your time"], 88, "opener"), [])

    def test_two_token_opener_needs_two_uses(self):
        # "ok go" opens her lines 87 and 95
        self.assertEqual(self.kinds(["ok go. now"], 88, "opener"), [])
        self.assertEqual(self.kinds(["ok go. now"], 96, "opener"), ["opener"])

    def test_repeated_signoff(self):
        # her line 82 ends "no messages during three"
        self.assertEqual(self.kinds(["fine, you win. no messages during three"], 83, "signoff"), ["signoff"])
        self.assertEqual(self.kinds(["fine, you win. bye"], 83, "signoff"), [])

    def test_reasked_question(self):
        # rows 2 to 11 are hers with nothing of his between: "what did you actually cook" is still open
        d = ["ok but what did you actually cook"]
        self.assertEqual(self.kinds(d, 11, "reask"), ["reask"])

    def test_answered_question_is_not_reasked(self):
        # he answered at row 13, so the question is closed
        d = ["ok but what did you actually cook"]
        self.assertEqual(self.kinds(d, 14, "reask"), [])

    def test_unrelated_question_is_fine(self):
        self.assertEqual(self.kinds(["where is kaito's sock now"], 11, "reask"), [])

    def test_echo_opener_english(self):
        his = self.rows[13][1]       # "... chicken and rice with some kinda garlic sauce ..."
        hist = thread(self.rows, 2) + [("him", his)]
        found = s10.check(["garlic sauce, nice. was it good"], hist, only("echo"))
        self.assertEqual([k for k, _n in found], ["echo"])
        found = s10.check(["improvised. so you cant tell me the recipe"], hist, only("echo"))
        self.assertEqual(found, [])

    def test_all_kinds_clean_draft(self):
        d = ["sauce was actually good, bit too much garlic but i'll live"]
        self.assertEqual(s10.check(d, thread(self.rows, 2) + [("him", "was the sauce good")], {}), [])


class RepetitionMomoka(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load("cl2_s_momoka")

    def echo(self, draft, his_row):
        hist = [("her", "おはよ。"), ("him", self.rows[his_row][1])]
        return [k for k, _n in s10.check([draft], hist, only("echo"))]

    def test_pasta_echo(self):
        self.assertEqual(self.echo("ぱすた、いいな。", 50), ["echo"])

    def test_quiet_music_echo(self):
        self.assertEqual(self.echo("しずかな音楽、いいね。", 69), ["echo"])

    def test_farm_game_echo(self):
        self.assertEqual(self.echo("農場のやつ、いいね。", 74), ["echo"])

    def test_answer_that_is_not_an_echo(self):
        self.assertEqual(self.echo("おなか、ほんとにしちゃった。", 74), [])
        self.assertEqual(self.echo("ゲーム、何するの。", 69), [])

    def test_near_duplicate_japanese(self):
        sent = [self.rows[i] for i in (14, 15, 16, 17, 18)]
        hist = [("him", "おはよ")] + [("her", t) for _w, t in sent] + [("him", "ひま")]
        found = s10.check(["百花の予定は、それだけ。"], hist, only("near_dup"))
        self.assertEqual([k for k, _n in found], ["near_dup"])
        self.assertEqual(s10.check(["今日はね、少しだけ散歩した。"], hist, only("near_dup")), [])

    def test_repeated_japanese_opener(self):
        # her row 18 is "待ってるから。"
        hist = [("her", self.rows[18][1]), ("him", "うん")]
        self.assertEqual([k for k, _n in s10.check(["待ってるから、またね。"], hist, only("opener"))], ["opener"])
        self.assertEqual(s10.check(["またね、待ってるから。"], hist, only("opener")), [])


# ----------------------------------------------------------------- revise once

class RevisePath(unittest.TestCase):
    def run_pass(self, first, redraft, history, **cfg):
        c = {"repeat_check": True}
        c.update(cfg)
        msgs = [{"role": "assistant" if w == "her" else "user", "text": t} for w, t in history]
        p = persona_stub(FakeStore(msgs), **c)
        calls = []

        def _draft(situation):
            calls.append(situation)
            return redraft, ""
        p._draft = _draft
        p._s10_redrafted = False
        bubbles, voice = p._s10_repeat_pass(first, "", "SIT", [{"text": history[-1][1]}] if history[-1][0] == "him" else [])
        return bubbles, calls

    def test_hit_redrafts_exactly_once_with_a_note(self):
        rows = load("cl2_s_tomoe")
        hist = thread(rows, 11)
        first = ["ok but what did you actually cook"]
        bubbles, calls = self.run_pass(first, ["the dinner. you owe me the dinner, not a vibe"], hist)
        self.assertEqual(len(calls), 1)
        self.assertIn("repeating yourself", calls[0])
        self.assertIn("did you actually cook", calls[0])
        self.assertTrue(calls[0].startswith("SIT"))
        self.assertEqual(bubbles, ["the dinner. you owe me the dinner, not a vibe"])

    def test_second_hit_is_not_redrafted_again(self):
        rows = load("cl2_s_tomoe")
        hist = thread(rows, 11)
        again = ["so what did you actually cook then"]
        bubbles, calls = self.run_pass(["ok but what did you actually cook"], again, hist)
        self.assertEqual(len(calls), 1)                       # one revise, never a second
        self.assertEqual(bubbles, again)                      # the redraft stands as written

    def test_clean_draft_makes_no_call(self):
        rows = load("cl2_s_tomoe")
        bubbles, calls = self.run_pass(["laundry room door is real, i believe you"], ["x"], thread(rows, 11))
        self.assertEqual(calls, [])
        self.assertEqual(bubbles, ["laundry room door is real, i believe you"])

    def test_off_makes_no_call(self):
        rows = load("cl2_s_tomoe")
        bubbles, calls = self.run_pass(["ok but what did you actually cook"], ["x"], thread(rows, 11), repeat_check=False)
        self.assertEqual(calls, [])

    def test_editor_already_redrafted_means_no_second(self):
        rows = load("cl2_s_tomoe")
        c = {"repeat_check": True}
        p = persona_stub(FakeStore([{"role": "assistant" if w == "her" else "user", "text": t} for w, t in thread(rows, 11)]), **c)
        calls = []
        p._draft = lambda s: (calls.append(s) or (["x"], ""))
        p._s10_redrafted = True
        bubbles, _v = p._s10_repeat_pass(["ok but what did you actually cook"], "", "SIT", [])
        self.assertEqual(calls, [])
        self.assertEqual(bubbles, ["ok but what did you actually cook"])

    def test_empty_redraft_keeps_the_first(self):
        rows = load("cl2_s_tomoe")
        first = ["ok but what did you actually cook"]
        bubbles, calls = self.run_pass(first, [], thread(rows, 11))
        self.assertEqual(len(calls), 1)
        self.assertEqual(bubbles, first)

    def test_note_in_japanese_room(self):
        f = [("echo", "you open by repeating his words")]
        self.assertIn("繰り返し", s10.revise_note(f, True))
        self.assertIn("repeating yourself", s10.revise_note(f, False))


class Defaults(unittest.TestCase):
    def test_config_py_defaults_off_and_make_run_on(self):
        import config
        d = config.DEFAULTS["bz_s10"]
        self.assertIs(d["budget"], False)
        self.assertIs(d["repeat_check"], False)
        self.assertEqual(set(d) - set(s10.DEFAULTS), set())
        mr = open(os.path.join(ROOT, "bzombie", "arms", "s", "make_run.py"), encoding="utf-8").read()
        self.assertIn('"budget": True, "repeat_check": True', mr)


if __name__ == "__main__":
    unittest.main()
