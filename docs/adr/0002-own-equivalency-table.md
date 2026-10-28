# ADR 0002 · Own equivalency table and CSV posting instead of BU integration

**Status:** accepted (2026-10-28)

**Context.** Sponsor: no access to Transferology or BU's equivalency DB; no MyBU integration; synthetic data only.

**Decision.** PostgreSQL `decisions` table is the equivalency source (reason code, reusable flag, catalog year). Posting = MyBU-style CSV export.

**Consequences.** Conflicts resolved by "newest catalog year wins; same-year conflict flagged" (R11). A real deployment would swap the table for a BU adapter.
