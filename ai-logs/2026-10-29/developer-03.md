# developer-03 · Entra ID sign-in with app roles (Student, Department, …)

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (backend + frontend) + devops (nginx, deploy script, infra docs) |
| Tool / model | Claude Code (Opus 5.5) |
| Human owner | Sagar (spathur) |
| Trigger | User: "I have added Entra ID credentials in .env, make sure ROLE should work for student and department inside our application" |

## Prompt (summary)
Roles must come from Microsoft Entra ID (the app registration Hackathon-AI-F-TheSolutionauts), not from the demo switcher.

## Inputs used
- `backend/app/guard.py` (role table, entra mode previously failed closed), the frontend role service and interceptor
- App registration client id and tenant id (ids only). The client secret in `.env` is not used.

## Output
- `backend/app/guard.py`, entra mode:
  - Validates the Entra access token with PyJWT: RS256 signature from the tenant JWKS, issuer (v1 or v2), audience (client id or `api://` form), expiry, tenant.
  - Roles come from the `roles` claim. `X-Demo-Role` only selects the active role among those (403 otherwise); the default is the first role in ALL_ROLES order.
  - The verified role is written back for the routes (audit actor).
  - With no role the API returns 403; with no or a bad token, 401.
  - The route permission table is unchanged.
- `backend/requirements.txt`: added `PyJWT==2.15.1`.
- `backend/tests/test_entra.py`: 14 tests with real RS256 tokens.
- Frontend:
  - `api/auth.service.ts` (MSAL `@azure/msal-browser@5.25.1`, loaded only in entra mode, redirect flow, sessionStorage)
  - `api/role.service.ts`: the dropdown lists only the assigned roles
  - `api/role.interceptor.ts`: adds the bearer token
  - `app.config.ts`: an app initializer
  - `app.html` / `app.ts`: Sign in, Sign out and a "No TransferIQ role assigned" screen
  - `api/errors.ts`: 401/403 sign-in messages, and a 502 now shows the API detail
  - `public/auth-config.json`: demo for dev
  - `api/role.service.spec.ts`: 4 tests
- Container:
  - nginx serves `/auth-config.json` from env (`AUTH_MODE`, `ENTRA_*`, ids only).
  - Security headers moved to `nginx/security-headers.conf` and included in every location. **This fixes a bug**: the headers were not sent, because nginx drops server-level `add_header` in a location that has its own.
  - The CSP allows `login.microsoftonline.com` (connect-src and frame-src), also in `staticwebapp.config.json`.
- `scripts/deploy_aca.sh`: `ENTRA_CLIENT_ID` + `ENTRA_TENANT_ID` turn on entra mode for both apps; without them, demo mode.
- `infra/README.md` ("Entra ID sign-in" section) and `infra/main.bicep`: the description no longer says "fails closed".

## Human review
- Pending. The app registration still needs the app roles, the SPA redirect URIs and the user role assignments. A Graph CLI re-login was blocked by Conditional Access (InteractionRequired).
- Note: an earlier masking command printed the `.env` client secret into the session output (the value was on its own line). It is not used by the app. Recommend rotating it.

## Verification
- `pytest -q`: 321 passed. `ng test`: 29 passed. `ng build --configuration production`: OK.
- Deployed in demo mode (sign-in not enabled until the app registration is configured).

## Commit
see git log
