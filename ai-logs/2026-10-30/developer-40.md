# developer-40 · Front page Upload step: student only

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) acting as developer |
| Human owner | Sagar (spathur) |
| Trigger | User: "In front page, under upload - the student uploads the transcripts, syllabi are added as they come in. no need 'or credit staff'" |

## Prompt (summary)
Drop "or credit staff" from the Upload step of "How it works" on the home page.

## Inputs used
- `frontend/src/app/pages/home.html`

## Output
- `home.html`: Upload step now reads "The student uploads the transcript; syllabi are added as they come in."

## Human review
- Pending.

## Verification
- `npx ng test --watch=false`: 11 files, 82 tests passed.

## Commit
See git log (`developer: front page Upload step names only the student (developer-40)`).
