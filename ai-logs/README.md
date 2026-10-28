# AI usage logs

Every agent run that produced or changed something in this repo has a log here, one file per run:
`ai-logs/<date>/<agent>-<NN>.md`, written from [TEMPLATE.md](TEMPLATE.md).

Agent roles are defined in [`.claude/agents/`](../.claude/agents/). Each role has a human owner who reviews its output.

| Role | Definition | Human owner |
| --- | --- | --- |
| BA / Discovery | [ba-discovery.md](../.claude/agents/ba-discovery.md) | Product lead |
| Synthetic Data | [synthetic-data.md](../.claude/agents/synthetic-data.md) | Data / QA lead |
| Architect | [architect.md](../.claude/agents/architect.md) | Tech lead |
| Developer | [developer.md](../.claude/agents/developer.md) | Backend + front-end devs |
| QA | [qa.md](../.claude/agents/qa.md) | QA lead |
| Security | [security.md](../.claude/agents/security.md) | Tech lead |
| DevOps | [devops.md](../.claude/agents/devops.md) | Tech lead |
| Adoption | [adoption.md](../.claude/agents/adoption.md) | Product lead |

## Index
<!-- INDEX:START -->
| Date | Run | What | Human owner |
| --- | --- | --- | --- |
| 2026-10-26 | [architect-01](2026-10-26/architect-01.md) | First architecture and 7-day build plan | Tech lead |
| 2026-10-26 | [ba-discovery-01](2026-10-26/ba-discovery-01.md) | Problem framing, scoring map and discovery questions | puspalata sahoo (Product lead) |
| 2026-10-28 | [adoption-01](2026-10-28/adoption-01.md) | Student FAQ, evaluator quick-start, release notes, deck outline, demo runbook | Product lead |
| 2026-10-28 | [adoption-02](2026-10-28/adoption-02.md) | Adoption docs and deck updated for contract v0.3.0 (posting step) | Product lead |
| 2026-10-28 | [architect-02](2026-10-28/architect-02.md) | Repo structure, agent roles, API contract and ADRs | Tech lead |
| 2026-10-28 | [architect-03](2026-10-28/architect-03.md) | Contract v0.2.0: role matrix, reason codes | Tech lead |
| 2026-10-28 | [architect-04](2026-10-28/architect-04.md) | Contract v0.3.0: posting step, approved vs posted, decision validation, strict metric | Tech lead |
| 2026-10-28 | [ba-discovery-02](2026-10-28/ba-discovery-02.md) | Apply sponsor answers to the plan | puspalata sahoo (Product lead) |
| 2026-10-28 | [ba-discovery-03](2026-10-28/ba-discovery-03.md) | Sponsor answer summary and user stories | puspalata sahoo (Product lead) |
| 2026-10-28 | [developer-01](2026-10-28/developer-01.md) | FastAPI backend: store, rules engine R01–R24, matcher, API | Backend + AI dev |
| 2026-10-28 | [developer-02](2026-10-28/developer-02.md) | Angular front end (student status, evaluator workbench, evaluation, registrar) | Front-end dev |
| 2026-10-28 | [developer-03](2026-10-28/developer-03.md) | Backend hardening for contract v0.2.0: default-deny roles, reason codes, managed identity, upload limits, LLM output validation | Backend + AI dev |
| 2026-10-28 | [developer-04](2026-10-28/developer-04.md) | Front end on contract v0.2.0: role gating, 401/403 guidance, reason codes from API | Front-end dev |
| 2026-10-28 | [developer-05](2026-10-28/developer-05.md) | Backend for contract v0.3.0: posting step, approved vs posted, decision validation, metrics, parse time-out, pinned deps | Backend + AI dev |
| 2026-10-28 | [developer-06](2026-10-28/developer-06.md) | Front end on contract v0.3.0: approved vs posted, posting step, strict metric, SWA security config (F-01) | Front-end dev |
| 2026-10-28 | [developer-07](2026-10-28/developer-07.md) | Backend reminder wording | Backend + AI dev |
| 2026-10-28 | [devops-01](2026-10-28/devops-01.md) | Dockerfile, Azure Bicep, CI and OIDC deploy workflows | Tech lead |
| 2026-10-28 | [devops-02](2026-10-28/devops-02.md) | Align infra with backend env vars; API-only CORS | Tech lead |
| 2026-10-28 | [qa-01](2026-10-28/qa-01.md) | Backend test suite and matcher evaluation on the 30 holdout decisions | QA lead |
| 2026-10-28 | [qa-02](2026-10-28/qa-02.md) | Role-matrix, upload-limit, reason-code and LLM-validation tests; eval metrics redefined | QA lead |
| 2026-10-28 | [qa-03](2026-10-28/qa-03.md) | Tests for contract v0.3.0: posting step, approved vs posted, decision validation, parse time-out | QA lead |
| 2026-10-28 | [security-01](2026-10-28/security-01.md) | STRIDE threat model, Dependabot and backend review checklist | Tech lead |
| 2026-10-28 | [security-02](2026-10-28/security-02.md) | Backend security review against the checklist | Tech lead |
| 2026-10-28 | [security-03](2026-10-28/security-03.md) | Re-review of fixed findings F-01, F-02, F-04, F-06, F-07 | Tech lead |
| 2026-10-28 | [synthetic-data-01](2026-10-28/synthetic-data-01.md) | First synthetic data set (fictional colleges) | Data / QA lead |
| 2026-10-28 | [synthetic-data-02](2026-10-28/synthetic-data-02.md) | Rebuild on Northeastern + NYU | Data / QA lead |
| 2026-10-28 | [synthetic-data-03](2026-10-28/synthetic-data-03.md) | Transcript layout change | Data / QA lead |
<!-- INDEX:END -->

Regenerate the index with `python scripts/build_log_index.py`.
