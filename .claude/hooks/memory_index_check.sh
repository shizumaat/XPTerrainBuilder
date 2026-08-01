#!/bin/bash
# SessionStart: warn (into context) if any memory file is missing from the
# MEMORY.md index — an unindexed memory is never recalled. Non-blocking.
MEM="$HOME/.claude/projects/-Users-noah-XPTerrainBuilder/memory"
[ -d "$MEM" ] && [ -f "$MEM/MEMORY.md" ] || exit 0

orphans=""
for f in "$MEM"/*.md; do
  b=$(basename "$f")
  [ "$b" = "MEMORY.md" ] && continue
  grep -q "($b)" "$MEM/MEMORY.md" || orphans="$orphans $b"
done

if [ -n "$orphans" ]; then
  echo "MEMORY INDEX DRIFT: these memory files are absent from MEMORY.md and will never be recalled:$orphans — add a one-line pointer for each now."
fi
exit 0
