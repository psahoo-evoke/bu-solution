---
name: run-transferiq
description: Build, run, and drive TransferIQ (FastAPI backend + Angular frontend) locally. Use when asked to run, start, launch or stop the app, take a screenshot of a page, click through the student / evaluator / evaluation / registrar flows, reset the demo data, or run the backend and e2e tests.
---

TransferIQ is a FastAPI API on `:8000` plus an Angular dev server on `:4200` that proxies `/api` to it.
You drive it with **`.claude/skills/run-transferiq/driver.mjs`**, a Playwright script that uses the
installed Chrome and writes screenshots to `.shots/`. For API-only changes, `curl` is enough.

Verified on Windows 11 with PowerShell 5.1. All paths are relative to the unit root (`bu-solution/`).
No Azure keys are needed: the matcher falls back to its offline engine (`Engine: offline-fallback` in the UI).

## Prerequisites

Python 3.12 and Node 22 (CI uses 22). Fresh machines here had only the Microsoft Store `python.exe` stub:

```powershell
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
winget install -e --id OpenJS.NodeJS.22 --silent --accept-package-agreements --accept-source-agreements
```

Terminals that were open before the install don't see them on PATH. Either open a new terminal or prefix commands with
`$env:Path="C:\Program Files\nodejs;$env:Path"` and call Python by full path
(`$env:LOCALAPPDATA\Programs\Python\Python312\python.exe`), as below.

## Setup (once)

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt
$env:Path="C:\Program Files\nodejs;$env:Path"; Set-Location frontend; npm ci --no-audit --no-fund; Set-Location ..
```

`npm ci` takes about 2 minutes. You don't need `npx playwright install`, because the driver and the e2e tests use the installed Chrome.

## Run (agent path)

Start both servers detached, with logs in `%TEMP%`, and wait until both answer. The wait gives up after about 2 minutes per URL and prints `... FAILED`:

```powershell
$env:Path="C:\Program Files\nodejs;$env:Path"   # must come first: npm.cmd spawns `node` from PATH
# Optional: AI on. The app never reads backend/.env itself; this loads it into the env uvicorn inherits. Skip for offline.
if (Test-Path backend\.env) { Get-Content backend\.env | Where-Object { $_ -match '^\s*[A-Z_]+=.+' } | ForEach-Object { $n,$v = $_ -split '=',2; Set-Item "env:$($n.Trim())" $v.Trim() } }
Start-Process -WindowStyle Hidden -FilePath backend\.venv\Scripts\python.exe -ArgumentList '-m','uvicorn','app.main:app','--port','8000' -WorkingDirectory backend -RedirectStandardOutput $env:TEMP\tiq-api.log -RedirectStandardError $env:TEMP\tiq-api.err
Start-Process -WindowStyle Hidden -FilePath 'C:\Program Files\nodejs\npm.cmd' -ArgumentList 'start' -WorkingDirectory frontend -RedirectStandardOutput $env:TEMP\tiq-web.log -RedirectStandardError $env:TEMP\tiq-web.err
foreach ($u in 'http://127.0.0.1:8000/api/health','http://localhost:4200/api/health') { $ok=$false; $t=(Get-Date).AddSeconds(120); while (-not $ok -and (Get-Date) -lt $t) { try { Invoke-RestMethod $u -TimeoutSec 5 | Out-Null; $ok=$true } catch { Start-Sleep 1 } }; if ($ok) { "$u ok" } else { "$u FAILED - see $env:TEMP\tiq-*.log/.err" } }
```

Then drive it (same shell, so `node` is on PATH):

```powershell
node .claude/skills/run-transferiq/driver.mjs tour
```

| command | what it does |
|---|---|
| `tour` (default) | Student (SYN-24001), evaluator workbench with PSYCH-UA 10 open, AI evaluation, registrar. One PNG each. |
| `shot <path> [role]` | Opens `<path>`, optionally sets the Demo role (`Student`, `CreditStaff`, `Evaluator`, `Department`, `Registrar`), and screenshots it |
| `decide <course>` | As Evaluator, approves the AI's top candidate for `<course>` (e.g. `PSYCH-UA 10`), then prints the "Saved." status and takes a screenshot |
| `reset` | `POST /api/demo/reset` as Registrar, which reseeds the synthetic data (expect `reset 204`) |

Screenshots go to `.shots/<name>.png` (gitignored). **Read them.** The exit code is 1 if the browser logged any console or page errors, and they're printed.
Env vars: `TIQ_URL` (default `http://localhost:4200`), `TIQ_SHOTS`, and `TIQ_BROWSER` (`chrome` by default, or `msedge`/`chromium`).

Stop both servers:

```powershell
Get-NetTCPConnection -LocalPort 8000,4200 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

## Run (human path)

Two terminals: `cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`, then
`cd frontend; npm start`. Open http://localhost:4200 and stop each with Ctrl-C.

## Test

```powershell
backend\.venv\Scripts\python.exe -m pytest -q backend                  # 321 passed, 1 skipped (~105 s, offline)
$env:Path="C:\Program Files\nodejs;$env:Path"; Set-Location frontend
$env:CHROME_BIN="C:\Program Files\Google\Chrome\Application\chrome.exe"; npx playwright test; Set-Location ..   # 7 passed, needs both servers up
```

## AI on (Azure AI Foundry)

`backend/.env` (gitignored) holds `AZURE_OPENAI_ENDPOINT` (`https://bu-solution-resource.services.ai.azure.com`), `AZURE_OPENAI_DEPLOYMENT` (`gpt-4.1-mini`),
`AZURE_OPENAI_API_KEY`, and optionally `AZURE_DI_ENDPOINT` / `AZURE_DI_KEY` (same resource, same key). With it loaded, the UI shows
`Engine: azure-openai`. At startup a background thread fills the model cache for the review queue and the evaluation page
(about 45 s); wait for that before demoing, or the first load takes 15–25 s. Set `TRANSFERIQ_PREWARM=0` to turn the warm-up off.
Tests always run offline (conftest removes the endpoint), whatever is in `.env`.

## PostgreSQL (optional persistence)

Off unless `POSTGRES_HOST` is set. Then the backend (`backend/app/db.py`) runs `backend/db/schema.sql` at startup (idempotent),
seeds empty tables from `data/synthetic/seed/`, loads its in-memory state from the database and writes decisions, postings,
transcript lines, syllabus uploads and the audit log through to it. `driver.mjs reset` truncates and reseeds the tables.
`backend/.env` holds `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD` for the dev server
(`bu-solution-pg.postgres.database.azure.com`, database `butransfer`). In Azure, `POSTGRES_AUTH=entra` replaces the password
with a managed-identity token. Start the backend with the `.env` loader from "Run (agent path)" above; nothing else changes.

Check that state survives a restart (Git Bash `curl`; restart = the stop command, then the start lines again):

```bash
curl -s -X POST http://127.0.0.1:8000/api/decisions -H "X-Demo-Role: Evaluator" -H "Content-Type: application/json"   -d '{"ext_id":"NYU|PSYCH-UA 10","decision":"Equivalent","bu_course":"CAS PS 211","reason_code":"EQ-EVALUATOR","reusable":true,"evaluator":"Evaluator PS-A","catalog_year":"2025-26"}'
# restart the backend, then: D-0101 is still listed
curl -s "http://127.0.0.1:8000/api/courses/NYU%7CPSYCH-UA%2010/recommendation" -H "X-Demo-Role: Evaluator"
curl -s -X POST http://127.0.0.1:8000/api/demo/reset -H "X-Demo-Role: Registrar" -w "%{http_code}
"   # 204, back to the seed
```

Seeded row counts: bu_courses 150, schools 4, external_courses 194, external_courses_gt 194, decisions 100 (70 train +
30 holdout), students 4, transcript_lines 56, syllabi 12; decision_scope, audit_log and postings 0.

- Tests never touch the database: conftest removes `POSTGRES_*`. The round trip in `backend/tests/test_db.py` runs only when
  `TRANSFERIQ_TEST_PG_DSN` is set, and it **truncates** that database, so point it at a scratch database (or reset afterwards).
- If the server is unreachable, startup fails (on purpose, so the app never runs on stale data without telling you) and a
  write answers 503 without changing anything. Check the firewall rule for your IP first.
- With AI on, startup also warms the model cache (about 45 s). Running `driver.mjs tour` straight after a restart can time out
  on the evaluation page (`page.waitForLoadState: Timeout 30000ms exceeded`); wait and rerun.

## Gotchas

- **Demo data is shared state in the running backend.** `decide`, and the e2e suite, change it: an approved course moves from the review queue to `TP` on the student page. Run `driver.mjs reset` to get back to the seeded state. The e2e suite resets before and after itself, so it also wipes anything you changed by hand.
- **Role is a UI dropdown, not auth.** Pages render a "Switch role to ..." message instead of data when the Demo role is wrong (for example `/review` as Student). Pass the role to `shot`. API calls take the `X-Demo-Role` header.
- **Use the `:4200/api/...` path** to check the proxy wiring. `:8000` alone being healthy doesn't prove the SPA can reach it.
- **Probe the backend at `127.0.0.1:8000`, not `localhost:8000`, from PowerShell.** Uvicorn listens on IPv4 only. `Invoke-RestMethod http://localhost:8000` tries `::1` first, and on Windows a refused loopback connect takes about 2 s, so with a short `-TimeoutSec` it never gets to IPv4 and reports failure even though the server is up. curl and the Angular proxy aren't affected.
- **`playwright.config.ts` reads `CHROME_BIN`.** Without it, `npx playwright test` looks for its own Chromium download and fails. Setting it is quicker than running `playwright install`.
- **`npx playwright test` in PowerShell prints a red `NativeCommandError` about `NO_COLOR`/`FORCE_COLOR`.** That's only a Node warning on stderr. Check the `N passed` line.

## Troubleshooting

- **`Python was not found; run without arguments to install from the Microsoft Store`**: only the WindowsApps stub is on PATH. Install with winget (see above) and use the full path or a new terminal.
- **The `:4200` wait never succeeds, and `%TEMP%\tiq-web.err` says `'"node"' is not recognized as an internal or external command`**: `npm.cmd` ran without Node on PATH. Set `$env:Path` *before* `Start-Process`, stop whatever is on the ports, and relaunch.
- **`http://localhost:8000/api/health FAILED` while `tiq-api.err` shows `Application startup complete`**: the IPv6-first timeout described above. Probe `127.0.0.1`.
- **Engine still shows `offline-fallback` with `.env` filled in**: either `.env` wasn't loaded before `Start-Process`, or every model call failed and fell back silently (wrong endpoint path, an `o`-series/gpt-5 deployment that rejects `temperature: 0`, or a Claude deployment, which this client can't call). Test the deployment directly; the app hides the error.
- **`node: command not found` right after the winget install**: the PATH change doesn't reach shells that are already open. Prefix with `$env:Path="C:\Program Files\nodejs;$env:Path"`.
