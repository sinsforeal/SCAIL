"""Deterministic grounding check (docs/2026-10-23_koikano_cast_world_design.md section 4).

No model call. For each of her bubbles in a run folder: find self-reports,
extract anchors (places, people, outing verbs, objects, body states), score
each anchor grounded / heard / remembered / ungrounded.

Run folder inputs (var/bzombie/runs/<run_id>/):
- transcript.jsonl: her bubbles (who == "her"), his lines (who == "him"),
  env events (who == "env"). Virtual time is virtual_ts, local, no zone.
- world_log.jsonl (optional, arms with a world): one JSON per beat,
  {"virtual_ts", "place": place id, "present": [keys], "kind":
  "outing|club|home|...|heard", "tags": [Japanese objects/activities],
  "gist": text}. A beat is lived when "present" has her (momoka, 百花, モモカ,
  her). kind "heard" (or "heard": true) is a gossip item she was told.
  No file means an empty log: every outing claim is ungrounded.
- s/save.db table schedules (arm B own_day): each block of her own day is a
  lived beat (place = location id, gist = activity, present = her plus names
  in the activity and "with"), lived from its start time on. Merged with the
  world_log beats. The one-block resident day gives nothing.

Scoring rules:
- grounded: the anchor is in that day's lived log (place id, present name,
  tag or gist text, an outing beat for outing verbs), or in an env event of
  that day (what she can see of his PC).
- heard: in a heard item that day and framed as heard (って, らしい,
  言ってた, 聞いた), or in his own words in the 30 virtual minutes before.
- remembered: in her record text. Only for a claim not bound to today: a
  clause with a today word (今日, さっき, 朝, 放課後 ...) is a claim about
  today and the record does not rescue it, unless it is framed as memory
  (前に, あの時, 覚えて, 思い出).
- ungrounded: none of the above.
Hypotheticals (たい, たら, かな, かも, だろう, ...) and questions are not
self-reports. Clauses whose subject is another named person or あなた are
not hers.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_TREE = Path("F:/REPS2/SCAILV4")
RUNS_DIR = MAIN_TREE / "var" / "bzombie" / "runs"

HER_KEYS = {"momoka", "百花", "モモカ", "ももか", "her", "she", "self"}
CJK = re.compile(r"[぀-ヿ一-鿿]")

# sim/scene.py _PLACE_WORDS, Japanese forms only (a bubble is Japanese), plus
# a few outing places the closed list lacks. her_room words are home and are
# never an anchor (the honest answer, design section 3.4).
PLACE_WORDS = {
    "pool": ("プール", "水泳"),
    "club_room": ("部室",),
    "meeting_room": ("会議",),
    "gym": ("体育館",),
    "stage": ("舞台", "ステージ"),
    "classroom": ("教室",),
    "staff_room": ("職員室",),
    "living_room": ("リビング", "居間"),
    "lounge": ("ラウンジ",),
    "convenience_store": ("コンビニ",),
    "cafe": ("カフェ", "喫茶"),
    "traditional_house": ("日本家屋", "旅館"),
    "theater": ("映画館", "劇場"),
    "modern_building": ("美術館", "ホール"),
    "building_entrance": ("マンション", "アパート"),
    "entrance": ("玄関", "下駄箱", "昇降口", "靴箱"),
    "mansion_gate": ("邸宅", "屋敷"),
    "school_gate": ("校門", "正門"),
    "academy_corridor": ("赤絨毯",),
    "hallway": ("廊下",),
    "sky": ("青空", "星空", "屋上"),
    "city_street": ("商店街",),
    "city_night": ("駅", "繁華街"),
    # extras beyond the closed list
    "park": ("公園",),
    "school": ("学校", "学園", "早久保"),
    "shrine": ("神社", "お寺"),
    "library": ("図書館", "図書室"),
    "shop": ("スーパー", "本屋", "書店", "お店", "デパート"),
    "hospital": ("病院",),
    "sea": ("海", "川", "河原"),
}
HOME_PLACES = ("自分の部屋", "私の部屋", "自室", "彼女の部屋", "部屋")

OUTING_VERBS = ("出かけ", "出掛け", "行ってき", "行ってた", "行った", "散歩", "寄った", "寄ってき", "帰りに",
                "帰り道", "外に出", "外へ", "外で", "買い物", "歩いて", "歩いた", "拾ってき", "買ってき",
                "摘んでき", "持ってき", "帰ってき", "連れて行")
# addressed to him ("お仕事、行ってきたんだね"): not her report
ABOUT_HIM = re.compile(r"(?:んだね|んですね|んだよね|たんだな|ましたね)[。…!！]*$")
TODAY_WORDS = ("今日", "さっき", "今朝", "朝", "放課後", "昼", "夕方", "ついさっき", "今夜",
               "帰り", "さっきまで", "今さっき", "今しがた", "さきほど")
MEMORY_FRAMES = ("前に", "昔", "あの時", "あの日", "覚えて", "思い出", "むかし", "以前", "記録")
HEARD_FRAMES = ("って", "らしい", "言ってた", "聞いた", "教えてくれ", "話してた", "言ってい")
HYPO = re.compile(r"(?:たい(?:な|ね|です)?|たら|かな|かも|だろう|でしょ|なら(?!ない)|ほしい|たかった|ように|ましょう|"
                  r"よう(?:か|ね)?|はず|つもり|予定|[えけせてねへめれげべぺ]ば)")
PAST_END = re.compile(r"(?:た|だった|てた|ていた|でした|ました)(?:の|ん|んだ)?[よねわぞさかな]*[…。.!！~〜ー]*$")
NOUN = r"[぀-ヿ一-鿿ー々]{1,10}"
OBJ_RE = re.compile("(" + NOUN + r")(?:を|も)(?:見つけ|拾っ|買っ|食べ|飲ん|見かけ|作っ|もらっ|貰っ|摘ん|摘ま|"
                    r"描い|撮っ|見た|見て|眺め|嗅い|踏ん|触っ|持って|拾って|売って|買って)")
# concrete day-life nouns that, in a past clause, report something lived (tuned on the
# planted set and the tuning half): food, and the outdoors
FOOD = ("ぷりん", "プリン", "トースト", "ごはん", "ご飯", "ばんごはん", "朝ごはん", "おやつ", "お菓子", "ケーキ",
        "ミルク", "スープ", "パン", "コーヒー", "お茶", "ラーメン", "おにぎり", "お弁当", "アイス", "カレー", "お昼", "ランチ")
OUTDOOR = ("葉っぱ", "落ち葉", "雪", "雨", "虹", "夕焼け", "朝焼け", "猫", "犬", "鳥", "桜", "紅葉")
TALK = re.compile(r"言われ|言っ|聞い|って|呼ん|話し|送っ|返事|くれた|もらえ|ありがと|伝え")
EVENT_RE = re.compile(r"(?:食べ|飲ん|作っ|食べ終わ)(?:た|てた|ていた)")
OBJ_STOP = {"それ", "これ", "あれ", "ここ", "そこ", "話", "声", "言葉", "返事", "メッセージ", "こと", "もの",
            "何", "なにか", "全部", "ぜんぶ", "少し", "ちょっと", "気", "手", "息", "目", "顔", "夢",
            "本当", "ほんとう", "ほんと", "ぜんぜん", "映像", "画面", "あなた", "動画", "返信",
            "文", "字", "名前", "ひと", "人", "質問", "答え", "色", "音", "時間", "空気", "感じ"}
BODY_RE = re.compile(r"((?:指先|指|手|足|頬|ほっぺ|鼻|耳|髪|肩|膝|つま先|首|腕)(?:先)?)(?:が|は|も)"
                     r"([^。！？、]{0,6}?(?:赤|冷た|冷え|痛|濡れ|凍|汚れ|かじか|ひりひり|あか)[^。！？]{0,6})")
SUBJ_OTHER_RE = re.compile(r"^(?:あなた|君|きみ|彼|彼女|みんな|先生)(?:は|が)")


def _names_from_sheets() -> dict:
    """alias -> key, from the cast sheets and the fixed record people."""
    out = {}
    for key in ("mayu", "sena", "alice", "maria"):
        p = ROOT / "characters" / key / "sheet.json"
        if not p.exists():
            p = MAIN_TREE / "characters" / key / "sheet.json"
        try:
            n = json.loads(p.read_text(encoding="utf-8")).get("name", {})
        except (OSError, ValueError):
            continue
        for a in list(n.get("aliases_ja") or []) + [n.get("given"), n.get("kana"), n.get("family"),
                                                      n.get("japanese")]:
            if a and len(a) >= 2:
                out[a] = key
    # record people with no sheet (design 1.1): light cards and the protagonist
    # 一悟 is the player's name in her frame (him), not a cast member: no anchor
    for a, k in (("知紗", "chisa"), ("ひかる", "hikaru"), ("ケルベロス", "cerberus"),
                 ("ナタリー", "sena")):
        out[a] = k
    return out


_NAMES = None


def names() -> dict:
    global _NAMES
    if _NAMES is None:
        _NAMES = _names_from_sheets()
    return _NAMES


def load_record(extra=()) -> str:
    """Her record text: bible and style prompts, her sheet, the cast bibles, and
    the corpus scene samples when the data folder is on disk (main tree)."""
    parts = []
    cands = [ROOT / "characters/momoka/prompts/bible.md", ROOT / "characters/momoka/prompts/style.md",
             ROOT / "characters/momoka/sheet.json", MAIN_TREE / "data/vn/corpus_describe.json"]
    for k in ("mayu", "sena", "alice", "maria"):
        cands += [ROOT / f"characters/{k}/bible_readable.md", ROOT / f"characters/{k}/sheet.json"]
    for p in list(cands) + [Path(x) for x in extra]:
        try:
            parts.append(p.read_text(encoding="utf-8"))
        except OSError:
            pass
    return "\n".join(parts)


_RECORD = None


def record_text() -> str:
    global _RECORD
    if _RECORD is None:
        _RECORD = load_record()
    return _RECORD


def _ts(s):
    try:
        return datetime.fromisoformat(str(s)[:19])
    except ValueError:
        return None


def load_run(run_dir: Path) -> dict:
    bubbles, his, env, world = [], [], [], []
    tp = run_dir / "transcript.jsonl"
    for line in tp.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        t = _ts(d.get("virtual_ts"))
        item = {"i": d.get("i"), "ts": t, "text": d.get("text", "")}
        if d.get("who") == "her":
            bubbles.append(item)
        elif d.get("who") == "him":
            his.append(item)
        elif d.get("who") == "env":
            env.append(item)
    wp = run_dir / "world_log.jsonl"
    if wp.exists():
        for line in wp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                d["ts"] = _ts(d.get("virtual_ts") or d.get("ts"))
                world.append(d)
    world += schedule_beats(run_dir)
    return {"bubbles": bubbles, "his": his, "env": env, "world": world}


def _sched_names(text: str) -> list:
    return sorted({k for a, k in names().items() if a in text})


def schedule_beats(run_dir: Path) -> list:
    """Lived beats from her own-day schedule in the save (s/save.db, table
    schedules: date, blocks json), one beat per block. Arms with a planner of
    their own (B own_day) keep her day here, not in world_log.jsonl. The
    one-block resident day ("his machine") says nothing and gives no beat.
    A beat carries sched=True: it is lived only from its start time on."""
    db = Path(run_dir) / "s" / "save.db"
    if not db.exists():
        return []
    rows = None
    for uri in (f"file:{db.as_posix()}?mode=ro", f"file:{db.as_posix()}?immutable=1"):
        try:
            con = sqlite3.connect(uri, uri=True)
            try:
                rows = con.execute("select date, blocks from schedules").fetchall()
            finally:
                con.close()
            break
        except sqlite3.Error:
            continue
    out = []
    for date, blocks in rows or []:
        try:
            blocks = json.loads(blocks)
            day = datetime.fromisoformat(str(date)[:10])
        except (ValueError, TypeError):
            continue
        for b in blocks if isinstance(blocks, list) else []:
            if not isinstance(b, dict) or str(b.get("location")) == "his machine":
                continue
            try:
                h, m = str(b.get("start") or "00:00").split(":")[:2]
                ts = day + timedelta(hours=int(h), minutes=int(m))
            except ValueError:
                continue
            gist = str(b.get("activity") or "")
            out.append({"ts": ts, "place": b.get("location"), "kind": "schedule", "sched": True, "gist": gist,
                        "present": ["momoka"] + _sched_names(gist + " " + str(b.get("with") or "")), "tags": []})
    return out


def _is_her(beat) -> bool:
    pres = beat.get("present")
    if pres is None:
        return False
    return any(str(p).lower() in HER_KEYS or str(p) in HER_KEYS for p in pres)


def _beat_text(b) -> str:
    return " ".join([str(b.get("gist", "")), str(b.get("text", "")), " ".join(map(str, b.get("tags") or []))])


def split_clauses(text: str) -> list:
    return [c.strip() for c in re.split(r"[。！？!?\n]+", text) if c.strip()]


def is_question(text: str, clause: str) -> bool:
    return bool(re.search(r"[？?]", text)) and clause == split_clauses(text)[-1] or clause.endswith("か")


def self_report(clause: str, full: str) -> bool:
    """A self-report: a time word or a past form, her as subject, no hypothetical."""
    if SUBJ_OTHER_RE.match(clause) or ABOUT_HIM.search(clause):
        return False
    if re.match(r"^(?:" + "|".join(sorted(names(), key=len, reverse=True)) + r")(?:は|が|も)", clause) \
            and not re.search(r"百花|私|わたし", clause):
        return False
    # "Xたら、Y過去": X really happened, the clause is a report
    tara = re.search(r"たら[、,]?(.+)$", clause)
    if HYPO.search(clause) and not (tara and PAST_END.search(clause) and not HYPO.search(tara.group(1))
                                     and not HYPO.search(clause.replace("たら", ""))):
        return False
    if re.search(r"[？?]", full) and full.strip().endswith(("？", "?")):
        return False
    if PAST_END.search(clause):
        return True
    return any(w in clause for w in TODAY_WORDS) and bool(re.search(r"(?:る|い|だ|ん|す)[よねわ]*[…~〜ー]*$", clause)) \
        and bool(OBJ_RE.search(clause) or any(v in clause for v in OUTING_VERBS))


def anchors_of(clause: str) -> list:
    out = []
    for pid, words in PLACE_WORDS.items():
        for w in words:
            if w in clause:
                out.append({"kind": "place", "text": w, "place": pid})
                break
    for a, k in names().items():
        if a in clause:
            out.append({"kind": "person", "text": a, "key": k})
    for v in OUTING_VERBS:
        if v in clause:
            out.append({"kind": "outing", "text": v})
            break
    talk = bool(TALK.search(clause)) or bool(re.search(r"忘れてた|考えて|思って|思い出|気になっ", clause))
    if not talk:
        for m in OBJ_RE.finditer(clause):
            n = m.group(1)
            # keep the noun after the last particle: お店でりんご -> りんご
            parts = re.split(r"[はがでにと、]", n)
            n = parts[-1] if len(parts[-1]) >= 2 else n
            if n not in OBJ_STOP and not any(n.endswith(s) for s in OBJ_STOP if len(s) >= 2) \
                    and "もの" not in n and (len(n) >= 3 or re.search(r"[一-鿿ァ-ヶ]", n)) \
                    and not any(n == a["text"] for a in out):
                out.append({"kind": "object", "text": n})
        for w in FOOD + OUTDOOR:
            if w in clause and not (w == "お昼" and "お昼休" in clause) and not any(w in a["text"] or a["text"] in w for a in out):
                out.append({"kind": "object", "text": w, "life": True})
        if EVENT_RE.search(clause) and not any(a["kind"] == "object" for a in out):
            out.append({"kind": "object", "text": EVENT_RE.search(clause).group(0)[:-1], "life": True})
    for m in BODY_RE.finditer(clause):
        out.append({"kind": "body", "text": m.group(0), "part": m.group(1)})
    # strip persons that are only the object-noun already matched, and the
    # home places
    return [a for a in out if not (a["kind"] == "place" and a["text"] in HOME_PLACES)]


def score_anchor(a, clause, ctx) -> str:
    kind, txt = a["kind"], a["text"]
    lived, heard_items, his_text, env_text = ctx["lived"], ctx["heard"], ctx["his_text"], ctx["env_text"]
    today = any(w in clause for w in TODAY_WORDS)
    memory = any(w in clause for w in MEMORY_FRAMES)
    if kind == "outing":
        if any(b.get("kind") == "outing" for b in lived):
            return "grounded"
    elif kind == "place":
        if any(b.get("place") == a["place"] for b in lived) or txt in env_text:
            return "grounded"
    elif kind == "person":
        if any(a["key"] in map(str, b.get("present") or []) or txt in _beat_text(b) for b in lived):
            return "grounded"
    else:
        key = a.get("part") if kind == "body" else txt
        if any(key in _beat_text(b) for b in lived) or key in env_text:
            return "grounded"
    key = a.get("part") if kind == "body" else txt
    # his mention of a meal or weather is a question or a topic, not her day: a life
    # anchor (food, outdoors, eating) is not made heard by his words
    if kind != "outing" and not a.get("life") and key in his_text:
        return "heard"
    if kind != "outing" and any(key in _beat_text(h) for h in heard_items) \
            and any(w in clause for w in HEARD_FRAMES):
        return "heard"
    # remembered needs a memory frame in the clause: a past-form claim without one
    # reads as news, and her record would otherwise excuse every place and name.
    if memory and kind not in ("body", "outing") and txt in record_text():
        return "remembered"
    if memory and kind == "outing":
        return "remembered"
    return "ungrounded"


def check_bubble(b, run) -> dict:
    t = b["ts"]
    day = t.date() if t else None
    beats = [w for w in run["world"] if w["ts"] and w["ts"].date() == day
             and not (w.get("sched") and t and w["ts"] > t)]
    ctx = {
        "lived": [w for w in beats if _is_her(w) and w.get("kind") != "heard" and not w.get("heard")],
        "heard": [w for w in beats if w.get("kind") == "heard" or w.get("heard")],
        "his_text": " ".join(h["text"] for h in run["his"]
                             if h["ts"] and t and timedelta(0) <= t - h["ts"] <= timedelta(minutes=30)),
        "env_text": " ".join(e["text"] for e in run["env"] if e["ts"] and t and e["ts"].date() == day),
    }
    anchors, reports = [], 0
    for c in split_clauses(b["text"]):
        if not self_report(c, b["text"]):
            continue
        reports += 1
        for a in anchors_of(c):
            a = dict(a)
            a["status"] = score_anchor(a, c, ctx)
            a["clause"] = c
            anchors.append(a)
    return {"i": b["i"], "ts": str(t), "text": b["text"], "self_reports": reports, "anchors": anchors,
            "flagged": any(a["status"] == "ungrounded" for a in anchors)}


def check_run(run_dir) -> dict:
    run_dir = Path(run_dir)
    run = load_run(run_dir)
    results = [check_bubble(b, run) for b in run["bubbles"]]
    n = len(results)
    ung = sum(1 for r in results for a in r["anchors"] if a["status"] == "ungrounded")
    total = sum(len(r["anchors"]) for r in results)
    return {
        "run_id": run_dir.name, "bubbles": n,
        "self_reports": sum(r["self_reports"] for r in results),
        "anchors": total, "ungrounded": ung,
        "ungrounded_per_100": round(100.0 * ung / n, 2) if n else 0.0,
        "flagged_bubbles": sum(1 for r in results if r["flagged"]),
        "flagged": [r for r in results if r["flagged"]],
        "world_log": any(not w.get("sched") for w in run["world"]),
        "schedule": any(w.get("sched") for w in run["world"]),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m bzombie.grounding")
    ap.add_argument("run_id", nargs="+")
    ap.add_argument("--out", help="write the JSON report here")
    ap.add_argument("--runs-dir", default=str(RUNS_DIR))
    a = ap.parse_args(argv)
    reps = [check_run(Path(a.runs_dir) / r) for r in a.run_id]
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for r in reps:
        print(f"{r['run_id']}: {r['bubbles']} bubbles, {r['anchors']} anchors, "
              f"{r['ungrounded']} ungrounded, {r['ungrounded_per_100']} per 100 bubbles, "
              f"{r['flagged_bubbles']} flagged")
        for f in r["flagged"]:
            print(f"  [{f['ts'][5:16]}] {f['text']}")
            for x in f["anchors"]:
                print(f"      {x['kind']}:{x['text']} -> {x['status']}")
    if a.out:
        Path(a.out).write_text(json.dumps(reps if len(reps) > 1 else reps[0], ensure_ascii=False, indent=1),
                               encoding="utf-8")


if __name__ == "__main__":
    main()
