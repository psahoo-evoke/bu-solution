# Data model

Schema: `backend/db/schema.sql` (the single source). PostgreSQL is optional: with `POSTGRES_HOST` set, `backend/app/db.py`
runs the schema at startup (idempotent), seeds empty tables from `data/synthetic/seed/`, loads the in-memory Store from
the tables and writes every runtime change through to them. `POST /api/demo/reset` truncates and reseeds. Without
`POSTGRES_HOST` the app runs from the CSVs in memory only.

| Table | Key | Main columns | Seed file |
| --- | --- | --- | --- |
| bu_courses | bu_code | title, program, requirement_type, level, credits, residency_rule, description, learning_outcomes[], topics[] | bu_courses.csv |
| schools | school_code | name, calendar, accreditation, role | schools.csv |
| external_courses | ext_id (`SCHOOL|CODE`) | title, credits, calendar, course_type, level, source, description, outcomes[], topics[], elective_code. No gt_* columns | external_courses.csv (+ courses first seen on an uploaded transcript) |
| external_courses_gt | ext_id | gt_counterpart, gt_overlap, gt_tier (eval only, never read by the matcher) | external_courses.csv gt_* columns |
| decisions | decision_id | ext_id, decision, bu_course, units_awarded, reason_code, reusable, split, catalog_year, decided_by, decision_date, ai_suggestion, ai_agreed, note, overlap_pct | past_decisions.csv + runtime (`split = runtime`) |
| decision_scope | (decision_id, student_id) | students a non-reusable runtime decision applies to | (runtime) |
| equivalency_table (view) | | decisions without holdout; the app reads decisions only through it | |
| students | student_id | name, intended_major, bu_school, bu_start_term, email, phone, address, previous_school (FK schools; school of the most recent regular, non-summer term) | students.csv |
| transcript_lines | (student_id, ext_id, term) | seq (transcript order), school_code, course_code, title, grade, credits, calendar | transcript_lines_expected.csv (input columns only) + uploads |
| syllabi | ext_id | state, injection_detected, source_file, seed_state, extracted_text (untrusted, ADR 0004), received_at, blob_url (unused until Blob Storage) | syllabi_index.csv + uploads |
| audit_log | id | actor_role, action, ext_id, before, after, at | (runtime) |
| postings | (student_id, ext_id, term) | decision_id, posted_at, actor_role | (runtime, POST /postings) |

`split = holdout` decisions are hidden from the app (they are not in `equivalency_table`) and are read separately, only by the evaluation.

Rules and reason codes are configuration and stay in `rules.csv` / `reason_codes.csv`; they are not in the database.

Student contact fields (`email`, `phone`, `address`, `previous_school`) are personal data. They are returned in the
`Student` object of `GET /students` and `GET /students/{id}/evaluation` (with `previous_school_name`), are never sent to an
AI service (the matcher only receives course data; `tests/test_llm.py` checks every prompt) and are not written to the
audit log. Seed values are fictional: example.edu emails (RFC 2606), 555-0100..0199 phone numbers, invented streets.
`address` is one text field. `previous_school` is the school of the most recent regular (non-summer) term; summer-only stints do not count. The full history is in `transcript_lines`.
Databases created before these columns existed get them from the `ALTER TABLE students ADD COLUMN IF NOT EXISTS`
statements in `schema.sql`; run `POST /api/demo/reset` to fill them.
