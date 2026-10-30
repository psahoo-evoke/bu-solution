# adoption-02 · Roadmap to production, agent guardrails, README links

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | adoption |
| Tool / model | Solutionauts AI (Claude Code) |
| Human owner | Team lead |
| Trigger | Gap check against the jury scorecard: 7.4 (gaps and roadmap, incl. 10x load) and 3.2 (agent guardrails and sample outputs) |

## Prompt (summary or verbatim)
"ok": go ahead with the roadmap and the agent files.

## Inputs used
- ADR 0007 (capacity), `docs/deck-outline.md` (limits, future scope), README "Known limits", `docs/quality/eval-report.md`
- `backend/app/rules.py`, `backend/app/notify.py`, `backend/app/db.py` (to check reminders, email and persistence before writing them down)
- Discovery log Gap review sheet (Q-037–Q-050)

## Output
- `docs/roadmap.md`: 10 known limitations with evidence; a 5-phase roadmap with effort; what changes at 10x load; reuse for another university
- `agents/{developer,devops,qa}.md` and `.claude/agents/` copies: Scope, Guardrails and Sample outputs (links to real ai-logs)
- `README.md`: link to the roadmap from Known limits; `.claude/agents/` listed next to `agents/`
- Finding: syllabus reminders run every 2 days (max 7), not on the sponsor's day 7 / 21 / 45 schedule (Q-020); recorded as L8

## Human review
- Effort figures are team estimates, labelled as such.

## Verification
- Every relative link in the edited Markdown files resolves
- Claims checked against code: PostgreSQL persistence (`app/db.py`), email via ACS or Logic App (`app/notify.py`), reminder interval (`app/rules.py`), one replica (`infra/modules/containerapp-api.bicep`)

## Commit
See `git log -- docs/roadmap.md`
