# developer-41 · UX quick wins for students and department reviewers

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) acting as developer (UI/UX review) |
| Human owner | Sagar (spathur) |
| Trigger | User: "act as UI/ux expert design the application for customer satisfaction and experience". Chose "Build quick wins now", focus Students + Department reviewers |

## Prompt (summary)
Review the student and department screens as a UX expert and build the highest-value improvements without changing how any feature works.

## Inputs used
- `frontend/src/styles.scss`, `app/app.html`, `app/app.ts`, `pages/home.*`, `pages/student-status.*`, `pages/review.*`
- Headless Edge screenshots of the local app (desktop and phone width)

## Findings
- Students: nothing tells them what to do; the syllabus request is one cell in a 7-column table; that table is unusable on a phone; loading is a grey line of text.
- Department: workbench subtitle is jargon ("Maybe courses ..."); no way to find a course in a long queue; the queue scrolls away while reading a long comparison.
- Everyone: when the API is unreachable, customers see a developer message about `localhost:8000`.

## Output
- Student status page
  - "N courses need a syllabus" card at the top listing those courses (only syllabus needed TS / incomplete TM, not "syllabus on file"), and the same rows highlighted in the table.
  - Progress bar and "X% secured · a of b units so far" above the totals.
  - Phone layout: each course becomes a card with labelled values; empty cells are hidden; the Upload syllabus button is full width.
  - Loading shows a spinner panel instead of plain text.
- Evaluator workbench
  - Subtitle: "Courses waiting for your decision, with the AI comparison already done."
  - Search box over the loaded queue (course, title, school, department, top BU code) with "n of m" and a "No course matches" + Clear search state.
  - On desktop the queue stays in view (sticky, own scroll) while the comparison scrolls.
- App shell: off localhost the API-unreachable banner reads "TransferIQ is not reachable right now. Your saved work is safe. Please try again in a moment." with a "Try again" button; localhost keeps the developer hint.
- No API, rule or permission changes.

## Human review
- Pending.

## Verification
- `npx ng test --watch=false`: 11 files, 86 tests passed (new: syllabus to-do + highlighted rows, no to-do when all syllabi are in, progress bar, queue search and no-match state).
- `npx ng build`: succeeded.
- Screenshots checked at desktop and phone width; fixed a phone-layout bug (multi-line cells spilling into the label column) and a wrong to-do entry for a course whose syllabus was already on file.

## Commit
See git log (`developer: UX quick wins for students and department reviewers (developer-41)`).
