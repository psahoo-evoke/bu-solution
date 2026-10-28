# ADR 0001 · Credit rules live in a deterministic engine, not in prompts

**Status:** accepted (2026-10-28)

**Context.** The sponsor gave ~24 rules (eligibility, quarter x 2/3 rounded to 2 decimals, 68-unit cap, residency, codes). Credit math must be exact and auditable.

**Options.** (a) Ask the LLM to apply rules; (b) rules in Python with tests; (c) rules engine product.

**Decision.** (b). Each rule cites its ID (R01–R24) and is covered by tests generated from `transcript_lines_expected.csv`.

**Consequences.** AI is limited to reading documents and judging similarity. Rules change by code + test, not prompt edits.
