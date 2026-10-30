# developer-28 · Quick check: a course picker for the chosen school

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (backend + frontend) + architect (contract) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Human (screenshot of the quick check): "can we load all course of respective program?" |

## Prompt (summary)
After choosing a school in the public quick check, offer that school's courses instead of making the student type the code. Edge cases were listed first:
- catalog courses only
- an unlisted course must still work
- changing the school clears the code
- the route goes on the exact public allowlist
- an unknown school returns 404

## Output
- **Backend:**
  - `credit_check.courses()` returns a school's catalog courses (code, title, credits), sorted. Courses known only from a transcript upload are left out (ADR 0006), and no decisions are included.
  - New public route `GET /api/credit-check/courses?school=` (rate-limited; 404 for an unknown school, 422 without `school`), added to `guard.PUBLIC`.
- **Estimates:** a typed-in course with no description is now ranked on its title. The matcher scores the course text, so before this a title alone always gave no candidates.
- **Contract:** `/credit-check/courses` and the `CreditCourse` schema in `openapi.yaml`; the allowlist text and ADR 0006 updated. `test_roles.py` checks the contract and the allowlist still match.
- **Frontend** (`credit-check.ts/.html/.scss`, `api.service.ts`, `models.ts`, `role.interceptor.ts`):
  - The course code field is disabled until a school is chosen, then offers that school's courses ("CODE – title (credits)") as type-ahead suggestions. Free text still works.
  - The placeholder is the school's first course, and a hint shows how many courses there are.
  - The list is loaded once per school per visit; changing the school clears the code.
  - A code that is not in the list shows "What does the course cover?" (title and topics), which is sent as the description so the preliminary estimate has something to compare.

## Human review
- The human asked for it from the screenshot. The "what does it cover" field replaces a title-only field after a live check showed that a title alone gave no possible matches.

## Verification
- `pytest -q backend`: 474 passed. New: the course-picker test (catalog only, sorted, 404/422) and the title-only estimate test.
- `npm test`: 69 passed. New: picker spec (loaded once per school, case-insensitive match, field for unlisted codes, code cleared). `ng build --configuration production`: OK.
- Browser, signed out, real Azure model (`cc_picker.mjs`, shots `.shots/cc-picker*.png`):
  - code disabled before a school is chosen
  - NEU: 95 courses, placeholder BIOL 1107
  - the code is cleared when switching to NYU (96 courses)
  - NYU PSYCH-UA 77 plus topics: "Needs evaluation" with CAS PS 205 (50%), CAS MA 113 and CAS MA 115 as preliminary matches
  - no console errors
