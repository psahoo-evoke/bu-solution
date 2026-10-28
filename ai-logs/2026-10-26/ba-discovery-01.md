# ba-discovery-01 · Problem framing, scoring map and discovery questions

| Field | Value |
| --- | --- |
| Date | 2026-10-26 |
| Agent (role) | ba-discovery |
| Tool / model | Claude (Cowork) |
| Human owner | puspalata sahoo (Product lead) |
| Trigger | "plan this hackathon problem from discovery to demo" + kickoff slides, problem statement (Boston University.docx), course-match workbook |

## Prompt (summary)
Read the BU problem statement, the NU/NYU/BU course-match workbook and the kickoff slides (must-have checklist, 100-point scoring, FDE lens, deliverables). Produce a discovery-to-demo plan and the sponsor question list.

## Inputs used
- Boston University.docx (Problem 1: transfer credit evaluation)
- BU_Transfer_Program_Course_Match.xlsx (41 BU courses, 38 NU, 38 NYU, match levels)
- 5 kickoff slide photos

## Output
- Living doc "EvoHack 2026 — Transfer Credit Evaluation: Discovery-to-Demo Plan" (sections 1–3, 5, 7–9)
- 15 sponsor questions in 5 groups (volume/time, evaluators, students, rules/systems, success)
- Key framing: AI-First Delivery = 30 pts judged from the deck, so agent logging starts day 1
- Measured workbook facts: NU 21 likely / 11 partial / 6 none / 3 BU-only; NYU 31 / 6 / 1 / 3

## Human review
- Chose stack: Azure, Angular, FastAPI; ~1 week, 3–5 people
- Team submitted 33 questions to the sponsor (extended from the 15 proposed)

## Verification
- Workbook counts computed with pandas from the source file

## Commit
pre-repo, imported in the initial commit
