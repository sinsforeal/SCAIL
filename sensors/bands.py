"""How hard he was working, said as a band rather than as a count.

Every figure a character has ever recited about his machine came from one
function, `system_monitor.format_system_activity`, and it rounded nothing: the
keypress total, the per-category breakdown, the count and seconds of each
typing burst, the CPU and RAM percentages and the uptime in hours and minutes
all went to the account-writing role exactly as measured. Over three days the
second character's ninety-seven accounts carried a mean of thirty-eight
numerals each, and what came back out of her was "百九十三時間、機械つけっぱなし
の人だし" and "夜中の4時、起きてキー八個押して" (2026-09-05).

A band says the same thing without handing anybody a number to quote. The
thresholds are `sensors.bands.*` so they can be tuned without touching code,
and the wording lives here, once, in both languages: a caller passes the
`t(en, ja)` closure of whoever is being written for, so the resident on the
Japanese arm reads her own and the first character reads English. The mind's
language module is NOT imported here -- `sensors/` is the machine's layer and
the collector loads it, so the dependency would run the wrong way; the closure
comes down from `sim/phone.py`, which has the config.

What is NOT banded, on his instruction: the clock time a window run started
and how long it ran. She is watching him continuously and what time he got up
is hers to know.
"""


def _t_default(en, _ja):
    return en


def _pick(value, table, t):
    """The first band whose floor `value` clears, walking down."""
    for floor, en, ja in table:
        if value >= floor:
            return t(en, ja)
    return t(*table[-1][1:])


def _cfg(config, key, default):
    b = getattr(config, "bands", None)
    if b is None:
        return default
    return float(getattr(b, key, default))


def typing(config, keys, minutes, t=None):
    """How hard he was typing over the stretch, from keys per minute.

    A total on its own says nothing without the span it happened in: 1,616
    keys is a hammering half-hour and an ordinary afternoon, and the model was
    handed the total either way."""
    t = t or _t_default
    if keys <= 0:
        return ""
    rate = keys / max(1.0, float(minutes))
    table = [
        (_cfg(config, "typing_hard_per_minute", 60.0),
         "typing hard, most of the stretch", "ほとんどずっと、強く打っていた"),
        (_cfg(config, "typing_steady_per_minute", 20.0),
         "typing steadily", "こつこつ打っていた"),
        (_cfg(config, "typing_light_per_minute", 4.0),
         "typing on and off", "ときどき打っていた"),
        (0.0, "barely typing", "ほとんど打っていない"),
    ]
    return _pick(rate, table, t)


def bursts(config, spans, t=None):
    """The shape of his typing, as a count of long and short runs.

    `spans` is (keys, seconds) per burst. The old line was
    `TYPING: 17:23(8keys/9s), 17:24(259keys/66s)`, which is four clock times
    and eight figures for a fact that fits in six words."""
    t = t or _t_default
    if not spans:
        return ""
    long_floor = _cfg(config, "burst_long_seconds", 30.0)
    longs = sum(1 for _k, s in spans if float(s) >= long_floor)
    shorts = len(spans) - longs

    def count(n, one_en, one_ja, few_en, few_ja, many_en, many_ja):
        if n <= 0:
            return ""
        if n == 1:
            return t(one_en, one_ja)
        if n <= 3:
            return t(few_en, few_ja)
        return t(many_en, many_ja)

    parts = [p for p in (
        count(longs, "one long burst", "長いのが一度",
              "a couple of long bursts", "長いのが数回",
              "long bursts throughout", "長いのが何度も"),
        count(shorts, "one short one", "短いのが一度",
              "a few short ones", "短いのが数回",
              "a lot of short ones", "短いのが何度も"),
    ) if p]
    if not parts:
        return ""
    return t(" and ", "、").join(parts)


def uptime(config, seconds, t=None):
    """How long since he restarted, as a band.

    `Up 244h34m` is where "百九十三時間、機械つけっぱなしの人だし" came from. The
    fact worth having is that he does not turn it off."""
    t = t or _t_default
    days = float(seconds) / 86400.0
    table = [
        (_cfg(config, "uptime_long_days", 7.0),
         "the machine has not been restarted in over a week",
         "マシンは一週間以上、再起動されていない"),
        (_cfg(config, "uptime_days_days", 2.0),
         "the machine has been on for days",
         "マシンは何日もつけっぱなし"),
        (_cfg(config, "uptime_today_days", 0.5),
         "the machine has been on since earlier today",
         "マシンは今日の早いうちからついたまま"),
        (0.0, "the machine was restarted recently", "マシンは最近再起動された"),
    ]
    return _pick(days, table, t)


def clicks(config, n, t=None):
    """Mouse clicks, which were a bare count beside the keys."""
    t = t or _t_default
    if n <= 0:
        return ""
    table = [
        (_cfg(config, "clicks_many", 60.0), "clicking a lot", "クリックも多い"),
        (_cfg(config, "clicks_some", 10.0), "some clicking", "クリックもそこそこ"),
        (0.0, "a little clicking", "クリックは少し"),
    ]
    return _pick(float(n), table, t)
