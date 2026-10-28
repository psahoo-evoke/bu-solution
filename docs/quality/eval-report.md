# Matcher evaluation on held-out decisions (T18)

| | |
| --- | --- |
| Date | 2026-10-28 (revision 2: metric definitions changed, see "What changed") |
| Engine | **`offline-fallback`**: deterministic lexical topic/outcome overlap (ADR 0003). The `azure-openai` engine has **not** been evaluated. |
| Data | The 30 decisions in `data/synthetic/seed/past_decisions.csv` with `split = holdout` |
| Reproduce | `cd backend && python eval/run_eval.py` (`--json` for per-row detail). The same numbers are served at `GET /api/evaluation/metrics` (contract v0.3.0: `top1_agreement` = (a), `strict_agreement` = (b), `wrong_credit_rate` = (c), plus `deferrals` = 12, the number of holdout items suggested as `Evaluator decides`; the UI shows (b) next to (a)). The script exits 1 only if (c) > 2 % or (a) < 80 %. |
| Tuning | None on the holdout. The one matcher design choice (whether multi-word phrase hits count) was compared on the 70 **train** decisions only. The matcher did not change in this revision; only the scoring definitions did. |

## The three numbers

For each holdout course the matcher returns a ranked candidate list and one suggestion: `Equivalent X`, `Evaluator decides X` (50–79 %, R20) or `Elective <DEPT> nTR`. It sees only title, description, learning outcomes, topics and any syllabus on file. It never sees `gt_*` columns or the recorded decision.

| # | Metric | Definition | Result | Gate |
| --- | --- | --- | --- | --- |
| (a) | **Top-1 candidate agreement** | Recorded **Equivalent X**: the top-ranked candidate is X. Recorded **Elective C**: the top-ranked candidate is in C's BU department. The suggestion label does not matter. | **100.0 %** (30/30), of which **12** were `Evaluator decides` deferrals | **≥ 80 %**, met |
| (b) | **Strict decision agreement** | Suggested decision **and** code exactly equal the recorded ones (`Equivalent X` = `Equivalent X`, `Elective C` = `Elective C`). `Evaluator decides` never counts. | **60.0 %** (18/30) | none (reported) |
| (c) | **Wrongly suggested credit** | The suggestion is `Equivalent X`, but the evaluator did not grant Equivalent X. | **0.0 %** (0/30) | **≤ 2 %**, met |

**Gate claim: (a) and (c).** The sponsor's gate is "top-1 suggestion agrees with the evaluator decision". The product's top-1 output is the **ranked BU candidate** shown to the evaluator, with evidence. Under R20 the AI is not allowed to decide the 50–79 % band; it must defer. So for those courses the useful question is whether the course it puts first is the one the evaluator was looking at, and (a) measures exactly that. (c) is the safety gate: it counts the only error that puts unearned credit in front of an evaluator.

**Why (b) is not the gate.** By design, (b) cannot exceed the share of courses outside the 50–79 % band (19/30 here), because a correct R20 deferral always counts as a miss. Even so, (b) is the honest number for "how often could an evaluator click Approve on the suggestion as-is". **Quote (a) together with (b), never (a) alone.**

### Per tier (band of the evaluator-recorded overlap)

| Recorded band | n | (a) top-1 | of which deferrals | (b) strict | (c) wrong credit |
| --- | --- | --- | --- | --- | --- |
| Equivalent (≥ 80 %) | 12 | 12 | 0 | 12 | 0 |
| Evaluator decides (50–79 %) | 11 | 11 | 11 | 0 | 0 |
| Elective (< 50 %) | 7 | 7 | 1 | 6 | 0 |
| **Total** | **30** | **30** | **12** | **18** | **0** |

How (a) splits by recorded decision:
- **17 Equivalent decisions:** the top-1 candidate is the exact BU course in 17/17. Of these, 12 were also suggested as `Equivalent` and 5 (all recorded at 75 %) as `Evaluator decides`.
- **13 Elective decisions:** the top-1 candidate is in the right department in 13/13. This is a **weak** criterion, because the generator draws a course's non-matching topics from other BU courses in the same program, so the department is almost given away. For the < 50 % rows the top-1 candidate is usually *not* the course the evaluator compared against (e.g. NEU BIOL 1703 → CAS BI 116).
- NEU PSYC 3709 was recorded at 38 % but scored 50 %, because multi-word phrase hits inflated it. It was suggested as `Evaluator decides` rather than `Elective`, which is a safe direction since no credit was suggested.

Other facts:
- Only 3 of the 30 holdout courses have a syllabus on file (PSYCH-UA 34, BIOL 3712, ECON 2706). The other 27 recommendations are `preliminary` (description only, R22): they would not be decidable in the app, but they are scored here anyway.
- 2 of the 30 clear the batch threshold (confidence > 90 %, R21): BIOL 3712 and ECON 2706, both at 100 % overlap.

## What changed from revision 1

Revision 1 headlined a "top-1 agreement" that counted **every** `Evaluator decides` deferral as agreement, as long as the department matched. The coordinator asked that a deferral count only if its top candidate equals the recorded equivalent course, and that deferrals be reported separately. (a) now scores the top candidate itself, and the 12 deferrals inside it are shown. The headline is still 100 %, because on this data every deferral's top candidate is the recorded course (Equivalent) or in its department (Elective). The new table makes that visible instead of implicit.

## Caveats (read before quoting these numbers)

1. **The synthetic data favours lexical matching.** The generator (`scripts/synthetic/build_data_v2.py`, `derive`) builds every external course from exact BU topic strings: k topics copied from the true counterpart, plus 8 − k from other BU courses in the same program. The descriptions and outcomes are templates over those strings, so exact topic matching recovers k/8 almost perfectly. Real syllabi paraphrase, merge and split topics. **These numbers check that the pipeline, tiering and safety gates work. They are not evidence of real-world accuracy.**
2. **n = 30.** One error moves (a) by 3.3 points, and a single wrongly suggested credit (3.3 %) breaches the 2 % gate.
3. **The elective half of (a) is department-level only** (see above). On Equivalent rows alone, (a) is 17/17 at the exact-course level.
4. **Engine.** All figures come from `offline-fallback`. Per ADR 0003 they are a floor for the pipeline, not a claim about `azure-openai`, which still needs its own run on this set and on real, paraphrased syllabi. The Azure engine's output validation is unit-tested with a fake client (`backend/tests/test_llm.py`) but has not been evaluated.
