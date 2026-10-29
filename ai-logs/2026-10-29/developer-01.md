# developer-01 · Remove "synthetic data" wording from the UI

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer |
| Tool / model | Claude Code (Opus 5.5) acting as developer |
| Human owner | Sagar (spathur) |
| Trigger | User: "in UI not mention Synthetic data" |

## Prompt (summary)
The deployed UI must not mention synthetic data.

## Inputs used
- `frontend/src` (grep for "synthetic"), `frontend/e2e/demo.spec.ts`

## Output
- `app.html`:
  - removed the header badge "Synthetic data – EvoHack 2026"
  - removed the footer sentence "All people and records are synthetic."
- `index.html`: removed "(EvoHack 2026, synthetic data)" from the meta description.
- `api/errors.ts`: the 404 message no longer mentions the synthetic data set.
- `pages/registrar.html` and `.ts`: the reset text now says "original data".
- `styles.scss`: removed the now unused `.badge--synthetic`.
- Tests:
  - `app.spec.ts` now asserts that no "synthetic" wording appears.
  - `e2e/demo.spec.ts` has its assertions updated.
- Not changed:
  - The data itself is still synthetic (CLAUDE.md hard rule).
  - Student IDs such as `SYN-24001` come from the seed data and still appear in URLs.
  - Code comments and docs still say "synthetic".

## Human review
- Pending.

## Verification
- `npx ng build --configuration production`: OK.
- `npx ng test --watch=false`: 6 files, 25 tests passed.

## Commit
see git log
