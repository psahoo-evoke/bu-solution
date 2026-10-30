# architect-05 · Review of the public credit check and chat (developer-26)

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | architect |
| Tool / model | Solutionauts AI subagent acting as architect |
| Human owner | psahoo (POD) |
| Trigger | Human: "you should use architect and review agent for this change" |

## Prompt (summary)
Read-only review of the uncommitted developer-26 change. Check:
- whether the contract matches the implementation (shapes, status codes, `x-roles` conventions)
- service boundaries and rules-logic drift from the evaluation
- public data exposure
- operations: replicas, cost, timeouts, outages
- whether an ADR is needed

## Inputs used
- `backend/app/{credit_check,credit_chat,ratelimit,main,guard,rules,matcher}.py`
- `docs/api/openapi.yaml`, `docs/adr/0005-role-matrix-default-deny.md`
- `backend/tests/test_credit_{check,chat}.py`, `test_roles.py`
- `frontend/src/app/api/{models,role.interceptor}.ts`, `frontend/nginx/default.conf.template`, `infra/modules/containerapp-api.bicep`, `backend/Dockerfile`

## Output (findings; no files edited by the agent)
- **Blocker B1:** estimate candidate codes counted as "grounded", so the chat could name an estimate as the outcome.
- **Should fix:**
  - S1/S2: contract drift (missing result fields and `required`, inline chat schemas, undocumented Retry-After and 422 shapes)
  - S3: ADR 0005 and the contract still said "only /health is public"; version not bumped
  - S4: R01-R06 and R13 duplicated; the R11 conflict flag dropped
  - S5: reusable-only filtering was implicit
  - S6: courses known only from an upload were publicly queryable
  - S7: about 16 model calls per chat turn
  - S8: spoofable rate-limit key
  - S9: per-replica counters
  - S10: no turn deadline or concurrency cap
  - S11: client-sent assistant turns not sanitised
  - S12: public estimates evicted the pre-warmed model cache
- **Nice to have:**
  - N1: architecture and threat-model docs don't cover the public routes
  - N2/N5: comments and version strings
  - N3: the code pattern is stricter than `EXT_ID_RE`
  - N4: results were lost when the budget ran out mid-turn
- **Recommended** ADR 0006 and an amendment to ADR 0005.

## Human review
- The human asked for the review; the fixes are in developer-27.

## Verification
- Static review only; the agent had no shell, so it reviewed file contents rather than the git diff.
