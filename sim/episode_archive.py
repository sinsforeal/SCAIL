"""Everything fetched about one episode, kept on disk and findable later.

The cache row in `recaps` holds one chosen text. Everything the choice was
made from -- each candidate page's extracted text and its raw HTML, each
subtitle file, the transcript it parsed to, each digest, the judge's verdict
-- is written here instead of being thrown away, so a bad summary can be
argued with afterwards rather than re-fetched and guessed at.

    data/recaps/<show>/ep<NNN>/
        manifest.json                  the index: what each file is
        page-01-myanimelist.net.txt    the extracted text of a candidate
        page-01-myanimelist.net.html   the bytes it was extracted from
        subtitle-01-<name>.srt         the file as downloaded
        transcript-01.json             its parsed lines with timestamps
        digest-01.txt                  what the digest role made of a page
        judge-01.json                  the verdict and the reason

`<show>` is the show's id on his list when there is one and a slug of its
title otherwise -- an episode of a television programme, not a person, which
is why one directory serves both characters (`tools/isolation.py`).

**Nothing is overwritten.** A second fetch of the same page writes
`page-02-...`, and the manifest gains a row; the manifest itself is the one
file rewritten, because it is the index rather than a record.

Each manifest row says what the file is (`kind`), where it came from (`url`),
when it arrived (`at`, machine local time), and how big it was. `chosen`
names the file and URL the judge picked, with its reason and confidence.
"""
import hashlib
import json

import atomic
import os
import re
import time

import logger

_SAFE = re.compile(r"[^0-9A-Za-z._-]+")


def slug(name, fallback=""):
    """A directory name from a show's title. A Japanese title reduces to
    nothing under an ASCII filter, so it becomes a short stable hash with a
    `jp-` mark; the readable title is written into the manifest."""
    s = _SAFE.sub("-", str(name or "").strip()).strip("-")[:60]
    if s:
        return s
    src = str(name or fallback or "")
    if not src:
        return "unknown"
    return "jp-" + hashlib.sha1(src.encode("utf-8")).hexdigest()[:10]


class EpisodeArchive:
    def __init__(self, root="data/recaps", enabled=True):
        self.root = str(root or "data/recaps")
        self.enabled = bool(enabled)

    # ---------------- where ----------------

    def show_key(self, anime_id=None, ja="", title=""):
        if anime_id:
            return str(int(anime_id))
        return slug(title or ja, ja)

    def dir_for(self, show_key, ep):
        return os.path.join(self.root, str(show_key), "ep%03d" % int(ep or 0))

    def _manifest_path(self, show_key, ep):
        return os.path.join(self.dir_for(show_key, ep), "manifest.json")

    def manifest(self, show_key, ep):
        p = self._manifest_path(show_key, ep)
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_manifest(self, show_key, ep, man):
        p = self._manifest_path(show_key, ep)
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            atomic.write_json(p, man, indent=1)
        except OSError as e:
            logger.log(f"[archive] index not written: {type(e).__name__}")

    # ---------------- writing ----------------

    def save(self, show_key, ep, kind, data, url="", ext=".txt", note="", name="",
             show="", ja=""):
        """Write one fetched thing and index it. Returns its file name, or ''.

        `kind` is what it is: page, html, subtitle, transcript, digest, judge,
        index. The file name carries the kind, a version number that never
        reuses an earlier one, and a hint of where it came from."""
        if not self.enabled:
            return ""
        try:
            d = self.dir_for(show_key, ep)
            os.makedirs(d, exist_ok=True)
            man = self.manifest(show_key, ep)
            files = man.get("files") or []
            n = 1 + sum(1 for f in files if f.get("kind") == kind)
            hint = name or (re.sub(r"^www\.", "", (url or "").split("//")[-1].split("/")[0]) if url else "")
            fname = _SAFE.sub("-", f"{kind}-{n:02d}-{hint}").strip("-")[:90] + ext
            path = os.path.join(d, fname)
            while os.path.exists(path):      # never overwrite; the next version
                n += 1
                fname = _SAFE.sub("-", f"{kind}-{n:02d}-{hint}").strip("-")[:90] + ext
                path = os.path.join(d, fname)
            raw = data if isinstance(data, bytes) else str(data or "").encode("utf-8")
            with open(path, "wb") as fh:
                fh.write(raw)
            files.append({"file": fname, "kind": kind, "url": url,
                          "at": time.strftime("%Y-%m-%d %H:%M:%S"), "bytes": len(raw),
                          "note": note})
            man["files"] = files
            man["show"] = show or man.get("show", "")
            man["ja"] = ja or man.get("ja", "")
            man["ep"] = int(ep or 0)
            self._write_manifest(show_key, ep, man)
            return fname
        except OSError as e:
            logger.log(f"[archive] {kind} not saved: {type(e).__name__}")
            return ""

    def note_choice(self, show_key, ep, url="", confidence="", reason="", anchor="",
                    candidates=()):
        """Which candidate the judge chose, and why, beside the files it chose
        among -- so the index answers 'which one did it take' on its own."""
        if not self.enabled:
            return
        man = self.manifest(show_key, ep)
        man["chosen"] = {"url": url, "confidence": confidence, "reason": reason,
                         "anchor": anchor, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "candidates": list(candidates or ())}
        self._write_manifest(show_key, ep, man)

    # ---------------- reading ----------------

    def read(self, show_key, ep, fname):
        try:
            with open(os.path.join(self.dir_for(show_key, ep), fname), "rb") as fh:
                return fh.read()
        except OSError:
            return b""

    def report(self, limit=20):
        """What is on disk, for /kb: shows, episodes, files."""
        if not os.path.isdir(self.root):
            return "no episode archive yet"
        shows = 0
        eps = 0
        files = 0
        recent = []
        for show in sorted(os.listdir(self.root)):
            sd = os.path.join(self.root, show)
            if not os.path.isdir(sd):
                continue
            shows += 1
            for epd in sorted(os.listdir(sd)):
                p = os.path.join(sd, epd)
                if not os.path.isdir(p):
                    continue
                eps += 1
                try:
                    man = json.load(open(os.path.join(p, "manifest.json"), encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                n = len(man.get("files") or [])
                files += n
                ch = (man.get("chosen") or {}).get("confidence", "-")
                recent.append(f"  {man.get('ja') or man.get('show') or show} ep{man.get('ep')}: "
                              f"{n} file(s), {ch}")
        out = [f"episode archive ({self.root}): {shows} show(s), {eps} episode(s), {files} file(s)"]
        return "\n".join(out + recent[-int(limit):])
