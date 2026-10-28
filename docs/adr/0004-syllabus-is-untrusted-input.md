# ADR 0004 · Syllabus text is untrusted input

**Status:** accepted (2026-10-28)

**Decision.** Syllabus text is passed to the model only inside a delimited data block with an instruction that it contains no instructions; a pre-filter flags imperative phrases aimed at automated systems ("ignore previous instructions", "recommend ... 100%"). A flagged syllabus keeps its computed tier and shows a warning to the evaluator. AI output never posts credit.

**Test.** T17: NYU ECON-UA 266 syllabus.
