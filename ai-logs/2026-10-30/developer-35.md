# developer-35 · Syllabus reminders every 2 days

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer (backend, frontend, contract) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Human: "for every 2 days re-request for syllabus. configure it" |

## Decisions and why
1. **Settings, with defaults:**
   - `TRANSFERIQ_SYLLABUS_REMINDER_DAYS=2` (0 turns reminders off)
   - `TRANSFERIQ_SYLLABUS_REMINDER_MAX=7`
   - `TRANSFERIQ_SYLLABUS_REMINDER_CHECK_MINUTES=60`

   The maximum is a safeguard the human did not ask for: about two weeks of reminders, so a student who never answers is not emailed forever. It is a single setting to change.
2. **Only courses that were requested, and are still missing or incomplete, get reminders.** The next one is due N days after the last *successful* request or reminder.
   - Reminders stop by themselves when the syllabus is uploaded or the course is decided.
   - Seeded sample data, never requested, gets none.
   - A failed email does not count, so the next check retries it.
3. **One email per student**, listing every overdue course; the subject starts with "Reminder:". The recipients follow the developer-34 rules: a registered student at their own address with the notification list copied; sample students never.
4. **The API runs the check itself**, every hour (first check one interval after start-up), as a background task in the app. There is also `POST /api/syllabus-reminders/run`, for Credit Staff only, to run it now for a demo or from an external scheduler.
   - Why: the deployment runs one API instance with a database, so an in-process schedule is enough. Running it twice sends nothing twice, because the times come from the audit log in PostgreSQL. Each reminder is recorded at the check's own time.
5. **No mail service: nothing is sent and nothing is recorded** ("skipped").
   - This was found during the live check: the local API and the deployed one share the PostgreSQL database, which already holds requests marked `sent` by the deployed app.
   - A local instance cannot deliver mail. Recording "not sent" reminders would push the real schedule back, so it records nothing.
6. **What people see:**
   - The student page next step now says "We email a reminder every 2 days until it arrives." The text comes from the API, built from the setting (`rules.STATE_TEXT`). The old frontend override that said "days 7, 21 and 45 (email sending not enabled)" was removed, because the reminders are real now.
   - The workbench banner shows "reminded 1× (last 1 Nov) · next reminder 3 Nov, 09:15", or "no more reminders planned".
   - `GET /courses/{ext_id}/syllabus` now returns one entry per student with `requested_at`, `last_sent_at`, `reminders` and `next_reminder_at`.

## Edge cases covered
- Not yet due.
- Due.
- The same check twice.
- The next one counted from the last reminder.
- The maximum reached.
- The syllabus arrives.
- A failed send is retried.
- Never requested.
- Reminders off.
- No mail service.
- Roles (Credit Staff only for "run now").

## Output
- `rules.py`: the reminder settings and the student text.
- `main.py`:
  - `_reminder_plan`, `send_due_reminders`, `_reminder_loop` (started and stopped with the app), and `POST /syllabus-reminders/run`
  - `_send_syllabus_request(reminder=, at=)` and `_audit(at=)`
  - the syllabus route returns per-student reminder plans
- `guard.py`: the route's roles. **Contract v0.7.0.**
- Frontend:
  - `shared/status.ts`: the next step is shown as given by the API
  - workbench banner: the reminder plan
  - models

## Human review
- Requested by the human.
- After deploying with a mail service, the requests already in the shared database will get reminders 2 days after their last send. Jordan's NEU HIST 1130, for example, is due 1 Nov.

## Verification
- `pytest -q backend`: 539 passed. 11 new reminder tests in `tests/test_syllabus_requests.py`.
- `npm test`: 74 passed, with the specs updated to the real reminder text and the banner plan. `ng build --configuration production`: OK.
- Live, local API in portal mode, Credit Staff:
  - "run now" returned `skipped: "no mail service configured"` and wrote nothing
  - the student next step reads "…every 2 days until it arrives."
  - NEU HIST 1130 (Jordan, sent 30 Oct 08:07) shows `next_reminder_at` 1 Nov 08:07
