#!/bin/zsh
# pair.sh NAME ICAO — gap-free base with --null-change + --solved-out, late pair, pad_edge_read (reverify's pair.sh form) on the pass2 tree
NAME=$1; ICAO=$2
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/pass2/Ortho4XP
CAP=/Users/noah/XPTerrainBuilderData/.harness/frames/pads67/$ICAO.pkl
D=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/$NAME; mkdir -p $D
venv/bin/python -u tools/v2_solve_replay.py --replay $CAP --from classify --gap-free --workers 9 --solved-out $D/base_gf.pkl --null-change --json $D/base_gf.json > $D/base_gf.log 2>&1 || { echo "base_gf FAILED"; exit 1; }
grep "NULL-CHANGE" $D/base_gf.log
venv/bin/python -u tools/v2_solve_replay.py --replay $CAP --from classify --workers 9 --late-from $D/base_gf.pkl --emit $D/emit --json $D/late.json > $D/late.log 2>&1 || { echo "late FAILED"; exit 1; }
venv/bin/python tools/pad_edge_read.py $D/emit/$ICAO.graded.json --capture $CAP --json $D/edge.json > $D/edge.txt 2>&1
echo pair done
