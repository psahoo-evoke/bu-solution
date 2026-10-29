# security-02 · Backend security review against the checklist

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | security |
| Tool / model | Solutionauts AI subagent acting as security |
| Human owner | Tech lead |
| Trigger | Orchestrator: "run docs/security/checklist.md against the current backend; report findings, don't edit backend/app or tests" |

## Prompt (summary)
Start the API locally from `backend/`, run every checklist item with curl/pytest, and write `docs/security/review-2026-10-28.md` (pass / fail / N/A + evidence). Re-check the infra env var names against the backend (DevOps part logged as devops-02).

## Inputs used
- `docs/security/checklist.md`, `docs/security/threat-model.md`, `docs/api/openapi.yaml` v0.2.0 (`x-roles`), ADR 0004, ADR 0005
- `backend/app/{main,guard,safety,matcher,ingest,store}.py` and `backend/tests/*` at `6a5e056`, `frontend/src` (grep only)
- Synthetic PDFs in `data/synthetic/syllabi` and `data/synthetic/transcripts`

## Output
- `docs/security/review-2026-10-28.md`: 30 items, **24 pass, 3 fail, 3 N/A**. Findings: 2 medium (F-01 no `staticwebapp.config.json`, so no CSP and no SPA fallback; F-02 `bu_course` / decision–reason consistency not validated), 5 low (F-03 demo header auth, an accepted risk; F-04 no PDF parse time-out; F-05 audit log in memory and cleared by reset; F-06 client filename stored as metadata; F-07 unpinned pip requirements) and 2 info.
- `docs/security/threat-model.md`: marked the key-auth open item resolved and noted that CORS is API-only.
- Fixed the security-01 findings verified here: default deny (no role → 401), export roles per ADR 0005, managed identity in matcher/ingest, CORS from env.

## Human review
- Pending. The tech lead decides on accepting F-03 and assigns F-01/F-02 to the developer.

## Verification
- `pytest -q` in `backend/`: 268 passed (Python 3.13 venv in the sandbox; the image uses 3.12).
- Live probe (uvicorn on localhost):
  - Role matrix from openapi `x-roles`: 117 requests, 0 mismatches.
  - Path-normalisation bypass attempts: none succeeded.
  - Uploads: 11 MB (with Content-Length and chunked) → 413, non-PDF → 415, malformed → 422, 40 pages → 422.
  - T17 live: 62 %, `evaluator_decides`, injection flagged, batch → 422.
  - Other checks: CORS with a custom env list, security headers on 200/401/CSV, entra mode fail-closed with docs hidden, CSV formula escaping, no `gt_` in 8 GET routes.
- `pip-audit` reported no known vulnerabilities and `npm audit` found 0.
- Not verified: anything in Azure (nothing deployed), the real Azure OpenAI engine, a dynamic SPA scan.

## Commit
see git log
