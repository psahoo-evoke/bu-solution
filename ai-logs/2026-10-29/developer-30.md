# developer-30 · Chat keeps its context; partial school and course codes get matches

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (backend + frontend) + architect (contract, ADR) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Human (screenshot): the bot guessed "NE" is Northeastern, but after "yes" and "cs 30" it said "'NE' is not a school in the catalog". "When we pass a partial course code it should understand, or provide matching course codes." |

## Root causes
1. Since developer-27 the model never saw its own earlier replies (browser-held assistant turns can be forged), so "yes" and "cs 30" lost their context.
2. School and course lookups were exact only.

## Edge cases listed first
- **School:**
  - an exact code or name works as before
  - exactly one partial match (start of a code, start of a word in the name, or part of the name) is used, and the message says so
  - several matches, or none, return suggestions
- **Course:**
  - an exact code works as before
  - a partial code ("cs 30", a department "CS", or a number "3000") returns up to 6 *catalog* courses (never upload-only ones) and says how many more exist
  - no automatic choice between, for example, CS 3000 and CS 3001
- **Context:** assistant turns are trusted only when the server signed them; an edited or forged turn means all assistant turns are dropped (the earlier, safe behaviour).

## Output
- `credit_check.py`:
  - `resolve_school` and `course_suggestions` are new.
  - `check_course` uses one partial school match, prefixing the message with "Taking 'NE' to mean Northeastern University (NEU).".
  - New result fields: `school_suggestions` (unknown_school) and `suggestions` (partial or unknown code). The message lists them too ("Did you mean …").
  - A department or number alone is now valid input that returns suggestions.
- `credit_chat.py`:
  - Every reply carries an HMAC `signature` (`TRANSFERIQ_CHAT_SECRET`, or a per-process random key).
  - Correctly signed assistant turns are sent to the model; otherwise the student's earlier turns become one context message.
  - Prompt rule 5: list the suggestions and ask which one is meant.
  - Credit numbers from suggestions are accepted by the grounding check.
- `main.py`: assistant turns may be up to 1500 characters with an optional `signature` (user turns are still capped at 600).
- **Contract:** `suggestions` and `school_suggestions` on `CreditCheckResult`; `ChatTurn.signature`; `CreditChatReply.signature` (required); the `course_code` pattern accepts a department or number alone.
- **ADR 0006:** signed turns, partial input, and the replica caveat (set a shared secret when deploying).
- **Frontend:**
  - suggestions show as chips on result cards: in the chat a click asks about that course or school; in the quick check a click fills in the code and checks it
  - the page sends each reply's signature back with it

## Human review
- Requested from the screenshot. Security note: this brings back assistant turns, but only ones the server signed; forged or edited turns are dropped (tested).

## Verification
- `pytest -q backend`: 484 passed. New:
  - partial school (3 forms), ambiguous school lists, partial course code, department alone ("more"), upload-only courses never suggested
  - signed context reaches the model, an edited signed reply is dropped, suggestion credits stay grounded
- `npm test`: 71 passed (new: the signature is sent back, and a suggestion chip asks about the course). `ng build --configuration production`: OK.
- Live, signed out, real gpt-4.1-mini (`cc_partial.mjs`, shots `.shots/cc-partial-*.png`):
  - "Can I transfer a course from NE?" → "Do you mean Northeastern University (NEU)?"
  - "yes" → asks for the Northeastern course
  - "cs 30" → "Did you mean CS 3000 (Algorithms and Data)?" with a chip; clicking it gives "Needs evaluation" for CS 3000
  - quick check "cs 36" → CS 3650 suggested; clicking it gives "Already decided"
  - no console errors
