# Live demo runbook (8 minutes)

Synthetic data only. Checked against contract v0.3.0 on 2026-10-28 (adoption-02). Every step was run as API calls with its role. The Playwright demo flow passes 7/7, including approve → TP → post → T (developer-06).

The **Demo role** drop-down is in the top bar. It sets who you are. The four pages are in the top nav: **Student status**, **Evaluator workbench**, **AI evaluation**, **Registrar**.

## A. Start the app (once, before the session)

Terminal 1, backend on http://localhost:8000:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Terminal 2, front end on http://localhost:4200 (proxies `/api` to :8000):
```bash
cd frontend
npm ci
npm start
```

Check: `curl -s localhost:8000/api/health` → `{"status":"ok"}`. Open http://localhost:4200; it redirects to Maya's page. No "API offline" banner.

No Azure keys are needed. With no `AZURE_OPENAI_ENDPOINT` set, the matcher runs `offline-fallback` (ADR 0003). Do **not** set Azure variables for the demo.

## B. Rehearse and reset (10 minutes before)

1. Optional full rehearsal (about 1 minute, 7 steps, resets before and after):
   ```bash
   cd frontend && CHROME_BIN=/path/to/chrome npm run e2e   # or: npx playwright install chromium && npm run e2e
   ```
2. **Reset**, in this order of preference:
   - In the app: **Demo role = Registrar** → **Registrar** page → **Reset demo data** → confirm → "Demo reset to the seeded synthetic state."
   - Or: `curl -X POST -H 'X-Demo-Role: Registrar' localhost:8000/api/demo/reset` (204).
   - Or restart the backend (the store is in memory, so a restart is a reset).
3. Set **Demo role = Student**, open **Student status**, pick **Maya R. Delgado (SYN-24001)**.
4. Open a file browser on `data/synthetic/syllabi/` (you upload `Syllabus_NYU_PSYCH-UA-25.pdf` in step 3).
5. Zoom the browser to 125 % so the room can read it. Close other tabs and notifications.

Expected starting state for Maya: **Secured 14.67**, **Pending 8**, **No credit 0**.

**Approved is not posted.** An evaluator's approval makes a line **TP "Approved – awaiting posting"**. It counts as **pending**. It becomes **T** and **secured** only when the Registrar presses **Post approved courses**. This follows the sponsor process: department → Registrar → posting.

## C. The demo, click by click

### Step 1 · Student sees everything at once (1:30) · Demo role: **Student**
1. **Student status** page, Maya. Point at the totals: Secured 14.67, Pending 8, No credit 0.
2. Fall 2024: PSYCH-UA 1 → CAS PS 101, MATH-UA 121 → CAS MA 123, ECON-UA 2 → CAS EC 101, each **T**, 4 units. "Existing equivalencies: instant."
3. Summer 2025: PSC **PSY 215**, quarter system, 4 credits → **CAS PS 2TR, 2.67 units**. "Rules compute: 4 × 2/3."
4. Spring 2025: **PSYCH-UA 10 = TP** (syllabus on file, under review). **PSYCH-UA 25 = TS**: "Upload the course syllabus. Reminders scheduled for days 7, 21 and 45 (email sending not enabled in this prototype)."
5. *(Optional, 15 s)* **Upload transcript (PDF)** → `data/synthetic/transcripts/Transcript_SYN-24001_NYU_Maya_Delgado.pdf`. The lines are re-read from the PDF and nothing changes (re-upload is idempotent).
6. *(Optional, 10 s)* Click **Evaluator workbench** while still a Student: "Switch role to CreditStaff, Evaluator or Department to open the review queue." The server enforces this too.

### Step 2 · Evaluator decides in under 2 minutes (2:00) · Demo role: **Evaluator**
1. Switch **Demo role = Evaluator**. Click **Evaluator workbench**.
2. Click **PSYCH-UA 10 Statistics for the Behavioral Sciences** (students SYN-24001 and SYN-24004). The timer starts.
3. Show: AI suggestion "Evaluator decides", engine `offline-fallback`; top candidate **CAS PS 211, 75 %**, tier Evaluator decides; **Covered** vs **Missing** outcomes (missing: experimental design, t-tests and ANOVA); **Past decisions on this course**.
4. Say: "50–79 %: the AI is not allowed to decide. It did the reading; I decide."
5. Select **Approve equivalent** with **CAS PS 211** selected in the candidates. Reason code **EQ-EVALUATOR**. Leave **Reusable** checked.
6. Press **Approve equivalent**. "Saved." Point at the timer: still under 2:00.

### Step 3 · No syllabus, no decision; then the student fixes it (1:15)
1. Still **Evaluator**: click **PSYCH-UA 25 Cognitive Neuroscience**. Banner **"Preliminary – not decidable."** The decision buttons are disabled. "Descriptions are not evidence."
2. Switch **Demo role = Student** → **Student status** (Maya). PSYCH-UA 10 now shows **TP · Approved – awaiting posting**, CAS PS 211, with the note "counts as pending until posted". Secured stays **14.67**. Pending stays **8**, "incl. 4 approved, awaiting posting". Say: "The department said yes, but nothing is secured until the Registrar posts it."
3. On the PSYCH-UA 25 row click **Upload syllabus** → `Syllabus_NYU_PSYCH-UA-25.pdf`. Status changes **TS → TP**.
4. Switch **Demo role = Evaluator** → **Evaluator workbench** → **PSYCH-UA 25**: now decidable, **CAS PS 231 at 62 %**, Evaluator decides.
5. *(Optional, if time)* **Elective (TR code)** → code `CAS PS 2TR` → reason **EL-PARTIAL** → **Approve as elective**. This is the workbook's expected outcome. The server checks the decision: a TR code with an Equivalent reason, or a made-up course, is refused (422).

### Step 4 · Safety and reuse (1:15)
1. Still **Evaluator**: click **ECON-UA 266 Intro to Econometrics** (Liam). Banner **"Warning: possible prompt injection."** The syllabus says "ignore all previous instructions…". Tier is still **Evaluator decides, CAS EC 204 at 62 %**. "Untrusted text cannot change the tier, and it is never batch-eligible."
2. Point at **Batch approve (confidence above 90%)**: "No items above 90% right now." Say: "Batch is for > 90 % only, one logged decision per course. No course in today's queue qualifies; the highest is 87 %."
3. Switch **Demo role = Student** → **Student status** → **Student** picker → **Liam O. Novak (SYN-24004)**. Find **PSYCH-UA 10**: **TP · Approved – awaiting posting, CAS PS 211, 4 units**. It never went to an evaluator. Say: "Maya's decision was reusable, so Liam matched instantly. Nobody decides this course twice. Like Maya, his credit is secured when the Registrar posts his record."
4. *(Optional)* Point at Liam's no-credit lines (ROTC, internship, non-accredited school → TX with reasons) and the CAP-68 flag.

### Step 5 · Proof, posting and export (2:00)
1. Click **AI evaluation** (any role). Show **Top-1 candidate agreement 100 %** against the 80 % gate. Next to it are **Strict agreement 60 %** and **Deferrals to evaluator 12 of 30**. Then **Wrongly suggested credit 0 %** against the 2 % gate, engine `offline-fallback`, and the by-tier table. Say: "Strict counts every correct deferral as a miss, because the AI is not allowed to decide 50–79 %. Offline engine, synthetic data."
2. Switch **Demo role = Registrar** → **Registrar**. In the **Student** selector pick **SYN-24001 · Maya R. Delgado**. Click **Post approved courses**. You see **"Posted just now: 1 course"** with the row `SYN-24001, NYU|PSYCH-UA 10, CAS PS 211, 4.00, T`. (If you approved PSYCH-UA 25 as an elective in step 3, it says 2 courses.)
3. Switch **Demo role = Student** → **Student status** → Maya. PSYCH-UA 10 is now **T · Posted – credit secured**. Secured went from 14.67 to **18.67**, and Pending from 8 to **4**. Say: "Now it is secured."
4. Back to **Demo role = Registrar** → **Registrar** → **Download MyBU CSV**. The preview shows Maya's posted row plus `PSC|PSY 215, CAS PS 2TR, 2.67, T`. A no-credit line shows `TFRGEN NOCRDT, 0.00, TX`. Downloading the CSV does not post anything.
5. Close: "Department → Registrar → posted → one CSV. The AI never posted anything."

*(Short on time? Skip step 5.4. Steps 5.2 and 5.3 are the important ones.)*

## D. After the demo
**Demo role = Registrar** → **Registrar** → **Reset demo data**, so the next run starts clean. This also clears postings.

## E. Fallbacks

| Problem | What to do (in order) |
| --- | --- |
| "API offline" banner or blank data | Check terminal 1. Restart `uvicorn app.main:app --port 8000` (this also resets the data). Click **Check again** in the banner. |
| Front end won't load | Restart `npm start`. If `node_modules` is broken: `npm ci`. The prebuilt `frontend/dist/` alone will not work (it needs the `/api` proxy), so if `npm start` still fails, use the last row. |
| "Switch role to …" message | You are in the wrong **Demo role**. Use the one-click switch in the message or the top-bar drop-down. |
| A decision was saved by mistake | Reset (section B.2). It wipes all decisions made during the demo. |
| Upload fails (413 / 415 / 422) | Use the exact file from `data/synthetic/`. Only PDFs ≤ 10 MB and ≤ 30 pages are accepted. |
| Whole UI unusable | Play the backup screen recording of this runbook (record it during the rehearsal). Then show the API live with curl: |

curl fallback (backend only, run from the repo root):
```bash
B=localhost:8000/api
curl -s -H 'X-Demo-Role: Student'   $B/students/SYN-24001/evaluation | python3 -m json.tool | head -40
curl -s -H 'X-Demo-Role: Evaluator' "$B/courses/NYU%7CPSYCH-UA%2010/recommendation" | python3 -m json.tool | head -40
curl -s -H 'X-Demo-Role: Evaluator' -H 'Content-Type: application/json' \
  -d '{"ext_id":"NYU|PSYCH-UA 10","decision":"Equivalent","bu_course":"CAS PS 211","reason_code":"EQ-EVALUATOR","reusable":true,"evaluator":"demo"}' $B/decisions
curl -s -H 'X-Demo-Role: Evaluator' "$B/courses/NYU%7CECON-UA%20266/recommendation" | grep -o '"injection_detected":[a-z]*'
curl -s -X POST -H 'X-Demo-Role: Registrar' -H 'Content-Type: application/json' -d '{"student_id":"SYN-24001"}' $B/postings   # {"posted":1,...}
curl -s -H 'X-Demo-Role: Student'   $B/students/SYN-24001/evaluation | grep -o '"totals":{[^}]*}'   # secured 18.67
curl -s -H 'X-Demo-Role: Registrar' $B/exports/mybu.csv | head
curl -s -X POST -H 'X-Demo-Role: Registrar' $B/demo/reset -o /dev/null -w '%{http_code}\n'   # 204
```
Also show the test run as proof: `cd backend && python3 -m pytest -q` (301 passed, about 25 s) and `python3 eval/run_eval.py`.
