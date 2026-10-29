# developer-01 · One-click Approve on the selected BU candidate for Department approvers

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) acting as developer |
| Human owner | Sagar (spathur) |
| Trigger | User: "In Evaluator Workbench, under BU Candidates, after radio button on for the candidates, please provide an Approve button on selection box the right side for department-level approvers to review and approve candidates directly from the screen" |

## Prompt (summary)
Department approvers should be able to approve the BU candidate they picked straight from its card in the Evaluator Workbench.

## Inputs used
- `frontend/src/app/pages/review.html`, `review.ts`, `review.spec.ts`
- `frontend/src/app/api/permissions.ts` (`decide`: Evaluator, Department), `role.service.ts`
- `frontend/src/styles.scss` (`.candidate`)

## Output
- `review.html`: the selected candidate card has an **Approve** button on the right of its header. It is shown only for the Department role and only on the card whose radio is on.
- `review.ts`: `isDepartment` and `approveCandidate(c)`. It sets the candidate, switches the decision to Equivalent (the reason code is prefilled as before: EQ-CONTENT at ≥ 80 % overlap, otherwise EQ-EVALUATOR) and calls the existing `submit()`. It uses the same `POST /api/decisions`, so there is no API or contract change and the backend still checks the role.
- The button is disabled while saving, when the recommendation is preliminary (no complete syllabus), and until the reason codes have loaded. It uses the catalog year, note and Reusable flag from the "Your decision" form.
- `styles.scss`: `.candidate__top` puts the radio label on the left and the button on the right.
- `review.spec.ts`: 2 tests. Department: the button appears only on the selected card, and the request posts `Equivalent` with that candidate. Evaluator: the button is not shown.

- Follow-up "make sure this approve is reflected in PostgreSQL": no code change needed. `POST /api/decisions` → `_save_decision` writes through `db.save_decisions` (tables `decisions` and, for a one-off decision, `decision_scope`) BEFORE the in-memory store changes, and `save_audit` adds an `audit_log` row with `actor_role` = Department. The live API (`bu-solutions-api`) has `POSTGRES_HOST` set. New test `backend/tests/test_api.py::test_department_approve_is_written_to_postgres`: a Department approval reaches `save_decisions` and the audit log, and a failed database write returns 503 with nothing changed.

## Human review
- Pending.

## Verification
- `npx ng test --watch=false`: 9 files, 66 tests passed.
- `python -m pytest -q` (backend): 407 passed.

## Commit
See git log (`developer: one-click Approve on the selected BU candidate for Department (developer-01)`).
