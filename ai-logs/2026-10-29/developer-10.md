# developer-10 · Remove the "AI recommends, rules compute, evaluators decide" wording everywhere in the app

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (frontend) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | Sagar (spathur) |
| Trigger | User: the wording "AI recommends, rules compute, evaluators decide. The AI never posts credit." must not appear anywhere inside the application |

## Output
- `pages/home.html`, the hero:
  - Removed the bold sentence "The AI recommends, the rules compute, people decide."
  - Removed the three principle boxes ("AI recommends and never posts credit", "Rules compute…", "People decide…").
  - `home.scss`: the hero is now one column; the unused `.hero__pillars` and `.pill-ico` styles are removed.
- `pages/review.html`: the workbench subtitle no longer ends with "The AI recommends; you decide."
- (The footer sentence was removed in developer-09.)
- A search of `frontend/src` (not tests) for the wording finds 0 matches.

## Verification
- `ng build --configuration production`: OK. `ng test`: 49 passed.
- Live check after the deploy: see the summary.

## Commit
see git log
