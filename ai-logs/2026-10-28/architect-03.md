# architect-03 · Contract v0.2.0: role matrix, reason codes

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | architect |
| Tool / model | Solutionauts AI (Cowork) |
| Human owner | Tech lead |
| Trigger | security-01 findings (missing role checks, export role ambiguity) and developer-02 gap (reason codes hard-coded) |

## Output
- `docs/api/openapi.yaml` v0.2.0: `x-roles` on all 13 role-protected operations, default-deny description, new `GET /reason-codes`
- `docs/adr/0005-role-matrix-default-deny.md` with the decisions on each proposed cell

## Human review
- Pending tech lead review

## Verification
- YAML parsed; 14 paths, 13 operations with `x-roles`

## Commit
see `git log -- docs/api/openapi.yaml`
