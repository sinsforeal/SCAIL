"""Every play his media player has FINISHED, and the timeline of them he reads.

The player's history log says a file opened and nothing else. That is enough
to know an episode happened and useless for the only question that follows:
did he sit through it. A file opened for four seconds and a file watched to
the last frame leave the identical line, so an open was fetched, digested,
paid for and kept as "he watched it" either way. The 2023 logger recorded the
position at exit for exactly this reason and the current one had stopped.

So `tools/mpv/scail_logger.lua` writes a second log, one line per finished
play, and this module is what reads it. THE RECORD FORMAT, appended when a
file ends:

    <open epoch>|<end epoch>|<path>|length=<s>|time=<s>|watched=<s>|reason=<r>

    1700000000|1700001400|D:\\Videos\\Example Show - 06.mkv|length=1421.0|time=1419.3|watched=1402.5|reason=eof

  * `open epoch` is the same integer the history log carries for that open,
    which is what joins a play to the file that opened it. Nothing else is
    needed to match the two, and matching on the path alone would confuse two
    plays of one file in an evening.
  * `length` is the file's duration in seconds, `time` where he stopped.
    Both `0.0` when the player never knew (a stream).
  * `watched` is WALL CLOCK SPENT UNPAUSED, in seconds, and it is the number
    that separates a watch from a skim. The end position cannot do it: seeking
    to the last minute and closing the file gives the same `time=` as sitting
    through the whole thing, and a file left paused for an hour gives the same
    elapsed clock as an hour watched.
  * `reason` is the player's own word for what ended it -- `eof` it ran out,
    `stop` he closed the file, `quit` he closed the player, `error`,
    `redirect`, `unknown`.

The live half of the same signal is `mpv_now.json`, which carries `watched`
and `opened` while a file is open, so a reader can gate on how far in he is
before the play has ended.

**The timeline is the machine's, not a character's**, and this module is why
it is not written by a character's process. Three processes run the watching
module over one player. Electing one writer means the record stops when that
character is stopped; letting all three write means three copies of every
line. So any process may call `record_new()` as often as it likes and the
write is idempotent: the open's own epoch is a column of the row, a row whose
epoch is already in the file is not written again, and the append is taken
under a lock file so two processes reaching one play in the same second still
produce one row. Whatever is in the plays log and not yet in the timeline is
written on the first call after a boot, so plays made while nothing was
running are picked up rather than lost.

The timeline itself is `reports/plays.md` (`watching.plays_timeline_path`) --
plain text he can open, newest at the bottom, one row per play:

    | 2026-01-02 15:05 | Example Show ep6 | 23.4 of 23.7 min | stopped 15:29 | full | counted | 1700000000 |

spec: PROJECT.md §12.12
"""

import errno
import ntpath
import os
import time

# How close to the end he has to have stopped for a play to be a full watch,
# in seconds. A television episode's credits run a minute and a half and he
# closes the file over them, which is a finished episode by any reading.
FULL_TAIL_SECONDS = 100.0
# ...or this much of the file's whole length spent unpaused, which is what
# covers a file whose duration the player never learned and a watch he broke
# off two minutes before the end.
FULL_FRACTION = 0.9

HEADER = (
    "# What he has played\n"
    "\n"
    "Every file his media player finished, newest at the bottom, one row per\n"
    "play. Written by `machine/plays.py` from `mpv_plays.log`, which\n"
    "`tools/mpv/scail_logger.lua` appends to when a file ends.\n"
    "\n"
    "`watched` is wall clock spent unpaused, which is what separates a watch\n"
    "from a skim: seeking to the last minute and closing the file leaves the\n"
    "same end position as sitting through the whole thing. `counted` says\n"
    "whether the play was far enough in to be read up on and told to a\n"
    "character (`watching.min_watched_minutes`). The last column is the\n"
    "epoch the file opened at, which is what makes a row impossible to write\n"
    "twice.\n"
    "\n"
    "| when | what | watched | ended | verdict | for her | open |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n")


# ---------------- the log ----------------

def parse_line(line):
    """One line of the plays log as a dict, or None.

    Tolerant on purpose: a line written by a future version of the script with
    a field this build does not know keeps its known fields rather than being
    thrown away, and a truncated last line (the player was killed mid-write)
    is simply not a play."""
    s = str(line or "").strip()
    if not s or "|" not in s:
        return None
    bits = s.split("|")
    if len(bits) < 3:
        return None
    try:
        opened = int(float(bits[0]))
        ended = int(float(bits[1]))
    except (TypeError, ValueError):
        return None
    row = {"opened": opened, "ended": ended, "path": bits[2],
           "length": 0.0, "time": 0.0, "watched": 0.0, "reason": ""}
    for field in bits[3:]:
        name, _, val = field.partition("=")
        name = name.strip()
        if name == "reason":
            row["reason"] = val.strip()
        elif name in ("length", "time", "watched"):
            try:
                row[name] = float(val)
            except (TypeError, ValueError):
                pass
    if not row["path"]:
        return None
    return row


def read(path, tail=400):
    """The last `tail` finished plays, oldest first. `[]` for a log that is
    not there, which is every machine until he next opens the player."""
    p = os.path.expandvars(str(path or ""))
    if not p or not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()[-int(tail or 400):]
    except OSError:
        return []
    return [r for r in (parse_line(ln) for ln in lines) if r]


def for_open(path, open_ts, file_path="", window=3.0):
    """The finished play for ONE open of the history log, or None.

    Matched on the open's own epoch, which both logs write from the same
    call, with a few seconds of slack because the two lines are written by
    two `os.time()` calls either side of a file load. The path is compared as
    well where the caller has one, so a slack window that happens to span two
    opens cannot answer with the wrong file."""
    try:
        want = float(open_ts or 0)
    except (TypeError, ValueError):
        return None
    if not want:
        return None
    same = _norm(file_path)
    best = None
    for row in read(path):
        if abs(float(row["opened"]) - want) > float(window):
            continue
        if same and _norm(row["path"]) != same:
            continue
        if best is None or abs(row["opened"] - want) < abs(best["opened"] - want):
            best = row
    return best


def _norm(p):
    return str(p or "").replace("/", "\\").strip().lower()


# ---------------- what a play was ----------------

def _reached_the_end(row):
    """Did this play run to the end of its own file: the player said so, or he
    stopped inside the credits, or he sat unpaused through nearly all of it."""
    length = float(row.get("length") or 0)
    end = float(row.get("time") or 0)
    watched = float(row.get("watched") or 0)
    if str(row.get("reason") or "") == "eof":
        return True
    if length > 0 and (length - end) <= FULL_TAIL_SECONDS:
        return True
    return bool(length > 0 and watched >= FULL_FRACTION * length)


def verdict(row, min_watched_seconds):
    """`full`, `partial`, `played out` or `skim` for one play.

    The gate -- the minutes a play has to run before anything is fetched --
    decides whether the play reaches her, and it is a poor name for what
    happened when the FILE is shorter than the gate. A six-second clip played
    to its own end came out as `skim` in his timeline, which reads as him
    losing interest six seconds in. So the two questions are asked in order:
    did it run to the end of the file, and was there enough of it for her.
    Nothing under the gate is counted either way."""
    watched = float(row.get("watched") or 0)
    if watched < float(min_watched_seconds or 0):
        return "played out" if _reached_the_end(row) else "skim"
    return "full" if _reached_the_end(row) else "partial"


def _mmss(seconds):
    s = max(0, int(float(seconds or 0)))
    return f"{s // 60}:{s % 60:02d}"


def _row_text(row, resolve, min_watched_seconds, when_fmt="%Y-%m-%d %H:%M"):
    """One timeline row. Every time in it is machine local time, because the
    file is his and his clock is the one he reads it by."""
    name = ""
    if resolve:
        try:
            name = resolve(row.get("path") or "") or ""
        except Exception:
            name = ""
    if not name:
        name = ntpath.basename(str(row.get("path") or "")) or "?"
    when = time.strftime(when_fmt, time.localtime(float(row.get("opened") or 0)))
    length = float(row.get("length") or 0)
    watched = float(row.get("watched") or 0)
    of = f" of {length / 60:.1f}" if length > 0 else ""
    v = verdict(row, min_watched_seconds)
    ended = f"stopped {_mmss(row.get('time'))}"
    if str(row.get("reason") or "") == "eof":
        ended = "played out"
    elif str(row.get("reason") or "") not in ("stop", "quit", ""):
        ended += f" ({row.get('reason')})"
    counted = "counted" if v in ("full", "partial") else f"no ({v})"
    return (f"| {when} | {name} | {watched / 60:.1f}{of} min | {ended} "
            f"| {v} | {counted} | {row.get('opened')} |")


# ---------------- the timeline ----------------

def written_opens(timeline_path):
    """The open epochs already in the timeline. Read off the rows themselves
    rather than a sidecar, so deleting the file rebuilds it and no second
    record can disagree with it."""
    p = os.path.expandvars(str(timeline_path or ""))
    out = set()
    if not p or not os.path.exists(p):
        return out
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.startswith("|"):
                    continue
                bits = [b.strip() for b in line.strip().strip("|").split("|")]
                if not bits:
                    continue
                try:
                    out.add(int(bits[-1]))
                except (TypeError, ValueError):
                    continue
    except OSError:
        return out
    return out


class _Lock:
    """A lock file over the append, so two characters' processes reaching one
    play in the same second write one row between them. A lock older than
    `stale` is taken over: a process is stopped with `Stop-Process -Force` and
    leaves its lock behind."""

    def __init__(self, path, stale=30.0, tries=40, wait=0.05):
        self.path = str(path) + ".lock"
        self.stale = float(stale)
        self.tries = int(tries)
        self.wait = float(wait)
        self.fd = None

    def __enter__(self):
        for _ in range(self.tries):
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except OSError as e:
                if e.errno != errno.EEXIST:
                    return self          # no lock is better than no record
                try:
                    if time.time() - os.path.getmtime(self.path) > self.stale:
                        os.unlink(self.path)
                        continue
                except OSError:
                    pass
                time.sleep(self.wait)
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            try:
                os.unlink(self.path)
            except OSError:
                pass
        self.fd = None
        return False


def record_new(plays_path, timeline_path, min_watched_seconds, resolve=None,
               tail=400, log=None):
    """Append every finished play not in the timeline yet. Returns the rows
    written.

    Idempotent and safe to call from every process on every poll: the open's
    epoch is read back out of the file under the lock, so a row cannot be
    written twice however many processes ask."""
    rows = read(plays_path, tail=tail)
    if not rows:
        return []
    p = os.path.expandvars(str(timeline_path or ""))
    if not p:
        return []
    d = os.path.dirname(os.path.abspath(p))
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return []
    written = []
    with _Lock(p):
        have = written_opens(p)
        fresh = [r for r in rows if int(r.get("opened") or 0) not in have]
        if not fresh:
            return []
        # one open is one row even if the log holds the play twice
        seen, uniq = set(), []
        for r in sorted(fresh, key=lambda r: int(r.get("opened") or 0)):
            k = int(r.get("opened") or 0)
            if k in seen:
                continue
            seen.add(k)
            uniq.append(r)
        new_file = not os.path.exists(p) or os.path.getsize(p) == 0
        try:
            with open(p, "a", encoding="utf-8") as fh:
                if new_file:
                    fh.write(HEADER)
                for r in uniq:
                    fh.write(_row_text(r, resolve, min_watched_seconds) + "\n")
        except OSError as e:
            if log:
                log(f"[plays] his timeline not written: {type(e).__name__}")
            return []
        written = uniq
    if written and log:
        log(f"[plays] {len(written)} finished play(s) added to {p}")
    return written
