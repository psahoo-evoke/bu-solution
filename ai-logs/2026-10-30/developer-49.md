# developer-49 · portal_accounts: widen the role rule, table as the only account store

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer |
| Tool / model | Claude Code (Sonnet 5.5) |
| Human owner | psahoo (user) |
| Trigger | "fix the table rule, and operate everything from table no memory" |

## Output
- `portal_accounts.role` rule now allows every role (`db.ACCOUNT_ROLES`, equal to `guard.ALL_ROLES`); `seeded` column added; `_migrate_portal_accounts` widens an existing table's rule and adds the column (idempotent, runs from `ensure_schema`).
- PostgreSQL mode: demo accounts are rows (seeded = true, inserted/refreshed at start-up by `sync_seeded_accounts`); sign-in, registration, duplicate check, session check and `registered_student_email` read or write the table every time; the in-memory registry stays empty. Session role/name come from the row.
- No database (tests, local): unchanged in-memory registry (+ optional Blob copy).
- Tests: tests/test_accounts_db.py (fake table with the same primary key and role rule).

## Verification
- backend pytest: 669 passed.
- NOT verified against a real PostgreSQL: the new SQL (alter table / pg_get_constraintdef / on conflict / unique-violation mapping) has only been read, not run. Needs a run on a throw-away schema (POSTGRES_SCHEMA) before commit.

## Commit
Not committed yet (see Verification).

## Later in the same run
- Staff registration: POST /api/auth/register/staff (role + staff invite code from TRANSFERIQ_STAFF_INVITE_CODE, default `bu-staff`, empty = off; 10 tries per client per 10 min), "New staff? Register" on /login/staff, home page link.
- Each role sees only its own pages: PAGE_ROLES + pageGuard, nav per role, no Home once signed in, /students/summary now Advisor and FinancialAid only (CreditStaff removed).
- Verification: backend pytest 681 passed; frontend 139 tests passed and production build OK; browser checks of staff registration and of every role's nav and URL access.
- Still NOT run against a real PostgreSQL: the portal_accounts migration and table-backed account code (committed at the user's request, "ok commit"). First start-up against the real database should be watched.

## Commit
`developer: portal_accounts as the only account store, staff registration, role-only pages`

## Follow-up: first start-up against the real PostgreSQL (2026-10-30)
- Backend started from the committed code with backend/.env loaded: start-up succeeded.
- Read-only checks afterwards: the role rule now lists all seven roles; the `seeded` column exists; 15 demo accounts are rows with seeded = true; the 15 accounts registered earlier (10 students, 5 departments) are kept with seeded = false; the real student's account is present and answers "Incorrect password" to a wrong password; advisor, financialaid and registrar demo accounts sign in; `staff_registration` is on.
- This closes the "not run against a real PostgreSQL" gap above. The information_schema query listed each column twice, so another schema in the database also has a portal_accounts table (not touched by this change).
