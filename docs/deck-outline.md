# TransferIQ: deck outline (EvoHack 2026)

20-minute presentation + 10-minute Q&A. Slides follow the judges' required order: 1 Discovery, 2 Solution + architecture, 3 AI agents used, 4 Quality, validation and security, 5 Metrics and business impact, 6 Future scope, 7 Live demo.

**Number labels.** Every number on a slide carries one tag:
- **[M] measured**: we ran it in this repo on 2026-10-28.
- **[S] sponsor estimate**: from the sponsor's answers (`docs/discovery/sponsor-answers.md`). The sponsor marked most of these "Assumption"; they are not BU data.
- **[A] assumption**: ours.

## Timing

| # | Slide | Judges' section | Time | Running |
| --- | --- | --- | --- | --- |
| 0 | Title | — | 0:30 | 0:30 |
| 1 | The problem we found | 1 Discovery | 2:00 | 2:30 |
| 2 | Solution and architecture | 2 Solution | 2:00 | 4:30 |
| 3 | AI agents used: discovery to adoption | 3 AI agents | 2:30 | 7:00 |
| 4 | Quality, validation and security | 4 Quality | 1:45 | 8:45 |
| 5 | Honest limits | 4 Quality | 0:45 | 9:30 |
| 6 | Metrics and business impact | 5 Metrics | 1:15 | 10:45 |
| 7 | Future scope | 6 Future | 0:45 | 11:30 |
| 8 | Live demo | 7 Demo | 8:00 | 19:30 |
| 9 | Close | — | 0:30 | **20:00** |

Scoring map: AI-First Delivery 30 (slides 3, 4, 5), Solution design 25 (slide 2), Problem fit and ROI 20 (slides 1, 6), Technical creativity / UX 15 (slide 8, live), Communication 10 (all; keep to time).

---

## Slide 0 · Title (0:30)

**TransferIQ: an AI co-pilot for BU transfer credit**
Tagline: *AI recommends, rules compute, evaluators decide.*
Team solutionauts · EvoHack 2026 · Synthetic data only.

> Speaker notes: "Every transfer student asks the same question: what counts? Today a 'maybe' course takes about two months to answer. We built a co-pilot that does the comparison work for the evaluator and never takes the decision away from them."

## Slide 1 · Discovery insights and the key problem (2:00)

**Left: how we discovered.** 33 questions sent to the sponsor [M: count in the discovery log], grouped into volume/time, evaluators, students, rules/systems and success. Answers changed the plan: headline outcome, ~24 rules (R01–R24), BU status codes.

**Right: what we learned** (all [S])
| | |
| --- | --- |
| Courses evaluated per year | ~8,000 (800 students × 10) |
| "Maybe" courses | 35 % → ~2,800 / year |
| Evaluator time per syllabus | 12 min |
| Days to posting | ~7 for an existing match, ~60 for a "maybe" |
| Evaluators | 12 (2 per department × 6) |
| Maybe courses that never get a syllabus | ~10 % |

**Key problem (one line):** the slow, expensive part is the ~2,800 "maybe" courses, where an evaluator reads a syllabus against BU courses by hand, and the student waits weeks without knowing what is secured.

**Constraints we designed for:** no Transferology / BU equivalency DB access → our own equivalency table; no MyBU integration → MyBU-style CSV; FERPA → synthetic data only, no names or IDs to the AI; descriptions are not evidence.

> Speaker notes: Stress the cross-check from ba-discovery-02: 12 evaluators × ~120 reviews × 2 terms ≈ 2,880 reviews against ~2,800 maybe courses, so the sponsor's numbers hang together [S, consistency check]. Say clearly these are sponsor estimates, not BU data.

## Slide 2 · Solution approach and architecture (2:00)

**Three layers, one rule each:**
1. **Rules compute.** R01–R24 in plain Python (eligibility, quarter × 2/3, lookup, duplicates, residency, 68-unit cap, codes). No AI in credit math (ADR 0001).
2. **AI recommends.** Only for "maybe" courses with a complete syllabus: top-3 BU candidates, learning-outcome overlap, tier ≥ 80 / 50–79 / < 50, covered vs missing outcomes. Syllabus text is untrusted (ADR 0004).
3. **Evaluators decide.** One click with a reason code; reusable decisions build our own equivalency table, so the next student matches instantly.

**Architecture diagram:** use the mermaid diagram in `docs/architecture.md` (Angular SPA on Static Web Apps → FastAPI on Container Apps → Document Intelligence, AI Search, Azure OpenAI, Communication Services, PostgreSQL, Blob, Key Vault, App Insights). Highlight the learning loop: decision → equivalency table → instant match.

**Footer:** 5 ADRs: rules in code, own equivalency table, offline matcher fallback, syllabus is untrusted, default-deny role matrix.

> Speaker notes: Be explicit that the Azure design is written as Bicep and compiles cleanly [M], but it is **not deployed**; the demo runs locally with the offline matcher (ADR 0003). Point at the one-course data flow: line → rules → lookup → syllabus check → matcher → evaluator → reusable decision → **posted at once** → T, secured → CSV (the Registrar's posting step only catches a failed save).

## Slide 3 · AI agents used: from business analysis to adoption (2:30)

**Visual: a pipeline of 8 role agents**, each a file in `agents/`, each run logged in `ai-logs/` from one template, each with a human owner. CI fails if code changes without a log entry (`scripts/check_ai_logs.sh`).

| Stage | Agent role | Runs [M] | Human owner | What it produced (from the logs) |
| --- | --- | --- | --- | --- |
| Business analysis | ba-discovery | 3 | Product lead | Problem framing + scoring map; 15 proposed questions (team sent 33); applied sponsor answers (ROI, rules, codes); 12 user stories US-01..12 |
| Data | synthetic-data | 3 | Data / QA lead | 150 BU, 194 external courses, 100 past decisions (70/30 split), 4 students, 7 transcripts, 12 syllabi incl. a red-team injection syllabus; 20 test cases |
| Design | architect | 4 | Tech lead | Architecture + 7-day plan; repo, agent roles, OpenAPI contract, ADRs 0001–0004; contract v0.2.0 role matrix + ADR 0005; contract v0.3.0 (posting step, approved vs posted, decision validation, strict metric) |
| Build | developer | 7 | Backend + AI dev; Front-end dev | FastAPI backend (rules R01–R24, matcher, API); Angular front end (4 screens); security hardening; role-aware UI; posting step, decision validation, PDF parse time-out, pinned deps; CSP / SWA config; honest reminder wording |
| Test | qa | 3 | QA lead | Test suite (107 → 268 → 301 tests), holdout evaluation and report, redefined metrics more strictly, end-to-end posting tests |
| Secure | security | 2 | Tech lead | STRIDE threat model, Dependabot, checklist; live review: 30 items, 117 role probes, 0 mismatches |
| Ship | devops | 2 | Tech lead | Dockerfile, Bicep for all Azure services, CI with AI-log check, OIDC deploy; env-var alignment |
| Adopt | adoption | 2 | Product lead | Student FAQ, evaluator quick-start, release notes, this deck outline, demo runbook; checked the docs against the running app and reported 12 inconsistencies, which started the v0.3.0 round |

**Total: 26 logged runs across 8 roles** [M: files in `ai-logs/` on 2026-10-28, including adoption-02; re-count on the day if more runs are added]. Tools: Solutionauts AI (Cowork) for discovery, data, architecture and small fixes (architect-01..04, developer-07); Solutionauts AI subagents for build, test, security, ops and adoption.

**Callout: humans stayed in charge (3 examples from the logs)**
- synthetic-data-01 **rejected** by the human: fictional colleges replaced with Northeastern + NYU, the schools the hackathon supplied.
- synthetic-data-03: the agent **declined** to put a real university letterhead on a fake transcript; the human accepted a fictional stand-in.
- qa-02: the coordinator asked for a **stricter** metric; the agent rewrote the evaluation and added the 60 % strict number instead of keeping only the 100 % headline.

**Callout: agents checked each other (two full loops).**
- Security loop: security-01 found missing role checks → architect-03 wrote the role matrix → developer-03/04 built it → qa-02 tested 138 role cases → security-02 verified it live (117 probes, 0 mismatches).
- Adoption loop: adoption-01 walked the demo against the sponsor's process. It found that approved credit showed as secured before posting, that the strict metric was not on screen, and that the reminder text claimed emails were sent. Then architect-04 wrote contract v0.3.0 → developer-05/06/07 built it (with security fixes F-01, F-02, F-04, F-06, F-07) → qa-03 added 23 posting tests → adoption-02 updated the runbook and the deck. **The adoption agent changed the product, not just the slides.**

> Speaker notes: This slide carries the 30-point AI-First criterion. Say "agents did the business analysis and adoption, not only the code". Run counts: ba-discovery 3, synthetic-data 3, architect 4, developer 7, qa 3, security 2, devops 2, adoption 2 = **26 runs**. One run (synthetic-data-01) was superseded and not imported; say so if asked. Be honest: 19 of the 25 logs before adoption-02 still say "Human review: pending" (20 of 26 with adoption-02). Close those reviews before demo day, or the slide's "human owner" column is a claim, not evidence.

## Slide 4 · Quality, validation and security (1:45)

**Tests** [M, 2026-10-28]
- Backend: **301 passed**, 0 failed, fully offline (`python3 -m pytest -q`): roles 148, rules 74, postings 23, API 19, LLM validation 14, hardening 12, matcher 11.
- Rules: all **56** expected transcript lines reproduced (55 exactly; the 56th differs only in a narration note, not a rule result).
- Front end: **25** unit tests passed; Playwright demo flow **7/7**, including approve → TP → post → T (developer-06).

**AI quality on 30 held-out decisions** [M, offline engine]
| Metric | Result | Gate |
| --- | --- | --- |
| (a) Top-1 candidate agreement | 100 % (30/30; 12 are deferrals) | ≥ 80 % [S] met |
| (b) Strict decision agreement | 60 % (18/30) | reported |
| (c) Wrongly suggested credit | 0 % (0/30) | ≤ 2 % [S] met |
Not tuned on the holdout.

**Security** [M]: STRIDE threat model; default-deny on every route; live probe of 117 role checks with 0 mismatches; uploads limited (413 / 415 / 422); prompt injection test T17 flagged and tier unchanged (62 %); no names, IDs or ground truth in prompts (unit-tested); `pip-audit` and `npm audit` clean. Review (security-02): 30 items, 24 pass, 3 fail (low/medium), 3 N/A; 0 critical, 0 high. Since then the developers fixed F-01 (CSP + SWA config), F-02 (decision validation), F-04 (PDF parse time-out), F-06 (server-generated file names) and F-07 (pinned versions), with tests (qa-03). **The security agent has not re-reviewed these fixes yet.**

> Speaker notes: Always say (a) and (b) together, never 100 % alone. Explain (b): under the sponsor's own rule, the AI must not decide 50–79 % courses, so every correct deferral counts as a miss in (b). (c) is the safety number: no unearned credit was ever suggested.

## Slide 5 · Honest limits (0:45)

- **Offline engine.** All AI numbers come from a deterministic word-overlap matcher. Azure OpenAI is built and its output validation is unit-tested, but it has **not been evaluated**.
- **Synthetic data favours our matcher.** External courses were generated from exact BU topic strings. Real syllabi paraphrase. These numbers prove the pipeline, tiers and safety gates work, **not** real-world accuracy.
- **Small sample.** n = 30: one wrong credit = 3.3 %, which would break the 2 % gate.
- **Strict agreement is 60 %**, not 100 % (now shown on the evaluation page next to top-1). On Elective rows, (a) checks only the department.
- **Not deployed.** Bicep compiles, nothing runs in Azure yet. Demo roles are a header, not sign-in.
- **No measured time saving yet.** The under-2-minute target is the sponsor's goal; we show a timer, not a study.

> Speaker notes: Say this before the judges ask. It earns trust for the numbers on the next slide.

## Slide 6 · Metrics and business impact (1:15)

**ROI (all inputs [S]; arithmetic ours)**
| | |
| --- | --- |
| Baseline: 2,800 maybe courses × 12 min | **560 h / year** |
| Target: under 2 min per course | **~93 h / year** |
| Evaluator time returned | **~467 h / year** |

**Student impact**
- Maybe courses today: ~60 days to posting [S]. Instant answers for ineligible courses and existing matches. Reusable decisions mean a course is decided once, not once per student; the next student's line skips the evaluator and waits only for posting.
- Students see secured vs pending units from day one, and exactly which document is missing, with reminders on days 7 / 21 / 45.

**Success test (sponsor) → where we are**
| Goal [S] | Status |
| --- | --- |
| Time per course 12 → < 2 min | Not measured yet [A: comparison pre-done + one click + batch] |
| Top-1 agreement ≥ 80 % | 100 % (a), 60 % strict (b) [M, offline, synthetic] |
| Wrongly suggested credit ≤ 2 % | 0 % [M, offline, synthetic] |

> Speaker notes: The ~467 hours is a sponsor-estimate scenario, not a measurement. Our pilot proposal (next slide) is how BU would measure it.

## Slide 7 · Future scope (0:45)

1. **Pilot measurement:** time real evaluators per course (before vs after) on one department; run the Azure OpenAI engine on the same 30 holdout + real, paraphrased syllabi.
2. **Production hardening:** Entra ID sign-in, PostgreSQL + Blob (persistent audit log, F-05), a security re-review of the v0.3.0 fixes, private endpoints, and a real SWA deployment to confirm the CSP headers.
3. **Real reminders** via Communication Services email + portal; a "two syllabi" view for split courses (T19) and combined courses (T20).
4. **Integrations** when BU grants access: Transferology / BU equivalency DB import, MyBU posting instead of CSV.
5. **More departments and rules** (e.g. Engineering residency R16).

> Speaker notes: Keep it short; the demo is next.

## Slide 8 · Live demo end to end (8:00)

Follow `docs/demo-runbook.md` exactly. Script outline:
1. Student Maya: secured vs pending, codes in words, quarter course 2.67 units, missing syllabus with reminders. (1:30)
2. Evaluator: PSYCH-UA 10 comparison already done, decide in under 2 minutes, reusable. (2:00)
3. Maya's PSYCH-UA 10 is now T "Posted – credit secured": secured 14.67 → 18.67. PSYCH-UA 25: preliminary, not decidable → student uploads syllabus → decidable at 62 %. (1:15)
4. Liam's ECON-UA 266: injection warning, tier unchanged. Liam's PSYCH-UA 10: matched instantly by reuse (TP, awaiting his posting). (1:15)
5. AI evaluation page (top-1, strict, deferrals, wrong credit) → Registrar → MyBU CSV with Maya's posted row. (2:00)

Backup: pre-recorded video + screenshots (see runbook fallback).

## Slide 9 · Close (0:30)

*AI recommends, rules compute, evaluators decide.*
Three take-aways: (1) a real sponsor problem with a ~467 h/year [S] answer, (2) a full agent pipeline from business analysis to adoption, logged and human-owned, (3) safety first: 0 % wrongly suggested credit [M, offline, synthetic], injection flagged, AI never posts credit.

## Q&A prep (10 min)

| Likely question | Answer |
| --- | --- |
| "100 % sounds too good." | It is the offline engine on synthetic data built from exact topic strings. Strict agreement is 60 %. We claim the pipeline and the safety gates, not real-world accuracy (eval-report caveats). |
| "What does the LLM actually do?" | Scores outcome overlap for search candidates, returns strict JSON. Code checks every BU code is from the shortlist, clamps overlap, recomputes the tier. Any bad output falls back to offline. |
| "What stops the AI granting credit?" | Only a human role can call `/decisions`, and the server validates every decision (real BU course, matching reason code). Batch needs > 90 % and an Evaluator/Department role. Units come only from `rules.py`. Credit is secured only after a separate Registrar posting step. |
| "Why does Liam's reused course still say pending?" | Matching is instant, but posting is per student record, like the real Department → Registrar flow. Open design question for the sponsor: should a reused table match be secured at once (developer-05 note)? |
| "FERPA?" | Synthetic only. Prompts contain course data only (unit-tested). Production: BU tenant, school-official agreement, Entra roles, retention policy. |
| "Why not Transferology?" | No access was granted (sponsor). We built our own equivalency table with reason codes and a reusable flag; it can import later. |
| "Cost?" | DevOps estimate ≈ $130–170 / month for the demo-sized Azure footprint [A, not deployed]. |
| "Who checked the agents?" | Each run has a named human owner; examples of rejected and corrected runs on slide 3. CI blocks code changes without a log. |
