# devops-01 · All credentials in Azure Key Vault

| Field | Value |
| --- | --- |
| Date | 2026-10-31 |
| Agent (role) | devops |
| Tool / model | Solutionauts AI (CLI) acting as devops |
| Human owner | Sagar (spathur) |
| Trigger | User: "make sure to store all credentials to store to azure key vault" |

## Finding
- No Key Vault in `AI-F-TheSolutionauts`. The API (`bu-solutions-api`) held five plain Container Apps secrets: `openai-key`, `postgres-password`, `session-secret`, `chat-secret`, `notify-webhook`.
- `deploy_aca.sh` and `setup_email_logicapp.sh` wrote secrets straight into the app, so a later deploy would have turned a vault reference back into a plain secret.
- The Windows az CLI ends each `-o tsv` line with `\r`; a first migration run read the name `openai-key\r`, which the vault stored as `openapikey` (a stray copy of the OpenAI key). Nothing on the app changed in that run.

## Output
- Vault `kv-transferiq-95de2` (westus2, RBAC mode, 7-day soft delete). Roles: Key Vault Secrets Officer for the signed-in owner; Key Vault Secrets User for the API's system identity.
- `scripts/lib_secrets.sh`: `app_secret` (vault + reference with `KEYVAULT`, plain app secret without), `kv_secret`, `kv_link` (`keyvaultref:…,identityref:system`), `kv_grant`, `azv` (az output without `\r`).
- `scripts/setup_keyvault.sh`: one-off move of every app secret into the vault (values never printed), plus the `.env` keys not used live yet (`document-intelligence-key`, `search-key`), then a restart of the API.
- `scripts/deploy_aca.sh`, `scripts/setup_email_logicapp.sh`: all secret writes go through `app_secret`; `KEYVAULT=<vault>` keeps them in the vault.
- `README.md`: Key Vault in the Azure services table, the secrets note and the deploy command.

## Human review
- Pending. Delete and purge the stray vault secret `openapikey` (the automated delete was blocked by the permission check).

## Verification
- All five app secrets now show a `keyVaultUrl` in `kv-transferiq-95de2`; vault values have the same lengths as the old app values.
- Live after restart (revision 0000046 healthy): `/api/health` 200; portal sign-in 200 (session secret); `/api/students` 200 with the token (PostgreSQL password); `/api/credit-chat` answered with Azure OpenAI (OpenAI key).
- `bash -n` on all four scripts: OK. No app code changed, so the test suites are unaffected.

## Commit
See git log (`devops: all credentials in Azure Key Vault; deploy scripts keep them there (devops-01)`).
