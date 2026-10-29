"""Running the speech recogniser on another machine on the network.

The graphics card that is free is not always the card in the machine holding
the episode. Copying a 16 kHz mono audio file over the network costs a few
seconds and lets the recogniser run wherever there is a card, so where the
recogniser lives is a fact about a machine and is written in the subject file
beside the other machine facts, never in this package.

Three commands and no daemon: copy the audio up, run the executable over a
remote shell, copy the subtitle back. Nothing is left running on the other
machine, and the file that comes back is registered exactly like a transcript
made here, so nothing downstream can tell the difference except the note in the
record saying where it ran.

Two details of a Windows remote, both learned the hard way. Its default remote
shell is the command interpreter, which chains with `&&` and not with `;`, and
needs `cd /d` to change drive and directory in one step. And a path handed to
the copy program is parsed twice, once here and once by that interpreter, and
no quoting of a space survives both: an episode's own name, which always has
spaces in it, came back as a path beginning with two backslashes. So nothing
copied either way is allowed a space in its name. The audio goes up under a
name with the spaces replaced, and the subtitle comes back under a fixed name
the far side copies it to. The one path this cannot fix is the working folder
on the other machine, which must itself have no space in it.
"""
import os
import subprocess
import time


def _win(path):
    return path.replace("/", "\\")


def _posix(path):
    return path.replace("\\", "/")


def _remote(host, path):
    return "%s:%s" % (host, _posix(path))


def _safe(name):
    """A filename with nothing in it that a second shell would re-parse."""
    out = []
    for ch in name:
        out.append(ch if (ch.isalnum() or ch in "._-") else "_")
    return "".join(out)


def _run(cmd, timeout=None):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def send(host, local_path, remote_dir):
    """Copy one file to the other machine, returning its path there."""
    dest = _posix(remote_dir).rstrip("/") + "/" + _safe(os.path.basename(local_path))
    r = _run(["scp", "-o", "BatchMode=yes", local_path, _remote(host, dest)])
    if r.returncode != 0:
        raise RuntimeError("could not copy the audio up: %s"
                           % (r.stderr or r.stdout or "").strip()[:300])
    return dest


def transcribe(host, exe, remote_dir, remote_audio, tag, args, log=print,
               timeout=7200):
    """Run the recogniser on the other machine and leave its subtitle there.

    Returns (path of the subtitle on the other machine, seconds of wall clock,
    the command that was run, the last lines it printed). The exit code is not
    the test: this recogniser has ended with a teardown fault and a complete
    file every time it has been watched, here and on the other machine.
    """
    d = _win(remote_dir).rstrip("\\")
    out_dir = "%s\\out_%s" % (d, tag)
    stem = os.path.splitext(os.path.basename(remote_audio))[0]
    cmd = ('cd /d "%s" && "%s" "%s" %s --output_dir "%s" && copy /y "%s\\%s.srt" '
           '"%s\\transcript.srt"'
           % (d, _win(exe), os.path.basename(remote_audio), args, out_dir,
              out_dir, stem, out_dir))
    log("on %s: %s" % (host, cmd))
    t0 = time.time()
    r = _run(["ssh", "-o", "BatchMode=yes", host, cmd], timeout=timeout)
    took = time.time() - t0
    tail = [x for x in (r.stdout or "").strip().split("\n")[-3:] if x.strip()]
    tail += [x for x in (r.stderr or "").strip().split("\n")[-3:] if x.strip()]
    return "%s\\transcript.srt" % out_dir, took, cmd, tail


def fetch(host, remote_path, local_path):
    """Copy the subtitle back."""
    d = os.path.dirname(os.path.abspath(local_path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    r = _run(["scp", "-o", "BatchMode=yes", _remote(host, remote_path), local_path])
    if r.returncode != 0 or not os.path.exists(local_path):
        raise RuntimeError("could not copy the subtitle back: %s"
                           % (r.stderr or r.stdout or "").strip()[:300])
    return local_path
