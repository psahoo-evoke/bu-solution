# Architecture (Architect agent)

**AI recommends, rules compute, evaluators decide.**

```mermaid
flowchart TB
  subgraph Users
    S[Student] --- A[Advisor]
    E[Evaluator / Department] --- R[Registrar / Credit staff]
  end
  Users -->|HTTPS + Entra token| SWA[Angular SPA<br/>Azure Static Web Apps]
  SWA --> API[FastAPI on Azure Container Apps]
  subgraph API_parts[FastAPI modules]
    ING[Ingest: transcripts, syllabi]
    RUL[Rules engine R01-R24<br/>deterministic]
    MAT[Matcher: candidates + overlap tiers]
    REV[Review + decisions + batch]
    STA[Status, reminders, MyBU CSV]
  end
  API --- API_parts
  ING --> DI[Azure AI Document Intelligence]
  MAT --> SRCH[Azure AI Search<br/>BU course index]
  MAT --> AOAI[Azure OpenAI<br/>outcome comparison]
  STA --> ACS[Azure Communication Services<br/>email reminders]
  API --> PG[(PostgreSQL<br/>courses, equivalency table, decisions, audit)]
  API --> BLOB[(Blob Storage<br/>transcripts, syllabi)]
  API --> KV[Key Vault] & AI[Application Insights]
  REV -->|approved + reusable| PG
```

| Module | Responsibility | AI? |
| --- | --- | --- |
| Ingest | Parse transcript PDF -> lines; syllabus completeness check (outcomes, schedule) | Document Intelligence + LLM normalisation |
| Rules engine | Eligibility, conversion, existing equivalency, conflicts, duplicates, residency, 68-unit cap, status codes | **No** (pure Python, unit-tested) |
| Matcher | Narrow BU candidates (search), score learning-outcome overlap, tier, evidence, injection flag | Azure OpenAI; offline fallback for CI/demo |
| Review | Queue, single decision, batch (> 90%), reuse flag, audit | No |
| Status | Plain-words status, next step, secured vs pending, reminders day 7/21/45, MyBU CSV | Status wording only |

Data flow for one course: extract line -> rules (R01–R07) -> equivalency lookup (R10–R12) -> if none: syllabus state -> matcher -> evaluator -> decision saved (reusable) -> Department -> Registrar -> CSV.

See ADRs in `docs/adr/` and the contract in `docs/api/openapi.yaml`.
