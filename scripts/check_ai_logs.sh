#!/usr/bin/env bash
# AI-log rule (AGENTS.md "Logging is mandatory"), enforced by CI job `log-check`:
#   If a push / PR range changes any file under backend/, frontend/src/ or infra/,
#   the SAME range must also add or change at least one file under ai-logs/.
# Usage: scripts/check_ai_logs.sh <base-sha> <head-sha>
# A missing/all-zero base (new branch) falls back to checking only the head commit.
set -euo pipefail

base="${1:-}"
head="${2:-HEAD}"

if [[ -z "$base" || "$base" =~ ^0+$ ]] || ! git cat-file -e "${base}^{commit}" 2>/dev/null; then
  echo "No usable base commit; checking only ${head}."
  changed="$(git diff-tree --no-commit-id --name-only -r --root "$head")"
else
  changed="$(git diff --name-only "$base" "$head")"
fi

code="$(grep -E '^(backend/|frontend/src/|infra/)' <<<"$changed" || true)"
logs="$(grep -E '^ai-logs/' <<<"$changed" || true)"

if [[ -z "$code" ]]; then
  echo "OK: no changes under backend/, frontend/src/ or infra/."
  exit 0
fi
if [[ -n "$logs" ]]; then
  echo "OK: code changes are accompanied by AI log(s):"
  echo "$logs" | sed 's/^/  /'
  exit 0
fi

echo "::error::Code changed without an AI log. Add ai-logs/<YYYY-MM-DD>/<agent>-<NN>.md (see ai-logs/TEMPLATE.md)."
echo "Changed code files:"
echo "$code" | sed 's/^/  /'
exit 1
