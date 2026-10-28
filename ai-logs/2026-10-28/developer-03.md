# developer-03 · Backend hardening for contract v0.2.0: default-deny roles, reason codes, managed identity, upload limits, LLM output validation

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | developer |
| Tool / model | Claude subagent (general-purpose) acting as developer |
| Human owner | Backend + AI dev |
| Trigger | Coordinator: implement contract v0.2.0 (`x-roles`, `GET /reason-codes`), ADR 0005, and the security-01 checklist items in `backend/` |

## Prompt (summary)
1. Default deny: every route except /health needs a valid `X-Demo-Role` (missing/unknown → 401, not in `x-roles` → 403), checked before any side effect, with the actor role recorded in the audit log.
2. Add `GET /api/reason-codes`.
3. Use `DefaultAzureCredential` for Azure OpenAI and Document Intelligence, with keys only as a local-dev fallback and no azure imports at module load.
4. CORS origins from `TRANSFERIQ_CORS_ORIGINS`.
5. Upload hardening: 10 MB → 413, `%PDF-` → 415, 30 pages, malformed → 422, id patterns.
6. Validate LLM output.
7. Redefine the eval headline. Do not commit.

## Inputs used
- `docs/api/openapi.yaml` v0.2.0, `docs/adr/0005-role-matrix-default-deny.md`, `docs/security/checklist.md`, `docs/security/threat-model.md`, `infra/main.bicep` (backend env-var contract)

## Output
- **New `backend/app/guard.py`:** `RoleGuardMiddleware`, a pure ASGI middleware, so the role check and Content-Length check run before the body is read or any handler runs.
  - Its `ROUTE_ROLES` table mirrors `x-roles`, and a test asserts the two are identical.
  - Uploads: a declared Content-Length over 10 MB + 64 KB multipart slack → 413; chunked bodies are counted while streaming → 413.
  - Adds `nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` to every `/api` response.
  - `TRANSFERIQ_AUTH_MODE=entra` fails closed (401) because JWT validation is not built yet.
- **`backend/app/main.py`:**
  - Guard middleware, with CORS outermost so 401/403 responses carry CORS headers. CORS origins come from `TRANSFERIQ_CORS_ORIGINS` (default `http://localhost:4200`, `*` dropped), and allowed methods/headers are narrowed.
  - `GET /api/reason-codes`.
  - Path/query/body validation: `student_id` `^[A-Za-z0-9][A-Za-z0-9-]{0,31}$`, `ext_id` `^[A-Z]{2,8}\|[A-Za-z0-9][A-Za-z0-9 .&-]{0,31}$`, length limits on evaluator, note and batch size.
  - Upload size/magic re-check in the handler, and generic 422 messages (no exception text).
  - CSV formula-injection escaping on export. `/demo/reset` disabled in entra mode. `/docs` and `/openapi.json` off in entra mode.
  - The handlers' own `require_role` was removed; the guard is the single enforcement point. Batch is now Evaluator + Department per ADR 0005.
- **`backend/app/ingest.py`:**
  - `check_pdf_bytes` (magic → 415). `pdf_text` enforces the 30-page limit and turns any pdfplumber failure into `UploadError(422)`.
  - Document Intelligence is now a real REST adapter (prebuilt-layout 2024-11-30) using a bearer token from a lazily created `DefaultAzureCredential` (scope `https://cognitiveservices.azure.com/.default`), with `AZURE_DI_KEY` only as a local-dev fallback.
  - DI is used only when pdfplumber finds no text (a scan). This matters because infra sets `AZURE_DI_ENDPOINT` in the cloud: with revision 1's stub, every upload there would have failed.
- **`backend/app/matcher.py`:**
  - `_openai_auth_headers()` uses `azure.identity.get_bearer_token_provider(DefaultAzureCredential, cognitive scope)`, imported lazily, with `AZURE_OPENAI_API_KEY` only as a local-dev fallback.
  - Pure `build_prompt()` and a swappable `llm_client`.
  - `validate_llm_output()`: strict JSON, non-empty candidates, every `bu_code` among the search shortlist, overlap must be numeric (bools rejected) and is clamped 0–100, model `tier` must be in the enum and is then recomputed in code (R20), covered outcomes filtered to verbatim BU outcomes. Any violation raises `LLMOutputError` and the engine falls back to offline.
- **`backend/app/evaluation.py`, `backend/eval/run_eval.py`:** the three metrics (a) top-1 candidate agreement [gate], (b) strict decision agreement, (c) wrongly suggested credit [gate], with deferrals inside (a) counted separately. Exit 1 only if (c) > 2 % or (a) < 80 %.
- **`backend/requirements.txt`:** + `azure-identity`, + `pyyaml` (test_roles reads the contract).

## Notes for other roles
- **Frontend (developer-02):**
  - Every `/api` call now needs `X-Demo-Role`.
  - Student and Advisor get 403 on `/review-queue` and `/courses/{ext_id}/recommendation`, and Student/Advisor/Evaluator/Department get 403 on the export.
  - `/reason-codes` is available to replace hard-coded codes. Not checked or changed here (out of scope).
- **Security:**
  - Checklist items addressed: 1 (all), 2 (size, magic, pages, malformed, id patterns; blob names n/a because nothing is stored to Blob yet), 3 (validation), 4 (prompt PII test), 5 (CSV escaping), 6 (CORS env, headers, docs off in entra), 7 (DefaultAzureCredential).
  - Not done: a parse timeout on pdfplumber (only the page limit bounds it), pinned requirement versions, and Entra JWT validation (entra mode fails closed instead).

## Human review
- Pending review by the Backend + AI dev.

## Verification
- `pytest -q` from `backend/`: **268 passed**, 0 failed (see qa-02).
- uvicorn smoke test:
  - `/api/health` 200; `/api/students` without header 401, as Student 200.
  - `/api/review-queue` as Student 403; `/api/reason-codes` as Advisor 200.
  - CORS preflight from `http://localhost:4200` allowed.
  - A 1.1 MB non-PDF upload → 415.
- `python eval/run_eval.py` → exit 0.

## Commit
see git log
