# prompts, 真優 (mayu)

Status 2026-10-23: refreshed from the 13 B3 mechanisms; check_prompt_numbers.py reports 0 misses. Read the open limits.

## Feed order

- bible.md then style.md, as the system prompt, in that order.
- sheet.json is never sent. It holds the type; no model call reads it.

## Files

- bible.md: Japanese character sheet, relationships, record facts. Mechanism ids removed (quotes kept).
- style.md: speech rules with receipts. The hands section lists her 10 firm, 2 thin mechanisms; the weak stammer is in the house-style list.
- ../sheet.json: roster fields plus `type`, `why`, `axes`, `contradictions`.

## Open limits

- Number check: 0 misses (bible.md and style.md). Rerun after any bible.json rebuild.
- Gate 6/6 on the full corpus: rules_beat_bigram passes on 13 own speech_guide markers, 0.792 vs 0.723. Leak-free (markers and rates fitted on the build block only) it fails, 0.673 vs 0.723; the other five pass.
- mechanisms_distinctive passes (11 of 13) but the mechanisms were found on all her lines, holdout included. Four firm mechanisms have 0 or 1 holdout hit (opens_with_datte, names_momoka_with_chan, offers_to_do_for_him, whimpers_u_u).
- Tiers: one count rule (firm n>=40, thin 10-39, weak under 10, inferred capped at thin, a mechanism at or under the control share is weak, firm needs 2x control). 10 firm, 2 thin, 1 weak mechanisms. Six speech rules changed tier (tier_was kept).
- The record does not say: how to read 真優, which club she belongs to, the みゃー先輩 / ナタリー names, her family (see B5_NOTES.md).
- The type is thin on T/F (0.4) and J/P (0.35).
