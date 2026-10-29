# developer-11 · "Syllabus needed, please upload" email when Upload syllabus is clicked

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (backend + frontend) + devops (deploy scripts) + architect (contract change) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | Sagar (spathur) |
| Trigger | User: when Upload syllabus is clicked, send an email saying the syllabus is needed, please upload, with CC to two Evoke addresses |

## Decisions (by the human owner, when asked)
- **Recipients:** To `spathur@evoketechnologies.com`, CC `psahoo@evoketechnologies.com`. The email names the student and course. The student's own address is not emailed, because the sample students' addresses are made up on the real bu.edu domain and mail could reach real people.
- **Trigger:** clicking the existing **Upload syllabus** button (the file picker still opens).
- **Mail service:** Azure Communication Services Email. A subscription admin must first register `Microsoft.Communication`; it is `NotRegistered` and the team only has resource-group rights. Until then requests are recorded and reported as not sent.

## Output
- `backend/app/notify.py`: ACS Email via managed identity (`azure-communication-email==1.1.0`). Recipients come from `SYLLABUS_REQUEST_TO` / `SYLLABUS_REQUEST_CC`, the link from `APP_BASE_URL`. It returns `sent` or `not_sent`; a rejection raises (the route returns 502).
- `backend/app/main.py`: `POST /api/students/{student_id}/courses/{ext_id}/syllabus-request`:
  - The course must be on that student's transcript (404 otherwise).
  - Repeat clicks within 15 minutes are not re-sent (`already_requested`).
  - Each request is recorded in the audit log.
  - The email has plain-text and HTML parts (HTML-escaped).
- `backend/app/guard.py` + `docs/api/openapi.yaml`: the new route with x-roles `[Student, CreditStaff, Evaluator, Department]` (same as uploading a syllabus), and a new `SyllabusRequest` schema. In portal mode the student-own-record rule applies.
- Frontend:
  - `student-status`: the Upload syllabus input calls the request on click. The page then shows "emailed to … cc …", "already emailed in the last 15 minutes", or "recorded. Email is not set up yet, so no email was sent."
  - `api.service.ts` and `models.ts`: the new call and type.
- `scripts/deploy_aca.sh`: `NOTIFY_TO` / `NOTIFY_CC` → API env, plus `APP_BASE_URL` = web URL.
- `scripts/setup_email.sh` (new; **not run yet**, it needs the provider registration): ACS + Email service + Azure-managed domain + link + role for the API identity + env vars.
- `infra/README.md`: env table rows.
- Tests:
  - `tests/test_notify.py`: 8 tests (not_sent recorded; sent only to the notification list with the right subject, link and escaping; 15-minute dedupe; send failure 502 then retry; failed status 502; course not on transcript 404; Registrar/Advisor 403; portal student blocked on another student's course).
  - Frontend message tests: 3.

## Verification
- `pytest -q`: 362 passed. `ng test`: 52 passed. `ng build`: OK. Playwright e2e (local): 7 passed.
- Local API call: `not_sent` (no service or recipients configured locally).

## Commit
see git log
