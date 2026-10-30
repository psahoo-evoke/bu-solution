# security-05 · Security review of the course picker, chat context, partial matching and workbench identity

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | security |
| Tool / model | Solutionauts AI subagent acting as security |
| Human owner | psahoo (POD) |
| Trigger | Human: "change review, log why decision you took in that way, review, validate and commit if all ok" |

## Prompt (summary)
Read-only threat model of `faed214..75197ad`: the new public route, signed chat replies, partial matching, the grounding change, `decided_by`, and the new templates. The tests used the TestClient with an in-memory store; the PostgreSQL database was not touched and no `.env` values were printed.

## Output (findings; no repo files edited by the agent)
No Critical findings.
- **Medium:**
  - M-1 [C]: `decided_by` could be spoofed in Entra mode, and the audit log had no actor identity.
  - M-2 [R]: the server signs text the model was made to echo (and the summary fallback echoed the raw school string); signed turns reached the model unsanitised.
  - M-3 [R]: suggested courses' credits let "You would receive 4 BU credits" pass the grounding check.
- **Low:**
  - L-1 [R]: a non-ASCII signature crashed the check (502).
  - L-2 [R]: signed replies could be replayed or spliced into other conversations.
  - L-3 [C]: no key length or domain separation; an operator who reused the session secret would turn the chat into a session-token forgery oracle.
  - L-4 [C]: up to about 16.5k characters of context per request.
  - L-5 [C]: a partial school was resolved automatically.
- **Pre-existing [R]:** a lone surrogate in any chat turn gave a 500.
- **Verified fine:**
  - the new route returns only catalog courses (uploads excluded, no existence oracle), with exact school matching and a rate limit
  - no XSS sinks in `frontend/src`
  - forged or edited turns dropped
  - portal `decided_by` came from the signed session

## Human review
- The human asked for the review; the fixes are in developer-33.

## Verification
- `pytest -q backend`: 485 passed. TestClient probes in the session scratchpad reproduced M-2, M-3, L-1, L-2 and the surrogate 500.
