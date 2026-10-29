# developer-07 · Backend reminder wording

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (Cowork) |
| Human owner | Backend + AI dev |
| Trigger | developer-06 / adoption-01: backend text claimed reminders "are sent" but no email sending exists |

## Output
- `backend/app/rules.py`: TS next step now reads "Reminders scheduled for days 7, 21 and 45 (email sending not enabled in this prototype)."

## Human review
- Pending

## Verification
- Backend `pytest -q`: 301 passed. Front end `npm test`: 25 passed (the page's rewrite of the old sentence still works and is a no-op for the new one).

## Commit
see git log
