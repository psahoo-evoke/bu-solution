# developer-15 · Model-answer cache, parallel ranking and startup warm-up (ported from bu-solutions)

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | "whatever changes you have made in bu-solution repo, bring that into bu-solution-final if needed" |

## Prompt (summary or verbatim)
Compare the working copy in `bu-solutions/bu-solution` with this repo and bring over the work that is missing here.

## Inputs used
- `bu-solutions/bu-solution` working tree and its logs: `ai-logs/2026-10-29/developer-01.md` (cache), `devops-01.md` (PostgreSQL), `ai-logs/2026-10-28/devops-03.md` (run skill)
- `backend/app/matcher.py`, `evaluation.py`, `main.py`, `tests/conftest.py`, `tests/test_llm.py`

## Output
- Compared both copies file by file:
  - **Ported:** the model-answer cache and its warm-up, from developer-01 in bu-solutions.
  - **Not ported:** the PostgreSQL work (devops-01), because developer-14 here already does more, including portal accounts.
  - **Not ported:** the run skill (devops-03), because its files are identical in both copies.
- `backend/app/matcher.py` (patch applied unchanged):
  - an LRU cache (1024 entries) around the Azure OpenAI call. The key is a SHA-256 of the prompt plus endpoint, deployment and API version. Only validated answers are cached, and hits are returned as deep copies.
  - new `clear_cache()`
  - new `recommend_many()`, which runs up to 8 model calls in parallel
- `backend/app/evaluation.py`: `evaluate_holdout` uses `recommend_many`.
- `backend/app/main.py`:
  - `review_queue` ranks its rows with `recommend_many`
  - a FastAPI `lifespan` starts a daemon thread that warms the cache for the review queue and the holdout evaluation. It runs only when the engine is `azure-openai`; `TRANSFERIQ_PREWARM=0` turns it off.
  - Difference from bu-solutions: `review_queue` takes `request` here, so `_prewarm` builds the job list from `_maybe_lines()` directly instead of calling the route.
- Tests:
  - `tests/conftest.py` clears the cache around every test.
  - `tests/test_llm.py` gains the cache, failure, ordering and warm-up tests from bu-solutions.
- Rules (ADR 0001) and tiers (R20) are unchanged, and nothing changes in offline mode.

## Human review
- Pending.

## Verification
- `pytest -q backend`: 373 passed, offline.
- Live with `gpt-4.1-mini`: `/api/review-queue` took 7.9 s on the first call (warm-up still running) and 0.0 s on the second. A course recommendation reported `"engine":"azure-openai"`.

## Commit
see git log
