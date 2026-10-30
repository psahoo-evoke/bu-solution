# Volume test: one year of transfer intake and beyond

| | |
| --- | --- |
| Date | 2026-10-30 |
| Script | [`backend/eval/run_volume.py`](../../backend/eval/run_volume.py) |
| Reproduce | `cd backend && python eval/run_volume.py --scales 0.1,0.5,1,2` and `--scales 5 --sample 30` (about 10 minutes in total; `--json` for raw numbers) |
| Engine | `offline-fallback` (the deterministic matcher, ADR 0003); in-memory store; no Azure, no database |
| Machine | Developer laptop, 2 logical CPUs. The live API container has 0.5 vCPU, so single-threaded steps there can take up to about twice as long. |

## What was tested

**Scale 1x = one year of BU transfer volume** from discovery (Q-002): 800 students × 10 courses = **8,000 transcript lines**. For each scale the script adds N synthetic students to the seed data and calls the **real API routes** through FastAPI's test client:

- **Student status page**: `GET /api/students/{id}/evaluation`, timed for a random sample of 200 students. This is the same evaluation a transcript upload returns.
- **Department review queue**: `GET /api/review-queue`. The first call computes a recommendation for every "maybe" course not seen before; a refresh reuses them.
- **Registrar export**: `GET /api/exports/mybu.csv` for all students.
- **PDF reading** (pdfplumber) on the 7 sample transcript PDFs. This does not depend on volume.

Course mix per line: 65 % catalogue courses of the student's school (existing equivalencies, maybe courses, ineligible course types), 35 % courses new to the catalogue (3 per student, so distinct courses grow with volume, the "mixed schools" case in ADR 0007). Grades include C-, D and P/F, so the rules engine rejects some lines. Fixed random seed: the run is repeatable.

## Results

| Scale | Students | Transcript lines | Distinct courses | Status page p50 / p95 | Review queue items | Queue first load | Queue refresh | One department | MyBU export | Peak memory |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.1x | 84 | 856 | 327 | 336 / 778 ms | 249 | 0.7 s | 0.07 s | 0.03 s | 0.02 s | 83 MB |
| 0.5x | 404 | 4,056 | 994 | 201 / 610 ms | 853 | 17.7 s | 0.32 s | 0.16 s | 0.13 s | 116 MB |
| **1x (one year)** | **804** | **8,056** | **1,792** | **188 / 598 ms** | **1,603** | **32.1 s** | **0.50 s** | **0.29 s** | **0.24 s** | **141 MB** |
| 2x | 1,604 | 16,056 | 3,476 | 187 / 506 ms | 3,134 | 50.5 s | 1.49 s | 1.23 s | 1.03 s | 163 MB |
| 5x | 4,004 | 40,056 | 8,483 | 818 / 1,347 ms | 7,714 | **101.6 s** | **7.38 s** | 6.41 s | **10.27 s** | 198 MB |

Student counts include the 4 seed students. The 5x row was a separate run (`--scales 5 --sample 30`): 30 sampled students instead of 200. PDF reading: mean 62-83 ms, max 144-183 ms per transcript across the two runs.

## What the numbers say

**At one year's volume the app is fast enough.**
- A student sees their course-by-course status in about **0.2 s** (p95 0.6 s) at 1x and 2x (0.8 s at 5x, see below). Reading the PDF adds about 0.1 s.
- Processing a whole year of transcripts takes about **3 minutes of CPU** (191 s for all 804 status pages). Spread over an intake season, that is negligible.
- An evaluator's queue refresh takes **0.5 s** with 1,603 courses waiting; one department's view takes 0.3 s.
- Memory peaks at **141 MB**, well inside the container's 1 GiB.

**Two parts grow faster than the data, and set the 10x limit.**
1. **Queue refresh and export grow quadratically.** From 1x to 5x the data grows 5x, but the refresh gets 15x slower (0.50 → 7.38 s) and the export 43x slower (0.24 → 10.27 s); the status page also slows (p50 0.19 → 0.82 s). The cause: `Store.lines_for()` scans *every* transcript line to find one student's lines, and the queue and export do that for *every* student. At 10x this extrapolates to roughly **30 s per queue refresh** and **40 s per export**. Fix: index transcript lines by student (an estimated half-day change in `app/store.py`), which makes both linear.
2. **The first queue load after a restart is long.** It ranks every waiting maybe course in turn (offline engine: about 13-20 ms each). It took 32 s at 1x and **102 s at 5x**, just under the web proxy's **120 s** limit (`proxy_read_timeout`); at 10x it would fail on the first try. Also, the offline result cache holds at most **4,096** courses; at 5x there are already 8,483 distinct courses, so cached rankings are pushed out and refreshes recompute part of the queue. Fix: compute recommendations when a transcript is uploaded, in the background (ADR 0007 phase 2), and store them in PostgreSQL so a restart does not start cold.

**With the Azure OpenAI engine** the limit is the model quota, not CPU: ADR 0007 measures about 3,100 tokens per maybe course. At 1x that is at most 5.6 M tokens (1,792 distinct courses, of which only the maybe ones go to the model): up to about 9 hours at today's 10K tokens per minute, or about 40 minutes at the proposed 150K.

## What changes at 10x (80,000 lines a year)

| Part | At 1x (measured) | At 5x (measured) | At 10x (extrapolated) | Change needed |
| --- | --- | --- | --- | --- |
| Student status page p50 | 0.19 s | 0.82 s | ~1.6 s (the line scan) | Index lines by student |
| Review queue refresh | 0.5 s | 7.4 s | ~30 s (quadratic) | Index lines by student, then linear; paginate the queue by department |
| Review queue first load | 32 s | 102 s | past the 120 s proxy timeout: fails | Recommend at upload time in the background; persist results (ADR 0007 phase 2) |
| MyBU export | 0.24 s | 10.3 s | ~40 s | Index lines by student; export per department or per day |
| Memory | 141 MB | 198 MB | ~0.3 GB | Fits the 1 GiB container; 2 GiB in ADR 0007 phase 1 gives headroom |
| AI quota (Azure engine) | up to ~5.6 M tokens | - | up to ~50 M tokens | Higher quota plus the background queue; reused decisions avoid repeat calls |

See also [ADR 0007](../adr/0007-capacity-for-800-transcripts.md) for the capacity plan and [roadmap](../roadmap.md) for the order of work.

## Caveats

- Offline engine only. The Azure OpenAI engine's latency and quota are covered by ADR 0007, not measured here.
- In-memory store, as in tests and local runs. With PostgreSQL every change is also written to the database (a few ms per write, ADR 0007); reads still come from memory.
- One process, one request at a time. Concurrent users share one Python process; that is not measured here.
- The 10x column is extrapolated from the measured 1x-5x trend, not measured.
