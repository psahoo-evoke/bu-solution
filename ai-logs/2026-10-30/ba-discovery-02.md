# ba-discovery-02 · Discovery document with requirements and traceability

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | ba-discovery |
| Tool / model | Solutionauts AI (Claude Code) |
| Human owner | Team lead |
| Trigger | Submission checklist item 2 ("Discovery doc (MD) covering the problem, users, requirements and scope") and scorecard criteria 1.1 and 1.2 |

## Prompt (summary or verbatim)
"discovery doc do this"

## Inputs used
- Discovery log (Q-001–Q-050, Gap review sheet), `docs/discovery/sponsor-answers.md`, `docs/stories.md`, `data/synthetic/seed/rules.csv`
- `docs/roadmap.md`, `docs/quality/eval-report.md`, `docs/quality/scalability-report.md`, ADRs
- Test names in `backend/tests/` and `frontend/e2e/demo.spec.ts`

## Output
- `docs/discovery/discovery.md`: problem with baseline numbers; users and needs; 17 functional requirements, each mapped to source question, rule IDs, feature and tests; 13 non-functional requirements with target, status and evidence; assumptions; constraints; out of scope; 22 edge cases with handling and tests; known differences from discovery; open questions
- `backend/tests/test_rules.py`: `test_R19_pending_courses_are_flagged_after_the_one_year_deadline`. While mapping requirements to tests, R19 (one-year deadline) turned out to have no test.
- `README.md` and `docs/discovery/sponsor-answers.md` link the document

## Human review
- Team lead asked for the document. Statuses marked [T] (team assumption) and "not measured" are stated as such, not as met.

## Verification
- Every test name cited in the document exists in `backend/tests/`; every e2e title exists in `demo.spec.ts`; every relative link resolves
- `pytest -q tests/test_rules.py`: 78 passed (including the new R19 test)

## Commit
See `git log -- docs/discovery/discovery.md`
