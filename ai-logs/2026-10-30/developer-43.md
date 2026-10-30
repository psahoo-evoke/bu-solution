# developer-43 · Credit chat answers keywords, subjects and general questions

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) acting as developer |
| Human owner | Sagar (spathur) |
| Trigger | User: "Ensure the chatbot can answer queries using single keywords (e.g., syllabus, course, subject), subject-wise/course-wise searches, and full-sentence questions." |

## Prompt (summary)
"Ask in your words" only worked with a school plus a course code. Make it answer single keywords, subject or course searches, and general questions, as well as full sentences.

## Finding (real model, before)
- "syllabus", "course", "subject", "psychology", "calculus", "NYU", "NYU psychology courses", "PSYCH-UA 10", "Do I need a syllabus?", "Which NYU math courses transfer?": every one got "please provide the school and course code", with nothing looked up. The model had no way to search the catalog or answer rule questions.

## Output
- `credit_check.search_courses(store, query, school)`: catalog search by keyword, subject, course code (spaces and dashes optional, exact) or full title of 2+ words ("Calculus I" is not Calculus II). Short forms (calc, stats, psych, econ, bio, cs, math), a school named in the query ("NYU math", "northeastern biology"), every search word must match (code, title, subject, topics), intro level first, at most 8 shown. No search word: the subjects per school. Catalog courses only (`is_catalog`, ADR 0006); fields returned: school, code, title, subject, credits; never `gt_*`.
- `credit_chat`:
  - new read-only tools `search_courses` and `transfer_info` (BU's general rules from `rules.csv`: syllabus, grades, pass/fail, units, quarter conversion, 68-unit cap, age, course types, accreditation, Hub, deadline, process). Rule texts contain no BU codes or promises and pass `grounded()` (tested).
  - prompt rules 7 and 8: search before asking for detail; answer general questions only from `transfer_info`.
  - a search with exactly one match also runs `check_course` for it (with the student's stated grade) in the same round.
  - a first message with no search word ("course", "subject", "NYU") is answered from the catalog with the subject list, without a model call. Follow-up turns always go to the model (context kept).
  - fallback reply when the model's answer fails the grounding check: course checks, else the catalog search, else the rules, else a search of the student's own words; only then "tell me the school and course code".
  - one retry when the connection to Azure OpenAI drops (seen locally: `SSLEOFError`); HTTP errors are not retried.
- The grounding check, limits, signing and injection handling are unchanged.

## Human review
- Pending.

## Verification
- `pytest`: 595 passed (new: keyword/subject/code/title search, upload-only courses and gt_* never returned, subject list without the model, follow-up still uses the model, single match checked with the stated grade, rules answered and grounded, ungrounded replies fall back to search or rules).
- Frontend `ng test`: 89 passed (no frontend change).
- Real model (local API, Azure OpenAI from `.env`): "syllabus", "Do I need a syllabus?", "pass fail", "What about quarter credits?" answered from the rules; "course", "subject", "NYU" list subjects; "psychology", "biology", "economics at NYU", "computer science at Northeastern", "Which NYU math courses transfer to BU?" list matching courses; "PSYCH-UA 10", "Intro to Psychology", "I took Calculus I at NYU and got a B" checked directly; "Will NYU PSYCH-UA 1 transfer?" unchanged. All grounded.

## Commit
See git log (`developer: credit chat answers keywords, subjects and general questions (developer-43)`).
