# developer-07 · Persist registered portal accounts in Blob Storage

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (backend) + devops (deploy script) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | Sagar (spathur) |
| Trigger | User: "save registered accounts to blob so they survive restart" |

## Output
- `backend/app/blob_store.py`: `save_json` (overwrite) and `load_json` (None when missing, `BlobStoreError` when unreadable), plus an `accounts` container kind (`AZURE_STORAGE_CONTAINER_ACCOUNTS`, default `accounts`).
- `backend/app/accounts.py`:
  - **Storage:** registered accounts and the student records they created live in `accounts/accounts.json`. Passwords are stored only as PBKDF2 hashes; seeded accounts are not stored (rebuilt at start-up).
  - **Start-up:** the API loads the document and merges it (seeded accounts win on an email clash).
  - **Registration:** the document is saved before the registration is accepted. A failed save gives 502 and rolls everything back (account, student record).
  - **Unreadable storage:** registration is paused (503) and retried on the next attempt. The stored list is never overwritten with a partial one.
  - **Student ids:** new ids also consider stored registrations, so they never repeat after a restart or a demo reset.
- `scripts/deploy_aca.sh`:
  - The `accounts` container is created private.
  - The API's system identity gets Storage Blob Data Contributor scoped to that container.
  - The env var is set.
- `backend/tests/test_accounts_store.py`: 6 tests with an in-memory fake Blob service:
  - student and department survive a "restart"
  - ids do not repeat
  - a failed save leaves no account
  - unreadable storage pauses registration and never overwrites
  - nothing is stored without an endpoint

## Verification
- `pytest -q`: 344 passed (+6).
- Live: registered `persistence.check@bu.edu` (SYN-24005, 201 = saved), restarted the API revision (new replica 13:33:54Z, only replica running), then signed in again and opened the own record ("Persistence Check"). Note: the start-up "loaded N account(s)" log line is not emitted (accounts load during import, before main.py attaches the log handler); cosmetic only.

## Commit
see git log
