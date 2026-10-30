# Evaluator quick-start (one page)

**AI recommends, rules compute, you decide.** The AI never posts credit. Only your decision does.

## 1. Open the queue

1. In the top bar, set **Demo role** to **Evaluator** (or **Department**). *CreditStaff* can see the queue read-only. In production your role comes from your BU sign-in.
2. Click **Evaluator workbench**.
3. Filter by department if you want. Each row shows the course, the students who have it, the syllabus state and the AI's top BU candidate.

Only "maybe" courses are here. Ineligible courses (grade below C, Pass/Fail, one-credit, remedial, PE, ROTC, internship, research, non-accredited school) and existing equivalencies are already handled by the rules.

**Ready to decide** lists only courses with a complete syllabus. A course whose syllabus is missing (TS) or incomplete (TM) is the student's step, not yours: it sits in the collapsed **Waiting for a syllabus** list below the queue, with no confidence score, and cannot be decided (the API refuses it too). Open one to see the syllabus request and reminders, or to send a request. It moves to **Ready to decide** as soon as a complete syllabus is uploaded.

## 2. Read the comparison

Click a course. A **timer** starts (target: under 2:00).

- **AI suggestion** and the engine that made it (`offline-fallback` in this prototype).
- **BU candidates**: the top 3 BU courses, each with an **overlap %**, a **tier**, and the learning outcomes **covered** and **missing**, side by side.
- **Past decisions on this course**, so you stay consistent with earlier evaluators.

## 3. Tiers (from the learning-outcome overlap)

| Overlap | Tier | What it means |
| --- | --- | --- |
| **≥ 80 %** | Equivalent | The AI proposes the BU course. You confirm or change it. |
| **50–79 %** | Evaluator decides | The AI does **not** pick. Look at what is missing and decide. |
| **< 50 %** | Elective | Proposed as an elective (BU code ending in `TR`) if the course is eligible. |

## 4. Decide

Choose one: **Approve equivalent** (pick a BU candidate above), **Elective (TR code)** (for example `CAS PS 2TR`) or **No credit** (posts as `TFRGEN NOCRDT`, 0 units, TX). Then press the submit button (**Approve equivalent**, **Approve as elective** or **Record no credit**).

- Pick a **reason code**. The list is filtered by your decision:
  - Equivalent: `EQ-CONTENT` (≥ 80 %), `EQ-EVALUATOR` (partial overlap, you judged it equivalent)
  - Elective: `EL-PARTIAL`, `EL-LOWOVERLAP`, `EL-NOEQUIV`, `EL-DUPLICATE`, `EL-RESIDENCY`
  - No credit: `NC-…` codes (grade, pass/fail, one-credit, remedial, PE, vocational, ROTC, internship, research, accreditation)
- **Reusable** is on by default. Leave it on, and the next student with this course gets your decision instantly. Turn it off for a one-off (for example, an unusual section).
- Catalog year and note are optional.

Units are always computed by the rules (the student's units, quarter credits × 2/3). You never type units.

The server checks every decision. Equivalent needs a real BU course, Elective a TR code (`… 1TR` or `… 2TR`), No credit `TFRGEN NOCRDT`, and the reason code must fit the decision. If it doesn't, the decision is refused and nothing is saved.

## 5. Batch approval (> 90 %)

The **Batch approve (confidence above 90%)** list shows only items with confidence **strictly above 90 %**, a complete syllabus and no injection warning. Approving a batch still saves **one logged decision per course**. If any item does not qualify, the whole batch is refused and nothing is saved.

## 6. Warnings you must read

- **"Warning: possible prompt injection."** The syllabus contains text aimed at the AI (for example "ignore previous instructions"). That text was removed before scoring, and the tier did **not** change. Read the source document yourself. Flagged items are never batch-eligible.
- **"Preliminary – not decidable."** There is no complete syllabus, so the suggestion comes from the catalog description only. The decision buttons are disabled. The student is asked for the syllabus (TS) or more material (TM), with reminders on days 7, 21 and 45.

## 7. After you decide

Your approval posts the credit straight away: the student sees **T "Posted – credit secured"**, and the course appears in the MyBU-style CSV. If your decision is reusable, other students with the same course match and are posted at once too. (If a posting cannot be saved, the course shows **TP "Approved – awaiting posting"** until the Registrar presses **Post approved courses**.) Every decision and posting is logged with the role, the time, the AI suggestion and whether you agreed with it.
