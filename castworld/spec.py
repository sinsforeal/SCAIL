"""World spec loader and the code-side checks (design 3.2, 7).

Spec file: characters/momoka/world/koikano_world.json. Shape coded against design 3.2:

    {"her": {"key": "momoka", "name": "百花", "home_place": "her_room", "sick_rate": 0.08},
     "places": {"<place id>": {"ja": "部室", "receipt": "d05_01:0353"}},
     "cast": {"<key>": {"name": "千奈", "aliases": [], "light": false, "attention": 50,
                        "voice": ["..."], "calls_her": "百花",
                        "week": {"mon": ["放課後 club_room 稽古"], ...}, "receipt": "..."}},
     "anchors": [{"weekday": "fri", "time": "15:30", "place": "meeting_room", "who": ["mayu"], "gist": "..."}]}

The loader is tolerant: weekday lists may be strings or lists, cast may be a list with a "key" field.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "characters" / "momoka" / "world" / "koikano_world.json"
MAIN_SPEC_PATH = Path("F:/REPS2/SCAILV4/characters/momoka/world/koikano_world.json")

HER_KEY = "momoka"
PROTAGONIST_IDS = {"ichigo", "一悟", "him", "player", "protagonist"}
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# No age and no grade is ever emitted (User 10-23 13:29). Checked on every beat and every cast line.
AGE_GRADE = re.compile(
    r"[0-9０-９一二三四五六七八九十]+\s*(?:歳|才|年生)|(?:小|中|高|大)[1-3１-３一二三]\b|"
    r"(?:小学|中学|高校|高等学校|大学)[0-9０-９一二三]?年?生?|[0-9０-９一二三]\s*年\s*[A-Za-zＡ-Ｚ0-9０-９]?\s*組|"
    r"年齢|学年|新入生|\bage\b|\d+\s*years?\s*old|grade\s*\d|(?:first|second|third)[- ]year",
    re.I)
# a parent named or given invented detail is out (design 7.2): only a light unnamed background role
NAMED_PARENT = re.compile(r"(?:お?父|お?母|パパ|ママ|父親|母親|お父さん|お母さん)(?:の|は|が)?[^。]{0,4}[ぁ-んァ-ヶ一-龥]{2,}(?:さん|氏)")


class SpecError(ValueError):
    pass


def has_age_grade(text: str) -> bool:
    return bool(AGE_GRADE.search(str(text or "")))


def load(path=None) -> dict:
    p = Path(path) if path else (SPEC_PATH if SPEC_PATH.exists() else MAIN_SPEC_PATH)
    if not p.exists():
        raise SpecError(f"world spec not found: {p}")
    return normalize(json.loads(p.read_text(encoding="utf-8")))


PLACE_JA = {
    "club_room": "部室", "meeting_room": "会議室", "staff_room": "職員室", "gym": "体育館", "stage": "舞台",
    "classroom": "教室", "hallway": "廊下", "pool": "プール", "entrance": "昇降口", "living_room": "リビング",
    "his_room": "一悟の部屋", "her_room": "百花の部屋", "city_night": "夜の街", "lounge": "ラウンジ", "sky": "空",
    "cafe": "カフェ", "school_gate": "校門", "mansion_gate": "屋敷の門", "building_entrance": "建物の入口",
    "academy_corridor": "学園の廊下", "city_street": "街の通り", "convenience_store": "コンビニ",
    "modern_building": "ビル", "theater": "劇場", "traditional_house": "日本家屋", "family_room": "居間",
    "tv_living_room": "テレビのある居間", "twin_bedroom": "双子の寝室",
}
# slots in the record's rows -> weekdays they apply to (the record fixes no timetable, design 3.2 holes)
SLOT_DAYS = {"school_day": ("mon", "tue", "wed", "thu", "fri"), "weekend": ("sat", "sun"),
             "always": WEEKDAYS}
SLOT_TIME = {"morning": "朝", "lunch": "昼休み", "after_school": "放課後", "evening": "夕方", "rounds": "見回り",
             "outside_shift": "バイト以外の時間", "sick_bay": "保健室", "bad_day": "調子の悪い日", "festival": "文化祭"}


def _from_record(raw: dict) -> dict:
    """The real spec (rows with slot-keyed week facts, places as a list, sick draw under momoka) -> legacy shape."""
    places = {}
    for p in raw.get("places") or []:
        places[p["id"]] = {"ja": PLACE_JA.get(p["id"], p["id"]), "receipt": p.get("receipt"), "note": p.get("note")}
    cast = {}
    for key, r in (raw.get("rows") or {}).items():
        week = {wd: [] for wd in WEEKDAYS}
        for f in r.get("week") or []:
            slot = f.get("slot", "")
            days = SLOT_DAYS.get(slot, WEEKDAYS if slot in SLOT_TIME else ())
            where = f" @{f['place']}" if f.get("place") else ""
            line = f"[{SLOT_TIME.get(slot, slot)}{where}] {f.get('text', '')}"
            for wd in days:
                week[wd].append(line)
        cast[key] = {"name": r.get("name", key), "week": week, "light": r.get("source", "").endswith("card.json"),
                     "voice": [str(x.get("text", x)) for x in (r.get("speech") or [])][:4]}
    her_week = (raw.get("momoka") or {}).get("week") or []
    draw = ((raw.get("momoka") or {}).get("sick_days") or {}).get("draw") or {}
    return {"her": {"key": HER_KEY, "name": "百花", "home_place": "her_room",
                    "sick_rate": float(draw.get("p_per_school_day", 0.08)), "sick_school_days_only": True,
                    "week": her_week},
            "places": places, "cast": cast, "anchors": [], "npc": []}


def normalize(raw: dict) -> dict:
    if "rows" in raw and isinstance(raw.get("places"), list):
        raw = _from_record(raw)
    her = {"key": HER_KEY, "name": "百花", "home_place": "her_room", "sick_rate": 0.08, **(raw.get("her") or {})}
    places = {}
    for pid, v in (raw.get("places") or {}).items():
        places[str(pid)] = v if isinstance(v, dict) else {"ja": str(v)}
        places[str(pid)].setdefault("ja", str(pid))
    cast_raw = raw.get("cast") or {}
    if isinstance(cast_raw, list):
        cast_raw = {c["key"]: c for c in cast_raw}
    cast = {}
    for key, c in cast_raw.items():
        c = dict(c)
        week = {}
        for wd, v in (c.get("week") or {}).items():
            week[str(wd).lower()[:3]] = [v] if isinstance(v, str) else list(v)
        c["week"] = week
        c.setdefault("name", key)
        c.setdefault("aliases", [])
        c.setdefault("voice", [])
        c.setdefault("attention", 40 if c.get("light") else 55)
        cast[str(key)] = c
    if not places or not cast:
        raise SpecError("world spec needs places and cast")
    if her["home_place"] not in places:
        raise SpecError(f"her home_place {her['home_place']!r} is not a place id")
    for k in cast:
        if k == her["key"] or k in PROTAGONIST_IDS:
            raise SpecError(f"cast key {k!r} is reserved")
    return {"her": her, "places": places, "cast": cast, "anchors": list(raw.get("anchors") or []),
            "npc": list(raw.get("npc") or [])}


def place_ja(spec: dict, pid: str) -> str:
    return (spec["places"].get(pid) or {}).get("ja", pid)


def validate_beat(spec: dict, b: dict):
    """Return (clean beat, None) or (None, reason). Unknown ids are dropped, never repaired (design 7 risks)."""
    if not isinstance(b, dict):
        return None, "not an object"
    pid = str(b.get("place") or "").strip()
    if pid not in spec["places"]:
        return None, f"unknown place id {pid!r}"
    pres = b.get("present")
    if not isinstance(pres, list) or not pres:
        return None, "present missing"
    pres = [str(x).strip() for x in pres]
    valid = set(spec["cast"]) | {spec["her"]["key"]}
    for x in pres:
        if x.lower() in PROTAGONIST_IDS or x in PROTAGONIST_IDS:
            return None, f"protagonist id {x!r} in present (the world never writes him)"
        if x not in valid:
            return None, f"unknown roster id {x!r}"
    pres = list(dict.fromkeys(pres))
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", str(b.get("time") or ""))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None, f"bad time {b.get('time')!r}"
    gist = str(b.get("gist") or "").strip()
    if not gist:
        return None, "empty gist"
    tags = [str(t).strip() for t in (b.get("tags") or []) if str(t).strip()]
    for txt in [gist] + tags:
        if has_age_grade(txt):
            return None, "age or grade in text"
    if "一悟" in gist and re.search(r"一悟[はがも](?:[^。]{0,12})(?:言|答|笑|頷|うなず|手を|立ち|座|歩)", gist):
        return None, "gist writes 一悟's words or actions"
    return {"time": f"{int(m.group(1)):02d}:{m.group(2)}", "place": pid, "present": pres,
            "kind": (str(b.get("kind") or "home").strip() or "home")[:20], "tags": tags[:6], "gist": gist[:200]}, None
