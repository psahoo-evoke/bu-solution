# TransferIQ web (Angular)

Angular 22 single-page app for the TransferIQ demo (EvoHack 2026, synthetic data only).
It is built against `docs/api/openapi.yaml` and talks to the FastAPI backend under `/api`.

## Screens

| Route | Screen | Typical demo role |
| --- | --- | --- |
| `/student/:id` (default `SYN-24001`, Maya) | Student status: secured, pending and no-credit totals, courses grouped by term with a status chip (plain words + BU code T/TX/TP/TS/TM), BU course, units, next step, flags, transcript and per-course syllabus upload | Student / Advisor |
| `/review` | Evaluator workbench (CreditStaff read-only; Evaluator/Department decide): queue with department filter and > 90% batch approval; detail pane with top-3 BU candidates (overlap %, tier, outcomes covered vs missing), past decisions, injection warning, "preliminary – not decidable" banner, decision form (Equivalent / Elective TR code / No credit, reason code, reusable) and a timer against the 2-minute target | Evaluator / Department |
| `/evaluation` | Matcher quality: top-1 candidate agreement vs the 80% gate, with strict agreement and deferrals beside it, wrongly suggested credit vs the 2% gate, engine, per-tier table | anyone |
| `/registrar` | Post approved courses (`POST /api/postings`: approved → posted/secured), MyBU CSV download (with preview) and demo reset | Registrar / CreditStaff |

The **Demo role** switcher in the top bar sets the `X-Demo-Role` header on every `/api` call (see `src/app/api/role.interceptor.ts`). In production this is replaced by an Entra ID token.

If the API is unreachable, the app shows an "API offline" banner and per-page error banners with Retry, not a blank page.

## Run with the backend

```bash
# 1. Backend (from the repo root), served on http://localhost:8000
cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8000

# 2. Frontend, in another terminal
cd frontend
npm ci
npm start            # ng serve on http://localhost:4200, proxies /api -> http://localhost:8000 (proxy.conf.json)
```

Open http://localhost:4200. It redirects to Maya's status page.

## Approved vs posted (contract v0.3.0)

An evaluator approval does not secure credit yet. The student sees the line as **Approved – awaiting posting** (TP), and it counts in the pending total. The pending total shows how much of it is approved. After the Registrar posts it on `/registrar`, the line becomes secured (T). The app never claims reminder emails were sent: it says "Reminders scheduled for days 7, 21 and 45 (email sending not enabled in this prototype)".

## Build

```bash
npm run build        # output: dist/transferiq-web/browser (deployed as static files)
```

In a deployed environment the SPA and API must share an origin, or the host must route `/api` to the backend (for example with an Azure Static Web Apps linked backend or a reverse proxy). The client always calls the relative path `/api`.

`public/staticwebapp.config.json` is copied into the build output. It sets the SPA `navigationFallback` (deep links like `/review` work, `/api/*` and static files excluded) and security headers: CSP (`script-src 'self'`, `connect-src 'self'`, `frame-ancestors 'none'`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`. The CSP has no API origin because Azure Static Web Apps' linked backend serves `/api` from the same origin. If the API is ever called cross-origin, add its origin to `connect-src`. The production build turns off critical-CSS inlining (`angular.json` → `optimization.styles.inlineCritical: false`) so `index.html` has no inline script. `style-src` still needs `'unsafe-inline'` for Angular component styles.

## Tests

```bash
npm test             # unit tests: Vitest + jsdom via `ng test --watch=false`, headless, no browser needed
```

End-to-end demo flow (Playwright) in `e2e/demo.spec.ts`. It needs the backend and `npm start` running:

```bash
npx playwright install chromium   # once
npm run e2e
# or reuse an installed Chromium:
CHROME_BIN=/path/to/chrome npm run e2e
# against another host:
E2E_BASE_URL=https://example npm run e2e
```

The e2e flow calls `POST /api/demo/reset` first, decides `NYU|PSYCH-UA 10` and resets again at the end.

## Layout

```
src/app/
  api/        models.ts (OpenAPI schemas), api.service.ts (one method per operation),
              role.service.ts + role.interceptor.ts (X-Demo-Role), permissions.ts (x-roles), errors.ts
  shared/     status chip, error banner, helpers (term grouping, TR elective code)
  pages/      student-status, review, evaluation, registrar
```

Reason codes for the decision form are loaded from `GET /api/reason-codes`.

## Roles (contract v0.2.0, default deny)

`src/app/api/permissions.ts` mirrors `x-roles` from `docs/api/openapi.yaml`. The UI hides or disables actions the current role can't use and says which role to switch to (for example "Switch role to Evaluator or Department to decide."). The server still enforces the roles: a missing role returns 401 and a wrong role returns 403, and both are shown as role guidance. The default role on first load is Student, which can use the student page.
