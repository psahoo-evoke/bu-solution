# developer-19 · Transcript upload records: previous school's student ID, duplicate detection, change summary

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (API contract change: architect review needed) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | "this student_id is portal student id, but in transcript different student id, so we are not storing that?", then "how do you handle duplicate transcript upload?", then "yes" to building the proposed changes |

## Prompt (summary or verbatim)
The transcript's printed Student ID is the previous school's ID, not the portal ID. Store it, stop rejecting real transcripts because of it, and handle duplicate and replacing uploads.

## Inputs used
- `backend/app/main.py` (`upload_transcript`), `store.py`, `db.py`, `ingest.py` (`parse_transcript` reads `Student ID`), `blob_store.py`
- The sample transcripts in `data/synthetic/transcripts/` print `SYN-24001-NYU`-style IDs.

## Output
- **Finding:** the upload required the printed Student ID to start with the portal ID. A real transcript (e.g. NYU `N12345678`) was rejected with 422, and the ID was never stored. The `_archive()` blob path was thrown away too.
- `backend/app/store.py`:
  - new `TranscriptRecord` with: `transcript_id`, `student_id`, `school_code`, `school_student_id`, `sha256`, `blob_url`, `course_count`, `uploaded_by` and `uploaded_at`
  - `Store.transcripts` list
  - `Store.latest_transcript()`
- `backend/app/db.py`:
  - a `transcripts` table and index, added to `EXTRA_TABLES` so existing databases get them at startup
  - `save_transcript(..., record)` writes the record in the same transaction as the lines
  - `load_store` reads the records back; `reseed` deletes them, like the other runtime data
- `backend/app/main.py` `upload_transcript`:
  - rejects the upload only when the printed ID belongs to **another portal student**, or differs from the ID on **this student's earlier transcript from the same school**
  - the **same file** as the latest transcript from that school is a duplicate: nothing is archived or changed, and the response has `upload.duplicate = true`
  - a **replacing** upload reports `added`, `removed` and `updated` (new grade or credits) as "COURSE (Term)". It compares lines, so seeded lines with no upload record count as replaced.
  - every accepted upload saves a `TranscriptRecord` with `blob_url`, and `uploaded_by` set to the portal email or the demo role
- Response: `StudentEvaluation` plus `upload` (see `TranscriptUploadResult` in `docs/api/openapi.yaml`), which also documents the 422 cases.
- Frontend:
  - `models.ts` gains `TranscriptUpload`.
  - `student-status.ts` adds `transcriptUploadMessage()`, which shows "already on file … Nothing changed" for a duplicate, the course count for a first upload, or "Replaced the earlier … transcript: 1 added (…); 1 removed (…)".
- Decision: a different ID for the same school is **rejected**, not flagged, because nothing in the app shows staff those flags yet.
- Not done:
  - matching the student's name on the PDF (the parser doesn't extract it)
  - `transcript_id` on `transcript_lines`
  - a staff view of a student's transcripts
  - the `transcripts` table is created in `db.py`, like `portal_accounts`; it isn't in `schema.sql` or `docs/data-model.md` yet

## Human review
- Pending. The API contract change (`openapi.yaml`) needs architect review.

## Verification
- `pytest -q backend`: 379 passed (5 new tests in `test_api.py`). `npm test`: 59 passed (3 new).
- Live against the Azure database: Maya's NYU transcript, uploaded as Maya through portal sign-in, returned 201 and created `TR-2e85e8c47d7c` with `school_student_id = SYN-24001-NYU`, uploaded by `maya.delgado@bu.edu`. The same file again returned `duplicate: true` and added no row.
- `blob_url` is empty locally because `AZURE_STORAGE_BLOB_ENDPOINT` isn't set in `backend/.env`.

## Commit
see git log
