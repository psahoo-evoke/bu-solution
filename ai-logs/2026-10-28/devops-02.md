# devops-02 · Align infra with backend env vars; API-only CORS

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | devops |
| Tool / model | Solutionauts AI subagent acting as devops |
| Human owner | Tech lead |
| Trigger | Orchestrator: "re-check the infra env var names against what the backend now reads; fix only infra/" (during security-02) |

## Prompt (summary)
Compare what `backend/app` reads (DefaultAzureCredential, `TRANSFERIQ_CORS_ORIGINS`, `TRANSFERIQ_AUTH_MODE`, …) with what `infra/main.bicep` and the Dockerfile set, and fix `infra/` where they disagree.

## Inputs used
- `grep environ backend/app/*.py` at `6a5e056`; `backend/app/guard.py`, `main.py`, `matcher.py`, `ingest.py`
- `infra/main.bicep`, `infra/modules/containerapp-api.bicep`, `infra/README.md`

## Output
- Names: all variables the backend reads are set with matching names (`TRANSFERIQ_AUTH_MODE`, `TRANSFERIQ_CORS_ORIGINS`, `TRANSFERIQ_SEED_DIR` (Dockerfile), `AZURE_OPENAI_ENDPOINT/DEPLOYMENT/API_VERSION`, `AZURE_DI_ENDPOINT`). No renames were needed.
- `infra/modules/containerapp-api.bicep`: **removed the ingress `corsPolicy`** and the `corsOrigins` param. The API now owns CORS from `TRANSFERIQ_CORS_ORIGINS`. Two CORS layers could emit duplicate or conflicting `Access-Control-*` headers, and ingress had `allowCredentials: false` while the app has `true`. Also added a comment saying not to set `AZURE_CLIENT_ID`, because `DefaultAzureCredential` must pick the system-assigned identity that holds the data roles.
- `infra/main.bicep`: `authMode` description now says `entra` fails closed (401 everywhere) until JWT validation exists. The `extraCorsOrigins` description is updated. The corsOrigins argument is removed.
- `infra/README.md`: env var table gains a "Read by backend" column (several provisioned services aren't consumed yet). Added notes on `AZURE_CLIENT_ID` and on the missing `staticwebapp.config.json` (developer scope, security finding F-01). Marked the key-auth gap resolved.

## Human review
- Pending review by the tech lead.

## Verification
- Bicep CLI 0.48.1: `bicep build infra/main.bicep` and `build-params infra/main.bicepparam` give 0 errors and 0 warnings. `bicep lint` on `main.bicep` and every module is clean.
- Not deployed (no Azure credentials in the sandbox).

## Commit
see git log
