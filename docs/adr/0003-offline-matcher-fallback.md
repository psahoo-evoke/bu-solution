# ADR 0003 · Matcher has an offline fallback

**Status:** accepted (2026-10-28)

**Context.** CI and the live demo must not depend on Azure quota or network. The quality gates must still be measurable.

**Decision.** `matcher.py` exposes one interface with two engines: `azure-openai` (when `AZURE_OPENAI_ENDPOINT` is set) and `offline-fallback` (lexical topic/outcome overlap). Metrics report which engine produced them.

**Consequences.** Fallback numbers are a floor, not the production claim. The deck must say which engine produced each number.
