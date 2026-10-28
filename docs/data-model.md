# Data model

| Table | Key | Main columns | Seed file |
| --- | --- | --- | --- |
| bu_courses | bu_code | title, program, requirement_type, level, credits, residency_rule, description, learning_outcomes[], topics[] | bu_courses.csv |
| schools | school_code | name, calendar, accreditation, role | schools.csv |
| external_courses | ext_id (`SCHOOL|CODE`) | title, credits, calendar, course_type, level, source, description, outcomes[], topics[]; gt_* (eval only) | external_courses.csv |
| decisions | decision_id | ext_id, decision, bu_course, units_awarded, reason_code, reusable, split, catalog_year, decided_by, decision_date | past_decisions.csv |
| students | student_id | name, intended_major, bu_start_term | students.csv |
| transcript_lines | (student_id, ext_id, term) | grade, credits, calendar | transcript_lines_expected.csv |
| syllabi | ext_id | state (complete / incomplete / missing / complete-injection), file | syllabi_index.csv |
| audit_log | id | actor_role, action, ext_id, before, after, at | (runtime) |

`split = holdout` decisions are hidden from the app and used only by the evaluation.
