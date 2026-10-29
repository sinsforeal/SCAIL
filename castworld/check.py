"""Output check for cast lines (design 7 risks: cast lines pass the same kind of check as hers before they enter her
thread). Same classes as the bench's output check (separators, tags, stamps, template junk), plus the world's own
rules: no age or grade, no line by 一悟, speaker must be present and in the cast. No model call."""
from __future__ import annotations

import re

from .spec import PROTAGONIST_IDS, has_age_grade

STAMP = re.compile(r"\[(?:[A-Z][a-z]{2}\s)?\d{1,2}[:/]\d{2}[^\]]*\]|\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}")
TAGS = re.compile(r"</?[A-Za-z][^>]*>|<｜|ds_safety|Valid channels:")
JA = re.compile(r"[぀-ヿ一-鿿]")
MAX_LEN = 90


def clean_line(text: str) -> str:
    t = str(text or "").strip()
    t = re.sub(r"^[「『]|[」』]$", "", t).strip()
    return t


def check_line(who: str, text: str, present: list, cast: set):
    """(text, None) when the line may enter her thread, else (None, reason)."""
    if who in PROTAGONIST_IDS or who.lower() in PROTAGONIST_IDS:
        return None, "line by the protagonist"
    if who not in cast or who not in present:
        return None, f"speaker {who!r} not a present cast member"
    t = clean_line(text)
    if not t:
        return None, "empty"
    if "\n" in t or "|||" in t:
        return None, "separator or newline"
    if TAGS.search(t):
        return None, "tag or template junk"
    if STAMP.search(t):
        return None, "time stamp in the line"
    if len(t) > MAX_LEN:
        return None, "too long"
    if not JA.search(t):
        return None, "not Japanese"
    if has_age_grade(t):
        return None, "age or grade"
    return t, None
