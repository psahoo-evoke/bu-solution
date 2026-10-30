# developer-46 · Approve said "Not saved: API not reachable": duplicate decision id

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) acting as developer |
| Human owner | Sagar (spathur) |
| Trigger | User: "Not saved: The TransferIQ API is not reachable. Start the backend on http://localhost:8000 and try again, correct this once approved, make sure it's live and deploy and correct and push" |

## Finding
- Live API log at the failed Approve: `transferiq.db database error: UniqueViolation: duplicate key value violates unique constraint "decisions_pkey"`, then `POST /api/decisions 503`. The API was up; the database refused the new decision.
- `Store.next_decision_id()` returned *count + 1*. That repeats an id that is already stored whenever the numbering has a gap, or when another app instance saved a decision this one never loaded: during every deploy the old and new revisions run side by side, each with its own memory, and several deploys ran today.
- The page turned every 503 into "The TransferIQ API is not reachable. Start the backend on http://localhost:8000", a developer hint shown to live users, hiding the API's own message.

## Output
- `backend/app/store.py`: `next_decision_id(floor)` = one above the highest `D-<n>` in memory or `floor`.
- `backend/app/db.py`: `max_decision_number()`: highest `D-<n>` in the `decisions` table.
- `backend/app/main.py` (`_save_decision`): the id is taken under the store lock from both (database first), so two saves at once or two app instances never share an id; a database failure there is a 503 with nothing changed. Batch approve uses the same path.
- `frontend/src/app/api/errors.ts`: a 503 with a reason shows the API's text ("The change could not be saved. Please try again."); with no answer from the API, live users read "TransferIQ is not reachable right now. Please try again in a moment."; the localhost hint is kept for developers on localhost only.

## Human review
- Pending.

## Verification
- `pytest -q`: 604 passed (new: ids after a gap and above a higher id in the database; a failing id lookup is a 503 with nothing changed; the existing Postgres test stubs the new lookup).
- `ng test`: 106 passed (new: 503 shows the API's reason, never localhost; status 0 shows the live message off localhost). `ng build`: OK.
- Live check after deploy: see the session.

## Commit
See git log (`developer: decision ids never reuse a stored id; clear save errors (developer-46)`).
