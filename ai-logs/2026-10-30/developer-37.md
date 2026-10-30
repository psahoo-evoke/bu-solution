# developer-37 · Remove "Other staff" from the front page

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) acting as developer |
| Human owner | Sagar (spathur) |
| Trigger | User: "in front page, dont include this, remove other staff and its content, remove from page" |

## Prompt (summary)
Take the "Other staff" section and everything in it off the home page.

## Inputs used
- `frontend/src/app/pages/home.html`, `home.ts`, `home.scss`

## Output
- `home.html`: removed the "Other staff" section (Evaluator, Credit staff, Registrar, Advisor buttons and the AI evaluation link).
- `home.ts`: removed the `staff` list that fed it.
- `home.scss`: removed the `.staff`, `.staff__list`, `.staff__item` styles.
- The roles and the `/evaluation` route still exist; they are only no longer linked from the front page.

## Human review
- Pending.

## Verification
- `npx ng test --watch=false`: 11 files, 80 tests passed.
- `npx ng build`: succeeded.

## Commit
See git log (`developer: remove Other staff from the front page (developer-37)`).
