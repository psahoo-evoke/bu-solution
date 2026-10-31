# architect-07 · Architecture doc brought in line with the code

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | architect |
| Tool / model | Solutionauts AI (Claude Code) acting as architect |
| Human owner | psahoo (POD) |
| Trigger | Human: "provide the architecture component diagram end to end flow, including all", then "ok" to updating `docs/architecture.md` |

## Prompt (summary)
Draw the full component diagram and the end-to-end flow. After the diagrams were shared as a page, update `docs/architecture.md` to match the code.

## Inputs used
- `backend/app/*.py` (module docstrings, routes in `main.py`, role matrix in `guard.py`, env variables)
- `backend/db/schema.sql`, `db.py` (tables)
- `frontend/src/app/app.routes.ts`, `docker-compose.yml`, `infra/README.md`, `.github/workflows/*.yml`
- `data/synthetic/seed/rules.csv`, `docs/adr/*`

## Output
- `docs/architecture.md` rewritten:
  - a component diagram with every backend module, split into domain modules and Azure-facing ones, each Azure-facing module pointing to its one service
  - a 15-step flow for one course
  - tables for sign-in modes and offline fallbacks
  - a deployment summary
- Fixed drift in the old doc:
  - it had no portal accounts, role guard, rate limiter, public chat or in-app notifications
  - reminders were "day 7/21/45"; the code sends one every `TRANSFERIQ_SYLLABUS_REMINDER_DAYS` (default 2)
  - ingest was described as "LLM normalisation"; the code uses pdfplumber, with Document Intelligence for scans only
  - eligibility was given as R01–R07; the code applies R01–R09
- Decision: the API contract was not touched. The doc describes the code and points to `openapi.yaml` and `guard.py` for the full role matrix.

## Human review
- The human approved updating the doc after seeing the diagram page.

## Verification
- Every claim was checked against the files listed above. The CI steps were rechecked against `ci.yml` after a first draft named the wrong steps.
- The Mermaid blocks were not rendered locally: there is no Node or mermaid-cli in this environment. Risky labels are quoted.

## Commit
See the git log entry `architect: architecture doc brought in line with the code`.
