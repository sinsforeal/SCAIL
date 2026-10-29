"""Two speech guides, the same woman, the same situations: which one is her.

The question this answers is narrow on purpose. `tools/voice_verify.py` asks
whether her generated markers sit where the corpus says they should, which is
a screen and cannot see stance. `tools/character_test.py` asks whether a sheet
loads and decays correctly, which is machinery. Neither can tell you that a
character who says わかんない at five times the corpus rate is using it to stop
talking where the tape uses it to start.

So this runs the real reply role against fixed situations with ONE variable --
the speech guide -- and prints the output for a person to read. It scores
nothing. The signal table it prints is evidence for a reading, not a verdict,
and the file says so wherever it prints a number.

THREE THINGS IT HOLDS STILL, because each of them has confounded this
comparison before:

  1. **Everything except the speech guide.** Same bible, same scene, same
     history, same closing instructions, same model, same temperature. The
     closing block is BUILT BY `persona.closing_instruction`, the same function
     the live renderer calls, with the flags her config renders
     (`shape.tell_length` false, `embodied` true), so the arms are compared
     inside the machinery she really runs in rather than in a clean room that
     flatters both -- and so this file cannot drift away from what she reads.
     `--instructions` moves that block to another arm, which is the one thing
     it is for; with it unset the block is whatever her config says.
  2. **Length.** A candidate guide that says "be longer" wins on a variable the
     tape cannot adjudicate: the corpus is 47 hours of broadcast and holds no
     observation of her writing anything. Both guides must carry the same
     length budget or the run is rigged, and `--check-bias` diffs them for it.
  3. **The medium.** The corpus is a radio programme with a format, four staff
     behind glass and a hundred thousand listeners; the target is one stranger
     in a text box. Holding the floor for thirty cues is an affordance of the
     first and its absence in the second is not a fault. So scenarios carry a
     `set`: `chat` is the target and is read on stance only, `broadcast` is the
     fairness control -- the situation the tape actually contains, where a
     guide that cannot produce her has no excuse.

    python tools/voicelab.py                          # both arms, both sets, 2 samples
    python tools/voicelab.py --set chat --samples 3
    python tools/voicelab.py --only cold-open,compliment
    python tools/voicelab.py --arms control           # one guide
    python tools/voicelab.py --check-bias             # diff the guides, no model call
    python tools/voicelab.py --instructions in_english    # the closing block in the other arm
    python tools/voicelab.py --dry                    # print one built prompt and stop
"""

import argparse
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import datetime
import glob
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# This console is cp932 and everything printed here is Japanese with em dashes
# in it. Without this the tool dies on its own first line of output.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import logger
logger.setup = lambda out_dir: None
_QUIET = [True]
logger.log = lambda m, to_console=True: (None if _QUIET[0] else print("   log:", str(m)[:160]))

from config import Config
from llm import LLM
from voicelab_models import MODELS, Caller, cost

# An arm is a bible AND a speech guide, because the two are read as one thing
# and an approach can differ in both: `voice_replica_in_text` rewrites the
# bible's speech section from the counts, so pairing its guide with the other
# bible would bench a hybrid nobody proposed.
#
# `live` is READ FROM HER CONFIG, so a run always measures the thing she is
# actually using and the name cannot go stale: it was a hardcoded path to the
# first set, and the day the replica was adopted it pointed at the wrong files.
# Every recorded run before 2026-09-02 19:24 carries arm "live" meaning the
# `writes` set; `writes` is the explicit name for that set from now on.
# `pre` is that set's guide as it stood before the last adoption, kept in
# data/retired/ so a change can be shown to have helped rather than asserted to.
_W = "prompts_yukarin/voice_as_she_writes_in_text"
_R = "prompts_yukarin/voice_replica_in_text"


def _live_arm():
    try:
        c = json.load(io.open("config_yukarin.json", encoding="utf-8"))
        return (c["models"]["persona"]["prompt"], c["character"]["style_prompt"])
    except Exception:
        return (f"{_R}/bible.md", f"{_R}/style.md")


ARMS = {
    "live":      _live_arm(),
    "writes":    (f"{_W}/bible.md", f"{_W}/style.md"),
    "pre":       (f"{_W}/bible.md", "data/retired/20260902_152107_style_adopt/style.md.before"),
    "candidate": (f"{_W}/bible.md", f"{_W}/style_candidate.md"),
    "replica":   (f"{_R}/bible.md", f"{_R}/style.md"),
}
SCENARIOS = "data/voicelab_scenarios.json"
OUT_ROOT = "data/voicelab"


# --------------------------------------------------------------------------
# the prompt, assembled the way persona.py assembles it, minus the machinery
# --------------------------------------------------------------------------

# What she knows about him. Deliberately almost nothing and IDENTICAL in every
# arm: the live picture of him grows call by call, and a fatter one in one arm
# would be a second variable. It is also true to the opening condition -- how
# much of him she has starts at zero.
HIM_FACTS = """- 名前はジョン。
- 相手のパソコンの中にいる。相手が何をしているかは、見ようと思えば見える。
- それ以外、この人については何も分かっていない。"""

# The closing block, built by the live renderer rather than copied from it.
# It used to be a copy of `persona.py:_draft` pasted in here with a comment
# saying so, which is fine until the instructions become a variable: a copy
# can only ever hold one arm of a comparison, and it drifts.
#
# `persona.closing_instruction` is called with the flags her config renders --
# writes_to_him japanese, shape.tell_length false (so no bubble rule and no
# length line), existence.embodied true -- and the arm comes from
# `sim.lang`, so `--instructions` moves it. The extra line is this harness's
# own: its scenarios want more than one message without the length machinery
# that would normally say so.
BUBBLE_NOTE = ("\n\nseparate messages are separated by a BLANK LINE.",
               "\n\nメッセージとメッセージのあいだは空行で分ける。")


def tail_chat(cfg):
    from persona.persona import closing_instruction
    from sim.lang import say
    return (closing_instruction(cfg, spillish=False, tell_length=False,
                                embodied=True, writes_ja=True)
            + say(cfg)(*BUBBLE_NOTE))


# The broadcast set needs its own closing block for the obvious reason -- she
# is not texting anybody -- and it must be as neutral about HOW she talks as
# the chat one is. It says where she is and stops. It moves with the
# instruction arm like everything else addressed to her, so a broadcast run is
# not silently held in one language while the chat run moves.
def tail_radio(cfg):
    # This block has no live counterpart -- she never broadcasts in the running
    # bot -- so "as it runs today" means "as the control bench was bought",
    # and that was the Japanese wording. Only the English arm renders English;
    # rendering it under the control too would silently re-buy every broadcast
    # answer and compare two guides under two different tails.
    import sim.lang as _lang
    en = ("you are at the microphone now, doing this part of the programme. IN JAPANESE. "
          "listening are the listeners (always a collective, never a name) and the staff behind the glass. "
          "write only the words you say: no stage directions, no explanations in brackets, no speaker names.")
    jp = ("あなたは今マイクの前にいて、番組のこの部分を喋る。IN JAPANESE. "
          "聞いているのはリスナー（常に集合で、名前ではない）と、ガラスの向こうのスタッフ。"
          "喋った言葉だけを書く。ト書き、括弧の中の説明、話者名は書かない。")
    return en if _lang.arm(cfg) == _lang.ENGLISH else jp


def build_system(cfg, arm, scene, radio=False):
    """the arm's bible + what she knows about him + the arm's speech guide.

    The order is `persona.py:_assemble`'s: the bible first, then what she
    knows, then the style file LAST, because the last thing in a system prompt
    is the thing a model weights hardest and that is where the live assembly
    puts it.
    """
    bible_path, style_path = arm
    bible = io.open(bible_path, encoding="utf-8").read().strip()
    style = io.open(style_path, encoding="utf-8").read().strip()
    where = "## 今どこにいるか\n" + scene
    known = "## この相手について分かっていること\n" + HIM_FACTS
    if radio:
        # she is at work; the person she is talking to does not exist here
        known = "## 今日の収録\n週に一回の自分の番組。台本はあるが、あなたはその通りには喋らない。"
    return f"{bible}\n\n{known}\n\n{where}\n\n{style}"


def build_messages(cfg, sc, arm):
    radio = sc.get("set") == "broadcast"
    system = build_system(cfg, arm, sc["scene"], radio=radio)
    msgs = [{"role": "system", "content": system}]
    for turn in sc.get("history") or []:
        msgs.append({"role": "assistant" if turn["who"] == "her" else "user",
                     "content": turn["text"]})
    tail = tail_radio(cfg) if radio else tail_chat(cfg)
    msgs.append({"role": "user", "content": f"{sc['him']}\n\n---\n{tail}"})
    return msgs


# --------------------------------------------------------------------------
# the answer store: never buy the same answer twice
# --------------------------------------------------------------------------

# Every run used to be standalone, so changing one section of one speech guide
# meant paying for every model's every scenario again -- and the six-model
# bench was re-run in full when only the guide had moved. An answer is a pure
# function of (model, the exact messages sent, sample index), so it is cached
# under a hash of exactly that. Change the guide and the hash changes and the
# call is made; change nothing and the run is free.
#
# The sample index is IN the key on purpose. Sample 2 of a scenario is a
# different draw from the same distribution, so it has to be stored separately
# or a three-sample run would collapse into one answer repeated.
CACHE = os.path.join(OUT_ROOT, "_answers")
# a byte that cannot occur in a prompt, so two different message lists
# cannot hash the same by running into each other
SEP = bytes([31])


def cache_key(model, messages, sample):
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    for m in messages:
        h.update(SEP + m["role"].encode("utf-8") + SEP + m["content"].encode("utf-8"))
    h.update(SEP + str(sample).encode("utf-8"))
    return h.hexdigest()[:32]


def cache_get(key):
    p = os.path.join(CACHE, key + ".json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return None


def cache_put(key, row):
    os.makedirs(CACHE, exist_ok=True)
    # an answer that failed or came back empty is NOT cached: caching it would
    # make a rate limit permanent, and 26 of Vertex's calls once died on 429
    if row.get("error") or not (row.get("text") or "").strip():
        return
    json.dump(row, io.open(os.path.join(CACHE, key + ".json"), "w", encoding="utf-8"),
              ensure_ascii=False)


# --------------------------------------------------------------------------
# signals -- counted, never scored
# --------------------------------------------------------------------------

# Her markers against the room, per 100k characters over the attributed corpus,
# from the same split bounds.json uses. Presence in a message of 40-200
# characters is the only question worth asking at this volume: a marker at 118
# per 100k is expected 0.2 times in a 200-character message, so a COUNT here
# would be arithmetic theatre. Presence, across many messages, is readable.
MARKERS = ["じゃん", "みたいな", "っけ", "ほいで", "あいつ", "なんか", "ゆかり",
           "わかんない", "もん", "のかな", "だもん"]
POLITE = ["です", "ます", "でしょうか", "ください"]
# the shapes the tape ends a bit with, rather than handing the turn over
UNDERCUT = ["嘘です", "今のなし", "まあいいや", "じゃあ次", "もういいや", "知らないけど",
            "って感じ", "ということで", "以上"]
FEELING = ["寂しい", "さみしい", "不安", "悲しい", "怖い", "嬉しい", "うれしい",
           "落ち着かない", "安心", "傷つ", "つらい", "辛い"]
# her own world: the flat, the body, the work, the tastes -- all from the bible
OWN_WORLD = ["蛍光灯", "ブレーカー", "ファンヒーター", "冷蔵庫", "脱衣所", "押し入れ",
             "洗濯", "納豆", "コンタクト", "眼鏡", "メガネ", "収録", "スタジオ", "番組",
             "マネージャー", "ヨシイ", "矢野", "鈴木", "弟", "福岡", "テレビ", "お風呂",
             "トレイ", "年賀状", "コーヒー", "口内炎", "親知らず", "157"]
SELF_ANALYSIS = ["タイプだから", "タイプなので", "性格だから", "そういう人間", "いつもこう",
                 "こういうとき", "ゆかりって、そういう"]

# The candidate guide is longer than the control because it demonstrates where
# the control describes, and the risk that buys is recital: a model handed a
# funny worked example can lift it wholesale instead of doing the same thing
# with new material. That is not the character transferring, it is a quotation,
# and it has to be visible or an arm wins on a trick.
#
# It used to be a hand-picked list of spans from ONE candidate's block quotes,
# which left every other arm unwatched -- and the replica guide carries
# thirty-six blockquoted lines of raw cue text, which is exactly the material a
# model lifts. So the demonstrations are read out of each arm's own files:
# everything inside 「」 and every blockquote line, bible and guide separately,
# and an answer is checked for its longest run in common with them. A quoted
# line arriving verbatim is recital rather than speech whichever file it came
# from; the two columns stay apart because the bible is shared by most arms
# and the guide is what differs.
RECITE_MIN = 10         # characters in common before it counts: at 8 のかなーみたいな and ドジっ子じゃない fire, and those are habits, not quotations; エロくないエレガンス is exactly 10
_QUOTE = re.compile(r"「([^」]{4,})」")
_CITE = re.compile(r"（ep[^）]*）")
_PUNCT = re.compile(r"[\s。、,.!！?？…「」『』\-]+")
_DEMOS = {}


def demonstrations(path):
    """Every quoted or blockquoted span in a persona file, punctuation stripped."""
    if path in _DEMOS:
        return _DEMOS[path]
    text = io.open(path, encoding="utf-8").read()
    spans = [m.group(1) for m in _QUOTE.finditer(text)]
    for ln in text.split("\n"):
        if ln.startswith(">"):
            spans.append(_CITE.sub("", ln[1:]))
    _DEMOS[path] = [q for q in (_PUNCT.sub("", x) for x in spans) if len(q) >= 4]
    return _DEMOS[path]


RECITE_TAPE_MAX = 3     # a span the tape holds more often than this is a habit, not a quotation
_TAPE = []


def _tape():
    """Her attributed speech as one string, punctuation stripped the same way
    the demonstrations are, so a span can be counted in it."""
    if not _TAPE:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from quote_audit import her_cues
        _TAPE.append(_PUNCT.sub("", "".join(t for _, _, t in her_cues())))
    return _TAPE[0]


def recites(text, demos):
    """The longest run the answer shares with any demonstration, when it is
    long enough to be a quotation rather than an idiom AND rare enough on the
    tape to be a quotation rather than a habit. A guide built from raw cue
    text carries her habits in its demonstrations, so without the second test
    ありがとうございます counted as recital 29 times in one run. One string in a
    list, so the field reads as the old one did: empty means nothing lifted."""
    from difflib import SequenceMatcher
    t = _PUNCT.sub("", text)
    spans = []
    for d in demos:
        m = SequenceMatcher(None, t, d, autojunk=False).find_longest_match(0, len(t), 0, len(d))
        if m.size >= RECITE_MIN:
            spans.append(t[m.a:m.a + m.size])
    tape = _tape()
    spans = [s for s in spans if tape.count(s) <= RECITE_TAPE_MAX]
    return [max(spans, key=len)] if spans else []


def signals(text, his_last, arm=None):
    """What is mechanically visible in one answer. Every field is a fact about
    the string; none of them is a judgement, and several of them are only
    meaningful read across a whole column."""
    lines = [l for l in text.split("\n") if l.strip()]
    head = text.strip()[:14]
    # an echo open: his last content word repeated back inside the first few
    # characters, with the quoting って. This is the shape that dominates her
    # live output; the tape uses って constantly but not to open a turn with.
    his_words = [w for w in re.split(r"[、。！？\s,.!?]+", his_last) if len(w) >= 2]
    echo = any(w[:4] in head for w in his_words) and "って" in head
    return {
        "chars": len(text.replace("\n", "")),
        "bubbles": len([b for b in text.split("\n\n") if b.strip()]),
        "polite": any(p in text for p in POLITE),
        "markers": [m for m in MARKERS if m in text],
        "undercut": any(u in text for u in UNDERCUT),
        "feeling_named": [f for f in FEELING if f in text],
        "own_world": [w for w in OWN_WORLD if w in text],
        "self_analysis": [s for s in SELF_ANALYSIS if s in text],
        "opens_ellipsis": any(l.strip().startswith(("…", "...", "・・・")) for l in lines),
        "ellipsis_lines": sum(1 for l in lines if "…" in l or "..." in l),
        "ends_question": text.rstrip().endswith(("？", "?")),
        "echo_open": bool(echo),
        "recites_guide": recites(text, demonstrations(arm[1])) if arm else [],
        "recites_bible": recites(text, demonstrations(arm[0])) if arm else [],
    }


# --------------------------------------------------------------------------
# bias check -- run before believing any result
# --------------------------------------------------------------------------

LENGTH_WORDS = ["短い", "長い", "一行", "三行", "字", "文字", "簡潔", "手短", "たくさん", "何通"]


def check_bias():
    """A candidate guide wins unfairly if it asks for a different amount of
    text, because the corpus cannot adjudicate length -- it holds no
    observation of her writing anything at all. This prints every length
    sentence in each guide so the two can be read side by side before any
    result is believed."""
    print("\nLENGTH INSTRUCTIONS, which must match across arms\n" + "=" * 62)
    for arm, (bible, path) in ARMS.items():
        print(f"\n--- {arm}  ({path})")
        for line in io.open(path, encoding="utf-8").read().split("\n"):
            if any(w in line for w in LENGTH_WORDS) and line.strip():
                print("   " + line.strip()[:160])
    print("\nSIZE\n" + "=" * 62)
    for arm, (bible, path) in ARMS.items():
        t = io.open(path, encoding="utf-8").read()
        b = io.open(bible, encoding="utf-8").read()
        print(f"   {arm:<10} guide {len(t):>6} chars {len(t.splitlines()):>3} lines   bible {len(b):>6} chars  {bible}")
    print("\nRead these yourself. If one guide asks for more text than the other,")
    print("the run measures length and not voice, and the result is worthless.\n")


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=2, help="answers per scenario per arm")
    ap.add_argument("--set", default="all", choices=["all", "chat", "broadcast"])
    ap.add_argument("--only", default="", help="comma-separated scenario ids")
    ap.add_argument("--arms", default="live", help="comma-separated arm names; have " + ", ".join(ARMS))
    ap.add_argument("--brief", default="", metavar="PATH",
                    help="write the subagent brief for the first arm to PATH and stop (no model call)")
    ap.add_argument("--instructions", default="",
                    help="which instruction arm to build the closing block in: "
                         "as_they_run_today (the control, and what her config says), "
                         "in_english, in_her_language. One process, no config edit, no restart, "
                         "so the arms differ in the instructions and in nothing else.")
    ap.add_argument("--check-bias", action="store_true", help="diff the guides and stop")
    ap.add_argument("--dry", action="store_true", help="print one built prompt and stop")
    ap.add_argument("--models", default="deepseek-v4-flash",
                    help="comma-separated, or 'all'; see tools/voicelab_models.py")
    ap.add_argument("--probe", action="store_true",
                    help="one call per model, then print a measured cost estimate for the full run and stop")
    ap.add_argument("--no-cache", action="store_true",
                    help="call even when the identical answer is already stored")
    ap.add_argument("--retries", type=int, default=3, help="attempts per call before giving up")
    ap.add_argument("--workers", type=int, default=16, help="concurrent calls across ALL models; tasks are interleaved so this divides across hosts rather than piling onto one")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    _QUIET[0] = not args.verbose

    if args.check_bias:
        check_bias()
        return 0

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    for a in arms:
        if a not in ARMS:
            print(f"[FATAL] unknown arm {a}; have {list(ARMS)}")
            return 1
        for f in ARMS[a]:
            if not os.path.exists(f):
                print(f"[FATAL] {a}: no such file {f}")
                return 1

    if args.instructions:
        import sim.lang as _lang
        if not _lang.set_override(args.instructions):
            print(f"[FATAL] unknown instruction arm {args.instructions}; have {list(_lang.ARMS)}")
            return 1
        print(f"[voicelab] instructions: {_lang.arm()}")

    scen = json.load(io.open(SCENARIOS, encoding="utf-8"))["scenarios"]
    if args.set != "all":
        scen = [s for s in scen if s.get("set", "chat") == args.set]
    if args.only:
        want = {s.strip() for s in args.only.split(",")}
        scen = [s for s in scen if s["id"] in want]
    if not scen:
        print("[FATAL] no scenarios selected")
        return 1

    # Her live config is read by a running process and Config REWRITES the file
    # it is given when the backfill changes anything. Copy first, always.
    tmp = os.path.join(tempfile.gettempdir(), "voicelab_config.json")
    shutil.copy("config_yukarin.json", tmp)
    cfg = Config(tmp)
    role_cfg = cfg.model("persona")
    caller = Caller(cfg)

    models = list(MODELS) if args.models == "all" else [m.strip() for m in args.models.split(",") if m.strip()]
    for m in models:
        if m not in MODELS:
            print(f"[FATAL] unknown model {m}; have {list(MODELS)}")
            return 1

    if args.brief:
        write_brief(cfg, scen, arms[0], args.brief)
        return 0

    if args.dry:
        sc = scen[0]
        msgs = build_messages(cfg, sc, ARMS[arms[0]])
        print(f"--- {arms[0]} / {sc['id']} / {len(msgs)} messages ---")
        for m in msgs:
            print(f"===== {m['role']} ({len(m['content'])} chars)")
            print(m['content'][:2600])
        return 0

    # Measure the bill rather than guess it: one call per model, then multiply.
    # A guess for this bench was out by a factor of two on input alone, because
    # the bible is 5,800 CHARACTERS in 16.8 KB and the obvious reading of
    # `wc -c` is the wrong one for Japanese.
    if args.probe:
        # Read the token counts already on disk before buying any. Five of the
        # twelve models in the Japanese bench had been probed before AND had
        # complete 42-call runs recorded, and re-probing them bought nothing a
        # `grep` could not have answered. History wins; a call is only made for
        # a model with nothing on record.
        history = {}
        for f in sorted(glob.glob(os.path.join(OUT_ROOT, "*", "runs.jsonl"))):
            for line in io.open(f, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("error") or not r.get("tok_in"):
                    continue
                history.setdefault(r["model"], []).append(r)
        sc = scen[0]
        full = len(scen) * len(arms) * args.samples
        print(f"probe: ONE call per model (not {args.samples}); --samples only scales the")
        print(f"       projection below, which is for the full {full}-call run per model")
        print()
        print(f"{'model':<22}{'served by':<18}{'in':>7}{'out':>8}{'secs':>7}{'$/call':>9}{'$ full':>9}  chars")
        grand = 0.0
        arm0 = "live" if "live" in ARMS else list(ARMS)[0]
        for mn in models:
            past = history.get(mn) or []
            if past and not args.no_cache:
                # mean of everything ever recorded for this model
                usage = {"in": sum(r["tok_in"] for r in past) // len(past),
                         "out": sum(r["tok_out"] for r in past) // len(past)}
                charged = [r.get("charged") for r in past if r.get("charged")]
                c1 = (sum(charged) / len(charged)) if charged else cost(mn, usage["in"], usage["out"])
                dt = sum(r.get("seconds", 0) for r in past) / len(past)
                grand += c1 * full
                print(f"{mn:<22}{'(from ' + str(len(past)) + ' recorded)':<18}{usage['in']:>7}{usage['out']:>8}"
                      f"{dt:>7.0f}{c1:>9.4f}{c1 * full:>9.2f}  --")
                continue
            msgs = build_messages(cfg, sc, ARMS[arm0])
            try:
                text, usage, dt, served = caller.call(mn, msgs, role_cfg.get("temperature", 1.0))
            except Exception as e:
                print(f"{mn:<22}{'--':<18} FAILED: {type(e).__name__}: {str(e)[:80]}")
                continue
            c1 = cost(mn, usage["in"], usage["out"], usage.get("cost"))
            grand += c1 * full
            print(f"{mn:<22}{str(served or MODELS[mn]['host'])[:17]:<18}{usage['in']:>7}{usage['out']:>8}"
                  f"{dt:>7.0f}{c1:>9.4f}{c1 * full:>9.2f}  {len(text)}")
        print()
        print(f"{'ESTIMATED TOTAL':<22}{'':<18}{'':>7}{'':>8}{'':>7}{'':>9}{grand:>9.2f}")
        print()
        print("Output tokens are mostly reasoning and vary by scenario, so read this as")
        print("the right order of magnitude rather than a quote.")
        return 0

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(OUT_ROOT, stamp)
    os.makedirs(out_dir, exist_ok=True)
    jsonl = io.open(os.path.join(out_dir, "runs.jsonl"), "w", encoding="utf-8")

    total = len(scen) * len(arms) * args.samples * len(models)
    print(f"voicelab: {len(scen)} scenarios x {len(arms)} arms x {args.samples} samples "
          f"x {len(models)} model(s) = {total} calls")
    print(f"          models: {', '.join(models)}")
    print(f"          -> {out_dir}")
    print()

    # One task per answer, run on a small pool. Sequentially this bench is four
    # hours: the slowest host in the probe took 57s a call and there are 504 of
    # them. Concurrency is per-task rather than per-model so a slow host cannot
    # hold the run open after the fast ones have finished, and it is kept low
    # because half the hosts in yukarin/providers.db earned a FLAKY verdict on
    # 429s the last time this project pushed them.
    import threading
    from concurrent.futures import ThreadPoolExecutor

    # **Interleaved by model, not grouped by it.** Grouped, every worker sits on
    # the same model and therefore the same host at once: seven other hosts idle
    # while one is hammered, a slow model cannot overlap with a fast one, and
    # the run looks like it is testing one model at a time because it is. Round
    # robin spreads the pool across every host in play, so the wall clock is the
    # slowest MODEL rather than the sum of all of them, and per-host concurrency
    # stays near workers/len(models) instead of workers.
    per_model = [[(mn, sc, arm, i) for sc in scen for arm in arms for i in range(args.samples)]
                 for mn in models]
    tasks = [t for group in zip(*per_model) for t in group] if len(set(map(len, per_model))) == 1 else             [t for lst in per_model for t in lst]
    total = len(tasks)
    lock = threading.Lock()
    state = {"n": 0, "spent": 0.0, "fail": 0, "cached": 0}

    def one(task):
        mn, sc, arm, i = task
        msgs = build_messages(cfg, sc, ARMS[arm])
        key = cache_key(mn, msgs, i)
        if not args.no_cache:
            hit = cache_get(key)
            if hit is not None:
                hit = dict(hit, cached=True)
                with lock:
                    state["n"] += 1
                    state["cached"] += 1
                    rows.append(hit)
                    jsonl.write(json.dumps(hit, ensure_ascii=False) + "\n")
                    jsonl.flush()
                return hit
        text, usage, dt, served, err = "", {"in": 0, "out": 0}, 0.0, None, ""
        # A 429 is the expected failure here, not an exceptional one, and the
        # first version of this retried three times over twelve seconds --
        # which lost 26 of Vertex's 84 calls, because a per-minute quota does
        # not care how politely you ask twelve seconds later. Long backoff for
        # a rate limit, short for anything else.
        for attempt in range(args.retries):
            try:
                text, usage, dt, served = caller.call(mn, msgs, role_cfg.get("temperature", 1.0))
                err = ""
                break
            except Exception as e:
                err = f"{type(e).__name__}: {str(e)[:160]}"
                if attempt + 1 < args.retries:
                    rate_limited = "429" in err or "esource" in err or "uota" in err
                    time.sleep((30 * (attempt + 1)) if rate_limited else (4 * (attempt + 1)))
        row = {"model": mn, "served_by": served, "scenario": sc["id"],
               "set": sc.get("set", "chat"), "arm": arm, "sample": i,
               "him": sc["him"], "tests": sc["tests"], "text": text,
               "tok_in": usage["in"], "tok_out": usage["out"],
               # what the provider actually charged, when it says so; None on
               # Vertex, which returns no cost field at all
               "charged": usage.get("cost"),
               "seconds": round(dt, 1), "error": err, "cached": False,
               **signals(text, sc["him"], ARMS[arm])}
        with lock:
            state["n"] += 1
            state["spent"] += cost(mn, usage["in"], usage["out"], usage.get("cost"))
            if err:
                state["fail"] += 1
                print()
                print(f"  [!] {mn}/{sc['id']}/{arm}: {err}")
            rows.append(row)
            jsonl.write(json.dumps(row, ensure_ascii=False) + "\n")
            jsonl.flush()
            cache_put(key, row)
            sys.stdout.write(f"\r  [{state['n']}/{total}] ${state['spent']:.2f} "
                             f"{state['fail']} failed {state['cached']} cached  {mn:<22}{sc['id']:<20}  ")
            sys.stdout.flush()
        return row

    rows, spent = [], 0.0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(one, tasks))
    spent, n = state["spent"], state["n"]
    jsonl.close()
    print(f"\r  {n} calls in {time.time()-t0:.0f}s, ${spent:.2f}" + " " * 40)

    write_report(out_dir, scen, arms, rows, models)
    print(f"read this: {os.path.join(out_dir, 'read.md')}")
    print(f"counts:    {os.path.join(out_dir, 'table.md')}")
    return 0


BRIEF_HEAD = """# Sitting the same test as the API models

You are being benchmarked on one thing: **how well you write Japanese in a
specific woman's voice.** Twelve API models are answering these exact prompts,
one fresh call per answer, and your answers go in the same table.

## The rules that make this a fair comparison

1. **Answer every scenario as if it were the only thing you had been asked.**
   You have all {n} in one context and the API models do not -- that asymmetry
   is the known flaw in this arm and it is recorded as such. Do not let an
   earlier answer shape a later one, do not vary an answer to avoid repeating
   yourself, and do not build a running character across scenarios.
2. **Three samples per scenario.** They must be independent attempts at the
   same prompt, not three parts of one answer and not deliberate variations.
   Write each as a first draft.
3. **Output only what she types.** No commentary, no stage directions, no
   speaker labels, no quotation marks around the message, no explanation of
   your choices. Japanese only.
4. **Do not look at any file in this repository.** Everything you need is in
   this brief. Reading her spec, the corpus or another model's answers would
   make your row incomparable.

## Output

Write `OUTPUT_PATH` (given in your task) as JSON Lines, one object per answer:

    {{"scenario": "<id>", "sample": 0, "text": "<her message(s)>"}}

`sample` is 0, 1, 2. Separate bubbles inside one answer with a blank line.
{total} lines total: {n} scenarios x 3 samples. Nothing else in the file.

---
"""


def write_brief(cfg, scen, arm, path):
    """The same test for an agent: the arm's system prompt, both closing
    blocks and every scenario, so an agent row is built from the same bytes
    the API rows are. Generated rather than kept, because a brief written by
    hand for one arm is a brief that quietly describes that arm."""
    chat = [sc for sc in scen if sc.get("set", "chat") != "broadcast"]
    sc0 = chat[0] if chat else scen[0]
    out = [BRIEF_HEAD.format(n=len(scen), total=len(scen) * 3)]
    out.append(f"\n# The system prompt (identical to the one every API model receives; arm `{arm}`)\n")
    out.append("```\n" + build_system(cfg, ARMS[arm], sc0["scene"]) + "\n```\n")
    out.append("The line `## 今どこにいるか` is replaced per scenario by that scenario's scene.\n"
               "For the `broadcast` scenarios the block `## この相手について分かっていること`\n"
               "is instead `## 今日の収録 / 週に一回の自分の番組。台本はあるが、あなたはその通りには喋らない。`\n"
               "and there is no chat partner: she is on air.\n")
    out.append("# The closing instruction (appended to the last user turn)\n")
    out.append("**chat scenarios:**\n\n```\n" + tail_chat(cfg) + "\n```\n")
    out.append("**broadcast scenarios:**\n\n```\n" + tail_radio(cfg) + "\n```\n\n---\n")
    out.append(f"# The {len(scen)} scenarios\n")
    for sc in scen:
        out.append(f"\n## {sc['id']}  ({sc.get('set', 'chat')})\n")
        out.append(f"**Scene** (goes in `## 今どこにいるか`): {sc['scene']}\n")
        if sc.get("history"):
            out.append("**Conversation so far:**\n")
            for t in sc["history"]:
                who = "ゆかり（あなた）" if t["who"] == "her" else "彼"
                out.append(f"- {who}: {t['text']}")
            out.append("")
        out.append(f"**His last message, which you are answering:** {sc['him']}\n")
    io.open(path, "w", encoding="utf-8").write("\n".join(out))
    print(f"[voicelab] brief for arm {arm} -> {path}")


def write_report(out_dir, scen, arms, rows, models):
    """Two files. `read.md` is the answers, grouped so one scenario can be read
    across every model at once, because that is how a voice is judged. `table.md`
    is the counts averaged over the samples.

    They are separate files for a reason that cost a reading once: with the
    table at the bottom of the transcript, the eye goes to the table.
    """
    by = {}
    for r in rows:
        by.setdefault((r["scenario"], r["model"], r["arm"]), []).append(r)

    o = io.open(os.path.join(out_dir, "read.md"), "w", encoding="utf-8")
    P = lambda s: o.write(s + "\n")
    P("# voicelab: the answers")
    P("")
    P("Grouped by scenario, then model, then arm, so one situation can be read")
    P("across every model at once. The counts are in `table.md` and settle")
    P("nothing on their own.")
    P("")
    P("A `chat` scenario is judged on stance and never on length: the corpus is")
    P("47 hours of broadcast, holds no observation of her writing anything, and")
    P("none at all of her in a private two-person exchange. The `broadcast`")
    P("scenarios are the fairness control -- the situation the tape does contain.")
    P("")
    for sc in scen:
        P("")
        P("---")
        P("")
        P("## %s  (%s)" % (sc["id"], sc.get("set", "chat")))
        P("")
        P("**What it is for.** " + sc["tests"])
        P("")
        P("**Scene.** " + sc["scene"])
        P("")
        for t in sc.get("history") or []:
            P("> **%s:** %s" % ("彼" if t["who"] == "him" else "ゆかり", t["text"]))
            P(">")
        P("> **彼:** " + sc["him"])
        P("")
        for mn in models:
            P("### " + mn)
            P("")
            for arm in arms:
                g = by.get((sc["id"], mn, arm), [])
                if not g:
                    continue
                P("**%s**" % arm)
                P("")
                for r in g:
                    if r.get("error"):
                        P("*sample %d* -- FAILED: %s" % (r["sample"] + 1, r["error"]))
                        P("")
                        continue
                    P("*sample %d* -- %d chars, %d bubble(s), %ds" % (
                        r["sample"] + 1, r["chars"], r["bubbles"], r.get("seconds", 0)))
                    P("")
                    for line in (r["text"] or "(empty)").split("\n"):
                        P("    " + line)
                    P("")
    o.close()

    t = io.open(os.path.join(out_dir, "table.md"), "w", encoding="utf-8")
    T = lambda s: t.write(s + "\n")
    T("# voicelab: the counts")
    T("")
    T("Averaged over the samples in the run. Counted, not scored: at 40-200")
    T("characters a marker RATE cannot be tested, only presence across a column,")
    T("and a share here is evidence for a reading rather than a verdict.")
    T("")
    T("`polite` is です/ます/ください present at all. `undercut` ends a bit on her")
    T("own terms. `echo` opens by quoting him back. `feel` names a feeling, which")
    T("the closing instruction given to every arm forbids. `own` mentions her own")
    T("flat, body or work. `recital` lifts a worked example out of the guide.")
    T("")

    def block(title, sel):
        T("## " + title)
        T("")
        T("| model | arm | n | fail | polite | undercut | ends ? | echo | ell | feel | own | recital | chars | secs | $ |")
        T("|" + "---|" * 15)
        for mn in models:
            for arm in arms:
                g = [r for r in rows if r["model"] == mn and r["arm"] == arm and sel(r)]
                ok = [r for r in g if not r.get("error")]
                if not g:
                    continue
                n = len(ok) or 1
                pct = lambda f: "%d%%" % round(100.0 * sum(1 for r in ok if f(r)) / n)
                spend = sum(cost(mn, r.get("tok_in", 0), r.get("tok_out", 0)) for r in g)
                T("| %s | %s | %d | %d | %s | %s | %s | %s | %s | %s | %s | %s | %d | %d | %.2f |" % (
                    mn, arm, len(ok), len(g) - len(ok),
                    pct(lambda r: r["polite"]),
                    pct(lambda r: r["undercut"]),
                    pct(lambda r: r["ends_question"]),
                    pct(lambda r: r["echo_open"]),
                    pct(lambda r: r["opens_ellipsis"]),
                    pct(lambda r: r["feeling_named"]),
                    pct(lambda r: r["own_world"]),
                    pct(lambda r: r["recites_guide"]),
                    sum(r["chars"] for r in ok) // n,
                    sum(r.get("seconds", 0) for r in ok) // n,
                    spend))
        T("")

    block("Chat", lambda r: r["set"] == "chat")
    block("Broadcast", lambda r: r["set"] == "broadcast")

    T("## Marker presence, chat only")
    T("")
    T("| model | arm | " + " | ".join(MARKERS) + " |")
    T("|" + "---|" * (len(MARKERS) + 2))
    for mn in models:
        for arm in arms:
            g = [r for r in rows if r["model"] == mn and r["arm"] == arm
                 and r["set"] == "chat" and not r.get("error")]
            if not g:
                continue
            cells = ["%d%%" % round(100.0 * sum(1 for r in g if m in r["markers"]) / len(g))
                     for m in MARKERS]
            T("| %s | %s | %s |" % (mn, arm, " | ".join(cells)))
    T("")

    T("## Spend and speed")
    T("")
    T("| model | host | calls | failed | tok in | tok out | mean secs | $ |")
    T("|" + "---|" * 8)
    grand = 0.0
    for mn in models:
        g = [r for r in rows if r["model"] == mn]
        if not g:
            continue
        ok = [r for r in g if not r.get("error")]
        spend = sum(cost(mn, r.get("tok_in", 0), r.get("tok_out", 0)) for r in g)
        grand += spend
        served = next((r.get("served_by") for r in ok if r.get("served_by")), MODELS[mn]["host"])
        T("| %s | %s | %d | %d | %d | %d | %d | %.2f |" % (
            mn, served, len(g), len(g) - len(ok),
            sum(r.get("tok_in", 0) for r in g), sum(r.get("tok_out", 0) for r in g),
            (sum(r.get("seconds", 0) for r in ok) // len(ok)) if ok else 0, spend))
    T("| **total** | | %d | | | | | **%.2f** |" % (len(rows), grand))
    t.close()


if __name__ == "__main__":
    sys.exit(main())
