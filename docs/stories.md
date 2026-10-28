# User stories (BA / Discovery agent)

Rule IDs refer to `data/synthetic/seed/rules.csv`.

| ID | As a | I want | So that | Acceptance (Given / When / Then) | Rules |
| --- | --- | --- | --- | --- | --- |
| US-01 | Student | to upload my transcript and see every course's status at once | I know what is secured and what is pending | Given Maya's NYU + PSC transcripts, when uploaded, then 6 lines appear with status, BU course or next step, and secured vs pending units | R08–R10, R24 |
| US-02 | Student | a quarter-system course converted correctly | my units are right | Given 4 quarter credits with a B and no equivalent, then 2.67 elective units, code ending TR | R08, R09, R24 |
| US-03 | Student | to know exactly which document is missing | I can fix it quickly | Given no syllabus, then status TS, an upload link and reminders on days 7, 21, 45 | R22, R23 |
| US-04 | Credit staff | ineligible courses resolved automatically | I only handle exceptions | Given C-, P/F, 1-credit, remedial, PE, ROTC, internship, research or unaccredited school, then no credit, TX, with reason code | R01–R06 |
| US-05 | Evaluator | the comparison already done for each maybe course | I decide in under 2 minutes | Given a complete syllabus, then top-3 BU candidates with overlap %, tier, outcomes covered/missing and similar past decisions | R20 |
| US-06 | Evaluator | to approve > 90% recommendations as a batch | I skip obvious cases | Given items > 90%, when batch-approved, then each course gets its own logged decision | R21 |
| US-07 | Evaluator | my decision reused for the next student | I never decide the same course twice | Given an approved reusable decision, when another student has that course, then it matches instantly | R10 |
| US-08 | Department | conflicting past decisions flagged | we stay consistent | Given two decisions in the same catalog year, then the newest applies and a conflict flag shows | R11 |
| US-09 | Registrar | a MyBU-style CSV of approved courses | posting is one step | When exported, then rows contain BU course or TR code, units, grade T/TX | R24 |
| US-10 | Advisor | to see approved-but-not-posted credit | I can plan registration | Then status "Approved – awaiting posting" and forecast are visible read-only | — |
| US-11 | Product owner | the AI quality measured on held-out decisions | we can prove the gates | Then the evaluation page shows top-1 agreement and wrong-credit rate on 30 holdout decisions | R20 |
| US-12 | Security | syllabus text treated as untrusted | injected instructions cannot grant credit | Given the ECON-UA 266 syllabus, then the tier is unchanged and the injection is flagged | — |
