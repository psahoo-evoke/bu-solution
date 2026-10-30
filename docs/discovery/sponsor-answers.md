# Sponsor answers — what we learned (2026-10-28)

Source: `Hackathon_Discovery_Log_solutionauts.xlsx` (33 questions). The sponsor labels most numbers **Assumption**; we treat them as sponsor estimates, not BU data.
Note: in the log, the answers to Q-018–Q-025 sit two rows above their questions and Q-027–Q-029 three rows above; we read them by content. The row mapping, the other gaps in the log, and the requirement areas it did not cover (non-functional, retention, identity, out of scope) are on the log's **Gap review** sheet, with follow-up questions Q-037–Q-050 (confirmation requested in Q-048).

## Numbers (sponsor estimates)
| Fact | Value |
| --- | --- |
| Courses evaluated per year | ~8,000 (800 students x 10) |
| "Maybe" share | 35% (~2,800 courses) |
| Days to posting | ~7 existing match, ~60 maybe, ~45 average |
| Evaluator time per syllabus | 12 minutes |
| Evaluators | 12 (2 per dept x 6), ~120 reviews each per term |
| Maybe courses never getting a syllabus | ~10% |

## Success test (headline outcome)
Evaluator time per course 12 -> under 2 minutes, while the top suggestion matches the evaluator decision >= 80% and wrongly suggested credit <= 2%.

## Integration and data
- No access to Transferology or BU's equivalency DB -> our own equivalency table with reason code + reusable flag.
- No MyBU integration -> MyBU-style CSV export. Synthetic data only; no real names or IDs in prompts or logs. FERPA applies to real transcripts.

## Decision rules
- >= 80% outcome overlap -> equivalent; 50–79% -> evaluator decides; < 50% -> elective if eligible; ineligible -> no credit.
- Batch approval allowed for > 90%, logged per course.
- Course descriptions are not evidence; only for preliminary AI suggestions.
- Codes: equivalent = BU course; elective = code ending TR; no credit = TFRGEN NOCRDT, 0 units, TX. Every evaluated course shows grade T (TX for no credit). Units = student's units (quarter x 2/3, 2 decimals).
- Full list: `data/synthetic/seed/rules.csv` (R01–R24).

## Process
- Missing syllabus -> TS; incomplete -> TM ("additional materials"). Reminders day 7, 21, 45 by email + portal with upload link.
- Results: department -> Registrar -> posting. Student sees TP until posting; advisor sees "Approved – awaiting posting".
