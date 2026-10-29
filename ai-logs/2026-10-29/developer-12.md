# developer-12 · Send the syllabus emails through a Logic App + Office 365 Outlook

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (backend) + devops (Logic App, connection, secret) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | Sagar (spathur) |
| Trigger | User: "I'm not receiving mail once I upload a syllabus" |

## Diagnosis
- The live API log shows `email not sent (no mail service configured)`. Recipients were set, but no mail service existed: the `Microsoft.Communication` provider is `NotRegistered`, and registering it was refused (`AuthorizationFailed`, it needs a subscription admin).
- `Microsoft.Logic` and `Microsoft.Web` are registered, so a Logic App with the Office 365 Outlook connector can send with resource-group rights.

## Output
- `backend/app/notify.py`: second sender, `NOTIFY_WEBHOOK_URL`. The API POSTs `{to, cc, subject, html}` (semicolon-separated addresses) to the Logic App trigger; 200/202 = sent, anything else = 502. The URL carries an access signature and is never logged. ACS still wins when both are configured.
- `scripts/setup_email_logicapp.sh` (run on 2026-10-29):
  - created the API connection `office365-transferiq`
  - created the Logic App `la-transferiq-mail` (HTTP trigger → Office 365 "Send an email (V2)" → Response 200)
  - stored the trigger URL as Container Apps secret `notify-webhook` on `bu-solutions-api`, with `NOTIFY_WEBHOOK_URL=secretref:notify-webhook`
- `infra/README.md`: env row. `.gitignore`: the script's temp file.
- Tests: 3 new (webhook sends to/cc and subject; a failure is 502 and the URL never appears in the logs or response; ACS wins when both are set).

## Human step still needed
- Authorize the connection once in the Azure portal: API connection `office365-transferiq` → Edit API connection → Authorize → Save. Mail is then sent from the mailbox that authorized it.

## Verification
- `pytest -q tests/test_notify.py`: 11 passed. Connection status after the script: `Error` (not authorized yet, as expected).

## Commit
see git log
