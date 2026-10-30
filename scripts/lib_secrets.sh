# Sourced by the deploy scripts (needs RG). Stores Container App secrets; values are never printed.
# With KEYVAULT=<vault name> each value goes into Azure Key Vault and the app keeps only a reference, read at runtime
# by the app's system identity (role "Key Vault Secrets User" on the vault). Without KEYVAULT: a plain app secret.

# azv <az args...>: az output for $(...) captures, without the \r the Windows az CLI puts at each line end.
azv() { az "$@" | tr -d '\r'; }

# app_secret <app> <name> <value>
app_secret() {
  if [ -n "${KEYVAULT:-}" ]; then
    kv_secret "$2" "$3"
    kv_link "$1" "$2"
  else
    az containerapp secret set -n "$1" -g "$RG" --secrets "$2=$3" -o none --only-show-errors
  fi
}

# kv_secret <name> <value>: write one vault secret (a new version if it exists).
kv_secret() {
  az keyvault secret set --vault-name "$KEYVAULT" -n "$1" --value="$2" -o none --only-show-errors
}

# kv_link <app> <name>: the app's secret <name> becomes a reference to the vault secret of the same name.
kv_link() {
  local uri
  uri="$(azv keyvault show -n "$KEYVAULT" --query properties.vaultUri -o tsv)"
  az containerapp secret set -n "$1" -g "$RG" -o none --only-show-errors \
    --secrets "$2=keyvaultref:${uri%/}/secrets/$2,identityref:system"
}

# kv_grant <app>: system identity on the app, allowed to read the vault's secrets (safe to re-run).
kv_grant() {
  local kv_id principal
  kv_id="$(azv keyvault show -n "$KEYVAULT" --query id -o tsv)"
  principal="$(azv containerapp identity assign -n "$1" -g "$RG" --system-assigned --query principalId -o tsv)"
  if [ -z "$(az role assignment list --scope "$kv_id" --role "Key Vault Secrets User" \
               --query "[?principalId=='$principal'].id | [0]" -o tsv)" ]; then
    az role assignment create --assignee-object-id "$principal" --assignee-principal-type ServicePrincipal \
      --role "Key Vault Secrets User" --scope "$kv_id" --only-show-errors -o none
    echo "Key Vault Secrets User granted to $1; waiting 30s for RBAC propagation"; sleep 30
  fi
}
