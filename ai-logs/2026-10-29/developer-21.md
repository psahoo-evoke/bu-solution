# developer-21 · Loader while a transcript is read

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | "put loader while extracting the transcript" |

## Prompt (summary or verbatim)
Show clearly that the transcript is being read while the upload and extraction run.

## Inputs used
- `frontend/src/app/pages/student-status.html`, `student-status.spec.ts`, `frontend/src/styles.scss`
- Before: only the button text changed to "Reading transcript…", and on a new student's start panel that was easy to miss.

## Output
- `student-status.html`, while `uploadingTranscript()` is true:
  - a spinner sits in the "Add another transcript" button next to "Reading transcript…".
  - a `.loader-panel` card (`role="status"`, `aria-live="polite"`) appears under the student card: a large spinner, "Reading your transcript…" and "Extracting the courses and matching each one to BU credit. This can take up to a minute."
  - for a new student the panel replaces the "Start here" card, so the start panel's button no longer needs a busy state.
  - existing totals and term tables get `.is-stale` (dimmed, not clickable) and `aria-busy="true"`.
- `styles.scss`: `.spinner` (with a `--lg` size), the `spin` animation, `.loader-panel` and `.is-stale`. With reduced motion turned on, the spinner turns more slowly.
- `student-status.spec.ts`: 2 tests, one for the first-transcript loader and one for the dimmed, busy courses with the button spinner.

## Human review
- Pending.

## Verification
- `npm test`: 61 passed.
- Screenshot as Maya in portal mode, with the upload request held and then aborted so nothing was saved: the button spinner, the loader panel and the dimmed courses all appeared, with no page errors.

## Commit
see git log
