# Koikano cast gate rerun, own markers, 2026-10-23

Branch cast/gate_rerun, code commit 349a6fe. Agent: Sonnet 5.5. Raw output in tmp/wt_gate_rerun/var/gate_rerun (gitignored): full/<slug>, lf/<slug> (gate_checks.json, gate.json), cross_full.json, cross_lf.json, logs beside them.

## Result

- Full corpus: 百花 5/6, 真優 6/6, 千奈 5/6, アリス 5/6, 真里亜 5/6. 真優 passes all six.
- Leak-free: 5/6 for all five. Every subject still fails rules_beat_bigram.
- 百花 regression: identical to the earlier run (full 0.782 v 0.819, leak-free 0.544 v 0.819, mechanisms 10 of 15, 5/6 both). She has no marker file, so her default 13 markers ran untouched.
- Commands: `run_leak_free.py --full --out <d>/full`, then `run_leak_free.py --out <d>/lf --full-dir <d>/full`, then `cross_control.py --out ...` and the same with `--leak-free`. One subject at a time. No gate errored. `python -m unittest tests.test_koikano_markers -v`: 6 tests OK, render_doc KeyError('name') is gone (render_doc now raises a clear TypeError on a bare bible.json; use render_doc_from_files).
- Two things moved the numbers, not one. Own markers moved the rule detector and rules_beat_bigram. The merged B3 specs (tools/koikano/b3/<slug>.py, absent in the earlier gate_split run) moved mechanisms_distinctive from fail to pass for the four. The old numbers in the brief were on 百花's markers and default specs.

## Gate checks, full corpus (old on 百花's markers, new on own markers)

| check | 百花 | 真優 | 千奈 | アリス | 真里亜 |
|---|---|---|---|---|---|
| checks passed | 5/6 v 5/6 | 6/6 v 6/6 | 5/6 v 5/6 | 5/6 v 5/6 | 5/6 v 5/6 |
| mechanisms_distinctive | 10/15 v 10/15 | 4/14 FAIL v 11/13 pass | 4/14 FAIL v 9/10 pass | 3/14 FAIL v 10/17 pass | 1/14 FAIL v 13/14 pass |
| rule_detector balanced acc | 0.782 v 0.782 | 0.674 v 0.792 | 0.738 v 0.817 | 0.550 v 0.717 | 0.798 v 0.896 |
| rules_beat_bigram (own v bigram) | 0.782 v 0.819 FAIL, same | pass v 0.792 v 0.723 pass | 0.817 v 0.837 FAIL (old as brief) | 0.717 v 0.760 FAIL (old as brief) | 0.896 v 0.897 FAIL (old as brief) |

Notes on the old column. The brief's old full-corpus counts (真優 6/6, others 5/6) were from a run with the same checks passing on count; the gate_split notebook's 4/6 figures were before the b3 specs. The old mechanisms cell here is the gate_split value (default 百花 specs), the new one is on the merged b3 specs. The brief's old rules_beat_bigram values for 千奈, アリス, 真里亜 equal the new ones to three places, so own markers did not move the full-corpus comparison there. 真優 full-corpus old detector value is the gate_split 0.674; the new 0.792 now beats the bigram 0.723.

Marker counts applied: 真優 13, 千奈 10, アリス 14, 真里亜 8, 百花 none (default 13).

## Gate checks, leak-free (build block only, holdout scored)

| check | 百花 | 真優 | 千奈 | アリス | 真里亜 |
|---|---|---|---|---|---|
| checks passed | 5/6 v 5/6 | 4/6 v 5/6 | 4/6 v 5/6 | 4/6 v 5/6 | 4/6 v 5/6 |
| mechanisms_distinctive | 10/15 v 10/15 | 4/14 v 11/13 | 4/14 v 9/10 | 3/14 v 10/17 | 1/14 v 13/14 |
| rule_detector balanced acc | 0.544 v 0.544 | 0.674 v 0.673 | 0.735 v 0.760 | 0.516 v 0.579 | 0.798 v 0.896 |
| rules_beat_bigram | 0.544 v 0.819 FAIL, same | 0.673 v 0.723 FAIL (old 0.673 v 0.723) | 0.760 v 0.837 FAIL | 0.579 v 0.760 FAIL | 0.896 v 0.897 FAIL |

Leak-free detector gap to full corpus (new): 百花 0.782 to 0.544, 真優 0.792 to 0.673, 千奈 0.817 to 0.760, アリス 0.717 to 0.579, 真里亜 0.896 to 0.896.

## Cross-subject control (old v new, own cell must beat every other in the row by the margin)

Subjects passing:

| detector | full old | full new | leak-free old | leak-free new |
|---|---|---|---|---|
| rules | 4 of 5 | 3 of 5 (百花, アリス, 真里亜) | 2 of 5 | 2 of 5 (アリス, 真里亜) |
| mechanisms | 1 of 5 | 5 of 5 | 0 of 5 | 4 of 5 (all but 百花) |

Rules rows, full corpus, columns 百花 真優 千奈 アリス 真里亜:
- 百花: 0.581* 0.323 0.122 0.204 0.038 PASS
- 真優: 0.928 0.980* 0.257 0.988 0.160 FAIL (fires on アリス's lines at 0.988)
- 千奈: 0.073 0.087 0.739* 0.081 0.742 FAIL (真里亜 0.742, no gap)
- アリス: 0.193 0.362 0.118 0.655* 0.189 PASS
- 真里亜: 0.014 0.028 0.474 0.072 0.827* PASS

Rules rows, leak-free:
- 百花: 0.778* 0.820 0.199 0.720 0.221 FAIL
- 真優: 0.877 0.853* 0.242 0.951 0.154 FAIL
- 千奈: 0.018 0.021 0.626* 0.068 0.739 FAIL
- アリス: 0.393 0.504 0.134 0.624* 0.204 PASS
- 真里亜: 0.014 0.028 0.498 0.072 0.891* PASS

Mechanism own cells, full / leak-free: 百花 0.234 / 0.164, 真優 0.250 / 0.185, 千奈 0.542 / 0.568, アリス 0.526 / 0.343, 真里亜 0.789 / 0.828. Own-beats-all-others mechanism counts, full: 百花 9 of 15, 真優 11 of 13, 千奈 10 of 10, アリス 11 of 17, 真里亜 13 of 14. Leak-free: 8, 9, 9, 8, 12. The four rows are no longer one detector; the b3 specs made them separate.

## What moved and why

- Mechanisms 4/14 etc. to 9-13 passes: the b3 specs are now on this branch. Before, the four ran 百花's 14 default specs, which are genre-level on them. Not an effect of the marker files.
- Rule detector up by 0.04 to 0.17 full corpus: each subject's own speech_guide markers fire on her own text. 百花's markers never fired on theirs (真優 0.674 to 0.792, アリス 0.550 to 0.717).
- 真優 6/6 full corpus: own markers lift her detector over the bigram (0.792 v 0.723). Fails leak-free (0.673 v 0.723).
- Leak-free 4/6 to 5/6 for four: purely the mechanisms check. rules_beat_bigram stays failed for everyone.
- Cross rules, full corpus: passes fell 4 to 3. 真優 flipped to fail: her own markers fire on アリス's lines (0.988) as hard as on hers (0.980), so they are not specific to her. 千奈 was already failing and did not change.

## Passing and open failures

Full corpus: 真優 passes all six. The other four pass five and fail rules_beat_bigram.

Open failures, with the reason found:
- rules_beat_bigram, all five in leak-free, four in full corpus. A 8-14 regex marker set fitted per class cannot beat a bigram trained on the whole build block; the gaps are 0.001 (真里亜), 0.020 to 0.040 (千奈, アリス) full corpus, and 0.05 to 0.28 leak-free. 真里亜 0.896 v 0.897 is within noise.
- 真優 leak-free 0.792 to 0.673: markers were chosen with her whole text in view, so the full-corpus score is in-sample. Her holdout also drops わたし to 0.094 vs 0.172 build.
- 百花 leak-free 0.544: her holdout is 63 percent H lines while the build block is mostly non-H. Not a marker problem; regression is identical on purpose.
- アリス leak-free 0.579 and cross rules 0.624 own v 0.504 on 真優: her markers are shared with 真優's speech.
- 真優 and 千奈 cross rules: 真優 markers fire on アリス (0.988 full) and 千奈 markers fire on 真里亜 (0.742 v own 0.739). These are first-person and register markers the two pairs share. A marker that separates the pair is needed, not a different threshold.
- 真里亜 leak-free detector 0.896 identical to full corpus to three places. Her cross own cell does differ (0.827 to 0.891), so the build-only path ran; I did not trace why the gate balanced accuracy matches. Check before trusting that number.
- 百花 cross mechanisms leak-free: own cell 0.164 under 真優's 0.169 (holdout is H heavy).
