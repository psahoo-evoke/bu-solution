# developer-08 · Remove the top-bar Sign in link (portal mode)

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (frontend) |
| Tool / model | Claude Code (Opus 5.5) |
| Human owner | Sagar (spathur) |
| Trigger | User: "in application top signin, remove as its not happening anything" |

## Output
- `frontend/src/app/app.html`: when signed out in portal mode, the top bar shows no Sign in link. It only pointed to `/`, so on the home page it did nothing. Students and departments sign in from the Student View / Department View cards.
- The Entra-mode top-bar Sign in (Microsoft redirect) is unchanged.
- Commit `e64a7b6`.

## Verification
- `ng build --configuration production`: OK. `ng test`: 49 passed.
- Deployed in portal mode (see the deploy run that follows this log).

## Commit
`e64a7b6` (change) + this log
