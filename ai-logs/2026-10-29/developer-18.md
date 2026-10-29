# developer-18 · Student page: a "Start here" panel for new students; transcript upload becomes secondary

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Screenshot of a newly registered student's header: "what is best changes we can make on this part as per UX". The human accepted the recommended items 1 (empty state) and 3 (button that changes after the first upload). |

## Prompt (summary or verbatim)
Improve the student status header for a student who has no courses yet, without adding new student fields to the page.

## Inputs used
- `frontend/src/app/pages/student-status.html`, `student-status.ts`, `student-status.spec.ts`, `frontend/src/styles.scss`
- `backend/app/guard.py` (`MAX_UPLOAD_BYTES` = 10 MB, quoted in the help text)

## Output
- `student-status.ts`: new `hasCourses` computed.
- `student-status.html`:
  - **No courses, and the role can upload:** the button leaves the student card. A `.start-panel` card shows "Step 1 · Start here: upload your transcript", two sentences on what happens next, the primary **Upload transcript (PDF)** button, and "PDF, up to 10 MB. One transcript per school; you can add more later."
  - **Courses on file:** the card keeps a secondary (white) **Add another transcript (PDF)** button.
  - Read-only roles see the read-only note as before.
  - The Secured / Pending / No credit totals are hidden while there are no courses, and the old "No courses on file yet. Upload a transcript to start." line now appears only for read-only roles.
- `styles.scss`: `.start-panel`. On screens up to 600 px the button is full width.
- `student-status.spec.ts`: two tests, one for the new-student panel (no totals) and one for the secondary button once courses exist.
- Not done (recommended, not accepted yet): a four-step progress tracker, labelled details line, and a merged title and name card.

## Human review
- Pending.

## Verification
- `npm test`: 56 passed.
- Signed in as Maya in portal mode and took screenshots of her normal page and the same page with the evaluation API stubbed to no courses, on desktop (1400 px) and phone (390 px) widths. No page errors.

## Commit
see git log
