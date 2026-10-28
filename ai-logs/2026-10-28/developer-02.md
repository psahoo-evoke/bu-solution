# developer-02 · Angular front end (student status, evaluator workbench, evaluation, registrar)

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | developer |
| Tool / model | Claude subagent (general-purpose) acting as developer |
| Human owner | Front-end dev |
| Trigger | Orchestrator: "Build `frontend/` in Angular against docs/api/openapi.yaml" (backend built in parallel by another developer run) |

## Prompt (summary)
Create `frontend/` with the Angular CLI (app name `transferiq-web`, output `dist/transferiq-web/browser`), a `/api` → `http://localhost:8000` proxy, a hand-written typed API client, an `X-Demo-Role` interceptor driven by a top-bar role switcher, and four screens: student status `/student/:id`, evaluator workbench `/review`, evaluation `/evaluation`, registrar `/registrar`. Accessible plain-SCSS UI with a "Synthetic data – EvoHack 2026" badge, graceful API-down handling, unit tests, a Playwright demo spec and a README. Do not touch `backend/`, `infra/`, `.github/`; do not commit.

## Inputs used
- `CLAUDE.md`, `.claude/agents/developer.md`
- `docs/api/openapi.yaml` (the contract), `docs/stories.md` (US-01..US-12), `docs/architecture.md`
- `data/synthetic/seed/students.csv`, `transcript_lines_expected.csv`, `reason_codes.csv`
- The parallel backend (`backend/app/main.py`), run locally only to smoke-test the UI; not modified

## Output
- Angular CLI **22.2.5**, Angular framework **22.2.3**, TypeScript 6.0.3, Vitest 5.0.5 + jsdom, @playwright/test 1.64.1. All versions pinned exactly in `frontend/package.json`; `package-lock.json` committed, `node_modules` ignored.
- `frontend/proxy.conf.json`; `angular.json` serve uses it, so `npm start` proxies `/api`
- `frontend/src/app/api/`: `models.ts` (all OpenAPI schemas + reason codes copied verbatim from the seed CSV), `api.service.ts` (one method per operation, ext_id URL-encoded), `role.service.ts`, `role.interceptor.ts`, `errors.ts`
- `frontend/src/app/shared/`: status chip (words + BU code, so colour is never the only signal), error banner, helpers (term grouping, TR elective code)
- `frontend/src/app/pages/`:
  - `student-status`: student picker (SYN-24001 default), totals bar Secured / Pending / No credit (+ 68-unit cap meter), courses grouped by term, status chip, BU course, units (+ "if approved"), next step, flags, reason, transcript upload and per-course syllabus upload (for maybe / pending lines)
  - `review`: queue with department filter, > 90% batch checkbox list + "Approve batch", detail with AI suggestion and engine, top-3 candidates (overlap meter, tier, covered vs missing side by side), past decisions, injection warning banner, "Preliminary – not decidable" banner (submit disabled), decision form (Approve equivalent / Elective TR code / No credit, reason code select filtered by decision, reusable toggle, catalog year, note), and a live timer against the 2:00 target
  - `evaluation`: top-1 agreement vs 80% gate, wrong-credit rate vs 2% gate, engine, generic per-tier table
  - `registrar`: MyBU CSV download (with preview), demo reset
- App shell: top nav, role switcher, synthetic-data badge, skip link, global "API offline" banner from `/api/health`
- Tests: `src/app/app.spec.ts`, `api/api.service.spec.ts`, `shared/status.spec.ts`, `pages/student-status.spec.ts`
- `frontend/e2e/demo.spec.ts` + `frontend/playwright.config.ts` (`npm run e2e`; `CHROME_BIN` optional)
- `frontend/README.md`

### Key decisions
- Signals + standalone components, zoneless default of Angular 22; lazy-loaded routes; no UI kit (plain SCSS in `styles.scss`).
- Rates in `/evaluation/metrics` are accepted as fractions (0–1) or percentages; the backend currently sends fractions.
- The batch list shows only items with `batch_eligible` and `confidence_pct > 90` (R21: strictly above 90%).
- The decision form is disabled when the recommendation is preliminary or the syllabus is not complete (US-03, US-05).
- Reason codes are copied into the client because the contract has no reason-code endpoint (possible contract addition for the architect).
- No credit math in the client: units, totals and status codes are shown as the API returns them (ADR 0001).

## Human review
- Pending review by the front-end dev.

## Verification
- `npx ng build` (production): **success, no warnings**. Initial bundle 294 kB raw / 80 kB transfer; output at `frontend/dist/transferiq-web/browser`.
- `npm test` (`ng test --watch=false`, Vitest + jsdom, headless): **4 files, 13 tests passed**.
- Playwright `e2e/demo.spec.ts` against the parallel backend (uvicorn :8000) + `ng serve` (:4200) using the preinstalled Chromium (`CHROME_BIN=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`): **5/5 passed**. The bundled Playwright 1.64.1 expects a newer browser build, so `npx playwright install chromium` is needed when `CHROME_BIN` is not set.
- Manual screenshots of student status, workbench and evaluation pages checked for layout, then the servers were stopped.

## Not done / gaps
- Not checked with a screen reader. Keyboard and focus styles were added but not audited.
- The injection banner and batch approval were not exercised end to end: the current seed has no queue item above 90%, and the e2e flow does not open ECON-UA 266.
- No Entra ID login. The demo role header only.
- Did not run `scripts/build_log_index.py`, because this run was told not to edit `ai-logs/README.md`. The orchestrator should run it.

## Commit
see git log
