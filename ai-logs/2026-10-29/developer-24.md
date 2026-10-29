# developer-24 · Prompt experiment: a broader definition of "covered" (rejected, reverted)

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (+ qa: evaluation) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | Follow-up from developer-23: on 4 held-out misses, Search ranks the recorded BU course first but gpt-4.1-mini scores it at 17–50% overlap. The human said "ok" to looking into it. |

## Prompt (summary or verbatim)
Find out why the model scores recorded equivalents so low, and try a fix without weakening the wrong-credit gate.

## Inputs used
- `backend/app/matcher.py` (`SYSTEM_PROMPT`, `build_prompt`), `app/evaluation.py`, the 70 train and 30 holdout decisions
- Model input and answer for NEU ECON 2706 compared with CAS EC 240

## Output
- **Cause:** ECON 2706 and CAS EC 240 cover the same 8 topics, but each outcome pairs a topic with a different verb ("Use labor supply…" vs "Explain the core ideas of labor supply"). The model counted only word-for-word matches: 1/6 = 17%. The prompt doesn't define "covered", and it sends BU outcomes but not BU topics.
- **Tried:** a `SYSTEM_PROMPT` paragraph saying "covered = same subject matter at a comparable level; wording and verbs need not match; never from the title alone", plus BU `topics` in each candidate.
- **Method:** changes were compared on the 70 TRAIN decisions; the 30 holdout decisions were scored once at the end.

| Set | Prompt | Top-1 | Strict | Wrong credit |
| --- | --- | --- | --- | --- |
| Train (70) | current | 62.9% | 30.0% | 4.3% |
| Train (70) | new, run 1 | 60.0% | 38.6% | 1.4% |
| Train (70) | new, run 2 | 55.7% | 38.6% | 2.9% |
| Holdout (30) | current (developer-23) | 86.7% | 40.0% | 0.0% |
| Holdout (30) | new, single run | 90.0% | 30.0% | **6.7%, fails the ≤2% gate** |

- On train, the new prompt raised overlap scores for recorded equivalents (strict 6 → 13 of 37).
- On holdout it caused 2 wrong-credit suggestions:
  - PSYC 3709: the evaluator recorded Elective at 38%; the new prompt suggested Equivalent CAS PS 310 at 83%
  - MATH-UA 235: recorded Equivalent CAS MA 213; the new prompt suggested Equivalent CAS EC 203 (economics) at 83%
- **Decision: rejected and reverted.** `matcher.py` is back to the committed version; no code change remains.
- The holdout set has now been used to score this prompt variant. Further prompt work should be judged on train only, with the holdout kept for a final check.
- Ideas not tried:
  - add BU topics without the broader rule (tests whether topics alone help)
  - score per outcome with an explicit evidence quote
  - a stronger model (e.g. gpt-4.1) for the 50–79% band only

## Human review
- Pending.

## Verification
- Evaluation runs as in the table, through `app.evaluation.evaluate_holdout`. Train used the same scoring code pointed at `split == "train"`.
- After the revert, `git status` shows no change to `backend/app/matcher.py`.

## Commit
see git log (log only)
