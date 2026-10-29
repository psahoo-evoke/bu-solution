# security-01 · STRIDE threat model, Dependabot and backend review checklist

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | security |
| Tool / model | Solutionauts AI subagent acting as security |
| Human owner | Tech lead |
| Trigger | Orchestrator: "Security agent: threat model, dependabot, checklist to run against the backend" |

## Prompt (summary)
STRIDE per component (SPA, API, matcher/LLM, storage, DB, CI/CD) with mitigations mapped to code/infra: role checks per route, prompt injection (ADR 0004, T17), PII/FERPA posture, upload risks, audit log, Key Vault + managed identity, supply chain. Add Dependabot (pip, npm, actions) and a checklist to run once the backend exists.

## Inputs used
- `AGENTS.md`, `agents/security.md`, ADRs 0001–0004, `docs/api/openapi.yaml`, `docs/data-model.md`, `docs/discovery/sponsor-answers.md`, `data/synthetic/seed/test_cases.csv` (T17), `syllabi_index.csv`
- The infra produced in devops-01 (to map mitigations to Bicep)
- Read-only skim of the in-progress `backend/app/main.py`, `matcher.py`, `ingest.py`

## Output
- `docs/security/threat-model.md`: data classification, FERPA posture (synthetic only, no names/IDs/`gt_*` to the LLM; production needs a school-official agreement + data in the BU tenant), STRIDE tables for 6 components, secrets/identity summary, accepted residual risks
- `docs/security/checklist.md`: route × role matrix from openapi.yaml (cells openapi doesn't define are marked proposed), upload limits, injection, PII/logging, data access, CORS/headers, secrets/supply chain
- `.github/dependabot.yml`: pip (`/backend`), npm (`/frontend`), github-actions, docker (`/backend`), all weekly and grouped

## Early observations (backend snapshot 2026-10-28; not a formal review)
- `GET /api/students` with no `X-Demo-Role` returned 200. Only `/decisions`, `/decisions/batch` and `/exports/mybu.csv` call `require_role`, so default deny is missing.
- Export allows `CreditStaff` but openapi says Registrar, so the architect must decide.
- `matcher.py` uses an `api-key` header and `ingest.py` reads `AZURE_DI_KEY`, but infra disables key auth. The backend must move to `DefaultAzureCredential`.
- CORS is hard-coded to `http://localhost:4200`. It should read `TRANSFERIQ_CORS_ORIGINS`.
- The matcher prompt already wraps course data in `<course_data>` with an "untrusted data" instruction (ADR 0004). Good.

## Human review
- Pending. The architect must confirm the proposed role-matrix cells (marked *).

## Verification
- `dependabot.yml` parsed as YAML. The threat-model mitigations were cross-checked against the Bicep properties (`disableLocalAuth`, `allowSharedKeyAccess: false`, `passwordAuth: Disabled`, RBAC Key Vault).
- The checklist has **not** been run yet (the backend is still being built). The next security run writes `docs/security/review-<date>.md`.

## Commit
see git log
