# developer-31 · Workbench: the department and the evaluator name come from the signed-in account

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer (backend + frontend) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Human (screenshots of the workbench): "auto select the department", then "fix this also name of evaluator from db" |

## Prompt (summary)
Two fields on the evaluator workbench ignored who is signed in:
- **Department dropdown:** a department user had to pick their department, although the API already limits them to it (`main.py` `review_queue`).
- **"Evaluator name":** a free-text box defaulting to "Demo Evaluator". The API stored whatever the browser sent as `decided_by`, so a decision could be recorded under anyone's name.

Cases:
- **Portal department account:** fixed to its own department, and decides as its own account name.
- **Portal staff** (Evaluator, CreditStaff): the "All departments" picker stays; decides as its account name.
- **Demo mode** (no accounts): the picker and the typed name stay.

## Output
- **Backend** (`main.py`): new `_decided_by(request, typed)`. In portal mode, `POST /decisions` and `POST /decisions/batch` record the signed-in account's name, taken from the session (issued at login from the account store, the PostgreSQL `portal_accounts` table for registered users); the `evaluator` field the browser sends is ignored. Demo mode keeps the typed name.
- **Contract:** the descriptions of `DecisionInput.evaluator` and the batch `evaluator` say so (field shapes unchanged).
- **Frontend:**
  - `review.ts`:
    - `ownDepartment` (the account's department when the role is Department) is used by `loadQueue`, so the first request already asks for `?department=Computer Science`.
    - `evaluator` is the signed-in user's name, or the typed name in demo mode.
  - `review.html`:
    - department account: the dropdown becomes a fixed "Department: Computer Science" label
    - signed in: "Evaluator name" becomes a fixed "Deciding as <name>"
  - `styles.scss`: `.dept-fixed` and `.evaluator-fixed` styles.

## Human review
- Requested from the screenshots.

## Verification
- `pytest -q backend`: 485 passed. New: a portal decision and a batch record the account's name ("Transfer Evaluator", "Biology Department") even when the body says "Someone Else".
- `npm test`: 73 passed. New and extended:
  - a department account loads with its department, with no picker and no name box
  - demo staff keep the picker and the name box
- `ng build --configuration production`: OK.
- Live, portal mode (`dept_queue.mjs`, `evaluator_name.mjs`; `.shots/dept-queue.png`, `.shots/evaluator-name-*.png`); no decision was saved live, so the database is unchanged:
  - `computerscience.dept@bu.edu`: first queue request `?department=Computer%20Science`, 6 CS courses; "Deciding as Computer Science Department"
  - `evaluator@bu.edu`: "Deciding as Transfer Evaluator"
  - no console errors
