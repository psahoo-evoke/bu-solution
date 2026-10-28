# ba-discovery-02 · Apply sponsor answers to the plan

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | ba-discovery |
| Tool / model | Claude (Cowork) |
| Human owner | puspalata sahoo (Product lead) |
| Trigger | "received the answers from sponsor. check it and modify the plan if needed" |

## Prompt (summary)
Read the 33 answered questions in the discovery log and update every affected section of the plan.

## Inputs used
- Hackathon Discovery Log _solutionauts 1.xlsx

## Output
- New plan section "What changed after the sponsor's answers"
- Headline outcome changed to: evaluator time 12 -> under 2 min/course; top-1 agreement >= 80%; wrongly suggested credit <= 2%
- Baseline table: ~8,000 courses/yr, 35% (~2,800) "maybe", 12 min/syllabus, 7 vs 60 days, 12 evaluators x ~120 reviews/term, ~10% never get a syllabus
- ROI: 2,800 x 12 min = 560 h/yr; target 93 h; ~467 h returned
- Rules expanded from 5 to ~24 (see `data/synthetic/seed/rules.csv`); BU status codes TP/TS/TM/T/TR/TX; quarter rounding 2.67 (sponsor) vs 2.66 (brief)
- Flagged to sponsor: answers to Q17–24 and Q29 appear shifted one or two rows

## Human review
- Accepted. Headline outcome confirmed (comment thread on the plan doc)

## Verification
- Cross-check: 12 evaluators x 120 x 2 terms = 2,880 reviews vs 2,800 maybe courses (consistent)

## Commit
pre-repo, imported in the initial commit
