"""Generate the synthetic var tree: python bzombie/viewer/fixtures/make_fixture.py [outdir]
All text is obviously fake. Schemas follow bzombie/CONTRACT.md."""
import json
import os
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "var")

RUNS = [
    # run_id, arm, character, lang, model, status
    ("fx_S_momoka_ds", "S", "momoka", "ja", "deepseek-v4.1-flash-1017", "running"),
    ("fx_P_momoka_ds", "P", "momoka", "ja", "deepseek-v4.1-flash-1017", "done"),
    ("fx_S_tomoe_glm", "S", "tomoe", "en", "glm-5.3", "done"),
    ("fx_P_tomoe_glm", "P", "tomoe", "en", "glm-5.3", "paused"),
]
TEXT = {
    "ja": {"him": ["テスト発言: おはよう（偽）", "テスト発言: 今なにしてる？（偽）", "テスト発言: ねむい（偽）"],
           "her": ["テスト返信: おはよう、ダミーだよ", "テスト返信: ダミーの作業中だよ", "テスト返信: もう寝なよ、ダミー", "テスト返信: ダミーの独り言"],
           "env": ["FAKE window title: dummy editor", "FAKE idle 10 min"]},
    "en": {"him": ["FAKE him: morning", "FAKE him: how was class", "FAKE him: tired"],
           "her": ["FAKE her: hey, dummy reply one", "FAKE her: dummy lecture was fine", "FAKE her: go to sleep, dummy", "FAKE her: dummy unprompted thought"],
           "env": ["FAKE world: lecture at 2nd period", "FAKE world: friend posts in group chat"]},
}


def w(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def wl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def build_run(base, rid, arm, ch, lang, model, status, variant=0, branch=None):
    t0 = datetime.fromisoformat("2026-11-02T08:00:00+09:00")
    tx = TEXT[lang]
    tr, calls, n = [], [], 0
    for day in (1, 2):
        d0 = t0 + timedelta(days=day - 1)
        seq = [("env", 0, 0), ("him", 5, 0), ("her", 6, 0), ("him", 90, 1), ("her", 91, 1),
               ("env", 300, 1), ("her", 301, 3), ("him", 600, 2), ("her", 602, 2 if variant == 0 else 0)]
        for who, mins, i in seq:
            ts = (d0 + timedelta(minutes=mins)).isoformat()
            line = {"virtual_ts": ts, "who": who, "text": tx[who][i % len(tx[who])], "sim_day": day}
            if who == "her":
                n += 1
                oid = "out_%s_%03d" % (rid[-6:], n)
                line["output_id"] = oid
                line["kind"] = "unprompted" if i == 3 else "reply"
                cid = ["c-%s-%03d-%d" % (rid[-6:], n, k) for k in range(2)]
                for k, c in enumerate(cid):
                    calls.append({
                        "call_id": c, "arm": arm, "run_id": rid, "wall_ts": "2026-10-22T18:%02d:%02d+09:00" % (n % 60, k),
                        "virtual_ts": ts, "model": model,
                        "request": {"messages": [{"role": "system", "content": ("FAKE SYSTEM PROMPT. " * 60)},
                                                 {"role": "user", "content": "FAKE user turn %d: %s" % (n, tx["him"][0])}]},
                        "response": {"choices": [{"message": {"role": "assistant", "content": line["text"] if k == 1 else "FAKE planning step",
                                                              "reasoning": "FAKE reasoning " * 5}}]},
                        "usage": {"prompt_tokens": 900 + 40 * n, "completion_tokens": 60 + k * 20},
                        "cost_micro": 1200 + 300 * k, "latency_s": 1.1 + 0.4 * k + (n % 5) * 0.2,
                        "error": None})
                causal = ({"admitted": [{"text": "FAKE attention line a", "weight": 0.6, "constant": False},
                                        {"text": "FAKE constant line", "weight": 0.3, "constant": True},
                                        {"text": "FAKE attention line b", "weight": 0.1, "constant": False}],
                           "gauges": {"fatigue": 0.4}, "stances": ["warm"]}
                          if arm == "S" else
                          {"percepts": ["FAKE percept"], "workspace": ["FAKE item"], "decision": "FAKE decision text", "route": "reply"})
                w(os.path.join(base, "traces", oid + ".json"), {
                    "output_id": oid, "arm": arm, "run_id": rid, "virtual_ts": ts, "text": line["text"],
                    "final_call_id": cid[1],
                    "calls": [{"call_id": cid[0], "role": "plan"}, {"call_id": cid[1], "role": "speak"}],
                    "inputs": [{"kind": "his_words", "source": "tr:%d" % n, "text": tx["him"][0]},
                               {"kind": "env_event", "source": "env:%d" % n, "text": tx["env"][0]},
                               {"kind": "memory", "source": "mem:1", "text": "FAKE memory " * 20},
                               {"kind": "state", "source": "st:1", "text": "FAKE state"},
                               {"kind": "persona", "source": "persona", "text": "FAKE persona " * 40},
                               {"kind": "own_past_line", "source": "tr:%d" % (n - 1), "text": tx["her"][0]}],
                    "state_at_output": {"mood": "fake"}, "causal": causal})
            elif who == "env":
                line["kind"] = "pc" if lang == "ja" else "world"
            tr.append(line)
    wl(os.path.join(base, "transcript.jsonl"), tr)
    wl(os.path.join(base, "calls.jsonl"), calls)
    return tr


def main():
    # files are overwritten in place; point OUT at an empty dir for a clean tree
    for rid, arm, ch, lang, model, status in RUNS:
        base = os.path.join(OUT, "runs", rid)
        build_run(base, rid, arm, ch, lang, model, status)
        w(os.path.join(base, "config.json"), {
            "run_id": rid, "arm": arm, "character": ch, "lang": lang, "model": model, "cap_usd": 5.0, "sim_days": 3,
            "clock_start": "2026-11-02T08:00:00+09:00", "seed": 7, "status": status,
            "started_wall": "2026-10-22T18:00:00+09:00", "updated_wall": "2026-10-22T18:30:00+09:00"})
        w(os.path.join(base, "clock.json"), {"virtual_ts": "2026-11-03T18:02:00+09:00", "sim_day": 2})
    bb = os.path.join(OUT, "runs", "fx_S_momoka_ds", "branches", "no_gauge")
    build_run(bb, "fx_S_momoka_ds", "S", "momoka", "ja", "deepseek-v4.1-flash-1017", "done", variant=1)
    w(os.path.join(bb, "branch.json"), {"branch_id": "no_gauge", "from_snapshot": "day1_end", "target": "gauge:fatigue",
                                        "value": "off", "replayed_from_virtual_ts": "2026-11-03T08:00:00+09:00"})
    # judge
    def crit(i, name, v1, v2):
        return {"id": "c%d" % i, "name": name, "passes": [
            {"pass": 1, "verdict": v1, "scores": {"A": 4, "B": 3}, "reason": "FAKE reason 1: 理由（偽） A is warmer.",
             "quotes": {"A": ["テスト返信: おはよう、ダミーだよ"], "B": ["FAKE her: dummy"]}},
            {"pass": 2, "verdict": v2, "scores": {"A": 3, "B": 3}, "reason": "FAKE reason 2.", "quotes": {"A": ["x"], "B": []}}]}
    w(os.path.join(OUT, "judge", "m_momoka", "results.json"), {
        "match_id": "m_momoka", "character": "momoka", "label_map": {"A": "fx_S_momoka_ds", "B": "fx_P_momoka_ds"},
        "criteria": [crit(1, "Consistency", "A", "A"), crit(2, "Warmth", "A", "B"), crit(3, "Naturalness", "tie", "tie")],
        "calibration": [{"defect": "FAKE planted repetition", "caught": True}, {"defect": "FAKE planted wrong language", "caught": False}],
        "summary": "FAKE summary: A slightly ahead."})
    w(os.path.join(OUT, "judge", "m_tomoe", "results.json"), {
        "match_id": "m_tomoe", "character": "tomoe", "criteria": [crit(1, "Consistency", "B", "B")], "calibration": [], "summary": "FAKE"})
    # calibration: judge/calibration/<stamp>/results.json (+ claude_calls.jsonl), newest stamp sorts last
    for stamp, miss in (("20260101_000001", True), ("20260102_000002", False)):
        by_lang, cal = {}, []
        for crit_id in ("answers_him", "own_life"):
            for lang in ("ja", "en"):
                ids = ["%s.%s.1" % (crit_id, lang), "%s.%s.2" % (crit_id, lang)]
                bad = miss and crit_id == "own_life" and lang == "en"
                for i, e in enumerate(ids):
                    cal.append({"defect": e, "caught": not (bad and i == 1)})
                by_lang.setdefault(crit_id, {})[lang] = {
                    "planted": 2, "caught": 1 if bad else 2, "controls": 0, "controls_passed": 0, "ids": ids,
                    "complete": True, "calibrated": not bad, "hash": "fx"}
        w(os.path.join(OUT, "judge", "calibration", stamp, "results.json"), {
            "match_id": "calibration_" + stamp, "character": "both", "label_map": {"A": "clean", "B": "planted"}, "criteria": [],
            "calibration": cal, "summary": {"model": "fx-judge", "calibrated": {}, "by_lang": by_lang,
                                            "uncalibrated": ["own_life"] if miss else [], "entries": len(cal), "calls": 8}})
        wl(os.path.join(OUT, "judge", "calibration", stamp, "claude_calls.jsonl"),
           [{"task": "judge", "cost_usd": 0.01, "is_error": False} for _ in range(8)])
    # modelcheck
    mods = ("fxmodel-a", "fxmodel-b")
    moments, samples, labels, sc1, sc2, rk1, rk2 = [], [], {}, {}, {}, {}, {}
    for mi, ch in enumerate(("momoka", "tomoe")):
        mid = "m%d" % (mi + 1)
        moments.append({"id": mid, "character": ch, "mood": "FAKE mood", "situation": "FAKE situation 状況 " + mid,
                        "chat": [["him", "FAKE まだ起きてる?"], ["her", "FAKE うん"]], "newest": "FAKE newest line"})
        labs = []
        for k in range(3):
            for mn, model in enumerate(mods):
                lab = "s%s%d%d" % (mid, k, mn)
                labs.append(lab)
                samples.append({"label": lab, "moment_id": mid, "text": "FAKE sample %s テスト" % lab})
                labels[lab] = {"model": model, "moment": mid, "k": k, "call_id": "fake-" + lab, "finish_reason": "stop",
                               "usage": {"completion_tokens": 17, "prompt_tokens": 100, "buyer_cost_micro": 100 + mn * 50}}
                sc1[lab] = {"kino": 3 + mn, "natural": 4 - mn, "flags": ["timestamp_stamps"] if mn else []}
                sc2[lab] = {"kino": 4, "natural": 3, "flags": []}
        rk1[mid], rk2[mid] = labs, list(reversed(labs))
    summ = {m: {"all": {"kino": 3.5, "natural": 3.5, "rank": 3.5}, "momoka": {"kino": 3.0, "natural": 3.2, "rank": 3.0},
                "tomoe": {"kino": 4.0, "natural": 3.8, "rank": 4.0}, "flags": {"timestamp_stamps": 3}, "first_places": 1 + i}
            for i, m in enumerate(mods)}
    w(os.path.join(OUT, "modelcheck", "samples.json"), {"run_id": "modelcheck", "moments": moments, "samples": samples})
    w(os.path.join(OUT, "modelcheck", "key.json"), {"run_id": "modelcheck", "labels": labels})
    w(os.path.join(OUT, "modelcheck", "judgments.json"), {
        "run_id": "modelcheck", "judge": "fx-judge", "criteria": ["kino", "natural"],
        "passes": [{"pass": 1, "judge": "fx-judge", "scores": sc1, "ranks": rk1}, {"pass": 2, "judge": "fx-judge", "scores": sc2, "ranks": rk2}],
        "summary": summ, "winner_model_agreement_moments": "1/2"})
    # pairs
    for pid, ch in (("p1", "momoka"), ("p2", "tomoe")):
        w(os.path.join(OUT, "pairs", pid + ".json"), {
            "pair_id": pid, "character": ch, "mapping": {"A": "fx_S_momoka_ds", "B": "fx_P_momoka_ds"},
            "A": {"text": "FAKE output A for " + pid + " テスト"}, "B": {"text": "FAKE output B for " + pid}})


if __name__ == "__main__":
    main()
