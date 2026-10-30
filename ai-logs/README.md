# AI usage logs

Every agent run that produced or changed something in this repo has a log here, one file per run:
`ai-logs/<date>/<agent>-<NN>.md`, written from [TEMPLATE.md](TEMPLATE.md).

Agent roles are defined in [`agents/`](../agents/). Each role has a human owner who reviews its output.

| Role | Definition | Human owner |
| --- | --- | --- |
| BA / Discovery | [ba-discovery.md](../agents/ba-discovery.md) | Product lead |
| Synthetic Data | [synthetic-data.md](../agents/synthetic-data.md) | Data / QA lead |
| Architect | [architect.md](../agents/architect.md) | Tech lead |
| Developer | [developer.md](../agents/developer.md) | Backend + front-end devs |
| QA | [qa.md](../agents/qa.md) | QA lead |
| Security | [security.md](../agents/security.md) | Tech lead |
| DevOps | [devops.md](../agents/devops.md) | Tech lead |
| Adoption | [adoption.md](../agents/adoption.md) | Product lead |

## Index
<!-- INDEX:START -->
| Date | Run | What | Human owner |
| --- | --- | --- | --- |
| 2026-10-26 | [architect-01](2026-10-26/architect-01.md) | First architecture and 7-day build plan | Tech lead |
| 2026-10-26 | [ba-discovery-01](2026-10-26/ba-discovery-01.md) | Problem framing, scoring map and discovery questions | puspalata sahoo (Product lead) |
| 2026-10-28 | [adoption-01](2026-10-28/adoption-01.md) | Student FAQ, evaluator quick-start, release notes, deck outline, demo runbook | Product lead |
| 2026-10-28 | [adoption-02](2026-10-28/adoption-02.md) | Adoption docs and deck updated for contract v0.3.0 (posting step) | Product lead |
| 2026-10-28 | [architect-02](2026-10-28/architect-02.md) | Repo structure, agent roles, API contract and ADRs | Tech lead |
| 2026-10-28 | [architect-03](2026-10-28/architect-03.md) | Contract v0.2.0: role matrix, reason codes | Tech lead |
| 2026-10-28 | [architect-04](2026-10-28/architect-04.md) | Contract v0.3.0: posting step, approved vs posted, decision validation, strict metric | Tech lead |
| 2026-10-28 | [ba-discovery-02](2026-10-28/ba-discovery-02.md) | Apply sponsor answers to the plan | puspalata sahoo (Product lead) |
| 2026-10-28 | [ba-discovery-03](2026-10-28/ba-discovery-03.md) | Sponsor answer summary and user stories | puspalata sahoo (Product lead) |
| 2026-10-28 | [developer-01](2026-10-28/developer-01.md) | FastAPI backend: store, rules engine R01–R24, matcher, API | Backend + AI dev |
| 2026-10-28 | [developer-02](2026-10-28/developer-02.md) | Angular front end (student status, evaluator workbench, evaluation, registrar) | Front-end dev |
| 2026-10-28 | [developer-03](2026-10-28/developer-03.md) | Backend hardening for contract v0.2.0: default-deny roles, reason codes, managed identity, upload limits, LLM output validation | Backend + AI dev |
| 2026-10-28 | [developer-04](2026-10-28/developer-04.md) | Front end on contract v0.2.0: role gating, 401/403 guidance, reason codes from API | Front-end dev |
| 2026-10-28 | [developer-05](2026-10-28/developer-05.md) | Backend for contract v0.3.0: posting step, approved vs posted, decision validation, metrics, parse time-out, pinned deps | Backend + AI dev |
| 2026-10-28 | [developer-06](2026-10-28/developer-06.md) | Front end on contract v0.3.0: approved vs posted, posting step, strict metric, SWA security config (F-01) | Front-end dev |
| 2026-10-28 | [developer-07](2026-10-28/developer-07.md) | Backend reminder wording | Backend + AI dev |
| 2026-10-28 | [devops-01](2026-10-28/devops-01.md) | Dockerfile, Azure Bicep, CI and OIDC deploy workflows | Tech lead |
| 2026-10-28 | [devops-02](2026-10-28/devops-02.md) | Align infra with backend env vars; API-only CORS | Tech lead |
| 2026-10-28 | [qa-01](2026-10-28/qa-01.md) | Backend test suite and matcher evaluation on the 30 holdout decisions | QA lead |
| 2026-10-28 | [qa-02](2026-10-28/qa-02.md) | Role-matrix, upload-limit, reason-code and LLM-validation tests; eval metrics redefined | QA lead |
| 2026-10-28 | [qa-03](2026-10-28/qa-03.md) | Tests for contract v0.3.0: posting step, approved vs posted, decision validation, parse time-out | QA lead |
| 2026-10-28 | [security-01](2026-10-28/security-01.md) | STRIDE threat model, Dependabot and backend review checklist | Tech lead |
| 2026-10-28 | [security-02](2026-10-28/security-02.md) | Backend security review against the checklist | Tech lead |
| 2026-10-28 | [security-03](2026-10-28/security-03.md) | Re-review of fixed findings F-01, F-02, F-04, F-06, F-07 | Tech lead |
| 2026-10-28 | [synthetic-data-01](2026-10-28/synthetic-data-01.md) | First synthetic data set (fictional colleges) | Data / QA lead |
| 2026-10-28 | [synthetic-data-02](2026-10-28/synthetic-data-02.md) | Rebuild on Northeastern + NYU | Data / QA lead |
| 2026-10-28 | [synthetic-data-03](2026-10-28/synthetic-data-03.md) | Transcript layout change | Data / QA lead |
| 2026-10-29 | [adoption-01](2026-10-29/adoption-01.md) | Rename the agent folder, name the assistant, rewrite README around the problem statement | Sagar (spathur) |
| 2026-10-29 | [architect-05](2026-10-29/architect-05.md) | Review of the public credit check and chat (developer-26) | psahoo (POD) |
| 2026-10-29 | [developer-01](2026-10-29/developer-01.md) | Remove "synthetic data" wording from the UI | Sagar (spathur) |
| 2026-10-29 | [developer-02](2026-10-29/developer-02.md) | Store uploaded transcripts and syllabi in Azure Blob Storage | Sagar (spathur) |
| 2026-10-29 | [developer-03](2026-10-29/developer-03.md) | Entra ID sign-in with app roles (Student, Department, …) | Sagar (spathur) |
| 2026-10-29 | [developer-04](2026-10-29/developer-04.md) | Home / SSO sign-in page: My view, Student View, Department View | Sagar (spathur) |
| 2026-10-29 | [developer-05](2026-10-29/developer-05.md) | Portal sign-in: per-student and per-department accounts with registration | Sagar (spathur) |
| 2026-10-29 | [developer-06](2026-10-29/developer-06.md) | Fix "You are not signed in or your session has expired" | Sagar (spathur) |
| 2026-10-29 | [developer-07](2026-10-29/developer-07.md) | Persist registered portal accounts in Blob Storage | Sagar (spathur) |
| 2026-10-29 | [developer-08](2026-10-29/developer-08.md) | Remove the top-bar Sign in link (portal mode) | Sagar (spathur) |
| 2026-10-29 | [developer-09](2026-10-29/developer-09.md) | Remove the page footer line | Sagar (spathur) |
| 2026-10-29 | [developer-10](2026-10-29/developer-10.md) | Remove the "AI recommends, rules compute, evaluators decide" wording everywhere in the app | Sagar (spathur) |
| 2026-10-29 | [developer-11](2026-10-29/developer-11.md) | "Syllabus needed, please upload" email when Upload syllabus is clicked | Sagar (spathur) |
| 2026-10-29 | [developer-12](2026-10-29/developer-12.md) | Send the syllabus emails through a Logic App + Office 365 Outlook | Sagar (spathur) |
| 2026-10-29 | [developer-13](2026-10-29/developer-13.md) | Status page title "Transfer credit status"; no student picker for students | Sagar (spathur) |
| 2026-10-29 | [developer-14](2026-10-29/developer-14.md) | Persist all changing data in PostgreSQL (bu-solution-pg / butransfer) | Sagar (spathur) |
| 2026-10-29 | [developer-15](2026-10-29/developer-15.md) | Model-answer cache, parallel ranking and startup warm-up (ported from bu-solutions) | psahoo (POD) |
| 2026-10-29 | [developer-16](2026-10-29/developer-16.md) | Student contact fields and the bu_school = NULL fix (ported from bu-solutions) | psahoo (POD) |
| 2026-10-29 | [developer-17](2026-10-29/developer-17.md) | Portal registration accepts any email; the email is saved on the student record | psahoo (POD) |
| 2026-10-29 | [developer-18](2026-10-29/developer-18.md) | Student page: a "Start here" panel for new students; transcript upload becomes secondary | psahoo (POD) |
| 2026-10-29 | [developer-19](2026-10-29/developer-19.md) | Transcript upload records: previous school's student ID, duplicate detection, change summary | psahoo (POD) |
| 2026-10-29 | [developer-20](2026-10-29/developer-20.md) | Never compare the transcript's Student ID with portal IDs | psahoo (POD) |
| 2026-10-29 | [developer-21](2026-10-29/developer-21.md) | Loader while a transcript is read | psahoo (POD) |
| 2026-10-29 | [developer-22](2026-10-29/developer-22.md) | Upload hardening for transcripts and syllabi: junk, hostile and scanned PDFs, file size | psahoo (POD) |
| 2026-10-29 | [developer-23](2026-10-29/developer-23.md) | Azure AI Search picks the model's BU candidate shortlist | psahoo (POD) |
| 2026-10-29 | [developer-24](2026-10-29/developer-24.md) | A syllabus can be uploaded only once; the button disappears after the upload | Sagar (spathur) |
| 2026-10-29 | [developer-25](2026-10-29/developer-25.md) | Prompt experiment: a broader definition of "covered" (rejected, reverted) | psahoo (POD) |
| 2026-10-29 | [developer-26](2026-10-29/developer-26.md) | Public "Will my course transfer?" check and chat (no login) | psahoo (POD) |
| 2026-10-29 | [developer-27](2026-10-29/developer-27.md) | Fix the architect-05 and security-04 findings on the public credit check and chat | psahoo (POD) |
| 2026-10-29 | [developer-28](2026-10-29/developer-28.md) | Quick check: a course picker for the chosen school | psahoo (POD) |
| 2026-10-29 | [developer-29](2026-10-29/developer-29.md) | Chat UX polish on the public "Will my course transfer?" page | psahoo (POD) |
| 2026-10-29 | [developer-30](2026-10-29/developer-30.md) | Chat keeps its context; partial school and course codes get matches | psahoo (POD) |
| 2026-10-29 | [devops-03](2026-10-29/devops-03.md) | Containerised frontend + lean Azure Container Apps deployment | Sagar (spathur) |
| 2026-10-29 | [security-04](2026-10-29/security-04.md) | Security review of the public credit check and chat (developer-26) | psahoo (POD) |
| 2026-10-30 | [architect-06](2026-10-30/architect-06.md) | Review of the course picker, chat context, partial matching and workbench identity | psahoo (POD) |
| 2026-10-30 | [developer-01](2026-10-30/developer-01.md) | One-click Approve on the selected BU candidate for Department approvers | Sagar (spathur) |
| 2026-10-30 | [developer-02](2026-10-30/developer-02.md) | Green candidate Approve button | Sagar (spathur) |
| 2026-10-30 | [developer-31](2026-10-30/developer-31.md) | Workbench: the department and the evaluator name come from the signed-in account | psahoo (POD) |
| 2026-10-30 | [developer-32](2026-10-30/developer-32.md) | Evaluator workbench UX | psahoo (POD) |
| 2026-10-30 | [developer-33](2026-10-30/developer-33.md) | Review fixes, and why each design decision was taken | psahoo (POD) |
| 2026-10-30 | [developer-34](2026-10-30/developer-34.md) | Step 5: automatic syllabus request, and the syllabus next to the AI comparison | psahoo (POD) |
| 2026-10-30 | [developer-35](2026-10-30/developer-35.md) | Syllabus reminders every 2 days | psahoo (POD) |
| 2026-10-30 | [developer-36](2026-10-30/developer-36.md) | In-app notifications for students | psahoo (POD) |
| 2026-10-30 | [developer-37](2026-10-30/developer-37.md) | Remove "Other staff" from the front page | Sagar (spathur) |
| 2026-10-30 | [security-05](2026-10-30/security-05.md) | Security review of the course picker, chat context, partial matching and workbench identity | psahoo (POD) |
<!-- INDEX:END -->

Regenerate the index with `python scripts/build_log_index.py`.
