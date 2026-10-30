# developer-47 · Reminder loop survives a failed check; a late AI comparison never fills another course

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) acting as developer |
| Human owner | psahoo (POD) |
| Trigger | Code and security review of bu-solution-final; user: "fix 5 and 6" (the two confirmed bugs from that review) |

## Prompt (summary or verbatim)
Fix the two bugs the review confirmed: the syllabus reminder loop dying on its first error, and the evaluator workbench filling the open course's decision form from a late AI comparison for another course.

## Inputs used
- `backend/app/main.py` (`_reminder_loop`), `frontend/src/app/pages/review.ts` (`open`)
- Existing tests: `backend/tests/test_syllabus_requests.py`, `frontend/src/app/pages/review.spec.ts`

## Output
- `backend/app/main.py`: `_reminder_loop` logged through `log`, which does not exist in the module (the logger is `_log`). The `NameError` escaped the `except`, ended the task, and reminders stopped for good after any failed check, with nothing in the log. Now `_log.warning`, so the error is logged and the next hourly check runs. Cancelling (shutdown) still ends the loop.
- `frontend/src/app/pages/review.ts`: the recommendation answer is ignored (success and error) unless its course is still the one open, as the syllabus answer already was. Before: open course A, then B; if A's comparison came back last, B's form was prefilled with A's BU code and Approve posted B with A's code. The API accepts that (any catalogue course is valid), and a decision now posts straight away. A late error for A also cleared B's loading line and showed A's error on B.
- Edge cases covered: late success and late error for a course no longer open; answer after the course was closed (nothing selected); A -> B -> A uses the answer for the open course.

## Human review
- Pending.

## Verification
- New `test_a_failed_reminder_check_does_not_stop_the_hourly_loop`: fails on the old code (`NameError`), passes now.
- New review.spec tests ("a late AI comparison for a course no longer open", 2 tests): both fail on the old `review.ts`, pass now.
- `pytest -q`: 615 passed. `ng test`: 109 passed. `ng build`: OK.

## Commit
See git log (`developer: ... (developer-47)`).
