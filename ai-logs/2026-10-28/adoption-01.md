# adoption-01 · Student FAQ, evaluator quick-start, release notes, deck outline, demo runbook

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | adoption |
| Tool / model | Solutionauts AI subagent acting as adoption |
| Human owner | Product lead |
| Trigger | Orchestrator: "Adoption agent: student FAQ, evaluator quick-start, release notes, deck outline in the judges' order, demo runbook" |

## Prompt (summary)
Write the adoption docs and the deck outline for the 20-minute demo + 10-minute Q&A, in the judges' order (discovery, solution + architecture, AI agents used, quality, metrics, future scope, live demo). Use only numbers present in the repo, each labelled measured / sponsor estimate / assumption. Include an "AI agents used" slide built from the actual `ai-logs/`, an honest-limits slide and the ROI (2,800 × 12 min = 560 h; ~93 h target; ~467 h returned). Write a click-by-click demo runbook with the role for each step. Do not edit code, other logs or `ai-logs/README.md`. Do not commit.

## Inputs used
- `AGENTS.md`, `agents/adoption.md`, `docs/discovery/sponsor-answers.md`, `docs/stories.md`, `docs/architecture.md`, `docs/quality/eval-report.md`, `docs/security/threat-model.md`, `docs/security/review-2026-10-28.md` (summary)
- All 19 earlier runs in `ai-logs/2026-10-26/` and `ai-logs/2026-10-28/`
- `data/synthetic/seed/test_cases.csv`, `rules.csv`, `reason_codes.csv`, `students.csv`, `syllabi_index.csv`, `transcript_lines_expected.csv`
- Sheet "Demo Scenario" of `data/synthetic/TransferIQ_Synthetic_Data.xlsx` (openpyxl), 8 steps
- `frontend/README.md`, `frontend/e2e/demo.spec.ts`, `frontend/src/app/**/*.html` (labels only), `backend/app/guard.py` (role table)

## Output
- `docs/adoption/student-faq.md`: statuses T / TX / TP / TS / TM, secured vs pending, units and quarter conversion, what to upload and where, reminders day 7/21/45, one-year deadline, departments decide and the AI only suggests, privacy.
- `docs/adoption/evaluator-quickstart.md`: one page on the queue, comparison, tiers, decision form, reason codes, reusable flag, batch > 90 %, injection warning, "Preliminary – not decidable".
- `docs/adoption/release-notes.md`: v0.1, what works, measured quality, what is simulated, known gaps from the logs.
- `docs/deck-outline.md`: 10 slides with timings summing to 20:00 (demo 8:00), every number tagged [M]/[S]/[A], an agents slide (8 roles, 20 runs, owners, outputs, 3 human-override examples), an honest-limits slide, ROI, and a Q&A prep table.
- `docs/demo-runbook.md`: start, rehearse, reset, 5 timed steps with the Demo role for each click, after-demo reset, fallbacks with a curl script.

Key decisions:
- The demo follows the workbook's Demo Scenario, but transcripts are already seeded, so the transcript upload is optional (re-upload is idempotent).
- Batch approval is **explained, not shown**, because no seeded queue item is above 90 %.
- The presenter states strict agreement (60 %) out loud, because the AI evaluation page shows only (a) and (c).
- The FAQ says reminders are shown but not sent in the prototype.

## Human review
- Pending review by the Product lead.

## Verification
- `cd backend && python3 -m pytest -q` → **268 passed** (19.5 s).
- `cd backend && python3 eval/run_eval.py` → (a) 100.0 % (12 deferrals), (b) 60.0 %, (c) 0.0 %, gates met.
- `cd frontend && npm test` → **6 files, 22 tests passed**. Playwright e2e not re-run (cites developer-04: 6/6).
- Walked the runbook against a local uvicorn through the API, with each step's role:
  - Maya's start totals: secured 14.67, pending 8, no credit 0.
  - Queue: 11 items, none batch-eligible, highest confidence 87 %.
  - PSYCH-UA 10: CAS PS 211, 75 %, evaluator decides.
  - PSYCH-UA 25 syllabus upload as Student → TP; the recommendation becomes non-preliminary, CAS PS 231 at 62 %.
  - Decision as Evaluator → 201, `ai_agreed: true`. Liam's PSYCH-UA 10 → T, CAS PS 211, "Approved - awaiting posting". Maya's secured → 18.67.
  - ECON-UA 266: `injection_detected: true`, 62 %.
  - MyBU CSV as Registrar shows the new row.
  - Reset as Evaluator → 403, as Registrar → 204.
- UI labels in the runbook checked against the templates and the e2e spec. A full browser click-through was not done in this run.
- Did not run `scripts/build_log_index.py`, because it rewrites `ai-logs/README.md`, which this run was told not to edit. The orchestrator should run it.

## Commit
not committed (orchestrator commits)
