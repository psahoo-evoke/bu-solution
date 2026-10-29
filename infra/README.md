# TransferIQ infrastructure (Azure, Bicep)

Owner: DevOps agent · Human owner: Tech lead

Everything is in `infra/main.bicep` (resource-group scope) with one module per concern in `infra/modules/`.
Parameters live in `infra/main.bicepparam`.

## Two ways to deploy

| | Containers only (`scripts/deploy_aca.sh`) | Full platform (`infra/main.bicep`) |
| --- | --- | --- |
| Frontend | Container App `ca-<prefix>-web` (nginx + SPA, `frontend/Dockerfile`) | Static Web App |
| Backend | Container App `ca-<prefix>-api`, **internal** ingress, 1 replica | Container App, external ingress |
| Other resources | ACR Basic, Container Apps environment (+ its Log Analytics), one AcrPull identity | Postgres, OpenAI, Search, Doc Intelligence, Key Vault, Storage, ACS, App Insights |
| AI | offline matcher (ADR 0003) | Azure OpenAI when `deployOpenAi = true` |
| Cost | ≈ 30–60 USD/month | ≈ 130–170 USD/month |
| How | `az login` then `scripts/deploy_aca.sh`, or the `deploy-containers` workflow (manual) | `deploy.yml` or the steps below |

Use the containers-only path for the demo. The backend keeps all state in memory today, so the services the full platform creates would sit idle.

### Containers only

```
Internet --HTTPS--> ca-tiq-web  (nginx :8080, serves the SPA, proxies /api/* -> API_UPSTREAM)
                        |
                        v
                    ca-tiq-api  (FastAPI :8000, internal ingress, not reachable from the internet)
```

```bash
az login
az account set -s <subscription>
scripts/deploy_aca.sh                                   # defaults: RG=rg-transferiq-aca LOCATION=eastus2 PREFIX=tiq
RG=rg-tiq-test LOCATION=westeurope scripts/deploy_aca.sh   # overrides
```

- Runs in Git Bash, WSL, macOS/Linux or Azure Cloud Shell. Images are built with `az acr build`, so you don't need Docker locally.
- Re-running is safe: it builds new image tags and rolls both apps to a new revision.
- The web image reads `API_UPSTREAM` at container start, so the same image works with `docker compose` (`http://api:8000`) and in Azure (`https://<api internal fqdn>`).
- The API runs with **exactly one replica**, because `backend/app/store.py` is in memory and every restart re-seeds it. Don't raise `--max-replicas` until the store moves to Postgres.
- **Upload archive:** add `STORAGE_ACCOUNT=<existing account>` (and `STORAGE_RG` if it's in another resource group). The script then:
  - creates the `transcripts` and `syllabi` containers if they're missing (private)
  - turns on the API's system-assigned identity
  - grants that identity **Storage Blob Data Contributor** on those two containers only
  - sets the `AZURE_STORAGE_*` variables

  The API then stores every uploaded transcript and syllabus PDF in Blob Storage.
- Locally with Docker: `docker compose up --build` gives http://localhost:8080.

### Entra ID sign-in (roles from Microsoft Entra)

Run the deploy script with `ENTRA_CLIENT_ID=<application (client) id> ENTRA_TENANT_ID=<directory (tenant) id>`. These are ids, not secrets; no client secret is used anywhere.
- **API:** `TRANSFERIQ_AUTH_MODE=entra`. Every `/api` call except `/api/health` needs a valid Entra access token. The caller's roles come from the token's `roles` claim, and `X-Demo-Role` can only choose among those roles.
- **Web:** `AUTH_MODE=entra`. The SPA reads `/auth-config.json` and shows "Sign in with Microsoft". The role dropdown lists only the roles the signed-in user is assigned.

The app registration (one registration for the SPA and the API) needs:
1. **Authentication → Single-page application** redirect URIs: the web app URL (for example `https://bu-solutions.<env domain>`) and `http://localhost:4200` for local dev.
2. **App roles** (allowed member types: Users/Groups). The value must match exactly: `Student`, `CreditStaff`, `Evaluator`, `Department`, `Registrar`, `Advisor`.
3. **Enterprise applications → the app → Users and groups:** assign each person (or a group) one or more of those roles. A signed-in user with no role sees "No TransferIQ role assigned", and the API answers 403.
4. Optional: set *Assignment required* = Yes so that only assigned users can sign in.

Tokens are requested for `<client id>/.default`. Set `ENTRA_API_SCOPE` to use an exposed scope (`api://<client id>/<scope>`) instead.
- Tear down: `az group delete -n rg-transferiq-aca --yes`.

The rest of this file describes the full platform.

| Module | Resources |
| --- | --- |
| `monitoring.bicep` | Log Analytics (1 GB/day cap) + workspace-based Application Insights |
| `keyvault.bicep`, `kv-secret.bicep` | Key Vault (RBAC mode, soft delete 7 days) + secrets (App Insights and ACS connection strings) |
| `storage.bicep` | StorageV2, shared keys **disabled**, private containers `transcripts`, `syllabi` |
| `registry.bicep` | ACR Basic (admin user off) + user-assigned identity with AcrPull and Key Vault Secrets User |
| `postgres.bicep` | PostgreSQL Flexible Server 16, Burstable `Standard_B1ms`, **Entra auth only**, DB `transferiq` |
| `ai.bicep` | Azure OpenAI + one model deployment (parameterised), Document Intelligence (`FormRecognizer`), AI Search Basic; all with key auth disabled |
| `communication.bicep` | Communication Services + Email with an Azure-managed sender domain; connection string goes straight to Key Vault |
| `containerapps-env.bicep` | Container Apps environment (Consumption) |
| `containerapp-api.bicep` | API container app: system-assigned identity, external HTTPS ingress, health probes, min 1 replica (CORS is handled by the API itself from `TRANSFERIQ_CORS_ORIGINS`, not by ingress) |
| `roles.bicep` | Roles for the API's system identity: Key Vault Secrets User, Storage Blob Data Contributor, Search Index Data Contributor + Search Service Contributor, Cognitive Services User (Doc Intelligence), Cognitive Services OpenAI User |
| `postgres-admin.bicep` | Adds the API identity as a Postgres Entra admin (demo shortcut, see gaps) |
| `staticwebapp.bicep`, `staticwebapp-backend.bicep` | Static Web App (Standard) + linked backend so the SPA calls relative `/api/*` |

All resources are tagged `project=transferiq` and `env=<env>`. No keys or passwords are created for the app: it uses managed identity everywhere except ACS email and App Insights, whose connection strings are Key Vault references.

## Prerequisites

1. Azure CLI ≥ 2.60 with Bicep (`az bicep install`), logged in: `az login`.
2. A resource group: `az group create -n rg-transferiq-demo -l eastus2`.
3. Resource providers registered once per subscription:
   ```bash
   for p in Microsoft.App Microsoft.ContainerRegistry Microsoft.DBforPostgreSQL Microsoft.CognitiveServices \
            Microsoft.Search Microsoft.Communication Microsoft.Web Microsoft.OperationalInsights Microsoft.Insights \
            Microsoft.KeyVault Microsoft.Storage Microsoft.ManagedIdentity; do az provider register -n $p; done
   ```
4. Your identity needs **Contributor + Role Based Access Control Administrator** (or Owner) on the resource group, because the template creates role assignments.
5. Azure OpenAI access and quota in `openAiLocation` for the model you choose (or set `deployOpenAi = false`).
6. **Fill in `infra/main.bicepparam`** (see "Parameters the team must set").

## Deploy (order of steps)

The container app can only start once its image is in ACR, and ACR is created by the same template, so the template is deployed twice (incremental mode, idempotent). `.github/workflows/deploy.yml` does exactly this.

```bash
RG=rg-transferiq-demo

# 1. Infrastructure without the API (creates ACR, Key Vault, DB, AI services, SWA, ...)
az deployment group create -g $RG -f infra/main.bicep -p infra/main.bicepparam -p deployApi=false

# 2. Build the API image (build context = repo root) and push it to ACR
ACR=$(az acr list -g $RG --query "[0].name" -o tsv)
az acr login -n $ACR
docker build -f backend/Dockerfile -t $ACR.azurecr.io/transferiq-api:v1 .
docker push $ACR.azurecr.io/transferiq-api:v1

# 3. Same template with the API: creates/updates the container app, its roles, the Postgres admin and the SWA /api link
az deployment group create -g $RG -f infra/main.bicep -p infra/main.bicepparam \
  -p deployApi=true apiImage=$ACR.azurecr.io/transferiq-api:v1

# 4. SPA
(cd frontend && npm ci && npx ng build)
TOKEN=$(az staticwebapp secrets list -n swa-tiq-demo -g $RG --query properties.apiKey -o tsv)
npx @azure/static-web-apps-cli deploy frontend/dist/transferiq-web/browser --deployment-token "$TOKEN" --env production
```

Once the image exists, steps 1–3 are a single command for later updates (step 3 alone).

### GitHub Actions (OIDC)

`deploy.yml` runs on `workflow_dispatch` and on pushes to `main`. Setup, once:

1. Create an Entra app registration (or user-assigned identity) for GitHub, and grant it **Contributor + Role Based Access Control Administrator** on the resource group.
2. Add a federated credential. The job uses the GitHub environment `demo`, so the subject is
   `repo:<org>/<repo>:environment:demo` (not the branch subject).
3. Repo **secrets** (identifiers, not credentials): `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
4. Repo **variables**: `AZURE_RESOURCE_GROUP` (required), `TIQ_ENV` (optional, default `demo`).
5. Create the `demo` environment in GitHub (optionally with a required reviewer).

The SWA deployment token is read at run time with `az staticwebapp secrets list` and masked; it is never stored in the repo.

### CI (`ci.yml`)

Runs on every push and PR, fully offline (no Azure secrets): backend `pytest -q`, `eval/run_eval.py` when present (report uploaded as artifact `eval-report`), Angular build, `bicep build`, and the **AI-log rule**:

> A push or PR that changes anything under `backend/`, `frontend/src/` or `infra/` must also add or change a file under `ai-logs/` in the same range. Implemented in `scripts/check_ai_logs.sh` (run it locally with `scripts/check_ai_logs.sh origin/main HEAD`).

## Parameters the team must set

| Parameter | Why |
| --- | --- |
| `openAiModelName`, `openAiModelVersion`, `openAiDeploymentSku`, `openAiLocation` | No default in `main.bicep` on purpose. The bicepparam values (`gpt-4o-mini` / `2024-07-18`, GlobalStandard) are **placeholders to verify**: `az cognitiveservices model list -l <region> -o table`. Models are retired over time. |
| `openAiCapacity` | TPM quota (×1,000) available in your subscription. |
| `deployOpenAi` | `false` if there is no Azure OpenAI access; the API then runs the offline matcher (ADR 0003). |
| `location`, `staticWebAppLocation`, `postgresLocation` | Region availability and offer restrictions differ per subscription. |
| `postgresEntraAdminObjectId` / `Name` / `Type` | Entra group for humans to administer the DB (optional). |
| `keyVaultAdminObjectId` | Group allowed to read/write secrets (optional). |
| `authMode` | `demo` (header `X-Demo-Role`, anyone can pick any role) or `entra` (Entra ID access token required; roles come from the token's app roles, see "Entra ID sign-in"). The Bicep template does not set `ENTRA_CLIENT_ID` / `ENTRA_TENANT_ID` yet, and `entra` without them answers 401, so use `scripts/deploy_aca.sh` for Entra mode. |
| `staticWebAppSku` | `Standard` for the linked `/api` backend; `Free` saves $9/month but the SPA must then call the API URL directly. |

## Environment variable contract for the API

Set by `main.bicep` on the container app (developer agent: read these, never hard-code endpoints). The "Read by backend" column was checked against `backend/app` on 2026-10-28 (devops-02).

| Variable | Value | Read by backend |
| --- | --- | --- |
| `TRANSFERIQ_ENV` | env name | not yet |
| `TRANSFERIQ_AUTH_MODE`, `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID` | `demo` / `entra`; app registration ids for token validation | yes, `guard.py` |
| `TRANSFERIQ_CORS_ORIGINS` | comma-separated origins: SWA host + `extraCorsOrigins` (`*` ignored) | yes, `main.py` |
| `TRANSFERIQ_DATA_DIR`, `TRANSFERIQ_SEED_DIR` | set in the image: `/app/data/synthetic`, `/app/data/synthetic/seed` | `TRANSFERIQ_SEED_DIR` yes, `store.py` |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` | only present when `deployOpenAi = true` (absent ⇒ offline fallback) | yes, `matcher.py` (managed identity via `DefaultAzureCredential`) |
| `AZURE_DI_ENDPOINT` | Document Intelligence endpoint (OCR for scanned PDFs) | yes, `ingest.py` (managed identity) |
| `AZURE_SEARCH_ENDPOINT` | AI Search endpoint | not yet (shortlist is lexical in-process) |
| `AZURE_STORAGE_BLOB_ENDPOINT`, `AZURE_STORAGE_CONTAINER_TRANSCRIPTS`, `AZURE_STORAGE_CONTAINER_SYLLABI` | blob endpoint + container names | yes, `blob_store.py`. Every accepted transcript or syllabus PDF is stored as `<container>/<student or course>/<UTC time>-<id>.pdf` via managed identity. If the write fails, the upload is rejected (502) and nothing is recorded. Unset = no archive (offline). |
| `AZURE_KEY_VAULT_URI` | for any runtime secret lookups | not yet |
| `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_AUTH=entra` | password = Entra token: `DefaultAzureCredential().get_token("https://ossrdbms-aad.database.windows.net/.default").token`, `sslmode=require`; refresh before expiry | not yet (in-memory store) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING`, `ACS_CONNECTION_STRING` | Key Vault references (secretRef) | not yet (no telemetry SDK, no email sender) |
| `AZURE_COMMUNICATION_ENDPOINT`, `ACS_SENDER_ADDRESS` | email reminders | not yet |

The SPA calls relative `/api/...` URLs (`frontend/src/app/api/api.service.ts` `API_BASE = '/api'`), and the SWA linked backend proxies them to the container app.

**Do not set `AZURE_CLIENT_ID`** on the container app. Without it, `DefaultAzureCredential` uses the system-assigned identity, which holds the data roles. With it, the app would switch to the user-assigned pull identity, which has no data roles.

The SPA also needs `frontend/public/staticwebapp.config.json` with a `navigationFallback` to `/index.html` (deep links such as `/review` otherwise return 404 on SWA) and security headers. This is developer scope and is tracked in `docs/security/review-2026-10-28.md`.

## Local container

```bash
docker build -f backend/Dockerfile -t transferiq-api .     # from the repo root
docker run --rm -p 8000:8000 transferiq-api               # http://localhost:8000/api/health
```

The image contains `backend/` (no tests) and the synthetic `seed/`, `syllabi/` and `transcripts/` folders, runs as UID 10001 and has a health check on `/api/health`.

## Cost note (rough, USD, pay-as-you-go, verify in the Azure pricing calculator)

| Item | ~ per month |
| --- | --- |
| AI Search Basic | ~75 (largest item; `searchSku = 'free'` if one free service per subscription is still available) |
| Container Apps, 1 always-on replica (0.5 vCPU / 1 GiB) | ~25–45 |
| PostgreSQL B1ms + 32 GB | ~15–20 |
| Static Web App Standard | ~9 |
| ACR Basic | ~5 |
| Log Analytics / App Insights (1 GB/day cap) | 0–10 |
| Azure OpenAI, Doc Intelligence, ACS email, Storage, Key Vault | usage-based, cents to a few dollars for the demo |
| **Total** | **≈ 130–170 / month, about 5 / day** |

Tear down after the hackathon: `az group delete -n $RG`. Key Vault and Cognitive Services accounts are soft-deleted; before redeploying with the same names purge them (`az keyvault purge -n <kv>`, `az cognitiveservices account purge -g $RG -l <loc> -n <name>`).

## Known gaps (demo shortcuts, documented on purpose)

- Public endpoints everywhere; production should use a VNet-integrated Container Apps environment and private endpoints for Postgres, Storage, Key Vault, OpenAI, Search and Doc Intelligence.
- Postgres firewall allows all Azure services (`0.0.0.0` rule) because Consumption Container Apps have no fixed egress IP.
- The API identity is a Postgres Entra **admin**; production should create a least-privilege role (`pgaadauth_create_principal`) and grant only needed tables.
- Key Vault purge protection is off so the resource group can be recreated.
- The SWA linked backend may put an auth provider in front of the container app so direct calls to the container app URL are rejected; use the SWA URL. If you switch to `Free`, the SPA must call `apiUrl` (CORS: the SWA host is already in `TRANSFERIQ_CORS_ORIGINS`).
- `deployApi=true` with an empty `apiImage` fails; the workflow always passes it.
- This template was compiled with the Bicep CLI (0.48.1) with zero errors or linter warnings but has **not** been deployed to a subscription yet; expect first-run fixes (region/model/quota).
- ~~Backend alignment needed~~ **Resolved** in developer-03 (dd962e6): `matcher.py` and `ingest.py` now use `DefaultAzureCredential`. The key env vars are only an optional local-dev fallback and are not set by this template. Re-checked in devops-02.
- Several provisioned services (Postgres, AI Search, ACS, App Insights) are not yet used by the backend (in-memory store). Blob Storage is used, but only to archive uploaded PDFs. They cost money while idle; see the cost note.
