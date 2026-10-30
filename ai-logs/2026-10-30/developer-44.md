# developer-44 · Index transcript lines by student (volume fix)

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (Claude Code) |
| Human owner | Team lead |
| Trigger | Volume test (qa-01): review queue refresh and MyBU export grew quadratically because `Store.lines_for()` scanned every transcript line for each student. "ok correct that" |

## Prompt (summary or verbatim)
"ok correct that"

## Inputs used
- `docs/quality/scalability-report.md` (qa-01), `backend/app/store.py`, `backend/app/notifications.py`, every place that changes `Store.lines`

## Output
- `backend/app/store.py`: `lines_for()` uses a per-student index, rebuilt when the `lines` list is replaced or its length changes. Every writer either replaces the list (upload, database load, tests) or appends to it (seed load, tests); nothing edits it in place. The index holds the list it was built from, so a later list cannot reuse its id. Callers get a copy.
- `backend/app/notifications.py`: uses `lines_for()` instead of its own full scan
- `backend/tests/test_rules.py`: 3 tests: matches a full scan in transcript order for every student; follows an append, a shorter replacement and a same-length replacement; returns a copy
- `docs/quality/scalability-report.md`, `docs/roadmap.md`, `README.md`: before/after numbers

## Human review
- Team lead asked for the fix after reading the volume findings.

## Verification
- `pytest -q`: 603 passed (600 + 3 new)
- `python eval/run_volume.py --scales 1,2 --sample 200` and `--scales 5 --sample 30`, before vs after:
  - MyBU export 5x: 10.27 s -> 0.33 s; 2x: 1.03 -> 0.08 s; 1x: 0.24 -> 0.05 s
  - Queue refresh 5x: 7.38 -> 2.19 s; one department 5x: 6.41 -> 0.59 s
  - Status page p50 5x: 818 -> 308 ms
  - First queue load unchanged (matcher work, not the scan)

## Commit
See `git log -- backend/app/store.py`
