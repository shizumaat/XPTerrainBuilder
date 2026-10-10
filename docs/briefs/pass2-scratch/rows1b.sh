#!/bin/zsh
I=$1; N=$2; K=$3; shift 3
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/pass2/Ortho4XP
venv/bin/python -u /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/rows1b.py /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/${I}_prob.pkl $N $K --workers 9 "$@"
