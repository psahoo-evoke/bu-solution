# developer-23 · Azure AI Search picks the model's BU candidate shortlist

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Agent (role) | developer (+ devops: index script, deploy step) |
| Tool / model | Solutionauts AI (CLI) |
| Human owner | psahoo (POD) |
| Trigger | "let get it done Azure AI Search now"; the human pointed at the existing service `bu-solution-serach` (Standard, Central US, RG AI-F-TheSolutionauts), added the endpoint, admin key and index name to `backend/.env`, and reported no quota for `text-embedding-3-small` |

## Prompt (summary or verbatim)
Replace the offline shortlist ("Azure AI Search in prod") with Azure AI Search. List the edge cases before building.

## Inputs used
- `backend/app/matcher.py` (`_azure_rank`, `build_prompt`, `validate_llm_output`), `infra/modules/ai.bicep` and `roles.bicep` (planned Search service and roles), `scripts/deploy_aca.sh`
- `bu-solution-serach`: admin key works, no indexes. `bu-solution-resource`: no embedding deployment (`DeploymentNotFound` for 3-small, 3-large and ada-002).

## Output
- Edge cases listed first and covered by tests:
  - not configured; service down, slow or throttled
  - index missing, empty or out of date; codes not in the catalogue; fewer than 10 results
  - search syntax and injected text in the query; student data kept out of the query
  - query and embedding size limits; no embedding model or no quota
  - semantic ranker off
  - 8 parallel calls (one retry on 429/503)
- New `backend/app/search.py` (REST through urllib, no new dependency):
  - auth: `AZURE_SEARCH_API_KEY` if set, else `DefaultAzureCredential`
  - index `bu-courses`: BU catalogue only. Key `id` is the base64url of `bu_code`, because keys can't contain spaces. Fields: `bu_code`, `dept`, `title`, `description`, `learning_outcomes`, `topics`, `content_hash`; semantic configuration `default`; `content_vector` (size taken from the model) only when embeddings work.
  - `sync_index()` creates the index or rebuilds it when its layout changes, upserts the catalogue and deletes stale documents.
  - `shortlist()`: the query is plain words from the external course only (filtered for injection, max 120 terms), sent as keyword search, plus semantic ranking and vectors when available. A feature the service rejects with 400 is dropped for the process; any other failure returns None. Shortlists and embeddings are cached in memory.
  - embeddings can use their own resource (`AZURE_OPENAI_EMBEDDING_ENDPOINT` / `_API_KEY`), e.g. a region with quota; a 404 deployment turns vectors off once.
- `backend/app/matcher.py`:
  - new `candidate_shortlist()`: Search order is kept, unknown codes are dropped, and the list is topped up from the offline ranking to 10. With no usable results, the offline shortlist is used.
  - `_azure_rank` returns `(ranked, retrieval)`, and `recommend()` adds `retrieval` ("azure-ai-search" or "offline").
  - the offline engine is unchanged.
- New `scripts/build_search_index.py` (catalogue from the seed CSV, no database).
- `scripts/deploy_aca.sh`: optional `SEARCH_SERVICE=<name>`. It gives the API's system identity **Search Index Data Reader** (read only, no key in the app) and sets `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_INDEX` and `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`.
- `infra/README.md`: settings row. `tests/conftest.py` keeps tests offline (search and embedding settings removed, caches reset).
- Live: index `bu-courses` was first built with keyword plus semantic only (the semantic ranker is on, no embedding deployment yet). After the human deployed `text-embedding-3-large` on `bu-solution-resource`, the script rebuilt it with 150 BU courses and 3072-size vectors. All three are now on: keyword, semantic and vector.

## Human review
- The human chose to use the existing service and to proceed without vectors for now (no embedding quota). Options given: Global Standard deployment type, `text-embedding-3-large` or `ada-002`, or another region's resource through `AZURE_OPENAI_EMBEDDING_ENDPOINT`.

## Verification
- `pytest -q backend`: 402 passed (17 new in `test_search.py`), offline.
- Holdout evaluation (30), gpt-4.1-mini:
  - with Search: top-1 86.7%, strict 40.0%, wrong credit 0.0%, gates met
  - same run with the offline shortlist: 90.0% / 40.0% / 0.0%
  - offline engine: 100% / 60% / 0%
- Retrieval check on the 17 held-out Equivalent decisions: the recorded BU course is in Search's top 10 for 17/17 and ranked first for 17/17, the same as the offline shortlist. So the difference in top-1 is the model's choice between runs (earlier runs: 93.3% vs 96.7%), not retrieval.
- Live API: `/courses/NYU|PSYCH-UA 10/recommendation` returned `engine: azure-openai`, `retrieval: azure-ai-search`. The model picked CAS MA 113 at 50% (Evaluator decides), although Search ranked CAS PS 211 first.
- Hybrid search (keyword, semantic and vector with `text-embedding-3-large`), two runs: top-1 86.7% both times, strict 40.0% / 30.0%, wrong credit 0.0%, gates met. Retrieval: 17/17 ranked first. The same 4 misses as keyword search.
- **Finding for a follow-up:** the 4 misses (MATH-UA 235, CHEM 1703, CHEM-UA 63, ECON 2706) are all recorded Equivalent. Search ranks the recorded BU course first, but the model scores the outcome overlap 17–50% (the offline engine says 75–100%) and picks another course or Elective. That's model or prompt calibration, not retrieval; e.g. the prompt sends BU outcomes but not BU topics. Not changed here.

## Commit
see git log
