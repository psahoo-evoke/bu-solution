# developer-39 · Title-case status page names, also on the menu link

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) acting as developer |
| Human owner | Sagar (spathur) |
| Trigger | User: "when Student login page rename to My Transfer Credit Status and department page rename to Student Transfer Credit Status" |

## Prompt (summary)
Follow-up to developer-38: use the exact title-case names, and rename the page (not only its heading).

## Inputs used
- `frontend/src/app/shared/status.ts`, `pages/student-status.ts`, `pages/student-status.spec.ts`, `app.ts`, `app.html`

## Output
- `shared/status.ts`: new `statusTitle(role)`: Student → "My Transfer Credit Status", Department → "Student Transfer Credit Status", other roles → "Transfer credit status". Kept in `shared/` so the top bar can use it without loading the lazy status page.
- `pages/student-status.ts`: the heading uses `statusTitle`.
- `app.ts` / `app.html`: the top-bar link uses the same names for Student and Department (was "My status" / "Student status"); other roles keep "Student status".
- Browser tab title unchanged.

## Human review
- Pending.

## Verification
- `npx ng test --watch=false`: 11 files, 82 tests passed.
- `npx ng build`: succeeded.

## Commit
See git log (`developer: title-case status page names, also on the menu link (developer-39)`).
