# TransferIQ — AI co-pilot for transfer credit evaluation

EvoHack 2026 · Boston University problem statement · team THE SOLUTIONAUTS

**AI recommends, rules compute, evaluators decide.** TransferIQ pre-matches every transfer course, gives students a live view of secured vs pending credit, and hands department evaluators an evidence-backed recommendation. The AI never posts credit.

## Built by role agents, every run logged
| Where | What |
| --- | --- |
| [`.claude/agents/`](.claude/agents/) | 8 role agents: BA/Discovery, Synthetic Data, Architect, Developer, QA, Security, DevOps, Adoption |
| [`ai-logs/`](ai-logs/README.md) | One log per agent run (prompt, output, human review, verification, commit) — index in `ai-logs/README.md` |
| [`CLAUDE.md`](CLAUDE.md) | Working agreement: which role owns what, mandatory logging |
| `git log` | One commit per agent run, message `<agent>: <what> (<log id>)` |

## Map
| Path | Owner role | Contents |
| --- | --- | --- |
| `docs/discovery/` | BA | Sponsor discovery log + what we learned |
| `docs/stories.md` | BA | 12 user stories with acceptance criteria |
| `docs/architecture.md`, `docs/adr/`, `docs/api/openapi.yaml` | Architect | Architecture, 5 ADRs, API contract v0.3.0 |
| `data/synthetic/`, `scripts/synthetic/` | Synthetic Data | NU/NYU-based test data, transcripts, syllabi, generator |
| `backend/` | Developer + QA | FastAPI, rules engine R01–R24, matcher, 301 tests, eval |
| `frontend/` | Developer | Angular: student status, evaluator workbench, evaluation, registrar |
| `infra/`, `.github/` | DevOps | Bicep (Azure), CI with AI-log check, OIDC deploy |
| `docs/security/` | Security | Threat model, checklist, review + re-review |
| `docs/adoption/`, `docs/deck-outline.md`, `docs/demo-runbook.md` | Adoption | FAQ, quick-start, release notes, deck outline, demo runbook |
| `docs/quality/eval-report.md` | QA | Matcher evaluation on 30 held-out decisions |

## Run locally
```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8000
cd frontend && npm ci && npm start   # http://localhost:4200, proxies /api to :8000
cd backend && pytest -q && python eval/run_eval.py
```
All data is synthetic. Tests and the demo run offline (no Azure keys needed).
