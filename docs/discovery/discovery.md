# Discovery: BU transfer credit evaluation

**Team:** THE SOLUTIONAUTS · EvoHack 2026 · Boston University problem statement · 2026-10-30

This page brings discovery together in one place: the problem, the users, the requirements, the scope and how each requirement is built and tested. The sources are:
- **Sponsor Q&A:** [`Hackathon_Discovery_Log_solutionauts.xlsx`](Hackathon_Discovery_Log_solutionauts.xlsx), 36 questions answered by the sponsor (Q-001–Q-036) and 14 follow-ups (Q-037–Q-050), plus a **Gap review** sheet. A summary is in [`sponsor-answers.md`](sponsor-answers.md).
- **User stories:** [`../stories.md`](../stories.md) (US-01–US-12).
- **Business rules:** [`rules.csv`](../../data/synthetic/seed/rules.csv) (R01–R24).

Labels used below:
- **[S]** = sponsor policy or sponsor estimate from the Q&A.
- **[T]** = team assumption, still awaiting sponsor confirmation.
- **[M]** = measured by us.

## 1. Problem

Boston University receives **more than 800 transfer students a year**. Every course on their earlier transcripts must be evaluated for BU credit. Today this is slow, manual and invisible to the student.

| Baseline (today) | Value | Source |
| --- | --- | --- |
| Transfer courses evaluated per year | ~8,000 (800 students × 10 courses) | [S] Q-002 |
| Courses that are a "maybe" (no existing equivalency) | 35 % (~2,800 a year) | [S] Q-002 |
| Days until credit is posted | ~7 for an existing match, **~60 for a maybe**, ~45 on average | [S] Q-003, Q-014 |
| Evaluator time per syllabus comparison | **12 minutes**, so ~560 evaluator hours a year on maybe courses | [S] Q-004 |
| Evaluators | 12 (2 per department × 6), ~120 reviews each per term | [S] Q-036 |
| Maybe courses whose syllabus never arrives | ~10 % | [S] Q-035 |

**Biggest pain [S] Q-012.** Evaluation delays, caused by missing syllabi and by comparing the same courses by hand again and again. The most visible symptom is that students do not know their credit status.

**Where the manual work is [S] Q-015**, in order:
1. Course comparison.
2. Chasing missing syllabi.
3. Typing in transcripts.

Credit conversion and posting are mostly rule-based.

**Business reason.** Students cannot plan their first BU semester while credit is pending. Faculty time goes into repeat comparisons, and evaluators answer "where is my credit?" emails ([S] Q-010).

## 2. Users and what they need

| User | Today | Needs from the solution | Source |
| --- | --- | --- | --- |
| **Transfer student** | Sees TP ("under review") for weeks; no idea what is missing | Secured vs pending credit, a plain status and next step per course, exactly which document is missing, an upload link | Q-023, Q-006, Q-020 |
| **Department evaluator** | Reads each syllabus against the BU catalog by hand, often for a course already decided | The comparison already done (outcomes covered and missing, overlap %, past decisions), one-click decisions, batch approval for clear matches, an override | Q-010, Q-011, Q-021 |
| **Credit Evaluation staff** | Chase syllabi by email; apply eligibility rules by hand | Automatic eligibility rules, automatic syllabus requests and reminders, exceptions only | Q-019, Q-020 |
| **Registrar** | Re-keys results into MyBU | Approved credit as a MyBU-style CSV, posted in one step | Q-006, Q-024 |
| **Advisor** | Cannot see approved-but-not-posted credit | "Approved – awaiting posting", read-only | Q-006 |

## 3. Functional requirements and traceability

Every key requirement maps to a feature and to automated tests. The tests are in `backend/tests/`; e2e means `frontend/e2e/demo.spec.ts`.

| ID | Requirement | Source | Rules | Feature (where) | Tested by |
| --- | --- | --- | --- | --- | --- |
| FR-01 | A student or credit staff uploads a transcript PDF; every course line is read | Q-019, Q-031; US-01 | — | Upload on the student status page; `app/ingest.py` | `test_upload_transcript`, `test_all_transcripts_parse_to_index_counts`, `test_ocr_text_of_a_scanned_transcript_parses_like_the_text_pdf` |
| FR-02 | Ineligible courses are resolved automatically with a reason code: accreditation, course type, 1-credit, P/F, grade below C, age | Q-008, Q-022; US-04 | R01–R07 | Rules engine `app/rules.py` | `test_T03_c_minus_no_credit`, `test_T04_developmental_math_no_credit`, `test_T08_pass_fail`, `test_T09_age_review`, `test_T10_non_accredited`, `test_expected_line` (56 lines) |
| FR-03 | Units are the student's units; quarter credits × 2/3; codes T / TX, BU course, TR elective, TFRGEN NOCRDT | Q-022, Q-030; US-02 | R08, R09, R24 | Rules engine | `test_T01_three_credit_semester_film_course_elective`, `test_T02_quarter_conversion`, `test_T05_lab_units_are_students_units` |
| FR-04 | The equivalency table is checked first; an approved reusable decision is applied to the next student without review | Q-001, Q-028; US-07 | R10 | Own equivalency table with a reusable flag | `test_T15_reuse_after_approval`, `test_non_reusable_decision_only_for_waiting_students` |
| FR-05 | Conflicting past decisions: newest for the same catalog years wins, conflict flagged; a duplicate course gets elective only | Q-022; US-08 | R11, R12 | Rules engine | `test_T12_superseded_decision`, `test_T13_same_year_conflict`, `test_T06_duplicate_becomes_elective` |
| FR-06 | Residency rules and the 68-unit cap block the requirement, not the credit | Q-034, Q-008 | R13–R17 | Rules engine (flags) | `test_T07_cs_group_c_residency`, `test_T11_68_unit_cap`, `test_T14_econ_cap_not_applied_before_matriculation`, `test_R15_econ_cap_applies_after_matriculation` |
| FR-07 | For each maybe course: top-3 BU candidates with overlap %, tier (≥ 80 / 50–79 / < 50), outcomes covered and missing, similar past decisions | Q-007, Q-010, Q-018; US-05 | R20 | Matcher `app/matcher.py`; evaluator workbench | `test_top3_shape_and_evidence`, `test_ai_tiers_match_expected_for_syllabus_on_file`, e2e "evaluator decides a maybe course with the comparison already done" |
| FR-08 | A decision needs a complete syllabus; a description gives a preliminary suggestion only | Q-018; US-03 | R22 | Workbench marks preliminary items and blocks the decision | `test_a_course_without_a_complete_syllabus_cannot_be_decided`, `test_preliminary_without_complete_syllabus`, e2e "a course without a syllabus is preliminary and not decidable" |
| FR-09 | Matches above 90 % can be approved as a reviewed batch, each logged per course | Q-011; US-06 | R21 | Batch approve in the workbench | `test_batch_threshold`, `test_batch_decisions_pass_validation` |
| FR-10 | Missing syllabus → TS, incomplete → TM; the student is asked automatically and reminded, with an upload link | Q-020, Q-027, Q-035; US-03 | R23 | Automatic request on upload; reminders; email and in-app | `test_upload_asks_once_for_maybe_courses_without_a_complete_syllabus`, `test_reminders_stop_when_the_syllabus_arrives`, `test_T16_incomplete_syllabus` |
| FR-11 | The student sees secured vs pending units, a plain-words status and next step for every course | Q-012, Q-023; US-01 | — | Student status page, notifications | e2e "student sees secured vs pending and every course status", `test_the_students_journey_shows_up_newest_first` |
| FR-12 | Department decision → posting (at once since 2026-10-30, with the Registrar's posting step as the safety net); the student sees TP only until posted; the advisor sees "Approved – awaiting posting" | Q-006; US-10 | — | Auto-posting on decision, Registrar page posting step | `test_demo_step8_approve_posts_straight_away`, `test_failed_posting_keeps_the_decision_and_leaves_it_for_the_registrar`, e2e "an approved course is posted straight away" |
| FR-13 | Approved credit is exported as a MyBU-style CSV | Q-019, Q-024; US-09 | R24 | Registrar export | `test_export_csv`, `test_csv_formula_escaping`, e2e "registrar downloads the MyBU CSV" |
| FR-14 | Every decision is logged with a reason code and who made it | Q-009, Q-021 | — | Audit log; reason codes | `test_decision_audit_records_actor_role`, `test_reason_codes`, `test_decision_validation` |
| FR-15 | AI quality is measured on held-out past decisions | Q-025; US-11 | R20 | Evaluation page; `eval/run_eval.py` | `test_T18_quality_gates_on_holdout`, e2e "evaluation page shows the sponsor gates" |
| FR-16 | Credits not transferred within one year are flagged for an Outstanding Transfer Credit Review | Q-008, Q-035 | R19 | Rules engine flag | `test_R19_pending_courses_are_flagged_after_the_one_year_deadline` |
| FR-17 | *Team addition:* anyone can ask "will this course transfer?" without signing in | ADR 0006 | R01–R12 | Public credit check and chat | `test_credit_check.py` (31 tests), `test_credit_chat.py` (38 tests) |

## 4. Non-functional requirements

| ID | Requirement | Target | Status | Evidence |
| --- | --- | --- | --- | --- |
| NFR-01 | **Accuracy** of AI suggestions | Top-1 agreement ≥ 80 %, wrongly suggested credit ≤ 2 % [S] Q-025 | **Met on synthetic data** [M]: 100 % / 0 % (strict agreement 60 %), offline engine | [`eval-report.md`](../quality/eval-report.md) |
| NFR-02 | **Evaluator time** per maybe course | 12 → under 2 minutes [S] Q-010 | **Not measured yet** | Pilot measurement, [roadmap](../roadmap.md) phase 1 |
| NFR-03 | **Privacy (FERPA)**: synthetic data only; no student names, IDs or `gt_*` columns sent to an AI service | [S] Q-024, Q-033 | Met | `test_prompt_contains_course_data_only`, `test_ext_course_has_no_ground_truth_fields`, `test_audit_log_has_no_contact_data` |
| NFR-04 | **Access control**: default deny; a student sees only their own record; a department only its own courses | ADR 0005 | Met (portal and Entra modes) | `test_role_matrix`, `test_student_sees_only_their_own_record`, `test_department_sees_and_decides_only_its_courses`, `test_entra.py` |
| NFR-05 | **AI guardrails**: the AI never posts credit or changes units; it may not decide the 50–79 % band; syllabus text is untrusted | ADR 0001, 0004 | Met | `test_T17_injection_flagged_and_tier_unchanged`, `test_injection_cannot_raise_tier_through_the_model`, `test_grounding_cannot_be_bypassed` |
| NFR-06 | **Input robustness**: bad uploads get a clear message, never a crash | Scorecard 2.2 | Met | See the edge cases in section 8 |
| NFR-07 | **Performance**: status after upload | < 30 s per transcript [T] Q-037 | **Met** [M]: 0.2-0.3 s plus ~0.1 s PDF reading at one year's volume | [`scalability-report.md`](../quality/scalability-report.md) |
| NFR-08 | **Volume**: one year of intake and 10x growth | 8,000 lines a year [S]; 10x plan [T] Q-038 | **Tested to 5x** [M]; the 10x limits and fixes are documented | [`scalability-report.md`](../quality/scalability-report.md), ADR 0007 |
| NFR-09 | **Offline and repeatable**: tests and demo run without Azure | ADR 0003 | Met | `test_offline_engine_by_default`, `test_offline_import_does_not_load_azure`; CI runs offline |
| NFR-10 | **Secrets**: none in the repo; managed identity in Azure | Scorecard 7.3 | Met | `.gitignore`, [`backend/.env.example`](../../backend/.env.example), `test_auth_prefers_managed_identity` |
| NFR-11 | **Abuse limits** on the public check and chat | ADR 0006 | Met | `test_per_ip_rate_limit`, `test_ai_budget_exhausted_is_429`, `test_one_client_cannot_spend_the_global_budget` |
| NFR-12 | **Availability** | Business hours, short outage tolerated outside them [T] Q-039 | Partly: one API replica (ADR 0007) | [Roadmap](../roadmap.md) phase 3 |
| NFR-13 | **Accessibility**: WCAG 2.1 AA, phone-friendly student pages | [T] Q-041 | Phone layouts built; **WCAG not audited** | Roadmap |

## 5. Assumptions

| # | Assumption | Source |
| --- | --- | --- |
| A1 | Overlap tiers: ≥ 80 % equivalent, 50–79 % the evaluator decides, < 50 % elective if eligible | [S] Q-007 |
| A2 | Overlap is weighted by topics and learning outcomes, then level and prerequisites, labs, contact hours, assessments; the grade decides eligibility only | [S] Q-018 |
| A3 | Batch approval is allowed above 90 %, logged per course | [S] Q-011 |
| A4 | Credit Evaluation contacts the student; reminders on days 7, 21 and 45 | [S] Q-020 |
| A5 | About 10 % of maybe courses never get a syllabus | [S] Q-035 |
| A6 | Evaluators accept AI recommendations that show evidence, a confidence level and an override | [S] Q-021 |
| A7 | Answers that sit on the wrong row of the log are read by content (mapping on the Gap review sheet) | [T] Q-048 |
| A8 | Performance, peak load, availability, accessibility, retention and identity targets in section 4 | [T] Q-037–Q-043 |

## 6. Constraints

- **No access to BU systems:** no Transferology, no BU equivalency database, no MyBU API. We build our own equivalency table and a MyBU-style CSV ([S] Q-001, Q-019, Q-024).
- **Synthetic data only:** no real transcripts, names or IDs anywhere, including prompts and logs. Transcripts are FERPA records ([S] Q-024, Q-033).
- **The AI only recommends.** Evaluators make every new equivalency decision ([S] Q-021). Credit math lives only in the rules engine (ADR 0001).
- **Course descriptions are not evidence.** They may drive preliminary suggestions only ([S] Q-018).
- **Hackathon timeline:** one Azure subscription, an Azure OpenAI quota of 10K tokens per minute, and one API replica (ADR 0007).

## 7. Out of scope (for the prototype)

Proposed to the sponsor in Q-044 and listed in the [roadmap](../roadmap.md):
- AP / IB / CLEP and other test credit
- Non-English and international transcripts
- The appeals workflow (Q-008 only says appeals happen in the first year; Q-046)
- Hub / degree-audit mapping: transfer courses earn no Hub units (R18)
- Engineering residency (R16): no Engineering students in the data set
- Live posting to MyBU and import from Transferology (CSV export instead)
- Emailing the seeded sample students: their syllabus requests go to the credit office list

## 8. Edge cases

| Edge case | How it is handled | Tested by |
| --- | --- | --- |
| Non-PDF upload | 415 with a message | `test_non_pdf_is_415` |
| Malformed or encrypted PDF | 422 "could not be read", never 500 | `test_malformed_pdf_is_422_not_500` |
| Oversized upload (declared or streamed) | 413 with the size limit | `test_oversize_upload_413_by_content_length`, `test_oversize_upload_413_when_chunked`, `test_upload_at_limit_is_not_413` |
| PDF with no text, too many pages, or a slow parse | Rejected with a clear message; parse time-out returns 422 | `test_pdf_without_text_is_rejected_with_a_clear_message`, `test_page_limit`, `test_slow_pdf_parse_times_out_with_422` |
| Not a transcript, or a school not in the catalog | 422 naming the problem | `test_non_transcript_and_unknown_school_are_rejected` |
| The same transcript uploaded twice | Recognised as a duplicate; nothing changes | `test_same_transcript_again_is_a_duplicate` |
| A new transcript for the same school | Replaces that school's lines; reports added, removed and changed courses | `test_replacing_transcript_reports_what_changed` |
| A transcript with another student's ID for the same school | Rejected | `test_a_different_id_for_the_same_school_is_rejected` |
| Prompt injection in a course title or syllabus | Title: transcript rejected. Syllabus: flagged, and the tier is unchanged | `test_transcript_with_injected_course_title_is_rejected`, `test_T17_injection_flagged_and_tier_unchanged` |
| A syllabus for a different course | Rejected | `test_syllabus_must_be_a_syllabus_for_this_course` |
| Incomplete syllabus | TM, preliminary, not decidable | `test_T16_incomplete_syllabus` |
| One external course split across two BU courses, or two combined | Shown as a split or combined relationship | `test_T19_split_course_relationship`, `test_T20_combined_chemistry` |
| Quarter-system credits | × 2/3, 2 decimals | `test_T02_quarter_conversion` |
| Grade C-, P/F, 1-credit, remedial, internship, unaccredited school | No credit, TX, reason code | `test_T03_c_minus_no_credit`, `test_T04_developmental_math_no_credit`, `test_T08_pass_fail`, `test_T10_non_accredited`, `test_expected_line` |
| Course 5+ years old | Pending review | `test_T09_age_review` |
| Duplicate course | Elective only | `test_T06_duplicate_becomes_elective` |
| Conflicting decisions in the same catalog year | Newest wins, conflict flagged | `test_T13_same_year_conflict` |
| Over the 68-unit cap | Units beyond the cap don't count | `test_T11_68_unit_cap` |
| AI model fails, times out or returns invalid output | Falls back to the offline matcher; never a crash | `test_invalid_output_falls_back_to_offline`, `test_client_error_falls_back`, `test_model_failure_is_502_not_a_crash` |
| Wrong role or another student's record | 401 / 403, no side effect | `test_role_matrix`, `test_refusal_has_no_side_effect`, `test_student_sees_only_their_own_record` |
| Formula injection in exported CSV cells | Cells prefixed so Excel does not evaluate them | `test_csv_formula_escaping` |
| Email service down | Request recorded and retried at the next check | `test_a_failed_reminder_is_retried_at_the_next_check`, `test_a_failed_email_is_recorded_and_retried_on_the_next_upload` |
| Large volume (5x one year) | Measured; export and queue indexed by student | [`scalability-report.md`](../quality/scalability-report.md) |

## 9. Known differences from discovery

- **Reminder schedule.** The sponsor asked for reminders on days 7, 21 and 45 (Q-020). The app reminds every 2 days, at most 7 times. Both settings are configurable (`TRANSFERIQ_SYLLABUS_REMINDER_DAYS` / `_MAX`); a fixed 7/21/45 schedule is on the roadmap.
- **Evaluator time** (NFR-02) and the **Azure OpenAI engine's accuracy** are not measured yet. The accuracy figures come from the offline engine on synthetic data.

## 10. Open questions

The 14 follow-ups Q-037–Q-050 on the discovery log, mainly:
- performance and peak-load targets
- data retention and audit access
- production sign-in
- the out-of-scope list
- the Q-032 re-ask on decision reuse
- the MyBU import format

The team works from the assumptions in section 5 until they are answered.
