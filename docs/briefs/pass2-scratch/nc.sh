#!/bin/zsh
# nc.sh NAME TREE CAPTURE [extra] — gap-free base --null-change on TREE
N=$1; T=$2; C=$3; shift 3
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/$T/Ortho4XP
venv/bin/python -u tools/v2_solve_replay.py --replay $C --from classify --gap-free --workers 9 --null-change --json /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/$N.json "$@"
