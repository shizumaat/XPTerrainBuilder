#!/bin/zsh
# cen.sh TREE_NAME PATCH OUTNAME — harness census of one patch on the named worktree (each tree's own census)
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/reverify
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/$1/Ortho4XP
venv/bin/python tools/harness/census.py $2 --json $S/cen/$3.json --quiet > $S/cen/$3.txt 2>&1
echo "== census $3 rc $? $(date +%T)" >> $S/.progress; touch $S/cen/$3.DONE
