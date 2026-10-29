# developer-24 · A syllabus can be uploaded only once; the button disappears after the upload

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (backend + frontend) + architect (contract) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | Sagar (spathur) |
| Trigger | User: users may upload a syllabus only once; once it is uploaded (and the email request sent), hide the upload section and remove the Upload syllabus button to prevent duplicate uploads |

## Output
- `backend/app/store.py`: `SyllabusRecord.uploaded_at`, set only by an upload through the app.
- `backend/app/db.py`: loaded from `syllabi.received_at` (already written by uploads; NULL for seed rows). No schema change.
- `backend/app/main.py`:
  - **Upload:** `POST /courses/{ext_id}/syllabus` answers **409** once a syllabus was uploaded for the course. It is checked before reading the file and again under the lock, so of two simultaneous uploads only one wins.
  - **Email request:** `POST /students/{id}/courses/{ext_id}/syllabus-request` answers 409 too, so no "syllabus needed" email is sent after the upload.
  - **Course lines** carry `syllabus_uploaded`.
  - Seed syllabi do not count as uploaded (an incomplete seed syllabus can be replaced once), and a demo reset clears uploads.
- `docs/api/openapi.yaml`: `CourseEvaluation.syllabus_uploaded`, plus the 409 responses on both routes.
- Frontend:
  - `student-status`: Upload syllabus is shown only while `!line.syllabus_uploaded`; an uploaded course shows "✓ Syllabus uploaded". After a successful upload the page reloads, so the button disappears.
  - `errors.ts`: a 409 shows the API message.
  - `models.ts`: new field. `styles.scss`: `.syllabus-done`.
- Tests:
  - `test_api.py`: 3 new (upload once for any role + no email request afterwards; seed syllabi not counted; demo reset allows an upload again).
  - `test_hardening.py::test_page_limit`: reordered. It uploaded twice to one course; now the 31-page rejection comes first, since a rejected file is not an upload.
  - `student-status.spec.ts`: 1 new (no upload input, "✓ Syllabus uploaded" shown).

## Verification
- `pytest -q`: 389 passed. `ng test`: 64 passed. `ng build --configuration production`: OK.
- Playwright e2e: not run (the local backend had been stopped for low memory).

## Commit
see git log
