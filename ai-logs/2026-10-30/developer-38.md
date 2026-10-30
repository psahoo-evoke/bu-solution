# developer-38 · Status page heading per signed-in role

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) acting as developer |
| Human owner | Sagar (spathur) |
| Trigger | User: department sees "Student Transfer credit Status"; student sees "My Tranfer credit Status" instead of "Transfer credit status" |

## Prompt (summary)
Rename the status page heading depending on who is signed in.

## Inputs used
- `frontend/src/app/pages/student-status.html`, `student-status.ts`, `student-status.spec.ts`

## Output
- `student-status.ts`: new `heading` computed from the role: Student → "My transfer credit status", Department → "Student transfer credit status", every other role keeps "Transfer credit status".
- `student-status.html`: the `<h1>` shows `heading()`.
- Wording kept in the app's sentence case; the typo "Tranfer" in the request was corrected.
- The navigation link ("My status" / "Student status") and the browser tab title are unchanged.

## Human review
- Pending.

## Verification
- `npx ng test --watch=false`: 11 files, 82 tests passed (new tests for Student, Department and Evaluator headings).

## Commit
See git log (`developer: status page heading per signed-in role (developer-38)`).
