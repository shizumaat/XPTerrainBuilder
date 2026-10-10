#!/bin/zsh
# cen.sh NAME PATCH — harness census with row dump, on the pass2 tree
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/pass2/Ortho4XP
venv/bin/python tools/harness/census.py $2 --json /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/cen/$1.json --rows-json /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/cen/$1.rows.json --quiet
