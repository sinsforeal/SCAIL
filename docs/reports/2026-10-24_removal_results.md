# Removal tests on S Momoka (tk-lmv stage 5): mechanical result

2026-10-24 10:25, scail orchestrator. 72 branches, 0 failed: 3 base runs (gr2_b_s3, gr2_b_s4, gr_b_s5, own-day arm) x 2 snapshots (day1_end, day2_end) x (10 removal targets + 2 noop replays). Each branch replays the same 6 of his messages plus 30 min. Code bz/s_ground (removal harness e209ce1). Full table: H:\SCAIL\temp\removal_s5.md and .json.

## Result

No part was shown to change her beyond replay drift. The mechanical test cannot separate any of the ten from noise.

- Drift is large: two noop replays of the same snapshot and messages differ by 0.47 to 0.58 in text distance (0 same, 1 nothing shared). Half her text changes on a rerun with nothing changed.
- A cell counts as changed when the branch is further from both noops than they are from each other. With three exchangeable replays that happens by chance 1 time in 3, so pure noise gives about 2 of 6 cells per target.
- Observed, cells changed of 6: foresight 4, recall 4, goals 4, commitments 3, attachment 3, primitives 3, coherence 3, budget 3, repeat_check 3, morning 1. Mean 3.1. Getting 4 or more of 6 by chance is about 10% per target, so three of ten at 4 is what noise produces.
- The removals were real: the removed role made 0 calls in every branch where the noops made it (foresee 6 to 9 per window, commit_him 6 to 9, recall up to 8).

## Read

- Over 6 messages, switching off foresight (190 calls and 662k tokens per 3-day run, the most expensive part), commitments (186 calls) or recall (101 calls, 374k tokens) does not move her text more than a rerun does. Either the effect is smaller than the drift, or it needs longer than 6 messages to show.
- This is evidence of a weak link between her inner machinery and her replies, the same thing the User raised at 06:36 ("how can we make the internal state meaningful"). It is not yet a reason to cut: short windows cannot show slow parts (goals, morning, attachment).
- The judge pass (removal_summary --judge) was not run: at this drift a quality judge would mostly read noise, and it costs about 1,000 to 2,000 claude calls. The directional test (tk-6si injection, steer judge) is the better instrument and runs next.

## Memory, measured over the batch

- Gateway: peak 3,834 MB private, 1,451 MB working set (the shared embedding model). Fixed cost of the bench.
- Each S arm: peak 160 MB private, 145 MB working set, after a day or two of state from the snapshots.
- Batch and branch drivers: about 35 MB private each.
