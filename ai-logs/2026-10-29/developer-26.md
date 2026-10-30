# developer-26 · Public "Will my course transfer?" check and chat (no login)

| Field | Value |
| --- | --- |
| Date | 2026-10-29 (security-relevant: a public, unauthenticated endpoint that calls the model; needs security review) |
| Agent (role) | developer (backend + frontend) + architect (contract) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | "what about having a chat bot enabled in student page, to get to know about a course credit upfront uploading the transcript", then "without login, coz we use it for equivalency bu course credit only" |

## Prompt (summary or verbatim)
Let anyone, without signing in, ask whether a course from another school will transfer to BU, before uploading a transcript. Edge cases were listed and agreed first.

## Inputs used
- `backend/app/rules.py` (`eligibility`, `lookup`, `convert_units`, `elective_code`), `matcher.recommend`, `guard.py` (`PUBLIC`), `store.visible_decisions`
- `frontend` routing, `role.interceptor.ts`, home and student pages

## Output
- New `backend/app/credit_check.py`, `check_course()`:
  - **applied exactly** (per-course rules): R01 accreditation, R02/R03 course type, R04 one credit, R05 pass/fail, R06 minimum grade, R07 age, R08 quarter conversion, R10/R11 **reusable** past decisions, R13 CS Group C
  - **returned as caveats, not applied** (record-wide rules): R12, R14–R17, R19
  - **never revealed**: holdout decisions and decisions made for one student
  - result kinds: decided_equivalent, decided_elective, not_transferable, pending_review, needs_evaluation, unknown_school, unknown_course
  - needs_evaluation gets a preliminary estimate (R22) from the matcher; a description is filtered for injection
  - a decided result without a grade says "assumes a grade of C or better"
- New `backend/app/credit_chat.py`, `chat()`:
  - Azure OpenAI tool calling with two read-only tools, `check_course` and `list_schools`, and at most 3 lookup rounds per message
  - user messages are filtered for injection; at most 12 messages of 600 characters; nothing is stored
  - **grounding check:** a reply that names a BU code not returned by the tools is replaced by a plain summary of the results
  - **grade fill-in:** if the student states exactly one grade (and at most one course code) and the model leaves it out of `check_course`, the server adds it
  - without Azure OpenAI configured the chat returns 503 and the page falls back to the form
- New `backend/app/ratelimit.py`: 20 requests per minute per IP (first X-Forwarded-For hop), plus a global budget of 300 model calls per hour that a spoofed header can't avoid. When the budget runs out, the check still returns the facts without the estimate.
- `backend/app/main.py`: `GET /api/credit-check/schools`, `POST /api/credit-check`, `POST /api/credit-chat`. `guard.py`: all three are in `PUBLIC` in every sign-in mode; everything else stays protected.
- `docs/api/openapi.yaml`: the three routes (`security: []`), `CreditCheckInput` and `CreditCheckResult`. `tests/test_roles.py` now reads the public set from `guard.PUBLIC`.
- Frontend:
  - new public route `/credit-check` (`CreditCheckPage`: "Ask" chat tab and "Quick check" form)
  - result cards labelled by kind; estimates marked "Preliminary estimate – not a promise of credit"; caveats shown
  - links: "Check a course" in the top bar, a card on the home page, and a line under the student page's "Start here" panel
  - `role.interceptor.ts` treats `/api/credit-check` and `/api/credit-chat` as public, so no Entra token is requested for anonymous visitors
- **Live finding fixed during the run:** "I got a C- in NYU MATH-UA 121. Does it count?" The model called `check_course` without the grade and answered that it transfers as CAS MA 123. That's false credit that the grounding check couldn't catch, because the code came from a real lookup. Fixed with the prompt rule, the server-side grade fill-in, and the "assumes C or better" note. Re-asked, it now answers "not transferable, grade below C".

## Human review
- The human chose public access without login, for equivalency questions only. Conversations are not stored.
- Reviewed by architect-05 and security-04; findings fixed in developer-27.

## Verification
- `pytest -q backend`: 451 passed. New: `test_credit_check.py` (21) and `test_credit_chat.py` (26).
- `npm test`: 68 passed. New: `credit-check.spec.ts` (4). `ng build --configuration production`: OK.
- Live chat, signed out, gpt-4.1-mini, 6 questions:
  - a decided course: correct
  - C- grade: not transferable, correct after the fix
  - an undecided course: "needs evaluation" with the estimate labelled
  - an unknown school: asks for a catalogue school
  - an injection attempt to promise CAS PS 999: ignored, real result given
  - an off-topic poem: politely declined
- Browser, signed out: home card → `/credit-check` → chat and quick check work, no console errors (`.shots/cc-chat.png`, `.shots/cc-form.png`).

## Commit
see git log
