# devops-01 · Dockerfile, Azure Bicep, CI and OIDC deploy workflows

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | devops |
| Tool / model | Solutionauts AI subagent acting as devops |
| Human owner | Tech lead |
| Trigger | Orchestrator: "DevOps agent: Dockerfile, Bicep for all Azure services, ci.yml with log-check, deploy.yml with OIDC, infra README" |

## Prompt (summary)
Build the API container image (build context = repo root, non-root, include synthetic seed/syllabi/transcripts), Bicep for Log Analytics + App Insights, Key Vault (RBAC), Storage (transcripts, syllabi), PostgreSQL Flexible (Entra auth, burstable), Container Apps (system MI, min 1 replica), Static Web App, Azure OpenAI (parameterised model), AI Search basic, Document Intelligence, Communication Services email, ACR, role assignments, tags `project`/`env`; CI (backend tests + eval, frontend build, AI-log check); deploy via OIDC; infra README with cost note. Do not touch `backend/app`, `backend/tests`, `frontend/src`.

## Inputs used
- `AGENTS.md`, `agents/devops.md`, `docs/architecture.md`, ADRs 0001–0004, `docs/api/openapi.yaml`, `docs/discovery/sponsor-answers.md`
- Read-only look at the in-progress `backend/requirements.txt` and `backend/app/*.py` to align env var names

## Output
- `backend/Dockerfile`, `.dockerignore` (allow-list)
- `infra/main.bicep`, `infra/main.bicepparam`, `infra/modules/{monitoring,keyvault,kv-secret,storage,registry,postgres,postgres-admin,ai,communication,containerapps-env,containerapp-api,roles,staticwebapp,staticwebapp-backend}.bicep`
- `infra/README.md` (prerequisites, deploy order, OIDC setup, env var contract, parameters to fill, cost ≈ $130–170/month, gaps)
- `.github/workflows/ci.yml` (backend, frontend, infra bicep build, log-check), `.github/workflows/deploy.yml`
- `scripts/check_ai_logs.sh` (AI-log rule used by CI)

Key decisions:
- **Two-phase deploy** of the same template (`deployApi=false` then `true` + `apiImage`), because ACR is created by the template and the app needs the image to exist first.
- **Two identities on the container app:** system-assigned for data plane (as asked); user-assigned for ACR pull and Key Vault references so their roles exist before the first revision (avoids the role race).
- Key auth disabled on OpenAI, Doc Intelligence, Search and Storage. Only the App Insights and ACS connection strings exist, and both are stored in Key Vault.
- OpenAI model name/version are **required params with no default** in `main.bicep`. The bicepparam has placeholders (`gpt-4o-mini` / `2024-07-18`, GlobalStandard) that the team must verify. `deployOpenAi=false` gives offline fallback (the env var is then absent, per ADR 0003).
- SWA Standard + linked backend so the SPA uses relative `/api`. The SWA deploy token is fetched at run time, never stored.
- Env var names aligned with the backend snapshot (`AZURE_DI_ENDPOINT`, `TRANSFERIQ_SEED_DIR`).

## Human review
- Pending review by the tech lead. Open decisions: OpenAI model/region/quota, SWA Standard vs Free, AI Search Basic (~$75/month) vs free tier.

## Verification
- **Bicep compiled:** Bicep CLI 0.48.1 (downloaded linux-x64 release) `bicep build infra/main.bicep` and `build-params infra/main.bicepparam` both pass with 0 errors and 0 warnings after fixes (a for-expression inside `concat`, an invalid ACR property, null-safety on conditional modules). `bicep lint` is clean. **Not deployed** to any subscription (no Azure credentials in the sandbox), so `what-if` was not run and region/quota/model availability is unverified.
- **Workflows:** YAML parsed; `actionlint` 1.7.7 reports no issues for `ci.yml` and `deploy.yml`. Not executed on GitHub.
- **Log-check script:** tested in a throwaway git repo with 4 cases: code without a log fails, code plus a log in the range passes, docs only passes, and all-zero base with a code-only head commit fails.
- **Docker:** a full image build was **not possible** (Docker Hub blocked by the sandbox proxy, so `python:3.12-slim` could not be pulled). Verified instead: (a) the `.dockerignore` allow-list via a `FROM scratch` build that copies the context. Only `backend/` (no tests, `__pycache__`, `.env`), `data/synthetic/{seed,syllabi,transcripts}` are sent. (b) The backend snapshot started with uvicorn from the image's `/app/backend` + `/app/data` layout in a venv, and `GET /api/health` returned 200.

## Commit
see git log
