# synthetic-data-02 · Rebuild on Northeastern + NYU

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | synthetic-data |
| Tool / model | Solutionauts AI (Cowork) |
| Human owner | Data / QA lead |
| Trigger | "we should choose NYU or NU college for syllabus and transcript. hackathon given those college data only" |

## Prompt (summary)
Use the 76 real NU/NYU catalog courses from the workbook as the external catalog and transcript source; keep ground truth aligned with the workbook's Course Match sheet.

## Output (`data/synthetic/`, generator in `scripts/synthetic/`)
- 194 external courses: 76 real NU/NYU catalog courses (code/title/credits real; content synthetic) + 115 synthetic NU/NYU-style courses (flagged in Source) + 3 helper-school courses
- Two fictional helper schools kept on purpose: a quarter-system college (NU/NYU use semesters) and a non-accredited school
- 100 past decisions (70 train / 30 holdout), 56 transcript lines with expected outcomes, 20 test cases (T01–T20)
- Demo: Maya from NYU — 3 existing matches, PSYCH-UA 10 (~75% vs CAS PS 211), PSYCH-UA 25 (~62% vs CAS PS 231), 1 quarter course (2.67)

## Human review
- Accepted. Agent decision kept: real-institution documents are labelled as generated test files

## Verification
- Recalc 0 errors; PDFs rendered and inspected; injection text present in ECON-UA 266 syllabus

## Commit
pre-repo, imported in the initial commit
