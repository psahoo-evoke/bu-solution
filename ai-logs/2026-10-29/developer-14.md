# developer-14 · Persist all changing data in PostgreSQL (bu-solution-pg / butransfer)

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (backend) + devops (deploy, firewall) + architect (schema.sql aligned with the live database) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | Sagar (spathur) |
| Trigger | User added PostgreSQL credentials to `.env` (not committed). Asked, the owner chose: all changing data in PostgreSQL, and add the developer IP to the firewall. |

## Findings
- The database already held the seed data model: 150 BU courses, 194 external courses, 100 decisions (70 train / 30 holdout), 56 transcript lines, 4 students, 12 syllabi. The runtime tables were empty.
- `backend/db/schema.sql` was behind the live database: it was missing `postings`, `decisions.overlap_pct`, syllabus `source_file`/`seed_state`/`extracted_text`, extra student columns. It is now aligned with the live database.
- Firewall: rules `transferiq-dev-spathur` (103.183.203.20) and `transferiq-dev-spathur-2` (43.228.92.79) were added for local development (two egress IPs). The office network later stopped reaching port 5432 again.

## Output
- `backend/app/db.py` (new; `psycopg[binary]==3.2.13`):
  - load the Store from the tables
  - write-through: transcript upload, syllabus, decisions + decision_scope, postings, audit (best-effort), portal accounts and new students
  - `reseed()` for an empty database and for demo reset
  - `ensure_schema()` adds the `portal_accounts` table
  - `POSTGRES_SCHEMA` for tests
- `backend/app/store.py`: with `POSTGRES_HOST` set, the store loads from PostgreSQL (rules and reason codes still from the CSVs); reset re-seeds the database. Without it, nothing changes (CSV, in memory).
- `backend/app/main.py`: every mutation writes to the database before memory; a failed write gives 503 with nothing changed.
- `backend/app/accounts.py`: accounts come from `portal_accounts`. The one account stored earlier in Blob Storage is copied over once.
- `scripts/deploy_aca.sh`: `PG_HOST`/`PG_DB`/`PG_USER`/`PG_PASSWORD`. The password goes into Container Apps secret `postgres-password` (never printed).
- `infra/README.md`: env row. `tests/conftest.py`: `POSTGRES_HOST` unset, so CI stays offline.

## Verification
- `pytest -q` (database off): 365 passed.
- Integration test against the real server in a throw-away schema (created and dropped): 19/20 checks passed:
  - seeding: counts and every student's evaluation identical to the CSVs
  - transcript, syllabus, one-off + batch decisions and postings through the API, then a fresh load (= restart): identical evaluations, postings, decision scope, audit entries
  - a registered student signs in after a restart
  - demo reset back to the seed, registered student kept
  - The 1 failure was ground-truth number formatting (0.8750 vs 0.875; the app does not read it). Fixed. The re-run could not connect from the office network (port 5432 timing out).

## Commit
see git log
