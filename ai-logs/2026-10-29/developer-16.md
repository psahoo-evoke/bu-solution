# developer-16 · Student contact fields and the bu_school = NULL fix (ported from bu-solutions)

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (with the synthetic-data output from bu-solutions) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Same port as developer-15. During the run the human added: "dont add new student colums in html" |

## Prompt (summary or verbatim)
Bring the student contact fields (`email`, `phone`, `address`, `previous_school`) from bu-solutions into this repo, without showing them on the student page.

## Inputs used
- `bu-solutions/bu-solution` logs: `ai-logs/2026-10-29/developer-02.md`, `synthetic-data-01.md`, `synthetic-data-02.md`
- `backend/app/store.py`, `db.py`, `main.py`; `backend/db/schema.sql`; `data/synthetic/seed/students.csv`

## Output
- Applied from bu-solutions without changes:
  - the generator scripts: `scripts/synthetic/build_data_v2.py`, `build_outputs.py`
  - the regenerated seed data: `students.csv`, `transferiq_seed.json`, `TransferIQ_Synthetic_Data.xlsx`
  - the docs: `docs/api/openapi.yaml` (`Student` schema) and `docs/data-model.md`
  - the type file `frontend/src/app/api/models.ts`
  - `backend/tests/test_api.py`
- The fields are fictional by construction: `example.edu` addresses, 555-01xx phone numbers and invented streets. `previous_school` is the school of the student's most recent non-summer term.
- `backend/app/store.py`:
  - `Student` gains `bu_school`, `email`, `phone`, `address` and `previous_school`, all defaulting to `""`.
  - `to_api(schools)` also returns `previous_school_name`.
- `backend/app/main.py`: `/students` and `/students/{id}/evaluation` pass the schools to `to_api`.
- `backend/app/db.py`: a single `STUDENT_COLS` list now drives the students SELECT, the seed INSERT and the registration INSERT.
  - This fixes the same bug bu-solutions had: `bu_school` was never written, so PostgreSQL stored NULL.
  - The seed INSERT now updates the profile columns of seed students that already exist, so the live database picks up the contact data.
- `backend/db/schema.sql`: the comment on the contact columns now says they are served by the API and never sent to the AI. The columns already existed in the live database.
- **Rejected by the human:** the profile block on the student page (`student-status.html`, its spec assertions and `.student-profile` CSS). It was removed, and the API still returns the fields.
- The fields are personal data and are never put in a prompt. `test_llm.py::test_prompt_contains_course_data_only` checks this.

## Human review
- The human rejected showing the fields on the student page ("dont add new student colums in html").
- Still open from bu-solutions:
  - architect review of the additive `Student` schema change in `openapi.yaml`
  - sign-off on the "most recent non-summer term" rule for `previous_school`

## Verification
- `pytest -q backend`: 373 passed. `npm test`: 56 passed.
- Live: after `/api/demo/reset`, `GET /api/students` returned `bu_school`, `email`, `phone`, `previous_school` and `previous_school_name` for SYN-24001 to SYN-24004 from PostgreSQL.

## Commit
see git log
