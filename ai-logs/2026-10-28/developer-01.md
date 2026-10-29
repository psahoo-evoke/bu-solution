# developer-01 · FastAPI backend: store, rules engine R01–R24, matcher, API

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI subagent acting as developer |
| Human owner | Backend + AI dev |
| Trigger | Orchestrator: "Build `backend/` (Python 3.11+, FastAPI) against docs/api/openapi.yaml; then act as QA" |

## Prompt (summary)
Build `backend/`: seed loader / in-memory store (holdout hidden, gt_* never reach the matcher), PostgreSQL DDL, a deterministic rules engine that reproduces all 56 lines of `transcript_lines_expected.csv` using the semantics of `scripts/synthetic/build_data_v2.py`, a matcher with `azure-openai` and `offline-fallback` engines (ADR 0003/0004), every path in the OpenAPI contract with `X-Demo-Role` checks, pdfplumber transcript and syllabus ingest, `/demo/reset`, MyBU CSV export, and CORS for `http://localhost:4200`. Do not touch `frontend/`, `infra/` or `.github/`. Do not commit.

## Inputs used
- `AGENTS.md`, `agents/developer.md`, `docs/api/openapi.yaml`, `docs/architecture.md`, `docs/data-model.md`, `docs/adr/0001-0004`, `docs/stories.md`
- `data/synthetic/seed/*.csv`, `data/synthetic/transcripts/*.pdf`, `data/synthetic/syllabi/*.pdf`
- `scripts/synthetic/build_data_v2.py` (reference `evaluate`, `lookup`, `course_decision`)

## Output
- `backend/requirements.txt`, `backend/app/__init__.py`
- `backend/app/store.py`: CSV loader and in-memory repository. `gt_*` columns go into `Store.ground_truth` (eval only), and `ExtCourse` has no gt fields. Holdout decisions go into `Store.holdout_decisions` and never into the lookup. `reset()` restores the seed.
- `backend/app/rules.py`: R01–R24, each rule cited in comments. It covers eligibility order, the age rule (`term_year <= start_year - 5`), quarter conversion, the lookup (newest catalog year wins, same-year conflict flag), duplicate handling (`CAS <DEPT> 1TR/2TR` + EL-DUPLICATE), Group C residency, the Econ-timing flag, the 68-unit cap in transcript order, Biology advisory, the R19 deadline, and the mapping to `state` / `bu_status_code` (T, TX, TP, TS, TM) / plain-words `status` / `next_step`.
- `backend/app/matcher.py`: one `recommend()` interface. `offline-fallback` scores the overlap of BU topics/outcomes with the external course (title, description, outcomes, topics + sanitised syllabus) and returns the top-3 with covered/missing outcomes, R20 tier, suggested decision/code and confidence. `azure-openai` (urllib REST, strict JSON, syllabus inside `<course_data>` as untrusted data) shortlists lexically, and the tier is recomputed in code. It falls back to offline on any error.
- `backend/app/safety.py`: ADR 0004 regex pre-filter (`detect_injection`, `sanitize`). Flagged sentences are removed before scoring, so the tier cannot change.
- `backend/app/ingest.py`: pdfplumber text, transcript parser, syllabus completeness check (learning outcomes + schedule), and an Azure Document Intelligence adapter stub.
- `backend/app/evaluation.py`: holdout scoring shared by `/api/evaluation/metrics` and `eval/run_eval.py`.
- `backend/app/main.py`: `app`, all 13 contract paths under `/api`, and CORS for `http://localhost:4200`.
- `backend/db/schema.sql`: PostgreSQL DDL. Ground truth is in a separate table, and the `equivalency_table` view excludes holdout.

Key decisions:
- **Seed state.** All four students' transcript lines are pre-loaded from the input columns of `transcript_lines_expected.csv` (its outcome columns are test oracles only). Uploading a transcript PDF replaces that student's lines for that school, so re-upload is idempotent.
- **R15 Econ-timing flag without ground truth.** The reference script used `gt_counterpart`. This engine uses the applied decision's BU course, or the matcher's top candidate for pending lines (passed in as `ai_hint`). The hint affects advisory flags and wording only, never units or codes.
- **Runtime decisions.** They get `split=runtime`, `state=approved` ("Approved - awaiting posting") and default `catalog_year=2026-27`, so they supersede older seed decisions. `reusable=false` applies only to students who currently have the line.
- **Batch (R21).** It rejects the whole batch with 422, saving nothing, if any item has confidence ≤ 90, is preliminary, is injection-flagged, or is tiered "Evaluator decides".
- **Confidence.** Equivalent tier = overlap − max(0, 25 − margin over the runner-up); evaluator-decides tier = overlap; elective tier = 100 − overlap.
- **Role checks.** Enforced only where the brief specifies them (decisions, batch, export). Other routes are open to any demo role.

## Human review
- Pending review by the Backend + AI dev.

## Verification
- 55/56 expected lines matched exactly on the first run. The remaining difference is a narrative annotation, not a rule flag (see qa-01).
- `pytest -q` from `backend/`: **107 passed**, 0 failed (see qa-01).
- Smoke test: `uvicorn app.main:app` served `/api/health`, `/api/courses/NYU%7CECON-UA%20266/recommendation`, `/api/demo/reset` (204) and `/api/exports/mybu.csv` (Registrar).
- Did not run `scripts/build_log_index.py`, because it rewrites `ai-logs/README.md`, which this run was told not to edit. The orchestrator should run it.

## Commit
see git log
