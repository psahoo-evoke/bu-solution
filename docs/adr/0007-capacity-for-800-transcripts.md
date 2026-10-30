# ADR 0007 · Capacity for an intake of 800 transcripts

**Status:** proposed (2026-10-30). Builds on ADR 0003 (offline matcher fallback). Changes `infra/main.bicep`, `infra/modules/containerapp-api.bicep` and, in phase 2, the backend.

**Context.** An intake cycle can bring about 800 transcripts in a few days, with peaks of a few hundred in one day. Today the API runs as **one replica** (0.5 vCPU, 1 GiB), and Azure OpenAI is deployed at **10K tokens per minute**. The question is what has to change so that every transcript gets an AI comparison, not the offline fallback, within an acceptable time.

## Where the time goes (measured 2026-10-30)

Measured on a developer laptop with the seeded data:

| Step per transcript | Cost | Scales with |
|---|---|---|
| Read the PDF (pdfplumber, text PDF) | ~40 ms CPU | transcripts |
| Rules engine (R01-R24) | < 1 ms CPU | transcripts |
| Offline shortlist, per "maybe" course | ~75 ms CPU | maybe courses |
| **Azure OpenAI comparison, per maybe course** | **~2,800 tokens in + ~300 out ≈ 3,100 tokens** | **distinct (course, syllabus) pairs** |
| PostgreSQL writes | a few ms | transcripts |

- **CPU is not the limit.** 800 transcripts need about 800 × 0.2 s ≈ 3 minutes of CPU in total. On 0.5 vCPU that is perhaps 10 minutes, spread across the day.
- **The AI quota is the limit.** The model's answers are cached by prompt, so the cost depends on the number of **distinct** courses, not on transcripts:

| Scenario | Distinct maybe courses | Tokens | Time at 10K TPM | at 150K TPM | at 300K TPM |
|---|---|---|---|---|---|
| Students from a few peer schools (NEU/NYU catalog, ~200 courses) | ~200 | ~0.6 M | ~1 h | ~4 min | ~2 min |
| Mixed schools, 3 maybe courses each, little overlap | ~2,400 | ~7.4 M | **~12 h** | ~50 min | ~25 min |

- When the quota is exceeded, calls fail and the app falls back to the offline matcher (ADR 0003). The intake still completes, but with weaker comparisons and nothing to say so.
- **More replicas do not help.** Every replica shares the same Azure OpenAI quota. Replicas are also unsafe today: the API reads from a copy of the PostgreSQL data held in memory, so a second replica would not see the first one's decisions until it restarts (`maxReplicas` is capped at 1 for this reason).

## Options

- (a) Scale out the API (more replicas). Does not raise the AI quota, and breaks data consistency until reads come from PostgreSQL. **Rejected for now.**
- (b) Scale up the single replica, and raise the AI quota. Small change, no code change, keeps the data consistent. **Chosen as phase 1.**
- (c) Queue the AI work in the background. Uploads return straight away, and comparisons run at the pace the quota allows instead of failing over to offline. **Chosen as phase 2.**
- (d) Read from PostgreSQL on every request, so the API can run as several replicas. Only needed for much more than 800 transcripts, or for zero-downtime deployments. **Phase 3, only if needed.**

## Proposal

### Phase 1: parameter changes only (before the intake)

| Resource | Today | Proposed | Why |
|---|---|---|---|
| Azure OpenAI deployment (`openAiCapacity`) | 10K TPM | **150K TPM** (300K if the subscription quota allows) | The real bottleneck: 12 h → under 1 h in the worst case above |
| API container (`cpu` / `memory`) | 0.5 vCPU / 1 GiB | **2 vCPU / 4 GiB** | Room for PDF reading, parallel model calls (`MAX_PARALLEL = 8`) and the in-memory data of 800 students |
| API replicas (`minReplicas` / `maxReplicas`) | 1 / 1 | **1 / 1** (unchanged) | Data consistency, see above |
| PostgreSQL (`postgresSku`) | Standard_B1ms (Burstable, 1 vCore) | **Standard_B2s** for the intake weeks | Burst credits run out under sustained writes; B2s doubles the baseline. Storage of 32 GB is ample. |
| Document Intelligence (`docIntelSku`) | S0 | S0 (unchanged) | Only scanned PDFs use OCR; S0 handles this volume |
| Azure AI Search (`searchSku`) | basic | basic (unchanged) | One query per maybe course |

- Azure OpenAI quota is per subscription and region. Check the available TPM for the model in `eastus2` before deploying, and request an increase if it is below the target.
- Scale back after the intake: the model capacity and the PostgreSQL SKU are parameters, so it is one redeploy.

### Phase 2: background AI queue (backend change, ~1-2 days)

- A transcript upload stores the lines and returns at once. Its maybe courses are marked "comparison pending".
- One worker in the API process sends the model calls, keeping under the configured TPM (a token bucket). On a 429 it waits and retries instead of falling back to offline.
- The cached model results are stored in PostgreSQL, so a restart does not pay for the comparisons again (today the cache is in memory).
- The workbench and the status page show "AI comparison pending" until the result arrives. Offline is used only when the model is not configured or keeps failing.

### Phase 3: several replicas (only if needed)

- Each request checks a change counter in PostgreSQL (one cheap query) and reloads only what changed. Alternatively, readers query the database directly.
- Then lift the `@maxValue(1)` cap on `maxReplicas`.

## Consequences

- **Phase 1** removes the bottleneck for this intake with no code change and no risk to data consistency. The API is still a single point of failure: a restart means about a minute of downtime and a cold model cache.
- **Phase 2** makes the AI path predictable under load: no silent fallback to offline, and no paying twice after a restart.
- **Cost** goes up mainly with model tokens: the same 0.6-7.4 M tokens are used whatever the quota. A higher quota only lets them be used faster. The bigger container and database only cost more during the weeks they are scaled up.
- **To check during the intake:** Application Insights already receives the API logs. Alert on HTTP 429 from Azure OpenAI and on `engine = offline-fallback` in recommendations.
