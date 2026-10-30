# developer-34 · Step 5: automatic syllabus request, and the syllabus next to the AI comparison

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer (backend, frontend, contract) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Human, with the "How the work runs today" table: the department evaluator should have the syllabus content while evaluating, along with the AI comparison. The syllabus request is part of the Credit Evaluation Department process: an automatic mail to the student, no request button. The upload button stays on the student page. |

## Before
- The workbench told the evaluator to "Request the syllabus (TS/TM)", but it had no way to do that.
- The only request was a side effect of clicking **Upload syllabus** on the student page. It emailed a fixed notification list, never the student.
- The evaluator could not see the syllabus text, only the AI comparison built from it.

## Decisions and why
1. **The request is automatic, right after a transcript upload** (`auto_request_syllabi`, called at the end of `POST /students/{id}/transcripts`).
   - Why: in the process, the request belongs to the Credit Evaluation Department's processing step (step 3 to 5), not to a person clicking.
   - The upload is the moment the "maybe" courses become known.
2. **One email per student and upload, listing every course** that has no syllabus (TS) or an incomplete one (TM).
   - Why: one clear to-do list instead of a mail per course.
   - Courses already requested are not asked again. A request that **failed** is retried on the next upload.
   - Courses whose syllabus was already uploaded through the app are skipped, since a syllabus is uploaded only once and the department reviews what is on file.
3. **Who receives it:**
   - A student who **registered themselves** gets it at the address they gave, with the notification list (`SYLLABUS_REQUEST_TO/CC`) copied.
   - **Seeded sample students are never emailed** (their addresses are made up, some on the real bu.edu domain); for them the list receives it, with the student named.
   - Why: this keeps the earlier safety rule of not emailing made-up addresses, while real users get their own request (`accounts.registered_student_email`).
4. **The record is the audit log** (action `syllabus_request`, actor `System`), not a new table.
   - Why: the audit log is already saved in PostgreSQL and loaded at start-up, so requests survive restarts; it is also where an auditor looks.
   - The old in-memory request dict was removed.
5. **A failed email never fails the transcript upload.**
   - Why: the student's courses must still be evaluated.
   - The failure is recorded, shown to the evaluator ("email failed, retried on the next upload"), and retried.
6. **Upload syllabus only uploads.**
   - Why: a click on Upload should not send an email. That side effect was the old way of requesting.
   - After a transcript upload, the student's message says which syllabi are needed, and whether we emailed them.
7. **The evaluator reads the syllabus** via the new `GET /courses/{ext_id}/syllabus` route.
   - Access is limited to staff (CreditStaff, Evaluator, Department); a department sees only its own department's courses.
   - It returns the text extracted from the PDF, capped at 30,000 characters, plus the requests sent to the students waiting on this course.
   - The workbench shows it in a "Syllabus" panel above the BU candidates (open when there is text), as **plain text**, never HTML. Any injection warning is repeated there.
   - Why: in step 6 the department evaluator decides from the syllabus, the course descriptions, the learning outcomes and the credit hours; the AI comparison helps but does not replace reading the source.
8. **The banner states what actually happened** ("Requested from Maya R. Delgado automatically on 30 Oct 2026 · emailed to the student").
   - With no request on record it says so: "No request on record yet: the student is asked automatically when their transcript is uploaded."
   - Why: the seeded sample students were never processed, so the banner must not claim a request that was not sent.
9. **The staff re-send route stays** (`POST …/syllabus-request`), now built on the same function. It keeps the 15-minute repeat guard, ignores failed requests for that guard, and is no longer called from the page.
   - Why: a contract route should not disappear without a reason; staff may need to send a request again.

## Edge cases covered
- Re-uploading a transcript (same file: nothing happens; another file: no second request).
- A course already requested.
- A failed email.
- A sample student vs a registered student.
- An app-uploaded syllabus (not requested again).
- A syllabus shared by several students.
- Injection text in a syllabus (warning, plain text).
- A department reading another department's syllabus (403).
- A student or anonymous caller (403 / 401).
- An unknown course (404).
- A late answer for a previously opened course (ignored).

## Output
- **Backend:**
  - `main.py`: `syllabus_requests`, `_send_syllabus_request`, `auto_request_syllabi`, the re-send route on top of them, and `GET /courses/{ext_id}/syllabus`; the transcript upload returns `upload.syllabus_request`.
  - `notify.send` takes recipients.
  - `accounts.registered_student_email`.
  - `guard.py`: the new route's roles.
- **Contract v0.6.0:** `GET /courses/{ext_id}/syllabus` (`CourseSyllabus`), `TranscriptUploadResult.upload.syllabus_request`, and the re-send route description.
- **Frontend:**
  - workbench: syllabus panel, request status in the banner
  - student page: Upload only uploads; the transcript message names the syllabi needed
  - models and the API service
- `docs/architecture.md`: the data flow includes the automatic request and the evaluator reading the syllabus.

## Human review
- Requested by the human with the process table.

## Verification
- `pytest -q backend`: 519 passed. New `tests/test_syllabus_requests.py`:
  - asked once for TS courses only; a sample student goes to the list; a registered student is emailed with the list copied
  - a failed email is recorded and retried; no request from page loads
  - the evaluator reads the text and the requests; staff only; injection flag; department scoping
- `test_notify.py` was updated to the new wording.
- `npm test`: 74 passed. New: the workbench shows the request status and the syllabus panel; `syllabusAskedMessage` is covered.
- `ng build --configuration production`: OK.
- Live, read-only, portal mode, `evaluator@bu.edu` (`wb_syllabus.mjs`, `.shots/wb-syllabus-*.png`):
  - NYU PSYCH-UA 10: the syllabus panel shows "complete · uploaded 29 Oct 2026" with 2,389 characters of text above the BU candidates
  - NYU PSYCH-UA 25: "Decide once the syllabus arrives" and "No request on record yet" (a sample student)
  - no console errors
  - No transcript was uploaded live, so the local database is unchanged and no real email was sent.
