"""Fixed script for simulated him (tk-mz5).

Run config "him_via": "script" plus "him_script": "<run_id>" (a reference run) or a path to a JSONL file. The driver
then sends his lines from that source at their virtual_ts, verbatim, and makes no sim-him call. Same lines for two
arms, or for a run and its removal-test branch, so a difference in her lines is her inside, not his improvising.

Source forms:
- a run id: runs/<run_id>/transcript.jsonl, lines with who == "him". The reference run's config.json is read for the
  character; a different character is refused at load.
- a path to a JSONL file (any transcript.jsonl, a branch's too): lines with who == "him", or lines with no "who"
  field. Each needs virtual_ts and text. No character check is possible; the caller owns that.
"""
from __future__ import annotations

from pathlib import Path

from ..common import iso, parse_ts, read_json, read_jsonl, run_dir


class ScriptError(ValueError):
    pass


def resolve(source: str) -> tuple[Path, str | None]:
    """(transcript path, reference run id or None for a plain file)."""
    s = str(source)
    p = Path(s)
    if p.is_file():
        return p, None
    rd = run_dir(s)
    if (rd / "transcript.jsonl").is_file():
        return rd / "transcript.jsonl", s
    raise ScriptError(f"him_script {s!r}: not a file and no run with a transcript")


def load(source: str, character: str | None = None) -> dict:
    """{"lines": [{"virtual_ts", "text"}] sorted by ts (stable), "ref_run", "last_ts", "source"}.

    Refuses a reference run whose character differs from `character`, and an empty script."""
    path, ref = resolve(source)
    if ref and character:
        rc = (read_json(run_dir(ref) / "config.json") or {}).get("character")
        if rc and rc != character:
            raise ScriptError(f"him_script {ref}: character {rc!r} differs from this run's {character!r}")
    lines = []
    for r in read_jsonl(path):
        if r.get("who", "him") != "him" or not r.get("text") or not r.get("virtual_ts"):
            continue
        lines.append({"virtual_ts": iso(parse_ts(r["virtual_ts"])), "text": r["text"]})
    lines.sort(key=lambda r: r["virtual_ts"])
    if not lines:
        raise ScriptError(f"him_script {source}: no lines of his")
    return {"lines": lines, "ref_run": ref, "last_ts": lines[-1]["virtual_ts"], "source": str(source)}


def check_config(cfg: dict) -> None:
    """Called from load_config: him_via script needs a loadable him_script of the same character."""
    if cfg.get("him_via") != "script":
        return
    if not cfg.get("him_script"):
        raise ScriptError("him_via script needs him_script (a run id or a JSONL path)")
    load(cfg["him_script"], cfg.get("character"))
