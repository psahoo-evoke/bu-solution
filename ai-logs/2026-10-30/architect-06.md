# architect-06 · Review of the course picker, chat context, partial matching and workbench identity

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | architect |
| Tool / model | Solutionauts AI subagent acting as architect |
| Human owner | psahoo (POD) |
| Trigger | Human: "change review, log why decision you took in that way, review, validate and commit if all ok" |

## Prompt (summary)
Read-only review of commits `42df5c1`, `c6b024c` and `75197ad` (diff `faed214..75197ad`):
- the contract against the code
- ADR 0005 and 0006 fit
- whether partial matching can mislead a student
- the signature design
- `decided_by` in every auth mode
- drift and missing tests

## Output (findings; no files edited by the agent)
- **Blocker B1:** a single partial school match was used automatically ("northeast" → Northeastern), so a student from another school could see a *decided* result for the wrong school.
- **Should fix:**
  - S1: `decided_by` was still taken from the client in Entra mode, the production mode.
  - S2: `decided_by` recorded a display name, which is not unique; a self-registered account picks its own.
  - S3: the chat key was not wired for deployment.
  - S4: contract and ADR drift on `suggestions`; `school_suggestions` items lacked `required`; the version was not bumped.
  - S5: "CS" also matched "CSE".
- **Nice to have:**
  - N1: signature not bound to the conversation, and signed turns not sanitised.
  - N2: the "catalog only" rule was written in three places.
  - N3: title-only estimates are not labelled as such.
  - N4: course-code validation came after school resolution.
  - N5: `evaluator` was still required in portal mode.
  - N6: no total cap on the context sent to the model.
- **Missing tests:** Entra identity, partial school never decided, a different signing key, CS vs CSE, title suggestions.

## Human review
- The human asked for the review; the fixes are in developer-33.

## Verification
- Static review of the diff and the current files.
