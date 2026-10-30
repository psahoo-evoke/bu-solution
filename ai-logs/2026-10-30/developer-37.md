# developer-37 · No misleading Retry after a refused upload

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer (frontend) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Human (screenshot: "Problem: The request was rejected. This does not look like a transcript: no 'Institution:' line was found. [Retry]"): "is try enabled?" |

## Finding
The Retry button on the student page only reloads the page data (`load()`); it does not repeat the upload. For a refused file it could never help, because the file has to change, and "The request was rejected" is technical wording.

## Decisions and why
- **Retry only where it can help:** when loading the status page failed (network, server), because reloading can fix that.
- **Refused upload** (415 not a PDF, 422 not a transcript or syllabus, 413 too large): no Retry. The message gives the reason and the next step: "This file was not accepted. <reason> Choose the official transcript PDF from your previous school and upload it again." (or "the course syllabus as a PDF").
- **409 already uploaded:** the API's sentence is shown as is.
- **No answer from the service** (status 0 or 5xx) during an upload: "Please upload the file again in a moment". No Retry button, because the browser does not keep the file.
- **The same rules for syllabus uploads**, and for the checks in the page itself before upload (type, empty file, size).
- **Accessibility:** the transcript file inputs had no accessible name; they now have "Upload transcript (PDF)".

## Output
- `pages/student-status.ts`: `errorRetryable`, `uploadFailed()` and `uploadErrorMessage()`.
- `pages/student-status.html`: the banner gets `[retryable]`, and the transcript inputs get an `aria-label`.
- Spec updates.

## Human review
- Asked by the human.

## Verification
- `npm test`: 81 passed. New: a refused upload shows the reason and the next step with no Retry button; `uploadErrorMessage` for 415, 422 (text and list details), 409 and no answer. `ng build --configuration production`: OK.
- Live, portal, `jordan.reyes@bu.edu`, uploading a syllabus PDF as the transcript (`refused_upload.mjs`, `.shots/refused-upload.png`):
  - banner: "This file was not accepted. This does not look like a transcript: no 'Institution:' line was found. Choose the official transcript PDF from your previous school and upload it again."
  - no Retry button; no page errors
  - the upload was refused, so nothing was stored
