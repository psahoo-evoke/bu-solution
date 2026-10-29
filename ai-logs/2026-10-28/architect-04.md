# architect-04 · Contract v0.3.0: posting step, approved vs posted, decision validation, strict metric

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | architect |
| Tool / model | Solutionauts AI (Cowork) |
| Human owner | Tech lead |
| Trigger | adoption-01 inconsistencies #1 (student saw approved as secured; sponsor: TP until posting) and #2 (strict agreement not on screen); security-02 F-02 (free-text bu_course) |

## Output (`docs/api/openapi.yaml` v0.3.0)
- New `POST /postings` (Registrar, CreditStaff): approved lines become posted/secured, returns the MyBU rows posted
- `CourseEvaluation.state` adds `posted`; `approved` = awaiting posting, student still sees TP and it counts as pending; totals add `approved_units`
- `DecisionInput.bu_course` pattern + must agree with the decision; `reason_code` must exist and match the decision
- `Metrics` adds `strict_agreement` and `deferrals`, to be shown next to `top1_agreement`

## Human review
- Pending tech lead review

## Verification
- YAML parsed; 15 paths

## Commit
see `git log -- docs/api/openapi.yaml`
