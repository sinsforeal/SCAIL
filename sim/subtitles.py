"""The episode's own subtitle file, downloaded and turned into lines.

Ranked above every synopsis on the web and not a synopsis at all: the file is
what was said, in order, with timestamps, and for a broadcast or streaming
caption rip with the speaker attached. It is the anchor a web candidate is
checked against, never the thing she reads.

Sources, in this order, and the first three cost no network at all:

* **the file already beside his video** -- same directory, same stem, one of
  the subtitle extensions, with or without a language suffix
  (`Show - S01E26 - The Future.srt`, `... .ja.srt`), and the same in a
  `Subs/` folder beside it. It was being ignored: a Japanese subtitle of 339
  lines sits next to an episode he played, and the fetcher was asking the
  internet for it;
* **the archive mirror cloned onto this machine** (`subtitles_local_mirror`),
  walked as directories on disk. The repository is 3.71 GB with its history,
  so it is cloned shallow, one branch, sparse to the three folders this walks;
  `refresh_mirror` pulls it at most once a day and belongs to the machine's
  own clock, never to a character's thread;
* **the same mirror through the GitHub tree API**, the fallback for a machine
  that has not cloned it. Rate-limited, and it was the first network hop of
  every miss;
* **the fan archive's own site**, whose download path needs no account (only
  its JSON API does). Its index is one server-rendered page of every entry, so
  the catalogue is greppable in one request and cached for the day.

When every one of them misses, the episode is transcribed from the file he
played (`sim/transcribe.py`). Three of five episodes in a fortnight came away
with nothing here, and not because of a bad match: neither archive carries
those works at all, under any name.

Three checks, each of which a file has failed in the wild:

* a file in a folder marked Japanese is not always a Japanese transcript --
  one show's files are a Chinese group's listening script, and one of those is
  dual-language with the Japanese layer under half the lines. The share of
  lines carrying Japanese script is measured on the file, not assumed from
  where it sat;
* a bitmap subtitle (`.sup`) is images of text and would need optical
  recognition. Refused, with every archive format that has to be unpacked;
* a track translated from English is not a transcript of what was said.
  Refused by name, and outranked in any case by a caption rip.

One fetch attempt per show and episode per day, hit or miss, and a miss is
recorded so a show with no file is not looked for on every tick.

spec: docs/recap.md
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

import logger

# a line that is dialogue rather than a style block, a karaoke effect or a
# scrolling banner
_JA = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")
_KANA = re.compile(r"[぀-ゟ゠-ヿ]")
# a caption rip prefixes the speaker: （唯(ゆい)） / (律) / 唯：
# the label may carry the reading in ascii brackets inside the full-width
# ones -- 「（唯(ゆい)）」 -- so the inner group is matched rather than ended on
_SPEAKER = re.compile(r"^[（(]((?:[^（()）]|\([^)]*\)){1,24})[）)]\s*"
                      r"|^([^\s:：]{1,12})[:：]\s*")
_RUBY = re.compile(r"\(([぀-ゟ]{1,12})\)")

_REFUSED_EXT = (".sup", ".idx", ".sub", ".zip", ".rar", ".7z", ".tar", ".gz")
_SUB_EXT = (".srt", ".ass", ".ssa", ".vtt")
# a file whose name says it was made from an English track, or carries a
# Chinese layer
_MACHINE = ("translated", "machine", "mtl", "en2ja", "eng2jpn", "auto-translate")
# The latin marks are matched as whole tokens: a release name is full of
# words, and a bare `gb` is inside `bigband` while `chs` is inside
# `batchsize`. The Japanese and Chinese ones need no boundary.
_CHINESE_TOKEN = re.compile(r"(?<![a-z0-9])(chs|cht|gb|gb2312|big5|chinese|sc|tc)(?![a-z0-9])")
_CHINESE_TEXT = ("简", "繁", "中文", "字幕组", "簡体", "繁體")
_DUAL = ("en+jp", "jp+en", "en-jp", "bilingual")

# what the filename says about where the file came from, best first
_BROADCAST = ("tbs", "mbs", "bs11", "atx", "tokyomx", "-mx", "shincaps", "raws",
              "bdrip", "blu-ray", "bluray", "dvdrip", "hdtv", "ts)")
_STREAMING = ("netflix", "amazon", "primevideo", "disney", "crunchyroll", "abema",
              "unext", "webrip", "web-dl", "[cc]", "[sdh]", "hulu")


def _has_ja(s):
    return bool(_JA.search(s or ""))


def japanese_share(lines):
    """The share of dialogue lines carrying Japanese script. A dual-language
    script whose Japanese layer is a third of the file reads well under 0.6."""
    if not lines:
        return 0.0
    n = sum(1 for l in lines if _has_ja(l.get("text") or ""))
    return n / float(len(lines))


def _clean(s):
    s = re.sub(r"\{[^}]*\}", "", s or "")            # ASS override tags
    s = re.sub(r"<[^>]+>", "", s)                    # VTT/SRT markup
    s = s.replace("\\N", " ").replace("\\n", " ").replace("\\h", " ")
    s = re.sub(r"[ \t　]+", " ", s)
    return s.strip()


def _t_srt(s):
    m = re.match(r"(\d+):(\d\d):(\d\d)[,.](\d{1,3})", s.strip())
    if not m:
        return 0.0
    h, mi, se, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + se + ms / 1000.0


def _t_ass(s):
    m = re.match(r"(\d+):(\d\d):(\d\d)[.:](\d{1,2})", s.strip())
    if not m:
        return 0.0
    h, mi, se, cs = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + se + cs / 100.0


def parse(text, name=""):
    """A subtitle file as [{start, end, speaker, text}], in time order.

    `.srt` and `.vtt` are cue blocks; `.ass`/`.ssa` are `Dialogue:` rows whose
    fourth field is the style and whose tenth is the text. Speaker labels a
    broadcast caption rip carries in the line itself are lifted out, with the
    reading in parentheses dropped: 「（唯(ゆい)）ただいま」 is 唯 saying
    ただいま."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    low = (name or "").lower()
    out = []
    if low.endswith((".ass", ".ssa")) or "\nDialogue:" in text or text.startswith("Dialogue:"):
        for line in text.split("\n"):
            if not line.startswith("Dialogue:"):
                continue
            parts = line[len("Dialogue:"):].split(",", 9)
            if len(parts) < 10:
                continue
            out.append({"start": _t_ass(parts[1]), "end": _t_ass(parts[2]),
                        "style": parts[3].strip(), "text": _clean(parts[9])})
        out.sort(key=lambda r: r["start"])
    else:
        block = []
        for line in text.split("\n") + [""]:
            if line.strip() == "":
                if block:
                    cue = None
                    body = []
                    for b in block:
                        if "-->" in b and cue is None:
                            a, _, z = b.partition("-->")
                            cue = (_t_srt(a.strip().split(" ")[0]), _t_srt(z.strip().split(" ")[0]))
                        elif cue is not None:
                            body.append(b)
                    if cue:
                        out.append({"start": cue[0], "end": cue[1], "style": "",
                                    "text": _clean(" ".join(body))})
                    block = []
                continue
            block.append(line)
    rows = []
    for r in out:
        t = r["text"]
        if not t:
            continue
        who = ""
        m = _SPEAKER.match(t)
        if m:
            who = _RUBY.sub("", (m.group(1) or m.group(2) or "")).strip()
            # a bracket that is a sound annotation, not a speaker
            if who and (_KANA.search(who) or _JA.search(who)):
                t = t[m.end():].strip()
            else:
                who = ""
        rows.append({"start": round(r["start"], 2), "end": round(r["end"], 2),
                     "speaker": who, "text": t})
    return rows


def provenance(name):
    """broadcast / streaming / fan, from the filename. A caption rip off the
    air or off a service carries speaker labels; a fan listening transcript
    does not, and its wording is somebody's guess at what was said."""
    low = (name or "").lower()
    if any(k in low for k in _STREAMING):
        return "streaming"
    if any(k in low for k in _BROADCAST):
        return "broadcast"
    return "fan"


def _ep_of(name):
    """The episode number a subtitle filename claims, or None."""
    s = str(name or "")
    m = re.search(r"S\d{1,2}E(\d{1,3})", s, re.I)
    if m:
        return int(m.group(1))
    for m in re.finditer(r"\[(\d{1,3})\]", s):
        return int(m.group(1))
    stem = re.sub(r"\[[^\]]*\]", " ", s)
    stem = re.sub(r"\([^)]*\)", " ", stem)
    stem = re.sub(r"\.(srt|ass|ssa|vtt)$", "", stem, flags=re.I)
    m = re.search(r"[-–—]\s*(\d{1,3})(?:v\d)?\s*$", stem.strip())
    if m:
        return int(m.group(1))
    m = re.search(r"[\s.](\d{1,3})(?:v\d)?\s*$", stem.strip())
    if m:
        return int(m.group(1))
    m = re.search(r"第(\d{1,3})話", s)
    if m:
        return int(m.group(1))
    return None


def acceptable(name):
    """Whether the file is worth downloading at all, on its name: a text
    subtitle, not Chinese, not dual-language, not translated from English."""
    low = (name or "").lower()
    if low.endswith(_REFUSED_EXT):
        return False, "not text (bitmap or an archive)"
    if not low.endswith(_SUB_EXT):
        return False, "not a subtitle file"
    if any(k in low for k in _MACHINE):
        return False, "translated, not transcribed"
    if any(k in low for k in _DUAL):
        return False, "dual-language script"
    stem = re.sub(r"\.(srt|ass|ssa|vtt)$", "", low)
    if _CHINESE_TOKEN.search(stem) or any(k in stem for k in _CHINESE_TEXT):
        return False, "a Chinese-language rip"
    return True, ""


def rank(name):
    """Lower is better: a caption rip over a fan transcript, `.srt` over
    `.ass` (fewer style rows to walk past)."""
    p = provenance(name)
    base = {"broadcast": 0, "streaming": 1, "fan": 2}.get(p, 3)
    return base * 10 + (0 if (name or "").lower().endswith(".srt") else 1)


def local_counts(root):
    """(shows, files) in a clone of the archive on this machine."""
    shows = files = 0
    for folder in ("anime_tv", "drama_tv", "anime_movie"):
        p = os.path.join(root or "", folder)
        try:
            names = [n for n in os.listdir(p) if os.path.isdir(os.path.join(p, n))]
        except OSError:
            continue
        shows += len(names)
        for n in names:
            try:
                files += len([x for x in os.listdir(os.path.join(p, n))
                              if os.path.isfile(os.path.join(p, n, x))])
            except OSError:
                pass
    return shows, files


def refresh_local_mirror(root, hours=24, log=print):
    """Bring the clone of the archive up to date, at most once a day.

    **The MACHINE's job, not a character's.** It runs from the list mirror's
    own daemon, which is where this project's machine-owned periodic fetches
    live, and never on either bot's thread: a pull of a fifteen-gigabyte
    working tree is not something a reply should wait behind. A module
    function rather than a method because that daemon has no character and no
    Config -- it reads the path out of the config file and calls this.

    A failure is logged by exception TYPE: git quotes the remote it failed on,
    and a remote can carry a credential. Returns the one line it logged, or ""
    when nothing was due."""
    import subprocess
    if not root or not os.path.isdir(os.path.join(root, ".git")):
        return ""
    stamp = os.path.join(root, ".scail_refreshed")
    try:
        if os.path.exists(stamp) and (time.time() - os.path.getmtime(stamp)) < float(hours) * 3600:
            return ""
    except OSError:
        pass
    sub = os.path.join(root, "subtitles")
    before = local_counts(sub)
    try:
        r = subprocess.run(["git", "-C", root, "pull", "--ff-only", "--depth", "1"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=3600)
    except Exception as e:
        log(f"[subs] the subtitle mirror was not refreshed ({type(e).__name__})")
        return ""
    try:
        with open(stamp, "w", encoding="utf-8") as fh:
            fh.write(str(int(time.time())))
    except OSError:
        pass
    after = local_counts(sub)
    line = (f"[subs] the subtitle mirror was refreshed: {after[0]} show(s), {after[1]} file(s)"
            + f", {after[1] - before[1]:+d} file(s)"
            + (f"; git exit {r.returncode}" if r.returncode else ""))
    log(line)
    return line


class Subtitles:
    """Finds one episode's Japanese subtitle file: beside his video, in the
    clone of the archive on this machine, or on the internet."""

    def __init__(self, config, store, clock, archive=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.archive = archive
        self._dir_cache = {}

    # every key below is read with a default so this module runs before the
    # config patch that adds them (data/retired/<ts>_summaries_build)
    def _c(self, key, default):
        return getattr(self.config.recap, key, default)

    def enabled(self):
        return bool(self._c("subtitles_enabled", True))

    # ---------------- HTTP ----------------

    def _get(self, url, limit=4_000_000):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": str(self._c("subtitles_user_agent", "scail-recap/1.0")),
                "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=float(self._c("http_timeout_seconds", 20))) as fh:
                return fh.read(limit)
        except Exception as e:      # any network failure, by TYPE: a URL can carry a key
            logger.log(f"[subs] fetch failed ({type(e).__name__})")
            return b""

    def _get_json(self, url):
        raw = self._get(url)
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            return None

    def _read_ref(self, ref):
        """The bytes of a candidate, whether it is a URL or a path on disk."""
        if str(ref).startswith(("http://", "https://")):
            return self._get(ref)
        try:
            with open(ref, "rb") as fh:
                return fh.read(4_000_000)
        except OSError as e:
            logger.log(f"[subs] a file on this machine could not be read ({type(e).__name__})")
            return b""

    # ---------------- the file already beside his video ----------------

    def sidecar(self, video, ep=None):
        """The subtitle sitting next to the file he opened: (name, path) or
        None. Read-only, and the video itself is never opened.

        The stem is the video's, with or without a language suffix, and a
        `Subs` folder beside it is looked in too, because that is where a
        release puts them when it does not put them flat. The episode number
        is not re-derived from the name -- the file is named after THIS video,
        which is the episode he played."""
        if not self._c("local_subtitles_enabled", True) or not video:
            return None
        try:
            d = os.path.dirname(str(video))
            stem = os.path.splitext(os.path.basename(str(video)))[0]
        except (TypeError, ValueError):
            return None
        if not d or not stem or not os.path.isdir(d):
            return None
        sufs = list(self._c("local_subtitle_suffixes", ["", ".ja", ".jpn"]) or [""])
        out = []
        for folder in (d, os.path.join(d, "Subs"), os.path.join(d, "subs"),
                       os.path.join(d, "Subtitles"), os.path.join(d, stem)):
            if not os.path.isdir(folder):
                continue
            for suf in sufs:
                for ext in _SUB_EXT:
                    p = os.path.join(folder, stem + suf + ext)
                    if os.path.exists(p):
                        ok, why = acceptable(os.path.basename(p))
                        if not ok:
                            logger.log(f"[subs] the file beside his video is {why}")
                            continue
                        out.append((rank(os.path.basename(p)), os.path.basename(p), p))
        return sorted(out)[0][1:] if out else None

    # ---------------- the archive mirror, cloned onto this machine ---------

    def local_root(self):
        """The cloned mirror's `subtitles/` directory, or "" when there is
        none. The clone belongs to the machine, like the episode archive."""
        root = str(self._c("subtitles_local_mirror", "") or "")
        if not root:
            return ""
        p = os.path.join(root, "subtitles")
        return p if os.path.isdir(p) else ""

    def _local_dirs(self, folder):
        p = os.path.join(self.local_root(), folder)
        try:
            return [n for n in os.listdir(p) if os.path.isdir(os.path.join(p, n))]
        except OSError:
            return []

    def _local_files(self, folder, show_dir):
        p = os.path.join(self.local_root(), folder, show_dir)
        try:
            return [n for n in os.listdir(p) if os.path.isfile(os.path.join(p, n))]
        except OSError:
            return []

    def refresh_mirror(self, log=None):
        """Bring the clone up to date. See `refresh_local_mirror`; this is the
        form for a caller that holds a config."""
        return refresh_local_mirror(str(self._c("subtitles_local_mirror", "") or ""),
                                    hours=float(self._c("subtitles_local_refresh_hours", 24) or 24),
                                    log=log or logger.log)

    def _local_counts(self):
        return local_counts(self.local_root())

    # ---------------- the mirror on GitHub ----------------

    def _mirror_dirs(self, folder):
        """Every show directory under one folder of the mirror, cached for the
        run: 3,500 names in one request."""
        if folder in self._dir_cache:
            return self._dir_cache[folder]
        base = str(self._c("subtitles_mirror_tree",
                           "https://api.github.com/repos/Ajatt-Tools/kitsunekko-mirror/git/trees/main:subtitles"))
        d = self._get_json(f"{base}/{urllib.parse.quote(folder)}")
        names = [t.get("path", "") for t in ((d or {}).get("tree") or []) if t.get("type") == "tree"]
        self._dir_cache[folder] = names
        return names

    @staticmethod
    def _match_dir(names, titles):
        """The show directory for one of these titles: an exact match first,
        then a case-folded one, then a containment both ways long enough not
        to fire on a common word."""
        low = {n.lower(): n for n in names}
        for t in titles:
            t = str(t or "").strip()
            if not t:
                continue
            if t in names:
                return t
            if t.lower() in low:
                return low[t.lower()]
        for t in titles:
            tl = str(t or "").strip().lower()
            if len(tl) < 6:
                continue
            for n in names:
                nl = n.lower()
                if (tl in nl or nl in tl) and min(len(tl), len(nl)) / max(len(tl), len(nl)) >= 0.7:
                    return n
        return ""

    def _mirror_files(self, folder, show_dir):
        base = str(self._c("subtitles_mirror_tree",
                           "https://api.github.com/repos/Ajatt-Tools/kitsunekko-mirror/git/trees/main:subtitles"))
        d = self._get_json(f"{base}/{urllib.parse.quote(folder)}/{urllib.parse.quote(show_dir)}")
        return [t.get("path", "") for t in ((d or {}).get("tree") or []) if t.get("type") == "blob"]

    def _mirror_candidates(self, titles, ep):
        """The archive mirror's files for this episode: from the clone on this
        machine when there is one, and from the tree API when there is not.

        The clone is preferred because reading it is free and instant, and
        because the API is rate-limited and was the first network hop of every
        miss. Which one answered is visible in the reference: a path on this
        machine, or a raw URL."""
        raw_base = str(self._c("subtitles_mirror_raw",
                               "https://raw.githubusercontent.com/Ajatt-Tools/kitsunekko-mirror/main/subtitles"))
        local = bool(self.local_root())
        out = []
        for folder in ("anime_tv", "drama_tv", "anime_movie"):
            names = self._local_dirs(folder) if local else self._mirror_dirs(folder)
            if not names:
                continue
            show_dir = self._match_dir(names, titles)
            if not show_dir:
                continue
            files = (self._local_files(folder, show_dir) if local
                     else self._mirror_files(folder, show_dir))
            for f in files:
                if _ep_of(f) != int(ep):
                    continue
                ok, why = acceptable(f)
                if not ok:
                    logger.log(f"[subs] {f[:60]}: {why}")
                    continue
                ref = (os.path.join(self.local_root(), folder, show_dir, f) if local else
                       f"{raw_base}/{urllib.parse.quote(folder)}/"
                       f"{urllib.parse.quote(show_dir)}/{urllib.parse.quote(f)}")
                out.append((rank(f), f, ref))
            if out:
                break
        return sorted(out)

    # ---------------- the fan archive's own site ----------------

    def _archive_index(self):
        """The whole entry index, one server-rendered page, cached for a day
        in the save rather than re-fetched per episode."""
        cached = self.store.get("subs_index", None) or {}
        now = self.clock.now_ts()
        if cached.get("at") and now - float(cached["at"]) < 86400 and cached.get("rows"):
            return cached["rows"]
        url = str(self._c("subtitles_archive_index", "https://jimaku.cc/"))
        html = self._get(url, limit=3_000_000).decode("utf-8", "replace")
        rows = []
        for m in re.finditer(r'href="/entry/(\d+)"[^>]*>(.*?)</a>', html, re.S):
            name = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
            name = name.replace("&#34;", '"').replace("&amp;", "&")
            if name:
                rows.append([int(m.group(1)), name[:120]])
        if rows:
            self.store.set("subs_index", {"at": now, "rows": rows})
        return rows

    def _archive_candidates(self, titles, ep):
        rows = self._archive_index()
        if not rows:
            return []
        names = [r[1] for r in rows]
        hit = self._match_dir(names, titles)
        if not hit:
            return []
        eid = next(r[0] for r in rows if r[1] == hit)
        base = str(self._c("subtitles_archive_base", "https://jimaku.cc"))
        html = self._get(f"{base}/entry/{eid}", limit=1_000_000).decode("utf-8", "replace")
        out = []
        for m in re.finditer(r'href="(/entry/%d/download/([^"]+))"' % eid, html):
            f = urllib.parse.unquote(m.group(2))
            if _ep_of(f) != int(ep):
                continue
            ok, why = acceptable(f)
            if not ok:
                logger.log(f"[subs] {f[:60]}: {why}")
                continue
            out.append((rank(f), f, base + m.group(1)))
        return sorted(out)

    # ---------------- the one public call ----------------

    def _attempted_today(self, key):
        log = self.store.get("subs_attempts", {}) or {}
        at = float(log.get(key, 0) or 0)
        return at and (self.clock.now_ts() - at) < float(self._c("subtitles_retry_hours", 24)) * 3600

    def _mark_attempt(self, key):
        log = self.store.get("subs_attempts", {}) or {}
        log[key] = self.clock.now_ts()
        if len(log) > 400:
            log = dict(sorted(log.items(), key=lambda kv: float(kv[1] or 0))[-400:])
        self.store.set("subs_attempts", log)

    def fetch(self, titles, ep, show_key="", show="", ja="", video=""):
        """The best acceptable subtitle file for this episode, parsed.

        Returns `{lines, source, provenance, file, ja_share, origin}` or None.
        One attempt per show and episode per day whatever the answer, so a
        show with no file costs one listing request a day and not one a tick.

        `video` is the file he opened, and it is tried FIRST because a file
        already beside it costs nothing at all. The day's attempt is only
        recorded once the network is about to be used, so a machine that gains
        a sidecar an hour later is not locked out until tomorrow."""
        if not self.enabled():
            return None
        titles = [t for t in (titles or []) if str(t or "").strip()]
        if not titles or not ep:
            return None
        key = f"{show_key or titles[0]}:{int(ep)}"
        cands, origin = [], ""
        side = None
        try:
            side = self.sidecar(video, ep)
        except Exception as e:
            logger.log(f"[subs] the folder beside his video was not read ({type(e).__name__})")
        if side:
            cands, origin = [(rank(side[0]), side[0], side[1])], "beside his video"
        if not cands:
            if self._attempted_today(key):
                return None
            self._mark_attempt(key)
            try:
                cands = self._mirror_candidates(titles, ep)
                origin = ("the archive mirror on this machine" if self.local_root()
                          else "the archive mirror") if cands else ""
            except Exception as e:
                logger.log(f"[subs] mirror listing failed ({type(e).__name__})")
        if not cands:
            try:
                cands = self._archive_candidates(titles, ep)
                origin = "the fan archive" if cands else ""
            except Exception as e:
                logger.log(f"[subs] archive listing failed ({type(e).__name__})")
        if not cands:
            logger.log(f"[subs] no Japanese subtitle file for {titles[0]} ep{ep}")
            return None
        floor = float(self._c("subtitles_min_ja_share", 0.6))
        for _r, name, url in cands[: int(self._c("subtitles_try_files", 3))]:
            raw = self._read_ref(url)
            if not raw:
                continue
            text = raw.decode("utf-8-sig", "replace")
            lines = parse(text, name)
            if len(lines) < int(self._c("subtitles_min_lines", 40)):
                logger.log(f"[subs] {name[:60]}: {len(lines)} line(s); too few to be an episode")
                continue
            share = japanese_share(lines)
            if share < floor:
                # the folder said Japanese and the file is somebody else's
                # language, or a dual-language script with the Japanese layer
                # a minority of it
                logger.log(f"[subs] {name[:60]}: {share:.0%} of lines in Japanese; refused")
                continue
            saved = ""
            if self.archive and show_key:
                ext = "." + name.rsplit(".", 1)[-1].lower()
                saved = self.archive.save(show_key, ep, "subtitle", raw, url=url, ext=ext,
                                          name=name[:40],
                                          note=f"{provenance(name)}, {origin}", show=show, ja=ja)
            logger.log(f"[subs] {titles[0]} ep{ep}: {len(lines)} lines, "
                       f"{provenance(name)}, {share:.0%} Japanese, from {origin}: {name[:60]}")
            return {"lines": lines, "source": url, "provenance": provenance(name),
                    "file": name, "ja_share": round(share, 3), "archived": saved,
                    "origin": origin}
        return None
