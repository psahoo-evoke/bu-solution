# adoption-01 · Rename the agent folder, name the assistant, rewrite README around the problem statement

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | adoption (README, docs) + devops (CI comment, scripts) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | Sagar (spathur) |
| Trigger | User asked: no mention of the AI tool's folder or file names in git, give the assistant its own name, and make README.md clearly explain the problem statement |

## Output
- **Renamed:** the 8 role definitions moved from the hidden tool folder to [`agents/`](../../agents/). The working agreement is now [`AGENTS.md`](../../AGENTS.md). Every link is updated: `README.md`, `ai-logs/README.md`, `.github/workflows/ci.yml`, `scripts/check_ai_logs.sh`, `backend/app/store.py`, `docs/deck-outline.md`, `docs/security/threat-model.md`, the earlier log entries.
- **Assistant name:** **Solutionauts AI**. AI-log "Tool / model" fields and `ai-logs/TEMPLATE.md` now read "Solutionauts AI (Cowork)", "Solutionauts AI (CLI)" or "Solutionauts AI subagent acting as <role>".
- **`README.md` rewritten around the BU problem statement:**
  1. The problem, with the sponsor estimates.
  2. The success test.
  3. The solution: 4 steps, what each user sees, guardrails.
  4. Measured results (from `docs/quality/eval-report.md`, quoting top-1 together with strict agreement).
  5. Try it, with the sample accounts.
  6. Architecture.
  7. Run locally.
  8. How we built it and the repo map.
  9. Known limits.

## Not changed
- Git history: earlier commit messages and earlier file versions are unchanged. Rewriting history would need a force-push to shared branches; it was offered, not done.

## Verification
- `git grep -i` for the old tool and vendor names: 0 matches in tracked files.
- README claims checked against the sources: R20 (`rules.csv`), ADR 0001 and 0004, the eval-report numbers, the sponsor-answers numbers.
- `scripts/check_ai_logs.sh`: run on this commit range (see commit).

## Commit
see git log
