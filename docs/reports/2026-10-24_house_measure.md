# House measure (tk-dlp): does the second mind show up in her chat

2026-10-24 01:50, scail orchestrator. Follows docs/reports/2026-10-24_grounding_results.md ("Momoka + 真里亜"), which could not tell the two-mind runs from their own-day twins because the judge read only her chat with him.

## Result

With the judge shown the peer lines, the two-mind run wins both house criteria on all three seeds, both passes agreeing. The result is partly built in, so read the caveat before using it.

- house_presence, two-mind v twin: s3 3 v 1, s4 5 v 1, s5 4 v 1. Mean 4.00 v 1.00.
- house_grounded, two-mind v twin: s3 3 v 1, s4 4 v 1, s5 4 v 2. Mean 3.67 v 1.33.
- Every pass of every match, 12 of 12, picked the two-mind side. No uncalibrated criterion.
- Twin runs invent household events with 真里亜 in all three seeds: she brings lunch, they eat miso soup and onigiri, she makes a gyoza-like dish. No peer line or his line backs any of it. The two-mind runs' house claims follow their peer lines (okayu and honey hot milk, ゆるきゃん together, the 真優ちゃん costume talk). Small overreach in the two-mind runs: lunch together that no peer line shows (seed 3 days 1 and 3, seed 5 day 2).

## What it does and does not say

- house_presence on the twin is 1 by construction: it has no peer lines, so the house is empty. That score is a definition, not a finding. Only the two-mind side's 3, 5 and 4 carry information (how much of the shared day reaches him).
- house_grounded is a real contrast: the twin's 真里亜 talk is invented (the bible names her, nothing simulates her), the two-mind talk has a source. This is the same kind of fault the code checker flags as an ungrounded anchor.
- He never sees the peer lines. In his chat the twin's invented house is as consistent as the two-mind one, which fits the earlier result that the grounding test could not separate them. The gain is that the house talk is true to something and carries detail (what she brought, what they watched), not that his chat reads differently.
- The two-mind run costs 1.13x calls (grounding report) and 75 peer lines per run.

Decision: the two-mind world is a measurable improvement in grounded house talk and nothing else we can measure. It does not change the live config choice (Momoka is down). The go for the rest of the cast stays with the User's rule: this is the Maria result, and the other heroines' peer branches (tk-149) are not started. If he wants the community, tk-149 is next; if not, the cheap own-day arm stays.

## How it ran

- Branch bz/dlp (agent, Sonnet, notebook docs/reports/2026-10-24_dlp_notebook.md on the branch), merged into bz/s_ground. New slice "H" merges peer lines by time; the nine older slices are byte-identical with and without peers. Peer lines load through load_peer_events (bzombie/judge/runner.py).
- Calibration: house_presence 2 of 2 planted caught, control passed. house_grounded first run failed its control: the control's added line ended in 「いそがしそう」, an observation stated as fact, so the judge marking it down was correct. The control was rewritten as a fully hedged guess and passed on the rerun (house1, house2 in H:\SCAIL\bzombie\var\judge\calibration). The edit was to the control text only; prompts unchanged, hash ed875927e1a1.
- Matches g2_s3_house, g2_s4_house, g2_s5_house (A mm_sN_momoka_maria, B gr2_b_s3 / gr2_b_s4 / gr_b_s5 _momoka; in seed 5 the label map is swapped, the twin was A). Seeds 3, 4, 5. Results in H:\SCAIL\bzombie\var\judge\g2_sN_house\results.json. Reader script H:\SCAIL\temp\mm\show_house.py.
- Limits: three seeds, ja only, one judge model, a control that was edited once after failing.
