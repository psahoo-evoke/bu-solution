# TransferIQ — AI co-pilot for transfer credit evaluation

EvoHack 2026 · Boston University problem statement · team **THE SOLUTIONAUTS**

> **AI recommends, rules compute, evaluators decide.** TransferIQ pre-matches every transfer course, shows each student what is secured and what is still pending, and gives department evaluators an evidence-backed recommendation. The AI never posts credit.

**Live demo:** https://bu-solutions.wonderfultree-9ae9802e.westus2.azurecontainerapps.io (sample accounts below).

---

## 1. The problem

When a student transfers to Boston University, every course on their old transcripts has to be evaluated for BU credit. Today that is slow, manual and opaque.

| Sponsor estimate (from discovery) | Value |
| --- | --- |
| Transfer courses evaluated per year | ~8,000 (≈ 800 students × 10 courses) |
| Courses that are a "maybe" (no existing equivalency) | 35 % (~2,800 per year) |
| Days until credit is posted | ~7 for an existing match, **~60 for a "maybe"** |
| Evaluator time per syllabus comparison | **12 minutes** |
| Evaluators | 12 (2 per department × 6 departments) |
| "Maybe" courses whose syllabus never arrives | ~10 % |

What goes wrong today:
- **Students wait in the dark.** For weeks they cannot see which credits are safe and which are still under review, so they cannot plan their first BU semester.
- **Evaluators repeat the same work.** Each "maybe" course means reading a syllabus against the BU catalog by hand, often for a course that was already decided for an earlier student.
- **Missing paperwork stalls everything.** Nobody is chased for a missing or incomplete syllabus, so courses sit in limbo.
- **No system integration.** There is no access to Transferology, BU's equivalency database or MyBU, so results are re-keyed by hand.

All numbers are the sponsor's estimates, not measured BU data. Full answers: [`docs/discovery/sponsor-answers.md`](docs/discovery/sponsor-answers.md).

### Success test (agreed with the sponsor)
Evaluator time per course drops from **12 minutes to under 2**, while the AI's top suggestion matches the evaluator's decision in **≥ 80 %** of cases and **wrongly suggested credit stays ≤ 2 %**.

---

## 2. Our solution

| Step | What happens | Who |
| --- | --- | --- |
| **1. Upload** | The student (or credit staff) uploads the transcript PDF; syllabi follow as they come in. The original PDFs are kept in Azure Blob Storage. | Student, credit staff |
| **2. Pre-match** | Known equivalencies are secured immediately. Eligibility rules (grade, pass/fail, remedial, age, residency, unit cap, quarter → semester conversion, …) are applied by a deterministic rules engine (**R01–R24**). The AI compares every remaining course with the BU catalog and past decisions. | Rules engine + AI |
| **3. Decide** | The department sees the ranked BU candidates with overlap %, outcomes covered and missing, and past decisions, then decides in one click. Matches above 90 % can be approved as a batch. Every decision is logged with a reason code. | Department / evaluator |
| **4. Post** | The Registrar posts approved credit and downloads a MyBU-style CSV. The student's status moves from pending (TP) to secured (T). | Registrar |

**What each user sees**
- **Student**: their own record only. Secured vs pending units, a plain-language status and next step for every course, and upload buttons for the transcript and missing syllabi.
- **Department**: the review queue for their own department, the AI comparison with evidence, single and batch decisions.
- **Registrar / credit staff / advisor**: posting and export, triage, and a read-only view.

**Guardrails**
- The AI only **recommends**. It never posts credit and cannot decide the 50–79 % band; there it defers to the evaluator (rule R20).
- Credit math lives only in the rules engine ([ADR 0001](docs/adr/)); the AI cannot change units or codes.
- Syllabus text is treated as **untrusted**: injected instructions are detected and flagged, and cannot change a recommendation ([ADR 0004](docs/adr/)).
- Every request is checked server-side for the user and role; a student cannot open another student's record.
- **Synthetic data only.** No real student names, IDs or transcripts are used anywhere.

---

## 3. Results

Measured on 30 held-out past decisions the matcher never saw ([`docs/quality/eval-report.md`](docs/quality/eval-report.md)), with the offline matching engine:

| Metric | Result | Sponsor gate |
| --- | --- | --- |
| Top-1 candidate agreement | **100 %** (30/30; 12 of them correctly deferred to the evaluator) | ≥ 80 % ✅ |
| Strict decision agreement (suggestion could be approved as-is) | **60 %** (18/30) | reported, no gate |
| Wrongly suggested credit | **0 %** (0/30) | ≤ 2 % ✅ |

The evaluator-time target (12 → < 2 minutes) has not been measured with real evaluators yet.

---

## 4. Try it

Open the live demo and choose **Student View** or **Department View** on the home page. Every sample account uses the password **`admin`**:

| Sign in as | Email | Lands on |
| --- | --- | --- |
| Student Maya R. Delgado | `maya.delgado@bu.edu` | Her own status (SYN-24001) |
| Student Jordan A. Reyes | `jordan.reyes@bu.edu` | His own status (SYN-24002) |
| Student Aisha K. Bello | `aisha.bello@bu.edu` | Her own status (SYN-24003) |
| Student Liam O. Novak | `liam.novak@bu.edu` | His own status (SYN-24004) |
| Department reviewer | `psychology.dept@bu.edu`, `biology.dept@bu.edu`, `economics.dept@bu.edu`, `computerscience.dept@bu.edu`, `mathematics.dept@bu.edu`, `generaleducation.dept@bu.edu` | Evaluator workbench, own department |
| Staff ("Staff sign in") | `evaluator@bu.edu`, `creditstaff@bu.edu`, `registrar@bu.edu`, `advisor@bu.edu` | Workbench / Registrar |

New students and department reviewers can **Register** from the sign-in page. A demo walkthrough is in [`docs/demo-runbook.md`](docs/demo-runbook.md).

---

## 5. Architecture

```
Browser ──HTTPS──▶ bu-solutions      (Angular SPA served by nginx, public)
                        │  /api/*  same origin
                        ▼
                   bu-solutions-api  (FastAPI: rules engine + matcher, internal only)
                        │
                        ▼
                   Azure Blob Storage (transcripts, syllabi, registered accounts)
```

- **Frontend:** Angular, in `frontend/`. Pages: home and sign-in, student status, evaluator workbench, AI evaluation, registrar.
- **Backend:** FastAPI, in `backend/`. Contains the rules engine R01–R24 (`app/rules.py`), the matcher (`app/matcher.py`), the role guard (`app/guard.py`) and portal accounts (`app/accounts.py`).
- **Hosting:** two Azure Container Apps, with images in Azure Container Registry. One command deploys both: [`scripts/deploy_aca.sh`](scripts/deploy_aca.sh). Details are in [`infra/README.md`](infra/README.md), which also covers the full Bicep platform.
- **Sign-in modes:**
  - `portal`: TransferIQ accounts. This is what the live demo uses.
  - `demo`: a role switcher, for local development.
  - `entra`: Microsoft Entra ID single sign-on with app roles.
- **API contract:** [`docs/api/openapi.yaml`](docs/api/openapi.yaml). **Architecture and decisions:** [`docs/architecture.md`](docs/architecture.md) and [`docs/adr/`](docs/adr/).

---

## 6. Run locally

```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8000
cd frontend && npm ci && npm start          # http://localhost:4200 (proxies /api to :8000)
cd backend && pytest -q && python eval/run_eval.py
```

Locally the app runs in **demo mode** (pick a role in the top bar). Tests and the demo run offline; no Azure keys are needed. With Docker: `docker compose up --build` gives http://localhost:8080.

---

## 7. How we built it

The work was split across eight **role agents** run with our AI assistant, **Solutionauts AI**. Each role has a human owner who reviews its output, and every run is logged.

| Where | What |
| --- | --- |
| [`agents/`](agents/) | The 8 role definitions: BA/Discovery, Synthetic Data, Architect, Developer, QA, Security, DevOps, Adoption |
| [`AGENTS.md`](AGENTS.md) | Working agreement: which role owns what, the hard rules, mandatory logging |
| [`ai-logs/`](ai-logs/README.md) | One log per run (prompt, inputs, output, human review, verification, commit), with an index. CI fails if code changes without a log entry. |

### Repository map
| Path | Owner role | Contents |
| --- | --- | --- |
| `docs/discovery/`, `docs/stories.md` | BA | Sponsor discovery log, what we learned, 12 user stories |
| `docs/architecture.md`, `docs/adr/`, `docs/api/` | Architect | Architecture, ADRs, API contract |
| `data/synthetic/`, `scripts/synthetic/` | Synthetic Data | Test catalogs, past decisions, transcripts, syllabi, generator |
| `backend/` | Developer + QA | FastAPI, rules engine, matcher, sign-in, 344 tests, evaluation |
| `frontend/` | Developer | Angular app, unit tests, Playwright end-to-end tests |
| `infra/`, `scripts/deploy_aca.sh`, `.github/` | DevOps | Azure (Container Apps, Bicep), CI with the AI-log check, deploy workflows |
| `docs/security/` | Security | Threat model, checklist, reviews |
| `docs/adoption/`, `docs/deck-outline.md`, `docs/demo-runbook.md` | Adoption | FAQ, quick-start, release notes, deck, demo runbook |
| `docs/quality/eval-report.md` | QA | Matcher evaluation on 30 held-out decisions |

---

## 8. Known limits (hackathon scope)

- **Demo-grade sign-in:** sample accounts share the password `admin`, anyone can register as a department reviewer, and there is no limit on repeated login attempts.
- **In-memory course data:** the course and decision data is kept in memory and reset to the seed data on restart. Uploaded files and registered accounts are kept in Blob Storage.
- **No live BU systems:** results are exported as a MyBU-style CSV, not posted to MyBU.
- **The AI engine evaluated so far is the offline matcher.** The Azure OpenAI engine has not been evaluated yet.
