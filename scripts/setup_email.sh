#!/usr/bin/env bash
# One-off: Azure Communication Services Email for the "syllabus needed" emails (backend/app/notify.py).
#
# Prerequisite (needs SUBSCRIPTION-level rights, ask a subscription Owner/Contributor once):
#   az provider register -n Microsoft.Communication
#
# Then, with Owner (or Contributor + RBAC Administrator) on the resource group:
#   RG=AI-F-TheSolutionauts API_APP=bu-solutions-api scripts/setup_email.sh
#
# Creates: Email Communication Service + an Azure-managed sender domain (DoNotReply@<id>.azurecomm.net),
# a Communication Services resource linked to that domain, and gives the API's system identity the
# "Communication and Email Service Owner" role on it (managed identity, no keys). Sets AZURE_COMMUNICATION_ENDPOINT
# and ACS_SENDER_ADDRESS on the API. Re-running is safe.
set -euo pipefail
export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 PYTHONUTF8=1

RG="${RG:?set RG}"
API_APP="${API_APP:?set API_APP}"
ACS="${ACS:-acs-transferiq}"
ECS="${ECS:-ecs-transferiq}"
DATA_LOCATION="${DATA_LOCATION:-UnitedStates}"

log() { printf '\n==> %s\n' "$*"; }

state="$(az provider show -n Microsoft.Communication --query registrationState -o tsv)"
if [ "$state" != "Registered" ]; then
  echo "Microsoft.Communication is '$state'. A subscription admin must run: az provider register -n Microsoft.Communication"
  exit 1
fi
az extension add --name communication --upgrade --only-show-errors -y >/dev/null

log "Email Communication Service + Azure-managed domain"
az communication email show -n "$ECS" -g "$RG" -o none 2>/dev/null \
  || az communication email create -n "$ECS" -g "$RG" --location global --data-location "$DATA_LOCATION" -o none
az communication email domain show --domain-name AzureManagedDomain --email-service-name "$ECS" -g "$RG" -o none 2>/dev/null \
  || az communication email domain create --domain-name AzureManagedDomain --email-service-name "$ECS" -g "$RG" \
       --location global --domain-management AzureManaged -o none
DOMAIN_ID="$(az communication email domain show --domain-name AzureManagedDomain --email-service-name "$ECS" -g "$RG" --query id -o tsv)"
SENDER_DOMAIN="$(az communication email domain show --domain-name AzureManagedDomain --email-service-name "$ECS" -g "$RG" --query mailFromSenderDomain -o tsv)"

log "Communication Services resource linked to the domain"
az communication show -n "$ACS" -g "$RG" -o none 2>/dev/null \
  || az communication create -n "$ACS" -g "$RG" --location global --data-location "$DATA_LOCATION" -o none
az communication update -n "$ACS" -g "$RG" --linked-domains "$DOMAIN_ID" -o none
ACS_ID="$(az communication show -n "$ACS" -g "$RG" --query id -o tsv)"
ENDPOINT="https://$(az communication show -n "$ACS" -g "$RG" --query hostName -o tsv)"

log "API identity may send mail"
PRINCIPAL="$(az containerapp identity assign -n "$API_APP" -g "$RG" --system-assigned --query principalId -o tsv)"
if [ -z "$(az role assignment list --scope "$ACS_ID" --role "Communication and Email Service Owner" \
             --query "[?principalId=='$PRINCIPAL'].id | [0]" -o tsv)" ]; then
  az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
    --role "Communication and Email Service Owner" --scope "$ACS_ID" -o none
fi

az containerapp update -n "$API_APP" -g "$RG" --only-show-errors -o none --set-env-vars \
  AZURE_COMMUNICATION_ENDPOINT="$ENDPOINT" ACS_SENDER_ADDRESS="DoNotReply@$SENDER_DOMAIN"

cat <<EOF

Done. Sender: DoNotReply@$SENDER_DOMAIN  Endpoint: $ENDPOINT
Recipients come from deploy_aca.sh NOTIFY_TO / NOTIFY_CC. Role assignments can take a few minutes to apply.
Note: Azure-managed domains have low sending limits and mail may land in spam/quarantine the first time.
EOF
