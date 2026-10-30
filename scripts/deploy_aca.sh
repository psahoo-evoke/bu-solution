#!/usr/bin/env bash
# Lean container deployment of TransferIQ to Azure Container Apps (frontend + backend as two containers).
#
#   Internet --HTTPS--> ca-<prefix>-web (nginx + Angular SPA, external ingress :8080)
#                           |  /api/*  (proxied, same origin, no CORS)
#                           v
#                       ca-<prefix>-api (FastAPI, INTERNAL ingress only :8000, exactly 1 replica)
#
# Images are built in Azure Container Registry (az acr build), so local Docker is NOT required.
# The API pulls nothing at runtime: offline matcher, synthetic data baked into the image (ADR 0003).
# For the full platform (Postgres, OpenAI, Search, Key Vault, SWA ...) use infra/main.bicep instead.
#
# Usage (Git Bash, WSL, macOS/Linux or Azure Cloud Shell), from anywhere in the repo, after `az login`:
#   scripts/deploy_aca.sh
#   RG=rg-tiq-test LOCATION=westeurope PREFIX=tiqt scripts/deploy_aca.sh
#   STORAGE_ACCOUNT=<account> scripts/deploy_aca.sh   # also keep uploaded transcripts/syllabi in Blob Storage
#   ENTRA_CLIENT_ID=<app id> ENTRA_TENANT_ID=<tenant id> scripts/deploy_aca.sh   # Microsoft sign-in + app roles
#     (ids only, no secret; the app registration needs a SPA redirect URI = the web URL and the app roles,
#      see infra/README.md "Entra ID sign-in"). Without them both apps run in demo mode (X-Demo-Role switcher).
#   PORTAL_AUTH=1 scripts/deploy_aca.sh   # TransferIQ accounts: student / department / staff sign-in + register
# Re-running is safe: it rebuilds the images with a new tag and rolls both apps to a new revision.
#
# Needs: Azure CLI >= 2.60, and Contributor + Role Based Access Control Administrator (or Owner) on the
# resource group, because it grants AcrPull to the apps' pull identity.
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash on Windows: don't rewrite /subscriptions/... resource IDs into file paths
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1   # Windows az CLI crashes (cp1252) printing build logs with Unicode

RG="${RG:-rg-transferiq-aca}"
LOCATION="${LOCATION:-eastus2}"
PREFIX="${PREFIX:-tiq}"                       # lowercase letters/digits
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${TAG:-$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)-$(date +%H%M%S)}"

SUB_ID="$(az account show --query id -o tsv)"
ACR="${ACR:-cr${PREFIX}$(printf '%s' "$SUB_ID/$RG" | md5sum | cut -c1-8)}"   # globally unique, stable per RG
ENV_NAME="${ENV_NAME:-cae-${PREFIX}}"         # override to reuse an existing environment / registry / apps
ID_NAME="${ID_NAME:-id-${PREFIX}-acrpull}"
API_APP="${API_APP:-ca-${PREFIX}-api}"
WEB_APP="${WEB_APP:-ca-${PREFIX}-web}"

log() { printf '\n==> %s\n' "$*"; }

log "Subscription $(az account show --query name -o tsv) | RG $RG | $LOCATION | tag $TAG"
az extension add --name containerapp --upgrade --only-show-errors -y >/dev/null
# Registering needs subscription-level rights; skip providers that are already registered (RG-scoped users).
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry Microsoft.ManagedIdentity; do
  [ "$(az provider show -n "$p" --query registrationState -o tsv 2>/dev/null)" = "Registered" ] && continue
  az provider register -n "$p" --only-show-errors >/dev/null \
    || echo "WARNING: could not register $p (needs subscription rights); ask a subscription owner if later steps fail"
done

log "Resource group, registry and pull identity"
az group show -n "$RG" -o none 2>/dev/null \
  || az group create -n "$RG" -l "$LOCATION" --tags project=transferiq --only-show-errors -o none
az acr show -n "$ACR" -g "$RG" -o none 2>/dev/null \
  || az acr create -n "$ACR" -g "$RG" -l "$LOCATION" --sku Basic --admin-enabled false --only-show-errors -o none
ACR_SERVER="$(az acr show -n "$ACR" -g "$RG" --query loginServer -o tsv)"
ACR_ID="$(az acr show -n "$ACR" -g "$RG" --query id -o tsv)"

az identity show -n "$ID_NAME" -g "$RG" -o none 2>/dev/null \
  || az identity create -n "$ID_NAME" -g "$RG" -l "$LOCATION" --only-show-errors -o none
ID_ID="$(az identity show -n "$ID_NAME" -g "$RG" --query id -o tsv)"
ID_PRINCIPAL="$(az identity show -n "$ID_NAME" -g "$RG" --query principalId -o tsv)"
# Filter by principalId instead of --assignee: no Graph lookup (new identities take a while to replicate there).
if [ -z "$(az role assignment list --scope "$ACR_ID" --role AcrPull --query "[?principalId=='$ID_PRINCIPAL'].id | [0]" -o tsv)" ]; then
  az role assignment create --assignee-object-id "$ID_PRINCIPAL" --assignee-principal-type ServicePrincipal \
    --role AcrPull --scope "$ACR_ID" --only-show-errors -o none
  echo "AcrPull granted; waiting 30s for RBAC propagation"; sleep 30
fi

log "Building images in ACR (cloud build)"
# API: build context = repo root (bundles data/synthetic; filtered by the root .dockerignore allow-list).
# Relative paths from the repo root: the Windows az CLI cannot read Git Bash paths such as /c/Users/...
# --no-logs: the Windows az CLI crashes streaming Unicode build logs; it still waits, and we check the status.
# Failed build logs: az acr task logs -r <acr> --run-id <id>
cd "$ROOT"
acr_build() {
  local status
  # timeout: the az client has been seen polling forever after ACR already finished the run.
  status="$(timeout 900 az acr build -r "$ACR" --no-logs --only-show-errors --query status -o tsv "$@" || true)"
  echo "acr build $* -> $status"
  [ "$status" = "Succeeded" ] || { echo "ERROR: image build failed"; exit 1; }
}
acr_build -t "transferiq-api:$TAG" -f backend/Dockerfile .
acr_build -t "transferiq-web:$TAG" frontend

log "Container Apps environment"
az containerapp env show -n "$ENV_NAME" -g "$RG" -o none 2>/dev/null \
  || az containerapp env create -n "$ENV_NAME" -g "$RG" -l "$LOCATION" --only-show-errors -o none

# deploy_app <name> <image> <ingress> <port> <min> <max> <env vars...>
deploy_app() {
  local name="$1" image="$2" ingress="$3" port="$4" min="$5" max="$6"; shift 6
  if az containerapp show -n "$name" -g "$RG" -o none 2>/dev/null; then
    # Existing app (possibly a portal placeholder): make sure pull identity, registry and ingress are set.
    az containerapp identity assign -n "$name" -g "$RG" --user-assigned "$ID_ID" --only-show-errors -o none
    az containerapp registry set -n "$name" -g "$RG" --server "$ACR_SERVER" --identity "$ID_ID" --only-show-errors -o none
    az containerapp ingress enable -n "$name" -g "$RG" --type "$ingress" --target-port "$port" --transport auto \
      --only-show-errors -o none
    az containerapp update -n "$name" -g "$RG" --image "$image" \
      --min-replicas "$min" --max-replicas "$max" --set-env-vars "$@" --only-show-errors -o none
  else
    az containerapp create -n "$name" -g "$RG" --environment "$ENV_NAME" --image "$image" \
      --user-assigned "$ID_ID" --registry-server "$ACR_SERVER" --registry-identity "$ID_ID" \
      --ingress "$ingress" --target-port "$port" --cpu 0.5 --memory 1.0Gi \
      --min-replicas "$min" --max-replicas "$max" --env-vars "$@" --tags project=transferiq \
      --only-show-errors -o none
  fi
}

if [ -n "${ENTRA_CLIENT_ID:-}" ] && [ -n "${ENTRA_TENANT_ID:-}" ]; then
  AUTH_ENV_API=(TRANSFERIQ_AUTH_MODE=entra ENTRA_CLIENT_ID="$ENTRA_CLIENT_ID" ENTRA_TENANT_ID="$ENTRA_TENANT_ID")
  AUTH_ENV_WEB=(AUTH_MODE=entra ENTRA_CLIENT_ID="$ENTRA_CLIENT_ID" ENTRA_TENANT_ID="$ENTRA_TENANT_ID"
                ENTRA_API_SCOPE="${ENTRA_API_SCOPE:-}")
elif [ "${PORTAL_AUTH:-}" = "1" ]; then
  # TransferIQ portal accounts (backend/app/accounts.py): student / department / staff sign-in + registration.
  AUTH_ENV_API=(TRANSFERIQ_AUTH_MODE=portal)
  AUTH_ENV_WEB=(AUTH_MODE=portal)
else
  AUTH_ENV_API=(TRANSFERIQ_AUTH_MODE=demo)
  AUTH_ENV_WEB=(AUTH_MODE=demo)
fi

log "API container app ($API_APP, internal only, auth ${AUTH_ENV_API[0]#*=})"
# Exactly one replica: the store is in memory (backend/app/store.py), so replicas would not share state.
deploy_app "$API_APP" "$ACR_SERVER/transferiq-api:$TAG" internal 8000 1 1 \
  TRANSFERIQ_ENV="$PREFIX" "${AUTH_ENV_API[@]}"
API_FQDN="$(az containerapp show -n "$API_APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)"

# Portal mode: a stable session-signing key (Container Apps secret, created once), so a restart or a new revision
# does not sign everyone out. Never printed or committed.
if [ "${PORTAL_AUTH:-}" = "1" ] && [ -z "${ENTRA_CLIENT_ID:-}" ]; then
  if [ -z "$(az containerapp secret list -n "$API_APP" -g "$RG" --query "[?name=='session-secret'].name" -o tsv)" ]; then
    az containerapp secret set -n "$API_APP" -g "$RG" --only-show-errors -o none \
      --secrets session-secret="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  fi
  az containerapp update -n "$API_APP" -g "$RG" --only-show-errors -o none \
    --set-env-vars TRANSFERIQ_SESSION_SECRET=secretref:session-secret
fi

# Public credit chat (every auth mode): a stable key for signing replies (backend/app/credit_chat.py), created once, so
# the chat keeps its context across restarts and revisions. Separate from the session secret. Never printed.
if [ -z "$(az containerapp secret list -n "$API_APP" -g "$RG" --query "[?name=='chat-secret'].name" -o tsv)" ]; then
  az containerapp secret set -n "$API_APP" -g "$RG" --only-show-errors -o none \
    --secrets chat-secret="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi
az containerapp update -n "$API_APP" -g "$RG" --only-show-errors -o none \
  --set-env-vars TRANSFERIQ_CHAT_SECRET=secretref:chat-secret

# Optional PostgreSQL (backend/app/db.py): PG_HOST, PG_DB, PG_USER, PG_PASSWORD. The password goes into a Container
# Apps secret (never printed); the server firewall must allow Azure services. Without PG_HOST the API keeps whatever
# database settings it already has (or runs in memory).
if [ -n "${PG_HOST:-}" ]; then
  log "PostgreSQL ($PG_HOST / ${PG_DB:-postgres})"
  az containerapp secret set -n "$API_APP" -g "$RG" --secrets postgres-password="${PG_PASSWORD:?set PG_PASSWORD}" \
    -o none --only-show-errors
  az containerapp update -n "$API_APP" -g "$RG" --only-show-errors -o none --set-env-vars \
    POSTGRES_HOST="$PG_HOST" POSTGRES_DB="${PG_DB:-postgres}" POSTGRES_USER="${PG_USER:?set PG_USER}" \
    POSTGRES_PASSWORD=secretref:postgres-password
fi

# Optional upload archive (backend/app/blob_store.py): STORAGE_ACCOUNT=<existing account> [STORAGE_RG=<its RG>].
# The API's SYSTEM identity writes blobs (DefaultAzureCredential picks it because AZURE_CLIENT_ID is not set);
# the user-assigned identity above stays pull-only. Roles are scoped to the two containers, not the account.
if [ -n "${STORAGE_ACCOUNT:-}" ]; then
  log "Upload archive in Blob Storage ($STORAGE_ACCOUNT)"
  ST_RG="${STORAGE_RG:-$RG}"
  ST_ID="$(az storage account show -n "$STORAGE_ACCOUNT" -g "$ST_RG" --query id -o tsv)"
  BLOB_EP="$(az storage account show -n "$STORAGE_ACCOUNT" -g "$ST_RG" --query primaryEndpoints.blob -o tsv)"
  API_PRINCIPAL="$(az containerapp identity assign -n "$API_APP" -g "$RG" --system-assigned --query principalId -o tsv)"
  for c in transcripts syllabi accounts; do
    az storage container-rm show --storage-account "$ST_ID" -n "$c" -o none 2>/dev/null \
      || az storage container-rm create --storage-account "$ST_ID" -n "$c" --public-access off --only-show-errors -o none
    scope="$ST_ID/blobServices/default/containers/$c"
    if [ -z "$(az role assignment list --scope "$scope" --role "Storage Blob Data Contributor" \
                 --query "[?principalId=='$API_PRINCIPAL'].id | [0]" -o tsv)" ]; then
      az role assignment create --assignee-object-id "$API_PRINCIPAL" --assignee-principal-type ServicePrincipal \
        --role "Storage Blob Data Contributor" --scope "$scope" --only-show-errors -o none
    fi
  done
  az containerapp update -n "$API_APP" -g "$RG" --only-show-errors -o none --set-env-vars \
    AZURE_STORAGE_BLOB_ENDPOINT="$BLOB_EP" AZURE_STORAGE_CONTAINER_TRANSCRIPTS=transcripts AZURE_STORAGE_CONTAINER_SYLLABI=syllabi \
    AZURE_STORAGE_CONTAINER_ACCOUNTS=accounts
fi

# Optional Azure AI Search shortlist (backend/app/search.py): SEARCH_SERVICE=<existing service> [SEARCH_RG=<its RG>]
# [SEARCH_INDEX=bu-courses] [EMBEDDING_DEPLOYMENT=<name>]. Build the index first with scripts/build_search_index.py.
# The API's SYSTEM identity only reads (Search Index Data Reader); the service's API access control must allow
# role-based access ("Both" or "Role-based access control"). No search key is stored in the app.
if [ -n "${SEARCH_SERVICE:-}" ]; then
  log "Candidate shortlist from Azure AI Search ($SEARCH_SERVICE)"
  SR_ID="$(az search service show -n "$SEARCH_SERVICE" -g "${SEARCH_RG:-$RG}" --query id -o tsv)"
  API_PRINCIPAL="$(az containerapp identity assign -n "$API_APP" -g "$RG" --system-assigned --query principalId -o tsv)"
  if [ -z "$(az role assignment list --scope "$SR_ID" --role "Search Index Data Reader" \
               --query "[?principalId=='$API_PRINCIPAL'].id | [0]" -o tsv)" ]; then
    az role assignment create --assignee-object-id "$API_PRINCIPAL" --assignee-principal-type ServicePrincipal \
      --role "Search Index Data Reader" --scope "$SR_ID" --only-show-errors -o none
  fi
  az containerapp update -n "$API_APP" -g "$RG" --only-show-errors -o none --set-env-vars \
    AZURE_SEARCH_ENDPOINT="https://$SEARCH_SERVICE.search.windows.net" AZURE_SEARCH_INDEX="${SEARCH_INDEX:-bu-courses}" \
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT="${EMBEDDING_DEPLOYMENT:-}"
fi

log "Web container app ($WEB_APP, public)"
deploy_app "$WEB_APP" "$ACR_SERVER/transferiq-web:$TAG" external 8080 1 3 \
  API_UPSTREAM="https://$API_FQDN" "${AUTH_ENV_WEB[@]}"
WEB_URL="https://$(az containerapp show -n "$WEB_APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)"

# "Syllabus needed" emails (backend/app/notify.py): NOTIFY_TO / NOTIFY_CC = comma-separated recipients. The link in
# the mail points at the web app. Sending also needs the mail service: scripts/setup_email.sh (one-off).
if [ -n "${NOTIFY_TO:-}" ]; then
  log "Syllabus request emails -> ${NOTIFY_TO}${NOTIFY_CC:+ (cc ${NOTIFY_CC})}"
  az containerapp update -n "$API_APP" -g "$RG" --only-show-errors -o none --set-env-vars \
    SYLLABUS_REQUEST_TO="$NOTIFY_TO" SYLLABUS_REQUEST_CC="${NOTIFY_CC:-}" APP_BASE_URL="$WEB_URL"
fi

log "Smoke test"
for i in 1 2 3 4 5 6 7 8 9 10; do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$WEB_URL/api/health" || true)"
  echo "GET $WEB_URL/api/health -> $code"
  [ "$code" = "200" ] && break
  sleep 10
done

cat <<EOF

Done.
  App:        $WEB_URL
  API (int.): https://$API_FQDN  (reachable only from inside $ENV_NAME, via the web app's /api)
  Images:     $ACR_SERVER/transferiq-{api,web}:$TAG
  Logs:       az containerapp logs show -n $API_APP -g $RG --follow
  Tear down:  az group delete -n $RG --yes
EOF
