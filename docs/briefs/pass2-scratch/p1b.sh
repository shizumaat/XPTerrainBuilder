#!/bin/zsh
# p1b.sh NAME ICAO [p1b args] — stage-1 null pair on the pass2 tree
N=$1; I=$2; shift 2
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/pass2/Ortho4XP
venv/bin/python -u /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/p1b.py /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/${I}_prob.pkl $N --workers 9 "$@"
