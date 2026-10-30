# Known gaps and roadmap to production

**AI recommends, rules compute, evaluators decide.** This page lists what the hackathon build does not do yet, and the ordered steps to take it to production at Boston University. Effort is in person-days for this team and is an estimate.

## Known limitations (today)

| # | Limitation | Why it matters | Evidence |
| --- | --- | --- | --- |
| L1 | The **Azure OpenAI engine has not been evaluated**. All accuracy numbers come from the offline matcher. | Real-world accuracy is unproven. | [eval-report.md](quality/eval-report.md), ADR 0003 |
| L2 | **Synthetic data favours word matching.** External courses were generated from exact BU topic strings; real syllabi paraphrase. n = 30 holdout decisions. | The 100 % / 0 % figures check the pipeline and safety gates, not real accuracy. | [eval-report.md](quality/eval-report.md) caveats |
| L3 | **Evaluator time saved is not measured.** 12 → under 2 minutes is the sponsor's target. | The main business KPI is still an estimate. | Discovery Q-004, Q-040 |
| L4 | **Demo-grade sign-in.** Sample accounts share one password, anyone can register as a department reviewer, and there is no limit on repeated login attempts. Entra ID sign-in is built but not used by the live demo. | Not safe for real student records (FERPA). | README §8, ADR 0005 |
| L5 | **One API replica.** The API serves reads from an in-memory copy of the PostgreSQL data, so a second replica would not see the first one's changes. | Single point of failure; a restart is about a minute of downtime. | ADR 0007, `infra/modules/containerapp-api.bicep` |
| L6 | **AI quota is 10K tokens per minute.** Above it, calls fall back to the offline matcher without telling the evaluator. | At intake peaks most comparisons would silently be offline. | ADR 0007 |
| L7 | **No live BU systems.** No Transferology or BU equivalency database import; results are a MyBU-style CSV, not posted to MyBU. | Registrar still loads the CSV by hand. | Discovery Q-001, Q-019, Q-049 |
| L8 | **Reminder schedule differs from the sponsor's.** The app emails a syllabus reminder every 2 days, at most 7 times (`TRANSFERIQ_SYLLABUS_REMINDER_DAYS` / `_MAX`); the sponsor asked for days 7, 21 and 45. Email goes out only where Communication Services or the Logic App webhook is configured, and the seeded sample students are never emailed. | Students may be chased too often; nobody is emailed where no mail service is set up. | Discovery Q-020, `app/rules.py`, `app/notify.py` |
| L9 | **Out of scope for the prototype:** AP/IB/CLEP test credit, non-English transcripts, the appeals workflow, Hub/degree-audit mapping, Engineering residency rule. | Confirmed as assumptions; awaiting sponsor confirmation. | Discovery Q-044, Gap review sheet |
| L10 | **Single environment.** One `demo` environment; no separate test and prod. | Changes go straight to what the jury and users see. | `.github/workflows/deploy*.yml` |

## Roadmap (in priority order)

| Phase | Step | Closes | Effort | Done when |
| --- | --- | --- | --- | --- |
| **1. Prove value (pilot, 2-3 weeks)** | Time 2 evaluators in one department on the same 20 courses, by hand and with TransferIQ | L3 | 3 d | Before/after minutes per course, agreed with the department |
| | Evaluate the Azure OpenAI engine on the 30 holdout decisions and on 20 real, paraphrased syllabi | L1, L2 | 4 d | Top-1 ≥ 80 %, wrong credit ≤ 2 % on real syllabi, reported next to the offline numbers |
| | Show "AI comparison: offline" on every recommendation that fell back | L6 | 1 d | Evaluator can see which engine produced each suggestion |
| **2. Secure for real data (2-3 weeks)** | Entra ID / BU SSO only; remove shared passwords and self-registration of reviewers; login rate limit | L4 | 4 d | Security re-review passes; reviewer accounts approved by Credit Evaluation |
| | FERPA data-processing agreement for the AI service; private endpoints; retention (delete documents after the appeal window) | L4 | 5 d + legal | Signed agreement; retention job runs |
| | Separate dev / test / prod environments with their own parameters and approvals | L10 | 2 d | Prod deploys only from a tagged release after test passes |
| **3. Scale for the intake (1-2 weeks, before the semester)** | ADR 0007 phase 1: raise Azure OpenAI to 150K TPM, API to 2 vCPU / 4 GiB, PostgreSQL to B2s | L6 | 1 d | Load test of 800 transcripts completes with the AI engine in under 1 hour |
| | ~~Index transcript lines by student~~ **Done 2026-10-30** (developer-44): export 31x and queue refresh 3.4x faster at 5x | L5 | done | Volume test: export and department queue grow linearly |
| | ADR 0007 phase 2: background AI queue that waits on quota instead of falling back; model results cached in PostgreSQL | L6, L5 | 2 d | No silent offline fallback under load; restart does not repeat AI calls |
| | Reminders on the sponsor's day 7 / 21 / 45 schedule, sent through Communication Services in every environment | L8 | 1 d | Students receive day 7 / 21 / 45 emails with an upload link |
| **4. Integrate (when BU grants access)** | Import Transferology / BU equivalency data into our equivalency table | L7 | 5 d | Existing matches resolve instantly from BU's own data |
| | Post approved credit to MyBU instead of a CSV | L7 | 5-10 d | Registrar posting is one click |
| **5. Extend scope** | Appeals workflow, AP/IB/CLEP credit, Engineering residency, more departments | L9 | per item | Agreed with the sponsor |

## At 10x load

Measured up to 5x in the [volume test](quality/scalability-report.md): at one year's volume a status page loads in 0.2 s and the review queue refreshes in 0.5 s, the queue refresh and the MyBU export grew quadratically until transcript lines were indexed by student (fixed the same day: export 31x faster at 5x), and the first queue load after a restart ranks every waiting course in turn. Both are added to phase 3 below.

Today's volume is about 8,000 courses a year (800 students × 10). At 10x (80,000 courses, about 8,000 transcripts a year, peaks of a few thousand in a day):

| Part | What happens at 10x | Change needed |
| --- | --- | --- |
| Rules engine and PDF reading | CPU-light (~0.2 s per transcript, ADR 0007); about 30 minutes of CPU on a peak day | None beyond phase 3 sizing |
| **Azure OpenAI quota** | **The bottleneck.** Cost scales with *distinct* courses (cached by prompt), up to ~74 M tokens in a fully mixed intake | Phase 2 queue plus a higher quota (300K TPM or a second region); reuse of past decisions cuts calls each year |
| API replicas | One replica cannot absorb peaks or deploy without downtime | ADR 0007 phase 3: read from PostgreSQL per request, then allow several replicas |
| PostgreSQL | Writes grow 10x; still small (well under 32 GB) | General Purpose tier during intake; read replica for reporting |
| Evaluators | Same 12 evaluators; maybe courses grow 10x | Batch approval (> 90 %) and decision reuse matter more; measure reuse rate per term |

## Reuse for another university

The rules, catalog and decisions are data, not code:
- Eligibility and credit rules: `data/synthetic/seed/rules.csv` (R01-R24) and `app/rules.py`, which cites each rule ID.
- Catalog, equivalency table and reason codes: seed CSVs loaded into PostgreSQL.
- The matcher compares learning outcomes, so it works for any catalog that has outcomes or syllabi.

Another school needs its own rules file, catalog import and role mapping. The matcher, workbench, student status page and audit trail are reused as they are.
