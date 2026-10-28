# adoption-02 · Adoption docs and deck updated for contract v0.3.0 (posting step)

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | adoption |
| Tool / model | Claude subagent (general-purpose) acting as adoption |
| Human owner | Product lead |
| Trigger | Coordinator: contract v0.3.0 (architect-04) implemented in developer-05/06/07 and qa-03. Update the runbook (Liam shows TP; add the posting step as Registrar), the deck (numbers, run count), the release notes and the FAQ; resolve the adoption-01 inconsistencies that are now fixed |

## Prompt (summary)
- Update `docs/demo-runbook.md`, `docs/deck-outline.md`, `docs/adoption/release-notes.md` and the FAQ/quick-start for v0.3.0:
  - approved = TP and pending;
  - Registrar posting makes it T and secured;
  - Liam's reused line is TP until his own posting;
  - strict agreement and deferrals on the evaluation page;
  - decision validation;
  - honest reminder text.
- Re-count the agent runs from `ai-logs/`.
- No code, no commits.

## Inputs used
- `ai-logs/2026-10-28/architect-04.md`, `developer-05.md`, `developer-06.md`, `developer-07.md`, `qa-03.md`; `git log` (12ec818..cbad1ed)
- `docs/api/openapi.yaml` v0.3.0 (via the logs), `docs/quality/eval-report.md` diff
- `frontend/src/app/pages/registrar.html`, `evaluation.html` (labels only)
- My adoption-01 docs

## Output
- `docs/demo-runbook.md`:
  - New "approved is not posted" note.
  - Step 3: Maya's PSYCH-UA 10 is TP, secured stays 14.67, pending 8 "incl. 4 approved".
  - Step 4: Liam's PSYCH-UA 10 is TP, CAS PS 211, 4 units, matched instantly.
  - Step 5 rewritten: evaluation page with strict 60 % and deferrals 12 of 30 → **Registrar: pick SYN-24001 → Post approved courses → "Posted just now: 1 course"** → Student: Maya T "Posted – credit secured", secured 18.67, pending 4 → CSV.
  - Timings re-balanced to 8:00 (1:30 / 2:00 / 1:15 / 1:15 / 2:00).
  - New reminder wording; reset also clears postings; curl fallback adds `POST /postings`; 301 tests.
- `docs/deck-outline.md`:
  - Agents slide: architect 4, developer 7, qa 3, adoption 2, **26 runs** in total.
  - New "adoption loop" callout (adoption-01 → architect-04 → developer-05/06/07 → qa-03 → adoption-02).
  - Tests now 301 / 25 / e2e 7/7.
  - Security fixes listed, with "not re-reviewed by security yet".
  - Data flow includes posting; demo outline matches the runbook.
  - Future scope revised; two Q&A rows added or changed (posting, why Liam is pending); pending-review count 19 of 25.
- `docs/adoption/release-notes.md`: rewritten for v0.3.0 (changes section, posting, measured table re-run, simulated table, known gaps).
- `docs/adoption/student-faq.md`: TP includes "Approved – awaiting posting"; secured = matched or posted; pending includes approved; the reuse answer notes posting; reminder wording.
- `docs/adoption/evaluator-quickstart.md`: decision validation paragraph; the "after you decide" section explains TP → posting → T.

## Human review
- Pending review by the Product lead.

## Verification
- `cd backend && python3 -m pytest -q` → **301 passed** (25 s). `python3 eval/run_eval.py` → (a) 100.0 % (12 deferrals), (b) 60.0 %, (c) 0.0 %, gates met.
- `cd frontend && npm test` → **6 files, 25 tests passed**. e2e not re-run (developer-06: 7/7).
- Runbook walked through the API on a local uvicorn (v0.3.0), with the role for each step:
  - Decision as Evaluator → 201. Maya: secured 14.67, approved 4.0, pending 8.0; PSYCH-UA 10 TP "Approved – awaiting posting". Liam: PSYCH-UA 10 TP, CAS PS 211, 4.0.
  - TS next step: "Reminders scheduled … (email sending not enabled in this prototype)".
  - `POST /postings {"student_id":"SYN-24001"}` as Registrar → posted 1, row `CAS PS 211,4.00,T`. Maya → secured 18.67, approved 0.0, pending 4.0, line T "Posted – credit secured".
  - PSYCH-UA 25 syllabus upload → TP. Elective `CAS PS 2TR` / EL-PARTIAL → 201.
  - Reset as Registrar → 204, and Maya is back to 14.67 / 0 / 8.
- Labels checked in the templates: "Post approved courses", "Posted just now: N course(s)", "Top-1 candidate agreement", "Strict agreement", "Deferrals to evaluator", and the Registrar's "Student" selector.
- Run count: 25 files in `ai-logs/` before this run, 26 with it. 19 of the 25 say "Human review: pending".
- Did not run `scripts/build_log_index.py`, because this run was told not to edit `ai-logs/README.md`.

## Commit
not committed (orchestrator commits)
