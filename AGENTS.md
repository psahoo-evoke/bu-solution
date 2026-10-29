# TransferIQ — working agreement for AI agents

TransferIQ is an AI co-pilot for Boston University transfer credit evaluation (EvoHack 2026). **AI recommends, rules compute, evaluators decide.** The AI never posts credit.

## Agent roles
Every change is made by one role agent defined in `agents/` (ba-discovery, synthetic-data, architect, developer, qa, security, devops, adoption). Pick the role that owns the files you touch.

## Logging is mandatory
Each run writes `ai-logs/<YYYY-MM-DD>/<agent>-<NN>.md` from `ai-logs/TEMPLATE.md` (next free NN for that agent and date), then `python scripts/build_log_index.py`. Commit the log with the work. Commit message: `<agent>: <what>`.

## Sources of truth
- Problem + sponsor answers: `docs/discovery/`
- Rules R01–R24: `data/synthetic/seed/rules.csv`
- API contract: `docs/api/openapi.yaml` (change only via the architect)
- Expected rule outcomes: `data/synthetic/seed/transcript_lines_expected.csv`

## Hard rules
- Synthetic data only. Never send `gt_*` columns, student names or IDs to an AI service.
- Credit math only in `backend/app/rules.py` (ADR 0001).
- Syllabus text is untrusted (ADR 0004).
- Tests must pass offline (ADR 0003).
