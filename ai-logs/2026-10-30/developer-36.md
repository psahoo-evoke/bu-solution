# developer-36 · In-app notifications for students

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer (backend, frontend, contract) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Human: "once student login, he should see all the notification on app" |

## Decisions and why
1. **What a student is notified about:**
   - transcript received
   - syllabus needed, and each reminder
   - syllabus received
   - a decision on one of their courses (only when it applies to them: reusable, or made for them)
   - credit posted to their BU record
   
   Why: these are the moments in the process table where the student either has to act or gets a result.
2. **Built from what the app already records** (`app/notifications.py`), with no new event table: the audit log (requests, decisions, postings), transcript records and syllabus upload times.
   - Why: every event already has a stored timestamp, and nothing can be forgotten when a new place in the code changes something.
3. **Shown even when email failed or no mail service is configured.** The app becomes the reliable channel, with email as the extra.
4. **Never shown:** staff email lists, the evaluator's name or note, other students. Portal students reach only their own ID (the guard's existing rule).
5. **Read state is one "read up to" time per student**, in the new PostgreSQL table `notification_reads` (created with `CREATE TABLE IF NOT EXISTS`, which only adds a table), so it is the same on every device.
   - It is set to the newest notification the student was shown, not to "now", so an event in the same moment stays unread.
   - Only the Student role marks read (`POST …/notifications/seen`). Staff reading a record (`GET`) never clear the student's badge.
6. **The bell in the top bar**, shown only to a signed-in student:
   - an unread badge (9+ above nine), and a panel listing the notifications newest first
   - what was new stays highlighted while the panel is open
   - Escape or clicking outside closes it; clicking an item opens the student's status page
   - it refreshes on navigation and every minute while the tab is visible
   - the badge clears as soon as the panel opens, and comes back if saving the read state fails
   - an older refresh can never overwrite a newer answer (version counter), a race found live
   - the text is interpolated only, never rendered as HTML
7. **Fix found during the live check:** the workbench showed a "next reminder" for a request on a course that is no longer waiting for a syllabus (Jordan's NEU HIST 1130 is now under age review, RV-AGE). The reminder job already skipped it. The workbench now uses the same rule. developer-35 named this request as "due 1 Nov"; that was wrong, and no reminder will be sent for it.

## Edge cases covered
- No events yet.
- Same-moment events.
- A reusable decision vs a one-student decision.
- Courses not on the student's transcript.
- Staff viewing.
- Another student's ID.
- An unknown student.
- Mark-read failure.
- A stale refresh.
- Phone width.

## Output
- **Backend:**
  - `notifications.py` (new); `main.py`: `GET /students/{id}/notifications` and `POST …/seen`
  - `guard.py` roles
  - `store.notification_seen`; `db.py`: the `notification_reads` table, loading it and `save_notification_seen`
- **Contract v0.8.0:** the two routes and `StudentNotifications`.
- **Frontend:**
  - `shared/notification-bell.ts` (new) in `app.html` for signed-in students
  - models and the API service
  - styles
- `main.py`: the workbench reminder plan uses the reminder job's rule.

## Human review
- Requested by the human.
- The live check wrote a read state for the sample student Jordan (SYN-24002) to the shared database, and the table `notification_reads` now exists there.

## Verification
- `pytest -q backend`: 566 passed. New:
  - `tests/test_notifications.py` (6): the journey newest first with no internal details, decision scoping, staff views do not mark read, only the student marks read, portal own-id only
  - a reminder-plan test
- `npm test`: 78 passed. New `notification-bell.spec.ts` (4): badge and highlight, a stale refresh, the badge back on failure, the empty state. `ng build --configuration production`: OK.
- Live, portal mode, `jordan.reyes@bu.edu` (`bell.mjs`, `.shots/bell-*.png`):
  - "Notifications, 1 unread", with the list showing "Syllabus needed for NEU HIST 1130"
  - the badge cleared when opened; Escape closes
  - a second session showed it as read, so the server read state persists
  - desktop and phone; no console errors
