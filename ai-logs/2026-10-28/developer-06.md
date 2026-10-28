# developer-06 · Front end on contract v0.3.0: approved vs posted, posting step, strict metric, SWA security config (F-01)

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | developer |
| Tool / model | Claude subagent (general-purpose) acting as developer |
| Human owner | Front-end dev |
| Trigger | Orchestrator follow-up after architect-04 (openapi v0.3.0) and security-02 finding F-01 |

## Prompt (summary)
1. Student page: `approved` shows as "Approved – awaiting posting" (TP) and counts as pending, `approved_units` appears in the totals, `posted` is secured (T); reminder wording must not claim emails were sent.
2. Registrar: "Post approved courses" button → `POST /api/postings`, showing the count and the rows posted; keep the CSV.
3. Evaluation: show `strict_agreement` and `deferrals` next to top-1, with an explanation; rename the label to "Top-1 candidate agreement".
4. F-01: `frontend/public/staticwebapp.config.json` with navigation fallback and security headers, copied to the build output.
5. Add `/postings` to `permissions.ts`; add e2e step 8 (approve → TP → post → secured).

Front end only, no commit.

## Inputs used
- `docs/api/openapi.yaml` v0.3.0 (commit 921a69b), `ai-logs/2026-10-28/architect-04.md`
- `docs/security/review-2026-10-28.md` (F-01 recommendation), `infra/README.md` (SWA linked backend, so `/api` is same-origin)
- The parallel backend, run locally (read-only) for the e2e run

## Output
- `src/app/api/models.ts`:
  - `CourseState` adds `posted`; totals add `approved_units`.
  - `Metrics` adds `strict_agreement` and `deferrals`.
  - New `PostingInput` and `PostingResult` types.
- `api/api.service.ts`: `postApproved()` → `POST /api/postings`.
- `api/permissions.ts`: `post` allowed for Registrar and CreditStaff (matrix is now v0.3.0).
- `shared/status.ts`:
  - `displayStatus()`: an approved line shows as "Approved – awaiting posting" with TP, whatever code the API sends.
  - `nextStepText()`: replaces any "Reminders … 7, 21 and 45" sentence with "Reminders scheduled for days 7, 21 and 45 (email sending not enabled in this prototype)". The backend still sends "Reminders are sent…", so the client rewrites it; the backend text should change too.
  - `BU_COURSE_PATTERN`: the contract's `bu_course` pattern.
  - `electiveCodeFor()`: clamps to 1TR or 2TR, the only levels the pattern allows (so CAS CH 373 → CAS CH 2TR).
- `pages/student-status.*`:
  - Status chip uses `displayStatus`.
  - Approved lines note "counts as pending until posted".
  - The Pending total shows "incl. X approved, awaiting posting".
  - The next-step text uses the new reminder wording.
- `pages/registrar.*`:
  - Student selector shared by all actions.
  - New "Post approved courses" card, role-gated with a hint.
  - Result card "Posted just now: N courses" with the posted rows as a table.
  - CSV download, preview and reset kept.
- `pages/evaluation.*`:
  - Card renamed "Top-1 candidate agreement".
  - Strict agreement and "Deferrals to evaluator (X of n)" shown beside it, with the line "Strict counts a correct deferral to the evaluator (50–79% band) as a miss…".
- `pages/review.*`: the decide button stays disabled until `bu_course` matches the contract pattern. The elective code field shows the expected format and sets `aria-invalid`. This complements the server-side F-02 validation.
- `public/staticwebapp.config.json` (new):
  - `navigationFallback` → `/index.html`, excluding `/api/*` and static file types.
  - Global headers: CSP `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy`.
- `angular.json`: production `optimization.styles.inlineCritical: false`. Critical-CSS inlining injected an inline `<script>`, which `script-src 'self'` blocks. The built `index.html` now has only `<script src="main-*.js" type="module">`.
- Tests:
  - `shared/status.spec.ts`: approved → TP, reminder wording, `bu_course` pattern, 2TR clamp.
  - `pages/student-status.spec.ts`: TP chip, "incl. 4 approved", no "Reminders are sent".
  - `api/permissions.spec.ts`: `post` roles.
  - `e2e/demo.spec.ts`: new step "approved course stays pending (TP) until the Registrar posts it, then it is secured (T)"; evaluation step checks the strict and deferrals labels.
- `frontend/README.md`: approved vs posted, SWA config and CSP notes.

### Decision: CSP `connect-src`
`connect-src 'self'` only, with no API-origin placeholder. The infra uses a Static Web Apps linked backend, so `/api` is same-origin. A literal placeholder in JSON would be an invalid source, and it would ship as-is if nobody replaced it. The README says to add the origin if the API is ever called cross-origin.

## Human review
- Pending review by the front-end dev.

## Verification
- `npx ng build`: **success, no warnings**. `dist/transferiq-web/browser/staticwebapp.config.json` is present, and `index.html` has no inline scripts.
- `npm test` (Vitest + jsdom): **6 files, 25 tests passed**.
- CSP check: served the production build with the config's `globalHeaders` and navigation fallback from a small local Node server that proxies `/api` to the backend, then opened all 4 routes as deep links in headless Chromium. All rendered, with **0 CSP violations and 0 console errors**. This is an emulation, not real SWA.
- Backend v0.3.0 was live locally: `POST /api/postings` → 201 `{posted, csv}`, and metrics include `strict_agreement` and `deferrals`.
- Playwright `e2e/demo.spec.ts` against the backend + `ng serve` (`CHROME_BIN` = preinstalled Chromium): **7/7 passed**, including approve → TP → post → T with secured units rising. Servers were stopped afterwards.

## Not done / gaps
- The backend still writes "Reminders are sent on days 7, 21 and 45." in `next_step`. The UI rewrites it, but the backend text should be changed by the backend owner.
- SWA headers were not checked on a real Azure deployment, only emulated locally.
- `style-src 'unsafe-inline'` remains, because Angular component styles need it. Removing it would need a CSP nonce setup.
- Did not run `scripts/build_log_index.py`, because it rewrites `ai-logs/README.md`.

## Commit
see git log
