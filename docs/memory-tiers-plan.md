<!-- doc: reference -->
# Memory tiers: what rides in her thread as the record ages

A plan, his call (2026-09-04), to be built after a week of watching the
current two-tier shape so the tiers are set against measured card sizes.
What is true now is in PROJECT.md §5 (the thread) and §12.13 (the cards);
dated notes go to HISTORY.md.

## 1. What exists

Two tiers by clock (`thread.verbatim_hours` 168, `max_age_hours` 720,
`sim/thread.py _window`): seven days of record verbatim in the thread,
both rooms, then every day back to thirty as its cards (`sim/cards.py`,
one card per conversation, the exact lines kept for the last
`episodes.anchors_days`), then nothing in the thread at all. Past that a
conversation is reachable only through her memories, her facts and the
meaning-based recall, which can bring a whole exchange back into the
thread when the moment reaches for it. The store keeps everything; a tier
decides only what rides by default.

Measured 2026-09-04 on the first character's save: a day's record 4k to
7k tokens, a recent day's cards 1.2k to 3.9k (exact lines kept), an older
day's cards about 1k. So seven days verbatim is 30k to 50k, twenty-three
days of cards 25k to 35k once the record is that old, and the prompt stops
growing at about thirty days.

## 2. The curve to build

Five tiers, each a form the compile writes and the thread build walks:

| age of the record | rides as | cost |
|---|---|---|
| days 1 to 7 | verbatim, both rooms | 30k to 50k |
| days 8 to 10 | the day's cards with their exact lines | 1k to 4k a day |
| days 11 to 30 | the day's cards, shape only | about 1k a day |
| days 31 to 90 | one card per WEEK, compiled from the day cards on the Monday after: what mattered, what changed between the days, what was left hanging | 300 to 500 each |
| days 91 to 365 | one card per MONTH, compiled from the week cards on the 1st | about 300 each |
| past a year | nothing in the thread | 0 |

A year of history then costs the verbatim week plus about 40k, and the
prompt stops growing after twelve months.

## 3. Two exceptions that make it memory rather than an archive

- **Rehearsal.** A card that recall brought back into the thread has its
  age reset partway (a configurable fraction), the way the facts'
  forgetting curve already treats a fact met again (`last_seen`). A thing
  she keeps returning to stays in its fuller form longer.
- **Flashbulb.** A day whose gauges at the time crossed an arousal
  threshold -- a rupture, a spiral, a first -- keeps its full card past the
  tier that would compress it, up to a cap in days. The state store already
  holds the gauges per tick, so the compile can read them when it writes
  the day's cards and mark the card.

## 4. Where it goes in the code

- **Config.** `thread.tiers`, a list of `{until_days, form}` rows replacing
  the two hour values (kept as aliases for one release), plus
  `episodes.rehearsal_fraction` and `episodes.flashbulb_arousal` /
  `flashbulb_keep_days`. The tier table must be checked at boot the way the
  gauge table is: contiguous, ascending, one `verbatim` row first.
- **The compile** (`sim/timeline.py`, `sim/cards.py`): two more stages on
  the same nightly clock. On the first day of a week, write the week card
  for the week that ended from its day cards; on the first day of a month,
  the month card from its week cards. Both go through the same card writer
  role with their own prompt, and both keep the ids of the cards they were
  made from, so recall can descend from a month to a week to a day to the
  exact lines.
- **The thread build** (`sim/thread.py`): `_window` returns the tier
  boundaries instead of two cuts; `build` walks them oldest first, rendering
  each span in its form; the byte-stability rule holds because every
  boundary sits on a midnight and moves once a day.
- **Recall** (`sim/recall.py`): unchanged in principle; it already
  re-injects an exchange whole at the end of the thread. It gains the
  rehearsal write-back.
- **The ops view and `/context`**: one row per tier with the days and the
  tokens it costs.

## 5. What to measure first

A week of the current shape, then: the size of an older day's cards once
the exact lines are gone (the 1k figure is an estimate from two days of
cards); how often recall reaches past thirty days at all (if never, the
month tier can wait); and whether a week card written by the model from
seven day cards keeps the unresolved threads, which is the one thing it
must not lose.
