"""The railway a character actually uses, and what it refuses.

Every character in a world has one file that says where she lives and how she
travels (`world.geography_file`): her home station, the lines that station is
on, the stops her commute passes through. Nothing outside her day planner read
it, so the role that decides which national story reaches her was handed her
taste sheet, the date and the headlines, and nothing at all about where she
gets on a train. Asked why a crowding story at a station forty minutes away
was relevant to her, it wrote her a commute: a line that does not serve her
station, to a class that is nowhere near it. Nobody could have caught it,
because nothing downstream knows what she rides.

Two halves, and the second is only needed because the first can still be
ignored:

  `block(config)`   what her own file says, as a paragraph for a prompt that
                    is judging what reaches her. Empty for a character with no
                    world, whose geography path the load blanks.

  `unowned(text, config)`
                    the first railway line or station named in a sentence that
                    her own file does not give her, or None. A relevance line
                    that names one is dropped and logged; the story it was
                    attached to is kept, because the story was true and only
                    the reason was invented.

Nobody is named here: the paths come from the config and the names come out of
the file at the end of them.
"""
import json
import os
import re

# "Seibu Ikebukuro line (her commute, inbound to Ikebukuro)" -> the name, and
# the note in brackets thrown away.
_NOTE = re.compile(r"[（(].*?[)）]")
# a railway line as it is written in English and in Japanese
_EN_LINE = re.compile(r"\b((?:[A-Z][\w'\-]*)(?:[ \-](?:[A-Z][\w'\-]*|line|Line)){0,3}?)[ \-][Ll]ine\b")
# the run before 線 / 駅 stops at a kana particle, because a name does not
# contain one: "大雨で埼京線" is 埼京, not 大雨で埼京
_JA_LINE = re.compile(r"([一-鿿ァ-ヺA-Za-z][一-鿿ァ-ヺA-Za-z]{1,9})線")
# ...and a station, where it says so
_EN_STATION = re.compile(r"\b((?:[A-Z][\w'\-]*)(?:[ \-][A-Z][\w'\-]*){0,3})[ \-][Ss]tation\b")
_JA_STATION = re.compile(r"([一-鿿ァ-ヺA-Za-z][一-鿿ァ-ヺA-Za-z]{1,9})駅")


def _key(name):
    """One spelling for a name written five ways. The suffix that says what
    kind of thing it is carries no information here -- a line is already known
    to be a line by where the name was found -- so it comes off both
    languages, and so do the spaces, the dots and the hyphens."""
    s = _NOTE.sub("", str(name or "")).strip().lower()
    if s.startswith("the "):
        s = s[4:]
    for tail in (" line", "-line", "線", " station", "-station", "駅"):
        while s.endswith(tail):
            s = s[: -len(tail)].strip()
    return re.sub(r"[\s\.・\-]+", "", s)


def _map(config):
    path = str(getattr(getattr(config, "world", None), "geography_file", "") or "")
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _strings(value, out):
    """Every string anywhere under a value. The map files are hand-written and
    a station list has turned up under three different keys already, so this
    reads the shape rather than a path into it."""
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, list):
        for v in value:
            _strings(v, out)
    elif isinstance(value, dict):
        for k, v in value.items():
            if not str(k).startswith("_"):
                _strings(v, out)


def _trains(config, key):
    v = getattr(getattr(config, "trains", None), key, None)
    return [str(x).strip() for x in (v or []) if str(x).strip()]


def nearby(config):
    """The lines that run near her and are not hers to ride. Her own train
    watch already keeps the distinction -- the ones she is on carry one
    salience and the ones she only hears about carry another -- so this is
    that list under a name a reader can use, not a second one to disagree
    with it."""
    return _trains(config, "nearby_lines")


def ground(config):
    """(the lines she rides, the stations she uses), as display names.

    Two sources, because neither is complete on its own: her map file gives
    the station her home names, the lines that station is on and the stops her
    commute passes through, in whatever language it was written in, and her
    train watch gives the lines she is actually on in Japanese. A line she
    rides written one way in one file and another way in the other is hers
    under both spellings, which is the whole reason for reading both.

    A character whose world was blanked has an empty answer, and every reader
    of this treats an empty answer as "cannot judge" rather than as "she uses
    none of it"."""
    d = _map(config)
    st = d.get("station") if isinstance(d.get("station"), dict) else {}
    home = d.get("home") if isinstance(d.get("home"), dict) else {}
    com = d.get("commute") if isinstance(d.get("commute"), dict) else {}
    lines = [_NOTE.sub("", str(x)).strip() for x in (st.get("lines") or []) if str(x).strip()]
    lines += _trains(config, "her_lines")
    stations = []
    for v in (home.get("station"), st.get("name"), st.get("name_ja")):
        if str(v or "").strip():
            stations.append(str(v).strip())
    _strings(com.get("stops_inbound"), stations)
    _strings(com.get("stops_outbound"), stations)
    # de-duplicate on the normalised key, keeping the first spelling
    def uniq(rows):
        seen, out = set(), []
        for r in rows:
            k = _key(r)
            if k and k not in seen:
                seen.add(k)
                out.append(r.strip())
        return out
    return uniq(lines), uniq(stations)


def block(config):
    """What her own file says about how she travels, for a prompt deciding
    which of the day's news would reach her at all. Empty when there is no
    file to read, so a character with no world is told nothing rather than
    told a blank."""
    lines, stations = ground(config)
    if not lines and not stations:
        return ""
    d = _map(config)
    com = d.get("commute") if isinstance(d.get("commute"), dict) else {}
    route = str(com.get("route") or "").strip()
    out = ["HOW SHE ACTUALLY TRAVELS (from her own map and her own train watch; this is the "
           "whole of the railway she has):"]
    if stations:
        out.append("  stations she uses: " + ", ".join(stations))
    if lines:
        out.append("  lines she rides: " + ", ".join(lines))
    near = nearby(config)
    if near:
        out.append("  lines that run near her that she does NOT ride, and would only hear about: "
                   + ", ".join(near))
    if route:
        out.append("  her daily route: " + route)
    out.append("  A reason that puts her on any other line, or through any station that is not "
               "listed above, is invented and will be thrown away. If a travel story does not "
               "touch her own railway, say how it reaches her some other way -- it was on the "
               "news, the group is talking about it -- or leave the reason out.")
    return "\n".join(out)


# a sentence claiming the railway it names is part of her own routine
_ROUTINE = re.compile(
    r"\b(she takes|she rides|she uses|she gets on|she catches|she goes through|she passes through|"
    r"she changes at|takes the|her commute|her route|her line|her station|her own line|"
    r"on her way|to get to|gets? off at)\b", re.I)


def refuse(text, config):
    """Why a sentence about how a story reaches her cannot stand, as (the name
    it got wrong, the reason in plain words), or None when it is fine.

    Two ways to be wrong, and both are things her own files can settle:

      * it names a railway that is nowhere in her world -- not a line she
        rides, not a line her train watch keeps an eye on, not a station on
        her map. Nothing in her life touches it.
      * it names a line that does run near her, and says she is on it. Near
        her is not the same as hers, and this is the one that got written: a
        crowding story two wards away was made relevant by giving her a
        commute along it to a class that is nowhere near it.

    None when there is nothing to judge against: a character whose world was
    blanked has no map and no train watch, and refusing on no evidence is
    worse than letting the sentence through."""
    lines, stations = ground(config)
    if not lines and not stations:
        return None
    rides = {_key(x) for x in lines}
    near = {_key(x) for x in nearby(config)}
    uses = {_key(x) for x in stations}
    claimed = bool(_ROUTINE.search(str(text or "")))
    for rx, what, have in ((_EN_LINE, "line", rides), (_JA_LINE, "line", rides),
                           (_EN_STATION, "station", uses), (_JA_STATION, "station", uses)):
        for m in rx.finditer(str(text or "")):
            name = m.group(1).strip()
            k = _key(name)
            if not k or k in have:
                continue
            if name.lower().startswith("the "):
                name = name[4:]
            if what == "line" and k in near:
                if claimed:
                    return name, "it runs near her and she is not on it"
                continue
            return name, ("it is not one of the lines she rides" if what == "line"
                          else "it is not a station on her map")
    return None
