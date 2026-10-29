"""The command line: find, align, score, and write the line set out.

    python -m tools.speakers init      SUBJECT --video FILE [--mirror DIR]
    python -m tools.speakers candidates SUBJECT
    python -m tools.speakers songs     SUBJECT [--cut] [--full]        # mute the songs
    python -m tools.speakers transcribe SUBJECT --exe FILE --args "..." [--audio F] [--tag T]
    python -m tools.speakers transcribe SUBJECT --import FILE --tag T  # made elsewhere
    python -m tools.speakers remote    SUBJECT --audio FILE --tag T    # on another machine
    python -m tools.speakers skeleton  SUBJECT [--stream N]
    python -m tools.speakers align     SUBJECT [--reference FILE]      # on text
    python -m tools.speakers blind     SUBJECT [--candidate NAME]      # on onsets only
    python -m tools.speakers agree     SUBJECT --candidate NAME
    python -m tools.speakers caseb     SUBJECT [--segments FILE] [--label NAME]
    python -m tools.speakers spotcheck SUBJECT --tag NAME [--against FILE] [--dry-run]
    python -m tools.speakers snap      --segments FILE --reference FILE --out FILE
    python -m tools.speakers score     --reference FILE --hypothesis FILE
    python -m tools.speakers check     SUBJECT [--aligned FILE]
    python -m tools.speakers report    SUBJECT
    python -m tools.speakers selftest

Every step writes its result under `data/speakers/SUBJECT/` and reads it back
on the next run, so a step already done is skipped unless `--redo` is given.
The subject's own file says which video, which reference line set, which
mirror folder and which names in the material answer to which name in the
scoring key; nothing about the work being processed is in this package.
"""
import argparse
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.speakers import (align, normal, remote, songs, sources, spotcheck,
                            timedtext, truth)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.join(ROOT, "data", "speakers")

DEFAULT_SUBJECT = {
    "video": "",
    "reference": "",
    "mirror_dir": "",
    "episode": None,
    "out_dir": "",
    "out_prefix": "",
    "english_stream": None,
    "key": "",
    "run_gap_s": 5.0,
    "extra_candidates": [],
    "whisper_exe": "",
    "whisper_args": "",
    # the other machine's card, when the one holding the episode is busy. Which
    # machine, where the recogniser sits on it and which folder to work in are
    # facts about machines, so they live beside the local recogniser's path and
    # are never looked for in anything belonging to a person.
    "remote_host": "",
    "remote_exe": "",
    "remote_dir": "",
    "name_map": {},
}

# the two ways of reading a key timestamp that carries no fraction: the
# half second the brief asked for, and the whole second the key can
# actually express, a cue at 6:28.6 being written 6:28
_WINDOWS = [(-0.5, 0.5, "within 500 ms of the stated second"),
            (0.0, 1.0, "inside the stated second")]


def log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


def subjdir(name):
    return os.path.join(BASE, name)


def load_subject(name):
    p = os.path.join(subjdir(name), "subject.json")
    if not os.path.exists(p):
        sys.exit("no subject '%s': run init first (%s)" % (name, p))
    cfg = dict(DEFAULT_SUBJECT)
    cfg.update(json.load(io.open(p, encoding="utf-8")))
    for k in ("video", "reference", "mirror_dir", "out_dir", "key"):
        if cfg.get(k):
            cfg[k] = os.path.join(ROOT, cfg[k]) if not os.path.isabs(cfg[k]) else cfg[k]
    return cfg


def cache(name, *parts):
    p = os.path.join(subjdir(name), *parts)
    d = os.path.dirname(p)
    if not os.path.isdir(d):
        os.makedirs(d)
    return p


def _load_json(path):
    if not os.path.exists(path):
        return None
    return json.load(io.open(path, encoding="utf-8"))


def _short(s, n=26):
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def _mmss(t):
    if t is None:
        return "--:--"
    return "%d:%05.2f" % (int(t) // 60, t - 60 * (int(t) // 60))


# ---------------------------------------------------------------- commands

def cmd_init(a):
    d = subjdir(a.subject)
    if not os.path.isdir(d):
        os.makedirs(d)
    p = os.path.join(d, "subject.json")
    cfg = dict(DEFAULT_SUBJECT)
    if os.path.exists(p):
        cfg.update(json.load(io.open(p, encoding="utf-8")))
    if a.video:
        cfg["video"] = os.path.relpath(os.path.abspath(a.video), ROOT).replace("\\", "/")
    if a.mirror:
        cfg["mirror_dir"] = os.path.relpath(os.path.abspath(a.mirror), ROOT).replace("\\", "/")
    if a.reference:
        cfg["reference"] = os.path.relpath(os.path.abspath(a.reference), ROOT).replace("\\", "/")
    if a.episode is not None:
        cfg["episode"] = a.episode
    timedtext.write_json(cfg, p)
    log("subject written: %s" % p)


def _written(subject):
    """Every file this tool has put beside the video for this subject.

    They have to be remembered, because they are subtitle files of this
    episode sitting in the folder the search looks in first, and on the second
    run the tool was offering its own output back to itself as a candidate to
    align. Nothing in a `.srt` can carry a marker saying who wrote it, so the
    list is kept instead.
    """
    return set(_load_json(cache(subject, "written.json")) or [])


def _remember(subject, paths):
    known = _written(subject)
    known.update(os.path.abspath(p) for p in paths)
    timedtext.write_json(sorted(known), cache(subject, "written.json"))


def _candidate_paths(cfg, subject=""):
    out = []
    mine = _written(subject) if subject else set()
    ref = os.path.abspath(cfg["reference"]) if cfg.get("reference") else ""
    for p in sources.beside(cfg["video"]):
        out.append(("beside the video", p))
    for p in sources.in_mirror(cfg.get("mirror_dir"), cfg.get("episode")):
        out.append(("the archive mirror", p))
    # a set in the mirror whose numbering does not agree with the rest -- one
    # release here starts the season at 1 and so calls the pre-broadcast
    # episode 1 as well -- is named in the subject file rather than guessed at
    for rel in cfg.get("extra_candidates") or []:
        p = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
        if os.path.exists(p):
            out.append(("named in the subject file", p))
    seen = set()
    kept = []
    for where, p in out:
        ap = os.path.abspath(p)
        if ap in seen or ap in mine:
            continue
        seen.add(ap)
        kept.append({"where": where, "path": ap, "name": os.path.basename(p),
                     "is_reference": ap == ref})
    return kept


def collect_candidates(cfg, subject, redo=False):
    p = cache(subject, "candidates.json")
    if os.path.exists(p) and not redo:
        return _load_json(p)
    rows = []
    for c in _candidate_paths(cfg, subject):
        lines = timedtext.parse(c["path"])
        share = sources.japanese_share(lines)
        named = sum(1 for ln in lines if ln["named"])
        rows.append(dict(c, lines=len(lines), japanese_share=round(share, 4),
                         named=named,
                         first_cue=round(lines[0]["start"], 3) if lines else None,
                         last_cue=round(lines[-1]["start"], 3) if lines else None,
                         japanese=share >= 0.6))
    timedtext.write_json(rows, p)
    return rows


def cmd_candidates(a):
    cfg = load_subject(a.subject)
    rows = collect_candidates(cfg, a.subject, a.redo)
    print("%-62s %-18s %6s %6s %6s %8s %s" %
          ("file", "found", "lines", "named", "ja", "first", "role"))
    for r in rows:
        print("%-62s %-18s %6d %6d %5.0f%% %8s %s" %
              (_short(r["name"], 62), r["where"], r["lines"], r["named"],
               100 * r["japanese_share"], _mmss(r["first_cue"]),
               "reference" if r["is_reference"] else
               ("candidate" if r["japanese"] else "not Japanese, skipped")))
    return rows


def cmd_skeleton(a):
    cfg = load_subject(a.subject)
    streams = sources.probe_streams(cfg["video"])
    print("subtitle streams in the video:")
    for s in streams:
        print("  %d  %-6s %-4s %s" % (s["index"], s["codec"], s["language"], s["title"]))
    idx = a.stream if a.stream is not None else cfg.get("english_stream")
    if idx is None:
        picked = [s for s in streams if s["language"].startswith("en")] or streams
        if not picked:
            sys.exit("the video carries no subtitle stream")
        idx = picked[0]["index"]
    ext = ".ass" if any(s["index"] == idx and s["codec"] in ("ass", "ssa")
                        for s in streams) else ".srt"
    out = cache(a.subject, "cache", "stream%d%s" % (idx, ext))
    sources.extract_stream(cfg["video"], idx, out, redo=a.redo)
    sk = sources.skeleton(out)
    sk["stream"] = idx
    sk["file"] = os.path.relpath(out, ROOT).replace("\\", "/")
    timedtext.write_json(sk, cache(a.subject, "skeleton.json"))
    print("\nextracted stream %d to %s" % (idx, sk["file"]))
    print("  styles kept as dialogue : %s" % ", ".join(sk["kept_styles"]))
    print("  styles dropped          : %s" % ", ".join(sk["dropped_styles"]))
    print("  events %d -> dropped by style %d, dropped as placed-on-picture %d, "
          "cues merged to %d" % (sk["events"], sk["dropped_by_style"],
                                 sk["dropped_as_placed"], len(sk["cues"])))
    print("  actor field filled on    : %s" % (", ".join(sk["actors"]) or "no line"))
    print("  first onset %s, last onset %s"
          % (_mmss(sk["cues"][0]["start"]), _mmss(sk["cues"][-1]["start"])))
    return sk


def _fit_one(cand_lines, ref_lines, tol, confirm):
    anchors, fwd = align.text_anchors(cand_lines, ref_lines)
    # a tolerance of zero means "measure it from this pair of files"
    tol = tol or align.tolerance(anchors)
    segs = align.merge_small(align.fit_segments(anchors, tol=tol, confirm=confirm),
                             tol=tol)
    q = align.fit_quality(anchors, segs)
    v = align.verdict(len(cand_lines), len(ref_lines), align.match_rate(fwd), q, segs)
    v["tolerance"] = round(tol, 3)
    v["scatter"] = round(align.scatter(anchors), 3)
    return anchors, segs, q, v


def _print_fit(name, r):
    print("\n  %s" % name)
    print("    lines %d, lines with a counterpart %.0f%%, anchors %d (%.0f%% of the "
          "shorter file)" % (r["lines"], 100 * r["match_rate"], r["quality"]["anchors"],
                             100 * r["coverage"]))
    print("    %-11s %-11s %8s %9s %9s %9s" %
          ("from", "to", "anchors", "offset", "rms", "max"))
    for s in r["segments"]:
        print("    %-11s %-11s %8d %8.3fs %8.3fs %8.3fs" %
              (_mmss(s["from"]), _mmss(s["to"]), s["anchors"], s["offset"],
               s["residual_rms"], s["residual_max"]))
    q = r["quality"]
    print("    the two files agree inside a stretch to %.3fs, so a step counts as a "
          "cut past %.3fs" % (r.get("scatter", 0), r.get("tolerance", 0)))
    print("    after fitting: median anchor error %.3fs, within 250 ms %.0f%%, "
          "within 500 ms %.0f%%, within 1 s %.0f%%"
          % (q["median_error"] or 0, 100 * q["within_250ms"],
             100 * q["within_500ms"], 100 * q["within_1000ms"]))
    if r["accepted"]:
        print("    ACCEPTED")
    else:
        for why in r["reasons"]:
            print("    REFUSED: %s" % why)


def cmd_songs(a):
    """Where the opening and the ending are, and the audio with them muted.

    The recogniser writes a song's lyrics down as speech, so the songs are
    taken out of what it hears. They are muted rather than removed, which keeps
    every later timestamp comparable with a transcript of the whole episode and
    with any caption of the same video.
    """
    cfg = load_subject(a.subject)
    sk = _load_json(cache(a.subject, "skeleton.json")) or {}
    ass_path = sk.get("file")
    ass_path = os.path.join(ROOT, ass_path) if ass_path else ""
    found = songs.find_spans(cfg["video"], ass_path)
    spans = found["spans"]
    if not spans:
        sys.exit("no song span found: the video has no chapter mark naming a "
                 "song and the English track has no song style")
    print("song spans decided by %s, against %d dialogue cues of the English "
          "track" % (found["decided_by"], found["dialogue_cues"]))
    for s in spans:
        print("  %s .. %s  (%s)" % (_mmss(s["from"]), _mmss(s["to"]), s["rule"]))
        for p in s["pushed"]:
            print("      the %s edge moved off a spoken cue at %s..%s: %s"
                  % (p["edge"], _mmss(p["cue_from"]), _mmss(p["cue_to"]),
                     _short(p["cue_text"] or "(a cue with no words in it)", 40)))
        if s["to"] <= s["from"]:
            sys.exit("that span has no room left after being pushed off the "
                     "dialogue cues; the song mark and the dialogue disagree")
    timedtext.write_json(dict(found, video=os.path.basename(cfg["video"])),
                         os.path.join(subjdir(a.subject), "songs.json"))
    log("wrote %s" % os.path.relpath(os.path.join(subjdir(a.subject), "songs.json"), ROOT))
    stem = a.stem or os.path.splitext(os.path.basename(cfg["video"]))[0]
    for want, suffix, use in ((a.cut, ".cut.wav", spans), (a.full, ".full.wav", ())):
        if not want:
            continue
        out = cache(a.subject, "cache", "cut", stem + suffix)
        if os.path.exists(out) and not a.redo:
            log("already written: %s" % os.path.relpath(out, ROOT))
            continue
        log("writing %s" % os.path.relpath(out, ROOT))
        _p, af = songs.write_audio(cfg["video"], out, use, redo=a.redo)
        if af:
            log("  filter: %s" % af)
        for row in songs.loudness(out, spans):
            print("    level %-34s %.4f" % (row["where"], row["rms"]))
    return found


def _tr_names(tag):
    """Cache folder, record file and the name beside the video, for one run.

    A run with no tag keeps the names the first run wrote, so the files and the
    record an earlier report points at stay exactly where it says they are.
    """
    if not tag:
        return "transcript", "transcript.json", ".whisper.ja.srt"
    return ("transcript_%s" % tag, "transcript_%s.json" % tag,
            ".whisper-%s.ja.srt" % tag)


def _transcript_record(subject, tag):
    _folder, rec_name, _suffix = _tr_names(tag)
    return _load_json(os.path.join(subjdir(subject), rec_name))


def _transcripts(subject):
    """Every recogniser run this subject has a record of, oldest naming first."""
    d = subjdir(subject)
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d)):
        if name == "transcript.json" or (name.startswith("transcript_")
                                         and name.endswith(".json")):
            row = _load_json(os.path.join(d, name)) or {}
            row.setdefault("tag", "")
            out.append(row)
    return out


def _register(subject, cfg, made, tag, record):
    """Put a finished transcript beside the video and write its record.

    One path for a transcript made here and a transcript made on another
    machine, so nothing downstream can tell them apart except by reading the
    record, which says where it came from.
    """
    _folder, rec_name, suffix = _tr_names(tag)
    lines = timedtext.parse(made)
    log("%s: %d segments, first %s, last %s"
        % (os.path.relpath(made, ROOT), len(lines),
           _mmss(lines[0]["start"]) if lines else "-",
           _mmss(lines[-1]["start"]) if lines else "-"))
    stem = os.path.splitext(os.path.basename(cfg["video"]))[0]
    beside = os.path.join(cfg.get("out_dir") or os.path.dirname(cfg["video"]),
                          (cfg.get("out_prefix") or stem) + suffix)
    shutil.copyfile(made, beside)
    _remember(subject, [beside])
    log("copied beside the video: %s" % os.path.relpath(beside, ROOT))
    row = dict(record)
    row.update({"tag": tag, "segments": len(lines),
                "file": os.path.relpath(made, ROOT).replace("\\", "/"),
                "beside": os.path.relpath(beside, ROOT).replace("\\", "/")})
    timedtext.write_json(row, cache(subject, rec_name))
    return made


def cmd_transcribe(a):
    """Speech recognition over the episode's own audio, cached on disk.

    The words this produces are the fallback line set for an episode with no
    Japanese subtitle anywhere, and the measurement for every episode that has
    one: scoring the recogniser against a caption rip says how much of any
    later error was transcription rather than anything after it.

    The recogniser is named on the command line or in the subject file and is
    never read out of a character's configuration, because where an executable
    sits is a fact about this machine and not about anybody. It reads the video
    itself, so no audio is extracted first -- unless `--audio` names a file, as
    it does for the run over the episode with its songs muted.

    `--import` covers the third case: the answer already exists, made on
    another machine or by hand, and only needs registering. What matters is
    that a transcript made anywhere is registered the same way, because the
    steps after this one read the record and not the machine.
    """
    cfg = load_subject(a.subject)
    folder, _rec, _suffix = _tr_names(a.tag)
    out_dir = cache(a.subject, "cache", folder)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    if a.import_file:
        if not os.path.exists(a.import_file):
            sys.exit("no such file to import: %s" % a.import_file)
        made = os.path.join(out_dir, os.path.basename(a.import_file))
        if os.path.abspath(made) != os.path.abspath(a.import_file):
            shutil.copyfile(a.import_file, made)
        log("imported %s" % os.path.relpath(a.import_file, ROOT))
        return _register(a.subject, cfg, made, a.tag,
                         {"source": "imported", "args": a.note,
                          "came_from": a.import_file.replace("\\", "/"),
                          "seconds": float(a.seconds or 0), "ran_on": a.ran_on})
    exe = a.exe or cfg.get("whisper_exe") or ""
    args = a.args or cfg.get("whisper_args") or ""
    if not exe or not os.path.exists(exe):
        sys.exit("no speech recogniser: pass --exe, which is a fact about this "
                 "machine and so is not looked for anywhere else")
    heard = a.audio or cfg["video"]
    if not os.path.exists(heard):
        sys.exit("no such audio or video: %s" % heard)
    stem = os.path.splitext(os.path.basename(heard))[0]
    made = os.path.join(out_dir, stem + ".srt")
    if os.path.exists(made) and not a.redo:
        log("already transcribed: %s" % os.path.relpath(made, ROOT))
        return made
    cmd = [exe, heard] + shlex.split(args) + ["--output_dir", out_dir]
    log("running the speech recogniser on the graphics card; a 23 minute "
        "episode took 6 to 21 minutes on this machine before")
    log(" ".join(cmd))
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    took = time.time() - t0
    log("exit %s (0x%X) after %.1f minutes"
        % (r.returncode, r.returncode & 0xFFFFFFFF, took / 60.0))
    for line in (r.stderr or r.stdout or "").strip().split("\n")[-3:]:
        log("  %s" % line[:160])
    if not os.path.exists(made):
        sys.exit("the recogniser wrote nothing to %s" % out_dir)
    # this recogniser has crashed on teardown with the file already complete
    # every time it has been watched, so the exit code is not the test; the
    # file is
    return _register(a.subject, cfg, made, a.tag,
                     {"source": "this machine", "exe": exe, "args": args,
                      "heard": os.path.relpath(heard, ROOT).replace("\\", "/"),
                      "returncode": r.returncode, "seconds": round(took, 1),
                      "ran_on": "this machine"})


def cmd_remote(a):
    """The same transcription on another machine's card, over the network."""
    cfg = load_subject(a.subject)
    host = a.host or cfg.get("remote_host") or ""
    exe = a.exe or cfg.get("remote_exe") or ""
    rdir = a.dir or cfg.get("remote_dir") or ""
    args = a.args or cfg.get("whisper_args") or ""
    if not (host and exe and rdir):
        sys.exit("no other machine: pass --host, --exe and --dir, or set "
                 "remote_host, remote_exe and remote_dir in subject.json")
    if not os.path.exists(a.audio):
        sys.exit("no such audio: %s" % a.audio)
    folder, _rec, _suffix = _tr_names(a.tag)
    made = os.path.join(cache(a.subject, "cache", folder),
                        os.path.splitext(os.path.basename(a.audio))[0] + ".srt")
    if os.path.exists(made) and not a.redo:
        log("already transcribed under the tag %r: %s" % (a.tag, os.path.relpath(made, ROOT)))
        return made
    log("copying %.1f MB to %s" % (os.path.getsize(a.audio) / 1e6, host))
    there = remote.send(host, a.audio, rdir)
    log("running the recogniser on %s; nothing of this machine's card is used"
        % host)
    got, took, cmd, tail = remote.transcribe(host, exe, rdir, there, a.tag, args,
                                             log=log)
    log("finished after %.1f minutes" % (took / 60.0))
    for line in tail:
        log("  %s" % line[:160])
    remote.fetch(host, got, made)
    return _register(a.subject, cfg, made, a.tag,
                     {"source": "another machine on the network", "exe": exe,
                      "args": args, "ran_on": host, "command": cmd,
                      "heard": os.path.basename(a.audio),
                      "seconds": round(took, 1)})


def cmd_align(a):
    cfg = load_subject(a.subject)
    ref_path = a.reference or cfg["reference"]
    if not ref_path or not os.path.exists(ref_path):
        sys.exit("no reference line set: pass --reference or set it in subject.json")
    ref_lines = timedtext.parse(ref_path)
    log("reference %s: %d lines" % (os.path.basename(ref_path), len(ref_lines)))
    rows = collect_candidates(cfg, a.subject, a.redo)
    results = []
    for c in rows:
        if c["is_reference"] or not c["japanese"]:
            continue
        lines = timedtext.parse(c["path"])
        anchors, segs, q, v = _fit_one(lines, ref_lines, a.tol, a.confirm)
        r = dict(c)
        r.update({"segments": segs, "quality": q, "anchors": len(anchors)})
        r.update(v)
        results.append(r)
        _print_fit(c["name"], r)
    ok = [r for r in results if r["accepted"]]
    if not ok:
        print("\nno candidate fits this video; nothing written")
        timedtext.write_json({"winner": None, "candidates": results},
                             cache(a.subject, "align_%s.json" % a.label))
        return None
    best = max(r["coverage"] for r in ok)
    tied = [r for r in ok if best - r["coverage"] <= 0.03]
    # the fit decides who is eligible; among files that fit equally well the
    # one carrying the most names wins, because names are the reason for
    # preferring a caption rip to a transcript in the first place
    winner = max(tied, key=lambda r: (r["named"], r["coverage"], -len(r["segments"])))
    print("\nwinner: %s (%d of %d lines named by the file itself)"
          % (winner["name"], winner["named"], winner["lines"]))
    if len(tied) > 1:
        print("  tied on fit with: %s" % ", ".join(_short(r["name"], 40)
                                                   for r in tied if r is not winner))
    out = _write_output(a.subject, cfg, winner, a.label, ref_path)
    if a.write_all:
        # every accepted file, not only the winner: a later step may want the
        # names of a rip that lost on timing, because two rips of one episode
        # label different lines
        for r in ok:
            if r is not winner:
                _write_output(a.subject, cfg, r, a.label + "-also", ref_path)
    timedtext.write_json({"winner": winner["name"], "candidates": results,
                          "reference": os.path.basename(ref_path),
                          "output": out},
                         cache(a.subject, "align_%s.json" % a.label))
    return results


def _write_output(subject, cfg, result, case, ref_path=""):
    """The aligned line set beside the video, as cues and as a styled file."""
    lines = timedtext.parse(result["path"])
    moved = align.apply_segments(lines, result["segments"])
    runs = timedtext.apply_runs(moved, cfg.get("run_gap_s", 5.0))
    stem = "%s.%s.%s" % (cfg.get("out_prefix") or "episode", case,
                         _tag(result["name"]))
    d = cfg.get("out_dir") or os.path.dirname(cfg["video"])
    srt = os.path.join(d, stem + ".ja.srt")
    ass = os.path.join(d, stem + ".ja.ass")
    notes = ["aligned by tools/speakers, case %s" % case,
             "source: %s" % result["name"],
             "reference: %s" % os.path.basename(ref_path or cfg.get("reference") or ""),
             "offsets: " + "; ".join("%s..%s %+.3fs" % (_mmss(s["from"]), _mmss(s["to"]),
                                                        s["offset"])
                                     for s in result["segments"]),
             "Actor is the speaker; the effect field says whether the file "
             "named the line or the run rule carried the name to it"]
    timedtext.write_srt(moved, srt)
    timedtext.write_ass(moved, ass, notes)
    _remember(subject, [srt, ass])
    log("wrote %s" % os.path.relpath(srt, ROOT))
    log("wrote %s" % os.path.relpath(ass, ROOT))
    print("  speaker names: %d named by the file, %d carried by the run rule "
          "(gap %.1fs), %d left unnamed, of %d lines"
          % (runs["direct"], runs["carried"], runs["gap_s"], runs["unnamed"],
             runs["lines"]))
    timedtext.write_json({"runs": runs, "lines": moved},
                         cache(subject, "aligned_%s_%s.json" % (case, _tag(result["name"]))))
    timedtext.write_json({"runs": runs, "lines": moved},
                         cache(subject, "aligned_%s.json" % case))
    return {"srt": os.path.relpath(srt, ROOT).replace("\\", "/"),
            "ass": os.path.relpath(ass, ROOT).replace("\\", "/"), "runs": runs}


def _tag(name):
    """A short, filesystem-safe word for where a candidate came from."""
    stem = os.path.splitext(os.path.basename(name))[0]
    for mark in ("[", "]", "(", ")", " ", ".", "-"):
        stem = stem.replace(mark, "_")
    parts = [p for p in stem.split("_") if p]
    return "-".join(parts[:2])[:28] or "candidate"


def cmd_blind(a):
    """Case B: fit a Japanese file to the video's own English track on times."""
    cfg = load_subject(a.subject)
    sk = _load_json(cache(a.subject, "skeleton.json"))
    if not sk:
        sys.exit("run `skeleton` first: the timing skeleton is not in the cache")
    ref_starts = [c["start"] for c in sk["cues"]]
    rows = collect_candidates(cfg, a.subject, False)
    picked = [c for c in rows if c["japanese"] and
              (not a.candidate or a.candidate.lower() in c["name"].lower())]
    if not picked:
        sys.exit("no Japanese candidate matches --candidate %r" % a.candidate)
    log("skeleton: %d spoken cues from the video's own English track" % len(ref_starts))
    results = []
    for c in picked:
        lines = timedtext.parse(c["path"])
        anchors, offsets = align.onset_anchors(
            [ln["start"] for ln in lines], ref_starts,
            max_offset=a.max_offset, tol=a.onset_tol,
            switch_penalty=a.switch_penalty)
        tol = a.tol or align.tolerance(anchors)
        segs = align.merge_small(align.fit_segments(anchors, tol=tol,
                                                    confirm=a.confirm),
                                 min_anchors=8, tol=tol)
        q = align.fit_quality(anchors, segs)
        rate = len(anchors) / float(max(1, min(len(lines), len(ref_starts))))
        v = align.verdict(len(lines), len(ref_starts), rate, q, segs,
                          min_match=0.30, min_coverage=0.30,
                          min_within=0.80, max_rms=0.60)
        r = dict(c)
        r.update({"segments": segs, "quality": q, "anchors": len(anchors),
                  "offsets_considered": [round(x, 2) for x in offsets]})
        r.update(v)
        r["tolerance"] = round(tol, 3)
        r["scatter"] = round(align.scatter(anchors), 3)
        results.append(r)
        _print_fit(c["name"], r)
        print("    offsets the vote put forward: %s"
              % ", ".join("%+.1fs" % x for x in r["offsets_considered"]))
    ok = [r for r in results if r["accepted"]]
    out = None
    if ok:
        winner = max(ok, key=lambda r: (r["coverage"], -len(r["segments"])))
        print("\nwinner on times alone: %s" % winner["name"])
        out = _write_output(a.subject, cfg, winner, "caseB")
    else:
        print("\nno candidate fits the skeleton; nothing written")
    timedtext.write_json({"candidates": results, "output": out},
                         cache(a.subject, "align_blind.json"))
    return results


def cmd_agree(a):
    """The two methods on one file: do they put it in the same place."""
    text = _load_json(cache(a.subject, "align_%s.json" % a.label))
    blind = _load_json(cache(a.subject, "align_blind.json"))
    if not text or not blind:
        sys.exit("run `align` and `blind` first")
    key = a.candidate.lower()
    ta = next((r for r in text["candidates"] if key in r["name"].lower()), None)
    tb = next((r for r in blind["candidates"] if key in r["name"].lower()), None)
    if not ta or not tb:
        sys.exit("that candidate was not fitted by both methods")
    print("agreement on %s" % ta["name"])
    print("  on text  : %s" % "; ".join("%s..%s %+.3fs" % (_mmss(s["from"]), _mmss(s["to"]), s["offset"]) for s in ta["segments"]))
    print("  on times : %s" % "; ".join("%s..%s %+.3fs" % (_mmss(s["from"]), _mmss(s["to"]), s["offset"]) for s in tb["segments"]))
    print("\n  %-11s %12s %12s %10s" % ("at", "on text", "on times", "difference"))
    marks = sorted({s["from"] for s in ta["segments"]} | {s["to"] for s in ta["segments"]}
                   | {s["from"] for s in tb["segments"]} | {s["to"] for s in tb["segments"]})
    worst = 0.0
    for t in marks:
        x = align.offset_at(ta["segments"], t)
        y = align.offset_at(tb["segments"], t)
        worst = max(worst, abs(x - y))
        print("  %-11s %11.3fs %11.3fs %8.0f ms" % (_mmss(t), x, y, 1000 * (x - y)))
    print("\n  largest disagreement at a stretch boundary: %.0f ms" % (1000 * worst))
    # The table above is read at the boundaries the two fits chose, so a
    # boundary one line apart shows up there as the whole size of the step.
    # What the file's own lines get is the honest number, so every line is
    # asked where the two methods would put it.
    lines = timedtext.parse(ta["path"])
    diffs = [abs(align.offset_at(ta["segments"], ln["start"])
                 - align.offset_at(tb["segments"], ln["start"])) for ln in lines]
    diffs.sort()
    n = float(len(diffs))
    print("\n  over the file's own %d lines:" % len(diffs))
    for ms in (10, 50, 100, 250, 500, 1000):
        print("    within %5d ms: %5.1f%%"
              % (ms, 100.0 * sum(1 for d in diffs if d <= ms / 1000.0) / n))
    print("    median %.0f ms, worst %.0f ms, on %d lines the two disagree by more "
          "than a second" % (1000 * diffs[len(diffs) // 2], 1000 * diffs[-1],
                             sum(1 for d in diffs if d > 1.0)))
    return worst


def cmd_caseb(a):
    """The whole of case B: recognised words on the English track's timings.

    This is the shape of the answer when the archive has no Japanese subtitle
    for the episode at all. The recogniser says what was said and roughly when;
    the video's own English track says when somebody speaks, because a person
    typed a cue boundary there while watching this exact cut. Snapping the one
    onto the other gives a Japanese line set whose times are a person's rather
    than a voice detector's, with the English line kept beside each as
    something to read against, never as the text.
    """
    cfg = load_subject(a.subject)
    sk = _load_json(cache(a.subject, "skeleton.json"))
    if not sk:
        sys.exit("run `skeleton` first")
    # without a file named on the command line, the recogniser run whose tag
    # matches the label, and failing that the untagged one
    tr = a.segments or (_transcript_record(a.subject, a.label) or {}).get("file") \
        or (_transcript_record(a.subject, "") or {}).get("file")
    if not tr:
        sys.exit("run `transcribe` first, or pass --segments")
    tr = tr if os.path.isabs(tr) else os.path.join(ROOT, tr)
    segs = timedtext.parse(tr)
    cues = sk["cues"]
    snapped = align.snap_to_skeleton(segs, cues, max_shift=a.max_shift)
    by_start = {round(c["start"], 3): c for c in cues}
    for ln in snapped:
        cue = by_start.get(round(ln["start"], 3))
        if cue and ln.get("snapped"):
            ln["gloss"] = cue.get("gloss", "")
    moved = sum(1 for r in snapped if r["snapped"])
    shifts = sorted(abs(r["shift"]) for r in snapped if r["snapped"])
    print("%d recognised segments, %d snapped to a cue of the English track, "
          "%d left on the recogniser's own times"
          % (len(snapped), moved, len(snapped) - moved))
    if shifts:
        print("  the segments moved by a median of %.3fs and at most %.3fs; "
              "%d of them moved more than half a second"
              % (shifts[len(shifts) // 2], shifts[-1],
                 sum(1 for s in shifts if s > 0.5)))
    # a label keeps one recogniser run's case B result from overwriting
    # another's; without one the names of the first run are kept, because an
    # earlier report points at them
    which = ("-" + a.label) if a.label else ""
    stem = "%s.caseB.whisper%s-on-english" % (cfg.get("out_prefix") or "episode", which)
    d = cfg.get("out_dir") or os.path.dirname(cfg["video"])
    timedtext.write_srt(snapped, os.path.join(d, stem + ".ja.srt"))
    timedtext.write_ass(snapped, os.path.join(d, stem + ".ja.ass"), [
        "case B: the words from the speech recogniser, the times from the "
        "video's own English track",
        "a Comment row carries the English line for the same moment, to read "
        "against the Japanese; it is a translation and not a transcript",
        "no speaker names: the recogniser does not carry any and this case has "
        "no caption rip to take them from"])
    _remember(a.subject, [os.path.join(d, stem + ".ja.srt"),
                          os.path.join(d, stem + ".ja.ass")])
    log("wrote %s" % os.path.join(os.path.basename(d), stem + ".ja.srt"))
    log("wrote %s" % os.path.join(os.path.basename(d), stem + ".ja.ass"))
    timedtext.write_json({"runs": {"direct": 0, "carried": 0,
                                   "unnamed": len(snapped), "gap_s": 0.0,
                                   "lines": len(snapped)},
                          "snapped": moved, "lines": snapped,
                          "segments_from": os.path.relpath(tr, ROOT).replace("\\", "/")},
                         cache(a.subject, "aligned_caseBwhisper%s.json"
                               % (("_" + a.label) if a.label else "")))
    return snapped


def cmd_spotcheck(a):
    """Ask a cheap model whether each recognised line says what the English says.

    The measure for the case with no Japanese subtitle: the recogniser's line
    and the translator's line for the same cue, cue by cue, with the model
    answering match, partial or mismatch. Given a found caption as well, the
    same run says whether those answers are worth anything -- a flag that lands
    on the lines the caption also shows as wrong is a flag that can be believed
    on the next episode, where there is no caption to check it with.
    """
    cfg = load_subject(a.subject)
    blob = _load_json(cache(a.subject, "aligned_caseBwhisper%s.json"
                            % (("_" + a.tag) if a.tag else "")))
    if not blob:
        sys.exit("no case B line set for the tag %r: run `caseb --label %s` first"
                 % (a.tag, a.tag))
    lines = blob["lines"]
    cues = [{"i": k + 1, "start": ln["start"], "end": ln["end"],
             "text": ln["text"], "gloss": ln.get("gloss", "")}
            for k, ln in enumerate(lines)]
    # a segment the snapping left on the recogniser's own times has no English
    # line to be checked against, so it is counted and left out rather than
    # sent with an empty side
    checkable = [c for c in cues if c["gloss"].strip() and c["text"].strip()]
    print("case B line set for tag %r: %d lines, %d with an English line to "
          "check against, %d left on the recogniser's own times"
          % (a.tag, len(cues), len(checkable), len(cues) - len(checkable)))

    errors = {}
    if a.against:
        errors = _cue_errors(a.against, checkable)
        print("\ncharacter error rate of each checkable line against %s:"
              % os.path.basename(a.against))
        got = [errors[c["i"]] for c in checkable if c["i"] in errors]
        got.sort()
        if got:
            print("  %d lines have a stretch of the caption to compare with; "
                  "median %.3f" % (len(got), got[len(got) // 2]))
            for th in (0.15, 0.25, 0.35):
                print("    above %.2f: %d lines" % (th, sum(1 for x in got if x > th)))

    est = spotcheck.estimate(checkable, size=a.batch)
    print("\n%d cues in %d calls of about %d; the prompt is about %d tokens in "
          "and %d out, which is about $%.4f at the posted price"
          % (est["cues"], est["batches"], a.batch, est["tokens_in"],
             est["tokens_out"], est["usd"]))
    if a.dry_run:
        print("dry run: nothing was asked and nothing was spent")
        return est

    path = cache(a.subject, "cache", "spotcheck_%s.json" % (a.tag or "untagged"))
    state = {"tag": a.tag, "model": spotcheck.MODEL, "cues": len(checkable),
             "batch": a.batch, "verdicts": {}, "unanswered": [],
             "usage": {"in": 0, "out": 0, "usd": 0.0},
             "when": time.strftime("%Y-%m-%d %H:%M")}
    for n, group in enumerate(spotcheck.batches(checkable, a.batch), 1):
        log("batch %d of %d, %d cues" % (n, est["batches"], len(group)))
        ans = spotcheck.ask(group, spotcheck.key_file(ROOT), a.slug,
                            a.order.split(","), log=log)
        u = ans["usage"]
        state["usage"]["in"] += u.get("in", 0)
        state["usage"]["out"] += u.get("out", 0)
        state["usage"]["usd"] += u.get("cost") if u.get("cost") is not None else \
            (u.get("in", 0) / 1e6 * 0.14 + u.get("out", 0) / 1e6 * 0.28)
        if ans["verdicts"] is None:
            state["unanswered"].append([g["i"] for g in group])
        else:
            for v in ans["verdicts"]:
                state["verdicts"][str(v["i"])] = v
        # written after every call: a paid answer is on disk the moment it
        # exists, so a stop halfway through loses nothing already bought
        timedtext.write_json(state, path)
    log("wrote %s" % os.path.relpath(path, ROOT))
    _spotcheck_table(state, checkable, errors)
    return state


def _cue_errors(caption_path, cues):
    """Character error rate of each recognised line against a found caption.

    The pairing is the one `score --pair time` uses, because it is the same
    question: a recogniser breaks its segments where a caption does not, so the
    two sides are joined wherever their spans touch and the joined stretch is
    what gets compared. A stretch holding more than one recognised line gives
    all of them the stretch's rate, that being the smallest piece of the
    episode over which the two sides can be compared at all.
    """
    ref = timedtext.parse(caption_path)
    hyp = [{"start": c["start"], "end": c["end"], "text": c["text"]} for c in cues]
    out = {}
    for g in _time_groups(ref, hyp):
        if not g["r"] or not g["h"]:
            continue
        r = "".join(normal.normalise(ref[i]["text"]) for i in g["r"])
        h = "".join(normal.normalise(hyp[i]["text"]) for i in g["h"])
        if not r:
            continue
        rate = normal.edits(h, r) / float(len(r))
        for i in g["h"]:
            out[cues[i]["i"]] = rate
    return out


def _spotcheck_table(state, cues, errors):
    counts = {}
    for v in state["verdicts"].values():
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    n = max(1, sum(counts.values()))
    print("\nverdicts on %d of %d cues (%d cues in batches that never parsed):"
          % (sum(counts.values()), len(cues), sum(len(b) for b in state["unanswered"])))
    for k in ("match", "partial", "mismatch"):
        print("  %-9s %4d (%.0f%%)" % (k, counts.get(k, 0), 100.0 * counts.get(k, 0) / n))
    print("  the calls cost $%.4f for %d tokens in and %d out"
          % (state["usage"]["usd"], state["usage"]["in"], state["usage"]["out"]))
    by_i = {c["i"]: c for c in cues}
    print("\n  every cue the model did not call a match:")
    print("  %-10s %-9s %6s  %s" % ("at", "verdict", "cer", "why"))
    for key in sorted(state["verdicts"], key=int):
        v = state["verdicts"][key]
        if v["verdict"] == "match":
            continue
        c = by_i.get(int(key))
        cer = errors.get(int(key))
        print("  %-10s %-9s %6s  %s"
              % (_mmss(c["start"]) if c else "-", v["verdict"],
                 "%.2f" % cer if cer is not None else "-", _short(v["why"], 44)))
    if not errors:
        return
    rows = [{"verdict": v["verdict"], "cer": errors[int(k)]}
            for k, v in state["verdicts"].items() if int(k) in errors]
    print("\n  the model's flags against the caption's own errors, on the %d "
          "cues that have both:" % len(rows))
    print("  %-10s %9s %9s %9s %9s %9s %8s"
          % ("above", "flagged", "flagged", "missed", "quiet", "precision", "recall"))
    print("  %-10s %9s %9s %9s %9s %9s %8s"
          % ("", "and bad", "and fine", "bad", "and fine", "", ""))
    for th in (0.15, 0.25, 0.35):
        m = spotcheck.coincidence(rows, th)
        print("  %-10.2f %9d %9d %9d %9d %8.0f%% %7.0f%%"
              % (th, m["flagged_bad"], m["flagged_ok"], m["unflagged_bad"],
                 m["unflagged_ok"], 100 * m["precision"], 100 * m["recall"]))


def cmd_snap(a):
    segs = timedtext.parse(a.segments)
    ref = timedtext.parse(a.reference)
    out = align.snap_to_skeleton(segs, ref, max_shift=a.max_shift)
    n = sum(1 for r in out if r["snapped"])
    shifts = sorted(abs(r["shift"]) for r in out if r["snapped"])
    timedtext.write_srt(out, a.out)
    print("%d of %d segments snapped to a reference cue, %d left where they were"
          % (n, len(out), len(out) - n))
    if shifts:
        print("  median move %.3fs, largest move %.3fs"
              % (shifts[len(shifts) // 2], shifts[-1]))
    print("wrote %s" % a.out)


def _time_groups(ref, hyp, slack=0.3):
    """Groups of lines that cover the same speech, when both sets share a clock.

    A speech recogniser does not break its output where a caption breaks its
    cues: it runs two or three cues together into one segment. Scoring those
    one against one calls a perfect transcription a total failure, because the
    reference line is a third of what the segment says. So the two sets are
    joined wherever their spans touch, and each connected group is scored as
    one piece of speech.
    """
    events = [("r", i, ln) for i, ln in enumerate(ref)] + \
             [("h", i, ln) for i, ln in enumerate(hyp)]
    events.sort(key=lambda e: e[2]["start"])
    groups = []
    cur = {"r": [], "h": [], "end": -1e9}
    for side, i, ln in events:
        if ln["start"] > cur["end"] + slack and (cur["r"] or cur["h"]):
            groups.append(cur)
            cur = {"r": [], "h": [], "end": -1e9}
        cur[side].append(i)
        cur["end"] = max(cur["end"], ln["end"])
    if cur["r"] or cur["h"]:
        groups.append(cur)
    return groups


def cmd_score(a):
    """Character error rate of one line set against another.

    Two ways of deciding which line to compare with which, because the two
    jobs this serves are different. Matching on the TEXT compares two subtitle
    files that may be timed to different cuts, and says how much their wording
    differs. Matching on the CLOCK compares a speech recogniser with a caption
    of the same video, where the times are the one thing both agree on and the
    wording is the thing being measured.

    Whichever way the lines are paired, the number that matters is the last
    one: every word of the episode in order, on each side, compared as one
    string. That is the only figure a difference in where the lines were
    broken cannot move.
    """
    ref = timedtext.parse(a.reference)
    hyp = timedtext.parse(a.hypothesis)
    if a.pair == "time":
        return _score_on_time(a, ref, hyp)
    fwd = align.best_matches(hyp, ref)
    used = set()
    pairs = []
    for m in sorted(fwd, key=lambda x: -x["sim"]):
        if m["j"] < 0 or m["sim"] < a.pair_sim or m["j"] in used:
            continue
        used.add(m["j"])
        pairs.append((m["i"], m["j"], m["sim"]))
    pairs.sort(key=lambda p: p[1])
    tot_e = tot_n = 0
    worst = []
    for i, j, _s in pairs:
        h = normal.normalise(hyp[i]["text"])
        r = normal.normalise(ref[j]["text"])
        e = normal.edits(h, r)
        tot_e += e
        tot_n += len(r)
        worst.append((e / float(max(1, len(r))), j, e, len(r)))
    miss_ref = [j for j in range(len(ref)) if j not in used]
    miss_hyp = [m["i"] for m in fwd if m["j"] < 0 or m["sim"] < a.pair_sim
                or m["i"] not in {p[0] for p in pairs}]
    del_chars = sum(len(normal.normalise(ref[j]["text"])) for j in miss_ref)
    ins_chars = sum(len(normal.normalise(hyp[i]["text"])) for i in set(miss_hyp))
    print("reference  %s: %d lines" % (os.path.basename(a.reference), len(ref)))
    print("hypothesis %s: %d lines" % (os.path.basename(a.hypothesis), len(hyp)))
    print("paired %d lines at overlap >= %.2f" % (len(pairs), a.pair_sim))
    print("  character error rate over paired lines : %.4f  (%d edits / %d chars)"
          % (tot_e / float(max(1, tot_n)), tot_e, tot_n))
    print("  unpaired reference lines %d (%d chars), unpaired hypothesis lines "
          "%d (%d chars)" % (len(miss_ref), del_chars, len(set(miss_hyp)), ins_chars))
    whole = (tot_e + del_chars + ins_chars) / float(max(1, tot_n + del_chars))
    print("  character error rate over the episode  : %.4f  (unpaired lines "
          "counted as whole errors)" % whole)
    worst.sort(reverse=True)
    if a.worst:
        print("\n  worst %d paired lines:" % a.worst)
        print("  %-11s %6s %s" % ("at", "cer", "reference / hypothesis"))
        for rate, j, e, n in worst[:a.worst]:
            i = next(p[0] for p in pairs if p[1] == j)
            print("  %-11s %5.2f  %s" % (_mmss(ref[j]["start"]), rate,
                                         _short(ref[j]["text"], 30)))
            print("  %-11s %5s  %s" % ("", "", _short(hyp[i]["text"], 30)))
    _whole_episode(ref, hyp)
    return {"paired": len(pairs), "cer_paired": tot_e / float(max(1, tot_n)),
            "cer_episode": whole}


def _whole_episode(ref, hyp):
    """Every word of the episode on each side, compared as one string."""
    r = "".join(normal.normalise(ln["text"]) for ln in ref)
    h = "".join(normal.normalise(ln["text"]) for ln in hyp)
    e, bounded = normal.edits_banded(h, r)
    print("  character error rate, whole episode as one string: %s%.4f  "
          "(%d edits / %d characters; independent of where either side broke "
          "its lines)" % ("at most " if bounded else "", e / float(max(1, len(r))),
                          e, len(r)))
    return e / float(max(1, len(r)))


def _measure_on_time(ref, hyp):
    """Every number the clock-paired comparison produces, and nothing printed.

    Split out from the printing because the per-episode report needs the same
    figures for every recogniser run it lists, and a second implementation of
    the same arithmetic would drift from this one.
    """
    all_groups = _time_groups(ref, hyp)
    groups = [g for g in all_groups if g["r"] and g["h"]]
    tot_e = tot_n = 0
    worst = []
    sung = []
    for g in groups:
        r = "".join(normal.normalise(ref[i]["text"]) for i in g["r"])
        h = "".join(normal.normalise(hyp[i]["text"]) for i in g["h"])
        e = normal.edits(h, r)
        tot_e += e
        tot_n += len(r)
        if not r:
            # the caption's line here is a music mark and nothing else, so
            # there are no characters to be wrong about: what the recogniser
            # wrote is the words of the song, counted as an insertion and kept
            # out of the per-line table where a rate over nothing means nothing
            sung.append((g, len(h)))
            continue
        worst.append((e / float(max(1, len(r))), g, e, len(r)))
    lone_r = [g for g in all_groups if g["r"] and not g["h"]]
    lone_h = [g for g in all_groups if g["h"] and not g["r"]]
    del_chars = sum(len(normal.normalise(ref[i]["text"]))
                    for g in lone_r for i in g["r"])
    ins_chars = sum(len(normal.normalise(hyp[i]["text"]))
                    for g in lone_h for i in g["h"])
    r_all = "".join(normal.normalise(ln["text"]) for ln in ref)
    h_all = "".join(normal.normalise(ln["text"]) for ln in hyp)
    whole_e, bounded = normal.edits_banded(h_all, r_all)
    return {"groups": groups, "all_groups": all_groups, "worst": worst,
            "sung": sung, "lone_r": lone_r, "lone_h": lone_h,
            "edits": tot_e, "chars": tot_n,
            "deleted_chars": del_chars, "inserted_chars": ins_chars,
            "sung_chars": sum(n for _g, n in sung),
            "cer_shared": tot_e / float(max(1, tot_n)),
            "cer_episode": (tot_e + del_chars + ins_chars)
            / float(max(1, tot_n + del_chars)),
            "cer_whole_string": whole_e / float(max(1, len(r_all))),
            "whole_string_edits": whole_e, "whole_string_chars": len(r_all),
            "whole_string_bounded": bounded}


def _score_on_time(a, ref, hyp):
    """The same measurement with the lines grouped by when they were spoken."""
    m = _measure_on_time(ref, hyp)
    groups, worst, sung = m["groups"], m["worst"], m["sung"]
    tot_e, tot_n = m["edits"], m["chars"]
    lone_r, lone_h = m["lone_r"], m["lone_h"]
    del_chars, ins_chars = m["deleted_chars"], m["inserted_chars"]
    print("reference  %s: %d lines" % (os.path.basename(a.reference), len(ref)))
    print("hypothesis %s: %d lines" % (os.path.basename(a.hypothesis), len(hyp)))
    print("grouped by the clock: %d stretches of speech both sides cover, "
          "%d only the reference has, %d only the hypothesis has"
          % (len(groups), len(lone_r), len(lone_h)))
    print("  character error rate over shared stretches: %.4f  (%d edits / %d chars)"
          % (tot_e / float(max(1, tot_n)), tot_e, tot_n))
    print("  the reference alone says %d characters the hypothesis has no stretch "
          "for; the hypothesis alone says %d" % (del_chars, ins_chars))
    print("  %d stretches where the caption has only a music mark and the "
          "recogniser wrote words: %d characters"
          % (len(sung), sum(n for _g, n in sung)))
    print("  character error rate over the episode  : %.4f  (a stretch only one "
          "side has counted as a whole error)" % m["cer_episode"])
    print("  character error rate, whole episode as one string: %s%.4f  "
          "(%d edits / %d characters; independent of where either side broke "
          "its lines)" % ("at most " if m["whole_string_bounded"] else "",
                          m["cer_whole_string"], m["whole_string_edits"],
                          m["whole_string_chars"]))
    worst.sort(key=lambda x: (-x[0], -x[3]))
    if a.worst:
        print("\n  worst %d stretches:" % a.worst)
        print("  %-10s %5s %5s  %s" % ("at", "cer", "chars", "caption / recogniser"))
        for rate, g, e, n in worst[:a.worst]:
            print("  %-10s %5.2f %5d  %s" % (_mmss(ref[g["r"][0]]["start"]), rate, n,
                                             _short(" ".join(ref[i]["text"] for i in g["r"]), 24)))
            print("  %-10s %5s %5s  %s" % ("", "", "",
                                           _short(" ".join(hyp[i]["text"] for i in g["h"]), 24)))
    return {"groups": len(groups), "cer_shared": m["cer_shared"],
            "cer_episode": m["cer_episode"],
            "cer_whole_string": m["cer_whole_string"]}


def cmd_check(a):
    """The aligned line set against the hand-written scoring key."""
    cfg = load_subject(a.subject)
    key_path = a.key or cfg.get("key")
    if not key_path or not os.path.exists(key_path):
        sys.exit("no scoring key: pass --key or set it in subject.json")
    if a.aligned:
        lines = timedtext.parse(a.aligned)
        timedtext.apply_runs(lines, cfg.get("run_gap_s", 5.0))
        source = a.aligned
    else:
        blob = _load_json(cache(a.subject, "aligned_%s.json" % a.case))
        if not blob:
            sys.exit("no aligned line set cached for case %s" % a.case)
        lines = blob["lines"]
        source = "the cached case %s line set" % a.case
    key = truth.read_key(key_path)
    names = cfg.get("name_map", {})
    print("key %s: %d timed lines" % (os.path.basename(key_path), len(key)))
    print("checked against %s\n" % os.path.basename(str(source)))

    # The ceiling: the file the key was pinned to, scored the same way. Any
    # line it misses is the key's own wording or the key's own timestamp, and
    # no alignment of any other file can do better on it.
    ceiling = None
    if cfg.get("reference") and os.path.exists(cfg["reference"]):
        ceil_lines = timedtext.parse(cfg["reference"])
        ceiling = {}
        for lo, hi, label in _WINDOWS:
            rows = truth.score(ceil_lines, key, names, lo, hi)
            ceiling[label] = sum(1 for r in rows if r["hit"])

    strict = None
    for lo, hi, label in _WINDOWS:
        rows = truth.score(lines, key, names, lo, hi)
        hit = sum(1 for r in rows if r["hit"])
        extra = "" if ceiling is None else \
            "   (the file the key was pinned to: %d)" % ceiling[label]
        print("alignment, %s: %d of %d (%.0f%%)%s"
              % (label, hit, len(rows), 100.0 * hit / max(1, len(rows)), extra))
        if strict is None:
            strict = rows
        wide = rows
    print("\n  misses at the half-second tolerance:")
    print("  %-8s %-9s %-34s %s" % ("at", "speaker", "key line", "why"))
    for r in strict:
        if r["hit"]:
            continue
        print("  %-8s %-9s %-34s %s" % (_mmss(r["t"]), r["want"],
                                        _short(r["key"], 34), r["reason"]))
    if all(r["hit"] for r in strict):
        print("  none")
    print("\n  misses inside the stated second, which is what the key can express:")
    print("  %-8s %-9s %-34s %s" % ("at", "speaker", "key line", "why"))
    for r in wide:
        if r["hit"]:
            continue
        print("  %-8s %-9s %-34s %s" % (_mmss(r["t"]), r["want"],
                                        _short(r["key"], 34), r["reason"]))
    if all(r["hit"] for r in wide):
        print("  none")

    sp = wide
    got = [r for r in sp if r["got"]]
    right = [r for r in got if r["right"]]
    named = [r for r in got if r["how"] == "named"]
    carried = [r for r in got if r["how"] == "carried"]
    print("\nspeaker names the rip gives the key's %d lines" % len(sp))
    print("  a name at all          : %d (%.0f%%)  -- %d printed by the file, "
          "%d carried by the run rule"
          % (len(got), 100.0 * len(got) / max(1, len(sp)), len(named), len(carried)))
    print("  and it is the right one: %d (%.0f%% of all lines, %.0f%% of the named)"
          % (len(right), 100.0 * len(right) / max(1, len(sp)),
             100.0 * len(right) / max(1, len(got))))
    for how, group in (("printed by the file", named), ("carried by the run rule", carried)):
        n = sum(1 for r in group if r["right"])
        print("    %-24s %d of %d right (%.0f%%)"
              % (how, n, len(group), 100.0 * n / max(1, len(group))))
    print("\n  every line the rip gets wrong or leaves unnamed:")
    print("  %-8s %-9s %-9s %-9s %s" % ("at", "key says", "rip says", "how", "raw label"))
    for r in sp:
        if r["right"]:
            continue
        print("  %-8s %-9s %-9s %-9s %s" % (_mmss(r["t"]), r["want"],
                                            r["got"] or "-", r["how"], r["raw"] or "-"))
    if a.sweep:
        print("\n  the run rule's gap, swept over the same %d key lines:" % len(sp))
        print("    %-8s %8s %8s %8s" % ("gap", "named", "right", "of named"))
        for gap in (0.0, 2.0, 3.0, 5.0, 8.0, 12.0, 1e9):
            fresh = [dict(x, speaker=x["speaker"] if x["named"] else "",
                          carried=False) for x in lines]
            timedtext.apply_runs(fresh, gap)
            g2 = [r for r in truth.score(fresh, key, names, _WINDOWS[1][0],
                                         _WINDOWS[1][1]) if r["got"]]
            n = sum(1 for r in g2 if r["right"])
            print("    %-8s %8d %8d %7.0f%%"
                  % ("none" if gap > 1e8 else ("off" if not gap else "%.0fs" % gap),
                     len(g2), n, 100.0 * n / max(1, len(g2))))
    return {"strict": strict, "wide": wide}


def _settings(args):
    """The few flags of a recogniser run that change the answer."""
    want = ("model", "beam_size", "patience", "compute_type", "vad_method")
    parts = shlex.split(args or "")
    out = []
    for k in want:
        flag = "--" + k
        if flag in parts:
            i = parts.index(flag)
            if i + 1 < len(parts):
                out.append("%s %s" % (k.replace("_", " "), parts[i + 1]))
    return ", ".join(out) or "-"


def _transcript_numbers(reference, row):
    """One recogniser run scored against the found caption, or None.

    A run over a slice of the episode -- the minute used to prove a machine
    works before an hour of its card is spent -- gets no numbers rather than
    numbers that read as a catastrophic transcription, because everything it
    did not listen to counts against it.
    """
    path = row.get("file") or ""
    path = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not (reference and os.path.exists(reference) and os.path.exists(path)):
        return None
    ref = timedtext.parse(reference)
    hyp = timedtext.parse(path)
    if not ref or not hyp or hyp[-1]["end"] < 0.6 * ref[-1]["end"]:
        return None
    return _measure_on_time(ref, hyp)


def cmd_report(a):
    cfg = load_subject(a.subject)
    text = _load_json(cache(a.subject, "align_caseA.json")) or {}
    blind = _load_json(cache(a.subject, "align_blind.json")) or {}
    sk = _load_json(cache(a.subject, "skeleton.json")) or {}
    wref = _load_json(cache(a.subject, "align_whisperref.json")) or {}
    cb = _load_json(cache(a.subject, "aligned_caseBwhisper.json")) or {}
    out = []
    w = out.append
    w("# %s -- episode line set, alignment and speaker names\n" % a.subject)
    w("Written by `python -m tools.speakers report %s` on %s (machine local time).\n"
      % (a.subject, time.strftime("%Y-%m-%d %H:%M")))
    w("Video: `%s`\n" % os.path.basename(cfg.get("video", "")))
    w("Reference line set for the text alignment: `%s`\n"
      % os.path.basename(cfg.get("reference", "")))
    w("\n## Candidates and their fit, matched on the Japanese text\n")
    w("| file | found | lines | named by the file | anchors | offsets | median error after fitting | verdict |")
    w("|---|---|---|---|---|---|---|---|")
    for r in text.get("candidates", []):
        offs = "; ".join("%s..%s %+.3fs" % (_mmss(s["from"]), _mmss(s["to"]), s["offset"])
                         for s in r["segments"])
        w("| %s | %s | %d | %d | %d | %s | %.3f s | %s |"
          % (r["name"], r["where"], r["lines"], r["named"], r["quality"]["anchors"],
             offs, r["quality"]["median_error"] or 0,
             "accepted" if r["accepted"] else "REFUSED: " + "; ".join(r["reasons"])))
    if text.get("winner"):
        w("\nWinner: `%s`.\n" % text["winner"])
        runs = (text.get("output") or {}).get("runs") or {}
        if runs:
            w("Speaker names on the winner: %d of %d lines printed by the file, "
              "%d carried by the run rule at a %.0f s gap, %d left unnamed.\n"
              % (runs["direct"], runs["lines"], runs["carried"], runs["gap_s"],
                 runs["unnamed"]))
        w("Written to `%s` and `%s`.\n"
          % ((text.get("output") or {}).get("srt", ""),
             (text.get("output") or {}).get("ass", "")))
    if sk:
        w("\n## The timing skeleton from the video's own English track\n")
        w("Stream %s, %d events, %d dropped as a song or a sign style (%s), "
          "%d dropped as text placed on the picture, %d spoken cues left.\n"
          % (sk.get("stream"), sk.get("events", 0), sk.get("dropped_by_style", 0),
             ", ".join(sk.get("dropped_styles", [])), sk.get("dropped_as_placed", 0),
             len(sk.get("cues", []))))
    if blind.get("candidates"):
        w("\n## The same files fitted on cue onsets alone, no shared text\n")
        w("| file | anchors | offsets | median error after fitting | verdict |")
        w("|---|---|---|---|---|")
        for r in blind["candidates"]:
            offs = "; ".join("%s..%s %+.3fs" % (_mmss(s["from"]), _mmss(s["to"]), s["offset"])
                             for s in r["segments"])
            w("| %s | %d | %s | %.3f s | %s |"
              % (r["name"], r["quality"]["anchors"], offs,
                 r["quality"]["median_error"] or 0,
                 "accepted" if r["accepted"] else "REFUSED: " + "; ".join(r["reasons"])))
    runs = _transcripts(a.subject)
    if runs:
        caseA = (text.get("output") or {}).get("srt") or cfg.get("reference", "")
        caseA = caseA if os.path.isabs(caseA) else os.path.join(ROOT, caseA)
        w("\n## The speech recogniser, every run\n")
        w("Scored against `%s` with the lines paired on the clock, which is "
          "what `score --pair time` does. A run over a slice of the episode "
          "rather than the whole of it is listed with no error rate.\n"
          % os.path.basename(caseA))
        w("| tag | where it ran | settings | wall clock | segments | error rate, "
          "whole episode | error rate, shared stretches | stretches sung over |")
        w("|---|---|---|---|---|---|---|---|")
        for row in runs:
            m = _transcript_numbers(caseA, row)
            w("| %s | %s | %s | %.1f min | %d | %s | %s | %s |"
              % (row.get("tag") or "(the first run)",
                 row.get("ran_on") or "this machine", _settings(row.get("args", "")),
                 (row.get("seconds") or 0) / 60.0, row.get("segments", 0),
                 "%.4f" % m["cer_whole_string"] if m else "-",
                 "%.4f" % m["cer_shared"] if m else "-",
                 "%d (%d chars)" % (len(m["sung"]), m["sung_chars"]) if m else "-"))
        for row in runs:
            w("\n`%s`: `%s`\n" % (row.get("tag") or "(the first run)",
                                  row.get("args", "")))
            heard = row.get("heard") or row.get("came_from")
            if heard:
                w("Heard: `%s`. Written to `%s`, and beside the video as `%s`.\n"
                  % (heard, row.get("file", ""), row.get("beside", "")))
    if wref.get("candidates"):
        w("\n## The same candidates fitted to the recogniser's transcript "
          "instead of to the caption beside the video\n")
        w("This is the shape the real run has: no file beside the video is "
          "assumed, and what the candidates are anchored to is what the "
          "episode's own audio says.\n")
        w("| file | anchors | offsets | median error after fitting | verdict |")
        w("|---|---|---|---|---|")
        for r in wref["candidates"]:
            offs = "; ".join("%s..%s %+.3fs" % (_mmss(s["from"]), _mmss(s["to"]), s["offset"])
                             for s in r["segments"])
            w("| %s | %d | %s | %.3f s | %s |"
              % (r["name"], r["quality"]["anchors"], offs,
                 r["quality"]["median_error"] or 0,
                 "accepted" if r["accepted"] else "REFUSED: " + "; ".join(r["reasons"])))
        w("\nWinner against the transcript: `%s`.\n" % wref.get("winner"))
    if cb:
        w("\n## Case B end to end: the recogniser's words on the English "
          "track's timings\n")
        w("%d recognised segments, %d snapped to a cue of the English track, "
          "%d left on the recogniser's own times. No speaker names: the "
          "recogniser carries none and this case has no caption rip to take "
          "them from.\n" % (len(cb.get("lines", [])), cb.get("snapped", 0),
                            len(cb.get("lines", [])) - cb.get("snapped", 0)))
    p = os.path.join(cfg.get("out_dir") or ".", "%s_stage1.md" % a.subject)
    timedtext._write(p, "\n".join(out) + "\n")
    log("wrote %s" % os.path.relpath(p, ROOT))


def cmd_selftest(a):
    from tools.speakers import selftest
    return selftest.run()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m tools.speakers",
                                 description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("subject"); p.add_argument("--video", default="")
    p.add_argument("--mirror", default=""); p.add_argument("--reference", default="")
    p.add_argument("--episode", type=int, default=None)
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("candidates")
    p.add_argument("subject"); p.add_argument("--redo", action="store_true")
    p.set_defaults(fn=cmd_candidates)

    p = sub.add_parser("skeleton")
    p.add_argument("subject"); p.add_argument("--stream", type=int, default=None)
    p.add_argument("--redo", action="store_true")
    p.set_defaults(fn=cmd_skeleton)

    p = sub.add_parser("songs")
    p.add_argument("subject")
    p.add_argument("--cut", action="store_true",
                   help="write the audio with the songs muted")
    p.add_argument("--full", action="store_true",
                   help="write the same audio untouched, as the control")
    p.add_argument("--stem", default="",
                   help="name the written audio something other than the video's stem")
    p.add_argument("--redo", action="store_true")
    p.set_defaults(fn=cmd_songs)

    p = sub.add_parser("transcribe")
    p.add_argument("subject"); p.add_argument("--exe", default="")
    p.add_argument("--args", default=""); p.add_argument("--redo", action="store_true")
    p.add_argument("--audio", default="",
                   help="listen to this file instead of the video")
    p.add_argument("--tag", default="",
                   help="what to call this run; without one the first run's "
                        "names are kept")
    p.add_argument("--import", dest="import_file", default="",
                   help="register a transcript made elsewhere instead of running "
                        "the recogniser")
    p.add_argument("--note", default="",
                   help="what the imported transcript was made with")
    p.add_argument("--seconds", type=float, default=0.0,
                   help="wall clock of the run that made an imported transcript")
    p.add_argument("--ran-on", default="",
                   help="which machine made an imported transcript")
    p.set_defaults(fn=cmd_transcribe)

    p = sub.add_parser("remote")
    p.add_argument("subject"); p.add_argument("--audio", required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--host", default=""); p.add_argument("--exe", default="")
    p.add_argument("--dir", default=""); p.add_argument("--args", default="")
    p.add_argument("--redo", action="store_true")
    p.set_defaults(fn=cmd_remote)

    p = sub.add_parser("spotcheck")
    p.add_argument("subject"); p.add_argument("--tag", default="")
    p.add_argument("--against", default="",
                   help="a found caption of the same video, to say whether the "
                        "model's flags land on the lines that are really wrong")
    p.add_argument("--batch", type=int, default=40)
    p.add_argument("--slug", default="deepseek/deepseek-v4-flash-0731")
    p.add_argument("--order", default="together",
                   help="the hosts to try, best first, comma separated")
    p.add_argument("--dry-run", action="store_true",
                   help="count the calls and price them, ask nothing")
    p.set_defaults(fn=cmd_spotcheck)

    p = sub.add_parser("align")
    p.add_argument("subject"); p.add_argument("--reference", default="")
    p.add_argument("--tol", type=float, default=0.0,
                   help="seconds; 0 measures it from the pair of files")
    p.add_argument("--confirm", type=int, default=align.CONFIRM)
    p.add_argument("--redo", action="store_true")
    p.add_argument("--write-all", action="store_true",
                   help="write every accepted candidate, not only the winner")
    p.add_argument("--label", default="caseA",
                   help="what to call this run in the cache and in the filenames")
    p.set_defaults(fn=cmd_align)

    p = sub.add_parser("blind")
    p.add_argument("subject"); p.add_argument("--candidate", default="")
    p.add_argument("--tol", type=float, default=0.0,
                   help="seconds; 0 measures it from the pair of files")
    p.add_argument("--confirm", type=int, default=align.CONFIRM)
    p.add_argument("--onset-tol", type=float, default=0.5)
    p.add_argument("--max-offset", type=float, default=420.0)
    p.add_argument("--switch-penalty", type=float, default=6.0)
    p.set_defaults(fn=cmd_blind)

    p = sub.add_parser("agree")
    p.add_argument("subject"); p.add_argument("--candidate", required=True)
    p.add_argument("--label", default="caseA")
    p.set_defaults(fn=cmd_agree)

    p = sub.add_parser("caseb")
    p.add_argument("subject"); p.add_argument("--segments", default="")
    p.add_argument("--label", default="",
                   help="which recogniser run this is; without one the first "
                        "run's names are kept")
    p.add_argument("--max-shift", type=float, default=1.0)
    p.set_defaults(fn=cmd_caseb)

    p = sub.add_parser("snap")
    p.add_argument("--segments", required=True); p.add_argument("--reference", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--max-shift", type=float, default=1.0)
    p.set_defaults(fn=cmd_snap)

    p = sub.add_parser("score")
    p.add_argument("--reference", required=True); p.add_argument("--hypothesis", required=True)
    p.add_argument("--pair-sim", type=float, default=0.40)
    p.add_argument("--pair", choices=("text", "time"), default="text",
                   help="match lines on their wording, or on the clock when "
                        "both sets are timed to the same video")
    p.add_argument("--worst", type=int, default=0)
    p.set_defaults(fn=cmd_score)

    p = sub.add_parser("check")
    p.add_argument("subject"); p.add_argument("--aligned", default="")
    p.add_argument("--key", default=""); p.add_argument("--case", default="caseA")
    p.add_argument("--sweep", action="store_true")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("report")
    p.add_argument("subject")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("selftest")
    p.set_defaults(fn=cmd_selftest)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
