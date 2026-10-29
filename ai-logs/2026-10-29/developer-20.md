# developer-20 · Never compare the transcript's Student ID with portal IDs

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Ekansh (portal SYN-24006) uploaded a transcript printed with `SYN-24005-NYU` and got 422. The human said: "here both id should not be equal. we should not compare" |

## Prompt (summary or verbatim)
The ID printed on a transcript belongs to the previous school. Don't compare it with portal student IDs.

## Inputs used
- `Downloads/Transcript_SYN-24005_NYU_Ekansh_Malhotra.pdf` (parsed: `Student ID SYN-24005-NYU`, New York University, 8 course lines)
- `backend/app/main.py` `upload_transcript` (developer-19), backend log (`POST /api/students/SYN-24006/transcripts` returned 422)

## Output
- **Cause:** developer-19 rejected a transcript whose printed ID started with another portal student's ID. `SYN-24005` is the registered "Persistence Check" test account, so Ekansh's PDF was read as SYN-24005's transcript.
- `backend/app/main.py`: removed that check. The printed ID is stored as `school_student_id` and compared only with this student's earlier transcript from the same school; a different ID there is still rejected.
- Tests:
  - `test_api.py`: `test_upload_transcript_wrong_student` is now `test_transcript_student_id_is_not_compared_with_portal_ids`. Maya's PDF uploaded for SYN-24002 is accepted, with `school_student_id = SYN-24001-NYU`.
  - `test_blob_store.py::test_rejected_upload_is_not_stored` now rejects a syllabus PDF posted as a transcript (unknown institution), and still checks that nothing is archived.
- `docs/api/openapi.yaml`: the transcript-upload 422 description no longer lists "another portal student's transcript".
- Trade-off: nothing now stops a transcript being attached to the wrong student, which matters most for CreditStaff uploads. Matching the name on the PDF (not built) is the planned safeguard.

## Human review
- The human decided this rule ("we should not compare").

## Verification
- `pytest -q backend`: 379 passed.
- Backend restarted with the change. The human re-tries Ekansh's upload.

## Commit
see git log
