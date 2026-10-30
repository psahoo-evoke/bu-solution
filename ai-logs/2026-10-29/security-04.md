# security-04 · Security review of the public credit check and chat (developer-26)

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | security |
| Tool / model | Solutionauts AI subagent acting as security |
| Human owner | psahoo (POD) |
| Trigger | Human: "you should use architect and review agent for this change" |

## Prompt (summary)
Read-only threat model and review of the three public routes. Areas:
- auth bypass through the PUBLIC allowlist and the interceptor
- data leakage: holdout or per-student decisions, PII, the system prompt
- prompt injection and grounding-check bypasses, including forged assistant turns
- cost and abuse: limits, X-Forwarded-For spoofing, body size
- output handling in Angular
- errors, logging and timeouts

No `.env` values printed.

## Inputs used
- `backend/app/{credit_check,credit_chat,ratelimit,main,guard,safety}.py`, `docs/api/openapi.yaml`, the frontend credit-check page and interceptor, nginx template, Dockerfile
- Probe scripts against the TestClient with a scripted model (no Azure calls), kept in the session scratchpad

## Output (findings; no repo files edited by the agent)
- **High:**
  - H1 [reproduced]: one IP could empty the global AI budget (about 20 budget units per request).
  - H2 [reproduced]: the grounding filter was bypassed by lower case, missing spaces, a zero-width space, fullwidth letters, hyphens, or a promise with no code.
- **Medium:**
  - M1 [reproduced]: forged assistant turns reached the model verbatim.
  - M2 [reproduced]: a rotating spoofed X-Forwarded-For bypassed the per-IP limit, and the key purge was O(n).
  - M3: tool-round off-by-one, and truncated tool calls left without responses (would give a 400 from Azure OpenAI).
- **Low:**
  - L1: no body cap on the public JSON routes.
  - L2: courses known only from uploads were enumerable.
  - L3: raw exception text was passed to the model.
  - L4: a chat turn could outlast the proxy timeout.
  - L5: the interceptor regex was broader than the backend allowlist.
- **Verified fine:**
  - exact-match guard (path and method variants all 401)
  - holdout and per-student decisions not revealed
  - no `innerHTML` or `bypassSecurityTrust`
  - user text not logged
  - generic 502 message

## Human review
- The human asked for the review; the fixes are in developer-27.

## Verification
- `pytest -q backend`: 451 passed before the fixes. The probes reproduced H1, H2, M1, M2 and M3 (off-by-one) and L1.
