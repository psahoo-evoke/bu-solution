# developer-29 · Chat UX polish on the public "Will my course transfer?" page

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (frontend, small backend prompt fix) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Human (screenshot of the Ask tab): "beauty this with user experience" |

## Prompt (summary)
Improve the look and usability of the public chat.

Problems seen in the screenshot:
- a large empty gap
- examples that read like a form label
- an oversized resizable textarea, with a faded Send button outside it
- no greeting, no typing feedback, no way to start over
- an easy-to-miss sign-in link

## Output
- `credit-check.html/.scss/.ts`:
  - **Tabs:** icon tabs ("Ask in your words", "Quick check") with proper `tab`/`tabpanel` wiring.
  - **Header:** a chat header ("Transfer credit assistant", "answers come from BU's rules · nothing is stored") with a **New chat** button once a conversation exists.
  - **Greeting:** a welcome message from the assistant, and example questions as pill chips; a fourth example, "Which schools can I ask about?".
  - **Messages:** assistant avatar, user messages right-aligned in BU red, typing dots while waiting (still with reduced motion).
  - **Composer:**
    - one rounded input that grows to about 6 lines with a round send button inside
    - an "Enter to send · Shift+Enter for a new line" hint, hidden on phones
    - a character counter after 450 characters, warning near 600
    - focus returns to the input after each reply or error
  - **Sign-up:** "Register or sign in" is now a callout with a button.
  - **Space:** the fixed minimum height of the message area is gone, so there is no empty gap.
- `credit_chat.py`: since developer-27 only the student's turns reach the model, so a follow-up question made the model answer the earlier question again (seen live). Earlier turns are now sent as one context message ("already answered; context only"), and system prompt rule 5 says to answer only the latest message.

## Human review
- Requested from the screenshot; no new public data or routes.

## Verification
- `pytest -q backend`: 474 passed (the forged-history test now also checks the context message).
- `npm test`: 70 passed (new: New chat clears the conversation and brings the examples back). `ng build --configuration production`: OK.
- Browser, signed out, real gpt-4.1-mini (`cc_chat_ux.mjs`, shots `.shots/cc-ux-*.png`), desktop 1280 and phone 390:
  - empty state, typing dots, a two-question conversation (the follow-up is answered once, without repeating the first)
  - focus back in the input
  - New chat brings back the 4 examples
  - no console errors
