# developer-17 · Portal registration accepts any email; the email is saved on the student record

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | 1. Registering with a non-BU address failed with "Use your BU email address (name@bu.edu)"; the human asked: "it should consider any email". 2. Then a screenshot of the `students` table showing `email` = NULL for SYN-24006: "email not persitest". |

## Prompt (summary or verbatim)
Let students and department reviewers register, and sign in, with any email address. Then save the registration email on the student record.

## Inputs used
- `backend/app/accounts.py` (`EMAIL_RE`, `register_student`, blob document), `backend/app/db.py`
- `frontend/src/app/pages/login.html`, `login.ts`, `home.html`
- `backend/tests/test_portal.py`, `test_accounts_store.py`

## Output
- `backend/app/accounts.py`:
  - `EMAIL_RE` accepts any well-formed address on any domain; the message is now "Enter a valid email address (name@example.com)". Sign-in and registration share this check.
  - `register_student` creates the `Student` with `email=`. Before, the email was saved only on the portal account, so `students.email` was NULL.
  - The Blob Storage copy of registered students (used without PostgreSQL) now writes and reads `email` too.
- `backend/app/db.py`: `ensure_schema()` copies `portal_accounts.email` onto students whose `email` is NULL. It's idempotent, and it fixed SYN-24005 and SYN-24006 in the live database.
- Frontend:
  - "BU email" is now "Email" on the sign-in and register forms, with placeholder `name@example.com`.
  - The sign-in error and the home-page hint say "email" instead of "BU email".
- Tests:
  - `test_portal.py`: `maya@gmail.com` now gets 404 (not registered) instead of 422; a malformed `sam@nodomain` is still 422.
  - New `test_register_accepts_any_email_domain` checks that the email reaches the student record.
  - `test_accounts_store.py` expects `email` in the blob document.
- Checked, no code change: the "Spring 2027 shows as Fall 2026" report. In a real browser the form posted `"start_term":"Spring 2027"`, and the API stored it. The likeliest cause is a resubmit after the email error, with the term back on its default.
- Not done: registration still doesn't collect `bu_school`, `phone`, `address` or `previous_school`.

## Human review
- Pending. Open sign-up with any email is a known demo limit (README "Known limits").

## Verification
- `pytest -q backend`: 374 passed.
- Live: logging in with `someone@gmail.com` returned 404 (valid email, not registered). After a restart, `GET /api/students` showed `psahoo@evoketechnologies.com` for SYN-24006.

## Commit
see git log
