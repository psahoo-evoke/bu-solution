# developer-45 · No Home for signed-in students and departments

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) acting as developer |
| Human owner | Sagar (spathur) |
| Trigger | User: "Once a student or department user logs into the application, the Home button and its associated functionality are no longer required. Please remove the Home button from the application UI and disable/remove any related navigation or functionality for both user roles." |

## Prompt (summary)
Signed-in students and department reviewers should not see or reach the Home page.

## Inputs used
- `frontend/src/app/app.html`, `app.ts`, `app.routes.ts`, `api/auth.guard.ts`, `api/role-home.ts`, `pages/login.*`, `api/role.interceptor.ts`

## Output
- `api/role-home.ts`: `homeHidden(role, signedIn)`: true for a signed-in Student or Department (one place for the rule).
- Top bar (`app.html`, `app.ts`): the **Home** link is hidden for them; the TransferIQ logo opens their own page instead of `/` (student: their status page; department: the workbench), with an accessible label "TransferIQ, my page".
- `api/auth.guard.ts` + `app.routes.ts`: `homeGuard` on `/` sends a signed-in student or department user to their own page (typing the URL, bookmarks, the back button). A signed-in user without a role stays on the home page, which explains it (no redirect loop with `authGuard`).
- Unchanged on purpose: staff (Evaluator, Credit staff, Registrar, Advisor) keep Home; signed-out visitors and demo mode keep Home (they pick a view there); sign out, an expired session and the sign-in page's "Back to home" still lead to the home page (the user is signed out by then).

## Human review
- Pending.

## Verification
- `npx ng test --watch=false`: 12 files, 101 tests passed (new: Home hidden and logo target for a student and a department; Home kept for staff and signed-out visitors; homeGuard redirects for student and department, allows staff, signed-out and demo).
- `npx ng build`: succeeded.

## Commit
See git log (`developer: no Home for signed-in students and departments (developer-45)`).
