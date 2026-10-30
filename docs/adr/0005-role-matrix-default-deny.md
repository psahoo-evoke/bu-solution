# ADR 0005 · Default-deny role matrix

**Status:** accepted (2026-10-28) — resolves security-01 findings 2 and 3

**Amended (2026-10-29).** The exceptions are an explicit allowlist, `guard.PUBLIC`: `/health`, `/auth/*` (portal sign-in and registration), and the public credit check and chat (ADR 0006). `tests/test_roles.py` checks that the allowlist matches the operations marked `security: []` in the contract.

**Decision.** Every route except `/health` requires a valid role (missing/unknown → 401, wrong role → 403). Allowed roles per operation are in `x-roles` in `docs/api/openapi.yaml` (v0.2.0). Choices on the proposals in `docs/security/checklist.md`:
- `GET /students`: all roles in demo mode (the student picker needs it); own record only in Entra mode.
- `GET /exports/mybu.csv`: Registrar **and** CreditStaff — the brief has the Credit Evaluation Department posting results.
- `POST /decisions/batch`: Evaluator and Department.
- `POST /demo/reset`: CreditStaff and Registrar (the Registrar screen hosts the reset button); disabled in Entra mode.
- New `GET /reason-codes` (all roles) so the front end stops hard-coding them.
