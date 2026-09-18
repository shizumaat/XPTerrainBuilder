#!/usr/bin/env bash
# THE BETA-2 BLOCKER GATE (owner standing 2026-09-18).
#
# docs/BETA2-BLOCKERS.md is the beta 1 feedback list.  No `-beta.N` tag with
# N >= 2 (and no plain release tag) may be cut while any row of its table is
# in a state other than CLOSED or WAIVED.  scripts/check_tag_version.sh calls
# this in the first step of every release job; run it by hand before tagging.
#
# Usage: scripts/check_beta_blockers.sh [tag] [blockers-file]
#   [tag]  v1.0.360-beta.2 etc.  Omitted: always enforce (the by-hand check).
#          A `-beta.1` tag passes with a note (beta 1 predates the list).
#
# bash, not zsh: runs on the Windows and Linux release runners too.
set -euo pipefail

TAG="${1:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="${2:-$HERE/docs/BETA2-BLOCKERS.md}"

if [[ "$TAG" =~ -beta\.1$ ]]; then
  echo "beta.1 tag — blocker list not enforced"
  exit 0
fi

if [[ ! -f "$FILE" ]]; then
  echo "ERROR: blocker list not found: $FILE (a missing list is a refusal, not a pass)" >&2
  exit 1
fi

# Table rows: | ID | Status | ...   with ID like GEN-1, OTHH-6.
ROWS="$(grep -E '^\| *[A-Z]+-[0-9]+ *\|' "$FILE" || true)"
TOTAL="$(printf '%s\n' "$ROWS" | grep -c . || true)"
if [[ "$TOTAL" -lt 23 ]]; then
  echo "ERROR: $FILE has $TOTAL blocker rows; the beta 1 list has 23 — rows are never deleted" >&2
  exit 1
fi

BAD="$(printf '%s\n' "$ROWS" | awk -F'|' '{
  id=$2; st=$3; gsub(/^ +| +$/, "", id); gsub(/^ +| +$/, "", st);
  if (st != "CLOSED" && st != "WAIVED") printf "  %-8s %s\n", id, st }')"

if [[ -n "$BAD" ]]; then
  echo "ERROR: beta 2 is blocked — rows not CLOSED/WAIVED in docs/BETA2-BLOCKERS.md:" >&2
  printf '%s\n' "$BAD" >&2
  exit 1
fi

echo "beta blockers: all $TOTAL rows CLOSED/WAIVED"
