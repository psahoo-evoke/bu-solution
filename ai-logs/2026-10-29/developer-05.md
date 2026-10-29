# developer-05 · Portal sign-in: per-student and per-department accounts with registration

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (backend + frontend) + devops (deploy script) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | Sagar (spathur) |
| Trigger | User: "for student login refer student_loginsample.txt and create per student sso, inside portal that student view should be viewed and password can be admin and if student not registered give to register for student; same way do for department login" |

## Prompt (summary)
- A per-user sign-in, where each student sees only their own view.
- Sample students from `student_loginsample.txt`, password `admin`.
- Registration for new students, and the same for departments.

## Inputs used
- `student_loginsample.txt`: SYN-24001..24004, `@bu.edu` emails, password admin
- Department names from the course data (`program_area`)

## Output
- `backend/app/accounts.py` (new mode `TRANSFERIQ_AUTH_MODE=portal`):
  - **Seeded accounts:** the 4 sample students, 6 department accounts (`<dept>.dept@bu.edu`) and 4 staff accounts (evaluator, creditstaff, registrar, advisor `@bu.edu`).
  - **Passwords:** PBKDF2-SHA256 hashes. The seeded accounts use `TRANSFERIQ_DEMO_PASSWORD` (default `admin`).
  - **Sessions:** an HS256 session token, valid 8 h.
  - **Registration:** a student account gets a new empty student record (`SYN-24005`, …); a department account is bound to one department. Registered accounts survive a demo reset.
- `backend/app/guard.py`, portal mode:
  - Every `/api` call needs a session token, and the role comes from the account (`X-Demo-Role` is ignored).
  - **A student may only touch `/students/{own id}`** (403 otherwise).
  - `/api/auth/*` is public.
- `backend/app/main.py`:
  - New public `/api/auth/{options,login,register/student,register/department}` routes, on their own router (not contract operations).
  - **Scoping:** `GET /students` returns only a student's own record; the review queue is forced to a department's own department; single and batch decisions on another department's course get 403; a student can add a syllabus only for a course on their own transcript.
- Frontend:
  - `api/auth.service.ts`: portal mode (sign-in, register, session in sessionStorage, expiry check); `secured()` = portal or entra.
  - `pages/login.*`: `/login/student|department|staff`, with Sign in / Register tabs, sample accounts (password admin), and a "No account → Register" prompt.
  - Home cards link to the sign-in pages.
  - The guard sends a student to their own record.
  - The nav shows only the pages the role can use, and "My status" for students.
  - The header shows a role badge, the user's name and Sign out.
  - The interceptor signs the user out on a 401.
- `scripts/deploy_aca.sh`: `PORTAL_AUTH=1`.

## Human review
- Pending.
- Known limits (demo only, synthetic data):
  - Shared password `admin`.
  - Anyone can self-register as a department reviewer.
  - Accounts are in memory, so a restart loses registered accounts and signs everyone out.
  - No login rate limiting.
  - The `/api/auth/*` routes are not yet in `docs/api/openapi.yaml` (architect).

## Verification
- `pytest -q`: 338 passed (+17 portal tests). `ng test`: 47 passed (+8). `ng build`: OK.
- Playwright e2e (demo mode, local): 7 passed.

## Commit
see git log
