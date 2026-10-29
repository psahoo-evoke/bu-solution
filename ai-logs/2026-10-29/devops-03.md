# devops-03 · Containerised frontend + lean Azure Container Apps deployment

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | devops |
| Tool / model | Claude Code (Opus 5.5) acting as devops |
| Human owner | Sagar (spathur) |
| Trigger | User: "I need to deploy to Azure, create Dockerfile, structure to deploy in Azure in container" |

## Prompt (summary)
Make both frontend and backend deployable to Azure as containers.

## Inputs used
- `backend/Dockerfile`, `.dockerignore`, `infra/main.bicep`, `infra/README.md`, `.github/workflows/deploy.yml`
- `frontend/angular.json`, `frontend/public/staticwebapp.config.json`, `frontend/src/app/api/api.service.ts` (`API_BASE = '/api'`)
- `backend/app/guard.py` (10 MB upload limit), `backend/app/store.py` (in-memory store)

## Output
- `frontend/Dockerfile`, `frontend/nginx/default.conf.template`, `frontend/.dockerignore`: multi-stage Node 22 build, then non-root nginx on :8080. Serves the SPA with the same fallback and security headers as `staticwebapp.config.json`, and proxies `/api/` to `API_UPSTREAM`, which is read at start via envsubst.
- `docker-compose.yml`: local run of both images (web :8080, api :8000).
- `scripts/deploy_aca.sh`: idempotent az CLI deploy. Creates the RG, ACR Basic (admin off), a user-assigned identity with AcrPull, and the Container Apps environment. Builds both images with `az acr build` and creates or updates `ca-<prefix>-api` (internal ingress, 1 replica) and `ca-<prefix>-web` (external ingress, 1–3 replicas), then runs a smoke test on `/api/health`.
- `.github/workflows/deploy-containers.yml`: manual (workflow_dispatch) OIDC workflow that runs the script.
- `infra/README.md`: "Two ways to deploy" section.
- Decisions:
  - The API is internal-only and reached same-origin through nginx, so no CORS is needed.
  - The API runs with max 1 replica because the store is in memory.
  - The images are built in ACR because there is no local Docker.
  - The existing Bicep/SWA path is left unchanged.

## Human review
- Pending.

## Verification
- `bash -n scripts/deploy_aca.sh`: OK.
- `npx ng build --configuration production`: output in `dist/transferiq-web/browser/`, as the Dockerfile expects.
- Deployed to RG `AI-F-TheSolutionauts`, reusing environment `managedEnvironment-AIFTheSolutiona-96c4`, ACR `acrsolutionauts95de2` and the placeholder app `bu-solutions` (now the web app), plus a new internal app `bu-solutions-api`.
- Script fixes from the first deploy runs on Windows / Git Bash with RG-only rights:
  1. Skip registering providers that are already registered (registering needs subscription rights).
  2. Check the AcrPull assignment by principalId, which avoids a Graph lookup of a just-created identity.
  3. Pass relative paths to `az acr build` (the Windows az CLI cannot read `/c/...` paths).
  4. Use `az acr build --no-logs` plus a status check (the Windows az CLI crashes printing Unicode build logs).
- `docker build` was not run locally (no Docker); the images are built by ACR.

## Commit
not committed yet
