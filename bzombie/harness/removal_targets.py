"""The removal-test targets of the S arm (tk-lmv): what is switched off, how, and what must be gone when it is.

Pure data, no imports of the arm: the batch planner, the summary and the proof all read it. The arm side is
bzombie/arms/s/control.py (apply_removal, BOOT_ONLY).

target   inject target string (`section.<name>` = config section <name>, enabled false; `bz_s10.<key>` = false)
roles    llm roles that must make no call in the branch (the base makes them)
inputs   prompt sections (trace input names) that must be absent from her reply prompt in the branch
boot     the App builds the part only when enabled: the arm rebuilds it over the restored save
why      the numbers that put it on the list (3 base runs, 3 days each: docs/reports/2026-10-24_removal_notebook.md)
"""
from __future__ import annotations

NOOP = "noop"

TARGETS = [
    {"name": "foresight", "target": "section.foresight", "roles": ["foresee"], "inputs": [], "boot": False,
     "why": "190 foresee calls, 662k prompt tokens: the most expensive part"},
    {"name": "commitments", "target": "section.commitments", "roles": ["commit_him"], "inputs": [], "boot": False,
     "why": "186 commit_him calls, 225k tokens; the ledger line (195 chars) is the longest mind section"},
    {"name": "recall", "target": "section.recall", "roles": ["recall"], "inputs": ["recall"], "boot": False,
     "why": "101 recall calls, 374k tokens, plus its own prompt line"},
    {"name": "attachment", "target": "section.attachment", "roles": [], "inputs": [], "boot": False,
     "why": "the gate lines (123 chars a prompt, the second longest block)"},
    {"name": "primitives", "target": "section.primitives", "roles": [], "inputs": ["primitives"], "boot": True,
     "why": "103 chars a prompt; built at boot only, so the arm rebuilds it"},
    {"name": "goals", "target": "section.goals", "roles": [], "inputs": ["goals"], "boot": False,
     "why": "69 chars a prompt, feeds the day plan"},
    {"name": "coherence", "target": "section.coherence", "roles": ["coherence"], "inputs": [], "boot": False,
     "why": "9 calls, 44k tokens, the continuity check on her own claims"},
    {"name": "morning", "target": "section.morning", "roles": ["morning"], "inputs": ["morning"], "boot": False,
     "why": "96 chars a prompt, 9 calls (thinking on)"},
    {"name": "budget", "target": "bz_s10.budget", "roles": [], "inputs": [], "boot": False,
     "why": "surface check from the brief: the bubble budget (no calls, changes the length line)"},
    {"name": "repeat_check", "target": "bz_s10.repeat_check", "roles": [], "inputs": [], "boot": False,
     "why": "surface check from the brief: the repetition check (a redraft call only when it fires)"},
]

# Considered and dropped, with the reason (named again in the notebook).
DROPPED = {
    "diary": "proof failed (H:/SCAIL/temp/proof_s5_day1.json): with diary.enabled false the `yesterday` line is still in her "
             "reply prompt, so the flag does not remove it (the line is read from the saved state); a cut needs a code change",
    "scene_director": "192 calls, but no enabled gate in the code (sim/director.py runs it every pass); a cut needs a code change",
    "state": "192 calls, the gauge scoring (sim/appraisal_gauge.py), no gate; the gauges every other part reads",
    "stances": "no calls and no prompt section of its own in the three runs",
    "wonder": "zero calls in the three base runs: nothing to remove, already a cut candidate on the numbers",
    "spiral": "zero calls in the three base runs",
    "reflect": "zero calls in the three base runs",
    "withholding": "zero calls in the three base runs",
    "expect": "zero expect_him calls in the three base runs",
    "beliefs": "zero settle_beliefs calls in the three base runs",
}

BY_NAME = {t["name"]: t for t in TARGETS}
