"""One table over every model AND every subagent, scored for Japanese.

`tools/voicelab.py` asks "is this her". This asks the narrower question the
model bench is actually for: **which model writes the best Japanese in her
voice.** Same answers, different lens, so the checks are different ones.

Four faults a voice screen does not look for, each seen in a real run:

  * **Script leakage.** qwen3.8-flash answered a Japanese prompt in English
    against three separate instructions. Latin letters in her output are almost
    always that, not a loanword.
  * **Wrong-language characters.** A model trained mostly on Chinese can emit a
    simplified form that is not a Japanese kanji (说, 时, 见) or a traditional
    one Japanese does not use (實, 體). Both read as Japanese to a checker that
    only asks "is this CJK", and to nobody who reads Japanese.
  * **Hangul and other scripts**, which appear when a multilingual model slips.
  * **Kanji density.** Her writing is chat, not prose: heavy kanji is the tell
    of a model writing formal Japanese in a text box. Reported, never scored --
    the corpus is speech transcription and its own kanji rate is a property of
    whisper, so this column compares models to each other and not to the tape.

Everything else here is the voice standard's (`docs/yukarin-voice-standard.md`),
counted the same way as in `tools/voicelab.py` so the two runs can be read
side by side.

**Subagent rows are not comparable on cost or on independence** and the table
says so: they answered all 42 prompts in one context while every API model got
42 fresh calls. That asymmetry cannot be removed with the tools here, so it is
labelled rather than hidden.

    python tools/voicelab_report.py --run data/voicelab/<stamp>
    python tools/voicelab_report.py --run <stamp> --agents data/voicelab
"""

import argparse
import collections
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from voicelab import signals, MARKERS
from voicelab_models import MODELS, cost

# Characters that are CJK but NOT Japanese: simplified Chinese forms whose
# Japanese counterpart is a different character (说/説, 时/時, 见/見, 问/問).
#
# **This list is validated against the corpus, because the first version was
# wrong and every row failed it.** It was typed from memory and swept in 書, 来,
# 点, 会, 体, 学, 国, 愛 -- ordinary Japanese kanji -- because Japanese shinjitai
# and Chinese simplified overlap heavily and eyeballing the difference does not
# work. The rule now: any character appearing in 532k characters of her real
# attributed Japanese is a Japanese character by definition and is dropped from
# the list at import. That check removed 么, 会, 党 and 写 from the candidates
# below, and it will remove anything else added carelessly later.
# The list is what has been SEEN, not what exists: it cannot be exhaustive, so
# a bench also prints every CJK character an answer used that her tape never
# did (`--unknown`), and a person reads that list. The second line below is
# what that reading found across two benches -- 电脑 for パソコン (minimax),
# 卻下 for 却下 and 收録 for 収録 and 家电 (glm-5.3-flash), 每晚 for 毎晩
# (glm-5.3), and 酑, which is not a word in any language. The first report
# said zero non-Japanese characters in fifteen rows; the rows had four.
_CANDIDATES = ("说时见对现实们这个么样问题让给两热爱应该开关闭书写读听讲语词汇灵构达标确认识别"
               "东义产会党务动员图团处备复够类练组织终绝网罗规觉计论设访证试话该谁调贵费质购"
               "轮软转输过还进远连迟适选"
               "电脑卻每晚收酑")


def _japanese_chars():
    """Every character she is on record using. Cached to a file: reading the
    corpus takes a second and this module is run per report."""
    cache = "data/voicelab/_corpus_chars.txt"
    if os.path.exists(cache):
        return set(io.open(cache, encoding="utf-8").read())
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from quote_audit import her_cues
        chars = set("".join(t for _, _, t in her_cues()))
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        io.open(cache, "w", encoding="utf-8").write("".join(sorted(chars)))
        return chars
    except Exception:
        return set()


_JP = _japanese_chars()
NOT_JAPANESE = {c for c in _CANDIDATES if c not in _JP} if _JP else set(_CANDIDATES)
_DROPPED = "".join(sorted(c for c in _CANDIDATES if c in _JP))

HANGUL = re.compile(r"[가-힯ᄀ-ᇿ]")
LATIN = re.compile(r"[A-Za-z]")
KANJI = re.compile(r"[一-鿿]")
KANA = re.compile(r"[぀-ヿ]")


def jp_signals(text):
    t = text or ""
    kanji = len(KANJI.findall(t))
    kana = len(KANA.findall(t))
    latin = len(LATIN.findall(t))
    return {
        "latin": latin,
        # a stray loanword is fine; a clause is not. 15 letters is about three
        # English words, which no Japanese chat message needs
        "english_leak": latin > 15,
        "hangul": len(HANGUL.findall(t)),
        "wrong_cjk": sorted({c for c in t if c in NOT_JAPANESE}),
        "kanji_ratio": round(kanji / max(kanji + kana, 1), 3),
    }


def load(run_dirs, agents_dir):
    """Several runs plus the agent files, as one set of rows.

    Several, because a model that has to be run apart from the others still
    belongs in the same table -- Gemini gets its own pass at two workers with a
    long backoff, since sharing a pool with ten other models is what produced 26
    Vertex 429s in one run. Later rows win on a (model, scenario, sample)
    collision, so a re-run of one model supersedes its earlier attempt without
    anybody editing a file.
    """
    rows, seen = [], {}
    for run_dir in run_dirs:
        p = os.path.join(run_dir, "runs.jsonl")
        if not os.path.exists(p):
            continue
        for l in io.open(p, encoding="utf-8"):
            l = l.strip()
            if not l:
                continue
            r = json.loads(l)
            if "model" not in r:
                continue          # the first bench predates the model column
            k = (r["model"], r.get("arm"), r["scenario"], r.get("sample", 0))
            if r.get("error") or not (r.get("text") or "").strip():
                if k in seen:
                    continue      # never let a failure overwrite a real answer
            seen[k] = r
    rows = list(seen.values())
    scen_set = {}
    try:
        for sc in json.load(io.open("data/voicelab_scenarios.json", encoding="utf-8"))["scenarios"]:
            scen_set[sc["id"]] = sc.get("set", "chat")
    except Exception:
        pass
    for f in sorted(glob.glob(os.path.join(agents_dir or run_dirs[0], "subagent_*.jsonl"))):
        name = os.path.basename(f)[len("subagent_"):-len(".jsonl")]
        for l in io.open(f, encoding="utf-8"):
            l = l.strip()
            if not l:
                continue
            d = json.loads(l)
            text = d.get("text", "")
            rows.append({"model": f"[agent] {name}", "arm": "live", "sample": d.get("sample", 0),
                         "scenario": d["scenario"], "set": scen_set.get(d["scenario"], "chat"),
                         "him": "", "text": text, "tok_in": 0, "tok_out": 0, "seconds": 0,
                         "error": "", "agent": True, **signals(text, "")})
    for r in rows:
        r.update(jp_signals(r.get("text", "")))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True,
                    help="run directory or stamp; repeat or comma-separate for several")
    ap.add_argument("--agents", default="data/voicelab")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    run_dirs = [d if os.path.isdir(d) else os.path.join("data/voicelab", d)
                for d in args.run.split(",") if d.strip()]
    rows = load(run_dirs, args.agents)
    run_dir = run_dirs[0]
    if not rows:
        print("[FATAL] no rows")
        return 1
    models = list(dict.fromkeys(r["model"] for r in rows))
    out = args.out or os.path.join(run_dir, "japanese.md")
    o = io.open(out, "w", encoding="utf-8")
    P = lambda s: o.write(s + "\n")

    P("# Which model writes the best Japanese in her voice")
    P("")
    P("Every row answered the same 14 scenarios on the same adopted speech guide,")
    P("three samples each. Counted, not scored: the verdict is in the reading.")
    P("")
    P("`eng` is an answer with more than 15 Latin letters -- a clause, not a loanword.")
    P("`badCJK` is a character that is CJK but not Japanese (a simplified or")
    P("traditional form Japanese does not use); any hit at all is a hard fault.")
    P("`kanji%` is kanji as a share of kanji+kana, reported so models can be compared")
    P("with each other -- NOT against the corpus, whose own rate belongs to whisper.")
    P("")
    P("**`[agent]` rows are not comparable on cost or independence.** They answered")
    P("all 42 prompts inside one context; every API model got 42 fresh calls. That")
    P("cannot be fixed with these tools, so it is labelled here instead of hidden.")
    P("")
    P("| model | n | fail | eng | badCJK | hangul | kanji% | polite | undercut | ends ? | ell | own | chars | secs | $ |")
    P("|" + "---|" * 15)
    for m in models:
        g = [r for r in rows if r["model"] == m]
        ok = [r for r in g if not r.get("error") and r.get("text", "").strip()]
        if not ok:
            P(f"| {m} | 0 | {len(g)} | | | | | | | | | | | | |")
            continue
        n = len(ok)
        pct = lambda f: "%d%%" % round(100.0 * sum(1 for r in ok if f(r)) / n)
        bad = sorted({c for r in ok for c in r["wrong_cjk"]})
        spend = 0.0
        if not g[0].get("agent"):
            try:
                spend = sum(cost(m, r.get("tok_in", 0), r.get("tok_out", 0)) for r in g)
            except KeyError:
                spend = 0.0
        P("| %s | %d | %d | %s | %s | %s | %d%% | %s | %s | %s | %s | %s | %d | %d | %s |" % (
            m, n, len(g) - n,
            pct(lambda r: r["english_leak"]),
            ("**" + "".join(bad[:8]) + "**") if bad else "--",
            pct(lambda r: r["hangul"] > 0),
            round(100 * sum(r["kanji_ratio"] for r in ok) / n),
            pct(lambda r: r["polite"]),
            pct(lambda r: r["undercut"]),
            pct(lambda r: r["ends_question"]),
            pct(lambda r: r["opens_ellipsis"]),
            pct(lambda r: r["own_world"]),
            sum(r["chars"] for r in ok) // n,
            sum(r.get("seconds", 0) for r in ok) // n,
            ("%.2f" % spend) if spend else "--"))
    P("")
    P("## Marker presence, chat scenarios only")
    P("")
    P("| model | " + " | ".join(MARKERS) + " |")
    P("|" + "---|" * (len(MARKERS) + 1))
    for m in models:
        g = [r for r in rows if r["model"] == m and r["set"] == "chat"
             and not r.get("error") and r.get("text", "").strip()]
        if not g:
            continue
        cells = ["%d%%" % round(100.0 * sum(1 for r in g if k in r["markers"]) / len(g)) for k in MARKERS]
        P("| %s | %s |" % (m, " | ".join(cells)))
    o.close()
    print("wrote", out)
    print(f"{len(rows)} answers over {len(models)} row(s)")
    for m in models:
        g = [r for r in rows if r["model"] == m]
        ok = [r for r in g if not r.get("error") and r.get("text", "").strip()]
        bad = sorted({c for r in ok for c in r["wrong_cjk"]})
        eng = sum(1 for r in ok if r["english_leak"])
        flag = []
        if bad:
            flag.append("NOT-JAPANESE " + "".join(bad[:8]))
        if eng:
            flag.append(f"{eng} English")
        if len(g) - len(ok):
            flag.append(f"{len(g)-len(ok)} empty/failed")
        print(f"  {m:<24} {len(ok):>3} ok  " + ("; ".join(flag) if flag else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
