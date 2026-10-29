# developer-13 · Status page title "Transfer credit status"; no student picker for students

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (frontend) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | Sagar (spathur) |
| Trigger | User: after a student signs in, rename "Student transfer credit status" to "Transfer credit status" and remove the student dropdown |

## Output
- `pages/student-status.html`: the heading is "Transfer credit status". The student picker is shown only when the active role is not Student.
- `pages/student-status.ts`: `showPicker` computed. A signed-in student only ever sees their own record (the API enforces this too), so the picker added nothing. Staff, departments and advisors keep it to switch students.
- `pages/student-status.spec.ts`: 2 tests (the title; the picker is hidden for Student and shown for CreditStaff).

## Verification
- `ng build --configuration production`: OK. `ng test`: 54 passed. Playwright e2e (local): 7 passed.

## Commit
see git log
