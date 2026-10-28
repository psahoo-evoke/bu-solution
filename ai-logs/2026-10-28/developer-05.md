# developer-05 · Backend for contract v0.3.0: posting step, approved vs posted, decision validation, metrics, parse time-out, pinned deps

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | developer |
| Tool / model | Claude subagent (general-purpose) acting as developer |
| Human owner | Backend + AI dev |
| Trigger | Coordinator: implement contract v0.3.0 (architect-04) and security-02 findings F-02, F-04, F-07 |

## Prompt (summary)
1. `POST /api/postings` (Registrar, CreditStaff; optional `student_id`) turns approved lines into posted ones and returns `{posted, csv}`; `GET /exports/mybu.csv` stays a read-only preview.
2. `approved` means awaiting posting: TP, "Approved – awaiting posting", counted in `pending_units` and the new `approved_units`, not secured. `posted` means T and secured.
3. Decision validation (F-02).
4. Metrics add `strict_agreement` and `deferrals`.
5. PDF parsing in a threadpool with a time-out (F-04); exact version pins (F-07).
6. Test for demo step 8.

No commits; no `frontend/` or `infra/` edits.

## Inputs used
- `docs/api/openapi.yaml` v0.3.0, `ai-logs/2026-10-28/architect-04.md`, `docs/security/review-2026-10-28.md` (F-01 to F-09), `docs/demo-runbook.md`, `docs/adoption/release-notes.md`

## Output
- **`backend/app/store.py`:** `Store.postings`, keyed by `(student_id, ext_id, term)` with `{decision_id, posted_at, actor_role}`. Reset clears it.
- **`backend/app/rules.py`:**
  - A line that applies a decision recorded in the app is `approved` (TP, "Approved – awaiting posting") until it has a posting for the same decision. With a posting it is `posted` (T, "Posted – credit secured").
  - Seed equivalency-table matches stay `matched` (T, secured).
  - `totals()`: `secured_units` = matched + posted, `approved_units` = approved, `pending_units` = maybe/pending + approved. All values are floats.
- **`backend/app/main.py`:**
  - `POST /api/postings` posts every `approved` line for one student or all, returns `{posted, csv}` for exactly the rows posted, and writes one audit entry per line with the actor role. Unknown student → 404, bad pattern → 422. It is idempotent.
  - The export preview now also lists `posted` rows.
  - `DecisionInput.bu_course` must match the contract pattern. `_validate_decision`: Equivalent needs a catalogue BU course, Elective a TR code (`CAS XX 1TR/2TR`, `TFRGEN 1TR`), No credit `TFRGEN NOCRDT`, and `reason_code` must exist with a matching `decision`. Otherwise 422. Batch decisions go through the same check.
  - F-04: `_parse_off_loop` runs `pdf_text` / `parse_transcript` with `asyncio.to_thread` under `asyncio.wait_for`, limited by `TRANSFERIQ_PDF_TIMEOUT_S` (default 15 s); a time-out returns 422. A timed-out worker thread cannot be killed and finishes in the background, bounded by the 10 MB / 30-page limits.
  - F-06 (bonus): the syllabus record stores a server-generated `upload-<uuid>.pdf`, never the client filename.
  - Version 0.3.0.
- **`backend/app/guard.py`:** `POST /postings` → {Registrar, CreditStaff}. The contract-equality test enforces it.
- **`backend/app/evaluation.py`:** `deferrals` (= 12). `strict_agreement` was already computed and is now in the contract.
- **`backend/requirements.txt`:** exact pins of the direct dependencies as installed: fastapi 0.162.0, uvicorn 0.54.0, python-multipart 0.0.32, pdfplumber 0.11.10, pydantic 2.13.5, azure-identity 1.27.0, pytest 9.2.0, httpx 0.28.1, PyYAML 6.0.3. Transitive dependencies are not locked (no pip-compile yet).

## Interpretation to confirm (tech lead / architect)
- **Liam's reused line is `approved` (TP, awaiting posting), not `matched` (T, secured).**
  - The contract defines approved/posted per line, but `DecisionInput` has no `student_id`, so the API cannot tell whose review a decision came from.
  - The rule chosen: any line that uses a decision recorded in the app awaits a Registrar posting for that student. Liam still matches instantly (CAS PS 211, 4 units, no evaluator step), and his line becomes T only when his own record is posted.
  - Note that `docs/demo-runbook.md` step 4 currently says Liam shows "T … Approved – awaiting posting". With v0.3.0 that is **TP**, so the runbook text needs an update (adoption's file, not edited here).
  - If Liam should be secured immediately as a table match, the minimal change is to add an optional `student_id` to `DecisionInput` (architect) and treat other students' lines as `matched`.
- A "No credit" decision recorded in the app still shows `posted_no_credit` / TX immediately (no posting step), as before.

## Human review
- Pending review by the Backend + AI dev.

## Verification
- `pytest -q` from `backend/`: **301 passed**, 0 failed (see qa-03).
- uvicorn smoke test of step 8:
  - Decision → 201. Maya's totals: secured 14.67, approved 4.0, pending 8.0.
  - `POST /postings {"student_id":"SYN-24001"}` as Registrar → `{"posted":1, ...CAS PS 211,4.00,T}`; as Student → 403.
  - Maya afterwards: secured 18.67, approved 0.0, pending 4.0.
  - `/evaluation/metrics`: top1 1.0, strict 0.6, deferrals 12, wrong 0.0.
- `python eval/run_eval.py` → exit 0.

## Commit
see git log
