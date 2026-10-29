# developer-02 · Store uploaded transcripts and syllabi in Azure Blob Storage

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (backend) + devops (deploy script, infra README) |
| Tool / model | Claude Code (Opus 5.5) |
| Human owner | Sagar (spathur) |
| Trigger | User: "make sure upload of transcripts and syllabus are storing into blob azure" |

## Prompt (summary)
Uploaded transcript and syllabus PDFs must be kept in Azure Blob Storage, not only parsed in memory.

## Inputs used
- `backend/app/main.py` (upload routes), `backend/app/ingest.py` (`azure_credential`)
- `infra/README.md` env contract (`AZURE_STORAGE_*`)
- Existing storage account `stsolutionauts95de2` (container `transcripts` already exists)

## Output
- `backend/app/blob_store.py`:
  - `save_pdf(kind, key, data)` writes to `<container>/<key>/<UTC time>-<id>.pdf` via managed identity (DefaultAzureCredential), with no overwrite and content type `application/pdf`.
  - With no endpoint set it does nothing (ADR 0003).
- `backend/app/main.py`:
  - Both upload routes store the PDF after validation and parsing, before any state change.
  - If the store fails, the route returns 502 and nothing is recorded.
  - A syllabus record's `file` now holds the blob path.
  - The `transferiq` logger now writes to the container log.
- `backend/requirements.txt`: added `azure-storage-blob==12.31.0`.
- `backend/tests/test_blob_store.py`: 6 tests using a fake Blob service. `conftest.py` unsets `AZURE_STORAGE_BLOB_ENDPOINT`.
- `scripts/deploy_aca.sh`: an optional `STORAGE_ACCOUNT` step that:
  - creates the containers if they're missing
  - turns on the API's system-assigned identity
  - grants Storage Blob Data Contributor scoped to each container
  - sets the env vars
- `infra/README.md`: env table and container docs updated.
- Decisions:
  - Writes use the system identity; the user-assigned identity stays pull-only, and `AZURE_CLIENT_ID` is not set.
  - Roles are scoped per container, not per account.
  - Failure is fail-closed (502) so an accepted upload is always stored.
  - Blob metadata has no names (only the student ID or course ID in the path).
- API contract: no request or response shape changed. A 502 on upload is new and not yet documented in `docs/api/openapi.yaml` (architect to add).

## Human review
- Pending.

## Verification
- `pytest -q`: 307 passed (301 existing + 6 new).
- Deployed with `STORAGE_ACCOUNT=stsolutionauts95de2`; see the commit message for the live check.

## Commit
see git log
