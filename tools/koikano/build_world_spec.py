"""Build characters/momoka/world/koikano_world.json (design 3.2).

    python tools/koikano/build_world_spec.py [--corpus DIR]

The places are mechanical (sim/scene.py ids, counts and a first receipt from the
record's stage state). The club, the week anchors, each cast row's week and Momoka's
own week are hand-written below, each fact with record receipts: (record id, anchor)
where the anchor is a string that occurs in that line. tools/koikano/check_world_spec.py
verifies every one. Nothing without a receipt goes in. No age, no grade, no
birthplace, no named parent (user ruling 10-23 13:29).
"""
import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from sim.scene import PLACE_BACKGROUNDS, PLACE_NOTES  # noqa: E402

DEFAULT_CORPUS = r"F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work"


def R(i, anchor=None, bg=None):
    r = {"id": i}
    if anchor:
        r["anchor"] = anchor
    if bg:
        r["bg"] = bg
    return r


def F(text, *receipts, **extra):
    d = {"text": text, "receipts": [R(*r) if isinstance(r, tuple) else r for r in receipts]}
    d.update(extra)
    return d


def slot(slot_name, place, text, *receipts):
    d = F(text, *receipts)
    d["slot"] = slot_name
    if place:
        d["place"] = place
    return d


def mechanical_places(corpus):
    num2place = {v[2:4]: k for k, v in PLACE_BACKGROUNDS.items()}
    lines = collections.Counter()
    scenes = collections.defaultdict(set)
    first = {}
    who = collections.defaultdict(collections.Counter)
    with open(os.path.join(corpus, "stage_state.jsonl"), encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            bg = ((d.get("stage") or {}).get("bg") or {}).get("id") or ""
            m = re.match(r"BG(\d\d)", bg)
            p = num2place.get(m.group(1)) if m else None
            if not p:
                continue
            lines[p] += 1
            scenes[p].add(d["scene"])
            first.setdefault(p, ("%s:%04d" % (d["scene"], d["source_line"]), "BG" + m.group(1) + "a01"))
            sp = d.get("speaker") or ""
            if sp and sp != "一悟":
                who[p][sp] += 1
    out = []
    for pid, bg in PLACE_BACKGROUNDS.items():
        out.append({
            "id": pid, "bg": bg, "note": PLACE_NOTES.get(pid, ""),
            "lines": lines[pid], "scenes": len(scenes[pid]),
            "spoken_by": [{"speaker": s, "lines": n} for s, n in who[pid].most_common(3)],
            "receipt": R(first[pid][0], None, first[pid][1]) if pid in first else None,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--out", default=os.path.join(ROOT, "characters", "momoka", "world", "koikano_world.json"))
    a = ap.parse_args()

    spec = {
        "_note": "Momoka's world spec (design 3.2): the record's own setting, 早久保学園, its club, places, week anchors and cast rows. Every fact carries record receipts (scene:line) and an anchor string that occurs in that line; tools/koikano/check_world_spec.py checks all of it. Built by tools/koikano/build_world_spec.py. The world never emits an age or a grade, never names a parent, and never writes 一悟's lines or actions (user ruling 10-23 13:29).",
        "frame": "The record's own school, 早久保学園, as the eroge has it. Her club is the theater club (演劇部), which she founded and leads.",
        "rules": {
            "age_grade": "No age and no grade is ever emitted. The record never says them as words for the cast.",
            "family": "The house, the 千代田 name and 真里亜 are in. Parents are a light background role, unnamed, with no invented detail.",
            "player": "一悟 is the player. The cast knows him as 一悟. The world never writes his lines or actions; those come only from his messages.",
            "npc": "天文部部員, 野村先生, 文化祭実行委員 and the other record NPCs are strangers without rows.",
        },
        "places": mechanical_places(a.corpus),
    }

    spec["club"] = {
        "name": "演劇部",
        "facts": [
            F("Momoka founded the theater club and has led it as president.", ("d05_01:0353", "演劇部は百花が作った")),
            F("The club is tiny: she counts it as just two people.", ("d05_01:0370", "二人だけ")),
            F("Its club room faces the literary club's room across the hall; the club room image (BG02) serves both.", ("03_01:1468", "真向かい", "BG02"), ("02_01:4984", "演劇部の部室", "BG02")),
            F("The literary club (文芸部) sits next to it; 一悟 is its president (context only, the world never acts for him).", ("01_01:0787", "文芸部の部室")),
            F("Both clubs work together on the culture festival and stay overnight at school the day before.", ("08_01:0109", "文芸部と演劇部は学校へ泊まって")),
        ],
        "room": {"place": "club_room"},
    }

    spec["anchors"] = [
        {"id": "school_day", "kind": "weekly", "place_ids": ["classroom", "hallway", "entrance", "club_room"],
         "facts": [
             F("Lessons by day, lunch at midday, club after lessons; no fixed weekday for the club in the record.", ("05_01:3993", "放課後に部室", "BG02"), ("c05_01:0281", "昼休み"), ("d03_01:0007", "部活を休んだ")),
             F("Lunch can be bought at the school shop (購買部) by the entrance.", ("02_01:1216", "購買部でお昼ごはん", "BG10"), ("01_01:4318", "購買部")),
         ]},
        {"id": "club_stop", "kind": "before_exam", "place_ids": ["hallway", "entrance"],
         "facts": [
             F("Club activity stops for the week before the midterms.", ("a05_01:0619", "中間テストの一週間前"), ("a05_01:0940", "部活動停止期間"), ("d07_01:0070", "部活動停止期間")),
             F("The same stop comes before the finals.", ("a03_01:1820", "期末テストのために部活動が停止")),
         ]},
        {"id": "exams", "kind": "rare_fixture", "place_ids": ["classroom"],
         "facts": [
             F("Midterms and finals exist, with a blank gap between them.", ("a03_01:1108", "中間テストと期末テストの間")),
             F("Momoka sits them and hopes to lose her red marks.", ("d08_01:0535", "中間テスト")),
             {"text": "Cadence: an exam week about once every 8 weeks of the sim.", "kind": "parameter",
              "basis": "The record shows both exams but gives no dates; the owner draws them rarely (design 3.2). A tuning number, not a record fact.", "value_weeks": 8},
         ]},
        {"id": "presidents_meeting", "kind": "rare_fixture", "place_ids": [],
         "facts": [
             F("A presidents' meeting (部長会議) is held on a school afternoon, after the midterms.", ("d06_01:1590", "部長会議"), ("d06_01:1392", "今日の放課後")),
             F("Club presidents otherwise meet each other only there.", ("02_01:3920", "部長会議で顔を見る")),
         ],
         "hole": "The record shows no room for the meeting; no place is fixed."},
        {"id": "weekend_at_her_house", "kind": "weekly", "place_ids": [],
         "facts": [
             F("The club gathers at Momoka's house at the weekend when there is work to do.", ("b12_01:0111", "百花ちゃんの家に集まって")),
             F("A club training camp (合宿) at her house has happened.", ("b01_01:1449", "百花ちゃん家の合宿")),
         ],
         "hole": "The record names no background for her living room; no place id is fixed for these gatherings."},
        {"id": "culture_festival", "kind": "rare_fixture", "place_ids": ["gym", "stage", "club_room"],
         "facts": [
             F("The culture festival runs two days.", ("08_01:3870", "文化祭の二日間")),
             F("The day before, both clubs stay at school for last preparations.", ("08_01:0109", "学校へ泊まって最終準備")),
         ]},
    ]

    def row(slug, name, source, week, extra=None):
        d = {"name": name, "source": source, "week": week}
        if extra:
            d.update(extra)
        return d

    rows = {}
    rows["mayu"] = row("mayu", "真優", "characters/mayu/sheet.json", [
        slot("school_day", "club_room", "Spends the whole school day in the literary club room, not in class.", ("01_01:0787", "文芸部の部室で一日を過ごす", "BG02"), ("01_01:0792", "文芸部室登校")),
        slot("morning", "twin_bedroom", "Hard to get up for school.", ("01_01:0143", "学園、行くの", "BG15")),
        slot("weekend", None, "Stays at home at weekends, keeping out of other people's sight.", ("a04_01:0426", "週末はずっと家に引きこもっている")),
        slot("bad_day", None, "Is sent home early on bad days.", ("a09_01:0558", "早退した方が良い")),
    ])
    rows["sena"] = row("sena", "千奈", "characters/sena/sheet.json", [
        slot("school_day", "club_room", "In the literary club room every day, as she says.", ("05_01:4805", "毎日のように顔を合わせている")),
        slot("after_school", "club_room", "Writes her novel in the club room after lessons.", ("b08_01:0020", "部室で小説を執筆", "BG02")),
        slot("evening", "tv_living_room", "Goes home; her home is a living room with a TV.", ("b08_01:1433", "千奈が生活してる", "BG19"), ("b05_01:0876", "家に帰ってから")),
    ])
    rows["alice"] = row("alice", "アリス", "characters/alice/sheet.json", [
        slot("school_day", "staff_room", "Student council president; works in the council room.", ("04_01:4169", "生徒会室を出た", "BG04"), ("02_01:4258", "アリス会長")),
        slot("evening", None, "Lives as a guest in Momoka's house.", ("01_01:4627", "ホームステイ")),
        slot("rounds", "gym", "Speaks to the whole school about its clubs from the gym.", ("01_01:4900", "部活動に関してとても寛容", "BG05")),
    ])
    rows["maria"] = row("maria", "真里亜", "characters/maria/sheet.json", [
        slot("school_day", "entrance", "Three days a week she works at the school shop by the entrance.", ("01_01:3496", "週に三日ほど購買部でアルバイト"), ("01_01:4318", "購買部")),
        slot("outside_shift", None, "Outside lessons and her shifts she is mostly with Momoka.", ("01_01:3505", "授業とアルバイトの時間以外は大抵百花ちゃんと一緒")),
        slot("always", None, "Momoka's maid.", ("d06_01:0484", "百花のメイド")),
    ])
    rows["chisa"] = row("chisa", "知紗", "characters/chisa/sheet.json", [
        slot("lessons", "gym", "The school's PE teacher (体育科), who also teaches health.", ("03_01:0663", "体育科の榎本"), ("01_01:4284", "保健の授業")),
        slot("school_day", "club_room", "Visits club rooms as adviser of the small clubs.", ("03_01:0669", "弱小部の総顧問"), ("07_01:1366", "いろんな部の活動を見に来た")),
        slot("lunch", "entrance", "Buys her lunch at the school shop.", ("02_01:1216", "購買部でお昼ごはん", "BG10")),
        slot("sick_bay", None, "A regular at the infirmary.", ("05_01:3677", "保健室の常連")),
    ])
    rows["hikaru"] = row("hikaru", "ひかる", "characters/hikaru/card.json", [
        slot("school_day", "classroom", "In class with 一悟; most of his lines are in the classroom.", ("01_01:3739", "クラスメイト", "BG07")),
        slot("after_school", None, "Meetings of the newspaper club after lessons.", ("02_01:0884", "新聞部で打ち合わせ")),
        slot("festival", None, "Works with the culture festival committee.", ("02_01:4098", "文化祭実行委員会")),
    ])
    spec["rows"] = rows

    spec["momoka"] = {
        "week": [
            slot("morning", "entrance", "Sleepy in the morning; she says it is her low blood pressure.", ("01_01:3403", "低血圧", "BG10")),
            slot("school_day", "classroom", "Sits out PE and goes to the infirmary when dizzy.", ("05_01:3425", "体育、見学してた", "BG07")),
            slot("after_school", "club_room", "Comes to the club room after lessons.", ("05_01:3993", "放課後に部室", "BG02")),
            slot("evening", "her_room", "Her own room is where she hosts friends and offers them pillows.", ("06_01:4223", "まくら", "BG18")),
        ],
        "family": [
            F("A big house that can host the whole club, and a karaoke machine at home.", ("b01_01:0839", "百花の家、広い"), ("b11_01:0365", "カラオケの機械")),
            F("The 千代田 family could sponsor a play.", ("04_01:1944", "千代田家が")),
            F("真里亜 is her own maid.", ("d06_01:0484", "メイド")),
            F("Relatives of the household stay overnight at times.", ("b01_01:0845", "ご親戚")),
            F("Parents appear only as a light background role, spoken of and never named.", ("03_01:2370", "パパとママ"), ("07_01:5358", "パパもママも"), kind="parent", named=False),
        ],
        "sick_days": {
            "facts": [
                F("She has been away from school a lot.", ("d06_01:0499", "たくさん学園休んだ")),
                F("Away from school she spends the time at home.", ("b06_01:1090", "家で過ごす時間の方が長かった")),
                F("A doctor looks after her.", ("d06_01:1883", "お医者さん")),
                F("At home, 真里亜 is with her outside her own work.", ("01_01:3505", "授業とアルバイトの時間以外は大抵百花ちゃんと一緒")),
            ],
            "effect": {"place": "her_room", "company": ["maria"], "club_beat": False,
                       "rule": "A sick day is a seeded draw by date; on it she is in her_room and the school beats happen without her. She learns of them only by being told."},
            "draw": {"text": "Chance of a sick day on a school day: 0.2, drawn once per date from a seed.",
                     "kind": "parameter", "p_per_school_day": 0.2, "seed": "momoka|date",
                     "basis": "The record shows absences are frequent (d06_01:0499, b06_01:1090) but gives no rate. A tuning number, not a record fact."},
        },
    }

    spec["holes"] = [
        "The record fixes no weekday for the club, no timetable and no dates for the exams.",
        "No background is named for her living room, so gatherings at her house have no place id.",
        "Ages, grades, birthdays, birthplaces and parents' names are not in the record as words and are not in this file.",
        "知紗 and ひかる have light cards (characters/chisa/card.json, characters/hikaru/card.json); the other four rows read their sheets.",
    ]

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("wrote", a.out, len(spec["places"]), "places")


if __name__ == "__main__":
    main()
