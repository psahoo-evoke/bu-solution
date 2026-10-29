# developer-06 · Fix "You are not signed in or your session has expired"

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (frontend) + devops (deploy script) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | Sagar (spathur) |
| Trigger | User: "check again, showing Problem: You are not signed in or your session has expired. Sign in again. correct and run and deploy" |

## Diagnosis
- A fresh session on the live site was fine: student, department and registrar clicking through every page gave no 4xx.
- The message means the API answered "Sign in required", i.e. a request without a token. The likely cause is a tab opened before the portal deploy, still running the demo-mode SPA: it sends only `X-Demo-Role`, which portal mode rejects.
- Second cause: the session-signing key was random per API process, so every deploy or restart invalidated all sessions.

## Output
- `api/auth.service.ts`: `handleUnauthorized()`:
  - In portal mode it signs out locally and sets a notice ("Your session has expired. Please sign in again.").
  - In demo mode it re-reads `/auth-config.json` and reloads the page if the site has switched to sign-in.
- `api/role.interceptor.ts`: every 401 (also in demo mode) goes through `handleUnauthorized()`; portal mode then navigates home.
- `pages/home.html`: shows the notice, with Dismiss. `api/errors.ts`: the "session has expired" detail now maps to the sign-in message.
- `scripts/deploy_aca.sh`: portal mode creates a Container Apps secret `session-secret` once and sets `TRANSFERIQ_SESSION_SECRET=secretref:session-secret`. The value is never printed or committed.
- Tests: 2 new (expired session leaves a notice; a demo tab does not reload while the site is still in demo mode).

## Verification
- `ng test`: 49 passed. Playwright e2e (demo, local): 7 passed. `ng build`: OK.
- Live, in Chrome:
  - A simulated stale demo-mode tab got 401 "Sign in required", reloaded itself and showed the sign-in home page.
  - Signed in as Aisha, restarted the API revision (a new replica was created at 13:19:35Z), reloaded: still signed in on `/student/SYN-24003`, with no 401.

## Commit
see git log
