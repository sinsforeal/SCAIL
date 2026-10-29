"""Build a fresh S-arm run: a config, a character's prompts and an empty save, all under
var/bzombie/runs/<run_id>/s/. Derived from config_momoka.json; Momoka's live save, logs and
data are never named (every `data/...` path is moved under the run folder).

    python bzombie/arms/s/make_run.py --run-id r1 --character tomoe --clock-start "2026-10-23 08:00"

Prints the path of the config. Config() rewrites the file it is given, so this file is only
ever the scratch copy the control server loads.
"""

import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if os.path.basename(os.path.dirname(ROOT)) == "tmp":
    LIVE_ROOT = os.path.dirname(os.path.dirname(ROOT))
else:
    LIVE_ROOT = ROOT
RUNS = r"H:\SCAIL\bzombie\var\runs"
BASE_URL = "http://127.0.0.1:18330/arm/S/{run_id}/v1"
MODEL = "bz-model"
TOMOE_DIR = r"F:\REPS2\SCAILV3\characters\tomoe"
MARIA_DIR = os.path.join(ROOT, "characters", "maria")

MOMOKA_CARD_JA = (
    "# テスト用カード（最優先）\n"
    "百花は成人した大人（二十歳）である。以下の人物設定はそのうえで読む。"
    "日本語だけで話す。\n\n")
TOMOE_CARD = (
    "# Test card (overrides the bible wherever they differ)\n"
    "Tomoe is 19, in her first year at university in Tokyo. This overrides the bible's age "
    "of 15, its Nerima home and its high school class 1-C: she is not in high school and has "
    "no class 1-C. Everything else in the bible stands unchanged. She writes English only.\n\n")


NO_PC_TEXT = ("He has told you he is on his computer a lot, and that is all you have of it: you have no app, no "
              "view of his screen, no access to his notes and no way to tell whether he is at his computer. "
              "What he does there you know only when he says it.")


def _blk(start, end, activity, location, with_="alone"):
    return {"start": start, "end": end, "activity": activity, "location": location, "with": with_,
            "phone_access": "free"}


def _student_day(kind):
    """A first-year's day in Tokyo (the clock is Tokyo time): asleep 01:00-07:30 every night."""
    b = [_blk("00:00", "01:00", "up late on her phone", "her_room"),
         _blk("01:00", "07:30", "asleep", "her_room"),
         _blk("07:30", "08:30", "getting ready, breakfast with mom", "kitchen", "mom")]
    if kind == "weekday":
        b += [_blk("08:30", "09:30", "on the train to campus", "train"),
              _blk("09:30", "12:10", "lectures", "campus"),
              _blk("12:10", "13:00", "lunch with friends from her year", "campus", "friends"),
              _blk("13:00", "16:30", "lectures and seminar", "campus"),
              _blk("16:30", "17:30", "on the train home", "train"),
              _blk("17:30", "19:00", "home, a bit of time in her room", "her_room"),
              _blk("19:00", "20:00", "dinner with mom, dad and Kaito", "kitchen", "family"),
              _blk("20:00", "24:00", "in her room: homework, group chat, phone", "her_room")]
    elif kind == "cafe":
        b += [_blk("08:30", "09:30", "on the train to campus", "train"),
              _blk("09:30", "12:10", "lectures", "campus"),
              _blk("12:10", "13:00", "lunch with friends from her year", "campus", "friends"),
              _blk("13:00", "15:30", "lectures", "campus"),
              _blk("15:30", "17:00", "on the train to the cafe", "train"),
              _blk("17:00", "22:00", "part-time shift at the cafe", "cafe", "coworkers"),
              _blk("22:00", "23:00", "on the train home", "train"),
              _blk("23:00", "24:00", "home, in her room", "her_room")]
    elif kind == "sat":
        b += [_blk("08:30", "10:30", "slow morning at home", "her_room"),
              _blk("10:30", "16:30", "free, out in the city or at home", "her_room"),
              _blk("16:30", "17:00", "on the train to the cafe", "train"),
              _blk("17:00", "22:00", "part-time shift at the cafe", "cafe", "coworkers"),
              _blk("22:00", "23:00", "on the train home", "train"),
              _blk("23:00", "24:00", "home, in her room", "her_room")]
    else:
        b += [_blk("08:30", "12:00", "slow morning at home", "her_room"),
              _blk("12:00", "13:00", "lunch with the family", "kitchen", "family"),
              _blk("13:00", "18:00", "free at home or out with friends", "her_room"),
              _blk("18:00", "19:30", "dinner with the family", "kitchen", "family"),
              _blk("19:30", "24:00", "in her room: homework, group chat, phone", "her_room")]
    return b


def tomoe_home():
    """Tomoe's home file (the world.home_file shape resident/schedule.py reads), with a fixed weekly plan so
    a stub run needs no model to plan her day. Nerima, with mom, dad and Kaito."""
    day = {"mon": "weekday", "tue": "weekday", "wed": "cafe", "thu": "weekday", "fri": "weekday",
           "sat": "sat", "sun": "sun"}
    return {
        "home": {"what": "the family house in Nerima, Tokyo, where she lives with mom, dad and her brother Kaito",
                 "rooms": [{"id": "her_room", "name": "her room", "what": "her own room upstairs"},
                           {"id": "kitchen", "name": "kitchen and dining room",
                            "what": "where the family eats; mom is usually here"}],
                 "building": {"what": "a two-storey family house in Nerima"}},
        "outside": [{"id": "train", "name": "the train", "what": "the line between Nerima and campus"},
                    {"id": "campus", "name": "campus", "what": "her university in Tokyo: lectures, seminar, lunch with friends"},
                    {"id": "cafe", "name": "the cafe", "what": "her part-time job, Wednesday and Saturday evenings"}],
        "week": {"anchors": [{"what": "first-year student: lectures most weekdays"},
                             {"what": "the cafe job on Wednesday and Saturday evenings"}],
                 "hours": [{"what": "asleep about 01:00 to 07:30"}],
                 "standing": [{"what": "home for dinner on the other evenings"}]},
        "plan": {**{d: _student_day(k) for d, k in day.items()},
                 "notes": "a first-year student's week in Tokyo, from her home file"},
    }


# Grounding test arms (tk-6r3). A is the plain S arm (arm_variant ""). B plans her day from a home file of small
# home happenings. C adds the honest-absence cue: no event, one situation line and one prompt line.
ARM_VARIANTS = ("", "own_day", "absence")
HOME_SRC = os.path.join(ROOT, "characters", "momoka", "world", "home.json")
SICK_P = 0.3   # chance a given weekday is a sick day, drawn from (seed, weekday), the same for every arm
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
ABSENCE_SITUATION = "いまの場所: 自分の部屋。ひとり。今日は特に何もなかった。"
ABSENCE_PROMPT = ("\n今日、特に何もなかったときは、何もなかったと言う。なかったことを作らない。"
                  "どこかへ行った話も、誰かに会った話も、そのときの百花にはない。\n")


def sick_days(seed):
    """The weekdays that are sick days for this seed: a seeded draw, so every arm and rerun agrees."""
    import random
    return [d for d in WEEKDAYS if random.Random(f"momoka-sick:{int(seed)}:{d}").random() < SICK_P]


def momoka_home(seed, src=HOME_SRC):
    """The home file for arm B: home.json with `plan` built from its `day`, `sick_day` and `sun_visit` blocks."""
    home = json.loads(_read(src))
    sick = set(sick_days(seed))
    plan = {}
    for d in WEEKDAYS:
        if d in sick:
            plan[d] = copy.deepcopy(home["sick_day"])
        elif d == "sun":
            rows = []
            for b in home["day"]:
                if b["start"] == "13:00":
                    rows += [dict(b, end="14:00"), *copy.deepcopy(home["sun_visit"]), dict(b, start="17:00", end="18:00")]
                else:
                    rows.append(copy.deepcopy(b))
            plan[d] = rows
        else:
            plan[d] = copy.deepcopy(home["day"])
    for rows in plan.values():
        for r in rows:
            r["phone_access"] = "free"
    plan["notes"] = "百花の一日。家で過ごす。ホームファイルの予定"
    home["plan"] = plan
    home["sick_weekdays"] = sorted(sick)
    return home


def _no_pc_sense(bible):
    """Tomoe sees nothing of his PC (User 10-22): the bible's app and notes-folder sentences are replaced."""
    a = bible.find("He gave you access to two things")
    tail = "You do not always tell him what you saw."
    b = bible.find(tail, a)
    if a < 0 or b < 0:
        raise ValueError("tomoe bible: the PC-access paragraph was not found; update _no_pc_sense")
    out = bible[:a] + NO_PC_TEXT + bible[b + len(tail):]
    return out.replace("", "")


def _read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def _write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


def _move_data(node, run_s):
    """Every string that is a `data/...` path or `logs...` dir moves under the run folder."""
    if isinstance(node, dict):
        return {k: _move_data(v, run_s) for k, v in node.items()}
    if isinstance(node, list):
        return [_move_data(v, run_s) for v in node]
    if isinstance(node, str) and (node.startswith("data/") or node in ("logs", "logs/dryrun")):
        return os.path.join(run_s, node).replace("\\", "/")
    return node


def _swap_strings(node, mapping):
    if isinstance(node, dict):
        return {k: _swap_strings(v, mapping) for k, v in node.items()}
    if isinstance(node, list):
        return [_swap_strings(v, mapping) for v in node]
    if isinstance(node, str) and node in mapping:
        return mapping[node]
    return node


STANDIN_CARD = (
    "# Test card (overrides the bible wherever they differ)\n"
    "Tomoe is 19 and, for this test, lives in Momoka Chiyoda's big house in Tokyo as a long-stay houseguest, in the "
    "room called the maid room. Momoka is a friend and a housemate. This overrides the bible's home in Nerima, "
    "mom, dad and Kaito, and every university and cafe detail: none of that is in her days now. She writes English "
    "only, to everybody.\n\n")

# One house, one set of place ids (tk-1pl). Both minds' home files use these ids, and the driver tells each one when the
# other is at home (bzombie/harness/peers.py House). Momoka's ids are the ones in characters/momoka/world/home.json.
HOUSE = {"id": "chiyoda", "rooms": {
    "her_room": {"ja": "百花の部屋", "en": "Momoka's room"},
    "house": {"ja": "家の広間", "en": "the main part of the house"},
    "maid_room": {"ja": "メイドの部屋", "en": "the maid room"}}}
PEER_NAMES = {"momoka": {"name": "Momoka", "name_ja": "百花"}, "tomoe": {"name": "Tomoe", "name_ja": "朋絵"},
              "maria": {"name": "Maria", "name_ja": "真里亜"}}
# what one mind calls another when it is not the plain name, (me, other) -> form, from the speaker's own record:
# 真里亜 addresses 百花 as お嬢様 (her bundle's quality cap お嬢様 3 and her cast.json row); 百花 says 真里亜.
ADDRESS = {("maria", "momoka"): "お嬢様"}


def standin_home(house=None):
    """The stand-in's home file: the same shape as Momoka's home.json, her day in the shared house (ids from HOUSE)."""
    house = house or HOUSE
    rooms = [{"id": k, "name": v["en"], "what": v["en"]} for k, v in house["rooms"].items()]
    day = [_blk("00:00", "06:00", "asleep", "maid_room"),
           _blk("06:00", "08:30", "up, tidying her things, breakfast", "house", "Momoka"),
           _blk("08:30", "12:00", "about the house, helping and chatting", "house", "Momoka"),
           _blk("12:00", "13:00", "lunch", "house", "Momoka"),
           _blk("13:00", "17:00", "in the maid room: reading, phone, her own things", "maid_room"),
           _blk("17:00", "21:00", "about the house, dinner", "house", "Momoka"),
           _blk("21:00", "22:30", "in the maid room, winding down", "maid_room"),
           _blk("22:30", "24:00", "asleep", "maid_room")]
    plan = {d: [dict(b) for b in day] for d in WEEKDAYS}
    plan["notes"] = "a houseguest's day in Momoka's house"
    return {"home": {"what": "Momoka Chiyoda's big house in Tokyo", "rooms": rooms,
                     "building": {"what": "the Chiyoda house"}},
            "outside": [], "week": {"anchors": [], "hours": [{"what": "asleep about 22:30 to 06:00"}], "standing": []},
            "plan": plan}


def maria_home(house=None):
    """真里亜's home file: the shared house (ids and names from HOUSE, Japanese) and a fixed weekly plan, so a run needs
    no model to plan her day. Her record is silent on her routine and where she sleeps (maria_house.json `silent`,
    `her_own_room`): the sleep hours and the maid room are the bench's liberty, written in the plan notes. The
    daytime blocks are her record's own: she serves お嬢様, makes tea, is in the house."""
    house = house or HOUSE
    facts = json.loads(_read(os.path.join(MARIA_DIR, "world", "maria_house.json")))
    unknown = [p for p in facts.get("place_ids", []) if p not in house["rooms"]]
    if unknown:
        raise ValueError(f"maria_house.json place ids not in HOUSE: {unknown}")
    rooms = [{"id": k, "name": v["ja"], "what": v["ja"]} for k, v in house["rooms"].items()]
    day = [_blk("00:00", "06:00", "眠っている", "maid_room"),
           _blk("06:00", "08:30", "起きて、お嬢様の朝の支度とお茶の用意", "house", "百花"),
           _blk("08:30", "12:00", "お嬢様のお世話、家の用事", "house", "百花"),
           _blk("12:00", "13:00", "昼食の用意とお給仕", "house", "百花"),
           _blk("13:00", "15:00", "お嬢様のお部屋でお世話", "her_room", "百花"),
           _blk("15:00", "17:00", "お茶の時間、家の用事", "house", "百花"),
           _blk("17:00", "21:00", "夕食とお風呂の支度、お給仕", "house", "百花"),
           _blk("21:00", "22:30", "自分の部屋で、ひと息", "maid_room"),
           _blk("22:30", "24:00", "眠っている", "maid_room")]
    plan = {d: [dict(b) for b in day] for d in WEEKDAYS}
    plan["notes"] = ("真里亜の一日。千代田家のメイド。記録に彼女の日課と寝る場所はない: 自分の部屋(メイドの部屋)と"
                     "眠る時間は、このテストの自由。昼は記録どおりお嬢様のお世話")
    return {"home": {"what": "千代田家、百花の大きな家(東京)", "rooms": rooms, "building": {"what": "千代田家の屋敷"}},
            "outside": [], "week": {"anchors": [], "hours": [{"what": "眠るのは22:30から06:00ごろ"}], "standing": []},
            "plan": plan}


def peer_contact_rows(minds, me, me_lang="ja"):
    """peer_talk.contacts for the mind `me` from every mind of the run [{key, call?}]: everybody but herself. `id` is
    the key the driver's hub files mail under, `name` what `me` calls her (her Japanese name when `me` writes
    Japanese, else the Latin one; `call` on the mind overrides)."""
    rows = []
    for p in minds:
        if p["key"] == me:
            continue
        nm = PEER_NAMES.get(p["key"], {})
        rows.append({"id": p["key"], "name": p.get("call") or ADDRESS.get((me, p["key"]))
                     or (nm.get("name_ja") if me_lang == "ja" else nm.get("name"))
                     or p["key"], "language": p.get("language", "")})
    return rows


def build(run_id, character, clock_start, runs_root=RUNS, port_base_url=None, base_config=None,
          max_tokens=8192, arm_variant="", seed=0, peer_contacts=None, role="primary", peer_key=""):
    if character not in ("momoka", "tomoe", "maria"):
        raise ValueError("character must be momoka, tomoe or maria")
    if role not in ("primary", "peer"):
        raise ValueError("role must be primary or peer")
    if role == "peer" and character not in ("tomoe", "maria"):
        raise ValueError("a peer mind is Maria or the Tomoe stand-in")
    if arm_variant not in ARM_VARIANTS:
        raise ValueError(f"arm_variant must be one of {ARM_VARIANTS}")
    if arm_variant and character != "momoka":
        raise ValueError("arm_variant is Momoka's grounding test only")
    run_dir = os.path.join(runs_root, run_id)
    run_s = os.path.join(run_dir, "s")
    os.makedirs(run_s, exist_ok=True)
    src = base_config or os.path.join(ROOT, "config_momoka.json")
    cfg = json.loads(_read(src))

    # prompts: the style and bible files, with the test card prepended
    pdir = os.path.join(run_s, "prompts")
    if character == "momoka":
        style = MOMOKA_CARD_JA + _read(os.path.join(ROOT, "prompts_momoka", "style.md"))
        bible = MOMOKA_CARD_JA + _read(os.path.join(ROOT, "prompts_momoka", "bible.md"))
        old_style, old_bible = "prompts_momoka/style.md", "prompts_momoka/bible.md"
    elif character == "maria":
        # her own prompts, as built from her record: no test card (they carry no age or grade by design)
        style = _read(os.path.join(MARIA_DIR, "prompts", "style.md"))
        bible = _read(os.path.join(MARIA_DIR, "prompts", "bible.md"))
        old_style, old_bible = "prompts_momoka/style.md", "prompts_momoka/bible.md"
    else:
        card = STANDIN_CARD if role == "peer" else TOMOE_CARD
        style = card + _read(os.path.join(TOMOE_DIR, "prompts", "style.md"))
        bible = card + _no_pc_sense(_read(os.path.join(TOMOE_DIR, "prompts", "bible.md")))
        old_style, old_bible = "prompts_momoka/style.md", "prompts_momoka/bible.md"
    if arm_variant == "absence":
        style += ABSENCE_PROMPT
    sp, bp = os.path.join(pdir, "style.md"), os.path.join(pdir, "bible.md")
    _write(sp, style)
    _write(bp, bible)
    cfg = _swap_strings(cfg, {old_style: sp.replace("\\", "/"), old_bible: bp.replace("\\", "/")})

    ch = cfg["character"]
    if character == "tomoe":
        sheet = json.loads(_read(os.path.join(TOMOE_DIR, "sheet.json")))
        sheet["age"] = 19
        sheet["born"] = "2007-05-23"
        sheet["school_year"] = "first year at university in Tokyo"
        sheet.setdefault("place", {})["lives"] = "Tokyo"
        # no world program: the sheet's own existence block wins over the config's, so it is set here
        sheet["existence"] = {"embodied": True, "in_world": False, "sees_him": "none",
                              "with_him": "chat", "has_account": False}
        shp = os.path.join(run_s, "sheet.json")
        _write(shp, json.dumps(sheet, ensure_ascii=False, indent=1))
        ch.update({"name": "Tomoe", "name_ja": "朋絵", "reading_ja": "ともえ",
                   "writes_to_him": "english", "instruction_language": "english",
                   "cast_file": "", "neutral_file": os.path.join(TOMOE_DIR, "fills.json").replace("\\", "/"),
                   "existence": {"embodied": True, "in_world": False, "sees_him": "none",
                                 "with_him": "chat", "has_account": False}})
        cfg["world"]["character_file"] = shp.replace("\\", "/")
        # her day: a home file with a student's week (asleep 01:00-07:30), so the asleep branch runs for her
        hp = os.path.join(run_s, "home_tomoe.json")
        _write(hp, json.dumps(standin_home() if role == "peer" else tomoe_home(), ensure_ascii=False, indent=1))
        cfg["world"]["home_file"] = hp.replace("\\", "/")
        cfg["tts"]["language_boost"] = "English"
    if character == "maria":
        # 真里亜 (tk-1pl): her sheet, fills and cast from characters/maria; existence from her sheet (in_world false: the
        # bench feeds her the house as events). Her config deltas come from bundle.json config_overrides, the part
        # that is her mind (character block, quality caps, shape); the gateway, clock and off-switches stay the bench's.
        ov = json.loads(_read(os.path.join(MARIA_DIR, "bundle.json")))["config_overrides"]
        shp = os.path.join(run_s, "sheet.json")
        _write(shp, _read(os.path.join(MARIA_DIR, "sheet.json")))
        cast = os.path.join(run_s, "cast.json")
        _write(cast, _read(os.path.join(MARIA_DIR, "cast.json")))
        fills = os.path.join(run_s, "fills.json")
        _write(fills, _read(os.path.join(MARIA_DIR, "fills.json")))
        ch.update(ov["character"])
        ch.update({"cast_file": cast.replace("\\", "/"), "neutral_file": fills.replace("\\", "/")})
        for sec in ("quality", "shape", "reunion"):
            if sec in ov:
                cfg.setdefault(sec, {}).update(copy.deepcopy(ov[sec]))
        cfg["world"]["character_file"] = shp.replace("\\", "/")
        hp = os.path.join(run_s, "home_maria.json")
        _write(hp, json.dumps(maria_home(), ensure_ascii=False, indent=1))
        cfg["world"]["home_file"] = hp.replace("\\", "/")
        cfg["tts"]["language_boost"] = "Japanese"
    if arm_variant == "own_day":
        # arm B: her day from a home file (resident/schedule.py own_day); she stays in_world false
        hp = os.path.join(run_s, "home_momoka.json")
        _write(hp, json.dumps(momoka_home(seed), ensure_ascii=False, indent=1))
        cfg["world"]["home_file"] = hp.replace("\\", "/")
    ch["style_prompt"] = sp.replace("\\", "/")
    ch["style_ja_prompt"] = sp.replace("\\", "/")

    # the gateway provider, one model name for every role
    url = base_url = (port_base_url or BASE_URL).format(run_id=run_id)
    cfg["api"]["provider"] = "bz"
    cfg["api"].setdefault("providers", {})["bz"] = {
        "kind": "bz", "base_url": url, "max_tokens": max_tokens, "models": {MODEL: MODEL}}
    cfg["api"]["base_url"] = url
    # embeddings through the gateway's shared e5 (tk-y11): the mind never imports torch (S peak 1685 -> 123 MB WS)
    cfg.setdefault("embed", {})["url"] = url + "/embeddings"
    for mrole in cfg.get("models", {}).values():
        if isinstance(mrole, dict):
            mrole["model"] = MODEL
            mrole.pop("provider", None)
            mrole["max_tokens"] = min(int(mrole.get("max_tokens") or max_tokens), max_tokens)

    # no channel but the queue, nothing live
    cfg["bz_channel"] = {"enabled": True}
    if peer_contacts:  # another running mind in this run (tk-1pl): the hub is the driver, the rows are her contacts
        cfg["peer_talk"] = {**(cfg.get("peer_talk") or {}), "enabled": True, "contacts": list(peer_contacts)}
    cfg["clock"] = {"mode": "stepped", "sim_start": clock_start, "sim_speed": 1.0}
    # typesafe: a separate classifier service; the match runs one model for every call on both arms (precheck point 3),
    # so it is off on purpose and SCAIL's fallbacks answer those uses (it failed on a relative key path before 18:45)
    for sec in ("vn", "tts", "sensors", "vision", "afterthought", "talkapp", "watching", "typesafe"):
        if isinstance(cfg.get(sec), dict):
            cfg[sec]["enabled"] = False
    cfg["telegram"].update({"bot_token": "", "chat_id": "", "console_only": True})
    cfg["world"]["weather_enabled"] = False
    # her own text_him pick goes through the unanswered-message backoff (tk-xfk: pings every 25 min into no answer)
    cfg.setdefault("pick", {})["hold_by_initiative"] = True
    # surface checks on the S arm (tk-7wb bubble budget, tk-wnp repetition check); off in config.py
    cfg.setdefault("bz_s10", {}).update({"budget": True, "repeat_check": True})
    # and a look is due on a change, not on the 25-minute clock (tk-y7j)
    cfg["pick"]["due_on_change"] = True
    # pushback against her card (tk-mfx): the judges found S Tomoe agreeable. Base temper and the card's own manner.
    cfg.setdefault("shape", {})["pushback"] = (
        {"enabled": True, "base": 0.45, "threshold": 0.5, "min_gap_minutes": 20,
         "how": "loud, rude as affection, never explaining or diagnosing yourself."} if character == "tomoe" else
        {"enabled": True, "base": 0.3, "threshold": 0.5, "min_gap_minutes": 20,
         "how": "refuse through your body and leave room to be talked out of it; never take charge."})
    # his clock (User 10-22 17:39): Momoka has no time difference, he is on Tokyo time with her. Tomoe's bible puts
    # him many hours behind her; a fixed UTC-4 (Etc/GMT+4) keeps exactly 13 h across the Nov 1 DST change.
    # Never "local": it drifts.
    cfg["world"]["user_timezone"] = "Asia/Tokyo" if (character in ("momoka", "maria") or role == "peer") else "Etc/GMT+4"
    cfg["world"]["shared_dir"] = ""
    # The machine's senses (User 10-22 19:06): a bench run reads nothing of his real PC. resident_sight (window
    # titles, his vault notes through a sensor view), notes (vault search), eroge (the text hooker db)
    # and the Chrome/Firefox/vault/mpv paths are all off or blank for both characters. Momoka's PC sense is only
    # the env pc events (phone_account in control.env_apply). Tomoe has none at all: him_profile (built from
    # PC digests) is off for her too.
    for sec in ("resident_sight", "notes", "eroge", "vault_snoop", "receipts"):
        if isinstance(cfg.get(sec), dict):
            cfg[sec]["enabled"] = False
    if character in ("tomoe", "maria") and isinstance(cfg.get("him_profile"), dict):
        cfg["him_profile"]["enabled"] = False
    for sec, keys in (("sensors", ("vault_path", "chrome_history_path", "firefox_history_path", "torrent_backup_dir")),
                      ("eroge", ("cache_dir", "userconfig_dir")),
                      ("watching", ("player_history_path", "now_playing_path", "player_plays_path")),
                      ("recap", ("whisper_exe",))):
        for k in keys:
            if isinstance(cfg.get(sec), dict) and k in cfg[sec]:
                cfg[sec][k] = ""
    # report folders are relative to the tree root: they would be Momoka's real reports/, so they move under the run
    for sec, k in (("recap", "episodes_report_dir"), ("recap", "transcripts_report"),
                   ("watching", "plays_timeline_path"), ("dossier", "dir")):
        if isinstance(cfg.get(sec), dict) and cfg[sec].get(k):
            cfg[sec][k] = os.path.join(run_s, "data", cfg[sec][k]).replace("\\", "/")
    cfg = _move_data(cfg, run_s)
    cfg["logging"]["db_path"] = os.path.join(run_s, "save.db").replace("\\", "/")
    cfg["logging"]["out_dir"] = os.path.join(run_s, "logs").replace("\\", "/")

    out = os.path.join(run_s, "config_s.json")
    _write(out, json.dumps(cfg, ensure_ascii=False, indent=1))
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--character", required=True, choices=["momoka", "tomoe", "maria"])
    p.add_argument("--clock-start", required=True, help="YYYY-MM-DD HH:MM, Asia/Tokyo")
    a = p.parse_args(argv)
    print(build(a.run_id, a.character, a.clock_start))


if __name__ == "__main__":
    main()
