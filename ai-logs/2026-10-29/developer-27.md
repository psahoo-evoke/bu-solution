# developer-27 · Fix the architect-05 and security-04 findings on the public credit check and chat

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer + architect (contract, ADR) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Human: "you should use architect and review agent for this change". Reviews: architect-05, security-04 |

## Prompt (summary)
Fix what the two reviews found in developer-26 before committing.

## Output
- **Grounding** (B1, H2; `credit_chat.py`):
  - The reply is normalised (NFKC, Unicode format characters removed) and BU codes are matched in any spelling.
  - Only *decided* results may be named; estimate candidates may not.
  - Promises ("guarantee", "definitely", …), "transfers as" or "already decided" without a decided result, and unit or credit numbers not in the results all switch the reply to the deterministic summary.
  - The prompt now says not to name candidates for undecided courses.
- **Forged history** (M1, S11): only user turns are sent to the model; client-sent assistant turns are dropped.
- **Cost** (H1, S7, M3, L4, N4):
  - Per-client AI budget (`AI_PER_IP`, 40 per hour) checked before the global one (`ratelimit.ai_call`).
  - Per chat turn: at most 2 tool rounds and 4 lookups, 1 preliminary estimate and a 45 s deadline.
  - The last model call gets `tool_choice="none"`. Tool calls are truncated before they enter the conversation, so every call has a response.
  - At most 4 concurrent chat turns (429 otherwise).
  - A budget running out mid-turn still returns the facts.
  - Model call timeout is 20 s.
- **Rate-limit key** (M2, S8): the key is the right-most *public* `X-Forwarded-For` hop, so prepended hops are ignored. At most 10,000 keys, with O(1) work per request.
- **Rules parity** (S4, S5):
  - New `rules.no_credit_reason` (R01-R06) is shared by `eligibility` and the public check.
  - New `rules.lookup_public` filters reusable decisions explicitly.
  - An R11 same-year conflict now adds a "department is confirming, may change" caveat.
  - New parity test over every seeded transcript line. It immediately caught the conflict case, NEU BIOL 2703.
- **Exposure** (S6, L2, L3): courses known only from an upload (no catalog `program_area`) are treated as unknown, and their syllabi are never used. Unexpected exceptions reach the model as a generic error.
- **Caches** (S12): a typed-in course is ranked with `recommend(..., cache=False)`. The offline ranking cache is bounded to 4096 entries.
- **Requests** (L1): public routes have a 64 KB body cap (413) in `guard.py`, through a shared `_capped` helper used by the upload routes too. The public models use `extra="forbid"`.
- **Contract** (S1-S3):
  - `openapi.yaml` is now 0.4.0, with `CreditSchool`, `CreditCheckInput` (patterns, maxLength, OpenAPI 3.0 `exclusiveMinimum`) and a complete `CreditCheckResult` with `required`.
  - New `ChatTurn`, `CreditChatInput` and `CreditChatReply` schemas, plus shared `RateLimited` (with the Retry-After header) and `PublicInvalid` (both 422 shapes) responses, and 413s.
  - The info text describes the public allowlist.
  - `test_roles.py` asserts that the contract's `security: []` operations equal `guard.PUBLIC` (minus `/auth/*`, which is not in the contract yet).
- **Docs:**
  - new `docs/adr/0006-public-credit-check-and-chat.md`
  - ADR 0005 amended
  - threat model §3b (STRIDE) and residual risk 6
  - architecture module table
- **Frontend:** the interceptor matches the three exact public URLs (L5, N2).

## Not changed (documented as accepted demo risks in ADR 0006)
- Per-replica in-memory counters.
- External API ingress with no WAF.
- Edge rate limiting.
- A token-based budget.
- The `_CODE_RE` vs `EXT_ID_RE` difference (N3). Upload-only codes are private now anyway.

## Human review
- The human chose to run both reviews. Deployment items (internal ingress, edge limits) need the POD's decision.

## Verification
- `pytest -q backend`: 472 passed. New tests:
  - 9 test functions in `test_credit_chat.py` and 5 in `test_credit_check.py`
  - the contract/allowlist test in `test_roles.py`
- `npm test`: 68 passed. `ng build --configuration production`: OK.
- Live run against the real gpt-4.1-mini, signed out, all correct:
  - decided course: "already decided", assumes C or better
  - C-: not transferable
  - undecided with B+: "possible matches … preliminary estimate", with no BU code named
  - unknown school: asks again
  - injection: ignored
  - poem: declined
  - NEU BIOL 2703: decided elective, "department is confirming … may change"
