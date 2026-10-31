#!/usr/bin/env bash
# One-off: keep every TransferIQ credential in Azure Key Vault instead of plain Container Apps secrets.
#
#   RG=AI-F-TheSolutionauts API_APP=bu-solutions-api KEYVAULT=kv-transferiq-95de2 scripts/setup_keyvault.sh
#
# 1. Creates the vault if missing (RBAC mode, westus2) and lets the signed-in user manage its secrets.
# 2. Copies each secret the API app holds (openai-key, postgres-password, session-secret, chat-secret, notify-webhook)
#    into the vault and turns the app secret into a Key Vault reference, read by the app's system identity.
# 3. Keys in the local .env that the live app does not use yet (Document Intelligence, AI Search) go into the vault too.
# 4. Restarts the API so it reads the references. Values are never printed. Re-running is safe.
# Afterwards pass KEYVAULT=<vault> to deploy_aca.sh / setup_email_logicapp.sh so new values land in the vault.
set -euo pipefail
export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 PYTHONUTF8=1

RG="${RG:?set RG}"
API_APP="${API_APP:?set API_APP}"
KEYVAULT="${KEYVAULT:?set KEYVAULT}"
LOCATION="${LOCATION:-westus2}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib_secrets.sh
. "$ROOT/scripts/lib_secrets.sh"
log() { printf '\n==> %s\n' "$*"; }

log "Key Vault $KEYVAULT"
az keyvault show -n "$KEYVAULT" -o none 2>/dev/null \
  || az keyvault create -n "$KEYVAULT" -g "$RG" -l "$LOCATION" --enable-rbac-authorization true \
       --retention-days 7 --tags project=transferiq --only-show-errors -o none
KV_ID="$(azv keyvault show -n "$KEYVAULT" --query id -o tsv)"
ME="$(azv ad signed-in-user show --query id -o tsv)"
if [ -z "$(az role assignment list --scope "$KV_ID" --role "Key Vault Secrets Officer" \
             --query "[?principalId=='$ME'].id | [0]" -o tsv)" ]; then
  az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
    --role "Key Vault Secrets Officer" --scope "$KV_ID" --only-show-errors -o none
  echo "Key Vault Secrets Officer granted to you; waiting 30s for RBAC propagation"; sleep 30
fi
kv_grant "$API_APP"

log "Move the secrets of $API_APP into the vault"
for name in $(azv containerapp secret list -n "$API_APP" -g "$RG" --query "[].name" -o tsv); do
  if [ -n "$(azv containerapp secret show -n "$API_APP" -g "$RG" --secret-name "$name" --query keyVaultUrl -o tsv)" ]; then
    echo "  $name: already in Key Vault"; continue
  fi
  value="$(azv containerapp secret show -n "$API_APP" -g "$RG" --secret-name "$name" --query value -o tsv)"
  [ -n "$value" ] || { echo "  $name: empty, skipped"; continue; }
  kv_secret "$name" "$value"
  kv_link "$API_APP" "$name"
  echo "  $name -> Key Vault"
done
unset value

log "Other keys from .env (stored only; the live app does not read them yet)"
env_value() { grep -E "^$1=" "$ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^["'\'']//' -e 's/["'\'']$//' || true; }
for pair in AZURE_DI_KEY:document-intelligence-key AZURE_SEARCH_API_KEY:search-key; do
  value="$(env_value "${pair%%:*}")"
  [ -n "$value" ] && kv_secret "${pair#*:}" "$value" && echo "  ${pair%%:*} -> ${pair#*:}"
done
unset value

log "Restart $API_APP so it reads the references"
REV="$(azv containerapp show -n "$API_APP" -g "$RG" --query properties.latestRevisionName -o tsv)"
az containerapp revision restart -n "$API_APP" -g "$RG" --revision "$REV" -o none --only-show-errors

log "Secrets of $API_APP now"
for name in $(azv containerapp secret list -n "$API_APP" -g "$RG" --query "[].name" -o tsv); do
  echo "  $name -> $(azv containerapp secret show -n "$API_APP" -g "$RG" --secret-name "$name" --query keyVaultUrl -o tsv)"
done
