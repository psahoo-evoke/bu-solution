# developer-32 · Evaluator workbench UX

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer (frontend) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Human (screenshot of the workbench): "beautify as per best UX experience" |

## Problems seen
- "Deciding as bu.computer1" floated in the far corner with no context.
- An empty "Batch approve" box took space just to say there was nothing to approve.
- Queue cards: every card repeated the fixed department, and syllabus state and confidence were plain grey text that could not be scanned.
- The empty detail panel was one grey sentence.

## Output (decisions and why)
- **Identity badge**
  - What: initials avatar, "Deciding as", the name, and the role · department.
  - Why: the evaluator sees who the decision will be recorded as, the same identity the server records (developer-31).
- **Batch box**
  - What: when nothing is above 90%, it becomes a one-line note ("…none can be batch-approved. Decide them one by one."). With eligible items it is unchanged.
  - Why: the rule (R21) is still explained, without the empty box.
- **Queue cards**
  - What:
    - The syllabus state is a coloured chip (complete green, incomplete amber, missing red), always with its word, because colour must not be the only cue.
    - "Top match CAS CS 112 · 50% overlap", then a small confidence meter labelled "50% confidence". The meter is green above 90% (the batch threshold), amber from 60%, red below.
    - The department is shown on each card only when the queue spans departments (staff "All departments"), not when it is fixed.
    - Visible keyboard focus, and a clearer selected state.
  - Why: a scan should tell which courses are blocked on a syllabus and which are close to batch-ready.
- **Empty detail panel**
  - What: "6 courses are waiting for a decision", three stat tiles (students waiting, courses that need a complete syllabus, average AI confidence), the 2:00 target, and an **Open first course** button. An empty queue shows "Nothing to review" with what makes courses appear.
  - Why: the panel is useful before any course is opened.
- **Narrow screens**
  - What: the detail stacks below the queue, so opening a course scrolls it into view.
  - Why: on a phone the student details would otherwise be out of sight.
- **Not changed:** the detail panel (AI comparison, timer, decision form), all API calls, permissions and data.

## Human review
- Requested from the screenshot.

## Verification
- `npm test`: 73 passed. `ng build --configuration production`: OK.
- Live, portal mode (`workbench_ux.mjs`, `.shots/wb-*.png`):
  - CS department account, desktop 1440:
    - identity "CS · Deciding as Computer Science Department · Department · Computer Science"
    - cards without the repeated department
    - stats: 2 students, 5 need a complete syllabus, 66% average confidence
    - "Open first course" opened NEU CS 2100 with the timer running
  - `evaluator@bu.edu`: cards show the department (Psychology).
  - Phone 390: badge full width, cards readable, stats stacked.
  - No console errors.
