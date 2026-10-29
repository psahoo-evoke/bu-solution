# developer-04 · Home / SSO sign-in page: My view, Student View, Department View

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (frontend) |
| Tool / model | Claude Code (Opus 5.5) |
| Human owner | Sagar (spathur) |
| Trigger | User: "create SSO login page, so student can login and department login, refer frontpage.txt, add more speciality and make UI better, and all functionality should work as before" |

## Prompt (summary)
`frontpage.txt` lists the page sections: "My view", "Student View", "Department View".

## Inputs used
- `frontpage.txt`, `src/app/api/permissions.ts` (what each role can do), the existing app shell and routes, `e2e/demo.spec.ts`

## Output
- `pages/home.{ts,html,scss}`, the new route `/` (previously a redirect to the student page). It has:
  - A hero with the three principles.
  - **My view**: the current user and role, with "Continue to my view". In Entra mode the assigned roles appear as chips, and a signed-in user with no role sees a message.
  - **Student View** and **Department View** cards, each listing what that role can do. In Entra mode the button is "Sign in with Microsoft", and the chosen view opens after the redirect if the account has the role (otherwise a message). In demo mode it is "Continue as Student/Department".
  - "How it works" (4 steps) and "Other staff" quick links (Evaluator, Credit staff, Registrar, Advisor, AI evaluation).
- `api/auth.service.ts`: `login(intent)` keeps the chosen view across the redirect (sessionStorage), and `consumeIntent()`.
- `api/auth.guard.ts`: in Entra mode the app pages need a signed-in user with a role, otherwise the user is sent to `/`.
- `api/role-home.ts`: the start page per role, and role labels.
- `app.html`:
  - The logo links home, and the nav has a Home link.
  - In Entra mode, the app links are hidden until sign-in.
  - The sign-in and no-role screens moved to the home page.
- `styles.scss`: phone layout for the top bar (the nav is one scrollable row).
- Tests: `pages/home.spec.ts` (10 tests: views, demo navigation, Entra sign-in intent, Student blocked from the Department view, no-role message, guard). The e2e first test now starts from the home page.

## Human review
- Pending.

## Verification
- `ng build --configuration production`: OK. `ng test`: 39 passed (8 files).
- Playwright e2e against local servers (system Chrome): 7 passed.
- Screenshots checked at 1366 px and 390 px wide.

## Commit
see git log
