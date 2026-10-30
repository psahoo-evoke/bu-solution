# adoption-01 · README: every feature we built, clearly

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | adoption |
| Tool / model | Solutionauts AI (CLI) acting as adoption |
| Human owner | Sagar (spathur) |
| Trigger | User: "all the functionality, department, student, storing blob, db update, sending mail if upload syllabus, chatbot and add more all functionality we implemented push to readme clearly" |

## Prompt (summary)
Rewrite the README so it lists every feature the team built, per user and per Azure service.

## Inputs used
- Old `README.md`; module docstrings of `backend/app/` (db, blob_store, notify, notifications, accounts, ingest, search, ratelimit, credit_check, credit_chat); `main.py` routes and the reminder settings; `frontend/src/app/api/permissions.ts`; the live API's settings (names only); ai-logs of 2026-10-29/30.

## Output
- `README.md` rewritten: new section 3 Features (students, department reviewers, staff, public check and chatbot, behind the scenes: rules engine, matcher, PostgreSQL, Blob Storage, email, audit, sign-in), chatbot prompts to try, architecture diagram with every Azure service and which are live, configuration table, deploy section, updated test counts (599 backend, 94 frontend) and known limits.
- Correction against the request: uploading a syllabus does **not** send an email. Emails go out when a syllabus is needed (automatically after the transcript upload), as reminders every 2 days (at most 7) and on a manual staff request; an upload stops the reminders and shows "Syllabus received" in the student's notifications. The README says this.
- "In-memory course data" removed from known limits: the live app stores everything in PostgreSQL.

## Human review
- Pending.

## Verification
- Every claim checked against the code (routes, permissions, settings, defaults) and the live app's settings; all relative links in the README point to existing files.

## Commit
See git log (`adoption: README lists every feature, Azure service and setting (adoption-01)`).
