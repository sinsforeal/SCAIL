"""Turn one of the people on the roster into a character who could run.

A person beside the first character exists today as three things: a row in the
roster (`data/cast.json`), a sheet in her own language under `prompts/cast/`,
and a file of her mechanisms (`data/cast_mechanisms/`) with a hidden type
beside it (`data/cast_types.json`, which no call may read). A character who
runs is a BUNDLE: one directory, `characters/<key>/`, holding everything that
is that person -- her sheet, the values that fill the shared prompts' holes,
her own voice and speech guide, and a manifest saying what kind of thing she
is and how she is run (`docs/bundle.md`). This tool writes that directory;
`tools/new_character.py compose <key>` turns it into her config, her prompt
directory, her row in the register, her staged launcher and her save, and
`verify <key>` says whether any of it is somebody else's.

    python tools/promote_cast.py Rena-chan --dry-run
    python tools/promote_cast.py Rena-chan --root C:/temp/bundles
    python tools/promote_cast.py Rena-chan            # into characters/rena-chan/

Two rules decide what it may write.

**Her material is her own.** Everything comes from her row, her sheet, her
mechanisms and the world's public facts -- the names on the roster, the school,
the line the trains run on. Another person's row carries that person's inside
(what they think of the first character, what their evenings are really like,
what the first character has noticed about them), and handing it to her would
give her a peer's interior for free. Her own sheet says so in as many words:
she does not know what one of them does after school and thinks she knows.

**The four letters never reach her sheet.** The type file exists for the author
and for the measurement. What is copied out of it is the sentence of behaviour
written for each axis, and every gauge baseline this tool sets carries that
sentence beside it as its reason, so a reader can argue with the number without
being told a letter.

What promotion CANNOT write is listed on the sheet under `holes`, in the
manifest under `holes`, and printed at the end of a run: her household as a
file, her map, her flat, what is going round for her, and a day of her own
beyond the week her row carries. Those are authored, and until they exist she
is a character whose boot refuses to start (`Config.PERSON_FILES`).

She keeps her row. The roster belongs to the world, not to the first character,
and the other people on it still speak to her through the row and the sheet
under `prompts/cast/` until they are promoted too.
"""
import argparse
import datetime
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import atomic  # noqa: E402
os.chdir(ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

BUNDLE_ROOT = "characters"
ROSTER = "data/cast.json"
SHEETS = "prompts/cast"
MECHANISMS = "data/cast_mechanisms"
TYPES = "data/cast_types.json"
GEOGRAPHY = "data/geography.json"


# ---------------------------------------------------------------- reading

def _load(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {} if default is None else default


def _text(path):
    try:
        with io.open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def sheet_path(key):
    """Her sheet under `prompts/cast/`, whose name is the roster key lowercased."""
    for name in (key.lower() + ".md", key + ".md"):
        p = os.path.join(SHEETS, name).replace("\\", "/")
        if os.path.exists(p):
            return p
    return ""


def sheet_sections(md):
    """The sheet's bold headings and the prose under each.

    The sheets are written as a run of `**heading.**` paragraphs, so the way she
    talks, her household and what she does not know can each be lifted whole
    without reading the rest as if it were structured."""
    out, head, buf = {}, "", []
    for line in md.splitlines():
        m = re.match(r"^\*\*(.+?)\*\*\s*$", line.strip())
        if m:
            if head:
                out[head] = "\n".join(buf).strip()
            head, buf = m.group(1).strip("。 "), []
            continue
        if head:
            buf.append(line)
    if head:
        out[head] = "\n".join(buf).strip()
    return out


# ---------------------------------------------------------------- kana, numbers

_KANA = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "を": "o", "ん": "n",
}
_YOON = {"ゃ": "ya", "ゅ": "yu", "ょ": "yo"}


def romaji(reading):
    """Hepburn for a name's kana reading, one word per space.

    Names only: no long-vowel marks and no particles, because what it is given
    is the `reading` field of a roster row, which is the name and nothing else.
    A reading it cannot resolve comes back as it went in, so a wrong guess is
    visible rather than silently English."""
    words = []
    for word in str(reading or "").split():
        out, i, gem = [], 0, False
        while i < len(word):
            ch = word[i]
            if ch == "っ":
                gem = True
                i += 1
                continue
            nxt = word[i + 1] if i + 1 < len(word) else ""
            syl = ""
            if ch in _KANA and nxt in _YOON:
                base = _KANA[ch]
                syl = (base[:-1] if base.endswith("i") else base) + _YOON[nxt]
                syl = base[0] + _YOON[nxt] if base in ("shi", "chi", "ji") else syl
                i += 2
            elif ch in _KANA:
                syl = _KANA[ch]
                i += 1
            else:
                return str(reading)
            if gem and syl:
                syl = syl[0] + syl
                gem = False
            out.append(syl)
        words.append("".join(out).capitalize())
    return " ".join(words)


_ONES = ("", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen")
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def number_word(n):
    n = int(n)
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")


_KANJI_DIGIT = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                "六": 6, "七": 7, "八": 8, "九": 9}


def kanji_number(n):
    n = int(n)
    d = "〇一二三四五六七八九"
    if n < 10:
        return d[n]
    tens, ones = divmod(n, 10)
    return ("" if tens == 1 else d[tens]) + "十" + (d[ones] if ones else "")


def _kanji_to_int(s):
    if "十" in s:
        a, _, b = s.partition("十")
        return (_KANJI_DIGIT.get(a, 1) if a else 1) * 10 + (_KANJI_DIGIT.get(b, 0) if b else 0)
    return _KANJI_DIGIT.get(s, 0)


def age_from_sheet(md):
    """Her age and the string it was read out of.

    A roster row does not carry an age; her sheet says it in her own language,
    in the first line about her, as either 「十五歳」 or 「15歳」."""
    m = re.search(r"([0-9]{1,2})\s*歳", md)
    if m:
        return int(m.group(1)), m.group(0)
    m = re.search(r"([一二三四五六七八九十]{1,3})歳", md)
    if m:
        return _kanji_to_int(m.group(1)), m.group(0)
    return 0, ""


_YEARS = [("高一", 1, "high school"), ("高二", 2, "high school"), ("高三", 3, "high school"),
          ("中一", 1, "middle school"), ("中二", 2, "middle school"), ("中三", 3, "middle school")]
_ORD = {1: "first", 2: "second", 3: "third"}


def school_year_from_sheet(md):
    """Which year she is in and which class, and the strings both came out of."""
    for token, n, level in _YEARS:
        if token in md:
            cls = ""
            m = re.search(r"\b([1-3])-([A-F])\b", md)
            if m:
                cls = ", class %s-%s" % (m.group(1), m.group(2))
            label = "%s year of %s (%s-nen)%s" % (_ORD[n], level, n, cls)
            return label, n, level, token + (m.group(0) if m else "")
    return "", 0, "", ""


def born_window(age, year_n, level, today):
    """The span her birthday must be in, and a date inside it.

    Two facts constrain it and neither gives a day. Her age today puts the
    birthday in the twelve months ending today. The Japanese school year puts a
    first-year of high school among those born between the second of April and
    the first of April of the following year, counted back from the April the
    current school year began in. The overlap is the answer, and it is a span
    of months rather than a date: the day and the month are not established by
    anything and are the author's to set."""
    lines = []
    lo = today.replace(year=today.year - age - 1) + datetime.timedelta(days=1)
    hi = today.replace(year=today.year - age)
    lines.append("age %d on %s puts the birthday in %s..%s"
                 % (age, today.isoformat(), lo.isoformat(), hi.isoformat()))
    if year_n:
        # the school year that is running today began in April: this April if
        # the month is April or later, the previous one if not
        ay = today.year if today.month >= 4 else today.year - 1
        # she entered in the April `year_n - 1` school years ago, having turned
        # the entry age between the second of April and the first of April of
        # the school year before that one
        entry_age = {"high school": 15, "middle school": 12}[level]
        entered = ay - (year_n - 1)
        s_lo = datetime.date(entered - entry_age - 1, 4, 2)
        s_hi = datetime.date(entered - entry_age, 4, 1)
        lines.append("the %s year of %s in the school year that began April %d means she entered "
                     "April %d, and that intake was born %s..%s"
                     % (_ORD[year_n], level, ay, entered, s_lo.isoformat(), s_hi.isoformat()))
        lo, hi = max(lo, s_lo), min(hi, s_hi)
    if lo > hi:
        lines.append("the two do not overlap: the age and the school year disagree, and the age wins")
        lo = today.replace(year=today.year - age - 1) + datetime.timedelta(days=1)
        hi = today.replace(year=today.year - age)
    born = lo + datetime.timedelta(days=(hi - lo).days // 2)
    lines.append("overlap %s..%s; the day and the month are established by nothing, so the middle "
                 "of the span is written and it is the author's to overrule" % (lo.isoformat(), hi.isoformat()))
    return born, lines


# ---------------------------------------------------------------- temperament

# What one pole of one axis does to a gauge, as a move off the mechanism's own
# baseline. Every move here is the behaviour sentence in the type file turned
# into a number, and the sentence is written onto the sheet beside the number:
# somebody who speaks first and keeps speaking runs warmer and is bored sooner;
# somebody who decides by who will be pleased and takes a short answer
# personally needs more answering; somebody who fixes the hour and treats it as
# settled leaves less unsaid. The numbers are a starting point and the author's
# to retune -- what the tool guarantees is that they came from a stated
# behaviour rather than from the first character's sheet.
AXIS_MOVES = {
    "E": {"energy": 15, "boredom": 10, "loneliness": -5},
    "I": {"energy": -10, "boredom": -5, "loneliness": 5},
    "S": {"curiosity": -10, "anxiety": -5},
    "N": {"curiosity": 15, "anxiety": 5},
    "T": {"validation_craving": -15, "guilt": -5, "awkwardness": -5},
    "F": {"validation_craving": 15, "guilt": 5, "awkwardness": 5},
    "J": {"anxiety": 5, "unsaid": -10, "pride": 5},
    "P": {"anxiety": -5, "unsaid": 10, "pride": -5},
}
AXES = ("EI", "SN", "TF", "JP")


def temperament(type_block, base_gauges):
    """Her gauge baselines and, per gauge, the behaviour they were written from.

    Returns (baselines, basis). The letters go no further than this function."""
    letters = str((type_block or {}).get("type") or "")
    axes = (type_block or {}).get("axes") or {}
    moves, why = {}, {}
    for i, axis in enumerate(AXES):
        if i >= len(letters):
            continue
        pole = letters[i]
        line = str(axes.get(axis) or "").strip()
        for gauge, delta in AXIS_MOVES.get(pole, {}).items():
            moves[gauge] = moves.get(gauge, 0) + delta
            if line:
                why.setdefault(gauge, []).append((delta, line))
    baselines, basis = {}, {}
    for gauge, delta in sorted(moves.items()):
        if not delta or gauge not in base_gauges:
            continue
        start = float(base_gauges[gauge].get("baseline", 0))
        value = max(0, min(100, start + delta))
        if value == start:
            continue
        baselines[gauge] = int(value)
        basis[gauge] = " / ".join("%+d from: %s" % (d, ln) for d, ln in why.get(gauge, []))
    return baselines, basis


# ---------------------------------------------------------------- the person

_ROLE_WORDS = {"母": "her mother", "父": "her father", "兄": "her older brother",
               "姉": "her older sister", "妹": "her little sister", "弟": "her little brother"}


def split_ja(row):
    """A roster row's family and given names in kanji.

    The row's own aliases carry both halves -- one is a prefix of the full name
    and another is a suffix -- so the split is read rather than guessed. A row
    with no such alias falls back to two characters of family name, which is
    right for every name on this roster and wrong for a one- or
    three-character family name."""
    ja = str((row or {}).get("ja") or "")
    if not ja:
        return "", ""
    aliases = [a for a in ((row or {}).get("aliases") or []) if a and a != ja]
    fam = next((a for a in aliases if ja.startswith(a) and len(a) < len(ja)), "")
    giv = next((a for a in aliases if ja.endswith(a) and len(a) < len(ja)), "")
    if fam and giv and len(fam) + len(giv) == len(ja):
        return fam, giv
    if giv:
        return ja[:len(ja) - len(giv)], giv
    if fam:
        return fam, ja[len(fam):]
    return ja[:2], ja[2:] or ja


class Person(object):
    """Everything the writers below need, read once out of her own material."""

    def __init__(self, key, world="tokyo", slug=""):
        self.key = key
        # The roster key is what the world calls her and carries whatever the
        # first character calls her by ("Rena-chan"); the short name is what
        # every file of a character who runs is named after, and an honorific
        # in a config filename and a scheduled task name is the roster's
        # business leaking into the operator's. `--slug` is how the author
        # says which one, and the roster key is still the default.
        self.slug = re.sub(r"[^a-z0-9_-]+", "-", (slug or key).lower()).strip("-")
        self.world = world
        cast = _load(ROSTER)
        people = cast.get("people") or {}
        if key not in people:
            raise SystemExit("[promote] %s is not on the roster (%s): %s"
                             % (key, ROSTER, ", ".join(sorted(k for k in people if k != "him"))))
        self.row = people[key]
        self.owner_key = next((k for k in cast if k not in ("_comment", "people")), "")
        self.owner = cast.get(self.owner_key) or {}
        # The roster's own owner is not one of its `people`, so without this she
        # would be promoted with the one person she talks to most missing from
        # her sheet and from every example in her prompts. She is filed under
        # the name SHE uses for her.
        # The name she is filed under is the one the owner's block gives
        # itself (`key`), which is also the name the promoted character's
        # roster resolves her by (`sim/roster.py`): the two must agree or her
        # fills name somebody her process has never heard of.
        self.owner_display = str(self.owner.get("key") or self.owner.get("name") or "") or next(
            (k for k in (self.row.get("calls") or {}) if k.lower() == self.owner_key.lower()),
            self.owner_key.capitalize())
        self.people = dict(people)
        if self.owner_key:
            self.people[self.owner_display] = dict(self.owner)
        self.sheet_md_path = sheet_path(key)
        self.sheet_md = _text(self.sheet_md_path)
        self.sections = sheet_sections(self.sheet_md)
        self.mech_path = os.path.join(MECHANISMS, key + ".json").replace("\\", "/")
        self.mech = _load(self.mech_path)
        self.type = (_load(TYPES).get("types") or {}).get(key) or {}
        self.geo = _load(GEOGRAPHY)

        self.ja = str(self.row.get("ja") or "")
        self.reading = str(self.row.get("reading") or "")
        fam_r, _, giv_r = self.reading.partition(" ")
        self.family_en = romaji(fam_r)
        self.given_en = romaji(giv_r) if giv_r else romaji(fam_r)
        self.full_en = (self.family_en + " " + self.given_en).strip()
        self.family_ja, self.given_ja = self._split_ja()
        self.age, self.age_src = age_from_sheet(self.sheet_md)
        self.year_label, self.year_n, self.level, self.year_src = school_year_from_sheet(self.sheet_md)
        self.born, self.born_lines = (None, [])
        if self.age:
            self.born, self.born_lines = born_window(
                self.age, self.year_n, self.level, datetime.date.today())
        self.calls = self.row.get("calls") or {}
        self.week = self.row.get("week") or {}
        self.stance = self.row.get("stance") or {}
        self.household = self._household()
        self.peers = [k for k in self.calls if k in self.people]
        self.home_area = str(self.week.get("home") or "").split(",")[0].split(";")[0].strip()
        self.school_area = self._school_area()
        self.train_line = self._train_line()
        self.year_short = ("%s-year %s" % (_ORD[self.year_n], self.level)) if self.year_n else ""
        self.city_ja = self._city_ja()
        self.city_en = self._city_en()

    # -- small readers -------------------------------------------------

    def _split_ja(self):
        return split_ja(self.row)

    def _household(self):
        """Who lives with her, from the household paragraph of her own sheet.

        Prose is the only place a roster row carries this, and only the roles
        stated as 「兄は慶太」 are taken: a role, a name, and nothing inferred."""
        out = []
        block = ""
        for head, body in self.sections.items():
            if "家" in head and "話" not in head:
                block = body
                break
        for m in re.finditer(r"(母|父|兄|姉|妹|弟)は([一-龥ぁ-んァ-ヶ]{1,4})[、,。]", block):
            out.append({"relation": m.group(1), "name_ja": m.group(2),
                        "english": _ROLE_WORDS.get(m.group(1), m.group(1))})
        return out

    def _school_area(self):
        if str(self.row.get("school") or "") != "same":
            return ""
        addr = ((self.geo.get("school") or {}).get("address_en") or "")
        return addr.split(" ")[0].rstrip(",") if addr else ""

    def _train_line(self):
        lines = ((self.geo.get("station") or {}).get("lines") or [])
        return lines[0].split(" ")[0] if lines else ""

    def _city_en(self):
        """The city, off the world's map rather than written here: the last
        part of her own address. A tool that writes one city's name into every
        character it promotes is the same fault as a default that is one
        person's file."""
        addr = str((self.geo.get("home") or {}).get("address_en") or "")
        part = [x.strip() for x in addr.split(",") if x.strip()]
        if not part:
            return ""
        return re.sub(r"\s*\d[\d-]*$", "", part[-1]).strip()

    def _city_ja(self):
        """The city in Japanese, off the world's map, for the values she is
        addressed in. Her ward has no Japanese form anywhere in her material,
        and a romanised ward inside a Japanese sentence is the tool inventing."""
        m = re.search(r"([一-龥]{2,3})[都道府県]", ((self.geo.get("home") or {}).get("address_ja") or ""))
        return m.group(1) if m else ""

    def mechanisms(self, cls=None, freq=None):
        out = []
        for m in (self.mech.get("mechanisms") or []):
            if cls and m.get("class") != cls:
                continue
            if freq and m.get("frequency") != freq:
                continue
            out.append(m)
        return out

    def variations(self, n):
        out = []
        for m in self.mechanisms():
            for v in (m.get("variation") or []):
                if v not in out:
                    out.append(v)
        return out[:n]

    def fixtures(self):
        """(day, what, start, end) for every fixture her week names."""
        out = []
        for day, items in sorted((self.week.get("fixtures") or {}).items()):
            for it in items:
                out.append((day, str(it.get("what") or ""), str(it.get("start") or ""),
                            str(it.get("end") or "")))
        return out

    def twists(self, n):
        out = []
        for row in (self.week.get("twists") or []):
            text = str(row[1] if isinstance(row, (list, tuple)) and len(row) > 1 else row)
            text = re.sub(r"^CANCEL:\s*", "", text).strip()
            if text:
                out.append(text)
        return out[:n]

    def peer_name(self, i, fallback=""):
        return self.peers[i] if i < len(self.peers) else fallback


# ---------------------------------------------------------------- the layout

class Layout(object):
    """Where each piece of the bundle goes, and what compose will make of it.

    Everything this tool writes is inside `characters/<slug>/`. With `--root`
    pointed somewhere else, the config, the save and the prompt directory that
    compose would make go inside that directory too, so a proof run is a whole
    character under one path that can be read and thrown away, and nothing
    live is touched."""

    def __init__(self, slug, root):
        d = root.replace("\\", "/").rstrip("/")
        self.root = d
        self.scratch = os.path.abspath(d) != os.path.abspath(BUNDLE_ROOT)
        self.bundle = "%s/%s" % (d, slug)
        self.sheet = self.bundle + "/sheet.json"
        self.fills = self.bundle + "/fills.json"
        self.manifest = self.bundle + "/bundle.json"
        self.prompts = self.bundle + "/prompts"
        self.bible = self.prompts + "/bible.md"
        self.style = self.prompts + "/style.md"
        # the three files promotion cannot write. They are named in the
        # manifest so her config points at them and her boot refuses until
        # they exist, rather than leaving a hole nothing reports.
        self.household = self.bundle + "/household.json"
        self.zeitgeist = self.bundle + "/zeitgeist.json"
        self.map = self.bundle + "/map.json"
        self.home = self.bundle + "/home.json"
        # what `tools/new_character.py compose` makes from the bundle
        if self.scratch:
            self.config = "%s/config_%s.json" % (d, slug)
            self.db = "%s/%s.db" % (d, slug)
            self.prompts_dir = "%s/prompts_%s" % (d, slug)
            self.launcher = ""
        else:
            self.config = "config_%s.json" % slug
            self.db = "data/%s.db" % slug
            self.prompts_dir = "prompts_%s" % slug
            self.launcher = "%s.cmd" % slug


# ---------------------------------------------------------------- the sheet

def sheet(p, layout):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    base = _base_gauges()
    baselines, basis = temperament(p.type, base)
    people = {}
    for key in sorted(p.people):
        if key == p.key:
            continue
        if key == "him":
            people["him"] = {
                "who": "the User, whom she has heard about and has never met",
                "what_she_thinks": str((p.stance or {}).get("about_him") or ""),
                "_source": "the stance on her roster row",
            }
            continue
        entry = {"key": key, "name_ja": str((p.people[key] or {}).get("ja") or "")}
        if key in p.calls:
            entry["she_calls_them"] = p.calls[key]
            entry["_source"] = "the `calls` block of her roster row"
        else:
            entry["she_calls_them"] = ""
            entry["_source"] = ("on the roster and not in her `calls`: no form of address is "
                                "established, and nothing about this person is copied across")
        people[key] = entry
    out = {
        "_note": ("Generated by tools/promote_cast.py from her roster row, her sheet in her own "
                  "language, her mechanisms file and the behaviour lines of her type. Nothing here "
                  "was taken from another person's row: a peer's note and stance are that person's "
                  "inside and the first character's view of them."),
        "_generated": {
            "tool": "tools/promote_cast.py",
            "when": now,
            "sources": {
                "roster row": "%s people[%r]" % (ROSTER, p.key),
                "sheet": p.sheet_md_path,
                "mechanisms": p.mech_path,
                "behaviour lines": "%s types[%r].axes (the letters are NOT copied here)" % (TYPES, p.key),
                "the world's map": GEOGRAPHY,
            },
        },
        "id": p.slug,
        "name": {
            "family": p.family_en,
            "given": p.given_en,
            "full": p.full_en,
            "japanese": p.ja,
            "reading": p.reading,
            "how_she_is_addressed": _addressed(p),
            "pronouns": "she/her",
            "aliases_ja": [a for a in (p.row.get("aliases") or []) if re.search(r"[^\x00-\x7f]", a)],
        },
        "age": p.age,
        "born": p.born.isoformat() if p.born else "",
        "_born_basis": p.born_lines,
        "school_year": p.year_label,
        "origin": {
            "from": "",
            "_from_why": "not established: her row and her sheet say where she lives, not where she is from",
            "dialect": _dialect(p),
        },
        "place": {
            "lives": p.home_area,
            "_lives_source": str(p.week.get("home") or ""),
            "school_area": p.school_area,
            "line": p.train_line,
            "geography_file": GEOGRAPHY,
            "_geography_why": ("the world's map, not hers: it holds the first character's flat and "
                               "the school they both go to. Her own address is a hole."),
        },
        "register": {
            "language": "Japanese, Tokyo standard",
            "first_person": str(p.row.get("first_person") or ""),
            "speech": p.sections.get("話し方", ""),
            "voice_line": str(p.row.get("voice") or ""),
            "_source": "the `first_person` and `voice` fields of her row, and the 話し方 section of her sheet",
        },
        "people": people,
        "premise": {
            "_note": "what the first character is to her, as her own row states it",
            "the_first_character": str((p.stance or {}).get("about_her") or ""),
            "her_part_in_the_group": str(p.row.get("role") or ""),
            "what_she_does_not_know": p.sections.get("知らないこと", ""),
        },
        "temperament": {
            "_note": ("Gauge baselines written from the behaviour stated for each axis of her type. "
                      "The letters themselves are never copied here: what is beside each number is "
                      "the sentence the number came from, so a reader can argue with it."),
            "gauge_baselines": baselines,
            "gauge_basis": basis,
        },
        "mechanisms": {
            "file": p.mech_path,
            "count": len(p.mech.get("mechanisms") or []),
            "drivers": [d.get("id", "") for d in (p.mech.get("drivers") or [])],
            "_note": ("Her mechanisms reach the calls where she speaks as somebody else's cast "
                      "member. They do not yet reach the role that writes her own words: that is "
                      "on the list of what she still lacks."),
        },
        "roster": {
            "cast_file": ROSTER,
            "key": p.key,
            "_note": ("She keeps her row and her sheet under prompts/cast/. The roster is the "
                      "world's, and the people who have not been promoted still speak to her "
                      "through it."),
        },
        "existence": _existence(p),
        "holes": _holes(p, layout),
    }
    return out


def _addressed(p):
    forms = []
    for other in p.people.values():
        c = (other or {}).get("calls") or {}
        if p.key in c and c[p.key] not in forms:
            forms.append(c[p.key])
    return ", ".join(forms)


def _dialect(p):
    speech = p.sections.get("話し方", "")
    if "方言は使わない" in speech or "標準語" in speech:
        return "none: 標準語 only, as her sheet's 話し方 section states"
    return ""


def _existence(p):
    return {
        "_note": ("What kind of thing she is. Each answer names what on her own row or sheet "
                  "settles it; nothing here is inherited from the character whose roster she is on."),
        "embodied": True,
        "_embodied_why": ("her row gives her a week in a real city: school hours, fixtures with "
                          "times, a walk to a station, a curfew and a phone that gets taken away."),
        "in_world": True,
        "_in_world_why": ("she is on the roster of a world that exists (%s), at the same school "
                          "(her row's `school` reads \"same\") and on the same line." % ROSTER),
        "sees_him": "none",
        "_sees_him_why": ("nothing on her row or her sheet gives her any sight of his machine. "
                          "What she has of him is what she has been told, which her row records "
                          "as a stance and not as a feed."),
        "has_account": False,
        "_has_account_why": "no account of her own is named anywhere in her material.",
        "with_him": "none",
        "_with_him_why": ("she is promoted for her friend's circle, not for him: no chat with him, "
                          "nothing felt or expected of him, and his phone does not list her."),
    }


def household_rows(p):
    """The rows in the world's roster that are HER household.

    They stay on the world's roster so that the owner's process can resolve
    them, and the promoted character's own cast file is written from them. In
    the owner's roster their meters are the OWNER's, on people she has never
    met, so they read zero -- and copied across, the zeros say the promoted
    girl is a stranger to the two people she lives with, which is what her save
    held for a day (`docs/seamless-additions-plan.md` step 3)."""
    people = (_load(ROSTER) or {}).get("people") or {}
    return {k: v for k, v in people.items() if str(v.get("family") or "") == p.key}


def flat_household(p):
    """Those of them whose meters are zero with nothing saying that was
    decided."""
    return {k: v for k, v in household_rows(p).items()
            if str(v.get("numbers") or "").lower() != "unset"
            and not any(float(v.get(f) or 0) for f in ("closeness", "standing", "tension"))}


def _holes(p, layout):
    out = [
        "Her household as a file (%s): her sheet names her people in prose and nothing writes the "
        "figures the director and the day's briefs read." % layout.household,
        "Her map (`world.geography_file`, and her config leaves it EMPTY on purpose): no "
        "address, no station, no walk to it, no ward. The world's map holds the OWNER's home "
        "and her line's notes, and pointing a second character at it printed the owner's "
        "address to her day planner under the heading HER MAP. Her boot refuses until she has "
        "one (`Config.PERSON_FILES`). The school and the ward's public places are the same "
        "places and are copied into hers, saying so on each of them.",
        "Her own day beyond the week on her row: school hours, %d fixture(s), an after-school "
        "habit, a curfew and %d twist(s). A character who runs plans a day from more than that."
        % (len(p.fixtures()), len(p.week.get("twists") or [])),
        "What she believes about herself and about him, and how each person in her world may "
        "sound: her config leaves all three blank, which every reader takes as \"she has decided "
        "nothing yet\". She starts with no picture of him at all.",
        "Her bible and her style guide are seeded from her own sheet and her own voice line. Both "
        "are the author's to finish before she says anything.",
    ]
    fam = household_rows(p)
    if fam:
        out.append("What she holds toward the %d person/people in her own household: their rows "
                   "in the world's roster carry the OWNER's meters, and her own cast file needs "
                   "HERS -- closeness, how she thinks she ranks in their eyes, and tension, for "
                   "%s." % (len(fam), ", ".join(sorted(fam))))
    if not p.household:
        out.append("Nobody at home: her sheet has no household paragraph this tool could read.")
    return out


# ---------------------------------------------------------------- the fills

_SHARED_JA_RULES = (
    "気持ちは物ではない。大きさも幅も温度もないし、胸や喉に座ったりしない。何かを感じたときに書くのは、"
    "それについて何をしたか——行動であって、気持ちの絵ではない。\n\n"
    "状況を物として名指さない。隙間・沈黙・距離・重さ・穴 に自分を入れない。起きていることはそのまま書く。"
)


def fills(p, layout):
    """Every hole the shared prompts leave, filled from her own material.

    A value is her row, her sheet, her mechanisms, or a shape with a name in it
    -- never a fact out of somebody else's row. The register values are in
    Japanese because she is addressed in Japanese; the rest are in the language
    of the mechanism prompt they land in."""
    n = p.age
    word, kanji = number_word(n), kanji_number(n)
    where = ", ".join(x for x in (p.home_area, "Tokyo") if x)
    peer1 = p.peer_name(0, "one of them")
    peer2 = p.peer_name(1, peer1)
    peer3 = p.peer_name(2, peer2)
    voice = str(p.row.get("voice") or "")
    first_person = str(p.row.get("first_person") or "")
    speech = p.sections.get("話し方", "")
    mech = p.mechanisms()
    top = mech[0] if mech else {}
    # the one about what a flat answer costs, by its own name rather than by its
    # id: an id match on "answer" caught the mechanism about sending three in a
    # row and put its trigger where the thing that settles her belongs
    reaction = next((m for m in mech if "reaction" in str(m.get("name", "")).lower()), top)
    fixtures = p.fixtures()
    fix = fixtures[0] if fixtures else ("", "", "", "")
    fix2 = fixtures[1] if len(fixtures) > 1 else fix
    twists = p.twists(4)
    after = str(p.week.get("after_school") or "")
    after_places = after.split(";")[-1].strip() if ";" in after else after
    after_first = _short(after_places)
    curfew = str(p.week.get("curfew") or "")
    phone = str(p.week.get("phone") or "")
    sib = next((h for h in p.household if h["relation"] in "兄姉妹弟"), None)
    mother = next((h for h in p.household if h["relation"] == "母"), None)
    home_words = ", ".join(h["english"] for h in p.household) or "the people she lives with"

    def q(*items):
        return ", ".join('"%s"' % i for i in items if i)

    f = {
        "_note": ("What fills the character-shaped holes in the shared mechanism prompts for %s. "
                  "Generated by tools/promote_cast.py from her roster row, her sheet and her "
                  "mechanisms. Every example is hers or is a shape with a name in it: nothing was "
                  "read out of another person's row, because a peer's note and stance are that "
                  "person's inside." % p.full_en),
        "_seeds": ("The six register values (the head-voice rules and lines, the diary's and the "
                   "scene director's register, the voice an opening approach is written in) are "
                   "assembled from her one authored 話し方 paragraph, her `voice` line and the "
                   "project's own two rules about feelings and situations. They are a starting "
                   "point and the author's to finish."),
        "id": p.slug,

        "NAME": p.given_en,
        "NAME_JA": p.given_ja,
        "FULLNAME": p.full_en,
        "RECORD_NAME": p.ja,
        "HER_NAME_FORMS": " / ".join(dict.fromkeys(
            [a for a in (p.row.get("aliases") or []) if re.search(r"[^\x00-\x7f]", a)]
            + [re.split(r"[ (（]", x)[0] for x in _addressed(p).split(", ") if x])),
        "WHO": "%s, %d, Tokyo" % (p.full_en, n),
        "WHO_IN": "%s, %d, in Tokyo" % (p.full_en, n),
        "WHO_SHORT": "%s, %d" % (p.full_en, n),
        "WHO_PAREN": "%s (%d, Tokyo)" % (p.full_en, n),
        "WHO_ORIGIN": "%s, %d, %s" % (p.full_en, n, where),
        "WHO_ORIGIN_B": "%s (%d, %s)" % (p.full_en, n, where),
        "WHO_SCHOOL": "%s, %d, %s, %s" % (p.full_en, n, p.year_short, where),
        "WHO_SCHOOL_B": "%s, %d, %s, %s" % (p.full_en, n, p.year_short, where),
        "WHO_CAST_DAY": "%s %s, %d, %s" % (p.family_en, p.ja, n, where),
        "AGE_WORD": word,
        "AGE_WORD_CAP": word.capitalize(),
        "AGE_BARE": "She is %s." % word,
        "AGE_KIND": "a %s year old" % word,
        "AGE_KIND_B": "a %s-year-old" % word,
        "AGE_KIND_GIRL": "a %s-year-old girl" % word,
        "HOME_AREA": p.home_area,
        "SCHOOL_AREA": p.school_area,
        "TRAIN_LINE": p.train_line,
        "CITY": p.city_en,
        "AGE_N": str(n),
        "SCHOOL_LEVEL": p.year_short,
        # the places a day is made of, off her own map: two she is named at,
        # then the three anybody her age has
        "DAY_PLACES": ", ".join([x for x in _day_places(p)] +
                                ["karaoke", "purikura", "someone's house"]),
        # her timeline, which she has not got: she is promoted without an
        # account, and the value is here because a token with no value is a
        # printed hole in whatever prompt reaches for it
        "FEED_KINDS": "Most of these are Japanese accounts: anime art, manga panels, "
                      "screenshots, photos of food and places, memes, merchandise, news images.",

        "HEADVOICE_JA": "これは%sの頭の中なので、日本語で書く。%s"
                        % (p.given_ja, "、".join(x for x in (kanji + "歳", _jp_year(p), p.city_ja) if x) + "。"),
        "HEADVOICE_RULES": "\n\n".join(x for x in (speech, first_person, _SHARED_JA_RULES) if x),
        "HEADVOICE_LINE": voice,
        "HEADVOICE_LINE_BRIEF": voice.split("。")[0] + "。" if voice else "",
        "DIARY_REGISTER": "\n\n".join(x for x in (
            "常体。日記なので誰にも見せない。敬語もエッセイの形も要らない。", speech, first_person) if x),
        "DIRECTOR_REGISTER": "\n\n".join(x for x in (
            "%s、%d歳。書くものは全部日本語の話し言葉で、書き言葉の形にしない。" % (p.ja, n),
            speech, first_person, _SHARED_JA_RULES) if x),
        "APPROACH_VOICE": "\n".join(x for x in (
            voice, "一〜二文。ときどき断片。作り込まない。カウンセラーみたいにしない。") if x),

        "A_PERSON": peer1,
        "A_PERSON_BARE": peer1,
        "ICK_CIRCLE_WHO": "%s or %s" % (peer1, peer2),
        "CAST_NAMES_JA": ", ".join(
            ["%s／%s" % (_short_ja(p, p.key), p.given_ja)]
            + ["%s／%s" % (p.calls[k], _given_ja(p.people[k])) for k in p.peers]),
        "BOYS_SAY_ORE": _ore_line(p),
        "CAST_ROLES": ", ".join(["a friend"] * len(p.peers) + [h["english"] for h in p.household])
                      or "a friend",
        "SCHEDULE_CAST": _schedule_cast(p, home_words),

        "SKIM_READER": "a teenager" if n and n < 20 else "somebody in a hurry",
        "NIGHT_ROOM_EG": ("%s's room" % sib["english"].replace("her ", "her ")) if sib else "the room next door",

        "STATE_SOOTHE_EG": "Settles her: %s. Does not: %s."
                           % (reaction.get("suppressor", ""), reaction.get("trigger", "")),
        "REFLECT_SMALL_EG": ", ".join(m.get("trigger", "") for m in mech[:3]),
        "RUPTURE_WHAT_EG": q(_sentence(reaction.get("trigger", ""))),
        "BREAKS_IF_EG": q("if he mentions %s" % (_short(fix[1]) or after_first or "the plan")),
        "AFFECTION_WHY_EG": q(*p.variations(3)),
        "COMMIT_UNSEEN_EG": 'Homework, being on time, "not %s"'
                            % _gerund(mech[1].get("name", "") if len(mech) > 1 else top.get("name", "")),
        "COMMIT_ATTEND_EG": ", ".join(x for x in [_short(f2[1]) for f2 in fixtures[:3]] if x)
                            or after_first,
        "COMMIT_WHAT_EG": q("be at %s" % (after_first or _short(fix[1]))),
        "COMMIT_WHAT_EG2": q(_short(fix[1]), _short(fix2[1])),
        "COMMIT_TELL_EG": q("I'll tell you what %s says" % peer1, "I'll let you know what time it is"),
        "COMMIT_HIM_EG": q("tell him whether the plan happened"),
        "COMMIT_HIM_EG2": q("tell him when she gets home", "send him what %s sent" % peer1),

        "DIRECTOR_EVENT_EG": ", ".join(_short(t) for t in twists[:4]),
        "DIRECTOR_THREAD_EG": ", ".join(x for x in (_short(fix[1]), curfew.split(",")[0].strip(),
                                                    after.split(";")[0].strip()) if x),
        "DIRECTOR_TEXTURE_EG": ", ".join(x for x in (
            [_short(f2[1]) for f2 in fixtures[:2]] + [after_places]) if x),
        "ZEITGEIST_NOT_EG": 'NOT "%s sends it to the group", NOT "%s brings it up at home"'
                            % (peer1, (sib or mother or {"english": "somebody"})["english"]),

        "ARC_EXAMPLES": " ".join(x for x in (
            "%s half somewhere else whenever they are together." % peer1,
            "An evening she cannot fill.",
            (_sentence(_short(twists[0])) + ".") if twists else "",
            "%s answering later than she used to." % peer2) if x),
        "ARC_BEAT_EG": '"%s" is a beat; "she realises she is losing them" is not'
                       % _short(twists[0] if twists else "her phone is taken at dinner"),
        "ARC_ARRIVE_EG": "; ".join(_short(t) for t in twists[:2]),

        "CAST_DAY_BEAT_EG": q("%s is pinning down a time and wants it answered" % peer1,
                              "%s has not answered since this morning and is not saying why" % peer2),
        "CAST_DAY_FIX_EG": q("%s -- fixed by her in the group chat at 19:12"
                             % _fixture_line(fix, after)),
        "CAST_DAY_FAMILY_EG": ", ".join(x for x in (
            "%s about the time" % (mother["english"] if mother else "the one who texts her"),
            ("%s in the doorway" % sib["english"]) if sib else "") if x),
        "CAST_DAY_ARC_EG": "a plan forming for the weekend, %s drifting" % peer1,
        "CAST_DAY_AT_EG": _fixture_line(fix, after),

        "EVENTS_REFUSE_EG": "Saying no to %s twice in a fortnight is not free, and she knows it." % peer1,
        "EVENTS_WHY_EG": q("%s has already told the group she is coming." % peer1),
        "EVENTS_PUSHER_EG": "%s asking gently is not the same as %s" % (peer3, peer1),

        "COMPARE_GLANCE_EG": "the glance at %s's bag on the train" % peer2,
        "COMPARE_NOTICE_EG": "the noticing that %s was answered first" % peer2,
        "COMPARE_BEHIND_EG": "%s already knowing, her catching up" % peer1,

        "ORBIT_OWNER_EG": q(_short(twists[0]) if twists else "she is stuck at home and resents it today"),
        "ORBIT_MERGE_EG": "%s's mother is not hers" % peer1,

        "TIMELINE_FACT_EG": q(phone.split(";")[-1].strip() or phone, curfew.split(",")[0].strip(),
                              _fixture_line(fix, after)),
        "TIMELINE_MEM_EG": q(twists[0] if twists else ""),
        "TIMELINE_CLAIM_EG": q("she said the meetup is at %s" % (fix[2] or "10:00"),
                               "she said she would be there"),
        "COHERENCE_EG": q("LINE with %s 16:18" % (_ja_of(p, peer2) or peer2),
                          "in person with %s 13:22" % (_ja_of(p, peer1) or peer1)),
    }
    return f


def _day_places(p):
    """Up to two places round her SCHOOL that a plan for a day may reach for.

    Her school's area and nothing nearer: the world's map is the owner's, and
    her own home area is one of the holes promotion cannot fill, so taking a
    shopping street off that map would hand her the owner's street as a place
    she goes. Where she lives goes into this value when her own map exists."""
    out = []
    for name in list(((p.geo.get("school_area") or {}).get("places") or {}))[:2]:
        name = str(name).strip()
        if name and name not in out:
            out.append(name)
    return out


def _sentence(text):
    text = (text or "").strip()
    return text[:1].upper() + text[1:] if text else ""


def _short(text):
    """The head of an authored line: a roster row writes a fixture or a twist as
    the thing and then a clause about it ("her little sister's swimming, she
    gets dragged"), and an example list wants the thing."""
    return re.split(r"[;,]", str(text or ""))[0].strip()


def _gerund(name):
    """A mechanism's name as something she could promise not to do.

    The names are written in the third person ("sends the next one before the
    last one is answered"), and a promise reads as a gerund."""
    words = str(name or "").split()
    if not words:
        return ""
    v = words[0]
    if v.endswith("s") and not v.endswith("ss"):
        v = v[:-1]
    v = (v[:-1] + "ing") if v.endswith("e") else (v + "ing")
    return " ".join([v] + words[1:])


def _jp_year(p):
    """Her school year as her own sheet writes it (高一), and nothing if it does
    not: a year label in English inside a Japanese sentence is the tool talking."""
    for token, _n, _lvl in _YEARS:
        if token in p.sheet_md:
            return token
    return ""


def _short_ja(p, key):
    for other in p.people.values():
        c = (other or {}).get("calls") or {}
        if key in c:
            return re.split(r"[ (（]", c[key])[0]
    return p.given_ja


def _given_ja(row):
    return split_ja(row)[1]


def _ja_of(p, key):
    return str((p.people.get(key) or {}).get("ja") or "")


def _ore_line(p):
    """Who on the roster writes 俺, from the roster's own `first_person` fields."""
    names = [_given_ja(v) for v in p.people.values() if "俺" in str((v or {}).get("first_person") or "")]
    return ("と".join(names) + "だけが「俺」") if names else ""


def _schedule_cast(p, home_words):
    bits = []
    if p.household:
        bits.append("At home: " + ", ".join(
            "%s %s" % (h["english"], h["name_ja"]) for h in p.household) + ".")
    if p.peers:
        bits.append("Friends: " + ", ".join(
            "%s (%s)" % (k, p.calls[k]) for k in p.peers) + ".")
    curfew = str(p.week.get("curfew") or "")
    if curfew:
        bits.append("Curfew: %s." % curfew)
    return " ".join(bits) or home_words


def _fixture_line(fix, after):
    day, what, start, end = fix
    what = _short(what)
    if not what:
        return after.split(";")[0].strip()
    when = (" at %s" % start) if start else ""
    on = (" on %s" % {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
                      "fri": "Friday", "sat": "Saturday", "sun": "Sunday"}.get(day, day)) if day else ""
    return what + when + on


# ---------------------------------------------------------------- the manifest
#
# The machine's own settings -- the provider and its key, the hub, the voice
# vendor's tool, the sensors and the feeds -- are not written here at all any
# more. They are `characters/machine.json`, and `tools/new_character.py
# compose` merges them under the library's defaults for every character, so
# there is one statement of what belongs to the machine rather than a second
# list here that could drift from it.


def manifest(p, layout, world_id):
    """Her bundle's own manifest: what kind of thing she is, how she is run,
    which of her files answer which config key, and every key her config needs
    that the library's defaults do not give her.

    `tools/new_character.py compose` turns this into her config, and nothing
    else does: this tool no longer writes a config at all, so there is one
    statement of what a character's config is made of rather than two that
    drift."""
    live = _load("config.json")
    over = overrides(p, layout, world_id)
    # The world's own files, which are the world's and not the first
    # character's: the places, the school calendar, the national holidays,
    # what the ward puts on and the directory the world file lives in. Two
    # processes in one world reading two of any of these is the fault this
    # copies them to avoid.
    #
    # The MAP is not one of them, and used to be. It carries the owner's flat,
    # her station, her walk to it and her line's notes, and it was printed to
    # the promoted character's day planner under the heading HER MAP: her
    # address was the owner's, and the train notes told her that a girl with
    # her own name gets on at her own station when they have agreed to meet.
    # The school and the ward's public places are the same places and are
    # copied INTO her map, which says so on each of them.
    for key in ("places_file", "school_calendar_file", "holidays_file",
                "local_events_file", "shared_dir"):
        if (live.get("world") or {}).get(key):
            over["world"][key] = live["world"][key]
    # what the people around her do, and the types they were written from:
    # both the world's, both read by the same section as the roster, and both
    # required while that section is on (`Config.PERSON_FILES`)
    for key in ("mechanisms_dir", "types_file"):
        if (live.get("cast") or {}).get(key):
            over.setdefault("cast", {})[key] = live["cast"][key]
    over["character"].setdefault("existence", {}).update(_existence(p))
    over.setdefault("models", {}).setdefault("persona", {})["prompt"] = \
        layout.prompts_dir + "/bible.md"
    over["character"]["style_prompt"] = layout.prompts_dir + "/style.md"
    over["character"]["style_ja_prompt"] = layout.prompts_dir + "/style.md"

    row = registry_row(p, layout)
    files = {"world.character_file": "sheet.json",
             "character.neutral_file": "fills.json",
             "world.household_file": "household.json",
             "world.geography_file": "map.json",
             "world.zeitgeist_file": "zeitgeist.json",
             "world.home_file": "home.json"}
    holes = sorted(os.path.basename(getattr(layout, a))
                   for a in ("household", "map", "zeitgeist", "home")
                   if not os.path.exists(getattr(layout, a)))
    return dict(row, **{
        "_note": "Everything that is this character and nothing that is not, written by "
                 "tools/promote_cast.py from her roster row, her sheet and her mechanisms. "
                 "`python tools/new_character.py compose %s` makes her config, her prompt "
                 "directory, her register row, her staged launcher and her save from it; "
                 "`verify %s` says whether any of it is somebody else's. The files under "
                 "`holes` are authored and her boot refuses to start without them." % (p.slug, p.slug),
        "world": {"id": world_id, "owner": False},
        "prompts_dir": layout.prompts_dir,
        "prompts_generated": True,
        # who runs is the operator's decision, so a promoted character is not
        # in the register until he puts her there
        "registered": False,
        "files": files,
        "blank": [],
        "holes": holes,
        "config_overrides": over,
    })


def overrides(p, layout, world_id):
    """Only what is about HER. Everything absent from here is the mechanism and
    is shared with every other character, and every consequence of what kind of
    thing she is, is left to `Config` to apply at load."""
    return {
        "world": {},
        # one world, one writer. She reads what the first character's process
        # writes and writes nothing back.
        "world_shared": {"enabled": True, "id": world_id, "owner": False},
        "character": {
            "name": p.given_en,
            "program": "tomoe",
            "writes_to_him": "japanese",
            "instruction_language": "japanese",
            "name_ja": p.ja,
            "reading_ja": p.reading,
            # the roster is the world's: her row and everybody's sheet stay
            # where they are, because the people who have not been promoted
            # still speak to her through them
            "cast_file": ROSTER,
            "cast_sheets_dir": SHEETS,
            # Blank, not a path to a file nobody wrote. What she has decided
            # about him, about herself and about how each person in her world
            # may sound is authored, and the readers of all three take an empty
            # path as "she has decided nothing yet" and a path naming a file
            # that is not on disk as a wrong path, which stops a boot
            # (`sim/model_of_him.py:_seed`, `sim/voicecheck.py`).
            "voice_rules_file": "",
            "beliefs_file": "",
            "self_beliefs_file": "",
        },
        # her own draw, or her cast planner rolls the first character's twists
        "cast": {"seed": p.slug},
        # She starts at zero with him: nothing on her row is a meter of a
        # private relationship, and what her row does carry is a stance.
        "primitives": {"enabled": True},
        "stances": {"enabled": True},
        # No voice: no voice id exists for her on this machine, and the shared
        # vendor config names the first character's, so a blank id here would
        # have her synthesised in it (`tools/isolation.py:effective_voice`).
        "tts": {"enabled": False, "voice_id": "", "always": False, "on_demand": False,
                "minimax_config_path": "", "minimax_script_path": ""},
        # no reaction set exists for her, and a character key naming somebody
        # else publishes another character's face as her mood
        "reactions": {"enabled": False, "character": ""},
        # her chat is her own: a second Telegram bot would need its own token
        "telegram": {"bot_token": "", "chat_id": ""},
    }


# ---------------------------------------------------------------- her prompts

def bible(p):
    """Her bible, seeded from the sheet she already has.

    The sheet under `prompts/cast/` is her, in her own language, written to be
    read by the call where she speaks. It is the only authored statement of who
    she is that exists, so it is where her bible starts."""
    head = ("<!-- Seeded by tools/promote_cast.py from %s, which is the sheet the calls where she "
            "speaks as a cast member already read. It is a starting point: a character who runs "
            "needs her own bible, and this is the material it is written from, not the finished "
            "thing. -->\n\n" % p.sheet_md_path)
    return head + p.sheet_md


def style(p):
    """Her speech guide: the 話し方 paragraph of her sheet, her first-person
    line and her `voice` line, over the project's own two rules about how a
    feeling and a situation may be written."""
    parts = ["<!-- Seeded by tools/promote_cast.py from the 話し方 section of %s and the `voice` "
             "and `first_person` fields of her roster row. The two closing rules are the "
             "project's and are the same for every character. -->" % p.sheet_md_path,
             "# %s — 話し方" % p.ja]
    # the sheet's paragraph and the row's line are two statements of the same
    # thing, the sheet's the fuller: only one of them goes in
    parts.append(p.sections.get("話し方") or str(p.row.get("voice") or ""))
    if p.row.get("first_person"):
        parts.append(str(p.row["first_person"]))
    parts.append(_SHARED_JA_RULES)
    return "\n\n".join(parts) + "\n"


PORTED_WHY = {
    "bible.md": ("the shared one is the first character herself, from her name down. Nothing in it "
                 "is a mechanism."),
    "style.md": ("the shared speech guide is written for a girl who renders casual Japanese into "
                 "English and slips into Hakata-ben when she is tired. Her row says Tokyo standard, "
                 "no dialect, and Japanese to everybody including him."),
}


# ---------------------------------------------------------------- launcher, registry

def registry_row(p, layout):
    return {
        "key": p.slug,
        "name": p.full_en,
        "hub_id": p.slug.replace("-", ""),
        "config": layout.config,
        "db": layout.db,
        "program": "tomoe",
        "launcher": layout.launcher,
        "task": "SCAIL_%s" % p.slug.replace("-", "_"),
        "match": r"scail\.py.*config_%s" % re.escape(p.slug).replace("\\-", "-"),
    }


# ---------------------------------------------------------------- running it

def _base_gauges():
    from config import DEFAULTS
    return DEFAULTS["state"]["gauges"]


def _named_paths(man, layout):
    """Every file the manifest names that promotion does not write."""
    return ["%s/%s" % (layout.bundle, n) for n in man.get("holes") or []]


def _write(path, text):
    # a bundle under characters/<key>/ is read by a running process
    atomic.replace(path, text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("key", help="the roster key, as data/cast.json spells it")
    ap.add_argument("--root", default=BUNDLE_ROOT,
                    help="where the bundle goes; a directory of your own keeps the whole "
                         "character, and everything compose would make from her, inside it")
    ap.add_argument("--world", default="tokyo", help="the world id she reads")
    ap.add_argument("--slug", default="",
                    help="the short name every file of hers is named after; the roster key "
                         "lowercased by default, which carries whatever the first character "
                         "calls her by")
    ap.add_argument("--dry-run", action="store_true", help="print everything, write nothing")
    args = ap.parse_args(argv)

    p = Person(args.key, world=args.world, slug=args.slug)
    layout = Layout(p.slug, args.root)

    flat = flat_household(p)
    if flat:
        print("REFUSED: %d row(s) of her own household in %s carry closeness 0, standing 0 and "
              "tension 0: %s" % (len(flat), ROSTER, ", ".join(sorted(flat))))
        print("  Those are the OWNER's meters on people she has never met, and this tool's "
              "character would be written from them. Either give each row the numbers SHE holds, "
              "or mark it \"numbers\": \"unset\" and write hers into her own cast file.")
        return 1

    the_sheet = sheet(p, layout)
    the_fills = fills(p, layout)
    the_manifest = manifest(p, layout, args.world)
    row = registry_row(p, layout)

    print("promoting %s -> %s (%s), world %s, into %s"
          % (p.key, p.full_en, p.ja, args.world, layout.bundle))
    print("  read: %s, %s, %s, the behaviour lines of her type" % (ROSTER, p.sheet_md_path, p.mech_path))
    print("  age %s from %r; %s from %r" % (p.age, p.age_src, p.year_label, p.year_src))
    for line in p.born_lines:
        print("    born: " + line)
    print("  born %s" % the_sheet["born"])
    print("  %d gauge baseline(s) written from behaviour: %s"
          % (len(the_sheet["temperament"]["gauge_baselines"]),
             ", ".join("%s %s" % (k, v) for k, v in sorted(
                 the_sheet["temperament"]["gauge_baselines"].items()))))
    print("  %d token(s) filled" % len([k for k in the_fills if k.isupper()]))

    if args.dry_run:
        print("\n---- %s ----" % layout.sheet)
        print(json.dumps(the_sheet, ensure_ascii=False, indent=1))
        print("\n---- %s ----" % layout.fills)
        print(json.dumps(the_fills, ensure_ascii=False, indent=1))
        print("\n---- %s (only what is hers; the machine's settings and every secret are "
              "merged in memory by compose and never written into a bundle) ----" % layout.manifest)
        print(json.dumps(the_manifest, ensure_ascii=False, indent=1))
        print("\n---- %s ----" % layout.bible)
        print("\n".join(bible(p).splitlines()[:6]) + "\n  ... %d line(s)" % len(bible(p).splitlines()))
        print("\n---- %s ----" % layout.style)
        print(style(p))
        print("---- the row compose would add to characters.json once `registered` is true "
              "(who runs is the operator's decision) ----")
        print(json.dumps(row, ensure_ascii=False, indent=1))
        print("\n  nothing was written")
        return 0

    _write(layout.sheet, json.dumps(the_sheet, ensure_ascii=False, indent=1))
    _write(layout.fills, json.dumps(the_fills, ensure_ascii=False, indent=1))
    _write(layout.bible, bible(p))
    _write(layout.style, style(p))
    # the manifest last, so a run that died half way leaves a bundle with no
    # manifest -- which compose refuses -- rather than one that claims to be
    # whole
    the_manifest = manifest(p, layout, args.world)
    _write(layout.manifest, json.dumps(the_manifest, ensure_ascii=False, indent=1) + "\n")
    for path in (layout.sheet, layout.fills, layout.bible, layout.style, layout.manifest):
        print("  wrote %s" % path)
    print("  ported %d prompt(s), one per shared file her own material contradicts:" % len(PORTED_WHY))
    for name, why in sorted(PORTED_WHY.items()):
        print("    %-10s %s" % (name, why))
    missing = _named_paths(the_manifest, layout)
    if missing:
        print("  %d file(s) her manifest names that promotion cannot write, and her boot "
              "refuses to start without:" % len(missing))
        for m in missing:
            print("    %s" % m)
    print("  she still lacks:")
    for h in the_sheet["holes"]:
        print("    - %s" % h)
    print("  then, to make her config, her prompt directory and her save from the bundle:")
    print("    python tools/new_character.py compose %s%s"
          % (p.slug, "" if not layout.scratch else " --root " + layout.root))
    print("    python tools/new_character.py verify  %s%s"
          % (p.slug, "" if not layout.scratch else " --root " + layout.root))
    print("  her manifest says `registered: false`, so compose leaves characters.json and the "
          "launcher alone. Her row, when you want her to run:")
    print("    " + json.dumps(row, ensure_ascii=False))
    # Who she is on her own roster is not something this tool can write for
    # her: it is two fields in the world's cast file, and until they are there
    # her process reads her own row as a stranger with her own name and the
    # girl whose world she is in as nobody at all. She ran that way for a day
    # (docs/shared-world.md §7).
    print("  in %s, by hand, before she boots:" % ROSTER)
    print("    - %r gets \"agent\": %r, so her own row folds into herself on her roster"
          % (p.key, row["hub_id"]))
    print("    - the `self` block keeps \"key\", \"role_id\", \"role\" and \"agent\", so the girl "
          "whose world she reads is a person on it")
    print("  and her fills (%s) must say HER household, HER ward and HER friends before her "
          "first schedule is written: a day planned under somebody else's fills stays in her "
          "save and drives her week." % layout.fills)
    return 0


if __name__ == "__main__":
    sys.exit(main())
