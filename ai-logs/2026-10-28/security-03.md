# security-03 · Re-review of fixed findings F-01, F-02, F-04, F-06, F-07

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | security |
| Tool / model | Claude subagent (general-purpose) acting as security |
| Human owner | Tech lead |
| Trigger | Orchestrator: "re-test only the five findings the developers addressed; update the review with a dated Re-review section" |

## Prompt (summary)
No commits and no code edits. Re-test F-01 (SWA config), F-02 (decision validation), F-04 (parse time-out), F-06 (server-generated upload names) and F-07 (pinned deps) against `cbad1ed`. Inspect the built frontend, update `docs/security/review-2026-10-28.md` with per-finding status, evidence and new counts.

## Inputs used
- `git diff 6a5e056..HEAD` for `backend/app/{main,guard,store}.py`; `backend/requirements.txt`; `frontend/public/staticwebapp.config.json`; `frontend/angular.json`
- `data/synthetic/seed/{bu_courses,past_decisions,external_courses,reason_codes}.csv` (regression check of the new code patterns)

## Output
- `docs/security/review-2026-10-28.md`: added the "Re-review · 2026-10-28 (security-03)" section and an updated result line.
  - **F-01 resolved** (static evidence; the CSP is not exercised in a real browser).
  - **F-02 resolved.**
  - **F-04 resolved**, with new info finding F-10: timed-out worker threads keep running.
  - **F-06 resolved.**
  - **F-07 partly resolved**: transitive dependencies are not locked.
  - Checklist totals are now 27 pass, 1 fail (5.3 audit log, F-05), 2 N/A.
- Still open: F-03 (Low, accepted risk), F-05 (Low), F-07 (Low, partial), F-08/F-09/F-10 (Info).

## Human review
- Pending. The tech lead should confirm acceptance of F-03 and decide whether F-05/F-07 matter before the demo.

## Verification
- `pytest -q` in `backend/`: 301 passed. `pip-audit -r requirements.txt`: no known vulnerabilities.
- Live uvicorn + curl:
  - Decisions: 7 invalid bodies → 422 (pattern, catalogue, TR code, NOCRDT, reason/decision mismatch, Pending reason) and 3 valid → 201.
  - Parsing: a 30-page PDF parsed in 1.2 s with `/api/health` at ≤ 63 ms throughout; with `TRANSFERIQ_PDF_TIMEOUT_S=0.05` both upload routes → 422 with no traceback.
  - Uploads: the `../../etc/passwd` filename was discarded.
  - New route: `POST /postings` role check (401/403/201 as per x-roles).
- `npx ng build` (frontend) succeeded. `dist/.../browser` contains `staticwebapp.config.json`, the `index.html` has no inline script, and the bundles have no `eval`/`new Function` and no external hosts.
- Not verified: CSP in a browser (Playwright Chromium download blocked by the sandbox proxy) and anything on a deployed SWA/Azure.
- Side effect: `frontend/dist/` was rebuilt locally (it is git-ignored). No tracked files changed apart from the review and this log.

## Commit
see git log
