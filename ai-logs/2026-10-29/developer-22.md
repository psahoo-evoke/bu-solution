# developer-22 · Upload hardening for transcripts and syllabi: junk, hostile and scanned PDFs, file size

| Field | Value |
| --- | --- |
| Date | 2026-10-29 (security-relevant: needs security review) |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | "what about junk transcript pdf, prompt inject pdf, security, any other type of pdf", then "do apply for all above cases for syllabus upload also. and what about the size of file", "if pdf it is a scan or a photo, ocr happening?" |

## Prompt (summary or verbatim)
Probe how both uploads handle bad PDFs, then close the gaps found, for transcripts and syllabi.

## Inputs used
- `backend/app/ingest.py`, `main.py`, `matcher.py`, `safety.py`, `guard.py`; `frontend/nginx/default.conf.template`
- Probes through the real upload endpoint, offline: a renamed text file, garbage after `%PDF-`, an unrelated PDF, an unknown school, an image-only PDF, injection in a course title, and 60 made-up course lines.
- Real Azure Document Intelligence OCR of image-only copies of Maya's NYU transcript and the PSYCH-UA 25 syllabus.

## Output
- Findings before the change:
  - A course title with injected instructions was accepted, saved as the course title and description, and sent unfiltered to the AI with `injection_detected = false`. A swayed overlap could have made it batch-approvable.
  - Made-up course lines created external courses without limit.
  - A recipe uploaded as a syllabus was accepted as "incomplete", and a syllabus for another course was accepted.
  - Scans were OCR'd, but the transcript parser found 0 courses in the OCR text, because OCR puts each table cell on its own line.
- `backend/app/ingest.py`:
  - a PDF with no readable text (after OCR, if configured) gets 422 "No readable text…"
  - transcripts: no `Institution:` line gets 422 "does not look like a transcript"; titles are cut to 120 characters, the Student ID to 40, and more than 60 course lines gets 422
  - new `parse_transcript_text()` also reads OCR's one-cell-per-line tables, including a row whose "earned" cell was lost
  - `check_syllabus()` returns `looks_like_syllabus` (a course code line or a syllabus section heading)
- `backend/app/main.py`:
  - transcript: a course title with injected instructions gets 422 and nothing is stored; "Unknown institution" now explains that only catalogue schools can be read
  - syllabus: not a syllabus gets 422; a syllabus for a different course gets 422 "This syllabus is for X, not Y."; injected sentences are still accepted, removed and flagged (ADR 0004)
  - batch refusal reason renamed to "course text flagged for injected instructions"
- `backend/app/matcher.py` (second line of defence):
  - `recommend()` also checks the course title and description for injection, so the course can't be batch-approved
  - `build_prompt()` filters out injected sentences from title and description and caps them at 200 and 2000 characters
- Frontend:
  - the syllabus picker accepts PDF only (it offered `.docx` and `.txt`, which the API always rejected)
  - `uploadProblem()` gives instant messages for non-PDF, empty and over-10-MB files on both uploads
- `docs/api/openapi.yaml`: 415 and 422 cases documented for both uploads.
- File size, unchanged and checked:
  - 10 MB per file, in the API guard (before reading the body, including chunked uploads) and again in `_read_upload`
  - at most 30 pages, 15 s parse time
  - nginx `client_max_body_size 12m`, so the deployed web proxy doesn't cut uploads below the API limit
- Tests:
  - `test_hardening.py`: 7 new tests, one being the OCR fixture `tests/ocr_transcript_SYN-24001_NYU.txt` (real Document Intelligence output, synthetic data) parsing to the same 5 courses as the text PDF
  - `test_page_limit` now uses syllabus-like pages
  - `student-status.spec.ts`: `uploadProblem` tests
- Not done:
  - photos as JPG or PNG are not accepted (PDF only)
  - OCR'd syllabi aren't treated differently

## Human review
- The human pointed out that these cases should have been worked through before building both uploads. Accepted: edge cases are listed before implementing from now on.
- Security review pending.

## Verification
- `pytest -q backend`: 386 passed. `npm test`: 63 passed.
- OCR: the image-only transcript copy, through Document Intelligence and `parse_transcript_text`, gives the same institution, Student ID and 5 courses as the text PDF. The image-only syllabus copy came back complete with code PSYCH-UA 25.

## Commit
see git log
