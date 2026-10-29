#!/usr/bin/env bash
# One-off: send the "syllabus needed" emails through a Logic App + Office 365 Outlook connection
# (backend/app/notify.py, NOTIFY_WEBHOOK_URL). Works with resource-group rights only (no provider registration).
#
#   RG=AI-F-TheSolutionauts API_APP=bu-solutions-api scripts/setup_email_logicapp.sh
#
# Then ONE manual step in the Azure portal (OAuth consent cannot be scripted):
#   Resource group -> API connection "office365-transferiq" -> Edit API connection -> Authorize -> sign in with the
#   mailbox that should send the mails -> Save.
# Mail is then sent FROM that mailbox to SYLLABUS_REQUEST_TO / _CC. Re-running is safe.
set -euo pipefail
export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 PYTHONUTF8=1

RG="${RG:?set RG}"
API_APP="${API_APP:?set API_APP}"
LOCATION="${LOCATION:-westus2}"
CONN="${CONN:-office365-transferiq}"
LOGIC_APP="${LOGIC_APP:-la-transferiq-mail}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"                                   # relative @file paths: the Windows az CLI cannot read /c/... paths
TMP=".setup-logicapp.tmp.json"
trap 'rm -f "$TMP"' EXIT

log() { printf '\n==> %s\n' "$*"; }
SUB="$(az account show --query id -o tsv)"
MANAGED_API="/subscriptions/$SUB/providers/Microsoft.Web/locations/$LOCATION/managedApis/office365"

log "Office 365 Outlook connection ($CONN)"
if ! az resource show -g "$RG" -n "$CONN" --resource-type Microsoft.Web/connections -o none 2>/dev/null; then
  printf '{"displayName":"TransferIQ mail (Office 365 Outlook)","api":{"id":"%s"}}' "$MANAGED_API" > "$TMP"
  az resource create -g "$RG" -n "$CONN" --resource-type Microsoft.Web/connections -l "$LOCATION" \
    --properties @"$TMP" -o none
fi
CONN_ID="$(az resource show -g "$RG" -n "$CONN" --resource-type Microsoft.Web/connections --query id -o tsv)"

log "Logic App ($LOGIC_APP): HTTP trigger -> Send an email (V2) -> 200"
cat > "$TMP" <<'JSON'
{
  "state": "Enabled",
  "definition": {
    "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
    "contentVersion": "1.0.0.0",
    "parameters": { "$connections": { "defaultValue": {}, "type": "Object" } },
    "triggers": {
      "manual": {
        "type": "Request", "kind": "Http",
        "inputs": { "schema": { "type": "object", "required": ["to", "subject", "html"], "properties": {
          "to": { "type": "string" }, "cc": { "type": "string" }, "subject": { "type": "string" }, "html": { "type": "string" } } } }
      }
    },
    "actions": {
      "Send_email": {
        "type": "ApiConnection",
        "inputs": {
          "host": { "connection": { "name": "@parameters('$connections')['office365']['connectionId']" } },
          "method": "post", "path": "/v2/Mail",
          "body": { "To": "@triggerBody()?['to']", "Cc": "@triggerBody()?['cc']", "Subject": "@triggerBody()?['subject']",
                    "Body": "@triggerBody()?['html']", "Importance": "Normal" }
        }
      },
      "Response": {
        "type": "Response", "kind": "Http", "runAfter": { "Send_email": ["Succeeded"] },
        "inputs": { "statusCode": 200, "body": { "status": "sent" } }
      }
    },
    "outputs": {}
  },
  "parameters": { "$connections": { "value": { "office365": {
    "connectionId": "__CONN_ID__", "connectionName": "__CONN__", "id": "__MANAGED_API__" } } } }
}
JSON
sed -i "s#__CONN_ID__#$CONN_ID#; s#__CONN__#$CONN#; s#__MANAGED_API__#$MANAGED_API#" "$TMP"
az resource create -g "$RG" -n "$LOGIC_APP" --resource-type Microsoft.Logic/workflows -l "$LOCATION" \
  --properties @"$TMP" -o none
WF_ID="$(az resource show -g "$RG" -n "$LOGIC_APP" --resource-type Microsoft.Logic/workflows --query id -o tsv)"

log "Store the trigger URL as a Container Apps secret on $API_APP (never printed)"
CALLBACK="$(az rest --method post --uri "https://management.azure.com$WF_ID/triggers/manual/listCallbackUrl?api-version=2016-06-01" --query value -o tsv)"
az containerapp secret set -n "$API_APP" -g "$RG" --secrets notify-webhook="$CALLBACK" -o none --only-show-errors
az containerapp update -n "$API_APP" -g "$RG" -o none --only-show-errors \
  --set-env-vars NOTIFY_WEBHOOK_URL=secretref:notify-webhook

STATUS="$(az resource show -g "$RG" -n "$CONN" --resource-type Microsoft.Web/connections --query properties.overallStatus -o tsv)"
cat <<EOF

Done. Connection status: $STATUS
EOF
if [ "$STATUS" != "Connected" ]; then
  cat <<EOF
ACTION NEEDED (once): Azure portal -> resource group $RG -> API connection "$CONN" -> Edit API connection
-> Authorize -> sign in with the mailbox that should send the emails -> Save.
Until then the API answers 502 "The email could not be sent" when Upload syllabus is clicked.
EOF
fi
