# developer-04 · Front end on contract v0.2.0: role gating, 401/403 guidance, reason codes from API

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | developer |
| Tool / model | Claude subagent (general-purpose) acting as developer |
| Human owner | Front-end dev |
| Trigger | Orchestrator follow-up after architect-03 (openapi v0.2.0: default-deny `x-roles`, `GET /api/reason-codes`) |

## Prompt (summary)
(1) Load reason codes from the new endpoint instead of the hard-coded copy. (2) Handle 401/403 with a clear "switch role" message, and hide or disable actions the current role can't use, per `x-roles`. (3) Make sure the default role on first load lets the student page work. Don't touch `backend/`, don't commit, run `ng build` + `npm test`.

## Inputs used
- `docs/api/openapi.yaml` v0.2.0 (`x-roles` per operation, `ReasonCode` schema)
- Front end from developer-02 (commit e98fa43)
- The parallel backend, run locally (read-only) to check the new routes and run e2e

## Output
- `frontend/src/app/api/permissions.ts` (new): the `x-roles` matrix per operation, `can(role, op)`, `switchRoleMessage(op)` (e.g. "Switch role to Evaluator or Department to decide."), `suggestedRole(op)`
- `api/errors.ts`: `describeError(err, role, op)`. A 401 says "No valid demo role was sent. Pick a role in the top bar…". A 403 says "The <role> role can't do this. Switch role to … to …".
- `api/models.ts`: removed the hard-coded `REASON_CODES`; `ReasonCode` now matches the schema (`reason_code`, `decision`, `meaning`)
- `api/api.service.ts`: `listReasonCodes()` → `GET /api/reason-codes`
- `pages/review.*`:
  - Reason codes come from the API, filtered by decision. The form shows a loading state or an error banner with Retry, and submit stays disabled until a code is chosen.
  - Roles other than CreditStaff, Evaluator or Department never call `/review-queue` or `/recommendation`. They see "Switch role to CreditStaff, Evaluator or Department to open the review queue." with a one-click switch.
  - CreditStaff sees the queue and comparison read-only.
  - Decide and batch work only for Evaluator or Department; batch checkboxes are disabled for other roles.
  - The queue reloads or clears when the role changes.
- `pages/student-status.*`:
  - Transcript upload is hidden unless the role is Student or CreditStaff; other roles see a read-only note.
  - Syllabus upload shows only for Student, CreditStaff, Evaluator and Department.
  - Errors are tagged with the operation.
- `pages/registrar.*`:
  - Export is enabled for Registrar and CreditStaff, reset for CreditStaff and Registrar; for other roles the buttons are disabled and a hint explains why.
  - A banner offers "Switch to Registrar".
- `pages/evaluation.ts`: errors are tagged with the operation.
- Default role on first load stays **Student**, which `x-roles` allows on `/students` and `/students/{id}/evaluation`. A unit test checks that the header is sent.
- Tests:
  - New: `api/permissions.spec.ts`, `pages/review.spec.ts`.
  - `api/api.service.spec.ts`: new cases for reason codes and the default role header.
  - `e2e/demo.spec.ts`: new step "a Student cannot open review data and is told which role to use".
- `frontend/README.md`: roles section; reason codes now come from the API

## Human review
- Pending review by the front-end dev.

## Verification
- `npx ng build`: **success, no warnings**.
- `npm test` (Vitest + jsdom, headless): **6 files, 22 tests passed**.
- Checked the backend's new routes with curl: `/api/reason-codes` returns 401 with no role and 200 as Student; `/api/review-queue` returns 403 as Student.
- Playwright `e2e/demo.spec.ts` against the local backend and `ng serve`, using the preinstalled Chromium via `CHROME_BIN`: **6/6 passed**. Servers were stopped afterwards.

## Not done / gaps
- The role matrix is copied by hand from `x-roles`. If the contract changes, `permissions.ts` must be updated too, because no code is generated from the spec.
- Production rule "Student only for own student_id" is not modelled in the UI: the demo student picker still lists all students. The server must enforce it.
- `/review` and `/registrar` stay in the nav for every role; they show the switch-role guidance instead of data.
- Did not run `scripts/build_log_index.py`, because it rewrites `ai-logs/README.md`. The orchestrator should run it.

## Commit
see git log
