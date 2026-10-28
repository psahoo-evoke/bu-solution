# architect-02 · Repo structure, agent roles, API contract and ADRs

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | architect |
| Tool / model | Claude (Cowork) |
| Human owner | Tech lead |
| Trigger | "everything should be logged and built with agent roles" |

## Prompt (summary)
Create the repo skeleton so every later change is made by a named role agent and logged; define the contract the developer agents build to.

## Output
- `.claude/agents/*.md` — 8 role agents (tools, inputs, outputs, rules, mandatory log step)
- `CLAUDE.md` working agreement; `ai-logs/TEMPLATE.md`, `ai-logs/README.md`, `scripts/build_log_index.py`
- `docs/api/openapi.yaml` — 13 endpoints (evaluation, transcripts, syllabus, recommendation, review queue, decisions, batch, MyBU CSV, metrics, rules, demo reset)
- `docs/architecture.md` (mermaid), `docs/data-model.md`
- ADRs: 0001 rules in code, 0002 own equivalency table + CSV, 0003 offline matcher fallback, 0004 syllabus is untrusted
- Synthetic data + generator moved into `data/` and `scripts/synthetic/`

## Key decisions
- Demo auth via `X-Demo-Role` header, Entra ID roles in production
- `ext_id = SCHOOL|CODE` as the external course key

## Human review
- Pending review by the tech lead

## Verification
- OpenAPI parsed with a YAML loader (see commit)

## Commit
see `git log -- docs/api/openapi.yaml`
