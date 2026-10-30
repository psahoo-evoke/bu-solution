# developer-33 · Review fixes, and why each design decision was taken

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer (backend, contract, ADR, deployment) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Human: "change review, log why decision you took in that way, review, validate and commit if all ok". Reviews: architect-06, security-05 |

## Scope
Commits `42df5c1` (course picker), `c6b024c` (chat UX, signed context, partial matching) and `75197ad` (workbench department and evaluator), reviewed by architect-06 and security-05, then fixed here.

## Decisions and why

### 1. Course picker: `GET /api/credit-check/courses?school=` (42df5c1)
- **Chosen:** a separate public route returning code, title and credits for one school, loaded once per school and offered as type-ahead suggestions. Typing a free code still works.
- **Why:**
  - A strict dropdown would block courses that are not in the catalog yet, and those still deserve a preliminary estimate.
  - A separate route keeps `/credit-check/schools` small.
  - Only code, title and credits are returned, never decisions, so the list cannot be used to bulk-read outcomes.
- **Privacy rule:** courses known only from student uploads (no catalog `program_area`) are never listed. Otherwise the public site would reveal what someone uploaded. The rule now lives in one helper, `credit_check.is_catalog`.
- **Unlisted codes:** the form asks "What does the course cover?" rather than for a title. A live test showed that a title alone gives the ranker nothing to compare.

### 2. Chat context: signed replies (c6b024c, hardened here)
- **The problem:** dropping all browser-sent assistant turns, the security fix of developer-27, made "Did you mean Northeastern?" → "yes" meaningless.
- **Chosen:** the server signs each reply, and only signed assistant turns reach the model. No server-side session store.
- **Why:**
  - The public chat stores nothing (ADR 0006).
  - An HMAC lets the browser hold the conversation without being trusted.
- **Hardened after review (security-05):**
  - The signature covers the reply *and the question it answered* (L-2). A signed reply moved after another question, or into another conversation, is rejected.
  - It binds to the previous question only, not the whole history, because the page trims long conversations to 12 turns; a whole-history binding would break every long chat.
  - Signed turns are sanitised like user turns (M-2). They are genuine server output, but the model, or the summary fallback, can echo what the student typed. Echoed school names and titles are sanitised at the source too.
  - The key is derived with its own label and must be at least 32 characters (L-3). Even if an operator reused the session secret, the chat could never mint session tokens.
  - Malformed signatures get a 422 instead of crashing the check (L-1). The whole conversation is capped at 9,000 characters (L-4). Lone-surrogate text gets a 422, and 422 responses no longer echo submitted values (that echo turned the 422 into a 500 and could repeat private input).
- **Considered, not chosen:** signing a small structured state (resolved school, last suggestions) instead of text. It is more robust against echo but loses the model's own question wording; text plus binding plus sanitising was enough for the demo, and this is written down in ADR 0006.
- **Deployment (architect S3):**
  - `scripts/deploy_aca.sh` creates `chat-secret` once, the same way as the existing `session-secret`.
  - `infra/main.bicep` writes both the chat and session secrets to Key Vault for the replica path. The session secret was missing there too, so portal sign-ins would have broken across replicas.
  - The API warns at startup when the chat secret is missing outside demo mode.

### 3. Partial school names: confirm, never pick (c6b024c, changed here)
- **First version:** one partial match was used automatically, with a "Taking 'NE' to mean …" note.
- **Changed after the architect's blocker B1:**
  - "northeast" could be a Northeast State student, and the model can drop the note.
  - A *decided* result for the wrong school misleads a prospective student.
  - Now only an exact code or name is used; anything partial returns `unknown_school` with suggestions, even a single one ("Did you mean Northeastern University (NEU)? Please confirm the school.").
- **Why this costs nothing:** the signed context makes the confirmation turn cheap ("yes" works), and the quick-check form uses a school list anyway.

### 4. Partial course codes: suggest, never pick (c6b024c, fixed here)
- **Chosen:** up to 6 catalog courses for:
  - a department alone ("CS")
  - a number alone ("3000")
  - the start of a code ("cs 30")
  - a full code not in the catalog
  - a title

  The message says how many more exist. The model must ask; nothing is chosen for the student.
- **Why:** CS 3000 and CS 3001 can transfer differently.
- **Fixed (architect S5):** a department alone matches exactly that department, so "CS" no longer suggests "CSE".
- **Grounding (security M-3):** suggested courses' credits are the other school's credits, not BU units, and never count as a credit claim. BU unit numbers may only come from a decided result or the 68-unit cap. The transfer-claim words were widened (would/could/should get or receive, "worth", "expect", "toward your degree"). "Can transfer" was left out on purpose: "I can check whether it can transfer" is normal. A false hit only swaps in the plain summary, so erring strict is safe.

### 5. Who decided: the verified sign-in, "Name <email>" (75197ad, fixed here)
- **First version:** portal mode recorded the account's display name from the session.
- **Fixed (architect S1, S2; security M-1):**
  - Entra mode, the production mode, still recorded the typed name. The guard now passes a verified `identity` (token `name` and `preferred_username` / `upn` / `oid`) in both portal and Entra mode.
  - Decisions record `"Name <email>"`, because display names repeat ("Transfer Evaluator" for every seeded evaluator) and a self-registered account picks its own.
  - Outside demo mode, a request with no verified identity is refused (401).
  - Demo mode keeps the typed name, since its role header is self-asserted anyway, and now refuses an empty one (422).
  - `evaluator` is therefore optional in the contract (N5).
- **Why a separate `identity`** instead of reusing the portal `user`: `user` drives portal record scoping (a student sees only their own record, a department its own courses). Setting it in Entra mode would silently change Entra scoping.
- **Not done** (recorded in the ADR 0005 amendment): a separate actor column in `audit_log`, and the actor for postings. The audit entry's `after` record already carries the verified evaluator.

### 6. Workbench UX (developer-31, developer-32; already committed)
- The department is fixed for department accounts because the API already enforces it.
- "Deciding as" shows the identity the server records.
- Colour is never the only cue: the syllabus chips include words, and the confidence meter has its number.

## Other changes in this commit
- **Contract v0.5.0** (`openapi.yaml`, `main.py`, `guard.py`, `test_roles.py`):
  - `evaluator` optional
  - `suggestions` and `school_suggestions` described for all cases, with `required` on school suggestion items
  - `ChatTurn.signature` pattern
  - 9,000-character cap on the conversation
- **ADR 0006:** signature binding, key derivation, confirm-never-pick schools, suggestion credits.
- **ADR 0005:** amended with how the decision-maker is recorded.
- **Order (N4):** the course code is validated before the school is resolved.

## Not changed
- N3: a title-only estimate is not separately labelled; it is still marked preliminary.
- N6: no cap on the number of assistant turns beyond the 9,000-character cap.

## Human review
- The human asked for the review and the rationale. Deployment: running `scripts/deploy_aca.sh` again creates the chat secret once.

## Verification
- `pytest -q backend`: 502 passed. New and changed tests:
  - a partial school is offered, never used (4 inputs × 3 courses)
  - "CS" vs "CSE"; title suggestions; an invalid code gives 422 for any school; echoed input is sanitised
  - signed context kept; edited, spliced and other-key replies dropped; an echoed injection is sanitised
  - malformed signatures, lone surrogates and oversized conversations give 422
  - four credit-claim replies are not grounded
  - Entra and portal record `"Name <email>"`; demo mode needs a typed name
- `npm test`: 73 passed. `ng build --configuration production`: OK.
- `bash -n scripts/deploy_aca.sh`: OK. `infra/main.bicep` is compiled by CI (`ci.yml`, `az bicep build`); `az` is not installed locally.
- Live, real gpt-4.1-mini, signed out (`cc_partial.mjs`):
  - "Can I transfer a course from NE?" → "Do you mean Northeastern University (NEU)?"
  - "yes" → asks for the NEU course
  - "cs 30" → suggests CS 3000; clicking it gives "Needs evaluation"
  - quick check "cs 36" → CS 3650, then "Already decided"
  - no console errors
