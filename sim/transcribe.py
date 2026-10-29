"""The episode transcribed on this machine, when nothing could be fetched.

Every source above this one can come away with nothing, and does: three of the
five episodes looked for in one fortnight are in neither internet archive at
all, under any name. What is always there is the file he played. So the last
step is to listen to it.

**His own install does the work.** `Faster-Whisper-XXL Pro` sits on this
machine with his own `processor.bat` beside it, and the command built here is
the one that batch file builds -- Japanese, transcribe, the large model, SRT
out, `cuda:0`, and his own flags after them -- so his batch file stays the
reference and this follows it. Nothing under that directory is touched. The
exe takes the video and writes the subtitle itself; there is no separate audio
extraction and the video is never opened by this code for anything.

**Where the result goes.** Beside the video, under the video's own stem, so
his player finds it the next time he opens the file -- unless something is
already there under that name, which is the sidecar case and was read one step
earlier. And into the episode archive
(`data/recaps/<show>/ep<NNN>/subtitle-01-*.srt`) with its origin noted, so the
rest of the path -- the same qualification, the same account of the scenes,
the same anchor over the web candidates -- does not know the difference.

**Three restraints, and the reason for each.** It is minutes of a GPU that the
reaction-image tool also wants, so: never on the reply path or the poll (the
caller is already a worker thread), at most `recap.whisper_max_per_day` a day,
nothing longer than `recap.whisper_max_minutes`, and only once he has watched
at least `recap.whisper_min_watched_minutes` of it. That last one is a
different question from whether the episode counts as watched at all
(`watching.min_minutes_in`, three minutes): three minutes says he did not just
brush the file, ten minutes says he settled into it, and paying for a GPU job
is worth the stronger evidence. The fetching steps are gated on the first and
not on this.

**One run between the two characters.** The claim and the answer go in the
machine's own store of what was fetched about the world (`machine/
retrievals.py`, pool `whisper`), keyed on the work and the episode and never
on a character, so the second character gets the text without the GPU running
twice.

spec: docs/recap.md
"""
import os
import shutil
import subprocess
import tempfile
import time

import logger


class Transcribe:
    def __init__(self, config, store, clock, archive=None, retrievals=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.archive = archive
        self.retrievals = retrievals
        # how long the last run of the transcriber took, in seconds. Read once,
        # by the caller that just made it, so the readable log can say what the
        # GPU cost; 0 when the answer came out of the machine's store and
        # nothing ran.
        self.last_run_seconds = 0.0

    def _c(self, key, default):
        return getattr(self.config.recap, key, default)

    # ---------------- whether it can run at all ----------------

    def available(self):
        """(True, "") when the transcriber is on this machine, else
        (False, why). Said once at boot rather than at the first miss."""
        if not self._c("whisper_enabled", True):
            return False, "switched off in the config"
        exe = str(self._c("whisper_exe", "") or "")
        if not exe:
            return False, "no transcriber is named in the config"
        if not os.path.exists(exe):
            return False, f"the transcriber named in the config is not on this machine ({os.path.basename(exe)})"
        return True, ""

    def boot_line(self):
        ok, why = self.available()
        return ("[subs] an episode nothing can be fetched for is transcribed here"
                if ok else f"[subs] nothing will be transcribed here: {why}")

    # ---------------- how long the episode is ----------------

    def minutes_of(self, video):
        """The file's length in minutes, or 0.0 when nobody can say. Read
        only: the probe opens the container's header and nothing else."""
        probe = str(self._c("ffprobe", "ffprobe") or "ffprobe")
        try:
            r = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                                "-of", "default=nw=1:nk=1", str(video)],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=60)
            return round(float((r.stdout or "0").strip() or 0) / 60.0, 1)
        except Exception as e:
            logger.log(f"[subs] the episode's length could not be read ({type(e).__name__})")
            return 0.0

    # ---------------- the day's budget ----------------

    def _today(self):
        return self.clock.date_str()

    def spent_today(self):
        return int((self.store.get("whisper_counts", {}) or {}).get(self._today(), 0) or 0)

    def _note_run(self):
        counts = self.store.get("whisper_counts", {}) or {}
        d = self._today()
        counts[d] = int(counts.get(d, 0) or 0) + 1
        self.store.set("whisper_counts", dict(sorted(counts.items())[-7:]))

    def _floor_minutes(self):
        """How long he must have sat through the file before it is worth
        minutes of the GPU -- and it is ONE number with the gate that decided
        the play was a watch at all (`watching.min_watched_minutes`), not a
        second one beside it.

        It used to be its own key at the same value, and the two were read at
        different instants off different pollings of the player: the read-up
        fired on a reading of 600 seconds and the transcriber was asked a
        second later with 599, so it was refused by rounding every time it was
        ever asked -- three logged refusals read "he is 10 min into it and the
        floor is 10", and no character process has ever run it. The key stays
        for an override; 0 means follow the gate, which is the default."""
        own = float(self._c("whisper_min_watched_minutes", 0) or 0)
        if own:
            return own
        try:
            return float(getattr(self.config.watching, "min_watched_minutes", 10.0) or 0)
        except Exception:
            return 10.0

    def why_not(self, video, watched_seconds):
        """Why this episode will not be transcribed, or "" when it will."""
        ok, why = self.available()
        if not ok:
            return why
        if not video or not os.path.exists(str(video)):
            return "there is no file of his to listen to"
        want = self._floor_minutes() * 60
        if want and float(watched_seconds or 0) < want:
            return (f"he is {float(watched_seconds or 0) / 60:.1f} min into it and the floor "
                    f"is {want / 60:.1f}")
        cap = int(self._c("whisper_max_per_day", 4) or 4)
        if self.spent_today() >= cap:
            return f"the day's {cap} are spent"
        mins = self.minutes_of(video)
        top = float(self._c("whisper_max_minutes", 40) or 40)
        if mins and top and mins > top:
            return f"it is {mins:.0f} min long and the ceiling is {top:.0f}"
        return ""

    # ---------------- the run ----------------

    def _command(self, video, out_dir):
        exe = str(self._c("whisper_exe", ""))
        args = str(self._c("whisper_args", "") or "")
        import shlex
        return [exe, str(video)] + shlex.split(args) + ["--output_dir", str(out_dir)]

    def for_episode(self, video, watched_seconds, show_key="", ep=0, show="", ja="",
                    shared_key="", retrievals=None):
        """Transcribe the episode he played. Returns the same shape a fetched
        file returns, or None.

        NEVER call this from the reply path or the poll: it is minutes of GPU
        on the calling thread. Its one caller is the watching worker, which is
        already off the loop and already fetching pages."""
        why = self.why_not(video, watched_seconds)
        if why:
            logger.log(f"[subs] not transcribing {os.path.basename(str(video))[:60]}: {why}")
            return None
        text = ""
        # The machine's store is a CALL ARGUMENT, never an attribute set after
        # this object was built: it reaches its owner as a declared wire and
        # is handed down by whichever module holds it, the same shape the
        # model client takes through this path.
        store = retrievals if retrievals is not None else self.retrievals
        reused = False
        if store is not None and shared_key:
            # one run between the two characters: the claim is the store's
            row = store.get_or_fetch(
                "whisper", shared_key, lambda: self._run(video, show_key, ep, show, ja),
                model=os.path.basename(str(self._c("whisper_exe", "whisper"))))
            if row:
                text = row.get("text") or ""
                reused = bool(row.get("reused"))
                if reused:
                    logger.log(f"[subs] the transcript of ep{ep} was made on this machine "
                               f"already; nothing was run")
        else:
            text = self._run(video, show_key, ep, show, ja)
        if not text:
            return None
        from sim import subtitles as S
        lines = S.parse(text, "whisper.srt")
        share = S.japanese_share(lines)
        floor = float(self._c("subtitles_min_ja_share", 0.6))
        if len(lines) < int(self._c("subtitles_min_lines", 40)) or share < floor:
            logger.log(f"[subs] what was transcribed is {len(lines)} line(s), "
                       f"{share:.0%} Japanese; it does not qualify")
            return None
        saved = ""
        if self.archive and show_key:
            saved = self.archive.save(show_key, ep, "subtitle", text.encode("utf-8"),
                                      url=str(video), ext=".srt", name="whisper",
                                      note="whisper, transcribed on this machine",
                                      show=show, ja=ja)
        self._beside_the_video(video, text)
        logger.log(f"[subs] {show or ja} ep{ep}: transcribed here, {len(lines)} lines, "
                   f"{share:.0%} Japanese")
        return {"lines": lines, "source": str(video), "provenance": "whisper",
                "file": os.path.basename(str(video)), "ja_share": round(share, 3),
                "archived": saved, "origin": "transcribed on this machine",
                # 0 when the machine's store answered and no GPU was spent
                "gpu_seconds": 0.0 if reused else float(self.last_run_seconds or 0)}

    def _beside_the_video(self, video, text):
        """His player should find it next time. Never over the top of a file
        that is already there -- that one is his, or it is the sidecar this
        step only runs because there was not one."""
        try:
            p = os.path.splitext(str(video))[0] + ".srt"
            if os.path.exists(p):
                return ""
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
            logger.log(f"[subs] the transcript was written beside his video as "
                       f"{os.path.basename(p)[:60]}")
            return p
        except OSError as e:
            logger.log(f"[subs] the transcript was kept in the archive only; his video's "
                       f"folder could not be written to ({type(e).__name__})")
            return ""

    def _run(self, video, show_key, ep, show, ja):
        """One run of his transcriber. Returns the SRT text, or ""."""
        out = tempfile.mkdtemp(prefix="scail_whisper_")
        stem = os.path.splitext(os.path.basename(str(video)))[0]
        cmd = self._command(video, out)
        started = time.time()
        self._note_run()
        code, console = -1, ""
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace",
                               timeout=float(self._c("whisper_timeout_seconds", 3600) or 3600))
            code, console = r.returncode, (r.stdout or "") + (r.stderr or "")
        except Exception as e:      # by TYPE only: a console line can hold a path
            logger.log(f"[subs] the transcriber did not finish ({type(e).__name__})")
            console = type(e).__name__
        took = time.time() - started
        self.last_run_seconds = took
        srt = os.path.join(out, stem + ".srt")
        text = ""
        try:
            if os.path.exists(srt):
                with open(srt, encoding="utf-8-sig", errors="replace") as fh:
                    text = fh.read()
        except OSError:
            text = ""
        # His own bridge treats a crash on cleanup with the file written as a
        # success (exit 0xC0000409 happens on teardown), and so does this: the
        # answer is the file, not the code.
        logger.log(f"[subs] the transcriber ran for {took / 60:.1f} min, exit {code}, "
                   f"{len(text)} characters of subtitle")
        if self.archive and show_key:
            self.archive.save(show_key, ep, "whisper_log", console[-40000:], url="",
                              ext=".txt", name="run", note=f"exit {code}, {took:.0f}s",
                              show=show, ja=ja)
        try:
            shutil.rmtree(out, ignore_errors=True)
        except Exception:
            pass
        return text
