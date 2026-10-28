# Security review checklist (backend)

The Security agent runs this against `backend/` once the developer marks the API feature-complete. Record results in `docs/security/review-<date>.md` (pass / fail / n.a. plus evidence) and log the run in `ai-logs/`.

Run the API locally first: `cd backend && uvicorn app.main:app --port 8000`.

## 1. Role matrix (from `docs/api/openapi.yaml`)

✔ = allowed, ✖ = must return **403**. "own" = allowed only for the student's own record (production; the demo header carries no identity). Cells marked * are **proposed**: openapi.yaml doesn't define them, so the architect must confirm.

| Route | Student | CreditStaff | Evaluator | Department | Registrar | Advisor | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET /health` | no auth | | | | | | openapi (`security: []`) |
| `GET /students` | ✖* | ✔ | ✔ | ✔ | ✔ | ✔ | * |
| `GET /students/{id}/evaluation` | own* | ✔ | ✔ | ✔ | ✔ | ✔ | * |
| `POST /students/{id}/transcripts` | own* | ✔ | ✖* | ✖* | ✖* | ✖* | * |
| `POST /courses/{ext_id}/syllabus` | ✔* | ✔ | ✔* | ✔* | ✖* | ✖* | * |
| `GET /courses/{ext_id}/recommendation` | ✖* | ✔* | ✔ | ✔ | ✖* | ✖* | * |
| `GET /review-queue` | ✖* | ✔* | ✔ | ✔ | ✖* | ✖* | * |
| `POST /decisions` | ✖ | ✖ | ✔ | ✔ | ✖ | ✖ | openapi ("Evaluator or Department role") |
| `POST /decisions/batch` | ✖ | ✖ | ✔ | ✔* | ✖ | ✖ | * (backend snapshot: Evaluator only) |
| `GET /exports/mybu.csv` | ✖ | ✖ (openapi) | ✖ | ✖ | ✔ | ✖ | openapi ("Registrar role"); backend snapshot also allows CreditStaff, so the architect must decide |
| `GET /evaluation/metrics` | ✔* | ✔ | ✔ | ✔ | ✔ | ✔ | * (no PII) |
| `GET /rules` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | * (public rules) |
| `POST /demo/reset` | ✖* | ✔* | ✖* | ✖* | ✖* | ✖* | *; must be disabled when `TRANSFERIQ_AUTH_MODE=entra` |

Checks:
- [ ] Missing or unknown `X-Demo-Role` returns 401/403 on every route except `/health` (default deny). Test: `curl -s -o /dev/null -w '%{http_code}' localhost:8000/api/students` (2026-10-28 snapshot returned **200**, which needs fixing).
- [ ] Every ✖ cell returns 403 (script: loop over roles × routes; add as `backend/tests/test_roles.py` with QA).
- [ ] Role check happens before any side effect (no partial writes on 403).
- [ ] Decisions record the actor role (and user in Entra mode) in the audit log.
- [ ] Entra mode (if built): token signature, issuer, audience and expiry are validated, and roles are taken from the `roles` claim only.

## 2. File uploads (`/students/{id}/transcripts`, `/courses/{ext_id}/syllabus`)

- [ ] Max size enforced **before** reading the whole body into memory (target ≤ 10 MB) → 413.
- [ ] Type check: `%PDF-` magic bytes, not only the `Content-Type` or file extension, → 415/422.
- [ ] Page limit (≤ 30) and parse time-out. Encrypted or malformed PDFs fail cleanly with 422, never 500 with a stack trace.
- [ ] Stored blob name is server-generated (UUID), never the client filename (path traversal).
- [ ] `ext_id` / `student_id` path params validated (pattern, length) before use in blob paths or queries.
- [ ] Note the production option: Defender for Storage malware scanning.

## 3. Prompt injection (ADR 0004)

- [ ] T17 passes offline: NYU ECON-UA 266 → `injection_detected=true`, tier stays `evaluator_decides` (~62 % vs CAS EC 204).
- [ ] Syllabus text goes only inside the delimited data block, and the system prompt states that it contains no instructions.
- [ ] LLM output is parsed as JSON and validated: overlap clamped 0–100, tier from enum, BU code ∈ search candidates; anything else falls back.
- [ ] No code path lets LLM output create a decision or units.

## 4. PII / FERPA and logging

- [ ] Prompt payload contains course fields only. Add a test asserting no `SYN-\d+`, student name, grade or `gt_` key appears in the prompt.
- [ ] Logs and App Insights traces contain no student names, transcript text or syllabus text. IDs are OK because they are synthetic.
- [ ] Error responses are generic (no stack traces, no SQL, no file paths); `debug` is off in the container.
- [ ] `gt_*` columns are never returned by any API route.

## 5. Data access

- [ ] Only parameterised SQL / ORM, with no f-string SQL.
- [ ] The CSV export escapes cells starting with `= + - @` (CSV/formula injection in Excel).
- [ ] The audit log is append-only (no update/delete route).

## 6. HTTP hardening

- [ ] CORS: origins come from `TRANSFERIQ_CORS_ORIGINS` (not `*`, not hard-coded). 2026-10-28 snapshot: hard-coded `http://localhost:4200` with `allow_credentials=True`. That is fine locally, and the SWA linked backend is same-origin, but read the env var.
- [ ] Response headers: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` on student data; HSTS is provided by Container Apps/SWA HTTPS.
- [ ] SPA: CSP and `X-Frame-Options: DENY` in `frontend/staticwebapp.config.json`; no `innerHTML` / `bypassSecurityTrust*` with syllabus or LLM text.
- [ ] OpenAPI docs (`/docs`) are acceptable for the demo, but disable them in `entra` mode.

## 7. Secrets and supply chain

- [ ] `grep -rEi "(api[_-]?key|password|secret|connectionstring)\s*=" backend frontend/src` finds no literals.
- [ ] Azure clients use `DefaultAzureCredential`, with no `AZURE_OPENAI_API_KEY` / `AZURE_DI_KEY` in the cloud (key auth is disabled in infra).
- [ ] `pip-audit -r backend/requirements.txt` and `npm audit --omit=dev` (in `frontend/`) show no high/critical issues.
- [ ] Dependabot is enabled. Consider pinning `requirements.txt` to exact versions (it currently uses `>=`).
