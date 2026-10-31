# developer-48 · Advisor caseload and Financial aid pages

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer (also touched the contract: new role and endpoint; architect review pending) |
| Tool / model | Claude Code (Sonnet 5.5) |
| Human owner | psahoo (user) |
| Trigger | "create pages for academic advisors and the financial aid team, end-to-end with the API" |

## Prompt (summary or verbatim)
Create pages for academic advisors and the financial aid team, with API integration where needed.

## Inputs used
- docs/api/openapi.yaml (v0.8.0), backend guard/accounts/rules/main, frontend role, nav and portal sign-in code. The Advisor role already existed; FinancialAid did not.

## Output
- Role `FinancialAid`: guard, contract, portal staff account `financialaid@bu.edu` (same demo password as the other staff), sign-in list, role-home, nav, Entra app-role doc in infra/README.md (an administrator must add the `FinancialAid` app role in Entra).
- `GET /api/students/summary` (Advisor, FinancialAid, CreditStaff): one row per student, no contact data, no AI call. Credit math stays in rules.py (`summarize_student`, `transfer_deadline`; R19 deadline now shared).
- Pages `/advisor` (caseload, attention filter, search, sort, expandable open courses with what to tell the student) and `/financial-aid` (confirmed vs provisional, could-reach vs the 68-unit cap, CSV of the rows on screen with formula guard). Advisor now lands on /advisor after sign-in (was the student page).
- Tests: backend/tests/test_summary.py, two portal tests in test_portal.py, frontend shared/summary.spec.ts.
- Decision: no award amounts or invented financial data; the aid view shows credit status only.

## Human review
- Pending. Contract change needs the architect's review (AGENTS.md).

## Verification
- backend pytest: 657 passed. Frontend: 120 tests passed, production build OK.
- Live check in portal mode on spare ports: signed in as financialaid@bu.edu and advisor@bu.edu, each landed on its page with the right nav link, 4 students listed, no console errors.

## Commit
See git log (developer: advisor caseload and financial aid pages).
