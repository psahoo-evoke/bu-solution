# TransferIQ v0.1 release notes (EvoHack 2026 slice)

Date: 2026-10-28 · API contract v0.3.0 · Synthetic data only · Runs locally (backend :8000, front end :4200)

**AI recommends, rules compute, evaluators decide, and the Registrar posts.** v0.1 is one end-to-end slice: transcript in, status out, evaluator decision, Registrar posting, MyBU-style export.

## Changes since the first draft (contract v0.3.0)

- **Approval posts at once (2026-10-30).** An evaluator's decision now posts the credit straight away, for every student it applies to, so students see it secured (T) without waiting on the Registrar. **Post approved courses** stays as the safety net for a posting that could not be saved. This replaces the two-step flow below.

- **Approved is not posted.**
  - An evaluator's approval shows **TP "Approved – awaiting posting"**. It counts as **pending** and appears in a new "approved" total.
  - The Registrar's **Post approved courses** step (`POST /api/postings`) turns it into **T "Posted – credit secured"**, and only then does it count as secured. This follows the sponsor process: department → Registrar → posting.
- **Reuse.** A reused decision matches the next student instantly, with no evaluator step (for example Liam's PSYCH-UA 10 → CAS PS 211, 4 units). It also stays TP until that student's record is posted.
- **Evaluation page.** It now shows **strict agreement** and **deferrals** next to **top-1 candidate agreement**.
- **Decision validation.** Every decision is checked on the server: a real BU course for Equivalent, a TR code for Elective, `TFRGEN NOCRDT` for No credit, and a reason code that exists and fits the decision. Anything else gets 422 and nothing is saved.
- **Reminder wording.** It now says "Reminders scheduled for days 7, 21 and 45 (email sending not enabled in this prototype)".
- **Security fixes** after the security review:
  - F-01: SWA config with CSP and SPA fallback.
  - F-02: decision validation.
  - F-04: PDF parse time-out, 15 s by default.
  - F-06: server-generated file names.
  - F-07: exact pins for direct Python dependencies.

## What works

**Student / Advisor (Student status page)**
- Every course from every transcript, grouped by term. Each shows a status in plain words plus the BU code (T, TX, TP, TS, TM), the BU course or TR elective code, units, "units if approved", next step and flags.
- Totals: Secured, Pending (including "approved, awaiting posting"), No credit, plus the 68-unit cap.
- Transcript upload (PDF) and per-course syllabus upload. Re-uploading a transcript replaces that school's lines.
- Syllabus completeness check (learning outcomes + weekly schedule): missing → TS, incomplete → TM, complete → TP.

**Rules engine (no AI)**: R01–R24 in `backend/app/rules.py`.
- Eligibility, 5-year age review, quarter conversion (× 2/3, 2 decimals), equivalency lookup with newest-wins and conflict flags, duplicates, residency, the 68-unit cap, the one-year deadline flag and the code mapping.
- Reproduces all 56 seeded transcript lines. Measured: 55 exactly; the 56th differs only in a demo narration note.

**Evaluator workbench**
- Queue with department filter.
- Top-3 BU candidates, each with overlap %, tier (≥ 80 / 50–79 / < 50) and outcomes covered vs missing.
- Past decisions and a 2-minute timer.
- Decision form with reason codes from the API, a reusable flag and validation.
- Batch approval for confidence > 90 %, with one logged decision per course.
- "Preliminary – not decidable" banner and prompt-injection warning (T17: ECON-UA 266 stays at 62 %, "Evaluator decides").

**Registrar**: **Post approved courses** for one student or all (idempotent, one audit entry per line), MyBU-style CSV download with preview (read-only, does not post), and demo reset.

**AI evaluation page**: top-1 candidate agreement, strict agreement and deferrals, plus the wrongly-suggested-credit rate, on 30 held-out decisions, with the gates.

**Security**
- Default-deny role matrix on every API route (401 with no role, 403 with the wrong role).
- Upload limits (10 MB, PDF magic bytes, 30 pages, parse time-out).
- LLM output validation.
- No student names, IDs or ground-truth columns in AI prompts.
- CSV formula escaping, security headers, CSP config for Static Web Apps.

## Measured quality (2026-10-28)

| What | Result | Source |
| --- | --- | --- |
| Backend tests (`python3 -m pytest -q`) | 301 passed, 0 failed | re-run by adoption-02 |
| Front-end unit tests (`npm test`) | 6 files, 25 tests passed | re-run by adoption-02 |
| Playwright demo flow (`npm run e2e`) | 7/7 passed, incl. approve → TP → post → T | developer-06 log (not re-run) |
| Matcher (a) top-1 candidate agreement | 100.0 % (30/30; 12 are "Evaluator decides" deferrals), gate ≥ 80 % | `eval/run_eval.py`, re-run |
| Matcher (b) strict decision agreement | 60.0 % (18/30), reported, not a gate | same |
| Matcher (c) wrongly suggested credit | 0.0 % (0/30), gate ≤ 2 % | same |
| Security checklist (before the v0.3.0 fixes) | 30 items: 24 pass, 3 fail, 3 N/A; 0 critical, 0 high | `docs/security/review-2026-10-28.md` |

All matcher figures come from the **offline engine on synthetic data**. Read the caveats in `docs/quality/eval-report.md` before quoting them.

## What is simulated

| Area | In v0.1 | In production |
| --- | --- | --- |
| Matcher | `offline-fallback`: deterministic word/topic overlap (ADR 0003). The Azure OpenAI path exists and its output validation is unit-tested with a fake client. It has **not** been run or evaluated. | Azure OpenAI + AI Search over the BU catalogue |
| Sign-in and roles | A **Demo role** switcher sends an `X-Demo-Role` header. It is not authentication. | Entra ID with BU app roles (`entra` mode currently fails closed: 401 everywhere) |
| Posting | **Post approved courses** marks lines as posted inside TransferIQ and returns MyBU-style CSV rows. Nothing reaches MyBU. | Registrar import into MyBU |
| Data | 4 synthetic students, 150 BU courses, 194 external courses, 100 past decisions (70 train / 30 holdout), 7 transcripts, 12 syllabi. NU/NYU course codes and titles are real; all content is synthetic. | Real records under FERPA |
| Storage | In memory. Restarting the backend or using "Reset demo data" restores the seed and **clears decisions, postings and the audit log**. | PostgreSQL + Blob Storage |
| Reminders | Day 7 / 21 / 45 shown as scheduled; no emails are sent (the text says so). | Communication Services email + portal |
| Scanned PDFs | Text PDFs are read with pdfplumber. The Document Intelligence adapter is written but not exercised. | Document Intelligence for scans |
| Azure | Bicep and workflows compile and lint cleanly but are **not deployed**. The SWA CSP was checked only in a local emulation. Docker image build was not run. | Deployed via OIDC |

## Known gaps

- **No batch-eligible item in the demo seed.** The highest queue confidence is 87 % (BIOL 3611), so batch approval is tested in code but cannot be shown live.
- **Reused decisions wait for posting (to confirm with the sponsor).** Liam's reused PSYCH-UA 10 is matched instantly but stays TP until his own record is posted. If BU wants reused table matches to be secured at once, the contract needs a `student_id` on decisions (developer-05).
- **Security fixes not re-reviewed.** F-01, F-02, F-04, F-06 and F-07 are fixed and tested, but `docs/security/review-2026-10-28.md` still lists them as open findings.
- **Open security items:**
  - F-03: demo header auth (accepted risk).
  - F-05: the audit log is in memory.
  - Transitive Python dependencies are not locked.
  - `style-src 'unsafe-inline'` remains in the CSP.
- **T20 (NU CHEM 1161).** The workbook expects a CH 101 vs CH 102 choice, but CH 102 is not in the top 3 (qa-01).
- **Student access.** The Student role can view any student in the demo picker. The server must enforce "own record only" once Entra is in (developer-04).
- **Front-end role matrix** is copied by hand from the contract (developer-04, still true for v0.3.0).
- **Accessibility.** Not checked with a screen reader (developer-02).
- **No measured evaluator time yet.** The 2-minute target is the sponsor's goal; the timer shows it, but no timing study has been done.
- **Human reviews.** Most agent runs are still marked "Human review: pending" in their logs (19 of the 25 before adoption-02).
