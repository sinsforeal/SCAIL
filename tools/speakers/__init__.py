"""Timed, aligned, speaker-attributed dialogue for one video, as a machine tool.

The pipeline this belongs to takes an episode of animation and ends with a
character card built from everything one person in it says. Everything after
this package needs the same thing first: the spoken lines of the episode, in
order, with a start time that is true of THIS video file, and with a name on
as many of them as can be had for free.

Two ways in, because the material comes two ways:

* a Japanese subtitle exists somewhere -- beside the video, or in the archive
  mirror on this machine. Its text can be matched against a reference line set
  directly, so the alignment is a text problem;
* no Japanese subtitle exists, only an English fansub. Its text says nothing
  about the Japanese, but its cue onsets say when somebody speaks. That is a
  timing skeleton, and a Japanese line set can be fitted to it on onsets and
  gaps alone.

The alignment is piecewise and never a single shift. A broadcast rip is timed
to the broadcast cut, which carries a sponsor card the disc does not, and the
gap between the two cuts changes again at the commercial break. A file whose
fit is poor is refused rather than shifted into place.

Nothing here reads or writes a character's configuration, save or code. Its
cache is `data/speakers/<subject>/`, its readable output goes beside the video,
and every step is idempotent: a finished step is skipped unless `--redo`.

    python -m tools.speakers --help
"""
