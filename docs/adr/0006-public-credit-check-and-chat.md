# ADR 0006 · Public course-credit check and chat (no login)

**Status:** accepted (2026-10-29). This is an exception to ADR 0005 (default deny) and builds on ADR 0001 (rules in code) and ADR 0004 (untrusted input).

**Context.** Prospective transfer students want to know whether a course will transfer *before* they register and upload a transcript. The product owner chose public access, limited to course-equivalency questions, with nothing stored.

**Options.**
- (a) Keep it behind sign-in. Safest, but defeats the purpose.
- (b) A public deterministic form only.
- (c) The form plus a chat in which the model can only call read-only tools. **Chosen.**
- (d) A published static equivalency table. No per-course rules, and it goes stale.

**Decision.**
- **Access.** `guard.PUBLIC` is an exact `(method, path)` allowlist, public in every auth mode:
  - `GET /credit-check/schools` and `GET /credit-check/courses?school=` (catalog courses for the form picker; code, title, credits only)
  - `POST /credit-check`
  - `POST /credit-chat`

  In the contract these routes are `security: []`, and `tests/test_roles.py` checks that the contract and the allowlist stay identical. Request bodies are capped at 64 KB, and the models reject unknown fields.
- **What it can reveal:**
  - catalog data, plus **reusable, non-holdout** decisions (`rules.lookup_public`, which filters `reusable` explicitly)
  - **never**:
    - per-student decisions
    - holdout decisions
    - student records
    - courses known only from a student's transcript upload (no catalog `program_area`)
    - syllabi uploaded for those courses
- **Rules:**
  - Per-course rules use the evaluation's own code: `rules.no_credit_reason` for R01-R06, then R07, R08, R10/R11 and R13. A parity test runs every seeded transcript line through both paths.
  - Without a grade, a decided result says it assumes C or better.
  - An R11 same-year conflict shows the newest decision, as the evaluation does, with a caveat that the department is confirming it.
  - Record-wide rules (R12, R14-R17, R19) are returned as caveats, not applied.
- **Estimates.** An undecided course gets at most a *preliminary* estimate, always labelled "not a promise of credit" (R22). A course typed in by the caller is ranked without entering the shared model cache, and the offline cache is bounded.
- **Chat:**
  - The model may only call `check_course` and `list_schools`.
  - The browser holds the conversation. Each reply carries an HMAC `signature` (key `TRANSFERIQ_CHAT_SECRET`, or a random per-process key), and an assistant turn reaches the model only when correctly signed, so the model keeps its own context ("Did you mean Northeastern?" → "yes"). If any assistant turn is unsigned or edited, all assistant turns are dropped and the student's earlier turns are sent as one context message. User turns are sanitised (ADR 0004).
  - Partial input: a school given in part that matches exactly one catalog school is used, and the reply says which ("NE" → Northeastern). A partial course code ("CS", "cs 30", "3000") returns up to 6 matching *catalog* courses as suggestions, never courses known only from uploads, and the model asks which one is meant.
  - The **result cards** come from `results` and are the source of truth.
  - The reply text is checked after NFKC normalisation and with invisible characters removed. It is replaced by a plain summary when it:
    - names a BU code other than a *decided* result (estimate candidates may not be named)
    - promises or guarantees credit
    - says "transfers as" or "already decided" with no decided result
    - states a unit or credit number the results do not contain
  - If the student states a grade and the model drops it from the lookup, the server adds it.
- **Cost and abuse:**
  - 20 requests per minute per client.
  - 40 model calls per hour per client.
  - 300 model calls per hour globally.
  - 4 concurrent chat turns.
  - Per chat turn: at most 2 tool rounds, 4 lookups and 1 estimate; the last model call may not call tools; one 45 s deadline per turn.
  - If the budget runs out mid-turn, the facts already looked up are still returned.
  - The client key is the **right-most public** `X-Forwarded-For` hop (the one our ingress appended), so hops a client prepends are ignored.
- **Unavailable AI.** Without Azure OpenAI the chat returns 503 and the page switches to the form. A model failure returns 502. The form always works, offline if needed.

**Consequences and accepted risks (demo):**
- With several replicas and no shared `TRANSFERIQ_CHAT_SECRET`, a reply signed by one replica is not accepted by another, so that turn falls back to context-only history. Set the secret (Key Vault) when deploying.
- Limits are kept in memory per replica, so the real budget is the configured number × replicas (max 2).
- The API ingress is external, so callers can skip nginx. They are still keyed on their own address, but there is no WAF.
- The check works as a public existence oracle for *catalog* courses and their reusable decisions. That is intended: these are the same facts every student sees.
- The model cost ceiling is ultimately the Azure OpenAI deployment quota.

**Revisit before production, or when real student data replaces synthetic data:**
- Edge rate limiting and WAF (Front Door or APIM).
- Shared counters (Redis or Postgres).
- An internal-only API ingress behind the web app.
- A token-based cost budget.
- Monitoring of `grounded=false` rates.
